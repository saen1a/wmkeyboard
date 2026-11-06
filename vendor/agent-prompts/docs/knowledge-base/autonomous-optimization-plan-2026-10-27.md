# Autonomous optimization and cleanup plan (2026-10-27)

Status: ready for subagent execution.
Owner: library maintainer.
Canonical location: `agent-prompts/docs/knowledge-base/autonomous-optimization-plan-2026-10-27.md`.

This plan turns the 2026-10-27 audit into work packages that independent
subagents can execute. It covers the library, containeromat, and the deployed
runtime. Seifomat has no open work and is out of scope.

## Working checkouts

- **Live library**: `/workspace/agent-prompts`, branch `main`. Every library
  work package reads and writes here.
- **Consumer**: `/workspace/containeromat`, branch `main`. Consumer work
  packages read and write here only.
- `/workspace/containeromat/agent-prompts` is a git submodule pinned to
  `b1ea951` plus a gitlink, not the library's main. It lags the live library and
  does not contain the later work packages or this plan's corrections. Never
  edit it as if it were the library; re-vendor from `/workspace/agent-prompts`.
- Where this plan names a commit or a version as the library baseline (section
  2, for example), read it as the consumer's pin at plan time, and read the live
  checkout for the current state.

## 1. Operating rules

Every work package (WP) follows these rules.

1. Work in a dedicated worktree or branch. Never edit another WP's branch.
2. One writer per repository at a time. Parallel lanes are listed in section 4;
   do not invent a new cross-repo edit.
3. Do not hand-edit a vendored library skill in a consumer. Re-vendor from the
   library, update the pin, and regenerate the manifest.
4. Do not change a skill body without its paired baseline. For shape changes,
   use the old-vs-new A/B (`tooling/run_refactor_ab.py`); for body changes, use
   the skill/no-skill runner (`tooling/run_behavioral_evals.py`).
5. Do not weaken a gate to make a change pass. If a required check is retired
   or missing, fix the contract or stop and report.
6. Every completed WP leaves a changelog entry and a green local gate. A PR
   with a red gate is not Done.
7. If a provider or credential is missing, record BLOCKED with the exact
   command and error. Do not substitute a different model without recording it.
8. Use the repository's existing script names and paths; do not add a parallel
   tool when a checked-in one exists.
9. **RAM limit: at most two agents run in parallel.** This includes
   implementation and audit agents. If a wave lists more than two work
   packages, split it; do not start a third session.
10. **Every wave ends with two audit agents.** They run in parallel, read-only,
    and both must pass before the next wave. Findings become fix tasks for the
    original implementation owner; a wave is not closed with an open
    high/medium finding.

## 2. Baseline at plan time

Library (`agent-prompts`):

- `main` at `b1ea951`; library 2.6.0; OMP projection and H2 merges included.
  That commit is the containeromat submodule pin (see "Working checkouts"); the
  live library has moved past it.
- `make gate`: 334 tests, floor 330; token-efficiency 0 warnings; routing 24/24;
  behavioral 24/18; `H2>8=1` is the frozen vendor `misakanet`.
- No open PRs or issues.

Containeromat:

- Open PRs: `#379` (Renovate grouping unblocker), `#378`, `#370`, `#369`,
  `#357` (dependency updates). The four dependency PRs are red until `#379`
  lands.
- Open issues: `#321` Dependency Dashboard, `#84` CI health digest.
- `agent-prompts` pin is a commit that includes the OMP projection and the
  H2 bodies; the exact commit is in `git ls-tree origin/main agent-prompts`.
- Branch protection was corrected by removing the retired
  `Build OpenHands image / docker*` context; verify the live list before
  relying on it.

Known non-issues, so no WP is created for them:

- Non-vendor H2, body, description and doctrine advisories are zero.
- Remaining shape advisories are frozen vendor copies (`misakanet`, `caveman*`).
- Seifomat has no open PRs, issues, or unmerged branches.

## 3. Work packages

| WP | Priority | Lane | Repo | Depends on |
|---|---|---|---|---|
| WP-01 Dependency queue | P0 | Ops | containeromat | none |
| WP-02 State-doc reconciliation | P0 | Docs | both | none |
| WP-03 CI / branch-protection contract | P1 | Ops | containeromat | WP-01 |
| WP-04 R4 live cache baseline | P1 | Measurement | library/consumer | provider credential |
| WP-05 Canon consolidation | P1 | Canon | both | WP-02 |
| WP-06 Semantic trigger check | P2 | Experiments | library | WP-04 or a judge key |
| WP-07 Context template + conduct placement | P2 | Experiments | library | paired runner |
| WP-08 P3 optimization loop | P3 | Optimization | library | WP-06, WP-07 |
| WP-09 Long-horizon live validation | P2 | Runtime | both | deployed harness |
| WP-10 OMP and runtime reload validation | P1 | Runtime | containeromat | deploy access |
| WP-11 H2 confirmation on canonical model | P2 | Measurement | library | DeepSeek credits |
| WP-12 Optional guard tightening | P3 | Backlog | library | operator decision (executed 2026-10-27) |

## 4. Parallel execution plan

Concurrency cap: **two agents maximum**. Each wave below has at most two
implementation agents. Implementation stops before the audit; the two audit
agents then run alone.

Wave 1 (two parallel implementation agents):

- WP-01 (containeromat PR queue only).
- WP-02 (agent-prompts docs plus containeromat runbooks; no PR conflicts with
  WP-01).

Wave 1 audit (two parallel, read-only):

- `reviewer`: diff scope, acceptance commands, no gate weakening, no stale pins.
- `code-skeptic`: completion claims, evidence, untested paths, cross-repo parity.

Wave 2 (two parallel implementation agents):

- WP-03 (containeromat CI/branch-protection contract).
- WP-10 (OMP/runtime reload validation).

Wave 2 audit: two agents as above.

Wave 3 (two parallel implementation agents):

- WP-05 (canon consolidation; one writer per repo, library then consumer).
- WP-04 (R4 cache baseline) only when a provider with cache telemetry is
  available. If not, WP-05 runs alone and WP-04 moves to Wave 4.

Wave 3 audit: two agents as above.

Wave 3 ran with WP-05 alone. No provider with cache telemetry is configured for
the harness, so WP-04 did not start and stays open for Wave 4 (section 10).

Wave 4 (two parallel implementation agents):

- WP-06 (semantic trigger check).
- WP-07 (context template + conduct placement).
- If WP-04 is still open, swap it for one of these; never run three.

Wave 4 audit: two agents as above.

Wave 5 (two parallel implementation agents):

- WP-09 (long-horizon live validation).
- WP-11 (H2 confirmation on canonical model, when credits exist).
  Ran 2026-10-27 and returned BLOCKED: the DeepSeek key authenticates but the
  account has no credit (HTTP 402 `insufficient_balance_error`). No canonical
  run exists, and the free-model H2 result remains the only evidence. No proxy
  model was substituted.

Wave 5 audit: two agents as above.

Wave 6 (one implementation agent):

- WP-08 (P3 optimization loop) consumes the evidence from WP-04, WP-06 and
  WP-07.

Wave 6 audit: two agents as above.

WP-12 is a backlog item, not a wave. It starts only on an operator decision and
then follows the same two-agent cap and audit gate.

### Wave audit gate

The two audit agents are independent of the implementers and do not edit files.
They run in parallel after every wave and report findings with severity,
evidence, and owner.

| Auditor | Scope | Blocks when |
|---|---|---|
| `reviewer` | Diff scope, acceptance commands, gate output, no gate weakening, no stale pin, no hand-edited vendored skill | Any high/medium finding, a red gate, or a command not reproduced |
| `code-skeptic` | Completion claims, evidence quality, untested paths, cross-repo parity, blocked-state honesty | A claim not backed by a command, a skipped verification, or a silent substitution |

Audit closeout:

1. Both auditors report their findings; the owner records them in the wave
   ledger in section 10. No wave ledger file is committed in this repository,
   so that section is the record. High and medium findings become fix tasks
   for the original owner.
2. The owner fixes them on the same branch, reruns the acceptance commands, and
   appends the new evidence.
3. The two auditors re-check only the changed findings. Both must pass.
4. The wave closes only when the ledger has no open high/medium finding and the
   final gate output is attached to the PR or report.
5. The next wave does not start until the wave audit is closed.

The two audit agents count toward the two-agent cap. Do not run an
implementation agent beside them.

## 5. Work package details

### WP-01 -- Containeromat dependency queue

Goal: land `#379`, then the four dependency PRs, with green required checks.

Steps:

1. Check `#379` (`fix/unmergeable-prs`). If pending, wait; if red, read the
   failing job and fix only the Renovate grouping defect it names.
2. Merge `#379` once all required checks pass.
3. For `#378`, `#370`, `#369`, `#357`: rebase on the new `main` if needed,
   dispatch or wait for checks, merge only when green. Do not merge a red
   dependency PR to "let the next one fix it".
4. If a dependency PR needs a conflict resolution, resolve only its lockfile or
   pin line; do not absorb unrelated changes.

Acceptance:

- `#379` merged with green required checks as `877ecb92`; it is the merge that
  carries the dependency lines.
- `#378`, `#370`, `#369` and `#357` are satisfied by content equivalence
  through `#379`, not by their own merge. The split-pin family could not pass
  the required checks individually -- one Renovate PR carried four pin sites in
  one family, and a partial bump fails the build -- so `#379` is the merge that
  carries those lines and the four PRs are closed as superseded, each with that
  reason on the PR. Content parity on `main` is recorded in section 10.
- `GET /api/v1/repos/saenta/containeromat/branch_protections` shows every
  required context reports on the PRs.
- No new red dependency PR remains.

Stop conditions:

- `#379` fails for a reason outside Renovate grouping.
- A required check is missing because its workflow is retired. Fix the branch
  protection or report; do not bypass.

### WP-02 -- State-doc reconciliation

Goal: remove stale pins and stale gate descriptions from the two repos.

Library files:

- `PLAN.md`: replace `0490cb7` / `886f186` with the current pin; update the
  deferred "consumer re-vendor" and "live deployment" lines.
- `docs/SYNC.md`: current pin and 24/24 state.
- `CATALOG.md`: current pin line.
- `docs/knowledge-base/integration-status.md`: current pin and 24/24 state.
- `docs/knowledge-base/skill-prompt-refactor-2026-10.md`: R4 is "design done,
  measurement pending"; AS-01..AS-12 in the current row.
- `README.md`: confirm 2.6.0 and the OMP row.

Containeromat files:

