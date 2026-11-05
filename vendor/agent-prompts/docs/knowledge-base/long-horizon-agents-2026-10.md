# Long-horizon autonomous runs (2026-10)

Status: design record for `standards/long-horizon-runs.md` (LH-01..LH-14) and
`tooling/run_state.py`. Evidence: `standards/evidence/long-horizon-2026-10.md`
(L1-L11). Scope: library-side. The layer was exercised locally on 2026-10-27
(section 6.1); a deployed harness run and the LH-13 A/B are **deferred to
November** because dsh and zcode are inactive this cycle, and they are not
claimed here.

## 1. The problem

A long run is not a long prompt. It is a sequence of sessions, each starting
with no memory of the last, that must still produce one coherent result. The
literature converges on the same failure set:

- one-shotting the whole job and running out of context mid-change (L2);
- declaring victory because progress is visible (L2, L5);
- marking work done without end-to-end proof (L2);
- context overload and "in-context locking" rather than a lack of time (L4);
- internal state silently diverging from the real environment (L7);
- a crash losing execution, because a checkpoint preserved data but not the
  run (L6);
- goal drift under competing objectives (L8).

The current library had a strong *unit* loop but no *run* layer. It could say
"Plan -> Implement -> Review -> Fix -> Verify -> Push" and keep a per-unit
ledger. It could not say where the run is after a crash, what to read first on
a cold start, when to stop, or how an operator sees progress without reading the
transcript.

## 2. Requirement model

| Capability | What the evidence requires | Source |
|---|---|---|
| Durable state | Goal, acceptance, unit order, current position, and next action live outside the context window | L2, L3, L7 |
| Checkpoints | State is written at defined points, not when the model remembers | L2, L6 |
| Resume | A cold session reconciles state with the repo before new work | L2, L6 |
| Incremental delivery | One unit at a time; a clean, recoverable state after each | L2 |
| Context discipline | Compaction preserves decisions and findings; raw output can go | L3, L9 |
| Progress and stall | Progress is a verified artifact; a stuck run stops instead of spinning | L4, L5 |
| Goal integrity | The goal and acceptance are restated and changed only by an operator | L7, L8 |
| Budget and termination | Limits are declared; partial completion is a real outcome | L4, L5 |
| Verification cadence | Per-unit proof plus a run-scope acceptance gate | L2, L5 |
| Monitoring | A status line, escalation triggers, and a heartbeat | L6 |
| Failure and idempotency | Crash, timeout, model switch, and partial side effects are expected | L6, L7 |
| Evaluation | Long-run changes are measured with a baseline and partial outcomes | L1, L10 |

## 3. Comparison with the library before this change

| Capability | Before | Gap | Now |
|---|---|---|---|
| Durable state | Per-unit ledger row; resume "from it" in prose | No run-level goal, acceptance table, budget, or next action | `RUN.md` / `provenance/run-<slug>.md` with a schema |
| Checkpoints | Implicit in the ledger | No trigger list, no completeness test | LH-03 triggers and a validator |
| Resume | "Resume from it" | No cold-start order, no state/repo reconciliation | LH-04 six-step protocol |
| Incremental delivery | One writer per surface; one refinement per gate | No commit-per-unit or clean-state rule | LH-05 |
| Context | Prompt token budgets; AP-14 | No compaction or external-memory policy | LH-06 |
| Progress | Gate outcomes | No progress definition or stall rule | LH-07, with stall detection in the tool |
| Goal integrity | One refinement bound | No goal restatement or drift check | LH-08 |
| Budget | None at run scope | No soft/hard limits or partial-completion outcome | LH-09 |
| Verification | Per-unit Review/Verify | No integrated run acceptance gate | LH-10 |
| Monitoring | Operator Push gate | No status line, cadence, or escalation triggers | LH-11 |
| Failure | HALT/rollback taxonomy | No crash, retry, or idempotency rule | LH-12 |
| Evaluation | WL-12 workflow metrics | No long-run metrics or partial-outcome reporting | LH-13 |

