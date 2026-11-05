#!/usr/bin/env python3
"""Structural validator for the agent-prompts template library.

Validates every file under ``agents/**`` (and ``prompts/tasks/*.md`` when present);
falls back to the legacy ``roles/`` / ``tasks/`` roots with a warning.
against the quality bar in ``docs/TEMPLATE-GUIDE.md`` and ``PLAN.md``:

1. Frontmatter parses and carries every required key; enums validate and the
   template id starts with its domain prefix.
2. Body block order: exactly one each of role, hard_rules, doctrine, (workflow
   or, for review tracks, scope),
   conduct, output, in that order; no other top-level tags; output last; the
   workflow block is prose (no list markers).
3. The doctrine block is byte-identical to fragments/agent-doctrine.md; the
   conduct block matches the fragment mapped from conduct_variant, compared
   byte-exact.
4. Element budget: role 1 + list-marker lines outside doctrine/conduct +
   doctrine 1 + workflow 1 + conduct 1 + output 1, capped per budget_tier.
   The AP-01 token target is an advisory WARN (standard 1000, dual 950,
   primary 1100); it never fails the run.
5. Hygiene: ASCII only, no plan-internal counters or ids.
6. read-only templates must not name mutating-tool verbs in the output block.
7. Every ``{{TOKEN}}`` used in the body is declared in required_slots or
   optional_slots.
8. With --instantiate, every discovered file must contain no ``{{...}}`` slot
   residue; without the flag slots are allowed (templates).

The read-only check (rule 6) is a deliberately simple, documented heuristic:
it matches the literal tool verbs ``Edit``, ``Write``, ``rm ``,
``git push``, ``docker compose up`` and ``restart`` inside the output block,
so prose such as "Write exactly ..." is flagged and must be reworded.

Exit 0 when clean, 1 when any violation is found. Each violation prints as
``FAIL <file>: <message>``.
"""

import argparse
import os
import re
import sys
from pathlib import Path

REQUIRED_KEYS = [
    "id",
    "name",
    "domain",
    "purpose",
    "status",
    "version",
    "source_archetypes",
    "runtimes",
    "budget_tier",
    "tool_profile",
    "owned_phases",
    "handoff",
    "evidence_style",
    "required_slots",
    "conduct_variant",
    "fragment_versions",
    "suggested_projects",
    "created",
    "updated",
]

DOMAINS = [
    "orchestration",
    "engineering",
    "design",
    "review",
    "research",
    "documentation",
    "operations",
    "networking",
    "tabletop",
]

STATUSES = ["stable", "draft", "speculative"]
BUDGET_TIERS = {"standard": 12, "dual-workflow": 15, "primary": 15}
TOOL_PROFILES = ["orchestrator", "read-only", "gated-write", "doc-write", "batch-write"]
EVIDENCE_STYLES = ["none", "claim-label", "severity", "both"]
CONDUCT_VARIANTS = ["kilo", "dsh-ha", "dsh-preset", "omp"]
CONDUCT_FRAGMENTS = {
    "kilo": "agent-conduct.md",
    "dsh-ha": "agent-conduct.dsh-ha.md",
    "dsh-preset": "agent-conduct.dsh-preset.md",
    "omp": "agent-conduct.omp.md",
}
OWNED_PHASES = ["Plan", "PlanReview", "Implement", "Review", "Fix", "Verify", "Push"]
RUNTIMES = ["kilo", "dsh"]
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

BLOCK_ORDER = ["role", "hard_rules", "doctrine", "workflow", "conduct", "output"]
# Scope-variant order (review tracks): the lens/ownership block replaces workflow.
SCOPE_ORDER = ["role", "hard_rules", "doctrine", "scope", "conduct", "output"]
# Workflow+scope order (review lead): phase map + scope contract both present.
WORKFLOW_SCOPE_ORDER = ["role", "hard_rules", "doctrine", "workflow", "scope", "conduct", "output"]
KNOWN_BLOCK_TAGS = set(BLOCK_ORDER) | {"scope"}

