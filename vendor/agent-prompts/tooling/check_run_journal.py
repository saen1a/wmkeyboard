#!/usr/bin/env python3
"""Validate an append-only run journal (LH-14).

Usage:
    python3 tooling/check_run_journal.py PATH [--state RUN.md] [--json]

Each line is one JSON object. Sequence numbers are consecutive from 1,
timestamps are non-decreasing, action receipts match a start, the terminal event
is coherent, and the last event is checkpoint, done, or stop.

`--state PATH` also checks that the state view is the one the journal last
committed: the last `checkpoint` event's `state_sha256` must equal the SHA-256
of the file's bytes. A mismatch is a stale view and fails (LH-14). A mismatch
cannot be repaired by editing the journal; rewrite the view from the journal.

An `action_started` with no matching receipt is reported as `WARN`, not as a
violation: the action may still be running when a live journal is read. On a
terminated journal it marks a possibly partial side effect that a resuming
reader must resolve before replaying (LH-12, LH-14).

Exit 0 clean, 1 violations (including invalid JSON and a stale view), 2
unreadable input. ASCII-only output.
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

KINDS = {"start", "checkpoint", "action_started", "action_result",
         "action_withheld", "note", "stop", "done"}
PHASES = {"Plan", "PlanReview", "Implement", "Review", "Fix", "Verify", "Push",
          "Ready", "Ready (unverified)", "Done", "HALT"}
GATES = {"pass", "fix", "hold", "halt"}
REQUIRED = ["schema", "seq", "at", "kind", "unit", "phase",
            "action", "result", "evidence"]
ALLOWED = set(REQUIRED) | {"gate", "action_id", "state_sha256", "reason"}
TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def parse_timestamp(value):
    if not isinstance(value, str) or not TIMESTAMP_RE.match(value):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def check(path, state_path=None):
    errors = []
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return None, ["cannot read: %s" % exc]
    events = []
    previous_at = None
    started = {}
    resolved = set()
    terminal_at = None
    for index, line in enumerate(lines, 1):
        if not line.strip():
            errors.append("line %d is empty" % index)
            continue
        try:
            event = json.loads(line)
        except ValueError as exc:
            errors.append("line %d is not JSON: %s" % (index, exc))
            continue
        if not isinstance(event, dict):
            errors.append("line %d is not an object" % index)
            continue
        events.append(event)
        position = len(events)
        for key in event:
            if key not in ALLOWED:
                errors.append("line %d unknown key: %s" % (index, key))
        for key in REQUIRED:
            if key not in event:
                errors.append("line %d missing %s" % (index, key))
        if event.get("schema") != "agent-run-journal/1":
            errors.append("line %d schema is not agent-run-journal/1" % index)
        seq = event.get("seq")
        if isinstance(seq, bool) or not isinstance(seq, int):
            errors.append("line %d seq is not an integer: %r" % (index, seq))
        elif seq != position:
            errors.append("line %d seq is %r, expected %d"
                          % (index, seq, position))
        at = parse_timestamp(event.get("at"))
        if at is None:
            errors.append("line %d at is not an ISO-8601 UTC timestamp" % index)
        elif previous_at is not None and at < previous_at:
            errors.append("line %d at is before the previous event" % index)
        if at is not None:
            previous_at = at
        kind = event.get("kind")
        if kind not in KINDS:
            errors.append("line %d kind is not canonical: %r" % (index, kind))
        if event.get("phase") not in PHASES:
            errors.append("line %d phase is not canonical: %r"
                          % (index, event.get("phase")))
        if "gate" in event and event.get("gate") not in GATES:
            errors.append("line %d gate is not canonical: %r"
                          % (index, event.get("gate")))
        for key in ("unit", "action", "result", "evidence"):
            if not isinstance(event.get(key), str):
                errors.append("line %d %s must be a string" % (index, key))
        if not str(event.get("unit", "")).strip():
            errors.append("line %d unit is empty" % index)
        if "reason" in event:
            if not isinstance(event["reason"], str) or not event["reason"].strip():
                errors.append("line %d reason must be a non-empty string" % index)
        if "state_sha256" in event and not HASH_RE.match(str(event["state_sha256"])):
            errors.append("line %d state_sha256 is not a sha256" % index)

        if position == 1 and kind != "start":
            errors.append("line 1 must be a start event")
        if kind == "start":
            if position != 1:
                errors.append("line %d start must be the first event" % index)
            if event.get("unit") != "run":
                errors.append("line %d start unit must be 'run'" % index)
            if not str(event.get("result", "")).strip():
                errors.append("line %d start needs the goal in result" % index)

        if terminal_at is not None:
            errors.append("line %d follows the terminal event at line %d"
                          % (index, terminal_at))
        if kind in ("done", "stop"):
            terminal_at = index

        if kind == "checkpoint":
            if "gate" not in event:
                errors.append("line %d checkpoint needs gate" % index)
            if "state_sha256" not in event:
                errors.append("line %d checkpoint needs state_sha256" % index)

        if kind in ("action_started", "action_result", "action_withheld"):
            action_id = event.get("action_id")
            if not isinstance(action_id, str) or not action_id.strip():
                errors.append("line %d action event needs action_id" % index)
            elif kind == "action_started":
                if action_id in started:
                    errors.append("line %d duplicate action_id: %s"
                                  % (index, action_id))
                started[action_id] = index
            else:
                if action_id not in started:
                    errors.append("line %d action_id %s has no action_started"
                                  % (index, action_id))
                if action_id in resolved:
                    errors.append("line %d action_id %s already has a receipt"
                                  % (index, action_id))
                resolved.add(action_id)

        if kind == "action_result" and not str(event.get("evidence", "")).strip():
            errors.append("line %d action_result needs evidence" % index)
        if kind == "action_withheld":
            if not str(event.get("reason", "")).strip():
                errors.append("line %d action_withheld needs reason" % index)
        if kind == "note":
            if not str(event.get("result", "")).strip() and \
                    not str(event.get("reason", "")).strip():
                errors.append("line %d note needs result or reason" % index)
        if kind == "done":
            if event.get("phase") != "Done":
                errors.append("line %d done phase must be Done" % index)
            if event.get("gate") != "pass":
                errors.append("line %d done gate must be pass" % index)
            if not str(event.get("evidence", "")).strip():
                errors.append("line %d done needs evidence" % index)
        if kind == "stop":
            if event.get("phase") != "HALT":
                errors.append("line %d stop phase must be HALT" % index)
            if event.get("gate") != "halt":
                errors.append("line %d stop gate must be halt" % index)
            if not str(event.get("reason", "")).strip():
                errors.append("line %d stop needs reason" % index)

    if not events:
        errors.append("journal has no events")
    elif events[-1].get("kind") not in ("checkpoint", "done", "stop"):
        errors.append("journal must end at checkpoint, done, or stop")
    if events and events[0].get("kind") != "start":
        errors.append("journal must begin with a start event")
    if state_path is not None:
        errors.extend(check_state_hash(events, state_path))
    return events, errors


def check_state_hash(events, state_path):
    """Return errors when the state view is not the last committed view."""
    checkpoints = [event for event in events
                   if event.get("kind") == "checkpoint"
                   and isinstance(event.get("state_sha256"), str)]
    if not checkpoints:
        return ["--state: the journal has no checkpoint with state_sha256"]
    try:
        digest = hashlib.sha256(Path(state_path).read_bytes()).hexdigest()
    except OSError as exc:
        return ["--state: cannot read %s: %s" % (state_path, exc)]
    expected = checkpoints[-1]["state_sha256"]
    if digest != expected:
        return ["stale view: %s hashes to %s, but the last checkpoint (seq %s) "
                "recorded %s; rewrite the view from the journal"
                % (state_path, digest, checkpoints[-1].get("seq"), expected)]
    return []


def advisories(events):
    """Return non-fatal notes a resuming reader must resolve (LH-12, LH-14)."""
    warnings = []
    started = {}
    resolved = set()
    for event in events:
        kind = event.get("kind")
        action_id = event.get("action_id")
        if kind == "action_started" and isinstance(action_id, str):
            started.setdefault(action_id, event.get("seq"))
        elif kind in ("action_result", "action_withheld") and isinstance(action_id, str):
            resolved.add(action_id)
    for action_id in sorted(started):
        if action_id not in resolved:
            warnings.append("action_id %s started at seq %s has no receipt; "
                            "resolve the side effect before replaying"
                            % (action_id, started[action_id]))
    return warnings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--state", default=None,
                        help="verify the last checkpoint state_sha256 against this "
                             "state file (a mismatch is a stale view)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    events, errors = check(args.path, args.state)
    if events is None:
        print("journal: %s" % errors[0])
        return 2
    warnings = advisories(events)
    if args.json:
        print(json.dumps({"path": args.path, "events": len(events),
                          "violations": errors, "warnings": warnings}, indent=2))
    else:
        for warning in warnings:
            print("WARN " + warning)
        for error in errors:
            print("FAIL " + error)
        print("run-journal: %d events, %d violation(s)" % (len(events), len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
