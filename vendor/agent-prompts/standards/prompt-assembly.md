# Prompt assembly standard (AS-01..AS-14)

Status: ACTIVE (2026-10-25). Applies to any consumer that builds a system
prompt, user turn, skill load, reference load, or cache breakpoint.

Evidence: `evidence/prompt-research-2026-10.md` (S5, S16, S26) and
`evidence/prompt-cache-2026-10.md` (T1..T14). The cache profile table is
`cache-profiles.json` (1.0.0); the deterministic checker is
`../tooling/check_token_efficiency.py`.

## AS-01 -- Static system message

The system message carries role, hard rules, doctrine, workflow, conduct, and
the output contract. It is identical across requests for the whole run: no
timestamps, no task text, no file contents, no per-request paths.

## AS-02 -- Dynamic context in the user turn

Task context, retrieved files, tickets, and environment facts go in the user
turn (or a tool result), never prepended to the system prompt. This keeps the
static prefix stable and makes the untrusted boundary explicit.

## AS-03 -- Skills load as their own message

A triggered skill body is delivered as a separate message or tool result, not
concatenated into the system prefix. Concatenation makes every distinct skill
selection a new prefix and defeats prefix caching.

## AS-04 -- References load only after routing

A reference file is loaded only when the skill body routes to it for the current
decision. Do not preload every reference "for completeness".

## AS-05 -- Breakpoint on the last stable block

Place the cache breakpoint on the last block that is identical across requests.
Use at most four breakpoints, ordered from most stable to least. A breakpoint on
a block containing a timestamp or per-request context never hits; a breakpoint
on a volatile layer is an assembly defect, not a cache miss. A declared
breakpoint must sit on a cumulative prefix above the model minimum (AS-09).
Measure the hit rate; the default five-minute TTL only helps back-to-back turns
(T1, T2).

## AS-06 -- Stable tools and ordering

Keep tool definitions and their ordering stable across turns. Tools sit ahead
of the system message and messages in the cache hierarchy, so a change to a
tool name, description, or parameter invalidates the entire cache (T1, T2).
Disable a tool with a stable mask (`tool_choice`, `allowed_tools`, or deferred
loading) instead of deleting or reordering its definition. A definition change
is a new tool-set version and a new prompt version (T1, T2, T7).

## AS-07 -- Untrusted data stays data

Mark retrieved or user-supplied content as data, not instructions, at the
boundary where it enters. Never put secrets in the static message or the skill
body; use placeholder names.

## AS-08 -- Measure the assembly

Record cache read tokens, cache write tokens, the prefix hash, the breakpoint
count, the TTL class, and the first divergent layer. A hit-rate claim without a
measurement is an assumption. If the host exposes cache diagnostics, use them
to find the first divergent block (T1, T2, T7).

## AS-09 -- Minimum, TTL, and economics

Read the model minimum, write/read multipliers, and TTL from
`cache-profiles.json`, not from memory. A prefix below the minimum cannot cache;
mark that arm as measured below minimum rather than treating it as a defect. Do
not pad a prefix merely to reach the minimum: a one-use write costs more than
the uncached input, and a read must be expected before the write pays (T1, T2,
T4). Use the short TTL for back-to-back turns; choose the longer TTL only when
the expected gap between uses exceeds the short TTL and the reuse count covers
the write premium.

## AS-10 -- Layer order and the first divergent layer

Declare the cache layers as `tools -> system -> skills -> messages`. Each layer
has a stability class (`static`, `run`, `session`, `turn`, `volatile`), an
owner, and a hash. A change in an earlier layer invalidates every later layer.
When diagnosing a miss, name the first divergent layer, not just the file: the
first differing byte is the actionable cause (T1, T2, T7).

## AS-11 -- Deterministic serialization

Deterministic serialization: no timestamps, run ids, hostnames, current
working directory, environment interpolation, random ordering, or
dictionary-iteration order in a cached layer. Render volatile values in the user turn. Serialize tool definitions,
manifests, and generated lists in canonical order. A byte-identical logical
prompt must produce a byte-identical cached prefix (T2, T7).

## AS-12 -- Append-only history and re-versioned compaction

Never rewrite, reorder, delete, or "clean up" earlier turns. Correct by
appending; keep failed attempts and error text. Compaction or truncation starts
a new prefix version: record the reason, the token delta, and the hit-rate
delta, and revert it when the total cost rises even if the hit rate improves
(T2, T7, T11, T13). Compaction is owned by the long-horizon run layer; this rule
owns how the new prefix is versioned and measured.

## AS-13 -- Volatile and derived layers go last

Assemble the prompt so that every layer which changes without a code change sits
at the tail, in this order: static role and rules text, then team-editable
sections, then generated settings-derived blocks.

- A settings-derived block is regenerated from its source of truth on every
  model request and never persisted into the cached prefix.
- A settings save therefore invalidates only the tail, not the layers above it,
  and the breakpoint budget (AS-05) is spent on the stable boundary.
- A generator writes each derived line deterministically: one line per setting,
  canonical order, no counts that change on an unrelated save.
- Collapsing a derived block into the static text passes a cache miss to every
  request; it also makes a settings diff invisible in the prompt.
- Evidence: `../docs/knowledge-base/superagent-prototype-2026-11.md` (mechanism
  table M9: ordering and override provenance come from one runtime that ran it in
  production).

## AS-14 -- Override provenance and upgrade visibility

A consumer may override any prompt part. The override must record the default it
was derived from, so an upgrade can be shown rather than guessed.

- Store the override together with a `base` identity: the hash or version of the
  default text it was edited from.
- After an upgrade, compare `base` with the current default and mark the part
  `Default updated`. Offer exactly three outcomes: keep the consumer text, take
  the new default, or edit again. Never replace consumer text silently, and never
  freeze it silently either.
- An override byte-identical to its default is dropped, so the part follows
  future defaults.
- An editable template declares its required placeholders; a save that drops one
  is refused. Placeholders are substituted in one pass, so substituted text is
  never re-scanned for further placeholders.
- An override for a part the version no longer defines is refused unless the
  saved configuration already held it, in which case it is dropped on the next
  save and listed for the operator.

## Cross-refs

- `agent-prompt-standard.md` -- AP-02 block order, AP-09 U-shape
- `agent-context-files.md` -- repository router content
- `skill-system-standard.md` -- skill layers and routing
- `long-horizon-runs.md` -- when to compact a run (LH-06)
- `cache-profiles.json` -- minima, multipliers, TTLs, breakpoint budget
- `tool-set.md` -- TS-01..TS-10, canonical tool-set manifest
- `tool-set.schema.json` -- manifest shape
- `../tooling/check_token_efficiency.py` -- static prefix checks
- `../tooling/check_tool_set.py` -- manifest validator and hash updater
- `../evals/harness-telemetry.schema.json` -- runtime cache fields
- `evidence/prompt-research-2026-10.md` -- S5, S16, S26
- `evidence/prompt-cache-2026-10.md` -- T1..T14
