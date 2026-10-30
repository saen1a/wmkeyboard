#!/usr/bin/env python3
"""vLLM-offline soft-target collector for the H100 teacher run.

Same output contract as `tools/wmlm/distill.py` (patch 0005, `multi=1`):
`sentences` int32 indices into `train.npz`, `starts` int64, `ids` int16
`[rows, topk]`, `probs` float16 `[rows, topk]`, row `k` of a sentence the
teacher's next-word distribution after word `k-1`, row 0 zeros. So
`tools/wmlm/merge_soft.py`, `check_soft.py` and `train.py distill=` work
unchanged.

Differences to `distill.py`, all deliberate:
- vLLM instead of `transformers`: batched prefill is where the H100 wins.
  `prompt_logprobs=topk` carries the distribution; no MTP / speculative
  decoding (`LLM` is built without `speculative_config`, and the script
  refuses to run if one is active).
- Sharded and resumable: one `.npz` per shard of `--shard-size` sentences,
  validated by `check_soft.py`; a shard is skipped when it already
  validates, and a partial checkpoint inside a shard is kept every
  `--checkpoint-every` sentences, so a crash costs at most that many.
- Per-sentence validation and retries: non-finite logprobs, a missing
  actual token, mean NLL > `--max-nll` (default 12), no usable soft rows,
  or an engine exception are retryable; every attempt is appended to a
  failure JSONL. HTTP-200-style "looks fine but is corrupt" is what this
  catches (the Chutes/vLLM MTP bug produced exactly that).
- `--retry-failures`: second pass over the sids in a failure JSONL; the
  affected shards are patched in place (atomically) and re-validated.

Examples:
    # pass 1: 1.2M sentences, 240 shards of 5k
    python3 distill_vllm.py out/de_lm_1m2 out/de_soft_1m2.npz \
        --model Qwen/Qwen3.8-27B-FP8 --sentences 1200000 --shard-size 5000 \
        --attempts 3

    # pass 2: only what failed, in the same shard layout
    python3 distill_vllm.py out/de_lm_1m2 out/de_soft_1m2.npz \
        --model Qwen/Qwen3.8-27B-FP8 --sentences 1200000 --shard-size 5000 \
        --retry-failures out/de_soft_1m2_shards/failures.jsonl --attempts 10

    # offline check of the prompt/row path, no GPU
    python3 distill_vllm.py out/de_lm_2m /tmp/x.npz --dry-run 3
"""
import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np

import vllm_common as vc

SOFT_KEYS = ("sentences", "starts", "ids", "probs")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_npz(path, sentences, starts, ids, probs):
    tmp = path + ".tmp.npz"
    np.savez(
        tmp,
        sentences=np.asarray(sentences, dtype=np.int32),
        starts=np.asarray(starts, dtype=np.int64),
        ids=np.asarray(ids, dtype=ids.dtype),
        probs=np.asarray(probs, dtype=np.float16),
    )
    os.replace(tmp, path)


def load_npz(path):
    z = np.load(path, allow_pickle=False)
    return {k: z[k] for k in SOFT_KEYS}


def valid_soft(path, vocab_size, expect=None, min_mass=0.0):
    """check_soft.py's validator, imported from the repo when available."""
    here = os.path.dirname(os.path.abspath(__file__))
    tools = os.path.abspath(os.path.join(here, "..", "..", "tools"))
    if tools not in sys.path:
        sys.path.insert(0, tools)
    try:
        from check_soft import validate_soft  # noqa: PLC0415
    except Exception:  # noqa: BLE001 - fall back to the local structural check
        validate_soft = None
    if validate_soft is not None:
        try:
            validate_soft(path, vocab_size=vocab_size, expect_sentences=expect, min_mass_ratio=min_mass)
            return True, None
        except Exception as e:  # noqa: BLE001
            return False, str(e)
    try:
        z = load_npz(path)
    except Exception as e:  # noqa: BLE001
        return False, f"cannot load: {e}"
    if len(z["starts"]) != len(z["sentences"]) + 1:
        return False, "starts/sentences mismatch"
    if len(z["starts"]) and z["starts"][-1] != len(z["ids"]):
        return False, "starts[-1] != rows"
    if expect is not None and len(z["sentences"]) != expect:
        return False, f"{len(z['sentences'])} sentences, expected {expect}"
    return True, None


