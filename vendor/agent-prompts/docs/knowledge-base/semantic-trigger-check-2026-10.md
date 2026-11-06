# Semantic trigger check (WP-06), 2026-10-27

Owner: library maintainer.

Question: the lexical checker (`tooling/check_skill_routing.py`) proves that
each skill's trigger vocabulary is present and distinct, but it only scores
shared words. Does a judge model route the same `evals/trigger/*.json` prompts
to the intended skill, and if not, where does it disagree?

This is a report. Nothing in the gate changed, no skill description or body was
edited, and the lexical checker is still the required check.

## Tool

`tooling/check_semantic_routing.py` (new, advisory):

- Loads the same 24 skills and the same 24 case files through
  `check_skill_routing.load_skills`, so both checks read one skill universe.
- For each positive and negative case, asks a judge model to rank at most three
  skill ids from id + description alone.
- Compares the ranking to the case file: `hit@1`, `hit@k`, false negatives
  (positive not in top-k), false positives (the case file's skill inside top-k
  on another skill's negative prompt), missed owners (declared owner not
  first), rank-1 near misses, near-collisions (top-1 cross-picks between a
  pair, mutual or total >= 2), and coverage.
- `--dry-run` prints the plan and the first payload with no network;
  `--judge fixture --fixture PATH` replays recorded selections so the parsing,
  comparison, and report paths are testable offline.
- Exit 0 for any completed report, 2 only for setup/input errors (missing key,
  bad case file, unusable provider). A misroute never fails the run.

Provider and model (fixed for both runs, no substitution):

- base URL `https://api.kilocode.ai/api/gateway/v1`
- model `nvidia/nemotron-3-ultra-550b-a55b:free`
- key from `KILO_API_KEY`

## Run

    python3 tooling/check_semantic_routing.py

- 24 skills, 24 case files, 126 prompts (75 positive, 51 negative)
- coverage 126/126 prompts judged (100.0%), 24/24 skills exercised as positives
- wall time about 3 minutes per run at `--workers 4`

Two complete runs were made before the free-model quota closed. Both used the
comparison and metric code that ships here; the only later change is the
additive rank-1 near-miss list and transport hardening (a socket timeout now
retries and reports an unjudged prompt instead of raising a traceback), which
the fixture tests cover. The table below is the only record of those runs: no
per-prompt artifact or summary JSON was committed, so the counts are the
evidence. A third run was attempted after the quota closed and is **BLOCKED**:
`HTTP 429` / `Free model usage limit reached`; no substitute model was used.

| run | hit@1 | hit@k | false positives | missed owners | near-collisions |
|---|---|---|---|---|---|
| 1 | 74/75 (98.7%) | 75/75 (100%) | 1 | 2 | 0 |
| 2 | 74/75 (98.7%) | 75/75 (100%) | 2 | 2 | 0 |

The two stable case findings are `verification-before-completion/negative/1`
and `subagent-delegation/negative/1`; both are described below.

Per-skill columns are in the report; every skill except `grilling` put all of
its positives first (2/3 for `grilling`), and 20 of 24 skill rows had no finding
at all in both runs.

## Findings

Stable across both runs:

1. `verification-before-completion/negative/1` -- "Write the unit tests for
   this module", declared owner `anti-hallucination`. The judge returns
   `[ask-questions-if-underspecified, verification-before-completion,
   subagent-delegation]`; the declared owner is absent. This is a false
   positive for `verification-before-completion` and a missed owner for
   `anti-hallucination`. Read: the prompt is about writing tests, which no
   skill owns, and "cite the source" framing that would pull
   `anti-hallucination` is not in the text. The case's owner is the part that
   does not follow from the prompt.
2. `subagent-delegation/negative/1` -- "Review this diff for correctness and
   cite evidence for each finding", declared owner
   `verification-before-completion`. The judge picks `caveman-review` first and
   `anti-hallucination` second; the declared owner is third or absent. Read:
   "review this diff" is the review skill's intent, so the case names a
   plausible but contested owner. Not evidence that either description is
   broken.

Run-dependent:

3. `first-principles-review/negative/1` -- "We are retiring the old code
   path - tell me the safe deletion order...", owner
   `anti-entropy-governance`. The owner ranked first in both runs; the case
   skill appeared third in run 2 and outside the top three in run 1. That is a
   false positive by the top-k rule and a non-finding in practice: third place
   on a deletion-order prompt is a reasonable adjacent skill.

No near-collision reached the threshold in either run, and no positive case
fell outside the top three. The lexical checker is also green on all 24 case
files (`check_skill_routing.py --fail-on-warn`: 24 skills, 24 case files, 0
violations), so the two checks agree that the trigger vocabulary is present;
they differ only on the two contested negative owners above.

## Interpretation

- The judge does not reproduce two negative-case owners. Both prompts are
  about writing tests or reviewing a diff, and the declared owners are
  verification/anti-hallucination skills whose trigger descriptions are about
  claims and evidence. The likely fix is case design (owner choice or prompt
  wording), not a skill description edit. That is a content decision and is
  not part of this work package.
- Run-to-run variance on one free endpoint: the same prompt moved in and out of
  third place between runs at temperature 0. One sample per prompt is enough to
  find contested cases but not enough to rank skills or set a threshold.
- `hit@k` is 100% and `hit@1` is 98.7%: semantic routing is not the weak point
  of this library on its own fixtures. The measured failures are fixture
  ownership questions, which a judge cannot settle without a product decision.

## Limits

- Descriptions only; the judge never sees skill bodies, so a thin description
  and a wrong skill look the same.
- The 24 case files are the library's own fixtures, not user traffic. Coverage
  is the registered skill set, not real routing demand.
- The free model is rate limited per account. Two full runs exhausted the
  quota: a third run at 2026-10-27 returned
  `BLOCKED semantic-routing: no prompt could be judged:
  nvidia/nemotron-3-ultra-550b-a55b:free HTTP 429 {"error":"Rate limit
  exceeded","error_type":"rate_limit_exceeded","message":"Free model usage
  limit reached. Please try again later, or switch to a paid model or your own
  API key."}`. The tool reports that as a BLOCKED setup error and exits 2; it
  does not fall back to another model.
- No threshold is agreed, so the check stays on demand. Adopting it as a gate
  would need repeated samples (or a paid endpoint), a stability number, and a
  decision on the two contested case owners first.

## Decision

Report only. `check_skill_routing.py --fail-on-warn` remains the gate and is
unchanged. No skill description, body, case file, or fragment changed. The
next step, if this is picked up, is to settle the two negative-case owners and
then re-run with multiple samples per prompt.

## Reproduce

    python3 tooling/check_semantic_routing.py --dry-run
    python3 tooling/check_semantic_routing.py --case verification-before-completion
    python3 tooling/check_semantic_routing.py
    python3 -m pytest tooling/tests/test_check_semantic_routing.py -q
