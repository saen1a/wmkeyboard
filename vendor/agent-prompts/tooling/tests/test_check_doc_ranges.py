"""Tests for the rule-range drift checker."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tooling" / "check_doc_ranges.py"


def _tree(tmp_path, standard, docs):
    root = tmp_path / "tree"
    (root / "standards").mkdir(parents=True)
    (root / "standards" / "demo.md").write_text(standard, encoding="utf-8")
    for name, text in docs.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _run(root, *extra):
    return subprocess.run([sys.executable, str(CHECK), "--root", str(root), *extra],
                          cwd=str(ROOT), capture_output=True, text=True)


STANDARD = """# Demo standard (WX-01..WX-04)

## WX-01 -- First rule

Body text long enough to look like a rule body and nothing else.

## WX-02 -- Second rule

Body text long enough to look like a rule body and nothing else.

## WX-03 -- Third rule

Body text long enough to look like a rule body and nothing else.

| WX-04 | A table-defined rule |

"""


def test_matching_range_passes(tmp_path):
    root = _tree(tmp_path, STANDARD, {"README.md": "Covers WX-01..WX-04 fully.\n"})
    result = _run(root)
    assert result.returncode == 0, result.stdout
    assert "0 violation(s)" in result.stdout


def test_range_beyond_defined_rule_fails(tmp_path):
    root = _tree(tmp_path, STANDARD, {"README.md": "Covers WX-01..WX-07 fully.\n"})
    result = _run(root)
    assert result.returncode == 1
    assert "which does not exist" in result.stdout


def test_stale_range_fails_without_marker(tmp_path):
    root = _tree(tmp_path, STANDARD, {"docs/guide.md": "Covers WX-01..WX-02.\n"})
    result = _run(root)
    assert result.returncode == 1
    assert "is stale" in result.stdout
    assert "[subset]" in result.stdout


def test_marked_subset_passes(tmp_path):
    root = _tree(tmp_path, STANDARD, {"docs/guide.md": "Covers WX-01..WX-02 [subset].\n"})
    result = _run(root)
    assert result.returncode == 0, result.stdout


def test_unknown_family_fails(tmp_path):
    root = _tree(tmp_path, STANDARD, {"docs/guide.md": "See ZZ-01..ZZ-03 for details.\n"})
    result = _run(root)
    assert result.returncode == 1
    assert "no standard defines" in result.stdout


def test_cross_family_range_fails(tmp_path):
    root = _tree(tmp_path, STANDARD, {"docs/guide.md": "See WX-01..ZZ-03 here.\n"})
    result = _run(root)
    assert result.returncode == 1
    assert "crosses two rule families" in result.stdout


def test_historical_records_are_skipped(tmp_path):
    root = _tree(tmp_path, STANDARD, {
        "CHANGELOG.md": "Covers WX-01..WX-02.\n",
        "PLAN.md": "Covers WX-01..WX-02.\n",
        "docs/knowledge-base/rotation-2026-10.md": "Covers WX-01..WX-02.\n",
        "provenance/record.md": "Covers WX-01..WX-02.\n",
        "packs/consumer.md": "Covers WX-01..WX-02.\n",
    })
    result = _run(root)
    assert result.returncode == 0, result.stdout
    assert "1 file(s)" in result.stdout  # only the standard itself is scanned
    assert "0 violation(s)" in result.stdout


def test_fenced_block_is_skipped(tmp_path):
    root = _tree(tmp_path, STANDARD, {"docs/guide.md": "```\nold range WX-01..WX-02\n```\n"})
    result = _run(root)
    assert result.returncode == 0, result.stdout


def test_json_summary_reports_families(tmp_path):
    root = _tree(tmp_path, STANDARD, {"README.md": "Covers WX-01..WX-04 fully.\n"})
    result = _run(root, "--json")
    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["summary"]["families"]["WX"] == 4
    assert payload["violations"] == []


def test_missing_standards_dir_is_exit_2(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    result = _run(empty)
    assert result.returncode == 2
    assert "cannot read standards" in result.stdout
