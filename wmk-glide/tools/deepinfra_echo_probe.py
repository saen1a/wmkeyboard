#!/usr/bin/env python3
"""Does DeepInfra's completions endpoint return log-probabilities for the
*prompt* tokens (not only for generated ones)?

The German `.wmlm` teacher pass needs p(token | prefix) for every token of a
corpus sentence. `tools/wmlm/distill.py` gets that from a local transformers
forward pass. An API teacher is only usable if its OpenAI-compatible
completions endpoint, with `echo=true` and `logprobs=N`, returns
`token_logprobs` for the echoed prompt positions **and** a wide enough
`top_logprobs` set (>= `--min-top` entries) to build a student top-k
target. A single logprob for the chosen token is not a distribution.
DeepInfra's docs describe
`echo` as "prompt included at the start of the returned text" and `logprobs`
as "generated tokens"; they do not promise prompt logprobs. This script
answers the question with one cheap request.

Usage:
    DEEPINFRA_API_KEY=... python3 deepinfra_echo_probe.py
    DEEPINFRA_API_KEY=... python3 deepinfra_echo_probe.py --model Qwen/Qwen3.8-Flash
    python3 deepinfra_echo_probe.py --key-file ~/.deepinfra.key
    python3 deepinfra_echo_probe.py --dry-run
    python3 deepinfra_echo_probe.py --self-test

Exit codes:
    0  prompt logprobs and a wide top-N distribution are present (usable)
    1  request worked but the distribution is missing/misaligned/too sparse
    2  no key (nothing sent)
    3  transport/HTTP error

The prompt is intentionally short: the probe costs a fraction of a cent.

Measured 27.10.2026: `Qwen/Qwen3.5-9B` returns the legacy shape with prompt
logprobs, but only 1-2 `top_logprobs` entries per position, so it fails the
`--min-top` gate. `openai/gpt-oss-120b` rejects `echo`; `Qwen/Qwen3.8-Flash`,
`google/gemma-3-27b-it` and `mistralai/Mistral-Nemo-Instruct-2407` return a
chat-style body without `token_logprobs`.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://api.deepinfra.com/v1/openai/completions"
MODEL = "Qwen/Qwen3.5-9B"
PROMPT = "Ich will nach Hause gehen und morgen"
TOP_N = 20


def build_request(model, prompt, top_n):
    return {
        "model": model,
        "prompt": prompt,
        "max_tokens": 1,
        "temperature": 0,
        "echo": True,
        "logprobs": top_n,
        # The schema has this switch; if honoured for prompt tokens the
        # response gives token ids directly instead of byte-level strings.
        "return_tokens_as_token_ids": True,
    }


def _completion_logprobs(choice):
    """The legacy completions shape, or None for the chat shape."""
    lp = choice.get("logprobs")
    if not isinstance(lp, dict) or "token_logprobs" not in lp:
        return None
    return lp


def inspect(payload, prompt=PROMPT, prompt_tokens=None, min_top=10):
    """Classify one response body. Pure, so --self-test can exercise it.

    A teacher needs a *distribution*, not just the chosen token. The first
    prompt position has no context and is naturally null; positions 1..n-1
    must carry a logprob and a wide enough `top_logprobs` entry set.
    """
    choices = payload.get("choices") or []
    if not choices:
        return {"verdict": "FAIL", "reason": "no choices"}
    choice = choices[0]
    text = choice.get("text") or ""
    usage = payload.get("usage") or {}
    prompt_tokens = prompt_tokens or usage.get("prompt_tokens") or 0
    if not prompt_tokens:
        # Without usage.prompt_tokens the echoed prefix cannot be separated
        # from the generated token(s), so the answer is not usable.
        return {
            "verdict": "FAIL",
            "reason": "usage.prompt_tokens missing; cannot locate the prompt positions",
            "text": text[:80],
        }
    lp = _completion_logprobs(choice)
    if lp is None:
        return {
            "verdict": "FAIL",
            "reason": "choices[0].logprobs is not the legacy completions shape "
                      "(no token_logprobs); chat-style response",
            "text": text[:80],
            "prompt_tokens": prompt_tokens,
        }
    tokens = lp.get("tokens") or []
    logs = lp.get("token_logprobs") or []
    tops = lp.get("top_logprobs") or []
    n = min(len(tokens), len(logs))
    # With echo, the first usage.prompt_tokens positions are the prompt.
    limit = prompt_tokens
    # Position 0 has no context; only 1..limit-1 are usable teacher targets.
    checked_logs = logs[1:limit]
    present = sum(1 for x in checked_logs if x is not None)
    need = max(0, limit - 1)
    # Count a *missing* entry as zero alternatives. The old version only
    # looked at the entries that were present, so a body with no top sets at
    # all skipped the width gate entirely (audit finding, 2026-11-03).
    top_counts = []
    for i in range(1, limit):
        t = tops[i] if i < len(tops) else None
        if isinstance(t, dict):
            top_counts.append(len(t))
        elif isinstance(t, (list, tuple)):
            top_counts.append(len(t))
        else:
            top_counts.append(0)
    top_min = min(top_counts) if top_counts else 0
    top_med = sorted(top_counts)[len(top_counts) // 2] if top_counts else 0
    top_present = sum(1 for x in tops[:limit] if x)
    echoed = text.startswith(prompt[:20]) if text else False
    if prompt_tokens and len(tokens) < prompt_tokens:
        verdict = "PARTIAL"
        reason = f"only {len(tokens)} logprob tokens for {prompt_tokens} prompt tokens"
    elif present == 0:
        verdict = "FAIL"
        reason = "prompt positions are null or absent: echo does not log prompt tokens"
    elif present < need:
        verdict = "PARTIAL"
        reason = f"{present}/{need} usable prompt positions have a logprob"
    elif top_min < max(1, min_top):
        verdict = "FAIL"
        reason = (
            f"prompt logprobs exist, but top_logprobs are too sparse: "
            f"{top_min} entries minimum, {top_med} median per position "
            f"(need >= {max(1, min_top)}); only the chosen token is exposed"
        )
    else:
        verdict = "PASS"
        reason = (
            f"{present}/{need} usable prompt positions have logprobs; "
            f"top_logprobs {top_min}..{max(top_counts)} entries (min {min_top})"
        )
    return {
        "verdict": verdict,
        "reason": reason,
        "text": text[:80],
        "prompt_tokens": prompt_tokens,
        "logprob_tokens": len(tokens),
        "prompt_logprobs_present": present,
        "prompt_positions_needed": need,
        "prompt_top_logprobs_present": top_present,
        "top_entries_min": top_min,
        "top_entries_median": top_med,
        "min_top_required": min_top,
        "echoed": echoed,
        "sample": [
            {"token": tokens[i], "logprob": logs[i]}
            for i in range(min(5, n))
        ],
        "usage": usage,
    }


def self_test():
    wide = [{f"t{i}_{j}": -float(j) for j in range(10)} for i in range(8)]
    base = {
        "choices": [{
            "text": PROMPT + " ",
            "logprobs": {
                "tokens": ["Ich", " will", " nach", " Hause", " gehen", " und", " morgen", " "],
                "token_logprobs": [None, -1.5, -2.0, -0.5, -0.8, -1.1, -2.2, -0.1],
                "top_logprobs": wide,
            },
        }],
        "usage": {"prompt_tokens": 7, "completion_tokens": 1},
    }
    good = inspect(base)
    assert good["verdict"] == "PASS", good

    sparse = json.loads(json.dumps(base))
    sparse["choices"][0]["logprobs"]["top_logprobs"] = [
        {} if i == 0 else {"a": -1.0, "b": -2.0} for i in range(8)
    ]
    sparse_result = inspect(sparse)
    assert sparse_result["verdict"] == "FAIL", sparse_result
    assert "too sparse" in sparse_result["reason"], sparse_result

    nulled = json.loads(json.dumps(base))
    nulled["choices"][0]["logprobs"]["token_logprobs"] = [None] * 7 + [-0.1]
    bad = inspect(nulled)
    assert bad["verdict"] == "FAIL", bad

    chat = {"choices": [{"message": {"content": "x"}}], "usage": {"prompt_tokens": 7}}
    assert inspect(chat)["verdict"] == "FAIL"

    nousage = json.loads(json.dumps(base))
    del nousage["usage"]
    assert inspect(nousage)["verdict"] == "FAIL", nousage

    print("self-test ok: PASS/sparse/FAIL/chat-shape/no-usage all classified")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--prompt", default=PROMPT)
    ap.add_argument("--top-n", type=int, default=20, help="requested teacher top-N")
    ap.add_argument(
        "--min-top",
        type=int,
        default=10,
        help="minimum top_logprobs entries per prompt position to be usable",
    )
    ap.add_argument(
        "--key-file",
        default="",
        help="read the key from this file (first line); alternative to DEEPINFRA_API_KEY",
    )
    ap.add_argument("--dry-run", action="store_true", help="print the request, send nothing")
    ap.add_argument("--self-test", action="store_true", help="test the response classifier offline")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    body = build_request(args.model, args.prompt, args.top_n)
    if args.dry_run:
        print(json.dumps({"url": ENDPOINT, "body": body}, indent=2, ensure_ascii=False))
        return 0

    key = os.environ.get("DEEPINFRA_API_KEY", "").strip()
    if not key and args.key_file:
        try:
            with open(args.key_file, encoding="utf-8") as f:
                key = f.readline().strip()
        except OSError as e:
            print(f"cannot read key file: {e}", file=sys.stderr)
            return 2
    if not key:
        print("DEEPINFRA_API_KEY is not set; nothing sent.", file=sys.stderr)
        return 2

    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "wmk-glide-echo-probe/1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            payload = json.load(r)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}", file=sys.stderr)
        return 3
    except Exception as e:  # noqa: BLE001 - diagnostic script
        print(f"error: {e}", file=sys.stderr)
        return 3

    result = inspect(payload, prompt=args.prompt, min_top=args.min_top)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
