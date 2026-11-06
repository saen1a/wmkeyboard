"""Tests for the canonical tool-set manifest checker."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tooling" / "check_tool_set.py"
EXAMPLE = ROOT / "exemplars" / "tool-set-example.json"


def _load():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _run(tmp_path, data, *extra, name="tool-set.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return subprocess.run([sys.executable, str(CHECK), str(path), *extra],
                          cwd=str(ROOT), capture_output=True, text=True)


def _update(tmp_path, data):
    result = _run(tmp_path, data, "--update-hash")
    assert result.returncode == 0, result.stdout
    return result.stdout.strip().split()[-1]


def _set_hash(data):
    raw = json.dumps(data["tools"], sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True)
    data["toolset_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_example_passes():
    result = subprocess.run([sys.executable, str(CHECK), str(EXAMPLE)],
                            cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    assert "0 violation(s)" in result.stdout


def test_reordered_tools_fail(tmp_path):
    data = _load()
    data["order"] = list(reversed(data["order"]))
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "order does not match" in result.stdout


def test_volatile_description_fails(tmp_path):
    data = _load()
    data["tools"][0]["description"] += " Updated 2026-10-25."
    _set_hash(data)
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "volatile ISO date" in result.stdout


def test_mask_unknown_tool_fails(tmp_path):
    data = _load()
    data["masks"]["roles"]["orchestrator"].append("missing_tool")
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "unknown tool missing_tool" in result.stdout


def test_hash_drift_fails_and_update_fixes(tmp_path):
    data = _load()
    data["tools"][1]["description"] = "Write a UTF-8 file."
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "toolset_sha256 does not match" in result.stdout
    data["toolset_sha256"] = _update(tmp_path, data)
    result = _run(tmp_path, data)
    assert result.returncode == 0


def test_duplicate_tool_fails(tmp_path):
    data = _load()
    data["tools"][2]["name"] = "read_file"
    data["order"] = ["read_file", "write_file", "read_file", "mcp_example"]
    result = _run(tmp_path, data, "--update-hash")
    assert result.returncode == 1
    assert "duplicate tool names" in result.stdout


def test_mask_only_change_keeps_hash(tmp_path):
    data = _load()
    data["masks"]["roles"]["orchestrator"] = ["read_file"]
    result = _run(tmp_path, data)
    assert result.returncode == 0


def test_deferred_pattern_needs_deferred_tool(tmp_path):
    data = _load()
    data["masks"]["deferred"] = ["nothing_*"]
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "matches no deferred tool" in result.stdout


def test_deferred_tools_must_be_suffix(tmp_path):
    data = _load()
    tool = data["tools"].pop()
    data["tools"].insert(0, tool)
    data["order"] = [item["name"] for item in data["tools"]]
    _set_hash(data)
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "contiguous suffix" in result.stdout


def test_update_hash_refuses_invalid(tmp_path):
    data = _load()
    del data["tools"]
    result = _run(tmp_path, data, "--update-hash")
    assert result.returncode == 1
    assert "tools must be a non-empty list" in result.stdout


def test_previous_requires_version_bump(tmp_path):
    data = _load()
    previous = tmp_path / "previous.json"
    previous.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    data["tools"][0]["description"] = "Read a file."
    data["toolset_sha256"] = _update(tmp_path, data)
    result = _run(tmp_path, data, "--previous", str(previous))
    assert result.returncode == 1
    assert "without a version bump" in result.stdout
    data["version"] = "1.0.1"
    result = _run(tmp_path, data, "--previous", str(previous))
    assert result.returncode == 0, result.stdout


def test_hyphenated_name_is_valid(tmp_path):
    data = _load()
    data["tools"][0]["name"] = "mcp-read"
    data["order"][0] = "mcp-read"
    data["masks"]["roles"]["orchestrator"][0] = "mcp-read"
    data["masks"]["roles"]["executor"][0] = "mcp-read"
    data["toolset_sha256"] = _update(tmp_path, data)
    result = _run(tmp_path, data)
    assert result.returncode == 0, result.stdout


def test_unknown_key_fails(tmp_path):
    data = _load()
    data["tools"][0]["extra"] = 1
    result = _run(tmp_path, data, "--update-hash")
    assert result.returncode == 1
    assert "unknown key" in result.stdout


def test_volatile_handler_fails(tmp_path):
    data = _load()
    data["tools"][0]["handler"] = "fs.read@550e8400-e29b-41d4-a716-446655440000"
    _set_hash(data)
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "volatile UUID" in result.stdout


def test_volatile_wire_fails(tmp_path):
    data = _load()
    data["tools"][0]["wire"] = {"session": "abc", "note": "built 25 Oct 2026"}
    _set_hash(data)
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "volatile" in result.stdout


def test_duplicate_deferred_pattern_fails(tmp_path):
    data = _load()
    data["masks"]["deferred"] = ["mcp_*", "mcp_*"]
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "duplicate patterns" in result.stdout


def test_stale_deferred_unmatched_fails(tmp_path):
    data = _load()
    data["masks"]["deferred_unmatched"] = ["mcp_*"]
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "stale" in result.stdout


def test_previous_with_update_hash_passes_after_version_bump(tmp_path):
    data = _load()
    previous = tmp_path / "previous.json"
    previous.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    data["version"] = "1.0.1"
    data["tools"][0]["description"] = "Read a file."
    result = _run(tmp_path, data, "--previous", str(previous), "--update-hash")
    assert result.returncode == 0, result.stdout
