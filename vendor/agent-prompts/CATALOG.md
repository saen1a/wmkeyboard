# Catalog

This is a template library, not a roster: it holds portable role templates that
a project selects, fills with project-owned slots and registers in its runtime.
The flow is select -> instantiate -> register: pick the rows for the project's
plane, fill the `{{SLOTS}}` and copy the library blocks byte-exact, then wire the
instantiated prompt into the project's Kilo/dsh agent registry.
Start with `docs/TEMPLATE-GUIDE.md` (schema + skeleton + quality bar),
`docs/INSTANTIATE.md` (slot contract + runtime mapping) and `docs/SYNC.md`
(fragment authority + anti-drift rules). A task that outlives one context
window is governed by `standards/long-horizon-runs.md` (LH-01..LH-14) and
validated with `tooling/run_state.py`; its history is the append-only journal
in `standards/run-journal.schema.json` and `tooling/check_run_journal.py`. Token and cache efficiency are governed by
`standards/prompt-assembly.md` (AS-01..AS-14) and `standards/cache-profiles.json`,
checked by `tooling/check_token_efficiency.py`. What a gate verdict must contain
is governed by `standards/verification-integrity.md` (VI-01..VI-15,
`standards/gate-verdict.schema.json`, `tooling/check_gate_verdict.py`). The loop
itself is `standards/workflow-loop.md` (WL-01..WL-15): seven phases, with the
plan-review gate (WL-15) mandatory before Implement; the
instruction surface by `standards/prompt-security.md` (PS-01..PS-14,
`tooling/check_prompt_security.py`); runtime projections by
`standards/agent-adapter.md` (AD-01..AD-12, `tooling/check_admission.py`).
Work authorization is governed by `standards/work-authorization.md`
(WA-01..WA-12, `standards/mandate.schema.json`, `tooling/check_mandate.py`);
durable side effects and their transport by `standards/durable-effects.md`
(EF-01..EF-10) and `standards/message-delivery.md` (MD-01..MD-08); unsolicited
contact by `standards/agent-notification.md` (NT-01..NT-10); and the
model-visible surface with its token budgets and resolvable rule citations by
`standards/model-surface.json` and `tooling/check_model_surface.py`.
`standards/verification-integrity.md` also governs derived status (VI-15).

## Index

Every row is maintained in sync with the template frontmatter (regenerate via
the review checklist). `purpose` is the
frontmatter one-liner; `tool_profile` is the declared tool posture. The library
currently ships **38 templates** under `agents/**` (8 engineering, 1 design,
1 documentation, 1 networking, 3 operations, 3 orchestration, 3 research,
13 review including 8 review tracks, 5 tabletop).

