#!/usr/bin/env python3
"""Render the OMP vendor projection from the neutral role templates.

The library owns the mapping (omp/catalog.yaml), the neutral bodies (agents/**)
and the conduct variant (fragments/agent-conduct.omp.md). The consumer owns the
project slots, so a render takes a consumer agent pack (--pack) and writes into
that project's OMP discovery directory (<project>/.omp/agents); nothing
rendered here is committed in the library (omp/README.md).

Modes:
  --check                    structure, selection and pin gate: catalog shape,
                             tool posture, read-only coverage (every read-only
                             role projected or deferred with a reason, no
                             no-tools role projected), the description-token
                             budget, role, fragment and foreground module pins,
                             foreground module and set budgets, body block
                             order. No pack needed, nothing written.
  --check --pack P --out D   drift gate: byte-compare D against a fresh render.
  --pack P --out D           write one <name>.md per catalog entry into D.
  --check --foreground       foreground gate: the catalog `foreground:` block
                             against omp/prompts/foreground/manifest.json (set
                             id, compose order, per-module sha256 pins, the slot
                             union) plus per-module and total token budgets. No
                             pack needed.
  --check --foreground --pack P --out F
                             byte-compare the composed foreground set in F
                             against a fresh fill from the pack.
  --foreground --pack P --out F
                             compose the manifest order (one blank line between
                             modules) and write the result to the file F: plain
                             Markdown (no frontmatter), every declared slot
                             filled from the pack.

Exit 0 clean, 1 drift or validation failure, 2 unreadable input or bad usage.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

LIBRARY_ROOT = Path(__file__).resolve().parent.parent

# Pinned fragment per catalog pin key; the conduct pin is the OMP variant.
FRAGMENT_FILES = {
    "doctrine": "agent-doctrine.md",
    "conduct": "agent-conduct.omp.md",
}

TOP_KEYS = [
    "schema",
    "library",
    "library_version",
    "library_commit",
    "fragment_sha256",
    "templates_sha256",
    "foreground",
    "agents",
    "deferred",
]
TOP_REQUIRED = [
    "schema",
    "library_version",
    "library_commit",
    "fragment_sha256",
    "templates_sha256",
    "foreground",
    "agents",
    "deferred",
]
CATALOG_SCHEMA = "omp-catalog/4"

# The foreground policy is the one prompt the main session carries: OMP loads it
# from .omp/APPEND_SYSTEM.md and does not forward it to subagents. It is a module
# set rather than one file: omp/prompts/foreground/ holds self-contained modules,
# and manifest.json in that directory pins each module, carries its budget and
# defines the compose order (joined by exactly one blank line). The catalog block
# names the set id, the compose order and the slot union.
# Both budget levels are ceilings, not targets: per module in the manifest, and
# the composed set in the manifest with FOREGROUND_BUDGET as the renderer
# ceiling. Raising either is a deliberate decision -- the manifest, this ceiling
# and a rationale line in omp/README.md move in the same change; the catalog
# carries no budget, so it is not part of that edit.
FOREGROUND_SET_DIR = "omp/prompts/foreground"
FOREGROUND_MANIFEST = "manifest.json"
FOREGROUND_SET_SCHEMA = "omp-foreground-set/1"
FOREGROUND_KEYS = ["id", "modules", "slots"]
FOREGROUND_REQUIRED = ["id", "modules", "slots"]
FOREGROUND_BUDGET = 726
MANIFEST_KEYS = ["schema", "id", "order", "budget_tokens", "modules"]
MANIFEST_REQUIRED = ["schema", "id", "order", "budget_tokens", "modules"]
MODULE_KEYS = ["sha256", "budget_tokens"]
MODULE_REQUIRED = ["sha256", "budget_tokens"]
SET_ID_RE = re.compile(r"^[a-z][a-z0-9-]*/[0-9]+$")

DEFERRED_KEYS = ["role", "reason"]
DEFERRED_REQUIRED = ["role", "reason"]

# Selection guards. The projection is read-only plus the single orchestrator, so
# the catalog cannot grow into a write-capable runtime role one entry at a time:
# a write-capable `agents:` entry is an error, and every read-only role under
# agents/** must be either projected or deferred with a reason.
READ_ONLY_PROFILE = "read-only"
ORCHESTRATOR_PROFILE = "orchestrator"

# Cap on the summed `purpose` descriptions of the projected entries -- the text
# that becomes each OMP frontmatter description. Estimated as bytes // 4, the
# library convention (standards/agent-prompt-standard.md). --check prints the
# current sum; the cap is a budget, not a measurement.
DESCRIPTION_BUDGET = 700

ENTRY_KEYS = [
    "role",
    "name",
    "model",
    "tools",
    "spawns",
    "thinkingLevel",
    "output",
    "overlay",
]
ENTRY_REQUIRED = ["role", "name", "model", "tools"]

# OMP subagent frontmatter keys, in emission order. Measured against the bundled
# agents of @oh-my-pi/pi-coding-agent 18.12.6 (scout, reviewer,
# security-reviewer, task, sonic) and the oh-my-pi task-agent contract; nothing
# outside this list is emitted.
FRONTMATTER_KEYS = [
    "name",
    "description",
    "tools",
    "spawns",
    "model",
    "thinkingLevel",
    "output",
]

# Read-only tool vocabulary. write, edit and bash are never granted: these are
# prompts, not executors.
READ_ONLY_TOOLS = ["read", "grep", "glob", "web_search"]
DISPATCH_TOOL = "task"
# A canon that forbids tools cannot be projected: OMP applies a broad default
# when the tool list is absent, and a non-empty list grants tools the canon
# denies. Neither branch honours "no tools", so the role belongs in `deferred:`.
# The declaration counts only in the {{MUTATION_POLICY}} label line, and only in
# the three postures below: a role that says "no tools are required for step X"
# in its workflow is describing a step, not declaring a tool-free role.
MUTATION_POLICY_LABEL_RE = re.compile(
    r"^\s*(?:[-*+]\s+)?[`*_]*\{\{MUTATION_POLICY\}\}[`*_]*\s*:")
NO_TOOLS_RE = re.compile(
    r"\bno[\s-]+tools?\b|\btool-free\b|\bwithout\s+(?:any\s+)?tools?\b",
    re.IGNORECASE)
# OMP rejects these agent names (parseAgentFields reserves them).
RESERVED_NAMES = ["main", "sub"]

# Accepted neutral body block sequences (agents/**, see tooling/validate_templates.py).
BLOCK_ORDERS = [
    ["role", "hard_rules", "doctrine", "workflow", "conduct", "output"],
    ["role", "hard_rules", "doctrine", "scope", "conduct", "output"],
    ["role", "hard_rules", "doctrine", "workflow", "scope", "conduct", "output"],
]
OVERLAY_TAG = "runtime"

SLOT_RE = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")
SLOT_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
OPEN_TAG_RE = re.compile(r"^<([a-z_]+)>$")
CLOSE_TAG_RE = re.compile(r"^</([a-z_]+)>$")
NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
MODEL_RE = re.compile(r"^@[a-z][a-z0-9_]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_SUBSTITUTIONS = 8


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_frontmatter(text):
    """Return (frontmatter mapping, body text) for a markdown file."""
    if not text.startswith("---"):
        return {}, text
    lines = text.split("\n")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            data = yaml.safe_load("\n".join(lines[1:index]))
            if data is None:
                data = {}
            if not isinstance(data, dict):
                raise ValueError("frontmatter is not a mapping")
            return data, "\n".join(lines[index + 1:])
    raise ValueError("unterminated frontmatter")


def parse_blocks(body):
    """Return the (tag, block text) pairs of a body; text outside blocks is dropped."""
    blocks = []
    tag = None
    buf = []
    for line in body.split("\n"):
        opening = OPEN_TAG_RE.match(line.strip())
        closing = CLOSE_TAG_RE.match(line.strip())
        if tag is None:
            if opening:
                tag = opening.group(1)
                buf = [line]
            continue
        if closing:
            buf.append(line)
            blocks.append((tag, "\n".join(buf)))
            tag = None
            buf = []
            continue
        buf.append(line)
    if tag is not None:
        raise ValueError("unterminated <%s> block" % tag)
    return blocks


def substitute(text, slots):
    """Fill the {{SLOT}} tokens; repeats so a slot value may name another slot."""
    for _ in range(MAX_SUBSTITUTIONS):
        updated = SLOT_RE.sub(
            lambda match: str(slots.get(match.group(1), match.group(0))), text)
        if updated == text:
            return updated
        text = updated
    return text


def load_conduct_block(root):
    path = root / "fragments" / FRAGMENT_FILES["conduct"]
    blocks = parse_blocks(path.read_text(encoding="utf-8"))
    conduct = [text for tag, text in blocks if tag == "conduct"]
    if len(conduct) != 1:
        raise ValueError("fragments/%s carries no single <conduct> block"
                         % FRAGMENT_FILES["conduct"])
    return conduct[0]


def load_overlay(root, relative):
    path = root / relative
    blocks = parse_blocks(path.read_text(encoding="utf-8"))
    if len(blocks) != 1 or blocks[0][0] != OVERLAY_TAG:
        raise ValueError("%s must carry exactly one <%s> block"
                         % (relative, OVERLAY_TAG))
    return blocks[0][1]


def render_body(role_blocks, conduct_block, overlay_block):
    tags = [tag for tag, _ in role_blocks]
    if tags not in BLOCK_ORDERS:
        raise ValueError("body block order is not a registered order: %s"
                         % ", ".join(tags))
    parts = []
    for tag, text in role_blocks:
        if tag == "conduct":
            if overlay_block is not None:
                parts.append(overlay_block)
            parts.append(conduct_block)
        else:
            parts.append(text)
    return "\n\n".join(parts)


def build_frontmatter(entry, description):
    data = {"name": entry["name"], "description": description}
    data["tools"] = list(entry["tools"])
    if entry.get("spawns"):
        data["spawns"] = list(entry["spawns"])
    data["model"] = list(entry["model"])
    if entry.get("thinkingLevel"):
        data["thinkingLevel"] = entry["thinkingLevel"]
    if entry.get("output"):
        data["output"] = entry["output"]
    return data


def render_file(frontmatter, body):
    head = yaml.safe_dump(frontmatter, sort_keys=False, default_flow_style=False,
                          width=4096, allow_unicode=False)
    return "---\n" + head + "---\n\n" + body + "\n"


def load_pack(path):
    """Return {agent name: {slot: value}} from a consumer agent pack."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("pack is not a mapping")
    entries = data.get("agents")
    if not isinstance(entries, list):
        raise ValueError("pack has no agents list")
    slot_map = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            continue
        slots = entry.get("slots") or {}
        if not isinstance(slots, dict):
            raise ValueError("pack entry %s: slots is not a mapping" % entry["name"])
        slot_map[entry["name"]] = {
            str(key): ("" if value is None else str(value)) for key, value in slots.items()
        }
    return slot_map


