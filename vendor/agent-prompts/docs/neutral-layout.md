# Neutral agent and prompt layout (2026-10-24)

## What is common practice

There is no single ratified directory standard for agent definitions yet, but
the stable pieces are:

- **`AGENTS.md` at the repository root** is the vendor-neutral instruction
  file. It is read by Codex, Copilot, Cursor, Windsurf, Amp, Devin, and others;
  it is stewarded by the Linux Foundation's Agentic AI Foundation. This
  is the closest thing to a proven cross-vendor convention.
- **`agents/` and `prompts/`** are the common visible names when a project
  externalizes agent definitions and prompt assets. They are plain, greppable,
  and not tied to a vendor.
- **`skills/`** is the common name for on-demand skill packages (Anthropic
  Agent Skills and compatible tools).
- **`.agents/`** is an emerging open directory convention that groups
  `AGENTS.md`, agents, skills, tasks, MCP config, and model presets in one
  hidden directory. It is a useful compatibility target, but it is still a
  draft proposal, not a settled standard.
- **Vendor directories** (`.kilo/`, `.claude/`, `.cursor/`, `.github/`) are
  adapters. They should be generated from, or checked against, the neutral
  source, not treated as the source itself.

## Recommended neutral layout

For a project that consumes this library:

```text
AGENTS.md              # vendor-neutral router
agents/                # agent/role definitions
prompts/               # task and workspace prompts
skills/                # on-demand skill packages
standards/             # normative rules
fragments/             # byte-exact shared blocks
commands/              # slash-command dispatchers
evals/                 # fixtures and result manifests
```

Vendor adapters map into it:

| Vendor surface | Neutral target | Direction |
|---|---|---|
| `.kilo/agents/*.md` | `agents/` | generated or checked against `agents/` |
| `.kilo/prompts/*.md` | `prompts/` | generated or checked against `prompts/` |
| `.kilo/command/*.md` | `commands/` | generated or checked against `commands/` |
| `.openhands/skills/**` | `skills/` | canonical in `skills/`, copied to the consumer |
| `.claude/agents/`, `.cursor/rules/` | `agents/` / `standards/` | generated adapters |

## Current library state

The migration is executed in 2.0.0:

| Current | Status |
|---|---|
| `agents/<domain>/` | canonical agent definitions |
| `prompts/tasks/` | canonical task prompts |
| `prompts/workspace/` | canonical workspace prompts |
| `roles/`, `tasks/`, `workspace-prompts/` | removed in 2.0.0; use the new roots |
| `skills/`, `standards/`, `commands/`, `fragments/` | neutral, unchanged |
| `dsh/` | parameterized DSH adapter templates; not neutral canon |
| `packs/` | project adoption records; not neutral canon |
| `evals/`, `exemplars/`, `provenance/` | evaluation, reference, and migration records; not runtime canon |

The neutral canon is the role, prompt, skill, standard, fragment, and command
layer. `dsh/`, `packs/`, and the evaluation/provenance records are adapters or
evidence; they are never instantiated as roles.

The rename is a **major-version migration**; 2.0.0 implements the new roots
and removed the legacy shims. The concrete inventory and follow-up steps are in
[neutral-layout-migration.md](knowledge-base/neutral-layout-migration.md).

The immediate neutral layer is therefore:

1. root `AGENTS.md` as the router;
2. the documented `agents/` + `prompts/` target;
3. `agents/`, `prompts/tasks/`, and `prompts/workspace/` as the only canonical
   roots; the old paths were removed in 2.0.0.

## Why not `.agents/` as the only source

`.agents/` is a good compatibility target, but:

- it is a draft convention, not a ratified standard;
- hidden directories are harder to review and discover;
- this library already has a visible, reviewable layout;
- a single hidden directory would still need vendor adapters.

Use `.agents/` only if a consumer tool requires it; generate it from the
visible neutral layout.

## Evidence

- `AGENTS.md` standard and Linux Foundation stewardship: https://agents.md/
- `.agents` protocol draft: https://dotagentsprotocol.com/
- `AGENTS.md` adoption and hierarchy: https://agentprotocol.ai/agents-md/
- Existing evidence register S13-S15 and S23 in
  `standards/evidence/prompt-research-2026-10.md`.
