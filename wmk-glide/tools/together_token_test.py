#!/usr/bin/env python3
"""Cheap Together AI probe on real corpus sentences: teacher-token top-1/top-k.

This is the step between the single echo probe and a full `distill_api.py`:
it sends 100 German sentences with `echo=true` and `logprobs=5` (Together's
hard cap; `together_echo_probe.py` explains why), then checks whether the
actual next teacher token is inside the returned top-1/top-k at every prompt
position. No student-vocabulary mapping yet; that comes only if the API
exposes a real distribution.

Usage:
    TOGETHER_API_KEY=... python3 together_token_test.py \
        --data-dir /root/wmlm-de/out/de_lm --model Qwen/Qwen3.5-9B
    python3 together_token_test.py --key-file ~/.together.key \
        --data-dir /root/wmlm-de/out/de_lm --model Qwen/Qwen3.8-Flash
    python3 together_token_test.py --dry-run --data-dir ... --model ...
    python3 together_token_test.py --self-test

The test is read-only and writes nothing except stdout.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np

ENDPOINT = "https://api.together.xyz/v1/completions"
PREFIX_LEN = 4
START = "\u2581"
CONT = "##"
PRICES = {
    "Qwen/Qwen3.5-9B": (0.17, 0.25),
    "Qwen/Qwen3.8-Flash": (0.15, 0.47),
    "Qwen/Qwen3.5-397B-A17B": (0.60, 3.60),
    "openai/gpt-oss-120b": (0.15, 0.60),
}


def sentence_text(row, vocab):
    """Rebuild the teacher text from the student token row."""
    words = [vocab[t] for t in row[PREFIX_LEN:-1]]
    text, ends = "", []
    for w in words:
        if w.startswith(CONT):
            text += w[len(CONT):]
            ends[-1] = len(text)
        else:
            text += " " + (w[len(START):] if w.startswith(START) else w)
            ends.append(len(text))
    return text, ends


def entries(entry):
    """(token, logprob) pairs from one position of `top_logprobs`."""
    if isinstance(entry, dict):
        return list(entry.items())
    out = []
    for x in entry if isinstance(entry, list) else []:
        if isinstance(x, dict):
            out.append((x.get("token", x.get("token_id")), x.get("logprob")))
    return out


def parse_and_score(payload, topk=5):
    """Return (positions, top1, topk_hits) from a legacy completions body.

    Together returns `top_logprobs` as an **unordered** JSON object: measured
    2026-11-03, only 11 of 233 positions came back sorted descending, and the
    order changed between two identical requests. The rank of an alternative
    therefore comes from its logprob, never from its position in the object.
    """
    lp = (payload.get("choices") or [{}])[0].get("logprobs")
    if not isinstance(lp, dict) or "token_logprobs" not in lp:
        raise ValueError("no legacy logprobs in response")
    tokens = lp.get("tokens") or []
    tops = lp.get("top_logprobs") or []
    usage = payload.get("usage") or {}
    prompt_tokens = usage.get("prompt_tokens") or len(tokens)
    tokens = tokens[:prompt_tokens]
    tops = tops[:prompt_tokens]
    positions = top1 = hit = 0
    for i in range(1, len(tokens)):
        cand = entries(tops[i]) if i < len(tops) else []
        cand = [(t, v) for t, v in cand if t is not None]
        if not cand:
            continue
        positions += 1
        ranked = sorted(cand, key=lambda kv: -(kv[1] if isinstance(kv[1], (int, float)) else -1e9))
        if tokens[i] == ranked[0][0]:
            top1 += 1
        if tokens[i] in [t for t, _ in ranked[:topk]]:
            hit += 1
    return positions, top1, hit


def call(model, prompt, top_n, key, timeout=90, endpoint=ENDPOINT):
    body = {
        "model": model,
        "prompt": prompt,
        "max_tokens": 1,
        "temperature": 0,
        "echo": True,
        "logprobs": top_n,
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "wmk-glide-together-token-test/1",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def load_sentences(data_dir, count, seed):
    vocab = [line.rstrip("\n") for line in open(os.path.join(data_dir, "vocab.txt"), encoding="utf-8")]
    z = np.load(os.path.join(data_dir, "train.npz"))
    tokens, starts = z["tokens"], z["starts"]
    n = len(starts) - 1
    rng = np.random.default_rng(seed)
    chosen = np.sort(rng.choice(n, size=min(count, n), replace=False))
    out = []
    for s in chosen:
        row = tokens[starts[s] : starts[s + 1]]
        text, _ = sentence_text(row, vocab)
        out.append(text)
    return out


def self_test():
    # Deliberately unordered: position 2 lists "C" (logprob -1.0) after "B"
    # (-2.0). A rank-from-position implementation scores it as a miss.
    payload = {
        "choices": [{
            "logprobs": {
                "tokens": ["A", "B", "C", "D"],
                "token_logprobs": [None, -1.0, -1.0, -1.0],
                "top_logprobs": [
                    {},
                    {"B": -1.0, "X": -2.0},
                    {"B": -2.0, "C": -1.0},
                    {"X": -1.0, "Y": -2.0},
                ],
            }
        }],
        "usage": {"prompt_tokens": 4},
    }
    positions, top1, hit = parse_and_score(payload, topk=5)
    assert positions == 3, positions
    assert top1 == 2, top1
    assert hit == 2, hit
    print("self-test ok: 3 positions, top-1 2, top-5 2 (unordered input)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", required=False)
    ap.add_argument("--model", default="Qwen/Qwen3.5-9B")
    ap.add_argument("--sentences", type=int, default=100)
    ap.add_argument("--top-n", type=int, default=5)
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--endpoint", default=ENDPOINT)
    ap.add_argument("--key-file", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.data_dir:
        sys.exit("--data-dir is required unless --self-test")
    texts = load_sentences(args.data_dir, args.sentences, args.seed)
    if not texts:
        sys.exit("no sentences selected")
    if args.dry_run:
        print(json.dumps({"url": args.endpoint, "model": args.model, "prompt": texts[0],
                          "max_tokens": 1, "temperature": 0, "echo": True,
                          "logprobs": args.top_n}, indent=2, ensure_ascii=False))
        return 0

    key = os.environ.get("TOGETHER_API_KEY", "").strip()
    if not key and args.key_file:
        try:
            with open(args.key_file, encoding="utf-8") as f:
                key = f.readline().strip()
        except OSError as e:
            print(f"cannot read key file: {e}", file=sys.stderr)
            return 2
    if not key:
        print("TOGETHER_API_KEY is not set; nothing sent.", file=sys.stderr)
        return 2

    def one(text):
        try:
            payload = call(args.model, text, args.top_n, key, endpoint=args.endpoint)
            return parse_and_score(payload, args.topk), payload.get("usage") or {}
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")[:300]
        except Exception as e:  # noqa: BLE001 - diagnostic script
            return None, str(e)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        results = list(ex.map(one, texts))

    positions = top1 = hit = 0
    prompt_tokens = completion_tokens = 0
    errors = []
    for r, usage in results:
        if isinstance(r, tuple) and len(r) == 3 and all(isinstance(x, int) for x in r):
            p, t, h = r
            positions += p
            top1 += t
            hit += h
            prompt_tokens += int(usage.get("prompt_tokens") or 0)
            completion_tokens += int(usage.get("completion_tokens") or 0)
        else:
            errors.append((r, usage))

    elapsed = time.time() - t0
    print(f"model {args.model}: {len(texts)} sentences, {positions} positions, {elapsed:.1f}s")
    if positions:
        print(f"top-1 {top1}/{positions} ({100*top1/positions:.1f}%)  "
              f"top-{args.topk} {hit}/{positions} ({100*hit/positions:.1f}%)")
    price = PRICES.get(args.model)
    if price and (prompt_tokens or completion_tokens):
        cost = prompt_tokens / 1e6 * price[0] + completion_tokens / 1e6 * price[1]
        print(f"tokens prompt={prompt_tokens} completion={completion_tokens}, cost≈${cost:.4f}")
    if errors:
        print(f"errors: {len(errors)}", file=sys.stderr)
        for r, u in errors[:3]:
            print(f"  {r}: {u}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
