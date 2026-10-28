#!/usr/bin/env python3
"""The compound-join oracle: how many swipes could a perfect join fix?

A target the list does not hold is *joinable* when it splits into two listed
words of at least three letters each. That is the ceiling `Tuning.join_cost`
can reach on the stroke set; the decoder's actual joins are far below it
because the parts of a real compound are often rare in the list while a
wrong split of two common words scores higher.

    python3 tools/join_oracle.py de_swipes.jsonl de_150k.txt
"""

import json
import sys

MIN_PART = 3


def main():
    strokes, words = sys.argv[1], sys.argv[2]
    known = set()
    for line in open(words, encoding="utf-8"):
        parts = line.split()
        if parts:
            known.add(parts[0].lower())

    targets = []
    for line in open(strokes, encoding="utf-8"):
        r = json.loads(line)
        w = r["word"].lower()
        if len(w) >= 2 and w.isalpha():
            targets.append(w)

    def joinable(word):
        for i in range(MIN_PART, len(word) - MIN_PART + 1):
            if word[:i] in known and word[i:] in known:
                return True
        return False

    hits = [w for w in targets if w not in known and joinable(w)]
    unique = set(hits)
    print(f"strokes {len(targets)}  unique targets {len(set(targets))}")
    print(f"joinable targets {len(unique)}  strokes {len(hits)}  ({100 * len(hits) / len(targets):.2f} % ceiling)")


if __name__ == "__main__":
    main()
