"""Tests for the role A/B summary: cost and latency beside the pass rate."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUMMARIZE = ROOT / "tooling" / "summarize_role_ab.py"


def _result(arm, score, cost, duration, prompt, completion,
            role="ops-executor", task=None):
    return {
        "role": role,
        "task": task,
        "arm": arm,
        "passed": score == 1.0,
        "score": score,
        "truncated": False,
        "executor_usage": {"prompt_tokens": prompt,
                           "completion_tokens": completion,
                           "cost": cost,
                           "finish_reason": "stop"},
        "grader_usage": {"cost": cost / 2},
        "duration_s": duration,
        "expectations": [{"expectation": "Names the evidence", "met": score == 1.0}],
        "response": "x",
    }


def _seed(tmp_path, seed, current, candidate):
    directory = tmp_path / ("run-%d" % seed)
    directory.mkdir()
    payload = {
        "schema": "role-ab/2",
        "run": {"seed": seed, "executor_model": "exec", "grader_model": "grade",
                "harness": "openai-compatible-chat", "max_tokens": 4096,
                "temperature": 0},
        "arms": {"current": {"sha256": "a", "chars": 1},
                 "candidate": {"sha256": "b", "chars": 2}},
        "results": [current, candidate],
    }
    (directory / ("ops-executor.role-ab-%d.json" % seed)).write_text(
        json.dumps(payload), encoding="utf-8")
    return str(directory)


def test_usage_carries_cost_and_latency(tmp_path):
    first = _seed(tmp_path, 1, _result("current", 1.0, 0.002, 4.0, 100, 20),
                  _result("candidate", 0.5, 0.004, 6.0, 110, 30))
    second = _seed(tmp_path, 2, _result("current", 0.5, 0.001, 2.0, 100, 10),
                   _result("candidate", 0.5, 0.002, 8.0, 120, 40))
    output = tmp_path / "summary.json"
    result = subprocess.run(
        [sys.executable, str(SUMMARIZE), "--results-dir", first,
         "--results-dir", second, "--output", str(output),
         "--experiment", "unit"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    manifest = json.loads(output.read_text(encoding="utf-8"))
    candidate = manifest["usage"]["candidate"]
    assert candidate["runs"] == 2
    assert candidate["input_tokens_total"] == 230
    assert candidate["output_tokens_total"] == 70
    assert candidate["cost_recorded_runs"] == 2
    assert candidate["cost_usd_total"] == 0.009
    assert candidate["latency_s_mean"] == 7.0


def _task_seed(tmp_path, seed, rows):
    """One result file per task, as a multi-task role run writes them."""
    directory = tmp_path / ("run-%d" % seed)
    directory.mkdir()
    for task, (current, candidate) in rows.items():
        payload = {
            "schema": "role-ab/2",
            "run": {"seed": seed, "executor_model": "exec", "grader_model": "grade",
                    "harness": "openai-compatible-chat", "max_tokens": 4096,
                    "temperature": 0},
            "arms": {"current": {"sha256": "a", "chars": 1},
                     "candidate": {"sha256": "b", "chars": 2}},
            "results": [current, candidate],
        }
        (directory / ("ops-executor.%s.role-ab-%d.json" % (task, seed))).write_text(
            json.dumps(payload), encoding="utf-8")
    return str(directory)


def test_tasks_of_one_role_are_summarized_separately(tmp_path):
    rows = {
        "01-a": (_result("current", 1.0, 0.001, 1.0, 10, 1, task="01-a"),
                 _result("candidate", 0.5, 0.002, 2.0, 20, 2, task="01-a")),
        "02-b": (_result("current", 0.5, 0.001, 1.0, 10, 1, task="02-b"),
                 _result("candidate", 0.5, 0.002, 2.0, 20, 2, task="02-b")),
    }
    first = _task_seed(tmp_path, 1, rows)
    second = _task_seed(tmp_path, 2, rows)
    output = tmp_path / "summary.json"
    result = subprocess.run(
        [sys.executable, str(SUMMARIZE), "--results-dir", first,
         "--results-dir", second, "--output", str(output),
         "--experiment", "unit"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert sorted(manifest["per_role"]) == ["ops-executor/01-a", "ops-executor/02-b"]
    assert manifest["protocol"]["tasks_per_role"] == "many"
    assert manifest["per_role"]["ops-executor/01-a"]["current"]["mean"] == 1.0
    assert manifest["per_role"]["ops-executor/01-a"]["candidate"]["mean"] == 0.5
    assert manifest["per_role"]["ops-executor/02-b"]["current"]["mean"] == 0.5
    assert manifest["overall_all"]["pairs"] == 4
    assert manifest["usage"]["candidate"]["runs"] == 4


def test_cost_is_null_when_the_harness_reports_none(tmp_path):
    current = _result("current", 1.0, 0.002, 4.0, 100, 20)
    candidate = _result("candidate", 1.0, 0.002, 4.0, 100, 20)
    for entry in (current, candidate):
        entry["executor_usage"].pop("cost")
        entry["grader_usage"].pop("cost")
    directory = _seed(tmp_path, 1, current, candidate)
    output = tmp_path / "summary.json"
    result = subprocess.run(
        [sys.executable, str(SUMMARIZE), "--results-dir", directory,
         "--output", str(output), "--experiment", "unit"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    usage = json.loads(output.read_text(encoding="utf-8"))["usage"]["current"]
    assert usage["cost_usd_total"] is None
    assert usage["cost_recorded_runs"] == 0


def test_opencode_list_cost_is_recorded_beside_a_zero_gateway_cost(tmp_path):
    current = _result("current", 1.0, 0.0, 4.0, 100, 20)
    candidate = _result("candidate", 1.0, 0.0, 4.0, 100, 20)
    for entry in (current, candidate):
        entry["executor_usage"]["opencode"] = {"list_cost": 0.0001}
        entry["grader_usage"]["opencode"] = {"list_cost": 0.00005}
    directory = _seed(tmp_path, 1, current, candidate)
    output = tmp_path / "summary.json"
    result = subprocess.run(
        [sys.executable, str(SUMMARIZE), "--results-dir", directory,
         "--output", str(output), "--experiment", "unit"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    usage = json.loads(output.read_text(encoding="utf-8"))["usage"]["current"]
    assert usage["cost_usd_total"] == 0.0
    assert usage["cost_recorded_runs"] == 1
    assert usage["list_cost_usd_total"] == 0.00015
    assert usage["list_cost_recorded_runs"] == 1


def test_request_headers_are_carried_into_the_protocol(tmp_path):
    current = _result("current", 1.0, 0.0, 4.0, 100, 20)
    candidate = _result("candidate", 1.0, 0.0, 4.0, 100, 20)
    directory = _seed(tmp_path, 1, current, candidate)
    path = Path(directory) / "ops-executor.role-ab-1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["run"]["request_headers"] = ["x-opencode-session"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "summary.json"
    result = subprocess.run(
        [sys.executable, str(SUMMARIZE), "--results-dir", directory,
         "--output", str(output), "--experiment", "unit"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["protocol"]["request_headers"] == ["x-opencode-session"]


def test_tallies_are_keyed_to_the_fixture_when_the_grader_paraphrases(tmp_path):
    rows = {
        "01-a": (_result("current", 1.0, 0.0, 1.0, 10, 1, task="01-a"),
                 _result("candidate", 1.0, 0.0, 1.0, 10, 1, task="01-a")),
    }
    for pair in rows.values():
        for entry in pair:
            entry["expectations"] = [
                {"expectation": "Does not accept the done", "met": True}]
    directory = _task_seed(tmp_path, 1, rows)
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "01-a.json").write_text(json.dumps({
        "role": "ops-executor", "prompt": "P",
        "expectations": ["Does not accept the done claim as verified"]}),
        encoding="utf-8")
    output = tmp_path / "summary.json"
    result = subprocess.run(
        [sys.executable, str(SUMMARIZE), "--results-dir", directory,
         "--output", str(output), "--experiment", "unit",
         "--tasks-dir", str(tasks)],
        cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["protocol"]["expectation_keys"] == "fixture"
    tallies = manifest["expectations"]["current"]["by_expectation"]
    assert list(tallies) == ["Does not accept the done claim as verified"]
    assert tallies["Does not accept the done claim as verified"]["met"] == 1


def _truncated(entry):
    entry["truncated"] = True
    entry["executor_usage"]["finish_reason"] = "length"
    return entry


def _summarize(directories, tmp_path):
    output = tmp_path / "summary.json"
    args = [sys.executable, str(SUMMARIZE)]
    for directory in directories:
        args += ["--results-dir", directory]
    result = subprocess.run(
        args + ["--output", str(output), "--experiment", "unit"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    return json.loads(output.read_text(encoding="utf-8"))


def test_truncation_is_counted_per_arm_and_sums_to_the_pair_list(tmp_path):
    first = _task_seed(tmp_path, 1, {
        "01-a": (_truncated(_result("current", 1.0, 0.0, 1.0, 10, 1, task="01-a")),
                 _result("candidate", 1.0, 0.0, 1.0, 10, 1, task="01-a")),
        "02-b": (_result("current", 1.0, 0.0, 1.0, 10, 1, task="02-b"),
                 _result("candidate", 1.0, 0.0, 1.0, 10, 1, task="02-b")),
    })
    second = _task_seed(tmp_path, 2, {
        "01-a": (_result("current", 1.0, 0.0, 1.0, 10, 1, task="01-a"),
                 _truncated(_result("candidate", 1.0, 0.0, 1.0, 10, 1, task="01-a"))),
        "02-b": (_result("current", 1.0, 0.0, 1.0, 10, 1, task="02-b"),
                 _result("candidate", 1.0, 0.0, 1.0, 10, 1, task="02-b")),
    })
    manifest = _summarize([first, second], tmp_path)
    assert manifest["truncated_by_arm"] == {"current": 1, "candidate": 1}
    assert len(manifest["truncated_pairs"]) == 2
    assert (manifest["truncated_by_arm"]["current"]
            + manifest["truncated_by_arm"]["candidate"]) == len(
                manifest["truncated_pairs"])
    # Each entry names its own arm, so the split is readable without raw runs.
    assert manifest["truncated_pairs"] == [
        {"role": "ops-executor/01-a", "seed": 1, "arms": ["current"]},
        {"role": "ops-executor/01-a", "seed": 2, "arms": ["candidate"]},
    ]


def test_a_pair_truncated_in_both_arms_is_listed_once_and_counted_twice(tmp_path):
    directory = _task_seed(tmp_path, 1, {
        "01-a": (_truncated(_result("current", 1.0, 0.0, 1.0, 10, 1, task="01-a")),
                 _truncated(_result("candidate", 1.0, 0.0, 1.0, 10, 1, task="01-a"))),
    })
    manifest = _summarize([directory], tmp_path)
    assert len(manifest["truncated_pairs"]) == 1
    assert manifest["truncated_pairs"][0]["arms"] == ["current", "candidate"]
    assert manifest["truncated_by_arm"] == {"current": 1, "candidate": 1}
