# Prompt and skill system audit (2026-10)

Status: audit and optimization plan.

Audience: prompt authors, reviewers, and maintainers of this library.

Related: [evaluation.md](evaluation.md), [governance.md](governance.md),
[surfaces.md](surfaces.md), [integration-status.md](integration-status.md).

Companion to
[prompt-research-2026-10.md](../../standards/evidence/prompt-research-2026-10.md)
(source IDs S1-S26 are cited from that register). The execution plan that
follows this audit is
[skill-prompt-refactor-2026-10.md](skill-prompt-refactor-2026-10.md).

Measured: 2026-10-23 against this tree, before the Wave 7 additions below. The
counts are the pre-wave baseline (21 skills, 21 trigger files, 6 standards,
4 behavioral files); Wave 7 adds one repo-authored skill and two standards, so
the pre-Wave-8 tree had 22 skills, 5 behavioral files, and 8 standards. Wave 8
added the skill system standard (9 standards) and the shape instrument; Wave 9
added model calibration and prompt assembly (11 standards), the paired runner,
and the CHANGELOG, then split seven skill bodies and trimmed two. Token
estimates use `bytes / 4`.
Role bodies exclude frontmatter; skill figures include it, because the skill
file is the loaded unit.

Scope: the role templates, fragments, standards, skills, commands, and eval
system. Runtime instances in consumer repositories are out of scope; this
audit measures the canon they consume.

## 1. System map

| Surface | Count | Notes |
|---|---|---|
| Role templates | 38 | 34 standard, 2 dual-workflow, 2 primary; 9 domains |
| Fragments | 4 files | doctrine 1.3.0; conduct in kilo, dsh-ha, dsh-preset variants |
| Standards | 13 | prompt, workflow loop, system prompt, review contract, evidence duty, halt, language, and the 2026 additions |
| Skills | 22 | 8 general, 8 shared, 6 vendor |
| Commands | 5 | thin dispatchers |
| Trigger eval files | 22 | one per portable skill |
| Behavioral eval files | 16 | 22 skills; paired baselines in results-baseline.md |
| Validators | 7 | templates, fragments, workflow loop, instantiation, skill routing, behavioral schema, telemetry |

Existing strengths that the 2026 evidence supports:

- **Element budgets and fixed block order.** Instruction density is still the
  scientific variable (S1, S2). The library counts elements instead of
  estimating quality by token count, which is the right unit.
- **U-shaped ordering.** Hard rules first, output contract last (S5).
- **Byte-exact fragments and manifests.** Directly addresses prompt rot and
  maintenance debt (S18). This is stronger than most public prompt libraries.
- **Progressive disclosure through skills and references.** The right loading
  model (S17, S24).
- **Separate reviewer roles with evidence and severity labels.** The
  generator-verifier split is the best-supported multi-agent pattern (S8, S9).
- **Deterministic gates.** Structural validation does not depend on model
  compliance, which is the correct place for invariants (S13).

## 2. Measured findings

### 2.1 Prompt bodies and budgets

| Metric | Result |
|---|---|
| Body token estimate, min / median / max | 814 / 954 / 1,464 |
| Element count, min / max | 10 / 13 |
| Element cap breaches | 0 of 38 |
| Bodies over the tier token target | 13 of 38 |
| Invariant fragment cost (doctrine + conduct) | 608 tokens |
| Invariant share of the median body | 63.7% |

The element budget is enforced and compliant. The token guardrail is advisory
and is not measured by the validator, so 13 templates exceed their tier target;
three of those are reported and justified by the invariant fragments in the
consumer ([integration-status.md](integration-status.md)), and the rest have no
recorded justification.
The largest overages:

| Template | Body tokens | Target | Overage |
|---|---|---|---|
| `roles/review/rev-review-lead.md` | 1,464 | 1,100 | +364 |
| `roles/operations/ops-executor.md` | 1,174 | 950 | +224 |
| `roles/review/rev-reviewer.md` | 1,116 | 950 | +166 |
| `roles/networking/net-network-architect.md` | 1,124 | 1,000 | +124 |
| `roles/engineering/eng-frontend-developer.md` | 1,116 | 1,000 | +116 |
| `roles/engineering/eng-api-developer.md` | 1,089 | 1,000 | +89 |
| `roles/engineering/eng-database-developer.md` | 1,086 | 1,000 | +86 |
| `roles/engineering/eng-backend-developer.md` | 1,060 | 1,000 | +60 |
| `roles/orchestration/orch-orchestrator.md` | 1,152 | 1,100 | +52 |
| `roles/operations/ops-ci-implementer.md` | 1,051 | 1,000 | +51 |
| `roles/engineering/eng-test-author.md` | 1,046 | 1,000 | +46 |
| `roles/review/rev-code-skeptic.md` | 1,025 | 1,000 | +25 |
| `roles/operations/ops-format-normalizer.md` | 1,012 | 1,000 | +12 |

