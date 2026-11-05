# Long-horizon run standard (LH-01..LH-14)

Status: ACTIVE (2026-10-25). Applies to any run expected to exceed one context
window, one session, or one operator sitting: multi-unit delivery, overnight or
unattended work, migrations, research programs, and any delegated fan-out whose
result must survive a restart.

This standard extends `workflow-loop.md` (WL-01..WL-15); it does not add a
phase or change a transition. A **run** contains many **units**; each unit
still uses the seven-phase loop and the WL ledger row. The run adds the durable
layer above the unit.

Evidence: `evidence/long-horizon-2026-10.md` (L1-L11). Numbers in that register
are evidence, not defaults for this standard. Frontier task horizons are growing
(L1), but reliability across sessions is still the binding constraint.

## LH-01 -- Definitions

- **Run** -- one goal, one acceptance table, and an ordered set of units that
  together satisfy it. A run may span sessions, context windows, models, and
  operator shifts.
- **Unit** -- one WL-01 loop instance with one artifact and one gate result.
- **Session** -- one context window or one agent invocation. A session is
  disposable; the run is not.
- **Run state** -- the durable, machine-readable record of the run. It is the
  source of truth for goal, acceptance, unit order, progress, budget, and next
  action.
- **Checkpoint** -- a written run state plus a durable artifact: a commit where
  the run owner has commit permission, otherwise a path plus a content hash or
  another recorded durable location.
- **Budget** -- the declared ceiling on tokens, wall-clock time, tool calls,
  and units.
- **Progress** -- a new verified artifact since the previous checkpoint. Elapsed
  time, tokens spent, and tool calls are not progress.

A run without a run state file is not a run; it is an unrecorded session.

## LH-02 -- Run state is durable and canonical

One run state file per run. Use `RUN.md` at the project root, or
`provenance/run-<slug>.md` in a library or repository that keeps provenance
records. Record the path in the task record (for example a `PLAN.md` wave entry
or the task brief), not as an extra WL-08 ledger column.

The file has YAML frontmatter that conforms to `run-state.schema.json`, plus
these sections:

- `## Units` -- one row per unit: `unit_id | phase | gate | status | artifact |
  evidence | kind | next`. This is a compact view of the unit's WL ledger row;
  the WL ledger is canonical for unit state. `kind` is `delivery` or `report`.
- `## Checkpoints` -- one row per checkpoint: `n | at | unit | phase | gate |
  kind | progress | artifact | next_action`. `kind` is `progress`, `cadence`,
  or `stop`.
- `## Decisions` -- operator decisions and re-baselines, newest last.
- `## Open findings` -- unresolved findings with severity and owner.
- `## In-flight` -- side effects in progress: `intent | key | state | at`
  where state is `planned`, `done`, or `failed`.
- `## Operator` -- the current status line and the escalation state.

Frontmatter fields:

