#!/usr/bin/env python3
"""Fail a build when a unit implemented without a clean plan review (WL-02, WL-15).

`standards/workflow-loop.md` forbids `Plan -> Implement`, but a rule on paper
does not stop a build. This gate reads the artifacts a unit leaves behind -- its
WL-08 ledger rows and its gate-verdict records -- and refuses the states that
mean the loop was skipped:

1. a verdict record that does not validate against the contract;
2. a unit that reached Implement (or any later phase) with no `plan-review`
   verdict for that unit;
3. a unit whose plan-review rounds are not contiguous from 0, whose last round
   is not a clean pass, or whose reviewed spec changed after that round;
4. a unit at Ready, Ready (unverified) or Done with no `verify` or `acceptance`
   pass for that unit;
5. a ledger row the WL-08 validator rejects (illegal `next`, bad attempt, gate
   and decision disagreeing, an open high/medium finding at Done).

Rows older than the effective date are skipped: the rule cannot retroactively
demand evidence for units that closed before it existed. The default is
`2026-11-03`; a consumer that adopts later passes its own `--since`.

Usage:
    python3 tooling/check_loop_gate.py \\
        --ledger provenance/ledger-*.md \\
        --verdict provenance/verdict-*.json \\
        [--since 2026-11-03] [--root DIR] [--json]

Both options accept several paths, a glob, or a directory. Exit 0 clean, 1
violations, 2 unreadable input. ASCII-only output.
"""

import argparse
import glob
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tooling"))

import check_gate_verdict  # noqa: E402
import check_workflow_loop  # noqa: E402

EFFECTIVE = "2026-11-03"
POST_PLAN = ("Implement", "Review", "Fix", "Verify", "Push", "Ready",
             "Ready (unverified)", "Done")
# WL-10: a finalize needs the verify record, so Push itself requires it.
VERIFY_REQUIRED = ("Push", "Ready", "Ready (unverified)", "Done")
BLOCKING = {"high", "medium"}
MAX_BYTES = 512 * 1024


def safe(value, limit=100):
    """One line, ASCII, capped: a record is data, never terminal escape codes."""
    text = " ".join(str(value).split())
    text = text.encode("ascii", "backslashreplace").decode("ascii")
    return text if len(text) <= limit else text[:limit] + "..."


def expand(patterns, suffix=None):
    """Expand file paths, globs and directories into a sorted path list."""
    found = []
    for pattern in patterns:
        path = Path(pattern)
        if path.is_dir():
            found.extend(sorted(item for item in path.iterdir()
                                if (suffix is None or item.suffix == suffix)
                                and not item.is_symlink()))
        elif any(char in pattern for char in "*?["):
            found.extend(Path(item) for item in sorted(glob.glob(pattern)))
        elif path.is_file():
            found.append(path)
    return sorted({item for item in found
                   if item.is_file() and not item.is_symlink()})


def load_verdicts(paths, violations):
    records = []
    contract = check_gate_verdict.load_contract()
    for path in paths:
        try:
            if path.stat().st_size > MAX_BYTES:
                violations.append("%s: verdict is larger than %d bytes; refusing to "
                                  "read it" % (path.as_posix(), MAX_BYTES))
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            violations.append("%s: unreadable verdict: %s" % (path.as_posix(), exc))
            continue
        errors = check_gate_verdict.check(data, contract)
        if errors:
            violations.append("%s: %s" % (path.as_posix(), safe(errors[0])))
            continue
        records.append(dict(data, _path=path.as_posix()))
    return records


def clean_plan_review(record):
    if record.get("verdict") != "pass":
        return False
    return not [finding for finding in record.get("findings") or []
                if isinstance(finding, dict)
                and finding.get("severity") in BLOCKING
                and finding.get("state") in {"open", "waived"}]


