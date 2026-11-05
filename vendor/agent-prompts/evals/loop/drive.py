#!/usr/bin/env python3
"""Exercise the workflow-loop guards against real verdict records.

`standards/workflow-loop.md` states the transitions; `verification-integrity.md`
states what a record must contain. Neither is executable on its own, so this
exercise drives the guards the way the loop does:

    Plan -> PlanReview -> Implement -> Review -> Fix -> Verify -> Push

Every scenario is a transition decision. The guard reads a verdict record
(`standards/gate-verdict.schema.json`) and answers `accept` or `reject: <why>`.
The scenario's expected answer is declared next to it, so a guard that silently
loosens fails the exercise.

What this proves: the loop's guards reject the ways a unit pretends to be
done -- a spec that never passed its plan review, a review without a record, an
open high finding, a skipped check, a stub artifact, a self-signed verification,
coverage below the floor -- and reject a finalize without the operator's `go` or
without publication proof. It also proves the bounds hold: a second spec-gap
return is refused, a code gate gets one refinement, and a plan-review round that
changes nothing is stalled.

What this does not prove: that an agent follows the loop. It proves the written
guards are consistent with the record contract and with each other.

Usage:

    python3 evals/loop/drive.py            # run every scenario
    python3 evals/loop/drive.py --verify    # same, quiet on success, for the gate
    python3 evals/loop/drive.py --json      # machine-readable summary

Exit 0 when every scenario matches its expectation, 1 otherwise. ASCII only, no
network, no writes.
"""

import argparse
import copy
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tooling"))

import check_gate_verdict  # noqa: E402  (path set above)

EXAMPLE = ROOT / "exemplars" / "gate-verdict-example.json"
PLAN_EXAMPLE = ROOT / "exemplars" / "gate-verdict-plan-review.json"
CONTRACT = check_gate_verdict.load_contract()
BLOCKING = {"high", "medium"}


def record(**overrides):
    """A valid pass record from the exemplar, with fields overridden."""
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data = copy.deepcopy(data)
    data.update(overrides)
    return data


def plan_record(**overrides):
    """A valid plan-review pass record, with fields overridden."""
    data = json.loads(PLAN_EXAMPLE.read_text(encoding="utf-8"))
    data = copy.deepcopy(data)
    data.update(overrides)
    return data


def record_errors(data):
    return check_gate_verdict.check(data, CONTRACT)


def blocking_findings(data):
    return [f for f in data.get("findings") or []
            if isinstance(f, dict) and f.get("severity") in BLOCKING
            and f.get("state") in {"open", "waived"}]


# --- guards ---------------------------------------------------------------

def guard_plan_to_plan_review(spec):
    """WL-02: only a decision-complete spec reaches the plan-review gate."""
    required = ("goal", "units", "acceptance", "verification")
    missing = [key for key in required if not spec.get(key)]
    if missing:
        return "reject: decision-complete spec is missing %s" % ", ".join(missing)
    return "accept"


def guard_plan_review_to_implement(verdict):
    """WL-15: the plan gate passes only on a clean plan-review record."""
    if not verdict:
        return "reject: no plan-review verdict record, a prose approval is not a gate"
    if verdict.get("gate") != "plan-review":
        return "reject: record is a %r gate, not plan-review" % verdict.get("gate")
    errors = record_errors(verdict)
    if errors:
        return "reject: invalid record: %s" % errors[0]
    if verdict.get("verdict") != "pass":
        return "reject: plan-review verdict is %r" % verdict.get("verdict")
    found = blocking_findings(verdict)
    if found:
        return "reject: open high/medium plan finding %s" % found[0].get("id")
    return "accept"


def guard_plan_review_round(previous, notes):
    """WL-15 + VI-12: a round must state a new change, or it is stalled."""
    match = re.search(r"(?m)CHANGED:[ \t]*(.*)", str(notes or ""))
    if not match:
        return "reject: no CHANGED line (VI-12)"
    changed = match.group(1).strip()
    if not changed:
        return "reject: empty CHANGED line (VI-12)"
    if changed == str(previous or "").strip():
        return "reject: stalled: the round repeats the previous change (WL-15)"
    return "accept"


