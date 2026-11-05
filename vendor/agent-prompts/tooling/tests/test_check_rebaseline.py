"""Tests for the re-baseline trigger (WP-08)."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tooling" / "check_rebaseline.py"
BASELINE = ROOT / "evals" / "optimization" / "baseline.json"
SAME = ROOT / "evals" / "role-ab" / "results" / "wp07-conduct-guard.json"
OTHER_MODEL = ROOT / "evals" / "role-ab" / "results" / "workflow-loop-1.3.0.json"


def _run(*args):
    return subprocess.run([sys.executable, str(CHECK), *args],
                          cwd=str(ROOT), capture_output=True, text=True)


def _record(tmp_path, name, run, **extra):
    data = {"schema": "agent-prompts-harness/1", "run": run}
    data.update(extra)
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _run_block(**overrides):
    block = {"model": "anthropic/claude-haiku-5.5",
             "provider": "kilo-gateway",
             "harness": "openai-compatible-chat",
             "seed": None,
             "timestamp_utc": "2026-10-27",
             "prompt_version": "agent-prompts@02e2ac2"}
    block.update(overrides)
    return block


def test_committed_baseline_matches_its_campaign():
    result = _run("--baseline", str(BASELINE), "--current", str(SAME))
    assert result.returncode == 0, result.stdout
    assert "identity matches" in result.stdout


def test_model_and_prompt_change_requires_a_new_baseline():
    result = _run("--baseline", str(BASELINE), "--current", str(OTHER_MODEL))
    assert result.returncode == 1
    assert "model changed" in result.stdout
    assert "prompt_version changed" in result.stdout
    assert "a new baseline is required" in result.stdout


def test_harness_change_is_detected(tmp_path):
    current = _record(tmp_path, "current.json",
                      _run_block(harness="openai-compatible-http"))
    result = _run("--baseline", str(BASELINE), "--current", str(current))
    assert result.returncode == 1
    assert "harness changed" in result.stdout


def test_identical_identity_passes(tmp_path):
    baseline = _record(tmp_path, "baseline.json", _run_block())
    current = _record(tmp_path, "current.json", _run_block())
    result = _run("--baseline", str(baseline), "--current", str(current))
    assert result.returncode == 0, result.stdout
    assert "cache_epoch is not recorded on either side" in result.stdout
    assert "grader is not recorded on either side" in result.stdout


def test_cache_epoch_change_is_detected(tmp_path):
    epoch = {"model": "anthropic/claude-haiku-5.5",
             "harness": "openai-compatible-chat",
             "toolset_sha256": "a1b2c3d4",
             "doctrine_version": "1.3.1"}
    baseline = _record(tmp_path, "baseline.json", _run_block(cache_epoch=epoch))
    changed = dict(epoch, doctrine_version="1.4.0")
    current = _record(tmp_path, "current.json",
                      _run_block(cache_epoch=changed))
    result = _run("--baseline", str(baseline), "--current", str(current))
    assert result.returncode == 1
    assert "cache_epoch.doctrine_version changed" in result.stdout


def test_grader_only_on_one_side_is_unverifiable(tmp_path):
    current = _record(tmp_path, "current.json", _run_block())
    result = _run("--baseline", str(BASELINE), "--current", str(current))
    assert result.returncode == 1
    assert "grader changed or is unverifiable" in result.stdout


def test_unreadable_record_exits_two(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{}", encoding="utf-8")
    result = _run("--baseline", str(BASELINE), "--current", str(path))
    assert result.returncode == 2
    assert "cannot read identity" in result.stdout


def test_json_output_reports_the_flag(tmp_path):
    current = _record(tmp_path, "current.json", _run_block(model="other-model"))
    result = _run("--baseline", str(BASELINE), "--current", str(current),
                  "--json")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["rebaseline_required"] is True
    assert any("model changed" in problem for problem in payload["problems"])
