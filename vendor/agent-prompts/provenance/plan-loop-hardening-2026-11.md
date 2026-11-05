# Plan: hard loop enforcement for every consumer and vendor

Status: active. Effective: 2026-11-03. Owner: library maintainer. Rules:
`standards/workflow-loop.md` WL-15 (plan review), WL-02 (transitions).

Unit under change: `loop-hardening`. This spec is reviewed by the plan-review
gate before any of it is implemented; its verdict is
`provenance/verdict-plan-review-loop-hardening.json`.

## Goal

Make "no implementation without a clean plan review" a check that fails a build
in every consumer and every vendor projection, instead of a sentence in a
prompt, and record each vendor's real strength honestly.

## Scope boundaries

- In scope: two vendor-neutral checkers (`check_plan_spec.py`,
  `check_loop_gate.py`), adapter parity in `check_workflow_loop.py`, an admission
  capability that names what a runtime actually enforces, consumer wiring
  (gate script, pack, re-vendor runbook, README of each projection), and this
  unit's own loop artifacts.
- Out of scope: editing a runtime (OMP, dsh, Kilo, OpenCode, Paseo) itself; a
  pre-dispatch hook that lives in a host process this library does not own;
  rewriting historical ledgers or verdicts; any claim of behavioral compliance
  without a measurement.

## Request coverage

| Request item | Unit | Why |
|---|---|---|
| "Hebe auf hart fuer alle Konsumenten / Vendors" | U1, U2 | a spec gate and an ordering gate that any consumer can run and that fails the build |
| Every projection must name the gate | U3 | dsh presets and carriers were covered; commands and the OMP foreground policy were not |
| Vendor strength must be a checked fact, not prose | U4 | an admission capability per runtime, fail-closed |
| Consumers must know how to wire it | U5 | gate script, pack, re-vendor runbook, projection READMEs |
| Use the loop for this change | U6 | the unit produces its own plan-review verdict, findings, and ledger row |

## Units

| Unit | Acceptance | Verification | Owner |
|---|---|---|---|
| U1 | MUST: `check_plan_spec.py` reports the six WL-15 checks per spec file and exits nonzero when one fails; MUST: `--json` emits `{path, checks[{id,state,detail}], ok}` so a verdict record can embed it | `python3 -m pytest tooling/tests/test_check_plan_spec.py -q` | library maintainer |
| U2 | MUST: `check_loop_gate.py` refuses a unit that reached Implement without a clean `plan-review` verdict, refuses Push without a verify pass, orders a unit's rounds by `attempt` and requires them contiguous from 0, and skips ledger rows older than the effective date (default `2026-11-03`, `--since` override); MUST: `--verdict` accepts a list | `python3 -m pytest tooling/tests/test_check_loop_gate.py -q` (the module is a declared U2 artifact) | library maintainer |
| U3 | MUST: `check_workflow_loop.py` requires a `Doctrine:` line naming the owned phases on every command outside a closed, self-pruning exemption set, and requires the **composed** OMP foreground set to state the plan-review gate exactly once (one module carries it, not all six); SHOULD: the check reports which module carries it | `python3 tooling/check_workflow_loop.py` | library maintainer |
| U4 | MUST: an admission record must declare `loop_gate`, and `admitted` plus `supported` requires evidence naming a pre-dispatch or CI gate | `python3 tooling/check_admission.py omp/admission.json` | library maintainer |
| U5 | MUST: the gate script, the pack, the re-vendor runbook, and each projection README name both commands and their failure meaning; MUST: `docs/measured-state.md`, `CATALOG.md`, and the projection pins are refreshed in the same change | `bash tooling/gate.sh` (it runs `measure_state --check`) | library maintainer |
| U6 | MUST: this unit has a plan-review verdict whose last round is clean, a findings ledger for the rounds it took, and one WL-08 row whose artifact cell names this spec | `python3 tooling/check_loop_gate.py --ledger provenance/ledger-loop-hardening-2026-11.md --verdict provenance/verdict-plan-review-loop-hardening*.json` | library maintainer |

## Ownership and order

One writer for the whole unit (library maintainer): the two checkers, the
parity extension, the admission records, and the consumer documents share
`tooling/gate.sh` and `standards/agent-adapter.md`, so splitting them across
writers would need a sequence for no gain.

1. U1 -- the spec gate first: without it, the plan review of every later unit is prose.
2. U2 -- the ordering gate: it consumes verdict records, so it needs the record shape U1 emits.
3. U3 -- adapter parity: cheap, independent, catches a surface that omits the gate.
4. U4 -- admission: the vendor matrix, written after U2 exists so `degraded` means something checkable.
5. U5 -- consumer wiring: last, because it quotes the final command lines.
6. U6 -- artifacts: updated as the units land, verified with U1 and U2 themselves.

## Risks and halts

| Risk | Halt path | Operator question |
|---|---|---|
| Historical ledgers have no plan-review evidence, so a strict ordering gate would fail on the record it should grandfather | HALT, no code written | none: resolved by the effective date U2 defines (default `2026-11-03`, `--since` override) |
| A library cannot intercept a dispatch inside a host process; claiming otherwise would be the exact "stated rule, not an enforced one" failure | HALT | accept `degraded` admission for runtimes without a pre-dispatch hook, or fund a host hook in the consumer |
| Requiring the full doctrine block in the OMP foreground policy would duplicate text and breach its 700-token cap | HALT | none: the spec asks for one loop sentence there, not the block |
| A parity check on commands would fail the three style/status utilities | HALT | none: closed, self-pruning exemption set in the spec |

None of these blocks the units above: each has a stated resolution, so the plan
proceeds to Implement after the plan-review gate passes.
