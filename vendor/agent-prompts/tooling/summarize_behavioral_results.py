#!/usr/bin/env python3
"""Summarize paired behavioral results (skill vs no-skill).

Reads ``<skill>.<mode>.grading.json`` files produced by
``run_behavioral_evals.py --mode both`` and prints a per-skill comparison.

Usage:
    python3 tooling/summarize_behavioral_results.py --dirs evals/results/seed-*
    python3 tooling/summarize_behavioral_results.py --dirs ... --json

Exit 0 when at least one pair is found and both modes are present for every
skill; 2 on a setup error. Missing arms are reported, not silently averaged.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

MODES = ("skill", "no-skill")


def load(results_dir):
    rows = []
    for path in sorted(results_dir.glob("*.grading.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        run = data.get("run") or {}
        skill = run.get("skill") or data.get("skill") or path.name.split(".")[0]
        mode = run.get("mode")
        if mode not in MODES:
            continue
        results = data.get("results") or []
        for entry in results:
            rows.append({
                "skill": skill,
                "mode": mode,
                "passed": bool(entry.get("passed")),
                "score": float(entry.get("score") or 0.0),
                "tokens": int((entry.get("executor_usage") or {}).get(
                    "total_tokens") or 0)
                + int((entry.get("grader_usage") or {}).get(
                    "total_tokens") or 0),
                "seed": run.get("seed"),
                "cache_hit": int((entry.get("executor_usage") or {}).get(
                    "prompt_cache_hit_tokens") or 0),
                "cache_miss": int((entry.get("executor_usage") or {}).get(
                    "prompt_cache_miss_tokens") or 0),
            })
    return rows


def summarize(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault((row["skill"], row["mode"]), []).append(row)
    skills = sorted({skill for skill, _ in grouped})
    summary = []
    for skill in skills:
        item = {"skill": skill, "arms": {}}
        for mode in MODES:
            entries = grouped.get((skill, mode), [])
            item["arms"][mode] = {
                "cases": len(entries),
                "passed": sum(1 for entry in entries if entry["passed"]),
                "mean_score": round(statistics.mean(
                    [entry["score"] for entry in entries]), 4) if entries else 0.0,
                "tokens": sum(entry["tokens"] for entry in entries),
                "cache_hit": sum(entry["cache_hit"] for entry in entries),
                "cache_miss": sum(entry["cache_miss"] for entry in entries),
                "cache_rate": round(
                    sum(entry["cache_hit"] for entry in entries)
                    / max(1, sum(entry["cache_hit"] + entry["cache_miss"]
                                 for entry in entries)), 4),
                "seeds": sorted({entry["seed"] for entry in entries
                                 if entry["seed"] is not None}),
            }
        skill_arm = item["arms"]["skill"]
        base_arm = item["arms"]["no-skill"]
        item["delta"] = round(skill_arm["mean_score"] - base_arm["mean_score"], 4)
        summary.append(item)
    return summary


def print_markdown(summary):
    print("| Skill | Cases | Skill pass | Baseline pass | Mean skill | Mean base | Delta | Tokens | Cache skill | Cache base |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for item in summary:
        skill = item["arms"]["skill"]
        base = item["arms"]["no-skill"]
        print("| %s | %d | %d/%d | %d/%d | %.2f | %.2f | %+.2f | %d | %.0f%% | %.0f%% |"
              % (item["skill"], skill["cases"],
                 skill["passed"], skill["cases"],
                 base["passed"], base["cases"],
                 skill["mean_score"], base["mean_score"],
                 item["delta"], skill["tokens"] + base["tokens"],
                 skill["cache_rate"] * 100, base["cache_rate"] * 100))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Summarize paired behavioral runs.")
    parser.add_argument("--dirs", nargs="+", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    rows = []
    for directory in args.dirs:
        path = Path(directory).resolve()
        if not path.is_dir():
            print("summarize: no such directory: %s" % path)
            return 2
        rows.extend(load(path))
    if not rows:
        print("summarize: no paired grading files found")
        return 2

    summary = summarize(rows)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print_markdown(summary)
        missing = [(item["skill"], mode) for item in summary
                   for mode in MODES if not item["arms"][mode]["cases"]]
        for skill, mode in missing:
            print("WARN missing %s arm for %s" % (mode, skill))
    return 0


if __name__ == "__main__":
    sys.exit(main())
