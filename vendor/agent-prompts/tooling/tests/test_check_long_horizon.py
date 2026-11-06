"""Mutation tests for the long-horizon library gate."""

import shutil
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tooling" / "check_long_horizon.py"
COPY = ("standards", "agents", "prompts", "exemplars", "evals", "docs", "skills",
        "tooling", "provenance")


def _copy_tree(tmp_path):
    for name in COPY:
        shutil.copytree(ROOT / name, tmp_path / name)
    shutil.copy2(ROOT / "CATALOG.md", tmp_path / "CATALOG.md")
    return tmp_path / "tooling" / "check_long_horizon.py"


def _run(check, tmp_path):
    return subprocess.run([sys.executable, str(check)], cwd=str(tmp_path),
                          capture_output=True, text=True)


def test_gate_passes_on_repo():
    result = subprocess.run([sys.executable, str(CHECK)], cwd=str(ROOT),
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    assert "0 violations" in result.stdout


def test_missing_rule_heading_fails(tmp_path):
    check = _copy_tree(tmp_path)
    standard = tmp_path / "standards" / "long-horizon-runs.md"
    standard.write_text(standard.read_text().replace("## LH-07 -- ", "## LH-07x -- "))
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "LH-07" in result.stdout


def test_schema_version_drift_fails(tmp_path):
    check = _copy_tree(tmp_path)
    schema = tmp_path / "standards" / "run-state.schema.json"
    schema.write_text(schema.read_text().replace('"version": "1.2.0"', '"version": "9.9.9"'))
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "schema version" in result.stdout or "Long-horizon" in result.stdout


def test_missing_evidence_id_fails(tmp_path):
    check = _copy_tree(tmp_path)
    evidence = tmp_path / "standards" / "evidence" / "long-horizon-2026-10.md"
    lines = [line for line in evidence.read_text().splitlines()
             if not line.startswith("| L4 |")]
    evidence.write_text("\n".join(lines) + "\n")
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "L4" in result.stdout


def test_orchestrator_duty_fails(tmp_path):
    check = _copy_tree(tmp_path)
    orchestrator = tmp_path / "agents" / "orchestration" / "orch-orchestrator.md"
    orchestrator.write_text(orchestrator.read_text().replace(
        "keep the long-horizon run state", "keep a different document"))
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "orchestrator missing" in result.stdout


def test_workflow_cross_reference_fails(tmp_path):
    check = _copy_tree(tmp_path)
    workflow = tmp_path / "standards" / "workflow-loop.md"
    workflow.write_text(workflow.read_text().replace("long-horizon-runs.md", "other.md"))
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "cross-reference" in result.stdout


def test_invalid_exemplar_fails(tmp_path):
    check = _copy_tree(tmp_path)
    exemplar = tmp_path / "exemplars" / "run-state-example.md"
    exemplar.write_text(exemplar.read_text().replace("units_done: 2", "units_done: 1", 1))
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "exemplar" in result.stdout


def test_missing_catalog_pin_fails(tmp_path):
    check = _copy_tree(tmp_path)
    catalog = tmp_path / "CATALOG.md"
    catalog.write_text(catalog.read_text().replace("Long-horizon: 1.2.0",
                                                   "Long-horizon: 9.9.9"))
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "Long-horizon" in result.stdout


def test_missing_kb_link_fails(tmp_path):
    check = _copy_tree(tmp_path)
    kb = tmp_path / "docs" / "knowledge-base" / "long-horizon-agents-2026-10.md"
    kb.write_text(kb.read_text().replace("evidence/long-horizon-2026-10.md", "other.md"))
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "knowledge-base" in result.stdout


def test_missing_skill_fails(tmp_path):
    check = _copy_tree(tmp_path)
    shutil.rmtree(tmp_path / "skills" / "general" / "long-horizon-run")
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "missing required skill" in result.stdout


def test_orchestrator_version_pin_fails(tmp_path):
    check = _copy_tree(tmp_path)
    catalog = tmp_path / "CATALOG.md"
    text = catalog.read_text()
    current = re.search(r"Orchestrator template: (\S+)", text).group(1)
    catalog.write_text(text.replace("Orchestrator template: %s" % current,
                                    "Orchestrator template: 9.9.9"))
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "Orchestrator template" in result.stdout


def test_missing_field_table_row_fails(tmp_path):
    check = _copy_tree(tmp_path)
    standard = tmp_path / "standards" / "long-horizon-runs.md"
    standard.write_text(standard.read_text().replace(
        "| `goal` | One sentence; the run's outcome |", "| goal | One sentence |", 1))
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "goal" in result.stdout


def test_missing_schema_section_fails(tmp_path):
    check = _copy_tree(tmp_path)
    standard = tmp_path / "standards" / "long-horizon-runs.md"
    standard.write_text(standard.read_text().replace("## In-flight", "## Side effects"))
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "In-flight" in result.stdout


def test_missing_ledger_row_fails(tmp_path):
    check = _copy_tree(tmp_path)
    ledger = tmp_path / "provenance" / "ledger-long-horizon-2026-10.md"
    ledger.write_text(ledger.read_text().replace("| long-horizon | Verify |", "| other | Verify |"))
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "no long-horizon row" in result.stdout


def test_schema_enum_narrowing_fails(tmp_path):
    check = _copy_tree(tmp_path)
    schema = tmp_path / "standards" / "run-state.schema.json"
    schema.write_text(schema.read_text().replace('"waiting"', '"waiting_x"'))
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "pinned set" in result.stdout


def test_exercise_state_drift_fails(tmp_path):
    check = _copy_tree(tmp_path)
    state = tmp_path / "evals" / "long-horizon" / "run-state.md"
    state.write_text(state.read_text().replace("units_done: 3", "units_done: 2", 1))
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "exercise:" in result.stdout


def test_exercise_stale_view_fails(tmp_path):
    check = _copy_tree(tmp_path)
    state = tmp_path / "evals" / "long-horizon" / "run-state.md"
    state.write_text(state.read_text().replace(
        "gate U1 pass", "gate U1 pass (edited by hand)", 1))
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "stale view" in result.stdout


def test_exercise_journal_gap_fails(tmp_path):
    check = _copy_tree(tmp_path)
    journal = tmp_path / "evals" / "long-horizon" / "events.jsonl"
    lines = journal.read_text().splitlines()
    assert len(lines) == 14
    journal.write_text("\n".join(lines[:5] + lines[6:]) + "\n")
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "expected 6" in result.stdout


def test_exercise_journal_needs_the_state_it_committed(tmp_path):
    check = _copy_tree(tmp_path)
    state = tmp_path / "evals" / "long-horizon" / "run-state.md"
    state.unlink()
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "missing exercise run state" in result.stdout


def test_exercise_readme_must_state_what_it_does_not_prove(tmp_path):
    check = _copy_tree(tmp_path)
    readme = tmp_path / "evals" / "long-horizon" / "README.md"
    readme.write_text(readme.read_text().replace(
        "## What it does not prove", "## Limits"))
    result = _run(check, tmp_path)
    assert result.returncode == 1
    assert "What it does not prove" in result.stdout
