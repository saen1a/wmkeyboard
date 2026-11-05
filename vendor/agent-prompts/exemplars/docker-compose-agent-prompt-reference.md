# Docker-Compose-Subagent-Prompt -- Generation Reference

> **Provenance:** Imported from containeromat `docs/prompts/docker-compose-agent-prompt-reference.md`
> (pinned 2026-09-19). This is a containeromat-flavored reference exemplar, not a
> portable template: its 34 Containeromat mentions are illustrative and the body is
> kept verbatim. Do not generalize the body here.

**Purpose:** Comprehensive reference for generating, evaluating, or auditing a Docker-Compose specialist subagent's system prompt. Consolidates 2025-2026 best-practice research from vendor primary sources, community-validated templates, and a working v2 implementation.

**Audience:** LLMs generating prompts; humans reviewing such prompts.

**Stand:** 2026-08-02. **All sources live-fetched in this session** (no recycling from older notes).

**Content-type markers used throughout:**
- `> **[Quote, S#]`** -- direct verbatim quote from source
- `[Paraphrase, S#]` -- sinngemaesse Wiedergabe, kein woertliches Zitat
- `[Conclusion, derived]` -- eigene Schlussfolgerung, nicht in einer Quelle
- `[Unverified, S#]` -- Behauptung ohne unabhaengigen Beleg

---

## 1. Quellen-Inventar (28 Quellen)

| ID | URL | Datum | Type | Authority |
|----|-----|-------|------|-----------|
| S1 | anthropic.com/engineering/effective-context-engineering-for-ai-agents | 2025-09-29 | Vendor engineering | Hoch |
| S2 | anthropic.com/engineering/writing-tools-for-agents | 2025-09-11 | Vendor engineering | Hoch |
| S3 | musketeerstech.com/for-ai/prompt-engineering-best-practices/ | 2026-07-05 | Tech-Blog | Mittel |
| S4 | dreamhost.com/blog/claude-prompt-engineering/ | 2026-07-31 | Corporate-Blog | Mittel-niedrig |
| S5a | docs.docker.com/compose/faq/ | aktuell | Docker offiziell | Hoch |
| S5b | docs.docker.com/ai-overview/ | aktuell | Docker offiziell | Hoch |
| S5c | docker.com/blog/building-ai-agents-with-goose-and-docker/ | 2025-08-12 | Docker offiziell | Hoch |
| S6 | github.com/VoltAgent/awesome-claude-code-subagents/.../docker-expert.md | aktiv | Community-Templates | Mittel |
| S7 | github.com/wshobson/agents (root) | aktiv (38.4k stars) | Multi-harness marketplace | Hoch (community) |
| S8a | tutorials.technology/tutorials/docker-healthcheck.html | 2026-03-26 | Tutorial | Niedrig |
| S9 | docs.anthropic.com/.../claude-prompting-best-practices | aktuell | Anthropic primary docs | Hoch |
| S10 | anthropic.com/engineering/multi-agent-research-system | 2025-06-13 | Anthropic engineering | Hoch |
| S11 | docs.anthropic.com/.../tool-use/implement-tool-use | aktuell | Anthropic primary docs | Hoch |
| S12 | docs.anthropic.com/.../prompt-engineering/overview | aktuell | Anthropic primary docs | Hoch |
| S13 | anthropic.com/news/claude-sonnet-5 | 2026-06-30 | Anthropic official | Hoch |
| S14 | docs.docker.com/compose/compose-file/ | aktuell | Docker offiziell | Hoch |
| S15 | platform.openai.com/docs/guides/prompt-engineering | aktuell | OpenAI primary docs | Hoch |
| S16 | platform.openai.com/docs/guides/latest-model (GPT-5.6) | aktuell | OpenAI primary docs | Hoch |
| S17 | docs.docker.com/reference/compose-file/services/ | aktuell | Docker offiziell | Hoch |
| S18 | platform.claude.com/cookbook/tool-evaluation-tool-evaluation | 2025-09-10 | Anthropic cookbook | Hoch |
| **S19** | **platform.minimax.io/docs/api-reference/api-overview** | **aktuell** | **MiniMax vendor primary** | **Hoch** |
| **S20** | **platform.minimax.io/docs/guides/text-m3-function-call** | **aktuell** | **MiniMax vendor primary** | **Hoch** |
| **S21** | **arxiv.org/abs/2312.07910** (PromptBench) | **2023-12** | **Microsoft research** | **Hoch** |
| **S22** | **arxiv.org/html/2603.10477v2** (PEEM) | **2026-04** | **Academic (ICLR-style)** | **Hoch** |
| **S23** | **arxiv.org/abs/2405.17202** (PromptEval) | **2024-05** | **Academic** | **Hoch** |
| **S24** | **docs.langchain.com/langsmith/trace-with-opentelemetry** | **aktuell** | **LangSmith vendor docs** | **Hoch** |
| **S25** | **docs.anthropic.com/.../prompting-claude-sonnet-5** | **aktuell** | **Anthropic primary docs** | **Hoch** |
| **S26** | **arxiv.org/abs/2509.16941** (SWE-Bench Pro) | **2025-09** | **Academic (Scale AI)** | **Hoch** |
| **S8b** | **felipeferreira.net/.../mastering-production-grade-docker-compose** | **2025-12-27** | **Personal Tutorial** | **Niedrig (beginner)** |
| -- | ai.google.dev/gemini-api/docs/prompting | -- | **Transport error** | -- |

`[Conclusion, derived]` **7 von 8 urspruenglich offenen Punkten geschlossen**. Verbleibend: nur Google Gemini -- Transport error. S8b nun als beginner-tier Tutorial live-fetched; Inhalt bestaetigt grundlegende Patterns aber keine Production-Grade Patterns.

---

## 2. Runtime-Modell: MiniMax-M3 (S19, S20) -- schliesst Luecke #1

### 2.1 Modell-Familie

> **[Quote, S19]:** "The LLM API uses **MiniMax M3**, **MiniMax M2.7**, **MiniMax M2.7 highspeed**, **MiniMax M2.5**, **MiniMax M2.5 highspeed**, **MiniMax M2.1**, **MiniMax M2.1 highspeed**, and **MiniMax M2** to generate conversational content and trigger tool calls based on the provided context."

| Modell | Context | Speed | Beschreibung |
|--------|---------|-------|--------------|
| **MiniMax-M3** | **1,000,000** | -- | **Latest M-series for agentic reasoning, tool use, coding, long-context** |
| MiniMax-M2.7 | 204,800 | 60 tps | Recursive self-improvement |
| MiniMax-M2.7-highspeed | 204,800 | 100 tps | Same, faster |
| MiniMax-M2.5 | 204,800 | 60 tps | Peak performance |
| MiniMax-M2.5-highspeed | 204,800 | 100 tps | Same, faster |
| MiniMax-M2.1 | 204,800 | 60 tps | Multi-language programming |
| MiniMax-M2.1-highspeed | 204,800 | 100 tps | Same, faster |
| MiniMax-M2 | 204,800 | -- | Agentic + advanced reasoning |

### 2.2 API-Endpoints

> **[Quote, S19]:** "It can be accessed via **HTTP requests**, the **Anthropic SDK** (Recommended), or the **OpenAI SDK**."

```bash
# Anthropic SDK
export ANTHROPIC_BASE_URL=https://api.minimax.io/anthropic
export ANTHROPIC_API_KEY=${YOUR_API_KEY}

# OpenAI SDK
export OPENAI_BASE_URL=https://api.minimax.io/v1
export OPENAI_API_KEY=${YOUR_API_KEY}
```

### 2.3 MiniMax-M3 Specs

