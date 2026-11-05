# Prompt library analysis (2026-09-12)

> **Provenance:** Accepted-findings record. Imported from containeromat
> `docs/research/prompt-library-analysis-2026-09-12.md` (pinned 2026-09-19) and
> kept verbatim, including its containeromat rule IDs and repo paths (R-038,
> `docs/prompts/`, `docs/rules/`). Findings F-1..F-11 and proposals P-1..P-6
> document decisions already accepted in containeromat; they are historical
> evidence for this library, not open items here.

Scope: every maintained prompt surface in this repo, compared against the
project's own prompt-building documentation:
`docs/rules/38-anythingllm-system-prompts.md` (R-038 PP-00..PP-10),
`docs/prompts/system-prompt-standard.md` (7 design principles + constraint
budget) and the evidence base `docs/prompts/rag-workspace-prompt-research-v2.md`.

Method: read every active prompt in full; measured the pasteable body
(after stripping the leading `#` header) and estimated tokens as
`body-bytes / 4`; counted instruction-carrying elements (rules + procedure
steps + capability bullets + format items) per principle 1. Live files only;
archive kept for rollback.

## 1. Inventory

| Surface | Files | Runtime | Governance |
|---|---|---|---|
| AnythingLLM workspace prompts | `docs/prompts/*.txt` (active: standard-rag-v1, homelab-workspace-v25, deep-research-generic-v8) | pasted into workspace UI | R-038 |
| AnythingLLM design docs | `system-prompt-standard.md`, `rag-workspace-prompt-research-v2.md` | none (reference) | R-038 |
| dsh HA subagents | `stacks/deepseek-harness/config/ha-orchestrator.config.json` (5 prompts, seeded) | agent orchestration | none (gap) |
| dsh agent presets | `config/agent-presets/{homelab,anchored-standard,orchestrator}/` | session persona | none (gap) |
| dsh skills | `config/skills/*/SKILL.md` (11) | on-demand load | none (gap) |
| Kilo agents | `.kilo/agents/*.md` (5) | subagent system prompts | AGENTS.md only |

## 2. Compliance snapshot (R-038)

| Prompt | Body ~tokens | Numbered rules | Instruction elements | Injection guard | Source duty | Output contract | Header |
|---|---|---|---|---|---|---|---|
| `standard-rag-v1` | ~412 | 6 | 12 (3+6+3) | yes (rule 2) | yes (CoVe + citations) | yes | PASTE BODY ONLY; numeric budget in header |
| `homelab-workspace-v25` | ~866 | 6 | ~22-24 | yes (rule 2) | yes | yes | PASTE BODY ONLY; dangling "re-estimated below"; long history |
| `deep-research-generic-v8` | ~860 | 6 | ~17-19 | yes (rule 2) | yes | yes | stale claim "<=800 (body ~700)" |
| `docker-compose-agent-prompt-v2.md` | ~5000 (not a runtime prompt) | n/a | n/a | n/a | n/a | n/a | none; German analysis doc |
| `archive/technical-reviewer-v3` | ~500 | 6 | ~14 | yes | PP-06 tags | PP-09 schema | archived |

Constraint budget from the standard: 12 instruction elements, <=6 numbered
rules, <=850 body tokens.

## 3. Findings

### F-1 [HIGH] `homelab-workspace-v25` exceeds both budget dimensions

Body ~866 tokens (>850) and ~22-24 instruction elements (standard: 12).
Duplicated / compressible content:

- Capability bullet "Verify:" duplicates CoVe VERIFY and rule 5.
- "Web research (3 paths)" restates the upstream-fact trigger chain that is
  already the point of the prompt; the mechanics belong in the flow/tool
  descriptions.
- "Docs:", "Images:", "Memory:" bullets carry tool mechanics that belong in
  tool descriptions; keep only the WHEN trigger.
- Rule 6 packs five instructions (whitelist, no-exploration, output caps,
  error reporting, no re-fetch) into one slot; splitting is impossible under
  the rule budget, so compress to two sentences.
- Header history block is repo metadata; move it to a changelog file to keep
  the file readable (no runtime effect).

Target for v26: <=850 tokens, <=16 elements without losing a single
behavioral requirement (merge, do not delete).

### F-2 [HIGH] `deep-research-generic-v8` over budget + stale header

Body ~860 tokens (>850, marginal). Rule 5 bundles four instructions
(verification-first, bounded revision, no retry, no repeat); the
`<context_handling>` block restates parts of rules 2-5. Header claims
"Body target <= 800 tokens (body ~700)" - measured ~860. Fix: tighten rules
3/5 and context block (~30-40 tokens), correct the header, target v9.

