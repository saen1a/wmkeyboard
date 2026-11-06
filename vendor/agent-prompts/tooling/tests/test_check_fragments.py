"""Tests for the fragment manifest checker and its conduct-variant parity rule."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tooling" / "check_fragments.py"


def _tree(tmp_path):
    root = tmp_path / "tree"
    shutil.copytree(ROOT / "fragments", root / "fragments")
    (root / "tooling").mkdir()
    shutil.copy(ROOT / "tooling" / "check_fragments.py", root / "tooling")
    shutil.copy(ROOT / "tooling" / "fragments.manifest.json", root / "tooling")
    return root


def _run(root):
    return subprocess.run([sys.executable, str(root / "tooling" / "check_fragments.py")],
                          capture_output=True, text=True)


def _repin(root, name):
    """Re-pin one fragment after a deliberate edit, so only parity can fail."""
    manifest_path = root / "tooling" / "fragments.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    fragment = root / "fragments" / name
    manifest["fragments"][name]["sha256"] = hashlib.sha256(fragment.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


def test_repo_passes():
    result = subprocess.run([sys.executable, str(CHECK)], cwd=str(ROOT),
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    assert "conduct parity" in result.stdout


def test_hash_drift_fails(tmp_path):
    root = _tree(tmp_path)
    fragment = root / "fragments" / "agent-doctrine.md"
    fragment.write_text(fragment.read_text() + "\n- extra rule\n")
    result = _run(root)
    assert result.returncode == 1
    assert "sha256 mismatch" in result.stdout


def test_variant_missing_a_shared_rule_fails(tmp_path):
    root = _tree(tmp_path)
    variant = root / "fragments" / "agent-conduct.omp.md"
    variant.write_text(variant.read_text().replace(
        "A stated rule is not an enforced one", "A rule"))
    _repin(root, "agent-conduct.omp.md")
    result = _run(root)
    assert result.returncode == 1
    assert "conduct parity" in result.stdout
    assert "agent-conduct.omp.md" in result.stdout


def test_unlisted_fragment_on_disk_fails(tmp_path):
    root = _tree(tmp_path)
    (root / "fragments" / "agent-conduct.extra.md").write_text("<conduct>\n- x\n</conduct>\n")
    result = _run(root)
    assert result.returncode == 1
    assert "do not match entries" in result.stdout
