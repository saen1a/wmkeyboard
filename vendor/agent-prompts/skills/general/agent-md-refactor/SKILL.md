---
name: agent-md-refactor
description: Refactor bloated AGENTS.md, CLAUDE.md, or similar agent instruction files to follow progressive disclosure principles. Use when a monolithic instruction file should be split into organized, linked documentation.
metadata:
  category: development
  source.repository: 'https://github.com/softaworks/agent-toolkit'
  source.path: skills/agent-md-refactor
  source.license_path: LICENSE
  source.commit: 3027f20f3181758385a1bb8c022d4041dfb4de84
triggers:
  - AGENTS.md
  - CLAUDE.md
  - agent instructions
  - refactor
---
<!-- Archetype copy imported from containeromat .openhands/skills/agent-md-refactor (pinned 2026-09-19). Adapted 2026-10-23: phase detail, templates, and examples moved to references/refactor-guide.md. -->

# Agent MD refactor

Refactor a bloated agent instruction file (`AGENTS.md`, `CLAUDE.md`,
`COPILOT.md`) so the root keeps only what applies to every task and the rest
lives in linked, categorized files. The root is always loaded, so every line
costs context on every task. "Keep everything in the root for safety" is not a
reason to skip the split; a small root plus routed files is the safe shape.

## Triggers

Use when the user says:

- "refactor my AGENTS.md" or "refactor my CLAUDE.md"
- "split my agent instructions" or "organize my CLAUDE.md"
- "my AGENTS.md is too long"
- "progressive disclosure for my instructions"
- "clean up my agent config"

## Quick reference

| Phase | Action | Output |
|---|---|---|
| 1. Analyze | Find contradictions | List of conflicts to resolve |
| 2. Extract | Identify essentials | Core instructions for the root |
| 3. Categorize | Group the rest | Logical categories |
| 4. Structure | Create the file hierarchy | Root plus linked files |
| 5. Prune | Flag for deletion | Redundant or vague instructions |

## Phase rules

1. **Find contradictions first.** Quote both instructions and ask which wins,
   or whether both are conditional. Ask the question and, in the same response,
   present the proposed split with the conflict marked unresolved; do not write
   files or silently choose a winner.
2. **Keep only universal content in the root.** One-sentence project
   description, non-standard package manager or commands, critical overrides,
   rules that apply to every task.
3. **Group the rest by topic.** Aim for 3-8 self-contained files such as
   `typescript.md`, `testing.md`, `code-style.md`, `git-workflow.md`,
   `architecture.md`. Each holds instructions scoped to its topic; flag vague
   rules rather than dropping them.
4. **Create the structure.** Move every source rule, including vague or
   redundant ones, into its linked file, then verify no instruction was dropped
   and show the source-to-destination mapping. A rule may be flagged for later
   deletion but must not be dropped during the move. Root file: description,
   commands, links. Treat 50
   lines as the tightening target; CF-04 allows up to 100-150 for a router that
   carries commands and pointers, so do not split a compliant router further.
   Each linked file starts with a one-line scope, rules, and examples.
5. **Flag for deletion; remove only with approval.** List redundant, vague,
   obvious, default-behavior, and outdated instructions with a reason. Do not
   delete anything until the owner approves the specific list; a blanket
   "delete anything vague" is not approval for a specific removal.

The detailed phase steps, root and linked-file templates, deletion criteria,
and the before/after example are in
[references/refactor-guide.md](references/refactor-guide.md). Read it when
creating the structure or deciding what to delete.

## Execution checklist

```text
[ ] Phase 1: all contradictions identified and resolved
[ ] Phase 2: root contains only essentials
[ ] Phase 3: remaining instructions categorized
[ ] Phase 4: root plus linked files created, links work
[ ] Phase 5: deletion list approved before any removal
[ ] Verify: each linked file is self-contained
[ ] Verify: root is at or below the CF-04 target (50 if tightening, 100-150 for a router)
[ ] Verify: no instruction was lost unless flagged
```

## Anti-patterns

| Avoid | Why | Instead |
|---|---|---|
| Keeping everything in the root | Bloated, hard to maintain | Split into linked files |
| Too many categories | Fragmentation | Consolidate related topics |
| Vague instructions | Wastes tokens, no value | Be specific or flag for deletion |
| Duplicating defaults | The agent already knows | Override only when needed |
| Deep nesting | Hard to navigate | Flat structure with links |

## Verification

- The root is at or below the CF-04 target (50 if tightening; 100-150 for a
  router) and contains only universal information.
- Every link resolves and every linked file is self-contained.
- No contradictions remain; no instruction was lost unless flagged.
- Every instruction is actionable or explicitly approved for removal.

## Doctrine position

Serves Implement for documentation refactors: the split and the links are the
Implement action, and the reference/nav gates are Verify. Push stays with the
operator.

## References

Shipped with the canon copy on the next consumer re-vendor:

- [references/refactor-guide.md](references/refactor-guide.md) -- phase detail,
  templates, deletion criteria, before/after example; read before restructuring
