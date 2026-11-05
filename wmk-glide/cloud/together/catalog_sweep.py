#!/usr/bin/env python3
"""Ask every Together text model the same question: do you give prompt log-probs?

One short echo request per model. This is the only way to answer "are Qwen3.5-9B
and gpt-oss-120b really the only ones" without trusting the catalogue's price
column. Output: JSON with one line per model and the usable shortlist.

    python3 catalog_sweep.py                 # all text models
    python3 catalog_sweep.py --only priced   # only non-zero price (serverless)
    python3 catalog_sweep.py --self-test
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import client as tg  # noqa: E402

PROMPT = "Ich will nach Hause gehen und morgen"
TEXT_TYPES = ("language", "chat")


def classify(choice, prompt=PROMPT):
    """(usable, reason) for one answer. Pure."""
    n = choice.prompt_tokens
    if n < 2:
        return False, f"only {n} prompt token(s) scored"
    if "".join(choice.tokens[:n]) != prompt:
        return False, "echo not honoured (response does not reproduce the prompt)"
    widths = [len(choice.alts[p]) for p in range(1, n) if p < len(choice.alts)]
    if not widths:
        return False, "no top_logprobs at any prompt position"
    if max(widths) < 2:
        return False, f"only {max(widths)} alternative per position"
    return True, f"width {min(widths)}-{max(widths)}, positions {n - 1}"


def list_models(key_file=""):
    import urllib.request

    req = urllib.request.Request(
        "https://api.together.xyz/v1/models",
        headers={"Authorization": f"Bearer {tg.resolve_key(key_file=key_file)}",
                 "User-Agent": tg.USER_AGENT}, method="GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = json.load(r)
    out = []
    for m in raw:
        if m.get("type") not in TEXT_TYPES:
            continue
        price = (m.get("pricing") or {}).get("input")
        try:
            price = float(price)
        except (TypeError, ValueError):
            price = None
        out.append({"id": m["id"], "type": m.get("type"), "ctx": m.get("context_length"),
                    "price_in": price})
    return sorted(out, key=lambda x: x["id"])


def sweep(models, key_file="", probe=()):
    """Probe every model; `probe` is a callable for tests."""
    results = {}
    for m in models:
        try:
            choice = probe(m) if probe else tg.Client(
                model=m["id"], key_file=key_file, batch=1).score_one(PROMPT)
            ok, why = classify(choice)
        except tg.TogetherError as e:
            ok, why = False, str(e).replace("\n", " ")[:120]
        results[m["id"]] = {"ok": ok, "reason": why, "type": m["type"],
                            "price_in": m["price_in"]}
    return results


def self_test():
    class C:
        def __init__(self, toks, alts, n=None):
            self.tokens = toks
            self.prompt_tokens = len(toks) if n is None else n
            self.alts = alts

    short = "Ich will nach"
    good = C(["Ich", " will", " nach"], [{}, {" a": -1.0}, {" b": -1.0, " c": -2.0}])
    assert classify(good, short) == (True, "width 1-2, positions 2"), classify(good, short)
    bad = C(["?"], [{}], 1)
    assert classify(bad, short)[0] is False, classify(bad, short)
    mis = C(["nope", " x"], [{}, {" a": -1.0}])
    assert "echo" in classify(mis, short)[1], classify(mis, short)
    one = C(["Ich", " will"], [{}, {" a": -1.0}])
    assert classify(one, short)[0] is False, classify(one, short)
    print("self-test ok: usable, short prompt, misaligned, single alternative")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="all", choices=["all", "priced"])
    ap.add_argument("--skip", default="", help="comma-separated ids to skip")
    ap.add_argument("--key-file", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)

    if a.self_test:
        self_test()
        return 0

    catalog = list_models(a.key_file)
    if a.only == "priced":
        catalog = [m for m in catalog if (m["price_in"] or 0) > 0]
    skip = {s.strip() for s in a.skip.split(",") if s.strip()}
    catalog = [m for m in catalog if m["id"] not in skip]
    print(f"{len(catalog)} text models to probe", file=sys.stderr)

    results = sweep(catalog, a.key_file)
    usable = sorted(k for k, v in results.items() if v["ok"])
    print(f"\n**{len(usable)} usable of {len(results)}**\n")
    print("| model | price in/1M | result |")
    print("|---|---:|---|")
    for k in usable:
        print(f"| `{k}` | {results[k]['price_in']} | {results[k]['reason']} |")
    print("\nrejected (grouped):")
    groups = {}
    for k, v in results.items():
        if v["ok"]:
            continue
        key = ("non-serverless" if "non-serverless" in v["reason"]
               else "echo not honoured" if "echo" in v["reason"]
               else "batch prompts" if "batch_prompts" in v["reason"]
               else "chat-only/role" if "Role must be" in v["reason"]
               else "other")
        groups.setdefault(key, []).append(k)
    for key, names in sorted(groups.items()):
        print(f"  {key}: {len(names)}")
        for n in names[:40]:
            print(f"    - {n}")

    payload = {"prompt": PROMPT, "models": results, "usable": usable}
    if a.out:
        tmp = a.out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=1, ensure_ascii=False, default=str)
            f.write("\n")
        os.replace(tmp, a.out)
        print(f"\nwrote {a.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
