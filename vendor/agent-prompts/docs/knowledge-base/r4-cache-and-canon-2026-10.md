# R4: cache-hit measurement and canon consolidation (2026-10)

Status: design complete and the `anthropic-5m` baseline is measured (2026-10-27,
section 3.6); the canon question is closed (2026-10-27, no registry change
needed -- see 4.3). No prompt body is changed by this plan.

## 1. Why R4 exists

The static assembly contract (AS-01..AS-12) and the profile table
(`standards/cache-profiles.json`) say what a cacheable prefix should look like.
They do not say whether a real harness actually hits the cache. R4 closes that
gap with a repeatable measurement, and it records what moving a remaining dsh
skill into the library canon actually needs -- content work, one skill at a
time -- and why no second canon root is involved.

## 2. Static baseline (2026-10-26)

`python3 tooling/check_token_efficiency.py` measures 41 carriers with prefix
tokens 809 / 940 / 1100 (min / median / max). Profile coverage is:

| Profile | Carriers above `min_tokens` | Reading |
|---|---|---|
| `anthropic-5m` (512) | 41/41 | every carrier can cache |
| `anthropic-1h` (512) | 41/41 | every carrier can cache |
| `deepseek-prefix` (512) | 41/41 | every carrier can cache |
| `vllm-apc` (512) | 41/41 | every carrier can cache |
| `openai-30m` (1024) | 2/41 | only the two largest prefixes |
| `openai-12h` (1024) | 2/41 | only the two largest prefixes |
| `gemini-2.5` (2048) | 0/41 | no carrier reaches the minimum |
| `gemini-3` (4096) | 0/41 | no carrier reaches the minimum |

This is a workload-size fact, not a gate failure. A consumer on an
OpenAI/Gemini profile should not expect prefix caching from the current
carriers unless it raises the stable prefix above the minimum or accepts the
miss.

## 3. Measurement protocol

### 3.1 Unit of observation

One **run** is one task on one model/harness/profile at one seed. A run emits
one `agent-prompts-harness/2` document per turn (schema:
`evals/harness-telemetry.schema.json`). The fields that matter for R4 are:

- run: `model`, `provider`, `harness`, `seed`, `cache_epoch`, `prompt_version`;
- turn: `prefix_hash`, `first_divergent_layer`, `seconds_since_last_request`;
- usage: `input_tokens`, `cache_hit_tokens`, `cache_miss_tokens`,
  `cache_read_tokens`, `cache_write_tokens`, `cache_write_ttl_class`;
- outcome: `status`, `duration_ms`, `cost_usd`, `escaped_defect`,
  `operator_interventions`.

WP-04 step 2 names the telemetry fields above, but `tooling/run_cache_baseline.py`
records the gateway's `usage` names instead, because the gateway emits no
`agent-prompts-harness/2` document. The mapping is explicit; the committed
record fields are not renamed to match the plan:

| WP-04 step 2 / telemetry field | Runner record field | Note |
|---|---|---|
| `input_tokens` | `usage.prompt_tokens` | Prompt tokens as the gateway counts them. |
| `cache_hit_tokens` | `usage.cached_tokens` | The gateway reports one read counter, so hit and read collapse into it. |
| `cache_read_tokens` | `usage.cached_tokens` | Same counter as `cache_hit_tokens`. |
| `cache_write_tokens` | `usage.cache_creation_input_tokens` | Tokens written to the cache on this request. |
| `cache_write_ttl_class` | not emitted | The gateway reports no TTL class. The 5 m class is inferred from the absence of an extended-TTL marker plus the observed expiry after the 340 s idle. |
| `cost_usd` | `usage.cost_usd` | Normalized from the gateway's `usage.cost`. |
| `duration_ms` | `latency_ms` | Wall time measured by the runner. |
| `prefix_hash` | `prefix_sha256` | SHA-256 of the stable prefix body. |
| `first_divergent_layer` | `first_divergent_layer` | Same name. |
| `seconds_since_last_request` | `seconds_since_last_request` | Same name. |

### 3.2 Run matrix

Measure at least one profile per cache family, not one average across all
profiles:

- `anthropic-5m` and `anthropic-1h`;
- `openai-30m` and `openai-12h`;
- `gemini-2.5` and `gemini-3`;
- `deepseek-prefix`;
- `vllm-apc`.

