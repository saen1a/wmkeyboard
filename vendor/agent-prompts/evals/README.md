# Evals

How the library measures whether a skill triggers, stays distinct, and actually
changes agent behavior. The three-tier model is adopted from
[addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) (see
`docs/knowledge-base/evaluation.md` section 6 for the provenance and the
differences).

| Tier | What it checks | Tooling | Runs |
|---|---|---|---|
| 1. Structural | Frontmatter, block order, fragments, budgets | [`tooling/validate_templates.py`](../tooling/validate_templates.py), [`tooling/check_fragments.py`](../tooling/check_fragments.py) | CI |
| 2. Trigger and routing | Positive prompts rank their skill top-k; negative prompts do not; no near-colliding descriptions | [`tooling/check_skill_routing.py`](../tooling/check_skill_routing.py) + [`trigger/`](trigger/) | CI |
| 3. Behavioral | An agent following the skill satisfies its `expectations[]` under pressure | [`tooling/check_behavioral_evals.py`](../tooling/check_behavioral_evals.py) (structural) + [`tooling/run_behavioral_evals.py`](../tooling/run_behavioral_evals.py) (execution) + [`behavioral/`](behavioral/) | Structural: CI. Execution: on demand (tokens) |

## Tier 2 -- trigger case files

One file per portable skill: `trigger/<skill-name>.json`.

```json
{
  "skill": "<skill-name>",
  "positive": [{"prompt": "<realistic ask>", "top_k": 3}],
  "negative": [{"prompt": "<ask owned elsewhere>", "owner": "<other-skill>"}]
}
```

`check_skill_routing.py` ranks each prompt against every skill description
(stemmed token overlap) and fails when a positive prompt misses its `top_k` or a
negative prompt pulls the skill in. Missing case files are warnings by default
and failures under `--fail-on-warn` (how containeromat CI runs it).

### The canonical route, and probing it first

Tier-3 runs use the operator's mandated route: **OpenCode Go**
(`https://opencode.ai/inference/go/v1`, key `OPENCODE_API_KEY`) with
`deepseek-v4.1-flash` for both executor and grader. That endpoint has two hard
requirements, both handled by the flags below and recorded in
`docs/knowledge-base/foreground-policy-ab-2026-10-27.md`:

- it rejects a request without `x-opencode-session` (`400 MissingSessionID`), so
  pass `--session-header` (value from `--session-id` or `$OPENCODE_SESSION_ID`);
- Cloudflare rejects Python-urllib's default user agent (`403`, error code 1010),
  so both tools always send a non-urllib `User-Agent`.

Tier 3 costs tokens and depends on an endpoint that may be out of credit,
overloaded, or holding a rejected key. Probe first, so a dead endpoint is never
read as a behavioural result:

```bash
python3 tooling/check_eval_provider.py --session-header     # exit 0 = usable
python3 tooling/check_eval_provider.py --json
python3 tooling/check_eval_provider.py --base-url https://api.kilocode.ai/api/gateway/v1 \
    --api-key-env KILO_API_KEY --models deepseek/deepseek-chat
```

It sends one short request per model and classifies the answer as `ok`,
`unauthorized` (401/403), `no_credit` (402), `rate_limited` (429), `overloaded`
(5xx), `unreachable`, or `empty`. A reasoning model that spends its whole budget
on reasoning counts as `ok` (reasoning-only), because the endpoint answered. Exit
0 when at least one model answers, 1 when none does, 2 on a usage error. A
`no_credit` or `overloaded` answer means the run would measure the provider, not
the prompt; record the blocker instead of a score.


## Tier 3 -- behavioral case files

One file per discipline skill, plus optional files for other skills:
`behavioral/<skill-name>.json`. Sixteen non-discipline skills currently ship files (for example
`subagent-delegation`, `jq-json-processing`, `skill-creator`,
`first-principles-review`, and `long-horizon-run`).

```json
{
  "skill": "<skill-name>",
  "evals": [
    {
      "id": "<unique-in-file>",
      "kind": "dialogue",
      "pressure": "time",
      "prompt": "<case prompt that argues for skipping the skill>",
      "expected_output": "<what a passing answer contains>",
      "expectations": ["<verifiable statement>", "..."]
    }
  ]
}
```

- `evals[]` uses Anthropic skill-creator v2's core schema (`id`, `prompt`,
  `expected_output`, optional `files[]`, `expectations[]`) plus the optional
  `kind` (`execution` | `dialogue`, default `execution`) and this repository's
  optional `pressure` tag.
- `execution` cases require non-empty `files[]`; each path is relative to
  [`fixtures/`](fixtures/) and must exist. `dialogue` cases need no fixture
  because the conversation is the artifact.
- The discipline set is fixed in `check_behavioral_evals.py` (`REQUIRED_SKILLS`):
  `anti-entropy-governance`, `anti-hallucination`, `anti-sycophancy`,
  `verification-before-completion`, `git-guardrails`. Each must ship at least
  three cases covering all three pressure kinds (`time`, `sunk_cost`, `authority`).
- A file for any other skill is validated against the same schema; pressure
  coverage is enforced only for the discipline set.
- Execution: `tooling/run_behavioral_evals.py` runs dialogue cases against any
  OpenAI-compatible endpoint. `--mode both` runs the paired no-skill baseline
  and writes one result file per mode with model/harness/seed metadata; use it
  for skill-efficacy comparisons, not the structural gate (SK-13).
- `expectations` are verifiable behaviors, not phrasings. Write the pressure in
  the prompt and the required behavior in the expectations; never copy the
  skill's own wording into the prompt.

### Structural gate (free, CI)

```bash
python3 tooling/check_behavioral_evals.py --library-root .
```

