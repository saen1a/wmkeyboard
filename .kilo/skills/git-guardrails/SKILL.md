---
name: git-guardrails
description: >-
  Prevent destructive git operations by blocking dangerous commands before
  they execute. Blocks: git push, git reset --hard, git clean, git branch -D,
  git checkout ., git restore .. Use when an agent might accidentally run
  destructive git commands.
rigid: true
---
<!-- Archetype copy imported from containeromat .openhands/skills/shared/git-guardrails (pinned 2026-09-19). Canon switch deferred; see PLAN.md wave 2. -->
# Source: https://github.com/mattpocock/skills (skills/misc/git-guardrails-claude-code)
# Vendored: 2026-07-15
# Note: Original skill uses Claude Code PreToolUse hooks. For non-Claude Code
# agents (Kilo, Cursor, etc.), this skill serves as a declarative guardrail
# instruction -- the agent MUST refuse to run these commands without explicit
# operator confirmation.


# Git Guardrails

Protects the repository by blocking destructive git operations.

## What Gets Blocked

The following git commands **MUST NOT** be executed without explicit operator confirmation:

- `git push` (all variants including `--force`, `--force-with-lease`)
- `git reset --hard`
- `git clean -f` / `git clean -fd`
- `git branch -D` (force-delete branch)
- `git checkout .` / `git restore .` (discard all working-tree changes)

## When Blocked Commands Are Needed

If the operator explicitly requests a blocked command, repeat the request back verbatim and ask for confirmation. Only proceed after receiving explicit `yes` / `go` / `confirmed`. Describe the blocked operation, but do not emit a copy-pasteable command, even in backticks or a code block, before confirmation.

Before asking for confirmation, propose the non-destructive first step: inspect
the state, stash or branch a backup, or dry-run the operation. For `reset
--hard`, propose `revert` or a backup branch; for `clean -fdx`, propose a dry
run or `stash -u`; for a history rewrite, propose `revert` or a backup branch.

## Why

One mistaken `push --force` or `reset --hard` can destroy work or rewrite remote history. This skill is a safety net, not a workflow obstacle.

## Integration Note

Some hosts enforce this with a pre-tool-use hook; others rely on the agent
reading this skill. Do not assume a hook exists or that the host will catch the
command. The agent self-enforces by refusing blocked commands until the
operator confirms.

## Common Rationalizations

| Rationalization | Why it's wrong |
|---|---|
| "The change is safe, I'll force-push" | The guardrail blocks destructive git without explicit operator confirmation, regardless of confidence. |
| "git clean is just cleanup" | `git clean` deletes untracked work irrecoverably. |
| "reset --hard is faster than revert" | It discards work and history; revert preserves both. |
| "The hook will catch it" | Non-Claude agents have no hook; this skill is the guardrail. |


## Red Flags

- You are about to run `git push`, `git reset --hard`, `git clean`, `git branch -D`, `git checkout .` or `git restore .`.
- You have no explicit operator confirmation for the destructive command.
- You are relying on a runtime hook that does not exist for this agent.


## Verification

- No destructive git command ran without recorded operator confirmation.
- History-preserving alternatives (revert, branch) were used where possible.

## Doctrine position

Serves the Implement/Push boundary: it blocks destructive git (`git push`,
`reset --hard`, `clean`, `branch -D`, `checkout .`, `restore .`) before they run,
and every blocked action escalates to the operator as the Push gate.
