#!/usr/bin/env python3
"""How much does context reranking buy the glide decoder?

Reads the pool dump `glide_beam_eval` writes with `DUMP=<path> RESULTS=8` and the
stroke file it was decoded from, builds a bigram model from the corpus's own
`sentence` fields, and reorders each stroke's candidates by

    score + alpha * ln P(word | previous word)

for a sweep of pool widths and alphas. Also prints how far the right word sits
from the leader when it is in the pool but not first — that is the gap a rerank
cap has to be able to cover.

    python3 rerank_eval.py pool.jsonl de_swipes.jsonl
"""

import json
import math
import re
import statistics
import sys
from collections import Counter

LAMBDA = 0.7          # bigram vs unigram interpolation
ALPHAS = (0.5, 1.0, 2.0, 3.0)
POOLS = (2, 4, 6, 8)


def tokens(sentence):
    return [re.sub(r"[^\wäöüß]", "", t.lower()) for t in sentence.split()]


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
    dump_path, stroke_path = sys.argv[1], sys.argv[2]
    rows = load_dump(dump_path)
    strokes = load_strokes(stroke_path)
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

    n = len(rows)
    empty = sum(1 for _, pool in rows if not pool)
    base = sum(1 for target, pool in rows if pool and pool[0][0] == target)
    cover = {k: sum(1 for target, pool in rows if target in [w for w, _ in pool[:k]])
             for k in POOLS}
    print(f"n={n}  no candidate={empty}  top1={100 * base / n:.2f} %")
    for k in POOLS:
        print(f"  target in top-{k}: {100 * cover[k] / n:.2f} %")

    subset = [(i, r) for i, r in enumerate(strokes) if prev_of(r) and rows[i][1]]
    baseline = sum(1 for i, r in subset if rows[i][1][0][0] == rows[i][0])
    print(f"\nwith a previous word: n={len(subset)}  baseline={100 * baseline / len(subset):.2f} %")
    for pool in POOLS:
        for a in ALPHAS:
            hit = 0
            for i, r in subset:
                p = prev_of(r)
                best = max(rows[i][1][:pool], key=lambda c: c[1] + a * logp(c[0], p))
                hit += best[0] == rows[i][0]
            print(f"  pool {pool} alpha {a:>3}: {100 * hit / len(subset):.2f} %")

    gaps = []
    for target, pool in rows:
        words = [w for w, _ in pool]
        if target in words and words[0] != target:
            gaps.append(pool[0][1] - pool[words.index(target)][1])
    if gaps:
        gaps.sort()
        q = lambda p: gaps[min(len(gaps) - 1, int(len(gaps) * p))]
        print(f"\ngap leader->target on {len(gaps)} in-pool misses: "
              f"median {statistics.median(gaps):.2f} nats, Q1 {q(.25):.2f}, "
              f"Q3 {q(.75):.2f}, P90 {q(.9):.2f}, max {gaps[-1]:.2f}")
        for cap in (1.0, 1.5, 2.0, 3.0, 4.0):
            reachable = sum(1 for g in gaps if g <= cap)
            print(f"  a {cap:.1f}-nat cap reaches {100 * reachable / len(gaps):.1f} % of them")


if __name__ == "__main__":
    main()