SLOT_RE = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")
LIST_MARKER_RE = re.compile(r"^(- |\d+\. )")
MUTATING_VERBS = [
    (re.compile(r"\bEdit\b"), "Edit"),
    (re.compile(r"\bWrite\b"), "Write"),
    (re.compile(r"\brm\s"), "rm "),
    (re.compile(r"git push"), "git push"),
    (re.compile(r"docker compose up"), "docker compose up"),
    (re.compile(r"\brestart\b"), "restart"),
]


def default_root():
    return Path(__file__).resolve().parent.parent


def unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def split_top(text, sep=","):
    """Split on ``sep`` but never inside a single- or double-quoted span."""
    parts = []
    quote = None
    current = ""
    for ch in text:
        if quote:
            current += ch
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            current += ch
        elif ch == sep:
            parts.append(current)
            current = ""
        else:
            current += ch
    parts.append(current)
    return parts


def parse_value(raw):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [unquote(p) for p in split_top(inner)]
    if raw.startswith("{") and raw.endswith("}"):
        inner = raw[1:-1].strip()
        out = {}
        if not inner:
            return out
        for part in split_top(inner):
            if ":" in part:
                key, value = part.split(":", 1)
                out[key.strip()] = unquote(value)
        return out
    return unquote(raw)


def parse_frontmatter(text):
    """Return (mapping, error). Minimal line-based YAML-ish parser."""
    if not text.startswith("---"):
        return None, "missing frontmatter (file must start with ---)"
    lines = text.split("\n")
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        return None, "unterminated frontmatter (no closing ---)"
    data = {}
    for number, line in enumerate(lines[1:end], start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            return None, "unparsable frontmatter line %d (content withheld)" % number
        key, raw = stripped.split(":", 1)
        data[key.strip()] = parse_value(raw)
    return data, None


def strict_yaml_errors(root, violations):
    """Fail when a SKILL.md frontmatter is not valid YAML for a strict parser.

    The hand-rolled parser above is line-based and tolerant; a consumer renders
    these files with a real YAML parser, so an unquoted description containing
    ": " breaks the projection instead of the gate. PyYAML is a dev dependency
    (requirements-dev.txt), so its absence is an error, not a skip.
    """
    try:
        import yaml
    except ImportError:
        violations.append(("requirements-dev.txt",
                           "PyYAML is required for the strict frontmatter check"))
        return
    for path in sorted((root / "skills").rglob("SKILL.md")):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            violations.append((rel, "missing frontmatter (file must start with ---)"))
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            violations.append((rel, "unterminated frontmatter"))
            continue
        try:
            data = yaml.safe_load(parts[1])
        except Exception as exc:  # noqa: BLE001 - the parser's message is the finding
            first = str(exc).splitlines()[0]
            violations.append((rel, "frontmatter is not valid YAML: %s" % first))
            continue
        if not isinstance(data, dict) or not str(data.get("description") or "").strip():
            violations.append((rel, "frontmatter has no description"))


def body_of(text):
    if not text.startswith("---"):
        return text
    lines = text.split("\n")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[index + 1:])
    return text


def find_tag_lines(text):
    """Return [(index, kind, name)] for lines that are exactly one tag."""
    found = []
    for index, line in enumerate(text.split("\n")):
        stripped = line.strip()
        open_match = re.fullmatch(r"<([A-Za-z_][A-Za-z0-9_]*)>", stripped)
        close_match = re.fullmatch(r"</([A-Za-z_][A-Za-z0-9_]*)>", stripped)
        if open_match:
            found.append((index, "open", open_match.group(1)))
        elif close_match:
            found.append((index, "close", close_match.group(1)))
    return found


def extract_block(text, name):
    """Return the block text from the opening to the closing tag inclusive."""
    lines = text.split("\n")
    start = None
    for index, line in enumerate(lines):
        if line.strip() == "<%s>" % name:
            start = index
            break
    if start is None:
        return None
    for index in range(start, len(lines)):
        if lines[index].strip() == "</%s>" % name:
            return "\n".join(lines[start:index + 1])
    return None


