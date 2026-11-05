#!/usr/bin/env python3
"""Short throughput gate for one H100 (Phase 0a): FP8 Qwen3.8-27B only.

Runs vLLM offline with `prompt_logprobs=24`, `max_tokens=1`, batch 32: one
warm-up batch, then up to `--prompts` prompts or `--seconds` of measurement.
Nothing else is loaded and no quality A/B happens here - the only questions
are "how many prompts per second does the card sustain" and "are the prompt
logprobs plausible at all".

Gate (from the session prompt):
    >= 35 prompts/s   keep going
    >= 100 prompts/s  and projected 2M run < 6 h / < 20 EUR -> take 2M
    35..100           -> take 1.2M
    < 35              stop, report, no BF16 / 100-sentence runs

Usage:
    python3 benchmark_quick.py --data out/de_lm_2m \
        --model Qwen/Qwen3.8-27B-FP8 --out out/bench_quick_fp8.json

Exit code: 0 when the gate passes, 3 when it fails (so a shell `&&` chain
stops), 2 on a setup error.
"""
import argparse
import math
import os
import sys
import time

import numpy as np

import vllm_common as vc

GATE_MIN = 35.0
GATE_TARGET = 100.0
EUR_PER_HOUR = 2.88775  # H100-1-80G 2.8665 + block storage / flexible IP
CHARS_PER_PROMPT_ROW = 40


def pick_prompts(vocab, tokens, starts, n_rows, seed):
    """Deterministic sample of sentence indices, spread over the corpus."""
    n = len(starts) - 1
    rng = np.random.default_rng(seed)
    chosen = np.sort(rng.choice(n, size=min(n_rows, n), replace=False))
    out = []
    for s in chosen:
        row = tokens[starts[s] : starts[s + 1]]
        text, ends = vc.prompt_text(vocab, row)
        if len(ends) >= 3:  # need at least three words for a sane measurement
            out.append((int(s), text))
    return out


def measure(llm, tok, items, batch, seconds, warmup, max_model_len):
    from vllm import SamplingParams  # noqa: PLC0415 - after the model loads

    sp = SamplingParams(max_tokens=1, temperature=0.0, prompt_logprobs=24)
    prepared = []
    for sid, text in items:
        enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
        ids = enc["input_ids"]
        if not ids or len(ids) > max_model_len:
            continue
        prepared.append((sid, ids, enc["offset_mapping"]))

    stats = {"prompts": 0, "prompt_tokens": 0, "batches": 0, "latencies": []}
    plaus = {"rows": 0, "missing": 0, "nll_sum": 0.0, "top1": 0, "width": [], "nonfinite": 0}

    def run(chunk):
        inputs = [{"prompt_token_ids": ids} for _, ids, _ in chunk]
        t0 = time.perf_counter()
        outs = llm.generate(inputs, sp)
        dt = time.perf_counter() - t0
        stats["latencies"].append(dt)
        stats["batches"] += 1
        stats["prompts"] += len(chunk)
        stats["prompt_tokens"] += sum(len(ids) for _, ids, _ in chunk)
        for (sid, ids, _), out in zip(chunk, outs):
            st = vc.sentence_stats(out.prompt_logprobs, ids)
            plaus["rows"] += st["rows"]
            plaus["missing"] += st["missing"]
            if st["mean_nll"] is not None:
                plaus["nll_sum"] += st["mean_nll"] * st["rows"]
            if st["top1"] is not None:
                plaus["top1"] += st["top1"] * st["rows"]
            if st["width_mean"] is not None:
                plaus["width"].append(st["width_mean"])
            dist = out.prompt_logprobs
            if dist:
                for d in dist:
                    if d:
                        plaus["nonfinite"] += sum(
                            1
                            for lp in d.values()
                            if lp.logprob is None or not math.isfinite(lp.logprob)
                        )
        return dt

    if not prepared:
        raise SystemExit("no usable prompts (all shorter than 3 words?)")

    # One warm-up batch (cuBLAS autotune, KV cache, first CUDA graph). Its
    # numbers are dropped: the gate is the sustained rate, not the first
    # batch after load.
    warm = prepared[:batch]
    if warmup and warm:
        run(warm)
        stats = {"prompts": 0, "prompt_tokens": 0, "batches": 0, "latencies": []}
        for key in plaus:
            if isinstance(plaus[key], list):
                plaus[key] = []
            else:
                plaus[key] = 0

    t_start = time.perf_counter()
    i = 0
    while i < len(prepared):
        elapsed = time.perf_counter() - t_start
        if elapsed >= seconds:
            break
        chunk = prepared[i : i + batch]
        run(chunk)
        i += batch

    wall = time.perf_counter() - t_start
    res = {
        "prompts": stats["prompts"],
        "batches": stats["batches"],
        "prompt_tokens": stats["prompt_tokens"],
        "seconds": round(wall, 3),
        "prompts_per_s": round(stats["prompts"] / wall, 2) if wall else 0.0,
        "prompt_tokens_per_s": round(stats["prompt_tokens"] / wall, 1) if wall else 0.0,
        "batch_ms_mean": round(1000 * sum(stats["latencies"]) / max(1, len(stats["latencies"])), 1),
        "batch_ms_p50": round(1000 * float(np.median(stats["latencies"])), 1) if stats["latencies"] else None,
        "tokens_per_prompt": round(stats["prompt_tokens"] / max(1, stats["prompts"]), 1),
    }
    rows = max(1, plaus["rows"])
    res["plausibility"] = {
        "positions": plaus["rows"],
        "missing_actual_token": plaus["missing"],
        "nonfinite_logprobs": plaus["nonfinite"],
        "mean_nll": round(plaus["nll_sum"] / rows, 4),
        "top1_share": round(plaus["top1"] / rows, 4),
        "topk_width_mean": round(float(np.mean(plaus["width"])), 2) if plaus["width"] else None,
    }
    return res


