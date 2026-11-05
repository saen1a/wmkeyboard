"""Tests for the WP-08 optimization proposal ledger and its schema."""

import json
import subprocess
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tooling" / "check_optimization_ledger.py"
LEDGER = ROOT / "evals" / "optimization" / "proposals.md"
SCHEMA = ROOT / "evals" / "optimization" / "proposals.schema.json"
EXAMPLE = ROOT / "evals" / "optimization" / "proposal-example.json"


def _run(path):
    return subprocess.run([sys.executable, str(CHECK), str(path)],
                          cwd=str(ROOT), capture_output=True, text=True)


def _write(tmp_path, text):
    path = tmp_path / "proposals.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_committed_ledger_is_valid():
    result = _run(LEDGER)
    assert result.returncode == 0, result.stdout
    assert "0 violation(s)" in result.stdout


def test_example_matches_schema():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    record = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    jsonschema.validate(record, schema)


def test_example_cases_exist_in_the_failure_set():
    record = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    text = (ROOT / "evals" / "optimization" / "failure-set.md").read_text(
        encoding="utf-8")
    for case in record["source_cases"]:
        assert ("| %s |" % case) in text


def test_accepted_requires_approved_gate(tmp_path):
    text = LEDGER.read_text(encoding="utf-8").replace(
        "| pending | rejected |", "| pending | accepted |")
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "accepted without an approved human gate" in result.stdout


def test_rejected_requires_paired_result(tmp_path):
    text = LEDGER.read_text(encoding="utf-8").replace(
        "A=0.6667; B=0.5000 | A=0.6667; B=0.5000 | A=1/1/1; B=0/3/0",
        "not-run | not-run | not-run")
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "rejected without a paired result" in result.stdout


def test_unknown_source_case_fails(tmp_path):
    text = LEDGER.read_text(encoding="utf-8").replace(
        "| FC-25, FC-26 |", "| FC-25, FC-99 |", 1)
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "absent from the failure set" in result.stdout


def test_missing_evidence_path_fails(tmp_path):
    text = LEDGER.read_text(encoding="utf-8").replace(
        "evals/optimization/results/p1-config-a.json",
        "evals/optimization/results/missing.json", 1)
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "evidence path does not exist" in result.stdout


def test_duplicate_proposal_id_fails(tmp_path):
    text = LEDGER.read_text(encoding="utf-8").replace("| P-2 |", "| P-1 |")
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "duplicate proposal id" in result.stdout


def test_missing_arm_fails(tmp_path):
    text = LEDGER.read_text(encoding="utf-8").replace(
        "evals/optimization/arms/exec-plan-evidence-v1", "evals/optimization/arms/nope", 1)
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "arm does not exist" in result.stdout


def test_cost_must_be_numeric_or_unrecorded(tmp_path):
    text = LEDGER.read_text(encoding="utf-8").replace(
        "A=0.004079; B=0.003172", "cheap")
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "cost_usd" in result.stdout


def test_configuration_keys_must_align(tmp_path):
    text = LEDGER.read_text(encoding="utf-8").replace(
        "| A=0.6667; B=0.5000 | A=0.6667; B=0.5000 |",
        "| A=0.6667; B=0.5000 | A=0.6667; C=0.5000 |")
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "name different configurations" in result.stdout
