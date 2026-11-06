#!/usr/bin/env python3
"""Validate the model-surface registry: coverage, budgets and rule citations.

Every string a model reads is a registered surface with a token budget, and
every rule ID it cites resolves to a definition in that family's standard -- a
`## XX-NN -- ` heading or a `| XX-NN |` table row -- (AP-01,
SK-03). The registry records the measured maximum per surface so budget drift
is visible before it reaches a prompt.

Usage:
    python3 tooling/check_model_surface.py [--root PATH] [--registry PATH] [--json]

A consumer that scans its own checkout while the registry lives elsewhere (for
example a vendored copy of this tool under its own standards directory) points
the checker at it explicitly:

    python3 vendor/tooling/check_model_surface.py --root . \
        --registry standards/model-surface.json

--registry overrides only the registry location. Relative paths for --root and
--registry resolve against the current working directory, not against each
other, and globs plus rule citations always resolve against --root. The default
registry is <root>/standards/model-surface.json.

Exit 0 clean, 1 violations, 2 unreadable or invalid registry. ASCII-only output.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from statistics import median

SCHEMA = "agent-model-surface/1"
TOP_KEYS = {"schema", "version", "surfaces", "rule_families", "allow_unresolved"}
REQUIRED = {"schema", "version", "surfaces", "rule_families"}
SURFACE_KEYS = {"id", "glob", "kind", "budget_tokens", "measured_max_tokens", "rationale"}
SURFACE_REQUIRED = {"id", "glob", "kind", "budget_tokens", "measured_max_tokens", "rationale"}
KINDS = ("role", "task", "workspace", "fragment", "skill", "command", "adapter", "preset")
ALLOW_KEYS = {"citation", "path", "reason", "review_by"}
ALLOW_REQUIRED = {"citation", "path", "reason", "review_by"}
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
GLOB_RE = re.compile(r"^(?!/)(?!.*\.\.)[A-Za-z0-9._*?/\[\]-]+$")
FAMILY_RE = re.compile(r"^[A-Z]{2}$")
FAMILY_PATH_RE = re.compile(r"^standards/[A-Za-z0-9._/-]+\.md$")
CITATION_RE = re.compile(r"\b([A-Z]{2})-([0-9]{2})(?:\.[0-9]+)?\b")
HEADING_RE = re.compile(r"^## ([A-Z]{2}-[0-9]{2}) -- ", re.MULTILINE)
ROW_RE = re.compile(r"^\|\s*([A-Z]{2}-[0-9]{2})\s*\|", re.MULTILINE)
BULLET_RE = re.compile(r"^\s*[-*]\s*\*\*([A-Z]{2}-[0-9]{2})\*\*", re.MULTILINE)
ASSET_SUFFIXES = {".md", ".txt", ".yml", ".yaml"}
WILDCARDS = "*?["


def ascii_text(value):
    return str(value).encode("ascii", "backslashreplace").decode("ascii")


def token_estimate(path):
    return max(1, len(path.read_bytes()) // 4)


def scope_of(glob):
    """Deepest concrete directory prefix and literal basename, if any."""
    parts = glob.split("/")
    wildcard_at = None
    for index, part in enumerate(parts):
        if any(char in part for char in WILDCARDS):
            wildcard_at = index
            break
    if wildcard_at is None:
        return "/".join(parts[:-1]), parts[-1]
    literal = None
    if not any(char in parts[-1] for char in WILDCARDS):
        literal = parts[-1]
    return "/".join(parts[:wildcard_at]), literal


def in_scope(rel, surface):
    root_dir, literal = scope_of(surface["glob"])
    if root_dir and not rel.startswith(root_dir + "/"):
        return False
    if literal is not None:
        return rel.rsplit("/", 1)[-1] == literal
    return Path(rel).suffix in ASSET_SUFFIXES


def positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def shape(registry):
    """Validate registry shape; return errors plus the usable declarations."""
    errors = []
    if not isinstance(registry, dict):
        return ["registry must be a JSON object"], [], {}, []
    for key in sorted(registry):
        if key not in TOP_KEYS:
            errors.append("unknown top-level key: %s" % key)
    for key in sorted(REQUIRED):
        if key not in registry:
            errors.append("missing top-level key: %s" % key)
    if registry.get("schema") != SCHEMA:
        errors.append("schema must be %s" % SCHEMA)
    version = registry.get("version")
    if not isinstance(version, str) or not SEMVER_RE.match(version):
        errors.append("version must be semver")

    surfaces = []
    declared = registry.get("surfaces")
    if not isinstance(declared, list) or not declared:
        errors.append("surfaces must be a non-empty list")
        declared = []
    seen = set()
    for index, surface in enumerate(declared):
        label = "surfaces[%d]" % index
        if not isinstance(surface, dict):
            errors.append("%s is not an object" % label)
            continue
        for key in sorted(surface):
            if key not in SURFACE_KEYS:
                errors.append("%s unknown key: %s" % (label, key))
        for key in sorted(SURFACE_REQUIRED):
            if key not in surface:
                errors.append("%s missing %s" % (label, key))
        valid = True
        surface_id = surface.get("id")
        if not isinstance(surface_id, str) or not ID_RE.match(surface_id):
            errors.append("%s id is not a valid surface id: %s" % (label, ascii_text(surface_id)))
            valid = False
        elif surface_id in seen:
            errors.append("%s duplicate surface id: %s" % (label, surface_id))
            valid = False
        else:
            seen.add(surface_id)
        glob = surface.get("glob")
        if not isinstance(glob, str) or not GLOB_RE.match(glob):
            errors.append("%s glob is not a sane relative glob: %s" % (label, ascii_text(glob)))
            valid = False
        elif any(char in glob.split("/")[0] for char in WILDCARDS):
            errors.append("%s glob must start with a concrete directory: %s" % (label, glob))
            valid = False
        if surface.get("kind") not in KINDS:
            errors.append("%s kind must be one of: %s" % (label, ", ".join(KINDS)))
            valid = False
        if not positive_int(surface.get("budget_tokens")):
            errors.append("%s budget_tokens must be a positive integer" % label)
            valid = False
        if not positive_int(surface.get("measured_max_tokens")):
            errors.append("%s measured_max_tokens must be a positive integer" % label)
            valid = False
        rationale = surface.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            errors.append("%s rationale is empty" % label)
            valid = False
        if valid:
            surfaces.append(surface)

    families = {}
    declared = registry.get("rule_families")
    if not isinstance(declared, dict) or not declared:
        errors.append("rule_families must be a non-empty object")
        declared = {}
    for family in sorted(declared):
        path = declared[family]
        if not FAMILY_RE.match(family):
            errors.append("rule_families key is not a two-letter family: %s" % ascii_text(family))
        elif not isinstance(path, str) or not FAMILY_PATH_RE.match(path):
            errors.append("rule_families.%s must be a standards/*.md path: %s"
                          % (family, ascii_text(path)))
        else:
            families[family] = path

    allow = []
    declared = registry.get("allow_unresolved", [])
    if not isinstance(declared, list):
        errors.append("allow_unresolved must be a list")
        declared = []
    for index, entry in enumerate(declared):
        label = "allow_unresolved[%d]" % index
        if not isinstance(entry, dict):
            errors.append("%s is not an object" % label)
            continue
        for key in sorted(entry):
            if key not in ALLOW_KEYS:
                errors.append("%s unknown key: %s" % (label, key))
        for key in sorted(ALLOW_REQUIRED):
            if key not in entry:
                errors.append("%s missing %s" % (label, key))
        valid = True
        citation = entry.get("citation")
        if not isinstance(citation, str) or not re.match(r"^[A-Z]{2}-[0-9]{2}(\.[0-9]+)?$", citation):
            errors.append("%s citation is not a rule ID: %s" % (label, ascii_text(citation)))
            valid = False
        path = entry.get("path")
        if not isinstance(path, str) or not path.strip():
            errors.append("%s path is empty" % label)
            valid = False
        reason = entry.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append("%s reason is empty" % label)
            valid = False
        review_by = entry.get("review_by")
        try:
            date.fromisoformat(review_by)
        except (TypeError, ValueError):
            errors.append("%s review_by must be an ISO date: %s" % (label, ascii_text(review_by)))
            valid = False
        if valid:
            allow.append(entry)
    return errors, surfaces, families, allow


def rules_in(text):
    """Rule ids a standard defines: headings, `| XX-NN |` rows, or `- **XX-NN**` bullets.

    A standard may define its rules as a table (halt-taxonomy) or as bold
    bullets (english-only), so a heading-only resolver would call every citation
    of such a rule dangling. `tooling/check_doc_ranges.py` counts the same three
    shapes; keep the two in step.
    """
    return (set(HEADING_RE.findall(text)) | set(ROW_RE.findall(text))
            | set(BULLET_RE.findall(text)))


def check(registry, root):
    """Return (errors, warnings, summary) for a registry evaluated at root."""
    root = Path(root).resolve()
    errors, warnings = [], []
    shape_errors, surfaces, families, allow = shape(registry)
    errors.extend(shape_errors)

    per_surface = {}
    file_surfaces = {}
    for surface in surfaces:
        surface_id = surface["id"]
        try:
            hits = sorted(path for path in root.glob(surface["glob"]) if path.is_file())
        except (ValueError, NotImplementedError) as exc:
            errors.append("surface %s glob cannot be evaluated: %s" % (surface_id, ascii_text(exc)))
            hits = []
        if not hits:
            errors.append("surface %s glob matches no file: %s" % (surface_id, surface["glob"]))
        per_surface[surface_id] = hits
        for hit in hits:
            rel = hit.relative_to(root).as_posix()
            file_surfaces.setdefault(rel, []).append(surface_id)

    for rel in sorted(file_surfaces):
        owners = file_surfaces[rel]
        if len(owners) > 1:
            errors.append("file is matched by more than one surface (%s): %s"
                          % (", ".join(sorted(owners)), ascii_text(rel)))

    registered = set(file_surfaces)
    reported = set()
    for surface in surfaces:
        root_dir, _literal = scope_of(surface["glob"])
        base = root / root_dir if root_dir else root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if rel in registered or rel in reported:
                continue
            if in_scope(rel, surface):
                reported.add(rel)
                errors.append("unregistered asset inside a registered root: %s" % ascii_text(rel))

    tokens = {rel: token_estimate(root / rel) for rel in sorted(file_surfaces)}
    for surface in surfaces:
        surface_id = surface["id"]
        files = per_surface.get(surface_id, [])
        if not files:
            continue
        budget = surface["budget_tokens"]
        values = [tokens[path.relative_to(root).as_posix()] for path in files]
        offenders = [(tokens[path.relative_to(root).as_posix()],
                      path.relative_to(root).as_posix()) for path in files
                     if tokens[path.relative_to(root).as_posix()] > budget]
        if offenders:
            offenders.sort(reverse=True)
            top = ", ".join("%s (%d tokens)" % (ascii_text(rel), count)
                            for count, rel in offenders[:3])
            errors.append("surface %s is over budget %d: %d file(s) exceed it; top offenders: %s"
                          % (surface_id, budget, len(offenders), top))
        current_max = max(values)
        if current_max != surface["measured_max_tokens"]:
            warnings.append("surface %s records measured_max_tokens=%d but the current max is %d"
                            % (surface_id, surface["measured_max_tokens"], current_max))
        if len(values) < 2:
            warnings.append("surface %s covers a single file" % surface_id)
        elif median(values) < budget * 0.25:
            warnings.append("surface %s budget is loose: median %d is below 25%% of %d"
                            % (surface_id, int(median(values)), budget))

    headings = {}
    for family in sorted(families):
        target = root / families[family]
        if not target.is_file():
            errors.append("missing rule family file for %s: %s" % (family, ascii_text(families[family])))
            continue
        text = target.read_text(encoding="utf-8", errors="replace")
        headings[family] = rules_in(text)

    standards = root / "standards"
    defined = {}
    if standards.is_dir():
        for path in sorted(standards.glob("*.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for rule in rules_in(text):
                defined.setdefault(rule.split("-")[0], path.relative_to(root).as_posix())
    for family in sorted(defined):
        if family not in families:
            errors.append("rule family %s is defined in %s but not registered in rule_families"
                          % (family, ascii_text(defined[family])))

    allowed = {(entry["citation"], entry["path"]) for entry in allow}
    cited = set()
    unresolved = 0
    citations = 0
    for rel in sorted(file_surfaces):
        text = (root / rel).read_text(encoding="utf-8", errors="replace")
        for match in CITATION_RE.finditer(text):
            family, number = match.group(1), match.group(2)
            if family not in families:
                continue
            citations += 1
            citation = match.group(0)
            rule = "%s-%s" % (family, number)
            cited.add((citation, rel))
            if family not in headings or rule in headings[family]:
                continue
            if (citation, rel) in allowed:
                continue
            unresolved += 1
            errors.append("citation %s in %s does not resolve to a definition in %s"
                          % (citation, ascii_text(rel), families[family]))

    today = date.today()
    for entry in allow:
        citation = entry["citation"]
        rel = entry["path"]
        if rel not in file_surfaces:
            errors.append("allow_unresolved path is not a surface file: %s" % ascii_text(rel))
            continue
        if date.fromisoformat(entry["review_by"]) < today:
            errors.append("allow_unresolved entry for %s in %s expired on %s"
                          % (citation, ascii_text(rel), entry["review_by"]))
        if (citation, rel) not in cited:
            errors.append("allow_unresolved entry for %s in %s is stale: the citation is gone"
                          % (citation, ascii_text(rel)))
            continue
        family, rule = citation.split("-")[0], citation.split(".")[0]
        if family in headings and rule in headings[family]:
            errors.append("allow_unresolved entry for %s in %s is unnecessary: it resolves in %s"
                          % (citation, ascii_text(rel), families[family]))

    summary = {
        "surfaces": len(surfaces),
        "files": len(file_surfaces),
        "total_tokens": sum(tokens.values()),
        "citations": citations,
        "unresolved": unresolved,
    }
    return errors, warnings, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None,
                        help="tree to check; defaults to this repository")
    parser.add_argument("--registry", default=None, metavar="PATH",
                        help="registry JSON path; a relative path resolves against the "
                             "current working directory, not --root; defaults to "
                             "<root>/standards/model-surface.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent
    registry_path = Path(args.registry) if args.registry \
        else root / "standards" / "model-surface.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("model-surface: cannot read %s: %s" % (ascii_text(registry_path), ascii_text(exc)))
        return 2
    if not isinstance(registry, dict):
        print("model-surface: registry must be a JSON object")
        return 2
    errors, warnings, summary = check(registry, root)
    if args.json:
        payload = dict(summary)
        payload["registry"] = str(registry_path)
        payload["violations"] = errors
        payload["warnings"] = warnings
        print(json.dumps(payload, indent=2))
    else:
        for error in errors:
            print("FAIL " + error)
        for warning in warnings:
            print("WARN " + warning)
        print("model-surface: %d surfaces, %d files, %d tokens, %d citation(s), %d unresolved, %d violation(s)"
              % (summary["surfaces"], summary["files"], summary["total_tokens"],
                 summary["citations"], summary["unresolved"], len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