### F-3 [MEDIUM] No runtime control-flow markers - violated by bounded-revision rules

`system-prompt-standard.md` derivation guide: "No runtime control-flow markers
in system prompts (round counters, loop state...)". Two active prompts carry
cycle counters: v25 rule 5 ("<=2 cycles then switch") and v8 rule 5 ("After at
most 2 revision cycles"). This is a documented design tension (v8 added the
bound deliberately per Huang ICLR 2024 / ACL 2025). Resolve explicitly:
either move the bound into the tool/flow layer, or record the deviation as an
accepted exception in the prompt header + this doc.

### F-4 [MEDIUM] Numeric token budgets in `#` headers (PP-02 hazard)

R-038's origin story: a header budget was misread as an output limit. All
three active prompts put numbers in the header, and two are now wrong (v8) or
dangling (v25). Recommendation: headers carry version, date, PASTE BODY ONLY,
design links only - budgets live in a lint script/report, not in the prompt
file. Fix while creating v26/v9.

### F-5 [MEDIUM] No automated R-038 gate

"<=6 numbered rules" is trivially checkable; "count ALL instruction-carrying
elements" is not, and no script checks anything. Proposal:
`scripts/verify-prompts.sh` - body token estimate, numbered-rule count,
forbidden plan-internal IDs (F-*/A-*/P-*), unverified AnythingLLM variables
allowlist (`{datetime}`, `{user.name}`), `PASTE BODY ONLY` header presence,
ASCII scan, German-text detection. Add a closeout row (R-007) for
`docs/prompts/` changes.

### F-6 [MEDIUM] `docs/prompts/` mixes runtime prompts with analysis docs

`docker-compose-agent-prompt-v2.md` is a 20 KB German analysis/rewrite
document (not a pasteable prompt, no R-038 header) - violates R-040 (English
artifacts) and blurs the folder contract. Also no `README.md` index. Actions:
move analyses to `docs/research/`, add `docs/prompts/README.md` with the file
map (currently only inside `system-prompt-standard.md`).

### F-7 [MEDIUM] Archived reviewer prompt may still be live in the UI

`technical-reviewer` v1-v3 are archived, but R-038 PP-01 has no auto-sync; if
the `reviewer` workspace still exists, its UI field may still hold v3.
Operator check recommended; if live, derive a `technical-reviewer-v4` per
R-038 PP-06/07/09 (the current standard), else document the retirement.

### F-8 [MEDIUM] dsh prompt surfaces have no authoring standard

The five HA subagents, the preset personas and 11 skills were authored with no
documented rules (R-038 applies to AnythingLLM only). The HA prompts are in
good shape informally - every one has a role, an explicit data-not-
instructions guard, an evidence duty and an output contract; the reviewer
defines severity H/M/L inline (analogous to PP-07). Formalize what we already
do: extend R-038 with an "agent/subagent prompts" annex (or new rule):
instruction-element budget per subagent prompt (<=12, <=400 tokens), injection
guard, output contract, no repo-rule IDs without inline definitions,
English-only, seed-version ownership (config file vs plugin-generated files).

### F-9 [LOW] Kilo agent prompts duplicate shared conduct boilerplate

`.kilo/agents/*.md` = 912 lines total (orchestrator 271, compose-step 218,
reviewer 192, code-skeptic 118, docs-specialist 113). Secret handling,
data-not-instructions and evidence formats are repeated per agent. Proposal:
one shared `agent-conduct` skill (secrets redaction, data-not-instructions,
read-only discipline, evidence block format) referenced by all agents; keep
role-specific gates (STOPP/HALT) inline. Estimated 10-15% token saving per
subagent invocation.

### F-10 [LOW] Large on-demand dsh skills

`anti-hallucination` 11.5 KB, `anti-sycophancy` 12 KB,
`deepseek-v4-agent-defense` 17 KB. On-demand load mitigates the cost, but the
same instruction-count principle applies when loaded. Proposal: split a
"core checklist" (<=60 lines) from examples/appendices, or compress prose;
note these are ports and keep parity with upstream where practical.

### F-11 [INFO] Strengths worth preserving

- Function-style roles, no persona adjectives (principle 2) in all AnythingLLM
  prompts and HA subagents.
- CoVe procedure and cite-or-omit in the AnythingLLM line.
- Data-not-instructions guard present everywhere external content is read.
- HA subagents define severity and output contracts inline; no plan-internal
  IDs leaked into runtime prompts.

## 4. New prompts worth integrating

