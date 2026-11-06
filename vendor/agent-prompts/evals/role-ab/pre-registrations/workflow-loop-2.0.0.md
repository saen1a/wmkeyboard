# Pre-registration: workflow loop 2.0.0 vs linear v1.1

Registered: 2026-10-24, before the run.

## Question

Does the 2.0.0 workflow loop, including the fixed `ops-executor` body, preserve
or improve task performance relative to the previous linear doctrine on the
role A/B tasks?

This replaces the **post-hoc** `ops-executor` recheck with a full registered
aggregate. The 1.3.0 result remains historical and still carries its original
loss; it is not rewritten.

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
- **Seeds:** 401, 409, 419 (new, unused).
- **Budget:** `--max-tokens 16384` both arms; temperature 0.
- **Model/harness:** executor `deepseek-flash`, grader `deepseek-v4-pro`,
  OpenAI-compatible chat.
- **Stopping rule:** run all 36 pairs; no optional stopping, no rerun of a valid
  loss. Retry only empty/error responses.
- **Truncation:** `completion_tokens >= max_tokens` or `finish_reason == length`
  excludes the pair from the complete aggregate.

## Hypotheses

- **H1 (non-inferiority):** current mean is not worse than linear by more than
  0.05.
- **H2:** `ops-executor` passes its previously failing expectation on the fixed
  body.
- **H3 (secondary):** no increase in truncation or token use beyond the fixed
  budget.

Superiority is not assumed. A neutral result means the loop is retained for
explicit state/gates, not for a measured performance gain.

## Analysis

- Primary: paired mean difference and wins/ties/losses across 36 pairs.
- Secondary: pass rate, per-role result, completion tokens, truncation.
- Publish both the raw result location and a committed manifest with arm hashes,
  `current_ref`, doctrine version, and exclusions.
- Report every loss and every truncated pair.

## Reproduction

```bash
for seed in 401 409 419; do
  python3 tooling/run_role_ab.py \
    --roles eng-api-developer eng-backend-developer eng-database-developer \
      eng-frontend-developer eng-test-author net-network-architect \
      ops-ci-implementer ops-executor orch-orchestrator rev-code-skeptic \
      rev-review-lead rev-reviewer \
    --candidates-dir evals/role-ab/arms/linear-v1.1 \
    --seed "$seed" --max-tokens 16384 \
    --results-dir "evals/results/loop-ab-2.0-$seed"
done

python3 tooling/summarize_role_ab.py \
  --results-dir evals/results/loop-ab-2.0-401 \
  --results-dir evals/results/loop-ab-2.0-409 \
  --results-dir evals/results/loop-ab-2.0-419 \
  --exclude ops-format-normalizer \
  --exclude-reason "tool-dependent task; text-only 0.33/0.33 vs tool-enabled 1.0/1.0" \
  --current-arm "doctrine 1.3.0 loop, template 2.0.0" \
  --doctrine-version 1.3.0 \
  --current-ref "<pre-registration commit>" \
  --note "Pre-registered 2.0.0 protocol; see evals/role-ab/pre-registrations/workflow-loop-2.0.0.md" \
  --output evals/role-ab/results/workflow-loop-2.0.0.json
```

## Post-run amendment (2026-10-25)

The doctrine text changed in `31952d9` and is now `1.3.1`. Any result recorded
under this protocol measures the older body; a new run is required for a
current-body claim.
