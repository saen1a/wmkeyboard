"""Tests for the token-efficiency and cache-prefix checks."""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tooling" / "check_token_efficiency.py"
COPY = ("agents", "prompts", "standards", "skills")


def _copy_tree(tmp_path):
    for name in COPY:
        shutil.copytree(ROOT / name, tmp_path / name)
    shutil.copy2(ROOT / "CATALOG.md", tmp_path / "CATALOG.md")
    return tmp_path


def _run(root):
    return subprocess.run([sys.executable, str(CHECK), "--root", str(root)],
                          cwd=str(ROOT), capture_output=True, text=True)


def test_gate_passes_on_repo():
    result = _run(ROOT)
    assert result.returncode == 0, result.stdout
    assert "0 violation(s)" in result.stdout


def test_volatile_date_fails(tmp_path):
    root = _copy_tree(tmp_path)
    path = root / "agents" / "engineering" / "eng-api-developer.md"
    path.write_text(path.read_text() + "\nToday is 2026-10-25.\n")
    result = _run(root)
    assert result.returncode == 1
    assert "volatile ISO date" in result.stdout


def test_duplicate_instruction_fails(tmp_path):
    root = _copy_tree(tmp_path)
    path = root / "agents" / "engineering" / "eng-api-developer.md"
    text = path.read_text()
    line = "This sentence is a duplicate instruction line in the same prompt."
    path.write_text(text + "\n" + line + "\n" + line + "\n")
    result = _run(root)
    assert result.returncode == 1
    assert "duplicates an instruction line" in result.stdout


def test_missing_assembly_rule_fails(tmp_path):
    root = _copy_tree(tmp_path)
    path = root / "standards" / "prompt-assembly.md"
    path.write_text(path.read_text().replace("## AS-12 -- ", "## AS-12x -- "))
    result = _run(root)
    assert result.returncode == 1
    assert "AS-12" in result.stdout


def test_bad_profile_version_fails(tmp_path):
    root = _copy_tree(tmp_path)
    path = root / "standards" / "cache-profiles.json"
    text = path.read_text()
    current = json.loads(text)["version"]
    path.write_text(text.replace('"version": "%s"' % current, '"version": "bad"'))
    result = _run(root)
    assert result.returncode == 1
    assert "version must be semver" in result.stdout


def test_missing_catalog_pin_fails(tmp_path):
    root = _copy_tree(tmp_path)
    catalog = root / "CATALOG.md"
    text = catalog.read_text()
    current = re.search(r"Cache policy: (\S+)", text).group(1)
    catalog.write_text(text.replace("Cache policy: %s" % current,
                                    "Cache policy: 9.9.9"))
    result = _run(root)
    assert result.returncode == 1
    assert "Cache policy: %s" % current in result.stdout


def test_skill_body_cap_fails(tmp_path):
    root = _copy_tree(tmp_path)
    skill = root / "skills" / "general" / "long-horizon-run" / "SKILL.md"
    skill.write_text(skill.read_text() + "\n" + ("word " * 2000))
    result = _run(root)
    assert result.returncode == 1
    assert "over the 1500 token cap" in result.stdout


def test_as_rule_body_removal_fails(tmp_path):
    root = _copy_tree(tmp_path)
    path = root / "standards" / "prompt-assembly.md"
    text = path.read_text()
    start = text.index("## AS-12 -- ")
    end = text.index("## Cross-refs")
    path.write_text(text[:start] + "## AS-12 -- Append-only history and re-versioned compaction\n\n" + text[end:])
    result = _run(root)
    assert result.returncode == 1
    assert "AS-12 body missing anchor" in result.stdout


def test_month_name_date_fails(tmp_path):
    root = _copy_tree(tmp_path)
    path = root / "agents" / "engineering" / "eng-api-developer.md"
    path.write_text(path.read_text() + "\nToday's date is Oct 25, 2026.\n")
    result = _run(root)
    assert result.returncode == 1
    assert "runtime metadata" in result.stdout or "month-name date" in result.stdout


def test_profile_drift_fails(tmp_path):
    root = _copy_tree(tmp_path)
    path = root / "standards" / "cache-profiles.json"
    path.write_text(path.read_text().replace('"min_tokens": 512',
                                             '"min_tokens": 99999', 1))
    result = _run(root)
    assert result.returncode == 1
    assert "does not match cache-profiles.pin.json" in result.stdout


def test_empty_profiles_fails(tmp_path):
    root = _copy_tree(tmp_path)
    path = root / "standards" / "cache-profiles.json"
    text = path.read_text()
    start = text.index('"profiles": [')
    path.write_text(text[:start] + '"profiles": []\n}\n')
    result = _run(root)
    assert result.returncode == 1
    assert "does not match cache-profiles.pin.json" in result.stdout


def test_day_first_date_fails(tmp_path):
    root = _copy_tree(tmp_path)
    path = root / "agents" / "engineering" / "eng-api-developer.md"
    path.write_text(path.read_text() + "\nSnapshot 25 October 2026 baseline.\n")
    result = _run(root)
    assert result.returncode == 1
    assert "day-first date" in result.stdout


def test_every_as_body_is_required(tmp_path):
    for number in range(1, 15):
        root = _copy_tree(tmp_path / ("as%02d" % number))
        path = root / "standards" / "prompt-assembly.md"
        text = path.read_text()
        rule = "AS-%02d" % number
        start = text.index("## %s -- " % rule)
        next_heading = text.find("\n## ", start + 1)
        end = next_heading + 1 if next_heading != -1 else len(text)
        path.write_text(text[:start] + text[start:end].split("\n", 1)[0] + "\n\n" + text[end:])
        result = _run(root)
        assert result.returncode == 1, (rule, result.stdout)


def test_empty_profiles_fails_even_after_pin_update(tmp_path):
    root = _copy_tree(tmp_path)
    path = root / "standards" / "cache-profiles.json"
    text = path.read_text()
    start = text.index('"profiles": [')
    path.write_text(text[:start] + '"profiles": []\n}\n')
    subprocess.run([sys.executable, str(CHECK), "--root", str(root), "--update-pin"],
                   cwd=str(ROOT), capture_output=True, text=True)
    result = _run(root)
    assert result.returncode == 1
    assert "at least 4 profiles" in result.stdout


def test_hash_report_and_profile_coverage():
    result = subprocess.run([sys.executable, str(CHECK), "--hash", "--json"],
                            cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    import json
    data = json.loads(result.stdout)
    assert data["hashes"]
    sample = next(iter(data["hashes"].values()))
    assert len(sample["prefix"]) == 64
    assert sample["layers"]
    assert data["coverage_by_profile"]["vllm-apc"] == data["carriers"]


def test_hash_text_output_includes_layers():
    result = subprocess.run([sys.executable, str(CHECK), "--hash"],
                            cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    hash_lines = [line for line in result.stdout.splitlines() if line.startswith("HASH ")]
    layer_lines = [line for line in result.stdout.splitlines() if line.startswith("LAYER ")]
    assert len(hash_lines) == 41
    assert layer_lines
    assert all(len(line.split()[2]) == 64 for line in hash_lines)
