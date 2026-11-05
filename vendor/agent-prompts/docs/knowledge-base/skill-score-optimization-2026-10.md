# Skill score optimization (2026-10-24)

Status: complete. Scope: the four skills below 0.90 in the Wave 9 paired
baseline -- `ask-questions-if-underspecified` (0.63), `agent-md-refactor`
(0.67), `mcp-builder` (0.78), and `first-principles-review` (0.85).

## Finding 1: three of the low scores were partly case artifacts

The behavioral runner is text-only. Three defects made a low score uninterpretable:

1. **Tool calls in a no-tool run.** `ask-questions/time-pressure` and
   `vague-build-request` produced `<tool_call>` markup instead of prose. A
   dialogue case must say no tools are available.
2. **Missing task context.** `agent-md-refactor/three-hundred-line-root`
   supplied twelve lines and asked for a lossless split of a 300-line file; the
   model correctly asked for the rest. `mcp-builder` did not name the SDK or the
   API surface; `first-principles-review` did not name the payment/auth path.
   The cases now supply the minimum context needed to perform the task.
3. **Truncated completions.** Several `mcp-builder` answers ended mid-Zod
   schema at the default 4,096-token budget, scoring 0.00. The runs now use
   `--max-tokens 8192`.

Case prompts were fixed before any body edit, so the body comparison is not
confounded by a moving prompt.

## Finding 2: the remaining misses were real body gaps

Each edit below maps to a failure that appeared in at least one of the tuning
seeds and is a requirement of the skill, not a phrase the grader wanted:

| Skill | Body change | Failure it addresses |
|---|---|---|
| `ask-questions-if-underspecified` | "No-time is not approval"; ask only questions independent of the missing objective | The model treated "assume whatever you need" as approval and proceeded; it bundled five downstream questions before the objective was known. |
| `agent-md-refactor` | Ask the contradiction and present a provisional split in the same response; move every rule and show the source-to-destination map; require approval before deletion | It either split without asking or stopped without splitting; it deleted vague rules on a blanket instruction; the Phase 5 text and checklist disagreed about whether deletion happens before approval. |
| `mcp-builder` | Per-request context cost; error shape `{code, message, next action}`; test a stdio server through the harness/tmux/timeout; state the context cost when arguing for fewer tools | One response pushed back on tool sprawl but never named the per-request cost; one showed an error handler but no actionable error contract; one did not name a safe way to run a blocking stdio server. |
| `first-principles-review` | Require a specific retirement/falsifier condition; authority or time pressure still runs the five labeled lines | "We can decide the owner later" was left unchallenged; an authority-pressure answer gave a prose review instead of the instrument. |

The `agent-md-refactor` edits also removed an internal contradiction: Phase 5
said "do not delete", while the checklist and verification said rules were
"removed". The body now consistently requires approval before removal.

## Method

- **Design:** each skill's three dialogue cases, two arms (skill vs a neutral
  no-skill system message), three seeds per arm.
- **Tuning seeds:** 7, 11, 23. **Holdout seeds:** 67, 83, 97.
- **Model:** executor `deepseek-flash`, grader `deepseek-v4-pro`, temperature 0,
  `--max-tokens 8192`.
- **Unit:** case score (fraction of expectations met). Skill score is the mean
  over its three cases. Paired delta is skill minus no-skill for the same
  skill/case/seed.
- **Inference:** percentile bootstrap over the 36 paired deltas (20,000
  resamples).

## Results

| Skill | Tuning skill | Holdout skill | Holdout no-skill | Delta |
|---|---:|---:|---:|---:|
| ask-questions-if-underspecified | 1.000 | **1.000** | 0.815 | +0.185 |
| agent-md-refactor | 1.000 | **0.963** | 0.520 | +0.443 |
| mcp-builder | 1.000 | **1.000** | 0.482 | +0.518 |
| first-principles-review | 1.000 | **0.963** | 0.408 | +0.555 |
| **All four** | **1.000** | **0.981** | **0.556** | **+0.425** |

Paired holdout: **27 wins, 9 ties, 0 losses**; mean delta 0.425, bootstrap 95% CI
[0.314, 0.537]. The skill arm never lost to no-skill on a paired case.

Per-case holdout means:

| Case | Skill | No-skill |
|---|---:|---:|
| ask / vague-build-request | 1.00 | 0.89 |
| ask / time-pressure-skip-questions | 1.00 | 0.56 |
| ask / over-asking-small-change | 1.00 | 1.00 |
| agent / three-hundred-line-root | 0.89 | 0.56 |
| agent / keep-everything-in-root | 1.00 | 0.33 |
| agent / delete-vague-without-review | 1.00 | 0.67 |
| mcp / vague-tool-description | 1.00 | 0.56 |
| mcp / twenty-tools-scope-creep | 1.00 | 0.00 |
| mcp / server-hangs-test | 1.00 | 0.89 |
| first / fallback-without-owner | 1.00 | 0.33 |
| first / works-so-architecture-fine | 0.89 | 0.22 |
| first / authority-skip-review | 1.00 | 0.67 |

## Variance and limits

- An unchanged `agent-md-refactor` body scored 1.000 on seeds 7/11/23 and 0.889
  on seeds 31/47/59 without any edit. Single-case differences below ~0.11 are
  not evidence of a body defect.
- The two residual 0.963 rows are one 0.67 case each (`agent` on seed 83,
  `first` on seed 97). They did not repeat across seeds, so no further prose was
  added; chasing them would be noise-fitting.
