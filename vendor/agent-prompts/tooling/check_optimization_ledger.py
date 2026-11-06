#!/usr/bin/env python3
"""Validate the human-gated optimization proposal ledger (WP-08).

Usage:
    python3 tooling/check_optimization_ledger.py PATH [--failure-set PATH] [--json]

One row per proposal. The ledger is the human gate: a proposal can be
`accepted` only with an operator-approved gate and a paired result, and a
rejected or accepted proposal must name the cases it answers and the committed
evidence that measures it.

Exit 0 clean, 1 violations, 2 unreadable input. ASCII-only output.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FAILURE_SET = ROOT / "evals" / "optimization" / "failure-set.md"
COLUMNS = ["proposal_id", "cycle", "configuration", "source_cases",
           "hypothesis", "candidate_change", "arm", "model_harness",
           "cost_usd", "latency_s", "tokens", "current_score",
           "candidate_score", "paired_wtl", "human_gate", "status", "evidence"]
GATES = {"pending", "approved", "rejected"}
STATUSES = {"proposed", "rejected", "accepted", "blocked"}
PATH_RE = re.compile(r"[A-Za-z0-9_./-]+\.(?:json|md|txt|jsonl|yaml|yml)")


def parse_cell(cell):
    """Split `A=1; B=2` into an ordered dict, or return {None: cell}."""
    if "=" not in cell:
        return {None: cell.strip()}
    values = {}
    for item in cell.split(";"):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            return {None: cell.strip()}
        key, value = item.split("=", 1)
        key = key.strip()
        if not re.match(r"^[A-Z][A-Za-z0-9-]*$", key) or key in values:
            return {None: cell.strip()}
        values[key] = value.strip()
    return values or {None: cell.strip()}


def numeric(cell, low=None, high=None):
    """Return (ok, detail). Accepts `A=0.5; B=0.4` and `unrecorded`."""
    values = parse_cell(cell)
    for key, value in values.items():
        label = key or "value"
        if value in ("unrecorded", "not-run"):
            continue
        try:
            number = float(value)
        except ValueError:
            return False, "%s is not a number or unrecorded: %s" % (label, value)
        if low is not None and number < low:
            return False, "%s is below %s: %s" % (label, low, value)
        if high is not None and number > high:
            return False, "%s is above %s: %s" % (label, high, value)
    return True, ""


def ratios(cell, parts=2, high=None):
    values = parse_cell(cell)
    for key, value in values.items():
        label = key or "value"
        if value == "not-run":
            continue
        numbers = value.split("/")
        if len(numbers) != parts:
            return False, "%s is not %d integers separated by '/': %s" % (
                label, parts, value)
        for number in numbers:
            if not re.match(r"^[0-9]+$", number.strip()):
                return False, "%s has a non-integer part: %s" % (label, value)
        if high is not None and int(numbers[0]) > high:
            return False, "%s has a numerator above %d: %s" % (label, high, value)
    return True, ""


def failure_ids(path):
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r"(?m)^\| (FC-[0-9]{2}) \|", text))


def parse(path, failure_set):
    errors = []
    text = Path(path).read_text(encoding="utf-8")
    if not text.isascii():
        errors.append("proposal ledger is not ASCII")
    header = next((line for line in text.splitlines()
                   if line.startswith("| proposal_id |")), "")
    columns = [cell.strip() for cell in header.strip().strip("|").split("|")]
    if columns != COLUMNS:
        return [], ["header does not match the proposal-ledger contract"]
    rows = []
    for line in text.splitlines():
        if not line.startswith("|") or line.startswith("| proposal_id |"):
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
        errors.append("ledger has no proposal row")

    known_cases = failure_ids(failure_set)
    seen = []
    for row in rows:
        label = row.get("proposal_id", "?")
        if not re.match(r"^P-[1-9][0-9]*$", label):
            errors.append("%s is not a proposal id (P-N)" % label)
        if label in seen:
            errors.append("duplicate proposal id: %s" % label)
        seen.append(label)
        if not re.match(r"^C[1-9][0-9]*$", row["cycle"]):
            errors.append("%s cycle is not C-N" % label)
        if row["human_gate"] not in GATES:
            errors.append("%s human_gate is not pending|approved|rejected" % label)
        if row["status"] not in STATUSES:
            errors.append("%s status is not proposed|rejected|accepted|blocked"
                          % label)
        for key in ("configuration", "hypothesis", "candidate_change",
                    "model_harness", "evidence"):
            if not row[key].strip():
                errors.append("%s has empty %s" % (label, key))

        cases = [item.strip() for item in row["source_cases"].split(",")
                 if item.strip()]
        if not cases:
            errors.append("%s names no source case" % label)
        for case in cases:
            if not re.match(r"^FC-[0-9]{2}$", case):
                errors.append("%s source case is not FC-NN: %s" % (label, case))
            elif known_cases is not None and case not in known_cases:
                errors.append("%s cites a case absent from the failure set: %s"
                              % (label, case))

        for key, check in (("cost_usd", lambda cell: numeric(cell, low=0)),
                           ("latency_s", lambda cell: numeric(cell, low=0)),
                           ("tokens", lambda cell: ratios(cell, parts=2)),
                           ("current_score", lambda cell: numeric(cell, 0, 1)),
                           ("candidate_score", lambda cell: numeric(cell, 0, 1)),
                           ("paired_wtl", lambda cell: ratios(cell, parts=3))):
            ok, detail = check(row[key])
            if not ok:
                errors.append("%s %s: %s" % (label, key, detail))
            elif not row[key].strip():
                errors.append("%s has empty %s" % (label, key))

        if row["status"] in ("accepted", "rejected"):
            for key in ("current_score", "candidate_score", "paired_wtl",
                        "cost_usd", "latency_s", "tokens"):
                if "not-run" in row[key] or row[key].strip() in ("", "-"):
                    errors.append("%s is %s without a paired result in %s"
                                  % (label, row["status"], key))
        pairs, detail = score_pairs(row["current_score"], row["candidate_score"])
        if detail and row["status"] != "blocked":
            errors.append("%s %s" % (label, detail))
        if row["status"] == "accepted":
            if row["human_gate"] != "approved":
                errors.append("%s is accepted without an approved human gate"
                              % label)
            if not pairs and not detail:
                errors.append("%s is accepted without a paired score" % label)
            elif not all(candidate >= current for _, current, candidate in pairs):
                errors.append("%s is accepted with a configuration that does not "
                              "improve" % label)
            elif not any(candidate > current for _, current, candidate in pairs):
                errors.append("%s is accepted without a measured gain" % label)
        if row["status"] == "blocked" and not row["evidence"].strip():
            errors.append("%s is blocked without the blocking evidence" % label)

        arm = row["arm"].strip()
        if arm and arm != "not-built":
            if not (ROOT / arm).exists():
                errors.append("%s arm does not exist: %s" % (label, arm))

        for token in PATH_RE.findall(row["evidence"]):
            if not (ROOT / token).exists():
                errors.append("%s evidence path does not exist: %s"
                              % (label, token))
        if not PATH_RE.findall(row["evidence"]):
            errors.append("%s evidence names no committed artifact" % label)
    return rows, errors


def score_pairs(current_cell, candidate_cell):
    """Return ([(key, current, candidate)], error) across configurations."""
    current = parse_cell(current_cell)
    candidate = parse_cell(candidate_cell)
    if set(current) != set(candidate):
        return [], "current_score and candidate_score name different configurations"
    pairs = []
    for key in current:
        values = []
        for cell in (current[key], candidate[key]):
            if cell in ("not-run", "unrecorded", ""):
                return [], "configuration %s has no paired score" % (key or "value")
            try:
                values.append(float(cell))
            except ValueError:
                return [], "configuration %s score is not a number: %s" % (
                    key or "value", cell)
        pairs.append((key, values[0], values[1]))
    return pairs, ""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--failure-set", default=str(DEFAULT_FAILURE_SET))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        rows, errors = parse(args.path, Path(args.failure_set))
    except OSError as exc:
        print("optimization-ledger: cannot read %s: %s" % (args.path, exc))
        return 2
    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    spread = ", ".join("%s %d" % (key, counts[key]) for key in sorted(counts))
    if args.json:
        import json
        print(json.dumps({"path": args.path, "proposals": len(rows),
                          "by_status": counts, "violations": errors}, indent=2))
    else:
        for error in errors:
            print("FAIL " + error)
        print("optimization-ledger: %d proposals (%s), %d violation(s)"
              % (len(rows), spread or "none", len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