For each profile, use three seeds and two workloads: a short turn (one user
message) and a continuation turn (the same prefix, one follow-up message).
Record a cold run and a warm run. The warm run is the only one that can show a
TTL hit.

### 3.3 Metrics

- **Hit rate** = `cache_hit_tokens / input_tokens`, per turn and per run.
- **TTL hit** = warm-run hit rate where `seconds_since_last_request` is below
  the profile TTL.
- **Write cost** = `cache_write_tokens` and the profile write multiplier.
- **Read cost** = `cache_read_tokens` and the profile read multiplier.
- **Cost per verified unit** = `cost_usd` divided by the number of verified
  units in the run.
- **Latency** = `duration_ms`, reported beside the hit rate so a cache write
  that slows the first turn is visible.
- **Divergence** = distribution of `first_divergent_layer`; `tools` or
  `system` in a supposedly stable prefix is a finding, not noise.
- **Epoch churn** = number of `cache_epoch` changes in the run set.

### 3.4 Acceptance

A baseline is recorded when at least one profile has three seeds, one cold run,
one warm run, and a complete telemetry document per turn. A prompt or tool-set
change is cache-neutral only when:

1. the hit rate does not fall by more than 5% relative on the measured profile;
2. cost per verified unit does not rise by more than 5%;
3. `first_divergent_layer` does not move earlier in the layer order;
4. the run records the new `cache_epoch` and `prompt_version`.

A model or harness change resets the baseline. A prompt change without a
baseline is not a cache result.

### 3.5 Data handling

Telemetry lives with the consumer harness, not in this library. The library
keeps the schema, the profile table, and the analysis method; a consumer keeps
the raw runs and reports aggregate metrics. Do not put provider keys, raw
prompts, or full tool outputs in a committed telemetry file.

### 3.6 Measured baseline, `anthropic-5m` (2026-10-27)

The measurement is `tooling/run_cache_baseline.py`. It sends one cold request,
the byte-identical warm request two seconds later, and one continuation turn per
seed, and records what the provider reports. The prefix is a real library
carrier (`agents/tabletop/tt-lore-keeper.md`, body only): 3,760 characters, 940
estimated tokens, 1,487 prefix tokens as reported (`prefix_tokens_observed`),
hash `912dc186d5b5...`. The summary's `max_cacheable_block_observed` is 1,508
because it takes the largest single-request cacheable block, which is the
continuation's 1,487 read plus its 21-token tail; the prefix itself stays
1,487. Route: the Kilo gateway at
`https://api.kilocode.ai/api/gateway/v1` with `anthropic/claude-haiku-5.5`,
recorded as harness `kilo-gateway`; this is a gateway route, not a direct
Anthropic call.

```bash
python3 tooling/run_cache_baseline.py --profile anthropic-5m \
  --prefix agents/tabletop/tt-lore-keeper.md \
  --model anthropic/claude-haiku-5.5 --harness kilo-gateway \
  --base-url https://api.kilocode.ai/api/gateway/v1 \
  --api-key-env KILO_API_KEY --seeds 401,409,419 --ttl-wait 340 --gap 2 \
  --summary evals/cache/r4-anthropic-5m-2026-10-27.json
```

Started 2026-10-27T14:40:51Z, finished 14:52:37Z. Seeds 401, 409, 419 (three
seeds, three requests each, nine of nine completed, none rate-limited). The
aggregate backs that last clause with `attempts` 9, `retries` 0 and
`rate_limited` 0: nine requests took nine attempts, so no request was retried
or rate-limited. Raw per-request records stay in the git-ignored
`evals/results/`; the aggregate is
`evals/cache/r4-anthropic-5m-2026-10-27.json`.

| Leg | n | prompt tokens | cached | cache write | hit rate | cost per run (USD) | latency median (ms) |
|---|---|---|---|---|---|---|---|
| Turn 1, cold | 3 | 1,491 | 0 | 1,487 | 0.0000 | 2.02e-04 | 2,892 |
| Turn 1, warm (+2.0 s) | 3 | 1,491 | 1,487 | 0 | 0.9973 | 3.1e-05 | 2,371 |
| Turn 2, continuation | 3 | 1,512 | 1,487 | 21 | 0.9835 | 3.4e-05 | 1,638 |

