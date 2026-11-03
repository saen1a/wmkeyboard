#!/usr/bin/env python3
"""Collect German soft targets from Together AI into `tools/wmlm/train.py` form.

The API twin of `cloud/scaleway/distill_vllm.py`: same corpus selection, same
prompt text, same four-array soft npz, same shard/merge discipline — but the
teacher is a hosted model whose support is capped at 5 alternatives per
position (see `client.py` for the measured endpoint facts).

What makes a 5-wide teacher usable here is `echo`: it scores every prompt
token, so every row gets

  * the returned top-5 alternatives mapped onto the student vocabulary,
  * the **actual** word's exact probability `p(w) = ∏ p(token)`, including the
    15.3 % of rows the top-24 pipeline scored 0.0 on (multi-token words), and
  * that exact probability is *injected* when the truncated list missed the
    word, so the row never under-reports the true target.

Per row the collector also records the captured teacher mass (1 - residual)
and the true word's exact probability in a **sibling** file `<out>.audit.npz`
— the four-key soft npz stays exactly what `check_soft.py`, `merge_soft.py`
and `train.py` already accept.

Usage:
    python3 distill_together.py out/de_lm out/de_soft_together.npz \
        --map out/wordmap_together.json --sentences 150000 --shard-size 25000
    python3 distill_together.py ... --dry-run          # plan + cost, no requests
    python3 distill_together.py ... --self-test        # offline, fake transport
"""
import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for extra in (HERE, os.path.join(HERE, "tests"),
              os.path.abspath(os.path.join(HERE, "..", "scaleway")),
              os.path.abspath(os.path.join(HERE, "..", "..", "tools"))):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import client as tg  # noqa: E402
import together_common as tc  # noqa: E402
import vllm_common as vc  # noqa: E402
import wordmap as wm  # noqa: E402

PREFIX_LEN = vc.PREFIX_LEN
SOFT_KEYS = ("sentences", "starts", "ids", "probs")
ID_DTYPE = np.int16

# Input price per 1M tokens, kb-inference-providers.md §1.7
PRICE_IN = {"Qwen/Qwen3.5-9B": 0.17, "openai/gpt-oss-120b": 0.15}


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def save_npz(path, sentences, starts, ids, probs):
    tmp = path + ".tmp.npz"
    with open(tmp, "wb") as f:
        np.savez(f,
                 sentences=np.asarray(sentences, dtype=np.int32),
                 starts=np.asarray(starts, dtype=np.int64),
                 ids=np.asarray(ids, dtype=ID_DTYPE),
                 probs=np.asarray(probs, dtype=np.float16))
    os.replace(tmp, path)


def word_ids_of(row):
    """`[(student id, is_piece), ...]` for the word groups of one train.npz row.

    Mirrors `vllm_common.prompt_text`: the 4-token prefix and the trailing
    `</s>` are dropped, `##` continuations belong to the previous word. A
    group whose first token is a piece marker (`▁`/`##`) is a word the
    vocabulary only spells, i.e. `soft_mask.py`'s PIECE row.
    """
    out = []
    for t in row[PREFIX_LEN:-1]:
        w = sp_vocab_lookup(int(t))
        if w.startswith(vc.CONT):
            continue
        piece = w.startswith(vc.START) or w.startswith(vc.CONT)
        out.append((int(t), piece))
    return out


_VOCAB = None


def sp_vocab_lookup(i):
    return _VOCAB[i]


def load_vocab(data_dir):
    global _VOCAB
    with open(os.path.join(data_dir, "vocab.txt"), encoding="utf-8") as f:
        _VOCAB = [line.rstrip("\n") for line in f]
    return _VOCAB


def validate_soft(path, vocab_size, expect, min_mass_ratio=0.0):
    """`check_soft.validate_soft` when present, else a local minimum check."""
    try:
        from check_soft import validate_soft as real  # noqa: PLC0415
    except Exception:                                     # noqa: BLE001
        z = np.load(path, allow_pickle=False)
        rows = len(z["ids"])
        mass = float((z["probs"].sum(axis=1) > 0).mean()) if rows else 0.0
        if expect is not None and len(z["sentences"]) != expect:
            raise SystemExit(f"{path}: {len(z['sentences'])} sentences, expected {expect}")
        if mass < min_mass_ratio:
            raise SystemExit(f"{path}: filled-row share {mass:.3f} < {min_mass_ratio}")
        return {"sentences": len(z["sentences"]), "rows": rows, "mass_ratio": mass}
    return real(path, vocab_size=vocab_size, expect_sentences=expect,
                min_mass_ratio=min_mass_ratio)