def split_blocks(z):
    """sid -> (ids rows, probs rows) out of a partial/shard npz."""
    out = {}
    s, st = z["sentences"], z["starts"]
    for i, sid in enumerate(s):
        lo, hi = int(st[i]), int(st[i + 1])
        out[int(sid)] = (z["ids"][lo:hi], z["probs"][lo:hi])
    return out


def pack_blocks(blocks, topk, id_dtype=np.int16):
    sids = sorted(blocks)
    starts = [0]
    ids, probs = [], []
    for sid in sids:
        a, b = blocks[sid]
        ids.append(a)
        probs.append(b)
        starts.append(starts[-1] + len(a))
    ids = np.concatenate(ids) if ids else np.zeros((0, topk), id_dtype)
    probs = np.concatenate(probs) if probs else np.zeros((0, topk), np.float16)
    return sids, starts, ids, probs


def shard_dir_for(out):
    base = out[:-4] if out.endswith(".npz") else out
    return base + "_shards"


def shard_path(shard_dir, prefix, i):
    return os.path.join(shard_dir, f"{prefix}_{i:05d}.npz")


def read_failures(path):
    sids = []
    seen = set()
    if not os.path.exists(path):
        return sids
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if rec.get("event") != "failed":
                continue
            sid = rec.get("sid")
            if isinstance(sid, int) and sid not in seen:
                seen.add(sid)
                sids.append(sid)
    return sorted(sids)