- **Cold/warm hit rate**: 0.0000 cold, 0.9973 warm. The miss is the 4 prompt
  tokens the gateway reports outside the cached block.
- **TTL hit**: the warm leg ran 2.0 s after the cold leg, inside the 5-minute
  window, and read 1,487 tokens; the continuation leg read the same 1,487 and
  wrote 21 new ones. Every seed produced identical token splits.
- **Write/read tokens per run**: 1,487 written on the cold leg, 1,487 read on
  the warm leg, 0 rewritten. The continuation re-read the prefix and wrote only
  its 21-token tail.
- **Cost per run**: 2.02e-04 cold, 3.1e-05 warm, 3.4e-05 continuation; 8.0e-04
  USD for the whole nine-request run. Total cold/warm cost ratio 6.52.
- **Latency**: 2,892 ms cold, 2,371 ms warm, 1,638 ms continuation (medians).
  The cache write is the slowest leg, but individual runs ranged 1,406-2,963 ms,
  so the ordering is indicative at n=3, not a measured write penalty.
- **Profile mapping**: `anthropic-5m`. The cold leg is write-only and the warm
  leg read-only with `cache_creation_input_tokens` at 0, and the request carried
  no extended-TTL marker, so the default 5-minute ephemeral class applies. The
  gateway emits no `cache_write_ttl_class` (see the mapping in 3.1); the class
  is inferred from the absence of an extended-TTL marker plus the observed
  expiry after the 340 s idle, which produced a cold leg. The
  cost arithmetic is consistent rather than independent: the 171e-06 USD
  cold/warm difference over 1,710 token-equivalents gives 1.0e-07 per input
  token, and both legs then leave the same ~16.1e-06 for the 32-token output --
  what a 1.25x write and a 0.1x read predict. A 2.0x write premium would instead
  need an output/input price ratio near 11, outside the 4:1-5:1 band the vendor
  uses. The gateway exposes no price table, so the multipliers are inferred.
- **Total vs prompt cost**: the 6.52 total-cost ratio is diluted by the 32-token
  output cap, charged on every leg (about 16.1e-06 USD). The prompt charge alone
  is 1.86e-04 cold and 1.49e-05 warm, which is the 12.5x the 1.25/0.1 pair gives.

Limits of this baseline:

- One prefix, one model, one gateway route, one day. It is not a general cache
  gain: a different carrier, a longer prefix, or a session that edits its stable
  prefix between turns will land elsewhere. The warm leg repeats an identical
  body, so 0.9973 is an upper bound for a well-behaved assembly, which is what
  AS-01..AS-12 exist to protect.
- Three deterministic repetitions are not three sampling draws; the hit rate is
  a property of the prefix, and only latency and cost vary.
- Turn 2 has no cold leg. The prefix is already warm from turn 1, and a cold
  continuation would need an idle wait longer than the TTL; turn 2 measures
  reuse under growth only.
- No `cache_control` breakpoint was sent. The gateway placed the boundary at the
  system block by itself (1,487 of 1,491 tokens), which is the AS-05 shape but
  is the gateway's choice, not a library-declared breakpoint.
- The OpenAI, Gemini, DeepSeek and vLLM profiles remain unmeasured. The
  coverage table in section 2 is still the static answer for them.

Rejected attempt, same day: the first run (started 14:22:20Z) had seed 401's
cold leg still warm (`cached_tokens` 1,467, `cache_creation` 20) because the
prefix had been probed 147 seconds earlier. `profile_consistency.cold_reads_zero`
was false, so the run was not reported; it was repeated with a six-minute idle
and `--ttl-wait 340`. Seeds 409 and 419 in that attempt were already clean, and
the recorded run reproduces all three.

## 4. Canon consolidation design

### 4.1 Current constraint (corrected 2026-10-27)

`containeromat:scripts/skills-roots.json` enforces exactly one `role: canon`
root, and that rule is about the LOCAL canon (`.openhands/skills`). The library
is the external canon for 24 skill names, declared separately in
`containeromat:scripts/skills-library.json` (`canonRoot: agent-prompts`); its
`skills` map is the ownership declaration, and `verify-agents.py` resolves every
copy of a library name against the library body (including that name's copy under
`.openhands/skills`) and every other copy against the local canon. Ownership is
one owner per name, so no skill needs a second canon root.

