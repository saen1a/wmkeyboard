# Pre-registration: workflow loop 1.3.0 vs linear v1.1

Registered: 2026-10-24, before the run.

## Question

Does the explicit workflow loop (doctrine 1.3.0) preserve or improve task
performance relative to the previous linear doctrine (v1.1.0) on the role A/B
tasks?

## Arms

- **Current:** the 38 role templates at the pre-registration commit, doctrine
  1.3.0.
- **Candidate:** `evals/role-ab/arms/linear-v1.1/`, pinned by body hash.
- Only the doctrine, phase maps, and the associated role edits differ; tasks
  are fixed and come from `evals/role-ab/tasks/`.

## Design

- **Roles:** the 12 valid role tasks. `ops-format-normalizer` is excluded
  before the run: its task depends on commit/format tooling; text-only runs are
  ~0.33/0.33 while the tool-enabled harness is 1.0/1.0, so the text-only A/B is
  not comparable.
- **Seeds:** 211, 223, 227 (new, unused by the earlier exploratory run).
- **Budget:** `--max-tokens 16384` for both arms; temperature 0.
- **Model/harness:** executor `deepseek-flash`, grader `deepseek-v4-pro`,
  OpenAI-compatible chat.
- **Stopping rule:** run all 36 pairs; no optional stopping, no rerun of a
  valid loss. Retry only empty/error responses, as implemented by the runner.
- **Truncation:** a run with `completion_tokens >= max_tokens` or
  `finish_reason == length` is truncated; exclude the pair from the complete
  aggregate and disclose it.

## Hypotheses

- **H1 (non-inferiority):** loop mean score is not worse than linear mean score
  by more than 0.05.
- **H2:** the loop does not increase the number of failed expectations.
- **H3 (secondary):** the loop does not increase truncation or token use beyond
  the fixed budget.

Superiority is not assumed. A neutral result means the loop is retained for
explicit state, gates, and auditability, not for a measured performance gain.

## Analysis

- Primary: paired mean difference (current - candidate) across 36 role/seed
  pairs; report wins/ties/losses and the complete-pair aggregate.
- Secondary: pass rate, completion tokens, truncation count.
- Publish both the raw result location and a committed summary manifest. Raw
  results are gitignored; the summary plus arm hashes are the durable evidence.
- Report every loss and every truncated pair; do not remove a valid loss.

## Reproduction

```bash
for seed in 211 223 227; do
  python3 tooling/run_role_ab.py \
    --roles eng-api-developer eng-backend-developer eng-database-developer \
      eng-frontend-developer eng-test-author net-network-architect \
      ops-ci-implementer ops-executor orch-orchestrator rev-code-skeptic \
      rev-review-lead rev-reviewer \
    --candidates-dir evals/role-ab/arms/linear-v1.1 \
    --seed "$seed" --max-tokens 16384 \
    --results-dir "evals/results/loop-ab-pre-$seed"
done

python3 tooling/summarize_role_ab.py \
  --results-dir evals/results/loop-ab-pre-211 \
  --results-dir evals/results/loop-ab-pre-223 \
  --results-dir evals/results/loop-ab-pre-227 \
  --exclude ops-format-normalizer \
  --exclude-reason "tool-dependent task; text-only 0.33/0.33 vs tool-enabled 1.0/1.0" \
  --current-arm "doctrine 1.3.0 loop" \
  --doctrine-version 1.3.0 \
  --current-ref bf26209 \
  --note "Pre-registered protocol: evals/role-ab/pre-registrations/workflow-loop-1.3.0.md; current arm measured at bf26209; f27a681 changed ops-executor after the run." \
  --output evals/role-ab/results/workflow-loop-1.3.0.json
```

## Post-run amendment (2026-10-25)

The doctrine fragment text changed in commit `31952d9` after this run, while
the doctrine version stayed `1.3.0`. The recorded arm hashes therefore measure
the pre-change body. The current body is doctrine `1.3.1`; these results are
historical evidence for the loop design, not evidence for the current body.
A new pre-registered run is required for a current-body claim.
