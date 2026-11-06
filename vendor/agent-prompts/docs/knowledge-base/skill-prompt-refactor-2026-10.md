# Skill and prompt system refactor (2026-10)

Status: analysis and execution record. Wave 8 added the standards and
instrumentation; Wave 9 changed nine skill bodies (seven splits and two H2
trims). No role template or fragment changed. Paired baselines remain
outstanding.

Audience: prompt authors, skill authors, reviewers, and the operator.

Related: [evaluation.md](evaluation.md), [governance.md](governance.md),
[surfaces.md](surfaces.md), [integration-status.md](integration-status.md).

Companion: [prompt-system-audit-2026-10.md](prompt-system-audit-2026-10.md)
(the Wave 7 gap register) and
[prompt-research-2026-10.md](../../standards/evidence/prompt-research-2026-10.md)
(sources S1-S26). Normative output:
[standards/skill-system-standard.md](../../standards/skill-system-standard.md)
(SK-01..SK-14) and [docs/SKILL-TEMPLATE.md](../SKILL-TEMPLATE.md).

Measured: 2026-10-23 with `tooling/report_skill_shape.py` and direct role
measurement. Token estimates are `bytes / 4`. Role bodies exclude frontmatter;
skill figures are whole-file and body-only where stated. Numbers are
reproducible with the commands in section 1.

Status update (Wave 9, 2026-10-23): R1 infrastructure is in place (model
calibration standard, paired no-skill runner with metadata); R2 split the three
bodies that had no reference layer; R3 split the four remaining over-cap bodies
and trimmed two section-heavy bodies. Current tree: body tokens
438 / 1,075 / 1,582, total 22,303; 1 body over 1,500 and it is a frozen vendor
copy; 9 skills with references; no body over 2,000 lacks a reference. Section 1
below is the pre-refactor snapshot; the per-skill rows in section 5 and the R2/R3
rows in section 4 carry the update.

## 0. Decision summary

1. **Adopt the three-layer skill system as normative**: metadata (always),
   body (on trigger), references (on demand). Body target 1,200 tokens, advisory
   cap 1,500, three modules, eight H2 sections (SK-03..SK-05).
2. **Keep the 12/15 element budgets and the 1,000/950/1,100 token targets.**
   They are calibrated to the weakest supported model, and the 2026 capacity
   data does not justify relaxing them for a stronger one (S1, S2).
3. **Measure before refactoring.** The library now has a shape instrument;
   the first refactor action is a paired baseline, not an edit (SK-13).
4. **Do not blanket-split.** Before R2/R3, eight bodies held 64.9% of body
   tokens. After the splits, no non-vendor body is over the cap; only the frozen
   vendor copy is. Do not touch the rest.
5. **Move depth, do not delete rules.** References preserve the content; the
   body keeps the decision gate and the check.
6. **Make prompt assembly cache-stable**: static system prompt, dynamic task
   context in the user turn, skills loaded as separate messages rather than
   concatenated into the cached prefix (S26).
7. **Record the target model and re-baseline on change.** A model change is a
   harness event, not a cosmetic one (S16, AP-01).
8. **Consolidate canon last.** The library (22 skills) and its consumers
   (25 containeromat, 16 dsh, 22 ZCode) already differ; consolidation is a
   registry project, not a copy project (section 3.8).

## 1. Measurement

Wave-8 snapshot (2026-10-23, before the R2/R3 splits):

