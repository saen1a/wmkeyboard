# External project scan (2026-10)

Status: research note, library-side only. Scope: evaluate three public projects
for quality patterns worth adopting into this library, and record why a pattern
was adopted, deferred, or rejected. No benchmark result, formula, or vendor
claim is adopted without a checkable artifact in this repository.

Method: each repository was cloned at the commit below and read from source and
docs. Adoption required a rule, a checker, or a schema that the library gate can
verify. A pattern that only exists as prose in another project is recorded as
considered, not adopted.

| Project | Snapshot | Read |
|---|---|---|
| `bahdan111/stepbook` | `3f556d1cc4c40ceb6a25943609b206fde5a7f8f1` (2026-10-11) | `README.md`, `docs/runs.md`, `docs/cli.md`, `docs/adapter.md`, `stepbook/contracts/journal.py` |
| `RunWield/runwield` | `98fbaeb3cd9c1044afd4f5f4a72d46ddc0e86179` (2026-10-24) | `README.md`, `docs/plan-lifecycle.md`, `docs/validation-authority.md`, `docs/engineering-quality-principles.md`, `docs/evaluation/` |
| `julianjohnson-web/julianflux-research` | `b0505320a6a2d316b81ca75ddd56ca6c5706e196` (2026-10-14) | `README.md`, `scale_ab_benchmark.py`, `julianflux_engine.py`, `julianflux_educational_mvp.py` |

## Adopted

| Pattern | Source | Landed in | Why |
|---|---|---|---|
| Append-only event journal; run state is a materialized view; resume replays the journal; unknown or unmatched actions stop instead of re-running | stepbook | LH-14, `standards/run-journal.schema.json`, `tooling/check_run_journal.py`, `exemplars/run-journal-example.jsonl` | A hand-edited state file cannot prove what happened. An append-only journal can, and replay makes resume deterministic. |
| One action per event, with a result receipt and evidence | stepbook | LH-14 | Detects a side effect that started but never recorded a result; forces evidence at the boundary. |
| Stable findings ledger with ids that survive review rounds | RunWield Review Issue Ledger | WL-13, `exemplars/findings-ledger-example.md`, `tooling/check_findings_ledger.py` | Findings in prose get re-litigated or silently dropped; stable ids make closure and waiver auditable. |
| Publication proof, not a push claim | RunWield | WL-14 | "Pushed" and "done" are different facts. `Done` now requires landing proof. |

The journal and the findings ledger are run and workflow rules. They add no
seventh phase and do not change a WL-01 transition.

## Considered, not adopted

| Pattern | Source | Reason |
|---|---|---|
| Protected state paths and a maximum-deletion guard | stepbook | Useful, but it belongs to a consumer-side state writer. The library already pins acceptance in `run-state.schema.json`; adding a deletion budget needs a live harness to enforce it. Recorded as a consumer option. |
| Operator repair receipt as a separate file | stepbook | The journal's decision event covers the library-side rule. A separate receipt format is consumer tooling, not a portable standard. |
| Ceremony tiers that scale planning to risk | RunWield | This library already selects ceremony through presets, the STOPP gate, and the orchestrator's task classification. A second tier system would duplicate the owner. |
| Fresh-context repair after a failed review | RunWield | Already required by the review loop and `subagent-delegation.md`. No new rule was needed; the existing rule now cites stable finding ids. |
| A separate reviewer benchmark corpus | RunWield | Valuable but large. This library's `evals/` covers skill routing and the workflow loop; a reviewer corpus is a later, separate unit. |
| One durable owner per fact (authority matrix) | RunWield | The principle is already present in WL-08 and the run-state owner field. Restating it as a new rule would create a second owner for the same fact. |

## Rejected: JulianFlux

The repository presents a "Clifford manifold" retrieval engine and an
"electrodynamic" routing claim. The code does not support the benchmark headline,
and none of its numbers should be copied or cited as evidence.

Specific reasons:

1. **Synthetic corpus, preassigned labels.** `scale_ab_benchmark.py` builds a
   10,000-document corpus from a small list of operational templates plus random
   perturbations. The "poison" nodes are synthetic documents that contain the
   literal words `bankrupt` or `fabricated` (`scale_ab_benchmark.py:253`).
2. **The detector and the label use the same signal.** The NLI gate assigns
   `q = -1.0` to documents it judges contradictory
   (`scale_ab_benchmark.py:76-99`); the JulianFlux arm then counts a document as
   poison when `charge < 0` (`scale_ab_benchmark.py:291-296`). That is a
   round-trip of the model's own decision, not independent ground truth.
3. **The baseline is scored by the keyword rule.** The Euclidean arm is judged
   with the same `bankrupt`/`fabricated` substring test
   (`scale_ab_benchmark.py:253`), so the comparison measures the keyword rule,
   not retrieval quality.
4. **No external validation.** There is no held-out corpus, no human
   adjudication, no independent replication, and no confidence interval. The
   claimed "0% hallucination" is a property of the fixture, not of the method.
5. **The physics language is decorative.** The `E` field, Poynting flux, and
   Clifford bivectors are implemented as array operations with no derivation or
   ablation showing they beat a plain similarity baseline. Naming an operation
   after a physical law does not make it one.

Decision: do not adopt the math, the benchmark, the latency numbers, or the
"0% hallucination" claim. The repository is recorded here so a later agent does
not re-discover it and treat it as evidence.

## Limits

- This is a source read at one commit, not a reproduction of either accepted
  pattern. The library-side checkers prove shape and internal consistency, not
  that a consumer writes a correct journal.
- RunWield and stepbook are active projects; their docs may move. The commit
  hashes above are the pinned snapshot for this scan.
- No live harness, consumer re-vendor, or A/B run was performed for this scan.
  The new rules are library contracts until a consumer records journal and
  ledger evidence.

## Cross-refs

- `standards/long-horizon-runs.md` -- LH-14
- `standards/workflow-loop.md` -- WL-13, WL-14
- `standards/run-journal.schema.json` -- journal event contract
- `tooling/check_run_journal.py` -- journal validator
- `tooling/check_findings_ledger.py` -- findings ledger validator
- `docs/knowledge-base/long-horizon-agents-2026-10.md` -- run-layer synthesis
- `docs/knowledge-base/workflow-loop-2026-10.md` -- loop synthesis