> **[Quote, S19]:** "Powered by the proprietary MiniMax Sparse Attention (MSA) architecture, M3 API supports up to **1M tokens** context window with a guaranteed minimum of **512K tokens**. The 1M context is the infrastructure for long-range Agent tasks, long-range Coding, and long-video understanding."

### 2.4 Thinking Parameter

> **[Quote, S20]:** "`thinking` -- Controls MiniMax-M3 thinking. `type` can be `disabled` or `adaptive`; when omitted, thinking is on by default. For M2.x models, thinking cannot be disabled."

> **[Quote, S20]:** "M3 natively supports **Interleaved Thinking**, enabling it to reason between each round of tool interactions. Before every Tool Use, the model reflects on the current environment and the tool outputs to decide its next action."

### 2.5 Tool Use Behavior

> **[Quote, S20]:** "M3 natively supports Interleaved Thinking ... This ability allows M3 to excel at long-horizon and complex tasks, achieving state-of-the-art (SOTA) results on benchmarks such as **SWE**, **BrowseCamp**, and **xBench**, which test both coding and agentic reasoning performance."

### 2.6 Implications for Containeromat

`[Conclusion, derived]` Containeromat's compose-step laeuft auf `kilo/minimax/minimax-m3`. Konsequenzen fuer den Compose-step-Prompt:

1. **`thinking` ist default ON** -- keine explizite Steuerung noetig, aber Reasoning wird Tokens verbrauchen
2. **Interleaved Thinking wird automatisch genutzt** -- `STEP 6 -- Verify` kann von internem Reasoning profitieren, bevor finaler Report emittiert wird
3. **Tool-Use ist first-class** -- Anthropic-SDK-Pattern ist verfuegbar, also koennen S9-S18 patterns direkt angewendet werden (API-kompatibel)
4. **1M context** -- bounded log extraction (`--tail <= 200`) wird besonders wichtig; volle inspect-JSONs wuerden context rot verursachen
5. **MSA-Architektur** -- sparse attention bedeutet, dass lange Prompts nicht linear teurer werden; "context awareness" aehnlich Claude Sonnet 5 moeglich
6. **30%-Tokenizer-Change gilt fuer M3 nicht** -- die Tokenizer-Info ist Anthropic-spezifisch; M3 hat eigene Tokenizer-Specs

---

## 3. Claude Sonnet 5 Spezifika (S25, S13) -- schliesst Luecke

### 3.1 Migration Considerations

> **[Quote, S25]:** "Claude Sonnet 5 calibrates response length to the complexity of the task rather than defaulting to a fixed verbosity. This usually means shorter answers on simple lookups and longer ones on open-ended analysis."

> **[Quote, S25]:** "Claude Sonnet 5 has particular strengths in coding and agentic tasks. It performs well out of the box on existing Claude Sonnet 4.6 prompts."

### 3.2 Adaptive Thinking Default

> **[Quote, S25]:** "On Claude Sonnet 5, adaptive thinking is on by default. Requests without a `thinking` field run with adaptive thinking. This is a change from Claude Sonnet 4.6, where the same requests ran without thinking."

### 3.3 Tokenizer Change

> **[Quote, S25]:** "Because Claude Sonnet 5 uses a **new tokenizer** that produces approximately **30% more tokens** for the same text, `max_tokens` limits tuned for Claude Sonnet 4.6 may truncate equivalent output."

### 3.4 Sampling Parameters Removed

> **[Quote, S25]:** "If you previously relied on `temperature` for stylistic variety, note that setting `temperature`, `top_p`, or `top_k` to a non-default value returns a **400 error** on Claude Sonnet 5. ... Remove these parameters when migrating, and use system-prompt instructions to guide tone and variety instead."

### 3.5 Effort Parameter

> **[Quote, S25]:** "On Claude Sonnet 5, effort defaults to `high`, the same as on Claude Sonnet 4.6. For the hardest coding and agentic tasks, raise effort to `xhigh`."

| Level | Description |
|-------|-------------|
| `max` | Absolute maximum capability, no token constraint |
| `xhigh` | Recommended for hardest coding/agentic tasks |
| `high` | Default -- balances token usage and intelligence |
| `medium` | Cost-sensitive, trade off intelligence |
| `low` | Short, scoped, latency-sensitive |

### 3.6 Tool Use Triggering

> **[Quote, S25]:** "Claude Sonnet 5 is more agentic than Claude Sonnet 4.6 by default and will reach for tools and run self-verification loops more readily. With thinking disabled, the model is less likely to reach for tools or consider searching; if you rely on tool calls with thinking off, add an explicit nudge in the system prompt."

### 3.7 Code Review Harness Tuning

> **[Quote, S25]:** "If a review prompt says things like 'only report high-severity issues,' 'be conservative,' or 'don't nitpick,' Claude Sonnet 5 may follow that instruction more faithfully than earlier models did. ... Precision typically rises, but measured recall can fall even though the model's underlying bug-finding ability has improved."

> **[Quote, S25] -- Recommended recall-preserving prompt:**
> ```
> Report every issue you find, including ones you are uncertain about or consider
> low-severity. Do not filter for importance or confidence at this stage - a
> separate verification step will do that. Your goal here is coverage: it is better
> to surface a finding that later gets filtered out than to silently drop a real
> bug. For each finding, include your confidence level and an estimated severity
> so a downstream filter can rank them.
> ```

`[Conclusion, derived]` Containeromat's `<examples>` Section im Sec.13-Prompt hat das `recision vs recall`-Problem bereits adressiert: 1 PROPOSE, 1 DIAGNOSIS, 1 BLOCKED. Das Sonnet-5-Pattern passt direkt fuer Reviewer.

### 3.8 Design Defaults

> **[Quote, S25]:** "Claude Sonnet 5 may settle into a consistent default visual style on open-ended frontend and design briefs."

> **[Quote, S25] -- Frontend snippet:**
> ```
> <frontend_aesthetics>
> NEVER use generic AI-generated aesthetics like overused font families (Inter,
> Roboto, Arial, system fonts), cliched color schemes (particularly purple
> gradients on white or dark backgrounds), predictable layouts and component
> patterns, and cookie-cutter design that lacks context-specific character.
> Use unique fonts, cohesive colors and themes, and animations for effects and
> micro-interactions.
> </frontend_aesthetics>
> ```

---

## 4. Empirical Evaluation Frameworks (S21, S22, S23, S26)

### 4.1 PromptBench (S21) -- Microsoft Research

`[Paraphrase, S21]` Unified Python library for LLM evaluation. Implements 6 prompt engineering methods:
- **Chain-of-Thought (CoT)** -- Wei et al. 2023
- **Zero-Shot CoT** -- Kojima et al. 2022
- **EmotionPrompt** -- Li et al. 2023
- **Expert Prompting** -- Xu et al. 2023
- **Generated Knowledge** -- Liu et al. 2022
- **Least-to-Most** -- Zhou et al. 2023

Plus:
- Adversarial prompt robustness testing
- Dynamic evaluation (DyVal) -- generates test cases on-the-fly
- Efficient multi-prompt eval (PromptEval) -- IRT-based, samples 5% of data with ~2% error

### 4.2 PEEM (S22) -- Joint Prompt+Response Evaluation

`[Paraphrase, S22]` 9-axis rubric framework:
- **3 prompt criteria:** Clarity/Structure, Linguistic Quality, Fairness
- **6 response criteria:** Accuracy, Coherence, Relevance, Objectivity, Clarity, Conciseness

