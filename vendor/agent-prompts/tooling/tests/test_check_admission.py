"""Tests for the runtime admission checker (standards/agent-adapter.md)."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tooling" / "check_admission.py"
OMP = ROOT / "omp" / "admission.json"
DSH = ROOT / "dsh" / "admission.json"


def _load(path=OMP):
    return json.loads(path.read_text(encoding="utf-8"))


def _run(tmp_path, data, *extra):
    path = tmp_path / "admission.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return subprocess.run([sys.executable, str(CHECK), str(path), *extra],
                          cwd=str(ROOT), capture_output=True, text=True)


def _base():
    return {
        "schema": "agent-admission/1",
        "runtime": "demo",
        "runtime_version": "1.0.0",
        "checked": "2026-10-31",
        "required_features": ["tool_allowlist"],
        "admission": "admitted",
        "capabilities": {
            "tool_allowlist": {
                "support": "supported",
                "evidence": "demo docs",
                "checked": "2026-10-31",
            },
            "loop_gate": {
                "support": "degraded",
                "degraded_behavior": "no hook; python3 tooling/check_loop_gate.py in CI",
                "checked": "2026-10-31",
            },
        },
    }


def test_omp_record_is_admitted():
    result = subprocess.run([sys.executable, str(CHECK), str(OMP)],
                            cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    assert "admitted" in result.stdout


def test_dsh_record_is_honestly_refused():
    result = subprocess.run([sys.executable, str(CHECK), str(DSH)],
                            cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    assert "refused" in result.stdout
    assert "unknown" in result.stdout


def test_supported_without_evidence_fails(tmp_path):
    data = _base()
    del data["capabilities"]["tool_allowlist"]["evidence"]
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "without an evidence pointer" in result.stdout


def test_stale_evidence_fails(tmp_path):
    data = _base()
    data["capabilities"]["tool_allowlist"]["checked"] = "2024-01-01"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "evidence older than" in result.stdout


def test_future_date_fails(tmp_path):
    data = _base()
    data["capabilities"]["tool_allowlist"]["checked"] = "2030-01-01"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "in the future" in result.stdout


def test_degraded_needs_named_behavior(tmp_path):
    data = _base()
    data["capabilities"]["tool_allowlist"] = {"support": "degraded", "checked": "2026-10-31"}
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "named degraded_behavior" in result.stdout


def test_unsupported_needs_refusal(tmp_path):
    data = _base()
    data["capabilities"]["shell_tool"] = {"support": "unsupported", "checked": "2026-10-31"}
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "without a named refusal" in result.stdout


def test_unknown_needs_attempt_record(tmp_path):
    data = _base()
    data["capabilities"]["mcp"] = {"support": "unknown"}
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "recorded verification attempt" in result.stdout


def test_unknown_required_feature_refuses(tmp_path):
    data = _base()
    data["capabilities"]["tool_allowlist"] = {"support": "unknown", "attempted": "tried"}
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "fail-closed computation" in result.stdout


def test_refused_record_must_name_refusals(tmp_path):
    data = _base()
    data["admission"] = "refused"
    data["capabilities"]["tool_allowlist"] = {"support": "unknown", "attempted": "tried"}
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "must name the refusing capability" in result.stdout


def test_degraded_required_feature_can_admit(tmp_path):
    data = _base()
    data["capabilities"]["tool_allowlist"] = {
        "support": "degraded",
        "degraded_behavior": "read-only allowlist only",
        "checked": "2026-10-31",
    }
    assert _run(tmp_path, data).returncode == 0


def test_projection_cannot_use_unsupported_capability(tmp_path):
    data = _base()
    data["capabilities"]["bash"] = {
        "support": "unsupported",
        "refusal": "never projected",
        "checked": "2026-10-31",
    }
    data["projection"] = {"writer": ["bash"]}
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "uses unsupported capability" in result.stdout


def test_projection_cannot_use_undeclared_capability(tmp_path):
    data = _base()
    data["projection"] = {"writer": ["edit"]}
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "uses undeclared capability" in result.stdout


def test_unknown_field_fails(tmp_path):
    data = _base()
    data["extra"] = True
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "unknown field: extra" in result.stdout


def test_json_output_reports_computed_admission(tmp_path):
    data = _base()
    data["admission"] = "refused"
    result = _run(tmp_path, data, "--json")
    payload = json.loads(result.stdout)
    assert payload["admission"] == "admitted"
    assert payload["violations"]


def test_non_string_required_feature_fails_without_crash(tmp_path):
    data = _base()
    data["required_features"] = [{"x": 1}]
    result = _run(tmp_path, data)
    assert "Traceback" not in result.stdout + result.stderr
    assert result.returncode == 1
    assert "must be a non-empty string" in result.stdout


def test_non_object_capabilities_fails_without_crash(tmp_path):
    data = _base()
    data["capabilities"] = ["x"]
    result = _run(tmp_path, data)
    assert "Traceback" not in result.stdout + result.stderr
    assert result.returncode == 1
    assert "capabilities must be a non-empty object" in result.stdout


def test_record_checked_must_be_an_iso_date(tmp_path):
    data = _base()
    data["checked"] = "not-a-date"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "checked must be an ISO date" in result.stdout


def test_record_checked_must_not_be_in_the_future(tmp_path):
    data = _base()
    data["checked"] = "2030-01-01"
    result = _run(tmp_path, data, "--today", "2026-10-31")
    assert result.returncode == 1
    assert "checked is in the future" in result.stdout


def test_refusal_must_name_the_feature_exactly(tmp_path):
    data = _base()
    data["required_features"] = ["shell", "shell_tool"]
    data["capabilities"]["shell"] = {"support": "unknown", "attempted": "tried"}
    data["capabilities"]["shell_tool"] = {"support": "unknown", "attempted": "tried"}
    data["admission"] = "refused"
    data["refusals"] = ["shell_tool: unknown"]
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "refusal does not name required feature: shell" in result.stdout


def test_loop_gate_capability_is_required(tmp_path):
    data = _base()
    data["capabilities"].pop("loop_gate")
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "capabilities.loop_gate is required" in result.stdout


def test_supported_loop_gate_must_name_the_check(tmp_path):
    data = _base()
    data["capabilities"]["loop_gate"] = {"support": "supported",
                                         "evidence": "the prompt says so",
                                         "checked": "2026-10-31"}
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "names no check that exists" in result.stdout


def test_degraded_loop_gate_must_name_what_carries_the_gate(tmp_path):
    data = _base()
    data["capabilities"]["loop_gate"] = {"support": "degraded",
                                         "degraded_behavior": "no hook in this runtime",
                                         "checked": "2026-10-31"}
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "names no check that exists" in result.stdout


def test_degraded_loop_gate_naming_the_ci_gate_passes(tmp_path):
    result = _run(tmp_path, _base())
    assert result.returncode == 0, result.stdout
