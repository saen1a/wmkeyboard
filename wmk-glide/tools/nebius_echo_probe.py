#!/usr/bin/env python3
"""Does Nebius Token Factory return a usable prompt-logprob distribution?

Nebius exposes an OpenAI-compatible `/v1/completions` endpoint with `echo`
and `logprobs`. DeepInfra had the same shape but capped `top_logprobs` at
1-2 entries; this probe checks whether Nebius returns a real top-N
distribution (target: >= 10 alternatives per prompt position).

Usage:
    NEBIUS_API_KEY=... python3 nebius_echo_probe.py
    NEBIUS_API_KEY=... python3 nebius_echo_probe.py --model Qwen/Qwen3-30B-A3B-Instruct-2507
    python3 nebius_echo_probe.py --key-file ~/.nebius.key
    python3 nebius_echo_probe.py --dry-run
    python3 nebius_echo_probe.py --self-test

Exit codes:
    0  prompt logprobs and a wide top-N distribution are present (usable)
    1  request worked but the distribution is missing/misaligned/too sparse
    2  no key (nothing sent)
    3  transport/HTTP error
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from deepinfra_echo_probe import PROMPT, inspect, self_test as classifier_self_test

ENDPOINT = "https://api.tokenfactory.nebius.com/v1/completions"
MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507"


def build_request(model, prompt, top_n):
    return {
        "model": model,
        "prompt": prompt,
        "max_tokens": 1,
        "temperature": 0,
        "echo": True,
        "logprobs": top_n,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--prompt", default=PROMPT)
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--min-top", type=int, default=10)
    ap.add_argument("--key-file", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        classifier_self_test()
        print("nebius probe reuses the same classifier; self-test ok")
        return 0

    body = build_request(args.model, args.prompt, args.top_n)
    if args.dry_run:
        print(json.dumps({"url": ENDPOINT, "body": body}, indent=2, ensure_ascii=False))
        return 0

    key = os.environ.get("NEBIUS_API_KEY", "").strip()
    if not key and args.key_file:
        try:
            with open(args.key_file, encoding="utf-8") as f:
                key = f.readline().strip()
        except OSError as e:
            print(f"cannot read key file: {e}", file=sys.stderr)
            return 2
    if not key:
        print("NEBIUS_API_KEY is not set; nothing sent.", file=sys.stderr)
        return 2

    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "wmk-glide-nebius-probe/1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            payload = json.load(r)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}", file=sys.stderr)
        return 3
    except Exception as e:  # noqa: BLE001 - diagnostic script
        print(f"error: {e}", file=sys.stderr)
        return 3

    result = inspect(payload, prompt=args.prompt, min_top=args.min_top)
    result["provider"] = "nebius"
    result["model"] = args.model
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
