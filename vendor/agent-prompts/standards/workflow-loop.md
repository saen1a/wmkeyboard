# Workflow loop standard (WL-01..WL-15)

Status: ACTIVE (2026-10-25; plan-review gate added 2026-11-03). Applies to every
library role, task prompt, orchestrator, and delegated subagent; live consumer
copies are outside this repository and must be re-vendored. The canonical
doctrine fragment is the prompt-level form; this standard is the normative state
machine.

## WL-01 -- States and outcomes

The loop has seven phases: `Plan`, `PlanReview`, `Implement`, `Review`, `Fix`,
`Verify`, `Push`. It has four outcomes: `Ready`, `Ready (unverified)`, `Done`,
`HALT`. Outcomes are not phases and do not create an eighth phase.

- **Ready** -- the agent has passed Verify and is waiting for the operator.
- **Ready (unverified)** -- a recorded exemption covers a missing check; the
  claim stays unverified and the operator decides at Push.
- **Done** -- the operator approved, the finalize action completed, and, for a
  Git finalize, WL-14 publication proof is recorded.
- **HALT** -- blocked, unsafe, unresolvable, or over the refinement bound.

`Push` is the finalize phase and is operator-gated. An agent enters `Push` only
after an explicit operator `go`; without that `go` it stops at `Ready`. The
agent may perform the commit/push/handoff only when its permissions and the
operator both allow it; otherwise the operator performs it and the agent
records the result.

`owned_phases` means artifact ownership, not tool permission. A read-only
research/report role may own non-mutating `Implement`/`Fix` artifacts but never
`Push`; a review-only role owns `Review` (findings), not `Fix` (patch). The
orchestrator checks `tool_profile` before dispatching a writer; no agent is
dispatched to execute a phase it cannot perform.

Vocabulary aliases are fixed:

- **Research is inside Plan.** It ends at a decision-complete spec.
- **Plan review is the spec gate.** It runs on every unit before Implement, is
  never skipped, and repeats until no open high or medium finding remains
  (WL-15).
- **Review is the audit gate.**
- **Push is the finalize gate.**

## WL-02 -- Transitions and guards

| From | Guard | To |
|---|---|---|
| Plan | Decision-complete spec: goal, units, acceptance, verification, research sources/dates | PlanReview |
| Plan | Unsafe, blocked, or one refinement cannot resolve | HALT |
| PlanReview | No open or waived high or medium plan finding, and the `plan-review` verdict record proves the review ran (VI-01, VI-02) | Implement |
| PlanReview | High or medium plan finding | Fix |
| PlanReview | Unresolvable conflict, missing authority, or a round that changes nothing | HALT |
| Implement | Complete diff, notes, one writer per shared surface | Review |
| Implement | Blocked, unsafe, or out of scope | HALT |
| Review | No open or waived high or medium finding, and the verdict record proves the review ran (`verification-integrity.md` VI-01, VI-02) | Verify |
| Review | High or medium finding | Fix |
| Review | Unresolvable conflict or missing authority | HALT |
| Fix | Patch answers every finding; spec still valid | Review |
| Fix | Plan-review finding answered with a spec patch and a `CHANGED` line | PlanReview |
| Fix | The spec itself is wrong, not the code; first return only | Plan |
| Fix | A second spec-gap return | HALT |
| Fix | Same code gate still blocked after one refinement | HALT |
| Verify | A valid verdict record: fresh output, exit code and artifact prove every criterion, no check skipped, coverage at or above the floor (VI-03, VI-08) | Ready |
| Verify | A recorded exemption covers the missing check; claim marked unverified | Ready (unverified) |
| Ready (unverified) | Explicit operator `go` | Push |
| Ready (unverified) | Explicit operator decline | HALT |
| Verify | Any criterion fails, or a MUST criterion is unmet, and the repair is in scope and safe; the record names the failing check (VI-05, VI-12) | Fix |
| Verify | A check could not run and no exemption covers it: record it as skipped and stay | hold |
| Verify | The proof harness itself is unsafe or out of scope for the gate | HALT |
| Ready | Explicit operator `go`, with the verdict record attached to the finalize (VI-01) | Push |
| Ready | Explicit operator decline | HALT |
| Push | Finalize succeeds and, for a Git finalize, WL-14 publication proof is recorded | Done |
| Push | Finalize action fails | HALT |