The invariant fragments are the single largest cost in every prompt. At 608
tokens they consume 63% of the median 954-token body, leaving about 350 tokens
for role-specific behavior. This is a deliberate trade: the fragments carry
safety and workflow invariants. It is also the first place to look for a
structural optimization, because trimming role-specific prose has less room
than the shared blocks.

### 2.2 Role phase ownership

| Owned phases | Roles |
|---|---|
| All six | 3 |
| Five (Plan through Verify) | 17 |
| Three | 2 |
| Two (Review/Fix, Review/Verify) | 14 |
| Plan only | 1 |
| Review only | 1 |

Every role carries the full six-phase doctrine, including the 16 roles that own
two or fewer phases. That is a deliberate binding workflow, but it is also the
clearest candidate for a model-tier A/B under S20: the same procedure can help a
mid-tier model and induce hyper-literalism in a stronger one.

### 2.3 Skills

| Metric | Result |
|---|---|
| Skills | 21 |
| Tokens (whole file, bytes / 4), min / median / max | 558 / 1,304 / 3,806 |
| Skills over 2,500 tokens | 6 |
| Skills with more than 10 H2 sections (fence-aware) | 4 |
| Skills with `references/` | 4 |

The large skills are concentrated in `general/` and `shared/`:
`mcp-builder` (3,806), `anti-entropy-governance` (3,662), `skill-creator`
(3,615), `deepseek-v4-agent-defense` (3,550), `jq-json-processing` (2,895),
and `first-principles-review` (2,780). SkillsBench's focused-bundle result
(S10) does not say these skills are wrong, but it does say their shape is a
risk: a skill with 20+ sections is doing several jobs in one always-available
body. The correct fix is a paired test, not a blanket split.

### 2.4 Evaluation coverage

| Tier | What it proves | What it does not prove |
|---|---|---|
| Structural | Skeleton, order, budgets, fragments, hygiene | Behavior on a task |
| Trigger | Description vocabulary and routing distinctness | Semantic routing; real user phrasing |
| Behavioral (schema) | Cases exist and cover pressure kinds | The model actually holds under pressure |
| Behavioral (execution) | On-demand model run | Continuous regression; cost; cross-model stability |
| Acceptance (XML sets) | Structural markers on selected roles | Live-model performance (dry-run baselines) |

Missing, in priority order:

1. No paired no-skill baseline for any skill. SkillsBench's method is the
   standard here (S10).
2. No model-tier calibration. The library supports Kilo and DSH, but no
   template records the target model's instruction capacity or the date it was
   measured (S2).
3. No harness/model/seed metadata on eval results, so a result cannot be
   reproduced or compared after a model change (S16).
4. No prompt-change evidence gate for roles. AP-13.8 requires it for skills;
   role templates can change without a baseline.
5. Trigger routing is lexical only. That is cheap and deterministic, but it
   cannot catch a semantic misroute.

## 3. Gap register

Severity: H = unsupported behavior or a direct cost/quality risk; M = a
measurable drift from the evidence; L = an improvement with limited current
impact.