def guard_review_to_verify(verdict):
    """WL-02: no open high/medium finding, and the record proves the review ran."""
    if not verdict:
        return "reject: no verdict record, a prose pass is not a review"
    errors = record_errors(verdict)
    if errors:
        return "reject: invalid record: %s" % errors[0]
    if verdict.get("verdict") != "pass":
        return "reject: review verdict is %r" % verdict.get("verdict")
    found = blocking_findings(verdict)
    if found:
        return "reject: open high/medium finding %s" % found[0].get("id")
    return "accept"


def guard_verify_to_ready(verdict):
    """WL-02 + VI-03/VI-08/VI-13: the record must be a pass with no gap."""
    if not verdict:
        return "reject: no verdict record"
    errors = record_errors(verdict)
    if errors:
        return "reject: invalid record: %s" % errors[0]
    attempt = verdict.get("attempt")
    if attempt is None:
        return "reject: no attempt field (VI-13)"
    if attempt > 1:
        return "reject: attempt %d exceeds the one-refinement bound (VI-13)" % attempt
    skipped = [c for c in verdict.get("checks") or []
               if isinstance(c, dict) and c.get("status", "ran") != "ran"]
    if skipped:
        return "reject: skipped check %r (VI-03)" % skipped[0].get("name")
    stubs = [a for a in verdict.get("artifacts") or []
             if isinstance(a, dict) and a.get("shape") != "ok"]
    if stubs:
        return "reject: %s artifact %r (VI-06)" % (stubs[0].get("shape"),
                                                   stubs[0].get("path"))
    if verdict.get("verifier") == verdict.get("implementer"):
        return "reject: the author is the verifier (VI-02)"
    coverage = verdict.get("coverage") or {}
    if (isinstance(coverage.get("measured"), (int, float))
            and isinstance(coverage.get("floor"), (int, float))
            and coverage["measured"] < coverage["floor"]):
        return "reject: coverage %s below floor %s (VI-08)" % (
            coverage["measured"], coverage["floor"])
    if verdict.get("verdict") != "pass":
        return "reject: verdict is %r" % verdict.get("verdict")
    return "accept"


def guard_verify_to_fix(verdict):
    if not verdict:
        return "reject: no verdict record"
    if record_errors(verdict):
        return "reject: invalid record: %s" % record_errors(verdict)[0]
    if verdict.get("verdict") != "fix":
        return "reject: a failing check must return fix, got %r" % verdict.get("verdict")
    if not verdict.get("findings") and not verdict.get("criteria"):
        return "reject: fix without a named cause (VI-12)"
    return "accept"


def guard_fix_to_plan(returns):
    """WL-07: one spec-gap return per unit, then HALT."""
    if returns > 1:
        return "reject: second spec-gap return is HALT (WL-07)"
    return "accept"


def guard_push(verdict, operator_go, publication_proof):
    """WL-10 + WL-14: operator go, the record, and publication proof."""
    if not operator_go:
        return "reject: no operator go"
    if not verdict:
        return "reject: no verdict record attached to the finalize"
    if record_errors(verdict):
        return "reject: invalid record: %s" % record_errors(verdict)[0]
    if not publication_proof:
        return "reject: Git finalize without publication proof (WL-14)"
    return "accept"


# --- scenarios ------------------------------------------------------------

