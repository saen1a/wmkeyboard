# Pre-registration: workflow loop 2.0.0 on the OpenCode Go model

Registered: 2026-10-24, before the run.

## Question

Does the 2.0.0 workflow loop, including the fixed `ops-executor` body, preserve
or improve task performance on the new executor model? This is a **new
experiment**, not a continuation of the DeepSeek 1.3.0/2.0.0 runs: the model and
provider changed, so prompt-cache state and token economics reset. Results are
not directly comparable to the DeepSeek numbers.

## Arms

- **Current:** the 38 role templates at this pre-registration commit, template
  2.0.0, doctrine 1.3.0.
- **Candidate:** `evals/role-ab/arms/linear-v1.1/`, pinned by body hash.
- Tasks are fixed in `evals/role-ab/tasks/`; the `ops-executor` task is not
  edited.

## Design

- **Roles:** the 12 valid role tasks. `ops-format-normalizer` is excluded
  before the run: its task depends on commit/format tooling; text-only runs are
  ~0.33/0.33 while the tool-enabled harness is 1.0/1.0.
- **Seeds:** 501, 509, 519 (new, unused).
- **Models:** executor `deepseek-v4.1-flash`, grader `deepseek-v4-pro` on
  `https://opencode.ai/zen/go/v1` (OpenCode Go).
- **Headers:** `User-Agent: opencode/2.0.18`,
  `x-opencode-session: agent-prompts-eval`.
- **Budget:** `--max-tokens 16384` both arms; temperature 0.
- **Stopping rule:** run all 36 pairs; no optional stopping, no rerun of a valid
  loss. Retry only empty/error responses.
- **Truncation:** `completion_tokens >= max_tokens` or `finish_reason == length`
  excludes the pair from the complete aggregate.

## Hypotheses

- **H1 (non-inferiority):** current mean is not worse than linear by more than
  0.05.
- **H2:** `ops-executor` passes its previously failing expectation on the fixed
  body in a full registered run.
- **H3 (secondary):** no increase in truncation beyond the fixed budget.

Superiority is not assumed.

## Analysis

- Primary: paired mean difference and wins/ties/losses across 36 pairs.
- Secondary: pass rate, per-role result, completion tokens, truncation.
- Publish both the raw result location and a committed manifest with arm hashes,
  `current_ref`, doctrine version, models, and exclusions.
- Report every loss and every truncated pair.

## Reproduction

```bash
export EXECUTOR_EXTRA_HEADERS='{"User-Agent":"opencode/2.0.18","x-opencode-session":"agent-prompts-eval"}'
for seed in 501 509 519; do
  python3 tooling/run_role_ab.py \
    --roles eng-api-developer eng-backend-developer eng-database-developer \
      eng-frontend-developer eng-test-author net-network-architect \
      ops-ci-implementer ops-executor orch-orchestrator rev-code-skeptic \
      rev-review-lead rev-reviewer \
    --candidates-dir evals/role-ab/arms/linear-v1.1 \
    --base-url https://opencode.ai/zen/go/v1 --api-key-env OPENCODE_API_KEY \
    --executor-model deepseek-v4.1-flash --grader-model deepseek-v4-pro \
    --seed "$seed" --max-tokens 16384 --timeout 240 \
    --results-dir "evals/results/loop-ab-oc-$seed"
done

python3 tooling/summarize_role_ab.py \
  --results-dir evals/results/loop-ab-oc-501 \
  --results-dir evals/results/loop-ab-oc-509 \
  --results-dir evals/results/loop-ab-oc-519 \
  --exclude ops-format-normalizer \
  --exclude-reason "tool-dependent task; text-only 0.33/0.33 vs tool-enabled 1.0/1.0" \
  --current-arm "doctrine 1.3.0 loop, template 2.0.0" \
  --doctrine-version 1.3.0 \
  --current-ref "0223eae" \
  --note "Pre-registered 2.0.0 OpenCode Go protocol; model changed, cache reset, not comparable to DeepSeek 1.3.0." \
  --output evals/role-ab/results/workflow-loop-2.0.0-opencode.json
```

## Amendment after the run

The run used `--timeout 240` (the runner default is 60) because OpenCode Go
requests timed out at 60 s. This changes no scoring rule, seed, model, or
budget, but it was not in the original command block. The command block above is
updated to match; the run remains the registered experiment.

## Post-run amendment (2026-10-25)

The doctrine fragment text changed in commit `31952d9` after this run, while
the doctrine version stayed `1.3.0`. The recorded arm hashes therefore measure
the pre-change body. The current body is doctrine `1.3.1`; these results are
historical evidence for the loop design, not evidence for the current body.
A new pre-registered run is required for a current-body claim.