The unit loop itself was not changed. The run layer wraps it: a run contains
units, each unit still uses WL-01..WL-13, and `Push` is still operator-gated and
proved by WL-14. LH-14 adds the append-only journal: state is a materialized
view, resume replays the journal, and the journal wins over a hand-edited view.

## 4. What was implemented

| Artifact | Purpose |
|---|---|
| `standards/long-horizon-runs.md` | Normative rules LH-01..LH-14, run-state sections, journal rules, field table, anti-patterns |
| `standards/run-state.schema.json` | Machine-readable contract: required keys, enums, table columns, patterns, defaults |
| `standards/run-journal.schema.json` | Append-only event contract for `events.jsonl` |
| `tooling/check_run_journal.py` | Monotonic sequence/timestamps, required fields, action receipts, terminal event, evidence/reason; `--state` compares the view with the last committed hash |
| `exemplars/run-journal-example.jsonl` | A valid five-event journal |
| `tooling/run_state.py` | `check`, `status`, `next`; validates schema conformance plus cross-field invariants |
| `exemplars/run-state-example.md` | A validated mid-run example |
| `tooling/check_long_horizon.py` | Library gate: rule headings, schema/doc alignment, evidence ids, orchestrator duties, exemplar validity, exercise validity |
| `evals/long-horizon/` | Two-session exercise: state, journal, replay comparison, two probes, and its runner |
| `skills/general/long-horizon-run/SKILL.md` | On-demand operational checklist for an agent running unattended |
| `agents/orchestration/orch-orchestrator.md` 2.1.3 | The orchestrator owns the run state, checkpoints, resume, and budget/stall stop |
| `standards/workflow-loop.md` | Cross-reference; states that the run layer adds no phase |
| `standards/subagent-delegation.md` | Handoff carries the run-state path; a subagent never edits run state; a budget stop returns partial evidence |

The tool enforces the invariants that are easy to get wrong by hand:

- `schema_version` matches the schema file; counters agree with the tables
  (`units_total`, `units_done`, `checkpoint`);
- every budget is within its limit (a real overrun is allowed only on a
  `halted` run with `reason: budget`); the unit budget is at least the planned
  unit count; and the used amount matches the closed-unit count;
- a closed unit has a passing gate and evidence; a `report` unit closes at
  `Ready`/`Ready (unverified)` with `next: none`; a `delivery` unit closes only
  at `Done`;
- `Done` requires every unit closed, `run_gate` (`command`, `exit`, `at`,
  `evidence`), `push_approval` (`operator`, `at`, `ids`) even when all rows are
  verified, no pending or failed row, no open high/medium finding, no planned
  `In-flight` side effect, and every unverified row covered by `ids`; an
  approved unverified row stays unverified;
- `waiting` requires every unit closed and cannot hide a pending or failed row; `halted` needs a canonical
  reason; `blocked` needs the dependency in `reason`;
- checkpoints are monotonic, name a real unit or `-`, carry a canonical `kind`,
  and their `at` does not exceed `updated`;
- an `active` run stalls when three `progress` checkpoints share the same count
  and artifact, or when the required `progress_max_minutes` is exceeded; a
  `blocked` run waits instead; `cadence` and `stop` checkpoints do not count;
- the `## Operator` line must start with the status line computed from the
  frontmatter;
- `updated` can be aged for an unattended-run check (`active` and `blocked`); a
  future timestamp beyond a 10-minute clock-skew tolerance is rejected;
- duplicate YAML keys and duplicate section headings are rejected;
- `checkpoint_archive` must point at an existing file when `checkpoint_base > 0`;
- a lease whose `expires` is before `updated` is rejected;
- `## In-flight` records the intent, idempotency key, state, and time of a side
  effect, and an optional `lease` bounds an exclusive resource.

## 5. Design decisions

- **No new phase.** The six-phase loop is the unit contract that the A/B
  evidence covers. Adding a seventh phase would invalidate that evidence and
  make every carrier's workflow map wrong. The run layer is orthogonal.
