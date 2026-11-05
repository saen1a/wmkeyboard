#!/usr/bin/env python3
"""Role-body A/B: current role prompt vs a trimmed candidate.

The skill refactor A/B tests whole skill bodies; this tests role prompts. The
candidate arm defaults to the pinned ``evals/role-ab/arms/linear-v1.1``; pass
``--candidates-dir`` for another arm. Tasks live at
``evals/role-ab/tasks/<role>.json``; ``--tasks-dir`` selects another set and
``--context-file`` compares a role alone with the same role plus an
always-loaded context file (AGENTS.md). A task set may hold more than one case
per role: any other ``*.json`` whose ``role`` field names the role is run as an
additional task, keyed by its file stem.

Usage:
    python3 tooling/run_role_ab.py --seed 7
    python3 tooling/run_role_ab.py --roles eng-frontend-developer

Results are written under ``evals/results/role-ab-<seed>/``.
"""

import argparse
import hashlib
import importlib.util
import json
import os
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


SLOT_VALUES = {
    "PROJECT_ID": "fixture-project",
    "PROJECT_RULES": "the project rules",
    "VERIFICATION_COMMANDS": "make test",
    "ACCESSIBILITY_STANDARD": "WCAG 2.2 AA",
    "MUTATION_POLICY": "edit only the approved files",
    "SAFETY_RULE": "no secrets; no push",
    "HANDOFF_TARGETS": "reviewer",
    "ROLLBACK_COMMAND": "git revert HEAD",
    "PROJECT_NORMALIZER_TOOLING": "python3 scripts/normalize.py",
}


def fill_slots(text):
    import re
    return re.sub(r"\{\{([A-Z0-9_]+)\}\}",
                  lambda m: SLOT_VALUES.get(m.group(1),
                                            "project value for %s" % m.group(1).lower()),
                  text)


def role_path(root, role):
    for base in (root / "agents", root / "roles"):
        matches = list(base.rglob("%s.md" % role)) if base.is_dir() else []
        if matches:
            return matches[0]
    raise SystemExit("role not found: %s" % role)


def candidate_path(root, role, candidates_dir):
    path = candidates_dir / ("%s.md" % role)
    if not path.is_file():
        raise SystemExit("candidate not found: %s" % path)
    return path


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def task(root, role, tasks_dir=None):
    base = tasks_dir or root / "evals" / "role-ab" / "tasks"
    path = base / ("%s.json" % role)
    if not path.is_file():
        raise SystemExit("task not found: %s" % path)
    return json.loads(path.read_text(encoding="utf-8"))


def validate_fixture(fixture, label):
    """Reject a task that the runner cannot grade."""
    if not isinstance(fixture, dict):
        raise SystemExit("task %s: not a JSON object" % label)
    prompt = fixture.get("prompt")
    expectations = fixture.get("expectations")
    if not isinstance(prompt, str) or not prompt.strip():
        raise SystemExit("task %s: missing prompt" % label)
    if not isinstance(expectations, list) or not expectations:
        raise SystemExit("task %s: expectations must be a non-empty list" % label)
    for entry in expectations:
        if not isinstance(entry, str) or not entry.strip():
            raise SystemExit("task %s: expectations must be non-empty strings"
                             % label)


def load_tasks(root, role, tasks_dir=None):
    """Return ``[(task_id, fixture)]`` for one role.

    A task set may hold one fixture per role at ``<role>.json`` (task id
    ``None``, the original behaviour) or several per role: any other
    ``*.json`` carrying a matching ``role`` field becomes an additional case
    with its stem as the task id. Sorted by stem, so the order is stable.
    """
    base = tasks_dir or root / "evals" / "role-ab" / "tasks"
    entries = []
    legacy = base / ("%s.json" % role)
    if legacy.is_file():
        entries.append((None, task(root, role, tasks_dir)))
    for path in sorted(base.glob("*.json")):
        if path.stem == role:
            continue
        fixture = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(fixture, dict) or fixture.get("role") != role:
            continue
        entries.append((path.stem, fixture))
    if not entries:
        raise SystemExit("task not found: %s/%s.json" % (base, role))
    for task_id, fixture in entries:
        validate_fixture(fixture, task_id or role)
    return entries


