# Prompt and skill system research register (2026-10)

Status: evidence record for the 2026-10 audit, the subagent-delegation
standard, and the agent-context-files standard.

Access date: 2026-10-23. S25-S26 were added by Wave 8 (skill and prompt
refactor) on the same date; S1-S24 back Wave 7.

Method: primary sources were fetched during this run; abstracts and the result
sections that carry the numbers were read. No claim is taken from model memory.
Claim labels:

- `verified` -- the fetched source states the claim (it does not mean the
  result was independently replicated).
- `likely` -- secondary source, partial evidence, or a reasonable inference
  across sources.
- `unverified` -- not confirmed; kept only to name an open question.

The register is deliberately conservative. Vendor engineering posts are
labelled as such; peer-reviewed or preprint results are preferred where both
exist.

## 1. What changed since the 2025 standard

1. Instruction capacity is model-tiered, not universal. The 2025 finding that
   quality collapses near a few hundred simultaneous constraints still holds for the
   models tested then, but 2026 frontier models track thousands of named
   constraints while the weakest current model in the same test starts losing
   them near 750 (`verified`, S1, S2).
2. The binding constraint moved from "can the model follow the instruction" to
   "what does the context cost, and which harness uses it". Harness-induced
   variance can exceed model-induced variance (`verified`, S16).
3. Skills became a standard layer: metadata first, body on demand, references
   last. Paired evaluation shows a real but variable gain (`verified`, S10,
   S17, S24).
4. Multi-agent evidence matured into a narrow rule: parallel read-only work can
   help; parallel writes fragment decisions (`verified`, S6, S7, S11).
5. Repository context files are a router, not a manual. Generic overviews do
   not improve success and can add about 20% inference cost (`verified`, S13,
   S14, S15).

## 2. Source register

