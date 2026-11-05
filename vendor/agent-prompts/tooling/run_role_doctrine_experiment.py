#!/usr/bin/env python3
"""Role-doctrine A/B pilot (on demand, costs tokens).

Runs a small set of role tasks twice: once with the full doctrine fragment and
once with the compact candidate. The role body is otherwise identical. The
compact text is a candidate, not a fragment; this tool does not edit prompts.

Usage:
    python3 tooling/run_role_doctrine_experiment.py --seed 7
    python3 tooling/run_role_doctrine_experiment.py --roles eng-frontend-developer

Fixtures live in ``evals/role-doctrine/<role>.json`` and the compact text in
``evals/role-doctrine/compact-doctrine.txt``. Results are written under
``evals/results/role-doctrine-<seed>.json`` with model, harness, arm, usage,
score, and duration.
"""

import argparse
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

TOOLING = Path(__file__).resolve().parent
RUNNER_PATH = TOOLING / "run_behavioral_evals.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("behavioral_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load_runner()
DOCTRINE_RE = re.compile(r"<doctrine>.*?</doctrine>", re.S)


def load_fragment_doctrine(root):
    text = (root / "fragments" / "agent-doctrine.md").read_text(encoding="utf-8")
    match = DOCTRINE_RE.search(text)
    if not match:
        raise SystemExit("no <doctrine> block in fragments/agent-doctrine.md")
    return match.group(0)


def load_compact(root):
    path = root / "evals" / "role-doctrine" / "compact-doctrine.txt"
    return "<doctrine>\n%s\n</doctrine>" % path.read_text(encoding="utf-8").strip()


def role_path(role, root):
    for base in (root / "agents", root / "roles"):
        matches = list(base.rglob("%s.md" % role)) if base.is_dir() else []
        if matches:
            return matches[0]
    raise SystemExit("role template not found: %s" % role)


def build_system(role, root, doctrine):
    text = role_path(role, root).read_text(encoding="utf-8")
    if not DOCTRINE_RE.search(text):
        raise SystemExit("role has no doctrine block: %s" % role)
    return DOCTRINE_RE.sub(lambda _match: doctrine, text, count=1)


def load_fixture(role, root):
    path = root / "evals" / "role-doctrine" / ("%s.json" % role)
    if not path.is_file():
        raise SystemExit("fixture not found: %s" % path)
    return json.loads(path.read_text(encoding="utf-8"))


def run_arm(role, fixture, system, args, api_key, arm):
    started = time.monotonic()
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": fixture["prompt"]}]
    response, usage = RUNNER.chat(
        args.base_url, api_key, args.executor_model, messages, args.timeout,
        args.max_tokens, seed=args.seed)
    grader_messages = RUNNER.grade(
        fixture["expectations"], fixture["prompt"], response)
    raw, grader_usage = RUNNER.chat(
        args.base_url, api_key, args.grader_model, grader_messages,
        args.timeout, args.max_tokens, seed=args.seed)
    try:
        graded = RUNNER.parse_grader(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("grader invalid JSON for %s/%s: %s" % (role, arm, exc))
    results = graded["results"]
    score = graded.get("score")
    if not isinstance(score, (int, float)):
        score = sum(1 for entry in results if entry.get("met")) / len(results)
    return {
        "role": role,
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
    parser = argparse.ArgumentParser(
        description="Role doctrine A/B pilot (full vs compact).")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--roles", nargs="+", default=None,
                        help="role ids; default all fixtures under evals/role-doctrine")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--results-dir", default=None)
    parser.add_argument("--base-url", default="https://api.deepseek.com/v1")
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--executor-model", default="deepseek-flash")
    parser.add_argument("--grader-model", default="deepseek-v4-pro")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-tokens", type=int, default=2048)
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    fixture_dir = root / "evals" / "role-doctrine"
    scope = fixture_dir / "scope.json"
    if args.roles:
        roles = args.roles
    elif scope.is_file():
        roles = json.loads(scope.read_text(encoding="utf-8")).get("roles", [])
    else:
        roles = sorted(path.stem for path in fixture_dir.glob("*.json")
                       if path.name != "scope.json")
    if not roles:
        print("role-doctrine: no fixtures under %s" % fixture_dir)
        return 2

    api_key = os.environ.get(args.api_key_env, "").strip()
    if not api_key:
        print("role-doctrine: %s is empty" % args.api_key_env)
        return 2

    full = load_fragment_doctrine(root)
    compact = load_compact(root)
    started = datetime.now(timezone.utc)
    results = []
    failures = 0
    for role in roles:
        fixture = load_fixture(role, root)
        for arm, doctrine in (("full", full), ("compact", compact)):
            system = build_system(role, root, doctrine)
            try:
                result = run_arm(role, fixture, system, args, api_key, arm)
            except (urllib.error.URLError, OSError, RuntimeError, KeyError) as exc:
                print("role-doctrine: harness error on %s/%s: %s" % (role, arm, exc))
                return 2
            results.append(result)
            if not result["passed"]:
                failures += 1
            print("%s %s/%s score=%.2f tokens=%s"
                  % ("PASS" if result["passed"] else "FAIL", role, arm,
                     result["score"],
                     result["executor_usage"].get("total_tokens", "?")))

    results_dir = Path(args.results_dir).resolve() if args.results_dir \
        else root / "evals" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    out = results_dir / ("role-doctrine-%s.json" % args.seed)
    out.write_text(json.dumps({
        "schema": "role-doctrine/1",
        "run": {
            "seeded": args.seed,
            "executor_model": args.executor_model,
            "grader_model": args.grader_model,
            "harness": "openai-compatible-chat",
            "started_utc": started.isoformat(timespec="seconds"),
            "duration_s": round(
                (datetime.now(timezone.utc) - started).total_seconds(), 3),
        },
        "results": results,
    }, indent=2), encoding="utf-8")
    print("role-doctrine: %d arms, %d failed -> %s"
          % (len(results), failures, out))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
