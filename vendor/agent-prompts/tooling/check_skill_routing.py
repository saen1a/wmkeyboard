#!/usr/bin/env python3
"""Deterministic lexical checker for skill trigger routing (Tier 2).

Purpose
-------
Test, without any model judgement, that a skill's trigger vocabulary is
discoverable and distinct:

1. Trigger-positive prompts must RANK their skill inside the top-k of all
   skill descriptions by a lexical (cosine-like token-overlap) score.
2. Trigger-negative prompts owned by another skill must NOT pull this skill
   into the top-k (a named skill in the owner's top-k is a misroute).
3. No two skill descriptions are near-collisions (high Jaccard), which would
   make routing ambiguous.

This is a lexical approximation only. It catches missing trigger vocabulary
and over-broad descriptions. Semantic trigger judgement is out of scope.

Skill universe
--------------
Every ``SKILL.md`` under ``<root>/skills/**``. A skill's name is the
frontmatter ``name:`` value, falling back to the directory name. Its
description is the frontmatter ``description:`` value (folded/joined); legacy
H1-only files fall back to the first paragraph after the H1.

Case files
----------
``<root>/evals/trigger/<skill-name>.json``, one per skill::

    {"skill": "verification-before-completion",
     "positive": [{"prompt": "...", "top_k": 3}],
     "negative": [{"prompt": "...", "owner": "other-skill-name"}]}

A skill without a case file is a ``WARN no trigger cases`` (a FAIL with
``--fail-on-warn``). A case file for an unknown skill, or two case files that
declare the same skill, is a FAIL.

Scoring
-------
``normalize`` lowercases, splits on non-alphanumerics, drops a small English
stopword list, applies a naive suffix stem, and dedupes to a token set.
``score = |prompt & desc| / sqrt(|prompt| * |desc|)`` (0 when either is
empty). Rank 1 is the best score; ties break by skill name.

Output
------
One ``FAIL <type>: <skill>: <detail>`` line per violation, then
``skill-routing: N skills, M case files, V violations``. ``--json`` prints the
machine-readable summary instead::

    {"skills": <int>, "cases": <int>, "checks": <int>,
     "violations": [{"type": <str>, "skill": <str>, "detail": <str>}]}

Exit 0 when there is no FAIL, 1 otherwise. ``--fail-on-warn`` turns missing
case files into FAILs.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

# --- normalization ---------------------------------------------------------

# Small English stopword list. Keeps lexical scoring focused on content terms
# shared by prompts and descriptions, not on connective boilerplate.
STOPWORDS = frozenset("""
a about above after again against all also am an and any are as at be because
been before being below between both but by can cannot could did do does doing
down during each few for from further had has have having he her here hers him
his how i if in into is it its itself just me more most must my no nor not of
off on once only or other our out over own same she should so some such than
that the their them then there these they this those through to too under until
up upon use used using very was we were what when where which while who whom
why will with would you your yours
""".split())

# Applied in order; a suffix is stripped only when the remainder is >= 3 chars.
SUFFIXES = ("ization", "ations", "ing", "ies", "ed", "es", "s")

TOKEN_RE = re.compile(r"[^a-z0-9]+")
H1_RE = re.compile(r"^#\s+\S")
KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):(.*)$")


def stem(token):
    """Naive suffix stem, applied once, first matching suffix wins."""
    for suffix in SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            if suffix == "ies":
                return token[:-3] + "y"
            return token[: -len(suffix)]
    return token


def normalize(text):
    """Lowercase -> tokenize -> drop stopwords -> stem -> dedupe token set."""
    tokens = set()
    for raw in TOKEN_RE.split((text or "").lower()):
        if not raw or raw in STOPWORDS:
            continue
        tok = stem(raw)
        if not tok or tok in STOPWORDS:
            continue
        tokens.add(tok)
    return tokens


def score(prompt_tokens, desc_tokens):
    """Cosine-like overlap in [0, 1]; 0 when either side is empty."""
    if not prompt_tokens or not desc_tokens:
        return 0.0
    return len(prompt_tokens & desc_tokens) / math.sqrt(
        len(prompt_tokens) * len(desc_tokens))


def jaccard(a, b):
    if not a and not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


# --- frontmatter / description extraction ----------------------------------


class Skill(object):
    def __init__(self, name, path, description):
        self.name = name
        self.path = path
        self.description = description
        self.tokens = normalize(description)


def read_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i])
    return None


def unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _block(lines):
    """Indented continuation lines of a YAML block scalar."""
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


def scalar_value(frontmatter, key):
    lines = frontmatter.splitlines()
    for i, line in enumerate(lines):
        match = KEY_RE.match(line)
        if not match or match.group(1) != key:
            continue
        rest = match.group(2).strip()
        if rest in (">", ">-", ">+", "|", "|-", "|+"):
            parts = _block(lines[i + 1:])
            if rest.startswith("|"):
                return "\n".join(parts).strip()
            return " ".join(part for part in parts if part).strip()
        return unquote(rest).strip()
    return None


def first_h1_paragraph(text):
    """First paragraph after the first H1 (legacy H1-only skill files)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not H1_RE.match(line):
            continue
        parts = []
        for cont in lines[i + 1:]:
            if not cont.strip():
                if parts:
                    break
                continue
            if cont.lstrip().startswith("#"):
                break
            parts.append(cont.strip())
        return " ".join(parts).strip()
    return ""