def block_line_range(text, name):
    lines = text.split("\n")
    start = None
    for index, line in enumerate(lines):
        if line.strip() == "<%s>" % name:
            start = index
            break
    if start is None:
        return None
    for index in range(start, len(lines)):
        if lines[index].strip() == "</%s>" % name:
            return (start, index)
    return None


def check_frontmatter(data, filename, violations):
    for key in REQUIRED_KEYS:
        if key not in data or data[key] in ("", None):
            violations.append((filename, "missing required frontmatter key: %s" % key))
    if violations:
        return
    domain = data.get("domain")
    if domain not in DOMAINS:
        violations.append((filename, "invalid domain: %r" % (domain,)))
    else:
        prefix = domain + "-"
        if not str(data.get("id", "")).startswith(prefix):
            violations.append((
                filename,
                "id %r does not start with domain prefix %r" % (data.get("id"), prefix),
            ))
    if data.get("status") not in STATUSES:
        violations.append((filename, "invalid status: %r" % (data.get("status"),)))
    if data.get("budget_tier") not in BUDGET_TIERS:
        violations.append((filename, "invalid budget_tier: %r" % (data.get("budget_tier"),)))
    if data.get("tool_profile") not in TOOL_PROFILES:
        violations.append((filename, "invalid tool_profile: %r" % (data.get("tool_profile"),)))
    if data.get("evidence_style") not in EVIDENCE_STYLES:
        violations.append((filename, "invalid evidence_style: %r" % (data.get("evidence_style"),)))
    if data.get("conduct_variant") not in CONDUCT_VARIANTS:
        violations.append((filename, "invalid conduct_variant: %r" % (data.get("conduct_variant"),)))
    if not isinstance(data.get("required_slots"), list):
        violations.append((filename, "required_slots must be an inline list"))
    if "optional_slots" in data and not isinstance(data["optional_slots"], list):
        violations.append((filename, "optional_slots must be an inline list"))
    if not isinstance(data.get("fragment_versions"), dict):
        violations.append((filename, "fragment_versions must be an inline mapping"))
    if not isinstance(data.get("owned_phases"), list) or not set(data["owned_phases"]) <= set(OWNED_PHASES):
        violations.append((filename, "invalid owned_phases: %r" % (data.get("owned_phases"),)))
    if not isinstance(data.get("runtimes"), list) or not set(data["runtimes"]) <= set(RUNTIMES):
        violations.append((filename, "invalid runtimes: %r" % (data.get("runtimes"),)))
    if not VERSION_RE.match(str(data.get("version", ""))):
        violations.append((filename, "invalid version: %r" % (data.get("version"),)))


def check_blocks(text, filename, violations):
    tag_lines = find_tag_lines(text)
    opens = [name for _, kind, name in tag_lines if kind == "open"]
    closes = [name for _, kind, name in tag_lines if kind == "close"]

    unknown = [name for name in opens if name not in KNOWN_BLOCK_TAGS]
    unknown += [name for name in closes if name not in KNOWN_BLOCK_TAGS]
    if unknown:
        violations.append((filename, "unknown top-level tag(s): %s" % ", ".join(sorted(set(unknown)))))
        return None

    if closes != opens:
        violations.append((filename, "unbalanced block tags (opens %s / closes %s)" % (opens, closes)))

    if opens == SCOPE_ORDER:
        variant = SCOPE_ORDER
    elif opens == WORKFLOW_SCOPE_ORDER:
        variant = WORKFLOW_SCOPE_ORDER
    else:
        variant = BLOCK_ORDER
    if opens not in (variant,):
        violations.append((
            filename,
            "block order must be %s, found %s" % (" -> ".join(variant), " -> ".join(opens) or "none"),
        ))
    for name in variant:
        if opens.count(name) != 1:
            violations.append((filename, "expected exactly one <%s> block, found %d" % (name, opens.count(name))))

    output_open = text.rfind("\n<output>") if "\n<output>" in text else text.find("<output>")
    output_close = text.rfind("\n</output>")
    if output_close != -1:
        tail = text[output_close + len("\n</output>"):]
        if tail.strip():
            violations.append((filename, "content found after </output>; output must be the last block"))
    elif output_open != -1:
        violations.append((filename, "missing </output> close tag"))


