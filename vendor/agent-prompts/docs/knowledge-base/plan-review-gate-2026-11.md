# Plan-review gate (2026-11-03)

Status: implemented, static evidence only. Operator direction: a loop where a
plan can go straight to implementation is a loop that discovers spec defects at
the most expensive point. Every spec is therefore reviewed before it is
implemented, and the review repeats until it is clean.

Scope: the workflow loop itself (`standards/workflow-loop.md`), the doctrine
fragment carried by every prompt, the verdict contract, the run state, the
executable guards, and every live document, skill, and projection that names a
phase.

## 1. The decision

`PlanReview` is a phase, not a sub-step of `Review`.

| Option | Why not |
|---|---|
| Fold the plan check into `Review` | `Review` audits a diff; a plan has no diff, no changed lines, and no test output. One gate name for two artifacts hides whether the plan was ever read. |
| Make it a checklist inside `Plan` | A checklist the author runs inside the authoring phase is not a gate: nothing records it, nothing can fail it, and nothing blocks the transition. |
| Add a plan-review track to the review contract | The track set is changed-line scoped (CR-02, CR-04). A track child cannot quote a line of a spec that does not exist yet. |
| **A seventh phase with its own gate record** | Chosen. The state machine refuses `Plan -> Implement`, the ledger refuses that `next`, and the verdict contract refuses a plan claim without the six checks. |

Cost accepted: +1 phase in every phase map, ~97 tokens per carrier from the
doctrine bullet (fragment 1.4.0 -> 1.5.0), one more gate enum value, and a
record per unit. Benefit: a defect is found when it costs a spec edit, not a
re-implementation.

## 2. What the gate checks (WL-15)

Six fixed checks, each a `MUST` criterion in the record:

| Check | Fails when |
|---|---|
| `goal` | the goal is a question, has two readings, or the scope boundary is unstated |
| `request-coverage` | a request item has no unit, or a unit traces to nothing in the request |
| `acceptance` | a unit has no checkable criterion, or the criterion came from the intended implementation |
| `verification` | a MUST criterion names no existing check, or the author wrote that check in this attempt (VI-02) |
| `ownership-order` | two units write one surface, the order contradicts a dependency, or an operator-gated step is unmarked |
| `risk-halt` | an unsafe, blocked, or unresolvable item is not named with the question the operator must answer |

Severity is structural: a failed check is high, a spec that omits the statement
the check needs is medium, wording is low. `pass` requires no open or waived
high/medium finding plus coverage of every spec section the record declares.

The verifier is a clean-context reader where one exists. Where it does not, the
author runs the same fixed checklist as `verifier_kind: mechanical` with
`defined_by` pointing at WL-15 and `authored_in_this_attempt: false`. That is
VI-02's mechanical-verifier path, not an exemption: the checklist predates the
attempt, so the gate is never waived for lack of a second context.

## 3. Rounds, and the one place the bound changes

WL-07 bounded every gate at one refinement. The plan gate is exempt from the
count and bound by progress instead:

- `Fix -> PlanReview` repeats until a round is clean.
- Every round records `PRIOR ROUND <n> FAILED: <check>` and `CHANGED: <what the
  spec now says>`; `attempt` is the round number.
- A round that repeats the previous change, or leaves the same check failing
  with no spec edit, is `halt` with reason `stalled`.

So "fix until error-free" is enforceable and terminating: the loop stops on
success or on a proven absence of progress, never on a rule-of-three that
abandons a fixable spec. The code gates (`Review`, `Verify`) keep the
one-refinement bound: there the change is expensive and a second blind attempt
is worse than escalation.

## 4. Enforcement points

| Surface | What now refuses the skip |
|---|---|
| `standards/workflow-loop.md` WL-02 | no `Plan -> Implement` row exists; `PlanReview -> Implement` requires the record |
| `tooling/check_workflow_loop.py` | `REQUIRED_TRANSITIONS` contains `Plan -> PlanReview` and `PlanReview -> Implement`; `ALLOWED_TRANSITIONS` excludes `Plan -> Implement`; a ledger row whose `next` is `Implement` at `Plan` fails; the doctrine block must state the gate, the round rule, and `stalled`; a carrier that owns `PlanReview` must be a gate authority |
| `tooling/validate_templates.py` | `OWNED_PHASES` accepts `PlanReview` only as a canonical phase |
| `standards/gate-verdict.schema.json` | gate enum `plan-review`; `attempt` is the round number only at that gate |
| `tooling/check_gate_verdict.py` | a `plan-review` record needs all six check ids, a `coverage.basis`, and a verifier that is not `self`; a round above 0 needs the round pair |
| `evals/loop/drive.py` | four gate guards and three round scenarios, each with its expected rejection reason, including "a diff record is not a plan record" and "no CHANGED line" |
| `fragments/agent-doctrine.md` 1.5.0 | the loop line, the gate bullet, and the round rule in every carrier |
| `tooling/check_model_surface.py` | the grown fragment and role bodies keep a hard token cap, so the gate text cannot quietly double |
| `standards/run-state.schema.json` 1.2.0 | `phase: PlanReview` is a valid active/blocked run phase |

## 5. Surface inventory touched

- Standards: `workflow-loop.md` (WL-01..WL-05, WL-07..WL-09, WL-11..WL-13, new
  WL-15), `agent-prompt-standard.md` (AP-14), `verification-integrity.md`
  (VI-01, VI-12, VI-13), `code-review-contract.md` (CR-01 scope note),
  `stop-gate.md` (SG-01), `long-horizon-runs.md`, `subagent-delegation.md`,
  `work-authorization.md` (cross-ref).
- Contracts: `gate-verdict.schema.json` 1.1.0, `run-state.schema.json` 1.2.0,
  `model-surface.json` 1.1.0.
- Prompts: 38 role templates and 3 task prompts (doctrine byte-exact,
  `owned_phases`, version bump, `updated`), 4 dsh presets, the `orchestrate`
  command, `docs/TEMPLATE-GUIDE.md`.
- Tooling: `check_workflow_loop.py`, `check_gate_verdict.py`,
  `validate_templates.py`, `run_state.py`, `check_run_journal.py`,
  `check_long_horizon.py`, `measure_state.py` outputs.
- Evals: `evals/loop/drive.py` (20 scenarios), `evals/loop/README.md`,
  `exemplars/gate-verdict-plan-review.json`, `evals/long-horizon/` fixtures
  (schema version), two test modules.
- Projections and records: `omp/catalog.yaml` pins, `CATALOG.md` pins,
  `docs/measured-state.md`, `PLAN.md`, `CHANGELOG.md`,
  `packs/containeromat.md`.
- Skills: `long-horizon-run`, `subagent-delegation`, `grilling`,
  `operator-setup-interview` doctrine positions.

## 6. What this does not prove

- No model was run. This is a static change: rules, contracts, and executable
  guards. The gate's effect on plan quality is unmeasured (WL-12: plan-review
  rounds per unit and escaped defects are the measures; a run with zero rounds
  is a gate that is not reading the spec, not a good plan).
- The mechanical path is weaker than a clean-context reviewer: it checks the
  presence and decidability of spec statements, not whether the stated design
  is the best one. A single-agent unit gets the former, not the latter.
- `PlanReview` is a phase in this library. A consumer's deployed prompts only
  change after a re-vendor; until then its runtime still runs the six-phase
  loop, and its own gates will not know the gate.