class Collector:
    def __init__(self, args, vocab, tokens, starts, mapping, by_first):
        self.a = args
        self.vocab = vocab
        self.tokens = tokens
        self.starts = starts
        self.mapping = mapping
        self.by_first = by_first
        self.topk = args.topk
        self.id_dtype = np.int16 if len(vocab) <= 32767 else np.int32
        self.llm = None
        self.tok = None
        self.stats = {"sentences": 0, "attempts": 0, "failed": 0, "high_nll": 0, "rows": 0, "prompt_tokens": 0}
        self.pending_retry = {}

    # ---------------------------------------------------------------- engine
    def ensure_engine(self):
        if self.llm is not None:
            return
        from vllm import LLM  # noqa: PLC0415
        from transformers import AutoTokenizer  # noqa: PLC0415

        t0 = time.perf_counter()
        self.llm = LLM(
            model=self.a.model,
            max_model_len=self.a.max_model_len,
            gpu_memory_utilization=self.a.gpu_mem,
            max_num_seqs=self.a.max_num_seqs,
            max_logprobs=max(20, self.a.topk),
            trust_remote_code=False,
            tensor_parallel_size=self.a.tensor_parallel,
            enforce_eager=False,
        )
        info = vc.teacher_info(self.llm)
        if info.get("speculative"):
            raise SystemExit(
                f"speculative decoding is active ({info['speculative']}); MTP must be off"
            )
        log(f"model {self.a.model} loaded in {time.perf_counter() - t0:.0f}s: {info}")
        self.tok = AutoTokenizer.from_pretrained(self.a.model, trust_remote_code=False)
        # The student->teacher map must be built with the *teacher's* tokenizer.
        self.mapping = vc.student_to_teacher(
            self.vocab, lambda s: self.tok.encode(s, add_special_tokens=False), multi=bool(self.a.multi)
        )
        self.by_first = vc.index_mapping(self.mapping)
        covered = len({sid for sid, _ in self.mapping})
        log(f"{covered} of {len(self.vocab)} student words map to the teacher (multi={self.a.multi})")

    # ---------------------------------------------------------------- one batch
    def prepare(self, sids):
        out = []
        for sid in sids:
            row = self.tokens[self.starts[sid] : self.starts[sid + 1]]
            text, ends = vc.prompt_text(self.vocab, row)
            if not ends:
                out.append((sid, None, "empty prompt"))
                continue
            enc = self.tok(text, add_special_tokens=False, return_offsets_mapping=True)
            ids = enc["input_ids"]
            if not ids or len(ids) > self.a.max_model_len:
                out.append((sid, None, f"prompt length {len(ids)}"))
                continue
            tok_ends = [o[1] for o in enc["offset_mapping"]]
            out.append((sid, (text, ends, ids, tok_ends), None))
        return out

    def generate(self, prepared):
        from vllm import SamplingParams  # noqa: PLC0415

        sp = SamplingParams(max_tokens=1, temperature=0.0, prompt_logprobs=self.topk)
        inputs = [{"prompt_token_ids": payload[2]} for _sid, payload in prepared]
        outs = self.llm.generate(inputs, sp)
        return outs

    def validate(self, out, ends, ids, tok_ends):
        """(rows, error, soft).

        Hard errors (missing actual token, non-finite logprobs, no rows) mean
        the distribution is unusable and the sentence must be retried or
        dropped. A mean NLL above `--max-nll` is *soft*: the distribution is
        still well formed, it just looks unusual (rare tokens, numbers,
        names). It is retried, and on the last attempt the rows are kept -
        otherwise every shard loses a handful of sentences (~0.08 % measured)
        and the run can never finish cleanly.
        """
        plp = out.prompt_logprobs
        if not plp:
            return None, "no prompt_logprobs", False
        st = vc.sentence_stats(plp, ids)
        if st["missing"]:
            return None, f"missing actual token at {st['missing']} positions", False
        if st["mean_nll"] is None:
            return None, "no usable positions", False
        positions = vc.word_positions(ends, tok_ends)
        if len(positions) < 2:
            return None, "sentence too short for soft rows", False
        rows_ids, rows_probs, rst = vc.rows_from_logprobs(
            plp, len(ids), positions, self.by_first, self.topk, id_dtype=self.id_dtype
        )
        if rst["nonfinite"]:
            return None, f"{rst['nonfinite']} non-finite logprobs", False
        if rst["rows"] == 0:
            return None, "no soft rows with teacher mass", False
        if st["mean_nll"] > self.a.max_nll:
            return (rows_ids, rows_probs), f"mean NLL {st['mean_nll']:.2f} > {self.a.max_nll}", True
        return (rows_ids, rows_probs), None, False

    # ---------------------------------------------------------------- shards
    def process(self, sids, partial_path, prefix, blocks=None):
        """Fill `blocks` (sid -> rows) for `sids`, with attempts and backoff."""
        self.ensure_engine()
        blocks = {} if blocks is None else blocks
        todo = [s for s in sids if s not in blocks]
        done_since_checkpoint = 0
        for attempt in range(1, self.a.attempts + 1):
            if not todo:
                break
            if attempt > 1:
                delay = self.a.backoff * (2 ** (attempt - 2))
                log(f"retry attempt {attempt}/{self.a.attempts} for {len(todo)} sentences in {delay:.1f}s")
                time.sleep(delay)
            still = []
            for i in range(0, len(todo), self.a.batch):
                chunk = todo[i : i + self.a.batch]
                prepared = []
                for sid, payload, err in self.prepare(chunk):
                    if err:
                        self._record(attempt, sid, err)
                        still.append(sid)
                        continue
                    prepared.append((sid, payload))
                if not prepared:
                    continue
                self.stats["attempts"] += 1
                try:
                    outs = self.generate(prepared)
                except Exception as e:  # noqa: BLE001 - engine failure: retry these
                    log(f"engine error on {len(prepared)} prompts: {type(e).__name__}: {e}")
                    for sid, _payload in prepared:
                        self._record(attempt, sid, f"engine: {type(e).__name__}: {e}")
                        still.append(sid)
                    continue
                for (sid, payload), out in zip(prepared, outs):
                    _text, ends, ids, tok_ends = payload
                    self.stats["prompt_tokens"] += len(ids)
                    got, err, soft = self.validate(out, ends, ids, tok_ends)
                    if err:
                        if soft and attempt >= self.a.attempts:
                            # Well-formed but unusual; keep the rows and record it.
                            blocks[sid] = got
                            self.stats["sentences"] += 1
                            self.stats["rows"] += len(got[0])
                            self.stats["high_nll"] += 1
                            vc.append_jsonl(self.a.failures, {
                                "event": "high_nll", "sid": sid, "attempt": attempt,
                                "error": err, "model": self.a.model, "ts": time.time(),
                            })
                            done_since_checkpoint += 1
                            continue
                        self._record(attempt, sid, err)
                        still.append(sid)
                        continue
                    blocks[sid] = got
                    self.stats["sentences"] += 1
                    self.stats["rows"] += len(got[0])
                    done_since_checkpoint += 1
                    if done_since_checkpoint >= self.a.checkpoint_every:
                        self.checkpoint(partial_path, blocks)
                        done_since_checkpoint = 0
                        log(
                            f"{self.stats['sentences']} sentences done, "
                            f"{self.stats['rows']} rows, {self.stats['failed']} permanent failures"
                        )
            todo = still
        if blocks:
            self.checkpoint(partial_path, blocks)
        if todo:
            log(f"{len(todo)} sentences still failing after {self.a.attempts} attempts")
        return blocks

    def _record(self, attempt, sid, err):
        event = "retry" if attempt < self.a.attempts else "failed"
        if event == "failed":
            self.stats["failed"] += 1
        else:
            log(f"retryable sid {sid} (attempt {attempt}): {err}")
        vc.append_jsonl(self.a.failures, {
            "event": event, "sid": sid, "attempt": attempt, "error": err,
            "model": self.a.model, "ts": time.time(),
        })

    def checkpoint(self, partial_path, blocks):
        if not blocks:
            return
        sids, starts_out, ids, probs = pack_blocks(blocks, self.topk, self.id_dtype)
        save_npz(partial_path, sids, starts_out, ids, probs)


