#!/usr/bin/env python3
"""Deterministic structural validator for Tier-3 behavioral eval cases.

Tier 3 (behavioral) is on-demand: an executor model answers a case prompt with
the skill body in context and a grader model checks the answer against the
case's ``expectations[]``. That run costs tokens, so it is not a CI gate. This
tool is the free, deterministic half: it validates the case files and their
fixtures so a behavioral suite cannot silently rot (missing case, unknown
skill, bad kind, absent fixture, lost pressure coverage).

Case files live at ``evals/behavioral/<skill-name>.json``:

    {
      "skill": "<skill-name>",
      "evals": [
        {"id": "<unique>", "kind": "execution|dialogue",
         "pressure": "time|sunk_cost|authority",   # optional
         "prompt": "<case prompt>",
         "expected_output": "<what a passing answer contains>",
         "files": ["<fixture dir or file under evals/fixtures/>"],  # execution only
         "expectations": ["<verifiable statement>", ...]}
      ]
    }

The schema follows Anthropic skill-creator v2's ``evals.json`` (``id``,
``prompt``, ``expected_output``, optional ``files[]``, ``expectations[]``) plus
an optional ``kind`` and this repository's optional ``pressure`` tag. The
discipline set is fixed in ``REQUIRED_SKILLS``; every member must ship a case
file with at least ``MIN_EVALS`` cases covering all three pressure kinds.

Exit 0 when no FAIL, 1 otherwise. ``--json`` prints a machine-readable summary.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# The discipline skills that must carry pressure cases (Tier-3 design).
REQUIRED_SKILLS = [
    "anti-entropy-governance",
    "anti-hallucination",
    "anti-sycophancy",
    "verification-before-completion",
    "git-guardrails",
]
PRESSURE_KINDS = {"time", "sunk_cost", "authority"}
KINDS = {"execution", "dialogue"}
MIN_EVALS = 3

FRONTMATTER_RE = re.compile(r"(?m)^name:\s*(\S+)\s*$")


def load_skills(skills_dir):
    """Map skill name -> path for every SKILL.md under skills_dir."""
    skills = {}
    for path in sorted(skills_dir.glob("**/SKILL.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        match = FRONTMATTER_RE.search(text)
        name = match.group(1) if match else path.parent.name
        skills.setdefault(name, path)
    return skills


def load_cases(cases_dir):
    """Return (cases_by_skill, violations) for evals/behavioral/*.json."""
    violations = []
    cases = {}
    if not cases_dir.is_dir():
        return cases, [{"type": "setup", "skill": "-",
                        "detail": "cases directory not found: %s" % cases_dir}]
    for path in sorted(cases_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            violations.append({"type": "invalid-case", "skill": path.name,
                               "detail": "unreadable JSON: %s" % exc})
            continue
        if not isinstance(data, dict) or not isinstance(data.get("skill"), str) \
                or not data["skill"].strip():
            violations.append({"type": "invalid-case", "skill": path.name,
                               "detail": "missing string 'skill'"})
            continue
        skill = data["skill"].strip()
        if skill in cases:
            violations.append({"type": "duplicate-skill", "skill": skill,
                               "detail": "more than one case file declares %s" % skill})
            continue
        cases[skill] = (path, data)
    return cases, violations


def validate_case(skill, path, data, skills, fixtures_dir, violations):
    evals = data.get("evals")
    if not isinstance(evals, list) or not evals:
        violations.append({"type": "no-cases", "skill": skill,
                           "detail": "%s has no 'evals' list" % path.name})
        return set()
    if skill not in skills:
        violations.append({"type": "unknown-skill", "skill": skill,
                           "detail": "no skills/**/SKILL.md declares %s" % skill})
    if len(evals) < MIN_EVALS:
        violations.append({"type": "eval-count", "skill": skill,
                           "detail": "%d case(s); at least %d required"
                                     % (len(evals), MIN_EVALS)})
    seen_ids = set()
    pressures = set()
    for index, entry in enumerate(evals):
        where = "%s[%d]" % (path.name, index)
        if not isinstance(entry, dict):
            violations.append({"type": "invalid-eval", "skill": skill,
                               "detail": "%s is not an object" % where})
            continue
        eval_id = entry.get("id")
        if not isinstance(eval_id, str) or not eval_id.strip():
            violations.append({"type": "invalid-eval", "skill": skill,
                               "detail": "%s lacks a string 'id'" % where})
        elif eval_id in seen_ids:
            violations.append({"type": "duplicate-eval", "skill": skill,
                               "detail": "%s reuses id %r" % (where, eval_id)})
        else:
            seen_ids.add(eval_id)
        kind = entry.get("kind", "execution")
        if kind not in KINDS:
            violations.append({"type": "invalid-kind", "skill": skill,
                               "detail": "%s kind %r not in %s"
                                         % (where, kind, sorted(KINDS))})
        pressure = entry.get("pressure")
        if pressure is not None:
            if pressure not in PRESSURE_KINDS:
                violations.append({"type": "invalid-pressure", "skill": skill,
                                   "detail": "%s pressure %r not in %s"
                                             % (where, pressure, sorted(PRESSURE_KINDS))})
            else:
                pressures.add(pressure)
        for field in ("prompt", "expected_output"):
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                violations.append({"type": "invalid-eval", "skill": skill,
                                   "detail": "%s lacks a non-empty %r" % (where, field)})
        expectations = entry.get("expectations")
        if not isinstance(expectations, list) or not expectations \
                or not all(isinstance(e, str) and e.strip() for e in expectations):
            violations.append({"type": "invalid-eval", "skill": skill,
                               "detail": "%s 'expectations' must be a non-empty list of strings"
                                         % where})
        files = entry.get("files")
        if kind == "execution":
            if not isinstance(files, list) or not files:
                violations.append({"type": "invalid-eval", "skill": skill,
                                   "detail": "%s execution case requires non-empty 'files'"
                                             % where})
            else:
                for rel in files:
                    if not isinstance(rel, str) or not rel.strip():
                        violations.append({"type": "invalid-eval", "skill": skill,
                                           "detail": "%s has a non-string fixture path" % where})
                        continue
                    target = fixtures_dir / rel
                    if not target.exists():
                        violations.append({"type": "missing-fixture", "skill": skill,
                                           "detail": "%s references absent fixture %s"
                                                     % (where, rel)})
        elif files is not None and not isinstance(files, list):
            violations.append({"type": "invalid-eval", "skill": skill,
                               "detail": "%s 'files' must be a list when present" % where})
    return pressures


