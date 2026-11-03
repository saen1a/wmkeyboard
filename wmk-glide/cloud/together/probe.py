#!/usr/bin/env python3
"""Capability probe for Together's prompt log-probs — and their limits.

Replaces the three ad-hoc probes (`together_echo_probe.py`,
`together_chat_probe.py`, `together_token_test.py`) with one script whose
classifier cannot pass on a half-missing body (the old shared classifier in
`tools/deepinfra_echo_probe.py:117-147` gated only the `top_logprobs` entries
that were *present*, so a body with no top sets at all could report PASS).

Modes:

  completions  (default) one array request, full report: echo alignment,
               alternatives per prompt position, argmax-vs-actual agreement
               (the cheap corruption detector the Chutes MTP bug needed),
               captured mass, and a PASS/FAIL against `--min-top`.
  chat         sends the chat shape and reports that prompt log-probs are
               not available there (the path is closed, KB §2b).
  repeat       pins today's negative results: identical requests,
               `temperature`/`n`/`seed`/`top_p` and a `logit_bias` sweep over
               the whole id range leave the prompt distribution unchanged.
  breadth      array-prompt throughput at several batch sizes.

Exit codes (one contract, unlike the four schemes in `tools/`):
  0 PASS (completions) / report written (chat, repeat, breadth)
  1 width below --min-top (sparse)
  2 no key
  3 transport or HTTP error
  4 echo mismatch (response does not reproduce the prompt)
"""
import argparse
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import client as tg  # noqa: E402

PROMPT = "Ich will nach Hause gehen und morgen"
BATCH_PROMPTS = [
    "Ich will nach Hause gehen und morgen früh losfahren.",
    "Der Zug fällt leider aus, deshalb nehmen wir das Auto.",
    "Kannst du mir bitte sagen, wo die nächste Tankstelle ist?",
    "Die Kinder haben den ganzen Nachmittag im Garten gespielt.",
    "Wir müssen noch Brot, Milch und Käse einkaufen, bevor der Laden schließt.",
]


def inspect(choice, prompt, min_top=10):
    """Classify one answer. Pure, so `--self-test` can exercise it offline.

    Every gate is independent: a body that is sparse *and* misaligned reports
    both, and a missing `top_logprobs` entry counts as zero alternatives
    rather than vanishing from the average.
    """
    n = choice.prompt_tokens
    toks = choice.tokens[:n]
    logs = choice.logs[:n]
    alts = choice.alts[:n]
    echoed = "".join(toks)
    widths, agree, positions, present, mass = [], 0, 0, 0, []
    for p in range(1, n):
        entries = dict(alts[p]) if p < len(alts) else {}
        lp = logs[p] if p < len(logs) else None
        if p < len(toks) and lp is not None and math.isfinite(lp):
            entries.setdefault(toks[p], lp)
        present += 1 if (p < len(alts) and alts[p]) else 0
        positions += 1
        widths.append(len(entries))
        if not entries:
            continue
        mass.append(sum(math.exp(v) for v in entries.values() if math.isfinite(v)))
        best = max(entries.items(), key=lambda kv: kv[1])[0]
        agree += toks[p] == best
    width_min = min(widths) if widths else 0
    width_med = sorted(widths)[len(widths) // 2] if widths else 0
    out = {
        "prompt_tokens": n,
        "echo_aligned": echoed == prompt,
        "positions": positions,
        "positions_with_alts": present,
        "width_min": width_min,
        "width_median": width_med,
        "argmax_agreement": (agree / positions) if positions else None,
        "mass_mean": (sum(mass) / len(mass)) if mass else None,
        "min_top": min_top,
    }
    if not out["echo_aligned"]:
        out["verdict"] = "MISALIGNED"
    elif positions == 0:
        out["verdict"] = "FAIL"
        out["reason"] = "no usable prompt positions"
    elif present < positions:
        out["verdict"] = "FAIL"
        out["reason"] = f"{positions - present}/{positions} positions carried no alternatives"
    elif width_min < max(1, min_top):
        out["verdict"] = "SPARSE"
        out["reason"] = (f"{width_min} alternatives minimum, {width_med} median "
                         f"per position (need >= {min_top})")
    else:
        out["verdict"] = "PASS"
    return out


def run_completions(args):
    client = tg.Client(model=args.model, key_file=args.key_file, batch=1)
    try:
        choice = client.score_one(args.prompt)
    except tg.TogetherError as e:
        print(json.dumps({"mode": "completions", "verdict": "MISALIGNED",
                          "error": str(e)}, indent=2, ensure_ascii=False))
        return 4
    res = inspect(choice, args.prompt, args.min_top)
    res.update({"mode": "completions", "model": args.model, "provider": "together",
                "cost_usd": round(client.cost_usd(0.17, 0.25), 6)})
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return {"PASS": 0, "SPARSE": 1, "FAIL": 1}.get(res["verdict"], 4)


def run_chat(args):
    """The chat path has no prompt log-probs; prove it instead of claiming it."""
    import urllib.error
    import urllib.request

    body = {"model": args.model,
            "messages": [{"role": "user", "content": args.prompt}],
            "max_tokens": 1, "temperature": 0, "logprobs": True,
            "top_logprobs": tg.MAX_LOGPROBS}
    req = urllib.request.Request(
        tg.CHAT_ENDPOINT, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {tg.resolve_key(key_file=args.key_file)}",
                 "User-Agent": tg.USER_AGENT}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            payload = json.load(r)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}", file=sys.stderr)
        return 3
    content = ((payload.get("choices") or [{}])[0].get("logprobs") or {}).get("content") or []
    widths = [len(x.get("top_logprobs") or {}) for x in content]
    print(json.dumps({
        "mode": "chat", "model": args.model,
        "generated_positions": len(content),
        "alternatives_per_generated_position": widths,
        "prompt_logprobs_present": False,
        "verdict": "chat has no prompt log-probs (only generated tokens); "
                   "use /v1/completions with echo",
        "usage": payload.get("usage"),
    }, indent=2, ensure_ascii=False))
    return 0