| id | domain | name | status | tool_profile | purpose |
|---|---|---|---|---|---|
| `design-ui-reviewer` | design | UI Reviewer | stable | `read-only` | Read-only critique of a user interface for cohesion, usability and intentional aesthetics, with severity-graded findings and concrete fixes. |
| `documentation-doc-writer` | documentation | Doc Writer | stable | `doc-write` | Write and repair persisted English documentation in the project's layout, with minimal diffs, CHANGELOG discipline and verified links; doc-write. |
| `engineering-api-developer` | engineering | API Developer | draft | `gated-write` | Implement HTTP or RPC contract changes from an approved spec, keeping versioning, error shape, idempotency and backwards compatibility explicit. |
| `engineering-backend-developer` | engineering | Backend Developer | stable | `gated-write` | Implement server-side logic and services from an approved spec as the smallest change, preserving the interface contracts the spec does not change. |
| `engineering-database-developer` | engineering | Database Developer | draft | `gated-write` | Implement schema, migration, query and index changes from an approved spec, with reversible migrations and no ungated destructive operation. |
| `engineering-explorer` | engineering | Explorer | stable | `read-only` | Fast read-only location of code for where-is questions, returning file:line hits as a capped list with a summary. |
| `engineering-fixer` | engineering | Fixer | stable | `gated-write` | Apply a complete approved spec exactly with the smallest change, refusing work without a spec. |
| `engineering-frontend-developer` | engineering | Frontend Developer | stable | `gated-write` | Implement UI components, styling and accessibility from an approved spec as the smallest change in the project's styling system. |
| `engineering-oracle` | engineering | Oracle | stable | `read-only` | Read-only architecture, debugging and simplification advice with explicit tradeoffs, claim labels and YAGNI discipline. |
| `engineering-test-author` | engineering | Test Author | speculative | `gated-write` | Author tests from acceptance criteria that assert the public contract, without editing production behavior. |
| `networking-network-architect` | networking | Network Architect | draft | `read-only` | Read-only design and review of network topologies -- addressing, zones, routing, trust boundaries and failure domains -- with tradeoff reasoning. |
| `operations-ci-implementer` | operations | CI implementer | stable | `gated-write` | Execute one operator-approved CI, workflow or CI-helper-script change, verify it with the project's gate battery and commit it once; never push or merge. |
| `operations-executor` | operations | Operations executor | stable | `gated-write` | Execute one operator-approved project change or one bounded diagnosis, gated by the operator and verified with the project's proof commands. |
| `operations-format-normalizer` | operations | Format normalizer | stable | `batch-write` | Execute one operator-approved format-normalization batch and commit it once with verification evidence. |
| `orchestration-council-synthesizer` | orchestration | Council synthesizer | stable | `read-only` | Merge the dispatcher-provided seat responses into one decision that preserves dissent and adds no facts. |
| `orchestration-councillor` | orchestration | Councillor | stable | `read-only` | Give one independent opinion on a plan or design as a single review seat, formed without seeing any other seat. |
| `orchestration-orchestrator` | orchestration | Orchestrator | stable | `orchestrator` | Own the Plan-to-Push workflow loop for one project by writing decision-complete specs, delegating units, gating phases, routing Review/Fix and Verify/Fix back-edges, keeping durable run state across sessions, and stopping at the operator Push gate. |
| `research-librarian` | research | Librarian | stable | `read-only` | Multi-repository, documentation and codebase lookup that separates official from community sources and reports labelled findings; read-only. |
| `research-research-merger` | research | Research Merger | stable | `read-only` | Merge multiple research sub-reports into one provenance-preserving summary with conflicts and gaps surfaced, adding no facts. |
| `research-researcher` | research | Researcher | stable | `read-only` | Live-source investigation that returns verifiable facts with source URLs, observation dates and claim labels; read-only plus web. |
| `review-code-skeptic` | review | Verification Skeptic | stable | `read-only` | Challenge completion claims and skipped steps, demand exit-code evidence for each claim and mark anything unproven without editing. |
| `review-consistency-reviewer` | review | Consistency Reviewer | speculative | `read-only` | Review a corpus for internal contradictions, timeline breaks and terminology drift and report claim-labelled findings without editing. |
| `review-review-lead` | review | Review Lead | stable | `read-only` | Resolve a review scope, select the tier, dispatch specialist track children and merge their high-confidence findings without editing. |
| `review-reviewer` | review | Change Reviewer | stable | `read-only` | Audit a change diff and its evidence against the task spec from clean context and report severity-graded, claim-labelled findings without editing. |
| `review-security-reviewer` | review | Security Reviewer | stable | `read-only` | Audit a change or stack through the defensive security lens only and report evidence-first findings on secrets, authentication, exposure and dependencies without editing. |
| `review-track-correctness` | review | Correctness Track | stable | `read-only` | Review the selected diff for ordering, error-path and wiring faults only and return changed-line findings without editing. |
| `review-track-dead-code` | review | Dead Code Track | stable | `read-only` | Review the selected diff for dead config or code it leaves behind only and return changed-line findings without editing. |
| `review-track-deploy-safety` | review | Deploy Safety Track | stable | `read-only` | Review the selected diff for rollout, data and rollback risks only and return changed-line findings without editing. |
| `review-track-duplication` | review | Duplication Track | stable | `read-only` | Review the selected diff for duplication it newly introduces only and return changed-line findings without editing. |
| `review-track-quality` | review | Quality Track | stable | `read-only` | Review the selected diff for clarity, naming and comments only and return changed-line findings without editing. |
| `review-track-security` | review | Security Track | stable | `read-only` | Review the selected diff for security and exposure risks only and return changed-line findings without editing. |
| `review-track-simplicity` | review | Simplicity Track | stable | `read-only` | Review the selected diff for minimalism and YAGNI only and return changed-line findings without editing. |
| `review-track-structure` | review | Structure Track | stable | `read-only` | Review the selected diff for layout, boundaries and documentation agreement only and return changed-line findings without editing. |
| `tabletop-lore-keeper` | tabletop | Lore Keeper | speculative | `doc-write` | Maintain the canonical world and character bible; reconcile new facts against it, record contradictions as findings and version every change. |
| `tabletop-prose-editor` | tabletop | Prose Editor | speculative | `doc-write` | Edit exported tabletop text for voice, clarity and consistency without changing canon; every content decision cites the world bible. |
| `tabletop-rules-designer` | tabletop | Rules Designer | speculative | `doc-write` | Design and balance mechanics and rule text with a stated design intent per rule, worked examples and edge cases. |
| `tabletop-scenario-writer` | tabletop | Scenario Writer | speculative | `doc-write` | Turn a stated premise into a playable scenario with explicit stakes, hooks, NPC motivations, an escalation ladder and ending conditions, consistent with the world bible. |
| `tabletop-worldbuilder` | tabletop | Worldbuilder | speculative | `doc-write` | Expand a setting's geography, factions, history and tone consistent with the world bible, flagging where canon is silent instead of inventing silently. |

