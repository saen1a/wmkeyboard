# agent-prompts

Standalone vendor-neutral library of role templates, skills, fragments, and
standards. Projects **select** templates from this catalog and generate their
own vendor adapters (Kilo, DSH, OMP, and others); the library is never an
always-loaded roster.

## Layout

| Path | Content |
|---|---|
| `AGENTS.md` | Vendor-neutral router for agents working in this repository |
| `fragments/` | Byte-exact shared blocks (`agent-conduct.md`, `agent-doctrine.md`); imported verbatim, never edited per-project |
| `standards/` | Normative, project-neutral standards (prompt standard, workflow loop, work authorization, durable effects, message delivery, agent notification, long-horizon runs, skill system, model calibration, prompt assembly, model surface, STOPP gate, system prompt standard, subagent delegation, agent context files, review contract, evidence duty, halt taxonomy, language mandate) |
| `standards/evidence/` | Evidence and audit records backing the standards (not runtime prompts) |
| `agents/<domain>/` | Role templates: orchestration, engineering, design, review, research, documentation, operations, networking, tabletop |
| `skills/` | Portable skill packages plus the `SKILLS.md` index; canon for the 27 library skills |
| `commands/` | Slash-command dispatchers |
| `dsh/` | Parameterized DSH adapter templates; not neutral canon |
| `packs/` | Project adoption records; not neutral canon |
| `omp/` | OMP vendor projection: `catalog.yaml` (role -> OMP agent), `prompts/foreground/` (main-session policy modules plus their manifest), overlays, and `tooling/render_omp.py`; no rendered projection is committed here (`omp/README.md`) |
| `evals/` | Trigger and behavioral cases, reference artifacts, and results |
| `CATALOG.md` | Role-template index and selection matrix, maintained in sync with the template frontmatter |
| `PLAN.md` | Migration plan, batches and quality bar |
| `CHANGELOG.md` | Prompt-surface change log (what, why, evidence, owner) |
| `prompts/` | Canonical task prompts under `prompts/tasks/` and paste-style workspace prompts under `prompts/workspace/` |
| `exemplars/` | Long-form reference exemplars plus a validated run-state example (not runtime prompts) |
| `tooling/` | Conformance validators, the skill-shape report, and the paired behavioral runner + fixture tests (see `evals/README.md`) |
| `provenance/` | Source analyses, vendored notices, migration records |
| `docs/` | INSTANTIATE / SYNC / TEMPLATE-GUIDE / SKILL-TEMPLATE / AGENTS-TEMPLATE guides; `neutral-layout.md` for the `agents/` + `prompts/` target; `opencode-projection.md` for the consumer-owned OpenCode V2 transform |

The 2.0.0 release removed the legacy `roles/`, `tasks/`, and `workspace-prompts/`
shims; use `agents/`, `prompts/tasks/`, and `prompts/workspace/`.

Run `make gate` (or `tooling/gate.sh`) for the complete deterministic library
gate. `prompts/tasks/`, `commands/`, `dsh/`, `packs/` and `skills/` are populated (waves 2-3);
`evals/` holds the trigger and behavioral case sets plus reference eval artifacts
for selected templates. `evals/optimization/` holds the labelled failure set, the
human-gated proposal ledger, and the re-baseline identity; see
`docs/knowledge-base/optimization-loop-2026-10.md`.

## Token and cache efficiency

`standards/prompt-assembly.md` (AS-01..AS-14) defines the cacheable layer order,
the breakpoint budget, the volatile-byte ban, deterministic serialization,
append-only history, volatile-and-derived-layers-last, and override provenance
with upgrade visibility. `standards/cache-profiles.json` carries the dated minima,
multipliers, and TTLs. `python3 tooling/check_token_efficiency.py` is the static
check; `evals/harness-telemetry.schema.json` `/2` carries the runtime cache
fields. The `cache-aware-assembly` skill is the operating procedure.

## Work authorization

Who may ask an agent for work, how far that work may go, and what survives a
rules change. `standards/work-authorization.md` (WA-01..WA-12) separates the
deterministic gate from the semantic assessment, fixes a two-value strength
ladder, and makes the grant a record: an immutable mandate that carries the
policy version, the admission basis and the scope ceiling. Revalidation before
resume reads that record instead of re-deriving authority, a rules change is a
notice rather than a cancellation, and a prompt edit may never be the only place
a permission exists. The machine contract is `standards/mandate.schema.json`,
validated by `python3 tooling/check_mandate.py` against
`exemplars/mandate-example.json`.