def scenarios():
    clean_review = record(gate="review", attempt=0)
    fix_record = record(verdict="fix", gate="verify", attempt=0)
    fix_record["checks"][0]["exit"] = 1
    fix_record["criteria"][0]["state"] = "unmet"
    complete_spec = {"goal": "g", "units": ["U1"], "acceptance": ["A1"],
                     "verification": ["make test"]}
    partial_spec = {"goal": "g", "units": ["U1"], "acceptance": [], "verification": []}

    plan_clean = plan_record()
    plan_open_high = plan_record(findings=[{"id": "F-4", "severity": "high",
                                            "state": "open",
                                            "file_line": "spec.md:9",
                                            "evidence": "verification check does not exist"}])
    plan_round_without_change = "PRIOR ROUND 2 FAILED: ownership-order."
    plan_round_repeat = "PRIOR ROUND 2 FAILED: ownership-order.\nCHANGED: added U3"

    # Each entry: (name, expected decision, expected reason fragment, callable).
    # The reason fragment is what keeps a scenario honest: a guard that starts
    # rejecting for an unrelated reason fails the exercise instead of passing.
    return [
        ("plan_complete_spec", "accept", "",
         lambda: guard_plan_to_plan_review(complete_spec)),
        ("plan_missing_acceptance", "reject", "acceptance",
         lambda: guard_plan_to_plan_review(partial_spec)),
        ("plan_review_clean", "accept", "",
         lambda: guard_plan_review_to_implement(plan_clean)),
        ("plan_review_without_record", "reject", "no plan-review verdict",
         lambda: guard_plan_review_to_implement(None)),
        ("plan_review_rejects_a_diff_record", "reject", "not plan-review",
         lambda: guard_plan_review_to_implement(record(gate="review", attempt=0))),
        ("plan_review_open_high_finding", "reject", "still open",
         lambda: guard_plan_review_to_implement(plan_open_high)),
        ("plan_review_round_states_a_change", "accept", "",
         lambda: guard_plan_review_round(
             "added U2", plan_round_repeat)),
        ("plan_review_round_repeats_a_change", "reject", "stalled",
         lambda: guard_plan_review_round(
             "added U3", "PRIOR ROUND 3 FAILED: ownership-order.\nCHANGED: added U3")),
        ("plan_review_round_without_a_change_line", "reject", "no CHANGED line",
         lambda: guard_plan_review_round("goal: v1", plan_round_without_change)),
        ("review_clean_record", "accept", "",
         lambda: guard_review_to_verify(clean_review)),
        ("review_without_record", "reject", "no verdict record",
         lambda: guard_review_to_verify(None)),
        ("verify_pass_complete", "accept", "",
         lambda: guard_verify_to_ready(record(attempt=1))),
        ("verify_fix_cannot_reach_ready", "reject", "verdict is 'fix'",
         lambda: guard_verify_to_ready(fix_record)),
        ("verify_failure_enters_fix", "accept", "",
         lambda: guard_verify_to_fix(fix_record)),
        ("fix_first_spec_gap_return", "accept", "",
         lambda: guard_fix_to_plan(1)),
        ("fix_second_spec_gap_return", "reject", "WL-07",
         lambda: guard_fix_to_plan(2)),
        ("push_without_operator_go", "reject", "operator go",
         lambda: guard_push(record(attempt=1), False, True)),
        ("push_without_verdict_record", "reject", "no verdict record",
         lambda: guard_push(None, True, True)),
        ("push_without_publication_proof", "reject", "publication proof",
         lambda: guard_push(record(attempt=1), True, False)),
        ("push_with_go_and_proof", "accept", "",
         lambda: guard_push(record(attempt=1), True, True)),
    ]


def run():
    results = []
    for name, expected, expected_reason, decide in scenarios():
        decision = decide()
        actual = decision.split(":", 1)[0]
        reason_ok = (expected == "accept") or (expected_reason in decision)
        results.append({"scenario": name, "expected": expected,
                        "actual": actual, "reason": expected_reason,
                        "detail": decision,
                        "ok": actual == expected and reason_ok})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true",
                        help="quiet on success; the gate mode")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    results = run()
    failures = [r for r in results if not r["ok"]]
    if args.json:
        print(json.dumps({"scenarios": results, "failures": len(failures)}, indent=2))
    elif not args.verify:
        for item in results:
            print("%s %-34s expected=%-6s %s"
                  % ("OK  " if item["ok"] else "FAIL", item["scenario"],
                     item["expected"], item["detail"]))
        print("loop-guards: %d scenarios, %d failure(s)" % (len(results), len(failures)))
    else:
        for item in failures:
            print("FAIL %s: expected %s, got %s (%s)"
                  % (item["scenario"], item["expected"], item["actual"],
                     item["detail"]))
        if not failures:
            print("loop-guards: %d scenarios, 0 failure(s)" % len(results))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
