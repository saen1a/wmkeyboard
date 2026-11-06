# H2 shape A/B: old vs merged bodies (2026-10-26)

Status: measured, 3 seeds, free-model proxy only. All seven non-vendor skills
with nine H2 sections were reduced to eight. The merge target stayed at the
section's original position; only the heading boundary moved. The canonical
DeepSeek confirmation (WP-11) is BLOCKED at the provider on 2026-10-27; see the
last section.

## Method

- Old body: `git show 2cd4e43:skills/.../SKILL.md` (pre-merge).
- New body: current `SKILL.md`.
- Skills: `anti-entropy-governance`, `ask-questions-if-underspecified`,
  `deepseek-v4-agent-defense`, `first-principles-review`, `mcp-builder`,
  `skill-creator`, `verification-before-completion`.
- Cases: the behavioral cases for each skill (22 cases; verification has four,
  including the text-only execution simulation).
- Seeds: 7, 11, 23.
- Harness: OpenAI-compatible chat through the Kilo gateway.
  Executor and grader are both `nvidia/nemotron-3-ultra-550b-a55b:free`,
  temperature 0, `max_tokens` 4096, timeout 300 s.
- Tool: `python3 tooling/run_refactor_ab.py --base-ref 2cd4e43 --seeds 7/11/23`.

## Why the free model

The canonical DeepSeek endpoint returned `402 Payment Required` and the OpenAI
key returned `401` during this run. The Kilo gateway was the only working
OpenAI-compatible endpoint. The free 550B model is a proxy for the structural
question ("does moving a heading change behavior?"), not a replacement for the
recorded DeepSeek baseline. Treat the absolute scores as this harness's
baseline, not as a general model ranking.

## Result

66 paired case/seed runs (132 arm-runs).

| Skill | Old | New | Delta | Old pass | New pass |
|---|---:|---:|---:|---:|---:|
| anti-entropy-governance | 1.000 | 1.000 | +0.000 | 9/9 | 9/9 |
| ask-questions-if-underspecified | 0.963 | 0.963 | -0.000 | 8/9 | 8/9 |
| deepseek-v4-agent-defense | 1.000 | 1.000 | +0.000 | 9/9 | 9/9 |
| first-principles-review | 0.778 | 0.889 | +0.111 | 6/9 | 7/9 |
| mcp-builder | 1.000 | 1.000 | +0.000 | 9/9 | 9/9 |
| skill-creator | 0.593 | 0.741 | +0.149 | 4/9 | 5/9 |
| verification-before-completion | 0.944 | 0.945 | +0.001 | 11/12 | 10/12 |
| **All** | **0.899** | **0.9345** | **+0.0355** | **56/66** | **57/66** |

Paired case results: 8 wins / 53 ties / 5 losses. No skill loses on mean score;
the single pass-count regression is one additional partial in the text-only
execution case for verification, where the mean is +0.001.

## What changed

| Skill | Merge |
|---|---|
| anti-entropy-governance | `## Repo bindings` -> bold lead-in inside `## Core principle and hard stops` |
| first-principles-review | `## Boundaries` -> bold lead-in inside `## Use and non-use` |
| ask-questions-if-underspecified | `## Goal` -> paragraph inside `## When to Use` |
| skill-creator | `## Project constraints` -> bold lead-in at the end of `## Workflow` |
| verification-before-completion | `## The Bottom Line` -> bold closing paragraph inside `## Doctrine position` |
| mcp-builder | `## Design rules` -> bold lead-in inside `## Implementation rules` |
| deepseek-v4-agent-defense | `## Why this skill exists` -> intro paragraph under the H1 |

The first attempt merged `first-principles-review` and `verification` at a
different position and merged `skill-creator` into `## Decision gate`; that
order moved use criteria and verification text earlier and scored worse
(overall 0.929 vs 0.950). The final version keeps each section's original
position, and that is the version measured above.

## Limits

- One free model/harness, three seeds, 22 cases. The grader is the same model.
- The execution case is a text-only simulation; it is noisy and is not a
  tool-using run.
- The free endpoint produced a few empty or malformed responses; those are
  included as graded, not silently dropped.
- This is a structural non-inferiority check. It does not claim a general
  quality gain, and it does not replace the DeepSeek baseline for model
  behavior.

## Decision

Accept all seven merges. `report_skill_shape.py` now reports `H2>8=1`, and that
one is the frozen vendor copy `misakanet`.

## Canonical-model confirmation (WP-11, BLOCKED)

Attempted 2026-10-27 to confirm the table above on the canonical DeepSeek
model with `$DEEPSEEK_API_KEY`. The credential is valid; the account has no
credit. Evidence:

- `GET https://api.deepseek.com/v1/models` -> HTTP 200, model list
  `deepseek-flash`, `deepseek-v4-pro` (the tool defaults). Auth passes and the
  model names are unchanged.
- `POST https://api.deepseek.com/v1/chat/completions` with `deepseek-flash`,
  one user turn (`Say OK`), `max_tokens` 8, `temperature` 0 -> HTTP 402.
  Body: `{"error":{"message":"Insufficient Balance (request_id:
  9394191c-8230-4ef2-b55f-e04edebcf291)","type":"insufficient_balance_error",
  "param":null,"code":"invalid_request_error"}}`.

The A/B command was therefore not run for seed 7, and seeds 11 and 23 did not
start. No canonical-model result exists for any skill. This is not a
confirmation, a partial confirmation, or a discrepancy: it is an absent
measurement.

The pending command, to run unchanged when credit returns:

```text
python3 tooling/run_refactor_ab.py --base-ref 2cd4e43 \
  --skills anti-entropy-governance first-principles-review \
  ask-questions-if-underspecified skill-creator \
  verification-before-completion mcp-builder deepseek-v4-agent-defense \
  --seed 7 --timeout 300 --max-tokens 4096
```

then seeds 11 and 23 under their own results dirs. The free-model result above
(0.899 old vs 0.9345 new, 56/66 vs 57/66, 8 wins / 53 ties / 5 losses) remains
the only evidence for the seven merges; no merge is reopened on this record.
No free or proxy model was substituted, because this WP is specifically the
canonical-model confirmation.