| ID | Source | Type | Key result used here | Label |
|---|---|---|---|---|
| S1 | Jaroslawicz et al., "How Many Instructions Can LLMs Follow at Once?" (IFScale), arXiv 2507.11538, 2025 | preprint | 20 models, 500 keyword constraints; best frontier model reaches 68% at N=500; bias toward earlier instructions; three degradation patterns | verified |
| S2 | Arize, "Models got an order of magnitude better at following instructions in one year", 2026 | vendor benchmark | frontier ceiling moved from ~200-300 to ~2,000; GPT-5.5 ~99% through N=5,000; Gemini 3.1 Pro strong to N=5,000; Claude Opus 4.7 ~50% at N=5,000; DeepSeek V4 Pro starts dropping near N=750 and ignores about half by N=2,000 | verified |
| S3 | Chroma, "Context Rot", 2025 | vendor research | 18 models; performance is non-uniform and degrades as input length grows even on simple tasks; distractors amplify the effect | verified |
| S4 | "Context Length Alone Hurts LLM Performance Despite Perfect Retrieval", arXiv 2510.05381, 2025 | preprint | 5 models; 13.9%-85% degradation as input length grows even when all relevant evidence is retrievable and distractions are removed | verified |
| S5 | Anthropic, "Effective context engineering for AI agents", 2025 | vendor engineering | context is a finite attention budget; compaction, note-taking, and sub-agents are the three long-horizon strategies; sub-agents return 1,000-2,000 token summaries | verified |
| S6 | Anthropic, "How we built our multi-agent research system", 2025 | vendor engineering | orchestrator-worker beat single-agent Claude Opus 4 by 90.2% on an internal research eval; ~4x chat tokens for one agent, ~15x for multi-agent; token use alone explains 80% of BrowseComp variance; 3-5 parallel subagents; vague delegation causes duplicated work | verified |
| S7 | Cognition, "Don't Build Multi-Agents", 2025 | vendor engineering | parallel agents make conflicting implicit decisions; share full context or do not parallelize writes | verified |
| S8 | Cognition, "Multi-Agents: What's Actually Working", 2026-04-22 | vendor engineering | working patterns keep writes single-threaded; clean-context code review catches ~2 bugs per PR, ~58% severe; "smart friend" escalation and map-reduce-manage work; parallel writer swarms still do not | verified |
| S9 | Cemri et al., "Why Do Multi-Agent LLM Systems Fail?" (MAST), arXiv 2503.13657, v3 2025 | preprint / NeurIPS 2025 | 1,600+ traces, 7 frameworks, 14 failure modes in 3 categories (system design, inter-agent misalignment, task verification), kappa 0.88; 41%-86.7% failure rate; better role specification +9.4% success; an added verification step +15.6% | verified |
| S10 | Li et al., "SkillsBench", arXiv 2602.12670, 2026 | preprint / benchmark | 87 tasks, 8 domains, 18 model-harness configurations; curated skills raise pass rate 33.9% -> 50.5% (+16.6 pp; +4.1 to +25.7 pp per configuration); focused skills with at most three modules beat larger bundles; smaller models with skills can match larger models without | verified |
| S11 | "When Sub-Agents Work in Parallel: The Promises and Pitfalls of Dynamic Concurrency in Long-Horizon Coding Tasks", arXiv 2610.10263, 2026 | preprint | 354 tasks, 2,124 executions; dynamic concurrency uses 1.41x-3.31x tokens; helps long-horizon tasks, little or negative on bounded tasks; concurrent writes are a distinct failure category (26.5% of instances; 62.9% for Codex); concurrency was >=20% faster on 12.6% of jointly solved tasks | verified |
| S12 | "MS-Eval: Benchmarking Sub-Agent Delegation and Orchestration in MCP-Intensive Working Scenarios", arXiv 2610.22869, 2026 | preprint | sub-agent specialization is the best practical practice; delegation generally raises cost with contingent payoff; some closed-source models got higher cost and degraded performance; redundant delegation is pure overhead | verified |
| S13 | Gloaguen et al., "Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?", arXiv 2602.11988, 2026 | preprint | developer-written context files +4% success, LLM-generated -3%; inference cost +20% to +23%; instructions are generally followed; repository overviews are not helpful | verified |
| S14 | Lulla et al., "On the Impact of AGENTS.md Files on the Efficiency of AI Coding Agents", arXiv 2601.20404, 2026 | preprint | 10 repositories, 124 pull requests; AGENTS.md associated with -28.64% median runtime and -16.58% output tokens, with comparable task completion | verified |
| S15 | "Agent READMEs: An Empirical Study of Context Files for Agentic Coding", arXiv 2511.12884, 2025 | preprint | 2,303 context files from 1,925 repositories; testing 75.9%, implementation 70.8%, architecture 68.1%; security 14.8%, performance 14.5%; files evolve like configuration code through frequent small additions | verified |
| S16 | "Stop Comparing LLM Agents Without Disclosing the Harness", arXiv 2605.23950, 2026 | position paper | harness configuration can be a stronger determinant of long-horizon performance than the model; same model scored 45.9% under one scaffold and 55.4% under another | verified |
| S17 | "Report: Progressive Disclosure of Agent Skills", arXiv 2609.35692, 2026 | industry report | lazy-loading skills improves retrieval quality and token use but adds a marginal latency cost; reported token savings up to 81.7% and latency +15% at N=50 | verified |
| S18 | "Configuration, Not Conscience: A Large-Scale Empirical Study of LLM System Prompts", arXiv 2609.31575, 2026 | preprint | 407 prompts from 62 vendors; ~58% of classified words are tool/protocol, ~5% safety policy; tool and file safety rules outnumber harmful-content rules 11:1; measurable maintenance debt and prompt rot | verified |
| S19 | Agrawal et al., "GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning", arXiv 2507.19457, 2025 | preprint / NeurIPS 2025 | reflective prompt evolution beats GRPO by 6% on average and up to 20%, with up to 35x fewer rollouts; beats MIPROv2 by >10% | verified |
| S20 | "You Don't Need Prompt Engineering Anymore: The Prompting Inversion", arXiv 2510.22251, 2025 | preprint | constrained prompting helped GPT-4o (97% vs 93% for CoT) but hurt GPT-5 (94.00% vs 96.36% for CoT); constraints that prevent errors in mid-tier models can induce hyper-literalism in advanced models | verified |
| S21 | Leviathan et al., "Prompt Repetition Improves Non-Reasoning LLMs", arXiv 2512.14982, 2025 | preprint | repeating the input improves performance across Gemini, GPT, Claude, and DeepSeek when reasoning is off, without increasing generated tokens or latency | verified |
| S22 | "Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models" (ACE), arXiv 2510.04618, 2025 | preprint | evolving playbooks with generation, reflection, and curation avoid brevity bias and context collapse; +10.6% on agents and +8.6% on finance in the reported benchmarks | verified |
| S23 | agents.md project, accessed 2026-10-23 | specification site | AGENTS.md is an open, vendor-neutral Markdown format used by 60k+ open-source projects; no required fields; nearest file in the tree wins; nested files for monorepos | verified (adoption count is self-reported) |
| S24 | Anthropic, "Equipping agents for the real world with Agent Skills", 2025 | vendor engineering | three-level progressive disclosure: metadata, body, linked files; skills are an open format | verified |
| S25 | Anthropic, "Skill authoring best practices" (skill-creator), accessed 2026-10-23 | vendor documentation | metadata about 100 words and always loaded; body under 500 lines; references load on demand and can be unlimited; a reference over 300 lines opens with a TOC; models under-trigger, so descriptions state concrete contexts | verified |
| S26 | Anthropic, "Prompt caching", accessed 2026-10-23 | vendor documentation | cache breakpoint must be on the last identical block; per-request content at the breakpoint prevents a hit; default TTL 5 minutes, 1 hour at a higher write price; tool_choice and image changes invalidate the message cache | verified |

