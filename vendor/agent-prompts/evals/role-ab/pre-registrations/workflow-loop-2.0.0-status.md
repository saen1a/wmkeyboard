# 2.0.0 A/B run status: blocked by provider balance

Date: 2026-10-24.

The pre-registered `workflow-loop-2.0.0.md` run was started but could not
finish. The DeepSeek API returned:

```text
HTTP 402 Payment Required
{"error":{"message":"Insufficient Balance ...","type":"insufficient_balance_error"}}
```

Progress before the abort:

- 52 of 72 arm-runs landed; 20 missing.
- Missing: `orch-orchestrator` seed 409 (both arms); `rev-code-skeptic`,
  `rev-review-lead`, and `rev-reviewer` all three seeds (both arms).
- No empty responses in the runs that landed.
- No aggregate was produced. The 1.3.0 pre-registered result and its original
  `ops-executor` loss remain the last complete registered evidence.
- The `ops-executor-2.0.0.json` check remains post-hoc.

To finish:

1. Replenish the DeepSeek balance.
2. Re-run the missing 10 role-seed pairs (both arms) using the same seeds and
   `--max-tokens 16384`.
3. Re-summarize all three result dirs to
   `evals/role-ab/results/workflow-loop-2.0.0.json`.
4. Only then replace the post-hoc note in the docs.

Do not summarize the partial 52 runs as a complete result.

Retry after the platform usage reset: the provider still returns HTTP 402
Insufficient Balance. The 20 missing arm-runs remain blocked.

The DeepSeek 2.0.0 run remains blocked. A separate pre-registered
workflow-loop-2.0.0-opencode.md run completed 72/72 arm-runs on OpenCode Go;
the model changed, so its result is not comparable.

## Post-run amendment (2026-10-25)

The doctrine text changed in `31952d9` and is now `1.3.1`. Any result recorded
under this protocol measures the older body; a new run is required for a
current-body claim.
