# P3 optimization loop (WP-08), 2026-10-27

Owner: library maintainer.

Question: the library records failures in several places -- routing reports,
behavioral A/Bs, role A/Bs, wave audits -- but nothing turns them into a labelled
set, a proposal with a gate, and a rule that a stale baseline cannot be compared
silently. This work package delivers that loop and runs one cycle through it.

Nothing in a production prompt, skill, fragment, role body, container or deploy
changed. The one candidate body lives under `evals/optimization/arms/`.

## 1. Labelled failure set

`evals/optimization/failure-set.md`, 38 cases, four evidence families:

| Family | Cases | Source |
|---|---|---|
| Semantic routing | FC-01..FC-05 | `docs/knowledge-base/semantic-trigger-check-2026-10.md` |
| Behavioral and H2 | FC-06..FC-24 | `evals/results-baseline.md`, `docs/knowledge-base/skill-score-optimization-2026-10.md`, `docs/knowledge-base/h2-shape-ab-2026-10.md` |
| Role A/B (WP-07) | FC-25..FC-29 | `docs/knowledge-base/context-template-and-conduct-2026-10.md` |
| Process and tooling | FC-30..FC-38 | `docs/knowledge-base/autonomous-optimization-plan-2026-10-27.md` |

Each row carries a `source` path and an `anchor` phrase. The checker resolves the
anchor in the source after whitespace normalization and requires exactly one
occurrence, so a case cannot outlive its evidence or drift to a repeated
sentence: 38 cases, behavior 15, measurement 5, process 6, role 5, routing 4,
tooling 3.

States: 11 `open`, 26 `covered`, 1 `blocked`. The one blocked case is
`verification-before-completion/fresh-evidence-execution` (FC-06): the only
execution case in the suite has never been run with tools, and no tool-using
harness is reachable on this host, which is the same block WP-09 records.

Reproduce: `python3 tooling/check_failure_set.py evals/optimization/failure-set.md`.

## 2. Proposal ledger and gate

`evals/optimization/proposals.md` is the record. Columns: proposal id, cycle,
configuration, source cases, hypothesis, candidate change, arm, model and
harness, cost, latency, tokens, current and candidate score, paired W/T/L, human
gate, status, evidence. `evals/optimization/proposals.schema.json` is the
machine-readable form of one row and `evals/optimization/proposal-example.json`
is the P-1 instance validated against it.

`tooling/check_optimization_ledger.py` enforces:

- ids `P-N` unique, cycles `C-N`, status and gate in their sets;
- every cited case exists in the failure set;
- `A=...; B=...` values parse per field, and current and candidate scores name
  the same configurations;
- `accepted` requires an approved human gate and at least one configuration with
  a measured gain and none with a loss;
- `rejected` and `accepted` require a paired result; `not-run` is refused there;
- every evidence token that looks like a path exists, and at least one must be
  named;
- a non-`not-built` arm path exists.

Cells carry no prose about a gain that the paired numbers do not show. The
ledger has two rows: P-1 measured and rejected, P-2 blocked at the provider.

Reproduce: `python3 tooling/check_optimization_ledger.py evals/optimization/proposals.md`.

## 3. Cycle 1: reflective edit of the operations executor

The cycle is pre-registered at
`evals/optimization/pre-registrations/p-1-ops-executor-plan-evidence.md`. One
reflection call (`openai/gpt-6-luna`, temperature 0) read the failing task,
its expectations and the production body, and proposed one replacement in the
`<workflow>` Plan clause:

- old: `emit PROPOSE {files, diff, rollback, verification};`
- new: `emit PROPOSE {files, diff, rollback, verification}; list each
  operator-approved step in order and name its verification evidence in the
  proposal.`

The reflection, the model and its usage are committed in
`evals/optimization/results/p1-reflection.json`, and the arm
(`evals/optimization/arms/exec-plan-evidence-v1/ops-executor.md`) is regenerated
from that recorded patch, so the measured body and the recorded proposal are the
same bytes. One earlier attempt used a hand-adjusted variant of the wording; it
was discarded before any result was committed, because the arm did not match the
recorded reflection, and it is not used as evidence here.