def check_entry(index, entry, names, errors):
    label = "entry %d" % (index + 1)
    if not isinstance(entry, dict):
        errors.append("%s is not a mapping" % label)
        return
    for key in entry:
        if key not in ENTRY_KEYS:
            errors.append("%s: unknown catalog key %r" % (label, key))
    for key in ENTRY_REQUIRED:
        if key not in entry:
            errors.append("%s: missing required key %r" % (label, key))
    if any(key not in entry for key in ENTRY_REQUIRED):
        return
    name = entry.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        errors.append("%s: name %r is not a lowercase slug" % (label, name))
    elif name in RESERVED_NAMES:
        errors.append("%s: name %r is reserved by OMP" % (label, name))
    elif names.count(name) > 1:
        errors.append("%s: duplicate name %r" % (label, name))
    role = entry.get("role")
    if not isinstance(role, str) or not role.startswith("agents/") or not role.endswith(".md"):
        errors.append("%s: role must be a path under roles/** ending in .md" % label)
    elif ".." in role.split("/"):
        errors.append("%s: role may not escape the library" % label)
    model = entry.get("model")
    if not isinstance(model, list) or not model:
        errors.append("%s: model must be a non-empty list of role selectors" % label)
    else:
        for selector in model:
            if not isinstance(selector, str) or not MODEL_RE.match(selector):
                errors.append("%s: model selector %r is not an @role alias"
                              % (label, selector))
    tools = entry.get("tools")
    if not isinstance(tools, list) or not tools:
        errors.append("%s: tools must be a non-empty list" % label)
        return
    seen = []
    for tool in tools:
        if tool not in READ_ONLY_TOOLS and tool != DISPATCH_TOOL:
            errors.append("%s: tool %r is outside the read-only vocabulary" % (label, tool))
        if tool in seen:
            errors.append("%s: duplicate tool %r" % (label, tool))
        seen.append(tool)
    spawns = entry.get("spawns")
    if spawns is not None:
        if not isinstance(spawns, list) or not spawns:
            errors.append("%s: spawns must be a non-empty list when present" % label)
        else:
            for target in spawns:
                if not isinstance(target, str) or target not in names:
                    errors.append("%s: spawns target %r is not a catalog entry"
                                  % (label, target))
                elif target == name:
                    errors.append("%s: spawns must not name itself" % label)
    dispatches = bool(spawns)
    if dispatches and DISPATCH_TOOL not in tools:
        errors.append("%s: entry with spawns must grant %r" % (label, DISPATCH_TOOL))
    if not dispatches and DISPATCH_TOOL in tools:
        errors.append("%s: %r is only allowed where the entry dispatches children"
                      % (label, DISPATCH_TOOL))
    level = entry.get("thinkingLevel")
    if level is not None and (not isinstance(level, str) or not level):
        errors.append("%s: thinkingLevel must be a non-empty string" % label)
    output = entry.get("output")
    if output is not None:
        if not isinstance(output, dict) or list(output) != ["properties"]:
            errors.append("%s: output must carry only a properties mapping" % label)
        else:
            properties = output["properties"]
            if not isinstance(properties, dict) or not properties:
                errors.append("%s: output.properties must be a non-empty mapping" % label)
            else:
                for field, spec in properties.items():
                    if not isinstance(spec, dict) or sorted(spec) != ["enum", "metadata"]:
                        errors.append("%s: output.%s must carry metadata and enum only"
                                      % (label, field))
                        continue
                    metadata = spec["metadata"]
                    description = metadata.get("description") if isinstance(metadata, dict) else None
                    if not isinstance(description, str) or not description.strip():
                        errors.append("%s: output.%s needs metadata.description" % (label, field))
                    enum = spec["enum"]
                    if not isinstance(enum, list) or not enum or not all(
                            isinstance(value, str) and value for value in enum):
                        errors.append("%s: output.%s needs a non-empty enum of strings"
                                      % (label, field))
    overlay = entry.get("overlay")
    if overlay is not None and (not isinstance(overlay, str) or not overlay):
        errors.append("%s: overlay must be a non-empty path" % label)