def normalize(text):
    """Collapse all whitespace runs to single spaces (runtime consumption shape)."""
    return " ".join(text.split())


def check_fragments(text, data, root, filename, violations):
    doctrine_path = root / "fragments" / "agent-doctrine.md"
    doctrine_block = extract_block(text, "doctrine")
    if doctrine_block is None:
        violations.append((filename, "missing <doctrine> block"))
    elif not doctrine_path.is_file():
        violations.append((filename, "fragment file not found: %s" % doctrine_path))
    else:
        fragment_block = extract_block(
            doctrine_path.read_text(encoding="utf-8", errors="replace"), "doctrine")
        if fragment_block is None:
            violations.append((filename, "fragment %s has no <doctrine> block" % doctrine_path.name))
        elif doctrine_block != fragment_block:
            violations.append((filename, "<doctrine> block is not byte-identical to %s" % doctrine_path.name))

    manifest_path = root / "tooling" / "fragments.manifest.json"
    if manifest_path.is_file():
        try:
            import json
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for key, file_stem in (("doctrine", "agent-doctrine.md"),
                                   ("conduct", "agent-conduct.md")):
                declared = (data.get("fragment_versions") or {}).get(key)
                pinned = manifest.get("fragments", {}).get(file_stem, {}).get("version")
                if declared and pinned and declared != pinned:
                    violations.append((
                        filename,
                        "fragment_versions.%s=%s does not match manifest %s"
                        % (key, declared, pinned),
                    ))
        except (OSError, ValueError, KeyError):
            violations.append((filename, "cannot read fragment manifest for version check"))
    variant = data.get("conduct_variant")
    conduct_name = CONDUCT_FRAGMENTS.get(variant, "agent-conduct.md")
    conduct_path = root / "fragments" / conduct_name
    conduct_block = extract_block(text, "conduct")
    if conduct_block is None:
        violations.append((filename, "missing <conduct> block"))
    elif not conduct_path.is_file():
        violations.append((filename, "fragment file not found: %s" % conduct_path))
    else:
        fragment_block = extract_block(
            conduct_path.read_text(encoding="utf-8", errors="replace"), "conduct")
        if fragment_block is None:
            violations.append((filename, "fragment %s has no <conduct> block" % conduct_path.name))
        elif conduct_block != fragment_block:
            violations.append((
                filename,
                "<conduct> block does not match %s (variant %r, byte-exact)"
                % (conduct_path.name, variant),
            ))


def check_budget(text, data, filename, violations):
    lines = text.split("\n")
    excluded = set()
    for name in ("doctrine", "conduct"):
        span = block_line_range(text, name)
        if span:
            excluded.update(range(span[0], span[1] + 1))
    count = 1  # role
    for index, line in enumerate(lines):
        if index in excluded:
            continue
        if LIST_MARKER_RE.match(line):
            count += 1
    count += 4  # doctrine 1 + (workflow or scope) 1 + conduct 1 + output 1
    tier = data.get("budget_tier")
    cap = BUDGET_TIERS.get(tier)
    if cap is not None and count > cap:
        violations.append((filename, "element budget %d exceeds %s cap %d" % (count, tier, cap)))