def run_repeat(args):
    """Pin the negative results of 2026-11-03 so a regression is visible."""
    client = tg.Client(model=args.model, key_file=args.key_file, batch=1)
    base = client.score_one(args.prompt)
    idx = min(6, base.prompt_tokens - 1)
    ref = sorted(base.alts[idx].items(), key=lambda kv: -kv[1])
    out = {"mode": "repeat", "position": idx, "reference": ref, "variants": {}}
    for label, extra in (("temperature=1.2", {"temperature": 1.2}),
                         ("n=3", {"temperature": 1.0, "n": 3}),
                         ("seed=42", {"seed": 42}),
                         ("top_p=0.5", {"temperature": 1.0, "top_p": 0.5})):
        body = {"model": args.model, "prompt": [args.prompt], "max_tokens": 1,
                "echo": True, "logprobs": tg.MAX_LOGPROBS, **extra}
        try:
            payload = client._call(body)          # noqa: SLF001 - probe, not pipeline
        except tg.TogetherError as e:
            out["variants"][label] = {"error": str(e)}
            continue
        got = sorted(client._parse(payload, 1, "").__getitem__(0).alts[idx].items(),  # noqa: SLF001
                     key=lambda kv: -kv[1])
        out["variants"][label] = {"values": got, "unchanged": got == ref}

    # A bias over the whole vocabulary: prompt scoring ignores it, so no
    # suppression round can widen the support.
    bias = {str(i): -100 for i in range(0, args.bias_ids)}
    body = {"model": args.model, "prompt": [args.prompt], "max_tokens": 1,
            "temperature": 0, "echo": True, "logprobs": tg.MAX_LOGPROBS,
            "logit_bias": bias}
    try:
        payload = client._call(body)
        got = sorted(client._parse(payload, 1, "").__getitem__(0).alts[idx].items(),  # noqa: SLF001
                     key=lambda kv: -kv[1])
        out["variants"][f"logit_bias<{args.bias_ids}"] = {"values": got, "unchanged": got == ref}
    except tg.TogetherError as e:
        out["variants"][f"logit_bias<{args.bias_ids}"] = {"error": str(e)}
    out["all_unchanged"] = all(v.get("unchanged") for v in out["variants"].values())
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def run_breadth(args):
    client = tg.Client(model=args.model, key_file=args.key_file, batch=1000)
    rows = []
    for n in (1, 20, 80, 200, 1000):
        prompts = [BATCH_PROMPTS[i % len(BATCH_PROMPTS)] for i in range(n)]
        t0 = time.time()
        try:
            answers = client.score(prompts)
        except tg.TogetherError as e:
            rows.append({"batch": n, "error": str(e)})
            continue
        dt = time.time() - t0
        ok = all("".join(a.tokens[:a.prompt_tokens]) for a in answers)
        rows.append({"batch": n, "answers": len(answers), "seconds": round(dt, 2),
                     "sentences_per_s": round(len(answers) / dt, 1), "tokens_ok": ok})
    print(json.dumps({"mode": "breadth", "model": args.model, "rows": rows},
                     indent=2, ensure_ascii=False))
    return 0