def dry_run(args, vocab, tokens, starts, chosen, n):
    print(f"chosen: {len(chosen)} sentences, seed {args.seed}", flush=True)
    for sid in chosen[:n]:
        row = tokens[starts[sid] : starts[sid + 1]]
        text, ends = vc.prompt_text(vocab, row)
        print(f"--- sid {int(sid)} words {len(ends)} chars {len(text)}")
        print(text)
    print("--- dry run: no model loaded, no npz written")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data_dir")
    ap.add_argument("out")
    ap.add_argument("--model", default="Qwen/Qwen3.8-27B-FP8")
    ap.add_argument("--sentences", type=int, default=0, help="0 = all sentences in train.npz")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=0)
    ap.add_argument("--topk", type=int, default=24)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--multi", type=int, default=1)
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--backoff", type=float, default=2.0)
    ap.add_argument("--max-nll", type=float, default=12.0)
    ap.add_argument("--shard-size", type=int, default=5000)
    ap.add_argument("--checkpoint-every", type=int, default=500)
    ap.add_argument("--shard-dir", default="")
    ap.add_argument("--prefix", default="")
    ap.add_argument("--failures", default="")
    ap.add_argument("--retry-failures", default="")
    ap.add_argument("--no-resume", action="store_true")
    ap.add_argument("--allow-identity-change", action="store_true",
                    help="reuse a shard dir written by a different corpus/model/topk")
    ap.add_argument("--gpu-mem", type=float, default=0.92)
    ap.add_argument("--max-num-seqs", type=int, default=64,
                    help="vLLM concurrency; must be >= --batch. Qwen3.8 needs one Mamba "
                         "cache block per sequence, 256 does not fit on 48 GB")
    ap.add_argument("--max-model-len", type=int, default=4096)
    ap.add_argument("--tensor-parallel", type=int, default=1)
    ap.add_argument("--dry-run", type=int, default=0)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        vc.self_test()
        return 0

    vocab, tokens, starts = vc.load_corpus(args.data_dir)
    sentences = args.sentences or (len(starts) - 1)
    chosen = vc.select_indices(len(starts) - 1, sentences, args.seed, args.start, args.count)
    if not len(chosen):
        raise SystemExit("empty selection (start/count/sentences)")

    if args.dry_run:
        return dry_run(args, vocab, tokens, starts, chosen, args.dry_run)

    shard_dir = args.shard_dir or shard_dir_for(args.out)
    os.makedirs(shard_dir, exist_ok=True)
    prefix = args.prefix or os.path.basename(shard_dir).removesuffix("_shards")
    failures = args.failures or os.path.join(shard_dir, "failures.jsonl")

    n_shards = (len(chosen) + args.shard_size - 1) // args.shard_size
    shards = []
    for i in range(n_shards):
        lo = i * args.shard_size
        hi = min(len(chosen), lo + args.shard_size)
        shards.append((i, [int(s) for s in chosen[lo:hi]]))

    collector = Collector(args, vocab, tokens, starts, None, None)
    args.failures = failures

    # A shard dir is only valid for the exact run that wrote it: same corpus,
    # same selection, same model and top-k. Otherwise a re-prep, another seed
    # or another teacher silently mixes rows from two different mappings and
    # the merged npz still passes check_soft.
    #
    # `count` is deliberately *not* part of the identity: the selection is a
    # fixed permutation (seed) truncated to `count`, so growing the count only
    # appends shards and every existing shard keeps its sentence ids. That is
    # what makes a staged run (1.2M now, the rest later) safe.
    identity = {
        "data_dir": os.path.abspath(args.data_dir),
        "train_npz_sha256": sha256(os.path.join(args.data_dir, "train.npz")),
        "vocab_sha256": sha256(os.path.join(args.data_dir, "vocab.txt")),
        "train_sentences": int(len(starts) - 1),
        "sentences": int(sentences),
        "start": int(args.start),
        "seed": int(args.seed),
        "model": args.model,
        "topk": int(args.topk),
        "multi": int(args.multi),
        "shard_size": int(args.shard_size),
        "vocab": int(len(vocab)),
    }
    identity_path = os.path.join(shard_dir, "run.json")
    if os.path.exists(identity_path) and not args.allow_identity_change:
        with open(identity_path, encoding="utf-8") as f:
            previous = json.load(f)
        diff = {
            k: (previous.get(k), v)
            for k, v in identity.items()
            if previous.get(k) != v
        }
        if diff:
            raise SystemExit(
                f"{shard_dir} belongs to a different run: {diff}\n"
                "use another --shard-dir/--prefix, or --allow-identity-change to reuse it anyway"
            )
        log(f"resuming in {shard_dir} (count grows from {previous.get('count')} to {args.count or 'all'})")
    with open(identity_path, "w", encoding="utf-8") as f:
        json.dump({**identity, "count": int(args.count)}, f, indent=2)
        f.write("\n")

    if args.retry_failures:
        failed = read_failures(args.retry_failures)
        if not failed:
            log(f"no failed sentences in {args.retry_failures}; nothing to do")
            return 0
        log(f"retrying {len(failed)} sentences from {args.retry_failures}")
        by_shard = {}
        for sid in failed:
            idx = _shard_of(sid, shards)
            if idx is None:
                log(f"WARN sid {sid} not in this selection; skipping")
                continue
            by_shard.setdefault(idx, []).append(sid)
        for idx, sids in sorted(by_shard.items()):
            i, members = shards[idx]
            path = shard_path(shard_dir, prefix, i)
            if not os.path.exists(path):
                log(f"WARN shard {path} missing; run pass 1 first")
                continue
            if not same_sentences(path, members):
                log(f"WARN shard {path} does not belong to this selection; run pass 1 again")
                continue
            blocks = split_blocks(load_npz(path))
            log(f"shard {i}: {len(blocks)} sentences, retrying {len(sids)}")
            collector.process(sorted(sids), path + ".partial.npz", prefix, blocks)
            sids_out, st, ids, probs = pack_blocks(blocks, args.topk, collector.id_dtype)
            save_npz(path, sids_out, st, ids, probs)
            ok, err = valid_soft(path, len(vocab), expect=len(members))
            if not ok:
                log(f"WARN patched shard {path} still invalid ({err}); keeping .INCOMPLETE")
                with open(path + ".INCOMPLETE", "w", encoding="utf-8") as f:
                    f.write("\n".join(str(s) for s in sids) + "\n")
                continue
            with open(path + ".sha256", "w", encoding="utf-8") as f:
                f.write(f"{sha256(path)}  {os.path.basename(path)}\n")
            drop_markers(path)
            log(f"shard {i} patched: {len(sids_out)} sentences")
        with open(os.path.join(shard_dir, "RETRY_DONE"), "w", encoding="utf-8") as f:
            f.write(f"{len(failed)} sids retried at {time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
        return 0

    log(
        f"{len(chosen)} sentences -> {n_shards} shards of {args.shard_size}, "
        f"batch {args.batch}, topk {args.topk}, attempts {args.attempts}, "
        f"failures -> {failures}"
    )
    for i, members in shards:
        path = shard_path(shard_dir, prefix, i)
        if not args.no_resume and os.path.exists(path):
            ok, err = valid_soft(path, len(vocab), expect=len(members))
            if ok and same_sentences(path, members):
                log(f"skip shard {i} ({path} valid)")
                continue
            if not ok:
                log(f"shard {i} invalid ({err}); recomputing")
            else:
                log(f"shard {i} holds different sentence ids; recomputing")
        partial = path + ".partial.npz"
        blocks = {}
        if not args.no_resume and os.path.exists(partial):
            ok, err = valid_soft(partial, len(vocab))
            if ok and subset_sentences(partial, members):
                blocks = split_blocks(load_npz(partial))
                log(f"resume shard {i}: {len(blocks)} sentences from {partial}")
            else:
                log(f"partial {partial} unusable ({err or 'foreign sentence ids'}); starting the shard over")
        t0 = time.perf_counter()
        collector.process(members, partial, prefix, blocks)
        rate = len(blocks) / max(1e-9, time.perf_counter() - t0)
        missing = [s for s in members if s not in blocks]
        sids_out, st, ids, probs = pack_blocks(blocks, args.topk, collector.id_dtype)
        save_npz(path, sids_out, st, ids, probs)
        ok, err = valid_soft(path, len(vocab), expect=len(members))
        if not ok:
            # A shard with permanent failures is written but not marked done.
            log(f"WARN shard {i}: {len(missing)} sentences missing; {path} does not validate ({err})")
            with open(path + ".INCOMPLETE", "w", encoding="utf-8") as f:
                f.write("\n".join(str(s) for s in missing) + "\n")
            continue
        with open(path + ".sha256", "w", encoding="utf-8") as f:
            f.write(f"{sha256(path)}  {os.path.basename(path)}\n")
        drop_markers(path)
        log(f"shard {i} done: {len(blocks)} sentences, {rate:.1f}/s, rows {st[-1]}")

    log(
        f"shards written to {shard_dir}: {collector.stats['sentences']} sentences this run, "
        f"{collector.stats['failed']} failed attempts, {collector.stats['high_nll']} accepted "
        f"with high NLL, {collector.stats['rows']} rows"
    )
    log(
        "merge with: find "
        f"{shard_dir} -maxdepth 1 -name '{prefix}_[0-9]*.npz' ! -name '*.partial.npz' | sort"
    )
    return 0


def same_sentences(path, members):
    """Exact sentence-id match between a shard and the current selection."""
    z = load_npz(path)
    return z["sentences"].tolist() == list(members)


def subset_sentences(path, members):
    """A partial checkpoint may hold any subset, but only of these ids."""
    return set(load_npz(path)["sentences"].tolist()) <= set(members)


def drop_markers(path):
    """Remove the resume checkpoint and the incomplete marker of a shard."""
    for extra in (".partial.npz", ".INCOMPLETE"):
        if os.path.exists(path + extra):
            os.remove(path + extra)


def _shard_of(sid, shards):
    for idx, (_i, members) in enumerate(shards):
        if sid in members:
            return idx
    return None


if __name__ == "__main__":
    sys.exit(main())

