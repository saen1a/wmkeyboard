# Role doctrine experiment (design, not run)

Status: protocol and candidate text. The full `fragments/agent-doctrine.md` is
the only active doctrine. Update 2026-10-24: the active fragment is now the
v1.3.0 loop; the candidate and cost figures below are the pre-loop baseline for
any future compact-doctrine experiment.

Question: can the 16 roles that own two or fewer phases use a compact doctrine
without losing behavior, saving roughly 230 tokens per invocation?

Evidence: S20 (constrained prompting can help mid-tier models and induce
hyper-literalism in stronger ones), S1/S2 (capacity is tiered), AP-14 (the
fragment is byte-exact until a registered variant exists).

## Arms

| Arm | Doctrine | Cost |
|---|---|---|
| A (control) | current `agent-doctrine.md`, 352 tokens | baseline |
| B (candidate) | compact text below, target <= 140 tokens | about 210 tokens saved per invocation |

The compare is within-model: same model, same harness, same role, same task;
only the doctrine block changes.

## Candidate text (not active)

```text
Plan -> Implement -> Review -> Fix -> Verify -> Push.
Plan: state the outcome and constraints before acting.
Implement: make the smallest change that satisfies the plan.
Review: check the change against evidence, not intent.
Fix: repair what Review found; do not widen scope.
Verify: run the proof command now; no completion claim without it.
Push: only with fresh evidence and explicit operator approval.
The orchestrating prompt owns the sequence; hand off at your phase boundary.
```

## Roles in scope (16)

The roles whose `owned_phases` has two or fewer entries. Do not include the
orchestrator, review lead, or any role that owns three or more phases.

## Design

- Tasks: the role's existing behavioral or execution cases, plus one realistic
  task per role. Same prompts in both arms.
- Repeats: at least 3 seeds where the endpoint supports it; otherwise 3 runs at
  temperature 0 and report variance.
- Metrics: task success (pre-registered rubric), phase-transition errors, input
  and output tokens, wall clock, and any hyper-literal behavior (for example
  refusing a reasonable action because the compact line did not mention it).
- Blinding: grade the artifact without knowing the arm.

## Acceptance

Adopt the compact variant only if all hold:

1. Success is non-inferior within the pre-registered margin (no more than 5
   percentage points below control).
2. No phase-transition error appears in the compact arm that is absent in
   control.
3. Token savings are at least 150 per invocation.
4. The stronger-model arm does not show a new hyper-literal refusal pattern
   (S20 falsifier).

If any fails, keep the full fragment and record the result; do not trim role
bodies to compensate.

## If it passes

1. Add `fragments/agent-doctrine.compact.md` as a registered variant.
2. Bump `fragment_versions` and the manifest hash; never edit the full fragment.
3. Add a validator rule: a role either carries the full fragment or the compact
   variant, never a mix.
4. Re-baseline consumers before switching any runtime.

## Cost of not running it

The 16 low-phase roles carry about 5,600 doctrine tokens per full roster cycle.
That is a real cost, but it is not evidence of waste. Without this experiment
the correct action is to keep the full doctrine (AP-01/AP-14).

## Pilot result (2026-10-23, seed 7)

Three roles (`eng-frontend-developer`, `rev-reviewer`, `ops-executor`), one
seed, full vs compact doctrine.

| Arm | Mean score | Matched cases | Executor tokens |
|---|---:|---:|---:|
| Full doctrine | 0.778 | 2.33 / 3 | 9,923 |
| Compact | 0.889 | 2.67 / 3 | 9,288 |

The compact arm was non-inferior on this sample and used about 212 fewer tokens
per case. The sample is too small to adopt: no phase-transition errors were
observed in either arm, but three roles and one seed cannot rule out the S20
hyper-literalism risk. Run all 16 roles, three seeds, before registering the
variant. The two full-arm failures were fixture strictness ("names a concrete
verification command", "assigns a severity"), not doctrine omissions.

## Full run (2026-10-23, seeds 7/11/23)

Sixteen low-phase roles, 96 arms total (16 roles x 2 arms x 3 seeds).

| Arm | Mean score | Executor tokens | Cases |
|---|---:|---:|---:|
| Full doctrine | 0.708 | 108,612 | 48 |
| Compact | 0.674 | 107,244 | 48 |

Delta: **-0.035** for compact. It is inside the pre-registered 5-point
non-inferiority margin, but the token saving is only about 14 per case, not the
150 required by the acceptance rule. Three roles regressed materially
(`rev-track-simplicity` -0.56, `rev-consistency-reviewer` -0.33,
`eng-explorer` -0.11); two improved (`rev-security-reviewer` +0.11,
`rev-track-correctness` +0.11).

**Decision: keep the full doctrine fragment.** The compact variant is not
adopted. Do not add `agent-doctrine.compact.md`, do not bump fragment versions,
and do not trim role bodies on the assumption that doctrine is redundant.

The earlier 3-role pilot (0.889 vs 0.778) was a small-sample artifact; the full
run is the record. Raw results are under `evals/results/role-seed-*/`
(gitignored).
