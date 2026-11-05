#!/usr/bin/env python3
"""Re-baseline trigger: compare a baseline identity with a current one.

Usage:
    python3 tooling/check_rebaseline.py --baseline PATH --current PATH [--json]

The identity is read from existing telemetry fields, not from a new schema:

- `run.model`, `run.harness`, `run.prompt_version`, `run.cache_epoch` from a
  telemetry record or from a baseline record that embeds a `run` block
  (`evals/harness-telemetry.schema.json`);
- `protocol.executor_model`, `protocol.grader_model`, `protocol.harness` and
  `protocol.current_ref` from a committed role-A/B summary
  (`evals/role-ab/results/*.json`, schema `role-ab-summary/*`).

Exit 0 when the identities match. Exit 1 when any identity field changed or
cannot be compared: a baseline is stale and a new paired campaign is required
before the new measurement may be compared with it. Exit 2 on unreadable or
unrecognised input. ASCII-only output.
"""

import argparse
import json
import sys
from pathlib import Path

FIELDS = ("model", "grader", "harness", "prompt_version", "cache_epoch")
NOT_RECORDED = "not-recorded"
UNVERIFIABLE = "unverifiable"


def identity(path):
    """Return (label, {field: value}) for a committed record."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("record is not a JSON object")
    schema = str(data.get("schema", ""))
    if schema.startswith("role-ab-summary/"):
        protocol = data.get("protocol") or {}
        ref = protocol.get("current_ref")
        return (data.get("experiment") or Path(path).stem), {
            "model": protocol.get("executor_model"),
            "grader": protocol.get("grader_model"),
            "harness": protocol.get("harness"),
            "prompt_version": ("agent-prompts@%s" % ref) if ref else None,
            "cache_epoch": None,
        }
    run = data.get("run")
    if not isinstance(run, dict):
        raise ValueError("record has neither a run block nor a role-ab protocol")
    return (data.get("baseline_id") or Path(path).stem), {
        "model": run.get("model"),
        "grader": data.get("grader_model"),
        "harness": run.get("harness"),
        "prompt_version": run.get("prompt_version"),
        "cache_epoch": run.get("cache_epoch"),
    }


def compare(baseline, current):
    problems = []
    notes = []
    for field in FIELDS:
        left, right = baseline.get(field), current.get(field)
        if left in (None, "", {}) and right in (None, "", {}):
            notes.append("%s is not recorded on either side" % field)
            continue
        if left in (None, "", {}) or right in (None, "", {}):
            missing = "baseline" if left in (None, "", {}) else "current"
            problems.append("%s changed or is %s: %s has no value, %s has %r"
                            % (field, UNVERIFIABLE, missing,
                               "current" if missing == "baseline" else "baseline",
                               right if missing == "baseline" else left))
            continue
        if field == "cache_epoch":
            left_keys = set(left)
            right_keys = set(right)
            for key in sorted(left_keys | right_keys):
                if key not in left or key not in right:
                    problems.append("cache_epoch.%s changed or is %s" %
                                    (key, UNVERIFIABLE))
                elif left[key] != right[key]:
                    problems.append("cache_epoch.%s changed: baseline %s != current %s"
                                    % (key, left[key], right[key]))
            continue
        if left != right:
            problems.append("%s changed: baseline %s != current %s"
                            % (field, left, right))
    return problems, notes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        baseline_label, baseline = identity(args.baseline)
        current_label, current = identity(args.current)
    except (OSError, ValueError) as exc:
        print("rebaseline: cannot read identity: %s" % exc)
        return 2
    problems, notes = compare(baseline, current)
    if args.json:
        print(json.dumps({"baseline": {"label": baseline_label,
                                       "identity": baseline},
                          "current": {"label": current_label,
                                      "identity": current},
                          "problems": problems, "notes": notes,
                          "rebaseline_required": bool(problems)}, indent=2))
    else:
        print("rebaseline: baseline %s (%s)" % (
            baseline_label, describe(baseline)))
        print("rebaseline: current  %s (%s)" % (
            current_label, describe(current)))
        for note in notes:
            print("NOTE " + note)
        for problem in problems:
            print("FAIL " + problem)
        if problems:
            print("rebaseline: %d identity difference(s); a new baseline is "
                  "required before this measurement may be compared"
                  % len(problems))
        else:
            print("rebaseline: identity matches; the baseline still applies")
    return 1 if problems else 0


def describe(identity_map):
    parts = []
    for field in ("model", "grader", "harness", "prompt_version"):
        value = identity_map.get(field)
        if value:
            parts.append("%s %s" % (field, value))
    return ", ".join(parts) or "no recorded identity"


if __name__ == "__main__":
    sys.exit(main())
