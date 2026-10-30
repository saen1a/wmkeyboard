#!/usr/bin/env python3
"""Build the 2M German soft-target corpus (Phase -1, no GPU needed).

Target: **2,000,000 unique rows, 53.3 % chat / 46.7 % news**
(1,066,000 / 934,000), same weighting as the shipped 1.2M corpus
(`corpora/de_1m_200k_chat.tsv`). The existing pool cannot reach 2M on its
own: `de_all.tsv` holds 1,784,711 rows (784,711 Tatoeba chat, 1,000,000
Leipzig news), and after dedup + the 3..40 word filter only ~776k chat rows
survive. The missing chat rows come from an extra licensed chat source,
OpenSubtitles DE (OPUS, `mono/de.txt.gz`).

Nothing is duplicated: every text is keyed with `tools/wmlm/common.py`'s
`tokenize` (the same function `prep.py` and the engine use), which is also
the space `heldout.tsv` is stored in, and entered into one global "seen"
set that is pre-seeded with the 20k held-out sentences - so a row can
appear once and never in heldout. A plain lower/whitespace key would miss
every heldout sentence that differs only in case or punctuation.

Output format is the same `register\\tfield\\tlang\\ttext` TSV that
`tools/wmlm/prep.py` reads. Chat rows are `1\\t1\\t1`, news rows `2\\t0\\t1`.
A sidecar manifest (`<out>.manifest.json`) and `<out>.sha256` record counts,
shares, sources, filter, seed and hashes so the run is reproducible and
auditable.

Usage (normal, with OpenSubtitles top-up):

    python3 prepare_2m.py \
        --all ../../artifacts/corpora/de_all.tsv \
        --heldout ../../artifacts/data/heldout.tsv \
        --extra-chat ../../artifacts/corpora/de_opensub_chat.txt \
        --out ../../artifacts/corpora/de_2m_mix.tsv

Usage (no extra source: build the maximum unique 1.78M and report it):

    python3 prepare_2m.py --all ... --heldout ... \
        --out ../../artifacts/corpora/de_1m78_max.tsv --no-extra

Verify an existing file and print the report:

    python3 prepare_2m.py --verify ../../artifacts/corpora/de_2m_mix.tsv \
        --heldout ../../artifacts/data/heldout.tsv --expect-rows 2000000
"""
import argparse
import gzip
import hashlib
import json
import os
import random
import sys
import unicodedata

# Register/field/lang labels as indices into common.REGISTERS / FIELDS / LANGS.
CHAT = ("1", "1", "1")
NEWS = ("2", "0", "1")

CHAT_TARGET = 1_066_000
NEWS_TARGET = 934_000


def _tokenize():
    """`common.tokenize`, the function prep.py and the engine share.

    The heldout file (`heldout.tsv` from prep.py) holds *tokenized* text:
    lower case, punctuation stripped, digits folded to `<num>`. Comparing it
    against raw corpus text misses every sentence that differs only in case
    or punctuation, which is almost all of them. Both sides therefore go
    through the same tokenizer; without the repo checkout the function
    degrades to a conservative lower/whitespace normalization.
    """
    root = os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tools", "wmlm")
    )
    if os.path.isfile(os.path.join(root, "common.py")):
        if root not in sys.path:
            sys.path.insert(0, root)
        import common  # noqa: PLC0415 - resolved at runtime

        return common.tokenize
    print(
        f"WARN: {root}/common.py not found; heldout matching falls back to "
        "lower/whitespace normalization and may miss punctuation-only differences",
        file=sys.stderr,
    )
    return None


TOKENIZE = _tokenize()


def norm(text):
    """Whitespace/case normalization (dedup fallback without the tokenizer)."""
    text = unicodedata.normalize("NFC", text.strip()).lower()
    return " ".join(text.split())


def key(text):
    """Comparison key in the same space as `heldout.tsv` and `train.npz`."""
    if TOKENIZE is None:
        return norm(text)
    return " ".join(TOKENIZE(text))


def clean(text):
    """Whitespace-normalized display text; punctuation is left alone."""
    text = unicodedata.normalize("NFC", text).strip()
    return " ".join(text.split())