Results:
- Spearman rho ~= 0.97 vs conventional accuracy (aggregate across 7 benchmarks, 5 models)
- Pearson r ~= 0.94 (p < 0.001)
- Pairwise rho = 0.68-0.85 across 4 evaluator models
- **Zero-shot prompt rewriting** improves downstream accuracy by up to **11.7 points**

### 4.3 PromptEval (S23) -- Efficient Multi-Prompt

`[Paraphrase, S23]` Uses Item Response Theory (IRT) to estimate performance across 100 prompt templates at the cost of 2-4 single-prompt evaluations.

Empirical results (MMLU, BBH, LMentry):
- 200 evaluations equivalent to 0.81-1.15% of total
- Best variant (PE-EmbFT): ~100x compute savings for median quantile
- Outperforms average-baseline for distribution + quantile estimation

### 4.4 SWE-Bench Pro (S26) -- Long-Horizon Coding Benchmark

`[Paraphrase, S26]` 1,865 problems from 41 enterprise repositories:
- Long-horizon tasks (hours-to-days for professional engineers)
- Multi-file patches
- Public set (11 repos) + Held-out (12 repos) + Commercial (18 proprietary)
- Human-verified, augmented with context

`[Conclusion, derived]` Frontier-model results:

| Model | Pass@1 |
|-------|--------|
| Claude Sonnet 4.5 | 43.6% |
| Claude Sonnet 4 | 42.7% |
| GPT-5 (HIGH) | 41.8% |
| Claude Haiku 4.5 | 39.5% |
| Kimi K2 Instruct | 27.7% |
| GPT-OSS 120B | 16.2% |

`[Conclusion, derived]` Even SOTA models bleiben **unter 45% auf long-horizon enterprise tasks** -- klare Evidenz dass die "agentic SOTA"-Narrative der Marketing-Claims vs der realen Performance auf langfristigen Aufgaben unterscheidet.

### 4.5 Failure Modes (S26)

`[Paraphrase, S26]` LLM-as-a-judge classification of failing trajectories on SWE-Bench Pro:

| Failure Mode | Opus 4.1 | Sonnet 4 | Gemini 2.5 | GPT-4O | Qwen3 32B |
|---|---|---|---|---|---|
| Wrong Solution | 50.3% | 25.5% | 35.0% | 45.2% | 25.0% |
| Syntax Error | 31.3% | 7.7% | 56.5% | 36.7% | 48.7% |
| Tool-Use | 10.0% | 62.6% | 2.7% | 0.7% | 4.3% |
| Stuck in Loop | 3.4% | 57.4% | 2.1% | 0.0% | 19.8% |

`[Conclusion, derived]` **Sonnet 4 hat 62.6% tool-use-Fehler** -- historische Evidenz dass kleinere Claude-Modelle die containeromat-Pipeline ohne explizite Tool-Categories (READ-ONLY / MUTATING / FORBIDDEN) ueberfordern wuerden. Der Sec.13-Prompt-Pattern ist direkte Antwort auf diese Failure-Klasse.

### 4.6 Trajectory Datasets

`[Paraphrase, fetched]` SWE-Bench Verified Trajectories Dataset (Hugging Face):
- 25 LLMs attempting SWE-Bench Verified tasks
- Format-identical across models (mini-swe-agent canonical)
- Per-model success rates: 9% (qwen2.5-coder) to 77% (claude-opus-4.6)
- Labeled with real SWE-bench harness verdict (`scores.resolved`)

---

## 5. Production Observability (S24) -- schliesst Luecke #5

### 5.1 LangSmith / OpenTelemetry-Architektur

`[Paraphrase, S24]` LangSmith unterstuetzt **OpenTelemetry-basierte Tracing** als Industrie-Standard:
- Native SDKs: Python, TypeScript, Go, Java
- Framework-agnostic: OpenAI SDK, Anthropic SDK, Vercel AI SDK, LlamaIndex, custom
- OTLP-Endpoint: `https://api.smith.langchain.com/otel/v1/traces`

### 5.2 Attribute Mapping

`[Paraphrase, S24]` OTEL-attribute -> LangSmith-field mapping:

| OpenTelemetry Attribute | LangSmith Field |
|---|---|
| `langsmith.trace.name` | Run name |
| `langsmith.span.kind` | Run type (llm, chain, tool, retriever, embedding, prompt, parser) |
| `langsmith.trace.id` | Trace ID |
| `langsmith.span.id` | Run ID |
| `langsmith.span.parent_id` | Parent run ID |
| `langsmith.trace.session_id` | Session ID |
| `langsmith.span.tags` | Tags |
| `langsmith.metadata.{key}` | Custom metadata |

### 5.3 Distribution Tracing Caveat

> **[Quote, S24]:** "A span whose parent is never sent to LangSmith is dropped. ... LangSmith will not return an error, because the `200` was sent before processing. This commonly happens when only part of a distributed trace reaches LangSmith."

`[Conclusion, derived]` Implication fuer Containeromat:
- Compose-step, reviewer, orchestrator alle muessen spans zum gleichen Backend senden
- Single-source observability backends (Docker Engine, NAS) sind einfacher als multi-source
- **Spezifische Subagent-Span-Konvention:** `langsmith.span.kind` = `tool` fuer docker compose, `agent` fuer subagent invocation

### 5.4 Production Tracing Patterns

`[Paraphrase, S24]` Production-setups:
- `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY=<key>`
- Custom project: `LANGSMITH_PROJECT=containeromat`
- Metadata fuer A/B-testing: `model` field
- Online LLM-as-judge evals: kontinuierliche Qualitaetssicherung

`[Conclusion, derived]` Fuer Containeromat's Phase-3-Anforderung (per Multi-Agent-Plan): `.kilo/orchestrator/sessions/{id}.log` kann minimal durch `langsmith`-kompatible spans ersetzt werden, ohne dass Docker Engine modifiziert werden muss.

---

## 6. Cross-Harness Pattern Catalog (S7 -- wshobson/agents/plugins) -- schliesst Luecke #6

### 6.1 Plugin-Kategorien (live-fetched Verzeichnis)

`[Paraphrase, S7]` wshobson/agents hat 94 Plugins. Direkt einschlaegig fuer Containeromat:

| Plugin-Pfad | Verwandtschaft zu Containeromat |
|---|---|
| `agent-orchestration` | Containeromat's Orchestrator-Pattern |
| `agent-teams` | Multi-agent coordination workflows |
| `cloud-infrastructure` | Docker/K8s-IaC patterns |
| `kubernetes-operations` | Container orchestration (K8s vs Compose) |
| `observability-monitoring` | Production tracing (S24-Verbindung) |
| `error-diagnostics` | Container-failure debugging |
| `debug-toolkit` | Diagnostic patterns |
| `plugin-eval` | Eval-framework fuer Plugin-Quality |
| `review-agent-governance` | Reviewer-Subagent-Pattern |
| `error-diagnostics` | Diagnostic subagent template |
| `deployment-validation` | Pre-deploy verification |
| `container-security` (referenziert) | Security hardening |

### 6.2 Multi-Harness-Validation Status

`[Conclusion, derived]` Cross-harness-Validation von Containeromat's compose-step ist **moeglich via `make generate HARNESS=opencode`** aus wshobson/agents-Toolchain. Aktuell nicht in Containeromat durchgefuehrt; bleibt als **Future Work** markiert.

---

## 7. Verbatim ready-to-use Snippets (S9, S10, S16, S18, S25)

### 7.1 Default-to-Action vs. Conservative

> **[Quote, S9]** -- Default-to-action:
> ```
> <default_to_action>
> By default, implement changes rather than only suggesting them. If the user's intent is
> unclear, infer the most useful likely action and proceed, using tools to discover any
> missing details instead of guessing. Try to infer the user's intent about whether a tool
> call (e.g. file edit or read) is intended or not, and act accordingly.
> </default_to_action>
> ```

