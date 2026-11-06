# Harness telemetry contract (2026-10)

Status: v2. The harness should emit one record per turn in this shape. Schema
`/1` remains valid for old records; `/2` adds the cache-policy fields. The
library validates it; the harness owns collection.

Why: AS-08 requires a measured cache hit rate and SG-09 requires fast-path
escape data. Without one record shape, both claims stay unverifiable.

Schema: `evals/harness-telemetry.schema.json`.
Validator: `python3 tooling/check_harness_telemetry.py <record.json>`.

## v2 cache block

A `/2` record additionally carries:

```json
{
  "schema": "agent-prompts-harness/2",
  "cache": {
    "prefix_hash": "a1b2c3d4e5f60708",
    "breakpoints": 1,
    "ttl": "5m",
    "tool_set_version": "tools-2026-10-25",
    "min_tokens": 512,
    "layer_hashes": {"tools": "a1b2c3d4", "system": "e5f60718"},
    "compaction": {"reason": "long turn", "before_tokens": 12000,
                    "after_tokens": 4000, "hit_rate_before": 0.82,
                    "hit_rate_after": 0.61}
  },
  "usage": {
    "cache_read_tokens": 900,
    "cache_write_tokens": 120,
    "cache_write_ttl_class": "5m"
  }
}
```

`cache.prefix_hash` is the actual rendered prefix, not a hash of the prompt
template. `turn.first_divergent_layer` names the earliest layer that changed
(`tools`, `system`, `skills`, or `messages`). `run.cache_epoch` records the
model, harness, toolset hash, and doctrine version so a hit-rate cliff can be
attributed to a deploy.

## Record

```json
{
  "schema": "agent-prompts-harness/1",
  "run": {
    "model": "deepseek-flash",
    "provider": "deepseek",
    "harness": "codex-like/v1",
    "seed": 7,
    "timestamp_utc": "2026-10-23T12:00:00+00:00",
    "prompt_version": "agent-prompts@22b6d8b",
    "skill_versions": {"jq-json-processing": "sha256:..."}
  },
  "turn": {
    "gate": "fast-path",
    "gate_reasons": ["one-file comment edit with verification"],
    "files": 1,
    "lines": 1,
    "verification": {"command": "make test", "exit_code": 0}
  },
  "usage": {
    "input_tokens": 1283,
    "output_tokens": 1871,
    "reasoning_tokens": 1801,
    "cache_hit_tokens": 1149,
    "cache_miss_tokens": 134
  },
  "outcome": {
    "status": "pass",
    "escaped_defect": false,
    "operator_interventions": 0,
    "duration_ms": 4200
  }
}
```

## Fields

| Field | Meaning |
|---|---|
| `run.model` / `run.provider` | Exact ids, not a marketing tier |
| `run.harness` | Client/scaffold and version; a harness change is a re-baseline event (MC-03) |
| `run.seed` | Request seed, or null when unsupported |
| `run.prompt_version` | Library commit or release |
| `turn.gate` | `fast-path`, `full-stopp`, `halt`, or `none` |
| `turn.gate_reasons` | Classifier output; fast-path must have at least one |
| `turn.files` / `turn.lines` | Scope of the turn |
| `turn.verification` | Command and exit code; fast-path requires exit 0 |
| `usage.*` | Provider usage fields; cache hit + miss should sum to input where the provider reports it |
| `usage.cache_read_tokens` / `cache_write_tokens` | Normalized provider split (`/2` requires them); never infer one from the other |
| `cache.prefix_hash` | Actual rendered prefix hash; compare it, not the template hash |
| `cache.breakpoints` / `cache.ttl` / `cache.tool_set_version` | Breakpoint budget (0-4), TTL class, and versioned tool set |
| `turn.first_divergent_layer` | Earliest layer that changed; the actionable cause of a miss |
| `run.cache_epoch` | Model + harness + toolset hash + doctrine version; a change is a re-baseline |
| `cache.compaction` | Reason, before/after tokens, hit-rate before/after; revert when cost rises |
| `outcome.status` | `pass`, `fail`, `halted`, or `error` |
| `outcome.escaped_defect` | Post-hoc: a defect that reached the user |
| `outcome.operator_interventions` | Count of human approvals/answers |
| `outcome.duration_ms` | Wall clock |

## Gate consistency rules

- `fast-path` requires exactly one file, a non-empty verification command, exit
  code 0, and at least one reason.
- `halt` requires `outcome.status = halted`; `halted` requires the halt gate.
- Unknown or missing values fail the validator; do not default them to zero.

## How this closes the open claims

- **Cache (AS-08):** group records by `run.prompt_version` and gate; hit rate =
  `cache_hit_tokens / (cache_hit_tokens + cache_miss_tokens)`. The Wave 9
  baseline already shows 82.4% on the skill arm and 0% on the short no-skill
  arm (below the cache minimum).
- **Fast path (SG-09):** group by `turn.gate`; compare
  `outcome.escaped_defect` and verification failures for `fast-path` vs
  `full-stopp`. Promote the pilot only if fast-path does not increase escapes.
- **Role/body changes:** compare `prompt_version` groups; that is the
  old-vs-new refactor test.

## Rules

1. One record per turn, not per session.
2. Emit even on failure and halt; a failed turn is data.
3. Never put secrets, prompts, or file contents in the record.
4. Validate before uploading; the schema is intentionally closed.
5. Do not aggregate in the harness; emit raw records and analyze offline.