- `docs/runbooks/neutral-agent-source.md`: current library pin and version.
- `docs/runbooks/skills-library-change.md`: history uses the current pin.
- `docs/runbooks/forgejo-registry-image.md`: required-check list must match the
  live branch protection; remove retired OpenHands/deep-research references.

Acceptance:

- `rg '0490cb7|886f186|2\.5\.2|Build OpenHands|deep-research'` returns only
  historical changelog/evidence entries, never a current-state claim.
- Library `make gate` exit 0.
- Containeromat `python3 scripts/verify-agents.py` and `ci-replica.sh --fast`
  exit 0.

### WP-03 -- CI and branch-protection contract

Goal: make the written contract, the active workflows, and branch protection
agree.

Steps:

1. Read `GET /api/v1/repos/saenta/containeromat/branch_protections`.
2. Compare against `.forgejo/workflows/*` and
   `scripts/lib/check_workflows.py` `REQUIRED_WORKFLOW_NAMES`.
3. Remove any required context whose workflow is retired. Add any active
   required workflow missing from the runbook's list.
4. Update the runbook and the checker comment so the next reader sees one list.

Acceptance:

- Every required context has an active workflow that reports on every PR.
- `python3 scripts/lib/check_workflows.py` passes.
- The runbook names the same contexts as the live API.

### WP-04 -- R4 live cache baseline

Status: **measured 2026-10-27 for `anthropic-5m`**, three seeds, nine of nine
requests completed. Audit: two PASS and five low findings, all fixed in the
closeout below. Not general: one prefix, one model, one gateway route.
Command, table and limits are in
`docs/knowledge-base/r4-cache-and-canon-2026-10.md` section 3.6; the aggregate is
`evals/cache/r4-anthropic-5m-2026-10-27.json`.

Goal: replace the static R4 coverage table with a measured hit-rate baseline.

Design source: `docs/knowledge-base/r4-cache-and-canon-2026-10.md`.

Steps:

1. Choose one profile with a real cache minimum and telemetry: `deepseek-prefix`,
   `anthropic-5m`, or `anthropic-1h`.
2. Run three seeds, one cold and one warm run per seed, using the
   `agent-prompts-harness/2` telemetry fields:
   `prefix_hash`, `first_divergent_layer`, `seconds_since_last_request`,
   `cache_hit_tokens`, `cache_read_tokens`, `cache_write_tokens`,
   `cache_write_ttl_class`, `cost_usd`, `duration_ms`.
3. Compute hit rate, TTL hit, cost per verified unit, latency, and divergence
   distribution.
4. Record the raw runs outside the repo; commit only aggregates and the method.
5. Update the R4 document and `docs/knowledge-base/skill-prompt-refactor-2026-10.md`
   R4 row.

Acceptance:

- At least one profile has a recorded baseline with three seeds and a warm run.
- `python3 tooling/check_token_efficiency.py` remains green.
- No prompt body changes.

Blocked state:

- If DeepSeek returns 402 or OpenAI 401, record BLOCKED with the exact provider
  and error. Do not call the free structural proxy a cache measurement; it has
  no provider cache telemetry.

### WP-05 -- Canon consolidation (external-canon role)

Status: **closed 2026-10-27 as already satisfied (option A).** No
`skills-roots/3` and no `role: external-canon` were added. The evidence and the
per-skill disposition are in section 10, "Wave 3 closeout".

Goal as written: remove the single-canon blocker for the 6 multi-root dsh
candidates plus the 3 single-instance skills.

Why the goal was already met:

- `containeromat:scripts/skills-roots.json` declares one `role: canon` root: the
  LOCAL canon, `.openhands/skills`. `containeromat:scripts/skills-library.json`
  declares `canonRoot: agent-prompts`, and its `skills` map is the ownership
  declaration.
- `check_library_canon` resolves every copy of a library name -- including that
  name's copy under `.openhands/skills` -- against the library body;
  `check_skill_copies` and `check_skill_reference_copies` resolve every other
  name against the local canon. That is one owner per name, and the
  exactly-one-canon rule only forbids a second LOCAL canon root.
- The nine dsh-root names absent from the library are not nine copies without a
  canon: six carry a local canon row plus three runtime copies, and three
  (`kilo-review`, `seifomat-dev`, `seifomat-dev-debug`) are single instances in
  the dsh root.

Delivered instead of the schema bump:

1. A contract test that fails a name copied into two or more registered roots
   when neither canon owns it (the guard the schema change was meant to buy),
   and one that fails a local copy whose body disagrees with the library canon.
   Both were proven by mutation.
2. The registry `note` and the `skills_roots.py` docstring corrected: their
   "single `role: canon`, no per-root pointer" wording is what this WP read as
   the blocker.
3. The consumer runbook gains a "Canon ownership" section; a KB entry records
   the decision; both repos carry a changelog entry.

Acceptance (met):

- The registry validates unchanged (`skills-roots/2`).
- `containeromat:verify-agents.py` passes with both canon sources: 24/24 library
  names, 99 library copies.
- A name copied into two roots without an owner fails the contract test, and a
  local body that disagrees with the library canon fails.
- No skill body moved, so no paired baseline was required; the follow-up below
  inherits that rule.

Follow-up, not this WP: moving a project skill into the library is content work
-- generalize the body, add the catalog row, register it in
`skills-library.json`, re-vendor the copies, then drop the local canon row --
and the paired baseline comes before any body change.

### WP-06 -- Semantic trigger check

Goal: measure routing that the lexical checker cannot see.

Status: **delivered 2026-10-27 as an advisory report.**
`tooling/check_semantic_routing.py` judges the existing 24 skills and 24 case
files (126 prompts); the lexical gate is unchanged. Evidence:
`docs/knowledge-base/semantic-trigger-check-2026-10.md`.

Steps:

1. Add an embedding or judge-based check beside
   `tooling/check_skill_routing.py`, using the same `evals/trigger/*.json`
   cases.
2. Keep the lexical check as the free CI gate; the semantic check is on demand
   or a separate scheduled job.
3. Report false positives, false negatives and near-collisions per skill.
4. Do not replace the lexical gate without a measured improvement.

Acceptance:

- The semantic check runs on the existing 24 case files.
- Its findings are recorded as a report, not a hard gate, until a threshold is
  agreed.
- `check_skill_routing.py --fail-on-warn` remains green.

### WP-07 -- Context-file template and conduct placement

Goal: test two P2 hypotheses with paired evidence.

Status: **delivered 2026-10-27.** The template is `docs/AGENTS-TEMPLATE.md`;
both experiments ran on the Kilo gateway, and the conduct variant is not
promoted. Evidence:
`docs/knowledge-base/context-template-and-conduct-2026-10.md`.

Steps:

1. Add a short AGENTS.md router template under `prompts/workspace/` or
   `docs/` (choose the existing convention) with commands, conventions,
   verification, and pointers.
2. Run the paired test from S13/S14 on one real repository; cut any section that
   does not change success, cost, or runtime.
3. Test a one-line data-not-instructions rule in `hard_rules` while keeping the
   conduct fragment byte-exact. The goal is the injection guard at both ends of
   the prompt, not moving the fragment.
4. Record non-inferiority or rejection.

Acceptance:

- A paired result exists for each experiment.
- No fragment content changes; fragment hashes stay pinned.
- A rejected experiment is recorded as rejected, not silently dropped.

### WP-08 -- P3 optimization loop

Goal: turn labelled failures into a human-gated optimization cycle.

Steps:

1. Build a 20-40 case labelled set from real failures.
2. Run a reflective optimization experiment (GEPA/ACE style); an optimized
   prompt is a proposal, not a merge.
3. Extend the paired benchmark across the supported models and harnesses;
   report per-configuration deltas.
4. Track cost, latency and tokens per run.
5. Automate the re-baseline trigger: a model or harness change opens an eval
   run; a prompt change without a baseline is blocked.

Acceptance:

- One proposal per cycle, human-gated.
- Cost and latency are reported beside pass rate.
- A model/harness change cannot silently invalidate a baseline.

Status (2026-10-27): **delivered; one provider configuration BLOCKED, the rest
measured.** A 38-case labelled set (`evals/optimization/failure-set.md`) draws
only on committed artifacts: each row names its source file and an anchor string
that must still appear there after whitespace normalization, exactly once, and
`tooling/check_failure_set.py` fails when one stops resolving or turns
ambiguous. The human-gated ledger (`evals/optimization/proposals.md`, plus
`proposals.schema.json` and an instance) is checked by
`tooling/check_optimization_ledger.py`: `accepted` needs an approved gate and a
paired result, and rejected or accepted rows must name the committed
measurement. Cycle 1 (`P-1`) ran a reflective edit on the operations executor
over held-out seeds 401/409/419 in two configurations and **rejected** it: the
candidate tied the production body (config A 0.6667 vs 0.6667, config B 0.5000
vs 0.5000) and the two target expectations stayed at 1/3 and 1/3 in A and 0/3
and 0/3 in B for both arms, so no quality gain is claimed. Cost, mean latency
and tokens are recorded per configuration beside the scores. Cycle 2 (`P-2`),
the canonical DeepSeek confirmation, is **BLOCKED** at HTTP 402
`insufficient_balance_error`; OpenAI direct returns 401 and no substitute was
used. The re-baseline trigger (`tooling/check_rebaseline.py`) compares the
`model`, `harness`, `prompt_version`, `grader` and `cache_epoch` fields of a
baseline record with a current campaign or telemetry record and requires a new
baseline when they differ. Record: `docs/knowledge-base/optimization-loop-2026-10.md`.

### WP-09 -- Long-horizon live validation

Goal: move LH-01..LH-14 from design-by-evidence to a live run.

Steps:

1. Run one real multi-session task with run state and the append-only journal.
2. Measure LH-13 metrics: units per hour, tokens per verified unit, recovery
   time, stall count.
3. Decide whether `lease`, `## In-flight` and idempotency need runtime
   enforcement or remain recorded fields.
4. Record the result in the long-horizon evidence file.

Acceptance:

- One deployed harness run with state, checkpoints and resume.
- Metrics recorded; a runtime decision recorded.
- No phase is added to the loop by this item (the plan-review phase that now
  precedes Implement was added to the loop itself in Wave 13, not by the
  long-horizon layer).

Status (2026-10-27): **deferred to November, local exercise delivered.** A
two-session exercise with the checked-in tooling now exists at
`evals/long-horizon/` (state, journal, replay, two probes), and the runtime
decision is recorded: `lease`, `## In-flight` and idempotency stay recorded
fields; the one closable gap, view/journal hash agreement, is enforced by
`check_run_journal.py --state`. The deployed-harness run and the LH-13 A/B are
deferred to November because dsh and zcode are inactive and will not be deployed
in this cycle (`dsh` resumes in November; `zcode` has no date and is not
applicable this cycle); they are not waiting on an operator action now. The
local exercise remains the only evidence, and no live metric is claimed. See
`docs/knowledge-base/long-horizon-agents-2026-10.md` section 6.1.

