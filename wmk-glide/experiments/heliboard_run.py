#!/usr/bin/env python3
"""Run two glide tunings over a HeliBoard slice and report paired evidence.

The slice is the output of heliboard_slice.py: a manifest, and one
records.jsonl + layout.json per keyboard geometry. Each geometry is decoded
twice with the harness's DUMP on, so every stroke's hit flag is paired within
the same layout.

    heliboard_run.py --lang nl \
        --slice /tmp/helio/slices-full/nl \
        --list /tmp/helio/wordlists/nl_aosp.txt \
        --harness ~/wm-glide-target/release/examples/glide_beam_eval \
        --out /tmp/helio/results/nl.json

Tuning A is the shipped default; tuning B is the measured profile. The report
includes top-1/top-4, the paired wins/losses, an exact McNemar p, and a cluster
bootstrap over geometries.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import subprocess
import tempfile

DEFAULT_A = "freq_weight=1.0 gap_weight=1.33"
DEFAULT_B = "freq_weight=0.75 gap_weight=2.0"
AGG = re.compile(r"top1 ([\d.]+) top4 ([\d.]+) n (\d+)")


def columns(layout: dict) -> int:
    """The widest key row, not the distinct x centres: rows are offset."""
    rows: dict[float, int] = {}
    for key in layout["keys"]:
        row = round(float(key["cy"]), 2)
        rows[row] = rows.get(row, 0) + 1
    return max(1, max(rows.values(), default=1))


def run_once(harness: str, records: str, layout: str, word_list: str, tuning: str, dump: str, cols: int, threads: int) -> tuple[float, float, int, list[int]]:
    env = os.environ.copy()
    env.update({
        "COLS": str(cols),
        "ALL": "1",
        "RESULTS": "4",
        "THREADS": str(threads),
        "DUMP": dump,
    })
    proc = subprocess.run(
        [harness, records, layout, word_list],
        input=tuning + "\n",
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"harness failed ({proc.returncode}): {proc.stderr.strip()[:400]}")
    match = AGG.search(proc.stdout)
    if not match:
        raise RuntimeError(f"no result line for {records}: {proc.stdout[:200]!r}")
    hits = []
    with open(dump, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                try:
                    hits.append(int(parts[2]))
                except ValueError:
                    pass
    return float(match.group(1)), float(match.group(2)), int(match.group(3)), hits


def mcnemar(wins: int, losses: int) -> float:
    discordant = wins + losses
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, i) for i in range(min(wins, losses) + 1)) / (2 ** discordant)
    return min(1.0, 2.0 * tail)


def cluster_ci(groups: list[dict], key: str, samples: int = 10000, seed: int = 20261109) -> tuple[float, float]:
    rng = random.Random(seed)
    out = []
    for _ in range(samples):
        a = b = n = 0
        for g in (rng.choice(groups) for _ in groups):
            a += g[f"a_{key}"]
            b += g[f"b_{key}"]
            n += g["n"]
        if n:
            out.append((b - a) / n)
    out.sort()
    if not out:
        return (0.0, 0.0)
    return out[int(0.025 * (len(out) - 1))], out[int(0.975 * (len(out) - 1))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", required=True)
    parser.add_argument("--slice", required=True)
    parser.add_argument("--list", required=True)
    parser.add_argument("--harness", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--a", default=DEFAULT_A)
    parser.add_argument("--b", default=DEFAULT_B)
    args = parser.parse_args()

    with open(os.path.join(args.slice, "manifest.json"), "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    groups = []
    with tempfile.TemporaryDirectory(prefix=f"helio-{args.lang}-") as tmp:
        for entry in manifest["groups"]:
            group = entry["group"]
            directory = os.path.join(args.slice, group)
            records = os.path.join(directory, "records.jsonl")
            layout_path = os.path.join(directory, "layout.json")
            with open(layout_path, "r", encoding="utf-8") as fh:
                layout = json.load(fh)
            cols = columns(layout)
            a_dump = os.path.join(tmp, f"{group}-a.dump")
            b_dump = os.path.join(tmp, f"{group}-b.dump")
            a1, a4, an, a_hits = run_once(args.harness, records, layout_path, args.list, args.a, a_dump, cols, args.threads)
            b1, b4, bn, b_hits = run_once(args.harness, records, layout_path, args.list, args.b, b_dump, cols, args.threads)
            if an != bn or an != len(a_hits) or bn != len(b_hits):
                raise RuntimeError(f"{group}: n mismatch {an}/{bn}/{len(a_hits)}/{len(b_hits)}")
            wins = sum(1 for a, b in zip(a_hits, b_hits) if a == 0 and b == 1)
            losses = sum(1 for a, b in zip(a_hits, b_hits) if a == 1 and b == 0)
            groups.append({
                "group": group,
                "n": an,
                "cols": cols,
                "a_top1": round(a1 * an),
                "b_top1": round(b1 * bn),
                "a_top4": round(a4 * an),
                "b_top4": round(b4 * bn),
                "wins": wins,
                "losses": losses,
            })
    total_n = sum(g["n"] for g in groups)
    result = {
        "language": args.lang,
        "slice": args.slice,
        "list": args.list,
        "n": total_n,
        "groups": len(groups),
        "a": args.a,
        "b": args.b,
        "a_top1": sum(g["a_top1"] for g in groups) / total_n,
        "b_top1": sum(g["b_top1"] for g in groups) / total_n,
        "a_top4": sum(g["a_top4"] for g in groups) / total_n,
        "b_top4": sum(g["b_top4"] for g in groups) / total_n,
        "wins": sum(g["wins"] for g in groups),
        "losses": sum(g["losses"] for g in groups),
        "mcnemar_p": mcnemar(sum(g["wins"] for g in groups), sum(g["losses"] for g in groups)),
        "top1_ci": cluster_ci(groups, "top1"),
        "top4_ci": cluster_ci(groups, "top4"),
        "detail": groups,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print(
        f"{args.lang}: n={total_n} groups={len(groups)} "
        f"A={100*result['a_top1']:.2f}/{100*result['a_top4']:.2f} "
        f"B={100*result['b_top1']:.2f}/{100*result['b_top4']:.2f} "
        f"delta={100*(result['b_top1']-result['a_top1']):+.2f}/{100*(result['b_top4']-result['a_top4']):+.2f} pp "
        f"wins={result['wins']} losses={result['losses']} p={result['mcnemar_p']:.3g} "
        f"CI1=[{100*result['top1_ci'][0]:+.2f},{100*result['top1_ci'][1]:+.2f}] "
        f"CI4=[{100*result['top4_ci'][0]:+.2f},{100*result['top4_ci'][1]:+.2f}]"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
