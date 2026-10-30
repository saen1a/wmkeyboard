#!/usr/bin/env python3
"""100-sentence A/B for the German teacher (Phase 0b / Phase 1).

Runs the same 100 chat + 100 news sentences through one or more teacher
checkpoints with `prompt_logprobs=24`, `max_tokens=1`, MTP off, and records
what a soft-target collector would actually see:

- teacher plausibility: mean NLL of the actual token, missing token count,
  non-finite count, top-k width;
- student-side rows: top-1 word per position, its mass, top-8 mass,
  renormalisation sanity;
- throughput: prompts/s, prompt tokens/s, batch latency.

With two models (BF16 reference vs FP8 run variant, or 27B vs
35B-A3B-Base) it also reports how often the top-1 words agree and how far
the probabilities move - the only thing that matters later, because the
student sees the projected distribution, not the raw teacher.

Each model runs in its own process (a 27B BF16 and a 27B FP8 do not fit on
one card together, and vLLM does not reliably return memory in-process).

Usage:
    python3 benchmark_prompt_logprobs.py --data out/de_lm_2m \
        --models Qwen/Qwen3.8-27B,Qwen/Qwen3.8-27B-FP8 \
        --per-class 100 --batch 16 --out out/ab_100.json
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

import numpy as np

import vllm_common as vc

CASUAL = "<reg:casual>"
FORMAL = "<reg:formal>"


def pick_sentences(vocab, tokens, starts, per_class, seed=0, sentences_file=""):
    """First `per_class` chat rows and news rows, spread over the corpus.

    `train.npz` stores the *vocabulary id* of the register token, not the
    register index (prep.py writes `ids[REGISTERS[reg]]`), so the class is
    read back from `vocab.txt`.

    With `sentences_file` the selection is read instead of computed, so two
    runs measure exactly the same sentences even on different hardware.
    """
    if sentences_file:
        chat, news = [], []
        with open(sentences_file, encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 2:
                    continue
                cls, sid = parts[0], int(parts[1])
                (chat if cls == "chat" else news).append(sid)
        if not chat or not news:
            raise SystemExit(f"{sentences_file}: no chat/news rows")
        return sorted(chat), sorted(news)

    n = len(starts) - 1
    rng = np.random.default_rng(seed)
    order = rng.permutation(n)
    chat, news = [], []
    for s in order:
        if len(chat) >= per_class and len(news) >= per_class:
            break
        row = tokens[starts[s] : starts[s + 1]]
        reg = vocab[int(row[0])]
        if reg == CASUAL and len(chat) < per_class:
            chat.append(int(s))
        elif reg == FORMAL and len(news) < per_class:
            news.append(int(s))
    if not chat or not news:
        raise SystemExit(
            f"no chat/news sentences selected (chat={len(chat)}, news={len(news)}); "
            "check that train.npz came from this corpus"
        )
    return sorted(chat), sorted(news)


def dump_sentences(path, vocab, tokens, starts, chat, news):
    """Write the fixed selection so every model can be measured on it."""
    with open(path, "w", encoding="utf-8") as f:
        f.write("# class\tsid\tprompt\n")
        for cls, sids in (("chat", chat), ("news", news)):
            for s in sids:
                row = tokens[starts[s] : starts[s + 1]]
                text, _ = vc.prompt_text(vocab, row)
                f.write(f"{cls}\t{int(s)}\t{text.strip()}\n")
    print(f"wrote {len(chat) + len(news)} sentences to {path}")


def split_models(value):
    """Split `--models` on commas that separate models, not on kwargs.

    `a,b` -> two models; `a|quantization=fp8_per_tensor,dtype=bfloat16,b`
    -> one spec with two kwargs plus a second model. A fragment is treated as
    a continuation of the previous spec when it looks like `key=value`
    (no path separator in the key).
    """
    out = []
    for part in value.split(","):
        frag = part.strip()
        if not frag:
            continue
        key = frag.split("=", 1)[0]
        if out and "=" in frag and "/" not in key and ":" not in key:
            out[-1] = f"{out[-1]},{frag}"
        else:
            out.append(frag)
    return out


def parse_spec(spec):
    """`model[|quantization=fp8_per_tensor,dtype=bfloat16]` -> (model, kwargs).

    Lets one run compare the shipped FP8 checkpoint against the same weights
    quantized at load time (vLLM's FP8_DYNAMIC: per-channel weights, dynamic
    per-token activations) without a second script. Only a fixed set of
    load options can be passed, never arbitrary LLM kwargs.
    """
    model, _, opts = spec.partition("|")
    kwargs = {}
    for item in (opts.split(",") if opts else []):
        if "=" in item:
            k, v = item.split("=", 1)
            k, v = k.strip(), v.strip()
            if k in {"quantization", "dtype", "kv_cache_dtype"} and v:
                kwargs[k] = v
    return model.strip(), kwargs


def run_model(args):
    from vllm import LLM, SamplingParams  # noqa: PLC0415
    from transformers import AutoTokenizer  # noqa: PLC0415

    model, llm_kwargs = parse_spec(args.model)
    vocab, tokens, starts = vc.load_corpus(args.data)
    chat, news = pick_sentences(vocab, tokens, starts, args.per_class, args.seed,
                                args.sentences_file)

    t0 = time.perf_counter()
    llm = LLM(
        model=model,
        max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_mem,
        max_num_seqs=args.max_num_seqs,
        max_logprobs=max(20, args.topk),
        trust_remote_code=False,
        tensor_parallel_size=1,
        enforce_eager=False,
        **llm_kwargs,
    )
    load_s = time.perf_counter() - t0
    info = vc.teacher_info(llm)
    if info.get("speculative"):
        raise SystemExit(f"speculative decoding active ({info['speculative']}); MTP must be off")
    tok = AutoTokenizer.from_pretrained(model, trust_remote_code=False)
    mapping = vc.student_to_teacher(vocab, lambda s: tok.encode(s, add_special_tokens=False), multi=True)
    by_first = vc.index_mapping(mapping)

    sp = SamplingParams(max_tokens=1, temperature=0.0, prompt_logprobs=args.topk)
    records = []
    t_start = time.perf_counter()
    prompt_tokens = 0
    for cls, sids in (("chat", chat), ("news", news)):
        for i in range(0, len(sids), args.batch):
            chunk = sids[i : i + args.batch]
            inputs, meta = [], []
            for sid in chunk:
                row = tokens[starts[sid] : starts[sid + 1]]
                text, ends = vc.prompt_text(vocab, row)
                enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
                ids = enc["input_ids"]
                if len(ids) < 3 or len(ids) > args.max_model_len:
                    continue
                inputs.append({"prompt_token_ids": ids})
                meta.append((sid, ends, ids, [o[1] for o in enc["offset_mapping"]]))
            if not inputs:
                continue
            outs = llm.generate(inputs, sp)
            for (sid, ends, ids, tok_ends), out in zip(meta, outs):
                prompt_tokens += len(ids)
                st = vc.sentence_stats(out.prompt_logprobs, ids)
                positions = vc.word_positions(ends, tok_ends)
                rows_ids, rows_probs, rst = vc.rows_from_logprobs(
                    out.prompt_logprobs, len(ids), positions, by_first, args.topk
                )
                top1, top1_p, top8 = [], [], []
                for k in range(1, len(positions)):
                    p = rows_probs[k].astype(np.float64)
                    if p.sum() <= 0:
                        continue
                    top1.append(int(rows_ids[k, 0]))
                    top1_p.append(float(p[0]))
                    top8.append(float(p[:8].sum()))
                records.append({
                    "sid": sid,
                    "class": cls,
                    "tokens": len(ids),
                    "words": len(ends),
                    "nll": st["mean_nll"],
                    "missing": st["missing"],
                    "top1_ids": top1,
                    "top1_p": top1_p,
                    "top8_p": top8,
                    "soft_rows": int(rst["rows"]),
                    "nonfinite": int(rst["nonfinite"]),
                })
    wall = time.perf_counter() - t_start
    out = {
        "model": model,
        "teacher": info,
        "load_seconds": round(load_s, 1),
        "prompts": len(records),
        "prompt_tokens": prompt_tokens,
        "measure_seconds": round(wall, 1),
        "prompts_per_s": round(len(records) / max(1e-9, wall), 2),
        "prompt_tokens_per_s": round(prompt_tokens / max(1e-9, wall), 1),
        "batch": args.batch,
        "topk": args.topk,
        "per_class": args.per_class,
        "seed": args.seed,
        "sentences_file": args.sentences_file or None,
        "records": records,
        "summary": summarize(records),
    }
    vc.write_json(args.out, out)
    print(json.dumps({"model": model, "summary": out["summary"],
                      "prompts_per_s": out["prompts_per_s"]}, indent=2))
    return 0


def summarize(records):
    out = {}
    for cls in ("chat", "news"):
        rs = [r for r in records if r["class"] == cls and r["nll"] is not None]
        if not rs:
            continue
        flat_p = [p for r in rs for p in r["top1_p"]]
        flat8 = [p for r in rs for p in r["top8_p"]]
        out[cls] = {
            "sentences": len(rs),
            "mean_nll": round(float(np.mean([r["nll"] for r in rs])), 4),
            "missing_actual": int(sum(r["missing"] for r in rs)),
            "nonfinite": int(sum(r["nonfinite"] for r in rs)),
            "top1_mass": round(float(np.mean(flat_p)), 4) if flat_p else None,
            "top8_mass": round(float(np.mean(flat8)), 4) if flat8 else None,
            "soft_rows": int(sum(r["soft_rows"] for r in rs)),
        }
    return out


def pairwise(a, b):
    """Top-1 agreement and mass movement between two model runs."""
    by_sid_b = {r["sid"]: r for r in b["records"]}
    same = total = 0
    dp = []
    per_class = {}
    for r in a["records"]:
        o = by_sid_b.get(r["sid"])
        if not o:
            continue
        n = min(len(r["top1_ids"]), len(o["top1_ids"]))
        hits = sum(1 for i in range(n) if r["top1_ids"][i] == o["top1_ids"][i])
        same += hits
        total += n
        dp.extend(abs(r["top1_p"][i] - o["top1_p"][i]) for i in range(n))
        c = per_class.setdefault(r["class"], {"same": 0, "total": 0})
        c["same"] += hits
        c["total"] += n
    return {
        "a": a["model"],
        "b": b["model"],
        "top1_agreement": round(same / total, 4) if total else None,
        "top1_agreement_by_class": {
            k: round(v["same"] / v["total"], 4) for k, v in per_class.items() if v["total"]
        },
        "mean_abs_delta_top1_mass": round(float(np.mean(dp)), 4) if dp else None,
        "positions": total,
    }


def compare_many(paths, out_path):
    """N models on one fixed sentence set: metrics table + all pairs."""
    runs = [json.load(open(p, encoding="utf-8")) for p in paths]
    pairs = [pairwise(runs[i], runs[j])
             for i in range(len(runs)) for j in range(i + 1, len(runs))]
    report = {
        "models": [r["model"] for r in runs],
        "summary": {r["model"]: r["summary"] for r in runs},
        "throughput": {r["model"]: {"prompts_per_s": r["prompts_per_s"],
                                    "prompt_tokens_per_s": r["prompt_tokens_per_s"]}
                       for r in runs},
        "pairs": pairs,
        "sentences": runs[0].get("sentences_file") or runs[0].get("per_class"),
    }
    vc.write_json(out_path, report)
    print("\n=== teacher A/B (same sentences, same projection) ===")
    for model, summ in report["summary"].items():
        for cls in ("chat", "news"):
            s = summ.get(cls)
            if not s:
                continue
            print(f"{model:32s} {cls:5s} top-1 {s['top1_mass']:.4f}  "
                  f"top-8 {s['top8_mass']:.4f}  NLL {s['mean_nll']:.4f}  "
                  f"rows {s['soft_rows']}")
    for p in pairs:
        print(f"agree {p['a']} vs {p['b']}: {p['top1_agreement']} "
              f"({p['top1_agreement_by_class']}), dP {p['mean_abs_delta_top1_mass']}")
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="")
    ap.add_argument("--model", default="")
    ap.add_argument("--models", default="", help="comma separated; run each in its own process")
    ap.add_argument("--out", default="out/ab_100.json")
    ap.add_argument("--per-class", type=int, default=100)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--topk", type=int, default=24)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--sentences-file", default="",
                    help="fixed class/sid selection; makes runs comparable across hosts")
    ap.add_argument("--dump-sentences", default="",
                    help="write the computed selection to this TSV and reuse it")
    ap.add_argument("--gpu-mem", type=float, default=0.92)
    ap.add_argument("--max-num-seqs", type=int, default=64,
                    help="vLLM concurrency; must be >= --batch (Mamba cache per sequence)")
    ap.add_argument("--max-model-len", type=int, default=4096)
    args = ap.parse_args(argv)

    if args.models:
        if not args.data:
            raise SystemExit("--data is required")
        base = args.out[:-5] if args.out.endswith(".json") else args.out
        # Freeze the sentence set once, then hand it to every model process.
        sentences_file = args.sentences_file
        if not sentences_file and args.dump_sentences:
            vocab, tokens, starts = vc.load_corpus(args.data)
            chat, news = pick_sentences(vocab, tokens, starts, args.per_class, args.seed)
            dump_sentences(args.dump_sentences, vocab, tokens, starts, chat, news)
            sentences_file = args.dump_sentences
        per_model = []
        for m in split_models(args.models):
            tag = re.sub(r"[^A-Za-z0-9._-]+", "_", m.replace("|", "_").rsplit("/", 1)[-1])
            path = f"{base}.{tag}.json"
            cmd = [
                sys.executable, os.path.abspath(__file__),
                "--data", args.data, "--model", m, "--out", path,
                "--per-class", str(args.per_class), "--batch", str(args.batch),
                "--topk", str(args.topk), "--seed", str(args.seed),
                "--gpu-mem", str(args.gpu_mem), "--max-model-len", str(args.max_model_len),
                "--max-num-seqs", str(args.max_num_seqs),
            ]
            if sentences_file:
                cmd += ["--sentences-file", sentences_file]
            print(f"=== {m} -> {path}", flush=True)
            rc = subprocess.run(cmd).returncode
            if rc != 0:
                print(f"WARN: model {m} failed with exit {rc}; continuing", flush=True)
                continue
            per_model.append(path)
        if len(per_model) >= 2:
            compare_many(per_model, args.out)
        elif len(per_model) == 1:
            vc.write_json(args.out, {"runs": per_model})
        else:
            raise SystemExit("no model finished")
        return 0

    if not args.data or not args.model:
        raise SystemExit("--data and --model (or --models) are required")
    return run_model(args)


if __name__ == "__main__":
    sys.exit(main())
