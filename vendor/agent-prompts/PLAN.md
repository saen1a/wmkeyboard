# Migration plan (2026-09-19)

Sequential migration of the prompt library out of containeromat into this
standalone repo. Orchestrated pattern: research -> plan -> implement -> review
-> fix.

Status: waves 0-6 shipped; waves 7-9 and the 2026-10-24 workflow-loop/library
layout remediation are merged (PRs #27-#33; wave 4 intentionally unused). The
library-side loop and the long-horizon run layer are complete; the consumer
re-vendor is current at library 2.6.0 and live harness validation is deferred to
November: dsh and zcode are inactive and only `opencode-go` is active (operator,
2026-10-27). The deferred items are
tracked below; the current subagent-ready work plan is
[autonomous-optimization-plan-2026-10-27.md](docs/knowledge-base/autonomous-optimization-plan-2026-10-27.md).

## Research basis

- Migration manifest: classification of every prompt asset (RUNTIME-PAIRED /
  LIBRARY / DUAL / GOVERNED-TOOLING), coupling register, sync-mechanism
  analysis (fragment byte-identity, skill-copy parity, skills manifest,
  skills-root registry, seed markers, kilo.json render, review catalogue).
- Role-catalog design: 38 role templates across 9 domains, slot anatomy,
  metadata schema, selection matrix, quality bar.

Both are summarized in `CATALOG.md` and `provenance/`; the governing decision:
**every DSH runtime prompt stays paired with its deploying stack and context**
(the deepseek-harness stack config in containeromat). This repo is the portable
library layer.

## Batches

| Batch | Scope | Owner |
|---|---|---|
| B0 | Scaffold: tree, fragments (byte-exact from containeromat `.kilo/templates/`), README, docs, plan | coordinator |
| B1 | `standards/`: generalized prompt standard, review contract, evidence duty, halt taxonomy, english-only + evidence records | subagent |
| B2a | `roles/engineering|design|networking/`: frontend-developer, backend-developer, api-developer, database-developer, test-author (spec.), explorer, oracle, fixer, ui-reviewer, network-architect | subagent |
| B2b | `roles/review/`: reviewer, review-lead, 8 review tracks, verification-skeptic, security-reviewer, consistency-reviewer (spec.) | subagent |
| B2c | `roles/orchestration|operations/`: orchestrator, councillor, council-synthesizer, ops-executor, ops-format-normalizer | subagent |
| B2d | `roles/research|documentation|tabletop/`: researcher, research-merger, librarian, doc-writer, 5 tabletop templates (spec.) | subagent |
| B3 | Intentionally unused -- batch numbering reserved, no scope | - |
| B4 | `workspace-prompts/`, `exemplars/`, `provenance/` | subagent |
| B5 | `CATALOG.md`, `tooling/` (fragment identity check, template validator, fixture tests) | subagent |
| Review | Independent verification vs this plan (3 verifiers) | subagents |
| Fix | Resolve findings, re-gate | coordinator |

## Wave 2 (2026-09-19, shipped)

Scope: fill the reserved surfaces with portable content. The canon switch
(containeromat `.openhands/skills` -> this repo) was deferred here and landed in
wave 3; wave 2 shipped ARCHETYPE copies marked in `skills/SKILLS.md`, and
platform-instance skills (compose-*, forgejo-registry-image, kilo-review,
seifomat-*) stay reference-only entries until their generalization pass.

- B6 `skills/` -- portable set: shared/ (anti-hallucination, anti-sycophancy,
  ask-questions, deepseek-v4-agent-defense, verification-before-completion,
  first-principles-review, anti-entropy-governance, convert-documents),
  general/ (mcp-builder, skill-creator, grilling, jq-json-processing,
  changelog-generator, agent-md-refactor, git-guardrails), vendor/ (caveman family,
  misakanet) + `skills/SKILLS.md` index with reference-only entries for the
  project instances.
- B7 `tasks/` -- new-component.md, harden-deployment.md (generalized from
  containeromat `.kilo/prompts/new-stack.md` + `harden-stack.md`),
  audit-report.md skeleton (from full-audit-compose).
- B8 `commands/` -- orchestrate.md, review.md (generalized),
  caveman.md, hallucination-check.md, sycophancy-check.md.
- B9 `dsh/` -- persona/prefix/command templates (orchestrator,
  generalist-prefix, seifomat-prefix, reviewer, knowledge-qa, review),
  parameterized; runtime instances stay
  paired with the deepseek-harness stack.

Seifomat pack: deferred by operator decision (skills stay in the dsh config
until the seifomat pack exists).
Coder single-project mode: operator runtime decision, out of scope.

## Wave 3 (2026-09-19, shipped)

Skills canon switch: `skills/` became the canon for the 23 portable skills at the time (current 24).
containeromat consumes this repo as the `agent-prompts` submodule and enforces
parity with `check_library_canon` (fail-closed, `--allow-missing-library` for
CI-less local runs). 8 runtime copies were regenerated from the generalized
canon; 13 were already conforming. Project-instance skills (compose-*,
forgejo-registry-image, kilo-review, seifomat-*) remain containeromat-canon by
design. Remainder: none for the skills plane; runtime adoption of agent
templates stays a separate future decision.

## Wave 3.1 (2026-09-19, shipped)

Scope-variant block order for the eight `review-*` track templates, the
containeromat runtime-adoption pack (`packs/containeromat.md` +
`tooling/check_instantiation.py`), and the `operations-ci-implementer` role
template with its `evals/` reference set.

## Wave 5 (2026-09-20, shipped)

Tier-2 skill trigger-routing evals and the discipline-skill anatomy tables
(adopted from addyosmani/agent-skills):

- `tooling/check_skill_routing.py` (deterministic lexical prompt-vs-description
  ranking; positive top-k, negative owner, collision threshold) with fixture
  tests, plus one case file per portable skill under `evals/trigger/` (21/21).
- containeromat runs the checker as a blocking `compose-validate.yml` step
  (`--library-root agent-prompts --fail-on-warn`), so a missing case file fails;
  the local parity battery carries the step as a `CI_ONLY` row.
- `anti-hallucination`, `anti-sycophancy` and `verification-before-completion`
  gained "Common Rationalizations" + "Red Flags" sections; the canon and all
  four runtime roots were regenerated.
- `tooling/check_instantiation.py` `MAPPING` now includes
  `operations-ci-implementer` -> `ci-step` (16/16 live agents audited).
- Tier-3 behavioral pressure cases: see wave 6.

## Wave 6 (2026-09-20, shipped)

Tier-3 behavioral evals (addyosmani's third tier, implemented):

- `evals/behavioral/<skill>.json` for the four discipline skills
  (`anti-entropy-governance`, `anti-hallucination`, `anti-sycophancy`,
  `verification-before-completion`), three pressure cases each (`time`,
  `sunk_cost`, `authority`); one `execution` case with a fixture.
- `tooling/check_behavioral_evals.py` validates schema, ids, kinds, pressure
  coverage, required skills and fixture paths; containeromat runs it blocking
  in `compose-validate.yml` (free).
- `tooling/run_behavioral_evals.py` executes the cases on demand over any
  OpenAI-compatible endpoint (default DeepSeek), decoupled from the kilo CLI;
  `execution` cases need a tool-using harness.
- First baseline recorded in `evals/results-baseline.md`: 11/12 dialogue cases
  fully pass, one partial (`anti-entropy-governance` authority case).

## Wave 7 (2026-10-23, ready for review)

Scope: adopt the 2026-10 prompt research without touching fragments, role
templates, or existing eval cases. The research register is the evidence base;
the audit is the optimization plan.

- `standards/evidence/prompt-research-2026-10.md` -- 24-source register
  (extended to S26 by wave 8)
  (instruction capacity, context rot, skills, subagents, context files,
  harness, prompt optimization) with claim labels and URLs.
- `docs/knowledge-base/prompt-system-audit-2026-10.md` -- measured audit
  (38 roles, pre-wave 21 skills, 13/38 bodies over the advisory token target,
  608-token invariant fragments) plus the P0-P3 plan.
- `standards/subagent-delegation.md` (SD-01..SD-11) -- hard gates for write
  isolation and specifiability, positive gates, handoff and return contracts,
  fan-out limits, verification separation.
- `standards/agent-context-files.md` (CF-01..CF-10) -- the repository context
  file as a router; layer map to skills, gates, docs, and MCP; paired test
  protocol. No replacement for AGENTS.md is claimed.
- `skills/general/subagent-delegation/` + `evals/trigger/` + `evals/behavioral/`
  cases -- the operational form of SD-01..SD-11.
- AP-01 gained a model-tier calibration note; AP cross-refs now name the two
  new standards.

Not changed in this wave: fragments (byte-exact), role templates, existing
eval cases, and the element budgets. The audit's P1-P3 items are evidence-gated
follow-ups, not part of this wave.

## Wave 8 (2026-10-23, ready for review)

Scope: turn the Wave 7 audit into a measured refactor architecture. No skill
body, role template, fragment, or existing eval case is edited; the refactor is
gated on baselines that do not exist yet.

- `tooling/report_skill_shape.py` + fixture tests -- skill shape instrument
  (body tokens, headings, references, description length, doctrine, rigid).
- `standards/skill-system-standard.md` (SK-01..SK-14) -- three-layer anatomy,
  five skill classes, shape targets, routing and evidence rules, lifecycle.
- `docs/SKILL-TEMPLATE.md` -- copyable skeleton and checklist.
- `docs/knowledge-base/skill-prompt-refactor-2026-10.md` -- measured diagnosis
  (D-01..D-10), target architecture, R0-R5 plan, and per-skill dispositions.
- Evidence register extended with S25 (skill authoring) and S26 (prompt
  caching); assembly contract documented for cache-stable prompts.
- `skills/SKILLS.md` gains a Type column (discipline, workflow, tool, vendor)
  and the shape baseline; README, governance, evaluation, surfaces, and
  CONTRIBUTING point at the new standard.

R0 is this wave. R1 (paired baselines and model calibration) was planned to
complete before R2 touched a body; Wave 9 proceeded under the AP-13.8 recorded
deferrals instead (evaluation.md section 5).

## Wave 9 (2026-10-23, ready for review)

Scope: start executing R1, R2, and R3 of the refactor plan. R1 infrastructure
only; the paired model runs are deferred. R2 and the R3 skill splits are
complete; the role doctrine A/B was completed later in this plan.

- `standards/model-calibration.md` (MC-01..MC-04) records the target model,
  measured capacity, harness, source, date, owner, and the AP-01 tier it
  justifies. DeepSeek V4 Pro (~750 constraints) is the governing row.
- `tooling/run_behavioral_evals.py` gains `--mode both` (paired no-skill
  baseline), `--seed`, per-mode result files, and a `run` metadata block
  (model, grader, harness, seed, start, duration, UTC timestamp). Helpers are
  tested in `tooling/tests/test_run_behavioral_evals.py`.
- `standards/prompt-assembly.md` (AS-01..AS-08) defines the static prefix,
  dynamic user turn, on-demand skill message, routed references, and cache
  breakpoint.
- `CHANGELOG.md` records the prompt-surface changes (G-13).
- `validate_templates.py` reports the AP-01 token target as a WARN.
- `tooling/run_role_doctrine_experiment.py` and `evals/role-doctrine/` provide
  the compact-doctrine A/B pilot; no fragment is active.
- `docs/knowledge-base/consumer-revendor-wave9.md` records the exact consumer
  steps; this repo stays canon.
- Behavioral cases added for `mcp-builder`, `deepseek-v4-agent-defense`, and
  `agent-md-refactor`, `ask-questions-if-underspecified`, `grilling`,
  `changelog-generator`, `convert-documents-to-markdown`; the suite is now 16
  files and every non-vendor skill has cases.
- R2 splits: `jq-json-processing` (2,735 -> 923), `skill-creator`
  (3,417 -> 1,171), and `first-principles-review` (2,703 -> 1,373).
- R3 splits: `mcp-builder` (3,648 -> 1,074),
  `anti-entropy-governance` (3,575 -> 1,455),
  `deepseek-v4-agent-defense` (3,443 -> 1,121), and `agent-md-refactor`
  (1,883 -> 984); `ask-questions` and `verification-before-completion` were
  trimmed to eight H2 sections.
- Long-form material is preserved in the new `references/` files. AP-13.8
  paired baselines are deferred and recorded in
  `docs/knowledge-base/evaluation.md`.
- Current shape (2026-10-31): 25 skills, body tokens 438 / 1,147 / 1,582,
  total 27,558; 1 body over 1,500 and it is a frozen vendor copy (0 non-vendor);
  11 with references; no body over 2,000 lacks a reference.

STOP-gate evidence is in `docs/knowledge-base/stop-gate-experiment.md`:
STOPP 0.852 vs direct 0.519; adopted `standards/stop-gate.md` with a narrow
comment/format/typo fast path and `tooling/classify_change.py`.
Refactor A/B: old 0.875 vs new 0.886, 41% fewer tokens. Role-body A/B: frontend 1.000 vs 0.889, orchestrator and network
1.000 vs 1.000; thirteen roles trimmed, WARNs 15 -> 0; all role A/B rows 1.000.
(`docs/knowledge-base/refactor-ab-2026-10.md`).
Paired baselines are recorded in `evals/results-baseline.md` (13 skills, seeds
7/11/23, 0.869 skill vs 0.555 baseline). The full 16-role doctrine run is in
`docs/knowledge-base/role-doctrine-experiment.md`: compact 0.674 vs full 0.708,
so the full fragment stays. Cache hit measurement remains.

Skill score optimization (2026-10-24): the four lowest skills
(`ask-questions-if-underspecified`, `agent-md-refactor`, `mcp-builder`,
`first-principles-review`) were re-baselined on corrected dialogue cases and
8,192-token runs. Tuning seeds 7/11/23 reached 1.000; holdout seeds 67/83/97
scored 0.981 with the skill vs 0.556 without (+0.425, 27 wins / 9 ties /
0 losses, bootstrap 95% CI [0.314, 0.537]). The remaining eight sub-1.000
skills then reached **1.000 vs 0.666** on holdout (+0.334, 34 wins / 38 ties /
0 losses, CI [0.245, 0.422]); `jq` is neutral. Evidence:
`docs/knowledge-base/skill-score-optimization-2026-10.md`.

Workflow loop (2026-10-24): doctrine 1.3.0 makes the six phases an explicit
loop with Review/Fix and Verify/Fix back-edges, a one-refinement bound, and
evidence at every transition. Research is inside Plan; Review is the audit gate;
Push is the finalize gate. `standards/workflow-loop.md` is the normative state
machine; `docs/knowledge-base/workflow-loop-2026-10.md` is the analysis. The
corrected A/B (pinned v1.1 arm, 16,384 tokens, 12 roles x 3 seeds) is
**0.9525 vs 0.9431**, 5 wins / 26 ties / 4 losses (one truncated pair excluded; A/B is pre-1.3.0 and not pre-registered): neutral, not a proven
improvement. Manifest: `evals/role-ab/results/workflow-loop-2026-10.json`.

Pre-registered confirmation (seeds 211/223/227, doctrine 1.3.0, pinned linear
v1.1): **0.9907 vs 0.9723**, 3 wins / 32 ties / 1 loss, 35/36 vs 33/36 passes,
no truncation. This measures the pre-1.3.1 body; it meets the registered non-inferiority bar,
but it is one model and one task per role, not proof. Manifest:
`evals/role-ab/results/workflow-loop-1.3.0.json`.

2.0.0 cleanup: the legacy `roles/`, `tasks/`, and `workspace-prompts/` shims
were removed; all templates except the orchestrator are 2.0.2 (orchestrator
2.1.2 adds the long-horizon duties and cache routing); doctrine is 1.3.1. `ops-executor` carries `rollback` in PROPOSE/FINAL_REPORT and names the
compose config and healthcheck verification; a post-hoc 3-seed check is
1.00/1.00 (3 ties); the registered 1.3.0 loss stands in the aggregate.
`evals/role-ab/results/ops-executor-2.0.0.json`.

Pre-registered 2.0.0 OpenCode Go run (the executor model changed, so cache
reset and results are not comparable to DeepSeek 1.3.0): 36-pair **0.9907 vs
0.9816**, 2 wins / 33 ties / 1 loss; 35-pair complete **0.9905 vs 0.9810**,
2/32/1; `ops-executor` is 1.00/1.00 on
all three seeds. The standalone post-hoc ops check is superseded by this full
registered aggregate, which measured the pre-1.3.1 body and is historical,
not evidence for the current body:
`evals/role-ab/results/workflow-loop-2.0.0-opencode.json`. The consumer checkout available
here is not a git repo and its submodule is empty, so re-vendor is blocked; the
neutral `agents/` + `prompts/` migration is executed; the plan and follow-up
steps are in `docs/knowledge-base/neutral-layout-migration.md`.

Neutral layout (2026-10-24): root `AGENTS.md` and `docs/neutral-layout.md`
define `agents/` + `prompts/` as the vendor-neutral target; the repository now
uses `agents/` + `prompts/tasks/`; the legacy shims were removed in 2.0.0. Do not treat `.kilo/`
as source.

Long-horizon runs (2026-10-25, library 2.2.0): `standards/long-horizon-runs.md` (LH-01..LH-13)
adds the run layer above the unit loop: durable run state, checkpoints, resume,
incremental delivery, context compaction, progress and stall detection, goal
integrity, budgets and termination, run-scope verification, operator monitoring,
crash/idempotency, and long-run evaluation. It adds no phase and does not
change a transition. The machine contract is
`standards/run-state.schema.json` (1.1.0); `tooling/run_state.py` validates a
state file and `tooling/check_long_horizon.py` is a gate step. The orchestrator
is 2.1.3 and owns the run state. The `long-horizon-run` skill is the operational
checklist. Evidence and the gap analysis are in
`standards/evidence/long-horizon-2026-10.md` and
`docs/knowledge-base/long-horizon-agents-2026-10.md`. These rules are
design-by-evidence; no deployed harness or A/B was run for them, and the 2.0.0
A/B evidence measured the pre-1.3.1 body and describes the unit loop, not the
new run layer.

Token and cache efficiency (2026-10-25, library 2.2.0):
`standards/prompt-assembly.md` now covers AS-01..AS-12. AS-09 carries a dated
minimum/TTL/economics profile; AS-10 names the layer order and first divergent
layer; AS-11 bans volatile bytes and random serialization in cached layers;
AS-12 makes history append-only and versions compaction. The data contract is
`standards/cache-profiles.json` (1.0.0); the static checker is
`tooling/check_token_efficiency.py`; the runtime shape is harness telemetry
`/2`; the operating procedure is the `cache-aware-assembly` skill. Evidence is
in `standards/evidence/prompt-cache-2026-10.md` (T1..T14) and the synthesis in
`docs/knowledge-base/token-efficiency-cache-2026-10.md`. No live cache
measurement was run; hit rate and cost remain harness telemetry.

Tool-set stability (2026-10-25, library 2.3.0):
`standards/tool-set.md` defines TS-01..TS-10 for a consumer-owned canonical tool
manifest: exact wire inventory, fixed order, definition-only sha256, mask rather
than remove, deferred/MCP append, separate version and mask_version, cache-epoch
and telemetry fields, and acceptance tests. `standards/tool-set.schema.json` is
the shape; `tooling/check_tool_set.py` validates order, names, masks, volatile
descriptions, and the hash, with `--update-hash` as the reviewed update path;
`exemplars/tool-set-example.json` is the worked example. The implementation
guide is `docs/knowledge-base/tool-set-stability.md`. No live tool set exists in
this library; the consumer supplies the manifest.

External scan hardening (2026-10-25, library 2.4.0):
`standards/workflow-loop.md` now carries WL-13 (findings ledger with stable ids,
severity, evidence, owner, state, and decision) and WL-14 (publication proof
before `Done`). `standards/long-horizon-runs.md` carries LH-14 (append-only
`events.jsonl`, state as a materialized view, replay on resume, journal-wins
reconciliation). Contracts and checkers:
`standards/run-journal.schema.json` + `tooling/check_run_journal.py`,
`exemplars/run-journal-example.jsonl`, `tooling/check_findings_ledger.py` +
`exemplars/findings-ledger-example.md`. Both checks run in `make gate`. The
decision record is `docs/knowledge-base/external-project-scan-2026-10.md`;
JulianFlux was rejected as unvalidated. The orchestrator is 2.1.3.

## R4, conduct canon, and H2 dispositions (2026-10-26)

R4 is now a design with a measurement gate, not an open question.
`docs/knowledge-base/r4-cache-and-canon-2026-10.md` records the protocol:
41 carriers, prefix tokens 809/940/1100, and profile coverage that clears the
minimum on Anthropic, DeepSeek, and vLLM for all carriers, on OpenAI for 2/41,
and on Gemini for 0/41. The `anthropic-5m` hit-rate baseline was measured on
2026-10-27 (3 seeds, cold 0.0000, warm 0.9973, 8.0e-04 USD for nine requests)
through the Kilo Anthropic route; it is a baseline for one prefix, not a general
cache gain, and the other seven profiles remain unmeasured. The same document's
external-canon design was rejected on
measurement (2026-10-27): ownership is per name in
`scripts/skills-library.json`, so the single-canon constraint never blocked a
migration. Option B -- content work, one skill at a time -- is the remaining
path.

`fragments/agent-conduct.md` is library-canonical from 1.0.0 (2026-10-26).
Containeromat re-vendors it; `--upstream` is a legacy diagnostic and the
manifest hash is the gate. The decision record is
`provenance/operator-acceptance-2026-10-26-conduct-canon.md`.

Seven non-vendor skills carried nine H2 sections. The merges are now executed
and measured in `docs/knowledge-base/h2-shape-ab-2026-10.md`: old 0.899 vs new
0.9345, 56/66 vs 57/66 full passes, 8 wins / 53 ties / 5 losses, no skill loses
on mean score. `report_skill_shape.py` now reports `H2>8=1`, the frozen vendor
`misakanet`. The per-skill dispositions are in
`docs/knowledge-base/skill-prompt-refactor-2026-10.md` section 5a.

## Wave 11 (2026-10-31, shipped): external-system adoption

Three external agent systems were read for portable, checkable mechanisms, then
implemented as standards, contracts, checkers, and one skill. The change record
with per-source line references and the rejection list is
`docs/knowledge-base/adopted-mechanisms-2026-10-31.md` (rowan `6766dd9`,
kageops-core `2357cc5`, autoprompt-skill `fe1ded6`).

| Item | Delivered |
|---|---|
| W11-1 | `standards/verification-integrity.md` (VI-01..VI-14), `gate-verdict.schema.json`, `exemplars/gate-verdict-example.json`, `tooling/check_gate_verdict.py` + 40 tests |
| W11-2 | `standards/prompt-security.md` (PS-01..PS-14), `tooling/check_prompt_security.py` + 24 tests, gate step |
| W11-3 | `standards/agent-adapter.md` (AD-01..AD-10), `agent-admission.schema.json`, `omp/admission.json`, `dsh/admission.json`, `tooling/check_admission.py` + 20 tests |
| W11-4 | Skill `untrusted-content-handling` with `references/patterns.md`, 5 trigger positives, 4 negatives, 3 behavioral cases |
| W11-5 | Rule additions: AP-02 non-goals, AP-10 and SD-08 deny-by-default, SD-07 leaf cap and minimum spawn budget, LH-09 terminal exhaustion, LH-11 intercept and handback, `verification-before-completion` four refusal rows + `references/proof-integrity.md` |
| W11-11 | Pass 7 (audit round 2, operator-opened unit): four round-1 repairs found non-holding and repaired (warn semantics, mechanical-verifier provenance, budget remnants, over-bound reason), ten new defects closed, six checker holes closed, `tooling/measure_state.py` + `docs/measured-state.md` added as the only source for live numbers (CONTRIBUTING rule 18), round-1 verdict corrected; 66 ledger rows over two rounds |
| W11-10 | Pass 6 (audit): four clean-context audits, 44 findings, 25 medium, all fixed; standards deduplication and nine contradictions removed (declared cycle budget dropped), six checker false negatives plus two crashes closed, 20 tests added, loop scenarios pruned to 13 with reason assertions, documentation claims corrected; `provenance/findings-wave11-audit.md` and `provenance/verdict-wave11-audit.json` gated |
| W11-9 | Pass 5 (skills): mcp-builder trust boundaries (PS-04/05/08/09), skill-creator gate list in `references/authoring-guide.md` section 7, long-horizon-run verdict record at unit gates, subagent-delegation skipped-return rule, deepseek-v4-agent-defense layer 6, behavioral sets for `caveman` and `misakanet` (21 case files) |
| W11-8 | Pass 4 (loop): WL-07 as the single cycle authority with VI-13 reduced to the verdict half, WL-02 guards bound to verdict records, WL-09 per-gate minimum table enforced by three checker rules, `evals/loop/drive.py` with 13 scenarios and 5 pytest cases as a gate step |
| W11-7 | Pass 3 (agents and subagents): orchestrator dispatch budget and child-return-as-data, review-lead child budget and merged-verdict identity, reviewer severity/verdict duties, skeptic and security-reviewer rule merges for the new duties, test-author and executor skipped-check rules, delegation-skill spawn floor and deny-by-default, gate-authority verdict drift guard, base 2.0.4 / orchestrator 2.1.5 |
| W11-6 | Pass 2: doctrine 1.4.0 in all 41 carriers, WL-04/WL-09/WL-10 and SG-04 cross-refs, prompt-security carrier scope and vocabulary, two real boundary gaps repaired, admission propagated into INSTANTIATE/omp/dsh READMEs, fragment-aware token guardrail, WP-07 arms regenerated |

No runtime measurement is claimed: every W11 item is a static rule plus a static
check. `make gate` is the proof; the limits are listed in section 12 of the
change record.

## Wave 13 (2026-11-03): plan-review gate

Operator direction: after Plan there is always a plan review, repeated until it
is clean. The loop is now seven phases -- `Plan -> PlanReview -> Implement ->
Review -> Fix -> Verify -> Push` -- and no unit reaches Implement without a
`plan-review` verdict record. Design record, enforcement table, and limits:
`docs/knowledge-base/plan-review-gate-2026-11.md`.

| Item | Delivered |
|---|---|
| W13-1 | `standards/workflow-loop.md`: seven phases, new WL-15 (six checks, severity, rounds, mechanical verifier), `Plan -> PlanReview -> Implement` as the only forward path, `Fix -> PlanReview` back-edge, WL-07 amended (code gates keep one refinement, the plan gate is progress-bound), WL-09 per-gate minimum, WL-11 STOPP note, WL-12 measures (`plan-review rounds per unit`) |
| W13-2 | `standards/gate-verdict.schema.json` 1.1.0 (gate `plan-review`, attempt is the round number there), `tooling/check_gate_verdict.py` (six check ids, coverage basis, no self-verifier, round pair), `exemplars/gate-verdict-plan-review.json` |
| W13-3 | `standards/run-state.schema.json` 1.2.0 and the long-horizon layer (`PlanReview` phase and status, schema pin, exercise and skill anchors, fixture hashes) |
| W13-4 | Doctrine 1.5.0 in 41 carriers and 4 presets; `owned_phases` gains `PlanReview` before `Review`; per-role workflow prose names the gate; 38 role templates and 3 task prompts version-bumped with `updated: 2026-11-03` |
| W13-5 | `tooling/check_workflow_loop.py` (transitions, doctrine invariants, ledger `next`, plan-review authorities), `validate_templates.py` phase list, `evals/loop/drive.py` 20 scenarios with 7 plan-review pytest cases |
| W13-6 | Cross-standard notes: AP-14, VI-01/VI-12/VI-13, CR-01 scope note, SG-01, SD handoff phase list, WA cross-ref; skills `long-horizon-run`, `subagent-delegation`, `grilling`, `operator-setup-interview` |
| W13-7 | Pins and records: CATALOG (library 2.12.0, doctrine 1.5.0, long-horizon 1.2.0, orchestrator 2.4.0), `model-surface.json` 1.1.0 budgets, `docs/measured-state.md`, `omp/catalog.yaml`, `packs/containeromat.md` re-vendor delta |

No runtime measurement is claimed. `make gate` is the proof; the limitation is
recorded in section 6 of the design record.

## Deferred (recorded, not forgotten)

- **Skills migration** (18 dsh / 24 library skills; 9 dsh skills absent from the
  library): the wave-3 canon switch made this repo the canon for the 24 portable
  skills. The rest is not blocked by a registry rule -- the one-canon rule in
  `skills-roots.json` is about the LOCAL canon, and `scripts/skills-library.json`
  already owns the names it lists (WP-05 closed 2026-10-27, no schema change).
  Moving a skill here is content work: generalize the body, add the catalog row,
  register it, re-vendor, then drop the consumer's local canon row, with the
  paired baseline before any body change. Six of the nine are multi-root
  candidates (`compose-audit`, `compose-smoke`, `compose-step`,
  `doubt-driven-review`, `forgejo-registry-image`, `knowledge-capture`);
  `kilo-review`, `seifomat-dev` and `seifomat-dev-debug` are single-instance
  project skills and stay local. Note when a copy does move: regenerate the
  consumer's `skills-manifest.py` after `git add`, because it enumerates tracked
  files.
- **Live deployment and validation**: agent-template adoption is complete
  (containeromat authors `agents/`, renders `.kilo`/Paseo from its pack, and has
  re-vendored doctrine/conduct and all 24 library skills at `b1ea951`). Runtime
  status (operator, 2026-10-27): dsh and zcode are **inactive** and will not be
  deployed in this cycle; `dsh` regains usage in November, `zcode` has no date
  and is **not applicable this cycle**. Only `opencode-go` is active, on
  `deepseek-v4.1-flash`. The seed-marker/reload item is therefore **closed, not
  blocked**: no reload, redeploy or gate work is owed while those runtimes are
  stopped. Live harness/A-B validation is deferred to November.
- **Coder single-project mode** (`CODER_HOST_DIR`): runtime deploy decision,
  operator-owned; orthogonal to the library (per-workspace `.kilo/` works in
  both mount modes).
- **Long-horizon live validation**: deferred to November, not awaiting an
  operator action now. There is no deployed harness run and no A/B for
  LH-01..LH-14; the local run-state exercise in `evals/long-horizon/` remains the
  only evidence and no live metric is claimed. The planned measures are in
  LH-13.
- **Run-layer runtime support**: `lease`, `## In-flight`, and idempotency are
  recorded fields, not enforced by a runtime. A supervisor, durable queue, or
  lock service is a deploy-time decision.
- **Consumer re-vendor**: advanced to `agent-prompts` `b1ea951` (library 2.6.0;
  skills, doctrine/conduct, agent pack). The consumer's `agent-prompts` submodule
  is current; the registry lists all 24 names, so no registration gap remains.
  The dsh and zcode skill roots stay in the consumer but are **inert** while
  those runtimes are stopped: no re-vendor, re-seed or seed-marker bump is owed
  this cycle, and no gate work follows from their presence.

## Quality bar

Every template: metadata frontmatter (schema in the template skeleton),
fixed block order (role, hard_rules, doctrine, workflow, conduct, output
last), element budget 12/15/15 with fragments counted once each, no runtime
control-flow markers, ASCII + English, fragments byte-exact, project slots
marked `{{LIKE_THIS}}` (templates may carry them; instantiations must not).
`tooling/` validators enforce this per template; review verifies each batch
against this plan.
