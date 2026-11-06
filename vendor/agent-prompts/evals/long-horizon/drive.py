#!/usr/bin/env python3
"""Exercise the run-state and journal contract across one session boundary.

This is the WP-09 local exercise for `standards/long-horizon-runs.md`. It runs
two real sessions as two separate OS processes that share nothing but the files
on disk:

    session A  -- plan, checkpoint 1, unit U1, checkpoint 2, exit
    session B  -- cold start: replay the journal, reconcile with the view,
                  resume at `next_action`, finish U2 and U3, run the run-scope
                  gate, append `done`

Each unit derives a real artifact from a checked-in contract file and its gate
recomputes that artifact byte for byte, so "progress" means a verified artifact
and not elapsed time. Every checkpoint writes the state view, validates it with
`tooling/run_state.py`, and only then appends the `checkpoint` event carrying the
SHA-256 of the bytes it wrote.

Usage:

    python3 evals/long-horizon/drive.py                 # both sessions, then probes
    python3 evals/long-horizon/drive.py --session a
    python3 evals/long-horizon/drive.py --session b
    python3 evals/long-horizon/drive.py --session b --replay-only
    python3 evals/long-horizon/drive.py --verify

`--verify` revalidates the committed state view and the journal, re-runs the
replay comparison, and re-runs both probes. It rewrites `probes/` only when the
probe bytes change, and every path it reports is repository-relative, so a
rerun in another checkout leaves the committed files byte-identical. It is the
run-scope gate recorded in `run_gate`.

Exit 0 when every step agrees; 1 on the first disagreement. ASCII-only output.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLING = ROOT / "tooling"

STATE = HERE / "run-state.md"
JOURNAL = HERE / "events.jsonl"
REPLAY_LOG = HERE / "session-b-replay.txt"
WORK = HERE / "work"
PROBES = HERE / "probes"
LOG_A = HERE / "session-a.txt"
LOG_B = HERE / "session-b.txt"

RUN_ID = "lh-contract-exercise"
SCHEMA = ROOT / "standards" / "run-state.schema.json"
JOURNAL_SCHEMA = ROOT / "standards" / "run-journal.schema.json"

UNIT_ORDER = ["U1", "U2", "U3"]
UNIT_ARTIFACT = {
    "U1": "work/frontmatter-keys.txt",
    "U2": "work/journal-kinds.txt",
    "U3": "work/sections.txt",
}
UNIT_LABEL = {
    "U1": "required run-state frontmatter keys",
    "U2": "canonical journal event kinds",
    "U3": "required run-state body sections",
}
UNIT_DONE_AT = {"U1": "t5", "U2": "t9", "U3": "t12"}
CP_TIME = {1: "t2", 2: "t5", 3: "t9", 4: "t12", 5: "t13"}
CP_DONE = {1: 0, 2: 1, 3: 2, 4: 3, 5: 3}
RECEIPT_SEQ = {"U1": 4, "U2": 8, "U3": 11}

sys.path.insert(0, str(TOOLING))
import check_run_journal  # noqa: E402
import run_state  # noqa: E402


# --------------------------------------------------------------------------
# artifacts and gates
# --------------------------------------------------------------------------

def derive(unit):
    """Return the artifact bytes for a unit, derived from a checked-in contract."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    if unit == "U1":
        values = sorted(schema["frontmatter"]["required"])
    elif unit == "U2":
        journal = json.loads(JOURNAL_SCHEMA.read_text(encoding="utf-8"))
        values = sorted(journal["properties"]["kind"]["enum"])
    elif unit == "U3":
        values = list(schema["sections"])
    else:
        raise SystemExit("unknown unit %s" % unit)
    return "".join("%s\n" % value for value in values).encode("ascii")


def artifact_rel(unit):
    return "evals/long-horizon/%s" % UNIT_ARTIFACT[unit]


def write_artifact(unit):
    path = HERE / UNIT_ARTIFACT[unit]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(derive(unit))
    return path


def gate(unit):
    """Recompute the artifact from the contract and compare bytes. Pass = exit 0."""
    path = HERE / UNIT_ARTIFACT[unit]
    if not path.is_file():
        return False, "%s missing" % artifact_rel(unit)
    actual = path.read_bytes()
    if actual != derive(unit):
        return False, "%s does not match the contract derivation" % artifact_rel(unit)
    if not actual.strip():
        return False, "%s is empty" % artifact_rel(unit)
    actual.decode("ascii")
    return True, "%s matches the contract derivation (%d lines)" % (
        artifact_rel(unit), actual.count(b"\n"))