### WP-10 -- OMP and runtime reload validation

Goal: prove the generated projection and re-vendored skills load in a live
session.

Status (2026-10-27): **closed for this cycle.** The projection half is proven
(Wave 2 closeout; the six project agents and 24 projected skills load and the
brief matches). The seeded runtime half is not applicable: dsh and zcode are
inactive and will not be deployed in this cycle (`dsh` regains usage in
November; `zcode` has no date), so no seed-marker reload, redeploy or gate work
is owed. Their roots stay in the consumer, inert. The steps below re-enter only
when `dsh` is deployed again.

Steps:

1. Rebuild/reload the containeromat runtime so the current library pin and the
   seed markers are live.
2. Start an OMP session; verify `.omp/agents/` and `.omp/skills/` load and that
   the session prompt block applies.
3. Run one read-only delegation and one skills trigger.
4. Record what is observed and what remains unobserved.

Acceptance:

- The generated projection loads; no unresolved slots.
- The skills copy is visible to OMP.
- A live observation is recorded; do not claim success from file presence alone.

### WP-11 -- H2 confirmation on canonical model

Status: BLOCKED at the provider, 2026-10-27. `$DEEPSEEK_API_KEY` authenticates
(`GET /v1/models` -> HTTP 200) but every chat call returns HTTP 402
`insufficient_balance_error` ("Insufficient Balance", request
`9394191c-8230-4ef2-b55f-e04edebcf291`). The A/B command was not run; no
canonical-model result exists. Evidence and the exact pending command are in
`docs/knowledge-base/h2-shape-ab-2026-10.md`.

Goal: confirm the H2 A/B on the canonical DeepSeek model when credits return.

Steps:

1. Re-run `tooling/run_refactor_ab.py` for the seven skills, seeds 7/11/23,
   against `2cd4e43`.
2. Compare with the recorded 0.899 old vs 0.9345 new and 56/66 vs 57/66.
3. Update `docs/knowledge-base/h2-shape-ab-2026-10.md` with the confirmation or
   the discrepancy.

Acceptance:

- A canonical-model run exists.
- If it differs materially, reopen the affected merge; do not overwrite the
  free-model result.

### WP-12 -- Optional guard tightening

Status: executed 2026-10-27 on operator decision (two of the four candidates).
Closeout in section 10.

Foreground-policy decision (operator, 2026-10-27): the full six-module
foreground policy is retained as a compliance guardrail -- it states read-only
subagents, the evidence duty, destructive-action gating and the authority order
-- and no efficacy claim is made for it. The primary A/B returned loss under the
pre-registered rule on one anomalous malformed run (`07/317`, counted three
times); without it the same rule returns gain, and read-only delegation is the
only behaviour that improved in both runs (0/3 -> 3/3). The measured cost is an
extra 616 input tokens per run (+41.8%), output -121 per run, +1.8% at list
price and zero invoice cost on `go-plus`, and no claim of improved outcomes is
made anywhere.

Goal: backlog items that need an operator decision, not autonomous execution.

Candidates and dispositions:

- Raise the test floor from 330 to 334 if the suite is stable for a week.
  **Superseded.** A count floor cannot hold a 441-test suite: 111 tests of
  headroom means a hundred deletions still pass. Replaced by an add-only
  test-identity manifest (`tooling/test-manifest.json`,
  `agent-prompts-test-manifest/1`): a plain `check_test_floor.py` run fails when
  the manifest names a collected test the suite no longer contains, additions
  pass unrecorded, `--write` merges new names without pruning, and only
  `--write --allow-removals` drops a name (printing each removal). `FLOOR = 330`
  stays as a secondary backstop against a gutted manifest. The count stays a
  side condition, not the guard.
- Decide whether `convert-documents-to-markdown` should be distributed beyond
  dsh. **Still open** (operator decision; not touched here).
- Triage any remaining role token warnings; currently zero. **Unchanged.**
- Decide whether the OMP projection should render more roles. **Decided and
  implemented.** The projection is now every projectable read-only role plus the
  single orchestrator: 12 entries, six added (`oracle`,
  `consistency-reviewer`, `researcher`, `librarian`, `research-merger`,
  `councillor`). Eleven read-only roles are deferred with a one-line reason in
  `omp/catalog.yaml` (`design-ui-reviewer`, `net-network-architect`,
  `council-synthesizer`, the eight review tracks); the 15 write-capable
  templates stay out because the projection never grants `write`, `edit` or
  `bash`. `council-synthesizer` was projected for part of the day and moved to
  `deferred:` on the same day (see "council-synthesizer deferred" below).
  `render_omp.py --check` enforces read-only coverage, a no-tools guard, a
  700-token description budget (v2 uses 420), and prints the computed hash for a
  stale pin. Record:
  `docs/knowledge-base/omp-projection-selection-2026-10-27.md`; policy:
  `omp/README.md`.

Acceptance: operator decision recorded; no code change until then. Satisfied for
the two executed candidates: the decision is recorded here, and the change is
tooling, catalog and documentation only -- no prompt body, skill, fragment or
`agents/**` edit.

Follow-up (consumer, separate change): the containeromat agent pack needs the
seven new entries before its next render, then re-render `.omp/agents/` and bump
the `agent-prompts` gitlink; the pack's `library_version` moves to 2.8.0 with it,
and the same change renders `.omp/APPEND_SYSTEM.md` (below).

#### WP-12 follow-up (2026-10-27): foreground orchestration policy

The main session needs a policy the subagents do not get: delegate reads,
mutate only here and only with approval, prove completion with exit codes. OMP
already splits those channels -- it discovers
`<project>/.omp/APPEND_SYSTEM.md` (or `~/.omp/agent/APPEND_SYSTEM.md`) for the
main session, and `packages/coding-agent/src/task/executor.ts` builds subagent
session options without `appendSystemPrompt` -- so the policy can be shipped as
that file instead of as a fourteenth agent.

- `omp/foreground.md`: plain Markdown, no frontmatter, 37 lines, 389/400 tokens
  at `bytes // 4`, slots `PROJECT_ID`, `PROJECT_RULES`, `VERIFICATION_COMMANDS`,
  `SAFETY_RULE`. One delegation line per projected agent; no tool grants.
- `omp/catalog.yaml` is `omp-catalog/3` with a required `foreground:` block
  (`source`, `sha256`, `slots`); the /2 checker rejected the unknown top-level
  key, so the schema names it instead of tolerating it silently.
  `library_version` is 2.8.0.
- `render_omp.py --foreground --pack P --out F` fills the slots from the same
  pack and writes plain Markdown; `--check --foreground` validates the block,
  slot declarations and pin; a plain `--check` checks the pin too. The budget is
  printed like the description budget. Subagent rendering is untouched.
- Evidence: `docs/knowledge-base/omp-foreground-policy-2026-10-27.md` -- the
  ZQ7-PINEAPPLE sentinel reached the main session and not the `scout` subagent on
  OMP 18.13.0, reproduced 2026-10-27; headless `task` needs an approval grant.

Follow-up (consumer, separate change): render `.omp/APPEND_SYSTEM.md`, add a
byte-compare step for it in `scripts/verify-omp-agents.py`, add the seven v2 pack
entries, re-render `.omp/agents/`, and bump the gitlink and the pack's
`library_version` to 2.8.0. The library side is green without it.

##### Module set replaces the single file (2026-10-27)

A single 389-token file could not carry governance, safety and output rules
without crowding out delegation, and it had no per-section pin. It is replaced
by six modules under `omp/prompts/foreground/`, still sent through the same
`.omp/APPEND_SYSTEM.md` channel, so the sentinel evidence above still applies:

| Module | Scope | Budget | Measured |
|---|---|---|---|
| `00-authority.md` | foreground authority; operator > policy > runtime defaults; you own the reply | 90 | 78 |
| `10-delegation.md` | 12-name dispatch list, one line each; delegate vs inline; subagents read-only | 170 | 157 |
| `20-evidence.md` | completion needs a command and its exit code from this run; subagent output is testimony | 120 | 84 |
| `30-governance.md` | project gates are the definition of done; ASCII; knowledge base; no CI runner | 150 | 121 |
| `40-safety.md` | destructive git, deploy and data operations operator-gated; no secrets; BLOCKED | 100 | 89 |
| `50-output.md` | lead with the answer; file:line; no tool-output restatement | 70 | 56 |

Total 588/700. `manifest.json` (`omp-foreground-set/1`, id `omp-foreground/1`)
holds the compose order, the per-module sha256 pins, the per-module budgets and
the total; `omp/catalog.yaml` is `omp-catalog/4` and its `foreground:` block is
`id` + `modules` + `slots`. The renderer composes in manifest order with one
blank line, fills the slot union, and refuses a missing, extra or reordered
module, a stale per-module pin (printing the `"<module>": "<hash>"` line), a
slot-declaration mismatch, a per-module overrun, or a total over the manifest
budget or the renderer ceiling. Both budget levels are ceilings; raising either
is a deliberate decision recorded as a rationale line in `omp/README.md` plus
the manifest/catalog update, which closes the Wave 7 low about the budget error
pointing at a silent README.

Evidence and limits: `docs/knowledge-base/omp-foreground-policy-2026-10-27.md`
section 5. No new propagation claim; the module split is untested against the
single file.

Consumer follow-up: the render and byte-compare commands are unchanged; re-render
`.omp/APPEND_SYSTEM.md` and bump the gitlink and pack `library_version` to
2.9.0.

##### council-synthesizer deferred: a no-tools canon is not projectable (2026-10-27)

`council-synthesizer` was projected with `tools: [read, grep, glob]`, which
contradicts its canon: `agents/orchestration/orch-council-synthesizer.md:33`
declares `{{MUTATION_POLICY}}: no tools -- synthesize from the provided
responses only`. OMP cannot express "no tools" safely. In
`src/task/executor.ts` the tool list is applied only `if (agent.tools)`, so an
absent list means the broad default set, and `read-only-policy.ts` treats an
empty list as not read-only. A non-empty list grants tools the canon forbids;
omitting the list grants more. The role is therefore not projectable under the
read-only posture.

- Selection: 12 projected entries, 11 deferred read-only roles; the
  description sum drops from 446 to 420 tokens. `omp-catalog/4` is unchanged.
- Guard: `render_omp.py --check` now fails a projected role whose canon declares
  no tools (the `no tools` phrase on the `{{MUTATION_POLICY}}` line or an
  equivalent), naming the role and pointing at `deferred:`. Test:
  `test_role_that_declares_no_tools_must_be_deferred`.
