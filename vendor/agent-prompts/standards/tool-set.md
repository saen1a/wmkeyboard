# Tool-set stability standard (TS-01..TS-10)

Status: ACTIVE (2026-10-25). Applies to any consumer that exposes tools to an
agent: chat tool calls, MCP tools, shell/file tools, and deferred discovery.

Tool definitions sit at the head of the cache hierarchy (`tools -> system ->
messages`). A change to a name, description, parameter, or order invalidates the
tool, system, and message cache. This standard keeps the definition block stable
and moves availability changes into a mask (T1, T2, T7; AS-06).

Evidence: `evidence/prompt-cache-2026-10.md` (T1, T2, T7). Contract:
`tool-set.schema.json`. Checker: `../tooling/check_tool_set.py`. Example:
`../exemplars/tool-set-example.json`.

## TS-01 -- Inventory the wire payload

Before changing anything, capture the exact `tools` array the harness sends for
one role and one turn. Record name, description, input schema, handler, order,
enabled set, and deferred/MCP tools. Do not inventory from documentation; dump
the outbound request. If the harness cannot dump it, that is the first blocker.

## TS-02 -- One canonical manifest

The consumer owns one manifest per stable tool set. Shape:
`schema`, `version`, `mask_version`, `toolset_sha256`, `order`, `tools`,
`masks`. The manifest is the only source for the `tools` array.

- The `tools` array is the definition block, in final wire order.
- `order` must equal the tool names in that order.
- `masks.roles` selects tools per role, in manifest order, without duplicates.
- A deferred tool is still a definition in `tools` with `stability: deferred`;
  deferred definitions form a contiguous suffix of `order`.
- `masks.deferred` patterns must match a deferred tool (for example `mcp_*`).
  A pattern for a not-yet-defined tool is listed in
  `masks.deferred_unmatched` as an intentional future entry.
- A role-specific set is a separate manifest version, not a runtime mutation.
- A tool name may contain uppercase letters, digits, `_`, or `-` (wire names are
  preserved exactly); it starts with a letter.
- Validate with `python3 tooling/check_tool_set.py PATH`.

## TS-03 -- Hash definitions only

`toolset_sha256` is the SHA-256 of the canonical JSON of `tools` (keys sorted,
separators `,`/`:`, ASCII). It covers names, descriptions, input schemas,
handlers, stability, order, and the optional provider `wire` passthrough. It
does **not** cover masks, role names, or `mask_version`.

Update it only with `python3 tooling/check_tool_set.py PATH --update-hash` after
reviewing the definition diff. A mask-only change leaves the hash unchanged.

## TS-04 -- Fixed order, no mid-run mutation

Build the `tools` array once from the manifest and reuse it byte-for-byte for
the whole run.

- Never add, remove, rename, reorder, or edit a definition mid-run.
- Never inject a timestamp, run id, hostname, cwd, environment value, or
  per-request description into a definition.
- Serialize deterministically; do not rely on dictionary iteration order.
- A genuine definition change is a new `version`, a new hash, and a new cache
  epoch. It is not a hot patch.

## TS-05 -- Mask, do not remove

Availability changes use a mask, not a definition change:

- Masks are a client-side allow-list: the model may see the full stable
  definition block, and the harness rejects calls outside the role's list.
- Anthropic: `tool_choice` can force one tool or none; a multi-tool subset
  requires the client-side allow-list or a new tool-set version. Do not edit
  `tools`.
- OpenAI: prefer `allowed_tools`, `tool_choice: "none"`, or deferred loading;
  do not remove definitions.
- Where a provider only supports removal, treat the removal as a new tool-set
  version and accept the cache invalidation.
- Deferred/MCP tools append at the end as a stable block. Existing order never
  changes.

## TS-06 -- Per-role sets are separate and stable

If two roles need different tool definitions, give each role its own manifest
and `version`. Do not switch the definition set inside one run. Role selection
happens before the first turn, not between tool calls.

## TS-07 -- Version, pin, and cache epoch

- `version`: semver; bump on any definition change.
- `mask_version`: bump on a mask-only change; `toolset_sha256` stays.
- Pin the hash in the consumer and fail closed on a mismatch. Consumer CI should
  compare the current manifest with the previous one (`--previous`) and fail
  when the hash changes without a version bump. The library gate validates the
  current exemplar's shape and hash; it does not keep a previous consumer
  manifest.
- Record `tool_set_version` and `toolset_sha256` in the cache epoch. A change is
  a re-baseline, not a silent rollout.

## TS-08 -- Telemetry

The harness records, per turn, `cache.tool_set_version`,
`run.cache_epoch.toolset_sha256`, and the prefix hash. Group hit rate and cost
by tool-set version. A hit-rate cliff with an unchanged tool-set version points
at system/messages; a cliff with a changed hash points at the tool block.

## TS-09 -- Acceptance tests

The implementation is not done until all of these pass:

1. Two consecutive turns with the same model, manifest, and history produce the
   same prefix hash.
2. Reordering `order` fails `check_tool_set.py`.
3. Editing a description or schema fails until `--update-hash` and a version
   bump.
4. A mask-only change leaves `toolset_sha256` unchanged.
5. A mask naming an unknown tool fails.
6. A deferred pattern that matches nothing is recorded as intentional, not
   silently ignored.
7. The harness emits `tool_set_version` and `toolset_sha256` and they match the
   manifest.
8. A mid-run tool add/remove is rejected by the harness (or recorded as a new
   version and cache epoch).

## TS-10 -- Failure modes

- Rebuilding `tools` from a set/dict each turn (order drift).
- Injecting the date, request id, or environment into a description.
- Removing a tool to disable it (invalidates everything).
- Reordering deferred tools ahead of static tools.
- Bumping `mask_version` and claiming the tool-set hash changed.
- Editing a definition and not bumping `version`.
- Pulling MCP tools into the initial block instead of appending them.

## Agent runbook

Point an agent at this file and ask it to implement tool-set stability for one
harness. It must:

1. Dump the current wire `tools` array for one role; save it as evidence.
2. Create the manifest from that array; preserve exact strings and order.
3. Run `python3 tooling/check_tool_set.py PATH --update-hash`; for a release,
   also run `--previous OLD_MANIFEST` and require a version bump when the hash
   changed.
4. Wire the harness builder to read the manifest; no other `tools` source.
5. Implement mask/deferred handling without editing definitions.
6. Record `tool_set_version` and `toolset_sha256` in telemetry `/2`.
7. Add the eight acceptance tests from TS-09.
8. HALT and report if the harness cannot dump the payload, if a provider only
   supports removal, or if a mid-run mutation cannot be avoided.

## Cross-refs

- `prompt-assembly.md` -- AS-06 stable tools, AS-10 layer order
- `tool-set.schema.json` -- manifest shape
- `../tooling/check_tool_set.py` -- validator and hash updater
- `../exemplars/tool-set-example.json` -- worked manifest
- `../docs/knowledge-base/tool-set-stability.md` -- implementation guide
- `../skills/general/cache-aware-assembly/SKILL.md` -- diagnosis procedure
- `evidence/prompt-cache-2026-10.md` -- T1, T2, T7