def load_skills(skills_dir):
    skills = []
    for path in sorted(skills_dir.rglob("SKILL.md")):
        text = path.read_text(encoding="utf-8")
        frontmatter = read_frontmatter(text)
        name = None
        description = None
        if frontmatter is not None:
            name = scalar_value(frontmatter, "name")
            description = scalar_value(frontmatter, "description")
        if not name:
            name = path.parent.name
        if not description:
            description = first_h1_paragraph(text)
        skills.append(Skill(name=name, path=path, description=description or ""))
    return skills


# --- checks ----------------------------------------------------------------


def ranked_skills(prompt_tokens, skills):
    return sorted(skills,
                  key=lambda s: (-score(prompt_tokens, s.tokens), s.name))


def load_cases(cases_dir):
    """Return (cases, violations). cases: ordered list of (path, data)."""
    cases = []
    violations = []
    if not cases_dir.is_dir():
        return cases, violations
    for path in sorted(cases_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            violations.append(_v("invalid-case", path.stem,
                                 "cannot parse case file: %s" % exc))
            continue
        if not isinstance(data, dict) or not isinstance(data.get("skill"), str) \
                or not data.get("skill").strip():
            violations.append(_v("invalid-case", path.stem,
                                 "missing string 'skill' field"))
            continue
        cases.append((path, data))
    return cases, violations


def _v(vtype, skill, detail):
    return {"type": vtype, "skill": skill, "detail": detail}


def run_checks(skills, cases, top_k, collision_threshold):
    violations = []
    checks = 0

    by_name = {}
    for skill in skills:
        if skill.name in by_name:
            violations.append(_v("duplicate-skill", skill.name,
                                 "two SKILL.md files share this name: %s and %s"
                                 % (by_name[skill.name].path, skill.path)))
        else:
            by_name[skill.name] = skill

    case_map = {}
    for path, data in cases:
        name = data["skill"].strip()
        checks += 1
        if name not in by_name:
            violations.append(_v("unknown-skill", name,
                                 "case file %s names a skill that does not "
                                 "exist" % path.name))
            continue
        if name in case_map:
            violations.append(_v("duplicate-case", name,
                                 "more than one case file declares this skill "
                                 "(%s)" % path.name))
            continue
        case_map[name] = (path, data)

    for skill in skills:
        checks += 1
        if skill.name in case_map:
            continue
        # Warning by default; is_fail() promotes it under --fail-on-warn.
        violations.append(_v("no-trigger-cases", skill.name,
                             "no case file at evals/trigger/%s.json"
                             % skill.name))

    for name in sorted(case_map):
        path, data = case_map[name]
        skill = by_name[name]
        positives = data.get("positive") or []
        negatives = data.get("negative") or []
        if not isinstance(positives, list) or not isinstance(negatives, list):
            violations.append(_v("invalid-case", name,
                                 "positive/negative must be lists"))
            continue
        for entry in positives:
            checks += 1
            if not isinstance(entry, dict) or not isinstance(
                    entry.get("prompt"), str):
                violations.append(_v("invalid-case", name,
                                     "positive entry lacks a prompt"))
                continue
            prompt = entry["prompt"]
            k = entry.get("top_k", top_k)
            if not isinstance(k, int) or k < 1:
                k = top_k
            ranking = ranked_skills(normalize(prompt), skills)
            rank = next(i + 1 for i, s in enumerate(ranking)
                        if s.name == name)
            if rank > k:
                violations.append(_v(
                    "positive-rank", name,
                    'prompt "%s" ranked %d (top_k %d)' % (prompt, rank, k)))
        for entry in negatives:
            checks += 1
            if not isinstance(entry, dict) or not isinstance(
                    entry.get("prompt"), str):
                violations.append(_v("invalid-case", name,
                                     "negative entry lacks a prompt"))
                continue
            prompt = entry["prompt"]
            owner = entry.get("owner")
            if not isinstance(owner, str) or owner not in by_name:
                violations.append(_v(
                    "unknown-owner", name,
                    'prompt "%s" names owner %r that does not exist'
                    % (prompt, owner)))
                continue
            ranking = ranked_skills(normalize(prompt), skills)
            rank = next(i + 1 for i, s in enumerate(ranking)
                        if s.name == name)
            if rank <= top_k:
                violations.append(_v(
                    "negative-trigger", name,
                    'prompt "%s" (owner %s) ranked %d (top_k %d)'
                    % (prompt, owner, rank, top_k)))

    ordered = sorted(skills, key=lambda s: s.name)
    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            checks += 1
            a, b = ordered[i], ordered[j]
            value = jaccard(a.tokens, b.tokens)
            if value >= collision_threshold:
                violations.append(_v(
                    "collision", "%s <-> %s" % (a.name, b.name),
                    "jaccard=%.2f" % value))

    violations = sorted(violations,
                        key=lambda v: (v["type"], v["skill"], v["detail"]))
    return checks, violations


def is_fail(violation, fail_on_warn):
    if violation["type"] == "no-trigger-cases":
        return fail_on_warn
    return True


def main(argv=None):
    root_default = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Deterministic lexical skill trigger-routing checker.")
    parser.add_argument("--library-root", default=None,
                        help="library repo root to operate on (overrides --root for skills/ and evals/trigger discovery)")
    parser.add_argument("--root", default=str(root_default),
                        help="repo root (default: script parent parent)")
    parser.add_argument("--skills-dir", default=None,
                        help="skills directory (default: <root>/skills)")
    parser.add_argument("--cases-dir", default=None,
                        help="case files directory (default: <root>/evals/trigger)")
    parser.add_argument("--top-k", type=int, default=3,
                        help="default top-k for rankings (default: 3)")
    parser.add_argument("--collision-threshold", type=float, default=0.55,
                        help="Jaccard threshold for description collisions "
                             "(default: 0.55)")
    parser.add_argument("--fail-on-warn", action="store_true",
                        help="turn missing case files into failures")
    parser.add_argument("--json", action="store_true",
                        help="print a machine-readable summary to stdout")
    args = parser.parse_args(argv)

    root = Path(args.library_root).resolve() if args.library_root \
        else Path(args.root).resolve()
    skills_dir = Path(args.skills_dir).resolve() if args.skills_dir \
        else root / "skills"
    cases_dir = Path(args.cases_dir).resolve() if args.cases_dir \
        else root / "evals" / "trigger"

    if not skills_dir.is_dir():
        print("FAIL setup: %s: skills directory not found" % skills_dir)
        if args.json:
            print(json.dumps({"skills": 0, "cases": 0, "checks": 1,
                              "violations": [_v("setup", str(skills_dir),
                                                "skills directory not found")]}))
        return 1

    skills = load_skills(skills_dir)
    cases, early = load_cases(cases_dir)
    checks, violations = run_checks(skills, cases, args.top_k,
                                    args.collision_threshold)
    violations = sorted(early + violations,
                        key=lambda v: (v["type"], v["skill"], v["detail"]))

    fails = [v for v in violations if is_fail(v, args.fail_on_warn)]

    if args.json:
        print(json.dumps({
            "skills": len(skills),
            "cases": len(cases),
            "checks": checks,
            "violations": violations,
        }))
    else:
        for v in violations:
            label = "FAIL" if is_fail(v, args.fail_on_warn) else "WARN"
            print("%s %s: %s: %s" % (label, v["type"], v["skill"], v["detail"]))
        print("skill-routing: %d skills, %d case files, %d violations"
              % (len(skills), len(cases), len(fails)))

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
