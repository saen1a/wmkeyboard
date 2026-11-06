"""Tests for the loop guard exercise (evals/loop/drive.py)."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRIVE = ROOT / "evals" / "loop" / "drive.py"

spec = importlib.util.spec_from_file_location("loop_drive", DRIVE)
drive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drive)


def test_every_scenario_matches_its_expectation():
    results = drive.run()
    failures = [item for item in results if not item["ok"]]
    assert not failures, failures


def test_rejections_name_their_reason():
    for item in drive.run():
        if item["expected"] == "reject":
            assert item["reason"], item["scenario"]
            assert item["reason"] in item["detail"], item


def test_fix_verdict_cannot_reach_ready():
    fix_record = drive.record(verdict="fix", gate="verify", attempt=0)
    fix_record["checks"][0]["exit"] = 1
    fix_record["criteria"][0]["state"] = "unmet"
    decision = drive.guard_verify_to_ready(fix_record)
    assert decision.startswith("reject")
    assert "verdict is 'fix'" in decision


def test_second_spec_gap_return_is_halt():
    assert drive.guard_fix_to_plan(1) == "accept"
    assert drive.guard_fix_to_plan(2).startswith("reject")
    assert "WL-07" in drive.guard_fix_to_plan(2)


def test_finalize_needs_all_three():
    good = drive.record(attempt=1)
    assert drive.guard_push(good, True, True) == "accept"
    assert drive.guard_push(good, False, True).startswith("reject")
    assert drive.guard_push(good, True, False).startswith("reject")
    assert drive.guard_push(None, True, True).startswith("reject")


def test_plan_review_gate_blocks_implement():
    assert drive.guard_plan_review_to_implement(None).startswith("reject")
    diff = drive.record(gate="review", attempt=0)
    assert "not plan-review" in drive.guard_plan_review_to_implement(diff)
    assert drive.guard_plan_review_to_implement(drive.plan_record()) == "accept"


def test_plan_review_round_needs_a_new_change():
    assert drive.guard_plan_review_round("a", "PRIOR ROUND 1 FAILED: goal.\nCHANGED: a") \
        .startswith("reject")
    assert drive.guard_plan_review_round(
        "a", "PRIOR ROUND 1 FAILED: goal.\nCHANGED: b") == "accept"
    assert drive.guard_plan_review_round("a", "PRIOR ROUND 1 FAILED: goal.") \
        .startswith("reject")
