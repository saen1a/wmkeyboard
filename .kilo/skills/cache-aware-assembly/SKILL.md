---
name: cache-aware-assembly
description: Use when prompt-cache hit rate drops or token cost rises - diagnosing a cache miss, checking whether a system prefix is stable, choosing a cache TTL or breakpoint, or reducing tokens without invalidating reuse.
rigid: true
---
<!-- Repo-authored 2026-10-25. Canon: this file. Rules: standards/prompt-assembly.md AS-01..AS-14. -->

# Cache-aware assembly

A cache miss is usually an assembly change, not a model change. Find the first
byte that differs; do not rewrite the prompt until you have named it.

## Module 1 - Decision gate

Use this when a measured cache hit rate falls, a deploy raises token cost, or an
edit will change the static prefix, tool definitions, or breakpoint placement.
Also use it before choosing a TTL or adding a tool.

Hand off instead when the task is:

- authoring or numbering one role prompt: `standards/agent-prompt-standard.md`;
- when to compact a long run: `long-horizon-run` (LH-06);
- long-context attention layout: `deepseek-v4-agent-defense`;
- retiring the old assembly: `anti-entropy-governance`;
- proving a fix: `verification-before-completion`.

A one-shot prompt with no reuse expectation is not a cache problem.

## Module 2 - Procedure

1. Run `python3 tooling/check_token_efficiency.py` and
   `python3 tooling/check_harness_telemetry.py` on a representative record.
2. Name the first divergent layer: `tools`, `system`, `skills`, or `messages`
   (AS-10). A later file change is a symptom, not the cause.
3. Classify the cause:
   - a volatile byte in a cached layer (date, run id, host, cwd, random order);
   - tool definitions added, removed, renamed, or reordered;
   - an earlier message edited, reordered, or deleted;
   - a prefix below the model minimum, or a breakpoint on the volatile tail;
   - a TTL shorter than the gap between uses.
4. Apply the smallest fix: move the byte to the user turn, mask the tool instead
   of removing it, append a correction instead of editing history, move the
   breakpoint to the last stable block, or choose the TTL from
   `standards/cache-profiles.json`.
5. Re-version the cache epoch (model, harness, toolset hash, doctrine version)
   and record the first divergent layer in the telemetry.
   For a tool definition change, follow `standards/tool-set.md` and validate the
   manifest with `tooling/check_tool_set.py`.

Do not compress the static prefix to save tokens; compression changes the prefix
on every call and can cost more than it saves (AS-09, AS-12).

## Module 3 - Verification and failure

Compare hit rate **and** total cost before and after on the same model, harness,
and seed. A higher hit rate with a higher total cost is a regression; a lower
hit rate can still be a win when fewer input tokens are sent (AS-08, AS-12).

Stop and escalate when:

- the provider dashboard says caching is on but the records have no cache read
  or write fields;
- the prefix is below the model minimum and padding is the only proposed fix;
- the only "fix" is to shorten the TTL or delete history;
- the cache epoch changed without a prompt-version record.

Failure modes: caching a one-shot prefix, padding to reach the minimum, editing
history to "clean up", trusting a dashboard flag, and tuning hit rate while
ignoring cost per verified task.

## Doctrine position

Cache work sits inside Plan and Verify; it does not add a phase. Plan names the
expected reuse and cache epoch; Implement keeps the static prefix and tools
stable; Review checks the prefix hash and first divergent layer; Verify compares
hit rate and total cost on the same harness. Push records the cache profile and
the measured delta. The orchestrator owns the assembly decision; a subagent
returns the measurement, not a rewritten prefix.
