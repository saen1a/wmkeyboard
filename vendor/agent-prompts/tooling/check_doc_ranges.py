#!/usr/bin/env python3
"""Fail when a live document quotes a rule range that no longer matches its standard.

Rule ranges rot silently: `AS-01..AS-12` stays in six documents after AS-13 and
AS-14 are added, `SD-01..SD-11` survives SD-12, and a reader cannot tell a stale
range from a deliberate one. `measure_state.py` already refuses hand-copied
numbers; this is the same rule for rule ranges.

A range is written `XX-01..XX-NN` and is checked against the number of rules the
family actually defines, counted from `## XX-NN -- ` headings and `| XX-NN |`
table rows in `standards/*.md`:

- `NN` above the defined count is an error: the range claims a rule that does
  not exist.
- A range that starts at `01` and ends below the defined count reads as "the whole
  standard" and is an error unless the line carries the literal marker
  `[subset]`. A range that starts anywhere else (`AS-09..AS-12`) is read as the
  subset it is, and is only checked for rules that do not exist.
- A family that no standard defines is an error, except under `exemplars/`, where
  an example may legitimately carry its own family (reported as a warning).

Rules are counted from `## XX-NN -- ` headings, `| XX-NN |` table rows, and
`- **XX-NN** --` bullets, so a standard may choose any of the three shapes.

Historical records keep their own measurement and are not scanned: `CHANGELOG.md`,
`PLAN.md`, `standards/evidence/`, `provenance/`, `packs/`, `evals/role-ab/arms/`
(frozen experiment arms), `docs/measured-state.md`, and dated knowledge-base
records (`docs/knowledge-base/*-20YY-MM*.md`).

Usage:
    python3 tooling/check_doc_ranges.py [--root PATH] [--json]

Exit 0 clean, 1 violations, 2 unreadable tree. ASCII-only output.
"""

import argparse
import json
import re
import sys
from pathlib import Path

STANDARD_DIR = "standards"
HEADING_RE = re.compile(r"(?m)^## ([A-Z]{2})-([0-9]{2}) -- ")
ROW_RE = re.compile(r"(?m)^\|\s*([A-Z]{2})-([0-9]{2})\s*\|")
BULLET_RE = re.compile(r"(?m)^\s*[-*]\s*\*\*([A-Z]{2})-([0-9]{2})\*\*")
RANGE_RE = re.compile(r"\b([A-Z]{2})-([0-9]{2})\.\.([A-Z]{2})-([0-9]{2})\b")
SUBSET_MARKER = "[subset]"
SKIP_FILES = {"CHANGELOG.md", "PLAN.md", "docs/measured-state.md"}
SKIP_PREFIXES = ("standards/evidence/", "provenance/", "packs/", "evals/role-ab/arms/")
EXAMPLE_PREFIXES = ("exemplars/",)
DATED_KB_RE = re.compile(r"^docs/knowledge-base/[a-z0-9-]*-20[0-9]{2}-[0-9]{2}")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def defined_rules(root):
    """Return family -> set of rule numbers defined in standards/*.md."""
    counts = {}
    for path in sorted((root / STANDARD_DIR).glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        pairs = [(m.group(1), int(m.group(2))) for m in HEADING_RE.finditer(text)]
        pairs += [(m.group(1), int(m.group(2))) for m in ROW_RE.finditer(text)]
        pairs += [(m.group(1), int(m.group(2))) for m in BULLET_RE.finditer(text)]
        for family, number in pairs:
            counts.setdefault(family, set()).add(number)
    return counts


def skipped(rel):
    if rel in SKIP_FILES:
        return True
    if rel.startswith(SKIP_PREFIXES):
        return True
    return bool(DATED_KB_RE.match(rel))


def check(root):
    """Return (errors, warnings, summary) for one tree."""
    standards = root / STANDARD_DIR
    if not standards.is_dir():
        return ["missing %s under %s" % (STANDARD_DIR, root)], [], {}
    counts = defined_rules(root)
    errors = []
    warnings = []
    scanned = 0
    ranges = 0
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if skipped(rel):
            continue
        scanned += 1
        in_fence = False
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for match in RANGE_RE.finditer(line):
                family = match.group(1)
                if family != match.group(3):
                    errors.append("%s:%d %s crosses two rule families"
                                  % (rel, number, match.group(0)))
                    continue
                ranges += 1
                start = int(match.group(2))
                end = int(match.group(4))
                defined_set = counts.get(family)
                defined = max(defined_set) if defined_set else None
                if not defined_set:
                    message = "%s:%d %s names a family no standard defines" % (rel, number, match.group(0))
                    if rel.startswith(EXAMPLE_PREFIXES):
                        warnings.append(message + " (an example may define its own family)")
                    else:
                        errors.append(message)
                    continue
                missing = sorted({n for n in range(start, end + 1) if n not in defined_set})
                if missing:
                    errors.append("%s:%d %s claims %s, which does not exist (%s defines %d rules)"
                                  % (rel, number, match.group(0),
                                     ", ".join("%s-%02d" % (family, n) for n in missing),
                                     family, len(defined_set)))
                elif end < defined and start == 1 and SUBSET_MARKER not in line:
                    errors.append("%s:%d %s is stale: %s defines %d rules; add %s "
                                  "if the partial range is deliberate"
                                  % (rel, number, match.group(0), family, defined, SUBSET_MARKER))
    summary = {"files_scanned": scanned, "ranges": ranges,
               "families": {family: len(numbers) for family, numbers in sorted(counts.items())}}
    return errors, warnings, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not (root / STANDARD_DIR).is_dir():
        print("doc-ranges: cannot read %s under %s" % (STANDARD_DIR, root))
        return 2
    errors, warnings, summary = check(root)
    if args.json:
        print(json.dumps({"root": str(root), "violations": errors,
                          "warnings": warnings, "summary": summary}, indent=2))
    else:
        for error in errors:
            print("FAIL " + error)
        for warning in warnings:
            print("WARN " + warning)
        print("doc-ranges: %d file(s), %d range(s), %d violation(s), %d warning(s)"
              % (summary.get("files_scanned", 0), summary.get("ranges", 0),
                 len(errors), len(warnings)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