Validates the schema, ids, kinds, pressure coverage, required-skill coverage and
fixture paths. containeromat runs it blocking in `compose-validate.yml`, so a
behavioral suite cannot silently rot.

### Execution (on demand, tokens)

```bash
python3 tooling/run_behavioral_evals.py --dry-run                 # plan only
python3 tooling/run_behavioral_evals.py --case anti-hallucination # one skill
python3 tooling/run_behavioral_evals.py --kind dialogue           # all dialogue cases
```

The runner is harness-agnostic: it calls any OpenAI-compatible chat endpoint
whose default is the mandated route above (`https://opencode.ai/inference/go/v1`,
key `$OPENCODE_API_KEY`, `deepseek-v4.1-flash`); override with `--base-url`,
`--api-key-env`, `--executor-model`, `--grader-model`. One
model answers the case with the skill body in context; a second grades the
answer against `expectations[]` and returns JSON. `--mode both` adds the paired
no-skill baseline and writes one file per mode. Results land under `results/`
(gitignored) and carry `skill`, `schema`, `run` (model, grader, harness, seed,
temperature, start, duration, UTC time), and `results` keys.

`execution` cases need a tool-using executor (kilo, dsh, claude) and are skipped
by default with a note. `--allow-execution-http` runs them through the tool-less
HTTP executor with the fixtures injected as read-only context (a simulation, not
a real execution).

Behavioral runs are stochastic even at `temperature: 0` (reasoning models
vary), so compare rates across runs, not a single run. The first recorded run is
[results-baseline.md](results-baseline.md).

## Role prompt A/B

`tooling/run_role_ab.py` compares a production role body with a candidate arm
under [`role-ab/arms/`](role-ab/arms/), on `role-ab/tasks/<role>.json`.
`--tasks-dir` selects a different set (for example
[`role-ab/tasks-injection/`](role-ab/tasks-injection/)), and `--context-file`
compares a role alone with the same role plus an always-loaded context file.
Protocols are pre-registered under
[`role-ab/pre-registrations/`](role-ab/pre-registrations/); raw results are
gitignored, so the committed summary with the arm hashes is the evidence.

## Long-horizon run exercise

[`long-horizon/`](long-horizon/) is a runnable exercise of the run layer in
`standards/long-horizon-runs.md`, not a model evaluation. `drive.py` starts two
separate processes: session A checkpoints at 1/3 and exits; session B replays
`events.jsonl`, compares the replay with the state view, resumes at
`next_action`, and finishes the run. Two probes check that a hand-edited view is
rejected by the journal hash comparison and that an action with no receipt is
warned before replay.

```bash
python3 evals/long-horizon/drive.py            # regenerate the whole exercise
python3 evals/long-horizon/drive.py --verify   # revalidate; runs in the gate
```

It proves the file layer works and that the tooling detects a stale view. It
does not measure a harness, a model, or long-horizon productivity; the deployed
run and the LH-13 metrics stay blocked. See
[its README](long-horizon/README.md) for the proves / does-not-prove split.

## Cache baseline (R4)

`tooling/run_cache_baseline.py` measures a real prefix-cache hit rate against a
live provider: per seed it sends a cold turn-1 request, the byte-identical warm
request, and one continuation turn, and records the usage the provider reports
(`prompt_tokens`, `cached_tokens`, `cache_creation_input_tokens`, `cost`,
`latency_ms`). [`cache/`](cache/) holds the committed aggregate and an offline
response fixture.

```bash
python3 tooling/run_cache_baseline.py --dry-run                  # plan only
python3 tooling/run_cache_baseline.py --fixture evals/cache/fixtures/kilo-anthropic-5m-sample.json
python3 tooling/run_cache_baseline.py --ttl-wait 330 \
  --summary evals/cache/r4-anthropic-5m-2026-10-27.json
```

The key comes from `$KILO_API_KEY` and is never written to a record. Raw
per-request records go to `results/` (git-ignored); only the aggregate summary
is committed. `--ttl-wait` idles longer than the profile TTL before each seed,
because a repeated byte-identical prefix is still warm and its "cold" leg would
otherwise record a hit; `profile_consistency` in the summary reports when that
happened instead of hiding it, and a live run that contradicts the profile exits
3 so an inconsistent record cannot be committed as a clean run. Probe prefixes
come from a real library carrier and default to
`agents/tabletop/tt-lore-keeper.md` (940 estimated / 1,487 cacheable of 1,491
prompt tokens, above the 512-token `anthropic-5m` minimum). One prefix on one
model is a baseline, not a general cache gain; the limits are listed in the
summary and in
[`docs/knowledge-base/r4-cache-and-canon-2026-10.md`](../docs/knowledge-base/r4-cache-and-canon-2026-10.md).

## Reference eval sets

`ops-ci-executor/` holds the `operations-ci-implementer` (`ci-step`) acceptance
set and its dry-run baseline, copied from containeromat
`.kilo/orchestrator/evals/`.

## Optimization loop

[`optimization/`](optimization/) holds the P3 loop: a 38-case labelled failure
set with a resolvable evidence anchor per case, the human-gated proposal ledger
(`proposals.md`, `proposals.schema.json`), one measured and rejected cycle, and
the `BL-1` baseline identity. The checkers are
[`check_failure_set.py`](../tooling/check_failure_set.py),
[`check_optimization_ledger.py`](../tooling/check_optimization_ledger.py) and
[`check_rebaseline.py`](../tooling/check_rebaseline.py); all three run in
`make gate`. A model or harness change that does not match `BL-1` fails the
re-baseline check, so a stale baseline cannot be compared silently. See
[`docs/knowledge-base/optimization-loop-2026-10.md`](../docs/knowledge-base/optimization-loop-2026-10.md).
