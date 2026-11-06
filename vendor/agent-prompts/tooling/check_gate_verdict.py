#!/usr/bin/env python3
"""Validate a gate verdict record (standards/verification-integrity.md).

A verdict is what a Review, Verify, acceptance, or run gate produced. This
checker enforces the mechanical half of VI-01..VI-11:

1. Shape: every required field, the enums, and the types are present and valid.
2. Identity: `verifier` is non-empty, differs from `implementer`, and `self`
   requires an exemption that forbids a pass (VI-02).
3. `pass` needs executed evidence: mode not off, no open or waived high/medium
   finding, every check ran fresh with exit 0, no stub or narration artifact,
   every MUST criterion met, empty `degraded`, coverage at or above the floor,
   and at least one substantive capture (VI-03..VI-09).
4. `fix` needs a cause, `hold` needs a reason, `halt` needs a taxonomy reason.
5. Every claim names an evidence id that exists in the record (VI-01).

Usage:
    python3 tooling/check_gate_verdict.py PATH [--json]

Exit 0 clean, 1 violations, 2 unreadable or structurally invalid input.
"""

import argparse
import json
import re
import sys
from pathlib import Path

CONTRACT = Path(__file__).resolve().parent.parent / "standards" / "gate-verdict.schema.json"

REQUIRED = ["schema", "verdict_id", "unit", "gate", "verdict", "mode",
            "attempt", "implementer", "verifier", "verifier_kind",
            "fresh_context", "artifacts", "checks", "criteria", "coverage",
            "findings", "degraded", "claims"]
OPTIONAL = ["exemption", "halt_reason", "hold_reason", "floor_rationale", "notes",
            "verification_provenance", "budget_summary"]
LISTS = ["artifacts", "checks", "criteria", "findings", "degraded", "claims"]
BLOCKING_SEVERITY = {"high", "medium"}
# WL-15: the six plan-review checks, as criterion ids in the record.
PLAN_REVIEW_CHECKS = ("goal", "request-coverage", "acceptance", "verification",
                      "ownership-order", "risk-halt")


def load_contract(path=CONTRACT):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def shape_errors(data, contract):
    errors = []
    for field in REQUIRED:
        if field not in data:
            errors.append("missing required field: %s" % field)
    allowed = set(REQUIRED) | set(OPTIONAL)
    for field in sorted(set(data) - allowed):
        errors.append("unknown field: %s" % field)
    enums = contract.get("enums", {})
    if data.get("gate") not in enums.get("gate", []):
        errors.append("gate not in vocabulary: %r" % (data.get("gate"),))
    if data.get("verdict") not in enums.get("verdict", []):
        errors.append("verdict not in vocabulary: %r" % (data.get("verdict"),))
    if data.get("mode") not in enums.get("mode", []):
        errors.append("mode not in vocabulary: %r" % (data.get("mode"),))
    if not isinstance(data.get("fresh_context"), bool):
        errors.append("fresh_context must be a boolean")
    attempt = data.get("attempt")
    gate = data.get("gate")
    if not isinstance(attempt, int) or isinstance(attempt, bool):
        errors.append("attempt must be an integer (WL-08: 0 or 1, or the "
                      "plan-review round number)")
    elif attempt < 0:
        errors.append("attempt %d is negative (WL-08)" % attempt)
    elif (gate != "plan-review" and attempt > 1
          and (data.get("verdict") != "halt"
               or data.get("halt_reason") != "over-bound")):
        errors.append("attempt %d exceeds the one-refinement bound (VI-13); "
                      "only gate plan-review may carry a round number, and only a "
                      "halt with reason over-bound may exceed it elsewhere"
                      % attempt)
    for field in LISTS:
        if field in data and not isinstance(data[field], list):
            errors.append("%s must be a list" % field)
    coverage = data.get("coverage")
    if not isinstance(coverage, dict):
        errors.append("coverage must be an object")
    else:
        for key in ("measured", "floor"):
            if not isinstance(coverage.get(key), (int, float)):
                errors.append("coverage.%s must be a number" % key)
    return errors