## 3. Findings

### 3.1 Instruction budgets remain necessary, but must be tiered

IFScale's result is about density, not tokens: the best model in that study
followed 68% of 500 simultaneous keyword constraints, and accuracy declined
with density (S1, `verified`). The 2026 replication does not overturn that
result; it shows the ceiling moved for the strongest models and did not move
equally for every model (S2, `verified`).

Consequence: a single element budget for every supported model is a floor, not
a capability statement. The library targets Kilo and DSH runtimes, and DSH
defaults to DeepSeek-class models. DeepSeek V4 Pro is the weakest model in the
2026 replication, starting to drop constraints near N=750 and ignoring about
half by N=2,000 (S2, `verified`). The existing 12/15-element budgets are
therefore well matched to the weakest supported target, and should not be
relaxed globally because a frontier model can absorb more.

### 3.2 Long context degrades before the window is full

Chroma measured non-uniform degradation across 18 models as input length grew,
including on simple retrieval tasks and with distractors (S3, `verified`).
A separate 2025 study found 13.9%-85% degradation even when all relevant
evidence was perfectly retrievable, when irrelevant tokens were whitespace, and
when the evidence was placed immediately before the question (S4, `verified`).
Anthropic frames the same effect as an attention budget (S5, `verified`).

Consequence: "the window is large" is not an argument for a long prompt.
Removing tokens that do not change behavior is still a correctness measure,
not only a cost measure.

### 3.3 Prompting strategy must co-evolve with the model

The "Prompting Inversion" result is the cleanest counterexample to a universal
prompt doctrine: a constrained, rule-based prompt helped GPT-4o (97% vs 93%)
and hurt GPT-5 (94.00% vs 96.36% for CoT) on GSM8K (S20, `verified`). The
authors describe a "guardrail-to-handcuff" transition: constraints that prevent
common-sense errors in a mid-tier model induce hyper-literalism in a stronger
one.

Consequence: a rigid procedure that is load-bearing for one model can be a
handicap for another. Prompt changes need a model-specific baseline, not a
global style rule.

### 3.4 Repetition is a cheap intervention for non-reasoning paths

Repeating the input prompt improved performance across Gemini, GPT, Claude,
and DeepSeek when reasoning was disabled, without increasing generated tokens
or latency (S21, `verified`). The abstract does not establish a universal gain
or a mechanism; treat it as a cheap A/B candidate, not a default.

### 3.5 Skills work, but the effect is variable and shape-sensitive

SkillsBench's paired evaluation found a +16.6 percentage point average gain
(33.9% -> 50.5%) across 18 model-harness configurations, but the per
configuration range was +4.1 to +25.7 pp (S10, `verified`). The same study
found that focused skills with at most three modules outperform larger or
exhaustive bundles, and that smaller models with skills can match larger
models without them (S10, `verified`).

Consequence: skill value is empirical and must be measured against a no-skill
baseline on the same harness. A skill library that only checks structure and
trigger routing is not yet measuring the outcome that matters.

### 3.6 Progressive disclosure is the right loading model

The Workday report found that lazy-loading skills improves retrieval quality
and token use but adds a marginal latency cost; it reports token savings up to
81.7% with latency rising about 15% at N=50 (S17, `verified`). Anthropic's
three-level model (metadata, body, linked files) is the same architecture
(S24, `verified`).

Consequence: keep the always-loaded layer small, the skill body focused, and
deep material in references. The description is part of the routing surface;
it is not marketing copy.

### 3.7 Subagents buy breadth and context isolation, not general intelligence

Anthropic's orchestrator-worker system beat single-agent Claude Opus 4 by
90.2% on an internal research eval, using ~15x chat tokens; token use alone
explained 80% of the variance (S6, `verified`). The gain came from parallel
breadth and separate context windows, not from a smarter model. The same post
states that most coding tasks have fewer truly parallelizable subtasks than
research (S6, `verified`).

