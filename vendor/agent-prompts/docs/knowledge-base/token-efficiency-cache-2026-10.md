# Token efficiency and prompt-cache hit rate (2026-10)

Status: design record for `standards/prompt-assembly.md` AS-09..AS-12,
`standards/cache-profiles.json` 1.0.0, and
`tooling/check_token_efficiency.py`. Evidence:
`standards/evidence/prompt-cache-2026-10.md` (T1..T14).

## 1. The problem

Agent prompts are prefix-heavy: the system message, tool definitions, and prior
turns are re-sent on every call. The provider caches a prefix only when the
earlier bytes are identical; a timestamp, a reordered tool, an edited message,
or a model switch invalidates from that point forward (T1, T2, T7). Token
efficiency and cache reuse are therefore the same design problem: keep the
stable part stable, keep the dynamic part late, and measure cost rather than
worshipping a hit rate.

The literature and vendor docs agree on the mechanism:

- static tools and instructions first, dynamic task context last (T1, T2, T3);
- append-only history, deterministic serialization, no timestamps in the
  prefix (T7);
- mask tools instead of removing or reordering them (T1, T2, T7);
- progressive disclosure and restorable file-path memory over irreversible
  compression (T7, T11, T13);
- cache writes cost more than base input and reads cost less, so a one-shot
  prefix is a loss and a below-minimum prefix never caches (T1, T2, T4).

## 2. Current library before this change

| Area | Before | Gap |
|---|---|---|
| Assembly rules | AS-01..AS-08: static system, dynamic user turn, skill/reference loading, breakpoint on last stable block, stable tools | No minimum/TTL table, no layer hash/first divergent layer, no deterministic-serialization rule, no append-only/compaction rule |
| Cache data | No machine-readable profile | Minima, multipliers, and TTLs lived in prose only |
| Static checks | Template token budgets, fragment hashes, skill shape | No volatile-byte scan, no duplicate-instruction scan, no cache-policy pin |
| Telemetry | `cache_hit_tokens` / `cache_miss_tokens` only | No read/write split, TTL class, prefix hash, cache epoch, or compaction record |
| Skills | No cache-specific operating procedure | Agents had to infer the diagnosis |

## 3. What was implemented

| Artifact | Purpose |
|---|---|
| `standards/prompt-assembly.md` AS-09..AS-12 | Prefix minimum and TTL economics, layer order + first divergent layer, deterministic serialization, append-only history and re-versioned compaction |
| `standards/cache-profiles.json` 1.0.0 | Dated minima, write/read multipliers, TTLs, and the four-breakpoint budget |
| `tooling/check_token_efficiency.py` | Static volatile scan, duplicate-instruction scan, prefix token report, AS-rule body anchors, profile/pin checks, non-vendor skill cap |
| `evals/harness-telemetry.schema.json` / `/2` | Cache prefix hash, breakpoint count, TTL, tool-set version, cache epoch, read/write tokens, first divergent layer, compaction record |
| `skills/general/cache-aware-assembly` | Decision gate, diagnosis procedure, and cost-aware verification |
| `standards/evidence/prompt-cache-2026-10.md` | T1..T14 with URLs and conservative labels |
| `docs/knowledge-base/token-efficiency-cache-2026-10.md` | This synthesis |

The checker reports each carrier's prefix hash and layer hashes with `--hash`,
and reports how many carriers meet each profile minimum. On the current tree
(41 carriers, 809-1,099 tokens) coverage is 41/41 at 512, 2/41 at 1,024, and
0/41 at 2,048/4,096. That is the clearest static signal: the role prompt alone
will not cache on models with a 2K/4K minimum; tools and message history must
carry the prefix over the threshold, or the prompt is a one-shot arm.

The static checker is deliberately narrow. It can prove:

- no ISO dates, timestamps, UUIDs, localhost ports, temp paths, PIDs, seeds, or
  frontmatter dates in a carrier body;
- no repeated instruction line of eight or more words inside one carrier;
- every carrier's static prefix is reported against the conservative 512-token
  default; a prefix below it is a warning, not a failure;
- every non-vendor skill body is at or below the 1,500-token cap;
- each carrier's prefix and layer hashes are reported for comparison;
- AS-01..AS-12 exist and the cache-policy version is pinned.

It cannot prove a cache hit rate, TTL adequacy, routing, or total cost. Those
need the harness telemetry.

## 4. Static vs runtime

| Question | Static library | Runtime harness |
|---|---|---|
| Is the prefix byte-stable? | Volatile scan, prefix token report, fragment pins | Actual rendered prefix hash |
| Is the prefix large enough? | Token estimate vs profile minimum | Provider-reported cache write/read |
| Did a tool change break reuse? | Tool definitions are not in templates; policy in AS-06 | Tool-set hash / version |
| Did an earlier message change? | Policy only (AS-12) | First divergent layer |
| Did the cache expire or was it invalidated? | No | TTL class + seconds since last request |
| Did the change save money? | No | Read/write tokens x price, cost per verified task |

## 5. Design decisions

- **Extend AS, do not create a second cache standard.** AS-01..AS-08 already own
  placement; AS-09..AS-12 complete the same axis.
- **Data, not prose, for minima.** Vendor minima and multipliers change; a
  dated JSON profile can be reviewed without rewriting a standard.
- **Hit rate is diagnostic.** The library tells the agent to compare hit rate
  **and** total cost. Compaction can lower hit rate while saving tokens; a
  padded prefix can raise hit rate while losing money.
- **One hash owner.** Fragment hashes remain in
  `tooling/fragments.manifest.json`; the cache checker reads them and does not
  re-pin.
- **No static compression.** LLMLingua-style compression is a runtime transform;
  applying it to the static prefix changes the prefix every call and defeats
  reuse (T11).

## 6. Limits

- No live harness was run; the hit-rate and cost claims are mechanisms from the
  sources, not repository measurements.
- The token estimate is `bytes / 4`; it is comparative, not a tokenizer.
- The profile table is a snapshot (2026-10-25) with a 2027-01-31 review date;
  vendor minima and prices will drift.
- The static checker cannot prove that a cached layer is actually sent as one
  prefix; that is a harness assembly responsibility (AS-10).
- Telemetry schema `/2` is documented here but not exercised by a live harness;
  old `/1` records still validate.

## 7. Verification

`make gate` runs the token-efficiency checker after the long-horizon gate. The
checker must report `0 violation(s)` and the current prefix range. New negative
tests cover a volatile date, a duplicate instruction, a missing AS rule, a
profile-version drift, a missing CATALOG pin, and an over-cap skill body.