def item_errors(data, contract):
    """Per-item shape: artifacts, checks, criteria, findings, claims."""
    errors = []
    enums = contract.get("enums", {})
    floor_chars = contract.get("limits", {}).get("substance_floor_chars", 200)
    for index, artifact in enumerate(data.get("artifacts") or []):
        label = "artifacts[%d]" % index
        if not isinstance(artifact, dict):
            errors.append("%s must be an object" % label)
            continue
        if not artifact.get("path"):
            errors.append("%s.path is required" % label)
        if artifact.get("shape") not in enums.get("artifact_shape", []):
            errors.append("%s.shape not in vocabulary: %r"
                          % (label, artifact.get("shape")))
        chars = artifact.get("non_whitespace_chars")
        if not isinstance(chars, int) or chars < 0:
            errors.append("%s.non_whitespace_chars must be a non-negative integer"
                          % label)
        elif artifact.get("shape") == "ok" and chars < floor_chars:
            errors.append("%s reports shape ok below the substance floor (%d < %d)"
                          % (label, chars, floor_chars))
    for index, check in enumerate(data.get("checks") or []):
        label = "checks[%d]" % index
        if not isinstance(check, dict):
            errors.append("%s must be an object" % label)
            continue
        if not check.get("name"):
            errors.append("%s.name is required" % label)
        status = check.get("status", "ran")
        if status not in enums.get("check_status", []):
            errors.append("%s.status not in vocabulary: %r" % (label, status))
        if status == "skipped" and not str(check.get("skip_reason") or "").strip():
            errors.append("%s is skipped without a skip_reason (VI-03)" % label)
        if status == "budget" and check.get("exit") == 0:
            errors.append("%s is budget-killed but records exit 0 (VI-11)" % label)
        if not isinstance(check.get("fresh"), bool):
            errors.append("%s.fresh must be a boolean" % label)
        if "exit" in check and check["exit"] is not None and not isinstance(check["exit"], int):
            errors.append("%s.exit must be an integer or null" % label)
    for index, criterion in enumerate(data.get("criteria") or []):
        label = "criteria[%d]" % index
        if not isinstance(criterion, dict):
            errors.append("%s must be an object" % label)
            continue
        if not criterion.get("id"):
            errors.append("%s.id is required" % label)
        if criterion.get("severity") not in enums.get("criterion_severity", []):
            errors.append("%s.severity not in vocabulary: %r"
                          % (label, criterion.get("severity")))
        if criterion.get("state") not in enums.get("criterion_state", []):
            errors.append("%s.state not in vocabulary: %r"
                          % (label, criterion.get("state")))
    for index, finding in enumerate(data.get("findings") or []):
        label = "findings[%d]" % index
        if not isinstance(finding, dict):
            errors.append("%s must be an object" % label)
            continue
        if finding.get("severity") not in enums.get("severity", []):
            errors.append("%s.severity not in vocabulary: %r"
                          % (label, finding.get("severity")))
        if finding.get("state") not in enums.get("finding_state", []):
            errors.append("%s.state not in vocabulary: %r"
                          % (label, finding.get("state")))
    for index, claim in enumerate(data.get("claims") or []):
        if not isinstance(claim, dict) or not claim.get("claim"):
            errors.append("claims[%d] must be an object with a claim" % index)
    return errors


DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def defined_by_resolves(data, defined_by):
    """A provenance pointer must name something this record or the repo can check."""
    if defined_by in evidence_ids(data):
        return True
    if any(str(c.get("command")) == defined_by for c in data.get("checks") or []
           if isinstance(c, dict)):
        return True
    root = Path(__file__).resolve().parent.parent
    return (root / defined_by).exists()


def evidence_ids(data):
    ids = set()
    for artifact in data.get("artifacts") or []:
        if isinstance(artifact, dict) and artifact.get("path"):
            ids.add(str(artifact["path"]))
    for check in data.get("checks") or []:
        if isinstance(check, dict) and check.get("name"):
            ids.add(str(check["name"]))
    for criterion in data.get("criteria") or []:
        if isinstance(criterion, dict) and criterion.get("id"):
            ids.add(str(criterion["id"]))
    for finding in data.get("findings") or []:
        if isinstance(finding, dict) and finding.get("id"):
            ids.add(str(finding["id"]))
    return ids