| Surface | Count | Shape |
|---|---|---|
| Skills | 22 | 8 general, 8 shared, 6 vendor |
| Skill body tokens, min/median/max | 435 / 1,193 / 3,648 | total 35,408 |
| Bodies over 1,500 tokens | 8 (7 non-vendor) | 64.9% of all skill body tokens |
| Bodies over 8 H2 sections (fence-aware) | 7 (1 vendor) | several are multi-job bodies |
| Skills with references | 5 | 4 use `references/`, mcp-builder uses `reference/` |
| Large bodies without references | 3 | skill-creator, jq-json-processing, first-principles-review |
| Missing `## Doctrine position` | 6 | 5 vendor + jq-json-processing |
| `rigid:` declared | 8 of 22 | gated subset only; not a defect, but taxonomy should decide |
| Role templates | 38 | 814 / 954 / 1,464 body tokens; 37,371 total |
| Roles over token target | 13 | see section 6 |
| Roles owning <= 2 phases | 16 | carry the full six-phase doctrine |
| Fragments | 4 files | doctrine 352 tokens + conduct 256 = 608 |
| Standards | 9 | AP, SK, SD, CF, CR, HF, EN, evidence duty, system prompt |
| Trigger cases | 22 files | 21 skills at 3 positive / 2 negative; subagent-delegation at 4 / 3 |
| Behavioral cases | 5 files | 4 discipline skills + subagent-delegation |
| Execution baselines | 1 library copy | 11/12 live dialogue baseline for the discipline cases; XML acceptance live run unverified |

The Wave 7 audit counted six skills over 2,500 whole-file tokens; this table
counts body tokens, so eight exceed the 1,500 body cap. Both are true and they
answer different questions: whole-file size is copy cost, body size is the cost
paid on every trigger.

Reproduce:

```bash
python3 tooling/report_skill_shape.py --limit 0
python3 tooling/report_skill_shape.py --json
python3 tooling/check_skill_routing.py --fail-on-warn
python3 tooling/check_behavioral_evals.py
```

Limits of this measurement:

- `bytes / 4` is an estimate, not a tokenizer. It is consistent across the
  library and good enough for ratios; do not compare it to a vendor counter.
- There is no invocation telemetry in this repository. Priority below is
  inferred from class and shape, not from how often a skill is loaded.
- No paired skill run exists yet, so no claim here is an efficacy claim.

## 2. Diagnosis

### D-01 Body mass is concentrated, not uniformly bloated

Before the pilot, the median body was 1,193 tokens and the smallest was 435.
Eight bodies held 22,986 of 35,408 tokens (64.9%). A blanket split would add
structure to the 14 healthy skills without addressing the cost. Refactor the
over-cap non-vendor bodies (none remain after R3) and stop; vendor bodies are frozen
(SK-10).

### D-02 The reference layer is now present

After R2/R3, nine skills ship reference files and no body over 2,000 tokens
lacks one. The only remaining shape exceptions are vendor-frozen: the caveman
body (1,582 tokens) and misakanet's nine H2 sections. Moving depth preserved
3,121 tokens in skill-creator, 1,473 in first-principles-review, 2,546 in jq,
3,260 in mcp-builder, 2,077 in anti-entropy-governance, 2,803 in
deepseek-v4-agent-defense, and 1,393 in agent-md-refactor.

### D-03 Five vendor skills lack a doctrine position

Before the pilot, six lacked it. Five are vendor copies and legitimately exempt
(SK-10). `jq-json-processing` was the one non-vendor gap and now carries the
section; do not touch vendor bodies.

### D-04 Descriptions are in range but uneven

All 22 descriptions are inside the 5-90 word advisory range; non-vendor
descriptions run 9-51 words, below the 25-70 target at the short end. Short is
not automatically good: the description is the router, and the 2026 authoring
guidance says models under-trigger when context is omitted (S25). The routing
gate passes, but it only proves the current case files can find the skill.

### D-05 Skill bodies duplicate normative rules

`subagent-delegation` restates the SD gate table; other discipline skills
restate parts of AP-03/CR rules. Some restatement is useful as an operational
reminder, but two full copies drift. SK-06 makes the rule explicit: cite the
standard ID, keep at most a one-line reminder. The duplication is currently
small enough to fix during splitting, not a separate project.

### D-06 Role prompts carry doctrine cost they may not need