| Field | Meaning |
|---|---|
| `schema_version` | `1.2.0`; must match the schema file |
| `run_id` | Lowercase slug, 3-64 characters |
| `goal` | One sentence; the run's outcome |
| `status` | `active`, `waiting`, `blocked`, `done`, or `halted` |
| `phase` | `Plan`, `PlanReview`, `Implement`, `Review`, `Fix`, `Verify`, `Push`, `Ready`, `Ready (unverified)`, `Done`, or `HALT` |
| `owner` | The single agent or role that writes the file |
| `started` | `YYYY-MM-DD` |
| `updated` | ISO-8601 UTC timestamp, `YYYY-MM-DDTHH:MM:SSZ` |
| `last_progress_at` | ISO-8601 UTC timestamp of the latest **changed** progress checkpoint; drives the stall age |
| `units_total` | Number of rows in `## Units` |
| `units_done` | Number of closed units: `Done`, or a `report` unit at `Ready`/`Ready (unverified)` with `next` = `none` |
| `checkpoint` | Number of the last checkpoint, including any archived base |
| `next_action` | One executable action for a cold reader |
| `budget` | Mapping with `tokens`, `wall_clock_minutes`, `tool_calls`, and `units`; each has `limit` and `used` |
| `acceptance` | List of `id`, `criterion`, `state`, `evidence`; state is `pending`, `verified`, `unverified`, or `failed` |
| `reason` | Required when `status` is `halted` (a run reason from LH-09) or `blocked` (the dependency) |
| `stall_window` | Optional; consecutive no-progress progress checkpoints before a stall, default 3, minimum 2 |
| `progress_max_minutes` | Required; set to the longest planned unit plus margin. A longer gap without progress is a stall. Minimum 1 |
| `checkpoint_base` | Optional; number of checkpoint rows archived out of the file, default 0 |
| `checkpoint_archive` | Required when `checkpoint_base > 0`; path of the archived checkpoint rows |
| `push_approval` | Required for `done` and `phase: Push`; `operator`, `at`, `ids` (acceptance ids), optional `scope` |
| `run_gate` | Required for `done`; `command`, `exit`, `at`, `evidence` for the integrated run-scope gate |
| `harness` | Optional harness name |
| `doctrine_version` | Optional doctrine version |
| `lease` | Optional; `resource`, `owner`, `expires` for an exclusive resource |
| `branch` | Optional branch or ref for the run |
| `model` | Optional executor model |
| `changed_files` | Optional list of paths changed since the last checkpoint |
| `notes` | Optional free-text pointer; no state that belongs in a field |

Body skeleton (sections in order):

```markdown
## Units

| unit_id | phase | gate | status | artifact | evidence | kind | next |
|---|---|---|---|---|---|---|---|

## Checkpoints

| n | at | unit | phase | gate | kind | progress | artifact | next_action |
|---|---|---|---|---|---|---|---|---|

## Decisions

- <date>: <decision and reason>

## Open findings

- <id> (<severity>, owner <unit>): <finding>

## In-flight

| intent | key | state | at |
|---|---|---|---|

## Operator

RUN <id> | <status> | units <done>/<total> | checkpoint <n> | tokens <used>/<limit> | next <action>
```

Unit and checkpoint gates use the WL-09 vocabulary: `pass`, `fix`, `hold`,
`halt`.

`next` is the next unit id, a WL phase, or `none` for a closed `report` unit.

The run-state frontmatter `status` is the run lifecycle. The run `phase` is the last executed phase, or the current wait/terminal
outcome. A unit waiting at `Ready` for its own Push is shown in `## Units`; it
does not force the run phase to `Ready`, and `waiting` is reserved for the
final run-level gate after every unit is closed. The `## Units` `status` cell uses the WL phase/outcome vocabulary (`Plan`..`Push`
in WL-01 order, `Ready`, `Ready (unverified)`, `Done`, `HALT`); its `gate` cell is the gate that admitted
the current phase or closed the unit.

Additional invariants: `budget.units.used` equals `units_done`; every budget
limit is positive and `used <= limit`; acceptance ids are unique; a closed unit
has `gate: pass` and evidence, except a `report` unit closed at
`Ready (unverified)`, which closes with `gate: hold`; `updated` is never before the last checkpoint or
`last_progress_at`; `next_action` is empty only for `done`/`halted`;
`push_approval.at` is between `started` and `updated`; `unit_id` matches
`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`.

With `checkpoint_base > 0`, the archived rows are the audit trail: set
`checkpoint_archive` to an existing archive path, and record its hash in
`## Decisions`.
When no progress row remains in the active table, the validator trusts
`last_progress_at` as the archived anchor.

Duplicate YAML keys and duplicate section headings are rejected; the file has
exactly one of each required section. Write no `|` inside a table cell; use a
comma or a dash. The file must stay
small enough to read in one screen: when `## Checkpoints` grows past the
active window, move the older rows to
`provenance/run-<slug>-checkpoints.md` and raise `checkpoint_base` by the number
moved. The counter `checkpoint` continues to increase; it does not reset.

The schema file's top-level `version` is the `schema_version` value in the run
state. It is pinned in `CATALOG.md` as well. A schema change is a migration:
read the old file, write the new one, keep the old file until the new one
validates.