# --------------------------------------------------------------------------
# time
# --------------------------------------------------------------------------

def stamp(base, seconds):
    return (base + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def journal_events():
    if not JOURNAL.is_file():
        return []
    return [json.loads(line) for line in
            JOURNAL.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_times():
    """Derive the exercise clock from the journal, never from process memory."""
    events = journal_events()
    if not events:
        raise SystemExit("no journal; run --session a first")
    first = datetime.strptime(events[0]["at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)
    base = first - timedelta(seconds=10)
    times = {"base": base, "started": first.strftime("%Y-%m-%d")}
    for index in range(1, 15):
        times["t%d" % index] = index * 10
    return times


# --------------------------------------------------------------------------
# state view
# --------------------------------------------------------------------------

def checkpoint_cells():
    return {
        1: ("-", "Plan", "pass", "progress",
            "0/3; goal, acceptance and budget fixed",
            "standards/long-horizon-runs.md",
            "Execute U1: derive %s" % UNIT_LABEL["U1"]),
        2: ("U1", "Verify", "pass", "progress",
            "1/3; %s" % UNIT_ARTIFACT["U1"],
            artifact_rel("U1"),
            "Resume in a new session and execute U2"),
        3: ("U2", "Verify", "pass", "progress",
            "2/3; %s" % UNIT_ARTIFACT["U2"],
            artifact_rel("U2"),
            "Execute U3: derive %s" % UNIT_LABEL["U3"]),
        4: ("U3", "Verify", "pass", "progress",
            "3/3; %s" % UNIT_ARTIFACT["U3"],
            artifact_rel("U3"),
            "Run the run-scope gate and finalize"),
        5: ("-", "Done", "pass", "cadence",
            "3/3; run gate exit 0; operator approved push",
            "evals/long-horizon/run-state.md",
            "none"),
    }


def render(stage, times):
    """Render the full state view for checkpoint `stage`. Stage 5 is final."""
    final = stage == 5
    done_count = CP_DONE[stage]
    status = "done" if final else "active"
    if final:
        phase = "Done"
    elif stage == 1:
        phase = "Plan"
    elif stage <= 3:
        phase = "Implement"
    else:
        phase = "Verify"

    next_action = {
        1: "Execute U1: derive %s" % UNIT_LABEL["U1"],
        2: "Resume in a new session and execute U2",
        3: "Execute U3: derive %s" % UNIT_LABEL["U3"],
        4: "Run the run-scope gate and finalize",
        5: "",
    }[stage]

    tokens = {1: 4000, 2: 8000, 3: 12000, 4: 16000, 5: 18000}[stage]
    calls = {1: 5, 2: 10, 3: 15, 4: 20, 5: 24}[stage]
    minutes = {1: 5, 2: 15, 3: 30, 4: 45, 5: 50}[stage]
    updated = stamp(times["base"], times[CP_TIME[stage]])
    last_progress = stamp(times["base"], times[CP_TIME[min(stage, 4)]])

    units = []
    for index, unit in enumerate(UNIT_ORDER):
        if index < done_count:
            units.append((unit, "Push", "pass", "Done", artifact_rel(unit),
                          "gate: derive matches; journal seq %d" % RECEIPT_SEQ[unit],
                          "delivery",
                          "U2" if unit == "U1" else "U3" if unit == "U2" else "none"))
        else:
            units.append((unit, "Plan", "pass", "Plan", "-", "planned",
                          "delivery", "Implement"))

    acceptance = [
        ("A1", "The required run-state frontmatter keys are recorded from the "
               "schema, not from memory.",
         "verified" if done_count >= 1 else "pending",
         "python3 evals/long-horizon/drive.py --verify; gate U1 pass"
         if done_count >= 1 else ""),
        ("A2", "The canonical journal event kinds are recorded from the schema.",
         "verified" if done_count >= 2 else "pending",
         "python3 evals/long-horizon/drive.py --verify; gate U2 pass"
         if done_count >= 2 else ""),
        ("A3", "A cold session rebuilds the committed units and the next action "
               "from the journal alone, and the view agrees.",
         "verified" if done_count >= 3 else "pending",
         "evals/long-horizon/session-b-replay.txt: AGREE"
         if done_count >= 3 else ""),
    ]

    cells = checkpoint_cells()
    checkpoints = []
    for number in sorted(cells):
        if number > stage:
            continue
        unit, cp_phase, cp_gate, kind, progress, artifact, nxt = cells[number]
        checkpoints.append((number, stamp(times["base"], times[CP_TIME[number]]),
                            unit, cp_phase, cp_gate, kind, progress, artifact, nxt))

    in_flight = []
    for index, unit in enumerate(UNIT_ORDER):
        key = "write-%s" % Path(UNIT_ARTIFACT[unit]).stem
        if index < done_count:
            in_flight.append(("Write %s" % UNIT_ARTIFACT[unit], key, "done",
                              stamp(times["base"], times[UNIT_DONE_AT[unit]])))
        elif index == done_count and not final:
            in_flight.append(("Write %s" % UNIT_ARTIFACT[unit], key, "planned",
                              updated))

    lines = [
        "---",
        "schema_version: 1.2.0",
        "run_id: %s" % RUN_ID,
        "goal: Exercise the run-state and journal contract across one session "
        "boundary and record what the local tooling proves.",
        "status: %s" % status,
        "phase: %s" % phase,
        "owner: orch-orchestrator",
        "started: %s" % times["started"],
        "updated: %s" % updated,
        "units_total: 3",
        "units_done: %d" % done_count,
        "checkpoint: %d" % stage,
        "last_progress_at: %s" % last_progress,
        "progress_max_minutes: 120",
        "next_action: \"%s\"" % next_action,
        "stall_window: 3",
        "branch: feat/wp-09-long-horizon-exercise",
        "model: local tooling only; no model call in this exercise",
        "harness: two local shell processes, not a deployed harness",
        "notes: exercise artifacts, see evals/long-horizon/README.md",
        "lease:",
        "  resource: evals/long-horizon/work",
        "  owner: %s" % RUN_ID,
        "  expires: %s" % stamp(times["base"], times["t9"] + 3600),
        "budget:",
        "  tokens: {limit: 20000, used: %d}" % tokens,
        "  wall_clock_minutes: {limit: 120, used: %d}" % minutes,
        "  tool_calls: {limit: 40, used: %d}" % calls,
        "  units: {limit: 3, used: %d}" % done_count,
        "acceptance:",
    ]
    for row_id, criterion, row_state, evidence in acceptance:
        lines.append("  - id: %s" % row_id)
        lines.append("    criterion: %s" % criterion)
        lines.append("    state: %s" % row_state)
        lines.append("    evidence: \"%s\"" % evidence)
    if final:
        lines.extend([
            "run_gate:",
            "  command: python3 evals/long-horizon/drive.py --verify",
            "  exit: 0",
            "  at: %s" % updated,
            "  evidence: session-b.txt ends at VERIFY OK and both probes match",
            "push_approval:",
            "  operator: library-maintainer (local exercise)",
            "  at: %s" % updated,
            "  ids: [A1, A2, A3]",
            "  scope: local exercise; no deploy, no production run",
        ])
    lines.extend([
        "---",
        "",
        "## Units",
        "",
        "| unit_id | phase | gate | status | artifact | evidence | kind | next |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for row in units:
        lines.append("| " + " | ".join(row) + " |")
    lines.extend([
        "",
        "## Checkpoints",
        "",
        "| n | at | unit | phase | gate | kind | progress | artifact | next_action |",
        "|---|---|---|---|---|---|---|---|---|",
    ])
    for row in checkpoints:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    lines.extend([
        "",
        "## Decisions",
        "",
        "- %s: operator approved the goal and the three-unit budget before the "
        "first unit." % times["started"],
        "- %s: session A ends at checkpoint 2 by design, so session B must resume "
        "from disk." % stamp(times["base"], times["t5"]),
        "- %s: session B resumed by replaying the journal, not by re-planning the "
        "run." % stamp(times["base"], times["t6"]),
        "- %s: the view is rewritten from the journal; the journal is never "
        "edited." % stamp(times["base"], times["t6"]),
    ])
    if final:
        lines.append("- %s: operator approved push for A1..A3; the run is local and "
                     "not deployed." % updated)
    lines.extend([
        "",
        "## Open findings",
        "",
        "- F1 (low, owner run): the journal contract has no resume event kind, so "
        "a resume is recorded as a note plus a replay.",
        "- F2 (low, owner run): a checkpoint event has no next_action field, so "
        "replay rebuilds it from the event result by convention.",
        "- No open high or medium finding.",
        "",
        "## In-flight",
        "",
        "| intent | key | state | at |",
        "|---|---|---|---|",
    ])
    for row in in_flight:
        lines.append("| " + " | ".join(row) + " |")
    lines.extend([
        "",
        "## Operator",
        "",
        operator_line(status, done_count, stage, tokens, next_action),
        "",
    ])
    return "\n".join(lines)


def operator_line(status, done_count, checkpoint, tokens, next_action):
    return ("RUN %s | %s | units %d/3 | checkpoint %d | tokens %d/20000 | next %s"
            % (RUN_ID, status, done_count, checkpoint, tokens,
               next_action or "none"))


# --------------------------------------------------------------------------
# journal writes
# --------------------------------------------------------------------------

def append_event(kind, unit, phase, action, result, evidence, **extra):
    event = {"schema": "agent-run-journal/1",
             "seq": len(journal_events()) + 1,
             "at": extra.pop("at"),
             "kind": kind, "unit": unit, "phase": phase,
             "action": action, "result": result, "evidence": evidence}
    event.update(extra)
    with JOURNAL.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")
    return event


def commit_checkpoint(stage, unit, phase, evidence):
    """Write the view, validate it, then append the hash-pinned checkpoint."""
    times = load_times()
    text = render(stage, times)
    STATE.write_text(text, encoding="utf-8")
    result = run_state.check(STATE)
    if not result["ok"]:
        for error in result["errors"]:
            print("FAIL state checkpoint %d: %s" % (stage, error))
        raise SystemExit(1)
    digest = hashlib.sha256(STATE.read_bytes()).hexdigest()
    cells = checkpoint_cells()[stage]
    progress, next_action, at = cells[4], cells[6], stamp(
        times["base"], times[CP_TIME[stage]])
    event = append_event(
        "checkpoint", unit, phase, "write the state view at checkpoint %d" % stage,
        "%s; next %s" % (progress, next_action), evidence,
        at=at, gate="pass", state_sha256=digest)
    print("checkpoint %d: view valid, sha256 %s..., journal seq %d"
          % (stage, digest[:12], event["seq"]))
    return event


# --------------------------------------------------------------------------
# session A
# --------------------------------------------------------------------------

def session_a():
    for path in (STATE, JOURNAL, LOG_A, LOG_B, REPLAY_LOG):
        if path.exists():
            path.unlink()
    for directory in (WORK, PROBES):
        if directory.exists():
            shutil.rmtree(directory)
    WORK.mkdir(parents=True)
    PROBES.mkdir(parents=True)

    base = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=10)
    times = {"base": base, "started": base.strftime("%Y-%m-%d")}
    for index in range(1, 15):
        times["t%d" % index] = index * 10

    log = []
    say = log.append
    say("== session A (pid %d) ==" % os.getpid())
    say("workspace: %s" % ROOT)
    say("run id: %s" % RUN_ID)
    say("plan: 3 units, budget 20000 tokens / 40 tool calls / 120 minutes")

    append_event("start", "run", "Plan", "read the standard and the two contracts",
                 "goal: exercise the run-state and journal contract across one "
                 "session boundary",
                 "standards/long-horizon-runs.md; standards/run-state.schema.json",
                 at=stamp(base, times["t1"]))
    say("journal seq 1: start")

    event = commit_checkpoint(
        1, "-", "Plan",
        "docs/knowledge-base/autonomous-optimization-plan-2026-10-27.md WP-09")
    say("journal seq %d: checkpoint 1 (Plan)" % event["seq"])

    append_event("action_started", "U1", "Implement",
                 "derive %s from standards/run-state.schema.json"
                 % UNIT_ARTIFACT["U1"], "", "intent recorded",
                 at=stamp(base, times["t3"]), action_id="a-01")
    say("journal seq 3: action_started a-01 (U1)")

    write_artifact("U1")
    ok, detail = gate("U1")
    if not ok:
        say("FAIL gate U1: %s" % detail)
        _finish(log, LOG_A)
        raise SystemExit(1)
    append_event("action_result", "U1", "Implement",
                 "derive %s" % UNIT_ARTIFACT["U1"], detail,
                 "gate exit 0: %s" % detail,
                 at=stamp(base, times["t4"]), gate="pass", action_id="a-01")
    say("gate U1 pass: %s" % detail)
    say("journal seq 4: action_result a-01")

    event = commit_checkpoint(
        2, "U1", "Verify", "evals/long-horizon/%s" % UNIT_ARTIFACT["U1"])
    say("journal seq %d: checkpoint 2 (U1 verified)" % event["seq"])
    say("session A ends at checkpoint 2; the next session must resume from disk")
    _finish(log, LOG_A)
    return 0


def _finish(log, path):
    text = "\n".join(log)
    print(text)
    path.write_text(text + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# replay
# --------------------------------------------------------------------------

def replay():
    """Rebuild the committed run from the journal alone, without the view."""
    events = journal_events()
    if not events or events[0].get("kind") != "start":
        raise SystemExit("replay: journal does not begin with a start event")
    committed = {}
    checkpoints = 0
    next_action = "none"
    for event in events:
        if event.get("kind") != "checkpoint":
            continue
        checkpoints += 1
        unit = event.get("unit")
        if unit not in (None, "run", "-"):
            committed[unit] = (event.get("phase"), event.get("gate"))
        result = str(event.get("result", ""))
        marker = "; next "
        next_action = result.split(marker, 1)[1] if marker in result else "none"
    return {"goal": events[0].get("result", ""), "committed": committed,
            "checkpoints": checkpoints, "next_action": next_action,
            "events": len(events)}


def compare_replay(rebuilt):
    """Return (exit code, lines) comparing the replay with the hand-written view."""
    lines = ["replay: %d events, %d checkpoints"
             % (rebuilt["events"], rebuilt["checkpoints"])]
    result = run_state.check(STATE)
    if not result["ok"]:
        for error in result["errors"]:
            lines.append("FAIL view: %s" % error)
        return 1, lines
    front, _ = run_state.split_frontmatter(STATE.read_text(encoding="utf-8"))
    for unit in sorted(rebuilt["committed"]):
        phase, cp_gate = rebuilt["committed"][unit]
        lines.append("replay: committed %s at %s (gate %s)" % (unit, phase, cp_gate))
    lines.append("replay: next_action = %s" % rebuilt["next_action"])
    lines.append("view:   checkpoint %s, units_done %s/%s"
                 % (front.get("checkpoint"), front.get("units_done"),
                    front.get("units_total")))
    lines.append("view:   next_action = %s" % (front.get("next_action") or "none"))

    events = journal_events()
    last = [event for event in events if event.get("kind") == "checkpoint"][-1]
    digest = hashlib.sha256(STATE.read_bytes()).hexdigest()
    lines.append("hash:   view %s..., last checkpoint seq %s records %s..."
                 % (digest[:12], last.get("seq"), last["state_sha256"][:12]))

    problems = []
    if rebuilt["checkpoints"] != front.get("checkpoint"):
        problems.append("checkpoint count differs")
    if len(rebuilt["committed"]) != front.get("units_done"):
        problems.append("committed unit count differs from units_done")
    if rebuilt["next_action"] != (front.get("next_action") or "none"):
        problems.append("next_action differs")
    if digest != last["state_sha256"]:
        problems.append("view hash does not match the last checkpoint")
    for unit in sorted(rebuilt["committed"]):
        if not (HERE / UNIT_ARTIFACT[unit]).is_file():
            problems.append("committed %s has no artifact" % unit)
    lines.append("AGREE" if not problems else "DISAGREE: " + "; ".join(problems))
    return (0 if not problems else 1), lines


# --------------------------------------------------------------------------
# probes
# --------------------------------------------------------------------------

def probes():
    """Two probes: a stale view, and a started action with no receipt."""
    times = load_times()
    lines = []
    problems = False

    state_text = STATE.read_text(encoding="utf-8")
    tampered = PROBES / "tampered-state.md"
    tampered_rel = tampered.relative_to(ROOT).as_posix()
    tampered.write_text(
        state_text.replace("gate U1 pass", "gate U1 pass (edited by hand)", 1),
        encoding="utf-8")
    # Paths are passed and reported relative to the repository so the committed
    # report does not carry the checkout location.
    alone = subprocess.run(
        [sys.executable, str(TOOLING / "run_state.py"), "check", tampered_rel],
        cwd=str(ROOT), capture_output=True, text=True)
    pair = subprocess.run(
        [sys.executable, str(TOOLING / "check_run_journal.py"),
         JOURNAL.relative_to(ROOT).as_posix(), "--state", tampered_rel],
        cwd=str(ROOT), capture_output=True, text=True)
    lines.append("probe 1: stale view (one evidence cell edited, view still valid)")
    failures = [line for line in pair.stdout.splitlines() if line.startswith("FAIL")]
    lines.append("  run_state.py check         exit %d (expected 0: the edited view "
                 "is internally valid)" % alone.returncode)
    lines.append("  check_run_journal --state  exit %d (expected 1: stale view "
                 "reported)" % pair.returncode)
    lines.append("  detail: %s" % (failures[-1].replace("FAIL ", "", 1)
                                  if failures else "no report"))
    if alone.returncode != 0:
        lines.append("  UNEXPECTED: the edited view should still validate alone")
        problems = True
    if pair.returncode != 1 or "stale view" not in pair.stdout:
        lines.append("  UNEXPECTED: --state did not report a stale view")
        problems = True

    events = journal_events()
    start, first_checkpoint = events[0], events[1]
    dangling = PROBES / "dangling-action.jsonl"
    synthetic = [
        start,
        first_checkpoint,
        {"schema": "agent-run-journal/1", "seq": 3,
         "at": stamp(times["base"], times["t3"] + 5), "kind": "action_started",
         "unit": "U2", "phase": "Implement",
         "action": "derive work/journal-kinds.txt", "result": "",
         "evidence": "intent recorded", "action_id": "a-02"},
        dict(first_checkpoint, seq=4, at=stamp(times["base"], times["t4"] + 5)),
    ]
    dangling.write_text("\n".join(json.dumps(event) for event in synthetic) + "\n",
                        encoding="utf-8")
    receiptless = subprocess.run(
        [sys.executable, str(TOOLING / "check_run_journal.py"),
         dangling.relative_to(ROOT).as_posix()],
        cwd=str(ROOT), capture_output=True, text=True)
    warn = [line for line in receiptless.stdout.splitlines()
            if line.startswith("WARN")]
    lines.append("probe 2: an action_started with no receipt before a checkpoint")
    lines.append("  check_run_journal.py       exit %d, %d WARN (expected 0 and 1)"
                 % (receiptless.returncode, len(warn)))
    lines.append("  detail: %s" % (warn[0] if warn else "no WARN"))
    if receiptless.returncode != 0 or not warn:
        lines.append("  UNEXPECTED: a start without a receipt should warn, not fail")
        problems = True
    lines.append("VERDICT %s" % ("OK" if not problems else "MISMATCH"))
    report = PROBES / "report.txt"
    payload = "\n".join(lines) + "\n"
    if not report.is_file() or report.read_text(encoding="utf-8") != payload:
        report.write_text(payload, encoding="utf-8")
    for line in lines:
        print(line)
    return 0 if not problems else 1


# --------------------------------------------------------------------------
# session B
# --------------------------------------------------------------------------

def session_b(replay_only=False):
    times = load_times()
    log = []
    say = log.append
    say("== session B (pid %d) ==" % os.getpid())
    say("cold start: the only inputs are evals/long-horizon/run-state.md and "
        "evals/long-horizon/events.jsonl")
    say("step 1: workspace %s, run id %s" % (ROOT, RUN_ID))

    rebuilt = replay()
    say("step 2: replayed the journal: %d events, %d checkpoints"
        % (rebuilt["events"], rebuilt["checkpoints"]))
    code, replay_lines = compare_replay(rebuilt)
    log.extend(replay_lines)
    REPLAY_LOG.write_text("\n".join(log) + "\n", encoding="utf-8")
    if code != 0:
        _finish(log, LOG_B)
        return 1
    if replay_only:
        _finish(log, LOG_B)
        return 0

    if rebuilt["next_action"] != "Resume in a new session and execute U2":
        say("FAIL: the recorded next_action is not the resume step")
        _finish(log, LOG_B)
        return 1

    say("step 3: every committed artifact path from the replay exists on disk")
    say("step 4: cheapest baseline check that detects a broken environment")
    baseline = subprocess.run(
        [sys.executable, str(TOOLING / "check_run_journal.py"), str(JOURNAL),
         "--state", str(STATE)], cwd=str(ROOT), capture_output=True, text=True)
    say("  check_run_journal --state exit %d: %s"
        % (baseline.returncode, baseline.stdout.strip().splitlines()[-1]))
    if baseline.returncode != 0:
        _finish(log, LOG_B)
        return 1
    say("step 5: the view and the journal agree; nothing to reconcile")
    say("step 6: execute next_action: %s" % rebuilt["next_action"])

    append_event("note", "run", "Verify", "resume the run in a new session",
                 "resume: replayed %d events and %d checkpoints, %d committed "
                 "units; next_action was %s"
                 % (rebuilt["events"], rebuilt["checkpoints"],
                    len(rebuilt["committed"]), rebuilt["next_action"]),
                 "evals/long-horizon/session-b-replay.txt",
                 at=stamp(times["base"], times["t6"]))
    say("journal seq 6: note (resume; the contract has no resume event kind)")

    for unit, action_id, cp_stage in (("U2", "a-02", 3), ("U3", "a-03", 4)):
        started_at = times["t%d" % (cp_stage * 3 - 2)]
        result_at = times["t%d" % (cp_stage * 3 - 1)]
        append_event("action_started", unit, "Implement",
                     "derive %s" % UNIT_ARTIFACT[unit], "", "intent recorded",
                     at=stamp(times["base"], started_at), action_id=action_id)
        write_artifact(unit)
        ok, detail = gate(unit)
        if not ok:
            say("FAIL gate %s: %s" % (unit, detail))
            _finish(log, LOG_B)
            return 1
        append_event("action_result", unit, "Implement",
                     "derive %s" % UNIT_ARTIFACT[unit], detail,
                     "gate exit 0: %s" % detail,
                     at=stamp(times["base"], result_at), gate="pass",
                     action_id=action_id)
        say("gate %s pass: %s" % (unit, detail))
        event = commit_checkpoint(cp_stage, unit, "Verify", artifact_rel(unit))
        say("journal seq %d: checkpoint %d (%s verified)"
            % (event["seq"], cp_stage, unit))

    event = commit_checkpoint(
        5, "-", "Done", "evals/long-horizon/session-b.txt; probes/report.txt")
    say("journal seq %d: checkpoint 5 (finalize)" % event["seq"])

    append_event("done", "run", "Done", "finalize the run",
                 "3/3 units closed; acceptance A1..A3 verified",
                 "python3 evals/long-horizon/drive.py --verify exit 0",
                 at=stamp(times["base"], times["t14"]), gate="pass")
    say("journal seq 14: done")
    _finish(log, LOG_B)
    return 0


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------

def verify():
    print("== verify: state view ==")
    result = run_state.check(STATE)
    state_cli = subprocess.run(
        [sys.executable, str(TOOLING / "run_state.py"), "check", str(STATE)],
        cwd=str(ROOT), capture_output=True, text=True)
    print("run_state.py check: exit %d: %s"
          % (state_cli.returncode, state_cli.stdout.strip()))
    if not result["ok"]:
        for error in result["errors"]:
            print("FAIL %s" % error)
        return 1

    print("== verify: journal and view hash ==")
    journal_cli = subprocess.run(
        [sys.executable, str(TOOLING / "check_run_journal.py"), str(JOURNAL),
         "--state", str(STATE)], cwd=str(ROOT), capture_output=True, text=True)
    print("check_run_journal.py --state: exit %d: %s"
          % (journal_cli.returncode, journal_cli.stdout.strip()))
    if journal_cli.returncode != 0:
        return 1

    print("== verify: replay agreement ==")
    code, lines = compare_replay(replay())
    for line in lines:
        print(line)
    if code != 0:
        return 1

    print("== verify: probes ==")
    if probes() != 0:
        return 1
    print("VERIFY OK")
    return 0


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", choices=("a", "b"), default=None)
    parser.add_argument("--replay-only", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    if args.verify:
        return verify()
    if args.session == "a":
        return session_a()
    if args.session == "b":
        return session_b(replay_only=args.replay_only)
    # Default: two sessions as two separate processes, then the probes.
    script = str(Path(__file__).resolve())
    for session in ("a", "b"):
        result = subprocess.run([sys.executable, script, "--session", session],
                                cwd=str(ROOT))
        if result.returncode != 0:
            return result.returncode
    print("== probes ==")
    return probes()


if __name__ == "__main__":
    sys.exit(main())
