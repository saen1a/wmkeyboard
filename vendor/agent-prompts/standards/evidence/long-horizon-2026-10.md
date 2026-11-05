# Long-horizon agent research register (2026-10)

Status: evidence record for `standards/long-horizon-runs.md` (LH-01..LH-13; LH-14 is an engineering pattern, not a benchmark claim) and
`docs/knowledge-base/long-horizon-agents-2026-10.md`.

Access date: 2026-10-25.

Method: primary pages and papers were fetched during this run; the sections
carrying the numbers were read. No claim is taken from model memory. Vendor
engineering posts are labelled as vendor posts; preprints are labelled as
preprints and are not treated as replicated results.

Claim labels (local to this register; they are not the repo-wide run-evidence
labels `verified` / `likely` / `unverified`):

- `stated` -- the fetched source states the claim. It does not mean the result
  was independently replicated.
- `likely` -- secondary source, partial evidence, or a reasonable inference
  across sources.
- `unverified` -- not confirmed; kept only to name an open question.

## 1. What the evidence says

1. **Task length is growing, but reliability is the binding constraint.** The
   frontier 50% time horizon is measured in hours; the same page warns that
   measurements above 16 hours are unreliable with the current task suite, and
   that real work is messier than the self-contained benchmark tasks (L1).
2. **A single context window is the wrong unit of work.** Long-running agents
   work in discrete sessions with no memory of the previous session; the
   successful pattern is an initializer that writes the environment, a feature
   list, a progress file, and one feature per session with a commit (L2).
3. **Context is a finite attention budget.** Compaction, structured
   note-taking, and sub-agents are the three long-horizon strategies; compaction
   must preserve architectural decisions, unresolved bugs, and implementation
   details, and may drop raw tool output (L3).
4. **Budget alone does not buy horizon.** On an ultra-long benchmark, simple
   scaling failed; agents failed through "in-context locking" and weak
   memory/plan management (L4).
5. **Partial progress is the normal shape.** A long-horizon terminal benchmark
   grades partial progress because tasks take hundreds of episodes and hours;
   the best tested model reached 15.2% at a 0.95 partial-reward threshold (L5).
6. **Checkpointed data is not durable execution.** A checkpoint preserves data;
   something must still detect failure, re-enter the run, and resume it. Durable
   execution retries the failed step and can bound history with
   continue-as-new (L6).
7. **Internal state drifts from real state.** State drift is a distinct failure
   mode: the agent's textual state diverges from the environment while local
   reasoning still looks coherent (L7). Goal drift is measurable under
   competing objectives (L8).
8. **Long contexts degrade recall even when retrieval works.** Context rot and
   length-induced degradation are already recorded in the prompt register
   (L9); the long-horizon response is external state, not a larger window.
9. **Long-horizon scale is large.** A 2026 benchmark report describes runs
   averaging 27M tokens with a best score of 26%, and grades the whole
   trajectory rather than one answer (L10). Treat this as a directional vendor
   report, not a replicated result.
10. **Concurrency is a long-horizon lever with a write tax.** Dynamic
    concurrency helps long-horizon coding tasks but concurrent writes remain a
    distinct failure category (L11); the library already forbids parallel
    writers (SD-02).

## 2. Source register

