#!/usr/bin/env python3
"""Validate and inspect a long-horizon run state (LH-02, LH-03, LH-07).

The run state is the durable source of truth for a run that spans sessions.
This tool is the deterministic half of `standards/long-horizon-runs.md`: it
checks the machine-readable contract and the cross-field invariants that a
reader or a model would otherwise have to remember.

Usage:

    run_state.py check PATH [--schema PATH] [--max-age-hours N] [--json]
    run_state.py status PATH [--json]
    run_state.py next PATH

Exit 0 when the state is valid, 1 on any violation. `status` and `next` are
read-only views.

`standards/run-state.schema.json` owns the required keys, enums, table columns,
checkpoint kinds, acceptance keys, status/phase mapping, patterns, and defaults.
This tool adds only the cross-field invariants: budget arithmetic, unit closure,
progress counters, acceptance coverage, checkpoint monotonicity, and stall
detection.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

class UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys."""

    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping", node.start_mark,
                    "found duplicate key %r" % (key,), key_node.start_mark)
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


ROOT = Path(__file__).resolve().parent.parent
PHASES = ["Plan", "PlanReview", "Implement", "Review", "Fix", "Verify", "Push"]
DEFAULT_SCHEMA = ROOT / "standards" / "run-state.schema.json"


def load_schema(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("schema is not an object")
    return data


def split_frontmatter(text):
    match = re.match(r"(?s)^---\s*\n(.*?)\n---\s*\n?(.*)$", text)
    if not match:
        return None, text
    try:
        front = yaml.load(match.group(1), Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise ValueError("frontmatter is not valid YAML: %s" % exc)
    if front is None:
        front = {}
    if not isinstance(front, dict):
        raise ValueError("frontmatter is not a mapping")
    return front, match.group(2)


def parse_table(body, heading, errors):
    """Return (columns, rows) for the first markdown table under ``## heading``."""
    lines = body.splitlines()
    start = None
    for index, line in enumerate(lines):
        if re.match(r"^##\s+%s\s*$" % re.escape(heading), line, re.I):
            start = index + 1
            break
    if start is None:
        errors.append("missing section: ## %s" % heading)
        return [], []
    table = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.strip().startswith("|"):
            table.append(line)
        elif table:
            break
    if len(table) < 2:
        errors.append("section %s has no table" % heading)
        return [], []
    columns = [cell.strip() for cell in table[0].strip().strip("|").split("|")]
    rows = []
    for line in table[1:]:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(set(cell) <= set("-: ") for cell in cells):
            continue
        rows.append(cells)
    return columns, rows


def iso_value(value):
    """YAML turns unquoted dates/timestamps into objects; normalize them back."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if hasattr(value, "isoformat") and not isinstance(value, str):
        return value.isoformat()
    return value


def as_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def parse_timestamp(value, pattern):
    if not isinstance(value, str) or not re.match(pattern, value):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def unit_closed(row, closure):
    if row["status"] in closure.get("terminal", []):
        return True
    return (row.get("kind") == "report"
            and row["status"] in closure.get("handoff", [])
            and row["next"] == closure.get("handoff_next", "none"))


def progress_count(row):
    match = re.match(r"\s*(\d+)\s*/\s*(\d+)", row["progress"])
    return (int(match.group(1)), int(match.group(2))) if match else None


def section_text(body, heading):
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if re.match(r"^##\s+%s\s*$" % re.escape(heading), line, re.I):
            out = []
            for candidate in lines[index + 1:]:
                if re.match(r"^##\s+", candidate):
                    break
                out.append(candidate)
            return "\n".join(out)
    return ""


def progress_signature(row):
    match = re.match(r"\s*(\d+)\s*/\s*(\d+)", row["progress"])
    count = (int(match.group(1)), int(match.group(2))) if match else row["progress"]
    return (count, row["artifact"])


def format_status(front):
    try:
        budget = front["budget"]["tokens"]
        return ("RUN %s | %s | units %s/%s | checkpoint %s | tokens %s/%s | next %s"
                % (front["run_id"], front["status"], front["units_done"],
                   front["units_total"], front["checkpoint"], budget["used"],
                   budget["limit"], front.get("next_action") or "none"))
    except (KeyError, TypeError):
        return None


def operator_line(body):
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if re.match(r"^##\s+Operator\s*$", line, re.I):
            for candidate in lines[index + 1:]:
                if re.match(r"^##\s+", candidate):
                    break
                if candidate.strip().startswith("RUN "):
                    return candidate.strip()
            return None
    return None


def check(path, schema_path=DEFAULT_SCHEMA, max_age_hours=None):
    errors = []
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "path": str(path), "errors": ["cannot read: %s" % exc]}

    try:
        schema = load_schema(schema_path)
    except (OSError, ValueError) as exc:
        return {"ok": False, "path": str(path),
                "errors": ["cannot read schema: %s" % exc]}

    enums = schema["enums"]
    patterns = schema["patterns"]
    defaults = schema.get("defaults", {})
    tables = schema["tables"]
    budget_spec = schema["budget"]
    acceptance_spec = schema["acceptance"]
    closure = schema.get("unit_closure", {})
    section_list = schema.get("sections", [])

    try:
        front, body = split_frontmatter(text)
    except ValueError as exc:
        return {"ok": False, "path": str(path), "errors": [str(exc)]}
    if front is None:
        return {"ok": False, "path": str(path),
                "errors": ["missing YAML frontmatter"]}

    allowed_keys = set(schema["frontmatter"]["required"]) | set(schema["frontmatter"]["optional"])
    for key in front:
        if key not in allowed_keys:
            errors.append("unknown frontmatter key: %s" % key)
    for key in schema["frontmatter"]["required"]:
        if key not in front:
            errors.append("frontmatter missing %s" % key)

    def enum_check(key, value, enum_name):
        if value not in enums[enum_name]:
            errors.append("%s is not a %s: %r" % (key, enum_name, value))

    schema_version = str(schema.get("version", ""))
    if front.get("schema_version") != schema_version:
        errors.append("schema_version is %r, expected %r"
                      % (front.get("schema_version"), schema_version))

    run_id = front.get("run_id")
    if not isinstance(run_id, str) or not re.match(patterns["run_id"], run_id):
        errors.append("run_id is not a lowercase slug: %r" % (run_id,))

    goal = front.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        errors.append("goal is empty")

    enum_check("status", front.get("status"), "status")
    enum_check("phase", front.get("phase"), "phase")

    status = front.get("status")
    phase = front.get("phase")
    allowed_phases = schema.get("status_phase", {}).get(status)
    if allowed_phases is not None and phase not in allowed_phases:
        errors.append("phase %r is not legal for status %r" % (phase, status))

    owner = front.get("owner")
    if not isinstance(owner, str) or not owner.strip():
        errors.append("owner is empty")

    if status == "halted":
        reason = front.get("reason")
        if reason not in schema.get("halt_reasons", []):
            errors.append("halted reason is not canonical: %r" % (reason,))
    elif status == "blocked":
        reason = front.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append("status blocked requires a non-empty dependency reason")
    elif "reason" in front and not isinstance(front["reason"], str):
        errors.append("reason is not a string")

    started = iso_value(front.get("started"))
    if not isinstance(started, str) or not re.match(patterns["date"], started):
        errors.append("started is not YYYY-MM-DD: %r" % (started,))
        started_at = None
    else:
        try:
            started_at = datetime.strptime(started, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            started_at = None
            errors.append("started is not a real date: %r" % (started,))

    updated = iso_value(front.get("updated"))
    updated_at = parse_timestamp(updated, patterns["timestamp"])
    if updated_at is None:
        errors.append("updated is not an ISO-8601 UTC timestamp: %r" % (updated,))

    if started_at and updated_at and updated_at < started_at:
        errors.append("updated is before started")
    if updated_at and updated_at > datetime.now(timezone.utc).replace(microsecond=0) + \
            timedelta(minutes=10):
        errors.append("updated is in the future")

    last_progress_at = iso_value(front.get("last_progress_at"))
    last_progress = parse_timestamp(last_progress_at, patterns["timestamp"])
    if last_progress is None:
        errors.append("last_progress_at is not an ISO-8601 UTC timestamp: %r"
                      % (last_progress_at,))
    elif updated_at is not None and last_progress > updated_at:
        errors.append("last_progress_at is after updated")

    if updated_at and max_age_hours is not None and status in ("active", "blocked"):
        age = (datetime.now(timezone.utc) - updated_at).total_seconds() / 3600.0
        if age > max_age_hours:
            errors.append("stale: updated is %.1f hours old (limit %s)"
                          % (age, max_age_hours))

    units_total = as_int(front.get("units_total"))
    units_done = as_int(front.get("units_done"))
    checkpoint_no = as_int(front.get("checkpoint"))
    for name, value in (("units_total", units_total), ("units_done", units_done),
                        ("checkpoint", checkpoint_no)):
        if value is None or value < 0:
            errors.append("%s is not a non-negative integer: %r"
                          % (name, front.get(name)))

    checkpoint_base = as_int(front.get("checkpoint_base", defaults.get("checkpoint_base", 0)))
    if checkpoint_base is None or checkpoint_base < 0:
        errors.append("checkpoint_base is not a non-negative integer: %r"
                      % (front.get("checkpoint_base"),))
        checkpoint_base = 0

    archive = front.get("checkpoint_archive")
    if checkpoint_base and (not isinstance(archive, str) or not archive.strip()):
        errors.append("checkpoint_archive is required when checkpoint_base > 0")
    elif archive is not None and (not isinstance(archive, str) or not archive.strip()):
        errors.append("checkpoint_archive must be a non-empty path")
    elif isinstance(archive, str) and archive.strip():
        candidates = [Path(archive), path.parent / archive, ROOT / archive]
        if not any(candidate.is_file() for candidate in candidates):
            errors.append("checkpoint_archive does not exist: %s" % archive)

    stall_window = front.get("stall_window", defaults.get("stall_window", 3))
    if as_int(stall_window) is None or as_int(stall_window) < 2:
        errors.append("stall_window must be an integer >= 2: %r" % (stall_window,))
        stall_window = None
    else:
        stall_window = as_int(stall_window)

    progress_max = front.get("progress_max_minutes")
    if as_int(progress_max) is None or as_int(progress_max) < 1:
        errors.append("progress_max_minutes must be a positive integer: %r"
                      % (progress_max,))
        progress_max = None
    else:
        progress_max = as_int(progress_max)

    next_action = front.get("next_action")
    if not isinstance(next_action, str):
        errors.append("next_action is not a string")
    elif not next_action.strip() and status not in ("done", "halted"):
        errors.append("next_action is empty for a non-terminal run")

    budget = front.get("budget")
    if not isinstance(budget, dict):
        errors.append("budget is not a mapping")
        budget = {}
    for measure in budget_spec["required"]:
        value = budget.get(measure)
        if not isinstance(value, dict):
            errors.append("budget.%s is missing" % measure)
            continue
        for field in budget_spec.get("measure_required", []):
            if field not in value:
                errors.append("budget.%s missing %s" % (measure, field))
        limit = as_int(value.get("limit"))
        used = as_int(value.get("used"))
        if limit is None or limit <= 0:
            errors.append("budget.%s.limit must be a positive integer" % measure)
        if used is None or used < 0:
            errors.append("budget.%s.used must be a non-negative integer" % measure)
        if (limit is not None and used is not None and used > limit
                and not (status == "halted" and front.get("reason") == "budget")):
            errors.append("budget.%s used %d exceeds limit %d"
                          % (measure, used, limit))

    acceptance = front.get("acceptance")
    acceptance_ids = []
    if not isinstance(acceptance, list) or not acceptance:
        errors.append("acceptance must be a non-empty list")
        acceptance = []
    for index, row in enumerate(acceptance):
        label = "acceptance[%d]" % index
        if not isinstance(row, dict):
            errors.append("%s is not a mapping" % label)
            continue
        for key in acceptance_spec["required"]:
            if key not in row:
                errors.append("%s missing %s" % (label, key))
        row_id = row.get("id")
        if isinstance(row_id, str) and row_id.strip():
            if row_id in acceptance_ids:
                errors.append("duplicate acceptance id: %s" % row_id)
            acceptance_ids.append(row_id)
        else:
            errors.append("%s id is empty" % label)
        criterion = row.get("criterion")
        if not isinstance(criterion, str) or not criterion.strip():
            errors.append("%s criterion is empty" % label)
        state = row.get("state")
        enum_check("%s.state" % label, state, "acceptance_state")
        evidence = row.get("evidence")
        if state in acceptance_spec["evidence_states"]:
            if not isinstance(evidence, str) or not evidence.strip():
                errors.append("%s has state %s without evidence" % (label, state))

    approval = front.get("push_approval")
    approval_at = None
    approval_ids = []
    approval_scope = ""
    if approval is not None:
        if not isinstance(approval, dict):
            errors.append("push_approval is not a mapping")
            approval = None
        else:
            for key in schema.get("push_approval", {}).get("required", []):
                if key not in approval:
                    errors.append("push_approval missing %s" % key)
            if "operator" in approval and (not isinstance(approval["operator"], str)
                                           or not approval["operator"].strip()):
                errors.append("push_approval.operator is empty")
            if "scope" in approval:
                if (not isinstance(approval["scope"], str)
                        or not approval["scope"].strip()):
                    errors.append("push_approval.scope is empty")
                else:
                    approval_scope = approval["scope"].lower()
            if "at" in approval:
                approval_at = parse_timestamp(iso_value(approval.get("at")),
                                              patterns["timestamp"])
                if approval_at is None:
                    errors.append("push_approval.at is not an ISO-8601 UTC timestamp")
                else:
                    if started_at and approval_at < started_at:
                        errors.append("push_approval.at is before started")
                    if updated_at and approval_at > updated_at:
                        errors.append("push_approval.at is after updated")
            ids = approval.get("ids")
            if not isinstance(ids, list) or not all(
                    isinstance(item, str) and item.strip() for item in ids):
                errors.append("push_approval.ids must be a list of acceptance ids")
            else:
                approval_ids = ids
                for item in ids:
                    if item not in acceptance_ids:
                        errors.append("push_approval.ids names unknown acceptance id: %s"
                                      % item)

    for key in ("branch", "model", "notes", "harness", "doctrine_version"):
        if key in front and (not isinstance(front[key], str) or not front[key].strip()):
            errors.append("%s must be a non-empty string" % key)

    run_gate = front.get("run_gate")
    run_gate_at = None
    run_gate_exit = None
    if run_gate is not None:
        if not isinstance(run_gate, dict):
            errors.append("run_gate is not a mapping")
            run_gate = None
        else:
            for key in schema.get("run_gate", {}).get("required", []):
                if key not in run_gate:
                    errors.append("run_gate missing %s" % key)
            if "command" in run_gate and (not isinstance(run_gate["command"], str)
                                          or not run_gate["command"].strip()):
                errors.append("run_gate.command is empty")
            if "evidence" in run_gate and (not isinstance(run_gate["evidence"], str)
                                           or not run_gate["evidence"].strip()):
                errors.append("run_gate.evidence is empty")
            if "at" in run_gate:
                run_gate_at = parse_timestamp(iso_value(run_gate.get("at")),
                                              patterns["timestamp"])
                if run_gate_at is None:
                    errors.append("run_gate.at is not an ISO-8601 UTC timestamp")
                elif updated_at is not None and run_gate_at > updated_at:
                    errors.append("run_gate.at is after updated")
            if "exit" in run_gate:
                run_gate_exit = as_int(run_gate.get("exit"))
                if run_gate_exit is None:
                    errors.append("run_gate.exit is not an integer")

    changed_files = front.get("changed_files")
    if changed_files is not None:
        if not isinstance(changed_files, list) or not all(
                isinstance(item, str) and item.strip() for item in changed_files):
            errors.append("changed_files must be a list of non-empty paths")

    lease = front.get("lease")
    if lease is not None:
        if not isinstance(lease, dict):
            errors.append("lease is not a mapping")
        else:
            for key in schema.get("lease", {}).get("required", []):
                if key not in lease:
                    errors.append("lease missing %s" % key)
            for key in ("resource", "owner"):
                if key in lease and (not isinstance(lease[key], str)
                                     or not lease[key].strip()):
                    errors.append("lease.%s is empty" % key)
            if "expires" in lease:
                expires = iso_value(lease.get("expires"))
                if parse_timestamp(expires, patterns["timestamp"]) is None:
                    errors.append("lease.expires is not an ISO-8601 UTC timestamp")

    unverified_ids = [row.get("id") for row in acceptance
                      if isinstance(row, dict) and row.get("state") == "unverified"]
    if status == "done" and run_gate_exit not in (None, 0):
        covered = ("run gate" in approval_scope or "run_gate" in approval_scope)
        if not covered:
            covered = any(item in approval_ids for item in unverified_ids)
        if not covered:
            errors.append("nonzero run_gate has no push_approval coverage")

    columns, unit_rows = parse_table(body, "Units", errors)
    expected_units = tables["units"]
    if columns and columns != expected_units:
        errors.append("Units columns are %s, expected %s" % (columns, expected_units))
        unit_rows = []
    units = []
    unit_ids = []
    for index, cells in enumerate(unit_rows):
        if len(cells) != len(expected_units):
            errors.append("Units row %d has %d cells, expected %d"
                          % (index + 2, len(cells), len(expected_units)))
            continue
        row = dict(zip(expected_units, cells))
        units.append(row)
        unit_id = row["unit_id"]
        if not re.match(patterns["unit_id"], unit_id):
            errors.append("Units row %d has an invalid unit_id: %r" % (index + 2, unit_id))
        if unit_id in unit_ids:
            errors.append("duplicate unit_id: %s" % unit_id)
        unit_ids.append(unit_id)
        enum_check("Units %s phase" % unit_id, row["phase"], "phase")
        enum_check("Units %s gate" % unit_id, row["gate"], "gate")
        enum_check("Units %s status" % unit_id, row["status"], "phase")
        if row["kind"] not in schema.get("unit_kinds", []):
            errors.append("Units %s kind is not canonical: %s" % (unit_id, row["kind"]))
        if (row["kind"] == "delivery" and row["status"] in closure.get("handoff", [])
                and row["next"] == closure.get("handoff_next", "none")):
            errors.append("Units %s is delivery but closes with next none" % unit_id)
        if unit_closed(row, closure) and row["gate"] != "pass":
            if not (row["kind"] == "report" and row["status"] == "Ready (unverified)"
                    and row["gate"] == "hold"):
                errors.append("Units %s is closed with gate %s" % (unit_id, row["gate"]))
        expected_unit_phase = {"Done": ("Push",),
                               "Ready": ("Verify",),
                               "Ready (unverified)": ("Verify",)}
        if row["status"] in expected_unit_phase:
            if row["phase"] not in expected_unit_phase[row["status"]]:
                errors.append("Units %s status %s has phase %s"
                              % (unit_id, row["status"], row["phase"]))
        elif row["status"] in PHASES and row["phase"] != row["status"]:
            errors.append("Units %s status %s has phase %s"
                          % (unit_id, row["status"], row["phase"]))
        evidence_statuses = closure.get("terminal", []) + closure.get("handoff", [])
        if row["status"] in evidence_statuses and not row["evidence"].strip():
            errors.append("Units %s is %s without evidence" % (unit_id, row["status"]))
        if not row["next"].strip():
            errors.append("Units %s has no next" % unit_id)

    for row in units:
        if row["next"] not in unit_ids + list(enums["phase"]) + ["none"]:
            errors.append("Units %s next is not a unit/phase/none: %s"
                          % (row["unit_id"], row["next"]))
        if row["status"] == "Done" and row["gate"] != "pass":
            errors.append("Units %s is Done with gate %s" % (row["unit_id"], row["gate"]))
        if row["kind"] == "report" and row["status"] == "Ready" and row["gate"] != "pass":
            errors.append("Units %s report Ready requires gate pass" % row["unit_id"])
        if (row["kind"] == "report" and row["status"] == "Ready (unverified)"
                and row["gate"] != "hold"):
            errors.append("Units %s report Ready (unverified) requires gate hold"
                          % row["unit_id"])
        if row["status"] in ("Done", "Ready", "Ready (unverified)") \
                and not row["evidence"].strip():
            errors.append("Units %s is %s without evidence" % (row["unit_id"], row["status"]))
        if row["status"] in ("Done", "Ready", "Ready (unverified)") \
                and row["evidence"].strip().lower() in ("-", "n/a", "tbd"):
            errors.append("Units %s evidence is a placeholder" % row["unit_id"])

    if units_total is not None and units_total < 1:
        errors.append("units_total must be at least 1")
    if units_total is not None and units_total != len(units):
        errors.append("units_total is %d but the Units table has %d rows"
                      % (units_total, len(units)))
    closed_count = sum(1 for row in units if unit_closed(row, closure))
    if units_done is not None and units_done != closed_count:
        errors.append("units_done is %d but %d unit rows are closed"
                      % (units_done, closed_count))
    if isinstance(budget.get("units"), dict):
        unit_limit = as_int(budget["units"].get("limit"))
        if unit_limit is not None and units_total is not None and unit_limit < units_total:
            errors.append("budget.units.limit is %d but units_total is %d"
                          % (unit_limit, units_total))
        unit_used = as_int(budget["units"].get("used"))
        if unit_used is not None and units_done is not None and unit_used != units_done:
            errors.append("budget.units.used is %d but units_done is %d"
                          % (unit_used, units_done))

    columns, checkpoint_rows = parse_table(body, "Checkpoints", errors)
    expected_checkpoints = tables["checkpoints"]
    if columns and columns != expected_checkpoints:
        errors.append("Checkpoints columns are %s, expected %s"
                      % (columns, expected_checkpoints))
        checkpoint_rows = []
    checkpoints = []
    expected_n = checkpoint_base + 1
    previous_at = None
    for index, cells in enumerate(checkpoint_rows):
        if len(cells) != len(expected_checkpoints):
            errors.append("Checkpoints row %d has %d cells, expected %d"
                          % (index + 2, len(cells), len(expected_checkpoints)))
            continue
        row = dict(zip(expected_checkpoints, cells))
        checkpoints.append(row)
        number = as_int(row["n"])
        if number != expected_n:
            errors.append("checkpoint n is %r, expected %d" % (row["n"], expected_n))
        expected_n += 1
        at = parse_timestamp(row["at"], patterns["timestamp"])
        if at is None:
            errors.append("checkpoint %s at is not an ISO-8601 UTC timestamp" % row["n"])
        elif previous_at is not None and at < previous_at:
            errors.append("checkpoint %s at is before the previous checkpoint" % row["n"])
        if at is not None:
            previous_at = at
        if row["unit"] != "-" and row["unit"] not in unit_ids:
            errors.append("checkpoint %s names unknown unit %s" % (row["n"], row["unit"]))
        enum_check("Checkpoints %s phase" % row["n"], row["phase"], "phase")
        enum_check("Checkpoints %s gate" % row["n"], row["gate"], "gate")
        if row["kind"] not in schema.get("checkpoint_kinds", []):
            errors.append("checkpoint %s kind is not canonical: %s"
                          % (row["n"], row["kind"]))
        for key in ("progress", "artifact", "next_action"):
            if not row[key].strip():
                errors.append("checkpoint %s has an empty %s" % (row["n"], key))

    if not checkpoints:
        errors.append("no checkpoint row")
    else:
        if checkpoint_no is not None and checkpoint_no != checkpoint_base + len(checkpoints):
            errors.append("checkpoint counter is %d but the table has %d rows from base %d"
                          % (checkpoint_no, len(checkpoints), checkpoint_base))
        if updated_at is not None and previous_at is not None and previous_at > updated_at:
            errors.append("updated is before the last checkpoint")
        if run_gate_at is not None and started_at is not None and run_gate_at < started_at:
            errors.append("run_gate.at is before started")

    columns, in_flight_rows = parse_table(body, "In-flight", errors)
    expected_flight = tables.get("in_flight")
    if columns and expected_flight and columns != expected_flight:
        errors.append("In-flight columns are %s, expected %s"
                      % (columns, expected_flight))
        in_flight_rows = []
    for index, cells in enumerate(in_flight_rows):
        if len(cells) != len(expected_flight):
            errors.append("In-flight row %d has %d cells, expected %d"
                          % (index + 2, len(cells), len(expected_flight)))
            continue
        row = dict(zip(expected_flight, cells))
        for key in ("intent", "key"):
            if not row[key].strip():
                errors.append("In-flight row %d has an empty %s" % (index + 2, key))
        if row["state"] not in schema.get("in_flight_states", []):
            errors.append("In-flight row %d state is not canonical: %s"
                          % (index + 2, row["state"]))
        if parse_timestamp(row["at"], patterns["timestamp"]) is None:
            errors.append("In-flight row %d at is not an ISO-8601 UTC timestamp"
                          % (index + 2))

    if status == "done":
        if units_total is not None and units_done != units_total:
            errors.append("status done requires every unit closed")
        completion_states = acceptance_spec.get("completion_states",
                                                ["verified", "unverified"])
        bad = [row.get("id") for row in acceptance
               if row.get("state") not in completion_states]
        if bad:
            errors.append("status done has unresolved acceptance: %s"
                          % ", ".join(str(item) for item in bad))
        unverified = [row.get("id") for row in acceptance
                      if row.get("state") == "unverified"]
        if not isinstance(run_gate, dict):
            errors.append("status done requires run_gate")
        if not isinstance(approval, dict):
            errors.append("status done requires push_approval")
        else:
            missing = [item for item in unverified if item not in approval_ids]
            if missing:
                errors.append("push_approval.ids does not cover unverified rows: %s"
                              % ", ".join(str(item) for item in missing))
    if status == "waiting":
        if units_total is not None and units_done != units_total:
            errors.append("status waiting requires every unit closed")
        bad = [row.get("id") for row in acceptance
               if row.get("state") in ("pending", "failed")]
        if bad:
            errors.append("status waiting has unresolved acceptance: %s"
                          % ", ".join(str(item) for item in bad))

    for section in section_list:
        matches = re.findall(r"(?m)^##\s+%s\b" % re.escape(section), body, re.I)
        if not matches:
            errors.append("missing section: ## %s" % section)
        elif len(matches) > 1:
            errors.append("duplicate section: ## %s" % section)

    for heading, columns in (("Units", tables["units"]),
                             ("Checkpoints", tables["checkpoints"]),
                             ("In-flight", tables.get("in_flight", []))):
        if not columns:
            continue
        header = "| " + " | ".join(columns) + " |"
        if body.count(header) > 1:
            errors.append("duplicate table header for %s" % heading)

    if status == "done":
        findings = section_text(body, "Open findings")
        for line in findings.splitlines():
            low = line.lower()
            if not (re.search(r"\b(high|medium)\b", low)
                    or re.search(r"\(\s*[hm]\s*[,)]", low)
                    or re.search(r"\|\s*(high|medium|h|m)\s*\|", low)
                    or re.search(r"\b[hm]\s*:\s*(?!none\b)(?:open|high|medium|[1-9])", low)):
                continue
            if re.match(r"^\s*(?:[-*]|\d+\.)?\s*no\s+(?:unresolved\s+)?(?:open\s+)?(?:high|medium)\b.*(?:finding|remain)", low):
                continue
            if re.match(r"^\s*(?:[-*]|\d+\.)?\s*none\.?\s*$", low):
                continue
            errors.append("status done has an open high/medium finding")
            break
        for row in in_flight_rows:
            if len(row) == len(expected_flight) and row[2] == "planned":
                errors.append("status done has a planned In-flight side effect")

    if lease and isinstance(lease, dict) and "expires" in lease:
        expires = parse_timestamp(iso_value(lease.get("expires")), patterns["timestamp"])
        if expires is not None and updated_at is not None and expires < updated_at:
            errors.append("lease is expired at updated")

    if phase == "Push" and not isinstance(approval, dict):
        errors.append("phase Push requires push_approval")

    progress_points = [row for row in checkpoints if row["kind"] == "progress"]
    progress_signatures = []
    previous_signature = None
    for row in checkpoints:
        if row["kind"] != "progress":
            continue
        count = progress_count(row)
        if count is None:
            errors.append("checkpoint %s progress is not '<done>/<total>'" % row["n"])
            continue
        signature = (count, row["artifact"])
        if signature != previous_signature:
            progress_signatures.append(row["at"])
        previous_signature = signature
    if progress_points:
        if progress_signatures:
            latest = progress_signatures[-1]
            if last_progress is not None and last_progress_at != latest:
                errors.append("last_progress_at is not the latest changed progress "
                              "checkpoint (%s)" % latest)
        latest_count = progress_count(progress_points[-1])
        if latest_count is not None:
            if latest_count[1] != units_total:
                errors.append("latest progress total is %d but units_total is %d"
                              % (latest_count[1], units_total))
            if latest_count[0] > units_done:
                errors.append("latest progress count %d exceeds units_done %d"
                              % (latest_count[0], units_done))
            if status == "done" and latest_count[0] != units_done:
                errors.append("status done requires progress at %d/%d, found %d/%d"
                              % (units_done, units_total, latest_count[0],
                                 latest_count[1]))
    elif checkpoint_base == 0:
        errors.append("a run with no archived checkpoints needs a progress checkpoint")

    if status == "active":
        if stall_window and len(progress_points) >= stall_window:
            tail = progress_points[-stall_window:]
            signatures = {progress_signature(row) for row in tail}
            if len(signatures) == 1:
                errors.append("stalled: the last %d progress checkpoints show "
                              "the same progress and artifact" % stall_window)
        if progress_max and updated_at is not None and last_progress is not None:
            minutes = (updated_at - last_progress).total_seconds() / 60.0
            if minutes > progress_max:
                errors.append("stalled: no progress for %.1f minutes (limit %d)"
                              % (minutes, progress_max))

    expected_line = format_status(front)
    if expected_line is not None:
        actual = operator_line(body)
        if actual is None:
            errors.append("missing Operator status line")
        elif not actual.startswith(expected_line):
            errors.append("Operator status line is stale")

    return {"ok": not errors, "path": str(path), "run_id": run_id,
            "units": len(units), "checkpoints": len(checkpoints),
            "errors": errors}


def status_line(path, schema_path=DEFAULT_SCHEMA):
    result = check(path, schema_path)
    if not result["ok"]:
        return "INVALID %s: %s" % (path, "; ".join(result["errors"]))
    front, _ = split_frontmatter(Path(path).read_text(encoding="utf-8"))
    return format_status(front)


def next_action(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("cannot read: %s" % exc)
    front, _ = split_frontmatter(text)
    if front is None:
        raise ValueError("missing YAML frontmatter")
    value = front.get("next_action", "")
    return value if str(value).strip() else "none"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    check_parser = sub.add_parser("check", help="validate a run state file")
    check_parser.add_argument("path")
    check_parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    check_parser.add_argument("--max-age-hours", type=float, default=None)
    check_parser.add_argument("--json", action="store_true")

    status_parser = sub.add_parser("status", help="print one status line")
    status_parser.add_argument("path")
    status_parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    status_parser.add_argument("--json", action="store_true")

    next_parser = sub.add_parser("next", help="print the next action")
    next_parser.add_argument("path")

    args = parser.parse_args(argv)
    if args.command == "check":
        result = check(args.path, args.schema, args.max_age_hours)
        if args.json:
            print(json.dumps(result, indent=2))
        elif result["ok"]:
            print("run-state: OK %s (%d units, %d checkpoints)"
                  % (result["run_id"], result["units"], result["checkpoints"]))
        else:
            for error in result["errors"]:
                print("FAIL %s: %s" % (result["path"], error))
            print("run-state: %d violation(s)" % len(result["errors"]))
        return 0 if result["ok"] else 1
    if args.command == "status":
        line = status_line(args.path, args.schema)
        if args.json:
            print(json.dumps({"status": line}, indent=2))
        else:
            print(line)
        return 0 if not line.startswith("INVALID") else 1
    try:
        print(next_action(args.path))
        return 0
    except ValueError as exc:
        print("FAIL %s: %s" % (args.path, exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