def word_ok(text, min_words, max_words):
    n = len(text.split())
    return min_words <= n <= max_words and any(c.isalpha() for c in text)


def read_heldout(path):
    seen = set()
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 4 and parts[3].strip():
                seen.add(key(parts[3]))
    return seen


def read_all(path, min_words, max_words, seen, held):
    """Split de_all.tsv into deduped, filtered chat and news pools."""
    chat, news = [], []
    dropped = {"heldout": 0, "duplicate": 0, "length": 0, "bad": 0}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t", 3)
            if len(parts) != 4:
                dropped["bad"] += 1
                continue
            reg, field, lang, text = parts
            k = key(text)
            if not k:
                dropped["length"] += 1
                continue
            if k in seen:
                # Heldout first, then rows already taken from this file.
                dropped["heldout" if k in held else "duplicate"] += 1
                continue
            if not word_ok(text, min_words, max_words):
                dropped["length"] += 1
                seen.add(k)
                continue
            seen.add(k)
            row = (*((reg, field, lang) if (reg, field) == ("1", "1") else NEWS), clean(text))
            if (reg, field) == ("1", "1"):
                chat.append(row)
            elif (reg, field) == ("2", "0"):
                news.append(row)
            else:
                dropped["bad"] += 1
    return chat, news, dropped


def read_extra_chat(path, min_words, max_words, seen, held):
    """Plain-text chat source, one utterance per line (OpenSubtitles mono).

    `.gz` is read through gzip, so the OPUS download stays compressed.
    """
    rows = []
    dropped = {"heldout": 0, "duplicate": 0, "length": 0}
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            text = clean(line)
            if not text:
                dropped["length"] += 1
                continue
            k = key(text)
            if not k:
                dropped["length"] += 1
                continue
            if k in seen:
                dropped["heldout" if k in held else "duplicate"] += 1
                continue
            if not word_ok(text, min_words, max_words):
                dropped["length"] += 1
                seen.add(k)
                continue
            seen.add(k)
            rows.append((*CHAT, text))
    return rows, dropped


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(out, manifest):
    text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    with open(out + ".manifest.json", "w", encoding="utf-8") as f:
        f.write(text)
    print(text, end="")


def build(args):
    held = read_heldout(args.heldout)
    print(f"heldout: {len(held)} unique texts", file=sys.stderr)

    seen = set(held)
    chat_base, news, dropped_all = read_all(
        args.all, args.min_words, args.max_words, seen, held
    )
    print(
        f"de_all: chat={len(chat_base)} news={len(news)} "
        f"dropped={dropped_all}",
        file=sys.stderr,
    )

    extra, dropped_extra = ([], {})
    if args.extra_chat:
        extra, dropped_extra = read_extra_chat(
            args.extra_chat, args.min_words, args.max_words, seen, held
        )
        print(
            f"extra chat: {len(extra)} usable from {args.extra_chat} "
            f"dropped={dropped_extra}",
            file=sys.stderr,
        )

    rng = random.Random(args.seed)
    rng.shuffle(chat_base)
    rng.shuffle(extra)
    rng.shuffle(news)

    chat = chat_base + extra
    if len(chat) > args.chat:
        chat = chat[: args.chat]
    if len(news) > args.news:
        news = news[: args.news]

    complete = len(chat) >= args.chat and len(news) >= args.news
    rows = chat + news
    rng.shuffle(rows)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for reg, field, lang, text in rows:
            f.write(f"{reg}\t{field}\t{lang}\t{text}\n")
    os.replace(tmp, args.out)

    digest = sha256(args.out)
    if args.no_extra:
        target = {
            "rows": None,
            "chat": None,
            "news": None,
            "two_million_complete": False,
            "note": "no extra licensed chat source; maximum unique set",
        }
    else:
        target = {
            "rows": args.chat + args.news,
            "chat": args.chat,
            "news": args.news,
            "two_million_complete": complete,
        }
    manifest = {
        "out": args.out,
        "rows": len(rows),
        "chat": len(chat),
        "chat_from_base": len(chat_base),
        "chat_from_extra": max(0, len(chat) - len(chat_base)),
        "news": len(news),
        "chat_share": round(len(chat) / max(1, len(rows)), 6),
        "news_share": round(len(news) / max(1, len(rows)), 6),
        "target": target,
        "sources": {
            "all": args.all,
            "heldout": args.heldout,
            "extra_chat": args.extra_chat or None,
            "extra_chat_license": (
                "OpenSubtitles v2018 (OPUS): CC BY-NC 4.0 style terms, "
                "attribution to opensubtitles.org + Lison & Tiedemann 2016; "
                "non-commercial, check before shipping a derived model"
                if args.extra_chat
                else None
            ),
        },
        "filter": {
            "min_words": args.min_words,
            "max_words": args.max_words,
            "normalize": "NFC, strip, collapse whitespace for the stored text",
            "dedup": "common.tokenize key (same space as heldout.tsv/train.npz), global seen-set, heldout pre-seeded",
            "tokenizer": "tools/wmlm/common.py tokenize" if TOKENIZE else "fallback norm()",
        },
        "dropped": {"de_all": dropped_all, "extra_chat": dropped_extra},
        "seed": args.seed,
        "sha256": digest,
    }
    write_manifest(args.out, manifest)
    with open(args.out + ".sha256", "w", encoding="utf-8") as f:
        f.write(f"{digest}  {os.path.basename(args.out)}\n")
    if not complete:
        print(
            f"WARN: target not reached (chat {len(chat)}/{args.chat}, "
            f"news {len(news)}/{args.news}); wrote the maximum unique set",
            file=sys.stderr,
        )
    return 0 if complete else 2