Cognition's 2026 follow-up narrows the pattern further: working multi-agent
systems keep writes single-threaded and let additional agents contribute
intelligence rather than actions; parallel writer swarms still do not work
(S8, `verified`). Clean-context review caught about 2 bugs per PR, 58% severe
(S8, `verified`).

### 3.8 Multi-agent failures are mostly specification and verification failures

MAST annotated 1,600+ traces across 7 frameworks and found 14 failure modes in
three categories: system design, inter-agent misalignment, and task
verification; the failure rate across the studied systems was 41%-86.7%
(S9, `verified`). Improving role specifications raised ChatDev success by 9.4%;
adding a high-level verification step raised it by 15.6% on ProgramDev
(S9, `verified`).

An independent 2026 coding study adds a concrete coordination failure:
concurrent writes to the same or related files are a distinct failure category,
present in 26.5% of instances and 62.9% for Codex; dynamic concurrency used
1.41x-3.31x tokens and was >=20% faster on only 12.6% of jointly solved tasks
(S11, `verified`). MS-Eval found that sub-agent specialization is the best
practical practice and that unnecessary delegation turns the cost into pure
overhead (S12, `verified`).

Consequence: delegation is a design decision with hard gates (write isolation,
specifiability) and a measurable cost. It is not a default scaling move.

### 3.9 Context files are routers, not manuals

The ETH Zurich evaluation found that developer-written context files improved
task success by 4% on average, LLM-generated ones reduced it by 3%, and
inference cost rose 20%-23% (S13, `verified`). Instructions in the files were
generally followed; repository overviews were not helpful (S13, `verified`).
A second study found AGENTS.md associated with -28.64% median runtime and
-16.58% output tokens with comparable completion (S14, `verified`). The two
results are compatible: repo-specific facts can make an agent more efficient
without making it more correct.

A large corpus study of 2,303 context files found they prioritize test
procedures, implementation details, and architecture, while security and
performance requirements are rarely specified; they also evolve like
configuration code and accumulate maintenance debt (S15, `verified`).

Consequence: keep the always-loaded file short and operational. Put procedures
in skills, invariants in executable gates, and deep material in linked docs. A
generic architecture overview is the first section to cut.

### 3.10 The harness is part of the prompt system

A 2026 position paper argues that for long-horizon tasks, harness
configuration (context construction, tool interaction, orchestration,
verification) can be a stronger determinant of performance than the model; the
same model scored 45.9% under one scaffold and 55.4% under another (S16,
`verified`). A large corpus of production system prompts found that operational
content dominates (~58% tool/protocol words, ~5% safety policy) and that prompts
carry measurable maintenance debt (S18, `verified`).

Consequence: version the harness with the prompt, record the model and harness
on every eval result, and treat prompt edits as configuration changes with an
owner and a changelog.

### 3.11 Prompt optimization is now empirical, and can be automated

GEPA uses natural-language reflection on trajectories to evolve prompts and
outperformed GRPO by 6% on average (up to 20%) with up to 35x fewer rollouts,
and beat MIPROv2 by more than 10% (S19, `verified`). ACE treats context as an
evolving playbook with generation, reflection, and curation, avoiding brevity
bias and context collapse; it reports +10.6% on agents and +8.6% on finance
(S22, `verified`).

Consequence: a small, well-labelled eval set is now an asset that can drive
semi-automated prompt improvement. The library's structural gates are
necessary but not sufficient; it needs paired outcome evals to feed this loop.

### 3.12 Skill anatomy and cache-aligned assembly

Anthropic's skill-authoring guide fixes the practical shape of the three-level
model: metadata is about 100 words and is always in context; the `SKILL.md`
body should stay under 500 lines; bundled references can be unlimited and are
read only when the body points at them. It also states that models currently
under-trigger skills, so descriptions should state the triggering contexts
explicitly rather than stay minimal (S25, `verified`).

Prompt caching adds an assembly constraint. A cache breakpoint must sit on the
last block that is identical across requests; if the breakpoint covers a
timestamp or per-request context, the prefix hash never matches and every
request pays a cache write instead of a read. The default TTL is five minutes,
with a one-hour option at a higher write price; changing `tool_choice` or
adding/removing images invalidates the message cache (S26, `verified`).

Consequence: keep the static system prompt free of per-request interpolation
and put dynamic task context in the user turn. A skill loaded on demand should
be a separate message or tool result, not concatenated into the cached prefix;
otherwise every distinct skill selection invalidates the base prompt cache.
Cache benefits are workload-dependent (a five-minute TTL only helps back-to-back
turns), so treat hit rate as a measured metric, not an assumption (`likely`).

