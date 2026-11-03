#!/usr/bin/env python3
"""Merge chunked `distill.py` outputs into one soft-target npz.

A long teacher pass is run in deterministic slices:

    distill.py ... out/soft_0.npz sentences=150000 start=0     count=25000
    distill.py ... out/soft_1.npz sentences=150000 start=25000 count=25000

Each chunk writes the same schema as a single run. This script validates each
chunk, concatenates `sentences`, `ids`, `probs`, rebuilds the global `starts`
offsets, writes atomically, and validates the result.

Usage:
    python3 merge_soft.py out/de_soft_150k.npz out/soft_0.npz out/soft_1.npz \
        --vocab-size 24576 --expect-sentences 150000
"""
import argparse
import os
import sys

import numpy as np

from check_soft import SoftError, validate_soft


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out")
    ap.add_argument("chunks", nargs="+")
    ap.add_argument("--vocab-size", type=int, default=None)
    ap.add_argument("--expect-sentences", type=int, default=None)
    ap.add_argument("--min-mass-ratio", type=float, default=0.90)
    args = ap.parse_args()

    sentences, ids, probs = [], [], []
    starts = [0]
    topk = None
    extras = {}          # extra per-row arrays (e.g. `weight`, `mass`)
    for path in args.chunks:
        try:
            validate_soft(path, vocab_size=args.vocab_size, min_mass_ratio=0.0)
        except SoftError as e:
            sys.exit(f"FAIL chunk: {e}")
        z = np.load(path, allow_pickle=False)
        if topk is None:
            topk = z["ids"].shape[1]
        elif z["ids"].shape[1] != topk:
            sys.exit(f"{path}: top-{z['ids'].shape[1]} != top-{topk}")
        n_sent = len(z["sentences"])
        if len(z["starts"]) != n_sent + 1:
            sys.exit(f"{path}: starts has {len(z['starts'])} entries for {n_sent} sentences")
        if z["starts"][0] != 0:
            sys.exit(f"{path}: starts[0] must be 0")
        starts.extend((starts[-1] + z["starts"][1:]).tolist())
        sentences.append(z["sentences"])
        ids.append(z["ids"])
        probs.append(z["probs"])
        # Carry any additional per-row array through the merge. The collector
        # writes per-row diagnostics (`mass`, `actual`, `weight`) that a KD
        # term or a weight file needs; dropping them here silently lost them
        # (audit finding, 2026-11-03).
        for key in z.files:
            if key in ("sentences", "starts", "ids", "probs"):
                continue
            arr = z[key]
            if arr.ndim == 1 and arr.shape[0] == len(z["ids"]):
                extras.setdefault(key, []).append(arr)

    out_sent = np.concatenate(sentences)
    if len(out_sent) and not np.all(np.diff(out_sent) > 0):
        sys.exit("chunks overlap or are out of order: sentences are not strictly increasing")
    if args.expect_sentences is not None and len(out_sent) != args.expect_sentences:
        sys.exit(f"merged {len(out_sent)} sentences, expected {args.expect_sentences}")

    out_ids = np.concatenate(ids)
    out_probs = np.concatenate(probs)
    if len(starts) != len(out_sent) + 1 or starts[-1] != len(out_ids):
        sys.exit("internal offset mismatch while merging")

    # Atomic write: a killed merge must not leave a plausible-looking npz.
    persona = {"sentences": out_sent.astype(np.int32, copy=False),
               "starts": np.asarray(starts, dtype=np.int64),
               "ids": out_ids,
               "probs": out_probs}
    for key, parts in extras.items():
        if len(parts) != len(args.chunks):
            sys.exit(f"extra array {key} present in {len(parts)} of "
                     f"{len(args.chunks)} chunks; refusing to merge")
        persona[key] = np.concatenate(parts)
    tmp = args.out + ".tmp.npz"
    np.savez_compressed(tmp, **persona)
    os.replace(tmp, args.out)

    try:
        s = validate_soft(
            args.out,
            vocab_size=args.vocab_size,
            expect_sentences=args.expect_sentences,
            min_mass_ratio=args.min_mass_ratio,
        )
    except SoftError as e:
        sys.exit(f"FAIL merged: {e}")
    print(
        f"wrote {args.out}: {len(args.chunks)} chunks, {s['sentences']} sentences, "
        f"{s['rows']} rows, row coverage {s['row_coverage']:.1%}, "
        f"mean row mass {s['mean_mass']:.3f}"
    )


if __name__ == "__main__":
    main()
