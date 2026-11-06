"""Tests for the WP-08 labelled failure set checker."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tooling" / "check_failure_set.py"
SET = ROOT / "evals" / "optimization" / "failure-set.md"


def _run(path):
    return subprocess.run([sys.executable, str(CHECK), str(path)],
                          cwd=str(ROOT), capture_output=True, text=True)


def _write(tmp_path, text):
    path = tmp_path / "failure-set.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_committed_set_is_traceable():
    result = _run(SET)
    assert result.returncode == 0, result.stdout
    assert "0 violation(s)" in result.stdout


def test_case_count_is_in_range():
    lines = SET.read_text(encoding="utf-8").splitlines()
    ids = [line for line in lines if line.startswith("| FC-")]
    assert 20 <= len(ids) <= 40


def test_anchor_must_resolve(tmp_path):
    text = SET.read_text(encoding="utf-8").replace(
        "the declared owner is absent", "a phrase that is not in the source")
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "anchor not found" in result.stdout


def test_duplicate_anchor_fails(tmp_path):
    text = SET.read_text(encoding="utf-8").replace(
        "Paired case results: 8 wins / 53 ties / 5 losses",
        "8 wins / 53 ties / 5 losses")
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "anchor resolves 2 times" in result.stdout
    assert "it must be unique" in result.stdout


def test_missing_source_fails(tmp_path):
    text = SET.read_text(encoding="utf-8").replace(
        "docs/knowledge-base/semantic-trigger-check-2026-10.md",
        "docs/knowledge-base/does-not-exist.md", 1)
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "source does not exist" in result.stdout


def test_duplicate_case_id_fails(tmp_path):
    text = SET.read_text(encoding="utf-8").replace("| FC-02 |", "| FC-01 |")
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "duplicate case id" in result.stdout


def test_unknown_category_fails(tmp_path):
    text = SET.read_text(encoding="utf-8").replace(
        "| FC-01 | routing |", "| FC-01 | vibes |")
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "category is not one of" in result.stdout


def test_covered_without_note_fails(tmp_path):
    text = SET.read_text(encoding="utf-8").replace(
        "Case prompts fixed in Finding 1, before any body edit.", "-")
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "FC-10 is covered without a state_note" in result.stdout


def test_ids_must_be_contiguous(tmp_path):
    text = SET.read_text(encoding="utf-8").replace("| FC-38 |", "| FC-99 |")
    result = _run(_write(tmp_path, text))
    assert result.returncode == 1
    assert "not contiguous" in result.stdout


def test_too_few_cases_fails(tmp_path):
    lines = SET.read_text(encoding="utf-8").splitlines()
    kept = []
    seen = 0
    for line in lines:
        if line.startswith("| FC-"):
            seen += 1
            if seen > 3:
                continue
        kept.append(line)
    result = _run(_write(tmp_path, "\n".join(kept) + "\n"))
    assert result.returncode == 1
    assert "3 cases, expected 20..40" in result.stdout