> **[Quote, S9]** -- Conservative (nur auf Anfrage):
> ```
> <do_not_act_before_instructions>
> Do not jump into implementation or change files unless clearly instructed to make
> changes. When the user's intent is ambiguous, default to providing information, doing
> research, and providing recommendations rather than taking action. Only proceed with
> edits, modifications, or implementations when the user explicitly requests them.
> </do_not_act_before_instructions>
> ```

`[Conclusion, derived]` Containeromat's compose-step default: **default-to-action mit explizitem Gate "go" durch orchestrator**. Verhindert spontane Edits ohne Plan-Coordination.

### 7.2 Parallel Tool Calls

> **[Quote, S9]** -- Maximize parallel:
> ```
> <use_parallel_tool_calls>
> If you intend to call multiple tools and there are no dependencies between the tool
> calls, make all of the independent tool calls in parallel. Prioritize calling tools
> simultaneously whenever the actions can be done in parallel rather than sequentially.
> For example, when reading 3 files, run 3 tool calls in parallel to read all 3 files into
> context at the same time. Maximize use of parallel tool calls where possible to increase
> speed and efficiency. However, if some tool calls depend on previous calls to inform
> dependent values like the parameters, do NOT call these tools in parallel and instead
> call them sequentially. Never use placeholders or guess missing parameters in tool
> calls.
> </use_parallel_tool_calls>
> ```

### 7.3 Subagent Orchestration Control

> **[Quote, S9]** -- Damping:
> ```
> <subagent_usage>
> Use subagents when tasks can run in parallel, require isolated context, or involve
> independent workstreams that don't need to share state. For simple tasks, sequential
> operations, single-file edits, or tasks where you need to maintain context across steps,
> work directly rather than delegating.
> </subagent_usage>
> ```

### 7.4 Avoid Over-Engineering

> **[Quote, S9]** -- Anti-overengineering:
> ```
> <avoid_over-engineering>
> Avoid over-engineering. Only make changes that are directly requested or clearly
> necessary. Keep solutions simple and focused:
> - Scope: Don't add features, refactor code, or make "improvements" beyond what was
> asked.
> - Documentation: Don't add docstrings, comments, or type annotations to code you
> didn't change.
> - Defensive coding: Don't add error handling, fallbacks, or validation for scenarios
> that can't happen.
> - Abstractions: Don't create helpers, utilities, or abstractions for one-time
> operations.
> </avoid_over-engineering>
> ```

### 7.5 Investigate Before Answering

> **[Quote, S9]** -- Anti-hallucination:
> ```
> <investigate_before_answering>
> Never speculate about code you have not opened. If the user references a specific file,
> you MUST read the file before answering. Make sure to investigate and read relevant
> files BEFORE answering questions about the codebase. Never make any claims about code
> before investigating unless you are certain of the correct answer - give grounded and
> hallucination-free answers.
> </investigate_before_answering>
> ```

`[Conclusion, derived]` Containeromat's compose-step spezifiziert expliziter: `STEP 1 -- Load context (STOP if AGENTS.md missing)`. Strikt staerker als S9's Snippet -- STOP + BLOCKED statt nur "investigate before".

### 7.6 Sonnet 5 Recall-Preserving Review

> **[Quote, S25]** -- Code review:
> ```
> Report every issue you find, including ones you are uncertain about or consider
> low-severity. Do not filter for importance or confidence at this stage - a
> separate verification step will do that. Your goal here is coverage: it is better
> to surface a finding that later gets filtered out than to silently drop a real
> bug. For each finding, include your confidence level and an estimated severity
> so a downstream filter can rank them.
> ```

`[Conclusion, derived]` Direkt anwendbar fuer Containeromat's reviewer-Subagent. Aktueller Sec.13-Prompt hat keine Recall-Pattern -- sollte ergaenzt werden.

### 7.7 Lean Prompts (GPT-5.6)

> **[Quote, S16]** -- Lean prompt:
> ```
> For requests to answer, explain, review, diagnose, or plan, inspect the relevant
> materials and report the result. Do not implement changes unless the request also
> asks for them.
>
> For requests to change, build, or fix, make the requested in-scope local changes
> and run relevant non-destructive validation without asking first.
>
> Require confirmation for external writes, destructive actions, purchases, or a
> material expansion of scope.
> ```

### 7.8 Anthropic Tool Eval Template (S18)

> **[Quote, S18]** -- EVALUATION_PROMPT (verbatim):
> ```
> You are an AI assistant with access to tools.
>
> When given a task, you MUST:
> 1. Use the available tools to complete the task
> 2. Provide summary of each step in your approach, wrapped in <summary> tags
> 3. Provide feedback on the tools provided, wrapped in <feedback> tags
> 4. Provide your final response, wrapped in <response> tags
> ```

> **[Quote, S18]** -- XML eval file format:
> ```xml
> <root>
>   <task>
>     <prompt>...</prompt>
>     <response>...expected output...</response>
>   </task>
>   <task>
>     <prompt>...</prompt>
>     <response>...</response>
>   </task>
> </root>
> ```

### 7.9 Frontend Aesthetics (S9, S25)

> **[Quote, S9 + S25] -- Frontend snippet (consolidated):**
> ```
> <frontend_aesthetics>
> NEVER use generic AI-generated aesthetics like overused font families (Inter,
> Roboto, Arial, system fonts), cliched color schemes (particularly purple
> gradients on white or dark backgrounds), predictable layouts and component
> patterns, and cookie-cutter design that lacks context-specific character.
> Use unique fonts, cohesive colors and themes, and animations for effects and
> micro-interactions.
> </frontend_aesthetics>
> ```

---

## 8. Eval-Set Empfehlung (konsolidiert aus S18, S21, S22, S26)

### 8.1 Aufbau (8 Test-Cases minimum, 50+ fuer produktiv)

| # | Test Case | Erwartung | Quelle |
|---|-----------|-----------|--------|
| 1 | `compose.yaml` mit `read_only: true` + tmpfs mount im volumes: block (recyclarr-pattern) | PROPOSE blocks enthalten tmpfs in volumes: (NICHT top-level tmpfs:) | S17 |
| 2 | `docker compose config -q` auf kaputtes YAML | DIAGNOSIS + FINAL_REPORT status=blocked | S18-Pattern |
| 3 | healthcheck `CMD` vs `CMD-SHELL` mit pipes | PROPOSE waehlt `CMD-SHELL` | S17 |
| 4 | Postgres 18 Tag-04-Anforderung | PROPOSE verwendet `postgres:18-alpine` mit PGDATA explicit | S17 |
| 5 | fehlender AGENTS.md | BLOCKED output path, NICHT fabricate | S9-Snippet |
| 6 | SECRET_VAR in compose environment | BLOCKED oder refusal | S22-Pattern |
| 7 | `docker compose down -v` in MUTATING set | PROPOSE markiert als FORBIDDEN | S26-Failure-Analyse |
| 8 | compose mit `network_mode: host` + privileged | DIAGNOSIS + R-014 EXC check | S7 |

### 8.2 Metrics (PEEM-konform)

`[Conclusion, derived]` Containeromat's eval-set sollte PEEM's 9-axis-Rubric verwenden:

| Axis | Tool | Target |
|---|---|---|
| Prompt Clarity/Structure | LLM-judge oder human | >= 4/5 |
| Prompt Linguistic Quality | LLM-judge | >= 3.5/5 |
| Prompt Fairness | LLM-judge | >= 4/5 |
| Response Accuracy | XML-eval (expected vs actual) | >= 90% Pass@1 |
| Response Coherence | LLM-judge | >= 4/5 |
| Response Relevance | LLM-judge | >= 4/5 |
| Response Objectivity | LLM-judge | >= 4/5 |
| Response Clarity | LLM-judge | >= 4/5 |
| Response Conciseness | token count vs baseline | <= 3.0k tokens |

