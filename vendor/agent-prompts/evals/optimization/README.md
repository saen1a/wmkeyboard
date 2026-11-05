# Optimization loop artifacts (WP-08)

The P3 loop: labelled failures in, one human-gated proposal out, and a rule that
a stale baseline cannot be compared silently. Record and limits:
`docs/knowledge-base/optimization-loop-2026-10.md`.

| Path | What it is | Checked by |
|---|---|---|
| `failure-set.md` | 38 labelled failures, each with a source path and a resolving anchor | `tooling/check_failure_set.py` |
| `proposals.md` | The human-gated ledger, one row per proposal | `tooling/check_optimization_ledger.py` |
| `proposals.schema.json` | Machine-readable form of one proposal row | `tooling/tests/test_check_optimization_ledger.py` |
| `proposal-example.json` | The `P-1` instance, validated against the schema | same test |
| `baseline.json` | `BL-1`: the identity of the last complete paired campaign | `tooling/check_rebaseline.py` |
| `arms/` | Candidate prompt bodies. Never production prompts | the ledger arm check |
| `pre-registrations/` | The protocol fixed before a cycle runs | review only |
| `results/` | Committed summaries: arm hashes, per-expectation tallies, usage, cost, latency | the ledger evidence check |

## Rules

- A proposal is a candidate arm under `arms/`, not a production edit. Promotion
  is a separate change with its own paired baseline and a human gate.
- One proposal per cycle. A cycle that measures no gain is `rejected`; a cycle
  that cannot run is `blocked` with the exact error.
- No row may claim a quality gain that its own paired numbers do not show. The
  checker refuses an `accepted` row without an approved gate and a measured gain,
  and refuses `rejected` or `accepted` without a paired result.
- Cost, latency and tokens are required per configuration. `unrecorded` is
  allowed with a reason; `not-run` is not allowed on a decided proposal.
- `source_cases` must exist in `failure-set.md`. A case whose anchor stops
  resolving fails the gate, so the set cannot drift from its evidence.

## Re-baseline

`evals/optimization/baseline.json` pins the identity of the campaign a new
measurement may be compared with: model, grader, harness, `prompt_version` and
`cache_epoch`, using the fields in `evals/harness-telemetry.schema.json`.

```bash
python3 tooling/check_rebaseline.py \
  --baseline evals/optimization/baseline.json \
  --current evals/role-ab/results/wp07-conduct-guard.json   # exit 0: same identity
python3 tooling/check_rebaseline.py \
  --baseline evals/optimization/baseline.json \
  --current evals/role-ab/results/workflow-loop-1.3.0.json  # exit 1: new baseline required
```

`--current` accepts a committed role A/B summary (`role-ab-summary/*`) or a
telemetry-shaped record with a `run` block. An identity field present on one
side only is unverifiable and fails the check; a field absent on both sides is
reported as not recorded. `make gate` runs the matching pair.

## Reproduce the cycle

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

See `pre-registrations/p-1-ops-executor-plan-evidence.md` for the full protocol,
including the second configuration and the held-out seeds. Raw results stay
under the gitignored `evals/results/`; the committed summaries in `results/` are
the evidence.