Every role carries the full six-phase doctrine (352 tokens), including 16 roles
that own two or fewer phases. Doctrine plus conduct is 608 tokens, 63.7% of the
median role body. A compact doctrine variant for low-phase roles would save
roughly 230 tokens per invocation; across the 16 roles that is about 3,700
tokens per full roster cycle, or 10% of the role corpus. That is a hypothesis
to test, not a change to make by argument (S20; AP-14 keeps the fragment
byte-exact until an A/B supports a registered variant).

### D-07 Evaluation was structure-only (now paired)

The gate battery is strong on shape, order, fragments, routing, and case
schema. Historically it did not answer "does this skill make the agent better
on a task?" Wave 9 added a 13-skill paired baseline with 3 seeds and metadata
(0.869 with the skill vs 0.555 without). The remaining limits are the generic
no-skill baseline and the lack of a per-refactor delta; see
`evals/results-baseline.md`.

### D-08 Canon is skewed across consumers

The library holds 22 skills; containeromat holds 25, dsh 16, ZCode 22. Seven
generalizable skills remain reference-only. Resolution (2026-10-27): the
single-canon rule is about the consumer's LOCAL canon root, and
`containeromat:scripts/skills-library.json` already owns this library's names, so
relocating a skill here is content work with a paired baseline, not a registry
change. Every new library skill widens the gap until consumers re-vendor. Commit
order matters: library first, then consumer copies, then seed-version bumps.

### D-09 Assembly was unstated (now AS-01..AS-08)

Nothing in the library stated how a runtime should assemble the static system
prompt, the dynamic task context, and a loaded skill. Wave 9 adds
`standards/prompt-assembly.md`: static prefix, dynamic user turn, separate skill
message, routed references, and a cache breakpoint on the last stable block
(S26). Hit-rate measurement is still owed.

### D-10 Model calibration was not recorded (now MC-01..MC-04)

AP-01 and S2 name DeepSeek V4 Pro as the weakest supported target (~750
constraints), but no single artifact recorded the target model, harness, date,
and the tier. Wave 9 adds `standards/model-calibration.md` with that table; a
model or harness change still requires re-baselining.

## 3. Target architecture

### 3.1 Three layers, three costs

| Layer | Budget | Loaded | Failure if wrong |
|---|---|---|---|
| Metadata | ~100 words per skill; description 25-70 words | Always | Misroute or undertrigger; permanent token tax |
| Body | <= 1,200 tokens target, 1,500 cap; <= 3 modules; <= 8 H2 | On trigger | Context cost on every use; procedure buried |
| References | Unbounded; TOC over 300 lines | On demand | Depth unavailable or never read |

The always-loaded layer is the only layer that scales with the number of
skills. The 22 descriptions total 748 words; all frontmatter totals about 1,010
words. At the 100-word ceiling the same set would be 2,200 words, which is why
the growth policy belongs to routing (merge duplicate intent, retire dead
skills), not to body compression.

### 3.2 Taxonomy: five classes, five contracts

| Class | Current examples | Contract |
|---|---|---|
| discipline | anti-hallucination, anti-sycophancy, anti-entropy, verification | Behavioral invariant; 3 pressure cases; rigid posture |
| workflow | subagent-delegation, skill-creator, grilling, first-principles | Multi-step procedure; dialogue case; paired baseline |
| tool/domain | jq, mcp-builder, convert-documents, deepseek-v4 defense | Mechanics; execution case when a fixture exists |
| vendor | caveman family, misakanet | Freeze; marker only; smoke trigger |
| project | compose-*, forgejo-registry, seifomat-* | Not in this canon; consumer-owned |

Class decides eval tier and edit rights. It is not a quality ranking. A vendor
skill that needs restructuring is forked with provenance, never edited.

### 3.3 Body contract

1. Frontmatter: name, description, `rigid` for gated skills, optional category.
2. One paragraph: what the skill buys, what it costs, when not to use it.
3. At most three modules: decision gate, procedure, verification/failure.
4. `## Doctrine position` (AP-14).
5. `## References` with a "when to read" line per file.

