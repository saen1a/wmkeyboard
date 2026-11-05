#!/usr/bin/env python3
"""Validate a runtime admission record (standards/agent-adapter.md).

Enforces the mechanical half of AD-02, AD-03, AD-06, AD-09, and AD-10:

1. Shape: required fields, enums, ISO dates, and no unknown keys.
2. Capability state: `supported` carries evidence and a `checked` date inside the
   evidence window; `degraded` names the narrower behavior; `unsupported` names
   the refusal; `unknown` records what the verification attempt observed.
3. Admission is recomputed fail-closed and compared with the recorded value:
   a required `unknown` or `unsupported` capability refuses admission, and the
   refusal is named.
5. AD-12: every record declares `loop_gate`, and a `supported` claim names the
   check that enforces it.
4. The projection block may not rely on a capability marked `unsupported`.

Usage:
    python3 tooling/check_admission.py PATH [--check-only] [--json] [--today YYYY-MM-DD]

`--today` exists for deterministic tests; the default is the system date.
Exit 0 clean, 1 violations, 2 unreadable or structurally invalid input.
"""

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

CONTRACT = Path(__file__).resolve().parent.parent / "standards" / "agent-admission.schema.json"
REQUIRED = ["schema", "runtime", "runtime_version", "checked",
            "required_features", "capabilities", "admission"]
OPTIONAL = ["degraded_behavior", "refusals", "projection", "notes", "evidence"]


def load_contract(path=CONTRACT):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def parse_date(value):
    if not isinstance(value, str) or len(value) != 10:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def shape_errors(data, contract, today):
    errors = []
    for field in REQUIRED:
        if field not in data:
            errors.append("missing required field: %s" % field)
    for field in sorted(set(data) - set(REQUIRED) - set(OPTIONAL)):
        errors.append("unknown field: %s" % field)
    if data.get("schema") != contract.get("contract"):
        errors.append("schema must be %r" % (contract.get("contract"),))
    enums = contract.get("enums", {})
    if data.get("admission") not in enums.get("admission", []):
        errors.append("admission not in vocabulary: %r" % (data.get("admission"),))
    if not isinstance(data.get("runtime"), str) or not data.get("runtime").strip():
        errors.append("runtime must be a non-empty string")
    if not isinstance(data.get("runtime_version"), str) or not data.get("runtime_version").strip():
        errors.append("runtime_version must be a non-empty string")
    checked = parse_date(data.get("checked"))
    if checked is None:
        errors.append("checked must be an ISO date")
    elif checked > today:
        errors.append("checked is in the future")
    features = data.get("required_features")
    if not isinstance(features, list) or not features:
        errors.append("required_features must be a non-empty list")
    else:
        for index, feature in enumerate(features):
            if not isinstance(feature, str) or not feature.strip():
                errors.append("required_features[%d] must be a non-empty string" % index)
    if not isinstance(data.get("capabilities"), dict) or not data.get("capabilities"):
        errors.append("capabilities must be a non-empty object")
    return errors


def capability_errors(data, contract, today):
    errors = []
    enums = contract.get("enums", {}).get("support", [])
    window = contract.get("limits", {}).get("max_evidence_age_days", 365)
    capabilities = data.get("capabilities")
    if not isinstance(capabilities, dict):
        return ["capabilities must be an object"]
    for name, entry in sorted(capabilities.items()):
        label = "capabilities.%s" % name
        if not isinstance(entry, dict):
            errors.append("%s must be an object" % label)
            continue
        support = entry.get("support")
        if support not in enums:
            errors.append("%s.support not in vocabulary: %r" % (label, support))
            continue
        checked = parse_date(entry.get("checked"))
        if entry.get("checked") is not None and checked is None:
            errors.append("%s.checked must be an ISO date" % label)
        if checked is not None:
            if checked > today:
                errors.append("%s.checked is in the future" % label)
            elif support == "supported" and (today - checked).days > window:
                errors.append("%s claims supported with evidence older than %d days"
                              % (label, window))
        if support == "supported":
            if not entry.get("evidence"):
                errors.append("%s is supported without an evidence pointer" % label)
            if checked is None:
                errors.append("%s is supported without a checked date" % label)
        elif support == "degraded":
            if not str(entry.get("degraded_behavior") or "").strip():
                errors.append("%s is degraded without a named degraded_behavior" % label)
        elif support == "unsupported":
            if not str(entry.get("refusal") or "").strip():
                errors.append("%s is unsupported without a named refusal" % label)
        elif support == "unknown":
            if not str(entry.get("attempted") or "").strip():
                errors.append("%s is unknown without a recorded verification attempt"
                              % label)
    return errors