| ID | Source | Type | Key result used here | Label |
|---|---|---|---|---|
| L1 | METR, "Task-Completion Time Horizons of Frontier AI Models", page updated 2026-09-08; paper arXiv 2503.14499 | measurement program + paper | 50%/80% horizons from a logistic fit over 100+ software/ML/cyber tasks; tasks are self-contained, well-specified, automatically scored; measurements above 16 h are unreliable with the current suite; agents score lower on holistic grading and on messier tasks | stated |
| L2 | Anthropic, "Effective harnesses for long-running agents", 2025-11-26 | vendor engineering | two-part harness: initializer writes `init.sh`, `claude-progress.txt`, `feature_list.json`, initial commit; each later session makes one feature of progress and leaves a clean state; failure modes: one-shotting, premature victory, and marking features done without end-to-end testing; JSON feature lists resist inappropriate edits better than Markdown | stated |
| L3 | Anthropic, "Effective context engineering for AI agents", 2025-09-29 | vendor engineering | context is a finite attention budget; long-horizon strategies are compaction, structured note-taking, and sub-agents; compaction preserves architectural decisions, unresolved bugs, and implementation details while dropping redundant tool output; sub-agents return 1,000-2,000 token summaries | stated |
| L4 | Luo et al., "UltraHorizon: Benchmarking Agent Capabilities in Ultra Long-Horizon Scenarios", arXiv 2509.21766, 2025 | preprint / benchmark | heaviest setting averages 200k+ tokens and 400+ tool calls, standard settings exceed 35k tokens and 60 tool calls; human participants score higher; simple scaling fails; eight error types attributed to "in-context locking" and capability gaps | stated |
| L5 | Li et al., "Long-Horizon-Terminal-Bench: Testing the Limits of Agents on Long-Horizon Terminal Tasks with Dense Reward-Based Grading", arXiv 2607.08964 v3, 2026 | preprint / benchmark | 46 tasks across nine categories; agents consume 9.9M tokens, 231 episodes, and 85.3 minutes per task on average; tasks stress long-horizon planning, long-context management, and iterative debugging; best model 15.2% pass@1 at a 0.95 partial-reward threshold, 10.9% at perfect reward, mean 4.3% / 1.7% | stated |
| L6 | Temporal, "LangGraph in production: Temporal's LangGraph Plugin adds Durable Execution", 2026-07-16 | vendor engineering | a checkpoint preserves data, not execution; a single-process run dies with the process; durable execution retries the failed step and resumes from durable state; continue-as-new bounds history for runs that last weeks or months; durable human waits cost nothing | stated |
| L7 | Singh, "State Drift in Language-Conditioned Autonomous Agents: A Failure Mode of Long-Horizon Reasoning", Preprints, doi 10.20944/preprints202601.0910.v1, 2026-01 | preprint | state drift is persistent divergence between the agent's internal textual state and the true environment state; it can persist while local reasoning steps remain coherent | stated |
| L8 | "Technical Report: Evaluating Goal Drift in Language Model Agents", arXiv 2505.02709, 2025 | preprint | goal drift is formalized and measured under competing objectives; the best scaffold held near-perfect adherence past 100k tokens in the hardest setting | stated |
| L9 | Chroma, "Context Rot", 2025; "Context Length Alone Hurts LLM Performance Despite Perfect Retrieval", arXiv 2510.05381, 2025 | vendor research + preprint | recall and reasoning degrade as input length grows, even when retrieval is perfect and distractors are removed; already recorded as S3/S4 in `prompt-research-2026-10.md` | stated |
| L10 | Arize, "Long-horizon agent benchmarks are fragmenting: a field guide to what each one actually measures", 2026 | vendor blog | SWE-Marathon runs average 27M tokens and peak near 877M; the best reported agent solves 26%; grading covers the whole trajectory; deterministic milestone checks are preferred where possible | likely |
| L11 | "When Sub-Agents Work in Parallel: The Promises and Pitfalls of Dynamic Concurrency in Long-Horizon Coding Tasks", arXiv 2610.10263, 2026 | preprint | 354 tasks, 2,124 executions; concurrency helps long-horizon tasks and is neutral or negative on bounded tasks; concurrent writes are a distinct failure category (26.5% of instances; 62.9% for one harness); already recorded as S11 | stated |

## 3. What this does and does not establish

- It establishes a design direction: external durable state, one unit at a
  time, checkpoint/resume, explicit budgets, progress and drift checks, and
  verification per unit and at the end.
- It does not establish a specific prompt wording, checkpoint cadence, or
  numeric budget. Those are design choices; the library marks them as defaults,
  not findings.
- It does not establish that the workflow loop improves long-horizon outcomes.
  That requires a deployed harness and a pre-registered run, which is deferred.
- Single-model, single-task, and vendor-reported results are not generalized
  here. Every rule in `long-horizon-runs.md` that depends on a number cites the
  source and keeps the number out of the normative text.
- `stated` is not replication. L2, L3, L6, and L10 are vendor publications;
  L9 combines vendor research with a preprint; L1 is a measurement program and
  paper; L4, L5, L7, L8, and L11 are preprints or benchmark reports.

## 4. Source URLs

| ID | URL |
|---|---|
| L1 | https://metr.org/time-horizons/ ; https://arxiv.org/abs/2503.14499 |
| L2 | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| L3 | https://www.anthropic.com/research/effective-context-engineering-for-ai-agents |
| L4 | https://arxiv.org/abs/2509.21766 |
| L5 | https://arxiv.org/abs/2607.08964 |
| L6 | https://temporal.io/blog/temporal-langgraph-plugin-durable-execution |
| L7 | https://doi.org/10.20944/preprints202601.0910.v1 |
| L8 | https://arxiv.org/abs/2505.02709 |
| L9 | https://research.trychroma.com/context-rot ; https://arxiv.org/abs/2510.05381 |
| L10 | https://arize.com/blog/long-horizon-agent-benchmarks-field-guide |
| L11 | https://arxiv.org/abs/2610.10263 |

Access date for every URL: 2026-10-25. L7 is a DOI landing page; the other
links are the primary pages or papers named in the table.
