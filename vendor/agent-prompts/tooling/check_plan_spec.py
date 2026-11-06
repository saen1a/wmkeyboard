#!/usr/bin/env python3
"""Run the six WL-15 plan-review checks against a spec file.

`standards/workflow-loop.md` WL-15 makes the plan review mandatory and names six
checks. A prose checklist is not a gate, so this script encodes the mechanical
half of those checks over a spec file and fails a build when one of them is
unmet. Any consumer can run it before dispatching implementation.

Spec shape (the headings are the contract, the tables are parsed):

    ## Goal
    one decidable sentence, no question mark
    ## Scope boundaries
    - in scope: ...
    ## Request coverage
    | Request item | Unit | Why |
    ## Units
    | Unit | Acceptance | Verification | Owner |
    ## Ownership and order
    1. <unit id> -- one writer: ...
    ## Risks and halts
    table whose every row names HALT, or the literal "None" plus a reason

The six checks map one-to-one onto WL-15:

1. `goal` -- a decidable goal plus explicit scope boundaries.
2. `request-coverage` -- every unit traces back to a request item.
3. `acceptance` -- every unit carries a MUST or SHOULD criterion.
4. `verification` -- every unit names a check that exists today. The cell needs
   a known runner (`python3`, `pytest`, `bash`, ...) or a path inside the root,
   and every path it names must be a real file there: WL-15 asks the check to
   exist before the attempt, so a command pointing at a file the plan has not
   written yet is unmet, not pending. `TBD`, `-`, `none`, an empty cell, an
   absolute path or one that escapes the root fail.
5. `ownership-order` -- one writer per unit and a dependency order that names
   every unit exactly once.
6. `risk-halt` -- unsafe, blocked or unresolvable items name the HALT path and
   the operator question, or the spec states that there are none and why.

Usage:
    python3 tooling/check_plan_spec.py SPEC.md [--root DIR] [--json]

Exit 0 when all six checks are met, 1 when one fails, 2 on unreadable input.
ASCII-only output.
"""

import argparse
import glob
import json
import re
import shlex
import sys
from pathlib import Path

CHECKS = ("goal", "request-coverage", "acceptance", "verification",
          "ownership-order", "risk-halt")
RUNNERS = {"python3", "python", "pytest", "bash", "sh", "make", "npm", "npx",
           "node", "cargo", "go", "docker", "uv", "deno", "ruby", "perl"}
EMPTY_CELL = {"", "-", "--", "none", "n/a", "tbd", "todo", "?"}
PLACEHOLDERS = {"tbd", "todo", "fixme", "<later>", "<tbd>"}
PATH_RE = re.compile(r"`([^`\s]+)`")
PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_./-]+\.(?:py|md|json|sh|ya?ml|txt|js|ts)")
SUFFIX_RE = re.compile(r"\.[A-Za-z0-9]{1,6}$")


def sections(text):
    """Split markdown into level-2 sections keyed by their lowercased title."""
    found = {}
    current = None
    for line in text.splitlines():
        match = re.match(r"^##\s+(.*\S)\s*$", line)
        if match:
            current = match.group(1).strip().lower()
            found[current] = []
            continue
        if current is not None:
            found[current].append(line)
    return found


def table(block):
    """Return (header, rows) for the first pipe table in a block."""
    header = None
    rows = []
    for line in block:
        if not line.strip().startswith("|"):
            if header and rows:
                break
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(set(cell) <= set("-: ") and cell for cell in cells):
            continue
        if header is None:
            header = [cell.lower() for cell in cells]
            continue
        rows.append(cells)
    return header, rows


def resolve(root, token):
    """Resolve a path token inside the root; None when it is absolute or escapes."""
    token = token.strip().strip("`")
    if not token or token.startswith("/") or ".." in Path(token).parts:
        return None
    return root / token


def first_body_line(block):
    for line in block:
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def column(header, name, exact_prefix=True):
    for index, cell in enumerate(header or []):
        if (cell.startswith(name) if exact_prefix else name in cell):
            return index
    return None


def bullets(block):
    return [line.strip()[2:].strip() for line in block
            if line.strip().startswith("- ")]


def cell(row, index):
    return row[index].strip() if index is not None and index < len(row) else ""


