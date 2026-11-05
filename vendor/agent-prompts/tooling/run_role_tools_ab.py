#!/usr/bin/env python3
"""Tool-enabled role A/B for file-changing operations.

The text-only role harness cannot test a role that must read, run, and commit.
This harness gives the role a small tool surface in a temporary workspace:

- read_file(path), list_files()
- run_command(command) with a strict prefix allowlist

It runs the current and candidate role bodies against the same fixture and
grades the final report plus the resulting workspace.
"""

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

TOOLING = Path(__file__).resolve().parent
RUNNER_PATH = TOOLING / "run_behavioral_evals.py"
ROLE_AB_PATH = TOOLING / "run_role_ab.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load_module("behavioral_runner", RUNNER_PATH)
ROLE_AB = load_module("role_ab", ROLE_AB_PATH)

TOOLS = [
    {"type": "function", "function": {
        "name": "list_files",
        "description": "List files in the workspace.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a UTF-8 text file.",
        "parameters": {"type": "object", "required": ["path"],
                       "properties": {"path": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "run_command",
        "description": "Run an allowed shell command in the workspace.",
        "parameters": {"type": "object", "required": ["command"],
                       "properties": {"command": {"type": "string"}}}}},
]

ALLOWED_PREFIXES = (
    "python3 scripts/normalize.py",
    "python3 scripts/verify_ascii.py",
    "git status",
    "git diff",
    "git add",
    "git commit",
)


def allowed(command):
    return any(command.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def execute_tool(name, args, workspace):
    if name == "list_files":
        files = sorted(str(p.relative_to(workspace))
                       for p in workspace.rglob("*") if p.is_file()
                       and ".git/" not in str(p))
        return "\n".join(files)
    if name == "read_file":
        path = (workspace / args.get("path", "")).resolve()
        if workspace not in path.parents and path != workspace:
            return "ERROR: path escapes workspace"
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            return "ERROR: %s" % exc
    if name == "run_command":
        command = args.get("command", "")
        if not allowed(command):
            return "ERROR: command not allowed: %s" % command
        result = subprocess.run(command, shell=True, cwd=workspace,
                                capture_output=True, text=True, timeout=60)
        return "exit_code: %d\nstdout:\n%s\nstderr:\n%s" % (
            result.returncode, result.stdout, result.stderr)
    return "ERROR: unknown tool %s" % name


def chat_tools(base_url, api_key, model, messages, tools, timeout, max_tokens,
               seed):
    payload = json.dumps({
        "model": model, "messages": messages, "tools": tools,
        "temperature": 0, "max_tokens": max_tokens, "seed": seed,
    }).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions", data=payload,
        headers={"Authorization": "Bearer %s" % api_key,
                 "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def run_agent(role, body, fixture, args, api_key):
    workspace = Path(tempfile.mkdtemp(prefix="role-tools-"))
    seed_workspace(workspace)
    messages = [{"role": "system", "content": body},
                {"role": "user", "content": fixture["prompt"]}]
    transcript = []
    usage = {}
    for _turn in range(args.max_turns):
        data = chat_tools(args.base_url, api_key, args.executor_model, messages,
                          TOOLS, args.timeout, args.max_tokens, args.seed)
        usage = data.get("usage") or usage
        message = data["choices"][0]["message"]
        messages.append(message)
        calls = message.get("tool_calls") or []
        transcript.append({"role": "assistant", "content": message.get("content", ""),
                           "tool_calls": calls})
        if not calls:
            break
        for call in calls:
            fn = call.get("function", {})
            try:
                arguments = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                arguments = {}
            output = execute_tool(fn.get("name"), arguments, workspace)
            transcript.append({"role": "tool", "name": fn.get("name"),
                               "output": output})
            messages.append({"role": "tool", "tool_call_id": call.get("id"),
                             "content": output})
    else:
        output = "ERROR: turn limit reached"
    final = ""
    for entry in reversed(transcript):
        if entry["role"] == "assistant" and entry.get("content"):
            final = entry["content"]
            break

    file_state = {}
    for rel in fixture.get("files", []):
        path = workspace / rel
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        file_state[rel] = {
            "ascii": text.isascii(),
            "bytes": len(text.encode()),
            "non_ascii": sum(1 for ch in text if ord(ch) > 127),
        }
    git_status = subprocess.run("git status --porcelain", shell=True,
                                cwd=workspace, capture_output=True, text=True)
    commit = subprocess.run("git log --oneline -1", shell=True, cwd=workspace,
                            capture_output=True, text=True)
    commit_message = subprocess.run("git log -1 --pretty=%B", shell=True,
                                    cwd=workspace, capture_output=True, text=True)
    shutil.rmtree(workspace, ignore_errors=True)

    graded = None
    grader_usage = {}
    grader_messages = RUNNER.grade(fixture["expectations"], fixture["prompt"],
                                   final)
    for _attempt in range(3):
        raw, grader_usage = RUNNER.chat(
            args.base_url, api_key, args.grader_model, grader_messages,
            args.timeout, args.grader_max_tokens, seed=args.seed)
        try:
            graded = RUNNER.parse_grader(raw)
            break
        except Exception:
            continue
    if graded is None:
        raise RuntimeError("grader invalid JSON for %s" % role)
    results = graded["results"]
    score = graded.get("score")
    if not isinstance(score, (int, float)):
        score = sum(1 for e in results if e.get("met")) / len(results)
    return {
        "role": role, "final": final, "usage": usage,
        "transcript_turns": len(transcript),
        "files": file_state,
        "git_status": git_status.stdout.strip(),
        "last_commit": commit.stdout.strip(),
        "commit_message_ascii": commit_message.stdout.isascii(),
        "passed": all(bool(e.get("met")) for e in results),
        "score": round(float(score), 4),
        "expectations": results,
        "grader_usage": grader_usage,
    }


def seed_workspace(workspace):
    (workspace / "docs").mkdir()
    (workspace / "scripts").mkdir()
    (workspace / "README.md").write_text(
        '# Fixture\n\nA “quoted” line — with an em dash…\n', encoding="utf-8")
    (workspace / "docs" / "guide.md").write_text(
        "Guide — use “curly” quotes and an ellipsis…\n", encoding="utf-8")
    (workspace / "docs" / "faq.md").write_text(
        "FAQ — don’t use ‘smart’ quotes…\n", encoding="utf-8")
    (workspace / "scripts" / "normalize.py").write_text(
        "import pathlib, sys\n"
        "MAP = {'\\u201c': '\"', '\\u201d': '\"', '\\u2018': \"'\", "
        "'\\u2019': \"'\", '\\u2014': '-', '\\u2013': '-', '\\u2026': '...'}\n"
        "for name in sys.argv[1:]:\n"
        "    p = pathlib.Path(name)\n"
        "    t = p.read_text(encoding='utf-8')\n"
        "    p.write_text(''.join(MAP.get(c, c) for c in t), encoding='utf-8')\n",
        encoding="utf-8")
    (workspace / "scripts" / "verify_ascii.py").write_text(
        "import pathlib, sys\n"
        "bad = 0\n"
        "for name in sys.argv[1:]:\n"
        "    t = pathlib.Path(name).read_text(encoding='utf-8')\n"
        "    bad += sum(1 for c in t if ord(c) > 127)\n"
        "print('residual_non_ascii_count:', bad)\n"
        "sys.exit(1 if bad else 0)\n", encoding="utf-8")
    (workspace / "docs" / "rules.md").write_text(
        "Batch paths only. Use scripts/normalize.py. Verify with "
        "scripts/verify_ascii.py. One commit, no push.\n", encoding="utf-8")
    subprocess.run("git init -q && git config user.email t@example.invalid && "
                   "git config user.name T && git add -A && "
                   "git commit -qm baseline", shell=True, cwd=workspace,
                   check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Tool-enabled role A/B on a temporary workspace.")
    parser.add_argument("--role", default="ops-format-normalizer")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--results-dir", default=None)
    parser.add_argument("--base-url", default="https://api.deepseek.com/v1")
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--executor-model", default="deepseek-flash")
    parser.add_argument("--grader-model", default="deepseek-v4-pro")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--grader-max-tokens", type=int, default=4096)
    parser.add_argument("--max-turns", type=int, default=10)
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    api_key = os.environ.get(args.api_key_env, "").strip()
    if not api_key:
        print("role-tools: %s is empty" % args.api_key_env)
        return 2
    fixture = json.loads((root / "evals" / "role-ab" / "tasks" /
                          ("%s.json" % args.role)).read_text(encoding="utf-8"))
    current = ROLE_AB.fill_slots(
        ROLE_AB.role_path(root, args.role).read_text(encoding="utf-8"))
    candidate = ROLE_AB.fill_slots(
        ROLE_AB.candidate_path(root, args.role).read_text(encoding="utf-8"))
    candidate = candidate.replace("{{PROJECT_NORMALIZER_TOOLING}}",
                                  "python3 scripts/normalize.py")
    current = current.replace("{{PROJECT_NORMALIZER_TOOLING}}",
                              "python3 scripts/normalize.py")

    results = []
    for arm, body in (("current", current), ("candidate", candidate)):
        started = time.monotonic()
        run = run_agent(args.role, body, fixture, args, api_key)
        run["arm"] = arm
        run["duration_s"] = round(time.monotonic() - started, 3)
        results.append(run)
        print("%s %s turns=%d ascii=%s commit=%s"
              % (arm, args.role, run["transcript_turns"],
                 all(v["ascii"] for v in run["files"].values()),
                 bool(run["last_commit"])), flush=True)

    results_dir = Path(args.results_dir).resolve() if args.results_dir \
        else root / "evals" / "results" / ("role-tools-%s" % args.seed)
    results_dir.mkdir(parents=True, exist_ok=True)
    out = results_dir / ("%s.tools-%s.json" % (args.role, args.seed))
    out.write_text(json.dumps({
        "schema": "role-tools/1",
        "run": {"role": args.role, "seed": args.seed,
                "executor_model": args.executor_model,
                "harness": "openai-compatible-tools",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(
                    timespec="seconds")},
        "results": results,
    }, indent=2), encoding="utf-8")
    print("role-tools: -> %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