`Done` and `HALT` are terminal for the forward path; `Ready` and
`Ready (unverified)` are wait states. An unverified Ready is not Done.
No operator answer is `hold`: remain in `Ready`; only an explicit decline is
`HALT`.
Recovery actions after HALT (rollback, cleanup) are recorded, not new phases.
A report-only unit that hands an artifact to its parent closes at `Ready`
without `Push`; the parent owns the next transition. A new unit starts at Plan;
a subagent never starts a second unit.

## WL-03 -- Back-edges are mandatory

- `Plan -> PlanReview -> Implement` is the only forward path into Implement.
  There is no direct `Plan -> Implement` transition, in prose or in a ledger.
- `PlanReview -> Fix -> PlanReview` is a loop, not a one-way handoff. It repeats
  until the plan review is clean; the round count is not capped, the progress
  requirement is (WL-15).
- `Review -> Fix -> Review` is a loop, not a one-way handoff.
- `Verify -> Fix -> Review -> Verify` is the proof loop. Code changed during
  Fix must re-enter Review before Verify.
- `Fix -> Plan` is allowed only when the spec is wrong, not when the code is
  wrong.
- `PlanReview`, `Review`, or `Verify` failures must return exact findings or
  evidence, not a summary.

## WL-04 -- Evidence at every transition

Every transition carries an artifact and evidence:

- Plan: spec and research source/date.
- PlanReview: findings with severity and evidence, or a clean pass recorded as a
  `plan-review` gate verdict (`verification-integrity.md`, VI-01); each repair
  round carries `PRIOR ROUND <n> FAILED` / `CHANGED:` (VI-12).
- Implement: diff and changed-file list.
- Review: findings with severity and evidence, or a clean pass recorded as a
  gate verdict (`verification-integrity.md`, VI-01).
- Fix: patch plus a response to each finding.
- Verify: command, output, exit code, scope, harness, model -- carried in the
  verdict record, not only in prose.
- Push: operator approval and closeout record.

A summary is not evidence. Silence is not a pass.

## WL-05 -- Clean-context audit and exemptions

The PlanReview, Review, and Verify agent receives the artifact, acceptance
criteria, and evidence commands, not the author's reasoning or conclusion. The
author is never the only verifier.

Where a second context is impossible (single-agent, tabletop, research, or
documentation-only work), use one of:

1. a mechanical check (test, linter, schema, validator, exit code);
2. a clean-context verifier;
3. an explicit recorded exemption that names the missing check and marks the
   claim `unverified`.

An exemption is a recorded limitation, not a pass. It closes Verify as
`Ready (unverified)`; the operator decides at Push, and the claim is never
reported as `verified`.

The plan review has one advantage over the code review: its checklist is fixed
by this standard (WL-15), so a single agent can run it as a mechanical verifier
with provenance -- the checklist predates the attempt. That is not an exemption
and it is not self-certification; it is VI-02's `verifier_kind: mechanical`
path. The plan review is therefore never waived for lack of a second context.

## WL-06 -- Single writer

One writer per shared file, module, or decision space. Parallelize reads,
searches, and independent reviews only. If two units must write, sequence them
or give one ownership and the other a read-only role.

## WL-07 -- Refinement bound

This section is the single authority for how many attempts a gate gets;
`verification-integrity.md` VI-13 states only the verdict-side consequence.

- The bound applies to the **code gates** (`Review`, `Verify`): one refinement
  per gate, then escalate. Do not run unbounded repair loops there, and do not
  introduce a per-gate cycle budget: the bound is the same for both, which is
  why `attempt` is `0` or `1` at those gates (WL-08).
- The **plan-review gate is not capped in rounds**: it repeats until no open
  high or medium finding remains, because a plan defect found later is paid for
  by the whole implementation (WL-15). It is bounded by progress, not by a
  count: every round names what changed, and a round that leaves the same
  finding open with no spec change is `halt` with reason `stalled`.
- An extra clean-context verification cycle needs an operator decision recorded
  in the ledger; it is not an agent's call.
- Every attempt carries the `PRIOR ATTEMPT <n> FAILED` / `CHANGED:` pair (VI-12);
  a plan-review round uses the same pair with `PRIOR ROUND <n> FAILED`.