**Precedence.** The WL ledger row is canonical for a unit's phase, gate,
status, artifact, findings, and evidence. The run state is canonical for the run
goal, acceptance, budget, checkpoints, and next action. When the two disagree, stop
and reconcile before the next unit (LH-04); do not continue on a state file that
contradicts the repository.

## LH-03 -- Checkpoint triggers and content

Write a checkpoint at every one of these points:

1. after a unit passes its gate and before the next unit starts (`kind:
   progress`); the first checkpoint of a run is also `progress`, recording the
   accepted Plan, so every run has at least one progress checkpoint;
2. before compaction, a handoff, a model switch, or a long or destructive tool
   call (`kind: cadence`);
3. before any deliberate stop, budget threshold, or wait state (`kind: stop`);
4. on an operator interrupt, a crash report, or an unexpected environment
   change (`kind: cadence`);
5. at the cadence the operator requested, even when nothing changed (`kind:
   cadence`).

A checkpoint is complete when the state file validates, the artifact path
exists, and the `next_action` is executable by a cold reader. A chat summary, a
memory entry, or a tool transcript is not a checkpoint.

Keep the checkpoint cheap: update the frontmatter counters, the units row, one
checkpoint row, and `next_action`. Do not rewrite the narrative sections on
every step.

The run state is itself an artifact. Commit it at each checkpoint where the
writer has commit permission; otherwise copy it to the durable location and
record the path or hash in `## Decisions`. A checkpoint that only exists in the
working tree is not recoverable after a reset.

## LH-04 -- Resume protocol

A new session has no memory of the previous one. Resume in this order, before
any new work:

1. Confirm the workspace and the run id (`pwd`, branch, project root).
2. Read the run state, the last checkpoints, and the WL ledger row.
3. Read `git status`, `git diff`, and the recent commit log; compare them with
   the recorded artifact paths.
4. Run the cheapest baseline check that detects a broken environment.
5. Reconcile state with reality. If they disagree, fix the state first and
   record the discrepancy as a finding; never continue on a state file that
   contradicts the repository.
6. Execute `next_action`. Do not re-plan the whole run, re-open settled
   decisions, or restart completed units unless step 5 proves they are not
   actually complete.

A resume that starts by re-planning from scratch is a new run; record it as
one. A run resumed from a stale state is worse than a run stopped at a
checkpoint.

## LH-05 -- Incremental delivery and clean state

Work one unit at a time. One unit produces one reviewable artifact, one gate
result, and one checkpoint. Do not batch several unverified units into one
large step.

After every unit the environment must be in a state a new engineer could
continue from:

- the artifact is durable: committed with a message that names the unit where
  the writer has commit permission, otherwise stored at a recorded path with a
  hash or another durable location;
- the proof command has been run and its output recorded;
- the run state and the WL ledger row agree on unit, phase, gate, status, and
  artifact path;
- partial or broken work is either reverted or explicitly recorded as
  incomplete, never left undocumented.

A `report` unit closes at `Ready` or `Ready (unverified)` with `next: none`;
it does not need Push. It counts as closed in `units_done` and satisfies the
run completion gate without pretending to be `Done`. The run's own `Done` is
the run-level finalize (`run_gate` plus `push_approval`), not a claim that the
report unit ran Push. A `delivery` unit closes
only at `Done`.

This is the library's form of the initializer/feature-list pattern: the unit
list is the feature list, the checkpoint is the progress file, and the durable
artifact is the recoverable state (L2). One feature at a time is not a style
preference; it is what keeps the next session from having to guess.

## LH-06 -- Context budget and compaction

Treat the context window as a finite attention budget, not as the run's
storage (L3, L9).

Before context pressure forces a decision, write to disk:

- the goal and acceptance table;
- decisions already made, with the reason;
- open findings and their owners;
- the artifact paths and the `changed_files` list;
- the next action and the budget state.

A compaction summary preserves exactly that list. It may drop raw tool output,
repeated file dumps, exploratory dead ends, and anything re-derivable from a
path or a command. It must not drop an unresolved finding, a rejected
alternative that explains a constraint, or an acceptance criterion.

