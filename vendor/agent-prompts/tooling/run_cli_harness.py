#!/usr/bin/env python3
"""Run one behavioral eval case on a real agent CLI, in a throwaway directory.

``run_behavioral_evals.py`` talks to a chat endpoint and never executes a tool
call, so the ``execution`` cases -- the ones that must probe a machine and check
a ready condition -- cannot be exercised there. This runner hands the same skill
body and case prompt to a CLI agent that has a shell, a working directory, and
read/write access there, then captures the CLI's final text as the executor
response.

It does NOT grade. Grading is the caller's job: ``graded`` is always false,
``score`` and ``passed`` are null, and every expectation carries ``met: null``
with a reason. A caller feeds ``executor_response`` to the same grader prompt
the HTTP runner uses. A CLI that cannot run (missing binary, timeout, non-zero
exit) is a harness error -- exit 2 with an ``error`` field -- never a score.

Isolation: the CLI runs with its working directory set to a fresh temp
directory, never the repository. ``--fixture NAME`` copies
``evals/fixtures/NAME`` into that directory as a read-only copy (files 0444,
directories 0555, executables 0555), so an execution case has real files to
probe and a real installer to run, while the repository copy and its history
stay untouched. A ``--workdir`` inside the repository is refused outright. If
this harness is itself running inside an omp session, that session's ``PI_*``
variables are stripped from the child's environment so the CLI under test
starts clean instead of resuming the parent.

Presets (probed 2026-11-02, see docs/knowledge-base/cli-harness-spike-2026-11.md):

  omp     prompt on stdin, skill body as the system prompt, answer on stdout,
          progress on stderr. The model is pinned to the mandated route
          (opencode-go/deepseek-v4.1-flash) so a run does not inherit whatever
          the host's config.yml happens to default to. It runs
          with ``--auto-approve`` because a headless run otherwise refuses
          ``bash`` ("requires approval but no interactive UI available"), which
          is exactly the tool an execution case needs.
  kilo    prompt (skill body + case prompt) on stdin, answer on stdout.
  claude  ``-p``; currently fails on this host without a login.
  codex   ``exec``; currently fails on this host without OpenAI credentials.

``--cli`` also accepts a path to any executable; it is run with the prompt on
stdin and the workdir as its cwd. That is how the deterministic tests drive a
fake CLI without a model.

Exit codes: 0 the CLI ran and printed an answer (ungraded); 2 harness error
(unknown CLI, unreadable case or fixture, timeout, non-zero exit).

Usage:
    python3 tooling/run_cli_harness.py --cli omp \\
        --case evals/behavioral/operator-setup-interview.json \\
        --case-id time-execute-before-answers --json
"""

import argparse
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTMATTER_RE = re.compile(r"(?m)^name:\s*(\S+)\s*$")
STDERR_TAIL = 2000
SKILL_PLACEHOLDER = "<skill-body>"

# How each probed CLI takes a prompt and where its final answer appears.
# ``system_prompt`` is True when the CLI can carry the skill body out of band;
# otherwise the body is prepended to the prompt text.
PRESETS = {
    "omp": {
        "argv": lambda workdir, skill_text: [
            "omp", "-p", "--model", "opencode-go/deepseek-v4.1-flash",
            "--cwd", str(workdir), "--no-session", "--mode", "text",
            "--auto-approve", "--no-rules", "--no-context-files", "--no-skills",
            "--no-extensions", "--system-prompt", skill_text,
        ],
        "system_prompt": True,
    },
    "kilo": {
        "argv": lambda workdir, skill_text: [
            "kilo", "run", "--auto", "--model", "opencode-go/deepseek-v4.1-flash",
        ],
        "system_prompt": False,
    },
    "claude": {
        "argv": lambda workdir, skill_text: [
            "claude", "-p", "--output-format", "text",
            "--dangerously-skip-permissions", "--system-prompt", skill_text,
        ],
        "system_prompt": True,
    },
    "codex": {
        "argv": lambda workdir, skill_text: [
            "codex", "exec", "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox", "-C", str(workdir),
        ],
        "system_prompt": False,
    },
}


# The agent running this harness may itself be an omp session. Its session
# plumbing must not leak into the CLI under test, or the child could resume or
# pollute the parent's session instead of starting a clean one.
PARENT_SESSION_VARS = ("PI_SESSION_FILE", "PI_SESSION_ID", "PI_TOOL_CALL_ID",
                       "PI_NOTIFICATIONS")


class HarnessError(Exception):
    """A failure of the harness or the CLI, never a graded outcome."""


