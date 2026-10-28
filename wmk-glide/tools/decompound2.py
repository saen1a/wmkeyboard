#!/usr/bin/env python3
"""Productivity-driven compound generator (prototype 2).

Prototype 1 ranked combinations by part frequency and produced 0.8 % real words:
the budget went to `auchhaus`-style junk from function words. This one learns
from a large corpus which parts actually combine, then generates only
combinations of productive first elements, productive heads and the linking
elements those heads are seen with.

Usage:
    python3 decompound2.py de_150k.txt de_full.txt out.txt --budget 50000 \
        --report-targets de_targets.txt
"""

import argparse
import heapq
import sys
from collections import Counter, defaultdict

LINKS = ("", "s", "n", "en", "er", "e", "es", "ns")
MAX_LEN = 24


def load(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            word, _, freq = line.strip().rpartition(" ")
            if word and freq.isdigit():
                out[word.lower()] = int(freq)
    return out


def splits(word, lexicon):
    """Every (first, link, head) the lexicon can spell, for one word."""
    if not (6 <= len(word) <= MAX_LEN):
        return
    for i in range(4, len(word) - 2):
        first = word[:i]
        if first not in lexicon:
            continue
        for link in LINKS:
            j = i + len(link)
            if j >= len(word) or word[i:j] != link:
                continue
            head = word[j:]
            if len(head) >= 3 and head in lexicon:
                yield first, link, head


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wordlist")
    ap.add_argument("corpus")
    ap.add_argument("out")
    ap.add_argument("--budget", type=int, default=50000)
    ap.add_argument("--modifiers-per-head", type=int, default=25)
    ap.add_argument("--min-head-seen", type=int, default=5)
    ap.add_argument("--report-targets")
    args = ap.parse_args()

    lex = load(args.wordlist)
    corpus = load(args.corpus)
    print(f"lexicon {len(lex)}  corpus {len(corpus)}", file=sys.stderr)

    first_seen = Counter()
    head_seen = Counter()
    head_links = defaultdict(Counter)
    for word, freq in corpus.items():
        if freq < 2:
            continue
        for first, link, head in splits(word, lex):
            first_seen[first] += 1
            head_seen[head] += 1
            head_links[head][link] += 1
    print(f"productive first elements {len(first_seen)}  heads {len(head_seen)}",
          file=sys.stderr)

    heads = [h for h, n in head_seen.most_common() if n >= args.min_head_seen]
    modifiers = [(m, n) for m, n in first_seen.most_common() if n >= 2]
    print(f"using {len(heads)} heads, {len(modifiers)} first elements",
          file=sys.stderr)

    candidates = {}
    for head in heads:
        usable = [l for l, _ in head_links[head].most_common(3)]
        taken = 0
        for first, seen in modifiers:
            if taken >= args.modifiers_per_head:
                break
            for link in usable:
                word = first + link + head
                if len(word) > MAX_LEN or word in lex:
                    continue
                # Score: how often the pair's parts were seen combining, damped
                # by how unusual the pair itself is. Nothing here reads the
                # target list.
                score = (min(first_seen[first], head_seen[head]) ** 0.5) * (1.0 + seen / 10.0)
                candidates[word] = max(candidates.get(word, 0.0), score)
            taken += 1

    ranked = sorted(candidates.items(), key=lambda kv: -kv[1])
    kept = ranked[: args.budget]
    print(f"candidates {len(candidates)}  keeping {len(kept)}  "
          f"(score >= {kept[-1][1]:.2f})", file=sys.stderr)
    with open(args.out, "w", encoding="utf-8") as out:
        for word, score in kept:
            out.write(f"{word} {max(1, int(score))}\n")

    if args.report_targets:
        targets = {l.strip().lower() for l in open(args.report_targets)}
        missing = targets - set(lex)
        got = missing & {w for w, _ in kept}
        real = {w for w, _ in kept} & set(corpus)
        print(f"generated {len(kept)}: real words {len(real)} "
              f"({100 * len(real) / len(kept):.1f} %)")
        print(f"missing targets {len(missing)}  recovered {len(got)} "
              f"({100 * len(got) / max(1, len(missing)):.1f} %)")


if __name__ == "__main__":
    main()