No second H1. No runtime counters (AP-04). No host-only names (AP-13.6). No
duplicated standard text (SK-06). The skeleton is in `docs/SKILL-TEMPLATE.md`.

### 3.4 Routing

- The description is a classifier over user vocabulary, not a summary for
  humans. Include synonyms and the artifact the skill produces.
- Minimum cases: 3 positive and 2 negative-owned for existing skills, 4 and 2
  for new ones (SK-11). Add a positive prompt that uses a synonym rather than
  the skill's own nouns.
- Keep the lexical gate: deterministic, free, and already blocking. Add an
  embedding or judge check beside it as an experiment; do not replace the
  deterministic check until the replacement is itself deterministic in CI.
- Growth rule: a new skill must own an intent no existing description claims.
  If two descriptions collide above the Jaccard threshold, merge or re-scope
  before adding cases.

### 3.5 Evidence ladder

| Tier | Question | Cost | Gate |
|---|---|---|---|
| 0 shape | Is the body the right shape? | free | advisory report |
| 1 structure | Frontmatter, anatomy, doctrine, ASCII, host-neutral | free | validators |
| 2 routing | Can the description find and not steal the request? | free | `check_skill_routing.py` |
| 3 behavior | Does the procedure hold under pressure? | model tokens | structural schema + on-demand runner |
| 4 efficacy | Does the skill beat no-skill on the same model/harness? | model tokens, seeds | paired baseline |

The refactor may not claim tier-4 benefit from tier-0/1 evidence. Tiers 1-2 are
CI; tier 0 is an advisory report run in the same pass; tier 3 is a scheduled
run; tier 4 is a release gate for a shape change.

### 3.6 Role prompts

- Keep the block order and the U-shape: role, hard rules, doctrine, workflow
  (or the documented `<scope>` variant), conduct, output last (AP-02, AP-09).
  Output last is worth more than a short cache extension inside the system
  prompt.
- Keep 12/15 element budgets. Trim by merging duplicate prose, not by deleting
  behavioral requirements (AP-01).
- Tested a compact doctrine variant for the 16 roles with two or fewer phases.
  Full run (3 seeds): compact 0.674 vs full 0.708, with only about 14 tokens
  saved per case. Decision: keep the full fragment; no variant is registered.
  Protocol and results are in
  [role-doctrine-experiment.md](role-doctrine-experiment.md).
- Review-phase roles are the largest bodies (review-lead 1,464 tokens). Treat
  them as the first role-trim candidates after the doctrine experiment.
- Phase maps stay prose, so they do not consume element budget.

### 3.7 Assembly and token cache

The library states one assembly contract for consumers
([standards/prompt-assembly.md](../../standards/prompt-assembly.md),
AS-01..AS-08):

1. **System message**: role, hard rules, doctrine, workflow, conduct, output
   contract. Static for the whole run; no timestamps, no task text, no file
   contents.
2. **User turn**: task context, retrieved files, and any per-request data.
3. **Skill**: loaded as its own message or tool result when triggered, not
   concatenated into the system prefix.
4. **References**: loaded only after the body routes to them.

Why: a cache breakpoint must sit on the last block identical across requests;
per-request content at the breakpoint prevents any hit, and the default TTL is
five minutes (S26). A cache hit is a workload-dependent benefit, not a guarantee.
The separate-message rule for skills is an engineering inference from the
cache mechanics, not a direct claim in S26.

### 3.8 Canon and governance

- End state: one canon root for library-owned skills, consumer copies generated
  from it, one manifest hash per skill, seed-version bump on change. Project
  roots are referenced externally, not merged.
- Precondition: the registry can reference an external project root. The seven
  reference-only skills stay consumer-owned (project class); a body moves only
  after a generalization pass that reclassifies it, not because the registry
  changed.
