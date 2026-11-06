#!/usr/bin/env python3
"""Validate a canonical tool-set manifest and its definition hash.

The manifest is consumer-owned; this checker is the library-side contract
(AS-06, TS-01..TS-10). It hashes the tool definitions in declared order, not the
masks, so a mask-only change does not invalidate the prompt cache.

Usage:
    python3 tooling/check_tool_set.py PATH [--update-hash] [--previous PATH] [--json]

Exit 0 clean, 1 violations, 2 unreadable/invalid JSON. ASCII-only output.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
VOLATILE = [
    (re.compile(r"\b20\d{2}-\d{2}-\d{2}\b"), "ISO date"),
    (re.compile(r"\b20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}"), "timestamp"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "UUID"),
    (re.compile(r"\blocalhost:\d+\b", re.I), "localhost port"),
    (re.compile(r"(?<![\w/])/tmp/"), "temp path"),
    (re.compile(r"\bpid=\d+\b", re.I), "PID"),
    (re.compile(r"\bseed=\d+\b", re.I), "seed"),
    (re.compile(r"\b(?:hostname|cwd|epoch|run_?id|request_?id|session|trace_?id)\s*[:=]", re.I), "runtime metadata"),
    (re.compile(r"\b[A-Z][A-Z0-9_]{1,}="), "environment value"),
    (re.compile(r"\{\{?[A-Z_]+\}?\}"), "template placeholder"),
    (re.compile(r"\b\d{1,2}:\d{2}\s*(?:UTC|GMT)\b", re.I), "clock time"),
    (re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b", re.I), "month-name date"),
    (re.compile(r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b", re.I), "day-first date"),
    (re.compile(r"\b1[6-9]\d{8}\b"), "epoch seconds"),
]
TOP_KEYS = {"schema", "version", "mask_version", "toolset_sha256", "order", "tools", "masks"}
TOOL_KEYS = {"name", "description", "input_schema", "handler", "stability", "wire"}
MASK_KEYS = {"roles", "deferred", "deferred_unmatched"}


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def canonical(tools):
    return json.dumps(tools, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(tools):
    return hashlib.sha256(canonical(tools).encode("utf-8")).hexdigest()


def check(data, check_hash=True):
    errors = []
    if not isinstance(data, dict):
        return ["manifest must be a JSON object"], ""
    for key in data:
        if key not in TOP_KEYS:
            errors.append("unknown top-level key: %s" % key)
    if data.get("schema") != "agent-toolset/1":
        errors.append("schema must be agent-toolset/1")
    version = data.get("version")
    if not isinstance(version, str) or not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+$", version):
        errors.append("version must be semver")
    mask_version = data.get("mask_version")
    if not isinstance(mask_version, str) or not mask_version.strip():
        errors.append("mask_version must be a non-empty string")
    tools = data.get("tools")
    if not isinstance(tools, list) or not tools:
        errors.append("tools must be a non-empty list")
        tools = []
    order = data.get("order")
    if not isinstance(order, list) or not order:
        errors.append("order must be a non-empty list")
        order = []
    names = []
    stabilities = {}
    for index, tool in enumerate(tools):
        label = "tools[%d]" % index
        if not isinstance(tool, dict):
            errors.append("%s is not an object" % label)
            continue
        for key in tool:
            if key not in TOOL_KEYS:
                errors.append("%s unknown key: %s" % (label, key))
        for key in ("name", "description", "input_schema", "handler", "stability"):
            if key not in tool:
                errors.append("%s missing %s" % (label, key))
        name = tool.get("name")
        if not isinstance(name, str) or not NAME_RE.match(name):
            errors.append("%s name is not a valid tool name: %s" % (label, ascii(name)))
        else:
            names.append(name)
            stabilities[name] = tool.get("stability")
        description = tool.get("description")
        if not isinstance(description, str) or not description.strip():
            errors.append("%s description is empty" % label)
        for pattern, kind in VOLATILE:
            if any(pattern.search(value) for value in strings(tool)):
                errors.append("%s contains volatile %s" % (label, kind))
                break
        if not isinstance(tool.get("input_schema"), dict):
            errors.append("%s input_schema must be an object" % label)
        if not isinstance(tool.get("handler"), str) or not tool["handler"].strip():
            errors.append("%s handler is empty" % label)
        if tool.get("stability") not in ("static", "deferred"):
            errors.append("%s stability is not static|deferred" % label)
        if "wire" in tool and not isinstance(tool["wire"], dict):
            errors.append("%s wire must be an object" % label)
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        errors.append("duplicate tool names: %s" % ", ".join(duplicates))
    if order != names:
        errors.append("order does not match tools order")
    deferred_indexes = [index for index, name in enumerate(names)
                        if stabilities.get(name) == "deferred"]
    if deferred_indexes:
        first = deferred_indexes[0]
        if any(stabilities.get(name) != "deferred" for name in names[first:]):
            errors.append("deferred tools must form a contiguous suffix")
    masks = data.get("masks")
    if not isinstance(masks, dict):
        errors.append("masks must be an object")
        masks = {}
    for key in masks:
        if key not in MASK_KEYS:
            errors.append("unknown masks key: %s" % key)
    roles = masks.get("roles")
    if not isinstance(roles, dict) or not roles:
        errors.append("masks.roles must be a non-empty object")
        roles = {}
    for role, allowed in roles.items():
        if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
            errors.append("masks.roles.%s must be a list of tool names" % role)
            continue
        if len(allowed) != len(set(allowed)):
            errors.append("masks.roles.%s has duplicate tools" % role)
        for item in allowed:
            if item not in names:
                errors.append("masks.roles.%s names unknown tool %s" % (role, item))
        positions = [order.index(item) for item in allowed if item in order]
        if positions != sorted(positions):
            errors.append("masks.roles.%s is not in manifest order" % role)
    deferred = masks.get("deferred")
    if not isinstance(deferred, list) or not all(isinstance(item, str) for item in deferred):
        errors.append("masks.deferred must be a list")
        deferred = []
    unmatched = masks.get("deferred_unmatched", [])
    if not isinstance(unmatched, list) or not all(isinstance(item, str) for item in unmatched):
        errors.append("masks.deferred_unmatched must be a list")
        unmatched = []
    if len(deferred) != len(set(deferred)):
        errors.append("masks.deferred has duplicate patterns")
    for item in deferred:
        if item.endswith("*"):
            prefix = item[:-1]
            matches = [name for name in names if name.startswith(prefix)
                       and stabilities.get(name) == "deferred"]
            if not matches and item not in unmatched:
                errors.append("masks.deferred pattern matches no deferred tool: %s" % item)
        else:
            if stabilities.get(item) != "deferred":
                errors.append("masks.deferred names no deferred tool: %s" % item)
    for item in unmatched:
        if item not in deferred:
            errors.append("masks.deferred_unmatched is not in masks.deferred: %s" % item)
        elif item.endswith("*") and any(
                name.startswith(item[:-1]) and stabilities.get(name) == "deferred"
                for name in names):
            errors.append("stale masks.deferred_unmatched entry: %s" % item)
    expected = digest(tools)
    actual = data.get("toolset_sha256")
    if check_hash and actual != expected:
        errors.append("toolset_sha256 does not match definitions (expected %s)" % expected)
    return errors, expected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--update-hash", action="store_true")
    parser.add_argument("--previous", default=None,
                        help="previous manifest; fail when the hash changes without a version bump")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    path = Path(args.path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("tool-set: cannot read %s: %s" % (path, exc))
        return 2
    if not isinstance(data, dict):
        print("tool-set: manifest must be a JSON object")
        return 2
    if args.previous:
        try:
            previous = json.loads(Path(args.previous).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print("tool-set: cannot read previous %s: %s" % (args.previous, exc))
            return 2
        old_errors, old_hash = check(previous, check_hash=False)
        new_errors, new_hash = check(data, check_hash=False)
        if old_errors or new_errors:
            for error in old_errors + new_errors:
                print("FAIL " + error)
            return 1
        if old_hash != new_hash and previous.get("version") == data.get("version"):
            print("FAIL definition hash changed without a version bump")
            return 1
    if args.update_hash:
        errors, expected = check(data, check_hash=False)
        if errors:
            for error in errors:
                print("FAIL " + error)
            return 1
        data["toolset_sha256"] = expected
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print("tool-set hash updated: %s" % expected)
        return 0
    errors, expected = check(data)
    count = len(data.get("tools")) if isinstance(data.get("tools"), list) else 0
    if args.json:
        print(json.dumps({"path": str(path), "expected": expected,
                          "violations": errors, "tools": count}, indent=2))
    else:
        for error in errors:
            print("FAIL " + error)
        print("tool-set: %d tools, %d violation(s)" % (count, len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