- `Fix -> Plan` is allowed once per unit and consumes the unit's code-gate
  bound; after one return, HALT.
- Record the unresolved decision and the exact evidence in the ledger.

## WL-08 -- Ledger

The orchestrator keeps one durable row per unit:

```text
unit_id | phase | attempt | gate | status | artifact | findings | evidence | decision | owner | timestamp | next
```

- `attempt`: the refinement attempt at the current gate -- `0` or `1` at a code
  gate, the round number at `PlanReview` (WL-15). The row is a snapshot of
  current state; earlier gate attempts are in the commit history.
- `gate`: `pass | fix | hold | halt`.
- `phase`: the last executed phase.
- `status`: the current phase or terminal outcome (`Ready (unverified)` is a
  wait state, not Done).
- `next`: the committed next transition; on `hold`, `next` equals `status`.
- `evidence`: command, exit code, timestamp, scope, harness, model.
- `findings`: id, severity, evidence, acceptance impact, owner.
- `decision`: pass, fix, hold, halt.

The ledger is a row in the active `PLAN.md` wave entry or a
`provenance/ledger-<task>.md` file. Resume from it, not chat memory.

## WL-09 -- Gate vocabulary

Use one gate vocabulary in the orchestrator ledger and gate decisions; component returns map to it. `hold` is a decision to remain in the current state, not a transition:

| Gate | Meaning |
|---|---|
| `pass` | Guard met and the verdict record proves it (`verification-integrity.md` VI-01..VI-09 [subset]); proceed to the next phase |
| `fix` | Findings or failed proof in scope; enter Fix |
| `hold` | Waiting for operator or missing input; stay in the current state; not a pass |
| `halt` | Blocked, unsafe, unresolvable, or over the bound |

Each gate owes a different minimum in its record (`gate-verdict.schema.json`,
`gate` field):

| Gate | The record must carry | Rule |
|---|---|---|
| `plan-review` | what was inspected: every spec section with its verdict, or the six WL-15 checks with their state; a verifier that did not write the spec; coverage of the plan's declared surface | VI-01, VI-02, WL-15 |
| `review` | what was inspected (findings, or criteria when clean), coverage of the tracks, a verifier that is not the author | VI-01, VI-02 |
| `verify` | at least one check with command, exit, freshness; every MUST criterion state; coverage and its floor; no skipped check | VI-03, VI-05, VI-08 |
| `acceptance` | at least one MUST criterion taken from the request, the measured surface, and any degraded gap | VI-05, VI-10 |
| `run` | the run-scope command, exit, timestamp and evidence, mirrored to the run state's `run_gate` | LH-10 |

Map legacy labels:

- `pass_with_warnings` -> `fix` if any warning is high/medium, else `pass`.
- `APPROVE WITH SUGGESTIONS` -> `pass` only if no high/medium remains.
- `NEEDS CHANGES` -> `fix`.
- `blocked`, `rolled_back`, `escalation_required` -> `halt`.
- `CRITICAL` / `WARNING` / `SUGGESTION` -> high / medium / low.
- `fail`, `findings` -> `fix`; `no_changes` -> `pass`;
  `NEEDS_CONTEXT` -> `hold`.
- `complete` -> `Ready`; `committed` after an approved Push -> `Done`.
- A review verdict `DONE` -> `pass` for that review, not the unit outcome `Done`.
- `APPROVE`, `NO_FINDINGS`, `CONFIRM` -> `pass`; `NOT DONE`, `REVISE` -> `fix`;
  `BLOCKED`, `REJECT` -> `halt`. Labels are case-insensitive.
- `DONE_WITH_CONCERNS` -> `fix`; `ready_for_operator` -> `hold` (stay in Ready).
- `Ready (unverified)` -> `hold` until the operator decides at Push.
- A plan verdict `PLAN APPROVED` / `SPEC READY` -> `pass` at gate `plan-review`;
  `PLAN REVISE` / `SPEC GAP` -> `fix`; `PLAN BLOCKED` -> `halt`.

## WL-10 -- Finalize

`Push` is not a generic completion claim. It requires:

- explicit operator approval;
- the evidence bundle from Verify, including its verdict record
  (`standards/gate-verdict.schema.json`);
