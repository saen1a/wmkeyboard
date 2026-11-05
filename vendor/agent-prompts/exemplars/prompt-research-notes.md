# Agent System Prompt Research: Best Practices & Docker Compose Subagent Templates

> **Provenance:** Imported from containeromat `docs/prompts/prompt-research-notes.md`
> (pinned 2026-09-19); kept verbatim as a research-notes exemplar. External URLs
> are research citations as of 2026-08-02, not maintained links.

**Scope:** 2025-2026 best practices for writing system prompts for coding/DevOps AI agents, with sourced rules and real subagent templates.
**Disclaimer:** Sources are real URLs actually fetched during this research session.

---

## 1. Best-Practice Rules for Agent System Prompts

Grouped by category. Each rule is backed by a fetched source.

---

### Structure & Formatting

**Rule 1 -- Use labeled section structure (XML tags or Markdown headers).**
Anthropic's own system prompts (analyzed by Simon Willison, May 2025) are organized into clearly labeled sections: behavior, artifacts, search instructions, model knowledge cutoff. Section headers or XML-style tags like `<background>`, `<instructions>`, `## Output description` let the model parse each block independently. Source: [Dreamhost -- Claude Prompt Engineering (2025)](https://www.dreamhost.com/blog/claude-prompt-engineering/)

