#!/usr/bin/env python3
"""Deterministic tests for run_cli_harness.py -- no model, no network.

A fake CLI (a shell script under ``tmp_path``) stands in for the agent, so the
harness contract is proved without a model: the fixture copy is isolated and
read-only, the timeout and a non-zero exit are harness errors, and the JSON
record keeps the HTTP runner's shape while reporting ``graded: false``.
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

TOOLING = Path(__file__).resolve().parent.parent
ROOT = TOOLING.parent
RUNNER = TOOLING / "run_cli_harness.py"
FIXTURE = "operator-setup-interview"

spec = importlib.util.spec_from_file_location("run_cli_harness", RUNNER)
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


def write_script(path, body):
    path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def case_file(tmp_path, *evals, skill="operator-setup-interview"):
    path = tmp_path / "case.json"
    path.write_text(json.dumps({"skill": skill, "evals": list(evals)}),
                    encoding="utf-8")
    return path


def case(**overrides):
    data = {
        "id": "fake-exec",
        "kind": "execution",
        "pressure": "time",
        "prompt": "Do the thing now.",
        "expectations": ["first expectation", "second expectation"],
        "files": [FIXTURE],
    }
    data.update(overrides)
    return data


def invoke(cli, case_path, workdir, *extra):
    return subprocess.run(
        [sys.executable, str(RUNNER), "--cli", str(cli),
         "--case", str(case_path), "--workdir", str(workdir), "--json"]
        + list(extra),
        capture_output=True, text=True, timeout=120)


def load_json(result):
    return json.loads(result.stdout)


def tree_hash(root):
    digest = hashlib.sha256()
    for path in sorted(Path(root).rglob("*")):
        digest.update(path.relative_to(root).as_posix().encode())
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_json_record_has_http_runner_shape_but_is_ungraded(tmp_path):
    fake = write_script(tmp_path / "fake_ok.sh",
                        'cat >/dev/null\necho "probe first, then answer"\n')
    work = tmp_path / "work"
    result = invoke(fake, case_file(tmp_path, case()), work, "--fixture", FIXTURE)

    assert result.returncode == 0, result.stderr
    record = load_json(result)
    assert record["id"] == "fake-exec"
    assert record["kind"] == "execution"
    assert record["mode"] == "cli"
    assert record["graded"] is False
    assert record["score"] is None
    assert record["passed"] is None
    assert record["exit_code"] == 0
    assert record["timed_out"] is False
    assert record["executor_response"] == "probe first, then answer"
    assert [entry["expectation"] for entry in record["expectations"]] == [
        "first expectation", "second expectation"]
    assert all(entry["met"] is None for entry in record["expectations"])
    assert all("not graded" in entry["reason"]
               for entry in record["expectations"])
    assert record["duration_s"] is not None


def test_fixture_copy_is_read_only_and_leaves_the_repo_untouched(tmp_path):
    source = ROOT / "evals" / "fixtures" / FIXTURE
    before = tree_hash(source)
    fake = write_script(
        tmp_path / "fake_probe.sh",
        'cat >/dev/null\n'
        'pwd\n'
        'test -r host.txt && echo HOST_READABLE\n'
        'if echo probe >> host.txt 2>/dev/null; then echo FIXTURE_WRITABLE; '
        'else echo FIXTURE_READ_ONLY; fi\n')
    work = tmp_path / "work"
    result = invoke(fake, case_file(tmp_path, case()), work, "--fixture", FIXTURE)

    assert result.returncode == 0, result.stderr
    response = load_json(result)["executor_response"]
    assert str(work) in response
    assert str(ROOT) not in response
    assert "HOST_READABLE" in response
    assert "FIXTURE_READ_ONLY" in response
    assert tree_hash(source) == before
    assert (work / "host.txt").stat().st_mode & 0o222 == 0
    assert (work / "check.sh").stat().st_mode & 0o222 == 0
    assert (work / "host.txt").read_text() == (source / "host.txt").read_text()


def test_timeout_is_a_harness_error_not_a_score(tmp_path):
    fake = write_script(tmp_path / "fake_slow.sh",
                        'cat >/dev/null\nsleep 30\necho late\n')
    started = time.monotonic()
    result = invoke(fake, case_file(tmp_path, case()), tmp_path / "work",
                    "--timeout", "1")
    elapsed = time.monotonic() - started

    assert result.returncode == 2, result.stderr
    record = load_json(result)
    assert record["timed_out"] is True
    assert "timed out" in record["error"]
    assert record["score"] is None and record["passed"] is None
    assert record["graded"] is False
    assert elapsed < 20


def test_nonzero_exit_is_a_harness_error_not_a_score(tmp_path):
    fake = write_script(tmp_path / "fake_fail.sh",
                        'cat >/dev/null\necho "boom" >&2\nexit 7\n')
    result = invoke(fake, case_file(tmp_path, case()), tmp_path / "work")

    assert result.returncode == 2, result.stderr
    record = load_json(result)
    assert record["exit_code"] == 7
    assert "cli exited 7" in record["error"]
    assert record["score"] is None and record["passed"] is None
    assert record["executor_response"] == ""
    assert "boom" in record["stderr_tail"]


def test_empty_answer_is_a_harness_error(tmp_path):
    fake = write_script(tmp_path / "fake_silent.sh", 'cat >/dev/null\n')
    result = invoke(fake, case_file(tmp_path, case()), tmp_path / "work")

    assert result.returncode == 2, result.stderr
    record = load_json(result)
    assert "no answer" in record["error"]
    assert record["score"] is None


def test_unknown_cli_is_refused(tmp_path):
    result = invoke("not-a-real-cli", case_file(tmp_path, case()),
                    tmp_path / "work")

    assert result.returncode == 2
    record = load_json(result)
    assert "unknown CLI" in record["error"]
    assert record["graded"] is False


def test_workdir_inside_the_repository_is_refused(tmp_path):
    result = invoke("omp", case_file(tmp_path, case()), ROOT / "tooling")

    assert result.returncode == 2
    assert "outside the repository" in load_json(result)["error"]


def test_ambiguous_case_file_requires_case_id(tmp_path):
    path = case_file(tmp_path, case(id="one"), case(id="two"))
    result = invoke("omp", path, tmp_path / "work")

    assert result.returncode == 2
    error = load_json(result)["error"]
    assert "--case-id" in error
    assert "one" in error and "two" in error


def test_case_id_selects_the_eval(tmp_path):
    fake = write_script(tmp_path / "fake_ok.sh", 'cat >/dev/null\necho ok\n')
    path = case_file(
        tmp_path,
        case(id="first", prompt="first prompt", expectations=["e1"]),
        case(id="second", prompt="second prompt", expectations=["e2", "e3"]))
    result = invoke(fake, path, tmp_path / "work", "--fixture", FIXTURE,
                    "--case-id", "second")

    assert result.returncode == 0, result.stderr
    record = load_json(result)
    assert record["id"] == "second"
    assert len(record["expectations"]) == 2


def test_prompts_carry_skill_body_only_where_the_cli_cannot(tmp_path):
    skill_text = "SKILL BODY"
    omp = harness.PRESETS["omp"]
    kilo = harness.PRESETS["kilo"]
    assert omp["system_prompt"] is True
    assert kilo["system_prompt"] is False
    assert harness.build_prompt(skill_text, "CASE PROMPT", omp) == "CASE PROMPT"
    inline = harness.build_prompt(skill_text, "CASE PROMPT", kilo)
    assert "SKILL BODY" in inline and "CASE PROMPT" in inline


def test_presets_cover_the_four_probed_clis(tmp_path):
    assert set(harness.PRESETS) == {"omp", "claude", "codex", "kilo"}
    omp_argv = harness.PRESETS["omp"]["argv"](tmp_path, "SKILL")
    assert omp_argv[0] == "omp"
    assert "--cwd" in omp_argv and "--no-session" in omp_argv
    assert "--auto-approve" in omp_argv
    assert "opencode-go/deepseek-v4.1-flash" in omp_argv
    assert "--system-prompt" in omp_argv
    assert omp_argv[-1] == "SKILL"
    kilo_argv = harness.PRESETS["kilo"]["argv"](tmp_path, "SKILL")
    assert "opencode-go/deepseek-v4.1-flash" in kilo_argv
    for name in harness.PRESETS:
        assert harness.PRESETS[name]["argv"](tmp_path, "SKILL")


def test_executable_path_is_accepted_as_a_cli(tmp_path):
    fake = write_script(tmp_path / "fake_ok.sh", 'cat >/dev/null\necho ok\n')
    name, preset = harness.resolve_cli(str(fake))
    assert name == str(fake)
    assert preset["argv"](tmp_path, "SKILL") == [str(fake.resolve())]
    assert preset["system_prompt"] is False
    with pytest.raises(harness.HarnessError):
        harness.resolve_cli(str(tmp_path / "missing.sh"))


def test_child_env_drops_parent_session_vars():
    source = {"PI_SESSION_ID": "parent", "PI_SESSION_FILE": "/tmp/s",
              "PI_TOOL_CALL_ID": "t", "PI_NOTIFICATIONS": "1",
              "OPENCODE_API_KEY": "k", "PATH": "/bin"}
    child = harness.child_env(source)
    for name in harness.PARENT_SESSION_VARS:
        assert name not in child
    assert child["OPENCODE_API_KEY"] == "k"
    assert child["PATH"] == "/bin"


def test_read_only_copy_keeps_scripts_executable_and_cleanup_works(tmp_path):
    target = tmp_path / "copy"
    target.mkdir()
    (target / "install.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (target / "install.sh").chmod(0o755)
    (target / "host.txt").write_text("k=v\n", encoding="utf-8")
    harness.make_read_only(target)
    assert (target / "install.sh").stat().st_mode & 0o111
    assert (target / "host.txt").stat().st_mode & 0o222 == 0
    harness.restore_writable(target)
    (target / "host.txt").unlink()
    (target / "install.sh").unlink()
    os.rmdir(target)
    assert not target.exists()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
