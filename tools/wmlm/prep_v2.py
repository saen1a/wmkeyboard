"""Build student-v2 arrays with a new German piece inventory.

usage: prep_v2.py <corpus.tsv> <old_data_dir> <out_dir>
                  [ctx=40] [pieces=2048] [seed=0] [heldout=20000] [limit=0]

The 22,512-word list and every word ID are copied from `old_data_dir/vocab.txt`.
Only the 2,048 appended pieces are rebuilt (matrices in the teacher cache use
word IDs, so they remain valid). The deterministic corpus shuffle and held-out
split are reproduced exactly, so `de_soft_2m.npz` sentence indices still match.

Writes vocab.txt, train.npz, heldout.npz, heldout.tsv; prints coverage and the
piece-length histogram. `limit=N` is only for smoke tests (does not reproduce
the full split).
"""
from __future__ import annotations

import collections
import os
import random
import sys

import numpy as np

from common import BOS, EOS, FIELDS, LANGS, NUM, REGISTERS, SPECIALS, UNK, tokenize
from pieces_v2 import build_v2


def opts(argv):
    o = dict(ctx=40, pieces=2048, seed=0, heldout=20000, limit=0)
    for a in argv:
        k, v = a.split("=", 1)
        if k not in o:
            raise SystemExit(f"unknown option {k}")
        o[k] = type(o[k])(v)
    return o


