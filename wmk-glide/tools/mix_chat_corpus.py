#!/usr/bin/env python3
"""Build the decided 1M + 200k chat corpus.

Reads the existing `de_all.tsv` (register, field, lang, text), excludes the
20k held-out sentences, deduplicates normalized text, and samples:

    440k Tatoeba + 560k News + 200k Tatoeba = 1.2M
    640k chat (53.3%) / 560k News (46.7%)

The 200k chat addition comes from the remaining Tatoeba rows by default; a
new chat corpus can replace that slice later without changing the totals.
The output keeps the original `register\tfield\tlang\ttext` format so
`tools/wmlm/prep.py` can consume it.

Usage:
    python3 mix_chat_corpus.py --in ../artifacts/corpora/de_all.tsv \
        --heldout ../artifacts/data/heldout.tsv \
        --out ../artifacts/corpora/de_1m_200k_chat.tsv
"""
import argparse
import hashlib
import json
import random
import sys
import unicodedata


def norm(text):
    text = unicodedata.normalize("NFC", text.strip()).lower()
    return " ".join(text.split())


def read_rows(path):
    tatoeba, news = [], []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t", 3)
            if len(parts) != 4:
                continue
            reg, field, lang, text = parts
            if not text.strip():
                continue
            if (reg, field) == ("1", "1"):
                tatoeba.append((reg, field, lang, text.strip()))
            elif (reg, field) == ("2", "0"):
                news.append((reg, field, lang, text.strip()))
    return tatoeba, news


def read_heldout(path):
    seen = set()
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 4:
                seen.add(norm(parts[3]))
    return seen


def sample_unique(rows, count, seen, rng):
    rng.shuffle(rows)
    out = []
    for row in rows:
        key = norm(row[3])
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
        if len(out) >= count:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--heldout", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tatoeba", type=int, default=440_000)
    ap.add_argument("--news", type=int, default=560_000)
    ap.add_argument("--chat", type=int, default=200_000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    tatoeba, news = read_rows(args.inp)
    held = read_heldout(args.heldout)
    print(f"read tatoeba={len(tatoeba)} news={len(news)} heldout={len(held)}", file=sys.stderr)

    seen = set(held)
    base_tatoeba = sample_unique(tatoeba, args.tatoeba, seen, rng)
    base_news = sample_unique(news, args.news, seen, rng)
    chat = sample_unique(tatoeba, args.chat, seen, rng)
    if len(base_tatoeba) < args.tatoeba or len(base_news) < args.news or len(chat) < args.chat:
        print(
            f"not enough unique rows: tatoeba={len(base_tatoeba)}/{args.tatoeba} "
            f"news={len(base_news)}/{args.news} chat={len(chat)}/{args.chat}",
            file=sys.stderr,
        )
        return 1

    rows = base_tatoeba + base_news + chat
    rng.shuffle(rows)
    with open(args.out, "w", encoding="utf-8") as f:
        for reg, field, lang, text in rows:
            f.write(f"{reg}\t{field}\t{lang}\t{text}\n")

    digest = hashlib.sha256()
    with open(args.out, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    manifest = {
        "source": args.inp,
        "heldout": args.heldout,
        "out": args.out,
        "seed": args.seed,
        "sentences": len(rows),
        "tatoeba": len(base_tatoeba) + len(chat),
        "news": len(base_news),
        "chat_share": (len(base_tatoeba) + len(chat)) / len(rows),
        "sha256": digest.hexdigest(),
    }
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
