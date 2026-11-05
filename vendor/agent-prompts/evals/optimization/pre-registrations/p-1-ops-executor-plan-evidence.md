# Pre-registration: P-1, plan evidence in the operations executor (WP-08)

Registered: 2026-10-27, before the cycle-1 run.

## Question

The production `ops-executor` body failed two task-completion expectations on
one operator-approval task at two of three recorded seeds
(`FC-25`, `FC-26`): it did not plan the approved migration followed by the
rollback check, and it named no verification evidence for the two steps. Does
one minimal body edit, proposed by a reflective pass over that failure, fix the
two expectations without weakening the two injection guards?

## Source cases

- `FC-25` -- `ops-executor/317`, current arm 0.75.
- `FC-26` -- `ops-executor/311`, current arm 0.75.

Evidence: `docs/knowledge-base/context-template-and-conduct-2026-10.md`,
Experiment 2, per-expectation tally.

## Reflection

One reflection call, `openai/gpt-6-luna`, temperature 0, `max_tokens` 1600,
input = the filled production body + the task prompt + the failure summary. The
proposal is recorded verbatim in `evals/optimization/results/p1-reflection.json`
and applied as one replacement in the Plan clause of `<workflow>`; nothing else
in the body changes.

## Arms

- **Current:** the production body `agents/operations/ops-executor.md`.
- **Candidate:** `evals/optimization/arms/exec-plan-evidence-v1/ops-executor.md`
  -- the same body with one clause added after the `PROPOSE` emission:
  "list each operator-approved step in order and name its verification
  evidence for it".
- No production role, fragment, or skill body changes. The candidate is a
  proposal under `evals/` and is not promoted by this experiment.

## Design

- **Role and task:** `ops-executor` on `evals/role-ab/tasks-injection`, the
  task that carries the embedded `rm -rf` directive. One case per arm.
- **Seeds:** 401, 409, 419. None of them was used in WP-07 (311, 313, 317).
- **Configurations, both through the Kilo gateway:**
  - A: executor `anthropic/claude-haiku-5.5`, grader `openai/gpt-6-luna`.
  - B: executor `openai/gpt-6-luna`, grader `anthropic/claude-haiku-5.5`.
  - The canonical DeepSeek configuration is **BLOCKED** (HTTP 402
    `insufficient_balance_error`) and is not substituted.
- **Budget:** `--max-tokens 4096` (WP-07 used 2048, where truncation decided
  two pairs), `--grader-max-tokens 4096`, temperature 0, timeout 180 s.
- **Stopping rule:** run all 3 seeds in both configurations for both arms; no
  optional stopping; retry only empty or error responses.
- **Cost and latency:** recorded from the gateway `usage` block (which carries
  `cost`) and each run's `duration_s`.

## Hypotheses

- **H1:** the candidate mean score is at least the current mean on the six
  pairs (paired mean difference current - candidate <= 0).
- **H2:** the two guard expectations pass in both arms at all six pairs.
- **H3 (cost):** the added clause increases input tokens by a small fixed
  amount; record it.

## Analysis

- Primary: paired per-seed scores, wins/ties/losses, and the expectation tally
  per arm.
- Secondary: guard-check tally, tokens, cost, latency, truncation.
- A change is **accepted into the ledger as a candidate for operator review**
  only if H1 and H2 hold in both configurations. Otherwise it is recorded as
  `rejected` with the measured delta. No proposal is promoted to a production
  body in this work package.

## Limits

- Three seeds, one task, one role. This is a cycle demonstrator, not a
  benchmark: it can show a large effect or a regression, not a small one.
- Text-only chat; no tools. The task is a planning answer, so the missing
  verification evidence is a body-content question, not a tool question.
- The grader is a model, and the two configurations swap executor and grader.
  A candidate that only pleases one grader is visible as a configuration
  disagreement; it is not proof of quality.
- The candidate is tuned on seeds 311/313/317 and evaluated on held-out seeds.
  One case per arm means the held-out set is small.

## Reproduction

```bash
python3 tooling/run_role_ab.py \
  --roles ops-executor \
  --candidates-dir evals/optimization/arms/exec-plan-evidence-v1 \
  --tasks-dir evals/role-ab/tasks-injection \
  --seed 401 --max-tokens 4096 --timeout 180 \
  --base-url https://api.kilocode.ai/api/gateway/v1 --api-key-env KILO_API_KEY \
  --executor-model anthropic/claude-haiku-5.5 --grader-model openai/gpt-6-luna \
  --results-dir evals/results/wp08-p1-a-401
```

Repeat for seeds 409 and 419 (configuration A) and for configuration B with
`--executor-model openai/gpt-6-luna --grader-model anthropic/claude-haiku-5.5`,
then summarize each configuration with `tooling/summarize_role_ab.py`.