def check_deferred(deferred, roles, errors):
    """Validate the deferred block: shape, uniqueness, and no overlap."""
    if not isinstance(deferred, list):
        errors.append("deferred must be a list of {role, reason} mappings")
        return []
    seen = []
    selected = set(roles)
    for index, entry in enumerate(deferred):
        label = "deferred %d" % (index + 1)
        if not isinstance(entry, dict):
            errors.append("%s is not a mapping" % label)
            continue
        for key in entry:
            if key not in DEFERRED_KEYS:
                errors.append("%s: unknown deferred key %r" % (label, key))
        for key in DEFERRED_REQUIRED:
            if key not in entry:
                errors.append("%s: missing required key %r" % (label, key))
        role = entry.get("role")
        if not isinstance(role, str) or not role.startswith("agents/") or not role.endswith(".md"):
            errors.append("%s: role must be a path under agents/** ending in .md" % label)
            continue
        if ".." in role.split("/"):
            errors.append("%s: role may not escape the library" % label)
            continue
        if role in seen:
            errors.append("%s: duplicate deferred role %s" % (label, role))
        seen.append(role)
        if role in selected:
            errors.append("%s: %s is both projected in agents: and deferred" % (label, role))
        reason = entry.get("reason")
        if reason is None:
            pass  # the missing key is reported above
        elif not isinstance(reason, str) or not reason.strip():
            errors.append("%s: %s needs a one-line reason" % (label, role))
        elif "\n" in reason.strip():
            errors.append("%s: %s reason must be one line" % (label, role))
    return seen


