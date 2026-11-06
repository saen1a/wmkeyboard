#!/usr/bin/env python3
"""Validate the WP-08 labelled failure set.

Usage:
    python3 tooling/check_failure_set.py PATH [--json]

Every row must name one committed source artifact, an anchor string that
appears in that artifact after whitespace normalization, and a concrete
failure. The anchor must resolve exactly once, so a repeated phrase cannot
silently point at the wrong sentence. The anchor is the traceability check: a
case whose evidence was deleted or reworded fails here.

Exit 0 clean, 1 violations, 2 unreadable input. ASCII-only output.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLUMNS = ["case_id", "category", "unit", "source", "anchor", "failure",
           "expected", "state", "state_note"]
CATEGORIES = {"routing", "behavior", "role", "measurement", "process", "tooling"}
STATES = {"open", "covered", "blocked"}
MIN_CASES = 20
MAX_CASES = 40


def normalize(text):
    return " ".join(text.split())


def parse(path):
    errors = []
    text = Path(path).read_text(encoding="utf-8")
    if not text.isascii():
        errors.append("failure set is not ASCII")
    header = next((line for line in text.splitlines()
                   if line.startswith("| case_id |")), "")
    columns = [cell.strip() for cell in header.strip().strip("|").split("|")]
    if columns != COLUMNS:
        return [], ["header does not match the failure-set contract"]
    rows = []
    for line in text.splitlines():
        if not line.startswith("|") or line.startswith("| case_id |"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(set(cell) <= set("-: ") for cell in cells):
            continue
        if len(cells) != len(COLUMNS):
            errors.append("row has %d cells, expected %d"
                          % (len(cells), len(COLUMNS)))
            continue
        rows.append(dict(zip(COLUMNS, cells)))
    if not rows:
        errors.append("failure set has no case row")
    elif not MIN_CASES <= len(rows) <= MAX_CASES:
        errors.append("%d cases, expected %d..%d"
                      % (len(rows), MIN_CASES, MAX_CASES))

    seen = []
    for row in rows:
        label = row.get("case_id", "?")
        if not re.match(r"^FC-[0-9]{2}$", label):
            errors.append("%s is not a case id (FC-NN)" % label)
        if label in seen:
            errors.append("duplicate case id: %s" % label)
        seen.append(label)
        if row["category"] not in CATEGORIES:
            errors.append("%s category is not one of %s"
                          % (label, ", ".join(sorted(CATEGORIES))))
        if row["state"] not in STATES:
            errors.append("%s state is not open|covered|blocked" % label)
        for key in ("unit", "failure", "expected"):
            if not row[key].strip():
                errors.append("%s has empty %s" % (label, key))
        if row["state"] != "open" and row["state_note"].strip() in ("", "-"):
            errors.append("%s is %s without a state_note" % (label, row["state"]))
        source = row.get("source", "")
        if not source:
            errors.append("%s has no source" % label)
            continue
        source_path = (ROOT / source).resolve()
        if not str(source_path).startswith(str(ROOT)):
            errors.append("%s source escapes the repository: %s" % (label, source))
            continue
        if not source_path.is_file():
            errors.append("%s source does not exist: %s" % (label, source))
            continue
        anchor = row.get("anchor", "")
        if not anchor:
            errors.append("%s has no anchor" % label)
            continue
        haystack = normalize(source_path.read_text(encoding="utf-8",
                                                  errors="replace"))
        needle = normalize(anchor)
        occurrences = haystack.count(needle)
        if occurrences == 0:
            errors.append("%s anchor not found in %s: %s"
                          % (label, source, anchor))
        elif occurrences > 1:
            errors.append("%s anchor resolves %d times in %s; it must be "
                          "unique: %s"
                          % (label, occurrences, source, anchor))
    ids = {int(label.split("-")[1]) for label in seen
           if re.match(r"^FC-[0-9]{2}$", label)}
    if ids and ids != set(range(1, len(rows) + 1)):
        errors.append("case ids are not contiguous from FC-01")
    return rows, errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        rows, errors = parse(args.path)
    except OSError as exc:
        print("failure-set: cannot read %s: %s" % (args.path, exc))
        return 2
    if args.json:
        print(json.dumps({"path": args.path, "cases": len(rows),
                          "by_category": {category: sum(
                              1 for row in rows if row["category"] == category)
                              for category in sorted(CATEGORIES)},
                          "violations": errors}, indent=2))
    else:
        for error in errors:
            print("FAIL " + error)
        counts = {}
        for row in rows:
            counts[row["category"]] = counts.get(row["category"], 0) + 1
        spread = ", ".join("%s %d" % (key, counts[key]) for key in sorted(counts))
        print("failure-set: %d cases (%s), %d violation(s)"
              % (len(rows), spread or "none", len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
