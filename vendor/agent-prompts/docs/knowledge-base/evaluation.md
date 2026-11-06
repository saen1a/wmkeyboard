# Evaluation system

Audience: future agents and the operator. This file records what exists today
to test prompts, what ships, and where the design comes from.

Citation convention: `containeromat:<path>` are citations into that checkout
(not links). Sources read 2026-09-20.

Related: [surfaces.md](surfaces.md), [governance.md](governance.md),
[integration-status.md](integration-status.md).

## 1. What is evaluated, on which axis

| Axis | Question | Tooling | Status |
|---|---|---|---|
| Acceptance (per prompt) | Does the agent emit the required structure/behavior on task prompts? | XML eval-sets + `run-prompt-eval.py` | 3 sets (001/002/003), dry-run baselines green |
| Structural conformance (templates) | Do templates hold the skeleton, order, budgets, fragments? | [tooling/validate_templates.py](../../tooling/validate_templates.py), `check_fragments.py` | shipped, fixture-tested |
| Adoption structure (live agents vs templates) | Do live agents keep the template block sequence and byte-exact fragments? | [tooling/check_instantiation.py](../../tooling/check_instantiation.py) | 16 mapped rows (16/16 OK), content NOT compared by design |
| Trigger routing (skills, Tier 2) | Does each skill's description carry the vocabulary users say, and stay distinct? | [tooling/check_skill_routing.py](../../tooling/check_skill_routing.py) | shipped; blocking in containeromat CI (24/24 case files, `--fail-on-warn`) |
| Skill shape (advisory) | Is the body the right size and shape for its class? | [tooling/report_skill_shape.py](../../tooling/report_skill_shape.py) | shipped 2026-10-23; report-only by design (SK-03) |
| Behavioral pressure (skills, Tier 3) | Does the workflow hold when the prompt argues for skipping it? | [tooling/check_behavioral_evals.py](../../tooling/check_behavioral_evals.py) (structural) + [tooling/run_behavioral_evals.py](../../tooling/run_behavioral_evals.py) (execution) | structural: CI; execution: on demand; baseline 11/12 (section 5) |
| Tool-set stability | Is the tool definition block canonical, ordered, hashed, and mask-only? | [tooling/check_tool_set.py](../../tooling/check_tool_set.py) | shipped 2026-10-25; consumer manifest required |
| Findings ledger | Is every review finding tracked with a stable id, severity, evidence, and a closed state? | [tooling/check_findings_ledger.py](../../tooling/check_findings_ledger.py) | shipped 2026-10-25; `--require-clean` gates a unit |
| Run journal | Is the run history append-only and consecutive, with matching action receipts and evidence on every close? | [tooling/check_run_journal.py](../../tooling/check_run_journal.py) | shipped 2026-10-25; consumer writes `events.jsonl` |
| Token/cache assembly | Is the static prefix free of volatile bytes and duplicate instructions, and above the cache minimum? | [tooling/check_token_efficiency.py](../../tooling/check_token_efficiency.py) | shipped 2026-10-25; static gate; runtime hit rate is harness telemetry |
| Long-horizon run state | Does a run state carry durable goal, progress, budget, and checkpoint invariants? | [tooling/run_state.py](../../tooling/run_state.py), [tooling/check_long_horizon.py](../../tooling/check_long_horizon.py) | shipped 2026-10-25; deterministic library gate; no live run yet |

## 2. Existing: subagent acceptance eval-sets

| Set | Target | Tasks | Location |
|---|---|---|---|
| `eval-set-001.xml` | `compose-step` (v3 acceptance) | 8 (tmpfs/read_only, broken YAML diagnosis, CMD-SHELL, postgres:18 tag, missing AGENTS.md, secret handling, forbidden `down -v`, exception registry) | `containeromat:.kilo/orchestrator/evals/eval-set-001.xml` |
| `eval-set-002.xml` | `orchestrator` (4) + `reviewer` (4) | 8 (gate flow, escalation ladder, verify-or-escalate, forbidden tools; recall review, exception-not-bug, diagnostic REJECT, ambiguity flag) | `containeromat:.kilo/orchestrator/evals/eval-set-002.xml` |
| `eval-set-003.xml` | `ci-step` | 8 (propose-before-apply, red-gate BLOCKED, gate battery, never push/merge, allowlist refusal, re-scope, coupling greps, per-command exit codes) | `containeromat:.kilo/orchestrator/evals/eval-set-003.xml`; library copy at [evals/ops-ci-executor/eval-set-003.xml](../../evals/ops-ci-executor/eval-set-003.xml) |

