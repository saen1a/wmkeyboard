#!/usr/bin/env python3
"""Validate a review/verify findings ledger (WL-13).

Usage:
    python3 tooling/check_findings_ledger.py PATH [--require-clean] [--json]

`--require-clean` fails when any high or medium finding is still `open`.
Exit 0 clean, 1 violations, 2 unreadable input.
"""

import argparse
import json
import re
import sys
from pathlib import Path

COLUMNS = ["finding_id", "severity", "unit", "file_line", "evidence",
           "acceptance_impact", "owner", "state", "round", "decision"]
SEVERITY = {"high", "medium", "low"}
STATE = {"open", "fixed", "waived"}


def parse(path):
    errors = []
    text = Path(path).read_text(encoding="utf-8")
    header = next((line for line in text.splitlines()
                   if line.startswith("| finding_id |")), "")
    columns = [cell.strip() for cell in header.strip().strip("|").split("|")]
    if columns != COLUMNS:
        return [], ["header does not match WL-13"]
    rows = []
    for line in text.splitlines():
        if not line.startswith("|") or line.startswith("| finding_id |"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(set(cell) <= set("-: ") for cell in cells):
            continue
        if len(cells) != len(COLUMNS):
            errors.append("row has %d cells, expected %d" % (len(cells), len(COLUMNS)))
            continue
        rows.append(dict(zip(COLUMNS, cells)))
    if not rows:
        errors.append("ledger has no finding row")
    seen = []
    for row in rows:
        label = row.get("finding_id", "?")
        if not re.match(r"^F-[1-9][0-9]*$", label):
            errors.append("%s is not a finding id" % label)
        if label in seen:
            errors.append("duplicate finding id: %s" % label)
        seen.append(label)
        if row["severity"] not in SEVERITY:
            errors.append("%s severity is not high|medium|low" % label)
        if row["state"] not in STATE:
            errors.append("%s state is not open|fixed|waived" % label)
        if row["state"] in ("fixed", "waived") and not row["evidence"].strip():
            errors.append("%s is %s without evidence" % (label, row["state"]))
        if row["state"] == "waived" and not row["decision"].strip():
            errors.append("%s is waived without an operator decision" % label)
        for key in ("unit", "file_line", "evidence", "acceptance_impact",
                    "owner", "round", "decision"):
            if not row[key].strip():
                errors.append("%s has empty %s" % (label, key))
    return rows, errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--require-clean", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        rows, errors = parse(args.path)
    except OSError as exc:
        print("findings: cannot read %s: %s" % (args.path, exc))
        return 2
    if args.require_clean:
        for row in rows:
            if row.get("state") == "open" and row.get("severity") in ("high", "medium"):
                errors.append("%s is an open %s finding"
                              % (row.get("finding_id"), row.get("severity")))
    if args.json:
        print(json.dumps({"path": args.path, "findings": len(rows),
                          "violations": errors}, indent=2))
    else:
        for error in errors:
            print("FAIL " + error)
        print("findings: %d findings, %d violation(s)" % (len(rows), len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