## Selection matrix

Project planes (what each project selects now):

| Project | Plane |
|---|---|
| containeromat | ops, review, research, docs -- **no software-implementation roles** |
| seifomat | full engineering + design plane |
| pen-and-paper | research, docs, consistency, tabletop |
| network-architecture | network, research, review, council |
| general-research | research, synthesis, skeptic, docs |

Legend: **S** = select now; **C** = conditional, the project selects it only
after growing the relevant surface (for example an architecture project grows a
code diff before taking the code-diff review tracks; a repo grows a canonical doc
corpus before taking the consistency reviewer); **-** = not selected. The
`suggested_projects` frontmatter can list a broader set than a project's current
plane, so the matrix (not the frontmatter) is the selection authority.

| Template | containeromat | seifomat | pen-and-paper | network-architecture | general-research |
|---|---|---|---|---|---|
| `engineering-frontend-developer` | - | S | - | - | - |
| `engineering-backend-developer` | - | S | - | - | - |
| `engineering-api-developer` | - | S | - | - | - |
| `engineering-database-developer` | - | S | - | - | - |
| `engineering-test-author` | - | S | - | - | - |
| `engineering-explorer` | S | S | - | - | - |
| `engineering-oracle` | S | S | - | - | - |
| `engineering-fixer` | - | S | - | - | - |
| `design-ui-reviewer` | - | S | - | - | - |
| `documentation-doc-writer` | S | S | S | C | S |
| `networking-network-architect` | S | C | - | S | - |
| `operations-ci-implementer` | S | - | - | - | - |
| `operations-executor` | S | S | - | - | - |
| `operations-format-normalizer` | S | S | - | - | - |
| `orchestration-orchestrator` | S | S | S | S | S |
| `orchestration-councillor` | S | S | S | S | S |
| `orchestration-council-synthesizer` | S | S | S | S | S |
| `research-librarian` | S | S | S | S | S |
| `research-researcher` | S | S | S | S | S |
| `research-research-merger` | S | S | S | S | S |
| `review-code-skeptic` | S | S | - | C | S |
| `review-consistency-reviewer` | C | C | S | C | S |
| `review-reviewer` | S | S | - | S | - |
| `review-review-lead` | S | S | - | S | - |
| `review-security-reviewer` | S | S | - | S | - |
| `review-track-correctness` | S | S | - | C | - |
| `review-track-dead-code` | S | S | - | C | - |
| `review-track-deploy-safety` | S | S | - | C | - |
| `review-track-duplication` | S | S | - | C | - |
| `review-track-quality` | S | S | - | C | - |
| `review-track-security` | S | S | - | C | - |
| `review-track-simplicity` | S | S | - | C | - |
| `review-track-structure` | S | S | - | C | - |
| `tabletop-lore-keeper` | - | - | S | - | C |
| `tabletop-prose-editor` | - | - | S | - | C |
| `tabletop-rules-designer` | - | - | S | - | C |
| `tabletop-scenario-writer` | - | - | S | - | C |
| `tabletop-worldbuilder` | - | - | S | - | C |

