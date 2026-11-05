"""Tests for the measured-state generator (docs/measured-state.md)."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tooling" / "measure_state.py"
STATE = ROOT / "docs" / "measured-state.md"


def _run(*extra):
    return subprocess.run([sys.executable, str(TOOL), *extra],
                          cwd=str(ROOT), capture_output=True, text=True)


def test_committed_state_matches_the_tree():
    result = _run("--check")
    assert result.returncode == 0, result.stdout
    assert "matches the tree" in result.stdout


def test_stale_state_is_reported(tmp_path, monkeypatch):
    original = STATE.read_text(encoding="utf-8")
    try:
        STATE.write_text(original.replace("| role templates | 38 |",
                                          "| role templates | 99 |"), encoding="utf-8")
        result = _run("--check")
        assert result.returncode == 1
        assert "is stale" in result.stdout
        assert "role templates | 38" in result.stdout
    finally:
        STATE.write_text(original, encoding="utf-8")


def test_json_output_measures_the_same_values():
    result = _run("--json")
    payload = json.loads(result.stdout)
    assert payload["counts"]["carriers"] == payload["counts"]["agents"] + payload["counts"]["task_prompts"]
    assert payload["skills"]["count"] >= payload["skills"]["vendor"]
    assert payload["admissions"]["dsh"]["admission"] == "refused"