- **Markdown plus YAML, not a database.** The file must be readable by a human
  operator and a model, diffable in git, and writable without a service. The
  schema is the machine contract; the body is the operator view.
- **A validator, not an executor.** The library cannot run an agent. It can
  make an invalid run state fail loudly and make the resume brief deterministic.
  Runtime enforcement belongs to the deployed harness (deferred).
- **Defaults are design choices, not findings.** The 3-checkpoint stall window
  and 80% soft budget are defaults. The evidence supports the mechanisms, not
  those numbers.
- **Partial completion is first-class.** `HALT` with a reason and a last valid
  checkpoint is a successful stop. `Done` means the operator approved Push and
  the finalize action happened; an approved unverified row stays unverified
  rather than being relabelled as proof.

## 6. Limits and what remains unverified

- No deployed harness ran this. The rules are not validated in a live loop. A
  local two-session exercise now validates the file layer (section 6.1); it does
  not replace a harness run.
- No A/B was run for the long-horizon additions. The 1.3.0 and 2.0.0 A/B results measured the pre-1.3.1 body; they cover the
  unit loop doctrine, not LH-01..LH-14 or the current body.
- The orchestrator template changed from 2.0.0 to 2.1.3 (current). The 2.0.0 A/B evidence
  therefore describes the loop doctrine, not the new orchestrator body.
- The evidence is mostly vendor engineering, preprints, and benchmark reports.
  Only the workflow-loop layer has a controlled comparison in this repository.
- The tool checks state files; it cannot prove that an agent actually wrote
  them at the right time or that a side effect was idempotent.
- Crash recovery, leases, and idempotency need runtime support (locks, durable
  queues, or a supervisor) that this library does not provide. The `lease` and
  `## In-flight` fields record intent; they do not enforce exclusivity. Section
  6.1 records why that stays the decision, and which part is now enforced.
- The validator cannot prove that the artifact path exists, that a checkpoint
  was written before compaction, or that two sessions did not write the run
  state concurrently.

### 6.1 Local exercise (2026-10-27) -- what is now proved, and what stays blocked

`evals/long-horizon/` runs the layer end to end on the live library checkout:
two separate OS processes, five checkpoints, 14 journal events, and three units
whose artifacts are derived from the checked-in contracts and re-derived byte
for byte by their gates. Session A stops at checkpoint 2 (1/3); session B starts
cold, replays `events.jsonl`, compares the replay with `run-state.md`, and only
then continues. Runner: `python3 evals/long-horizon/drive.py`; revalidation:
`python3 evals/long-horizon/drive.py --verify`, which rewrites only `probes/`.

Committed output of the two validators:

```text
$ python3 tooling/run_state.py check evals/long-horizon/run-state.md
run-state: OK lh-contract-exercise (3 units, 5 checkpoints)

$ python3 tooling/check_run_journal.py evals/long-horizon/events.jsonl \
    --state evals/long-horizon/run-state.md
run-journal: 14 events, 0 violation(s)
```

The replay in session B, before any new work:

```text
replay: 5 events, 2 checkpoints
replay: committed U1 at Verify (gate pass)
replay: next_action = Resume in a new session and execute U2
view:   checkpoint 2, units_done 1/3
view:   next_action = Resume in a new session and execute U2
hash:   view 9915aee07e6b..., last checkpoint seq 5 records 9915aee07e6b...
AGREE
```

Proved:

- the checkpoint protocol is executable as written, and a checkpoint is only
  admitted after the view validates and its hash is pinned in the journal;
- a cold process rebuilds the committed units, the checkpoint count and the
  `next_action` from the journal alone, and reaches the same result as the view;
- view/journal agreement is mechanisable. Probe 1 hand-edits one acceptance
  evidence cell: `run_state.py check` still exits 0 because the view is
  internally consistent, while `check_run_journal.py --state` exits 1 with
  `stale view`. Before this change, nothing reported that (LH-14 stated the rule;
  no command enforced it);
