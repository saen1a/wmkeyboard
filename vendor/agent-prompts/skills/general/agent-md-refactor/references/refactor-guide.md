# AGENTS.md refactor guide

Loaded from `SKILL.md` when executing the split. It carries the detailed phase
steps, root/linked-file templates, deletion criteria, and before/after examples.

## Contents

- Process
- Phase 1: find contradictions
- Phase 2: identify the essentials
- Phase 3: group the rest
- Phase 4: create the file structure (root and linked-file templates)
- Phase 5: flag for deletion
- Examples (before/after)

## Process

### Phase 1: Find Contradictions

Identify any instructions that conflict with each other.

**Look for:**
- Contradictory style guidelines (e.g., "use semicolons" vs "no semicolons")
- Conflicting workflow instructions
- Incompatible tool preferences
- Mutually exclusive patterns

**For each contradiction found:**
```markdown
## Contradiction Found

**Instruction A:** [quote]
**Instruction B:** [quote]

**Question:** Which should take precedence, or should both be conditional?
```

Ask the user to resolve before proceeding.

---

### Phase 2: Identify the Essentials

Extract ONLY what belongs in the root agent file. The root should be minimal - information that applies to **every single task**.

**Essential content (keep in root):**
| Category | Example |
|----------|---------|
| Project description | One sentence: "A React dashboard for analytics" |
| Package manager | Only if not npm (e.g., "Uses pnpm") |
| Non-standard commands | Custom build/test/typecheck commands |
| Critical overrides | Things that MUST override defaults |
| Universal rules | Applies to 100% of tasks |

**NOT essential (move to linked files):**
- Language-specific conventions
- Testing guidelines
- Code style details
- Framework patterns
- Documentation standards
- Git workflow details

---

### Phase 3: Group the Rest

Organize remaining instructions into logical categories.

**Common categories:**
| Category | Contents |
|----------|----------|
| `typescript.md` | TS conventions, type patterns, strict mode rules |
| `testing.md` | Test frameworks, coverage, mocking patterns |
| `code-style.md` | Formatting, naming, comments, structure |
| `git-workflow.md` | Commits, branches, PRs, reviews |
| `architecture.md` | Patterns, folder structure, dependencies |
| `api-design.md` | REST/GraphQL conventions, error handling |
| `security.md` | Auth patterns, input validation, secrets |
| `performance.md` | Optimization rules, caching, lazy loading |

**Grouping rules:**
1. Each file should be self-contained for its topic
2. Aim for 3-8 files (not too granular, not too broad)
3. Name files clearly: `{topic}.md`
4. Include only actionable instructions

---

### Phase 4: Create the File Structure

**Output structure:**
```
project-root/
|-- CLAUDE.md (or AGENTS.md)     # Minimal root with links
`-- .claude/                      # Or docs/agent-instructions/
    |-- typescript.md
    |-- testing.md
    |-- code-style.md
    |-- git-workflow.md
    `-- architecture.md
```

**Root file template:**

Keep the root small: description, commands, links. Fifty lines is the tightening
target; CF-04 allows 100-150 for a router carrying commands and pointers.

```markdown
# Project Name

One-sentence description of the project.

## Quick Reference

- **Package Manager:** pnpm
- **Build:** `pnpm build`
- **Test:** `pnpm test`
- **Typecheck:** `pnpm typecheck`

## Detailed Instructions

For specific guidelines, see:
- [TypeScript Conventions](.claude/typescript.md)
- [Testing Guidelines](.claude/testing.md)
- [Code Style](.claude/code-style.md)
- [Git Workflow](.claude/git-workflow.md)
- [Architecture Patterns](.claude/architecture.md)
```

**Each linked file template:**
```markdown
# {Topic} Guidelines

## Overview
Brief context for when these guidelines apply.

## Rules

### Rule Category 1
- Specific, actionable instruction
- Another specific instruction

### Rule Category 2
- Specific, actionable instruction

## Examples

### Good
\`\`\`typescript
// Example of correct pattern
\`\`\`

### Avoid
\`\`\`typescript
// Example of what not to do
\`\`\`
```

---

### Phase 5: Flag for Deletion

Identify instructions that should be removed entirely.

**Delete if:**
| Criterion | Example | Why Delete |
|-----------|---------|------------|
| Redundant | "Use TypeScript" (in a .ts project) | Agent already knows |
| Too vague | "Write clean code" | Not actionable |
| Overly obvious | "Don't introduce bugs" | Wastes context |
| Default behavior | "Use descriptive variable names" | Standard practice |
| Outdated | References deprecated APIs | No longer applies |

**Output format:**
```markdown
## Flagged for Deletion

| Instruction | Reason |
|-------------|--------|
| "Write clean, maintainable code" | Too vague to be actionable |
| "Use TypeScript" | Redundant - project is already TS |
| "Don't commit secrets" | Agent already knows this |
| "Follow best practices" | Meaningless without specifics |
```

---

## Examples

### Before (Bloated Root)
```markdown
# CLAUDE.md

This is a React project.

## Code Style
- Use 2 spaces
- Use semicolons
- Prefer const over let
- Use arrow functions
... (200 more lines)

## Testing
- Use Jest
- Coverage > 80%
... (100 more lines)

## TypeScript
- Enable strict mode
... (150 more lines)
```

### After (Progressive Disclosure)
```markdown
# CLAUDE.md

React dashboard for real-time analytics visualization.

## Commands
- `pnpm dev` - Start development server
- `pnpm test` - Run tests with coverage
- `pnpm build` - Production build

## Guidelines
- [Code Style](.claude/code-style.md)
- [Testing](.claude/testing.md)
- [TypeScript](.claude/typescript.md)
```

---