- Until then: library additions must be coordinated with a consumer re-vendor
  in the same release note. A library-only skill is not "shipped" to runtimes.
- Retire by archive note and catalog removal, never silent deletion.

### 3.9 Model calibration

Add one table, owned by the prompt standard, with: target model, measured
constraint capacity, source and date, harness, and the budget tier it
justifies. Re-baseline when model or harness changes. The table is the place to
argue for a budget change; an argument without it is a regression (AP-01).
Wave 9 ships this as `standards/model-calibration.md` (MC-01..MC-04).

## 4. Execution plan

| Wave | Window | Work | Exit criteria |
|---|---|---|---|
| R0 | 2026-10-23 (this wave) | Instrument, standard, template, analysis; no prompt-content edits | `report_skill_shape.py` green; SK standard published; docs updated |
| R1 | done 2026-10-23 | Paired campaign over 13 shape-changed skills, 3 seeds, model/harness/seed metadata | Paired results recorded (0.869 vs 0.555); calibration table filled |
| R2 | done 2026-10-23 | Split the large bodies with no references: jq, skill-creator, first-principles-review; doctrine and class cases added | All three bodies <= 1,500; references route; paired results in `results-baseline.md` |
| R3 | done 2026-10-23 | Split mcp-builder, anti-entropy-governance, deepseek-v4-agent-defense, agent-md-refactor; trim ask/verification H2 | All non-vendor bodies <= 1,500; paired results recorded; doctrine pilot run |
| R4 | design done; `anthropic-5m` baseline measured 2026-10-27 | Cache hit measurement against AS-01..AS-12; canon consolidation design | Hit-rate baseline (cold 0.0000, warm 0.9973, 3 seeds); migration plan; doctrine decision recorded (keep full) |
| R5 | ongoing | Reflective optimization on the labelled set (GEPA/ACE style) | One proposal per cycle, human-gated |

Ordering rule: baseline before split, split before merge, merge before retire.

## 5. Skill dispositions

Priority is shape-led: P1 means the body is over the cap, lacks a reference
layer, and is not vendor-frozen; P2 means over cap but already has one; P3
means structural cleanup only.

| Skill | Class | Body | Refs | Action | Target |
|---|---|---|---|---|---|
| mcp-builder | tool | 1,074 | 5 | **Done (R3)**: body = design rules + phase table; phases/docs in `reference/workflow.md`; one H1; 3 dialogue cases | 1,074, done |
| anti-entropy-governance | discipline | 1,455 | 2 | **Done (R3)**: body = checklist + principle + gates; class/guard detail in `references/retirement-playbook.md` | 1,455, done |
| deepseek-v4-agent-defense | tool | 1,135 | 2 | **Done (R3)**: body = failure modes + layer summary; rules in `references/layer-rules.md`, examples in `layers.md`; 3 dialogue cases | 1,135, done |
| skill-creator | workflow | 1,171 | 1 | **Done (R2)**: body = decision gate + workflow + gates; anatomy/process in `references/authoring-guide.md`; 3 dialogue cases | 1,171, done |
| jq-json-processing | tool | 923 | 1 | **Done (R2 pilot)**: body = selector + safety; recipes in `references/recipes.md`; doctrine added; 3 dialogue cases added | 923, done |
| first-principles-review | workflow | 1,373 | 1 | **Done (R2)**: body = instrument + five-line review; lenses in `references/lenses.md`; 3 dialogue cases | 1,373, done |
| agent-md-refactor | workflow | 1,076 | 1 | **Done (R3)**: body = phase rules + checklist; templates/examples in `references/refactor-guide.md`; 3 dialogue cases | 1,076, done |
| caveman | vendor | 1,582 | 0 | Freeze | unchanged |
| misakanet | vendor | 1,385 | 0 | Freeze; 9 H2 is upstream shape | unchanged |
| ask-questions-if-underspecified | workflow | 1,318 | 0 | **Done (R3)**: H2 10 -> 8; 3 dialogue cases; description still below the 25-word target | <=1,500 (1,200 target open) |
| verification-before-completion | discipline | 1,233 | 0 | **Done (R3)**: H2 11 -> 8; gate table kept | <=1,500 (1,200 target open) |
| subagent-delegation | workflow | 1,165 | 0 | Keep; replace duplicated SD prose with one-line reminders (SK-06) | <= 1,200 |
| caveman-compress | vendor | 1,147 | 0 | Freeze | unchanged |
| anti-sycophancy | discipline | 1,029 | 1 | Keep | <= 1,200 |
| anti-hallucination | discipline | 979 | 1 | Keep | <= 1,200 |
| changelog-generator | workflow | 764 | 0 | Keep; 7 H2; 3 dialogue cases | <= 1,200 |
| git-guardrails | discipline | 699 | 0 | **Done**: rigid posture; 3 pressure cases | <= 1,200 |
| caveman-review | vendor | 656 | 0 | Freeze | unchanged |
| caveman-commit | vendor | 609 | 0 | Freeze | unchanged |
| caveman-help | vendor | 580 | 0 | Freeze | unchanged |
| convert-documents-to-markdown | tool | 512 | 0 | Keep; 3 dialogue cases (OCR/CSV/large-file) | <= 1,200 |
| grilling | workflow | 438 | 0 | Keep; 3 dialogue cases | <= 1,200 |