| # | Proposal | Surface | Rationale | Effort |
|---|---|---|---|---|
| P-1 | `homelab-ops` subagent (compose/docker change specialist: PROPOSE -> STOP -> APPLY -> Verify) | dsh HA subagents | orchestration has code roles but no infra role for this homelab; mirrors `.kilo/agents/compose-step.md` | S |
| P-2 | `security-auditor` subagent (secret scan, auth surface, dependency risk) | dsh HA subagents | distinct lens from `reviewer`; fits EXC-26/security work | S |
| P-3 | `technical-reviewer-v4` (PP-06 evidence tags + PP-07 severity + PP-09 output contract) | AnythingLLM | revives the archived reviewer line on the current standard, if the workspace is still used | M |
| P-4 | `homelab-ops` workspace prompt (derived from standard-rag-v1 + repo-rule inline definitions) | AnythingLLM | only if a compose/incident workspace is wanted; current homelab prompt is generic RAG | M |
| P-5 | `scripts/verify-prompts.sh` + optional `/prompt-audit` command | tooling | turns R-038 from prose into a gate (F-5) | S |
| P-6 | `prompt-authoring` dsh skill (R-038 + dsh annex summary) | dsh skills | makes future subagent/skill prompts compliant by default (F-8) | S |

## 5. Recommended order

1. v26 trim of `homelab-workspace-v25` (F-1) - highest user-visible value.
2. v9 trim of `deep-research-generic-v8` + header fixes (F-2, F-4).
3. `scripts/verify-prompts.sh` + closeout row (F-5).
4. Folder hygiene: move `docker-compose-agent-prompt-v2.md`, add
   `docs/prompts/README.md` (F-6); resolve the control-flow marker question
   (F-3); operator check on the archived reviewer (F-7).
5. R-038 dsh annex (F-8); optional P-1/P-2 subagents; F-9/F-10 compaction.

## Cross-refs

- R-038: `docs/rules/38-anythingllm-system-prompts.md`
- Standard: `docs/prompts/system-prompt-standard.md`
- Evidence base: `docs/prompts/rag-workspace-prompt-research-v2.md`
- dsh prompt seeds: `stacks/deepseek-harness/config/ha-orchestrator.config.json`,
  `config/agent-presets/`, `config/skills/`
- Kilo agents: `.kilo/agents/*.md`

## 6. Post-implementation status (2026-09-12)

Landed the same day as this analysis:

- `homelab-workspace-v26.txt` and `deep-research-generic-v9.txt`: v26 body ~763
  tokens / ~16 elements (was ~873 / ~21), v9 ~720 / ~16 (was ~863 / ~17); both
  ASCII-clean, headers carry no token numbers, runtime cycle counters removed
  (F-1, F-2, F-3, F-4).
- `scripts/verify-prompts.sh`: latest-version default (`--all`, `--verbose`);
  hard checks = PASTE BODY ONLY header, body <= 850 tokens, <= 6 numbered rules,
  no plan-internal IDs, verified AnythingLLM variables only; soft WARN =
  non-ASCII count, R-040 German-stopword heuristic. Wired into the R-038
  self-check and the R-007 closeout (F-5).
- `docs/prompts/README.md` index added; the misfiled German v2 analysis moved to
  `docs/research/docker-compose-agent-prompt-v2-analysis.md` with an English
  provenance note (F-6).
- `docs/rules/42-agent-prompt-standard.md` (R-042) added for dsh/Kilo agent
  prompts; AGENTS.md rule navigation updated (F-8).
- Live pointers refreshed: anythingllm `OIDC.md` (v22 -> v26; research prompt
  v9) and `.kilo/README.md`.

## 7. Follow-ups (open)

- F-6b: translate the legacy German analysis doc (R-040). Deferred: R-040
  converts legacy content opportunistically, not in bulk; the provenance note
  records the tracking.
- F-7: operator check whether the archived `technical-reviewer-v3` is still
  pasted in a live workspace; if yes, derive `technical-reviewer-v4` per R-038
  PP-06/07/09, else document the retirement.
- F-9: shared Kilo `agent-conduct` skill to dedupe safety/evidence boilerplate
  across `.kilo/agents/*.md`.
- F-10: split the large dsh skills (`anti-hallucination`, `anti-sycophancy`,
  `deepseek-v4-agent-defense`) into a core checklist + examples.
- P-1/P-2: landed 2026-09-12 -- `homelab-ops` and `security-auditor` added to
  the seeded HA config (`ha-orchestrator.config.json`, seed
  `2026-09-12-homelab-ops-gate`); a force redeploy applies them. Review
  follow-up: `homelab-ops` is propose-only by default (apply only when the task
  says so; the orchestrator owns the gate) and points at
  `.kilo/agents/compose-step.md` as the mirrored canonical compose-change
  policy.
- Operator: paste v26/v9 BODY ONLY into the workspace UIs (R-038 PP-01: no
  auto-sync).