- an action with no receipt is visible before replay: probe 2 warns
  `action_id a-02 started at seq 3 has no receipt`;
- `tooling/check_long_horizon.py` now gates this state, journal and hash pair,
  and `tooling/gate.sh` runs the exercise verifier, so the evidence cannot drift
  silently.

Still not proved, and why:

- **Deferred to November -- deployed harness run and LH-13 A/B.** dsh and zcode
  are inactive and will not be deployed in this cycle (`dsh` regains usage in
  November; `zcode` has no date and is not applicable this cycle), so this is a
  deferral rather than a blocked operator action. Neither is deployed on this
  host: `docker ps -a` has no container named `dsh`, `zcode`, `deepseek-harness`
  or `goose-harness`, and the Docker endpoint is a read-only socket proxy
  (`paseo-ds-proxy`: `CONTAINERS=1`, `POST=0`, `EXEC=0`, `BUILD=0`). A harness
  cannot be started from this host, and starting or restarting a production
  container is out of scope for this work package. No harness metric is claimed.
- **No LH-13 metrics.** Units per hour, tokens per verified unit, checkpoint
  recovery time, stall count, drift events and escaped defects are not measured.
  There is no model in the loop, and the `budget` values in the exercise view are
  declared constants.
- **No recovery time and no crash.** Both sessions ran back to back; nothing
  restarted, compacted or died. Probe 2 fabricates the shape of an interrupted
  side effect, it does not produce one.
- **No concurrency.** One writer. Nothing here says two sessions can share a
  state file.
- **No task difficulty.** The units derive a list from a JSON contract on
  purpose. This tests the state machine, not endurance or planning quality.

Runtime decision (WP-09 step 3): `lease`, `## In-flight` and idempotency keys
stay recorded fields with mechanical file-layer checks, not runtime services.
The exercise is single-writer and file-based, and the validator already rejects
a `done` run with a planned side effect, an expired lease, a non-canonical
in-flight state, and a duplicate `action_id`. Exclusivity, key honesty and
checkpoint timing need an owner the library does not have -- a supervisor, a
lock or a durable queue -- and the only place that owner could live today is the
blocked harness. Inventing a service here would add an unowned dependency. The
one gap that was closable without a service, the view/journal hash comparison,
is now enforced. No new phase and no runtime service.

`standards/long-horizon-runs.md` LH-14 is unchanged. It already says a view
whose hash differs from the last checkpoint is stale; the missing piece was a
command, not a rule. Naming the flag in the standard is a standard edit, which
`CONTRIBUTING.md` ties to a schema version bump, and the schema is not changing
here (the skill's run-state example and the gate's anchor both pin `1.1.0`).
`--state` is documented in the tool, in the exercise README, and here.

Two contract findings are recorded, not fixed, because both are schema
migrations: the journal has no `resume` kind (a resume is a `note` plus replay,
`events.jsonl` seq 6), and a `checkpoint` event has no `next_action` field even
though LH-14 says replay rebuilds it. The convention used by the exercise is
that the checkpoint `result` ends with `; next <action>`, and `--verify` fails if
the rebuilt value disagrees with the view.

## 7. Verification

Run `make gate`. The long-horizon step checks the standard, schema, evidence
register, orchestrator duties, workflow cross-reference, exemplar, KB links,
skill anchors, and the exercise state/journal/hash triple.
`tooling/run_state.py check exemplars/run-state-example.md` must exit 0, and so
must `python3 evals/long-horizon/drive.py --verify`.

## 8. Sources

See `standards/evidence/long-horizon-2026-10.md` for the full register:
METR time horizons (L1); Anthropic long-running harness (L2); Anthropic context
engineering (L3); UltraHorizon (L4); Long-Horizon-Terminal-Bench (L5); Temporal
durable execution (L6); state drift (L7); goal drift (L8); context rot (L9);
long-horizon benchmark field guide (L10); parallel sub-agents in long-horizon
coding (L11).