Retrieve large material just in time by path or query. Do not keep whole
artifacts in context when a path and a line range will do. A subagent return is
a summary plus a path, not the run's state (L3, SD-06).

If a fact would be needed after a context reset, it must be in the run state
before the reset. "I will remember it" is not a mechanism.

## LH-07 -- Progress cadence and stall detection

Each progress checkpoint records `progress` (units done over total plus the
last verified artifact) and a single `next_action`. Update `last_progress_at` to
the checkpoint time.

Progress means a new verified artifact or a higher verified-unit count. A
progress checkpoint with the same count and artifact as the previous progress
checkpoint is not progress and does not advance `last_progress_at`. The latest
progress row must report the current `units_done/units_total` (for `active`,
it may be lower if cadence checkpoints followed the last unit gate; for `done`,
it must be exact). Cadence and stop checkpoints are not progress points and do
not reset or extend the window.

An `active` run is stalled when either condition holds:

- `stall_window` consecutive progress checkpoints show the same count and
  artifact (default: three);
- `progress_max_minutes` is set and `updated` is more than that many minutes
  after `last_progress_at`.

The checkpoint `unit` cell is `-` when the checkpoint is not tied to a single
unit.

A `blocked` run is waiting on an external dependency, not stalled; the operator
monitors it separately. `last_progress_at` must equal the `at` of the latest
**changed** progress checkpoint in the active table (or be the archived anchor
when `checkpoint_base` is non-zero).

On a stall:

1. diagnose once and record the cause;
2. re-plan once, within the WL-07 refinement bound;
3. if there is still no new artifact, stop at a checkpoint and report `HALT`
   with `reason=stalled`; if the operator explicitly asked to wait, record a
   `kind: stop` checkpoint with `gate: hold` and keep the run `active` (or
   `blocked` with a dependency reason).

Do not repeat an identical failed action, retry the same tool with the same
input, or add agents to compensate for a vague plan. More time and more budget
do not by themselves fix a stuck agent (L4).

## LH-08 -- Goal integrity and premature completion

The run state carries the goal and the acceptance table. Restate both in the
`## Operator` report and whenever either changes. The state file is the source
of truth when memory and the file disagree.

- The state file always carries the goal and the acceptance table; restate them
  in the `## Operator` report and whenever either changes.
- Change the goal only by an explicit operator decision. Keep the previous goal
  in `## Decisions` so the change is auditable.
- Scope discovered mid-run becomes a new unit or a recorded non-goal. It never
  becomes silent expansion.
- Do not rewrite acceptance criteria to match what was built.
- A halted run records a `reason`; a done run records `push_approval`
  regardless of acceptance state (see below), and each `unverified` row must be
  named in its `ids`.

Completion is a proof, not an impression. The run may report `Done` only when:

- every unit is closed (LH-05);
- every acceptance row is `verified` with evidence from this run, or an
  `unverified` row is covered by a recorded `push_approval` at Push;
- `run_gate` records the integrated run-scope gate command, exit, timestamp,
  and output; a nonzero exit is allowed only when `push_approval` covers it;
- `## Open findings` has no open high or medium finding, and `## In-flight`
  has no side effect left `planned`.

`push_approval` is required for every `Done` run and for `phase: Push`, even
when every row is verified: `Push` is operator-gated. An operator-approved unverified row stays
`unverified`; `Done` means the finalize action happened, not that the claim was
verified. Seeing that progress
exists is not completion (L2, L5). Goal adherence degrades under competing
objectives, so the recorded goal is the anchor, not the model's current
summary (L8).

## LH-09 -- Budgets and termination

Declare every budget before the first unit: tokens or context resets,
wall-clock time, tool calls, and units. Record the
limit and the used amount in the frontmatter.

- **Soft limit** (operator convention, default 80% of any budget): write a
  checkpoint, report the remaining work, and continue only within the approved
  plan. The 80% is not a schema field.
- **Hard limit** (default: 100%): stop at a checkpoint. Do not start a new unit,
  do not claim completion, and do not silently extend the budget. A real
  overrun may be recorded only on a halted run with `reason: budget`; the
  actual `used` value is never rewritten down.

