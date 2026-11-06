"""Tests for the gate verdict checker (standards/verification-integrity.md)."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tooling" / "check_gate_verdict.py"
EXAMPLE = ROOT / "exemplars" / "gate-verdict-example.json"


def _load():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _run(tmp_path, data, *extra):
    path = tmp_path / "verdict.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return subprocess.run([sys.executable, str(CHECK), str(path), *extra],
                          cwd=str(ROOT), capture_output=True, text=True)


def test_example_passes():
    result = subprocess.run([sys.executable, str(CHECK), str(EXAMPLE)],
                            cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    assert "0 violation(s)" in result.stdout


def test_anonymous_verifier_fails(tmp_path):
    data = _load()
    data["verifier"] = ""
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "anonymous pass" in result.stdout


def test_author_as_verifier_fails(tmp_path):
    data = _load()
    data["verifier"] = data["implementer"]
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "author is never the sole verifier" in result.stdout


def test_self_verifier_cannot_pass(tmp_path):
    data = _load()
    data["verifier"] = "self"
    data["exemption"] = {"check": "no second context", "claim": "Ready (unverified)"}
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "Ready (unverified)" in result.stdout


def test_skipped_check_cannot_pass(tmp_path):
    data = _load()
    data["checks"][0]["status"] = "skipped"
    data["checks"][0]["exit"] = None
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "non-passing check" in result.stdout


def test_stub_artifact_fails(tmp_path):
    data = _load()
    data["artifacts"][0]["shape"] = "stub"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "stub artifact" in result.stdout


def test_substance_floor_fails(tmp_path):
    data = _load()
    data["artifacts"][0]["non_whitespace_chars"] = 12
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "substance floor" in result.stdout


def test_unmet_must_fails(tmp_path):
    data = _load()
    data["criteria"][0]["state"] = "unverified"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "unmet MUST criterion" in result.stdout


def test_advisory_should_can_remain_unmet(tmp_path):
    data = _load()
    data["criteria"][2]["state"] = "unmet"
    assert _run(tmp_path, data).returncode == 0


def test_degraded_cannot_pass(tmp_path):
    data = _load()
    data["degraded"] = [{"check": "sca", "reason": "scanner unavailable"}]
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "degraded check set" in result.stdout


def test_mode_off_cannot_pass(tmp_path):
    data = _load()
    data["mode"] = "off"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "mode off" in result.stdout


def test_open_high_finding_blocks_pass(tmp_path):
    data = _load()
    data["findings"][0]["state"] = "open"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "still open" in result.stdout


def test_waived_high_finding_blocks_pass(tmp_path):
    data = _load()
    data["findings"][0]["state"] = "waived"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "still waived" in result.stdout


def test_zero_capture_cannot_pass(tmp_path):
    data = _load()
    data["checks"] = []
    data["artifacts"] = []
    data["claims"] = []
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "no substantive capture" in result.stdout


def test_coverage_below_floor_fails(tmp_path):
    data = _load()
    data["coverage"]["measured"] = 80
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "below the declared floor" in result.stdout


def test_low_floor_needs_rationale(tmp_path):
    data = _load()
    data["coverage"]["floor"] = 60
    data["coverage"]["measured"] = 60
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "below the default" in result.stdout


def test_claim_with_unknown_evidence_fails(tmp_path):
    data = _load()
    data["claims"][0]["evidence"] = ["A1", "nowhere"]
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "unknown evidence id" in result.stdout


def test_fix_requires_a_cause(tmp_path):
    data = _load()
    data["verdict"] = "fix"
    data["findings"] = []
    data["checks"][0]["exit"] = 0
    data["criteria"][0]["state"] = "met"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "fix without a cause" in result.stdout


def test_hold_accepts_skipped_reason(tmp_path):
    data = _load()
    data["verdict"] = "hold"
    data["hold_reason"] = "skipped-check"
    data["checks"][0]["status"] = "skipped"
    data["checks"][0]["exit"] = None
    data["checks"][0]["skip_reason"] = "no suite configured"
    result = _run(tmp_path, data)
    assert result.returncode == 0, result.stdout


def test_hold_without_reason_fails(tmp_path):
    data = _load()
    data["verdict"] = "hold"
    data.pop("notes", None)
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "hold requires hold_reason" in result.stdout


def test_halt_requires_taxonomy_reason(tmp_path):
    data = _load()
    data["verdict"] = "halt"
    data["halt_reason"] = "gave up"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "halt requires halt_reason" in result.stdout


def test_missing_required_field_fails(tmp_path):
    data = _load()
    del data["coverage"]
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "missing required field: coverage" in result.stdout


def test_bad_enum_fails(tmp_path):
    data = _load()
    data["gate"] = "signoff"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "gate not in vocabulary" in result.stdout


def test_json_output_reports_violations(tmp_path):
    data = _load()
    data["verifier"] = data["implementer"]
    result = _run(tmp_path, data, "--json")
    payload = json.loads(result.stdout)
    assert payload["violations"]
    assert payload["verdict"] == "pass"


def test_verify_gate_needs_a_check(tmp_path):
    data = _load()
    data["checks"] = []
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "verify gate record carries no check" in result.stdout


def test_acceptance_gate_needs_a_must_criterion(tmp_path):
    data = _load()
    data["gate"] = "acceptance"
    data["criteria"] = [c for c in data["criteria"] if c["severity"] != "MUST"]
    data["claims"] = [{"claim": "advisory only", "evidence": "A3"}]
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "no MUST criterion" in result.stdout


def test_review_gate_needs_a_subject(tmp_path):
    data = _load()
    data["gate"] = "review"
    data["findings"] = []
    data["criteria"] = []
    data["claims"] = []
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "names nothing inspected" in result.stdout


def test_review_gate_accepts_a_clean_pass_with_criteria(tmp_path):
    data = _load()
    data["gate"] = "review"
    data["findings"] = []
    result = _run(tmp_path, data)
    assert result.returncode == 0, result.stdout


def test_attempt_is_required(tmp_path):
    data = _load()
    del data["attempt"]
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "missing required field: attempt" in result.stdout


def test_attempt_above_one_needs_halt(tmp_path):
    data = _load()
    data["attempt"] = 2
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "one-refinement bound" in result.stdout


def test_attempt_above_one_is_allowed_on_halt(tmp_path):
    data = _load()
    data["verdict"] = "halt"
    data["halt_reason"] = "over-bound"
    data["attempt"] = 2
    result = _run(tmp_path, data)
    assert result.returncode == 0, result.stdout


def test_attempt_must_be_an_integer(tmp_path):
    data = _load()
    data["attempt"] = "1"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "attempt must be an integer" in result.stdout


def test_skipped_check_needs_a_reason(tmp_path):
    data = _load()
    data["verdict"] = "hold"
    data["checks"][0]["status"] = "skipped"
    data["checks"][0]["exit"] = None
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "skipped without a skip_reason" in result.stdout


def test_skipped_check_with_reason_is_accepted_on_hold(tmp_path):
    data = _load()
    data["verdict"] = "hold"
    data["hold_reason"] = "skipped-check"
    data["checks"][0]["status"] = "skipped"
    data["checks"][0]["exit"] = None
    data["checks"][0]["skip_reason"] = "no suite configured"
    result = _run(tmp_path, data)
    assert result.returncode == 0, result.stdout


def test_budget_killed_check_cannot_record_exit_zero(tmp_path):
    data = _load()
    data["verdict"] = "halt"
    data["halt_reason"] = "budget"
    data["checks"][0]["status"] = "budget"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "budget-killed but records exit 0" in result.stdout


def test_hold_needs_a_typed_reason(tmp_path):
    data = _load()
    data["verdict"] = "hold"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "hold requires hold_reason" in result.stdout


def test_operator_wait_is_a_legitimate_hold(tmp_path):
    data = _load()
    data["verdict"] = "hold"
    data["hold_reason"] = "operator-wait"
    assert _run(tmp_path, data).returncode == 0


def test_hold_reason_must_match_the_evidence(tmp_path):
    data = _load()
    data["verdict"] = "hold"
    data["hold_reason"] = "skipped-check"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "needs a skipped check" in result.stdout


def test_mechanical_provenance_must_resolve(tmp_path):
    data = _load()
    data["verifier"] = "pytest"
    data["verifier_kind"] = "mechanical"
    data["verification_provenance"] = {"defined_by": "nowhere/spec.md",
                                       "authored_in_this_attempt": False}
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "names no existing" in result.stdout


def test_mechanical_provenance_naming_a_criterion_passes(tmp_path):
    data = _load()
    data["verifier"] = "pytest"
    data["verifier_kind"] = "mechanical"
    data["verification_provenance"] = {"defined_by": "A1",
                                       "authored_in_this_attempt": False}
    assert _run(tmp_path, data).returncode == 0


def test_self_authored_mechanical_check_is_refused(tmp_path):
    data = _load()
    data["verifier"] = "pytest"
    data["verifier_kind"] = "mechanical"
    data["verification_provenance"] = {"defined_by": "A1",
                                       "authored_in_this_attempt": True}
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "self-verification" in result.stdout


def test_capture_needs_a_real_digest_and_command(tmp_path):
    data = _load()
    data["checks"] = [{"name": "x", "command": "true", "exit": 0, "fresh": True,
                       "status": "ran", "output_digest": "sha256:x"}]
    data["artifacts"] = []
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "no substantive capture" in result.stdout


PLAN_EXAMPLE = ROOT / "exemplars" / "gate-verdict-plan-review.json"


def _load_plan():
    return json.loads(PLAN_EXAMPLE.read_text(encoding="utf-8"))


def test_plan_review_example_passes():
    result = subprocess.run([sys.executable, str(CHECK), str(PLAN_EXAMPLE)],
                            cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


def test_plan_review_needs_every_wl15_check(tmp_path):
    data = _load_plan()
    data["criteria"] = [c for c in data["criteria"] if c["id"] != "risk-halt"]
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "missing the WL-15 checks: risk-halt" in result.stdout


def test_plan_review_needs_a_coverage_basis(tmp_path):
    data = _load_plan()
    data["coverage"].pop("basis")
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "coverage.basis" in result.stdout


def test_plan_review_refuses_a_self_verifier(tmp_path):
    data = _load_plan()
    data["verifier"] = "self"
    data["exemption"] = {"check": "no second context", "claim": "Ready (unverified)"}
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "plan-review with verifier 'self'" in result.stdout


def test_plan_review_round_needs_the_round_pair(tmp_path):
    data = _load_plan()
    data["attempt"] = 2
    data["notes"] = "reviewed again"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "PRIOR ROUND" in result.stdout


def test_plan_review_round_may_exceed_one(tmp_path):
    data = _load_plan()
    data["attempt"] = 4
    data["notes"] = ("PRIOR ROUND 3 FAILED: ownership-order.\n"
                     "CHANGED: unit U2 now names its writer.")
    result = _run(tmp_path, data)
    assert result.returncode == 0, result.stdout


def test_verify_gate_keeps_the_one_refinement_bound(tmp_path):
    data = _load()
    data["attempt"] = 2
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "one-refinement bound" in result.stdout
