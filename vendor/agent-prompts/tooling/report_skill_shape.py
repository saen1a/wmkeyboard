#!/usr/bin/env python3
"""Report the shape of every skill in a library tree.

Purpose
-------
Measure skill anatomy without judging content, so a refactor starts from
numbers instead of impressions. The report is advisory: it exits 0 even when a
skill exceeds a shape target. ``--fail-on-advisory`` promotes those rows to a
failure once a library has decided to enforce them.

Metrics per ``SKILL.md``
------------------------
- ``tokens_whole`` / ``tokens_body`` -- ``bytes / 4``, matching the library
  convention; the body excludes YAML frontmatter.
- ``lines_body`` -- body line count.
- ``h2`` / ``h3`` -- heading counts inside the body, excluding fenced code
  blocks (example headings are content, not sections).
- ``references`` -- number of ``.md`` files under a sibling ``references/`` or
  ``reference/`` directory.
- ``description_words`` -- word count of the frontmatter description, including
  folded (``>``) scalars.
- ``doctrine`` -- whether ``## Doctrine position`` is present (AP-14).
- ``rigid`` -- whether the frontmatter declares ``rigid:`` (AP-13.4).

Advisory targets (SK-03, SK-05)
-------------------------------
- body tokens <= 1,500 (target 1,200)
- H2 sections <= 8 (a body with more is usually several jobs)
- description 5-90 words
- ``## Doctrine position`` present
- a body over 2,000 tokens carries at least one reference file

These are review triggers, not a content budget; AP-01 explicitly exempts
skills from a prompt token budget. ``--fail-on-advisory`` ignores ``vendor``
rows because vendor bodies are frozen (SK-10); a vendor body may be
permanently over the cap without blocking the report.

Usage
-----
    python3 tooling/report_skill_shape.py
    python3 tooling/report_skill_shape.py --json
    python3 tooling/report_skill_shape.py --fail-on-advisory

Exit 0 on a successful report, 1 on a setup error or (with
``--fail-on-advisory``) when a non-vendor advisory target is breached.
"""

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):(.*)$")
H2_RE = re.compile(r"^##\s+")
H3_RE = re.compile(r"^###\s+")

BODY_TOKEN_CAP = 1500
H2_CAP = 8
DESC_MIN_WORDS = 5
DESC_MAX_WORDS = 90
REFERENCE_TRIGGER_TOKENS = 2000