Raising a budget is an operator decision recorded in `## Decisions`, with the
reason and the new limit. It is not a repair for a stalled run.

A check stopped by a hard limit is terminal for that attempt and the last
verified state is what the run reports (`verification-integrity.md` VI-11).

Record the termination as one of:

- `Done` -- `run_gate` passed (or a nonzero exit is covered by
  `push_approval`) and the operator approved Push;
- `Ready` / `Ready (unverified)` -- waiting at the operator gate;
- `HALT` -- unsafe, stalled, drift-detected, budget-exhausted, or
  operator-declined.

Use a canonical `reason` for a halted run: `blocked`, `unsafe`, `unresolvable`,
`over-bound`, `budget`, `stalled`, `drift`, or `operator-declined`. These are
run-scope reasons; map the task-level cause to a `halt-taxonomy.md` HF id where
one exists. A `blocked` run records the dependency text in `reason`; a halted
run whose cause was the external block records `blocked`.

A run that stops because the context window filled without a valid checkpoint
is a process failure, not a run outcome. Report the last known checkpoint and
the lost work explicitly.

## LH-10 -- Verification cadence

Verification happens twice, at different scopes:

- **Per unit** -- the WL Review and Verify gates. No unit is `Done` without
  fresh evidence for its own artifact.
- **Per run** -- an acceptance gate that runs the full acceptance command set
  against the integrated result, from a clean context where possible. It is not
  the sum of unit claims. Record its command, exit, timestamp, and output in
  `run_gate`; a nonzero exit is allowed only when `push_approval` covers it.

After each unit, run the cheapest regression check the project has. If a unit
can break an earlier acceptance row, re-run that row before moving on.

End-to-end proof is mandatory where the acceptance criterion is behavioral.
Unit tests and a local curl are not evidence that the feature works as a user
experiences it (L2). If the proof cannot run, record the exemption and close as
`Ready (unverified)`; a `Done` run that keeps that row must carry the operator's
`push_approval`, and the row stays unverified. Never label it `verified`.

The author is never the only verifier at run scope. Use a clean-context
verifier or a mechanical check (WL-05).

## LH-11 -- Operator monitoring and escalation

An unattended run must be observable without reading its transcript. Report at
the requested cadence and after every checkpoint that changes phase, budget
band, or blocker. Use this line exactly; optional prose may follow it:

```text
RUN <id> | <status> | units <done>/<total> | checkpoint <n> | tokens <used>/<limit> | next <action>
```

The `## Operator` section must contain this exact line; `run_state.py check`
compares it with the frontmatter. The `run_state.py status` command prints the
same line. If the operator asks for a heartbeat, update `updated` at least every
agreed interval; a run whose `updated` is older than that interval while
`active` or `blocked` is stale. Check it with
`run_state.py check RUN.md --max-age-hours <interval>`. A hung process that
writes nothing at all is caught by that flag, not by the stall fields.

Escalate instead of guessing when:

- acceptance is ambiguous or contradictory;
- the next action is destructive, irreversible, or outside the workspace;
- credentials, money, external accounts, or another team are required;
- a budget hard limit is reached, the run is stalled, or drift is detected;
- the operator's last instruction conflicts with the recorded goal.

Status and phase are paired: `active` uses `Plan`..`Push`; `blocked` uses
`Plan`..`Verify`; `waiting` uses `Ready` or `Ready (unverified)`; `done` uses
`Done`; `halted` uses `HALT`.

A wait state costs nothing and is a valid outcome. Use `blocked` for an external
dependency, with the dependency in `reason`. Use `waiting` only at the final
operator gate, after every unit is closed. A blocking approval
must not be simulated, and a declined approval is `HALT`, not `hold` (WL-02).

### Intercept and handback

An operator may pause, steer, or take over a run mid-unit. The run has one
writer at a time, and the operator outranks it.

- **Pause**: stop at the next safe point (after the current tool call, before
  the next destructive action), write a checkpoint with kind `stop`, and print
  the `RUN` line. Do not abandon a half-applied change silently.
