# Refactor A/B: old vs new skill bodies (2026-10-23)

Status: measured, 3 seeds. This answers the question the paired baseline could
not: did splitting the seven over-cap skill bodies preserve quality?

## Method

- Old body: `git show ff91dc3:skills/.../SKILL.md` (pre-refactor).
- New body: current `SKILL.md`.
- Same behavioral cases, model, harness, and seeds (7/11/23); executor
  `deepseek-flash`, grader `deepseek-v4-pro`.
- 126 scheduled runs; 5 runs were invalid because the model emitted tool-call
  markup despite a text-only task and were excluded. 122 valid runs.
- One case per skill family was re-run after the first pass exposed missing
  content; the table uses the fixed bodies.

## Result

| Arm | Mean score | Fully passed | Executor tokens |
|---|---:|---:|---:|
| Old body | 0.875 | 45/61 | 260,011 |
| New body | **0.886** | **46/61** | **152,451** |

The new bodies are non-inferior on this sample (+1.1 points) and use **41%
fewer executor tokens**. Per-skill:

| Skill | Old | New | Note |
|---|---:|---:|---|
| agent-md-refactor | 0.85 | 0.85 | equal after restoring the deletion/context rules |
| anti-entropy-governance | 0.96 | 0.93 | within noise; one more partial |
| deepseek-v4-agent-defense | 1.00 | 0.96 | one partial; bands restored after the first pass |
| first-principles-review | 0.83 | 0.82 | equal |
| jq-json-processing | 0.96 | 1.00 | new better on valid runs |
| mcp-builder | 0.85 | 0.82 | within noise |
| skill-creator | 0.63 | **0.85** | new materially better |

## What the A/B caught

The first pass found two real losses, both fixed before the final table:

1. `deepseek-v4-agent-defense` dropped the 5-10 parallel-call band from the
   compressed layer summary. Restored.
2. `agent-md-refactor` softened "flag, do not delete" and the always-loaded cost
   rationale. Restored, plus an explicit "do not skip the split for safety".

This is the argument for the A/B: the shape report would have passed both
bodies.

## Limits

- One model/harness, 7 skills, 3 cases each, 3 seeds.
- The no-tools instruction was not injected into this harness, so a few runs
  were tool-call markup and had to be excluded; the exclusion is reported.
- Cases are the current ones, which were written after the split; they may
  favor the new shape.
- The grader is a model, not a deterministic checker.

## Conclusion

The refactor is safe to bake: new bodies are non-inferior overall, better on
`skill-creator`, and 41% cheaper in executor tokens. Keep the two restored
rules; do not re-split further without the same test.

Harness: `tooling/run_refactor_ab.py`. Raw results: `evals/results/refactor-ab-*/`
(gitignored).
