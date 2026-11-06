"""Tests for the add-only test-identity manifest gate.

Every case builds a throwaway tree with its own `tests/` directory and
`manifest.json`, so the checker is exercised offline and never against the live
suite: a live-suite test would go red for the wrong reason (the manifest is the
subject here, not the repository's own tests).
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tooling" / "check_test_floor.py"
SCHEMA = "agent-prompts-test-manifest/1"


def _module(*names):
    return "\n\n".join("def %s():\n    assert True" % name for name in names) + "\n"


def _tree(tmp_path, files, manifest=None):
    root = tmp_path
    (root / "tests").mkdir(parents=True)
    for name, body in files.items():
        (root / "tests" / name).write_text(body, encoding="utf-8")
    if manifest is not None:
        (root / "manifest.json").write_text(
            json.dumps({"schema": SCHEMA, "tests": manifest}, indent=2) + "\n",
            encoding="utf-8")
    return root


def _run(root, *args):
    return subprocess.run(
        [sys.executable, str(CHECK), "--root", str(root), "--tests", "tests",
         "--manifest", "manifest.json", *args],
        cwd=str(root), capture_output=True, text=True)


def _names(root):
    data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    return data["tests"]


def test_missing_name_fails_and_names_module_and_test(tmp_path):
    root = _tree(tmp_path, {"test_a.py": _module("test_kept")},
                 {"tests/test_a.py": ["test_kept", "test_removed"]})
    result = _run(root)
    assert result.returncode == 1, result.stdout
    assert "identity FAILED: 1 manifest test(s) not collected" in result.stdout
    assert "missing tests/test_a.py::test_removed" in result.stdout


def test_new_name_passes_and_is_counted(tmp_path):
    root = _tree(tmp_path, {"test_a.py": _module("test_kept", "test_new")},
                 {"tests/test_a.py": ["test_kept"]})
    result = _run(root)
    assert result.returncode == 0, result.stdout
    assert "identity OK" in result.stdout
    assert "1 new test(s) not yet in the manifest" in result.stdout


def test_plain_run_never_writes_the_manifest(tmp_path):
    root = _tree(tmp_path, {"test_a.py": _module("test_kept", "test_new")},
                 {"tests/test_a.py": ["test_kept"]})
    before = (root / "manifest.json").read_text(encoding="utf-8")
    result = _run(root)
    assert result.returncode == 0, result.stdout
    assert (root / "manifest.json").read_text(encoding="utf-8") == before

    failing = _tree(tmp_path / "failing", {"test_a.py": _module("test_kept")},
                    {"tests/test_a.py": ["test_removed"]})
    before = (failing / "manifest.json").read_text(encoding="utf-8")
    result = _run(failing)
    assert result.returncode == 1, result.stdout
    assert (failing / "manifest.json").read_text(encoding="utf-8") == before


def test_write_adds_new_names_without_pruning(tmp_path):
    root = _tree(tmp_path, {"test_a.py": _module("test_added")},
                 {"tests/test_a.py": ["test_gone"]})
    result = _run(root, "--write")
    assert result.returncode == 0, result.stdout
    assert _names(root) == {"tests/test_a.py": ["test_added", "test_gone"]}
    assert "kept 1 name(s) the collection no longer has" in result.stdout


def test_pruning_needs_allow_removals(tmp_path):
    root = _tree(tmp_path, {"test_a.py": _module("test_kept")},
                 {"tests/test_a.py": ["test_kept", "test_gone"]})
    result = _run(root, "--write")
    assert result.returncode == 0, result.stdout
    assert _names(root)["tests/test_a.py"] == ["test_gone", "test_kept"]

    result = _run(root, "--write", "--allow-removals")
    assert result.returncode == 0, result.stdout
    assert _names(root)["tests/test_a.py"] == ["test_kept"]


def test_removed_name_is_reported(tmp_path):
    root = _tree(tmp_path, {"test_a.py": _module("test_kept")},
                 {"tests/test_a.py": ["test_kept", "test_removed"]})
    result = _run(root, "--write", "--allow-removals")
    assert result.returncode == 0, result.stdout
    assert "removed tests/test_a.py::test_removed" in result.stdout
    assert "1 removed" in result.stdout


def test_allow_removals_without_write_is_refused(tmp_path):
    root = _tree(tmp_path, {"test_a.py": _module("test_kept")},
                 {"tests/test_a.py": ["test_kept"]})
    result = _run(root, "--allow-removals")
    assert result.returncode == 2
    assert "--allow-removals needs --write" in result.stdout


def test_parametrization_suffixes_collapse_to_one_name(tmp_path):
    root = _tree(tmp_path, {"test_a.py": (
        "import pytest\n\n\n"
        "@pytest.mark.parametrize('value', [1, 2])\n"
        "def test_param(value):\n    assert value\n")})
    result = _run(root, "--write")
    assert result.returncode == 0, result.stdout
    assert _names(root) == {"tests/test_a.py": ["test_param"]}


def test_class_qualified_names_stay_distinct(tmp_path):
    root = _tree(tmp_path, {"test_a.py": (
        "class TestOne:\n    def test_same(self):\n        assert True\n\n\n"
        "class TestTwo:\n    def test_same(self):\n        assert True\n")})
    result = _run(root, "--write")
    assert result.returncode == 0, result.stdout
    assert _names(root) == {"tests/test_a.py": ["TestOne::test_same", "TestTwo::test_same"]}


def test_unknown_schema_fails(tmp_path):
    root = _tree(tmp_path, {"test_a.py": _module("test_kept")})
    (root / "manifest.json").write_text(
        json.dumps({"schema": "other/9", "tests": {}}) + "\n", encoding="utf-8")
    result = _run(root)
    assert result.returncode == 1
    assert "schema is not %s" % SCHEMA in result.stdout


def test_missing_manifest_fails_without_write(tmp_path):
    root = _tree(tmp_path, {"test_a.py": _module("test_kept")})
    result = _run(root)
    assert result.returncode == 1
    assert "manifest.json is missing; run --write to create it" in result.stdout
