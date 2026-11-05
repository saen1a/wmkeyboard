#!/usr/bin/env python3
"""Find the safe parallel request count for Chutes Qwen3.8-27B.

Runs the same completion/prompt_logprobs workload at increasing worker counts
and reports throughput, latency, 429s and validation failures. This is the
concurrency ramp for the 1.2M collector; it does not retry, so a 429 is a
real signal, not hidden by backoff.

Usage:
    python3 chutes_concurrency.py --key-file ~/.chutes.key
    python3 chutes_concurrency.py --levels 1,2,4,8,16,32 --sentences 100
    python3 chutes_concurrency.py --prompt-file ../artifacts/data/heldout.tsv
"""
import argparse
import json
import math
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ENDPOINT = "https://llm.chutes.ai/v1/completions"
MODEL = "Qwen/Qwen3.8-27B-TEE"


def read_prompts(path, count):
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            text = parts[3] if len(parts) >= 4 else (parts[-1] if parts else "")
            if text.strip():
                out.append(text.strip())
            if len(out) >= count:
                break
    return out


def one(url, key, model, prompt, top_n, timeout):
    body = {"model": model, "prompt": prompt, "max_tokens": 1,
            "temperature": 0, "stream": False, "prompt_logprobs": top_n}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}",
                 "User-Agent": "wmk-glide-concurrency/1"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            headers = dict(r.headers)
            payload = json.load(r)
        choice = (payload.get("choices") or [{}])[0]
        pl = choice.get("prompt_logprobs") or payload.get("prompt_logprobs")
        widths = [len(x) if isinstance(x, dict) else 0 for x in pl if x is not None] if pl else []
        if not pl or max(widths, default=0) < 2:
            return "invalid", time.time() - t0, None, headers
        return "ok", time.time() - t0, max(widths), headers
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        retry_after = e.headers.get("Retry-After") if e.headers else None
        return f"http{e.code}", time.time() - t0, retry_after, {"body": body[:120]}
    except Exception as e:
        return f"err:{type(e).__name__}", time.time() - t0, None, None


def run_level(url, key, model, prompts, workers, top_n, timeout):
    t0 = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, url, key, model, p, top_n, timeout) for p in prompts]
        for f in futs:
            results.append(f.result())
    wall = time.time() - t0
    ok = [r for r in results if r[0] == "ok"]
    codes = {}
    for r in results:
        codes[r[0]] = codes.get(r[0], 0) + 1
    lats = [r[1] for r in results]
    retry_after = [r[2] for r in results if r[0] == "http429" and r[2]]
    body = next((r[3].get("body") for r in results if r[3] and "body" in r[3]), None)
    print(f"workers={workers:3d} n={len(prompts):4d} ok={len(ok):4d} "
          f"wall={wall:6.1f}s throughput={len(ok)/wall:6.2f}/s "
          f"lat_med={statistics.median(lats):5.2f}s lat_p90={sorted(lats)[max(0,int(len(lats)*0.9)-1)]:5.2f}s "
          f"codes={codes} retry_after={retry_after[:3]}", flush=True)
    if body:
        print(f"  first error body: {body}", flush=True)
    return {"workers": workers, "n": len(prompts), "ok": len(ok), "wall": wall,
            "throughput": len(ok) / wall if wall else 0, "codes": codes,
            "lat_med": statistics.median(lats), "retry_after": retry_after}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key-file", default=None)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--url", default=ENDPOINT)
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--sentences", type=int, default=100)
    ap.add_argument("--prompt-file", default=None)
    ap.add_argument("--levels", default="1,2,4,8,16,32")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--cooldown", type=float, default=2.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.prompt_file:
        prompts = read_prompts(args.prompt_file, args.sentences)
    else:
        prompts = [f"ich will nach Hause gehen und morgen früh {i}" for i in range(args.sentences)]
    if not prompts:
        print("no prompts", file=sys.stderr)
        return 2

    key = None
    if args.key_file:
        with open(args.key_file, encoding="utf-8") as f:
            key = f.readline().strip()
    key = key or __import__("os").environ.get("CHUTES_API_KEY")
    if not key:
        print("no CHUTES_API_KEY / --key-file", file=sys.stderr)
        return 2

    # warm up one request so the first level is not a cold boot
    one(args.url, key, args.model, prompts[0], args.top_n, args.timeout)

    levels = [int(x) for x in args.levels.split(",") if x.strip()]
    rows = []
    for workers in levels:
        rows.append(run_level(args.url, key, args.model, prompts, workers,
                              args.top_n, args.timeout))
        time.sleep(args.cooldown)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
