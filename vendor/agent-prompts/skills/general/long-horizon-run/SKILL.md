---
name: long-horizon-run
description: Use when autonomous work must survive more than one context window or session - overnight unattended runs, multi-unit delivery, resuming after a crash or compaction, checkpointing progress, budget and stop conditions, goal drift, and long-run operator reporting.
rigid: true
---
<!-- Repo-authored 2026-10-25. Canon: this file. Rules: standards/long-horizon-runs.md. -->

# Long-horizon run

A long run is not a big prompt. It is a small durable state plus a sequence of
units, each proved and checkpointed. Treat each session as an engineer with no
memory of the last shift.

## Module 1 - Scope and run state

Use this when work outlives one context window, session, or operator sitting:
migrations, multi-unit builds, research programs, overnight automation, or
resumable fan-out; a bounded task uses the normal loop.

Canonical rules: `standards/long-horizon-runs.md` (LH-01..LH-14). Contracts:
`standards/run-state.schema.json` and `standards/run-journal.schema.json`.
Validate with `python3 tooling/run_state.py check RUN.md` and
`python3 tooling/check_run_journal.py events.jsonl`.

The state is a view; `events.jsonl` is history. Append one action per event and
replay on resume; stop on an unknown action, never re-run it.

Write one file per run: `RUN.md` or `provenance/run-<slug>.md`.

```yaml
schema_version: 1.2.0
run_id: docs-migration
goal: <one line>
status: active
phase: Implement
units_total: 3
units_done: 2
checkpoint: 4
last_progress_at: 2026-10-24T23:45:00Z
progress_max_minutes: 180
next_action: <one executable action>
budget: {tokens: 400000, wall_clock_minutes: 480, tool_calls: 400, units: 3}
acceptance:
  - {id: A1, criterion: <check>, state: verified, evidence: <command + exit>}
```

Body sections run `## Units` through `## Operator` (LH-02). A `report` unit may
close at `Ready` or `Ready (unverified)` with `next: none`; a `delivery` closes
only at `Done`. The orchestrator is the only writer; a subagent returns an
artifact and findings.

## Module 2 - Checkpoint and resume

The first checkpoint is `progress`, recording the accepted Plan (accepted means
the plan-review gate passed, WL-15);
`last_progress_at` must match the latest one. Checkpoint after every unit, before
compaction, a handoff, a model switch, a long or destructive tool call, or any
stop, and on an interrupt, crash, environment change, or requested cadence. Mark
`kind` as `progress`, `cadence`, or `stop`. Checkpoint before the action it
authorizes: the durable record is written in the transaction that justifies it,
and dispatch happens only after that commit (EF-01). A checkpoint is valid only
when the state file passes `run_state.py check`, the artifact path exists, and
the `next_action` is executable by a cold reader. Commit the state where the
writer has permission; otherwise copy it to the durable location and record the
path in `## Decisions`.

Resume in this order:

1. Confirm workspace and run id.
2. Read the run state, last checkpoints, and ledger.
3. Read `git status`, `git diff`, and the recent log.
4. Run the cheapest check that detects a broken environment.
5. Reconcile state with reality; fix the state first if they disagree.
6. Execute `next_action`; do not re-plan or restart completed units.

A checkpoint records that state was written, not that it was read or acted on
(EF-08). Confirm the artifact and ledger show the step's effect before counting
a unit resumed.

## Module 3 - Progress, budget, report, and failure

Progress means a new verified artifact or a higher verified-unit count. A
`progress` checkpoint with the same count and artifact as the previous one is
not progress; `stall_window` of them in a row (default 3, minimum 2) is a
stall. `progress_max_minutes` is required; set it to the longest planned unit
plus margin. A longer gap without progress is also a stall; cadence and stop
checkpoints do not count. On a stall: diagnose once, re-plan once, then HALT
with `reason=stalled`. A `blocked` run waits on an external dependency and is
not a stall.

The state file always carries the goal and acceptance; restate them in the
Operator report and whenever either changes. Change the goal only by a recorded
operator decision; turn discovered scope into a new unit or a recorded
non-goal. Completion requires every unit closed, `run_gate` (`command`, `exit`,
`at`, `evidence`), and `push_approval` (`operator`, `at`, `ids`) even when every
row is verified; `ids` must cover each unverified row, which stays unverified.
Before `Done`, clear open high/medium findings and planned `In-flight` side
effects. Each unit gate closes with a verdict record (VI-01): a skipped check is
unverified, never a pass (VI-03), and exhaustion is terminal (VI-11).

Declare budgets up front. At 80% (operator convention) checkpoint and report; at
100% stop, report the partial, never claim Done. A budget raise is an operator
decision, not a stall fix.

Report one line at the requested cadence and after any phase, budget, or
blocker change:

```text
RUN <id> | <status> | units <done>/<total> | checkpoint <n> | tokens <used>/<limit> | next <action>
```

Escalate ambiguous acceptance, destructive actions, missing credentials, a hard
budget limit, a stall, or drift. `waiting` is only the final operator gate after
every unit is closed; a declined approval is HALT.

Assume the process can die. Record intent in `## In-flight` before a side effect
and the result after it; make writes idempotent or replay-safe; lease exclusive
resources; on restart check for partial effects before retrying. A model or
harness switch mid-run is a checkpoint plus a re-baseline note.

Anti-patterns: context as the only state; one-shotting the run; silent scope
expansion; re-planning from scratch on resume.

## Doctrine position

Long runs wrap the seven-phase loop; they do not add a phase. Plan fixes the
run goal and acceptance; each unit then runs its own
Plan -> PlanReview -> Implement -> Review -> Fix -> Verify.
The orchestrator owns run state and checkpoints; a subagent owns one unit and
returns an artifact plus findings. Push stays operator-gated, and a budget or
stall stop is HALT, not Done.
