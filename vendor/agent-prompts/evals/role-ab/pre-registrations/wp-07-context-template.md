# Pre-registration: AGENTS.md router template (WP-07)

Registered: 2026-10-27, before the run.

## Question

Does an always-loaded AGENTS.md router template, as specified by
`docs/AGENTS-TEMPLATE.md` and instantiated in `evals/context-template/router-v1.md`,
change task success or cost when it is prepended to a role prompt?

## Arms

- **Current:** the role template alone, slots filled by the runner.
- **Candidate:** `evals/context-template/router-v1.md` + the same role body,
  loaded before it.
- The router fixture is a filled instance of the template, not a second
  canonical template.
- Only the router differs; tasks, role bodies and slot values are fixed.

## Design

- **Roles:** `rev-reviewer`, `rev-code-skeptic`, `ops-executor`,
  `eng-backend-developer`, `eng-frontend-developer`, `orch-orchestrator`.
- **Tasks:** the existing `evals/role-ab/tasks/<role>.json` set, unchanged.
- **Seeds:** 311, 313, 317 (unused by earlier role A/Bs).
- **Budget:** `--max-tokens 2048` for both arms; temperature 0.
- **Model/harness:** executor `anthropic/claude-haiku-5.5`, grader
  `openai/gpt-6-luna`, OpenAI-compatible chat through
  `https://api.kilocode.ai/api/gateway/v1`.
- **Stopping rule:** run all 18 pairs; no optional stopping and no rerun of a
  valid loss. Retry only empty or error responses, as implemented by the runner.
- **Truncation:** a run with `completion_tokens >= max_tokens` or
  `finish_reason == length` is truncated; disclose it and exclude the pair from
  the complete aggregate.

## Hypotheses

- **H1 (non-inferiority):** the router arm's mean score is not worse than the
  role-only arm by more than 0.05.
- **H2 (cost):** the router arm uses more input tokens; record the delta.
- **H3:** the router arm does not increase failed expectations or truncation.

This is an 18-pair pilot. It can detect a cost penalty and a large degradation;
it cannot establish a small success delta. It is not the full 20-30 task CF-08
set, and no non-inferiority claim is made from it alone.

## Analysis

- Primary: paired mean difference (current - candidate) and wins/ties/losses.
- Secondary: fail count, input/output tokens, duration.
- Report every loss and every truncated pair. A neutral result means the
  template is retained as a routing and efficiency aid only, per CF-08.

## Reproduction

```bash
for seed in 311 313 317; do
  python3 tooling/run_role_ab.py \
    --roles rev-reviewer rev-code-skeptic ops-executor \
      eng-backend-developer eng-frontend-developer orch-orchestrator \
    --context-file evals/context-template/router-v1.md \
    --seed "$seed" --max-tokens 2048 \
    --base-url https://api.kilocode.ai/api/gateway/v1 --api-key-env KILO_API_KEY \
    --executor-model anthropic/claude-haiku-5.5 \
    --grader-model openai/gpt-6-luna \
    --results-dir "evals/results/wp07-context-$seed"
done
```