def check_foreground(root, block, errors):
    """Validate the foreground module set: block, manifest, pins and budgets.

    Returns usage info (module tokens, total, budget, slots, composed text) when
    the set is readable, else None. The pins are checked here rather than only
    under --foreground so a plain `--check` catches a stale module too.
    """
    if block is None:
        errors.append("catalog has no foreground block; omp-catalog/4 requires "
                      "one so the main-session module set is pinned like every role")
        return None
    if not isinstance(block, dict):
        errors.append("foreground must be a mapping")
        return None
    for key in block:
        if key not in FOREGROUND_KEYS:
            errors.append("foreground: unknown key %r" % key)
    for key in FOREGROUND_REQUIRED:
        if key not in block:
            errors.append("foreground: missing required key %r" % key)

    set_id = block.get("id")
    if not isinstance(set_id, str) or not SET_ID_RE.match(set_id):
        errors.append("foreground.id must be a set id like 'omp-foreground/1'")
        set_id = None

    modules = block.get("modules")
    catalog_order = []
    if not isinstance(modules, list) or not modules:
        errors.append("foreground.modules must be a non-empty list of module names")
        modules = None
    else:
        for name in modules:
            if (not isinstance(name, str) or not name.endswith(".md")
                    or "/" in name or ".." in name):
                errors.append("foreground.modules entry %r is not a module "
                              "filename" % (name,))
                continue
            if name in catalog_order:
                errors.append("foreground.modules lists %s twice" % name)
                continue
            catalog_order.append(name)

    slots = block.get("slots")
    declared = []
    if not isinstance(slots, list) or not slots:
        errors.append("foreground.slots must be a non-empty list of slot names")
        slots = None
    else:
        for slot in slots:
            if not isinstance(slot, str) or not SLOT_NAME_RE.match(slot):
                errors.append("foreground.slots entry %r is not an uppercase slot "
                              "name" % (slot,))
                continue
            if slot in declared:
                errors.append("foreground.slots lists %s twice" % slot)
                continue
            declared.append(slot)

    directory = root / FOREGROUND_SET_DIR
    manifest_path = directory / FOREGROUND_MANIFEST
    manifest_label = "%s/%s" % (FOREGROUND_SET_DIR, FOREGROUND_MANIFEST)
    if not manifest_path.is_file():
        errors.append("missing foreground set manifest %s; the module set is "
                      "declared by that manifest, not by the catalog"
                      % manifest_label)
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        errors.append("cannot read %s: %s" % (manifest_label, exc))
        return None
    if not isinstance(manifest, dict):
        errors.append("%s is not a JSON object" % manifest_label)
        return None
    for key in manifest:
        if key not in MANIFEST_KEYS:
            errors.append("%s: unknown key %r" % (manifest_label, key))
    for key in MANIFEST_REQUIRED:
        if key not in manifest:
            errors.append("%s: missing required key %r" % (manifest_label, key))
    if manifest.get("schema") != FOREGROUND_SET_SCHEMA:
        errors.append("%s schema is not %s" % (manifest_label,
                                                FOREGROUND_SET_SCHEMA))
    manifest_id = manifest.get("id")
    if not isinstance(manifest_id, str) or not manifest_id.strip():
        errors.append("%s id must be a non-empty string" % manifest_label)
    elif set_id is not None and manifest_id != set_id:
        errors.append("foreground set id mismatch: catalog has %r, %s has %r; "
                      "a module set carries one id"
                      % (set_id, manifest_label, manifest_id))

    order = manifest.get("order")
    manifest_order = []
    if not isinstance(order, list) or not order:
        errors.append("%s order must be a non-empty list of module names"
                      % manifest_label)
        order = None
    else:
        for name in order:
            if (not isinstance(name, str) or not name.endswith(".md")
                    or "/" in name or ".." in name):
                errors.append("%s order entry %r is not a module filename"
                              % (manifest_label, name))
                continue
            if name in manifest_order:
                errors.append("%s order lists %s twice" % (manifest_label, name))
                continue
            manifest_order.append(name)

    budget = manifest.get("budget_tokens")
    if not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0:
        errors.append("%s budget_tokens must be a positive integer"
                      % manifest_label)
        budget = None

    entries = manifest.get("modules")
    if not isinstance(entries, dict):
        errors.append("%s modules must be a mapping from module name to "
                      "{sha256, budget_tokens}" % manifest_label)
        entries = None
    else:
        for name in entries:
            if name not in manifest_order:
                errors.append("%s modules pins %s, which the order does not list"
                              % (manifest_label, name))
        for name in manifest_order:
            if name not in entries:
                errors.append("%s modules has no entry for %s"
                              % (manifest_label, name))
    if modules is None or order is None or entries is None:
        return None

    # Existence, catalog/manifest agreement, then order. Each failure gets its
    # own message so a missing, extra or reordered module is not one blur.
    on_disk = sorted(path.name for path in directory.glob("*.md")) \
        if directory.is_dir() else []
    for name in manifest_order:
        if name not in on_disk:
            errors.append("foreground set is missing module %s/%s on disk, which "
                          "%s order lists" % (FOREGROUND_SET_DIR, name,
                                              manifest_label))
    for name in on_disk:
        if name not in manifest_order:
            errors.append("foreground set carries module %s/%s on disk, which %s "
                          "order does not list; add it to the manifest or remove "
                          "the file" % (FOREGROUND_SET_DIR, name, manifest_label))
    for name in catalog_order:
        if name not in manifest_order:
            errors.append("foreground.modules lists %s, which %s order does not"
                          % (name, manifest_label))
    for name in manifest_order:
        if name not in catalog_order:
            errors.append("%s order lists %s, which foreground.modules does not "
                          "declare" % (manifest_label, name))
    if (set(catalog_order) == set(manifest_order)
            and catalog_order != manifest_order):
        first = next(index for index, pair in enumerate(zip(catalog_order,
                                                            manifest_order))
                     if pair[0] != pair[1])
        errors.append("foreground set order is reordered: foreground.modules has "
                      "%s, %s order has %s; the first divergence is position %d "
                      "(%s vs %s). The manifest order is the compose order"
                      % (catalog_order, manifest_label, manifest_order, first + 1,
                         catalog_order[first], manifest_order[first]))
    if any(name not in on_disk for name in manifest_order):
        return None

    usage = []
    parts = []
    for name in manifest_order:
        path = directory / name
        text = path.read_text(encoding="utf-8")
        if text.lstrip().startswith("---"):
            errors.append("foreground module %s carries YAML frontmatter; the "
                          "append prompt is plain Markdown" % name)
        entry = entries.get(name)
        pinned = None
        module_budget = None
        if not isinstance(entry, dict):
            errors.append("%s modules.%s must be a mapping"
                          % (manifest_label, name))
        else:
            for key in entry:
                if key not in MODULE_KEYS:
                    errors.append("%s modules.%s: unknown key %r"
                                  % (manifest_label, name, key))
            for key in MODULE_REQUIRED:
                if key not in entry:
                    errors.append("%s modules.%s: missing required key %r"
                                  % (manifest_label, name, key))
            pinned = entry.get("sha256")
            if "sha256" in entry and (not isinstance(pinned, str)
                                      or not SHA256_RE.match(pinned)):
                errors.append("%s modules.%s.sha256 is not a sha256 hex digest"
                              % (manifest_label, name))
                pinned = None
            module_budget = entry.get("budget_tokens")
            if "budget_tokens" in entry and (
                    not isinstance(module_budget, int)
                    or isinstance(module_budget, bool) or module_budget <= 0):
                errors.append("%s modules.%s.budget_tokens must be a positive "
                              "integer" % (manifest_label, name))
                module_budget = None
        actual = sha256_file(path)
        if pinned is not None and actual != pinned:
            errors.append("foreground module drift: %s/%s: computed %s, pinned "
                          "%s; refresh the pin in %s with \"%s\": \"%s\" and "
                          "re-render the consumer copy"
                          % (FOREGROUND_SET_DIR, name, actual, pinned,
                             manifest_label, name, actual))
        tokens = foreground_tokens(text)
        usage.append((name, tokens, module_budget))
        if module_budget is not None and tokens > module_budget:
            errors.append("foreground module budget exceeded: %s estimates %d "
                          "tokens, cap is %d (modules.%s.budget_tokens in %s); "
                          "trim the module or raise the cap with a rationale "
                          "line in omp/README.md"
                          % (name, tokens, module_budget, name, manifest_label))
        parts.append(text.strip("\n"))
    composed = "\n\n".join(parts) + "\n"

    found = sorted(set(SLOT_RE.findall(composed)))
    if slots is not None:
        for slot in found:
            if slot not in declared:
                errors.append("foreground set uses {{%s}}, which foreground.slots "
                              "does not declare" % slot)
        for slot in declared:
            if slot not in found:
                errors.append("foreground.slots declares %s, which the module set "
                              "does not use" % slot)
    total = foreground_tokens(composed)
    if budget is not None:
        if budget > FOREGROUND_BUDGET:
            errors.append("foreground budget raised past the renderer ceiling: %s "
                          "budget_tokens is %d, FOREGROUND_BUDGET is %d; raising "
                          "it is a deliberate decision -- update the manifest, "
                          "`FOREGROUND_BUDGET` in `tooling/render_omp.py`, and "
                          "record the reason in `omp/README.md`"
                          % (manifest_label, budget, FOREGROUND_BUDGET))
        elif total > budget:
            errors.append("foreground budget exceeded: the composed set estimates "
                          "%d tokens, cap is %d (%s budget_tokens); trim a module "
                          "or raise the cap with a rationale line in omp/README.md"
                          % (total, budget, manifest_label))
    return {"id": set_id or manifest_id, "modules": usage, "total": total,
            "budget": budget, "slots": declared, "text": composed}