def unit_errors(unit, records, status, violations, warnings, label, row,
                grandfathered, root=None):
    reviews = sorted((record for record in records
                      if record.get("unit") == unit
                      and record.get("gate") == "plan-review"),
                     key=lambda record: record.get("attempt", 0))
    findings_text = str(row.get("findings", ""))
    exemption = ("exemption" in findings_text.lower()
                 or "unverified" in findings_text.lower())
    if status in POST_PLAN and not reviews:
        message = ("%s: unit %s reached %s with no plan-review verdict (WL-15)"
                   % (label, unit, status))
        if grandfathered:
            # An explicit, per-run allowlist entry for a unit that predates the
            # gate. It is named on the command line, never self-declared by the
            # artifact, and it can never close a unit as Done.
            warnings.append(message + "; grandfathered by --grandfather, so it "
                                       "stays unverified")
            if status != "Done":
                return
        else:
            violations.append(message)
            return
        violations.append("%s: grandfathered unit %s is at Done, which needs a "
                          "verify pass and a plan review (WL-15)" % (label, unit))
        return
    if not reviews:
        return
    rounds = [record.get("attempt") for record in reviews]
    if rounds != list(range(len(rounds))):
        violations.append("%s: unit %s plan-review rounds are %s, not contiguous "
                          "from 0 (WL-15)" % (label, unit, rounds))
    last = reviews[-1]
    if not clean_plan_review(last):
        violations.append("%s: unit %s last plan-review round (%s) is %r, not a "
                          "clean pass (WL-15)"
                          % (label, unit, safe(last.get("_path")),
                             safe(last.get("verdict"))))
        return
    # WL-15 binds the record to the reviewed artifact: the spec it names must be
    # the one the ledger row names, and it must not have changed since.
    artifact_cell = str(row.get("artifact", ""))
    reviewed = [str(item.get("path")) for item in last.get("artifacts") or []
                if isinstance(item, dict) and item.get("path")]
    matched = [path for path in reviewed if path in artifact_cell]
    if not matched:
        violations.append("%s: unit %s plan-review round names %s, but the ledger "
                          "artifact cell names no reviewed spec (WL-15)"
                          % (label, unit, safe(", ".join(reviewed) or "nothing")))
        return
    root = root or ROOT
    for path in matched:
        target = root / path
        if not target.is_file():
            # A consumer keeps its plans outside this tree; binding is still
            # required (the row names it), but existence and freshness can only
            # be checked where the file is.
            warnings.append("%s: unit %s plan-review names %s, which is not under "
                            "%s; existence and freshness are not checked"
                            % (label, unit, safe(path), safe(root)))
            continue
        digest = next((str(item.get("sha256")) for item in last.get("artifacts") or []
                       if isinstance(item, dict) and item.get("path") == path), "")
        if digest:
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual != digest:
                violations.append("%s: unit %s spec %s changed after the plan "
                                  "review; run another round (WL-15)"
                                  % (label, unit, safe(path)))
    gate_records = [record for record in records
                    if record.get("unit") == unit
                    and record.get("gate") in ("verify", "acceptance")]
    if status in VERIFY_REQUIRED:
        passed = [record for record in gate_records
                  if record.get("verdict") == "pass"]
        if not passed and status == "Ready (unverified)" and exemption:
            # WL-05: a recorded limitation keeps the claim unverified; it never
            # becomes Done, and the operator decides at Push.
            warnings.append("%s: unit %s is at Ready (unverified) with no verify "
                            "pass; recorded exemption, the operator decides"
                            % (label, unit))
        elif not passed:
            violations.append("%s: unit %s is at %s with no verify or acceptance "
                              "pass (WL-10)" % (label, unit, safe(status)))


def parse_date(value, label, violations):
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        violations.append("%s is not an ISO date (YYYY-MM-DD): %r" % (label, safe(value)))
        return None