Do not split a vendor body. Do not split a body that is already under 1,200
without a paired reason (SK-13).

**SK-12 debt closed (2026-10-23).** All 16 non-vendor skills now have a
behavioral file with at least 3 cases, including the five discipline skills
(`git-guardrails` joined the required set). Vendor copies are exempt from
behavioral cases under SK-10; their SK-11 trigger cases prove reachability.
`check_behavioral_evals.py` enforces the schema and the five required discipline
names.

## 5a. H2 shape changes (2026-10-26)

`tooling/report_skill_shape.py` reported eight skills with nine H2 sections. One
is the frozen vendor copy `misakanet`, so seven non-vendor skills remained. The
target is at most eight H2 sections (SK-01..SK-14). All seven were merged and
measured with an old-vs-new A/B: old `2cd4e43` vs the merged body, three seeds,
22 cases. The result is **0.899 old vs 0.9345 new**, 56/66 vs 57/66 full passes,
8 wins / 53 ties / 5 losses. No skill loses on mean score.

| Skill | H2 after | Merge | Reason |
|---|---|---|---|
| `anti-entropy-governance` | 8 | "Repo bindings" -> bold lead-in in "Core principle and hard stops" | Bindings are inputs to the same stop set |
| `first-principles-review` | 8 | "Boundaries" -> bold lead-in in "Use and non-use" | Both define scope; the use criteria stay first |
| `ask-questions-if-underspecified` | 8 | "Goal" -> paragraph in "When to Use" | The goal is one sentence |
| `skill-creator` | 8 | "Project constraints" -> bold lead-in at the end of "Workflow" | Keeps the constraints after the procedure |
| `verification-before-completion` | 8 | "The Bottom Line" -> closing paragraph in "Doctrine position" | Keeps the summary at the end |
| `mcp-builder` | 8 | "Design rules" -> bold lead-in in "Implementation rules" | Both are one rules block |
| `deepseek-v4-agent-defense` | 8 | "Why this skill exists" -> intro paragraph under the H1 | The reason is the failure it prevents |

Method, limits, and the model note (free Nemotron proxy because DeepSeek
returned 402 and OpenAI 401) are in
[h2-shape-ab-2026-10.md](h2-shape-ab-2026-10.md). `report_skill_shape.py` now
reports `H2>8=1`, the frozen vendor `misakanet`.

## 6. Role dispositions

13 of 38 bodies exceed the token target. The largest:

