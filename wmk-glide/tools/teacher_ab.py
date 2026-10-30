#!/usr/bin/env python3
"""Compare two teacher LMs on the same held-out sentences.

This is the fast teacher-only A/B before a full distillation pass. It loads
the baseline (BF16) and the candidate (optionally 8-bit), then measures
next-token top-1/top-8 and NLL on chat and news sentences from heldout.tsv.

Usage:
    python3 teacher_ab.py
    python3 teacher_ab.py --baseline Qwen/Qwen3.5-4B-Base \
        --candidate Qwen/Qwen3.5-9B-Base --candidate-8bit
    python3 teacher_ab.py --per-register 50 --max-tokens 64

It does not write soft targets and does not train; it is the gate before the
10k/1.2M distillation and student A/B.
"""
import argparse
import math
import sys
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


def read_heldout(path, per_register, max_tokens):
    rows = {1: [], 2: []}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            try:
                reg = int(parts[0])
            except ValueError:
                continue
            text = parts[3].strip()
            if reg in rows and text and len(rows[reg]) < per_register:
                rows[reg].append(text[:2000])
    out = []
    for reg, name in ((1, "chat"), (2, "news")):
        out.extend((name, s) for s in rows[reg])
    return out


def load_model(model_id, eight_bit):
    kwargs = {"device_map": {"": 0}, "trust_remote_code": True}
    if eight_bit:
        kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
    else:
        kwargs["torch_dtype"] = torch.bfloat16
    model = AutoModelForCausalLM.from_pretrained(model_id, **kwargs)
    model.eval()
    model.config.use_cache = False
    return model


def score(model, tokenizer, rows, max_tokens):
    stats = {name: {"tokens": 0, "top1": 0, "top8": 0, "nll": 0.0, "sent": 0}
             for name in ("chat", "news")}
    t0 = time.time()
    with torch.inference_mode():
        for name, text in rows:
            ids = tokenizer(text, return_tensors="pt", add_special_tokens=False,
                            truncation=True, max_length=max_tokens)["input_ids"].to("cuda")
            if ids.shape[1] < 2:
                continue
            logits = model(ids).logits[0, :-1].float()
            targets = ids[0, 1:]
            logp = torch.log_softmax(logits, dim=-1)
            actual = logp.gather(1, targets[:, None]).squeeze(1)
            top = torch.topk(logits, k=8, dim=-1).indices
            s = stats[name]
            s["tokens"] += int(targets.numel())
            s["top1"] += int((top[:, 0] == targets).sum())
            s["top8"] += int((top == targets[:, None]).any(dim=1).sum())
            s["nll"] += float(-actual.sum())
            s["sent"] += 1
    wall = time.time() - t0
    for s in stats.values():
        n = max(s["tokens"], 1)
        s["top1_rate"] = s["top1"] / n
        s["top8_rate"] = s["top8"] / n
        s["nll_mean"] = s["nll"] / n
    return stats, wall


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default="Qwen/Qwen3.5-4B-Base")
    ap.add_argument("--candidate", default="Qwen/Qwen3.5-9B-Base")
    ap.add_argument("--candidate-8bit", action="store_true", default=True)
    ap.add_argument("--data", default="../artifacts/data/heldout.tsv")
    ap.add_argument("--per-register", type=int, default=100)
    ap.add_argument("--max-tokens", type=int, default=64)
    args = ap.parse_args()

    rows = read_heldout(args.data, args.per_register, args.max_tokens)
    print(f"rows={len(rows)} (chat/news={sum(1 for n,_ in rows if n=='chat')}/"
          f"{sum(1 for n,_ in rows if n=='news')})", flush=True)

    for label, mid, eight in (("baseline", args.baseline, False),
                              ("candidate", args.candidate, args.candidate_8bit)):
        print(f"=== {label}: {mid} {'8bit' if eight else 'bf16'}", flush=True)
        tok = AutoTokenizer.from_pretrained(mid, trust_remote_code=True)
        model = load_model(mid, eight)
        stats, wall = score(model, tok, rows, args.max_tokens)
        for name in ("chat", "news"):
            s = stats[name]
            print(f"{name:5s} sent={s['sent']:3d} tokens={s['tokens']:6d} "
                  f"top1={s['top1_rate']:.2%} top8={s['top8_rate']:.2%} "
                  f"nll={s['nll_mean']:.3f}", flush=True)
        print(f"wall={wall:.1f}s throughput={len(rows)/wall:.2f} sent/s", flush=True)
        del model
        torch.cuda.empty_cache()

    return 0


if __name__ == "__main__":
    sys.exit(main())