def admission_result(data, today=None, window=365):
    """AD-03: compute admission fail-closed, return (result, reasons).

    A `supported` claim whose `checked` date is missing, stale or in the future is
    treated as `unknown` here, so the computed result cannot contradict the
    violations reported beside it.
    """
    today = today or date.today()
    capabilities = data.get("capabilities") or {}
    required = data.get("required_features") or []
    reasons = []
    refused = False
    for feature in required:
        if not isinstance(feature, str) or not feature.strip():
            reasons.append("%r: required feature is not a name" % (feature,))
            refused = True
            continue
        entry = capabilities.get(feature)
        if not isinstance(entry, dict):
            reasons.append("%s: required but not declared" % feature)
            refused = True
            continue
        support = entry.get("support")
        checked = parse_date(entry.get("checked"))
        if support == "supported" and (checked is None or checked > today
                                       or (today - checked).days > window):
            support = "unknown"
        if support in ("unknown", "unsupported"):
            reasons.append("%s: %s" % (feature, support))
            refused = True
        elif support == "degraded":
            behavior = str(entry.get("degraded_behavior") or "").strip()
            if not behavior:
                reasons.append("%s: degraded without a named behavior" % feature)
                refused = True
    return ("refused" if refused else "admitted"), reasons


def semantic_errors(data):
    errors = []
    computed, reasons = admission_result(data)
    recorded = data.get("admission")
    if computed != recorded:
        errors.append("admission is %r but the fail-closed computation says %r (%s)"
                      % (recorded, computed, "; ".join(reasons) or "no reason"))
    if computed == "refused":
        named = data.get("refusals") or []
        if not named:
            errors.append("refused admission must name the refusing capability in refusals")
        for reason in reasons:
            feature = reason.split(":", 1)[0].strip()
            if not any(str(item).split(":", 1)[0].strip() == feature for item in named):
                errors.append("refusal does not name required feature: %s" % feature)
    projection = data.get("projection")
    if projection is not None:
        if not isinstance(projection, dict):
            errors.append("projection must be an object")
        else:
            capabilities = data.get("capabilities") or {}
            for role, tools in sorted(projection.items()):
                if not isinstance(tools, list):
                    errors.append("projection.%s must be a list of tool names" % role)
                    continue
                for tool in tools:
                    entry = capabilities.get(str(tool))
                    if not isinstance(entry, dict):
                        errors.append("projection.%s uses undeclared capability %r"
                                      % (role, tool))
                    elif entry.get("support") == "unsupported":
                        errors.append("projection.%s uses unsupported capability %r"
                                      % (role, tool))
    return errors


LOOP_GATE = "loop_gate"


def loop_gate_errors(data):
    """AD-12: the loop gate is a declared capability with named evidence."""
    errors = []
    capabilities = data.get("capabilities") or {}
    if LOOP_GATE not in capabilities:
        errors.append("capabilities.loop_gate is required: a projection must say "
                      "whether the runtime enforces the plan-review gate (AD-12)")
        return errors
    cell = capabilities.get(LOOP_GATE) or {}
    support = cell.get("support")
    root = Path(__file__).resolve().parent.parent
    if support in ("supported", "degraded"):
        field = "evidence" if support == "supported" else "degraded_behavior"
        text = str(cell.get(field) or "")
        if not text.strip():
            errors.append("loop_gate %s needs %s (AD-02)" % (support, field))
            return errors
        if support == "degraded" and not any(
                word in text.lower() for word in ("ci", "gate", "hook", "check")):
            errors.append("loop_gate degraded must name what carries the gate "
                          "instead (AD-12), got %r" % text)
            return errors
        # A claim is a path, not a word: at least one file-like token in the
        # evidence must exist in this tree (AD-12). "the prose says so" passes
        # nothing.
        tokens = re.findall(r"[A-Za-z0-9_./-]+\.(?:py|sh|json|ya?ml|md)", text)
        resolved = [token for token in tokens
                    if not token.startswith("/") and ".." not in Path(token).parts
                    and (root / token).is_file()]
        if not resolved:
            errors.append("loop_gate %s names no check that exists: evidence must "
                          "cite a file in this tree such as "
                          "tooling/check_loop_gate.py (AD-12), got %r"
                          % (support, text))
    return errors


def check(data, contract=None, today=None):
    contract = contract if contract is not None else load_contract()
    today = today or date.today()
    errors = shape_errors(data, contract, today)
    if errors:
        return errors
    return (capability_errors(data, contract, today) + semantic_errors(data)
            + loop_gate_errors(data))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--today", default=None, help="ISO date for deterministic runs")
    args = parser.parse_args(argv)
    today = parse_date(args.today) if args.today else date.today()
    if today is None:
        print("admission: --today must be an ISO date")
        return 2
    path = Path(args.path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("admission: cannot read %s: %s" % (path, exc))
        return 2
    if not isinstance(data, dict):
        print("admission: record must be a JSON object")
        return 2
    contract = load_contract()
    if not contract:
        print("admission: cannot read contract %s" % CONTRACT)
        return 2
    errors = check(data, contract, today)
    computed, reasons = (admission_result(data, today)
                         if isinstance(data.get("capabilities"), dict)
                         else ("refused", []))
    if args.json:
        print(json.dumps({"path": str(path), "runtime": data.get("runtime"),
                          "admission": computed, "reasons": reasons,
                          "violations": errors}, indent=2))
    else:
        for error in errors:
            print("FAIL " + error)
        print("admission: %s %s/%s, %s, %d violation(s)"
              % (data.get("runtime"), data.get("admission"), computed,
                 "; ".join(reasons) or "no refusing capability", len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
