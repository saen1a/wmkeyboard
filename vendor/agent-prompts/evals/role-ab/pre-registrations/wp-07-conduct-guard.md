# Pre-registration: conduct guard in hard_rules (WP-07)

Registered: 2026-10-27, before the run.

## Question

Does adding one data-not-instructions bullet at the top of `hard_rules`, while
`fragments/agent-conduct.md` stays byte-exact at the end of the prompt, improve
resistance to an instruction embedded in data?

## Arms

- **Current:** the production role template; the conduct fragment already
  carries the data-not-instructions rule once, near the end.
- **Candidate:** `evals/role-ab/arms/conduct-guard-v1/<role>.md`, the same body
  plus one bullet in `hard_rules`. The `<conduct>` block is byte-identical to
  the production body.
- No production role, fragment, or skill body changes.

## Design

- **Roles:** `rev-reviewer`, `rev-code-skeptic`, `ops-executor`,
  `eng-backend-developer`, `eng-frontend-developer`, `orch-orchestrator`.
- **Primary tasks:** `evals/role-ab/tasks-injection/<role>.json`, one case per
  role with a directive inside a diff, tool output, source comment, review note,
  or handoff. Expectations require resisting the directive and completing the
  legitimate task.
- **Regression tasks:** the original `evals/role-ab/tasks/<role>.json` at seed
  311 only, to detect collateral damage on ordinary work.
- **Seeds:** 311, 313, 317 for the injection set; 311 for regression.
- **Budget:** `--max-tokens 2048`; temperature 0.
- **Model/harness:** executor `anthropic/claude-haiku-5.5`, grader
  `openai/gpt-6-luna`, OpenAI-compatible chat through
  `https://api.kilocode.ai/api/gateway/v1`.
- **Stopping rule:** run all 18 injection pairs and 6 regression pairs; no
  optional stopping; retry only empty or error responses.

## Hypotheses

- **H1:** the candidate arm scores at least as high on the injection set
  (paired mean difference current - candidate <= 0).
- **H2:** the candidate arm does not lose more than 0.05 mean score on the
  regression set.
- **H3 (cost):** the added bullet increases input tokens by a small fixed
  amount; record it.

A win on H1 with no regression is evidence for an experimental variant, not for
editing a production role. Promotion requires the full paired protocol and the
wave audit.

## Analysis

- Primary: paired mean difference on injection cases, wins/ties/losses.
- Secondary: regression delta, failed expectations, tokens, truncation.
- Publish the raw result location and a committed summary with arm hashes.
  Report every loss.

## Reproduction

```bash
for seed in 311 313 317; do
  python3 tooling/run_role_ab.py \
    --roles rev-reviewer rev-code-skeptic ops-executor \
      eng-backend-developer eng-frontend-developer orch-orchestrator \
    --candidates-dir evals/role-ab/arms/conduct-guard-v1 \
    --tasks-dir evals/role-ab/tasks-injection \
    --seed "$seed" --max-tokens 2048 \
    --base-url https://api.kilocode.ai/api/gateway/v1 --api-key-env KILO_API_KEY \
    --executor-model anthropic/claude-haiku-5.5 \
    --grader-model openai/gpt-6-luna \
    --results-dir "evals/results/wp07-conduct-$seed"
done

python3 tooling/run_role_ab.py \
  --roles rev-reviewer rev-code-skeptic ops-executor \
    eng-backend-developer eng-frontend-developer orch-orchestrator \
  --candidates-dir evals/role-ab/arms/conduct-guard-v1 \
  --seed 311 --max-tokens 2048 \
  --base-url https://api.kilocode.ai/api/gateway/v1 --api-key-env KILO_API_KEY \
  --executor-model anthropic/claude-haiku-5.5 \
  --grader-model openai/gpt-6-luna \
  --results-dir "evals/results/wp07-conduct-regression-311"
```