- Dispatch list: `10-delegation.md` drops the `council-synthesizer` line (12
  names, 157/170 tokens); its module pin is refreshed and the composed set is
  588/700.
- Consumer follow-up (separate writer, same wave): the containeromat pack must
  drop its `council-synthesizer` entry while adding the six v2 entries and
  bumping the gitlink and `library_version`.
- Record: `docs/knowledge-base/omp-projection-selection-2026-10-27.md`.

##### Foreground policy behaviour A/B (2026-10-27)

The sentinel experiment proved propagation; it did not measure behaviour. That
gap is now closed with the existing role-A/B harness, extended to accept several
tasks per role rather than forked:

- `tooling/run_role_ab.py`: `--tasks-dir` may hold `{role, prompt, expectations}`
  files whose stem is the task id, beside the original `<role>.json`. Results are
  written one file per (role, task) and carry `task`; the legacy single-task path
  and file names are unchanged.
- `tooling/summarize_role_ab.py`: keys rows by (role, task, seed, arm) and labels
  them `<role>/<task>`; a single-task role still labels by role alone. Usage,
  expectation tallies and win/tie/loss aggregate over both shapes.
- Pre-registration:
  `evals/role-ab/pre-registrations/wp-12-foreground-policy.md` (written before
  the run; margin 0.05, targeted-behaviour gain required).
- Tasks: `evals/role-ab/tasks-foreground/`, 8 text-only cases for
  `orch-orchestrator`, one per policy claim (delegation, read-only delegation,
  evidence, unverified gate, destructive approval, authority precedence, output
  discipline, blocked honesty).
- Run: candidate = the policy rendered with the containeromat pack and prepended
  to the same role body; executor `anthropic/claude-haiku-5.5`, grader
  `openai/gpt-6-luna`, seeds 311/313/317, `--max-tokens 2048`.
- Result: task success 11/24 current vs 13/24 candidate; mean score 0.7639 vs
  0.8472; paired ties 18, candidate ahead 6, current ahead 0; no truncation and
  no provider error. The gain is the delegation module: scout dispatch 0/3 ->
  2/3 and read-only refusal 0/3 -> 3/3, plus conflict naming 2/3 -> 3/3. The
  evidence, gate, safety, output and blocked probes were at or near ceiling in
  both arms, so those modules are not shown to add anything here.
- Verdict: **gain**, pre-registered decision rule met. That makes the policy a
  candidate for retention, not for promotion; no consumer text changed. The
  operator's 2026-10-27 decision (WP-12 status) keeps the policy as a compliance
  guardrail with no efficacy claim; that is not a re-reading of this verdict.
- Evidence: `docs/knowledge-base/foreground-policy-ab-2026-10-27.md` and
  `evals/role-ab/results/wp12-foreground-policy-2026-10-27.json`.

## 6. Subagent brief template

Copy this into a dispatch prompt:

```text
WP: <id and title>
Repo: <agent-prompts | containeromat>
Branch: <branch>
Dependencies: <merged WPs or none>
Concurrency: one of at most two parallel agents; stop before the wave audit
Goal: <one sentence>
Files: <exact paths>
Non-goals: <what not to touch>
Steps: <numbered, from this plan>
Acceptance: <commands and expected result>
Stop conditions: <gate, credential, conflict>
Deliverable: <PR, report, or blocked note>
```

## 7. Cross-cutting gates

Library:

```text
make gate
python3 tooling/check_token_efficiency.py
python3 tooling/check_skill_routing.py --fail-on-warn
python3 tooling/check_behavioral_evals.py
python3 tooling/report_skill_shape.py
```

Containeromat:

```text
python3 scripts/verify-agents.py
python3 scripts/skills-manifest.py
bash scripts/verify-skills-seed-version.sh
bash scripts/check-prompt-drift.sh
bash scripts/verify-ascii.sh
PATH="$HOME/.local/bin:$PATH" bash scripts/ci-replica.sh --fast
```

Seifomat (only if touched):

```text
bash scripts/check-rule-paths.sh
bash scripts/check-markdown-lint.sh
```

## 8. Definition of done

A WP is Done only when:

- its acceptance commands pass locally;
- its PR is merged or its report is committed;
- the changelog or evidence record names what changed and what was not verified;
- no stale pin, retired required check, or unresolved consumer copy remains;
- the wave's two audit agents have both passed, with no open high/medium
  finding in the ledger.

## 9. Frozen and not planned

- Vendor skill bodies: `caveman*`, `misakanet`; frozen under SK-10.
- The full doctrine fragment: retained after the A/B; not replaced by the
  doctrine-light variant.
- A second canon root: not needed. Ownership is per name in
  `containeromat:scripts/skills-library.json`; WP-05 closed on that evidence
  (2026-10-27).
- Raising every carrier above the OpenAI/Gemini cache minimum: not a library
  goal; prefix size is a workload decision.

## 10. Wave ledger

### Runtime status and open items (operator, 2026-10-27)

Operator statement: dsh and zcode are **inactive** and will not be deployed in
this cycle. `dsh` regains usage in November; `zcode` has no date and is **not
applicable this cycle**. Only `opencode-go` is active, on
`deepseek-v4.1-flash`.

Effect on the blocked items:

- WP-09 (deployed-harness run and LH-13 A/B): **deferred to November**, not
  blocked and not awaiting an operator action now. The local run-state exercise
  is the only evidence; no live metric is claimed.
- WP-10's seed-marker reload: **closed**, not blocked. No reload, redeploy or
  gate work is owed while dsh and zcode are stopped.
- The dsh and zcode skill roots: inert. No re-vendor, re-seed or seed-marker
  bump is an outstanding task, and the roots stay in the consumer.
- Unchanged and unrelated to runtime status: WP-11 (DeepSeek credit, HTTP 402),
  WP-06's third run (Kilo free-model 429), WP-08 cycle 2 (canonical provider),
  and the unmeasured R4 cache profiles (no provider with cache telemetry).

### Wave 1 closeout (2026-10-27)

Operator acceptance: the operator directed autonomous implementation of this
plan after the WP-02 audit blockage and asked for these fixes to be recorded, so
the WP-01 acceptance amendment above is recorded here as that operator
acceptance record.

Containeromat dependency queue (WP-01):

- `#379` (`fix/unmergeable-prs`) merged as `877ecb92`. It groups pin families
  by depType, so one pin is one PR.
- `#378`, `#370`, `#369` and `#357` closed as superseded, not merged. Content
  parity was verified on `main` after the closes: `stacks/paseo/Dockerfile:487`
  (`@oh-my-pi/pi-coding-agent/18.13.0`), `stacks/paseo/Dockerfile:1134` and
  `stacks/paseo/plugins.manifest.json` (`geoqiao/paseo-stuff` `8d2a3de4`),
  `stacks/paseo/Dockerfile:1143` and the same manifest
  (`yannelli/paseo-prompt-manager` `8abd00d6`).
- `#383` (ruff 0.17.3 across every pin site) merged as `9d7f6018`; `#380`, the
  single-site ruff PR, closed as superseded. `saenta/containeromat` has no
  open dependency PR (checked 2026-10-27); `#388` is a separate feature PR
  outside Wave 1 scope.

State-doc reconciliation (WP-02):

- `#47` in this repo plus containeromat `#384` and `#385` merged. Current pins,
  the R4 row, the required-check list and the no-runner knowledge entry are
  reconciled; the follow-up fix PRs carry the audit findings below.

Wave 1 audit:

- The `code-skeptic` findings ledger plus `reviewer`'s concurrent review
  reported nine findings: one high (no WP-02 changelog entry), three medium (the
  non-literal WP-01 acceptance, a stale present-tense 2.5.2 claim, and a
  rewritten historical `0490cb7`), and five low (`tooling/gate.sh` committed
  non-executable, an inaccurate "library main" parenthetical, the `755a3fd4`
  citation, wording that makes the retired required checks read as still
  listed, and a re-pin dated 2026-10-27 when the gitlink moved on 2026-10-26).
- Composition note (re-baselined 2026-10-27, Wave 2 audit residual L-1): this
  list read eight findings until `3ef757a` added the re-pin-date item as the
  fifth low, which is where the count became nine. The substitution is stated
  here instead of the count being recomputed silently. The `#380`/`#383` queue
  history lives in the WP-01 closeout above (`#383` merged as `9d7f6018`,
  `#380` closed as superseded), and the Wave 2 audit's own queue item -- open
  `#388` outside Wave 1 scope -- is closed in the Wave 2 closeout below (LOW 4).
- One item stayed unverified: the library `gate / gate` check cannot report a
  verdict, because `saenta/agent-prompts` has no registered Actions runner, so
  the local `make gate` output is the only evidence for that repo.
- Fixes: changelog entries in both repos; the WP-01 amendment and this ledger;
  the historical `0490cb7` move kept at 2026-10-26, and the `b1ea951` re-pin
  corrected to 2026-10-26 in both repos; `tooling/gate.sh` committed
  `100755`; the remaining wording and citation fixes. The auditors re-check
  only these changes, read-only, after the fix PRs merge.

### Wave 2 closeout (2026-10-27)

The Wave 2 audit raised two medium and five low findings. All are closed here;
the wave's implementation PRs are containeromat `#387` (WP-10 live validation)
and `#389` (WP-03 required-check contract).