| Role | Tokens | Target | Action |
|---|---|---|---|
| review-lead | 1,464 | 1,100 | Merge duplicated contract prose; keep the merge rules |
| ops-executor | 1,174 | 950 | Merge runbook duplicates; move mechanics to docs |
| orchestrator | 1,152 | 1,100 | Trim prose, keep sequencing rules |
| network-architect | 1,124 | 1,000 | Merge overlapping constraints |
| frontend-developer | 1,116 | 1,000 | Merge framework guidance into one paragraph |
| reviewer | 1,116 | 950 | Merge dual-workflow prose |

The remaining overages are between 1,001 and 1,100 tokens. The recorded
decisions are in
[token-warning-triage-2026-10.md](token-warning-triage-2026-10.md); none of the
roles is trimmed until the doctrine experiment reports.

## 7. What not to do

- Do not split every skill to hit a number; the median is already healthy.
- Do not delete a behavioral rule to save tokens (AP-01).
- Do not edit a fragment for cache or size convenience; use a registered
  variant and a manifest bump.
- Do not add a skill for a one-off task, or a second skill for an intent an
  existing description already owns.
- Do not make the 1,500-token advisory cap a hard gate just because it is
  measurable; no non-vendor body is over it now, and a size gate still needs a
  paired rationale (SK-03).
- Do not claim an efficacy gain from a shape gate.
- Do not copy vendor bodies into canon restructuring.

## 8. Open questions and falsifiers

| Question | Falsifier | Measurement |
|---|---|---|
| Does the 1,200-token target help, or is it arbitrary? | A paired run shows no difference or a loss | Tier-4 paired, 3 seeds |
| Does compact doctrine help low-phase roles? | Stronger model becomes more literal and slower | Role A/B on 16 roles |
| Does splitting a skill improve success or only reduce tokens? | Pass rate drops after split | Per-skill paired run |
| Does cache-aligned assembly improve hit rate? | Hit rate unchanged or TTL never hit | Host cache diagnostics |
| Does semantic routing beat lexical? | No reduction in misroutes on the same cases | Blind judge on 22 case files |
| Is canon consolidation worth the registry change? | A drift log shows no incident and the registry cost exceeds the drift it prevents | Drift log + copy counts |

## 9. Evidence map

| Design decision | Evidence | Confidence |
|---|---|---|
| Metadata/body/reference layers | S17, S24, S25 | verified |
| Body under 500 lines, references on demand | S25 | verified |
| Focused skills beat exhaustive bundles | S10 | verified |
| Descriptions must carry trigger context | S25 | verified |
| Keep element budgets for the weakest model | S1, S2 | verified |
| Paired eval before/after a skill change | S10, S13, S16 | verified |
| Single-threaded writes; clean-context verification | S7-S9, S11 | verified |
| Static prefix, dynamic user turn for caching | S26 | verified mechanism; workload benefit likely |
| Compact doctrine for low-phase roles | S20 | hypothesis |
| 1,200-token target | S25 shape guidance + local median | advisory, not causal |

## 10. Documentation changes in this wave

- New: `standards/skill-system-standard.md` (SK-01..SK-14).
- New: `standards/model-calibration.md` (MC-01..MC-04) -- R1 calibration record.
- New: `standards/prompt-assembly.md` (AS-01..AS-08) -- cache-aligned assembly
  contract.
- New: `CHANGELOG.md` -- G-13 prompt-surface change log.
- New: `docs/knowledge-base/role-doctrine-experiment.md` -- compact doctrine
  protocol and candidate text, not active.
- New: `docs/knowledge-base/token-warning-triage-2026-10.md` -- decisions for
  the 15 AP-01 WARN rows.
- New: `docs/knowledge-base/consumer-revendor-wave9.md` -- exact re-vendor and
  seed-bump steps for the consumer; no consumer files were touched.
