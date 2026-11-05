#!/usr/bin/env python3
"""Does the Together teacher actually know the next words of our own corpus?

The step between `probe.py` (is the endpoint usable) and
`distill_together.py` (a full pass): it sends real sentences from
`out/de_lm/train.npz` and reports, over every prompt position, the
teacher's mean NLL, how often the actual token is its argmax (top-1), how
often it is among the returned alternatives, and how much probability mass
the returned candidates carry.

Ranking always comes from the logprob (`together_common.candidates`), never
from the position in the unordered `top_logprobs` object.

    python3 token_test.py --data-dir out/de_lm --sentences 100
    python3 token_test.py --data-dir out/de_lm --model openai/gpt-oss-120b
    python3 token_test.py --self-test

Exit codes: 0 report written, 2 no key, 3 transport/HTTP error.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for extra in (HERE, os.path.abspath(os.path.join(HERE, "..", "scaleway"))):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import client as tg  # noqa: E402
import together_common as tc  # noqa: E402
import vllm_common as vc  # noqa: E402


def load_sentences(data_dir, count, seed):
    """The same selection `distill.py` makes, as raw text."""
    vocab, tokens, starts = vc.load_corpus(data_dir)
    chosen = vc.select_indices(len(starts) - 1, count, seed)
    out = []
    for sid in chosen:
        row = tokens[starts[sid]:starts[sid + 1]]
        text, ends = vc.prompt_text(vocab, row)
        if text and ends:
            out.append((int(sid), text))
    return vocab, out


def report(answers, prompts):
    rows = top1 = topk = missing = 0
    nll = 0.0
    widths, masses, misaligned = [], [], 0
    for (sid, text), ch in zip(prompts, answers):
        if "".join(ch.tokens[:ch.prompt_tokens]) != text:
            misaligned += 1
            continue
        st = tc.sentence_audit(ch.tokens, ch.logs, ch.alts, ch.prompt_tokens)
        rows += st["rows"]
        missing += st["missing"]
        if st["mean_nll"] is not None:
            nll += st["mean_nll"] * st["rows"]
        if st["top1"] is not None:
            top1 += st["top1"] * st["rows"]
        if st["width_mean"] is not None:
            widths.append(st["width_mean"])
        for p in range(1, min(ch.prompt_tokens, len(ch.tokens))):
            cand = tc.candidates(ch.tokens, ch.logs, ch.alts, p)
            if cand:
                masses.append(sum(__import__("math").exp(v) for v in cand.values()))
    return {
        "sentences": len(prompts),
        "positions": rows,
        "missing_logprobs": missing,
        "misaligned": misaligned,
        "mean_nll": (nll / rows) if rows else None,
        "top1_argmax": (top1 / rows) if rows else None,
        "width_mean": (sum(widths) / len(widths)) if widths else None,
        "mass_mean": (sum(masses) / len(masses)) if masses else None,
    }


def self_test():
    class C:
        def __init__(self, toks, logs, alts, n):
            self.tokens, self.logs, self.alts, self.prompt_tokens = toks, logs, alts, n

    import math
    lp = math.log
    text = " a b"
    good = C([" a", " b"], [None, lp(0.7)], [{}, {" q": lp(0.2)}], 2)
    bad = C(["a", "b"], [None, lp(0.7)], [{}, {" q": lp(0.2)}], 2)
    r = report([good, bad], [(0, text), (1, text)])
    assert r["misaligned"] == 1, r
    assert r["positions"] == 1, r
    assert abs(r["top1_argmax"] - 1.0) < 1e-9, r
    assert abs(r["mean_nll"] + lp(0.7)) < 1e-9, r
    assert abs(r["mass_mean"] - (0.7 + 0.2)) < 1e-6, r
    print("self-test ok: alignment guard, NLL, top-1, mass")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default="")
    ap.add_argument("--model", default=tg.DEFAULT_MODEL)
    ap.add_argument("--sentences", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--key-file", default="")
    ap.add_argument("--json-out", default="")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)

    if a.self_test:
        self_test()
        return 0
    if not a.data_dir:
        ap.error("--data-dir is required unless --self-test")

    vocab, prompts = load_sentences(a.data_dir, a.sentences, a.seed)
    try:
        client = tg.Client(model=a.model, key_file=a.key_file, batch=a.batch)
    except tg.TogetherError as e:
        print(str(e), file=sys.stderr)
        return 2
    try:
        answers = client.score([text for _, text in prompts])
    except tg.TogetherError as e:
        print(str(e), file=sys.stderr)
        return 3
    res = report(answers, prompts)
    res.update({"model": a.model, "vocab": len(vocab),
                "cost_usd": round(client.cost_usd(0.17, 0.25), 6)})
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if a.json_out:
        vc.write_json(a.json_out, res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