## Durable effects and message delivery

A side effect a model decided on has to survive a crash. `standards/durable-effects.md`
(EF-01..EF-10) fixes the store-then-execute order, one effect row with a
domain-derived idempotency key, a `seq`/`generation` guarded completion, three
retry classes (defer, transient, permanent), per-stream ordering, and one health
threshold per kind. `standards/message-delivery.md` (MD-01..MD-08) covers the
transport half: the stated guarantee, receipt-then-send with transport dedupe,
per-conversation ordering, a closed set of permanent `gone` answers, terminal
receipts, and payload limits measured once at the boundary.
`exemplars/durable-effects-reference.md` is the worked reference.

## Agent notification

`standards/agent-notification.md` (NT-01..NT-10) governs unsolicited contact:
silence as the default state, the attention test (a usable result, a decision or a resource or
permission the person must supply, or a definitive inability), the deletion test before sending, a hard
word ceiling, structured escalation instead of urgency wording, one deduplicated
acknowledgement, the automation disclosure line, and the rule that a dropped
message is never re-sent.

## Model surface

`standards/model-surface.json` registers every model-visible surface -- role
templates, task prompts, fragments, skill bodies, commands, runtime presets --
with a measured token budget, and maps each rule family to its standard.
`python3 tooling/check_model_surface.py` enforces the registry: an unregistered
asset fails, a file over budget fails, and every cited rule ID must resolve to a
real heading in its standard, so a prompt cannot cite authority that does not
exist. The allowlist for a known gap is live and expires.

## Tool-set stability

`standards/tool-set.md` (TS-01..TS-10) defines the canonical tool manifest,
definition-only hash, mask-versus-remove rule, deferred-tool handling, and
version/cache-epoch discipline. `tooling/check_tool_set.py` validates a manifest
and `exemplars/tool-set-example.json` is a worked example. The implementation
guide is `docs/knowledge-base/tool-set-stability.md`.

## Long-horizon runs

A task that outlives one context window is governed by
`standards/long-horizon-runs.md` (LH-01..LH-14): durable run state, checkpoints,
resume, context compaction, progress and stall detection, goal drift, budgets,
termination, operator reporting, and the append-only event journal. The machine
contracts are `standards/run-state.schema.json` and
`standards/run-journal.schema.json`; validate with
`python3 tooling/run_state.py check RUN.md` and
`python3 tooling/check_run_journal.py events.jsonl` (or the state-adjacent
`provenance/run-<slug>.events.jsonl`) and see
`exemplars/run-state-example.md` and `exemplars/run-journal-example.jsonl`. The operational checklist is the
`long-horizon-run` skill. This layer wraps the seven-phase loop and adds no
phase.

## Verification integrity

A `pass` is a record, not a sentence. `standards/verification-integrity.md`
(VI-01..VI-15) defines what a gate verdict must contain: a named verifier that is
not the author, executed checks with exit codes and freshness, a substance floor
for artifacts, MUST/SHOULD criteria taken from the request, measured coverage and
its floor, declared degraded gaps, terminal exhaustion, and repair rounds that
state what changed. The machine contract is `standards/gate-verdict.schema.json`,
validated by `python3 tooling/check_gate_verdict.py` against
`exemplars/gate-verdict-example.json`; the operating procedure is
`skills/shared/verification-before-completion/references/proof-integrity.md`.
The plan review is executable in two halves: `python3
tooling/check_plan_spec.py PLAN.md` reports the six WL-15 checks over a spec
(shape in `docs/PLAN-SPEC.md`, copyable example in
`exemplars/plan-spec-example.md`), and `python3 tooling/check_loop_gate.py`
refuses a ledger unit that reached Implement without a clean `plan-review`
record, a non-contiguous round sequence, or a finalize without a verify pass.
Both are `make gate` steps and both are consumer-runnable.

The loop's own guards are executable: `python3 evals/loop/drive.py --verify` (a
`make gate` step) drives 20 transition scenarios -- an incomplete spec, a spec
that never passed its plan review, a plan-review round that repeats its change, a
review without a record, a `fix` verdict trying to reach Ready, a second spec-gap
return, and a finalize without the operator's `go`, without the record, or
without publication proof -- each asserting its expected reason, and the exercise
fails when a guard stops rejecting for that reason. Record-level rejections (skipped
check, stub artifact, self-signed verification, coverage floor, attempt bound) are
proved by `tooling/check_gate_verdict.py` and its tests.

