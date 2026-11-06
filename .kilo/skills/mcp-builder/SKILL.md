---
name: mcp-builder
description: >-
  Guide for creating high-quality MCP (Model Context Protocol) servers that
  enable LLMs to interact with external services through well-designed tools.
  Use when building MCP servers to integrate external APIs or services, whether
  in Python (FastMCP) or Node/TypeScript (MCP SDK).
metadata:
  category: development
  source.repository: 'https://github.com/ComposioHQ/awesome-claude-skills'
  source.path: mcp-builder
  source.license_path: mcp-builder/LICENSE.txt
  source.commit: 92568c1edaff1bde5371154f036d959346c145a8
triggers:
  - mcp
  - model context protocol
  - mcp server
---
<!-- Archetype copy imported from containeromat .openhands/skills/mcp-builder (pinned 2026-09-19). Adapted 2026-10-23: phase detail and documentation library moved to reference/workflow.md. -->

# MCP server development guide

An MCP server is a tool surface for an agent, not an API wrapper. Design the
smallest set of tools that lets an agent complete a real task, with typed
schemas and errors that teach the next call.

## When to use

| Use this skill when... | Do not use it when... |
|---|---|
| Building an MCP server in Python or TypeScript | Calling an existing MCP server |
| Exposing an API or service as agent tools | Changing an unrelated application server |
| Reviewing tool descriptions, schemas, or pagination | Writing protocol transport code the SDK owns |
| Creating an evaluation set for a server | A one-off script with no agent consumer |

## Workflow

| Phase | Action | Output |
|---|---|---|
| 1. Research | Understand the workflows, tools, and limits | Tool list with what/when and schemas |
| 2. Implement | Shared utilities, then tools with typed schemas | Working server |
| 3. Review | DRY, errors, types, build, safe test | Build plus an exercised call |
| 4. Evaluate | 10 independent, read-only, verifiable questions | XML evaluation file |

Detailed steps, examples, and the documentation library are in
[reference/workflow.md](reference/workflow.md). Read it at the start of Phase 1,
then load the language guide before writing code.

## Implementation rules

**Design rules:**

- Build for workflows, not endpoints: a tool may combine a check and an action.
- Count the context cost: every tool definition is sent on every request, so add
  a tool only when a workflow needs it.
- Optimize for limited context: return high-signal fields, offer concise/detailed
  formats, and prefer names over opaque ids.
- Make errors actionable: say what to try next, not only what failed.
- Follow natural task boundaries; do not split one task across five tools.
- Use the SDK's transport and lifecycle; do not re-implement them.

**Implementation rules:**

- Python: MCP SDK, Pydantic v2 models, type hints, async I/O.
- TypeScript: MCP SDK, Zod schemas, strict mode, no `any`, explicit `Promise<T>`.
- Every tool needs a what + when description, a typed input schema, a return
  schema, and documented errors.
- Errors return a stable shape: code, message, and next action.
- Add tool annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`,
  `openWorldHint`) where the protocol supports them.
- Respect pagination and character limits; truncate with a clear signal.

**Trust boundaries (a server is an instruction channel):**

- Pin the definition hash and re-approve on change; a description edit that
  grants scope after approval is a rug pull (PS-04).
- Sampling and elicitation ask the user; a silent approval handler is a defect
  (PS-08). Secrets by `${VAR}`, grants scoped to a path or host, no
  unauthenticated `0.0.0.0` bind (PS-09).
- Low-privilege text stored and later returned inside a prompt or a tool
  description crosses a boundary: sanitize at write and read (PS-05).

## Common Rationalizations

| Rationalization | Why it is wrong |
|---|---|
| "More tools means more capable" | Tool sprawl bloats every request; ship the smallest useful surface. |
| "The description can be vague" | The model selects tools by description; a vague one is never called correctly. |
| "Validation is optional" | An unvalidated server ships broken tools; test the initialize and call path. |
| "Any SDK shape will do" | Follow the documented SDK for the target language; shortcuts break clients. |

## Red Flags

- A tool returns free-form text instead of structured data.
- Tool descriptions do not say when to use them.
- No test exercises tool discovery and a real call.
- A long-running stdio server is started directly in the foreground shell.
- The server re-implements transport concerns the SDK owns.

## Verification

- The initialize handshake and at least one tool call are exercised.
- A stdio server is tested through the evaluation harness, tmux, or a timeout,
  never by blocking the main shell.
- Each tool has a what + when description and a typed schema.
- When arguing for fewer tools, state the per-request context cost of every
  definition, not only the selection risk.
- The language guide's quality checklist was read before writing code.
- The evaluation set has 10 independent, read-only, verifiable questions.
- The definition hash is pinned, one sampling/elicitation request was observed
  asking the user, and the config carries no literal secret and no unscoped
  grant (PS-04, PS-08, PS-09).

## Doctrine position

Serves Implement and Verify for an MCP server: the tool/schema work is
Implement, and the initialize plus real-call test is Verify. Review consumes the
protocol check; Push stays with the operator.

## References

Shipped with the canon copy on the next consumer re-vendor:

- [reference/workflow.md](reference/workflow.md) -- phase detail and the
  documentation library; read at Phase 1
- [reference/mcp_best_practices.md](reference/mcp_best_practices.md) -- naming,
  response formats, pagination, limits, security; read during Phase 1 research
- [reference/python_mcp_server.md](reference/python_mcp_server.md) and
  [reference/node_mcp_server.md](reference/node_mcp_server.md) -- load the
  matching language guide before implementation
- [reference/evaluation.md](reference/evaluation.md) -- load at Phase 4
- `standards/prompt-security.md` -- PS-04 tool metadata, PS-05 privilege
  asymmetry, PS-08 approval, PS-09 configuration
