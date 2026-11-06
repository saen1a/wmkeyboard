---
name: jq-json-processing
description: >-
  Query, filter, and transform JSON with jq. Use when parsing JSON files or HTTP
  responses, filtering arrays or objects, extracting nested fields, reshaping
  output, or debugging a jq expression in a shell pipeline.
allowed-tools: 'Bash(jq *), Bash(cat *), Read, Write, Edit, Grep, Glob'
metadata:
  upstream.user-invocable: 'false'
  upstream.model: sonnet
  category: data
  source.repository: 'https://github.com/laurigates/claude-plugins'
  source.path: tools-plugin/skills/jq-json-processing
  source.license_path: LICENSE
  source.commit: 6b5be230ee9a5a002b97094715f2ca877b08ad15
triggers:
  - jq
  - json
  - filter
  - parse json
---
<!-- Archetype copy imported from containeromat .openhands/skills/jq-json-processing (pinned 2026-09-19). Adapted 2026-10-23: long-form recipes moved to references/recipes.md. -->

# jq JSON processing

jq is a streaming JSON processor: input goes through a filter, and the filter's
output is the result. Build the expression in small steps, test it on a sample,
then put it in the pipeline.

## When to use

| Use jq when... | Use something else when... |
|---|---|
| Extracting or filtering fields from JSON | The file is YAML (use yq, or convert first) |
| Parsing `gh`, `curl`, or `kubectl -o json` output | The transform spans JSON, YAML, CSV, and TOML (use a scripting language) |
| One pipeline transform that fits in one expression | You need multi-step aggregation and visual exploration (use nushell or SQL) |
| The runtime is a minimal image where jq is installed | jq is not installed and cannot be added (use the language runtime) |
| A large file fits a stream or a targeted path | You need database-style queries over data larger than memory (use SQL/duckdb) |

## Core model

- `.` is the identity filter; `.field` accesses a key; `.[]` iterates an array
  or object; `.[0]` indexes an array.
- `|` pipes one filter's output into the next.
- `select(condition)` keeps values that pass; `map(f)` transforms each element;
  `{a, b}` builds an object; `[f]` collects into an array.
- `-r` emits raw strings, `-c` emits compact JSON, `-s` slurps inputs into an
  array, `--stream` streams large documents.
- A missing key yields `null`; indexing `null` with a field also yields `null`.
  The error is indexing a non-object (string, number, or array) with a field:
  use `.field?` to suppress it and `// empty` to drop nulls.

## Start here

| Task | Expression |
|---|---|
| Pretty-print | `jq '.' file.json` |
| Extract a field | `jq '.user.email' file.json` |
| Map an array | `jq '.items \| map(.name)' file.json` |
| Filter an array | `jq '.items[] \| select(.active)' file.json` |
| Build an object | `jq '{id, name: .full_name}' file.json` |
| Keys or values | `jq 'keys' file.json` |
| Raw or compact output | `jq -r '.message' file.json` or `jq -c '.' file.json` |
| Merge files | `jq -s '.[0] * .[1]' base.json override.json` |
| Group and count | `jq 'group_by(.status) \| map({status: .[0].status, count: length})' file.json` |
| Validate syntax | `jq empty file.json` |

For strings, conditions, recursion, reduce, CSV/TSV, logs, HTTP responses, and
batch integration, read
Read [references/recipes.md](references/recipes.md) when you need the full command catalog.

## Safety and failure handling

- Wrap the filter in single quotes so the shell does not expand `$`, `*`, or
  backticks.
- Never build a filter with unquoted user input; a filter is code. Pass values
  with `--arg` or `--argjson` and index dynamically: `jq --arg k "$KEY" '.[$k]'`.
- Prefer `jq empty` as a syntax check, then run the real filter on a small
  sample before a large file.
- When a field may be missing or null, use `// empty` to drop it; use `?` to
  suppress a type error when indexing a value that may not be an object.
- On a type error, print `jq 'type'` and `jq 'keys'` before changing the filter.

## Doctrine position

Serves Implement and Verify: turns JSON input into the requested shape and
checks the filter against a sample before it is used in a pipeline. It hands the
verified command to the caller and does not edit the input in place; it may
write a derived output file when the caller asks.

## References

Shipped with the canon copy on the next consumer re-vendor:

- [references/recipes.md](references/recipes.md) -- full command catalog,
  advanced patterns, integrations, troubleshooting, and quick reference
