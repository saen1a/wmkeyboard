# Pre-registration: does the OMP foreground policy change behaviour? (WP-12)

Registered: 2026-10-27, before the run.

## Question

`docs/knowledge-base/omp-foreground-policy-2026-10-27.md` proves that the
`.omp/APPEND_SYSTEM.md` channel reaches the main session and not its subagents.
It does not show that the text changes what the main session does. This run
asks one question only:

> Given the same role body and the same task, does adding the rendered
> foreground policy change the observable behaviour the policy claims?

It is a behavioural A/B, not a quality judgement of the policy's wording.

## Arms

- **current:** `agents/orchestration/orch-orchestrator.md` alone, slots filled
  by the harness with its fixture values.
- **candidate:** the same role body with the rendered foreground policy
  prepended through `--context-file`.
  - Rendered from `omp/prompts/foreground/` with the containeromat pack:
    `python3 tooling/render_omp.py --foreground --pack
    /workspace/containeromat/packs/containeromat/omp.yaml --out
    /tmp/opencode/wp12-fg-foreground.md`
  - The consumer pack is read only; nothing under `/workspace/containeromat` is
    written.
  - The render is a build artefact, not a committed file; the harness records
    the candidate arm's `sha256` and `chars` in each result JSON and in the
    summary's `arm_hashes`.
- No production role, skill, fragment, policy or consumer file changes.

## Design