def ledger_errors(path, records, since, violations, warnings, grandfather,
                  root=None):
    if path.stat().st_size > MAX_BYTES:
        violations.append("%s: ledger is larger than %d bytes; refusing to read it"
                          % (path.as_posix(), MAX_BYTES))
        return 0
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    header = next((line for line in lines if line.startswith("| unit_id |")), "")
    columns = [cell.strip() for cell in header.strip().strip("|").split("|")]
    if not columns:
        violations.append("%s: no WL-08 header" % path.as_posix())
        return 0
    checked = 0
    rows = []
    for line in lines:
        if not line.startswith("|") or line.startswith("| unit_id |"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(set(cell) <= set("-: ") and cell for cell in cells):
            continue
        if len(cells) != len(columns):
            violations.append("%s: row has %d cells, expected %d"
                              % (path.as_posix(), len(cells), len(columns)))
            continue
        rows.append(dict(zip(columns, cells)))
    stamps = {}
    for row in rows:
        stamp = parse_date(row.get("timestamp", ""), "row %s timestamp"
                           % safe(row.get("unit_id")), violations)
        if stamp is not None:
            stamps[row.get("unit_id")] = stamp
    # A ledger whose newest row predates the gate is history and is read for
    # shape only. A mixed ledger is live, and every row in it is checked -- a
    # stale date in a live ledger is not a grandfather stamp.
    newest = max(stamps.values()) if stamps else None
    historical = newest is not None and newest < since
    for row in rows:
        for error in check_workflow_loop.validate_ledger_row(row):
            violations.append("%s: %s" % (path.as_posix(), safe(error)))
        unit = row.get("unit_id")
        stamp = stamps.get(unit)
        if historical or (stamp is not None and stamp < since
                          and row.get("status") in ("Done", "HALT")):
            continue
        if stamp is None:
            continue
        checked += 1
        unit_errors(unit, records, row.get("status"), violations, warnings,
                    path.as_posix(), row, unit in grandfather, root)
    return checked


def run(ledgers, verdicts, since, grandfather=(), root=None):
    violations = []
    warnings = []
    when = parse_date(since, "--since", violations)
    if when is None:
        return violations, warnings, {"error": "invalid --since"}
    records = load_verdicts(verdicts, violations)
    checked = 0
    for path in ledgers:
        checked += ledger_errors(path, records, when, violations, warnings,
                                 set(grandfather), root)
    return violations, warnings, {"ledgers": len(ledgers), "verdicts": len(records),
                                  "rows_checked": checked, "since": since}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ledger", nargs="+", default=[],
                        help="WL-08 ledger paths, globs or a directory")
    parser.add_argument("--verdict", nargs="+", default=[],
                        help="gate-verdict paths, globs or a directory")
    parser.add_argument("--since", default=EFFECTIVE,
                        help="effective date; a ledger whose newest row predates "
                             "it is read for shape only")
    parser.add_argument("--root", default=str(ROOT),
                        help="tree a reviewed spec path resolves against; a "
                             "consumer passes its own root")
    parser.add_argument("--grandfather", nargs="*", default=[],
                        metavar="UNIT",
                        help="unit ids that predate the gate; named here, never "
                             "self-declared by the artifact")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    base = Path(args.root)
    ledgers = (expand(args.ledger, ".md") if args.ledger
               else expand([str(base / "provenance" / "ledger-*.md")]))
    verdicts = (expand(args.verdict, ".json") if args.verdict
                else expand([str(base / "provenance" / "verdict-*.json")]))
    if not ledgers:
        print("loop-gate: no ledger found; pass --ledger")
        return 2
    violations, warnings, summary = run(ledgers, verdicts, args.since,
                                        args.grandfather, Path(args.root))
    if summary.get("error"):
        print("loop-gate: %s" % summary["error"])
        return 2
    if args.json:
        print(json.dumps(dict(summary, violations=violations, warnings=warnings),
                         indent=2))
    else:
        for warning in warnings:
            print("WARN " + warning)
        for violation in violations:
            print("FAIL " + violation)
        print("loop-gate: %d ledger(s), %d verdict(s), %d row(s) at or after %s, "
              "%d violation(s), %d warning(s)"
              % (summary["ledgers"], summary["verdicts"], summary["rows_checked"],
                 summary["since"], len(violations), len(warnings)))
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