Format: Anthropic Tool Evaluation Cookbook (S18); expected responses are
structural (block type + required keys + behavioral markers), not byte-exact
(`eval-set-001.xml:2-8`). Each task carries `<prompt>`, `<expected_response>`
and `<success_criteria>`.

Baselines (dry-run): `containeromat:.kilo/orchestrator/evals/v3-iteration-1.md`
(001, Pass@1 100.0%), `baseline-v2.md`, and
[evals/ops-ci-executor/ci-step-baseline.md](../../evals/ops-ci-executor/ci-step-baseline.md)
(003, Pass@1 100.0%, 8/8, 233 tool calls). Harness history and decisions:
`containeromat:.kilo/orchestrator/decisions.md`.

## 3. The harness: `run-prompt-eval.py`

`containeromat:scripts/run-prompt-eval.py` -- thin comparison harness for prompt
versions:

- `--harness kilo` shells out to `kilo agent run --subagent <name>` (real
  runtime; requires the kilo CLI + a configured model); `--subagent` selects the
  registered subagent (default `compose-step`).
- `--harness dry-run` does not call a model; it simulates each task with a
  canned response (`--sim-pass-all` / `--sim-pass-fraction`) so the pipeline and
  report format are validated structurally.
- Scoring is marker-based: each non-trivial expected token (>=4 chars,
  alnum + `[_-/:# ]`) that also appears verbatim in the response counts as a
  hit; Pass@1 = fraction of markers found. The raw response is preserved for
  manual review (`run-prompt-eval.py:26-33`).
- Fail-loud: a task missing `id` / `prompt` / `expected_response` exits with an
  ERROR before any model call (`run-prompt-eval.py:47-71`). The negative
  fixture `scripts/lib/tests/fixtures/eval-set-broken-entry.xml` plus two
  black-box tests pin that behavior (`containeromat:CHANGELOG.md:43-45`).
- Exit code: 0 on report written, 1 on eval failure or harness error.

Live-model eval remains **unverified**: the CI runner has no kilo CLI on PATH
(`CHANGELOG.md:46-47`); the recorded baselines are dry-run only.

## 4. Library-side conformance and the adoption audit

| Tool | Checks | Notes |
|---|---|---|
| [tooling/validate_templates.py](../../tooling/validate_templates.py) | Frontmatter schema + enums, block order (workflow or scope variant), fragment byte-identity, element budget, hygiene, no slot residue in instantiations | Fixture tests in [tooling/tests/test_validators.py](../../tooling/tests/test_validators.py) |
| [tooling/check_fragments.py](../../tooling/check_fragments.py) | sha256 of every fragment vs [tooling/fragments.manifest.json](../../tooling/fragments.manifest.json); both fragments are library-canonical (conduct 1.0.0, doctrine 1.3.1); `--upstream <dir>` is a legacy diagnostic | Consumer-runnable without an upstream checkout; manifest mode is authoritative |
| [tooling/check_instantiation.py](../../tooling/check_instantiation.py) | Structural audit only: block sequence, doctrine/conduct byte-identity vs fragments, output-last, workflow prose, hard_rules bullet shape | 16 mapped rows; content differences are intentional containeromat vocabulary |
| [tooling/report_skill_shape.py](../../tooling/report_skill_shape.py) | Skill shape metrics: body/whole tokens, headings, references, description length, doctrine section, rigid key; advisory targets | Report-only by default; fixture tests in [tooling/tests/test_report_skill_shape.py](../../tooling/tests/test_report_skill_shape.py) |

Adoption status: the audit maps all 16 live agents (all 8 review tracks, both
reviews, skeptic, doc-writer, orchestrator, compose-step, ascii-step and
ci-step). Each mapped row prints `OK <agent> -> <template>` and the tool exits 1
if any row fails (`check_instantiation.py:271-281`). The 16/16 result was
re-verified on 2026-09-20 after adding the `operations-ci-implementer` row.
`packs/containeromat.md` documents the mapping plus the three containeromat
flavor variants.

## 5. Wave 5 (shipped 2026-09-20) -- Tier-2 and Tier-3 skill evals

### Tier 2 -- trigger and routing (deterministic, no model judgement)

Built: [tooling/check_skill_routing.py](../../tooling/check_skill_routing.py)
(432 lines) with fixture tests
([tooling/tests/test_check_skill_routing.py](../../tooling/tests/test_check_skill_routing.py)).
Design elements:

