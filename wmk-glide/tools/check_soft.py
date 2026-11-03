#!/usr/bin/env python3
"""Validate a `distill.py` soft-target npz before training or merging.

Checks the schema (`sentences`, `starts`, `ids`, `probs`), row/sentence
alignment, monotonic sentence order, id range, finite/non-negative
probabilities, and the share of rows that actually carry teacher mass.

Usage:
    python3 check_soft.py out/soft_150k_0.npz --vocab-size 24576 \
        --expect-sentences 25000
    python3 check_soft.py out/de_soft_150k.npz --vocab-size 24576 \
        --expect-sentences 150000

Exit 0 when valid, 1 with the first errors otherwise.
"""
import argparse
import sys

import numpy as np


class SoftError(Exception):
    pass


def validate_soft(path, vocab_size=None, expect_sentences=None, min_mass_ratio=0.9):
    try:
        z = np.load(path, allow_pickle=False)
    except Exception as e:  # noqa: BLE001 - report the file, not a traceback
        raise SoftError(f"{path}: cannot load npz: {e}") from e

    missing = [k for k in ("sentences", "starts", "ids", "probs") if k not in z]
    if missing:
        raise SoftError(f"{path}: missing keys {missing}")

    sentences = z["sentences"]
    starts = z["starts"]
    ids = z["ids"]
    probs = z["probs"]

    if sentences.ndim != 1 or starts.ndim != 1:
        raise SoftError(f"{path}: sentences/starts must be 1-D")
    if ids.ndim != 2 or probs.ndim != 2:
        raise SoftError(f"{path}: ids/probs must be 2-D")
    if ids.shape != probs.shape:
        raise SoftError(f"{path}: ids {ids.shape} != probs {probs.shape}")
    if ids.shape[1] <= 0:
        raise SoftError(f"{path}: top-k must be positive")
    if len(starts) != len(sentences) + 1:
        raise SoftError(
            f"{path}: starts has {len(starts)} entries for {len(sentences)} sentences"
        )
    if len(starts) and starts[0] != 0:
        raise SoftError(f"{path}: starts[0] must be 0")
    if len(starts) > 1 and not np.all(np.diff(starts) >= 0):
        raise SoftError(f"{path}: starts must be monotonic")
    rows = len(ids)
    if len(starts) and starts[-1] != rows:
        raise SoftError(f"{path}: starts[-1]={starts[-1]} but {rows} rows")

    if expect_sentences is not None and len(sentences) != expect_sentences:
        raise SoftError(
            f"{path}: {len(sentences)} sentences, expected {expect_sentences}"
        )
    if len(sentences):
        if not np.issubdtype(sentences.dtype, np.integer):
            raise SoftError(f"{path}: sentences must be integer")
        if np.unique(sentences).size != len(sentences):
            raise SoftError(f"{path}: duplicate sentence indices")
        if not np.all(np.diff(sentences) > 0):
            raise SoftError(f"{path}: sentences must be strictly increasing")

    if rows:
        if not np.issubdtype(ids.dtype, np.integer):
            raise SoftError(f"{path}: ids must be integer")
        if ids.min() < 0:
            raise SoftError(f"{path}: negative id {ids.min()}")
        if vocab_size is not None and ids.max() >= vocab_size:
            raise SoftError(
                f"{path}: id {ids.max()} outside vocab size {vocab_size}"
            )
        if not np.issubdtype(probs.dtype, np.floating):
            raise SoftError(f"{path}: probs must be floating point")
        if not np.isfinite(probs).all():
            raise SoftError(f"{path}: non-finite probability")
        if (probs < 0).any():
            raise SoftError(f"{path}: negative probability")
        mass = probs.astype(np.float64).sum(axis=1)
        if (mass > 1.001).any():
            raise SoftError(f"{path}: row mass > 1.001")
        nonzero = int((mass > 0).sum())
        ratio = nonzero / rows
        # Two different quantities used to share one name (audit 2026-11-03):
        # `row_coverage` is the share of rows with *any* mass (what the 90 %
        # gate means), `mean_mass` is how much of the teacher's probability a
        # filled row captures (0.906 at top-24, 0.755 at 5 wide).
        mean_mass = float(mass[mass > 0].mean()) if nonzero else 0.0
        if ratio < min_mass_ratio:
            raise SoftError(
                f"{path}: only {ratio:.1%} of rows carry teacher mass "
                f"(need {min_mass_ratio:.0%})"
            )
    else:
        nonzero = 0
        ratio = 0.0
        mean_mass = 0.0

    return {
        "path": path,
        "sentences": len(sentences),
        "rows": rows,
        "topk": int(ids.shape[1]),
        "row_coverage": ratio,
        "mean_mass": mean_mass,
        "mass_ratio": ratio,   # kept: older scripts and logs print this key
        "id_max": int(ids.max()) if rows else -1,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path")
    ap.add_argument("--vocab-size", type=int, default=None)
    ap.add_argument("--expect-sentences", type=int, default=None)
    ap.add_argument("--min-mass-ratio", type=float, default=0.9,
                    help="minimum share of ROWS that carry any teacher mass "
                         "(not the teacher's probability mass; that is reported "
                         "as mean row mass)")
    args = ap.parse_args()
    try:
        s = validate_soft(
            args.path,
            vocab_size=args.vocab_size,
            expect_sentences=args.expect_sentences,
            min_mass_ratio=args.min_mass_ratio,
        )
    except SoftError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    print(
        f"OK {s['path']}: {s['sentences']} sentences, {s['rows']} rows, "
        f"top-{s['topk']}, row coverage {s['row_coverage']:.1%}, "
        f"mean row mass {s['mean_mass']:.3f}, max id {s['id_max']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