def project(prompts_per_s, rows, eur_per_hour=EUR_PER_HOUR):
    if prompts_per_s <= 0:
        return {"hours": None, "eur": None}
    hours = rows / prompts_per_s / 3600
    return {"hours": round(hours, 2), "eur": round(hours * eur_per_hour, 2)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="prep.py output dir (vocab.txt + train.npz)")
    ap.add_argument("--model", default="Qwen/Qwen3.8-27B-FP8")
    ap.add_argument("--out", default="out/bench_quick_fp8.json")
    ap.add_argument("--prompts", type=int, default=200)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--warmup", type=int, default=1, help="warm-up batches (0 disables)")
    ap.add_argument("--gpu-mem", type=float, default=0.92)
    ap.add_argument("--eur-per-hour", type=float, default=EUR_PER_HOUR,
                    help="rate for the projections: 2.88775 (H100-1-80G + storage) "
                         "or 1.46988 (L40S-1-48G)")
    ap.add_argument("--max-num-seqs", type=int, default=64,
                    help="vLLM concurrency; must be >= batch. Qwen3.8 allocates one "
                         "Mamba cache block per sequence, so 256 does not fit on 48 GB")
    ap.add_argument("--max-model-len", type=int, default=4096)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--fail-on-gate", type=int, default=1, help="exit 3 below the gate")
    args = ap.parse_args(argv)

    vocab, tokens, starts = vc.load_corpus(args.data)
    items = pick_prompts(vocab, tokens, starts, args.prompts, args.seed)
    print(f"data {args.data}: {len(starts) - 1} sentences, {len(items)} prompts selected", flush=True)

    from vllm import LLM  # noqa: PLC0415 - heavy import after the data check
    from transformers import AutoTokenizer  # noqa: PLC0415

    t0 = time.perf_counter()
    llm = LLM(
        model=args.model,
        max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_mem,
        max_num_seqs=args.max_num_seqs,
        max_logprobs=24,
        trust_remote_code=False,
        tensor_parallel_size=1,
        enforce_eager=False,
    )
    load_s = time.perf_counter() - t0
    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=False)
    info = vc.teacher_info(llm)
    if info.get("speculative"):
        raise SystemExit(
            f"speculative decoding is active ({info['speculative']}); MTP must be off "
            "for prompt_logprobs"
        )
    print(f"model loaded in {load_s:.0f}s: {info}", flush=True)

    t1 = time.perf_counter()
    res = measure(llm, tok, items, args.batch, args.seconds, args.warmup, args.max_model_len)
    res["model"] = args.model
    res["teacher"] = info
    res["load_seconds"] = round(load_s, 1)
    res["measure_seconds_wall"] = round(time.perf_counter() - t1, 1)
    res["batch"] = args.batch
    res["prompt_logprobs"] = 24
    res["gate"] = {
        "min": GATE_MIN,
        "target": GATE_TARGET,
        "passed": res["prompts_per_s"] >= GATE_MIN,
    }
    res["projection_1_2m"] = project(res["prompts_per_s"], 1_200_000, args.eur_per_hour)
    res["projection_2m"] = project(res["prompts_per_s"], 2_000_000, args.eur_per_hour)

    plausible = (
        res["plausibility"]["nonfinite_logprobs"] == 0
        and res["plausibility"]["missing_actual_token"] == 0
        and 0.0 < res["plausibility"]["mean_nll"] <= 12.0
    )
    res["plausible"] = plausible

    p = res["prompts_per_s"]
    if p >= GATE_TARGET and res["projection_2m"]["hours"] is not None and res["projection_2m"]["hours"] < 6 and res["projection_2m"]["eur"] < 20:
        res["dataset"] = "2m"
    elif p >= GATE_MIN:
        res["dataset"] = "1.2m"
    else:
        res["dataset"] = "stop"

    vc.write_json(args.out, res)
    print(
        f"{p:.1f} prompts/s ({res['prompt_tokens_per_s']:.0f} prompt tokens/s), "
        f"{res['batch_ms_mean']} ms/batch of {args.batch}, "
        f"NLL {res['plausibility']['mean_nll']}, top-1 {res['plausibility']['top1_share']}, "
        f"missing {res['plausibility']['missing_actual_token']}, "
        f"non-finite {res['plausibility']['nonfinite_logprobs']}"
    )
    print(
        f"projected 1.2M: {res['projection_1_2m']['hours']} h / "
        f"{res['projection_1_2m']['eur']} EUR; 2M: {res['projection_2m']['hours']} h / "
        f"{res['projection_2m']['eur']} EUR"
    )
    print(f"gate {'PASS' if res['gate']['passed'] else 'FAIL'} -> dataset {res['dataset']}; wrote {args.out}")
    if not (res["gate"]["passed"] and plausible) and args.fail_on_gate:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