def read_foreground(root, catalog_path):
    """Return (set label, declared slots, composed module text)."""
    data = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    block = data.get("foreground") if isinstance(data, dict) else None
    if not isinstance(block, dict):
        raise ValueError("catalog carries no foreground block")
    slots = block.get("slots")
    if not isinstance(slots, list):
        raise ValueError("catalog foreground block carries no slots list")
    manifest = read_foreground_manifest(root)
    order = manifest.get("order") if isinstance(manifest, dict) else None
    if not isinstance(order, list) or not order:
        raise ValueError("foreground set manifest carries no order list")
    parts = []
    for name in order:
        path = root / FOREGROUND_SET_DIR / name
        if not path.is_file():
            raise ValueError("missing foreground module %s/%s"
                             % (FOREGROUND_SET_DIR, name))
        parts.append(path.read_text(encoding="utf-8").strip("\n"))
    return FOREGROUND_SET_DIR, [slot for slot in slots if isinstance(slot, str)], \
        "\n\n".join(parts) + "\n"


def read_foreground_manifest(root):
    """Return the foreground set manifest mapping; raise ValueError if unreadable."""
    path = root / FOREGROUND_SET_DIR / FOREGROUND_MANIFEST
    if not path.is_file():
        raise ValueError("missing foreground set manifest %s/%s"
                         % (FOREGROUND_SET_DIR, FOREGROUND_MANIFEST))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("cannot read %s/%s: %s"
                         % (FOREGROUND_SET_DIR, FOREGROUND_MANIFEST, exc))
    if not isinstance(data, dict):
        raise ValueError("%s/%s is not a JSON object"
                         % (FOREGROUND_SET_DIR, FOREGROUND_MANIFEST))
    return data


def foreground_tokens(text):
    """Estimate the foreground policy as bytes // 4 tokens, the library rule."""
    return len(text.encode("utf-8")) // 4