def check_hygiene(text, filename, violations):
    for index, line in enumerate(text.split("\n"), start=1):
        for ch in line:
            if ord(ch) > 126:
                violations.append((filename, "non-ASCII character at line %d: %r" % (index, ch)))
                break
    patterns = [
        (re.compile(r"\b[FAP]-\d"), "plan-internal id"),
        (re.compile(r"\bplan \d{10,}\b"), "plan-internal id"),
        (re.compile(r"pass \d+ of"), "runtime control-flow counter"),
        (re.compile(r"round \d+"), "runtime control-flow counter"),
        (re.compile(r"\bcycle \d"), "runtime control-flow counter"),
    ]
    for pattern, label in patterns:
        match = pattern.search(text)
        if match:
            violations.append((filename, "%s: %r" % (label, match.group(0))))


def check_read_only_output(text, data, filename, violations):
    if data.get("tool_profile") != "read-only":
        return
    output = extract_block(text, "output")
    if output is None:
        return
    for pattern, label in MUTATING_VERBS:
        if pattern.search(output):
            violations.append((filename, "read-only output names mutating verb %r" % label))


def check_workflow_prose(text, filename, violations):
    for block_name in ("workflow", "scope"):
        block = extract_block(text, block_name)
        if block is None:
            continue
        for line in block.split("\n"):
            if LIST_MARKER_RE.match(line):
                violations.append((filename, block_name + " block must be prose (no list markers)"))
                return


def check_slots(text, data, filename, violations):
    declared = set()
    for key in ("required_slots", "optional_slots"):
        value = data.get(key)
        if isinstance(value, list):
            declared.update(str(item) for item in value)
    for token in sorted(set(SLOT_RE.findall(body_of(text)))):
        if token not in declared:
            violations.append((filename, "undeclared slot {{%s}}" % token))


# Advisory token guardrail (AP-01). The target is calibrated against the shared
# fragments at this baseline size; a deliberate fragment change raises every
# carrier by the same amount, so the guardrail tracks the growth instead of
# flagging all 41 carriers for one fragment decision. Body growth beyond the
# fragment allowance is still a warning.
# Per shared fragment: block tag and the token count the target was calibrated
# against. Both fragments are embedded in every carrier, so both are tracked;
# tracking one would re-WARN all carriers on a change to the other.
FRAGMENT_BASELINES = {"doctrine": 225, "conduct": 190}


def _block_tokens(path, tag):
    if not path.is_file():
        return 0
    match = re.search(r"(?ms)^\s*<%s>.*?</%s>" % (tag, tag),
                      path.read_text(encoding="utf-8", errors="replace"))
    return len(match.group(0).encode("utf-8")) // 4 if match else 0


# Baseline per conduct variant: a carrier embeds exactly one variant, so its
# allowance must be measured against that variant's own shipped size.
CONDUCT_BASELINES = {"kilo": 190, "dsh-ha": 183, "dsh-preset": 194, "omp": 219}


def _fragment_growth(root, conduct_variant="kilo"):
    """Tokens a carrier gained from the fragments it actually embeds."""
    growth = max(0, _block_tokens(root / "fragments" / "agent-doctrine.md",
                                  "doctrine") - FRAGMENT_BASELINES["doctrine"])
    conduct_name = CONDUCT_FRAGMENTS.get(conduct_variant, "agent-conduct.md")
    baseline = CONDUCT_BASELINES.get(conduct_variant, FRAGMENT_BASELINES["conduct"])
    growth += max(0, _block_tokens(root / "fragments" / conduct_name, "conduct")
                  - baseline)
    return growth


def check_token_target(text, data, filename, warnings, growth=0):
    """Advisory token guardrail (AP-01). A WARN, never a violation."""
    targets = {"standard": 1000, "dual-workflow": 950, "primary": 1100}
    tier = data.get("budget_tier")
    target = targets.get(tier)
    if target is None:
        return
    allowance = target + growth
    body = body_of(text)
    tokens = len(body.encode("utf-8")) // 4
    if tokens > allowance:
        message = "body tokens %d exceeds %s target %d" % (tokens, tier, allowance)
        if growth:
            message += " (%d of it fragment growth)" % growth
        warnings.append((filename, message))