| ID | Severity | Gap | Evidence | Action |
|---|---|---|---|---|
| G-01 | H | No normative rule for when to delegate to subagents, how to write the handoff, or how to keep writes coherent. | S6, S8, S9, S11, S12 | `standards/subagent-delegation.md` + skill + evals (P0) |
| G-02 | H | No guidance for the repository context file consumers write (AGENTS.md or equivalent). | S13, S14, S15 | `standards/agent-context-files.md` (P0) |
| G-03 | H | Token guardrail is advisory; 13 of 38 bodies exceed target, three are reported and justified by the invariant fragments in the consumer, the rest have no recorded reason. | S3, S4, S5 | Validator warning now, fail after cleanup (P1) |
| G-04 | H | No paired skill-efficacy baseline; only structure and routing are measured. | S10, S17 | Paired eval harness (P1) |
| G-05 | H | No model-tier instruction-capacity record; budgets are not calibrated to the target model. | S1, S2 | Calibration table + re-baseline trigger (P1) |
| G-06 | M | Full six-phase doctrine in every role, including single-phase roles. | S20 | Doctrine-light A/B for low-phase roles (P2) |
| G-07 | M | Invariant fragments consume 63% of the median prompt body. | S3, S4, S5 | Test a compressed doctrine variant; do not edit blindly (P2) |
| G-08 | M | Six skills exceed the 2,500-token cost signal and four have more than 10 H2 sections. The 2,500 figure is a review heuristic, not a standard or a gate. | S10, S17 | Split after a paired test; move depth to references (P2) |
| G-09 | M | Injection guard sits in the conduct block at position 5; hard rules do not carry a one-line data-not-instructions rule. | S5, S18 | A/B a one-line hard rule; keep conduct byte-exact (P2) |
| G-10 | M | Eval results record harness and model names but lack seed, repeat, and token metadata; the XML acceptance sets lack model/harness metadata. | S16, S18 | Extend eval schema and runner (P1) |
| G-11 | M | Prompt optimization is manual; no reflective loop over the eval set. | S19, S22 | GEPA/ACE-style experiment on a small eval set (P3) |
| G-12 | L | Trigger routing is lexical only. | S10 | Add an embedding or judge check beside the lexical gate (P2) |
| G-13 | L | No per-prompt changelog or named owner; PLAN waves are the only history. | S18 | Add a prompt change log (P1) |
| G-14 | L | English + ASCII mandate may reduce performance on non-English tasks. | -- | Keep as a project decision; record the trade-off |

## 4. Optimization plan

### P0 -- Delivered with this audit (low risk, no fragment changes; uncommitted)

| Change | Acceptance |
|---|---|
| Evidence register with 24 sources at Wave 7 (26 after Wave 8) and claim labels | Every factual claim carries a label and a URL |
| This audit and plan | Measured numbers are reproducible from the tree |
| `standards/subagent-delegation.md` (SD-01..SD-11) | Rules are testable; no runtime counters; ASCII |
| `standards/agent-context-files.md` (CF-01..CF-10) | Format layering is explicit; no AGENTS.md replacement claim |
| `skills/general/subagent-delegation/SKILL.md` | Focused, at most three modules, under 2,500 tokens (advisory cost signal) |
| Trigger and behavioral cases for the new skill | `check_skill_routing.py --fail-on-warn` and `check_behavioral_evals.py` pass |
| Cross-refs in the prompt standard, PLAN, README, skill index | No broken links; counts updated |

P0 does not change a fragment, a role template, or an existing eval case. It
adds the missing decision layer around the system that already exists.

### P1 -- Measure before changing (1-2 weeks)

1. **Token guardrail.** Add a token-target check to
   `tooling/validate_templates.py` as a warning first, listing the 13
   overages. Triage each: trim duplicate prose, merge a rule, or record a
   justified exemption. Only then promote the check to a failure. (Wave 9:
   warning live; 15 rows recorded in
   [token-warning-triage-2026-10.md](token-warning-triage-2026-10.md).)
2. **Model-tier calibration.** Add a small table to the prompt standard or a
   new `standards/model-calibration.md`: target model, measured instruction
   capacity, source, date, and the budget tier it justifies. Re-baseline when
   a model or harness changes. (Wave 9: shipped as
   `standards/model-calibration.md`, MC-01..MC-04.)
3. **Eval metadata.** Add `model`, `harness`, `seed`, and `date` to behavioral
   results and the runner output. Without this, an 11/12 baseline cannot be
   compared after a model change. (Wave 9: the runner emits a `run` block and
   supports `--seed` and `--mode both`; a provider that rejects the seed field
   fails the run rather than ignoring it.)
4. **Prompt change log.** Add a `CHANGELOG.md` (or a `provenance/` record) with
   one line per prompt/fragment/skill change: what, why, evidence, owner.
   (Wave 9: shipped as `CHANGELOG.md`.)
