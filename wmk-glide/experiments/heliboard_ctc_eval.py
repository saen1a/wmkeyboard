#!/usr/bin/env python3
"""Compare the FUTO CTC decoder with GlideBeam on one HeliBoard slice.

The CTC side is `ctc_glide_eval` over the FSW1 emissions `emit.py` produced
from the FUTO encoder/decoder. The GlideBeam side is the same group's
records/layout with the German profile. Both filter to the words the list
holds, so the denominator is the same.

    heliboard_ctc_eval.py --slices /tmp/slices/de --bins /tmp/ctc \
        --list /tmp/de_aosp.txt \
        --ctc /home/saenta/wm-glide-target/release/examples/ctc_glide_eval \
        --beam /home/saenta/wm-glide-target/release/examples/glide_beam_eval \
        --out /tmp/ctc-de.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess

CTC = re.compile(r"n (\d+) top1 ([\d.]+) top4 ([\d.]+)")
BEAM = re.compile(r"top1 ([\d.]+) top4 ([\d.]+) n (\d+)")
PROFILE = "freq_weight=0.75 gap_weight=2.0 join_cost=8 join_min_part=4 join_part_penalty=0.1"


def columns(layout: dict) -> int:
    rows: dict[float, int] = {}
    for key in layout["keys"]:
        row = round(float(key["cy"]), 2)
        rows[row] = rows.get(row, 0) + 1
    return max(1, max(rows.values(), default=1))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slices", required=True)
    parser.add_argument("--bins", required=True)
    parser.add_argument("--list", required=True)
    parser.add_argument("--ctc", required=True)
    parser.add_argument("--beam", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    with open(os.path.join(args.slices, "manifest.json"), "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    groups = []
    for entry in manifest["groups"]:
        group = entry["group"]
        binary = os.path.join(args.bins, f"{group}.bin")
        if not os.path.exists(binary):
            continue
        directory = os.path.join(args.slices, group)
        records = os.path.join(directory, "records.jsonl")
        layout_path = os.path.join(directory, "layout.json")
        with open(layout_path, "r", encoding="utf-8") as fh:
            layout = json.load(fh)
        ctc = subprocess.run([args.ctc, binary, args.list], text=True, capture_output=True, check=False)
        beam = subprocess.run(
            [args.beam, records, layout_path, args.list],
            input=PROFILE + "\n",
            text=True,
            capture_output=True,
            env={**os.environ, "COLS": str(columns(layout)), "THREADS": "8"},
            check=False,
        )
        cm = CTC.search(ctc.stdout)
        bm = BEAM.search(beam.stdout)
        if not cm or not bm:
            raise RuntimeError(f"{group}: no result line\nCTC: {ctc.stdout[-300:]}\nBEAM: {beam.stdout[-300:]}\n{ctc.stderr[-300:]}")
        n = int(cm.group(1))
        if n != int(bm.group(3)):
            raise RuntimeError(f"{group}: n mismatch {n} != {bm.group(3)}")
        groups.append({
            "group": group,
            "n": n,
            "ctc_top1": round(float(cm.group(2)) * n),
            "ctc_top4": round(float(cm.group(3)) * n),
            "beam_top1": round(float(bm.group(1)) * n),
            "beam_top4": round(float(bm.group(2)) * n),
        })
    total = sum(g["n"] for g in groups)
    result = {
        "n": total,
        "groups": len(groups),
        "ctc_top1": sum(g["ctc_top1"] for g in groups) / total,
        "ctc_top4": sum(g["ctc_top4"] for g in groups) / total,
        "beam_top1": sum(g["beam_top1"] for g in groups) / total,
        "beam_top4": sum(g["beam_top4"] for g in groups) / total,
        "detail": groups,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print(
        f"n={total} groups={len(groups)} "
        f"CTC={100*result['ctc_top1']:.2f}/{100*result['ctc_top4']:.2f} "
        f"beam={100*result['beam_top1']:.2f}/{100*result['beam_top4']:.2f} "
        f"delta={100*(result['ctc_top1']-result['beam_top1']):+.2f}/"
        f"{100*(result['ctc_top4']-result['beam_top4']):+.2f} pp"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