- harness, model, and seed metadata;
- the changelog or ledger update;
- the rollback or retirement note where relevant.

Without those, the state is `Ready`, not `Done`.

## WL-11 -- STOPP exception

When the consumer has adopted STOPP, the fast path (`SG-01..SG-09`) may skip
Review only for a one-file
comment, format, or typo change that it classifies as non-behavioral. Any code,
config, schema, or behavior change outside that narrow path re-enters Review
before Verify. Rollback is the action after a HALT or an unsafe failure; it is
not the normal Verify-failure path.

The fast path does not weaken the plan-review gate, and it never skips it: the
fast path has no Plan phase at all, so it writes no spec and has nothing to
review (`SG-02`). A unit that writes a spec -- including one written to justify
a "small" change -- enters `PlanReview` before Implement. There is no
classification that turns a spec into a fast-path edit.

## WL-12 -- Evaluation

Every workflow change is an experiment. Use a pre-registered protocol:

- pin both arms by body hash or git ref;
- use the same tasks, seeds, model, harness, and token budget for both arms;
- retry only on empty/error, and record every attempt;
- record `max_tokens`, temperature, doctrine version, and prompt hashes;
- exclude a task only for a stated structural reason, before the run;
- publish a result manifest with the raw result location.

Measure gate pass rate per gate, plan-review rounds per unit, escaped defects,
rework cycles, evidence completeness, handoff failures, tokens, wall-clock, and
cache hit rate. A workflow change without a baseline is an anecdote. A
plan-review gate whose rounds are always zero is not evidence of a good plan; it
is evidence that the gate is not reading the spec.

## WL-13 -- Findings ledger

Every PlanReview, Review or Verify finding gets a stable id in one findings
ledger per unit: `provenance/findings-<task>.md`. A finding is not a prose
paragraph that disappears on the next round.

Columns:

`finding_id | severity | unit | file_line | evidence | acceptance_impact | owner | state | round | decision`

- `finding_id`: `F-<n>`, unique and never reused.
- `severity`: high, medium, or low.
- `state`: `open`, `fixed`, or `waived`.
- `fixed` requires evidence from a re-review; `waived` requires an explicit
  operator decision and rationale, not the author's judgment.
- `round`: the review or verify attempt that produced or resolved the finding.
- Do not delete a finding. Change its state and append the resolution evidence.
- Review may pass only when no high or medium finding is `open` or `waived`; a
  waiver is a recorded limitation, not a pass.
- The WL-08 `findings` cell is a summary. It must name this ledger
  (`findings-<task>.md`) or record `none` when the review produced no finding.
- A review with no findings writes no ledger and records `none`; "no file" is
  not a clean pass unless `none` is recorded.
- A Verify failure either references an existing finding or opens a new one.

A waived high/medium finding is recorded as a limitation; it does not become a
pass. The same operator gate applies at Push (`Ready (unverified)`).

## WL-14 -- Publication proof

`Done` is a publication fact, not a push claim.

For a Git-backed finalize, record in the WL-08 ledger row, or in the run
state's `## Decisions` section when the run owns the state:

- the implementation commit;
- the landing ref or merged pull request;
- the proof that the commit is contained in that ref (ancestry, merge commit,
  or provider merge record);
- the verifier and timestamp.

A pushed branch, an open pull request, or an agent statement that it pushed is
`Ready`, not `Done`. If the finalize is a handoff, record the recipient and the
handed artifact; the recipient owns the onward publication. A failed or
unconfirmed publication is `HALT` or `Ready`, never `Done`.

The run-state validator checks unit closure and gate shape, not publication; a
`Done` unit still needs the WL-14 proof in the ledger (or `## Decisions`).

## WL-15 -- Plan review gate

Every unit enters `PlanReview` before `Implement`. The gate is not optional, not
folded into Implement, and not waived: the forward path is
`Plan -> PlanReview -> Implement`, and no other row exists (WL-02, WL-03).

- **Artifact.** The decision-complete spec from WL-02 -- goal, units,
  acceptance, verification, research sources/dates -- together with the request
  it answers. The reviewer reads the spec, the request, and the repository
  facts the spec claims; never the author's reasoning for it (WL-05).