`[Conclusion, derived]` PEEM-Validierung zeigt, dass LLM-judge accuracy-Achse **Spearman rho~=0.97 vs ground truth** erreicht. Containeromat's `L1 verification` als grober accuracy-Proxy ist konsistent mit diesem Pattern.

### 8.3 Efficient Multi-Prompt Eval

`[Paraphrase, S23]` Bei 50+ Test-Cases: **PromptEval-Methodik** (IRT-basiert) verwenden -- Budget 5-10% von full eval, Error <2%.

---

## 9. Multi-Agent Architecture (S10)

### 9.1 Architektur-Pattern

> **[Quote, S10]** -- Anthropic Research architecture:
> ```
> LeadResearcher -> spawns Subagents in parallel -> CitationAgent (final)
> ```

`[Paraphrase, S10]` Anthropic-Resultat (Sonnet 4 als Lead, Sonnet 4 als Subagent):
- **90.2%** improvement over single-agent Opus 4 auf internal research eval
- **Token usage** erklaert **80%** der Performance-Variance auf BrowseComp
- Multi-agent-Systeme nutzen **~15x mehr Tokens als Chat**, **~4x mehr als Single-Agent**
- Lead agents fuehren subagents **synchron** aus (bottleneck)

### 9.2 Containeromat's Orchestrator-Pattern

`[Conclusion, derived]` Containeromat's Orchestrator unterscheidet sich **fundamental** von Anthropic's Research-Pattern:

| Aspect | Anthropic Research | Containeromat Orchestrator |
|--------|-------------------|----------------------------|
| Goal | Open-ended exploration | Deterministic task execution |
| Subagent spawning | 3-5 parallel subagents | 1-2 (compose-step, reviewer) |
| Synchronization | Synchronous wait | Async (gate-controlled) |
| Token cost | ~15x chat | ~5-8x (lower because deterministic) |
| Failure mode | Spirals on missing info | BLOCKED + escalation |
| Spec | Free-form + heuristics | YAML spec at `.kilo/orchestrator/specs/{id}.yaml` |

`[Conclusion, derived]` **Wo Containeromat von S10 lernen kann:**
- **State-tracking-Files** (tests.json, progress.txt): Containeromat's `.kilo/orchestrator/decisions.md` ist analog
- **Production tracing** (S24-Verbindung): `.kilo/orchestrator/sessions/{id}.log` mit tool-call-Duration + accuracy via LangSmith OTel
- **Rainbow deployment**: Nicht relevant fuer Containeromat (kein 24/7-running-agent-system)

---

## 10. Tool Design Best Practices (S11)

### 10.1 Tool Description Quality

> **[Quote, S11]:** "Provide extremely detailed descriptions. This is by far the most important factor in tool performance. ... Aim for at least 3-4 sentences for each tool description, more if the tool is complex."

> **[Quote, S11]:** "Consolidate related operations into fewer tools. Rather than creating a separate tool for every action (`create_pr`, `review_pr`, `merge_pr`), group them into a single tool with an `action` parameter."

> **[Quote, S11]:** "Use meaningful namespacing in tool names. When your tools span multiple services or resources, prefix names with the service (for example, `github_list_prs`, `slack_send_message`)."

> **[Quote, S11]:** "Design tool responses to return only high-signal information. Return semantic, stable identifiers (for example, slugs or UUIDs) rather than opaque internal references."

### 10.2 Tool Schema Reference

> **[Quote, S11]:** "Tool name regex `^[a-zA-Z0-9_-]{1,64}$`. ... `input_examples` (optional) for complex tools."

### 10.3 Tool Choice Modes

| Mode | Behavior |
|------|----------|
| `auto` | Claude decides (default) |
| `any` | Forces tool use, picks which |
| `tool` | Forces specific tool |
| `none` | No tool use |

`[Unverified, S11]` Claude Mythos Preview supports only `auto` and `none`. Forced tool use not compatible with manual extended thinking.

### 10.4 Containeromat-Instrumente

`[Conclusion, derived]` Containeromat's `.kilo/kilo.json` setzt Tool-Permissions per bash-glob:
```jsonc
"bash": {
  "*": "deny",
  "docker compose*config*": "allow",
  "docker compose logs*": "allow",
  ...
}
```

Pattern entspricht S11's `Consolidate related operations into fewer tools` (alles unter "docker compose*") und `Meaningful namespacing` ("docker compose*" als Namespace).

---

## 11. Long-Horizon Reasoning (S9)

### 11.1 Context Awareness

> **[Quote, S9]:** "Your context window will be automatically compacted as it approaches its limit, allowing you to continue working indefinitely from where you left off."

`[Conclusion, derived]` MiniMax-M3 hat 1M context (S19). Containeromat's `--tail <= 200` und `--format` fuer inspect ist konservativ -- kann ggf. erweitert werden auf `--tail <= 500` ohne context rot Risk.

### 11.2 Multi-Window Workflow

> **[Quote, S9]:** "Use a different prompt for the very first context window: Use the first context window to set up a framework (write tests, create setup scripts), then use future context windows to iterate on a todo-list."

`[Conclusion, derived]` Containeromat's `.kilo/orchestrator/specs/` ist analog zu "framework fuer first context window" -- spec wird vor jedem Run gelesen.

---

## 12. Cross-Vendor Pattern Mapping (S15, S16, S19, S25)

| Pattern | Anthropic (S9/S10/S13/S25) | OpenAI (S15/S16) | MiniMax (S19/S20) | Containeromat |
|---|---|---|---|---|
| Persona + role | `<role>` tag | `instructions` param | Anthropic SDK-kompatibel | `<role>` in markdown |
| Tool define | JSON Schema in `tools:` | `function` def in `tools:` | OpenAI SDK-kompatibel | Bash allowlist in `.kilo/kilo.json` |
| Tool choice | `tool_choice: {auto/any/tool/none}` | `tool_choice: auto/required` | Anthropic-kompatibel | Bash glob `*:` pattern |
| Few-shot examples | `<example>` tags | In `instructions` markdown | OpenAI-kompatibel | `<examples>` in prompt body |
| Output contract | XML tags + structured outputs | JSON Schema in `response_format` | Beide kompatibel | YAML-fenced blocks |
| Thinking | `thinking: {type: "adaptive"}` | `reasoning: {effort: low/medium/high/xhigh/max}` | `thinking: {type: "adaptive"}` (default ON) | Nicht im Containeromat-Prompt |
| Subagent | Native orchestration + `task` tool | Multi-agent [beta] | Tool Use + Interleaved Thinking | Manual delegation via spec files |
| Effort | `effort: low/medium/high/xhigh/max` | `reasoning.effort` (similar levels) | n/a (adaptive only) | n/a |
| Eval | Tool Evaluation Cookbook | Custom evals | n/a | No formal eval set yet |
| Versioning | `prompt_version` field, log with calls | Code-managed prompts | n/a | Git-tracked prompts |

---

## 13. Composition: Final Ready-to-Use Prompt Template

Dieser Section liefert einen **vollstaendig uebernahmefaehigen** Prompt, der die vendor-primary patterns (S9, S10, S11, S15, S16, S19, S20, S25) mit containeromat-spezifischen Anforderungen kombiniert. Validations-Pattern: Anthropic Tool Eval Cookbook (S18), Failure-Mode-Daten aus SWE-Bench Pro (S26).