def validate_file(path, root, instantiate, warnings=None):
    if warnings is None:
        warnings = []
    try:
        relative = str(path.relative_to(root))
    except ValueError:
        relative = str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [(relative, "not valid UTF-8")]
    violations = []
    data, error = parse_frontmatter(text)
    if error:
        violations.append((relative, error))
        return violations
    # The line-based parser above is deliberately minimal; a plain scalar with a
    # bare ": " parses there and breaks in every real YAML loader (a skill body
    # shipped that way once). Cross-check with YAML when it is available.
    try:
        import yaml as _yaml
        block = text.split("---", 2)[1]
        loaded = _yaml.safe_load(block)
        if not isinstance(loaded, dict):
            violations.append((relative, "frontmatter is not a YAML mapping"))
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001 - any YAML error is a violation
        violations.append((relative, "frontmatter does not YAML-parse: %s"
                           % str(exc).splitlines()[0]))
    check_frontmatter(data, relative, violations)
    if any(msg.startswith("missing required") for _, msg in violations):
        return violations
    check_blocks(text, relative, violations)
    check_fragments(text, data, root, relative, violations)
    check_budget(text, data, relative, violations)
    variant = data.get("conduct_variant")
    variant = variant if isinstance(variant, str) else "kilo"
    check_token_target(text, data, relative, warnings,
                       _fragment_growth(root, variant))
    check_hygiene(text, relative, violations)
    check_read_only_output(text, data, relative, violations)
    check_workflow_prose(text, relative, violations)
    check_slots(text, data, relative, violations)
    if instantiate and SLOT_RE.search(text):
        violations.append((relative, "instantiated file contains slot residue"))
    return violations


def discover(root, instantiate=False):
    files = []
    roles = root / "agents"
    if not roles.is_dir():
        roles = root / "roles"
        if roles.is_dir():
            print("WARN legacy root: agents/ missing; using roles/")
    if roles.is_dir():
        for dirpath, _, filenames in os.walk(roles):
            for name in sorted(filenames):
                files.append(Path(dirpath) / name)
    tasks = root / "prompts" / "tasks"
    if not tasks.is_dir():
        tasks = root / "tasks"
        if tasks.is_dir():
            print("WARN legacy root: prompts/tasks/ missing; using tasks/")
    if tasks.is_dir():
        for name in sorted(os.listdir(tasks)):
            if name.endswith(".md"):
                files.append(tasks / name)
    if instantiate:
        for path in sorted(root.rglob("*.instantiated.md")):
            files.append(path)
    return sorted(set(files))


COMMAND_EXEMPT = {"caveman": "style toggle, not a task command"}


def check_commands(root, violations):
    """Commands are thin dispatchers: require a `Doctrine:` line (AP-14);
    style-only utilities are exempt via COMMAND_EXEMPT."""
    commands = root / "commands"
    if not commands.is_dir():
        return
    for path in sorted(commands.glob("*.md")):
        rel = path.relative_to(root).as_posix()
        if path.stem in COMMAND_EXEMPT:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "Doctrine:" not in text:
            violations.append((rel, "missing 'Doctrine:' line (or add it to COMMAND_EXEMPT)"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(default_root()), help="repo root (default: script parent)")
    parser.add_argument("--instantiate", action="store_true",
                        help="fail on any {{...}} slot residue; also scans **/*.instantiated.md (instantiated output)")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    command_violations = []
    check_commands(root, command_violations)
    files = discover(root, args.instantiate)
    violations = []
    warnings = []
    for path in files:
        violations.extend(validate_file(path, root, args.instantiate, warnings))
    violations.extend(command_violations)
    strict_yaml_errors(root, violations)

    for filename, message in violations:
        print("FAIL %s: %s" % (filename, message))
    for filename, message in warnings:
        print("WARN %s: %s" % (filename, message))
    print("validate_templates: checked %d file(s); %d violation(s); %d warning(s)"
          % (len(files), len(violations), len(warnings)))
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