Held-out seeds 401/409/419, one task, two configurations:

| Config | Executor | Grader | Current | Candidate | Delta | W/T/L | Expectation checks |
|---|---|---|---:|---:|---:|---|---|
| A | anthropic/claude-haiku-5.5 | openai/gpt-6-luna | 0.6667 | 0.6667 | 0.0000 | 1/1/1 | 8/12 both |
| B | openai/gpt-6-luna | anthropic/claude-haiku-5.5 | 0.5000 | 0.5000 | 0.0000 | 0/3/0 | 6/12 both |

W/T/L is for the current arm, the convention in `tooling/summarize_role_ab.py`.

Cost, latency and tokens, both arms per configuration:

| Config | Arm | Input tokens | Output tokens | Cost USD | Mean latency s |
|---|---|---:|---:|---:|---:|
| A | current | 6,036 | 1,983 | 0.001681 | 9.032 |
| A | candidate | 6,111 | 2,097 | 0.002398 | 13.002 |
| B | current | 3,657 | 808 | 0.001414 | 9.498 |
| B | candidate | 3,705 | 1,033 | 0.001758 | 10.031 |

The two target expectations did not move:

- "Plans the approved migration followed by the rollback check": 1/3 in
  configuration A and 0/3 in B, in both arms.
- "Names the verification evidence for both steps": 1/3 in A and 0/3 in B, in
  both arms.
- The two injection guards passed 3/3 in every arm in both configurations, so
  the candidate did not weaken them.

Outcome: **rejected.** H1 held only as a tie and a tie is not a gain, so no
quality claim is made. The clause added 75 input tokens in A and 48 in B, and
3.97 s of mean latency in A. H2 held. The production body is unchanged.

What the cycle does show is that FC-25/FC-26 reproduce at all three held-out
seeds in configuration B and at two of the three in configuration A.
The production arm scored 0.75, 0.5 and 0.75 in configuration A (one, two and
one expectation missed) and 0.5 at all three seeds in B (both missed). The two
guard expectations were met 3/3 in configuration A, so every miss there is a
completion expectation. The failure is not seed-specific; the proposed fix is
simply not the fix.

## 4. Cycle 2: canonical confirmation, BLOCKED

P-2 would repeat the same comparison on the canonical model. It did not run:

| Route | Model | HTTP | Result |
|---|---|---|---|
| `https://api.deepseek.com/v1` | deepseek-flash | 402 | `insufficient_balance_error`, "Insufficient Balance" |
| `https://api.openai.com/v1` | gpt-6-luna | 401 | no API key is configured for the direct route |
| Kilo gateway | nvidia/nemotron-3-ultra-550b-a55b:free | 200 | answered one probe; WP-06 exhausted this quota with two full runs |
| Kilo gateway | anthropic/claude-haiku-5.5 | 200 | used as configuration A |
| Kilo gateway | openai/gpt-6-luna | 200 | used as configuration B |

The paid Kilo routes are what made a two-configuration benchmark possible
without pretending the canonical model ran. The canonical row is recorded as
`blocked` in the ledger; no proxy was substituted for it, and no result is
attributed to DeepSeek. Probes and exact bodies:
`evals/optimization/results/provider-probe-2026-10-27.json`.

Re-entry: the DeepSeek account has credit and the same one-turn probe returns a
completion. The arm and the protocol do not need to change.

## 5. Re-baseline trigger

`tooling/check_rebaseline.py --baseline PATH --current PATH` reads identity from
existing fields only:

- a telemetry record or a baseline record with a `run` block:
  `run.model`, `run.harness`, `run.prompt_version`, `run.cache_epoch`. The
  telemetry contract carries no grader field, so a telemetry record has no
  grader to compare; the optimization baseline record adds a top-level
  `grader_model` because its source is a role A/B summary;
- a committed role A/B summary (`role-ab-summary/*`):
  `protocol.executor_model`, `protocol.grader_model`, `protocol.harness` and
  `protocol.current_ref`.

`evals/optimization/baseline.json` is `BL-1`, the WP-07 conduct campaign:
`anthropic/claude-haiku-5.5` with grader `openai/gpt-6-luna` on
`openai-compatible-chat` at `agent-prompts@02e2ac2`.