## 4. Contradictions and limits

- AGENTS.md evidence is not a single effect: +4% success and +20% to +23%
  inference cost in one study, -28.64% runtime in another. The metrics differ
  (success, cost, runtime), the corpora differ, and no study isolates file
  length.
  The defensible synthesis is "repo-specific operational facts can improve
  efficiency; generic prose adds cost without a reliable success gain"
  (`likely`).
- SkillsBench reports an average gain but a wide per-configuration range. A
  skill that helps one model/harness can be neutral or harmful in another
  (`verified` for the range; `likely` for the transfer).
- Subagent gains are model- and harness-dependent. MS-Eval found some
  closed-source configurations got higher cost and degraded performance
  (S12, `verified`). Anthropic's 90.2% is an internal research eval, not a
  coding benchmark (S6, `verified`).
- Several sources are vendor engineering posts, not peer-reviewed studies.
  They are used for mechanism and operational detail, not as effect-size
  estimates for this repository.
- The 2026 instruction-capacity replication uses keyword inclusion as a proxy
  for instruction following. It measures density tolerance, not reasoning
  quality (S2, `verified` as a proxy; `likely` as a general capability claim).
- No source here evaluates this repository's exact prompts. Every implication
  below is a hypothesis to test on this library's own eval set.

## 5. Implications for this library

| ID | Implication | Evidence | Audit gap |
|---|---|---|---|
| I-01 | Keep the element budget; add a model-tier calibration record instead of relaxing it globally. | S1, S2 | G-05 |
| I-02 | Add hard gates for delegation: write isolation and specifiability; require positive gates for breadth, context volume, verification, or economics. | S6, S8, S9, S11, S12 | G-01 |
| I-03 | Make clean-context verification explicit: generator and verifier must not share the author's reasoning context. | S8, S9 | G-01 |
| I-04 | Keep writes single-threaded; parallelize reads, search, and review only. | S7, S8, S11 | G-01 |
| I-05 | Treat the repository context file as a short router; move procedures to skills and invariants to gates. | S13, S14, S15 | G-02 |
| I-06 | Measure skill efficacy against a paired no-skill baseline, not only structure and routing. | S10, S17 | G-04 |
| I-07 | Cap skill shape: focused body, at most three modules, deep material in references. | S10, S17 | G-08 |
| I-08 | Enforce the advisory token guardrail or record a justified exemption for every overage. | S3, S4, S5 | G-03 |
| I-09 | Test doctrine-light variants for single-phase roles; do not assume the full six-phase procedure helps every model. | S20 | G-06 |
| I-10 | Put the injection guard early as well as in the conduct block, or test moving conduct earlier. | S5, S18 | G-09 |
| I-11 | Record model, harness, and seed on every eval result; re-baseline on model or harness change. | S16, S18 | G-10 |
| I-12 | Use the eval set as the input to reflective prompt optimization (GEPA/ACE-style), not ad hoc edits. | S19, S22 | G-11 |
| I-13 | Add cheap candidate experiments (prompt repetition for non-reasoning paths) behind an A/B, never as a default. | S21 | G-11 |
| I-14 | Keep the existing anti-drift machinery: byte-exact fragments, version fields, provenance records. The evidence supports it. | S18, S16 | -- |

## 6. Source URLs

- S1: https://arxiv.org/abs/2507.11538
- S2: https://arize.com/blog/llm-instruction-following-benchmark-2026/
- S3: https://research.trychroma.com/context-rot
- S4: https://arxiv.org/abs/2510.05381
- S5: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- S6: https://www.anthropic.com/engineering/multi-agent-research-system
- S7: https://cognition.com/blog/dont-build-multi-agents
- S8: https://cognition.com/blog/multi-agents-working
- S9: https://arxiv.org/abs/2503.13657
- S10: https://arxiv.org/abs/2602.12670
- S11: https://arxiv.org/abs/2610.10263
- S12: https://arxiv.org/abs/2610.22869
- S13: https://arxiv.org/abs/2602.11988
- S14: https://arxiv.org/abs/2601.20404
- S15: https://arxiv.org/abs/2511.12884
- S16: https://arxiv.org/abs/2605.23950
- S17: https://arxiv.org/abs/2609.35692
- S18: https://arxiv.org/abs/2609.31575
- S19: https://arxiv.org/abs/2507.19457
- S20: https://arxiv.org/abs/2510.22251
- S21: https://arxiv.org/abs/2512.14982
- S22: https://arxiv.org/abs/2510.04618
- S23: https://agents.md/
- S24: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- S25: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- S26: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