def self_test():
    """Classifier tests, including the cases the old shared classifier missed."""
    class C:
        def __init__(self, toks, logs, alts, n):
            self.tokens, self.logs, self.alts, self.prompt_tokens = toks, logs, alts, n

    lp = math.log
    prompt = " a b c"
    # 1. healthy: 5 alternatives everywhere, actual token is the argmax -> PASS
    toks, logs = [" a", " b", " c"], [None, lp(0.5), lp(0.4)]
    alts = [{}, {" x": lp(0.2), " y": lp(0.1), " z": lp(0.05), " w": lp(0.01), " v": lp(0.02)},
            {" x": lp(0.2), " y": lp(0.1), " z": lp(0.05), " w": lp(0.01), " v": lp(0.02)}]
    r = inspect(C(toks, logs, alts, 3), prompt, min_top=5)
    assert r["verdict"] == "PASS", r
    assert abs(r["argmax_agreement"] - 1.0) < 1e-9, r
    assert r["width_min"] == 6, r          # 5 returned + the actual token

    # 2. a position whose alternatives are missing entirely must NOT pass:
    #    this is the old hole (missing entries simply vanished from the average)
    r = inspect(C(toks, logs, [{}, {}, {}], 3), prompt, min_top=1)
    assert r["verdict"] == "FAIL", r
    assert r["positions_with_alts"] == 0, r

    # 3. width below the requirement is SPARSE, not PASS, and min_top=0 cannot crash
    r = inspect(C(toks, logs, [{}, {" x": lp(0.1)}, {" x": lp(0.1)}], 3), prompt, min_top=10)
    assert r["verdict"] == "SPARSE", r
    r0 = inspect(C(toks, logs, [{}, {}, {}], 3), prompt, min_top=0)
    assert r0["verdict"] == "FAIL", r0

    # 4. an echo that does not reproduce the prompt is MISALIGNED (exit 4)
    r = inspect(C(["a", "b", "c"], logs, alts, 3), prompt, min_top=1)
    assert r["verdict"] == "MISALIGNED", r

    # 5. argmax disagreement is reported (the corruption detector)
    r = inspect(C(toks, [None, lp(0.01), lp(0.4)], alts, 3), prompt, min_top=1)
    assert abs(r["argmax_agreement"] - 0.5) < 1e-9, r
    print("self-test ok: healthy, missing-alts, sparse, min-top-0, misaligned, disagreement")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", default="completions",
                    choices=["completions", "chat", "repeat", "breadth"])
    ap.add_argument("--model", default=tg.DEFAULT_MODEL)
    ap.add_argument("--prompt", default=PROMPT)
    ap.add_argument("--min-top", type=int, default=10,
                    help="PASS needs this many alternatives per position (0 is clamped to 1)")
    ap.add_argument("--bias-ids", type=int, default=20000)
    ap.add_argument("--key-file", default="")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        self_test()
        return 0
    try:
        tg.resolve_key(key_file=args.key_file)
    except tg.TogetherError as e:
        print(str(e), file=sys.stderr)
        return 2
    if args.mode == "completions":
        return run_completions(args)
    if args.mode == "chat":
        return run_chat(args)
    if args.mode == "repeat":
        return run_repeat(args)
    return run_breadth(args)


if __name__ == "__main__":
    sys.exit(main())