The nine dsh-root names absent from the library split into six multi-root dsh
candidates (`compose-audit`, `compose-smoke`, `compose-step`,
`doubt-driven-review`, `forgejo-registry-image`, `knowledge-capture`), which
carry a local canon row plus three runtime copies, plus three single-instance
skills (`kilo-review`, `seifomat-dev`, `seifomat-dev-debug`), which exist in
exactly one root each. None is without a canon.

Do not confuse that nine with the nine local-owned names among the 33 multi-root
names in 4.3. The two sets overlap in the six multi-root dsh candidates; the
other three local-owned multi-root names are not dsh-root names, and the other
three dsh names are the single-instance skills.

Current counts (2026-10-27): 24 library skills; 18 dsh skills; 32 skills under
the local canon root; 38 distinct names across the 6 registered roots.

### 4.2 Options

| Option | Shape | Cost | Risk |
|---|---|---|---|
| A. External-canon role | Add `role: external-canon` for the library root; keep one local canon | Registry schema bump and loader change | Two canon roots can hide ownership unless names are disjoint |
| B. Move the 6 multi-root dsh candidates into the library | Generalize and copy each into the library | Content work plus consumer re-vendor | Highest quality, slowest |
| C. Keep the split | Library canon for 24; containeromat canon for the rest | None | Permanent two-canon explanation and catalog drift |

### 4.3 Recommendation

Option A was recommended, then rejected on measurement (2026-10-27). It would
have restated an ownership split the two registries already implement: a direct
check found 38 names across the six registered roots, 33 in more than one root,
24 library-owned and 9 local-owned, none unowned. The decision and its evidence
are in the containeromat KB entry `skill-canon-ownership-two-registries` and in
the autonomous plan's Wave 3 closeout; the guards the schema change was meant to
buy exist there as two contract tests.

Option B (move a skill into the library) remains the only content path: one skill
at a time, with a paired baseline before any body change. It applies to the six
multi-root dsh candidates first. Option C's condition is met for the three
single-instance skills (`kilo-review`, `seifomat-dev`, `seifomat-dev-debug`):
they are documented as project-instance and never appear in this catalog.

### 4.4 Migration phases

Not executed, kept as the record. Phase 1-3 (schema, loader, duplicate-name test)
are cancelled: the split already exists and the tests now pin it from the
consumer side. Phase 4 is the remaining content path and applies per skill. Phase
5 still applies whenever a migration happens.

### 4.5 Acceptance and rollback

Acceptance: the design is rejected with a recorded reason (2026-10-27), every
library name has one owner, and a deliberate cross-owner name is rejected --
`check_library_canon` fails a local copy whose body disagrees with the library
body, and containeromat's `test_skills_roots_contract.py` fails a name copied
into two roots with neither owner. No prompt body and no pin is involved, so
rollback is a documentation revert.

## 5. R4 exit criteria

- A hit-rate baseline exists for at least one profile, with cold and warm runs.
  Met 2026-10-27 for `anthropic-5m` (section 3.6): 3 seeds, cold 0.0000, warm
  0.9973. The other seven profiles stay unmeasured.
- The profile coverage table is reproducible from `check_token_efficiency.py`.
- The external-canon design is accepted or rejected with a recorded reason
  (rejected 2026-10-27; ownership is per name in the existing library registry).
- No prompt body changed without a paired result.

## 6. Non-goals

- Raising every carrier above the OpenAI/Gemini minimum. Prefix size is a
  workload decision, not a library target.
- Replacing the lexical trigger check with a judge. That is P2, not R4.
- Measuring cost without a real harness. The library owns the schema and the
  method, not the provider bill.

## 7. Sources

- `standards/prompt-assembly.md` AS-01..AS-12.
- `standards/cache-profiles.json` and `tooling/check_token_efficiency.py`.
- `evals/harness-telemetry.schema.json` `/2`.
- `tooling/run_cache_baseline.py` and
  `evals/cache/r4-anthropic-5m-2026-10-27.json` (this baseline, section 3.6).
- `evals/cache/fixtures/kilo-anthropic-5m-sample.json` (offline replay of the
  same run).
- `docs/knowledge-base/token-efficiency-cache-2026-10.md`.
- `docs/knowledge-base/skill-prompt-refactor-2026-10.md` R4/R5.
- `PLAN.md` Deferred: skills migration and live validation.