- **Verifier.** A clean-context verifier that did not write the spec, where one
  exists. Where it does not, the author runs the fixed checklist below as
  `verifier_kind: mechanical` with `defined_by` pointing at this section and
  `authored_in_this_attempt: false` (VI-02). The checklist is defined here,
  before any attempt, so a single-agent unit has no exemption path at this gate
  and a `verifier: "self"` record is invalid here.
- **The six checks.** Each is a criterion in the `plan-review` verdict record;
  all are `MUST` unless stated:
  1. `goal` -- one decidable goal statement with no open question in it, plus
     the scope boundaries: what the unit will not touch.
  2. `request-coverage` -- every request item maps to exactly one unit, and
     every unit traces back to a request item: no dropped requirement, no
     invented scope.
  3. `acceptance` -- each unit carries at least one checkable criterion marked
     MUST or SHOULD, taken from the request rather than from the intended
     implementation (VI-05).
  4. `verification` -- every MUST criterion names a command, test id, or
     artifact check that exists today and was not authored in this attempt; a
     check that cannot run is recorded `unverified`, never assumed.
  5. `ownership-order` -- one writer per shared surface, units ordered by
     dependency, and the operator-gated steps named (WL-06, WA-04).
  6. `risk-halt` -- unsafe, blocked, or unresolvable items are named with the
     HALT path and the question the operator must answer (HF-01).
- **Severity and outcome.** A failed check is high severity by construction --
  a plan defect is paid for by the whole implementation. A spec that omits a
  statement the check needs is medium; wording is low. `pass` requires no open
  or waived high or medium finding, a record per VI-01, and coverage of every
  spec section the record declares.
- **Rounds.** `Fix -> PlanReview` repeats until a round is clean (WL-07). Each
  round records `PRIOR ROUND <n> FAILED: <check>` and `CHANGED: <what the spec
  now says>`, and carries `attempt` = the round number. A round that repeats the
  previous change, or leaves the same check failing with no spec edit, is
  `halt` with reason `stalled`.
- **Bounds of the gate.** It reviews the plan, not the code: naming a file the
  plan will edit is in scope; writing or patching that file during PlanReview is
  not, and is `halt` (the author resumes at Implement).
- **Not a prose pass.** `PLAN APPROVED` and `SPEC READY` map to gate
  `plan-review` verdict `pass`; `PLAN REVISE` and `SPEC GAP` map to `fix`;
  `PLAN BLOCKED` maps to `halt` (WL-09). A verdict without the record is not a
  gate.
- **Machine half.** The spec shape and the six checks are executable:
  `tooling/check_plan_spec.py` (spec -> six check states, nonzero on a failure)
  and `tooling/check_loop_gate.py` (ledger + verdicts -> refuse an Implement
  unit without a clean plan-review record, a non-contiguous round sequence, or a
  finalize without a verify pass). Shape and wiring: `../docs/PLAN-SPEC.md`.
  Both run in `tooling/gate.sh`; a consumer runs them where it commits.

## Long-horizon layer

A run that exceeds one context window, one session, or one operator sitting is
governed by `long-horizon-runs.md` (LH-01..LH-14). That layer adds durable run
state, checkpoints, resume, budgets, progress and drift checks above the unit
loop. It does not add a phase, change a transition, or weaken a gate: every
unit still uses WL-01..WL-13 [subset] and WL-15, and every finalize uses WL-14.

## Cross-refs

- `../fragments/agent-doctrine.md` -- prompt-level loop fragment
- `agent-prompt-standard.md` -- AP-14
- `subagent-delegation.md` -- SD-01..SD-12
- `long-horizon-runs.md` -- LH-01..LH-14, run state, journal, and checkpoints
- `run-state.schema.json` -- machine-readable run-state contract
- `code-review-contract.md` -- CR-01..CR-13 (the Review gate; the plan review is
  WL-15 and does not use the CR track set)
- `halt-taxonomy.md` -- HF-01..HF-15
- `verification-integrity.md` -- what a `pass` verdict must contain (VI-01..VI-15)
- `prompt-security.md` -- untrusted material is data inside the loop (PS-01..PS-14)
- `stop-gate.md` -- SG-01..SG-09
- `../docs/knowledge-base/workflow-loop-2026-10.md` -- design analysis and
  evidence
