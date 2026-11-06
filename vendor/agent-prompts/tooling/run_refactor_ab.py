#!/usr/bin/env python3
"""Old-vs-new skill-body A/B (on demand, costs tokens).

The paired baseline measures "skill vs no skill". This tool measures the
refactor itself: the pre-refactor body from a git ref vs the current body, on
the same behavioral cases, model, and seed.

Usage:
    python3 tooling/run_refactor_ab.py --seed 7
    python3 tooling/run_refactor_ab.py --base-ref ff91dc3 --skills jq-json-processing

Results are written under ``evals/results/refactor-ab-<seed>/``.
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

TOOLING = Path(__file__).resolve().parent
RUNNER_PATH = TOOLING / "run_behavioral_evals.py"

SPLIT_SKILLS = [
    "jq-json-processing",
    "skill-creator",
    "first-principles-review",
    "mcp-builder",
    "anti-entropy-governance",
    "deepseek-v4-agent-defense",
    "agent-md-refactor",
]


def load_runner():
    spec = importlib.util.spec_from_file_location("behavioral_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load_runner()


def skill_path(root, skill):
    matches = list((root / "skills").rglob("%s/SKILL.md" % skill))
    if not matches:
        raise SystemExit("skill not found: %s" % skill)
    return matches[0].relative_to(root).as_posix()


def old_body(root, ref, relative_path):
    result = subprocess.run(
        ["git", "-C", str(root), "show", "%s:%s" % (ref, relative_path)],
        capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit("git show failed for %s:%s: %s"
                         % (ref, relative_path, result.stderr.strip()))
    return result.stdout


def load_cases(root, skill):
    path = root / "evals" / "behavioral" / ("%s.json" % skill)
    if not path.is_file():
        raise SystemExit("no behavioral cases for %s" % skill)
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("evals", [])


def run_one(skill, body, case, args, api_key, arm):
    started = time.monotonic()
    messages = [{"role": "system", "content": body},
                {"role": "user", "content": case["prompt"]}]
    response, usage = RUNNER.chat(
        args.base_url, api_key, args.executor_model, messages, args.timeout,
        args.max_tokens, seed=args.seed)
    grader_messages = RUNNER.grade(case["expectations"], case["prompt"], response)
    graded = None
    grader_usage = {}
    last_error = None
    for _attempt in range(3):
        raw, grader_usage = RUNNER.chat(
            args.base_url, api_key, args.grader_model, grader_messages,
            args.timeout, args.grader_max_tokens, seed=args.seed)
        try:
            graded = RUNNER.parse_grader(raw)
            break
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = exc
    if graded is None:
        raise RuntimeError("grader invalid JSON for %s/%s/%s: %s"
                           % (skill, case["id"], arm, last_error))
    results = graded["results"]
    score = graded.get("score")
    if not isinstance(score, (int, float)):
        score = sum(1 for entry in results if entry.get("met")) / len(results)
    return {
        "skill": skill,
        "case": case["id"],
        "arm": arm,
        "passed": all(bool(entry.get("met")) for entry in results),
        "score": round(float(score), 4),
        "executor_usage": usage,
        "grader_usage": grader_usage,
        "duration_s": round(time.monotonic() - started, 3),
        "expectations": results,
        "response": response,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Old-vs-new skill-body A/B.")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--base-ref", default="ff91dc3",
                        help="git ref holding the pre-refactor bodies")
    parser.add_argument("--skills", nargs="+", default=SPLIT_SKILLS)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--results-dir", default=None)
    parser.add_argument("--base-url", default="https://api.deepseek.com/v1")
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--executor-model", default="deepseek-flash")
    parser.add_argument("--grader-model", default="deepseek-v4-pro")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--grader-max-tokens", type=int, default=4096)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    selected = []
    for skill in args.skills:
        relative = skill_path(root, skill)
        current = (root / relative).read_text(encoding="utf-8")
        previous = old_body(root, args.base_ref, relative)
        selected.append((skill, relative, previous, current,
                         load_cases(root, skill)))

    if args.dry_run:
        print("refactor-ab: dry run, base %s" % args.base_ref)
        for skill, relative, previous, current, cases in selected:
            print("  %s: old=%d bytes new=%d bytes cases=%d"
                  % (skill, len(previous.encode()), len(current.encode()),
                     len(cases)))
        return 0

    api_key = os.environ.get(args.api_key_env, "").strip()
    if not api_key:
        print("refactor-ab: %s is empty" % args.api_key_env)
        return 2

    results_dir = Path(args.results_dir).resolve() if args.results_dir \
        else root / "evals" / "results" / ("refactor-ab-%s" % args.seed)
    results_dir.mkdir(parents=True, exist_ok=True)
    out = results_dir / ("refactor-ab-%s.json" % args.seed)
    started = datetime.now(timezone.utc)
    results = []
    failures = 0
    for skill, relative, previous, current, cases in selected:
        for case in cases:
            for arm, body in (("old", previous), ("new", current)):
                try:
                    result = run_one(skill, body, case, args, api_key, arm)
                except (urllib.error.URLError, OSError, RuntimeError, KeyError) as exc:
                    print("refactor-ab: harness error on %s/%s/%s: %s"
                          % (skill, case.get("id"), arm, exc), flush=True)
                    out.write_text(json.dumps({
                        "run": {"base_ref": args.base_ref, "seed": args.seed,
                                "started_utc": started.isoformat(timespec="seconds")},
                        "results": results}, indent=2), encoding="utf-8")
                    return 2
                results.append(result)
                failures += 0 if result["passed"] else 1
                print("%s %s/%s/%s score=%.2f"
                      % ("PASS" if result["passed"] else "FAIL", skill,
                         result["case"], arm, result["score"]), flush=True)
                out.write_text(json.dumps({
                    "schema": "refactor-ab/1",
                    "run": {
                        "base_ref": args.base_ref,
                        "seed": args.seed,
                        "executor_model": args.executor_model,
                        "grader_model": args.grader_model,
                        "harness": "openai-compatible-chat",
                        "started_utc": started.isoformat(timespec="seconds"),
                        "duration_s": round(
                            (datetime.now(timezone.utc) - started).total_seconds(), 3),
                    },
                    "results": results,
                }, indent=2), encoding="utf-8")
    print("refactor-ab: %d runs, %d failed -> %s"
          % (len(results), failures, out))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