def run_checks(path, root):
    """Return a list of {id, state, detail} for the six WL-15 checks."""
    text = Path(path).read_text(encoding="utf-8")
    parts = sections(text)
    results = []

    def add(check, ok, detail):
        results.append({"id": check, "state": "met" if ok else "unmet",
                        "detail": detail})

    # 1 goal
    goal = first_body_line(parts.get("goal", []))
    scope = bullets(parts.get("scope boundaries", []))
    hard_scope = [item for item in scope if len(item.split()) >= 3]
    if not goal:
        add("goal", False, "no '## Goal' section with a statement")
    elif len(goal) < 40:
        add("goal", False, "goal is %d characters; state one decidable outcome" % len(goal))
    elif "?" in goal:
        add("goal", False, "goal contains a question mark, so it is not decidable")
    elif not hard_scope:
        add("goal", False, "no '## Scope boundaries' bullet with a stated boundary")
    else:
        add("goal", True, "goal stated, %d scope bullet(s)" % len(scope))

    # units table is the backbone of checks 2..5
    units_header, unit_rows = table(parts.get("units", []))
    id_col = column(units_header, "unit")
    acc_col = column(units_header, "accept")
    ver_col = column(units_header, "verif")
    own_col = column(units_header, "owner")
    unit_ids = [cell(row, id_col) for row in unit_rows if cell(row, id_col)]
    units_problem = None
    if not unit_rows:
        units_problem = "no '## Units' table"
    elif id_col is None or acc_col is None or ver_col is None or own_col is None:
        units_problem = "the Units table needs Unit, Acceptance, Verification, Owner columns"
    elif not unit_ids:
        units_problem = "the Units table has no unit id"

    # 2 request coverage
    cov_header, cov_rows = table(parts.get("request coverage", []))
    cov_unit_col = column(cov_header, "unit")
    if not cov_rows:
        add("request-coverage", False, "no '## Request coverage' table row")
    elif cov_unit_col is None:
        add("request-coverage", False, "the coverage table needs a Unit column")
    else:
        mapped = []
        for row in cov_rows:
            for name in re.split(r"[,;]", cell(row, cov_unit_col)):
                name = name.strip().strip("`")
                if name:
                    mapped.append(name)
        unknown = sorted(set(mapped) - set(unit_ids))
        missing = sorted(set(unit_ids) - set(mapped))
        if unknown:
            add("request-coverage", False,
                "coverage names unit(s) the Units table does not define: %s"
                % ", ".join(unknown))
        elif missing:
            add("request-coverage", False,
                "unit(s) with no request item: %s" % ", ".join(missing))
        else:
            add("request-coverage", True,
                "%d unit(s) mapped to %d request row(s)" % (len(unit_ids), len(cov_rows)))

    # 3 acceptance
    if units_problem:
        add("acceptance", False, units_problem)
    else:
        bad = []
        for row in unit_rows:
            unit = cell(row, id_col)
            criterion = cell(row, acc_col)
            if not re.search(r"\b(MUST|SHOULD)\b", criterion):
                bad.append("%s has no MUST/SHOULD" % unit)
            elif any(token in criterion.lower() for token in PLACEHOLDERS):
                bad.append("%s carries a placeholder criterion" % unit)
            elif not cell(row, own_col):
                bad.append("%s has no owner" % unit)
        add("acceptance", not bad,
            "every unit carries a MUST/SHOULD criterion and an owner" if not bad
            else "; ".join(bad))

    # 4 verification
    if units_problem:
        add("verification", False, units_problem)
    else:
        problems = []
        for row in unit_rows:
            unit = cell(row, id_col)
            spec = cell(row, ver_col)
            if spec.lower() in EMPTY_CELL:
                problems.append("%s has no verification" % unit)
                continue
            low = spec.lower()
            if any(token in low for token in PLACEHOLDERS):
                problems.append("%s names a placeholder check" % unit)
                continue
            try:
                tokens = PATH_RE.findall(spec) or shlex.split(spec.split(";")[0])
            except ValueError:
                problems.append("%s has an unbalanced quote in its check" % unit)
                continue
            runner = tokens[0].strip("`") if tokens else ""
            if runner not in RUNNERS:
                resolved = resolve(root, runner)
                if resolved is None or not resolved.is_file():
                    problems.append("%s names no runnable check (%r is not a known "
                                    "runner or a file inside the root)" % (unit, runner))
                continue
            candidates = PATH_TOKEN_RE.findall(spec)
            candidates += [token.strip("`\"' ")
                           for token in spec.split()
                           if token.startswith("/") or ".." in token]
            for token in candidates:
                resolved = resolve(root, token)
                if resolved is None:
                    problems.append("%s names %r, which is outside the root"
                                    % (unit, token))
                elif not resolved.is_file():
                    problems.append("%s names %r, which does not exist"
                                    % (unit, token))
        add("verification", not problems,
            "every unit names a check that exists today" if not problems
            else "; ".join(problems))

    # 5 ownership and order
    order_block = parts.get("ownership and order", [])
    order = [line for line in order_block if re.match(r"^\s*\d+\.\s", line)]
    order_ids = []
    writers = []
    for line in order:
        body = re.sub(r"^\s*\d+\.\s*", "", line).strip()
        match = re.search(r"`?([A-Za-z0-9][A-Za-z0-9._-]*)`?", body)
        order_ids.append(match.group(1) if match else body.split(" ")[0])
        writers.append(bool(re.search(r"writer|owner|owner:", body, re.I)))
    if not order:
        add("ownership-order", False, "no numbered '## Ownership and order' list")
    elif sorted(order_ids) != sorted(unit_ids):
        add("ownership-order", False,
            "the order %s does not name exactly the Units %s"
            % (order_ids, unit_ids))
    elif len(set(order_ids)) != len(order_ids):
        add("ownership-order", False, "the order names a unit twice")
    else:
        add("ownership-order", True, "%d unit(s) ordered by dependency" % len(order_ids))

    # 6 risks and halts
    risk_block = parts.get("risks and halts", [])
    body = " ".join(line.strip() for line in risk_block)
    risk_header, risk_rows = table(risk_block)
    halt_col = column(risk_header, "halt", exact_prefix=False)
    question_col = column(risk_header, "question", exact_prefix=False)
    if not risk_block:
        add("risk-halt", False, "no '## Risks and halts' section")
    elif re.match(r"(?i)^none\b", body.strip()) and len(body.split()) >= 6:
        add("risk-halt", True, "no blocked, unsafe or unresolvable item, with a reason")
    elif not risk_rows:
        add("risk-halt", False, "the risk section is neither a table nor a reasoned 'None'")
    elif halt_col is None or question_col is None:
        add("risk-halt", False, "the risk table needs Halt path and Operator question columns")
    else:
        bad = [cell(row, 1) or "row" for row in risk_rows
               if "HALT" not in cell(row, halt_col).upper()
               or cell(row, question_col).lower() in EMPTY_CELL]
        add("risk-halt", not bad,
            "every risk names its HALT path and question" if not bad
            else "risk row(s) without a HALT path or a question: %s" % ", ".join(bad))

    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", nargs="+", help="spec files, globs or directories")
    parser.add_argument("--root", default=".", help="repository root for path checks")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    specs = []
    for pattern in args.path:
        candidate = Path(pattern)
        if candidate.is_dir():
            specs.extend(sorted(item for item in candidate.glob("*.md")
                                if not item.is_symlink()))
        elif any(char in pattern for char in "*?["):
            specs.extend(Path(item) for item in sorted(glob.glob(pattern)))
        else:
            specs.append(candidate)
    specs = [item for item in specs if item.is_file()]
    if not specs:
        print("plan-spec: no spec file found")
        return 2
    worst = 0
    payload = []
    for spec in specs:
        try:
            results = run_checks(spec, Path(args.root))
        except (OSError, UnicodeDecodeError) as exc:
            print("plan-spec: cannot read %s: %s" % (spec, exc))
            worst = 2
            continue
        failures = [item for item in results if item["state"] != "met"]
        payload.append({"path": str(spec), "checks": results, "ok": not failures})
        if args.json:
            continue
        for item in results:
            print("%s %-17s %s" % ("OK  " if item["state"] == "met" else "FAIL",
                                   item["id"], item["detail"]))
        print("plan-spec: %d/%d checks met on %s"
              % (len(results) - len(failures), len(results), spec))
        worst = max(worst, 1 if failures else 0)
    if args.json:
        print(json.dumps(payload if len(payload) > 1 else payload[0], indent=2))
    return worst


if __name__ == "__main__":
    sys.exit(main())
