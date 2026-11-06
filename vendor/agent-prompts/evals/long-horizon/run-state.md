---
schema_version: 1.2.0
run_id: lh-contract-exercise
goal: Exercise the run-state and journal contract across one session boundary and record what the local tooling proves.
status: done
phase: Done
owner: orch-orchestrator
started: 2026-10-27
updated: 2026-10-27T12:21:10Z
units_total: 3
units_done: 3
checkpoint: 5
last_progress_at: 2026-10-27T12:21:00Z
progress_max_minutes: 120
next_action: ""
stall_window: 3
branch: feat/wp-09-long-horizon-exercise
model: local tooling only; no model call in this exercise
harness: two local shell processes, not a deployed harness
notes: exercise artifacts, see evals/long-horizon/README.md
lease:
  resource: evals/long-horizon/work
  owner: lh-contract-exercise
  expires: 2026-10-27T13:20:30Z
budget:
  tokens: {limit: 20000, used: 18000}
  wall_clock_minutes: {limit: 120, used: 50}
  tool_calls: {limit: 40, used: 24}
  units: {limit: 3, used: 3}
acceptance:
  - id: A1
    criterion: The required run-state frontmatter keys are recorded from the schema, not from memory.
    state: verified
    evidence: "python3 evals/long-horizon/drive.py --verify; gate U1 pass"
  - id: A2
    criterion: The canonical journal event kinds are recorded from the schema.
    state: verified
    evidence: "python3 evals/long-horizon/drive.py --verify; gate U2 pass"
  - id: A3
    criterion: A cold session rebuilds the committed units and the next action from the journal alone, and the view agrees.
    state: verified
    evidence: "evals/long-horizon/session-b-replay.txt: AGREE"
run_gate:
  command: python3 evals/long-horizon/drive.py --verify
  exit: 0
  at: 2026-10-27T12:21:10Z
  evidence: session-b.txt ends at VERIFY OK and both probes match
push_approval:
  operator: library-maintainer (local exercise)
  at: 2026-10-27T12:21:10Z
  ids: [A1, A2, A3]
  scope: local exercise; no deploy, no production run
---

## Units

| unit_id | phase | gate | status | artifact | evidence | kind | next |
|---|---|---|---|---|---|---|---|
| U1 | Push | pass | Done | evals/long-horizon/work/frontmatter-keys.txt | gate: derive matches; journal seq 4 | delivery | U2 |
| U2 | Push | pass | Done | evals/long-horizon/work/journal-kinds.txt | gate: derive matches; journal seq 8 | delivery | U3 |
| U3 | Push | pass | Done | evals/long-horizon/work/sections.txt | gate: derive matches; journal seq 11 | delivery | none |

## Checkpoints

| n | at | unit | phase | gate | kind | progress | artifact | next_action |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-27T12:19:20Z | - | Plan | pass | progress | 0/3; goal, acceptance and budget fixed | standards/long-horizon-runs.md | Execute U1: derive required run-state frontmatter keys |
| 2 | 2026-10-27T12:19:50Z | U1 | Verify | pass | progress | 1/3; work/frontmatter-keys.txt | evals/long-horizon/work/frontmatter-keys.txt | Resume in a new session and execute U2 |
| 3 | 2026-10-27T12:20:30Z | U2 | Verify | pass | progress | 2/3; work/journal-kinds.txt | evals/long-horizon/work/journal-kinds.txt | Execute U3: derive required run-state body sections |
| 4 | 2026-10-27T12:21:00Z | U3 | Verify | pass | progress | 3/3; work/sections.txt | evals/long-horizon/work/sections.txt | Run the run-scope gate and finalize |
| 5 | 2026-10-27T12:21:10Z | - | Done | pass | cadence | 3/3; run gate exit 0; operator approved push | evals/long-horizon/run-state.md | none |

## Decisions

- 2026-10-27: operator approved the goal and the three-unit budget before the first unit.
- 2026-10-27T12:19:50Z: session A ends at checkpoint 2 by design, so session B must resume from disk.
- 2026-10-27T12:20:00Z: session B resumed by replaying the journal, not by re-planning the run.
- 2026-10-27T12:20:00Z: the view is rewritten from the journal; the journal is never edited.
- 2026-10-27T12:21:10Z: operator approved push for A1..A3; the run is local and not deployed.

## Open findings

- F1 (low, owner run): the journal contract has no resume event kind, so a resume is recorded as a note plus a replay.
- F2 (low, owner run): a checkpoint event has no next_action field, so replay rebuilds it from the event result by convention.
- No open high or medium finding.

## In-flight

| intent | key | state | at |
|---|---|---|---|
| Write work/frontmatter-keys.txt | write-frontmatter-keys | done | 2026-10-27T12:19:50Z |
| Write work/journal-kinds.txt | write-journal-kinds | done | 2026-10-27T12:20:30Z |
| Write work/sections.txt | write-sections | done | 2026-10-27T12:21:00Z |

## Operator

RUN lh-contract-exercise | done | units 3/3 | checkpoint 5 | tokens 18000/20000 | next none
