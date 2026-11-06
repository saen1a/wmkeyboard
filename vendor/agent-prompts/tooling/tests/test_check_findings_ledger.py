"""Tests for the WL-13 findings ledger checker."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tooling" / "check_findings_ledger.py"
EXAMPLE = ROOT / "exemplars" / "findings-ledger-example.md"


def _run(path, *extra):
    return subprocess.run([sys.executable, str(CHECK), str(path), *extra],
                          cwd=str(ROOT), capture_output=True, text=True)


def _write(tmp_path, text):
    path = tmp_path / "findings.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_example_is_structurally_valid():
    result = _run(EXAMPLE)
    assert result.returncode == 0, result.stdout
    assert "0 violation(s)" in result.stdout


def test_require_clean_fails_open_medium(tmp_path):
    result = _run(EXAMPLE, "--require-clean")
    assert result.returncode == 1
    assert "open medium finding" in result.stdout


def test_duplicate_id_fails(tmp_path):
    text = EXAMPLE.read_text().replace("| F-3 |", "| F-1 |")
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "duplicate finding id" in result.stdout


def test_fixed_without_evidence_fails(tmp_path):
    text = EXAMPLE.read_text().replace(
        "Review R1: stale link; re-review R2 confirms the link resolves",
        "")
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "fixed without evidence" in result.stdout


def test_waived_without_decision_fails(tmp_path):
    text = EXAMPLE.read_text().replace(
        "operator waived; cosmetic", "")
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "waived without an operator decision" in result.stdout


def test_open_finding_without_evidence_fails(tmp_path):
    text = EXAMPLE.read_text().replace(
        "| Review R2: old screen name; no re-review yet |", "|  |")
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "F-2 has empty evidence" in result.stdout


def test_missing_acceptance_impact_fails(tmp_path):
    text = EXAMPLE.read_text().replace("| A3 | rev-reviewer |", "|  | rev-reviewer |")
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "F-2 has empty acceptance_impact" in result.stdout


def test_finding_ids_start_at_one(tmp_path):
    text = EXAMPLE.read_text().replace("| F-3 |", "| F-0 |")
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "F-0 is not a finding id" in result.stdout