def semantic_errors(data, contract):
    """VI-01..VI-11: what the verdict may claim given its evidence."""
    errors = []
    verdict = data.get("verdict")
    ids = evidence_ids(data)
    for index, claim in enumerate(data.get("claims") or []):
        if not isinstance(claim, dict):
            continue
        evidence = claim.get("evidence")
        if not evidence:
            errors.append("claims[%d] names no evidence" % index)
            continue
        if isinstance(evidence, list):
            missing = [str(item) for item in evidence if str(item) not in ids]
        else:
            missing = [] if str(evidence) in ids else [str(evidence)]
        for item in missing:
            errors.append("claims[%d] references unknown evidence id: %s"
                          % (index, item))

    verifier = str(data.get("verifier") or "").strip()
    implementer = str(data.get("implementer") or "").strip()
    if not verifier:
        errors.append("verifier is empty: an anonymous pass is a fabricated attestation")
    elif verifier == implementer:
        errors.append("verifier equals implementer: the author is never the sole verifier")
    elif verifier == "self" and not data.get("exemption"):
        errors.append("verifier 'self' requires an exemption record")

    kind = data.get("verifier_kind")
    if kind not in contract.get("enums", {}).get("verifier_kind", []):
        errors.append("verifier_kind not in vocabulary: %r" % (kind,))
    elif kind == "mechanical":
        provenance = data.get("verification_provenance")
        if not isinstance(provenance, dict) or not provenance:
            errors.append("a mechanical verifier requires verification_provenance (VI-02)")
        else:
            defined_by = str(provenance.get("defined_by") or "").strip()
            if not defined_by:
                errors.append("verification_provenance.defined_by is required (VI-02)")
            elif not defined_by_resolves(data, defined_by):
                errors.append("verification_provenance.defined_by %r names no existing "
                              "path, criterion id, or command (VI-02)" % defined_by)
            if provenance.get("authored_in_this_attempt") is not False:
                errors.append("a check authored in this attempt is self-verification, "
                              "not a verifier (VI-02)")

    checks = [c for c in (data.get("checks") or []) if isinstance(c, dict)]
    artifacts = [a for a in (data.get("artifacts") or []) if isinstance(a, dict)]
    criteria = [c for c in (data.get("criteria") or []) if isinstance(c, dict)]
    findings = [f for f in (data.get("findings") or []) if isinstance(f, dict)]
    degraded = data.get("degraded") or []

    blocking = [f for f in findings
                if f.get("severity") in BLOCKING_SEVERITY
                and f.get("state") in {"open", "waived"}]
    failed = [c for c in checks
              if c.get("status", "ran") != "ran"
              or c.get("exit") not in (0,)
              or c.get("fresh") is not True]
    must_unmet = [c for c in criteria
                  if c.get("severity") == "MUST" and c.get("state") != "met"]
    substantive = [c for c in checks
                   if c.get("status", "ran") == "ran" and c.get("exit") == 0
                   and str(c.get("command") or "").strip()
                   and str(c.get("command") or "").strip() not in ("true", ":", "echo")
                   and DIGEST.match(str(c.get("output_digest") or ""))]
    stub = [a for a in artifacts
            if a.get("shape") not in ("ok",)]

    if verdict == "pass":
        if data.get("mode") == "off":
            errors.append("pass with mode off: a gate that did not run cannot pass")
        if verifier == "self":
            errors.append("pass with verifier 'self': an exemption closes as Ready (unverified)")
        for finding in blocking:
            errors.append("pass with %s finding %s still %s"
                          % (finding.get("severity"), finding.get("id"),
                             finding.get("state")))
        for check in failed:
            errors.append("pass with non-passing check: %s (status=%s exit=%r fresh=%r)"
                          % (check.get("name"), check.get("status", "ran"),
                             check.get("exit"), check.get("fresh")))
        for artifact in stub:
            errors.append("pass with %s artifact: %s"
                          % (artifact.get("shape"), artifact.get("path")))
        for criterion in must_unmet:
            errors.append("pass with unmet MUST criterion: %s (%s)"
                          % (criterion.get("id"), criterion.get("state")))
        if degraded:
            errors.append("pass with a degraded check set: report partial and refuse pass")
        if not substantive and not [a for a in artifacts if a.get("shape") == "ok"]:
            errors.append("pass with no substantive capture: nothing was inspected")
        coverage = data.get("coverage") or {}
        measured, floor = coverage.get("measured"), coverage.get("floor")
        if isinstance(measured, (int, float)) and isinstance(floor, (int, float)):
            default_floor = contract.get("limits", {}).get("default_coverage_floor", 95)
            if floor < default_floor and not data.get("floor_rationale"):
                errors.append("coverage floor %s is below the default %s without a rationale"
                              % (floor, default_floor))
            if measured < floor:
                errors.append("coverage %s is below the declared floor %s" % (measured, floor))
    elif verdict == "fix":
        if not (blocking or failed or must_unmet):
            errors.append("fix without a cause: no open finding, failing check, or unmet MUST criterion")
    elif verdict == "hold":
        allowed = contract.get("enums", {}).get("hold_reason", [])
        reason = data.get("hold_reason")
        if reason not in allowed:
            errors.append("hold requires hold_reason from the enum %s, got %r"
                          % (allowed, reason))
        elif reason == "skipped-check" and not [c for c in checks
                                                if c.get("status", "ran") == "skipped"]:
            errors.append("hold_reason skipped-check needs a skipped check")
        elif reason == "degraded" and not degraded:
            errors.append("hold_reason degraded needs a degraded entry")
        elif reason == "mode-off" and data.get("mode") != "off":
            errors.append("hold_reason mode-off needs mode off")
        elif reason == "exemption" and not data.get("exemption"):
            errors.append("hold_reason exemption needs an exemption record")
    elif verdict == "halt":
        allowed = contract.get("enums", {}).get("halt_reason", [])
        if data.get("halt_reason") not in allowed:
            errors.append("halt requires halt_reason from the taxonomy, got %r"
                          % (data.get("halt_reason"),))
    if data.get("mode") == "off" and verdict == "pass":
        errors.append("mode off cannot carry any pass verdict")

    gate = data.get("gate")
    if gate == "verify" and not checks:
        errors.append("verify gate record carries no check: name the command that proves it")
    if gate == "acceptance" and not [c for c in criteria if c.get("severity") == "MUST"]:
        errors.append("acceptance gate record carries no MUST criterion taken from the request")
    if gate == "plan-review":
        ids = {str(c.get("id")) for c in criteria}
        missing = [name for name in PLAN_REVIEW_CHECKS if name not in ids]
        if missing:
            errors.append("plan-review gate record is missing the WL-15 checks: %s"
                          % ", ".join(missing))
        basis = str((data.get("coverage") or {}).get("basis") or "").strip()
        if not basis:
            errors.append("plan-review gate record needs coverage.basis naming the "
                          "spec sections inspected (WL-15)")
        if verifier == "self":
            errors.append("plan-review with verifier 'self': the WL-15 checklist is a "
                          "mechanical verifier with provenance, not an exemption")
        round_number = data.get("attempt")
        if (isinstance(round_number, int) and not isinstance(round_number, bool)
                and round_number >= 1):
            notes = str(data.get("notes") or "")
            if "PRIOR ROUND" not in notes or "CHANGED:" not in notes:
                errors.append("plan-review round %d needs the PRIOR ROUND <n> FAILED / "
                              "CHANGED pair (VI-12, WL-15)" % round_number)
    if gate == "review" and not (findings or criteria or data.get("claims")):
        errors.append("review gate record names nothing inspected: list findings or criteria")
    return errors


def check(data, contract=None):
    contract = contract if contract is not None else load_contract()
    errors = shape_errors(data, contract)
    if errors:
        return errors
    return item_errors(data, contract) + semantic_errors(data, contract)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    path = Path(args.path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("gate-verdict: cannot read %s: %s" % (path, exc))
        return 2
    if not isinstance(data, dict):
        print("gate-verdict: record must be a JSON object")
        return 2
    contract = load_contract()
    if not contract:
        print("gate-verdict: cannot read contract %s" % CONTRACT)
        return 2
    errors = check(data, contract)
    if args.json:
        print(json.dumps({"path": str(path), "verdict": data.get("verdict"),
                          "violations": errors}, indent=2))
    else:
        for error in errors:
            print("FAIL " + error)
        print("gate-verdict: %s/%s on %s, %d violation(s)"
              % (data.get("verdict"), data.get("gate"), data.get("unit"),
                 len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
