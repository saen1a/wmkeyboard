#!/usr/bin/env python3
"""Summarize role A/B results into a durable, auditable manifest.

The raw result JSON is gitignored; this manifest is the committed evidence. It
records the arm bodies by hash, the protocol, per-role/seed scores, truncation
flags, and both the all-runs and complete-runs aggregates.

Usage:
    python3 tooling/summarize_role_ab.py \
      --results-dir evals/results/loop-ab2-7 \
      --results-dir evals/results/loop-ab2-11 \
      --results-dir evals/results/loop-ab2-23 \
      --output evals/role-ab/results/workflow-loop-2026-10.json
"""

import argparse
import json
import statistics
from pathlib import Path


def load(paths):
    """Index results by (role, task), seed and arm.

    A single-task role has an empty task id, so its label is the role name --
    the original keying. A role with several tasks gets one label per case,
    ``<role>/<task>``, and never overwrites a sibling's rows.
    """
    rows = {}
    runs = {}
    arm_hashes = {}
    for directory in paths:
        for path in sorted(Path(directory).glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            seed = data["run"]["seed"]
            runs[str(seed)] = data["run"]
            for result in data["results"]:
                key = (result["role"], result.get("task") or "")
                rows[(key, seed, result["arm"])] = result
                if data.get("arms"):
                    arm_hashes.setdefault(key, {})[str(seed)] = data["arms"]
    return rows, runs, arm_hashes


def label(key):
    role, task_id = key
    return role if not task_id else "%s/%s" % (role, task_id)


def is_truncated(result, max_tokens):
    if result.get("truncated"):
        return True
    usage = result.get("executor_usage") or {}
    if usage.get("finish_reason") == "length":
        return True
    return usage.get("completion_tokens", 0) >= max_tokens


def usage_summary(rows, arm):
    results = [r for (_, _, a), r in rows.items() if a == arm]
    prompt = [int((r.get("executor_usage") or {}).get("prompt_tokens") or 0)
              for r in results]
    completion = [int((r.get("executor_usage") or {}).get("completion_tokens") or 0)
                  for r in results]
    # The Kilo gateway returns `cost` in `usage`; other endpoints do not. Record
    # how many runs carried it so a partial cost total is not read as complete.
    costs = []
    for result in results:
        executor = (result.get("executor_usage") or {}).get("cost")
        grader = (result.get("grader_usage") or {}).get("cost")
        if executor is None and grader is None:
            continue
        costs.append(float(executor or 0) + float(grader or 0))
    # OpenCode Go reports `cost: 0` on a subscription allowance and puts the
    # real price beside it as `opencode.list_cost`. Record that too when it is
    # present, so a zero gateway cost is not mistaken for a free run.
    list_costs = []
    for result in results:
        total = 0.0
        seen = False
        for key in ("executor_usage", "grader_usage"):
            published = ((result.get(key) or {}).get("opencode") or {}).get(
                "list_cost")
            if published is not None:
                total += float(published)
                seen = True
        if seen:
            list_costs.append(total)
    latency = [float(result.get("duration_s") or 0) for result in results]
    count = len(results)
    return {
        "runs": count,
        "input_tokens_total": sum(prompt),
        "input_tokens_mean": round(sum(prompt) / count, 2) if count else None,
        "output_tokens_total": sum(completion),
        "output_tokens_mean": round(sum(completion) / count, 2) if count else None,
        "cost_usd_total": round(sum(costs), 6) if costs else None,
        "cost_usd_mean": round(sum(costs) / len(costs), 6) if costs else None,
        "cost_recorded_runs": len(costs),
        "list_cost_usd_total": round(sum(list_costs), 6) if list_costs else None,
        "list_cost_usd_mean": round(sum(list_costs) / len(list_costs), 6)
        if list_costs else None,
        "list_cost_recorded_runs": len(list_costs),
        "latency_s_mean": round(sum(latency) / count, 3) if count else None,
    }


def expectation_tally(rows, arm, canonical=None):
    checked = met = 0
    by_expectation = {}
    for (key, _, a), result in rows.items():
        if a != arm:
            continue
        expected = (canonical or {}).get(key) or []
        for index, entry in enumerate(result.get("expectations", [])):
            # Key to the fixture when it is known: a grader that paraphrases
            # would otherwise split one expectation across several strings.
            text = expected[index] if index < len(expected) \
                else entry.get("expectation", "")
            bucket = by_expectation.setdefault(text, {"checked": 0, "met": 0})
            bucket["checked"] += 1
            checked += 1
            if entry.get("met"):
                bucket["met"] += 1
                met += 1
    return {
        "checked": checked,
        "met": met,
        "by_expectation": dict(sorted(by_expectation.items())),
    }


def load_expectations(directory):
    """Map ``(role, task id)`` to the expectation texts of a task directory.

    Mirrors ``run_role_ab.load_tasks`` keying: a file with a ``role`` field is
    one case keyed by its stem, a bare ``<role>.json`` is the legacy single-task
    shape keyed by the empty task id.
    """
    mapping = {}
    for path in sorted(Path(directory).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("expectations"), list):
            continue
        role = data.get("role") if isinstance(data.get("role"), str) else path.stem
        task_id = path.stem if isinstance(data.get("role"), str) else ""
        mapping[(role, task_id)] = [text for text in data["expectations"]
                                    if isinstance(text, str)]
    return mapping


def main(argv=None):
    parser = argparse.ArgumentParser(description="Summarize role A/B results.")
    parser.add_argument("--results-dir", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--exclude", action="append", default=[],
                        help="role to exclude from the aggregate")
    parser.add_argument("--exclude-reason", default="",
                        help="reason recorded for the excluded role(s)")
    parser.add_argument("--current-arm", default="doctrine 1.3.1 loop",
                        help="label for the current arm")
    parser.add_argument("--candidate-arm",
                        default="doctrine 1.1.0 linear (pinned at evals/role-ab/arms/linear-v1.1)",
                        help="label for the candidate arm")
    parser.add_argument("--experiment", default="workflow-loop-2026-10",
                        help="experiment name recorded in the manifest")
    parser.add_argument("--note", default="",
                        help="free-text protocol note")
    parser.add_argument("--doctrine-version", default="",
                        help="doctrine version used by the current arm")
    parser.add_argument("--current-ref", default="",
                        help="git ref/commit measured as the current arm")
    parser.add_argument("--tasks-dir", default=None,
                        help="task directory whose expectations key the tallies "
                             "(default: the texts the grader echoes)")
    args = parser.parse_args(argv)

    rows, runs, arm_hashes = load(args.results_dir)
    if not rows:
        raise SystemExit("no results found")
    canonical = load_expectations(args.tasks_dir) if args.tasks_dir else {}
    max_tokens = max(run.get("max_tokens", 0) for run in runs.values())
    excluded = set(args.exclude)
    keys = sorted({key[0] for key in rows if key[0] not in excluded})
    seeds = sorted({key[1] for key in rows})

    per_role = {}
    all_current = []
    all_candidate = []
    complete_current = []
    complete_candidate = []
    wins = ties = losses = 0
    complete_wins = complete_ties = complete_losses = 0
    truncated_pairs = []
    # The pair list above is arm-blind: it says a pair was truncated, not which
    # arm was cut off. The per-arm counts make the asymmetry the prose reports
    # readable from the committed manifest instead of re-derived from raw runs.
    truncated_by_arm = {"current": 0, "candidate": 0}

    for key in keys:
        name = label(key)
        entry = {}
        for arm in ("current", "candidate"):
            results = [r for (r_key, seed, r_arm), r in rows.items()
                       if r_key == key and r_arm == arm]
            scores = [r["score"] for r in results]
            entry[arm] = {
                "mean": round(statistics.mean(scores), 4) if scores else None,
                "passed": sum(bool(r["passed"]) for r in results),
                "runs": len(results),
            }
            (all_current if arm == "current" else all_candidate).extend(scores)
        for seed in seeds:
            current = rows.get((key, seed, "current"))
            candidate = rows.get((key, seed, "candidate"))
            if not current or not candidate:
                continue
            delta = current["score"] - candidate["score"]
            if delta > 0:
                wins += 1
            elif delta == 0:
                ties += 1
            else:
                losses += 1
            current_truncated = is_truncated(current, max_tokens)
            candidate_truncated = is_truncated(candidate, max_tokens)
            truncated = current_truncated or candidate_truncated
            entry[str(seed)] = {
                "current": current["score"],
                "candidate": candidate["score"],
                "delta": round(delta, 4),
                "truncated": truncated,
            }
            if truncated:
                arms = [arm for arm, hit in (("current", current_truncated),
                                             ("candidate", candidate_truncated))
                        if hit]
                for arm in arms:
                    truncated_by_arm[arm] += 1
                truncated_pairs.append({"role": name, "seed": seed, "arms": arms})
            else:
                complete_current.append(current["score"])
                complete_candidate.append(candidate["score"])
                if delta > 0:
                    complete_wins += 1
                elif delta == 0:
                    complete_ties += 1
                else:
                    complete_losses += 1
        per_role[name] = entry

    # One hash per role per arm; all seeds must agree.
    hashes = {}
    for key, by_seed in arm_hashes.items():
        if key not in keys:
            continue
        values = list(by_seed.values())
        current = {json.dumps(v["current"], sort_keys=True) for v in values}
        candidate = {json.dumps(v["candidate"], sort_keys=True) for v in values}
        if len(current) != 1 or len(candidate) != 1:
            raise SystemExit("arm hashes differ across seeds for %s" % label(key))
        hashes[label(key)] = {
            "current": values[0]["current"],
            "candidate": values[0]["candidate"],
        }

    manifest = {
        "schema": "role-ab-summary/3",
        "experiment": args.experiment,
        "protocol": {
            "seeds": seeds,
            "max_tokens": max_tokens,
            "temperature": 0,
            "executor_model": next(iter(runs.values())).get("executor_model"),
            "grader_model": next(iter(runs.values())).get("grader_model"),
            "harness": next(iter(runs.values())).get("harness"),
            "request_headers": sorted({name for run in runs.values()
                                       for name in run.get("request_headers")
                                       or []}),
            "doctrine_version": args.doctrine_version or None,
            "current_ref": args.current_ref or None,
            "current_arm": args.current_arm,
            "candidate_arm": args.candidate_arm,
            "excluded_roles": {role: args.exclude_reason for role in args.exclude},
            "tasks_per_role": "one" if all(not key[1] for key in keys) else "many",
            "expectation_keys": "fixture" if canonical else "grader",
            "raw_results": [str(Path(p).as_posix()) for p in args.results_dir],
            "note": args.note,
        },
        "arm_hashes": hashes,
        "usage": {
            "current": usage_summary(rows, "current"),
            "candidate": usage_summary(rows, "candidate"),
        },
        "expectations": {
            "current": expectation_tally(rows, "current", canonical),
            "candidate": expectation_tally(rows, "candidate", canonical),
        },
        "per_role": per_role,
        "truncated_pairs": truncated_pairs,
        "truncated_by_arm": truncated_by_arm,
        "overall_all": {
            "current_mean": round(statistics.mean(all_current), 4),
            "candidate_mean": round(statistics.mean(all_candidate), 4),
            "delta": round(statistics.mean(all_current) - statistics.mean(all_candidate), 4),
            "wins": wins,
            "ties": ties,
            "losses": losses,
            "pairs": len(all_current),
        },
        "overall_complete": {
            "current_mean": round(statistics.mean(complete_current), 4) if complete_current else None,
            "candidate_mean": round(statistics.mean(complete_candidate), 4) if complete_candidate else None,
            "delta": round(statistics.mean(complete_current) - statistics.mean(complete_candidate), 4)
            if complete_current and complete_candidate else None,
            "wins": complete_wins,
            "ties": complete_ties,
            "losses": complete_losses,
            "pairs": len(complete_current),
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("role-ab summary: %s" % output)
    print(json.dumps(manifest["overall_complete"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
