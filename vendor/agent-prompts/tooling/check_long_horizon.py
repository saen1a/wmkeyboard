#!/usr/bin/env python3
"""Check that the long-horizon layer is complete and internally consistent.

Checks:
1. `standards/long-horizon-runs.md` exists and carries every rule heading
   LH-01..LH-14 plus the anchors the tooling and the orchestrator rely on.
2. `standards/run-state.schema.json` parses, its version matches the standard
   and CATALOG, and every required/optional frontmatter key, table column,
   enum value, checkpoint kind, status/phase pair, and section is documented.
3. Every evidence id cited by the standard exists in
   `standards/evidence/long-horizon-2026-10.md`.
4. The orchestrator names the long-horizon duties and its version is pinned.
5. `standards/workflow-loop.md` cross-references the long-horizon standard and
   states that it adds no phase.
6. The exemplar run state validates with `tooling/run_state.py`.
7. The knowledge-base synthesis links back to the standard and the register.
8. The required skill exists and carries the operational anchors.
9. The provenance ledger exists, matches the WL-08 header, and carries gate
   evidence.
10. The long-horizon exercise under `evals/long-horizon/` validates: its state
    view passes `run_state.py`, its journal passes the receipt and sequence
    rules, the last checkpoint hash matches the view, and the README keeps the
    proves / does-not-prove pair. Journal advisories are reported as warnings,
    the same state `check_run_journal.py` gives them, and never fail the gate.

Exit 0 when clean, 1 on any violation. ASCII-only output.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STANDARD = ROOT / "standards" / "long-horizon-runs.md"
SCHEMA = ROOT / "standards" / "run-state.schema.json"
EVIDENCE = ROOT / "standards" / "evidence" / "long-horizon-2026-10.md"
ORCHESTRATOR = ROOT / "agents" / "orchestration" / "orch-orchestrator.md"
WORKFLOW = ROOT / "standards" / "workflow-loop.md"
EXEMPLAR = ROOT / "exemplars" / "run-state-example.md"
KB = ROOT / "docs" / "knowledge-base" / "long-horizon-agents-2026-10.md"
SKILL = ROOT / "skills" / "general" / "long-horizon-run" / "SKILL.md"
CATALOG = ROOT / "CATALOG.md"
LEDGER = ROOT / "provenance" / "ledger-long-horizon-2026-10.md"
EXERCISE = ROOT / "evals" / "long-horizon"
EXERCISE_HEADINGS = ("## What this proves", "## What it does not prove")
RULE_IDS = ["LH-%02d" % number for number in range(1, 15)]
EXPECTED_STATUS = {"active", "waiting", "blocked", "done", "halted"}
EXPECTED_PHASES = {"Plan", "PlanReview", "Implement", "Review", "Fix", "Verify", "Push",
                   "Ready", "Ready (unverified)", "Done", "HALT"}
EXPECTED_GATES = {"pass", "fix", "hold", "halt"}
EXPECTED_CHECKPOINT_KINDS = {"progress", "cadence", "stop"}
EXPECTED_UNIT_KINDS = {"delivery", "report"}
EXPECTED_IN_FLIGHT = {"planned", "done", "failed"}
EXPECTED_HALT = {"blocked", "unsafe", "unresolvable", "over-bound", "budget",
                 "stalled", "drift", "operator-declined"}
EXPECTED_SECTIONS = {"Units", "Checkpoints", "Decisions", "Open findings",
                     "In-flight", "Operator"}
EXPECTED_RUN_GATE = {"command", "exit", "at", "evidence"}
EXPECTED_PUSH = {"operator", "at", "ids"}
EXPECTED_LEASE = {"resource", "owner", "expires"}
EXPECTED_ACCEPTANCE = {"id", "criterion", "state", "evidence"}
EXPECTED_BUDGET = {"tokens", "wall_clock_minutes", "tool_calls", "units"}
ANCHORS = [
    "run state",
    "checkpoint",
    "resume",
    "next_action",
    "budget",
    "stall",
    "acceptance",
    "operator",
    "events.jsonl",
    "append-only",
    "replay",
]
SKILL_ANCHORS = [
    "long-horizon-runs.md",
    "schema_version: 1.2.0",
    "checkpoint",
    "resume",
    "stall_window",
    "progress_max_minutes",
    "last_progress_at",
    "RUN <id> | <status> | units <done>/<total> | checkpoint <n> | tokens <used>/<limit> | next <action>",
    "Plan -> PlanReview -> Implement -> Review",
    "events.jsonl",
    "replay",
]


def read(path, violations):
    if not path.is_file():
        violations.append("missing required file: %s" % path.relative_to(ROOT).as_posix())
        return ""
    return path.read_text(encoding="utf-8")


def main():
    violations = []
    advisories = []
    standard = read(STANDARD, violations)
    for rule in RULE_IDS:
        if not re.search(r"(?m)^## %s -- " % re.escape(rule), standard):
            violations.append("standard missing rule heading: %s" % rule)
    lowered = standard.lower()
    for anchor in ANCHORS:
        if anchor.lower() not in lowered:
            violations.append("standard missing anchor: %s" % anchor)

    schema_text = read(SCHEMA, violations)
    try:
        schema = json.loads(schema_text)
    except ValueError as exc:
        violations.append("schema is not valid JSON: %s" % exc)
        schema = {}
    catalog = read(CATALOG, violations)
    if schema:
        for name, expected in (
                ("status", EXPECTED_STATUS), ("phase", EXPECTED_PHASES),
                ("gate", EXPECTED_GATES)):
            if set(schema.get("enums", {}).get(name, [])) != expected:
                violations.append("schema enum %s is not the pinned set" % name)
        if set(schema.get("checkpoint_kinds", [])) != EXPECTED_CHECKPOINT_KINDS:
            violations.append("schema checkpoint_kinds is not the pinned set")
        if set(schema.get("unit_kinds", [])) != EXPECTED_UNIT_KINDS:
            violations.append("schema unit_kinds is not the pinned set")
        if set(schema.get("in_flight_states", [])) != EXPECTED_IN_FLIGHT:
            violations.append("schema in_flight_states is not the pinned set")
        if set(schema.get("halt_reasons", [])) != EXPECTED_HALT:
            violations.append("schema halt_reasons is not the pinned set")
        if set(schema.get("sections", [])) != EXPECTED_SECTIONS:
            violations.append("schema sections is not the pinned set")
        if set(schema.get("acceptance", {}).get("completion_states", [])) != {
                "verified", "unverified"}:
            violations.append("schema completion_states is not the pinned set")
        if schema.get("defaults") != {"stall_window": 3, "checkpoint_base": 0}:
            violations.append("schema defaults is not the pinned set")
        for block, expected in (
                ("run_gate", EXPECTED_RUN_GATE),
                ("push_approval", EXPECTED_PUSH),
                ("lease", EXPECTED_LEASE),
                ("acceptance", EXPECTED_ACCEPTANCE),
                ("budget", EXPECTED_BUDGET)):
            actual = set(schema.get(block, {}).get("required", []))
            if actual != expected:
                violations.append("schema %s.required is not the pinned set" % block)
        version = str(schema.get("version", ""))
        if not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+$", version):
            violations.append("schema version is invalid: %r" % version)
        if version and version not in standard:
            violations.append("standard does not pin schema version %s" % version)
        if version and ("Long-horizon: %s" % version) not in catalog:
            violations.append("CATALOG.md: missing 'Long-horizon: %s' pin" % version)

        frontmatter = schema.get("frontmatter", {})
        schema_keys = set(frontmatter.get("required", []) + frontmatter.get("optional", []))
        for key in schema_keys:
            if not re.search(r"(?m)^\| `%s` \|" % re.escape(key), standard):
                violations.append("schema key %s has no field-table row in the standard"
                                  % key)
        for key in re.findall(r"(?m)^\| `([a-z_]+)` \|", standard):
            if key not in schema_keys:
                violations.append("standard documents a field not in the schema: %s" % key)
        normalized = " ".join(standard.split())
        prefixes = {
            "units": "`## Units` -- one row per unit: `",
            "checkpoints": "`## Checkpoints` -- one row per checkpoint: `",
            "in_flight": "`## In-flight` -- side effects in progress: `",
        }
        for table, columns in schema.get("tables", {}).items():
            line = " | ".join(columns)
            prefix = prefixes.get(table)
            if prefix and (prefix + line + "`") not in normalized:
                violations.append("schema %s columns are not documented in its "
                                  "normative sentence: %s" % (table, line))
            elif not prefix and line not in normalized:
                violations.append("schema %s columns are not documented: %s"
                                  % (table, line))
        for name, values in schema.get("enums", {}).items():
            for value in values:
                if ("`%s`" % value) not in standard:
                    violations.append("schema enum %s=%r is not documented"
                                      % (name, value))
        for measure in schema.get("budget", {}).get("required", []):
            if ("`%s`" % measure) not in standard:
                violations.append("schema budget measure %s is not documented" % measure)
        for field in schema.get("budget", {}).get("measure_required", []):
            if ("`%s`" % field) not in standard:
                violations.append("schema budget field %s is not documented" % field)
        for key in schema.get("acceptance", {}).get("required", []):
            if ("`%s`" % key) not in standard:
                violations.append("schema acceptance key %s is not documented" % key)
        for kind in schema.get("checkpoint_kinds", []):
            if ("`%s`" % kind) not in standard:
                violations.append("checkpoint kind %s is not documented" % kind)
        for kind in schema.get("unit_kinds", []):
            if ("`%s`" % kind) not in standard:
                violations.append("unit kind %s is not documented" % kind)
        for reason in schema.get("halt_reasons", []):
            if ("`%s`" % reason) not in standard:
                violations.append("halt reason %s is not documented" % reason)
        for block, keys in (("push_approval", schema.get("push_approval", {})),
                            ("lease", schema.get("lease", {})),
                            ("run_gate", schema.get("run_gate", {}))):
            for key in keys.get("required", []) + keys.get("optional", []):
                if ("`%s`" % key) not in standard:
                    violations.append("%s key %s is not documented" % (block, key))
        for state in schema.get("acceptance", {}).get("completion_states", []):
            if ("`%s`" % state) not in standard:
                violations.append("completion state %s is not documented" % state)
        for state in schema.get("in_flight_states", []):
            if ("`%s`" % state) not in standard:
                violations.append("in-flight state %s is not documented" % state)
        for section in schema.get("sections", []):
            if not re.search(r"(?m)^## %s\s*$" % re.escape(section), standard):
                violations.append("schema section %s has no heading" % section)
        for status, phases in schema.get("status_phase", {}).items():
            if ("`%s`" % status) not in standard:
                violations.append("status_phase status %s is not documented" % status)
            for phase in phases:
                if ("`%s`" % phase) not in standard:
                    violations.append("status_phase value %s is not documented" % phase)

    evidence = read(EVIDENCE, violations)
    cited = sorted(set(re.findall(r"\bL(\d{1,2})\b", standard)), key=int)
    if not cited:
        violations.append("standard cites no evidence id")
    for number in cited:
        if not re.search(r"(?m)^\| L%s \|" % number, evidence):
            violations.append("evidence L%s is cited but missing from the register"
                              % number)

    orchestrator = read(ORCHESTRATOR, violations)
    for needle in ("LH-01", "long-horizon", "run state", "checkpoint", "resume"):
        if needle.lower() not in orchestrator.lower():
            violations.append("orchestrator missing long-horizon duty: %s" % needle)
    version_match = re.search(r"(?m)^version:\s*(\S+)\s*$", orchestrator)
    if not version_match:
        violations.append("orchestrator has no version")
    else:
        pin = "Orchestrator template: %s" % version_match.group(1)
        if pin not in catalog:
            violations.append("CATALOG.md: missing %r" % pin)

    workflow = read(WORKFLOW, violations)
    if "long-horizon-runs.md" not in workflow:
        violations.append("workflow-loop standard does not cross-reference long-horizon-runs.md")
    if not re.search(r"(?i)does not add a phase", workflow):
        violations.append("workflow-loop standard must state that the long-horizon "
                          "layer adds no phase")

    exemplar = read(EXEMPLAR, violations)
    if exemplar:
        sys.path.insert(0, str(ROOT / "tooling"))
        try:
            import run_state
        except ImportError as exc:
            violations.append("cannot import run_state: %s" % exc)
        else:
            result = run_state.check(EXEMPLAR)
            for error in result["errors"]:
                violations.append("exemplar: %s" % error)

    kb = read(KB, violations)
    for needle in ("standards/long-horizon-runs.md",
                   "evidence/long-horizon-2026-10.md"):
        if needle not in kb:
            violations.append("knowledge-base note does not link %s" % needle)

    exercise_readme = read(EXERCISE / "README.md", violations)
    for heading in EXERCISE_HEADINGS:
        if exercise_readme and heading not in exercise_readme:
            violations.append("exercise README missing heading: %s" % heading)
    exercise_state = EXERCISE / "run-state.md"
    exercise_journal = EXERCISE / "events.jsonl"
    if exercise_state.is_file():
        sys.path.insert(0, str(ROOT / "tooling"))
        try:
            import run_state
        except ImportError as exc:
            violations.append("cannot import run_state: %s" % exc)
        else:
            result = run_state.check(exercise_state)
            for error in result["errors"]:
                violations.append("exercise: %s" % error)
    else:
        violations.append("missing exercise run state: %s"
                          % exercise_state.relative_to(ROOT).as_posix())
    if exercise_journal.is_file():
        sys.path.insert(0, str(ROOT / "tooling"))
        try:
            import check_run_journal
        except ImportError as exc:
            violations.append("cannot import check_run_journal: %s" % exc)
        else:
            events, errors = check_run_journal.check(
                exercise_journal,
                str(exercise_state) if exercise_state.is_file() else None)
            for error in errors:
                violations.append("exercise journal: %s" % error)
            if events:
                # Advisories are what check_run_journal.py reports as WARN: a
                # condition worth surfacing that is not a rule violation. They
                # stay warnings here too, so the two tools agree.
                for warning in check_run_journal.advisories(events):
                    advisories.append("exercise journal: %s" % warning)
    else:
        violations.append("missing exercise journal: %s"
                          % exercise_journal.relative_to(ROOT).as_posix())

    if SKILL.is_file():
        skill = SKILL.read_text(encoding="utf-8")
        for needle in SKILL_ANCHORS:
            if needle not in skill:
                violations.append("skill missing anchor: %s" % needle)
    else:
        violations.append("missing required skill: %s" % SKILL.relative_to(ROOT).as_posix())

    ledger = read(LEDGER, violations)
    if ledger:
        header = next((line for line in ledger.splitlines()
                       if line.startswith("| unit_id |")), "")
        columns = [cell.strip() for cell in header.strip().strip("|").split("|")]
        expected = ["unit_id", "phase", "attempt", "gate", "status", "artifact",
                    "findings", "evidence", "decision", "owner", "timestamp", "next"]
        if columns != expected:
            violations.append("long-horizon ledger header does not match WL-08")
        sys.path.insert(0, str(ROOT / "tooling"))
        try:
            import check_workflow_loop as loop
        except ImportError as exc:
            violations.append("cannot import check_workflow_loop: %s" % exc)
            loop = None
        rows = []
        for line in ledger.splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if line.startswith("|") and cells and cells[0] not in ("unit_id", "---"):
                rows.append(line)
        if not rows:
            violations.append("long-horizon ledger has no unit row")
        if not any(row.startswith("| long-horizon |") for row in rows):
            violations.append("long-horizon ledger has no long-horizon row")
        unit_ids = []
        for row in rows:
            cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
            if cells:
                unit_ids.append(cells[0])
        duplicates = sorted({item for item in unit_ids if unit_ids.count(item) > 1})
        if duplicates:
            violations.append("long-horizon ledger duplicate unit ids: %s"
                              % ", ".join(duplicates))
        for row in rows:
            cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
            if len(cells) != len(expected):
                violations.append("long-horizon ledger row has %d cells, expected %d"
                                  % (len(cells), len(expected)))
                continue
            record = dict(zip(expected, cells))
            if record["gate"] not in ("pass", "fix", "hold", "halt"):
                violations.append("long-horizon ledger gate is not canonical")
            if record["status"] not in ("Plan", "PlanReview", "Implement", "Review",
                                        "Fix", "Verify", "Push", "Ready",
                                        "Ready (unverified)", "Done", "HALT"):
                violations.append("long-horizon ledger status is not canonical")
            if not record["evidence"].strip():
                violations.append("long-horizon ledger row has no evidence")
            if "make gate exit 0" not in record["evidence"]:
                violations.append("long-horizon ledger evidence lacks make gate exit 0")
            if "pytest" not in record["evidence"]:
                violations.append("long-horizon ledger evidence lacks the pytest result")
            if loop is not None:
                for error in loop.validate_ledger_row(record):
                    violations.append("long-horizon ledger: %s" % error)

    if violations:
        for violation in violations:
            print("FAIL " + violation)
        print("long-horizon: %d violation(s)" % len(violations))
        return 1
    for advisory in advisories:
        print("WARN " + advisory)
    exemplar_count = len(list((ROOT / "exemplars").glob("run-state-*.md")))
    print("long-horizon: %d rules, %d evidence ids, %d exemplar, exercise ok, "
          "0 violations, %d warning(s)"
          % (len(RULE_IDS), len(cited), exemplar_count, len(advisories)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