- Skill universe = every `SKILL.md` under `<root>/skills/**`; name from
  frontmatter `name:` (fallback: directory), description from frontmatter
  `description:` (fallback: first paragraph after the H1)
  (`check_skill_routing.py:19-24,207-222`).
- Case files: `<root>/evals/trigger/<skill-name>.json`, one per skill:
  `{"skill", "positive": [{"prompt", "top_k"}], "negative": [{"prompt", "owner"}]}`
  (`check_skill_routing.py:28-36`).
- Scoring: lowercased, stopword-filtered, naively stemmed token sets;
  `score = |prompt & desc| / sqrt(|prompt| * |desc|)`; rank 1 is the best score,
  ties break by name (`check_skill_routing.py:39-43,111-117,228-231`).
- Checks: positive prompts must rank their skill inside `top_k` (default 3);
  negative prompts (owner declared) must NOT rank the skill inside `top_k`;
  description pairs above the Jaccard collision threshold (default 0.55) fail;
  a missing case file is a WARN unless `--fail-on-warn`
  (`check_skill_routing.py:54-56,288-361`).
- FAIL types: `invalid-case`, `unknown-skill`, `duplicate-case`,
  `no-trigger-cases`, `positive-rank`, `negative-trigger`, `unknown-owner`,
  `collision`, `duplicate-skill`. Exit 0 when no FAIL, 1 otherwise; `--json`
  prints a machine-readable summary (`check_skill_routing.py:44-56,370-428`).
- State: shipped 2026-09-20; 24/24 case files as of 2026-10-25 under
  `evals/trigger/`, and containeromat's `compose-validate.yml` runs the checker
  with `--fail-on-warn` as a blocking gate, so a missing case file fails.

### Tier 3 -- behavioral pressure cases (shipped 2026-09-20)

- Cases test that the five discipline skills (including `git-guardrails`) keep
  their workflow under three
  pressure kinds: **time pressure**, **sunk cost**, and **authority pressure**.
- Case files: `evals/behavioral/<skill>.json` (skill-creator v2 schema plus the
  optional `kind` and `pressure` tags). `execution` cases carry fixtures under
  `evals/fixtures/`; `dialogue` cases do not need one.
- Structural gate: `tooling/check_behavioral_evals.py` (free, blocking in
  containeromat CI) validates schema, ids, kinds, pressure coverage and fixture
  paths.
- Execution: `tooling/run_behavioral_evals.py` is harness-agnostic (any
  OpenAI-compatible chat endpoint; default DeepSeek). It no longer depends on a
  kilo CLI on the runner. `execution` cases need a tool-using executor and are
  skipped by default; `--allow-execution-http` simulates them.
- AP-13.8 deferral (2026-10-25): `long-horizon-run` ships without a paired
  baseline; owner library maintainer; follow-up: LH-13 metrics (units per hour,
  tokens per verified unit, recovery time, stall count) once a consumer harness
  is live.
- Paired mode (2026-10-23): `--mode both` runs each case with the skill body and
  with a neutral no-skill system message; `--seed` is sent as the request seed
  when set, and a provider that rejects the field fails the run rather than
  silently ignoring it. Results are written per skill and mode (`<skill>.skill.grading.json`,
  `<skill>.no-skill.grading.json`) and carry a `run` block with executor model,
  grader model, harness, seed, temperature, and UTC timestamp. This is the R1
  pairing mechanism; it does not replace the grader.
- Baseline (2026-09-20): 11/12 dialogue cases fully pass, one partial
  (`anti-entropy-governance` authority case) -- `evals/results-baseline.md`.
- Wave 7 adds `evals/behavioral/subagent-delegation.json` (3 dialogue cases,
  time/authority/sunk-cost). It is validated structurally and is not part of
  the 11/12 baseline. Its paired baseline is recorded in
  `evals/results-baseline.md` (seeds 7, 11, 23).
- R2 splits (2026-10-23): `jq-json-processing` (2,735 -> 923),
  `skill-creator` (3,417 -> 1,171), and `first-principles-review`
  (2,703 -> 1,373) moved their long-form material to references and gained
  class-required dialogue cases. AP-13.8 baselines recorded in
  `evals/results-baseline.md` (seeds 7, 11, 23): skill mean 0.869 vs no-skill
  0.555 across 13 skills. The structural results remain reproducible with
  `report_skill_shape.py`; the paired table is the efficacy evidence.
