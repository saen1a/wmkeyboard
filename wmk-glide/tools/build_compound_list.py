#!/usr/bin/env python3
"""Build the German dictionary plus its real compound words.

The 150k list misses the compounds people actually swipe; generating new
compounds was a net loss (under 2 % of them were words). The full
FrequencyWords list, however, already contains real compounds. This script
takes every full-list word that is not in the 150k list and splits into two
150k words (any split with both parts at least three letters), and writes the
150k list followed by those compounds. The result is a larger dictionary, not
a generator: every added spelling was observed in the corpus.

Measured on FUTO German (2,588 swipes, German profile, `RESULTS=4 COLS=11`):

    150k                        74.15 / 82.81   (top-1 / top-4)
    + 441,470 compounds         75.70 / 84.23
    full 1.16M list             75.46 / 84.39
    + compounds + join guard    75.77 / 84.47

    python3 tools/build_compound_list.py \
        --base de_150k.txt --full de_full.txt --out de_150k_comp3.txt
"""

import argparse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="150k list: word count per line")
    ap.add_argument("--full", required=True, help="FrequencyWords de_full.txt")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-part", type=int, default=3)
    args = ap.parse_args()

    base = []
    known = set()
    for line in open(args.base, encoding="utf-8"):
        parts = line.split()
        if len(parts) >= 2:
            base.append((parts[0], parts[1]))
            known.add(parts[0].lower())

    compounds = []
    for line in open(args.full, encoding="utf-8"):
        parts = line.split()
        if len(parts) != 2:
            continue
        word, count = parts[0].lower(), int(parts[1])
        if word in known:
            continue
        if any(
            word[:i] in known and word[i:] in known
            for i in range(args.min_part, len(word) - args.min_part + 1)
        ):
            compounds.append((word, count))

    with open(args.out, "w", encoding="utf-8") as f:
        for word, count in base:
            f.write(f"{word} {count}\n")
        for word, count in compounds:
            f.write(f"{word} {count}\n")
    print(f"{len(base)} base + {len(compounds)} compounds -> {len(base) + len(compounds)} words")


if __name__ == "__main__":
    main()