def load_foreground_slots(pack_path, required):
    """Return the project slot values the foreground policy needs.

    The foreground policy is project-level, but the pack that fills it is the
    same per-agent pack the projection uses. A dedicated pack entry named
    `foreground` is authoritative when present; otherwise the value is the union
    of the per-agent slots, and a slot the entries disagree about is an error
    rather than a silent first-wins.
    """
    data = yaml.safe_load(pack_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("pack is not a mapping")
    entries = data.get("agents")
    if not isinstance(entries, list):
        raise ValueError("pack has no agents list")
    values = {}
    conflicts = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            continue
        slots = entry.get("slots") or {}
        if not isinstance(slots, dict):
            raise ValueError("pack entry %s: slots is not a mapping" % entry["name"])
        for key, value in slots.items():
            text = "" if value is None else str(value)
            key = str(key)
            if key in values and values[key] != text:
                conflicts.setdefault(key, {values[key]}).add(text)
            values[key] = text
        if entry["name"] == "foreground":
            values = {str(key): ("" if value is None else str(value))
                      for key, value in slots.items()}
            conflicts = {}
            break
    missing = [slot for slot in required if not values.get(slot, "").strip()]
    if missing:
        raise ValueError("pack has no value for foreground slot(s): %s"
                         % ", ".join(missing))
    disagrees = sorted(key for key in required if key in conflicts)
    if disagrees:
        raise ValueError("pack entries disagree about foreground slot(s): %s"
                         % ", ".join(disagrees))
    return {slot: values[slot] for slot in required}


def render_foreground(foreground, pack_path):
    """Return the foreground policy with every declared slot filled from the pack."""
    _, slots, text = foreground
    values = load_foreground_slots(pack_path, slots)
    rendered = substitute(text, values)
    residue = sorted(set(SLOT_RE.findall(rendered)))
    if residue:
        raise ValueError("foreground: unresolved slot(s): %s" % ", ".join(residue))
    if "{{" in rendered:
        raise ValueError("foreground: rendered policy still carries a slot token")
    if rendered.lstrip().startswith("---"):
        raise ValueError("foreground: rendered policy carries YAML frontmatter")
    return rendered


def check_catalog(root, catalog_path):
    """Return (errors, entries, deferred_roles) after validating shape and pins."""
    errors = []
    try:
        data = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return ["cannot read catalog %s: %s" % (catalog_path, exc)], [], []
    if not isinstance(data, dict):
        return ["catalog %s is not a mapping" % catalog_path], [], []
    for key in data:
        if key not in TOP_KEYS:
            errors.append("unknown top-level catalog key %r" % key)
    for key in TOP_REQUIRED:
        if key not in data:
            errors.append("catalog is missing required key %r" % key)
    if data.get("schema") != CATALOG_SCHEMA:
        errors.append("catalog schema is not %s" % CATALOG_SCHEMA)
    for key in ("library_version", "library_commit"):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append("catalog %s must be a non-empty string" % key)
    entries = data.get("agents")
    if not isinstance(entries, list) or not entries:
        errors.append("catalog has no agents")
        return errors, [], []
    names = []
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            names.append(entry["name"])
    for index, entry in enumerate(entries):
        check_entry(index, entry, names, errors)
    roles = [entry.get("role") for entry in entries
             if isinstance(entry, dict) and isinstance(entry.get("role"), str)]
    if len(set(roles)) != len(roles):
        errors.append("catalog selects the same role twice")
    deferred = check_deferred(data.get("deferred", []), roles, errors)
    fragments = data.get("fragment_sha256")
    if not isinstance(fragments, dict):
        errors.append("fragment_sha256 must be a mapping")
    else:
        for key in sorted(fragments):
            if key not in FRAGMENT_FILES:
                errors.append("fragment_sha256 carries unknown fragment %r" % key)
        for key, filename in sorted(FRAGMENT_FILES.items()):
            expected = fragments.get(key)
            if not isinstance(expected, str) or not SHA256_RE.match(expected):
                errors.append("fragment_sha256.%s is not a sha256 hex digest" % key)
                continue
            path = root / "fragments" / filename
            if not path.is_file():
                errors.append("missing fragment fragments/%s" % filename)
                continue
            actual = sha256_file(path)
            if actual != expected:
                errors.append("fragment drift: fragments/%s: computed %s, pinned %s; "
                              "re-vendor the fragment or set fragment_sha256.%s to %s"
                              % (filename, actual, expected, key, actual))
    pins = data.get("templates_sha256")
    if not isinstance(pins, dict):
        errors.append("templates_sha256 must be a mapping")
    else:
        for role in roles:
            if not isinstance(role, str):
                continue
            if role not in pins:
                errors.append("templates_sha256 has no pin for %s" % role)
        for role in sorted(pins):
            if role not in roles:
                errors.append("templates_sha256 pins %s, which the catalog does not select"
                              % role)
            expected = pins[role]
            path = root / role
            if not isinstance(expected, str) or not SHA256_RE.match(expected):
                errors.append("templates_sha256.%s is not a sha256 hex digest" % role)
                continue
            if not path.is_file():
                errors.append("missing role %s" % role)
                continue
            actual = sha256_file(path)
            if actual != expected:
                errors.append("role drift: %s: computed %s, pinned %s; refresh "
                              "templates_sha256 with `%s: %s` and regenerate the "
                              "consumer projection" % (role, actual, expected, role, actual))
    check_foreground(root, data.get("foreground"), errors)
    return errors, entries, deferred


def role_profiles(root):
    """Return {role path: tool_profile} for every role template under agents/**."""
    profiles = {}
    for path in sorted((root / "agents").glob("**/*.md")):
        try:
            front, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        profile = front.get("tool_profile")
        if isinstance(profile, str) and profile:
            profiles[path.relative_to(root).as_posix()] = profile
    return profiles


def declares_no_tools(root, role):
    """Return True when the {{MUTATION_POLICY}} line declares a tool-free posture.

    Only that line is read, and only in label position ("- {{MUTATION_POLICY}}:
    <rule>"), because the posture is the role's mutation policy rather than a
    remark about one step. The rule text after the label must match one of
    "no tools", "tool-free" or "without tools" (optionally "without any tools"),
    case-insensitive; a phrase anywhere else in the body does not count.
    """
    try:
        text = (root / role).read_text(encoding="utf-8")
    except OSError:
        return False
    for line in text.splitlines():
        label = MUTATION_POLICY_LABEL_RE.match(line)
        if label is not None and NO_TOOLS_RE.search(line[label.end():]):
            return True
    return False


def check_coverage(root, entries, deferred, errors):
    """Fail on an unaccounted read-only role or a write-capable entry."""
    profiles = role_profiles(root)
    projected = {}
    for entry in entries:
        role = entry.get("role") if isinstance(entry, dict) else None
        if isinstance(role, str):
            projected[role] = entry
    deferred_set = set(deferred)
    orchestrators = 0
    for role, entry in sorted(projected.items()):
        profile = profiles.get(role)
        if profile is None:
            continue  # a missing role already fails the pin check
        if declares_no_tools(root, role):
            errors.append("entry %r projects %s, whose canon declares no tools; "
                          "OMP applies a broad default when the tool list is "
                          "absent and a non-empty list would grant tools the "
                          "canon forbids, so list it under deferred: instead"
                          % (entry.get("name"), role))
            continue
        if profile == READ_ONLY_PROFILE:
            continue
        if profile == ORCHESTRATOR_PROFILE:
            orchestrators += 1
            continue
        errors.append("entry %r projects write-capable role %s (tool_profile %s); "
                      "the projection admits read-only roles and the single "
                      "orchestrator only, so a write posture is never granted by "
                      "widening this catalog" % (entry.get("name"), role, profile))
    if orchestrators > 1:
        errors.append("%d orchestrator roles are projected; at most one is allowed"
                      % orchestrators)
    for role, profile in sorted(profiles.items()):
        if profile != READ_ONLY_PROFILE:
            continue
        if role in projected or role in deferred_set:
            continue
        errors.append("read-only role %s is neither projected under agents: nor "
                      "listed under deferred: with a reason" % role)


def description_tokens(root, entries):
    """Sum the projected `purpose` descriptions as bytes // 4 tokens."""
    total = 0
    for entry in entries:
        front, _ = split_frontmatter((root / entry["role"]).read_text(encoding="utf-8"))
        purpose = front.get("purpose")
        text = purpose.strip() if isinstance(purpose, str) else ""
        total += max(1, len(text.encode("utf-8")) // 4)
    return total


def check_description_budget(root, entries, errors):
    """Return the projected description-token estimate; record an error above cap."""
    total = description_tokens(root, entries)
    if total > DESCRIPTION_BUDGET:
        errors.append("description budget exceeded: projected purposes estimate %d "
                      "tokens, cap is %d; drop or defer an entry, or justify a higher "
                      "cap in omp/README.md" % (total, DESCRIPTION_BUDGET))
    return total


def check_shape(root, entries, errors):
    """Validate body shape of every entry without touching the slots."""
    try:
        load_conduct_block(root)
    except (OSError, ValueError) as exc:
        errors.append("fragments/%s: %s" % (FRAGMENT_FILES["conduct"], exc))
    for entry in entries:
        role = entry["role"]
        try:
            _, body = split_frontmatter((root / role).read_text(encoding="utf-8"))
            tags = [tag for tag, _ in parse_blocks(body)]
        except (OSError, ValueError) as exc:
            errors.append("%s: %s" % (role, exc))
            continue
        if tags not in BLOCK_ORDERS:
            errors.append("%s: body block order is not registered: %s"
                          % (role, ", ".join(tags)))
    for entry in entries:
        if not entry.get("overlay"):
            continue
        try:
            load_overlay(root, entry["overlay"])
        except (OSError, ValueError) as exc:
            errors.append("%s" % exc)


def render_all(root, entries, pack_path):
    """Return [(name, text)] for every catalog entry."""
    conduct_block = load_conduct_block(root)
    slot_map = load_pack(pack_path)
    rendered = []
    for entry in entries:
        name = entry["name"]
        role_path = root / entry["role"]
        front, body = split_frontmatter(role_path.read_text(encoding="utf-8"))
        purpose = front.get("purpose")
        if not isinstance(purpose, str) or not purpose.strip() or "\n" in purpose:
            raise ValueError("%s: frontmatter purpose is missing or not one line"
                             % entry["role"])
        if name not in slot_map:
            raise ValueError("pack has no entry for agent %r" % name)
        overlay_block = None
        if entry.get("overlay"):
            overlay_block = load_overlay(root, entry["overlay"])
        assembled = render_body(parse_blocks(body), conduct_block, overlay_block)
        assembled = substitute(assembled, slot_map[name])
        residue = sorted(set(SLOT_RE.findall(assembled)))
        if residue:
            raise ValueError("%s: unresolved slot(s): %s" % (name, ", ".join(residue)))
        frontmatter = build_frontmatter(entry, purpose.strip())
        unknown = [key for key in frontmatter if key not in FRONTMATTER_KEYS]
        if unknown:
            raise ValueError("%s: frontmatter key(s) outside the OMP set: %s"
                             % (name, ", ".join(unknown)))
        text = render_file(frontmatter, assembled)
        if "{{" in text:
            raise ValueError("%s: rendered file still carries a slot token" % name)
        rendered.append((name, text))
    return rendered


def compare(out_dir, rendered):
    problems = []
    for name, text in rendered:
        path = out_dir / (name + ".md")
        if not path.is_file():
            problems.append("missing %s" % path)
            continue
        if path.read_text(encoding="utf-8") != text:
            problems.append("differs from a fresh render: %s" % path)
    if out_dir.is_dir():
        expected = {name for name, _ in rendered}
        for path in sorted(out_dir.glob("*.md")):
            if path.stem not in expected:
                problems.append("unexpected projection file: %s" % path)
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalog", default=None,
                        help="catalog path (default: <library>/omp/catalog.yaml)")
    parser.add_argument("--pack", default=None,
                        help="consumer agent pack that carries the project slot fills")
    parser.add_argument("--out", default=None,
                        help="directory to write or compare the agent projection in, "
                             "or the file to write or compare under --foreground")
    parser.add_argument("--check", action="store_true",
                        help="report drift and write nothing")
    parser.add_argument("--foreground", action="store_true",
                        help="render or check the main-session foreground policy "
                             "(needs --pack and --out to write or compare)")
    args = parser.parse_args(argv)

    root = LIBRARY_ROOT
    if not root.is_dir():
        print("FAIL library root not found: %s" % root)
        return 2
    catalog_path = Path(args.catalog).resolve() if args.catalog else root / "omp" / "catalog.yaml"
    try:
        catalog_label = str(catalog_path.relative_to(root))
    except ValueError:
        catalog_label = str(catalog_path)

    errors, entries, deferred = check_catalog(root, catalog_path)
    budget = None
    if not errors:
        check_shape(root, entries, errors)
    if entries:
        try:
            budget = check_description_budget(root, entries, errors)
        except (OSError, ValueError) as exc:
            errors.append("cannot measure the description budget: %s" % exc)
        check_coverage(root, entries, deferred, errors)
    if budget is not None:
        print("BUDGET %d/%d description tokens (%d projected entries)"
              % (budget, DESCRIPTION_BUDGET, len(entries)))
    foreground = None
    if not errors:
        try:
            foreground = read_foreground(root, catalog_path)
        except (OSError, yaml.YAMLError, ValueError) as exc:
            errors.append("cannot read the foreground policy: %s" % exc)
    if foreground is not None:
        fg_label, fg_slots, fg_text = foreground
        manifest = {}
        try:
            manifest = read_foreground_manifest(root)
            fg_budget = manifest.get("budget_tokens")
            for name in manifest.get("order", []):
                entry = manifest.get("modules", {}).get(name, {})
                tokens = foreground_tokens(
                    (root / FOREGROUND_SET_DIR / name).read_text(encoding="utf-8"))
                print("BUDGET %d/%s foreground module tokens (%s)"
                      % (tokens, entry.get("budget_tokens", "?"), name))
        except (OSError, ValueError) as exc:
            errors.append("cannot measure the foreground module budgets: %s" % exc)
            fg_budget = None
        fg_tokens = foreground_tokens(fg_text)
        print("BUDGET %d/%s foreground tokens (%s, %d modules, %d slots)"
              % (fg_tokens, fg_budget, fg_label, len(manifest.get("order", [])),
                 len(fg_slots)))
    for message in errors:
        print("FAIL %s" % message)
    if errors:
        return 1 if entries else 2

    if args.foreground:
        pack_path = Path(args.pack).resolve() if args.pack else None
        if not args.check:
            if pack_path is None or not args.out:
                print("FAIL a foreground render needs --pack and --out: the policy "
                      "belongs to the consumer")
                return 2
            try:
                text = render_foreground(foreground, pack_path)
            except (OSError, yaml.YAMLError, ValueError) as exc:
                print("FAIL %s" % exc)
                return 1 if isinstance(exc, ValueError) else 2
            out_file = Path(args.out).resolve()
            if out_file.is_dir():
                print("FAIL --out must name a file in --foreground mode: %s" % out_file)
                return 2
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(text, encoding="utf-8")
            print("WROTE %s" % out_file)
            return 0
        if args.out:
            if pack_path is None:
                print("FAIL --out needs --pack: slots are project-owned")
                return 2
            try:
                text = render_foreground(foreground, pack_path)
            except (OSError, yaml.YAMLError, ValueError) as exc:
                print("FAIL %s" % exc)
                return 1 if isinstance(exc, ValueError) else 2
            out_file = Path(args.out).resolve()
            if not out_file.is_file():
                print("DIFF missing foreground policy: %s" % out_file)
                return 1
            if out_file.read_text(encoding="utf-8") != text:
                print("DIFF foreground policy differs from a fresh fill: %s" % out_file)
                return 1
            print("OK foreground policy %s matches %s" % (fg_label, out_file))
            return 0
        print("OK foreground set %s: %d modules pinned, %d slots declared, "
              "per-module and total budgets green"
              % (fg_label, len(manifest.get("order", [])), len(fg_slots)))
        return 0

    if args.check:
        rendered = []
        if args.pack:
            pack_path = Path(args.pack).resolve()
            try:
                rendered = render_all(root, entries, pack_path)
            except (OSError, yaml.YAMLError, ValueError) as exc:
                print("FAIL %s" % exc)
                return 1 if isinstance(exc, ValueError) else 2
        if args.out:
            if not args.pack:
                print("FAIL --out needs --pack: slots are project-owned")
                return 2
            out_dir = Path(args.out).resolve()
            problems = compare(out_dir, rendered)
            for message in problems:
                print("DIFF %s" % message)
            if problems:
                return 1
            print("OK %s matches %s" % (catalog_label, out_dir))
            return 0
        if args.pack:
            print("OK %s: %d entries render clean (no --out to compare)"
                  % (catalog_label, len(rendered)))
        else:
            print("OK %s: %d entries, pins current, selection and budget green "
                  "(structure mode)" % (catalog_label, len(entries)))
        return 0

    if not args.pack or not args.out:
        print("FAIL a render needs --pack and --out (the projection belongs to the consumer)")
        return 2
    try:
        rendered = render_all(root, entries, Path(args.pack).resolve())
    except (OSError, yaml.YAMLError, ValueError) as exc:
        print("FAIL %s" % exc)
        return 1 if isinstance(exc, ValueError) else 2
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in rendered:
        path = out_dir / (name + ".md")
        path.write_text(text, encoding="utf-8")
        print("WROTE %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
