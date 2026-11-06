#!/usr/bin/env python3
"""Probe whether an OpenAI-compatible endpoint can actually answer.

Tier-3 behavioral runs are not a gate step, and every blocked measurement in this
repository has cost an investigation to discover the same thing: the endpoint
answered 402, 401, or 503, and the "result" was really the provider. This checker
answers that question in one command, before a run is started and before a
failure is read as a finding.

It sends one five-token request per model and classifies the answer:

    ok              a non-empty completion came back
    unauthorized    the credential was rejected (401/403)
    no_credit       the account cannot pay (402)
    rate_limited    the endpoint asked us to slow down (429)
    overloaded      the upstream provider answered 5xx
    request_rejected any other 4xx (or a redirect): the request itself is wrong,
                    such as a 400 MissingSessionID without --session-header
    unreachable     no HTTP answer at all (DNS, refused, timeout)
    empty           HTTP 200 with no content, which grades as a total miss

The default route is the mandated one: OpenCode Go with `deepseek-v4.1-flash`.
That endpoint rejects a request without `x-opencode-session` (400 MissingSessionID)
and Cloudflare rejects Python-urllib's default user agent (403, error 1010), so a
non-urllib `User-Agent` is always sent and `--session-header` adds the session id
from `--session-id` or `$OPENCODE_SESSION_ID`.

Usage:
    python3 tooling/check_eval_provider.py --session-header
    python3 tooling/check_eval_provider.py --json
    python3 tooling/check_eval_provider.py --base-url https://api.kilocode.ai/api/gateway/v1 \
        --api-key-env KILO_API_KEY --models deepseek/deepseek-chat

Exit 0 when at least one model answers, 1 when none does, 2 on a usage error
(no key in the environment, unusable base URL). ASCII-only output; the key is
never printed or written.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://opencode.ai/inference/go/v1"
DEFAULT_KEY_ENV = "OPENCODE_API_KEY"
DEFAULT_MODELS = ["deepseek-v4.1-flash"]
DEFAULT_USER_AGENT = "agent-prompts-eval/1.0 (+https://github.com/agent-prompts)"
PROBE_PROMPT = "Reply with the single word: ok"
PROBE_MAX_TOKENS = 256  # reasoning models spend the budget on reasoning first
CLASSES = ("ok", "unauthorized", "no_credit", "rate_limited", "overloaded",
           "request_rejected", "unreachable", "empty")


def classify_status(status):
    """Map an HTTP status to a class from CLASSES."""
    if status in (401, 403):
        return "unauthorized"
    if status == 402:
        return "no_credit"
    if status == 429:
        return "rate_limited"
    if 500 <= status <= 599:
        return "overloaded"
    if 200 <= status <= 299:
        return "empty"  # overridden to ok when content arrives
    return "request_rejected"  # another 4xx, or a redirect: the request is wrong


def parse_header(text):
    """Split ``NAME=VALUE`` (or ``NAME: VALUE``) into a header pair."""
    for separator in ("=", ":"):
        if separator in text:
            name, value = text.split(separator, 1)
            name, value = name.strip(), value.strip()
            if name and value:
                return name, value
    raise SystemExit("eval-provider: --header needs NAME=VALUE, got %r" % text)


def request_headers(extra_headers=None, session_header=False, session_id=None,
                    env=None):
    """Headers to send: always a non-urllib UA, plus any the endpoint requires."""
    env = os.environ if env is None else env
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    for text in extra_headers or []:
        name, value = parse_header(text)
        headers[name] = value
    if session_header:
        value = (session_id if session_id is not None
                 else env.get("OPENCODE_SESSION_ID", "")) or ""
        value = value.strip()
        if not value:
            raise SystemExit("eval-provider: --session-header needs --session-id "
                             "or OPENCODE_SESSION_ID")
        headers["x-opencode-session"] = value
    return headers


def probe(base_url, key, model, timeout, headers=None):
    """Return (class, detail) for one model. Never raises."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": PROBE_PROMPT}],
        "max_tokens": PROBE_MAX_TOKENS,
        "temperature": 0,
    }).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=body,
        headers=dict({"Authorization": "Bearer " + key,
                      "Content-Type": "application/json"}, **(headers or {})),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = ""
        try:
            detail = error.read()[:160].decode("utf-8", "replace")
        except Exception:
            detail = ""
        return classify_status(error.code), "http %d %s" % (error.code, detail.strip())
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return "unreachable", type(error).__name__
    except ValueError:
        return "empty", "response was not JSON"
    try:
        choice = payload["choices"][0]
        content = choice["message"].get("content") or ""
    except (KeyError, IndexError, TypeError):
        return "empty", "no choices in the response"
    if not content.strip():
        reasoning = ((payload.get("usage") or {}).get("completion_tokens_details") or {})
        spent = reasoning.get("reasoning_tokens")
        if isinstance(spent, int) and spent > 0:
            return "ok", "reasoning-only (%d reasoning tokens, finish %s)" % (
                spent, choice.get("finish_reason"))
        return "empty", "completion was empty"
    return "ok", content.strip()[:40]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key-env", default=DEFAULT_KEY_ENV)
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS),
                        help="comma-separated model ids to probe")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--header", action="append", default=[], metavar="NAME=VALUE",
                        help="extra request header (repeatable)")
    parser.add_argument("--session-header", action="store_true",
                        help="send x-opencode-session from --session-id or "
                             "$OPENCODE_SESSION_ID")
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    key = os.environ.get(args.api_key_env, "")
    if not key.strip():
        print("eval-provider: %s is empty; cannot probe %s"
              % (args.api_key_env, args.base_url))
        return 2
    models = [item.strip() for item in args.models.split(",") if item.strip()]
    if not models:
        print("eval-provider: no model to probe")
        return 2
    if not args.base_url.startswith(("http://", "https://")):
        print("eval-provider: --base-url must be http or https")
        return 2

    headers = request_headers(args.header, args.session_header, args.session_id)
    if "x-opencode-session" not in headers and "opencode.ai" in args.base_url:
        print("eval-provider: note: %s needs --session-header "
              "(400 MissingSessionID otherwise)" % args.base_url)
    rows = []
    for model in models:
        kind, detail = probe(args.base_url, key, model, args.timeout, headers)
        rows.append({"model": model, "class": kind, "detail": detail})
    ok = [row for row in rows if row["class"] == "ok"]
    if args.json:
        print(json.dumps({"base_url": args.base_url, "key_env": args.api_key_env,
                          "header_names": sorted(headers),
                          "reachable": bool(ok), "models": rows}, indent=2))
    else:
        for row in rows:
            print("%-46s %-13s %s" % (row["model"], row["class"], row["detail"]))
        print("eval-provider: %d of %d model(s) answered on %s"
              % (len(ok), len(rows), args.base_url))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