**Rule 2 -- Describe the outcome, not the steps.**
Anthropic's Sonnet 5 announcement (June 30, 2026) recommends giving agents a testable target ("Reduce load time below 2s and show before/after measurement") rather than step-by-step instructions. Micromanaging steps narrows the agent's options and prevents generalization to edge cases. Source: [Dreamhost -- Claude Prompt Engineering / Anthropic Sonnet 5](https://www.dreamhost.com/blog/claude-prompt-engineering/)

**Rule 3 -- Structure the system prompt as an operating manual, in order: role/scope -> hard constraints -> tool rules -> output contract -> failure behavior.**
This five-section order (operating-manual structure) is the consensus pattern across 2026 production agent guides. Failure behavior is the most commonly omitted section but the most critical for unattended operation. Source: [Musketeers Tech -- Prompt Engineering Best Practices for AI Agents (2026)](https://musketeerstech.com/for-ai/prompt-engineering-best-practices/)

**Rule 4 -- Separate instructions from untrusted data with delimiters.**
Wrapping user-supplied content in XML-style markers (or equivalent), with an explicit instruction that content inside is data and never instructions, reduces hallucination and blunts prompt-injection attacks. Delimiters are the first layer of defense; least-privilege tool permissions and confirmation gates for writes are the second. Source: [Musketeers Tech -- Prompt Engineering Best Practices for AI Agents (2026)](https://musketeerstech.com/for-ai/prompt-engineering-best-practices/)

---

### Role & Scope

**Rule 5 -- State the role at the right altitude: specific enough to guide, flexible enough for heuristics.**
One common failure: engineers hardcode complex if/else logic that creates brittleness. The other: overly general guidance that falsely assumes shared context. The optimal altitude gives concrete signals for desired behavior while letting the model apply strong heuristics. Source: [Anthropic -- Effective Context Engineering for AI Agents (Sep 29, 2025)](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

**Rule 6 -- Start minimal, then add instructions based on observed failure modes.**
Anthropic recommends testing the smallest viable prompt first with the best available model, then adding targeted corrections for failures observed in evaluation. Over-specifying upfront leads to accumulated contradictions that are hard to debug. Source: [Anthropic -- Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

---

### Tool Use

**Rule 7 -- Write tool descriptions as carefully as prompts.**
The model chooses tools based entirely on tool names, descriptions, and parameter documentation. Each tool description should state: what it does, when to use it and when not to, what each parameter means, and what the output looks like. Unambiguous, descriptive parameter names (e.g., `user_id` not `user`) dramatically reduce error rates. Source: [Anthropic -- Writing Tools for AI Agents (2025)](https://www.anthropic.com/engineering/writing-tools-for-agents)

**Rule 8 -- Provide a minimal, well-defined tool set; prune overlap.**
A common failure: bloated tool sets covering too much functionality, causing ambiguous decision points about which tool to use. If a human engineer cannot definitively say which tool applies in a given situation, the AI agent cannot be expected to. Curating a minimal viable tool set also reduces context overhead. Source: [Anthropic -- Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

---

### Decision Rules & Guardrails

**Rule 9 -- Specify explicit failure behavior for every error scenario.**
State what the agent does when a tool errors, when data is missing, or when confidence is low. Example: "If the customer record is not found, return `status: not_found` -- do not create one." Without this, agents fabricate data. Source: [Musketeers Tech -- Prompt Engineering Best Practices for AI Agents (2026)](https://musketeerstech.com/for-ai/prompt-engineering-best-practices/)

**Rule 10 -- Include stop conditions (max steps, max cost, human escalation).**
Agent loops without stop conditions lead to infinite retries and resource exhaustion. Define explicit boundaries alongside failure behavior so the agent knows when to stop or escalate. Source: [Musketeers Tech](https://musketeerstech.com/for-ai/prompt-engineering-best-practices/)

---

### Output Format

**Rule 11 -- Be specific about format, length, and audience; use positive instructions over prohibitions.**
Naming the output format, length, audience, and structure produces more consistent outputs than prohibitions ("do not add explanations"). Positive instructions ("respond only in JSON matching this schema") are followed more reliably. Source: [Musketeers Tech](https://musketeerstech.com/for-ai/prompt-engineering-best-practices/)

**Rule 12 -- Use few-shot examples (2-5 input/output pairs) to control output format.**
Showing 2-5 examples -- including at least one difficult case (ambiguous input, refusal, or missing-data scenario) -- controls output format more reliably than prose descriptions. Models generalize from the distribution of examples provided. Source: [Musketeers Tech](https://musketeerstech.com/for-ai/prompt-engineering-best-practices/)

---

### Context & Anti-Drift

**Rule 13 -- Budget the context window; treat tokens as a finite resource.**
Context rot degrades retrieval quality as context grows. Best practice: pin the system prompt, retrieve only relevant documents, summarize or drop old conversation turns. One production support-agent deployment reduced per-task token spend by ~60% by replacing full-history appending with rolling summaries. Source: [Anthropic -- Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

**Rule 14 -- Ground factual answers with retrieval and an explicit exit instruction.**
Require the model to answer only from supplied documents and quote its supporting passage. Give it an explicit exit: "If the documents do not contain the answer, say so and stop." The exit instruction prevents fabricated answers when retrieval returns nothing relevant. Source: [Musketeers Tech](https://musketeerstech.com/for-ai/prompt-engineering-best-practices/)

**Rule 15 -- Give reasoning room (chain-of-thought or built-in reasoning).**
For tasks involving judgment, instruct the model to reason before answering. In agents, reasoning should be emitted in a dedicated scratchpad/thinking block that downstream code ignores, keeping structured action output clean for parsing. Source: [Musketeers Tech](https://musketeerstech.com/for-ai/prompt-engineering-best-practices/)

---

### Evaluation

**Rule 16 -- Test prompts like code: maintain an evaluation set, version-control prompts.**
Prompt changes are code changes. Best practice: maintain an evaluation set of 20-50 real inputs with expected outputs or rubrics, run it on every edit, version prompts in git, and log every model call with its prompt version. Small refinements to tool descriptions alone can yield dramatic improvements (Anthropic improved SOTA on SWE-bench Verified through tool-description precision alone). Source: [Anthropic -- Writing Tools for AI Agents](https://www.anthropic.com/engineering/writing-tools-for-agents) and [Musketeers Tech](https://musketeerstech.com/for-ai/prompt-engineering-best-practices/)

**Rule 17 -- Evaluate tool-call accuracy and task completion rate.**
In evaluation prompts, instruct agents to output reasoning, feedback, and structured response blocks. Instructing agents to output these *before* tool-call blocks may trigger chain-of-thought behaviors. Pair each evaluation prompt with a verifiable outcome or ground-truth response. Source: [Anthropic -- Writing Tools for AI Agents](https://www.anthropic.com/engineering/writing-tools-for-agents)

**Rule 18 -- Decompose workflows into chained, focused prompts.**
A single prompt that classifies, extracts, decides, and drafts performs each job worse than four focused prompts chained together. Prompt chaining also makes agents debuggable: each step can be evaluated and fixed in isolation. If a prompt's success criterion cannot be stated in one sentence, the prompt is doing too many jobs. Source: [Musketeers Tech](https://musketeerstech.com/for-ai/prompt-engineering-best-practices/)

---

## 2. Real Docker/DevOps Subagent Prompt Templates Found

### Template A -- VoltAgent `docker-expert` (recommended for Docker Compose Specialist subagent)

- **Source:** [VoltAgent/awesome-claude-code-subagents -- `docker-expert.md`](https://github.com/VoltAgent/awesome-claude-code-subagents/blob/main/categories/03-infrastructure/docker-expert.md)
- **Structure outline:**
  1. **YAML frontmatter**: `name`, `description`, `tools` (explicit tool allowlist), `model` (e.g., `sonnet`)
  2. **Role definition**: single-sentence senior-specialist identity statement
  3. **"When invoked" block**: 4-step workflow (query context -> review -> analyze -> implement)
  4. **Domain checklist sections**: Docker excellence checklist, Dockerfile optimization, Container security, Docker Hardened Images, Supply chain security, Docker Compose orchestration, Registry management, Networking and volumes, Build performance, Modern Docker features -- each as a bullet list (no prose paragraphs)
  5. **Communication Protocol**: structured JSON context-query block for inter-agent messaging
  6. **Development Workflow**: numbered phases (Container Assessment -> Implementation Phase -> Container Excellence), each with priorities, technical evaluation criteria, and a progress-tracking JSON block
  7. **Integration section**: named peer agents (kubernetes-specialist, devops-engineer, security-engineer, etc.)
  8. **Closing directive**: a single-line value statement
- **Notable techniques:**
  - Explicit tool allowlist in YAML frontmatter (avoids over-permission)
  - "Docker excellence checklist" as measurable SLA-style targets (< 100MB images, < 5min build, zero critical vulnerabilities)
  - Structured JSON inter-agent communication protocol
  - Peer-agent integration mapping
  - Progress-tracking JSON with quantified metrics emitted on completion

---

### Template B -- wshobson/agents: `devops-troubleshooter` + `deployment-engineer`

- **Source:** [wshobson/agents -- agents directory](https://github.com/wshobson/agents/tree/main/agents) (23.9k+ GitHub stars, 184 agents)
- **Structure outline (per agent file):**
  1. **Header comment**: `# Agent: <name>` with one-line purpose
  2. **Role block**: concise role statement + specialization scope
  3. **Capabilities list**: domain-specific bullet list
  4. **Interaction model**: when and how to invoke the agent
  5. **Constraints**: what the agent should not do
  6. **Output guidance**: format expectations for responses
- **Notable techniques:**
  - Minimalist structure -- no lengthy prose; capability lists over narrative
  - Peer agents referenced by name (e.g., `devops-troubleshooter` and `deployment-engineer` coordinate)
  - Authors note that broad capability lists without depth produce generic results; depth achieved via companion Skills, not the agent prompt alone
  - Evaluated by the community: discussion [#42 "Very generic agents"](https://github.com/wshobson/agents/discussions/42) flagged that capability-list agents need companion skills for depth

---

### Template C -- Docker.com + tutorial ecosystem: Docker Compose `healthcheck` + `depends_on` patterns

- **Sources:**
  - [Docker -- Compose FAQ](https://docs.docker.com/compose/faq/) (official)
  - [tutorials.technology -- Docker Compose Healthcheck Syntax (2025)](https://tutorials.technology/tutorials/docker-healthcheck.html)
  - [felipeferreira.net -- Mastering Production-Grade Docker Compose (Dec 2025)](https://felipeferreira.net/2025/12/27/mastering-production-grade-docker-compose-your-essential-guide/)
- **Structure outline (Compose-specific knowledge a Docker Compose Specialist subagent should carry):**
  - `depends_on` with `condition: service_healthy` (not just container-start wait)
  - Health check syntax: `test`, `interval`, `timeout`, `retries`, `start_period`
  - `CMD` vs `CMD-SHELL` distinction (shell features require `CMD-SHELL`)
  - Restart policies: `no`, `on-failure`, `always`, `unless-stopped`
  - Health endpoint design: `/health` route checking internal dependencies, not the homepage
  - Label conventions: `com.myorg.*` for multi-container management
  - Environment file integration: `--env-file` + `.env` for secrets
  - Network isolation: custom `bridge` networks per project
- **Notable techniques:**
  - Liveness vs readiness distinction built into healthcheck design
  - Multi-label tagging for multi-container orchestration management
  - `start_period` tuned per service (database: 30s, web: 5s)

---

### Template D -- Docker.com: AI Agents & Docker Agent (agent-builder guidance)

- **Source:** [Docker -- AI Agents overview](https://docs.docker.com/ai-overview/) and [Docker -- Building AI Agents with Goose and Docker (Aug 2025)](https://www.docker.com/blog/building-ai-agents-with-goose-and-docker/)
- **Structure for agent-as-Compose-service (relevant to subagent architecture):**
  1. **Dockerfile**: builds the agent image with dependencies + config files
  2. **compose.yml**: orchestrates the agent as a service (model runner, MCP gateway, agent runtime)
  3. **Agent config** (`.goosehints` or equivalent): business-logic system prompt supplied as a mounted file
  4. **MCP Gateway**: isolates external tools in their own containers via SSE MCP server; mitigates command-injection risk
- **Notable techniques:**
  - Agent logic in mounted config file (not hardcoded in Dockerfile), enabling prompt iteration without rebuild
  - MCP Gateway as a security boundary between agent and external tools
  - `models:` block in compose.yml for declarative local LLM inference
  - Cloudflare tunnel as optional public exposure layer

---

## 3. Critique Checklist: Evaluate an Agent Prompt

Use this checklist to assess whether a given agent system prompt is well-designed.

### Scope & Role
- [ ] Is the role defined as a specific persona (not generic)?
- [ ] Does the prompt state what the agent should *not* do (hard constraints)?
- [ ] Is the scope bounded -- or does the agent try to be a "general-purpose everything"?

### Structure
- [ ] Is the prompt organized into labeled sections (headers or XML tags)?
- [ ] Are instructions separated from data via delimiters?
- [ ] Is the ordering consistent: role -> constraints -> tools -> output format -> failure behavior?

### Tools
- [ ] Does each tool have a clear description covering: purpose, when to use, parameters, output shape?
- [ ] Are parameters unambiguously named (no generic names like `user` or `id`)?
- [ ] Is the tool set minimal, with no redundant or overlapping tools?
- [ ] Does the agent know which tools *not* to call in a given situation?

### Output
- [ ] Is the output format specified (JSON schema, Markdown, table, etc.)?
- [ ] Are there 2-5 few-shot examples, including at least one difficult case?
- [ ] Does the prompt state expected length or word count?

### Failure & Guardrails
- [ ] Is failure behavior defined for each error scenario?
- [ ] Are stop conditions present (max steps, max cost, escalation trigger)?
- [ ] Is there an explicit exit instruction for when context/retrieval is insufficient?

### Context
- [ ] Does the system prompt avoid bloating with project-specific details that should come from retrieval?
- [ ] Is the prompt version-controlled and regression-tested against a real evaluation set?
- [ ] Are instructions at the right altitude -- guiding but not hardcoded if/else logic?

### Domain Fitness (Docker Compose Specialist)
- [ ] Does the prompt include measurable Docker/Compose SLA targets?
- [ ] Are healthcheck patterns, `depends_on` conditions, and network isolation specified?
- [ ] Does the prompt reference inter-agent communication protocols for context handoff?
- [ ] Is there a checklist or rubric the agent can self-evaluate against?

---

*Research conducted August 2, 2026. Sources reflect 2025-2026 publications. All URLs were actually fetched during this session.*