- R3 splits (2026-10-23): `mcp-builder` (3,648 -> 1,074),
  `anti-entropy-governance` (3,575 -> 1,455),
  `deepseek-v4-agent-defense` (3,443 -> 1,121), and `agent-md-refactor`
  (1,883 -> 984) moved detail into a reference and gained three dialogue cases;
  `ask-questions` and `verification-before-completion` were trimmed to eight H2
  sections. Baselines are recorded in `evals/results-baseline.md` with the R2
  table (seeds 7, 11, 23).

### Tier 0 -- skill shape (advisory, shipped 2026-10-23)

`tooling/report_skill_shape.py` measures body tokens, whole-file tokens, line
and heading counts, reference files, description length, `rigid`, and the
doctrine section. It exits 0 by default; `--fail-on-advisory` promotes the
non-vendor shape targets to a failure once the library has migrated (vendor
bodies are frozen, SK-10).

It exists because the strongest available evidence is about shape (S25): the
metadata layer is always loaded, the body is loaded on trigger, and references
load only when routed. Measured 2026-10-31 (`docs/measured-state.md`): 25 skills, body tokens 439 /
1,147 / 1,583, 1 body over 1,500 (a frozen vendor copy; 0 non-vendor), and 11
with references. The 2026-10-31 measurement, after
`untrusted-content-handling`: 25 skills, 438 / 1,147 / 1,582, same over-cap
body, 11 with references. Those are the 2026-10-31 measurements and stay as
history; `docs/measured-state.md` is the live value (27 skills after Wave 12,
body tokens 438 / 1,101 / 1,582, 0 non-vendor over cap). The pre-refactor snapshot and the remaining
waves are in
[skill-prompt-refactor-2026-10.md](skill-prompt-refactor-2026-10.md); shape
alone is never an efficacy claim (SK-13).

## 6. Upstream inspiration (live-fetched 2026-09-20)

Source: `https://raw.githubusercontent.com/addyosmani/agent-skills/main/evals/README.md`
(fetched in this session). Its three-tier model:

| Tier | What it checks | Runs | Cost |
|---|---|---|---|
| 1. Structural | Frontmatter, naming, required sections, command parity | CI | Free |
| 2. Trigger and routing | Positive prompts rank their skill top-k; negative prompts do not; no near-colliding descriptions | CI | Free |
| 3. Behavioral | An agent following the skill satisfies its `expectations[]` | On demand | Tokens |

Adopted ideas: the per-skill case-file format with `positive`/`negative`
triggers and an `owner` on negatives (turning a negative into a pairwise
routing test instead of a vacuous one); the lexical-approximation framing (fix
the description, not the eval); a rank-1 rate as the metric to watch, with a CI
floor. Differences in our design: the collision threshold defaults to 0.55
Jaccard (upstream errors at >=75% and warns at >=50%), `top_k` defaults to 3,
and missing case files are WARN-by-default; the gate is now complete.

The behavioral tier follows **Anthropic skill-creator v2**'s `evals.json`
schema (`id`, `prompt`, `expected_output`, optional `files[]`,
`expectations[]`) plus an optional `kind` field (`execution` | `dialogue`,
default `execution`) as described by the same upstream README. Our Tier-3
design uses `kind: execution` for the pressure cases.

## 7. Running and gaps

| Task | Command | Prerequisite |
|---|---|---|
| Prompt lint (all surfaces) | `python3 scripts/verify-agents.py` (containeromat; add `--report` for per-source sizes) | PyYAML; library submodule for canon |
| Acceptance eval (structural) | `python3 scripts/run-prompt-eval.py --prompt-file ... --eval-file ... --subagent ... --harness dry-run` | none |
| Acceptance eval (live) | same with `--harness kilo` | kilo CLI + configured model on PATH |
| Template conformance | `python3 tooling/validate_templates.py --root .` | none |
| Fragment identity | `python3 tooling/check_fragments.py` | none |
| Adoption audit | `python3 tooling/check_instantiation.py --project-root <containeromat> --library-root .` | containeromat checkout |
| Tier-2 routing | `python3 tooling/check_skill_routing.py [--fail-on-warn]` | none |
| Skill shape (advisory) | `python3 tooling/report_skill_shape.py [--json] [--fail-on-advisory]` | none |

Known gaps: no live-model (kilo harness) baseline for the XML acceptance sets;
Tier-3 `execution` cases need a tool-using harness (no recorded run; the
`dialogue` baseline is recorded); the XML eval sets cover 4 roles across 3 sets
(compose-step, orchestrator, reviewer, ci-step) and not the review tracks;
adoption audit covers all 16 live agents.
