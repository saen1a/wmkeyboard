#!/usr/bin/env python3
"""Validate a work mandate record against WA-02..WA-12.

The record is the only thing that grants work (`standards/work-authorization.md`,
WA-04). This checker enforces its mechanical half: shape, closed vocabularies,
basis/strength coherence, and the state invariants of `withdrawn` and `revoked`.
It cannot judge whether the semantic assessment was right, and it does not try.

Usage:
    python3 tooling/check_mandate.py PATH [--json]

Exit 0 clean, 1 violations, 2 unreadable/invalid JSON. ASCII-only output.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "agent-mandate/1"
TOP_KEYS = {"schema", "mandate_id", "policy_version", "strength", "basis",
            "scope", "actor", "granted_at", "state", "withdrawn_by",
            "revocation", "supersedes", "history"}
REQUIRED = ["schema", "mandate_id", "policy_version", "strength", "basis",
            "scope", "actor", "granted_at", "state", "history"]
BASIS_KEYS = {"via", "source", "sender", "scope_key", "cell", "addressed",
              "listed_sender", "rules", "trigger_id"}
SCOPE_KEYS = {"unit", "surface", "accept_mode", "notes"}
ACTOR_KEYS = {"kind", "name", "source"}
WITHDRAWN_KEYS = {"kind", "name", "at", "reason_code"}
REVOCATION_KEYS = {"at", "failed_check", "policy_version"}
HISTORY_KEYS = {"at", "event", "policy_version", "note"}
VIAS = ("addressed", "followup", "admission", "bot")
CELLS = ("listedUnaddressed", "unlistedAddressed", "unlistedUnaddressed")
STRENGTHS = ("explicit", "inferred")
STATES = ("active", "withdrawn", "revoked")
MODES = ("off", "observe", "auto")
FAILED_CHECKS = ("source_stopped_listening", "conversation_has_no_work",
                 "sender_not_listed", "weaker_admission_cell", "bot_not_listed",
                 "rule_disabled", "proactive_acceptance_disabled")
EVENTS = ("granted", "revalidated", "withdrawn", "revoked", "resumed")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.:_-]{1,63}$")
TIME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})Z$")
CODE_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
RULE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


def parse_time(value):
    """Return the parsed UTC datetime, or None when the value is not ISO-Z."""
    if not isinstance(value, str):
        return None
    if not TIME_RE.match(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def unknown_keys(obj, allowed, label, errors):
    for key in obj:
        if key not in allowed:
            errors.append("%s unknown key: %s" % (label, key))


def check(data, now=None):
    """Return the list of violations for one mandate record."""
    errors = []
    if not isinstance(data, dict):
        return ["mandate must be a JSON object"]
    now = now or datetime.now(timezone.utc)
    unknown_keys(data, TOP_KEYS, "mandate", errors)
    for key in REQUIRED:
        if key not in data:
            errors.append("missing required key: %s" % key)
    if data.get("schema") != SCHEMA:
        errors.append("schema must be %s" % SCHEMA)
    mandate_id = data.get("mandate_id")
    if not isinstance(mandate_id, str) or not ID_RE.match(mandate_id):
        errors.append("mandate_id is not a lowercase hyphenated id")
    policy_version = data.get("policy_version")
    if not isinstance(policy_version, str) or not VERSION_RE.match(policy_version):
        errors.append("policy_version is not a canonical version string")
    strength = data.get("strength")
    if strength not in STRENGTHS:
        errors.append("strength must be explicit|inferred")
    granted_at = parse_time(data.get("granted_at"))
    if granted_at is None:
        errors.append("granted_at must be an ISO-8601 UTC timestamp ending in Z")
    elif granted_at > now:
        errors.append("granted_at is in the future")

    basis = data.get("basis")
    if not isinstance(basis, dict):
        errors.append("basis must be an object")
        basis = {}
    else:
        unknown_keys(basis, BASIS_KEYS, "basis", errors)
        for key in ("via", "source", "sender", "scope_key"):
            if key not in basis:
                errors.append("basis missing %s" % key)
    via = basis.get("via")
    if via not in VIAS:
        errors.append("basis.via must be one of %s" % "|".join(VIAS))
    if "cell" in basis and basis["cell"] not in CELLS:
        errors.append("basis.cell is not an admission cell name")
    if via == "admission" and "cell" not in basis:
        errors.append("basis.via=admission requires basis.cell")
    if via == "addressed":
        if basis.get("addressed") is not True:
            errors.append("basis.via=addressed requires addressed=true")
        if basis.get("listed_sender") is not True:
            errors.append("basis.via=addressed requires listed_sender=true")
    rules = basis.get("rules", [])
    if not isinstance(rules, list):
        errors.append("basis.rules must be a list")
        rules = []
    rule_ids = []
    for index, rule in enumerate(rules):
        label = "basis.rules[%d]" % index
        if not isinstance(rule, dict):
            errors.append("%s is not an object" % label)
            continue
        unknown_keys(rule, {"id", "instruction"}, label, errors)
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not RULE_RE.match(rule_id):
            errors.append("%s id is not a rule id" % label)
        else:
            rule_ids.append(rule_id)
        if not isinstance(rule.get("instruction"), str) or not rule["instruction"].strip():
            errors.append("%s instruction is empty" % label)
    duplicates = sorted({rid for rid in rule_ids if rule_ids.count(rid) > 1})
    if duplicates:
        errors.append("basis.rules has duplicate ids: %s" % ", ".join(duplicates))

    scope = data.get("scope")
    if not isinstance(scope, dict):
        errors.append("scope must be an object")
        scope = {}
    else:
        unknown_keys(scope, SCOPE_KEYS, "scope", errors)
    for key in ("unit", "surface"):
        if key not in scope:
            errors.append("scope missing %s" % key)
    if not isinstance(scope.get("unit"), str) or not scope["unit"].strip():
        errors.append("scope.unit is empty")
    surface = scope.get("surface")
    if not isinstance(surface, list) or not surface:
        errors.append("scope.surface must be a non-empty list")
        surface = []
    if any(not isinstance(item, str) or not item.strip() for item in surface):
        errors.append("scope.surface has an empty entry")
    if len(surface) != len(set(item for item in surface if isinstance(item, str))):
        errors.append("scope.surface has duplicate entries")
    mode = scope.get("accept_mode")
    if "accept_mode" in scope and mode not in MODES:
        errors.append("scope.accept_mode must be off|observe|auto")

    actor = data.get("actor")
    if not isinstance(actor, dict):
        errors.append("actor must be an object")
        actor = {}
    else:
        unknown_keys(actor, ACTOR_KEYS, "actor", errors)
        for key in ("kind", "name", "source"):
            if key not in actor:
                errors.append("actor missing %s" % key)
    if actor.get("kind") not in ("person", "bot", "system"):
        errors.append("actor.kind must be person|bot|system")
    if actor.get("source") != basis.get("source"):
        errors.append("actor.source must equal basis.source (identities are per source)")
    if actor.get("kind") in ("bot", "system") and strength == "explicit":
        errors.append("strength=explicit requires actor.kind=person (WA-02)")
    if via == "bot" and actor.get("kind") != "bot":
        errors.append("basis.via=bot requires actor.kind=bot")

    # WA-02: a listed identity that addresses the agent is explicit; a bot never is.
    if via == "addressed" and strength == "inferred":
        errors.append("basis.via=addressed with a listed sender is an explicit request (WA-02)")
    if via == "bot" and strength != "inferred":
        errors.append("basis.via=bot can only produce an inferred candidate (WA-02)")

    if strength == "inferred":
        if not rule_ids:
            errors.append("strength=inferred requires at least one matched rule (WA-02)")
        if mode in (None, "off"):
            errors.append("strength=inferred requires scope.accept_mode observe|auto")
        elif mode == "observe":
            errors.append("scope.accept_mode=observe records no grant; an observe record "
                          "cannot be accepted (WA-07)")

    state = data.get("state")
    if state not in STATES:
        errors.append("state must be active|withdrawn|revoked")
    withdrawn = data.get("withdrawn_by")
    revocation = data.get("revocation")
    if withdrawn is not None and revocation is not None:
        errors.append("a mandate is withdrawn or revoked, never both")
    if state == "withdrawn":
        if not isinstance(withdrawn, dict):
            errors.append("state=withdrawn requires withdrawn_by")
        else:
            unknown_keys(withdrawn, WITHDRAWN_KEYS, "withdrawn_by", errors)
            if withdrawn.get("kind") != "person":
                errors.append("withdrawn_by.kind must be person (WA-10)")
            if not isinstance(withdrawn.get("name"), str) or not withdrawn["name"].strip():
                errors.append("withdrawn_by.name is empty")
            if not isinstance(withdrawn.get("reason_code"), str) \
                    or not CODE_RE.match(withdrawn["reason_code"]):
                errors.append("withdrawn_by.reason_code is not a code")
            at = parse_time(withdrawn.get("at"))
            if at is None:
                errors.append("withdrawn_by.at must be an ISO-8601 UTC timestamp ending in Z")
            elif granted_at is not None and at < granted_at:
                errors.append("withdrawn_by.at predates granted_at")
    elif withdrawn is not None:
        errors.append("withdrawn_by is only valid when state=withdrawn")
    if state == "revoked":
        if not isinstance(revocation, dict):
            errors.append("state=revoked requires revocation")
        else:
            unknown_keys(revocation, REVOCATION_KEYS, "revocation", errors)
            if revocation.get("failed_check") not in FAILED_CHECKS:
                errors.append("revocation.failed_check is not a revalidation check")
            if not isinstance(revocation.get("policy_version"), str) \
                    or not revocation["policy_version"].strip():
                errors.append("revocation.policy_version is empty")
            at = parse_time(revocation.get("at"))
            if at is None:
                errors.append("revocation.at must be an ISO-8601 UTC timestamp ending in Z")
            elif granted_at is not None and at < granted_at:
                errors.append("revocation.at predates granted_at")
    elif revocation is not None:
        errors.append("revocation is only valid when state=revoked")

    if "supersedes" in data:
        previous = data["supersedes"]
        if not isinstance(previous, str) or not ID_RE.match(previous):
            errors.append("supersedes is not a mandate id")
        elif previous == mandate_id:
            errors.append("a wider grant is a new mandate, not a rewrite (WA-04)")

    history = data.get("history")
    if not isinstance(history, list) or not history:
        errors.append("history must be a non-empty list")
        history = []
    last_time = None
    for index, entry in enumerate(history):
        label = "history[%d]" % index
        if not isinstance(entry, dict):
            errors.append("%s is not an object" % label)
            continue
        unknown_keys(entry, HISTORY_KEYS, label, errors)
        event = entry.get("event")
        if event not in EVENTS:
            errors.append("%s event is not a mandate event" % label)
        at = parse_time(entry.get("at"))
        if at is None:
            errors.append("%s at must be an ISO-8601 UTC timestamp ending in Z" % label)
        else:
            if at > now:
                errors.append("%s at is in the future" % label)
            if granted_at is not None and at < granted_at:
                errors.append("%s at predates granted_at" % label)
            if last_time is not None and at < last_time:
                errors.append("%s at goes backwards; history is append-only" % label)
            last_time = at
    if history and isinstance(history[0], dict) and history[0].get("event") != "granted":
        errors.append("history[0] must be the granted event (WA-04)")
    last_event = history[-1].get("event") if history and isinstance(history[-1], dict) else None
    expected = {"active": ("granted", "revalidated", "resumed"),
                "withdrawn": ("withdrawn",),
                "revoked": ("revoked",)}.get(state, ())
    if expected and last_event not in expected:
        errors.append("state=%s but the last history event is %s" % (state, last_event))
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    path = Path(args.path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("mandate: cannot read %s: %s" % (path, exc))
        return 2
    if not isinstance(data, dict):
        print("mandate: record must be a JSON object")
        return 2
    errors = check(data)
    if args.json:
        print(json.dumps({"path": str(path), "state": data.get("state"),
                          "strength": data.get("strength"),
                          "violations": errors}, indent=2))
    else:
        for error in errors:
            print("FAIL " + error)
        print("mandate: %s/%s, %d violation(s)"
              % (data.get("state"), data.get("strength"), len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