def split_frontmatter(text):
    """Return (frontmatter, body) or (None, text) when there is no block."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    return None, text


def block_lines(lines):
    """Indented continuation lines of a YAML folded/literal block."""
    base = None
    parts = []
    for line in lines:
        if not line.strip():
            parts.append("")
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            break
        if base is None:
            base = indent
        if indent < base:
            break
        parts.append(line[base:].rstrip())
    return parts


def scalar(frontmatter, key):
    """Scalar or folded-block value for ``key``; None when absent."""
    lines = frontmatter.splitlines()
    for i, line in enumerate(lines):
        match = KEY_RE.match(line)
        if not match or match.group(1) != key:
            continue
        rest = match.group(2).strip()
        if rest in (">", ">-", ">+", "|", "|-", "|+"):
            parts = block_lines(lines[i + 1:])
            if rest.startswith("|"):
                return "\n".join(parts).strip()
            return " ".join(part for part in parts if part).strip()
        return rest.strip("'\"")
    return None


def count_reference_files(folder):
    total = 0
    for name in ("references", "reference"):
        directory = folder / name
        if directory.is_dir():
            total += len(list(directory.rglob("*.md")))
    return total


def heading_counts(body_lines):
    """Count H2/H3 headings outside fenced code blocks."""
    h2 = h3 = 0
    fence = None
    for line in body_lines:
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            marker = stripped[:3]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence is not None:
            continue
        if line.startswith("    ") or line.startswith("\t"):
            continue
        if H2_RE.match(line):
            h2 += 1
        elif H3_RE.match(line):
            h3 += 1
    return h2, h3


def measure(path, base):
    text = path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(text)
    frontmatter = frontmatter or ""
    name = scalar(frontmatter, "name") or path.parent.name
    description = scalar(frontmatter, "description") or ""
    body_lines = body.splitlines()
    h2, h3 = heading_counts(body_lines)
    relation = path.parent.relative_to(base)
    tree = relation.parts[0] if relation.parts else ""
    try:
        display = str(path.relative_to(base.parent))
    except ValueError:
        display = str(path)
    result = {
        "name": name,
        "path": display,
        "tree": tree,
        "tokens_whole": len(text.encode("utf-8")) // 4,
        "tokens_body": len(body.encode("utf-8")) // 4,
        "lines_body": len(body_lines),
        "h2": h2,
        "h3": h3,
        "references": count_reference_files(path.parent),
        "description_words": len(description.split()),
        "doctrine": "## Doctrine position" in body,
        "rigid": scalar(frontmatter, "rigid") is not None,
    }
    flags = []
    if result["tokens_body"] > BODY_TOKEN_CAP:
        flags.append("body-tokens")
    if result["h2"] > H2_CAP:
        flags.append("h2-sections")
    if not DESC_MIN_WORDS <= result["description_words"] <= DESC_MAX_WORDS:
        flags.append("description-words")
    if not result["doctrine"]:
        flags.append("no-doctrine-position")
    if result["tokens_body"] > REFERENCE_TRIGGER_TOKENS and not result["references"]:
        flags.append("no-references")
    result["advisory"] = flags
    return result


def collect(skills_dir):
    rows = [measure(path, skills_dir) for path in sorted(skills_dir.rglob("SKILL.md"))]
    rows.sort(key=lambda row: (-row["tokens_body"], row["name"]))
    return rows


def summary(rows):
    bodies = [row["tokens_body"] for row in rows]
    total = sum(bodies)
    over_cap = sum(row["tokens_body"] for row in rows
                   if "body-tokens" in row["advisory"])
    return {
        "skills": len(rows),
        "body_tokens_min": min(bodies) if bodies else 0,
        "body_tokens_median": int(statistics.median(bodies)) if bodies else 0,
        "body_tokens_max": max(bodies) if bodies else 0,
        "body_tokens_total": total,
        "over_cap_tokens": over_cap,
        "over_cap_share": round(100.0 * over_cap / total, 1) if total else 0.0,
        "over_body_cap": sum(1 for row in rows if "body-tokens" in row["advisory"]),
        "over_body_cap_non_vendor": sum(
            1 for row in rows
            if "body-tokens" in row["advisory"] and row["tree"] != "vendor"),
        "over_h2_cap": sum(1 for row in rows if "h2-sections" in row["advisory"]),
        "description_out_of_range": sum(
            1 for row in rows if "description-words" in row["advisory"]),
        "missing_doctrine": sum(
            1 for row in rows if "no-doctrine-position" in row["advisory"]),
        "missing_doctrine_non_vendor": sum(
            1 for row in rows
            if "no-doctrine-position" in row["advisory"] and row["tree"] != "vendor"),
        "big_without_references": sum(
            1 for row in rows if "no-references" in row["advisory"]),
    }


def print_table(rows, limit):
    header = ("%6s %6s %4s %4s %5s %4s %3s %2s  %s"
              % ("whole", "body", "line", "H2", "H3", "refs", "doc", "rg", "skill"))
    print(header)
    print("-" * len(header))
    for row in rows[:limit]:
        print("%6d %6d %4d %4d %5d %4d %3s %2s  %s"
              % (row["tokens_whole"], row["tokens_body"], row["lines_body"],
                 row["h2"], row["h3"], row["references"],
                 "y" if row["doctrine"] else "-",
                 "y" if row["rigid"] else "-",
                 row["path"]))
    if len(rows) > limit:
        print("... %d more (use --limit 0 for all)" % (len(rows) - limit))
    print("legend: doc=Doctrine position, rg=rigid frontmatter")
    for row in rows:
        if row["advisory"]:
            print("ADVISORY %s: %s" % (row["name"], ", ".join(row["advisory"])))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Report skill shape metrics (advisory).")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent),
                        help="repo root (default: script parent parent)")
    parser.add_argument("--skills-dir", default=None,
                        help="skills directory (default: <root>/skills)")
    parser.add_argument("--limit", type=int, default=25,
                        help="rows to print; 0 prints all (default: 25)")
    parser.add_argument("--json", action="store_true",
                        help="print a machine-readable report")
    parser.add_argument("--fail-on-advisory", action="store_true",
                        help="exit 1 when a non-vendor advisory target is "
                             "breached (vendor bodies are frozen, SK-10)")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    skills_dir = Path(args.skills_dir).resolve() if args.skills_dir \
        else root / "skills"
    if not skills_dir.is_dir():
        print("FAIL setup: skills directory not found: %s" % skills_dir)
        return 1

    rows = collect(skills_dir)
    stats = summary(rows)
    if args.json:
        print(json.dumps({"summary": stats, "skills": rows}, indent=2))
    else:
        limit = len(rows) if args.limit == 0 else args.limit
        print_table(rows, limit)
        print("skill-shape: %(skills)d skills, body tokens "
              "%(body_tokens_min)d/%(body_tokens_median)d/%(body_tokens_max)d "
              "(min/median/max), total %(body_tokens_total)d, "
              "over-cap share %(over_cap_share).1f%%" % stats)
        print("advisory breaches: body>%d=%d (non-vendor=%d), H2>%d=%d, "
              "description=%d, no-doctrine=%d (non-vendor=%d), "
              "big-no-references=%d"
              % (BODY_TOKEN_CAP, stats["over_body_cap"],
                 stats["over_body_cap_non_vendor"], H2_CAP,
                 stats["over_h2_cap"], stats["description_out_of_range"],
                 stats["missing_doctrine"],
                 stats["missing_doctrine_non_vendor"],
                 stats["big_without_references"]))

    if args.fail_on_advisory and any(
            row["advisory"] for row in rows if row["tree"] != "vendor"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