- **F1 (medium 1, owner WP-10) -- the OMP `library_commit` was described as the
  whole canon, and it is not.** `agent-prompts/omp/catalog.yaml` called
  `library_commit: 2cd4e43` "the canon this projection was built from --
  agents/** and fragments/**", but `2cd4e43` has no
  `fragments/agent-conduct.omp.md`: that file was added on the projection branch
  in `94629f0` and last edited in `695fd8b`, and `2cd4e43` is an ancestor of
  neither. The rest of the label does hold: at `2cd4e43` the `sha256` of
  `agents/engineering/eng-explorer.md` and `fragments/agent-doctrine.md` equal
  the catalog's `templates_sha256` and `fragment_sha256.doctrine` pins,
  `fragments/agent-conduct.omp.md` at HEAD hashes to
  `fragment_sha256.conduct`, and its `<conduct>` body is present verbatim in all
  six rendered agents.
  **Disposition: semantics restated, no pin bump and no re-render.** `2cd4e43`
  is intentionally pre-OMP for `agents/**` and the doctrine fragment; the OMP
  conduct variant is pinned by its own hash; the catalog comment, the library
  changelog and the consumer runbook now say exactly that. The earlier report
  that assigned this to WP-05 was wrong -- the owner is WP-10.
- **F2 (medium 2, owner WP-10) -- the consumer runbook carried a stale pin.**
  `docs/runbooks/neutral-agent-source.md` said both packs "read `ff91dc3`
  today"; both read `2cd4e43`, and `ff91dc3` is only the merge-base of the
  pre-OMP canon and the projection branch. Corrected in place, with the canon
  description aligned to the catalog wording.
- **LOW 3 (owner WP-10).** `scripts/lib/tests/test_check_workflows.py` hoists the
  `scripts/lib` path insert from the one test method to module scope, so the file
  passes standalone as well as under full discovery.
- **LOW 4 (owner WP-10).** The Wave 1 ledger above now reads "no open dependency
  PR" and names `#388` as a separate feature PR outside Wave 1 scope.
- **LOW 5 (owner WP-10).** The Wave 1 audit attribution now names the
  `code-skeptic` audit report plus `reviewer`'s concurrent review, instead of
  claiming two persisted ledgers when neither produced a committed ledger. The
  wording is `audit report`, not `persisted ledger`: no wave ledger file is
  committed in this repository (`ls provenance/findings-*.md` has only the
  external-scan ledger), which is Wave 2 audit residual L-2.
- **LOW 6 (owner WP-10).** The `required-check-contract` knowledge entry carries
  `review_by: 2027-04-30`.
- **LOW 7 (owner WP-10).** The OMP live-inventory entry records the exact probe
  commands and observed output (brief quote, agent list, skill count,
  `git-guardrails` trigger, `scout` README result) instead of narrating them.

WP-10 live validation stands as merged: the projection loads in a live session
(six project agents, 24 projected skills plus six user-scope `paseo*` skills,
brief quoted verbatim, skill trigger and `scout` delegation correct). The seeded
runtime half is **closed, not blocked**: dsh and zcode are inactive and will not
be deployed in this cycle (`dsh` regains usage in November; `zcode` has no date
and is **not applicable this cycle**), so no seed-marker reload, redeploy or gate
work is owed. Their skill roots stay in the consumer and are inert while the
runtimes are stopped; no re-vendor or re-seed is an outstanding task. Check
observation: neither stack is deployed on this host and the session holds only
the read-only `paseo-ds-proxy` socket.
### Wave 3 closeout (2026-10-27)

Canon consolidation (WP-05) -- decision **A plus a per-skill disposition**: the
external library registry already supports the split, so no schema change.

- No `skills-roots/3`, no `role: external-canon`, no name-ownership map in
  `skills-roots.json`. `containeromat:scripts/skills-roots.json` stays
  `skills-roots/2`; `containeromat:scripts/skills-library.json` stays
  `skills-library/1` and its `skills` map remains the ownership declaration.
- The resolution already existed: `check_library_canon` verifies every copy of a
  library name -- including that name's copy under the local canon root
  `.openhands/skills` -- against the library body, while `check_skill_copies` and
  `check_skill_reference_copies` compare every other name with the local canon.
  The exactly-one-canon rule forbids a second LOCAL canon root only.
- Measured in containeromat: 38 skill names across the 6 registered roots, 33 of
  them in more than one root -- 24 library-owned, 9 local-owned, none unowned.
  `verify-agents.py` reports 24/24 library canon matches over 99 copies.
- Two different nines appear in this record and are not the same set: the nine
  local-owned names among those 33 multi-root names, and the nine dsh-root names
  absent from the library. They overlap in the six multi-root dsh candidates;
  the other three local-owned multi-root names are not dsh-root names, and the
  other three dsh names are the three single-instance skills.
- The count in section 4.1 of
  `docs/knowledge-base/r4-cache-and-canon-2026-10.md` was wrong in one respect:
  the nine dsh-root names absent from the library are the six multi-root dsh
  candidates plus the three single-instance skills, not nine skills living in
  the containeromat canon root. The six (`compose-audit`, `compose-smoke`,
  `compose-step`, `doubt-driven-review`, `forgejo-registry-image`,
  `knowledge-capture`) carry a local canon row plus three runtime copies; the
  three (`kilo-review`, `seifomat-dev`, `seifomat-dev-debug`) exist in exactly
  one root each, so they are instances, not copies.
- Per-skill disposition: all nine stay local and none migrated, because a
  migration is content work (generalize the body, add the catalog row, register
  the name, re-vendor, drop the local row) and needs the paired baseline before
  any body change. The six multi-root skills are the first candidates; the three
  single-instance skills are recorded as project-instance by design.
- Guards added in containeromat instead of the schema bump: a contract test that
  fails a name copied into two or more registered roots with neither canon
  owning it, and one that fails a local copy whose body disagrees with the
  library canon. Both were demonstrated by mutation -- an extra `kilo-review`
  copy under `stacks/zcode/config/skills` and a rewritten local
  `anti-hallucination` body each turned the suite red and green again after the
  restore.
- The registry `note` in `skills-roots.json` and the `skills_roots.py` docstring
  said copies resolve "from the single `role: canon` root ... because exactly
  one canon is enforced". That wording is what made this WP look like a schema
  task; both now name the external canon and say ownership is per name.
- Documentation: `containeromat:docs/runbooks/skills-library-change.md` gains a
  "Canon ownership" section; `containeromat` KB entry
  `skill-canon-ownership-two-registries` records the decision; both repos carry a
  changelog entry. The `agent-prompts` pin in containeromat is deliberately
  unchanged, because only library docs moved here -- no skill body.

WP-04 (R4 live cache baseline) did not start: no provider with cache telemetry is
configured for the harness, which is the WP-04 blocked state. It stays open for
Wave 4; nothing in this wave is evidence about cache hit rates.

Wave 2 audit residuals carried into this wave:

- L-1 (plan ledger, "nine findings"): stated as a composition note above, not by
  recomputing the count. The stale `#380`/`#383` queue item is recorded in the
  WP-01 closeout.
- L-2 ("persisted code-skeptic ledger"): closed by wording, not by committing a
  ledger. The audit-closeout step now says the auditors report findings and the
  owner records them in section 10, and the merged Wave 2 closeout LOW 5 line
  says `audit report` instead of `persisted ledger`; `provenance/findings-*.md`
  holds only the external-scan ledger, so no wave ledger exists to point at.
- L-4 (`README.md:1` as a path token): fixed in
  `containeromat:docs/knowledge-base/omp-live-skill-inventory-includes-user-scope.json`;
  the entry now names `README.md` line 1 in `detail` and keeps the path list
  free of line suffixes.

Gate evidence (local, because this repository has no registered Actions runner):
`containeromat` unittest discover 1444 tests OK (skipped=1; measured 2026-10-27);
`verify-agents.py` PASS; `skills-manifest.py` PASS (111 skills, 5 roots);
`verify-knowledge-base.sh` PASS (205 entries); `check-prompt-drift.sh` OK;
`verify-ascii.sh` PASS; `ci-replica.sh --fast` "PASS - full battery green";
`make gate` for this library, recorded with the PR.

### Wave 4 closeout (2026-10-27)

Semantic trigger check (WP-06) -- delivered as an advisory report.
`tooling/check_semantic_routing.py` judges the existing 24 skills and 24 case
files (126 prompts: 75 positive, 51 negative) through the Kilo gateway. Two
complete runs recorded hit@1 74/75 and hit@k 75/75 in both. The lexical gate
(`check_skill_routing.py --fail-on-warn`) is unchanged and remains the required
check. A third run is **BLOCKED** by `HTTP 429` / `Free model usage limit
reached`; no substitute model was used. Two stable case-ownership findings:
`verification-before-completion/negative/1` and
`subagent-delegation/negative/1`. The table in
`docs/knowledge-base/semantic-trigger-check-2026-10.md` is the only record of
the two runs; no per-prompt artifact was committed.

Context template and conduct placement (WP-07) -- delivered. The template
`docs/AGENTS-TEMPLATE.md` ships as a routing and documentation aid. In the
18-pair pilot the current arm scored 0.8891 and the candidate 0.8704 (12
complete pairs: 0.9725 current, 1.0000 candidate), so no success gain is
claimed. The context arm added 7,128 input tokens over 18 runs (36,723 ->
43,851; +396.0 mean), committed under `usage` in
`wp07-context-template.json`. The conduct variant is rejected, not promoted:
each arm met 75 of 78 expectation checks, and the 42 guard checks per arm
(all `guard_expectations` indices across three seeds) passed. The three unmet
checks per arm are task-completion expectations under the no-tools condition,
listed in `docs/knowledge-base/context-template-and-conduct-2026-10.md`. The
fragment is unchanged: `agent-conduct.md` hashes to
`ee26847738b7b05b76d7eafc5025d5b6da8215eee894869dd34cc9253991c2ae`.

Wave 4 audit: `medium 2 / low 4`. The audit carried one medium (48/48) and four
low findings, and an out-of-band reviewer record -- the reviewer's audit report,
not a committed ledger -- recorded a second medium for the missing wave closeout
and the missing WP-06 status line. An earlier revision of this paragraph called
that second item "not audit findings" and labelled it an implementation gap,
which made this closeout disagree with that review record on severity: that
reclassification is withdrawn and the item is medium 2 here. The rationale is
kept rather than dropped -- it is a gap in the wave's own deliverables, but the
review record's severity governs because the missing closeout blocked the
wave's acceptance line. All are fixed in this closeout change; the read-only
auditors re-check only these corrections.

- Medium 1: the "48/48 injection" headline was not derivable, and the token
  aggregate was not committed. The summaries now carry a per-expectation tally
  (`expectations`) and token `usage`; the prose says 75/78 met in each arm and
  42/42 guard checks, with the +396.0 input-token statement derived from the
  committed totals. No count is asserted without a committed denominator.
- Medium 2 (owner WP-06 and the Wave 4 closeout): Wave 4 had no closeout and
  WP-06 had no status line. Both are added here and in the WP-06 section. This
  is the item the out-of-band reviewer record rated medium; it is medium here
  too.
- Low 1: the WP-06 doc claimed its table was the only record without naming the
  two stable case IDs; it now says the table is the only record and names both.
- Low 2: the WP-07 prose did not label current vs candidate in table order.
- Low 3: the WP-07 prose did not disclose that the deciding pair was truncated.
- Low 4: no CHANGELOG entry recorded the closeout.

Wave 4 gate evidence (local, because this repository has no registered Actions
runner): `make gate` 367 tests (floor 330), token-efficiency 0 warnings,
routing 24/24, behavioral 24/18; `python3 tooling/check_semantic_routing.py
--dry-run` exit 0; `python3 -m pytest tooling/tests -q` 367 passed;
`git diff --check` clean.

### WP-04 closeout (2026-10-27): R4 cache baseline measured

WP-04 was deferred at the Wave 3 closeout for lack of a provider with cache
telemetry. It is unblocked and measured, after Wave 4, on the Kilo Anthropic
route. No prompt, skill or fragment changed; this is a measurement and its
harness.

- Measured 2026-10-27 on the Kilo gateway
  `https://api.kilocode.ai/api/gateway/v1`, model
  `anthropic/claude-haiku-5.5`, profile `anthropic-5m`, harness recorded as
  `kilo-gateway` because the route is the gateway, not a direct Anthropic call.
  The free Nemotron proxy was not used; it reports no cache telemetry.
- Matrix: 3 seeds (401, 409, 419), 9/9 requests completed, with the aggregate's
  `attempts` 9, `retries` 0 and `rate_limited` 0. Cold turn 1: 1,491 prompt
  tokens, 1,487 written, 0 cached, hit rate 0.0000. Warm turn 1 at +2.0 s: 1,491
  prompt tokens, 1,487 cached, 0 written, hit rate 0.9973. Turn-2 continuation:
  1,487 cached plus a 21-token write, hit rate 0.9835.
- Cost: 2.02e-04 cold, 3.1e-05 warm, 3.4e-05 continuation per run; 8.01e-04 USD
  total. Latency medians 2,892 / 2,371 / 1,638 ms.
- New `tooling/run_cache_baseline.py` and
  `tooling/tests/test_run_cache_baseline.py`: per seed one cold turn-1 request,
  the byte-identical warm request, and one continuation turn, recording
  `prompt_tokens`, `cached_tokens`, `cache_creation_input_tokens`, cost,
  latency, model, harness and timestamp. `--dry-run` plans without a request,
  `--fixture` replays a recorded response set so the tests need no network, and
  the key is read from `$KILO_API_KEY` and never written. A live run that
  contradicts the profile now exits 3, so a warm cold leg cannot be committed as
  a clean run.
- Command:
  `python3 tooling/run_cache_baseline.py --profile anthropic-5m --prefix agents/tabletop/tt-lore-keeper.md --model anthropic/claude-haiku-5.5 --harness kilo-gateway --base-url https://api.kilocode.ai/api/gateway/v1 --api-key-env KILO_API_KEY --seeds 401,409,419 --ttl-wait 340 --gap 2 --summary evals/cache/r4-anthropic-5m-2026-10-27.json`
- The first attempt at 14:22:20Z was rejected, not reported: seed 401's cold leg
  was still warm because the prefix had been probed 147 s earlier
  (`cached_tokens` 1,467, `cache_creation` 20), and
  `profile_consistency.cold_reads_zero` was false. The run was repeated after a
  six-minute idle with `--ttl-wait 340`; the recorded aggregate is the second
  run.
- Limits: one prefix (a tabletop role carrier, 1,487 prefix tokens), one model,
  one gateway route, and no cold continuation -- turn 2 is warm only because a
  cold continuation would need an idle wait longer than the TTL. The warm leg
  repeats an identical body, so 0.9973 bounds the rate from above. Cost comes
  from the gateway's rounded `usage.cost`, not a price table. The OpenAI,
  Gemini, DeepSeek and vLLM profiles remain unmeasured.
- Not claimed: any prompt or tool-set change is cache-neutral, and any general
  cache gain. The baseline is the input a future paired comparison needs.
- Audit outcome: two PASS and five low findings. All five lows are fixed in this
  closeout change: the runner exits 3 on an inconsistent live run,
  `evals/README.md` cites the measured token numbers, the R4 doc maps the WP-04
  step 2 field names to the record names, the aggregate records
  `attempts`/`retries`/`rate_limited`, and the prefix size is reported
  separately from the largest cacheable block.

WP-04 gate evidence (local, because this repository has no registered Actions
runner): `make gate` 440 tests (floor 330);
`python3 -m pytest tooling/tests/test_run_cache_baseline.py -q`; `--dry-run` and
the committed fixture replay both exit 0; `git diff --check` clean.

### Wave 5 (partial): WP-11 canonical H2 confirmation, BLOCKED

Recorded 2026-10-27. WP-11 is the canonical-model confirmation of the seven H2
merges, and it cannot start while the DeepSeek account has no credit. The
credential itself is valid: `GET https://api.deepseek.com/v1/models` returns
HTTP 200 with `deepseek-flash` and `deepseek-v4-pro`. A minimal
`POST /v1/chat/completions` (one turn, `max_tokens` 8, `temperature` 0) returns
HTTP 402 with
`{"error":{"message":"Insufficient Balance (request_id:
9394191c-8230-4ef2-b55f-e04edebcf291)","type":"insufficient_balance_error",
"param":null,"code":"invalid_request_error"}}`.

Consequences for this wave:

- `tooling/run_refactor_ab.py --base-ref 2cd4e43 --seed 7 --timeout 300
  --max-tokens 4096` was not run. Seeds 11 and 23 did not start. There is no
  partial result to report.
- No proxy model and no alternative endpoint was used. The WP is defined as the
  canonical-model confirmation, so a substitute would be a silent dependency
  swap and would not satisfy the acceptance line "a canonical-model run exists".
- The free-model result stays as recorded in
  `docs/knowledge-base/h2-shape-ab-2026-10.md` (old 0.899 vs new 0.9345, 56/66
  vs 57/66, 8 wins / 53 ties / 5 losses). It is the only evidence for the seven
  merges; it is not a confirmation on the canonical model and is not described
  as one.
- No skill body, fragment, prompt, or merge was changed by this attempt. No
  merge is reopened: reopening requires a material canonical-model loss, and no
  canonical data exists.

Re-entry condition: the DeepSeek account has credit and the same command
returns chat completions. The command and the comparison targets are fixed in
the H2 doc; nothing else needs to be re-decided. This entry is evidence of an
absent measurement, not of a completed one.

Wave 5 gate evidence for this doc-only change (local; no Actions runner is
registered for this repository): `make gate` -> `367 passed` (floor 330), token
efficiency 0 violations / 0 warnings, routing 24/24, behavioral 24/18, shape
advisories unchanged (`H2>8=1`, the frozen `misakanet`), and `git diff --check`
clean.

### Wave 5 (partial): WP-09 long-horizon exercise, deployed run deferred to November

Recorded 2026-10-27; status amended 2026-10-27. WP-09 cannot meet its first
acceptance line, "one deployed harness run with state, checkpoints and resume",
this cycle: dsh and zcode are inactive and will not be deployed before November
(`dsh` resumes then; `zcode` has no date and is not applicable this cycle), and
the Docker endpoint here is a read-only socket proxy (`paseo-ds-proxy`:
`CONTAINERS=1`, `POST=0`, `EXEC=0`, `BUILD=0`), so no harness can be started.
This is a deferral, not a blocked operator action and not a request for one.
Starting or restarting a production container is also outside this work package.
No harness run, no LH-13 metric and no A/B result is claimed.

What was delivered instead:

- `evals/long-horizon/`: a two-process exercise of LH-01..LH-14 on the live
  library checkout. Session A stops at checkpoint 2 (1/3); session B replays
  `events.jsonl`, compares the replay with the view (`AGREE`), resumes at
  `next_action` and finishes. Five checkpoints, 14 journal events, three
  units whose artifacts are derived from the checked-in contracts.
- `python3 tooling/run_state.py check evals/long-horizon/run-state.md` -> exit 0;
  `python3 tooling/check_run_journal.py evals/long-horizon/events.jsonl --state
  evals/long-horizon/run-state.md` -> exit 0, 14 events, 0 violations.
- `tooling/check_run_journal.py --state` enforces the LH-14 stale-view rule,
  which no command checked before; `tooling/check_long_horizon.py` gates the
  exercise state, journal and hash triple; `tooling/gate.sh` runs the exercise
  verifier.
- Runtime decision: `lease`, `## In-flight` and idempotency stay recorded fields
  with file-layer checks. No service, no new phase. Details and the two
  unfixed contract findings are in
  `docs/knowledge-base/long-horizon-agents-2026-10.md` section 6.1.

Re-entry condition: `dsh` is deployed again in November, or `zcode` gets a
deployment date, and a run can be started without touching a production
container that this work package may not restart. The exercise and the
state/journal tooling do not need to change to re-enter; the LH-13 metrics still
have no measurement.

Wave 5 gate evidence for this change (local; no Actions runner is registered for
this repository): `make gate` -> `380 passed` (floor 330), `long-horizon: 14
rules, 11 evidence ids, 1 exemplar, exercise ok, 0 violations`, token
efficiency 0 violations / 0 warnings, tool-set 4 tools / 0 violations, routing
24/24, behavioral 24/18, shape advisories unchanged (`H2>8=1`, the frozen
`misakanet`), and `git diff --check` clean.

This entry records WP-09 only. It is not a Wave 5 closeout: the wave audit gate
in section 4 still requires both read-only auditors, and WP-11 is separately
BLOCKED above.

### Wave 6: WP-08, the P3 optimization loop (2026-10-27)

Delivered with two providers blocked and one measured. Record:
`docs/knowledge-base/optimization-loop-2026-10.md`.

- **Labelled set.** `evals/optimization/failure-set.md` holds 38 cases drawn
  from four committed evidence families: the semantic routing report (FC-01..
  FC-05), the behavioral and H2 records (FC-06..FC-24), the WP-07 role A/B
  (FC-25..FC-29), and the Wave 1..4 audit ledger plus the Wave 5 lows
  (FC-30..FC-38). Each row names a source path and an anchor phrase;
  `tooling/check_failure_set.py` verifies both, requires exactly one occurrence
  after whitespace normalization, enforces 20..40 rows, unique contiguous ids,
  and a `state_note` for every non-open row. No case was invented and no source
  is a summary of a summary: the anchor must still be in the file.
- **Ledger and gate.** `evals/optimization/proposals.md` is the record and
  `evals/optimization/proposals.schema.json` the machine-readable form.
  `tooling/check_optimization_ledger.py` cross-checks source cases against the
  failure set, requires numeric cost, latency and tokens per configuration,
  refuses an `accepted` row without an approved gate and a measured gain, and
  refuses a rejected or accepted row whose paired result is `not-run`.
- **Cycle 1 (`P-1`) rejected.** One reflection call proposed a Plan-clause edit
  for the operations executor against FC-25/FC-26. Held-out seeds 401/409/419
  in two configurations produced a tie: A 0.6667 vs 0.6667 (W/T/L 1/1/1), B
  0.5000 vs 0.5000 (0/3/0); the two target expectations did not move (1/3 and
  1/3 in A, 0/3 and 0/3 in B in both arms) and the injection guards held 3/3
  everywhere. Cost, latency and tokens are committed per configuration. No
  quality claim is made for the candidate.
- **Cycle 2 (`P-2`) BLOCKED.** The canonical confirmation cannot run: DeepSeek
  returns HTTP 402 `insufficient_balance_error`, OpenAI direct returns 401, and
  the free Kilo model was rate-limited when WP-06 last used it. The paid Kilo
  routes (haiku-5.5, gpt-6-luna) answered, which is why cycle 1 has two measured
  configurations; the canonical configuration is recorded as blocked, not
  substituted. Exact probes: `evals/optimization/results/provider-probe-2026-10-27.json`.
- **Re-baseline trigger.** `tooling/check_rebaseline.py` compares `model`,
  `grader`, `harness`, `prompt_version` and `cache_epoch` from a baseline record
  against a current campaign summary or telemetry record, using the existing
  `evals/harness-telemetry.schema.json` fields. `evals/optimization/baseline.json`
  is `BL-1` (the WP-07 conduct campaign). It matches its own campaign (exit 0)
  and fires on a real committed campaign that changed model, grader and prompt
  version (`workflow-loop-1.3.0.json`, exit 1 with three changes), and on the
  same-cycle configuration B, which swapped executor and grader. `make gate`
  runs the matching pair only; the firing cases are fixture and real-record
  tests in `tooling/tests/test_check_rebaseline.py`.

Wave 5 lows carried into this work package, all fixed here:

- L1: `--verify` rewrites the probe report with the absolute checkout path, so
  a run in another checkout dirties a committed file. Now every path in the
  report is repository-relative and the write is skipped when the bytes match;
  `python3 evals/long-horizon/drive.py --verify` run twice leaves
  `probes/report.txt` byte-identical (verified by hash).
- L2: the exercise README never said that a default rerun replaces the committed
  transcripts. It now has a "Rerunning replaces the committed artifacts" section
  naming every file a default run deletes and rewrites, and states that
  `--verify` is the read-only path.
- L3: `tooling/check_long_horizon.py` promotes journal advisories to violations,
  so a WARN that `check_run_journal.py` reports as a warning failed the gate.
  Advisories are now collected as warnings and printed as `WARN`, with the count
  in the summary line; the exercise journal is validated the same way by both
  tools.
- L4: the Wave 4 closeout classification did not reconcile with the out-of-band
  reviewer record. The item is recorded as medium 2 in the Wave 4 closeout
  above, with the reason the earlier "implementation gap" label is withdrawn.

Wave 6 gate evidence (local, because this repository has no registered Actions
runner): `make gate` -> `411 passed` (floor 330, raised only by new tests),
`long-horizon: 14 rules, 11 evidence ids, 1 exemplar, exercise ok, 0
violations, 0 warning(s)`, failure set 38 cases 0 violations, optimization
ledger 2 proposals 0 violations, rebaseline match exit 0, token efficiency 0
violations / 0 warnings, tool-set 4 tools / 0 violations, routing 24/24,
behavioral 24/18, shape advisories unchanged (`H2>8=1`, the frozen `misakanet`),
and `git diff --check` clean.

### WP-12 closeout (2026-10-27): identity test guard and OMP read-only expansion

Operator decision: execute the two guard-tightening candidates that were ready
(test floor, OMP selection) and leave the two that need a product decision
(`convert-documents-to-markdown` distribution, role token warnings) open.

Test guard:

- `tooling/check_test_floor.py` no longer treats a count as the guard. It reads
  `tooling/test-manifest.json` (`agent-prompts-test-manifest/1`), collected from
  `python3 -m pytest tooling/tests --collect-only -q`, and fails when a manifest
  name is not collected, printing `missing <module>::<test>`. Additions pass
  without a manifest edit and are reported. `--write` merges new names and never
  prunes; `--write --allow-removals` is the only pruning path and prints every
  removed name. A plain run writes nothing. `FLOOR = 330` remains as a secondary
  backstop and is evaluated for the repository's own suite only.
- Guard proof in a scratch copy: renaming
  `tooling/tests/test_check_token_efficiency.py::test_gate_passes_on_repo` made
  the checker exit 1 with that exact node id, `--write` kept the stale name with
  a "pruning needs --write --allow-removals" note, `--write --allow-removals`
  printed the removal, and restoring the test returned exit 0.
- `tooling/tests/test_check_test_floor.py` adds 11 offline fixture tests; the
  checker stays a `gate.sh` step with no flag change.

OMP projection:

- `omp/catalog.yaml` is `omp-catalog/2` with 13 entries: the six of v1 plus
  `oracle`, `consistency-reviewer`, `researcher`, `librarian`, `research-merger`,
  `councillor`, `council-synthesizer`. A required `deferred:` block carries the
  ten read-only roles that are not projected, each with a one-line reason.
- `render_omp.py --check` enforces read-only coverage (a write-capable entry
  fails naming the role and its `tool_profile`; every read-only role must be
  projected or deferred; at most one orchestrator), a 700-token description
  budget (v2 measures 446; `BUDGET` is printed), and the copy-paste stale-pin
  message. `tooling/tests/test_render_omp.py` adds 10 tests.
- Measured description cost: 233 (v1, 6 entries), 446 (v2, 13), 517 (all 14
  read-only plus the orchestrator), 1014 (all 30; unreachable because 15
  templates are write-capable). The brief's ~519 reproduces at 517; its ~788
  does not and the measured 1014 is recorded instead.
- Follow-up, consumer side: add the seven pack entries, re-render
  `.omp/agents/`, bump the `agent-prompts` gitlink and the pack's
  `library_version`. Not done here by design. Superseded in part by the WP-12
  follow-up (section 5): the pack version is now 2.8.0, and the same consumer
  change renders `.omp/APPEND_SYSTEM.md`.

Local gate evidence (this repository has no registered Actions runner, so the
evidence is local): `make gate` -> `462 passed` (456 pinned names, floor 330
backstop), `render_omp.py --check` -> `BUDGET 446/700 description tokens (13
projected entries)` and 13 entries green, `git diff --check` clean.

### WP-12 follow-up gate evidence (foreground policy, 2026-10-27)

Local, no Actions runner: `make gate` -> `469 passed` (463 pinned names),
`render_omp.py --check` -> `BUDGET 446/700 description tokens (13 projected
entries)` and `BUDGET 389/400 foreground tokens (omp/foreground.md, 4 slots)`,
`--check --foreground` -> pin current, 4 slots, budget green, and
`git diff --check` clean. Live sentinel on OMP 18.13.0:
`docs/knowledge-base/omp-foreground-policy-2026-10-27.md`.

### WP-12 follow-up gate evidence (foreground module set, 2026-10-27)

Local, no Actions runner, so the evidence is the local run of the same gates:

- `make gate` -> `480 passed`; `check_test_floor` -> identity OK, 474 manifest
  names all collected, 474 pinned (floor 330 backstop).
- `render_omp.py --check` -> `BUDGET 446/700 description tokens (13 projected
  entries)`, then one `BUDGET <used>/<cap> foreground module tokens (<module>)`
  line per module (78/90, 168/170, 84/120, 121/150, 89/100, 56/70) and
  `BUDGET 599/700 foreground tokens (omp/prompts/foreground, 6 modules, 4
  slots)`.
- `render_omp.py --check --foreground` -> `OK foreground set
  omp/prompts/foreground: 6 modules pinned, 4 slots declared, per-module and
  total budgets green`; the byte-compare path with a pack and `--out` reports
  `OK foreground policy omp/prompts/foreground matches <file>`.
- `python3 -m pytest tooling/tests/test_render_omp.py -q` -> `28 passed`.
- `python3 tooling/check_test_floor.py` -> `474 distinct tests collected, 474
  pinned`; `git diff --check` clean.

The sentinel evidence for the channel is unchanged:
`docs/knowledge-base/omp-foreground-policy-2026-10-27.md` (section 2 for the
experiment, section 5 for the module set and its measurements).

### WP-12 follow-up (2026-10-27): Wave 8 audit findings that belong to the library

Five findings, all artifact-level: no `agents/**` body, skill body or fragment is
touched, so a reviewer who judges the canon wording of `review-lead` (or of the
orchestrator's use of `HANDOFF_TARGETS` for its unit owners) still has an
independent decision to make.

- `HANDOFF_TARGETS` semantics (MEDIUM). `packs/containeromat.md` documented
  `review-lead` as `HANDOFF_TARGETS = the eight review-* tracks below`; those
  are its dispatch targets, which come from `spawns`, and the row is why the
  consumer filled the slot with three reviewer names. The row now reads "the
  operator or requesting session that owns the authorized fix; dispatch targets
  come from `spawns`, not this slot", and the header paragraph defines the slot
  before the table. The `orchestrator` row changed for the same reason: it keeps
  its five unit owners, says they must mirror `spawns`, and names the operator's
  gated Push as the true handoff -- the one canon that uses the slot for
  dispatch. Every other row is `none` or "the requesting session", already
  correct. `omp/README.md` repeated the same error ("must name agents that exist
  in `.omp/agents/`") and is corrected with the pack.
- `40-safety` dangling label (LOW). The slot ended a sentence, so a filled
  policy read `...cleanup step. safety`. It now opens a label line
  (`- {{SAFETY_RULE}}:`) and names the irreversible categories: history rewrite
  or force-push, deleting data or volumes, deploying or redeploying a stack,
  dropping a database. 95/100 tokens (was 89).
- `30-governance` "no CI runner" (LOW). True here, false for containeromat,
  which has required status checks. The module now covers both cases: a CI
  runner's required checks are the evidence, otherwise local gate output is, and
  a gate that could not be run is reported as not run. 144/150 tokens (was 121).
- `declares_no_tools` scope (LOW). The regex scanned every line, so "no tools
  are required for this step" anywhere would defer a role, while "tool-free" and
  "without tools" were missed. The check now reads only the
  `{{MUTATION_POLICY}}` label line and matches `no tools`, `tool-free` or
  `without [any] tools`; the docstring names the three postures and the line.
  New tests: an incidental phrase in the body keeps the role projected, the four
  postures defer, and the live `orch-council-synthesizer` line still fails
  `--check`.
- Ceiling error (LOW). The 701-token error named a catalog key that does not
  exist (`budget_tokens` is rejected by the catalog). It now says to update the
  manifest, `FOREGROUND_BUDGET` in `tooling/render_omp.py`, and record the reason
  in `omp/README.md`; the renderer docstring and the catalog comment match.

Token totals after the rewrites (`bytes // 4`): `30-governance.md` 144/150,
`40-safety.md` 95/100, composed set 617/700 (2,468 bytes), was 599/700. Module
caps are unchanged, so only two `manifest.json` pins moved.

Consumer side, separate writer: the `review-lead` slot value, the `SAFETY_RULE`
label value, unused slot pruning and the pack header wording change in
containeromat. The library is green on its own.

Local gate evidence (no registered Actions runner here, so the local run is the
evidence):

- `make gate` -> `489 passed`; `check_test_floor` -> identity OK, 480 manifest
  names all collected, 480 pinned (floor 330 backstop); `all library gates
  passed`.
- `render_omp.py --check` -> `BUDGET 420/700 description tokens (12 projected
  entries)`, one per-module line (78/90, 157/170, 84/120, 144/150, 95/100,
  56/70) and `BUDGET 617/700 foreground tokens (omp/prompts/foreground, 6
  modules, 4 slots)`, then `OK omp/catalog.yaml: 12 entries, pins current,
  selection and budget green (structure mode)`.
- `render_omp.py --check --foreground` -> `OK foreground set
  omp/prompts/foreground: 6 modules pinned, 4 slots declared, per-module and
  total budgets green`.
- `python3 -m pytest tooling/tests/test_render_omp.py -q` -> `37 passed`.
- `python3 tooling/check_test_floor.py` -> `480 distinct tests collected, 480
  pinned (floor 330 backstop)`, 0 new tests; `git diff --check` clean.

### WP-12 follow-up evidence (foreground policy behaviour A/B, 2026-10-27)

Measurement only: no production prompt, skill, fragment or policy changed. The
harness gained multi-task support (`run_role_ab.py` one file per (role, task),
`summarize_role_ab.py` keyed by role+task) and kept its legacy single-task path.

- Protocol: pre-registered in
  `evals/role-ab/pre-registrations/wp-12-foreground-policy.md` before the first
  call; 8 tasks in `evals/role-ab/tasks-foreground/`, role
  `orch-orchestrator`, seeds 311/313/317, executor
  `anthropic/claude-haiku-5.5`, grader `openai/gpt-6-luna`, temperature 0,
  `--max-tokens 2048`, Kilo gateway, 48 executor + 48 grader calls, no dropped
  or truncated pair.
- Candidate arm: `omp/prompts/foreground/` rendered with the containeromat pack
  (`--foreground --pack /workspace/containeromat/packs/containeromat/omp.yaml`)
  and prepended to the same role body. The pack was read only.
- Result: task success 11/24 current vs 13/24 candidate (0.458 -> 0.542); mean
  score 0.7639 vs 0.8472; paired ties 18, candidate ahead 6, current ahead 0.
  Expectations 55/72 vs 61/72. Gain: scout dispatch 0/3 -> 2/3, read-only
  refusal 0/3 -> 3/3, conflict naming 2/3 -> 3/3; no expectation worsened and
  no task's success rate fell. Evidence, gate, safety, output and blocked
  probes were at or near ceiling under the role alone, so those modules are not
  shown to add anything on this set.
- Cost: candidate input +927 tokens per run (2,277.9 -> 3,204.9 mean, +40.7%);
  output -118.5 per run; gateway cost $0.016887 -> $0.015649 total over 24 runs
  (cost present on all runs).
- Decision rule: met -> **gain**, candidate for retention at its current scope.
  No promotion claim and no consumer change. **Superseded as a verdict** by the
  primary run below: this was the Kilo route, not the runtime.
- Known limits: one host, one model pair, 8 synthetic text-only tasks, n = 24
  per arm, no significance test; the policy entered as plain context rather than
  through OMP's assembly; one expectation (`07` "leads with the value") is a
  consistent grader false negative in both arms, so absolute success is a floor.
  Record: `docs/knowledge-base/foreground-policy-ab-2026-10-27.md`.

Local gate evidence (no registered Actions runner here, so the local run is the
evidence):

- `make gate` -> `494 passed`; `test-floor: identity OK: 485 manifest name(s)
  all collected`, 0 new tests; `all library gates passed`.
- `python3 tooling/check_test_floor.py` -> `485 distinct tests collected, 485
  pinned (floor 330 backstop)`; 5 names added to `tooling/test-manifest.json`
  for the new harness tests.
- `python3 -m pytest tooling/tests/test_run_role_ab.py -q` -> `10 passed`.
- `git diff --check` clean.

### WP-12 primary run on the runtime (OpenCode Go, 2026-10-27)

Provider correction: the foreground-policy A/B above ran on the Kilo gateway
(`anthropic/claude-haiku-5.5` / `openai/gpt-6-luna`), which is not the runtime.
The Kilo result is retained as a secondary artifact with its own model pair and
does not govern. The primary run repeats the pre-registered experiment on
OpenCode Go.

- Endpoint `https://opencode.ai/inference/go/v1`, `OPENCODE_API_KEY`; executor
  and grader both `deepseek-v4.1-flash` (the whole stack runs one model, so
  grading may be self-favouring; that is a stated limit, not a substituted
  model). Temperature 0, `--max-tokens 2048`, seeds 311/313/317, same 8 tasks
  and same arms; the rendered candidate context is byte-identical
  (8,089 chars).
- Harness: `run_role_ab.py` gained a generic repeatable
  `--header "name: value"` and `--session-header` (`--session-id` or
  `$OPENCODE_SESSION_ID`) because the endpoint requires `x-opencode-session`
  (400 `MissingSessionID` without it) and rejects `Python-urllib`'s user agent
  (403, error 1010). Header names only are recorded. `summarize_role_ab.py`
  gained `--tasks-dir` so per-expectation tallies are keyed to the fixture; the
  DeepSeek grader paraphrases some expectation text, which otherwise splits one
  expectation across several strings. `usage.opencode.list_cost` is recorded
  beside a subscription-zeroed `cost`.
- Calls: 48 executor + 48 grader, no terminal failure, no dropped pair. Five
  pairs hit `finish_reason: length` at 2,048 output tokens (four in the current
  arm, one in the candidate); reported, not repaired.
- Result: task success 16/24 current vs 16/24 candidate (0.667 both); mean score
  0.8336 vs 0.8474 over all 24 pairs, 0.8421 vs 0.8246 over the 19 complete
  pairs; expectations 60/72 vs 62/72; task-success pairs 2 / 20 / 2. Four
  expectations strictly better (read-only refusal 0/3 -> 3/3, subagent plan not
  permission 2/3 -> 3/3, bounded question 2/3 -> 3/3, gated destructive actions
  2/3 -> 3/3) and four strictly worse (all three `07` items plus scout dispatch,
  one run each).
- Cost: gateway `cost` 0 on all 24 runs per arm (`billing_source: go-plus`); the
  reported list price is 0.027533 vs 0.028027 USD total; input tokens
  1,474.0 -> 2,090.0 mean (+41.8%), output 1,178.5 -> 1,057.5.
- Decision rule on the primary run: (1) non-inferiority met, (2) targeted gain
  met, (3) no-regression **fails** (`07-output-discipline` 1.000 -> 0.667).
  **Verdict: loss** -> not a candidate for retention under the rule. It
  disagrees with the secondary Kilo run's gain; the primary governs and the
  disagreement is reported, not reconciled. The verdict turns on one run in each
  direction, so the set cannot discriminate at n = 24. Operator decision
  (2026-10-27) overrides the retention disposition without touching the
  measurement: the policy is retained as a compliance guardrail with no efficacy
  claim (WP-12 status; `docs/knowledge-base/foreground-policy-ab-2026-10-27.md`
  section 10).
- Evidence: `docs/knowledge-base/foreground-policy-ab-2026-10-27.md` (both runs);
  summary
  `evals/role-ab/results/wp12-foreground-policy-opencode-go-2026-10-27.json`;
  pre-registration amendment in
  `evals/role-ab/pre-registrations/wp-12-foreground-policy.md`.
- Limits: 8 synthetic tasks, one host, one model for both roles, text-only,
  n = 24 per arm, truncation-sensitive; the Kilo false negative on `07` did not
  reproduce under the primary grader.

### Operator decisions and status change (2026-10-27)

Documentation only; no prompt, module, catalog, renderer, standard or gate
changed.

- Foreground policy: retained as a compliance guardrail, no efficacy claim
  (WP-12 status; `docs/knowledge-base/foreground-policy-ab-2026-10-27.md`
  section 10). The A/B record is unchanged and is not re-run.
- Runtime status: dsh and zcode inactive, WP-09 and the LH-13 A/B deferred to
  November, WP-10's seed-marker reload closed, and the dsh/zcode skill roots
  inert and not removed (section 10, "Runtime status and open items").

Local gate evidence (no Actions runner is registered for this repository):
`make gate` -> `501 passed`, `test-floor: identity OK: 492 manifest name(s) all
collected`, token efficiency 0 violations / 0 warnings, tool-set 4 tools / 0
violations, routing 24/24, behavioral 24/18, `long-horizon: 14 rules, 11 evidence
ids, 1 exemplar, exercise ok, 0 violations, 0 warning(s)`, shape advisories
unchanged (`H2>8=1`, the frozen `misakanet`); `git diff --check` clean.

### Session close (2026-10-27)

Final state at close. Both repositories are clean, with no open pull requests.

| Repository | Head | State |
|---|---|---|
| `agent-prompts` | `e39b61f` | `make gate` 503 passed, 494 test identities pinned (floor 330), all library gates green |
| `containeromat` | `d400a7e9` | 12 rendered OMP agents, 24 skills in 44 files, `AGENTS.md` 3201 / 3300 tokens, ASCII clean |

Closed in this session: waves 1-6 of this plan; WP-01 through WP-12 except the
items below; the foreground policy as a six-module set with per-module pins and
budgets; the 12-agent OMP projection and `.omp/APPEND_SYSTEM.md` with a
byte-compare drift gate; the context-file shrink from 4,585 to 3,184 tokens; the
add-only test-identity manifest that replaced the count floor; the ASCII
pre-commit fail-open; and the projection coverage, budget and no-tools guards.

Open or deferred at close:

- WP-11 canonical H2 confirmation: DeepSeek chat returns `402 Insufficient
  Balance`; no canonical result exists and none is claimed.
- WP-09 deployed-harness run and LH-13 A/B: deferred to November, when `dsh`
  regains usage. `zcode` has no date. The local run-state exercise remains the
  only evidence.
- WP-06 third run: blocked by the free-model `429`; two runs are recorded.
- WP-08 cycle 2: canonical provider unavailable.
- R4 cache: `anthropic-5m` measured; OpenAI, Gemini, DeepSeek and vLLM remain
  unmeasured because no provider with cache telemetry is configured.

The foreground policy is retained as a compliance guardrail with no efficacy
claim; the A/B that produced that decision is
`docs/knowledge-base/foreground-policy-ab-2026-10-27.md` and is not re-run.