# ------------------------------------------------------------------ planning
def plan(args):
    """Everything that does not need the corpus: shard layout and identity."""
    shard_dir = args.out[:-4] + "_shards" if args.out.endswith(".npz") else args.out + "_shards"
    prefix = os.path.basename(shard_dir).replace("_shards", "")
    n = args.count or (args.sentences - args.start)
    size = args.shard_size or n
    shards = [(i, args.start + i * size, min(size, n - i * size))
              for i in range((n + size - 1) // size)] if n > 0 else []
    return {"shard_dir": shard_dir, "prefix": prefix, "shards": shards, "n": n}


def identity(args, data_dir, map_meta):
    return {
        "data_dir": os.path.abspath(data_dir),
        "train_sha256": sha256_file(os.path.join(data_dir, "train.npz")),
        "vocab_sha256": sha256_file(os.path.join(data_dir, "vocab.txt")),
        "sentences": args.sentences, "start": args.start, "seed": args.seed,
        "model": args.model, "topk": args.topk, "map": args.map,
        "map_model": map_meta.get("model"),
        "map_vocab_sha256": map_meta.get("vocab_sha256"),
        "inject_actual": not args.no_inject,
        "weight_mode": args.weight_mode,
        "temperature": args.temperature,
    }


def check_identity(path, want, allow_change):
    if not os.path.exists(path):
        vc.write_json(path, want)
        return
    with open(path, encoding="utf-8") as f:
        got = json.load(f)
    diff = {k: (got.get(k), v) for k, v in want.items() if got.get(k) != v}
    # `count`/`sentences` may grow between stages; everything else must match.
    diff.pop("sentences", None)
    if diff and not allow_change:
        raise SystemExit(f"run identity changed: {diff} (use --allow-identity-change)")
    if diff:
        log(f"identity change accepted: {diff}")
        vc.write_json(path, want)


# ---------------------------------------------------------------- collection
def rows_for_sentence(text, ends, actual, by_first, topk, inject, choice, temperature=1.0):
    """Guard the echo alignment, then build the rows."""
    n = choice.prompt_tokens
    echoed = "".join(choice.tokens[:n])
    if echoed != text:
        raise ValueError(f"echo mismatch: {echoed[:60]!r} != {text[:60]!r}")
    return tc.rows_from_sentence(choice.tokens, choice.logs, choice.alts, n, ends,
                                 by_first, topk=topk, id_dtype=ID_DTYPE,
                                 inject_actual=inject,
                                 actual=([sid for sid, _ in actual] or None),
                                 temperature=temperature)


def collect(args, client, by_first, chosen, tokens, starts, vocab, shards):
    """Fill every shard that is not already valid. Returns a summary."""
    summary = {"shards": 0, "sentences": 0, "rows": 0, "filled": 0, "injected": 0,
               "skipped_sentences": 0, "high_nll": 0, "mean_nll_sum": 0.0,
               "nll_rows": 0, "requests": 0, "prompt_tokens": 0, "seconds": 0.0}
    os.makedirs(shards["shard_dir"], exist_ok=True)
    failures = os.path.join(shards["shard_dir"], "failures.jsonl")
    t0 = time.time()

    for idx, off, size in shards["shards"]:
        path = os.path.join(shards["shard_dir"], f"{shards['prefix']}_{idx:05d}.npz")
        members = chosen[off:off + size]
        if os.path.exists(path):
            try:
                got = validate_soft(path, len(vocab), len(members))
                z = np.load(path, allow_pickle=False)
                if list(z["sentences"]) == [int(s) for s in members]:
                    log(f"shard {idx}: valid, skipped ({got['sentences']} sentences)")
                    summary["shards"] += 1
                    summary["sentences"] += len(members)
                    continue
            except SystemExit:
                pass
            log(f"shard {idx}: present but not valid, rebuilding")
            for junk in (path, path + ".sha256", path + ".audit.npz"):
                if os.path.exists(junk):
                    os.remove(junk)

        blocks = {}
        audit = {}
        for b in range(0, len(members), args.batch):
            sids = members[b:b + args.batch]
            texts, mains, actuals, keep = [], [], [], []
            for sid in sids:
                row = tokens[starts[sid]:starts[sid + 1]]
                text, ends = vc.prompt_text(vocab, row)
                if not text or not ends:
                    summary["skipped_sentences"] += 1
                    continue
                texts.append(text)
                mains.append(ends)
                actuals.append(word_ids_of(row))
                keep.append(int(sid))
            if not texts:
                continue
            try:
                answers = client.score(texts)
            except tg.TogetherError as e:
                vc.append_jsonl(failures, {"event": "failed", "shard": idx,
                                           "sids": keep[:20], "error": str(e)})
                log(f"shard {idx}: chunk failed, shard left unwritten: {e}")
                break

            for sid, text, ends, actual, ch in zip(keep, texts, mains, actuals, answers):
                st = tc.sentence_audit(ch.tokens, ch.logs, ch.alts, ch.prompt_tokens)
                if st["mean_nll"] is not None:
                    summary["mean_nll_sum"] += st["mean_nll"]
                    summary["nll_rows"] += 1
                    if st["mean_nll"] > args.max_nll:
                        summary["high_nll"] += 1
                        vc.append_jsonl(failures, {"event": "high_nll", "sid": sid,
                                                   "mean_nll": st["mean_nll"],
                                                   "model": args.model})
                try:
                    ids, probs, mass, act, ap, stats = rows_for_sentence(
                        text, ends, actual, by_first, args.topk,
                        not args.no_inject, ch, args.temperature)
                except ValueError as e:
                    summary["skipped_sentences"] += 1
                    vc.append_jsonl(failures, {"event": "unaligned", "sid": sid,
                                               "error": str(e)})
                    continue
                blocks[sid] = (ids, probs)
                pieces = np.zeros(ids.shape[0], dtype=np.uint8)
                for k, (_, is_piece) in enumerate(actual):
                    if k < len(pieces):
                        pieces[k] = 1 if is_piece else 0
                audit[sid] = (mass, act, ap, pieces)
                summary["rows"] += int(ids.shape[0])
                summary["filled"] += int(stats["filled"])
                summary["injected"] += int(stats["injected"])
        else:
            # every batch of this shard ran: write it
            if not blocks:
                log(f"shard {idx}: no rows, leaving it unwritten")
                continue
            sids = sorted(blocks)
            ids = np.concatenate([blocks[s][0] for s in sids])
            probs = np.concatenate([blocks[s][1] for s in sids])
            starts_out = [0]
            for s in sids:
                starts_out.append(starts_out[-1] + blocks[s][0].shape[0])
            save_npz(path, sids, starts_out, ids, probs)
            got = validate_soft(path, len(vocab), len(sids), args.min_mass_ratio)
            mass_all = np.concatenate([audit[s][0] for s in sids])
            piece_all = np.concatenate([audit[s][3] for s in sids])
            weight_all = tc.row_weights(args.weight_mode, mass_all,
                                        (probs > 0).sum(axis=1), piece_all,
                                        args.topk, args.piece_weight)
            tc.save_audit(path[:-4] + ".audit.npz",
                          mass_all,
                          np.concatenate([audit[s][1] for s in sids]),
                          np.concatenate([audit[s][2] for s in sids]),
                          weight=weight_all, piece=piece_all)
            with open(path + ".sha256", "w", encoding="utf-8") as f:
                f.write(sha256_file(path) + "\n")
            summary["shards"] += 1
            summary["sentences"] += len(sids)
            log(f"shard {idx}: {got['sentences']} sentences, {got['rows']} rows, "
                f"filled {got['mass_ratio']:.1%}")
            continue

    summary["requests"] = client.stats["requests"]
    summary["prompt_tokens"] = client.stats["prompt_tokens"]
    summary["seconds"] = time.time() - t0
    if summary["nll_rows"]:
        summary["mean_nll"] = summary["mean_nll_sum"] / summary["nll_rows"]
    return summary


def merge(args, shards, vocab_size):
    """Concatenate valid shards into `--out` plus its audit sibling."""
    paths = [os.path.join(shards["shard_dir"], f"{shards['prefix']}_{i:05d}.npz")
             for i, _, _ in shards["shards"]]
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        raise SystemExit(f"cannot merge, {len(missing)} shard(s) missing, e.g. {missing[0]}")
    sentences, ids, probs, starts_out = [], [], [], [0]
    mass, act, ap, weight, piece = [], [], [], [], []
    topk = None
    for p in paths:
        z = np.load(p, allow_pickle=False)
        if topk is None:
            topk = z["ids"].shape[1]
        elif z["ids"].shape[1] != topk:
            raise SystemExit(f"{p}: top-{z['ids'].shape[1]} != top-{topk}")
        sentences.append(z["sentences"])
        ids.append(z["ids"])
        probs.append(z["probs"])
        starts_out.extend((starts_out[-1] + z["starts"][1:]).tolist())
        audit_path = p[:-4] + ".audit.npz"
        if os.path.exists(audit_path):
            a = tc.load_audit(audit_path)
            mass.append(a["mass"])
            act.append(a["actual"])
            ap.append(a["actual_p"])
            if "weight" in a:
                weight.append(a["weight"])
            if "piece" in a:
                piece.append(a["piece"])
    out_sent = np.concatenate(sentences)
    if len(out_sent) and not np.all(np.diff(out_sent) > 0):
        raise SystemExit("shards overlap or are out of order")
    save_npz(args.out, out_sent, starts_out, np.concatenate(ids), np.concatenate(probs))
    if mass:
        tc.save_audit(args.out[:-4] + ".audit.npz", np.concatenate(mass),
                      np.concatenate(act), np.concatenate(ap),
                      weight=(np.concatenate(weight) if weight else None),
                      piece=(np.concatenate(piece) if piece else None))
    got = validate_soft(args.out, vocab_size, None, args.min_mass_ratio)
    with open(args.out + ".sha256", "w", encoding="utf-8") as f:
        f.write(sha256_file(args.out) + "\n")
    log(f"merged {len(paths)} shards -> {args.out}: {got['sentences']} sentences, "
        f"{got['rows']} rows, filled {got['mass_ratio']:.1%}")
    return got


# -------------------------------------------------------------------- entry
def build_parser():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data_dir", nargs="?", help="prep.py output dir (vocab.txt, train.npz)")
    ap.add_argument("out", nargs="?", help="merged soft npz to write")
    ap.add_argument("--map", help="word map JSON from wordmap.py")
    ap.add_argument("--model", default=tg.DEFAULT_MODEL)
    ap.add_argument("--sentences", type=int, default=150000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=0, help="0 = rest of --sentences")
    ap.add_argument("--topk", type=int, default=tc.DEFAULT_TOPK)
    ap.add_argument("--batch", type=int, default=256, help="sentences per request (array prompt)")
    ap.add_argument("--shard-size", type=int, default=25000)
    ap.add_argument("--max-nll", type=float, default=12.0)
    ap.add_argument("--min-mass-ratio", type=float, default=0.90)
    ap.add_argument("--temperature", type=float, default=1.0,
                    help="teacher softening p^(1/T) before ranking; mass stays raw "
                         "(KD guidance: 1.5-2.0, plans/student-quality-audit.md §3.2)")
    ap.add_argument("--weight-mode", default="mass", choices=["mass", "cand", "piece"],
                    help="per-row KD weight written as `weight` in the audit sibling "
                         "(mass = captured teacher probability, cand = soft_mask --weight=cand, "
                         "piece = build_kd_weight.py's 0.1/1.0)")
    ap.add_argument("--piece-weight", type=float, default=0.1)
    ap.add_argument("--no-inject", action="store_true",
                    help="do not add the true word when the top-5 missed it")
    ap.add_argument("--key-file", default="")
    ap.add_argument("--retries", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--allow-identity-change", action="store_true")
    ap.add_argument("--merge-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    return ap


def main(argv=None, transport=None):
    """`transport` exists for the offline end-to-end test: every HTTP hop in
    this module goes through `client.Client`, so one fake is enough."""
    args = build_parser().parse_args(argv)
    if args.self_test:
        from test_together_e2e import self_test  # noqa: PLC0415
        return self_test()
    if not args.data_dir or not args.out:
        build_parser().error("data_dir and out are required")

    vocab = load_vocab(args.data_dir)
    _, tokens, starts = vc.load_corpus(args.data_dir)
    shards = plan(args)
    if not os.path.exists(args.map):
        raise SystemExit(f"no word map at {args.map}: run wordmap.py first")
    by_first, map_meta = wm.load_map(args.map)
    check_identity(os.path.join(shards["shard_dir"], "run.json"),
                   identity(args, args.data_dir, map_meta), args.allow_identity_change)

    if args.dry_run:
        per = PRICE_IN.get(args.model, 0.20)
        est_tokens = shards["n"] * 12
        print(json.dumps({
            "shards": [[i, off, size] for i, off, size in shards["shards"]],
            "sentences": shards["n"], "topk": args.topk, "batch": args.batch,
            "map_first_tokens": len(by_first),
            "est_input_tokens": est_tokens,
            "est_cost_usd": round(est_tokens * per / 1e6, 4),
            "est_seconds": round(shards["n"] / 200.0, 1),
        }, indent=2))
        return 0

    chosen = vc.select_indices(len(starts) - 1, args.sentences, args.seed,
                              args.start, args.count)
    if args.merge_only:
        merge(args, shards, len(vocab))
        return 0

    client = tg.Client(model=args.model, key_file=args.key_file, batch=args.batch,
                       retries=args.retries, timeout=args.timeout,
                       transport=transport, key=("test-key" if transport else None))
    summary = collect(args, client, by_first, chosen, tokens, starts, vocab, shards)
    summary["cost_usd"] = round(client.cost_usd(PRICE_IN.get(args.model, 0.20)), 4)
    vc.write_json(os.path.join(shards["shard_dir"], "summary.json"), summary)
    log(json.dumps(summary, indent=2))
    merge(args, shards, len(vocab))
    return 0


if __name__ == "__main__":
    sys.exit(main())