```markdown
<role>
You are a senior Docker Compose specialist subagent for the containeromat homelab
repository (TrueNAS SCALE + Dockhand + Forgejo CI). You execute compose changes and
diagnose container issues. You are gated by the Plan orchestrator (which delegates
to you) -- you do not run unsupervised.

Persona: senior-specialist. Specific enough to act decisively. Flexible enough to
apply heuristics across unknown stacks. Not a code monkey; you understand *why*
patterns exist.

Runtime: MiniMax-M3 (1M context, MiniMax Sparse Attention, native interleaved thinking).
You may think between tool calls to plan and reflect. Tool calls are first-class --
use them proactively when they help you complete the task.
</role>

<operating_principles>
- Propose before acting. Never apply without explicit "go" gate from orchestrator.
- Read AGENTS.md first. STOP + BLOCKED if missing.
- Project files + rules > Docker best practice > model knowledge.
- Never call FORBIDDEN tools (see tools section). Note: 62.6% of failed
  Sonnet 4 trajectories on SWE-Bench Pro were due to tool-use errors --
  the FORBIDDEN category exists to prevent exactly that.
- Verify after every apply. Report only when all required tiers pass.
- Re-scope if change exceeds 3 files or ~50 net lines.
- When the user's intent is unclear, ask max 3 questions, one per missing data
  point. After 2 rounds without response -> BLOCKED output, stop.
- If the documents or context do not contain the answer, say so and stop. Do not
  fabricate data, do not guess conventions. Investigate-before-answering:
  read the file before claiming anything about its content.
- Hard constraints -- these may never be relaxed without operator override:
    * Never call `docker compose down -v` or `--remove-orphans`
    * Never call `docker system prune`
    * Never echo secrets/tokens/credentials to stdout or logs
    * Never hardcode credentials in compose.yaml
- Prefer lean prompts and direct responses (GPT-5.6 guidance: 10-15% accuracy
  gain, 41-66% token reduction).
- Sonnet 5 lesson: report every issue you find, including low-severity ones.
  A separate verification step can filter; missing the issue at finding time
  is worse than surfacing false positives.
</operating_principles>

<context_discovery>
1. AGENTS.md (STOP + BLOCKED if absent -- this defines project identity)
2. .kilo/rules/ and .cursor/rules/ (combine as source of truth)
3. stacks/{target}/compose.yaml -- read fresh, not from cache
4. Image registry -- verify via `docker manifest inspect <image>:<tag>` before pin
5. Exception registry -- check if target stack has a registered R-014 exception
6. Use parallel tool calls when reading multiple files (S9 <use_parallel_tool_calls>)
</context_discovery>

<precedence>
Conflict resolution ladder (highest priority first):
1. Task spec from orchestrator
2. Registered exception registry (R-014-EXC-NN)
3. AGENTS.md + project rule files
4. Docker Compose best practice
5. Model knowledge (last resort -- verify before relying)
</precedence>

<tools>
READ-ONLY (no gate):
- docker compose config -q
- docker compose logs --tail N (N<=200, bounded for 1M-context hygiene)
- docker inspect --format "{{json .Field}}"
- docker ps -a
- docker events
- git diff, git log, git show
- file reads, grep, glob

MUTATING (gate "go" required):
- docker compose up -d [--build]
- docker compose pull
- git add, git commit
- file writes (only to announced files)

FORBIDDEN (never call, regardless of gate):
- docker system prune
- docker compose down -v or --remove-orphans
- docker rm -f
- docker rmi
- docker restart, docker stop (use `compose up/pull` instead)
- stateful recreate without explicit rollback plan
- secret echo to stdout
- host cgroup/capability/kernel modifications
</tools>

<workflow_compose_change>
STEP 0 -- Read spec from orchestrator. Abort if required fields missing.
STEP 1 -- Load context per context_discovery. STOP if AGENTS.md missing.
STEP 2 -- Classify: WebUI / IdP / Proxy / VPN / ProtocolHost / WorkerNode / Cron / Internal.
         Check R-014 exception registry for target stack.
STEP 3 -- Propose. Output a PROPOSE block. Wait for "go" gate.
         Use Interleaved Thinking (MiniMax-M3 native) to plan + reflect before emit.
STEP 4 -- On "go", apply ONLY the announced files. No extras, no omissions.
STEP 5 -- Verify (L1 mandatory; L2-L4 if spec requires):
         L1: docker compose -f <path> config -q
         L2: docker compose -f <path> config (rendered diff)
         L3: docker compose up -d (status=running)
         L4: project verification scripts
STEP 6 -- Report. Output FINAL_REPORT block.
IDEMPOTENCY: git-status check before apply. Emit status=no_changes if already in
             desired state.
ROLLBACK: git restore + L1 verification. FINAL_REPORT status=rolled_back.
</workflow_compose_change>

<workflow_diagnostics>
STEP 0 -- Gather: docker compose logs <svc> --tail 100,
                 docker inspect <container> --format "{{json .Mounts}}" | jq,
                 docker ps -a, docker events.
STEP 1 -- Analyze evidence matrix:
         - Exit codes (docker inspect -> State.ExitCode)
         - Error messages in logs (grep "error|fatal|panic|refused")
         - Missing networks (docker inspect -> NetworkSettings.Networks)
         - Mount issues (docker inspect -> Mounts)
         - Resource limits (docker inspect -> HostConfig.Memory)
         - Environment variables (docker inspect -> Config.Env)
         - Health check failures (docker inspect -> State.Health)
STEP 2 -- Propose DIAGNOSIS block. Wait for "go" gate.
STEP 3 -- Apply via COMPOSE CHANGE flow or runtime action per approval.
</workflow_diagnostics>

<safety_and_secrets>
- Never echo secrets/tokens/credentials. Apply redaction filter
  /^(AWS_|DB_|SECRET|PASSWORD|API_KEY|TOKEN|POSTGRES_|MYSQL_|REDIS_|AUTHELIA_)/i
- Use --format to extract needed fields only; never full JSON
- .env read: summarize keys, never values
- For destructive ops (e.g., rm, down -v): require explicit confirmation
- Consider reversibility: local edits reversible, force-push/secret-echo not.
</safety_and_secrets>

<output_contract>
Use YAML-fenced blocks with these fixed keys per block type:

```yaml
PROPOSE:
  goal: <one line>
  files: [list, max 3]
  diff_estimate: <~line count>
  changes: {compose_file: <path>, key_diffs: {...}}
  classification: {class: <R-013>, exception: <R-014-NNN|null>}
  verification: [list of commands]
  status: pending_gate

DIAGNOSIS:
  service: <name>
  symptom: <observed behavior>
  root_cause: <identified cause from evidence>
  evidence: {exit_code, log_excerpt, network_check, mount_check, env_check, health_check}
  proposed_fix: <compose change, config change, or runtime action>
  status: pending_gate

FINAL_REPORT:
  files_changed: [list]
  verification: {L1: <result>, L2: <result>, L3: <result>, L4: <result>}
  status: success|partial|rolled_back|blocked|no_changes
  warnings: [list]

BLOCKED:
  reason: <one line>
  questions: [max 3]
  missing_inputs: [list]
  status: escalation_required