- **Guidance is scoped**: the operator's next instruction applies to the current
  unit, is recorded in `## Decisions`, and expires with that unit. It is not a
  permanent policy change and it is not a goal change (LH-08).
- **Takeover**: the operator owns the writer role for the duration. The agent
  performs no write, treats observed changes as the operator's, and re-reads the
  workspace before resuming.
- **Handback**: the guidance is appended to the unit's instruction (not to the
  goal), the unit returns to pending, and the run resumes at Plan for that unit
  only. Completed units are not re-planned.
- **Replay, never re-run**: on resume, an action already recorded complete is
  not executed again. A mismatch between the recorded action and the current
  workspace (hash, command, or file content) invalidates the checkpoint: the
  unit re-enters Plan instead of replaying blind (LH-12).
- **Intercept is never an approval**: a pause, a guidance note, or a takeover
  does not authorize Push. Push still needs the explicit `go` (WL-02).

## LH-12 -- Failure, crash, and idempotency

Assume the process can die at any step: crash, timeout, context exhaustion,
model switch, provider error, or operator interrupt.

- Record intent before a side effect in `## In-flight`, and the result after
  it. A step that cannot be replayed safely must record enough state to detect
  that it already happened.
- Make writes idempotent where the tool allows it: create-or-update, compare
  before write, or a recorded idempotency key.
- Use `lease` for an exclusive resource (branch, deploy target, shared account),
  with an owner and an expiry.
- On restart, run the resume protocol and check for partial side effects before
  retrying. Do not blindly replay a command whose first attempt may have
  succeeded.
- A model or doctrine switch mid-run is a checkpoint plus a re-baseline note.
  Results from different models or harnesses are not comparable and must not be
  pooled as one measurement.

Crash recovery is not a new phase. It is a resume from the last valid
checkpoint (L6, L7).

## LH-13 -- Long-run evaluation

Treat a long-horizon change like any other experiment (WL-12):

- pre-register the task, the unit count, the budgets, and the stop conditions;
- pin both arms by hash or ref, with the same model, harness, and budget;
- record every attempt, including crashes and budget-exhausted runs;
- report partial completion, stall count, and recovery time as outcomes, not as
  exclusions;
- measure units per hour, tokens and cost per verified unit, checkpoint
  recovery time, drift events, stalled checkpoints, escaped defects, and
  handoff failures;
- compare against a single-session baseline on the same model and harness;
- treat a small sample or one model as directional, not proof.

A long-horizon run without a baseline is an anecdote. A benchmark score without
the budget and the failure count is not a result. Most long-horizon benchmark
reports are still vendor or preprint results with large token budgets (L10);
concurrency is a separate lever and carries a write tax (L11).

## LH-14 -- Append-only run journal

The run state file is a view; the journal is the history. A resumed run rebuilds
the committed facts from the journal instead of trusting the last written view.

- **Journal** -- `events.jsonl` beside the run state file. When the state is
  `provenance/run-<slug>.md`, the journal is `provenance/run-<slug>.events.jsonl`.
  One JSON object per line, append-only, schema `run-journal.schema.json`.
- **State view** -- the run state file materialized from the journal. A writer
  may update it for readability; a reader reconstructs committed unit state from
  the journal.
- **Replay** -- on resume, read the journal in `seq` order, rebuild committed
  unit states, the checkpoint count, and `next_action`, then restore view-only
  counters (for example `budget.used`) from the last `state_sha256`-pinned view.
  Do not replay from chat memory and do not re-plan from scratch.

Event kinds:

| Kind | When | Additional requirements |
|---|---|---|
| start | First event of the run | `unit: run`; goal in `result` |
| checkpoint | A state view was committed | `gate`; `state_sha256` |
| action_started | Before a side effect | `action_id` |
| action_result | After a side effect | `action_id`; non-empty `evidence` |
| action_withheld | A planned action was not run | `action_id`; non-empty `reason` |
| note | Annotation that changes no state | `result` or `reason` |
| stop | Terminal HALT | `phase: HALT`; `gate: halt`; `reason` |
| done | Terminal Done | `phase: Done`; `gate: pass`; `evidence` |