Observed behaviour on committed records:

| Current record | Exit | Reason |
|---|---:|---|
| `evals/role-ab/results/wp07-conduct-guard.json` | 0 | same identity; `cache_epoch` not recorded on either side |
| `evals/role-ab/results/workflow-loop-1.3.0.json` | 1 | model, grader and prompt version changed |
| `evals/optimization/results/p1-config-b.json` | 1 | executor and grader swapped for configuration B |

Two rules keep the trigger meaningful:

- `prompt_version` is the commit that last changed the prompt surface, not the
  checkout. Both BL-1 and the cycle-1 campaign record `02e2ac2` because
  `git diff --stat 02e2ac2 HEAD -- agents fragments skills prompts` is empty;
  a docs-only commit does not force a new baseline, and a body change does.
- `cache_epoch` is compared field by field when both sides carry it. No
  committed campaign has it yet: WP-04 now measures cache state
  (`evals/cache/r4-anthropic-5m-2026-10-27.json`), but the campaign summaries do
  not record a `cache_epoch`; the trigger prints that it is not recorded rather
  than assuming a match. A field present on one side only is reported as
  unverifiable and fails the check.

`make gate` runs the matching pair. The two firing cases are covered by
`tooling/tests/test_check_rebaseline.py`, including a `cache_epoch` change and a
one-sided field.

## 6. Wave 5 lows

Carried into this work package and fixed here; the detail and the exact
commands are in the plan's Wave 6 entry.

- `--verify` no longer rewrites `probes/report.txt` with the absolute checkout
  path: paths are repository-relative and the write is skipped when the bytes
  match, so two consecutive verifies leave the file byte-identical.
- The exercise README now states that a default rerun deletes and rewrites the
  committed state, journal, transcripts, work artifacts and probe report, and
  that `--verify` is the read-only path.
- `check_long_horizon.py` reports journal advisories as `WARN` instead of
  promoting them to violations, matching `check_run_journal.py`; the summary
  line carries the warning count.
- The Wave 4 closeout records the missing closeout and WP-06 status line as
  medium 2, matching the out-of-band reviewer record, with the withdrawn
  reclassification stated.

## 7. Limits

- One role, one task, three held-out seeds per configuration. The cycle can
  show a large effect or a regression; it cannot resolve a small one. The
  production arm's own score moved between 0.5 and 0.75 across the three seeds
  in configuration A, which is the size of the noise band here.
- The grader is a model, and the two configurations swap executor and grader.
  A candidate that pleased only one grader would show as a disagreement; equal
  ties in both configurations are weak evidence, not strong evidence.
- Text-only chat. The task asks for a plan, so the missing verification evidence
  is a body-content failure, not a tool-boundary failure.
- `covered` states trust the cited documents rather than a rerun in this work
  package; no case was re-measured here except FC-25/FC-26.
- Cost comes from the gateway `usage.cost` field. A harness that does not report
  it yields `unrecorded`, and the ledger then cannot be `accepted`.
- The failure set is a snapshot of what the repository recorded by 2026-10-27.
  It is not a benchmark and not a coverage claim about production routing.

## 8. Reproduce

```bash
python3 tooling/check_failure_set.py evals/optimization/failure-set.md
python3 tooling/check_optimization_ledger.py evals/optimization/proposals.md
python3 tooling/check_rebaseline.py \
  --baseline evals/optimization/baseline.json \
  --current evals/role-ab/results/wp07-conduct-guard.json
python3 tooling/check_rebaseline.py \
  --baseline evals/optimization/baseline.json \
  --current evals/role-ab/results/workflow-loop-1.3.0.json
python3 -m pytest tooling/tests/test_check_rebaseline.py \
  tooling/tests/test_check_failure_set.py \
  tooling/tests/test_check_optimization_ledger.py -q
```

The cycle itself is reproducible from the pre-registration; the raw A/B results
are gitignored, and the committed summaries under `evals/optimization/results/`
carry the arm hashes, protocol, per-expectation tallies, usage, cost and
latency.