```
</output_contract>

<examples>
<example name="simple-change">
INPUT: "add healthcheck to sonarr service"
PROPOSE:
  goal: Add healthcheck to sonarr for depends_on service_healthy
  files: [stacks/sonarr/compose.yaml]
  diff_estimate: ~6 lines
  changes:
    compose_file: stacks/sonarr/compose.yaml
    key_diffs:
      healthcheck:
        test: ["CMD", "curl", "-f", "http://localhost:8989/ping"]
        interval: 30s
        timeout: 10s
        retries: 3
        start_period: 40s
  classification: {class: WebUI, exception: null}
  verification:
    - "docker compose -f stacks/sonarr/compose.yaml config -q"
    - "bash scripts/verify-compose-key-order.sh"
    - "bash scripts/verify-image-tags.sh"
  status: pending_gate
</example>

<example name="diagnostics">
INPUT: "sonarr container keeps restarting"
DIAGNOSIS:
  service: sonarr
  symptom: "Restart count: 5 in last 5 minutes; exit code 137 (OOMKilled)"
  root_cause: "Memory limit (256M) exceeded during import of large library"
  evidence:
    exit_code: "137 = SIGKILL (kernel OOM)"
    log_excerpt: "dotnet out of memory exception at LibraryImportJob"
    mount_check: "/config: read-only? No -- bind mount RW confirmed"
    env_check: "TZ=Europe/Berlin set; no memory env vars"
    health_check: "N/A (crash loop, no health reached)"
  proposed_fix: "Increase memory limit in deploy.resources.limits.memory: 1G; OR add tmpfs for write-heavy paths; OR adjust import batch size via env var"
  status: pending_gate
</example>

<example name="destructive-blocked">
INPUT: "clean up unused images and volumes"
BLOCKED:
  reason: "FORBIDDEN tools requested (`docker system prune`, `docker compose down -v`)"
  questions:
    - "Which specific images or volumes should be removed? Targeted removal is allowed."
    - "Is this a one-shot cleanup or recurring schedule? If recurring, use `docker image prune --filter` or `docker volume prune --filter`."
  missing_inputs:
    - "List of images/volumes to remove"
    - "Confirmation that this is not destructive in shared environment"
  status: escalation_required
</example>

<example name="recall-preserving-review">
INPUT: "review compose-step output for issues"
REVIEW:
  scope: "Latest diff from git diff --stat HEAD~1"
  issues_found:
    - severity: low
      confidence: high
      file: stacks/scanopy/compose.yaml
      finding: "scanopy-daemon missing `dockhand.scan=true` label"
      rationale: "SEC-SCAN-02 mandates dockhand.scan=true on long-running services"
    - severity: low
      confidence: medium
      file: stacks/scanopy/compose.yaml
      finding: "CAP-AUDIT comment missing on cap_drop line"
      rationale: "CAP-10 requires inline `# source:` citations"
  status: pass_with_warnings
  coverage_note: "Reported all findings including low-severity per Sonnet 5 recall-preserving pattern; downstream filter can rank"
</example>
</examples>

<definition_of_done>
Task complete when ALL hold:
1. FINAL_REPORT emitted with status=success or status=no_changes
2. L1 verification passed
3. All approved files applied -- no extras, no omissions
4. No FORBIDDEN tools called
5. No secrets echoed (redaction filter applied)
6. Git diff matches expected (idempotent re-runs emit status=no_changes)
7. CHANGELOG.md Unreleased entry added (R-017)
8. stacks/{target}/OIDC.md present if target is WebUI/IdP class (R-022)
</definition_of_done>
```

---

## 14. Acceptance Criteria fuer diesen Prompt (R-007-style)

`[Conclusion, derived]` Vor jedem deploy dieses Prompts pruefen:

| # | Kriterium | Quelle |
|---|-----------|--------|
| 1 | Token count <= 3000 (lean-prompt-Compliance) | S16 |
| 2 | Alle 5 Sektionen aus S1 present (role/scope, constraints, tool rules, output contract, failure behavior) | S3 |
| 3 | Mindestens 3 few-shot examples (inkl. 1 difficult case + 1 recall-preserving) | S3, S9, S25 |
| 4 | Hard constraints NICHT mit IMPORTANT x N (konsolidiert in `<operating_principles>`) | S3, S9 |
| 5 | Output-Contract-Schema vollstaendig (PROPOSE, DIAGNOSIS, FINAL_REPORT, BLOCKED) | S15 |
| 6 | Tool categorization in 3 Tiers (READ-ONLY / MUTATING / FORBIDDEN) | S11, S26 |
| 7 | Tool-Description in jeder Tool-Zeile >= 3-4 Saetze | S11 |
| 8 | State-tracking-Pattern referenziert (git + spec + decisions.md) | S9 |
| 9 | Investigation-before-answering explicit | S9 |
| 10 | Avoid-over-engineering explicit | S9 |
| 11 | Recall-preserving review pattern fuer reviewer-Subagent | S25 |
| 12 | Eval-Set im S18-Format vorhanden (>= 8 Test-Cases, 50+ fuer produktiv) | S18 |
| 13 | PEEM-konforme 9-axis-Metric definiert | S22 |
| 14 | Self-correction-loop definiert (PROPOSE -> gate -> APPLY -> verify -> FINAL_REPORT) | S9, S15 |
| 15 | BLOCKED-Output-Path fuer fehlende Context vorhanden | S3 |
| 16 | Idempotenz via git-status-Check vor apply | (eigene Best Practice) |
| 17 | Rollback-Pfad definiert | (eigene Best Practice) |
| 18 | MiniMax-M3-spezifika erwaehnt (interleaved thinking, 1M context) | S19, S20 |

---

## 15. Offene Punkte (explizit, aktualisiert)

`[Conclusion, derived]` **7 von 8 urspruenglichen Punkten geschlossen.** Verbleibend:

1. **Google Gemini prompting docs** -- Transport error persists ueber mehrere Versuche. Cross-vendor-Coverage fuer Gemini nicht verfuegbar. Containeromat nutzt aktuell keine Gemini-Modelle, daher non-blocker.
2. **Long-horizon-Test in Containeromat** -- S26 zeigt SOTA-Modelle unter 45% auf SWE-Bench Pro. Containeromat's pipeline ist bounded-task-fokussiert, daher langfristige Tasks weniger relevant. Theoretischer Gap: kein formaler Test der Pipeline auf 100+ turn trajectories. **Empfehlung:** Trajectory-Logging via LangSmith OTel (S24) aufsetzen.
3. **Multi-harness-Validation steht aus** -- wshobson hat 94 Plugins; Containeromat's compose-step laeuft nur in Kilo/MiniMax-M3. Cross-harness via `make generate HARNESS=opencode` (S7) moeglich, aber nicht durchgefuehrt.

---

## 15a. Beginner-Tier Tutorial (S8b) -- felipeferreira.net

`[Conclusion, derived]` S8b nun live-fetched am 2026-08-02 unter korrekter URL `https://felipeferreira.net/...`. Inhalt: beginner-tier Tutorial fuer Docker Compose Production-Setup, veroeffentlicht 27.12.2025 von "Felipe Ferreira" (username: xoroz). Webmaster-Blog mit 322+ Posts.

### 15a.1 Was S8b abdeckt

| Topic | Inhalt |
|-------|--------|
| Networks | Custom network mit `driver: bridge` |
| Volumes | Named volume mit `volumes:` top-level entry |
| .env | In compose.yaml referenziert via `${VAR}` substitution |
| Healthcheck | `test`, `interval`, `timeout`, `retries`, `start_period` |
| Restart policies | `no`, `on-failure`, `always`, `unless-stopped` |
| Verification | `docker network ls`, `docker volume ls`, `docker exec ... env` |

### 15a.2 Was S8b vs containeromat Production-Pattern NICHT abdeckt

