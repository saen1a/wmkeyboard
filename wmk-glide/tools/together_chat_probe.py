#!/usr/bin/env python3
"""Check Together's *chat* completions path for prompt logprobs.

Together's chat-completions schema documents `logprobs` (0..20) and `echo`
with "can be used with logprobs to return prompt logprobs". The existing
`together_echo_probe.py` uses the legacy `/v1/completions` shape; this probe
tests the documented chat path, including the free serverless models.

Usage:
    TOGETHER_API_KEY=... python3 together_chat_probe.py \
        --model Prism-ML/Ternary-Bonsai-27B
    python3 together_chat_probe.py --key-file ~/.together.key --model openai/gpt-oss-120b
    python3 together_chat_probe.py --dry-run
    python3 together_chat_probe.py --self-test

Exit codes: 0 response received (inspect the printed logprobs shape),
1 no prompt logprobs visible, 2 no key, 3 HTTP/transport error.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://api.together.xyz/v1/chat/completions"
MODEL = "Prism-ML/Ternary-Bonsai-27B"  # free serverless, if the account can use it
PROMPT = "Ich will nach Hause gehen und morgen"


def build_request(model, prompt, top_n):
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1,
        "temperature": 0,
        "echo": True,
        "top_logprobs": top_n,
        "logprobs": True,
    }


def summarize(payload):
    choice = (payload.get("choices") or [{}])[0]
    lp = choice.get("logprobs")
    usage = payload.get("usage") or {}
    out = {
        "choice_keys": sorted(choice.keys()),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "logprobs_type": type(lp).__name__,
        "logprobs_keys": sorted(lp.keys()) if isinstance(lp, dict) else None,
    }
    if isinstance(lp, dict):
        content = lp.get("content")
        if isinstance(content, list):
            out["content_len"] = len(content)
            out["content_sample"] = content[:5]
            # Chat logprobs normally cover generated tokens only. A prompt
            # echo should make this longer than the generated token count.
            out["content_longer_than_completion"] = len(content) > int(
                usage.get("completion_tokens") or 0
            )
        out["prompt"] = lp.get("prompt")
        out["tokens_head"] = lp.get("tokens", [])[:8] if isinstance(lp.get("tokens"), list) else None
        out["token_logprobs_head"] = (
            lp.get("token_logprobs", [])[:8] if isinstance(lp.get("token_logprobs"), list) else None
        )
    return out


def self_test():
    payload = {
        "choices": [{
            "message": {"role": "assistant", "content": "Hause"},
            "logprobs": {"content": [{"token": "Hause", "logprob": -0.1, "top_logprobs": [{"token": "Hause", "logprob": -0.1}]}]},
        }],
        "usage": {"prompt_tokens": 7, "completion_tokens": 1},
    }
    s = summarize(payload)
    assert s["prompt_tokens"] == 7, s
    assert s["content_len"] == 1, s
    assert s["content_longer_than_completion"] is False, s
    print("self-test ok: chat logprobs shape summarized")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--prompt", default=PROMPT)
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--key-file", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    body = build_request(args.model, args.prompt, args.top_n)
    if args.dry_run:
        print(json.dumps({"url": ENDPOINT, "body": body}, indent=2, ensure_ascii=False))
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

    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "wmk-glide-together-chat-probe/1",
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

    s = summarize(payload)
    print(json.dumps(s, indent=2, ensure_ascii=False))
    if s.get("logprobs_type") != "dict":
        print("No logprobs object in the chat response; not usable.", file=sys.stderr)
        return 1
    if s.get("content_longer_than_completion"):
        print("Chat logprobs are longer than the completion: prompt echo likely included.", file=sys.stderr)
        return 0
    print(
        "Chat logprobs cover only the generated token; prompt echo not visible in this shape.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