def main():
    src, old_dir, out = sys.argv[1:4]
    o = opts(sys.argv[4:])
    os.makedirs(out, exist_ok=True)

    old_vocab = [l.rstrip("\n") for l in open(os.path.join(old_dir, "vocab.txt"), encoding="utf-8")]
    if len(old_vocab) != 24576:
        raise SystemExit(f"old vocab {len(old_vocab)} != 24576")
    specials = old_vocab[: len(SPECIALS)]
    if specials != list(SPECIALS):
        raise SystemExit("old vocab specials do not match common.SPECIALS")
    rest = old_vocab[len(SPECIALS):]
    words = [t for t in rest if not t.startswith("\u2581") and not t.startswith("##")]
    old_pieces = [t for t in rest if t.startswith("\u2581") or t.startswith("##")]
    if len(words) != 22512:
        raise SystemExit(f"old words {len(words)} != 22512")
    if len(old_pieces) != 2048:
        raise SystemExit(f"old pieces {len(old_pieces)} != 2048")
    word_set = set(words)
    old_word_ids = {w: i for i, w in enumerate(old_vocab)}
    for w in words:
        if old_word_ids[w] < len(SPECIALS) or old_word_ids[w] >= len(SPECIALS) + len(words):
            raise SystemExit(f"word id outside block: {w} -> {old_word_ids[w]}")

    counts = collections.Counter()
    sentences = []
    with open(src, encoding="utf-8") as f:
        for line in f:
            if o["limit"] and len(sentences) >= o["limit"]:
                break
            reg, field, lang, text = line.rstrip("\n").split("\t", 3)
            toks = tokenize(text)
            if not toks:
                continue
            counts.update(toks)
            sentences.append((int(reg), int(field), int(lang), toks))
    print(f"{len(sentences)} sentences, {sum(counts.values())} tokens, {len(counts)} types", file=sys.stderr)

    oov = {w: c for w, c in counts.items() if w not in word_set and w != NUM}
    pieces = build_v2(oov, o["pieces"])
    vocab = list(SPECIALS) + words + pieces.tokens()
    if len(vocab) != 24576:
        raise SystemExit(f"new vocab {len(vocab)} != 24576")
    ids = {w: i for i, w in enumerate(vocab)}
    # Word IDs must be byte-for-byte the old block; only piece IDs move.
    for w in words:
        if ids[w] != old_word_ids[w]:
            raise SystemExit(f"word id moved: {w} {ids[w]} != {old_word_ids[w]}")
    with open(os.path.join(out, "vocab.txt"), "w", encoding="utf-8") as f:
        for w in vocab:
            f.write(w + "\n")

    covered = sum(c for w, c in counts.items() if w in ids) / max(1, sum(counts.values()))
    print(f"vocab {len(vocab)} words {len(words)} pieces {len(pieces.starts)}+{len(pieces.conts)} token coverage {covered:.4f}", file=sys.stderr)

    # Piece-length histogram on OOV types (by type and by token count).
    hist_t = collections.Counter()
    hist_c = collections.Counter()
    for w, c in oov.items():
        enc = pieces.encode(w)
        k = -1 if enc is None else len(enc)
        hist_t[k] += 1
        hist_c[k] += c
    print("k_hist_types", dict(sorted(hist_t.items())), file=sys.stderr)
    print("k_hist_tokens", dict(sorted(hist_c.items())), file=sys.stderr)
    over = sum(c for k, c in hist_c.items() if k < 0 or k > 6)
    over_t = sum(t for k, t in hist_t.items() if k < 0 or k > 6)
    print(f"k>6 or None: types {over_t} tokens {over} ({over / max(1, sum(counts.values())):.6f})", file=sys.stderr)
    for probe in ("gib", "zugleich", "straßenbahn", "universitätsklinikum", "durchsuchungsbefehl"):
        print(f"probe {probe} -> {pieces.encode(probe)}", file=sys.stderr)

    unk = ids[UNK]
    piece_cache = {}

    def encode(w):
        if w in ids:
            return [ids[w]]
        if w not in piece_cache:
            enc = pieces.encode(w)
            piece_cache[w] = [ids[p] for p in enc] if enc else [unk]
        return piece_cache[w]

    rng = random.Random(o["seed"])
    rng.shuffle(sentences)
    held = sentences[: o["heldout"]]
    train = sentences[o["heldout"]:]

    def pack(items, name):
        tokens, starts = [], []
        for reg, field, lang, toks in items:
            starts.append(len(tokens))
            seq = [ids[REGISTERS[reg]], ids[FIELDS[field]], ids[LANGS[lang]], ids[BOS]]
            for w in toks:
                seq += encode(w)
            seq = seq[: o["ctx"] - 1] + [ids[EOS]]
            tokens.extend(seq)
        starts.append(len(tokens))
        np.savez(os.path.join(out, name), tokens=np.array(tokens, dtype=np.int32), starts=np.array(starts, dtype=np.int64))
        print(f"{name}: {len(items)} sentences, {len(tokens)} tokens", file=sys.stderr)
        return len(items), len(tokens)

    ntr, ttr = pack(train, "train.npz")
    nhe, the = pack(held, "heldout.npz")
    with open(os.path.join(out, "heldout.tsv"), "w", encoding="utf-8") as f:
        for reg, field, lang, toks in held:
            f.write(f"{reg}\t{field}\t{lang}\t{' '.join(toks)}\n")

    # Split/order invariants (skip for the small smoke test).
    if not o["limit"]:
        old_tr = np.load(os.path.join(old_dir, "train.npz"))
        old_he = np.load(os.path.join(old_dir, "heldout.npz"))
        old_ntr = len(old_tr["starts"]) - 1
        old_nhe = len(old_he["starts"]) - 1
        if ntr != old_ntr or nhe != old_nhe:
            raise SystemExit(f"split changed: train {ntr} vs {old_ntr}, held {nhe} vs {old_nhe}")
        if nhe != 20000:
            raise SystemExit(f"heldout {nhe} != 20000")
        old_tsv = os.path.join(old_dir, "heldout.tsv")
        if os.path.exists(old_tsv):
            old_text = open(old_tsv, encoding="utf-8").read()
            new_text = open(os.path.join(out, "heldout.tsv"), encoding="utf-8").read()
            if old_text != new_text:
                raise SystemExit("heldout.tsv text/order changed")
        print("split invariants: PASS (train/held sentences + heldout text unchanged)", file=sys.stderr)
    print(f"done {out} train_sentences {ntr} heldout_sentences {nhe}", file=sys.stderr)


if __name__ == "__main__":
    main()