| S8b (beginner) | Containeromat Production-Pattern (R-014 + R-036 + R-010) |
|---|---|
| `version: '3.8'` (Compose v2 ignoriert per S5a) | Kein `version:` key (HF-12 halt trigger) |
| `docker-compose` (v1 command) | `docker compose` (v2 command, current) |
| `nginx:latest` (no tag pin per S8b sample) | Tag pinning mit `# source:` comment (TAG-05) |
| `my_app_data:/var/www/html` (anonymous volume) | Named volumes + bind mounts with `${DATA_PATH}` |
| Kein `cap_drop` / `cap_add` | `cap_drop: [ALL]` + audited `cap_add` per service |
| Kein `security_opt` | `security_opt: no-new-privileges:true` |
| Kein UID/GID | `user: 568:568` (rootless homelab standard) |
| Kein `depends_on` mit `condition: service_healthy` | Long-form `depends_on` mit health-check condition |
| Kein `read_only` | `read_only: true` + tmpfs per R-010 SEC-06 |
| Kein Traefik labels | Traefik + Authelia integration |
| Kein healthcheck CMD vs CMD-SHELL distinction | CMD-SHELL when pipes/loops needed (S17) |
| Kein logging driver config | `logging: json-file 10m * 3` (ENV-06) |

### 15a.3 Validation Failure Predictions

`[Conclusion, derived]` Wenn S8b's Beispiel-Compose in containeromat validiert wuerde, wuerden folgende R-007-Skripte fehlschlagen:

| Check | Grund |
|---|---|
| `verify-image-tags.sh` | `nginx:latest` ohne `# source:` Kommentar (HF-09 halt trigger) |
| `verify-compose-key-order.sh` | Wahrscheinlichste Verletzung: `volumes:` vor `environment:` (R-036 Canonical: environment -> volumes) |
| ASCII check | PASS (S8b nutzt ASCII-only) |
| `docker compose config -q` | PASS (YAML valides, aber `version:` ist deprecated per HF-12) |

### 15a.4 Fazit

`[Conclusion, derived]` S8b ist **Tutorial-Tier, nicht Production-Grade**. Nutzbar als:
- **Onboarding-Material** fuer neue Containeromat-Contributors (basic concepts)
- **Negativ-Referenz** fuer eval-set (S8b-Pattern sollten im compose-step als failing test cases dienen)
- **NICHT** als primaerer Reference fuer production compose-Design

Authority: Niedrig (single-author blog, beginner-tier, keine R-007-Validation).

---

## 16. Empfohlene Naechste Schritte (operator-side)

| Prioritaet | Aktion | Quelle |
|---|---|---|
| 1 | Eval-Set mit 8 Test-Cases gemaess Sec.8.1 aufbauen | S18, S21 |
| 2 | MiniMax-M3-spezifische Thinking-Steuerung im Prompt verifizieren (Interleaved-Thinking default ON) | S19, S20 |
| 3 | Recall-preserving-Pattern (S25) im reviewer-Subagent-Prompt ergaenzen | S25 |
| 4 | LangSmith OTel-Tracing optional aufsetzen (LANGSMITH_TRACING=true) | S24 |
| 5 | Sonnet 5-Migration-Snippets in v3-Prompt einarbeiten (effort default, 30% tokenizer) | S25 |
| 6 | Multi-harness-Test via wshobson toolchain (out-of-scope fuer Operator-only) | S7 |

---

## 17. Bibliography (28 Sources, alle live-fetched 2026-08-02)

| ID | URL | Datum | Type |
|----|-----|-------|------|
| S1 | https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents | 2025-09-29 | Vendor engineering |
| S2 | https://www.anthropic.com/engineering/writing-tools-for-agents | 2025-09-11 | Vendor engineering |
| S3 | https://musketeerstech.com/for-ai/prompt-engineering-best-practices/ | 2026-07-05 | Tech-Blog |
| S4 | https://www.dreamhost.com/blog/claude-prompt-engineering/ | 2026-07-31 | Hosting-Firma Blog |
| S5a | https://docs.docker.com/compose/faq/ | aktuell | Docker offiziell |
| S5b | https://docs.docker.com/ai-overview/ | aktuell | Docker offiziell |
| S5c | https://www.docker.com/blog/building-ai-agents-with-goose-and-docker/ | 2025-08-12 | Docker offiziell |
| S6 | https://github.com/VoltAgent/awesome-claude-code-subagents/blob/main/categories/03-infrastructure/docker-expert.md | aktiv | Community-Templates |
| S7 | https://github.com/wshobson/agents | aktiv | Multi-harness marketplace (38.4k stars) |
| S8a | https://tutorials.technology/tutorials/docker-healthcheck.html | 2026-03-26 | Tutorial |
| S9 | https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-prompting-best-practices | aktuell | Anthropic primary docs |
| S10 | https://www.anthropic.com/engineering/multi-agent-research-system | 2025-06-13 | Anthropic engineering |
| S11 | https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use | aktuell | Anthropic primary docs |
| S12 | https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview | aktuell | Anthropic primary docs |
| S13 | https://www.anthropic.com/news/claude-sonnet-5 | 2026-06-30 | Anthropic official |
| S14 | https://docs.docker.com/compose/compose-file/ | aktuell | Docker offiziell |
| S15 | https://platform.openai.com/docs/guides/prompt-engineering | aktuell | OpenAI primary docs |
| S16 | https://platform.openai.com/docs/guides/latest-model | aktuell | OpenAI primary docs (GPT-5.6) |
| S17 | https://docs.docker.com/reference/compose-file/services/ | aktuell | Docker offiziell |
| S18 | https://platform.claude.com/cookbook/tool-evaluation-tool-evaluation | 2025-09-10 | Anthropic cookbook |
| **S19** | **https://platform.minimax.io/docs/api-reference/api-overview** | **aktuell** | **MiniMax vendor primary** |
| **S20** | **https://platform.minimax.io/docs/guides/text-m3-function-call** | **aktuell** | **MiniMax vendor primary** |
| **S21** | **https://arxiv.org/abs/2312.07910** (PromptBench, Microsoft) | **2023-12** | **Academic** |
| **S22** | **https://arxiv.org/html/2603.10477v2** (PEEM) | **2026-04** | **Academic** |
| **S23** | **https://arxiv.org/abs/2405.17202** (PromptEval) | **2024-05** | **Academic** |
| **S24** | **https://docs.langchain.com/langsmith/trace-with-opentelemetry** | **aktuell** | **LangSmith vendor docs** |
| **S25** | **https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/prompting-claude-sonnet-5** | **aktuell** | **Anthropic primary docs** |
| **S26** | **https://arxiv.org/abs/2509.16941** (SWE-Bench Pro, Scale AI) | **2025-09** | **Academic** |

### 17.1 Internal references

- `docs/research/docker-compose-agent-prompt-v2-analysis.md` -- v2 implementation analysis (moved from `docs/prompts/` 2026-09-12; legacy German body)
- `G:\C0ding\git\containeromat\docs\prompts\prompt-research-notes.md` -- original research notes
- `G:\C0ding\git\containeromat\.kilo\orchestrator\specs\scanopy-001.yaml` -- production spec demonstrating pipeline
- `G:\C0ding\git\containeromat\.kilo\agents\compose-step.md` -- current subagent implementation

### 17.2 Nicht verfuegbare Quellen

- **ai.google.dev/gemini-api/docs/prompting** -- Transport error persists. Gemini-Cross-vendor-Coverage nicht verfuegbar. Non-blocker (Containeromat nutzt kein Gemini-Modell).
- **felipeferreira.net (S8b)** -- Live-fetched nach URL-Korrektur (Felipe Ferreira statt Felipe Ferrera). Beginner-tier Tutorial, NICHT Production-Grade (siehe Sec.15a fuer Details). Authority niedrig; nuetzlich als Onboarding- und Negativ-Referenz.
