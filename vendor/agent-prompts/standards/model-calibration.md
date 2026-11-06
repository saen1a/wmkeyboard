# Model calibration standard

Status: ACTIVE (2026-10-23). First calibration record, not a benchmark report.

Class: prompt-generation. It records the model and harness assumption behind the
AP-01 budgets and the SK-03 skill shape targets. It does not set prompts.

Evidence: `evidence/prompt-research-2026-10.md` (S1, S2, S16).

## MC-01 -- Record the target, not the category

Name the exact model id the runtime uses (provider/model) and the harness
(client, scaffold, tool loop). "A frontier model" or "the default model" is not
a calibration record (S16).

## MC-02 -- Capacity is measured, not assumed

A model's usable instruction capacity is the number of simultaneous constraints
it follows before accuracy degrades. Use a published curve only when its task
is close to this library's prompt shape (named constraints, one system prompt);
otherwise run a small probe against the target model and record it. Do not
infer capacity from context-window size.

## MC-03 -- The budget is set by the weakest supported target

The AP-01 element budgets and token targets are calibrated to the least capable
model the library is expected to run on. A stronger model does not justify
raising them; it only means the budget has headroom. Raising a budget requires a
paired eval and a new row in this table (AP-01).

## MC-04 -- Record

Each row carries: target model id, harness, measured capacity, source, date,
owner, and the AP-01 tier it justifies. A row without a date or source is
invalid.

## Current calibration

| Target (provider id per consumer) | Harness | Capacity (constraints) | Source | Date | Owner | AP-01 tier |
|---|---|---|---|---|---|---|
| DeepSeek V4 Pro (`deepseek-v4-pro`) | consumer harness, not measured here | starts dropping near 750; about half ignored by 2,000 (keyword-density proxy) | S2 (Arize 2026) | 2026-10-23 | library | standard (governing): <= 12 elements, <= 1,000 tokens |
| GPT-5.5 | vendor API, agent scaffold | ~99% through 5,000 (keyword-density proxy) | S2 | 2026-10-23 | library | headroom; no budget raise |
| Gemini 3.1 Pro | vendor API, agent scaffold | strong through 5,000 (keyword-density proxy) | S2 | 2026-10-23 | library | headroom; no budget raise |
| Claude Opus 4.7 | vendor API, agent scaffold | about 50% at 5,000 (keyword-density proxy) | S2 | 2026-10-23 | library | headroom; no budget raise |

Scope note (2026-10-27): the governing row was measured on `deepseek-v4-pro`,
not on the model the active runtime uses. The active runtime is
`deepseek-v4.1-flash` via `opencode-go`, and there is no calibration measurement
for it. The standard-tier budget is therefore **unvalidated for the active
runtime** and must not be cited as that model's limit; it remains the upper
bound until a probe is measured and recorded here (MC-02, MC-04).

The governing row is DeepSeek V4 Pro because it is the weakest target the
library supports today. If a consumer runs only a stronger model, that is a
rationale for a separate profile with its own paired eval, not a global budget
change.

An unmeasured runtime is not a calibration row and must not be used to justify a
budget. Measure it first (MC-02).

The S2 numbers are a keyword-density proxy, not a reasoning benchmark. Use them
as a degradation curve, not as a general capability claim (MC-02).

## Calibration protocol

1. Name the exact model id and harness in the evaluation record.
2. Use a published capacity result only if its task matches this prompt shape;
   otherwise run a 20-30 constraint probe with the target model and record the
   degradation point.
3. Map the result to a tier (standard, dual-workflow, primary) with the AP-01
   ceilings as the upper bound.
4. Record the row here with source, date, and owner.
5. Re-run when the model, harness, tool set, or output schema changes. Treat a
   model change as a harness event (S16).

## Cross-refs

- `agent-prompt-standard.md` -- AP-01 budgets and the calibration note
- `skill-system-standard.md` -- SK-03 shape targets
- `evidence/prompt-research-2026-10.md` -- S1, S2, S16
- `../docs/knowledge-base/skill-prompt-refactor-2026-10.md` -- R1 plan