Journal rules:

- Append only. Never edit or delete a written event. A correction is a new event
  with its own `seq`, `action`, and `evidence`; history is not rewritten.
- One action per event. Record `action_started` before a side effect and
  `action_result` after it, both with the same `action_id`. An `action_id` is
  unique for the whole run, not per unit. A write that may have partially
  applied is detected by a started event without a result or a withheld
  receipt.
- `seq` is consecutive from 1, one per line; `at` is ISO-8601 UTC and
  non-decreasing. A deleted or inserted line breaks the sequence and fails the
  checker.
- `phase` uses the WL-01 phase or outcome values. `gate`, when present, is one
  of `pass`, `fix`, `hold`, or `halt`; it is never a new value.
- The final event is `checkpoint`, `done`, or `stop`. `done` and `stop` may
  appear only as the last event; an unterminated journal is an interrupted run,
  not a finished one.
- `unit` is the unit id, or `run` for a run-scope event. There is no other
  sentinel.
- `done` carries evidence; `stop` carries a `reason`. An event without evidence
  cannot close a unit or the run.
- `state_sha256` on a `checkpoint` is the SHA-256 of the exact state file bytes
  (`sha256sum RUN.md`) written at that checkpoint. A view whose hash differs
  from the last checkpoint is stale.

Reconciliation and resume:

- The journal wins. If the hand-written view disagrees with replayed state, keep
  the journal and rewrite the view. Never "fix" the journal to match the view.
- If replay meets an unknown `kind`, an `action_started` with no recorded
  receipt, or an `action_result` with no matching start, withhold the next
  action and stop with the reason. Do not guess an outcome or re-run the action
  blindly (LH-12).
- An action whose result is recorded is not run again on resume. Idempotency
  keys cover the case where recording the result itself was interrupted.
- A journal that fails `tooling/check_run_journal.py` is not resumed. Structural
  damage -- bad sequence, decreasing time, unknown kind, or a missing required
  field -- is terminal for that journal: keep it as evidence, record the repair
  decision in `## Decisions`, and start a new journal at a new path from the
  last valid checkpoint. Never edit the offending line to make the checker pass,
  and never append into a journal that cannot validate.

Check with `python3 tooling/check_run_journal.py PATH`. The example is
`../exemplars/run-journal-example.jsonl`; the contract is
`run-journal.schema.json`.

## Anti-patterns

- Using the context window as the only run state.
- One-shotting the whole run and hoping compaction carries it.
- Batching unverified units into one large commit at the end.
- Declaring victory because progress is visible.
- Raising the budget to escape a stall.
- Silently expanding scope or rewriting acceptance to match the build.
- Resuming by re-planning from scratch and calling it continuity.
- Trusting chat memory after a context reset.
- Keeping unbounded history instead of checkpointing and continuing.
- Reporting a partial run as `Done`.
- Editing `events.jsonl` to make the state view look right.
- Appending to a journal that already fails the checker.
- Rewriting a failed action's result instead of appending a correction.
- Re-running an action whose result is already recorded.
- Resuming from the hand-written view without replaying the journal.

## Cross-refs

- `workflow-loop.md` -- the unit loop, ledger, and findings (WL-01..WL-15)
- `run-state.schema.json` -- the machine-readable run-state contract
- `verification-integrity.md` -- VI-11 exhaustion is terminal, VI-01 verdicts
- `run-journal.schema.json` -- the append-only event contract
- `../tooling/check_run_journal.py` -- journal validator
- `../exemplars/run-journal-example.jsonl` -- a five-event journal
- `subagent-delegation.md` -- handoff, return, budget, and verification rules
- `halt-taxonomy.md` -- HF ids for task-level halts and recovery
- `../exemplars/run-state-example.md` -- a validated run-state example
- `../docs/knowledge-base/long-horizon-agents-2026-10.md` -- synthesis and
  comparison with this library
- `evidence/long-horizon-2026-10.md` -- the evidence register
