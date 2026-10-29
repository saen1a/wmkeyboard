#!/usr/bin/env python3
"""Measure how much of a word list `distill.py` can map to one teacher token.

`distill.py`'s `student_to_teacher` only keeps a student word when the
teacher tokenizes `" word"` or `" Word"` as a *single* token. Every word the
teacher spells in several pieces gets no teacher target at all. That is a
property of the teacher tokenizer, not of the teacher model, and it decides
how much of a German vocabulary a distillation run can actually reach.

This script applies exactly that rule to a word list and reports two numbers:

  types    share of distinct words that map whole
  weighted share of running text, using an optional count column

With `--multi`, a second line reports the share reachable by the
multi-token mapping (the product of the conditional token probabilities),
i.e. every word the teacher tokenizer can spell at all, plus a histogram of
piece counts for the words that need more than one.

Usage:
    python3 tools/wmlm_token_coverage.py \
        --words de_150k.txt --limit 24000 --counts --multi \
        --tokenizer /path/Qwen2.5-3B/tokenizer.json \
                    /path/gemma-3-4b/tokenizer.json

Word file format: one word per line, optionally followed by a count
(`de_150k.txt` is `word count`). `#` starts a comment.

Needs only `tokenizers` (`pip install tokenizers`); no transformers, no
model weights, no network. Get a tokenizer with, for example:

    curl -L https://huggingface.co/Qwen/Qwen2.5-3B/resolve/main/tokenizer.json -o qwen.json

Gemma tokenizers are gated on Hugging Face; accept the licence first. The
`-it` and `-pt` tokenizer files are identical.
"""

import argparse
import os
import sys


def parse_words(path, limit, counts):
    words = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            word = parts[0].lower()
            count = int(parts[1]) if counts and len(parts) > 1 else 1
            words.append((word, count))
            if limit and len(words) >= limit:
                break
    return words


def measure(tokenizer_path, words):
    try:
        from tokenizers import Tokenizer
    except ImportError:
        sys.exit("missing dependency: pip install tokenizers")

    tok = Tokenizer.from_file(tokenizer_path)
    whole_types = 0
    whole_mass = 0
    multi_types = 0
    multi_mass = 0
    total_mass = 0
    pieces = {}
    for word, count in words:
        total_mass += count
        best = None
        for form in {word, word.capitalize()}:
            n = len(tok.encode(" " + form, add_special_tokens=False).ids)
            if n:
                best = n if best is None else min(best, n)
                if n == 1:
                    break
        if best is None:
            continue
        if best == 1:
            whole_types += 1
            whole_mass += count
        # A multi-token mapping (product of the conditional pieces) reaches
        # every word the tokenizer can spell at all.
        multi_types += 1
        multi_mass += count
        if best > 1:
            pieces[best] = pieces.get(best, 0) + 1
    return whole_types, whole_mass, total_mass, multi_types, multi_mass, pieces


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--words", required=True, help="word list, one per line")
    ap.add_argument("--tokenizer", nargs="+", required=True, help="tokenizer.json files")
    ap.add_argument("--limit", type=int, default=0, help="only the first N words")
    ap.add_argument("--counts", action="store_true", help="second column is a frequency")
    ap.add_argument(
        "--multi",
        action="store_true",
        help="also report the multi-token mapping's reach (product of pieces)",
    )
    args = ap.parse_args()

    words = parse_words(args.words, args.limit, args.counts)
    if not words:
        sys.exit("empty word list")
    print(f"{len(words)} words from {args.words}", file=sys.stderr)

    for path in args.tokenizer:
        whole, mass, total, multi, multi_mass, pieces = measure(path, words)
        base = os.path.basename(path)
        name = os.path.basename(os.path.dirname(path)) if base == "tokenizer.json" else base.removesuffix(".json")
        type_pct = 100.0 * whole / len(words)
        mass_pct = 100.0 * mass / total
        print(f"{name:32s} types {type_pct:5.1f}%  weighted {mass_pct:5.1f}%")
        if args.multi:
            m_type = 100.0 * multi / len(words)
            m_mass = 100.0 * multi_mass / total
            print(f"{name:32s} multi types {m_type:5.1f}%  weighted {m_mass:5.1f}%")
            if pieces:
                top = ", ".join(f"{n}:{c}" for n, c in sorted(pieces.items())[:6])
                print(f"{name:32s} pieces per word (words >1): {top}")


if __name__ == "__main__":
    main()