5. **Paired skill baseline.** Run every shape-changed skill with and without
   the skill on the same model/harness, at least three seeds: the five
   discipline skills (including `git-guardrails`), `subagent-delegation`, the
   R2 splits (jq, skill-creator, first-principles-review), the R3 splits
   (mcp-builder, anti-entropy-governance, deepseek-v4-agent-defense,
   agent-md-refactor), and the two H2 trims (`ask-questions-if-underspecified`,
   `verification-before-completion`). Deduplicate the overlaps; 13 unique
   skills.
   Record pass rate, tokens, and wall-clock. This is the SkillsBench method
   (S10). Wave 9 recorded the runs in `evals/results-baseline.md`: skill mean
   0.869 vs no-skill 0.555 across 13 skills (seeds 7, 11, 23).

Acceptance for P1: every overage has a decision; every eval result names its
model and harness; every change has a changelog entry; every shape-changed
skill has a paired baseline.

### P2 -- Structural experiments (2-6 weeks)

1. **Doctrine-light variant.** For the 16 roles that own two or fewer phases,
   test a two-line phase-position block against the full doctrine. Measure
   task success and token use on the behavioral set. Keep the full doctrine
   for the orchestrator and review lead. Do not edit the fragment until the
   A/B has a result.
2. **Conduct placement.** Test a one-line data-not-instructions rule in
   `hard_rules` while keeping the conduct block byte-exact. The goal is to
   put the injection guard at both ends of the prompt (S5), not to move the
   fragment.
3. **Skill shape.** For the six skills over 2,500 tokens, test a focused body
   plus references. Acceptance is a paired non-inferiority result, not a
   smaller file. The per-skill dispositions are in
   [skill-prompt-refactor-2026-10.md](skill-prompt-refactor-2026-10.md), and
   `tooling/report_skill_shape.py` measures the before/after shape.
4. **Context-file template.** Add a short AGENTS.md router template for
   consumers: commands, non-standard conventions, verification, pointers. Run
   the paired test from S13/S14 on a real repository. Cut any section that
   does not change success, cost, or runtime.
5. **Semantic trigger check.** Add an embedding or judge-based check beside
   the lexical gate, using the same case files. Keep the lexical gate as the
   free CI check.

### P3 -- Optimization loop (6-12 weeks)

1. Build a small, labelled eval set from real failures (20-40 cases) and run a
   reflective prompt-optimization experiment in the GEPA style (S19). Keep
   the human review gate: an optimized prompt is a proposal, not a merge.
2. Extend the paired skill benchmark across the supported models and harnesses.
   Report per-configuration deltas, not only the average (S10).
3. Track cost, latency, and token use per eval run. Anthropic's 15x token
   multiplier makes cost a first-class metric (S6).
4. Automate the re-baseline trigger: a model or harness change opens an eval
   run; a prompt change without a baseline is blocked.

## 5. What not to change

These are load-bearing and should survive the optimization:

- Byte-exact fragments and the fragment manifest. The evidence supports the
  anti-drift investment (S18); do not trade it for local convenience.
- Hard rules first and output contract last (U-shaped ordering).
- Evidence duty, claim labels, severity levels, and the null-findings rule.
- Least-privilege tool allowlists and read-only reviewer roles.
- Separate reviewer context from author context. This is the best-supported
  multi-agent pattern (S8, S9).
- The element budget as a ceiling calibrated to the weakest supported model.
  Relax it only with a model-tier calibration and an eval result.

## 6. Decision rules for future changes

1. A prompt edit without a baseline and a post-change check is a style change,
   not an optimization. Do not merge it as one.
2. A new skill needs a trigger case, a paired efficacy plan, and a focused
   shape. A skill that cannot be shown to help is a candidate for removal.
3. A new subagent pattern needs a write-isolation answer and a handoff
   contract. If the output cannot be accepted or rejected by an independent
   check, do not delegate it.
4. A context file line must be a command, a non-standard convention, or a
   pointer. Generic architecture prose is the first thing to cut.
5. A model or harness change invalidates the old baseline. Re-run before
   claiming the prompt still works.

## 7. Acceptance criteria for this plan

- P0: all validators pass; the new skill routes in the top 3 for its positive
  cases; the behavioral case file validates; no existing eval changes.
- P1: zero unexplained token overages; every eval result carries model,
  harness, seed, and date; one paired baseline per shape-changed skill (13).
- P2: each structural change has a paired result and a rollback path; no
  fragment edit without a version bump and consumer propagation.
- P3: an optimization loop runs on a labelled set and produces reviewed
  proposals, not automatic merges.

## 8. Sources

See [prompt-research-2026-10.md](../../standards/evidence/prompt-research-2026-10.md)
for the full register (S1-S26), claim labels, and URLs. This audit adds no
uncited external claim.