def run_checks(skills, cases, fixtures_dir):
    violations = []
    checks = 0
    for skill, (path, data) in sorted(cases.items()):
        pressures = validate_case(skill, path, data, skills, fixtures_dir, violations)
        checks += 1
        if skill in REQUIRED_SKILLS and pressures != PRESSURE_KINDS:
            missing = sorted(PRESSURE_KINDS - pressures)
            violations.append({"type": "pressure-coverage", "skill": skill,
                               "detail": "missing pressure kind(s): %s" % ", ".join(missing)})
    for skill in REQUIRED_SKILLS:
        if skill not in cases:
            violations.append({"type": "missing-skill", "skill": skill,
                               "detail": "no evals/behavioral/%s.json" % skill})
    return checks, violations


def main(argv=None):
    root_default = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Deterministic structural validator for Tier-3 behavioral eval cases.")
    parser.add_argument("--library-root", default=None,
                        help="library repo root (overrides --root for skills/ and evals/ discovery)")
    parser.add_argument("--root", default=str(root_default),
                        help="repo root (default: script parent parent)")
    parser.add_argument("--skills-dir", default=None,
                        help="skills directory (default: <root>/skills)")
    parser.add_argument("--cases-dir", default=None,
                        help="behavioral case files (default: <root>/evals/behavioral)")
    parser.add_argument("--fixtures-dir", default=None,
                        help="fixture root (default: <root>/evals/fixtures)")
    parser.add_argument("--json", action="store_true",
                        help="print a machine-readable summary to stdout")
    args = parser.parse_args(argv)

    root = Path(args.library_root).resolve() if args.library_root \
        else Path(args.root).resolve()
    skills_dir = Path(args.skills_dir).resolve() if args.skills_dir \
        else root / "skills"
    cases_dir = Path(args.cases_dir).resolve() if args.cases_dir \
        else root / "evals" / "behavioral"
    fixtures_dir = Path(args.fixtures_dir).resolve() if args.fixtures_dir \
        else root / "evals" / "fixtures"

    if not skills_dir.is_dir():
        print("FAIL setup: %s: skills directory not found" % skills_dir)
        if args.json:
            print(json.dumps({"skills": 0, "cases": 0, "checks": 0,
                              "violations": [{"type": "setup", "skill": "-",
                                              "detail": "skills directory not found"}]}))
        return 1

    skills = load_skills(skills_dir)
    cases, early = load_cases(cases_dir)
    checks, violations = run_checks(skills, cases, fixtures_dir)
    violations = sorted(early + violations,
                        key=lambda v: (v["type"], v["skill"], v["detail"]))

    if args.json:
        print(json.dumps({"skills": len(skills), "cases": len(cases),
                          "checks": checks, "violations": violations}))
    else:
        for v in violations:
            print("FAIL %s: %s: %s" % (v["type"], v["skill"], v["detail"]))
        print("behavioral-evals: %d skills, %d case files, %d violation(s)"
              % (len(skills), len(cases), len(violations)))

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