## Instantiation example

`engineering-frontend-developer` is the calibration template. Its declared slots
are `required_slots: [PROJECT_ID, PROJECT_RULES, VERIFICATION_COMMANDS,
ACCESSIBILITY_STANDARD, MUTATION_POLICY, SAFETY_RULE, HANDOFF_TARGETS]` and
`optional_slots: [MODEL_HINT]`. Instantiation replaces every `{{TOKEN}}`; the
`<doctrine>` and `<conduct>` blocks are copied byte-exact from `fragments/` and
are never filled. A filled `<hard_rules>` block for seifomat:

```markdown
<hard_rules>
- Work only in the seifomat workspace; if the workspace is not seifomat,
  report and stop.
- Read docs/rules/ and the WCAG 2.2 AA checklist before applying any cited
  rule; project rules > framework best practice > model memory.
- Edit only src/**: implement the approved spec as the smallest change in the
  project's styling system; reuse existing primitives and tokens, and add no new
  dependency and no speculative refactor.
- Never echo secrets; never commit, push or deploy.
- If the change exceeds ~3 files / ~50 net lines, or the spec or acceptance
  criteria are ambiguous, emit BLOCKED with at most three questions; refine once
  before escalating. No counters.
</hard_rules>
```

Register the result with the pinned `template_version` (`2.0.4`) and
`fragment_versions` (`doctrine: 1.5.0`, `conduct: 1.1.0`) so the consumer-side
drift check in `docs/SYNC.md` can detect a fragment bump.

## Version pins

- Library: 2.12.0
- Role templates: 38
- Task prompts: 3
- Template: 2.0.4
- Orchestrator template: 2.4.0
- Doctrine: 1.5.0
- Conduct: 1.1.0
- Long-horizon: 1.2.0
- Cache policy: 1.1.0
- Tool-set: 1.0.0
- Run journal: `agent-run-journal/1`
- Prompt assembly: AS-01..AS-14

## Deferred (recorded, not forgotten)

- **Skills migration wave 2.** Moving the remaining consumer-canon skills into
  this library is not blocked by a registry rule: the one-canon rule in the
  consumer's `skills-roots.json` is about its LOCAL canon, and this library is
  already the external canon of the 24 names registered in the consumer's
  `scripts/skills-library.json` (WP-05 closed 2026-10-27, no schema change).
  What remains is content work per skill -- generalize the body, add the catalog
  row, register it, re-vendor, then drop the consumer's local canon row -- with
  a paired baseline before any body change. Until then the catalog references
  them in place.
- **Live deployment and validation.** Agent-template adoption is complete:
  containeromat authors `agents/` and renders `.kilo/agents` and the Paseo ports
  from `packs/containeromat/agents.yaml`; doctrine/conduct and the 24 library
  skills are re-vendored at `agent-prompts` `b1ea951` (library 2.6.0 at that pin). What
  remains is the operator deployment (Kilo reload / Paseo rebuild) and live
  harness/A-B validation, not a library migration. The mapping and structural
  audit are in `packs/containeromat.md` (`tooling/check_instantiation.py`).
- **Coder single-project mode (`CODER_HOST_DIR`).** A runtime deploy decision
  owned by the operator and orthogonal to the library: per-workspace `.kilo/`
  works in both mount modes, so the catalog does not depend on the choice.
