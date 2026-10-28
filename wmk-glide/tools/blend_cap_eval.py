#!/usr/bin/env python3
"""Sweep a capped score-space context blend over a glide pool dump.

This is the shape `SuggestionEngine.blendGlideContextModel` ships:

    shift(c) = clamp(weight * (lnP(c | previous) - lnP(leader | previous)), -cap, +cap)
    rank by decoder score + shift

The pool is the decoder's own top 8 (`GLIDE_RERANK_POOL`). The language model
is a bigram built from the corpus's `sentence` fields, the same stand-in as
`rerank_eval.py`; the downloaded `.wmlm` is not available to this harness.

    ALL=1 RESULTS=8 DUMP=pool.jsonl COLS=11 THREADS=8 \\
        glide_beam_eval de_swipes.jsonl german.json de_150k.txt
    python3 tools/blend_cap_eval.py pool.jsonl de_swipes.jsonl
"""

import argparse
import json
import math
import re
import sys
from collections import Counter

LAMBDA = 0.7
WEIGHTS = (0.3, 0.5, 0.7, 1.0, 1.5)
CAPS = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, float("inf"))


def tokens(sentence):
    return [re.sub(r"[^\w\u00e4\u00f6\u00fc\u00df]", "", t.lower()) for t in sentence.split()]


def load_dump(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            fields = line.split("\t")
            pool = []
            for part in fields[4].split("|"):
                if not part:
                    continue
                word, sep, score = part.rpartition(":")
                if sep and score:
                    pool.append((word, float(score)))
            rows.append((fields[0], pool))
    return rows


def load_strokes(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            w = r["word"].lower()
            if len(w) >= 2 and w.isalpha():
                out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("strokes")
    ap.add_argument("--weight", type=float, default=0.7, help="the shipped GLIDE_LM_BLEND")
    ap.add_argument("--cap", type=float, default=3.0, help="the shipped GLIDE_LM_BLEND_CAP")
    args = ap.parse_args()

    rows = load_dump(args.dump)
    strokes = load_strokes(args.strokes)
    if len(rows) != len(strokes):
        raise SystemExit(f"{len(rows)} dump lines vs {len(strokes)} strokes")

    unigram = Counter()
    bigram = Counter()
    previous = Counter()
    for r in strokes:
        t = [x for x in tokens(r.get("sentence", "")) if x]
        for w in t:
            unigram[w] += 1
        for a, b in zip(t, t[1:]):
            bigram[(a, b)] += 1
            previous[a] += 1
    total = sum(unigram.values())
    vocab = len(unigram)

    def logp(word, prev):
        pu = (unigram[word] + 1) / (total + vocab)
        if previous[prev] == 0:
            return math.log(pu)
        pb = (bigram[(prev, word)] + 0.3 * pu * previous[prev]) / (previous[prev] + 0.3)
        return math.log(LAMBDA * pb + (1 - LAMBDA) * pu)

    def prev_of(r):
        t = [x for x in tokens(r.get("sentence", "")) if x]
        i = r.get("word_idx", 0) - 1
        return t[i] if 0 <= i < len(t) else None

    subset = [(i, r) for i, r in enumerate(strokes) if prev_of(r) and rows[i][1]]
    n = len(subset)
    base = sum(1 for i, r in subset if rows[i][1][0][0] == rows[i][0])
    print(f"n={n}  baseline={100 * base / n:.2f} %  (decoder top-1 on strokes with a previous word)")

    def accuracy(weight, cap):
        hit = 0
        for i, r in subset:
            pool = rows[i][1]
            p = prev_of(r)
            reference = logp(pool[0][0], p)
            best = max(
                pool,
                key=lambda c: c[1] + max(-cap, min(cap, weight * (logp(c[0], p) - reference))),
            )
            hit += best[0] == rows[i][0]
        return 100 * hit / n

    print(f"{'cap':>5} " + " ".join(f"{w:>6.1f}" for w in WEIGHTS))
    for cap in CAPS:
        label = "inf" if math.isinf(cap) else f"{cap:.1f}"
        print(f"{label:>5} " + " ".join(f"{accuracy(w, cap):6.2f}" for w in WEIGHTS))
    print(f"\nshipped weight {args.weight} cap {args.cap}: {accuracy(args.weight, args.cap):.2f} %")


if __name__ == "__main__":
    main()
