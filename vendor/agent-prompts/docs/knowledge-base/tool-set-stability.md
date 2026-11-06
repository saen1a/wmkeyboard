# Tool-set stability implementation guide (2026-10)

Status: implementation guide for `standards/tool-set.md` (TS-01..TS-10),
`standards/tool-set.schema.json`, and `tooling/check_tool_set.py`.

Use this when a harness needs cache-stable tool definitions. Point an agent at
this file and `standards/tool-set.md`; the agent can implement the consumer side
without re-deriving the design.

## Why this matters

Tool definitions are sent before the system message and the conversation. A
changed name, description, schema, or order invalidates the tool, system, and
message cache. That is the largest single cache loss in a tool-heavy agent.
Masking a tool is cheap; editing or removing it is not (T1, T2, T7).

## Current repository state

The library provides the contract, schema, checker, and example. It does not
own a live tool set; the consumer does. There is no tool manifest in this repo
beyond the example, and the harness telemetry `/2` fields are placeholders until
a harness emits them.

| Artifact | Purpose |
|---|---|
| `standards/tool-set.md` | Normative TS-01..TS-10 and the agent runbook |
| `standards/tool-set.schema.json` | Manifest shape |
| `tooling/check_tool_set.py` | Validator, canonical hash, `--update-hash` |
| `exemplars/tool-set-example.json` | Worked manifest with four tools |
| `evals/harness-telemetry.schema.json` `/2` | `tool_set_version`, `toolset_sha256` |

## Implementation sequence

1. **Dump the wire payload.** Add a one-line debug dump before the model call.
   Save the `tools` array and the request parameters (`tool_choice`, images,
   thinking, speed). Do not use the UI or docs as the source.
2. **Create the manifest.** Copy the definitions exactly, in wire order, into
   `tool-set.json`. Use `exemplars/tool-set-example.json` as the shape. Add
   `order`, `masks.roles`, and `masks.deferred`.
3. **Hash and validate.**
   `python3 tooling/check_tool_set.py tool-set.json --update-hash`, then
   `python3 tooling/check_tool_set.py tool-set.json`.
4. **Replace the builder.** The harness builds `tools` only from the manifest.
   Remove any other insertion, sorting, filtering, or per-request decoration.
5. **Implement masks.** Masks are a client-side allow-list; the definition
   block stays intact. Deferred tools are definitions with
   `stability: deferred`, appended as a contiguous suffix; `masks.deferred`
   patterns must match one, or be recorded in `masks.deferred_unmatched`.
   Where the provider only supports removal, record a new `version` and cache
   epoch instead of masking.
6. **Wire telemetry.** Emit `cache.tool_set_version`,
   `run.cache_epoch.toolset_sha256`, `cache.breakpoint`, `cache.prefix_hash`,
   and `usage.cache_read_tokens` / `cache_write_tokens`.
7. **Verify.** Run the eight acceptance tests in TS-09, then compare hit rate
   and total cost on the same model/harness/seed.

## Provider differences

| Provider | Stable definition block | Availability lever |
|---|---|---|
| Anthropic | `tools` array in fixed order | `tool_choice`; avoid editing `tools` |
| OpenAI | entire rendered prefix | `allowed_tools`, `tool_choice: "none"`, deferred loading |
| Gemini | prefix caching; large common content first | keep the tool block stable; do not reorder |
| DeepSeek | prefix matching | same stable block; per-model minimum |
| vLLM | block-hash prefix cache | stable serialized definitions; deterministic hash |

If the provider only supports removing a tool, the removal is a new tool-set
version. Masking is not available; accept the invalidation and record it.

## Migration from a dynamic tool builder

- Freeze the set for one run; do not discover tools between calls.
- If discovery is required, split into a stable "base tools" block and an
  appended "discovered tools" block. Never insert before the base.
- Convert enable/disable into a mask table keyed by role.
- Keep descriptions static; move version/date/host data into a tool result or
  the user turn.
- Run `check_tool_set.py` in CI. A hash change without a version bump is a
  failed release.

## Acceptance evidence

Record in the consumer ledger:

- manifest path and `version`;
- `toolset_sha256`;
- `mask_version`;
- the dump of the pre-change and post-change `tools` array;
- two-turn prefix hash equality;
- mask-only hash equality;
- telemetry sample with `tool_set_version` and `toolset_sha256`.

## Limits

- The library cannot enumerate a consumer's tools.
- The checker validates a manifest, not a live request; the harness must prove
  the wire payload matches.
- Provider cache behavior and TTL are runtime measurements, not static facts.
- Deferred/MCP discovery is the hardest case; if the provider reorders or
  injects discovered tools into the base block, treat it as a new version.