def load_skills(skills_dir):
    """Map skill name -> SKILL.md text, as the HTTP runner does."""
    skills = {}
    for path in sorted(Path(skills_dir).glob("**/SKILL.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        match = FRONTMATTER_RE.search(text)
        name = match.group(1) if match else path.parent.name
        skills.setdefault(name, text)
    return skills


def load_case(path, case_id=None):
    """Return ``(skill_name, case)`` from a behavioral case file.

    A case file holds one or more ``evals``; ``case_id`` selects one. A file
    with exactly one eval needs no ``case_id``, and a file with several must
    name one -- guessing would silently run the wrong case.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HarnessError("cannot read case file %s: %s" % (path, exc))
    if not isinstance(data, dict) or not isinstance(data.get("skill"), str):
        raise HarnessError("%s is not a behavioral case file" % path)
    evals = data.get("evals")
    if not isinstance(evals, list) or not evals:
        raise HarnessError("%s has no evals" % path)
    if case_id is None:
        if len(evals) != 1:
            ids = ", ".join(str(entry.get("id")) for entry in evals
                            if isinstance(entry, dict))
            raise HarnessError("%s holds %d evals; pick one with --case-id (%s)"
                               % (path, len(evals), ids))
        case = evals[0]
    else:
        matches = [entry for entry in evals
                   if isinstance(entry, dict) and entry.get("id") == case_id]
        if not matches:
            raise HarnessError("%s has no case id %r" % (path, case_id))
        case = matches[0]
    if not isinstance(case, dict) or not isinstance(case.get("prompt"), str):
        raise HarnessError("case %r has no prompt" % (case.get("id"),))
    return data["skill"], case


def resolve_cli(name):
    """Return the preset for ``name``, or a preset that runs an executable path."""
    preset = PRESETS.get(name)
    if preset is not None:
        return name, preset
    path = Path(name).expanduser()
    if path.is_file() and os.access(str(path), os.X_OK):
        return name, {
            "argv": lambda workdir, skill_text: [str(path.resolve())],
            "system_prompt": False,
        }
    raise HarnessError("unknown CLI %r: use one of %s or a path to an "
                       "executable" % (name, ", ".join(sorted(PRESETS))))


def guard_workdir(workdir):
    """Refuse a working directory inside the repository."""
    resolved = Path(workdir).resolve()
    root = ROOT.resolve()
    if resolved == root or root in resolved.parents:
        raise HarnessError("workdir must be outside the repository, got %s"
                           % resolved)
    return resolved


def prepare_workdir(workdir, fixture_dir=None):
    """Create the workdir and copy the fixture into it as a read-only copy."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    if any(workdir.iterdir()):
        raise HarnessError("workdir is not empty: %s" % workdir)
    if fixture_dir is None:
        return
    for entry in sorted(Path(fixture_dir).iterdir()):
        target = workdir / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target)
        else:
            shutil.copy2(entry, target)
    make_read_only(workdir)


def make_read_only(root):
    """Make every fixture copy read-only, keeping the exec bit on scripts."""
    root = Path(root)
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            path = Path(dirpath) / filename
            mode = path.stat().st_mode
            executable = mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            path.chmod(0o555 if executable else 0o444)
    for dirpath, dirnames, _filenames in os.walk(root, topdown=False):
        for dirname in dirnames:
            (Path(dirpath) / dirname).chmod(0o555)


def restore_writable(root):
    """Undo :func:`make_read_only` so the temp directory can be removed."""
    root = Path(root)
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames:
            try:
                (Path(dirpath) / name).chmod(0o644)
            except OSError:
                pass
        for name in dirnames:
            try:
                (Path(dirpath) / name).chmod(0o755)
            except OSError:
                pass
    try:
        root.chmod(0o755)
    except OSError:
        pass


def child_env(env=None):
    """Environment for the CLI with the parent agent's session vars removed."""
    child = dict(os.environ if env is None else env)
    for name in PARENT_SESSION_VARS:
        child.pop(name, None)
    return child


def build_prompt(skill_text, case_prompt, preset):
    """Skill body plus case prompt, in the place the CLI can carry it."""
    if preset["system_prompt"]:
        return case_prompt
    return ("Skill procedure to apply for this request:\n\n%s\n\n---\n\n%s"
            % (skill_text.strip(), case_prompt))


def run_cli(argv, workdir, prompt, timeout):
    """Run the CLI; return ``(stdout, stderr, exit_code, timed_out, seconds)``.

    The child gets its own process group so a timeout kills the whole tree, not
    just the wrapper that spawned the agent.
    """
    started = time.monotonic()
    try:
        proc = subprocess.Popen(
            argv, cwd=str(workdir), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            start_new_session=True, env=child_env())
    except OSError as exc:
        raise HarnessError("cannot start %r: %s" % (argv[0], exc))
    timed_out = False
    try:
        stdout, stderr = proc.communicate(prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()
        stdout, stderr = proc.communicate()
    duration = time.monotonic() - started
    return stdout or "", stderr or "", proc.returncode, timed_out, duration


def display_command(argv, skill_text):
    """The command line with the skill body redacted (it is already on disk)."""
    return [SKILL_PLACEHOLDER if skill_text and arg == skill_text else arg
            for arg in argv]


def build_record(skill, case, cli_name, workdir, fixture, timeout):
    """An ungraded result record shaped like the HTTP runner's result."""
    return {
        "id": case["id"],
        "kind": case.get("kind", "execution"),
        "pressure": case.get("pressure"),
        "skill": skill,
        "mode": "cli",
        "graded": False,
        "cli": cli_name,
        "fixture": fixture,
        "workdir": str(workdir),
        "timeout_s": timeout,
        "command": None,
        "exit_code": None,
        "timed_out": False,
        "duration_s": None,
        "stderr_tail": "",
        "executor_response": "",
        "score": None,
        "passed": None,
        "expectations": [
            {
                "expectation": expectation,
                "met": None,
                "reason": "not graded: the caller grades executor_response",
            }
            for expectation in case.get("expectations", [])
        ],
    }


def run(args):
    """Execute one case and return ``(record, exit_code)``."""
    skills = load_skills(ROOT / "skills")
    skill, case = load_case(args.case, args.case_id)
    if not args.no_skill and skill not in skills:
        raise HarnessError("no SKILL.md for skill %r under %s"
                           % (skill, ROOT / "skills"))
    skill_text = "" if args.no_skill else skills[skill]

    cli_name, preset = resolve_cli(args.cli)

    fixture = args.fixture
    if fixture is None and case.get("files"):
        fixture = case["files"][0]
    fixture_dir = None
    if fixture is not None:
        fixture_dir = ROOT / "evals" / "fixtures" / fixture
        if not fixture_dir.is_dir():
            raise HarnessError("no fixture %r under %s"
                               % (fixture, ROOT / "evals" / "fixtures"))

    created = args.workdir is None
    workdir = Path(tempfile.mkdtemp(prefix="cli-harness-")) if created \
        else guard_workdir(args.workdir)
    record = build_record(skill, case, cli_name, workdir, fixture, args.timeout)
    try:
        prepare_workdir(workdir, fixture_dir)
        argv = preset["argv"](workdir, skill_text)
        prompt = build_prompt(skill_text, case["prompt"], preset)
        record["command"] = display_command(argv, skill_text)
        stdout, stderr, code, timed_out, duration = run_cli(
            argv, workdir, prompt, args.timeout)
        record.update({
            "exit_code": code,
            "timed_out": timed_out,
            "duration_s": round(duration, 3),
            "stderr_tail": stderr[-STDERR_TAIL:],
        })
        if timed_out:
            record["error"] = "cli timed out after %ss" % args.timeout
            return record, 2
        if code != 0:
            record["error"] = "cli exited %s" % code
            return record, 2
        record["executor_response"] = stdout.strip()
        if not record["executor_response"]:
            record["error"] = "cli exited 0 but printed no answer to stdout"
            return record, 2
        return record, 0
    finally:
        if created:
            restore_writable(workdir)
            shutil.rmtree(workdir, ignore_errors=True)


def render_human(record):
    """Readable summary; the JSON is the machine-readable artifact."""
    lines = ["cli-harness: %s / %s (%s)" % (record["cli"], record["id"],
                                            record["skill"]),
             "  mode: cli, graded: false",
             "  workdir: %s" % record["workdir"],
             "  fixture: %s" % (record["fixture"] or "none"),
             "  command: %s" % " ".join(record["command"] or []),
             "  exit: %s timed_out=%s duration=%ss"
             % (record["exit_code"], record["timed_out"], record["duration_s"])]
    if record.get("error"):
        lines.append("  ERROR: %s" % record["error"])
    response = record["executor_response"]
    lines.append("  executor response (%d chars):" % len(response))
    lines.extend("    " + line for line in response.splitlines() or [""])
    for entry in record["expectations"]:
        lines.append("  expectation: %s -> not graded" % entry["expectation"])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run one behavioral case on a CLI agent harness "
                    "(ungraded: see the docstring).")
    parser.add_argument("--cli", default="omp",
                        help="preset name (%s) or a path to an executable "
                             "(default: omp)" % ", ".join(sorted(PRESETS)))
    parser.add_argument("--case", required=True,
                        help="a case json file from evals/behavioral/")
    parser.add_argument("--case-id", default=None,
                        help="eval id inside the case file; required when the "
                             "file holds more than one")
    parser.add_argument("--workdir", default=None,
                        help="directory to run in; default a fresh temp dir "
                             "that is removed afterwards")
    parser.add_argument("--timeout", type=float, default=600,
                        help="wall-clock seconds before the CLI is killed "
                             "(default: 600)")
    parser.add_argument("--no-skill", action="store_true",
                        help="omit the skill body: the paired no-skill baseline arm")
    parser.add_argument("--fixture", default=None,
                        help="fixture name under evals/fixtures/ to copy in "
                             "read-only; default the case's first files entry")
    parser.add_argument("--json", action="store_true",
                        help="print the ungraded result record as JSON")
    args = parser.parse_args(argv)
    try:
        record, code = run(args)
    except HarnessError as exc:
        if args.json:
            print(json.dumps({"graded": False, "mode": "cli",
                              "score": None, "passed": None,
                              "error": str(exc)}, indent=2))
        else:
            print("cli-harness: %s" % exc, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(record, indent=2))
    else:
        print(render_human(record))
    return code


if __name__ == "__main__":
    sys.exit(main())