## Prompt and agent security

`standards/prompt-security.md` (PS-01..PS-14) covers the instruction surface:
trust classes and where the data boundary sits, invisible-character and
smuggled-override detection, tool metadata pinning, privilege asymmetry on
handoff, egress and secret handling, stored memory as evidence, approval paths
that must ask, configuration as the trust root, coverage honesty for security
claims, inventory versus vulnerability, and suppressions that expire.
`python3 tooling/check_prompt_security.py` is the static check (PS-02, PS-03,
PS-06) over every prompt asset; the operating skill is
`untrusted-content-handling` with its hostile-pattern catalogue.

## Runtime projection admission

`standards/agent-adapter.md` (AD-01..AD-12) makes a projection a capability
claim instead of a copy: four-valued support (`supported`, `degraded`,
`unsupported`, `unknown`), fail-closed admission, no silent fallback to an
unconstrained native path, explicit identity mapping, pins that a check
enforces, dated gaps, and refusal by name. Records are `omp/admission.json`
(admitted, with named degradations) and `dsh/admission.json` (refused, because
the runtime was not exercised); `python3 tooling/check_admission.py PATH`
recomputes admission and rejects a record that disagrees with its own evidence.

## Select -> instantiate -> register

1. **Select** a template from `CATALOG.md` (domain, purpose, selection matrix).
2. **Instantiate** per `docs/INSTANTIATE.md`: fill the project slots, pick the
   conduct variant, copy fragments byte-exact.
3. **Register** the instantiation in your project's agent registry so your
   conformance gate covers it.
4. **Admit** the runtime per `standards/agent-adapter.md`: one
   `agent-admission/1` record per runtime, admission computed fail-closed
   (`python3 tooling/check_admission.py`). Generation parity is not admission.

## Sync policy

`docs/SYNC.md` records the anti-drift rule: fragments are vendored byte-exact
and pinned via `fragment_versions` in each template's frontmatter; a fragment
divergence in any consumer is a bug, not a customization.

## Status

Library 2.12.0 (2026-11-03) carries the long-horizon run layer (2.1.0; run state
1.2.0), doctrine 1.5.0 (the plan-review gate, so no spec reaches Implement
unreviewed, plus verdict integrity in the Verify bullet), the token/cache
assembly policy (AS-01..AS-14), the
tool-set stability contract (TS-01..TS-10), the findings ledger and publication
proof (WL-13/WL-14), the append-only run journal (LH-14), the agent-pack
renderer (2.5.0), overlay slot substitution (2.5.1), normalized skill anatomy
headings (2.5.2), the seven H2 shape merges (2.5.3; A/B in
`docs/knowledge-base/h2-shape-ab-2026-10.md`), the R4 design, the
conduct-canon decision, the OMP vendor projection (2.6.0), and wave 11:
verification integrity (VI-01..VI-15), prompt security (PS-01..PS-14), and
runtime projection admission (AD-01..AD-12), each with a contract and a gate
checker. The WP-07 A/B record predates doctrine 1.4.0 and is historical.

Foundation wave 2026-09-19: fragments, standards, 38 role templates across 9
domains, workspace prompts, exemplars, catalog. Wave 2 added `prompts/tasks/`,
`commands/` and `dsh/` templates; wave 3 shipped the skills canon switch (this
tree is the canon for the portable skills -- see `skills/SKILLS.md` and
`PLAN.md`). Wave 7 (2026-10-23) added the 2026 prompt research register, the
system audit and optimization plan, the subagent delegation standard and skill,
and the agent context file standard. See
`docs/knowledge-base/prompt-system-audit-2026-10.md`. Wave 8 (2026-10-23)
added the skill system standard, the skill template, the shape report, and the
measured refactor plan. See
`docs/knowledge-base/skill-prompt-refactor-2026-10.md`. Wave 9 (2026-10-23)
started R1/R2: a model calibration standard, a paired no-skill runner, and
three skill splits (jq, skill-creator, first-principles-review) that moved
long-form material into references. Wave 9 continued with R3: mcp-builder,
anti-entropy-governance, deepseek-v4-agent-defense, and agent-md-refactor
were split the same way, leaving no non-vendor body over the shape cap. The
prompt assembly contract (AS-01..AS-14) and `CHANGELOG.md` now close the cache
and change-log gaps.