def verify(path, heldout, expect_rows, min_words=3, max_words=40):
    held = read_heldout(heldout) if heldout else set()
    rows = 0
    chat = news = 0
    keys = set()
    leaks = 0
    short = long_ = noletter = 0
    bad = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t", 3)
            if len(parts) != 4:
                bad += 1
                continue
            reg, field, lang, text = parts
            k = key(text)
            rows += 1
            if k in keys:
                bad += 1
            keys.add(k)
            if k in held:
                leaks += 1
            w = len(text.split())
            if w < min_words:
                short += 1
            elif w > max_words:
                long_ += 1
            if not any(c.isalpha() for c in text):
                noletter += 1
            if (reg, field) == ("1", "1"):
                chat += 1
            elif (reg, field) == ("2", "0"):
                news += 1
            else:
                bad += 1
    report = {
        "path": path,
        "rows": rows,
        "chat": chat,
        "news": news,
        "chat_share": round(chat / max(1, rows), 4),
        "news_share": round(news / max(1, rows), 4),
        "unique": len(keys),
        "heldout_leaks": leaks,
        "bad_rows": bad,
        "too_short": short,
        "too_long": long_,
        "no_letter": noletter,
        "sha256": sha256(path),
    }
    print(json.dumps(report, indent=2))
    ok = (
        bad == 0
        and leaks == 0
        and len(keys) == rows
        and short == 0
        and long_ == 0
        and noletter == 0
        and (expect_rows is None or rows == expect_rows)
    )
    print("OK" if ok else "FAIL", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", dest="all", help="de_all.tsv (register/field/lang/text)")
    ap.add_argument("--heldout", required=False, help="20k heldout TSV, 4 columns")
    ap.add_argument("--extra-chat", default="", help="plain text chat source, one line per utterance")
    ap.add_argument("--out", default="", help="output TSV")
    ap.add_argument("--chat", type=int, default=CHAT_TARGET)
    ap.add_argument("--news", type=int, default=NEWS_TARGET)
    ap.add_argument("--min-words", type=int, default=3)
    ap.add_argument("--max-words", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-extra", action="store_true", help="build the maximum unique set (no extra source)")
    ap.add_argument("--verify", default="", help="verify an existing corpus instead of building")
    ap.add_argument("--expect-rows", type=int, default=None)
    args = ap.parse_args(argv)

    if args.verify:
        return verify(args.verify, args.heldout, args.expect_rows, args.min_words, args.max_words)

    if not args.all or not args.out or not args.heldout:
        ap.error("--all, --heldout and --out are required when building")
    if args.no_extra:
        args.extra_chat = ""
        # Without an extra source the honest target is "everything unique".
        args.chat = 10**9
        args.news = 10**9
    return build(args)


if __name__ == "__main__":
    sys.exit(main())