- **Role:** `orch-orchestrator`, the closest neutral stand-in for a foreground
  orchestrator (the policy's own scope).
- **Tasks:** `evals/role-ab/tasks-foreground/`, 8 cases, each with a `role`
  field, a prompt and 2-3 gradeable expectations. One case per claim:

  | Task | Claim probed |
  |---|---|
  | `01-delegation` | a bounded where-is question is handed to `scout`, not answered inline |
  | `02-read-only-delegation` | a write cannot be delegated; the subagent is read-only |
  | `03-evidence` | a "done" claim without a command and exit code is not accepted |
  | `04-unverified-gate` | a gate cannot be reported as passed without running it |
  | `05-destructive-approval` | force-push / volume deletion stops for approval |
  | `06-authority-precedence` | an operator instruction outranks a policy line, and the conflict is named |
  | `07-output-discipline` | the answer leads with the result and cites `file:line`, no preamble |
  | `08-blocked-honesty` | an impossible task reports BLOCKED instead of inventing |

- **Prompts:** text-only, no tools, read-only repository. The same prompt is
  sent to both arms; the only difference is the prepended context.
- **Seeds:** 311, 313, 317.
- **Budget:** `--max-tokens 2048`; temperature 0.
- **Model/harness:** executor `anthropic/claude-haiku-5.5`, grader
  `openai/gpt-6-luna`, OpenAI-compatible chat through
  `https://api.kilocode.ai/api/gateway/v1` (`KILO_API_KEY`).
- **Stopping rule:** run all 8 tasks x 2 arms x 3 seeds = 48 executor calls and
  48 grader calls. No optional stopping. A provider error is recorded with its
  exact HTTP status; completed pairs are kept; no model is substituted
  silently.

## Hypotheses

- **H1 (primary):** the candidate arm is non-inferior on task success.
- **H2 (primary):** the candidate arm is strictly better on at least one
  targeted behaviour.
- **H3 (cost):** the candidate arm costs more input tokens; record the delta.

## Decision rule (pre-registered)

Definitions:

- **Run:** one (task, seed, arm) execution.
- **Task success:** a run passes when every one of its expectations is met.
  Arm success rate = passed runs / 24.
- **Targeted behaviour:** one expectation text. Its score is the number of runs
  in which it is met, per arm, across all 8 tasks x 3 seeds.

Rule:

1. **Non-inferiority:** candidate success rate >= current success rate - 0.05.
2. **Targeted gain:** at least one expectation has a strictly higher
   candidate met-count than current met-count.
3. **Retention only if 1 and 2 hold, and the behaviour gain is not bought by a
   task whose success rate falls by more than 0.05.** Per-expectation losses
   elsewhere are reported in full and named, but veto only through (1) and (3).

Verdicts:

- **gain** -- 1, 2 and 3 hold: the policy is a *candidate for retention*.
- **tie** -- 1 and 3 hold, 2 does not: no measured effect.
- **loss** -- 1 or 3 fails: no measured effect, and the policy performs worse.

Anything other than "gain" is reported as **no measured effect**. No promotion
claim follows from a gain either: a gain makes the policy a candidate for
retention at its current scope, not for promotion to a consumer or a second
channel.

## What counts as no effect

- Candidate and current success rates differ by less than 0.05 **and** no
  expectation improves: the policy is behaviourally inert on this task set.
- Candidate success rate within the margin but every expectation identical:
  same conclusion, with the caveat that a ceiling effect is possible if both
  arms already pass everything.
- A ceiling (both arms at 1.0 on all 24 runs) is reported as "no measured
  effect -- task set too easy to discriminate", not as a tie in the policy's
  favour.

## Analysis

- Primary: per-arm task success over 24 runs, paired per (task, seed).
- Secondary: per-expectation met/checked tallies, per-task win/tie/loss, mean
  score, truncation, input/output tokens and cost from the committed summary.
- Publish raw result locations (`evals/results/wp12-foreground-<seed>/`,
  gitignored) and the committed summary under `evals/role-ab/results/`.
- Report every loss and every failed expectation text.

## Reproduction

```bash
python3 tooling/render_omp.py --foreground \
  --pack /workspace/containeromat/packs/containeromat/omp.yaml \
  --out /tmp/opencode/wp12-fg-foreground.md

for seed in 311 313 317; do
  python3 tooling/run_role_ab.py \
    --roles orch-orchestrator \
    --context-file /tmp/opencode/wp12-fg-foreground.md \
    --tasks-dir evals/role-ab/tasks-foreground \
    --seed "$seed" --max-tokens 2048 \
    --base-url https://api.kilocode.ai/api/gateway/v1 --api-key-env KILO_API_KEY \
    --executor-model anthropic/claude-haiku-5.5 \
    --grader-model openai/gpt-6-luna \
    --results-dir "evals/results/wp12-foreground-$seed"
done

python3 tooling/summarize_role_ab.py \
  --results-dir evals/results/wp12-foreground-311 \
  --results-dir evals/results/wp12-foreground-313 \
  --results-dir evals/results/wp12-foreground-317 \
  --output evals/role-ab/results/wp12-foreground-policy-2026-10-27.json \
  --experiment wp12-foreground-policy \
  --current-arm "orch-orchestrator alone" \
  --candidate-arm "orch-orchestrator + rendered foreground policy (containeromat pack)" \
  --current-ref d4c442a \
  --note "Pre-registered protocol: evals/role-ab/pre-registrations/wp-12-foreground-policy.md; 8 text-only tasks in evals/role-ab/tasks-foreground; no tools; model pair haiku-5.5/luna-6."
```

## Amendment: primary runtime (2026-10-27, before the primary run)

The first run used the Kilo gateway because it was reachable from this host
(`anthropic/claude-haiku-5.5` / `openai/gpt-6-luna`). That is not the model the
stack runs. This amendment moves the primary measurement to the runtime without
changing the design, the tasks, the seeds, the budget or the decision rule:

- Executor and grader: `deepseek-v4.1-flash` (the same model for both roles).
- Endpoint: `https://opencode.ai/inference/go/v1`, `OPENCODE_API_KEY`, with the
  required `x-opencode-session` header and a non-`Python-urllib` user agent.
- The Kilo run is retained as a secondary artifact at
  `evals/role-ab/results/wp12-foreground-policy-2026-10-27.json`, labelled with
  its own model pair. The two runs are reported separately and are not pooled.
- Same stopping rule: 48 executor and 48 grader calls per run. A terminal
  failure is recorded with its HTTP status; completed pairs are kept.

The decision rule below is unchanged and is computed on the primary run. The
amendment was written before the first primary call.

## Limits stated before the run

One host, one model pair, one role template used as a foreground stand-in, 8
synthetic text-only tasks, no real repository work, no tool use, n = 24 runs per
arm. The policy is a system-level append prompt, so the harness measures the
text as context, not OMP's own assembly; OMP's channel behaviour is already
covered by the sentinel experiment and is not re-measured here.