def discover_roles(base):
    """Roles named by a task set: the ``role`` field, else the file stem."""
    roles = set()
    for path in sorted(base.glob("*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(fixture, dict) and isinstance(fixture.get("role"), str):
            roles.add(fixture["role"])
        else:
            roles.add(path.stem)
    return sorted(roles)


def with_context(context_text, role_text):
    """Return the candidate arm: a context file loaded before the role body."""
    return context_text.strip() + "\n\n" + role_text


def display_path(path, root):
    path = Path(path).resolve()
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def parse_header(text):
    """Parse one ``name: value`` CLI header into a pair.

    Values may contain colons (a URL, a timestamp). An empty name, a missing
    colon or an embedded newline is rejected rather than sent.
    """
    name, sep, value = text.partition(":")
    name, value = name.strip(), value.strip()
    if not sep or not name:
        raise SystemExit("role-ab: --header must be 'name: value': %r" % text)
    if any(char in name + value for char in ("\r", "\n")):
        raise SystemExit("role-ab: --header must be a single line: %r" % text)
    return name, value


def request_headers(extra_headers, session_header=False, session_id=None,
                    env=None):
    """Build the extra request headers sent to both models.

    ``--header`` is generic: any endpoint can require a routing or user-agent
    header. ``--session-header`` is the OpenCode Go convenience: it sends
    ``x-opencode-session`` from ``--session-id`` or ``$OPENCODE_SESSION_ID``,
    because that endpoint rejects a request without one (400 MissingSessionID).
    Only names are ever printed or recorded; values stay out of the evidence.
    """
    env = os.environ if env is None else env
    headers = {}
    for text in extra_headers or []:
        name, value = parse_header(text)
        headers[name] = value
    if session_header:
        value = session_id if session_id is not None \
            else env.get("OPENCODE_SESSION_ID", "")
        value = (value or "").strip()
        if not value:
            raise SystemExit("role-ab: --session-header needs --session-id or "
                             "OPENCODE_SESSION_ID")
        headers["x-opencode-session"] = value
    return headers


def describe_http_error(exc):
    """Name a provider failure by status and body, so the log is evidence."""
    code = getattr(exc, "code", None)
    detail = ""
    try:
        detail = exc.read().decode("utf-8", "replace").strip()
    except (AttributeError, OSError, ValueError):
        detail = str(getattr(exc, "reason", "") or "")
    detail = " ".join(detail.split())[:400]
    if code is None:
        return detail or exc.__class__.__name__
    return "HTTP %s%s" % (code, ": " + detail if detail else "")


def run_one(role, body, fixture, args, api_key, arm, task_id=None,
            headers=None):
    started = time.monotonic()
    messages = [{"role": "system", "content": body},
                {"role": "user", "content": fixture["prompt"]}]
    response, usage = RUNNER.chat(
        args.base_url, api_key, args.executor_model, messages, args.timeout,
        args.max_tokens, seed=args.seed, extra_headers=headers)
    grader_messages = RUNNER.grade(
        fixture["expectations"], fixture["prompt"], response)
    graded = None
    grader_usage = {}
    error = None
    for _attempt in range(3):
        raw, grader_usage = RUNNER.chat(
            args.base_url, api_key, args.grader_model, grader_messages,
            args.timeout, args.grader_max_tokens, seed=args.seed,
            extra_headers=headers)
        try:
            graded = RUNNER.parse_grader(raw)
            break
        except (ValueError, json.JSONDecodeError) as exc:
            error = exc
    if graded is None:
        raise RuntimeError("grader invalid JSON for %s/%s: %s"
                           % (role, arm, error))
    results = graded["results"]
    # The grader may echo an expectation paraphrased or truncated. Key every
    # row to the fixture's text (results are positional) and keep the echo only
    # when it differs, so per-expectation tallies do not split one expectation
    # into several strings.
    for index, entry in enumerate(results):
        if index >= len(fixture["expectations"]):
            break
        expected = fixture["expectations"][index]
        echoed = entry.get("expectation")
        entry["expectation"] = expected
        if isinstance(echoed, str) and echoed != expected:
            entry["grader_expectation"] = echoed
    # The score is the fraction of votes, never the grader's own number: a number
    # that disagrees with the votes would silently become the result. The claimed
    # value is kept beside it so the disagreement stays visible.
    met = sum(1 for entry in results if entry.get("met"))
    score = met / len(results) if results else 0.0
    claimed = graded.get("score")
    if not isinstance(claimed, (int, float)) \
            or abs(float(claimed) - float(score)) <= 1e-9:
        claimed = None
    return {
        "role": role,
        "task": task_id,
        "arm": arm,
        "passed": all(bool(entry.get("met")) for entry in results),
        "score": round(float(score), 4),
        "grader_score": round(float(claimed), 4) if claimed is not None else None,
        "truncated": bool(usage.get("finish_reason") == "length"
                          or usage.get("completion_tokens", 0) >= args.max_tokens),
        "executor_usage": usage,
        "grader_usage": grader_usage,
        "duration_s": round(time.monotonic() - started, 3),
        "expectations": results,
        "response": response,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Role-body A/B.")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--roles", nargs="+", default=None)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--results-dir", default=None)
    parser.add_argument("--candidates-dir", default=None,
                        help="candidate arm directory (default: evals/role-ab/arms/linear-v1.1)")
    parser.add_argument("--tasks-dir", default=None,
                        help="task directory (default: evals/role-ab/tasks); "
                             "one <role>.json or several files with a role field")
    parser.add_argument("--context-file", default=None,
                        help="compare the role alone with the same role plus this "
                             "always-loaded context file")
    parser.add_argument("--allow-identical", action="store_true",
                        help="allow an A/B where both arms are byte-identical")
    parser.add_argument("--base-url", default="https://api.deepseek.com/v1")
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--header", action="append", default=[],
                        metavar="NAME: VALUE",
                        help="extra request header for both models, repeatable")
    parser.add_argument("--session-header", action="store_true",
                        help="send x-opencode-session from --session-id or "
                             "OPENCODE_SESSION_ID")
    parser.add_argument("--session-id", default=None,
                        help="session id for --session-header (default: "
                             "OPENCODE_SESSION_ID)")
    parser.add_argument("--executor-model", default="deepseek-flash")
    parser.add_argument("--grader-model", default="deepseek-v4-pro")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--max-tokens", type=int, default=16384,
                        help="reasoning models spend this budget on reasoning first; "
                             "at 2048 every arm returns empty content and scores 0.00")
    parser.add_argument("--grader-max-tokens", type=int, default=4096)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if args.candidates_dir:
        candidates_dir = Path(args.candidates_dir).resolve()
    else:
        pinned = root / "evals" / "role-ab" / "arms" / "linear-v1.1"
        candidates_dir = pinned if pinned.is_dir() else root / "evals" / "role-ab" / "candidates"
    tasks_dir = Path(args.tasks_dir).resolve() if args.tasks_dir else None
    context = None
    if args.context_file:
        context = fill_slots(Path(args.context_file).resolve().read_text(
            encoding="utf-8")).strip()
        if not context:
            raise SystemExit("role-ab: context file is empty: %s" % args.context_file)
        default_tasks = tasks_dir or root / "evals" / "role-ab" / "tasks"
        roles = args.roles or discover_roles(default_tasks)
    else:
        roles = args.roles or sorted(path.stem for path in candidates_dir.glob("*.md"))
    if not roles:
        print("role-ab: no roles selected")
        return 2

    selected = []
    for role in roles:
        current = fill_slots(role_path(root, role).read_text(encoding="utf-8"))
        if context is not None:
            candidate = with_context(context, current)
        else:
            candidate = fill_slots(candidate_path(root, role, candidates_dir).read_text(encoding="utf-8"))
        if current == candidate and not args.allow_identical:
            raise SystemExit("role-ab: %s arms are identical; use a pinned arm or --allow-identical" % role)
        selected.append((role, current, candidate,
                         load_tasks(root, role, tasks_dir)))
    if args.dry_run:
        print("role-ab: dry run")
        for role, current, candidate, fixtures in selected:
            for task_id, _fixture in fixtures:
                print("  %s%s: current=%d candidate=%d bytes"
                      % (role, "" if task_id is None else "/" + task_id,
                         len(current.encode()), len(candidate.encode())))
        return 0

    api_key = os.environ.get(args.api_key_env, "").strip()
    if not api_key:
        print("role-ab: %s is empty" % args.api_key_env)
        return 2

    headers = request_headers(args.header, args.session_header,
                              args.session_id)
    if headers:
        print("role-ab: extra request headers: %s"
              % ", ".join(sorted(headers)), flush=True)

    results_dir = Path(args.results_dir).resolve() if args.results_dir \
        else root / "evals" / "results" / ("role-ab-%s" % args.seed)
    results_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    failures = 0
    for role, current, candidate, fixtures in selected:
        for task_id, fixture in fixtures:
            label = role if task_id is None else "%s/%s" % (role, task_id)
            out = results_dir / ("%s.role-ab-%s.json"
                                 % (label.replace("/", "."), args.seed))
            results = []
            for arm, body in (("current", current), ("candidate", candidate)):
                try:
                    result = run_one(role, body, fixture, args, api_key, arm,
                                     task_id=task_id, headers=headers)
                except (urllib.error.HTTPError, urllib.error.URLError, OSError,
                        RuntimeError, KeyError) as exc:
                    print("role-ab: harness error on %s/%s: %s"
                          % (label, arm, describe_http_error(exc)), flush=True)
                    return 2
                results.append(result)
                failures += 0 if result["passed"] else 1
                print("%s %s/%s score=%.2f"
                      % ("PASS" if result["passed"] else "FAIL", label, arm,
                         result["score"]), flush=True)
            if len(results) != 2:
                print("role-ab: incomplete arms for %s; not writing %s"
                      % (label, out), flush=True)
                return 2
            out.write_text(json.dumps({
                "schema": "role-ab/2",
                "run": {"seed": args.seed,
                        "executor_model": args.executor_model,
                        "grader_model": args.grader_model,
                        "harness": "openai-compatible-chat",
                        "max_tokens": args.max_tokens,
                        "temperature": 0,
                        "candidates_dir": str(candidates_dir.relative_to(root))
                        if candidates_dir.is_relative_to(root) else str(candidates_dir),
                        "tasks_dir": display_path(args.tasks_dir, root) if args.tasks_dir else None,
                        "context_file": display_path(args.context_file, root)
                        if args.context_file else None,
                        "request_headers": sorted(headers),
                        "started_utc": started.isoformat(timespec="seconds")},
                "arms": {"current": {"sha256": sha256(current),
                                      "chars": len(current)},
                          "candidate": {"sha256": sha256(candidate),
                                        "chars": len(candidate)}},
                "results": results,
            }, indent=2), encoding="utf-8")
            print("role-ab: %s -> %s" % (label, out))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