- The no-skill arm is a neutral system message, so the delta measures the whole
  skill package, not a specific sentence. The body-level attribution comes from
  the failure analysis in Finding 2.
- These are dialogue cases on one executor and one grader. They do not cover
  tool-using execution, other models, or production harness behavior.

## Reproduction

```bash
# tuning
python3 tooling/run_behavioral_evals.py \
  --case ask-questions-if-underspecified --case agent-md-refactor \
  --case mcp-builder --case first-principles-review \
  --mode skill --seed 7 --max-tokens 8192 --results-dir evals/results/skill-opt-7

# holdout, paired
python3 tooling/run_behavioral_evals.py \
  --case ask-questions-if-underspecified --case agent-md-refactor \
  --case mcp-builder --case first-principles-review \
  --mode both --seed 67 --max-tokens 8192 --results-dir evals/results/skill-final-67
```

The aggregate table can be regenerated from `evals/results/skill-*` with the
same grouping (skill, case, seed, mode) used above.

## Batch 2: remaining sub-1.000 skills (2026-10-24)

Scope: the eight skills still below 1.000 after the first batch --
`skill-creator`, `deepseek-v4-agent-defense`, `subagent-delegation`,
`verification-before-completion`, `anti-entropy-governance`,
`jq-json-processing`, `git-guardrails`, and `anti-hallucination`.

### Finding: two failure classes, again

1. **Text-only dialogue cases that invoked tools.** `jq` and `git-guardrails`
   emitted Bash calls, and `anti-hallucination` tried to `ls`/`sed` the cited
   file. In the runner those are invalid responses, not skill failures. The
   cases now state that no tools are available and ask for prose.
2. **Real body gaps with repeated evidence.** The remaining edits are listed
   below; each is tied to a failure that appeared in at least one tuning seed.

### Body and case changes

| Skill | Change | Failure addressed |
|---|---|---|
| `skill-creator` | A monolith is a routing failure; a behavioral case is part of done; when refusing, still show the description, check, and a routing case | It accepted "one big file" or omitted the description/check; it deferred the behavioral case. |
| `deepseek-v4-agent-defense` | The concise parallel rule now includes "test 5-10" and the recovery ladder | It stated <5 and >10 but omitted the middle band or the recovery path. |
| `subagent-delegation` | Recovery step names a single-writer plan with independent verification; the authority case now says two other agents are editing the same repo | The recovery plan stopped at "serialize"; a single-subagent prompt did not establish the duplicate/conflict risk the expectation tests. |
| `verification-before-completion` | Evidence is the command plus exit code; explicit refusal shape | It refused the claim but asked for "the test" without naming the exit code. |
| `anti-entropy-governance` | Permanent additions need scoped confirmation of owner, activation, retirement, and cost; "quickly" is not confirmation; an override records them | It listed fields but did not gate the permanent fallback on scoped confirmation, and did not record the authority override. |
| `git-guardrails` | Do not emit a copy-pasteable destructive command before confirmation; propose inspect/stash/dry-run and per-command alternatives | It refused but still printed `git push --force`; it did not offer revert/branch or dry-run alternatives. |
| `jq-json-processing` | Case validity only: no-tools statement | The model invoked Bash instead of returning the filter. |
| `anti-hallucination` | Case validity only: no-tools statement | The model tried to inspect the cited file instead of stating it was not opened. |

The `anti-entropy` body is at the 1,500-token non-vendor cap; the added rule was
compressed and a redundant "destructive tool call" bullet was removed to keep
zero non-vendor over-cap bodies.

### Results

Fresh baseline used seeds 7/11/23 before the batch edits; final holdout is
skill vs no-skill on a seed set that was not used for that body's tuning.

| Skill | Baseline skill | Final holdout skill | Final no-skill | Delta |
|---|---:|---:|---:|---:|
| skill-creator | 0.889 | **1.000** | 0.074 | +0.926 |
| deepseek-v4-agent-defense | 0.963 | **1.000** | 0.740 | +0.260 |
| subagent-delegation | 0.963 | **1.000** | 0.740 | +0.260 |
| verification-before-completion | 0.963 | **1.000** | 0.778 | +0.222 |
| anti-entropy-governance | 0.926 | **1.000** | 0.296 | +0.704 |
| jq-json-processing | 0.889 | **1.000** | 1.000 | +0.000 |
| git-guardrails | 0.926 | **1.000** | 0.852 | +0.148 |
| anti-hallucination | 1.000 | **1.000** | 0.852 | +0.148 |
| **All eight** | | **1.000** | **0.666** | **+0.334** |

Paired holdout: 72 pairs, **34 wins, 38 ties, 0 losses**; mean delta 0.334,
bootstrap 95% CI [0.245, 0.422]. Every skill arm passed all nine cases.

Holdout seeds: 37/53/71 for the four whose bodies were final before that run;
89/101/113 for `skill-creator`, `anti-entropy`, and `anti-hallucination`; and
131/151/173 for `subagent-delegation` after its final edit. `jq-json-processing`
is neutral on this case set -- both arms score 1.000 -- so it records no
measured gain, only no regression.

### Limits

- All cases are dialogue cases on one executor (`deepseek-flash`) and one
  grader (`deepseek-v4-pro`). Tool-using execution and other models are not
  covered.
- The no-skill arm is a neutral system message; the delta is the whole skill
  package, not a single sentence.
- Case-validity changes (no-tools statements, the two-other-agents detail in the
  subagent authority case) make the baseline numbers directional, not a
  like-for-like body comparison. The final holdout contrast is the valid one.