- New: `tooling/run_role_doctrine_experiment.py` + fixtures under
  `evals/role-doctrine/` -- pilot harness for the compact-doctrine A/B.
- New: `tooling/summarize_behavioral_results.py` -- aggregates paired
  skill/no-skill result files into a delta table.
- New: `docs/knowledge-base/stop-gate-experiment.md` and
  `tooling/run_stop_gate_experiment.py` -- STOPP vs light/direct/risk evidence;
  recommendation is to keep STOPP with a narrow comment-only fast path.
- New: `standards/stop-gate.md` (SG-01..SG-09), `tooling/classify_change.py`,
  and `docs/knowledge-base/consumer-stopp-fastpath.md` -- the adopted fast-path
  rule and the consumer patch.
- New: `tooling/run_refactor_ab.py` and `docs/knowledge-base/refactor-ab-2026-10.md`
  -- old-vs-new body A/B: 0.875 old vs 0.886 new, 41% fewer tokens, 3 seeds.
- New: `tooling/run_role_ab.py` and `docs/knowledge-base/role-body-ab-2026-10.md`
  -- role-body pilot: frontend 1.000 vs 0.889, one WARN closed.
- New: `docs/knowledge-base/harness-telemetry.md` and
  `tooling/check_harness_telemetry.py` -- the field contract for cache and gate
  evidence.
- New: `docs/SKILL-TEMPLATE.md` (copyable skeleton + checklist).
- New: `tooling/report_skill_shape.py` + `tooling/tests/test_report_skill_shape.py`.
- Runner: `run_behavioral_evals.py` gains `--mode both` (paired no-skill
  baseline), `--seed`, per-mode result files, and a `run` metadata block with
  model, grader, harness, seed, temperature, and UTC timestamp.
- `validate_templates.py` reports the AP-01 token target as a WARN; the run
  still exits 0.
- R2/R3 splits: the seven over-cap bodies were reduced and their detail moved
  to `references/`; the jq, skill-creator, first-principles, mcp, anti-entropy,
  deepseek, and agent-md bodies now sit at 923-1,455 tokens. The three R2 splits
  and the three R3 splits that lacked one gained three dialogue cases each;
  `anti-entropy-governance` already had cases. `ask-questions` and
  `verification-before-completion` were trimmed to eight H2 sections.
- Behavioral cases: all 16 non-vendor skills now have a file with at least
  three cases (16 files); vendor copies are exempt under SK-10.
- Paired baseline: 13 skills, seeds 7/11/23, 0.869 with skill vs 0.555
  without; table in `evals/results-baseline.md`.
- Register: S25 (skill authoring) and S26 (prompt caching) added.
- `evals/trigger/anti-hallucination.json`: adds the second negative case
  required by SK-11 (no existing case changed).
- Updated: `skills/SKILLS.md` (Type/Origin columns, shape section), `README.md`,
  `PLAN.md`, `CONTRIBUTING.md`, `docs/TEMPLATE-GUIDE.md`, `governance.md`,
  `evaluation.md`, `surfaces.md`, `integration-status.md`, `evals/README.md`,
  `prompt-system-audit-2026-10.md`,
  `standards/agent-prompt-standard.md` (AP-01 skill note + cross-ref).

Wave 8 added infrastructure without prompt-content edits. Wave 9 changed nine
skill bodies as seven splits and two H2 trims, with recorded AP-13.8 baseline
deferrals; role templates and fragments remain untouched.

## 11. Cross-refs

- [prompt-system-audit-2026-10.md](prompt-system-audit-2026-10.md) -- Wave 7 gap
  register (G-01..G-14)
- [standards/skill-system-standard.md](../../standards/skill-system-standard.md)
  -- normative rules
- [docs/SKILL-TEMPLATE.md](../SKILL-TEMPLATE.md) -- skeleton
- [skills/SKILLS.md](../../skills/SKILLS.md) -- catalog and class assignment
- [evaluation.md](evaluation.md) -- gate and baseline status
