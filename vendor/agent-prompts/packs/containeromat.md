# Project pack: containeromat

containeromat selects the templates below. Its live instantiations sit at
containeromat `.kilo/agents/` and are registered by
`scripts/render-agent-config.py`; this record maps each selected template to the
live agent that instantiates it, so runtime adoption is auditable instead of
implicit.

## Agent source

containeromat authors agent bodies in its neutral `agents/` directory and
generates `.kilo/agents` plus the `.kilo/kilo.json` agent block from
`agents/runtime.yaml`. Stage B wave 1 renders the eight `review-*` tracks from
this library through `packs/containeromat/agents.yaml` and
`tooling/render_agents.py`; the manifest pins the library commit and the
`agents.lock.json` pins each output by sha256. The lock proves output stability,
not template provenance. The consumer re-vendored doctrine 1.3.1 and conduct
1.0.0 from this library across every carrier; `.kilo/templates` is the vendored
copy and the pack now uses the library fragments. The library moved to doctrine
1.4.0 on 2026-10-31 (verdict integrity in the Verify bullet), so the consumer
carries 1.3.1 until the next re-vendor: `check_workflow_loop.py` here pins
1.4.0, and the consumer's vendored copy is expected to differ until that pass. It also re-vendored the 24
library skills into 64 runtime copies at library `b1ea951` (2.6.0); the consumer
submodule is current.

Project-common slot fills:

- `PROJECT_ID` = `containeromat`
- `PROJECT_RULES` = `docs/rules/*` (read via the `AGENTS.md` entry point)
- `VERIFICATION_COMMANDS` = `docker compose config -q` + ASCII validation +
  `scripts/verify-image-tags.sh` + `scripts/verify-compose-key-order.sh`

`HANDOFF_TARGETS` is listed per row. It names the session that owns the next
authorized step -- the operator, or the requesting session a report returns to --
not the agents a row dispatches: dispatch targets come from the role's `spawns`
(its task allowlist), never from this slot. Leaf roles are subagents; their task
allowlist is empty and their findings or reports flow back to the dispatching
role.

## Template -> live agent

| Template | Live agent | Slot fills / notes |
|---|---|---|
| `orchestration-orchestrator` | `orchestrator` | HANDOFF_TARGETS = the unit owners it delegates to -- compose-step, reviewer, code-skeptic, docs-specialist, ascii-step -- which must mirror its `spawns` list; this is the one role whose canon uses the slot for dispatch, and the true handoff is the operator, who owns the gated Push. It owns the Plan-to-Push sequencer. |
| `operations-ci-implementer` | `ci-step` | containeromat flavor: CI/workflow/CI-helper-script executor; VERIFICATION_COMMANDS = the gate battery (`.forgejo/scripts/tests/run.sh`, `scripts/ci-replica.sh --fast`, `scripts/verify-*.py`, `shellcheck`, `shfmt -d -i 2 -ci -bn`, `scripts/verify-ascii.sh`); HANDOFF_TARGETS = none. |
| `operations-executor` | `compose-step` | containeromat flavor: compose L1-L4 escalation ladder and compose diagnostics; HANDOFF_TARGETS = none. |
| `operations-format-normalizer` | `ascii-step` | containeromat flavor: ASCII normalized-batch executor; HANDOFF_TARGETS = none. |
| `review-reviewer` | `reviewer` | HANDOFF_TARGETS = none; audits compose diffs and diagnostic findings from clean context. |
| `review-review-lead` | `review-lead` | HANDOFF_TARGETS = the operator or requesting session that owns the authorized fix; dispatch targets come from `spawns`, not this slot. Dispatches the read-only review and never edits. |
| `review-code-skeptic` | `code-skeptic` | HANDOFF_TARGETS = none; challenges completion claims. |
| `documentation-doc-writer` | `docs-specialist` | HANDOFF_TARGETS = none; PROJECT_DOC_SCOPE = docs/, CHANGELOG.md, README.md. |
| `review-track-security` | `review-security` | HANDOFF_TARGETS = none; findings return to review-lead. |
| `review-track-correctness` | `review-business-logic` | HANDOFF_TARGETS = none; containeromat names this track business-logic (logic, error-path, wiring). |
| `review-track-deploy-safety` | `review-deploy-safety` | HANDOFF_TARGETS = none; findings return to review-lead. |
| `review-track-duplication` | `review-duplication` | HANDOFF_TARGETS = none; findings return to review-lead. |
| `review-track-dead-code` | `review-dead-code` | HANDOFF_TARGETS = none; findings return to review-lead. |
| `review-track-quality` | `review-quality` | HANDOFF_TARGETS = none; findings return to review-lead. |
| `review-track-structure` | `review-structure` | HANDOFF_TARGETS = none; findings return to review-lead. |
| `review-track-simplicity` | `review-simplicity` | HANDOFF_TARGETS = none; findings return to review-lead. |
| `engineering-explorer` | `code-explorer` | HANDOFF_TARGETS = none; read-only where-is lookups (`cbm-query` first, then `rg`). Named `code-explorer` because the OpenCode V2 runtime ships an `explore` agent of its own. |
| `engineering-oracle` | `oracle` | HANDOFF_TARGETS = none; read-only architecture advice bound by R-014 (registered deviations are not defects), R-034 (no invented upstream solutions) and R-035 (deployed paths). |
| `orchestration-councillor` | `councillor` | HANDOFF_TARGETS = none; one seat, no cross-seat coordination. No overlay: the library body is project-neutral. |
| `orchestration-council-synthesizer` | `council-synthesizer` | HANDOFF_TARGETS = none; merges supplied seat responses. No tools and no overlay. |
| `research-researcher` | `researcher` | HANDOFF_TARGETS = the requesting session; the R-029 live-fetch obligation is added as an overlay rule (URL plus fetch date on every claim). |
| `research-librarian` | `librarian` | HANDOFF_TARGETS = the requesting session; knowledge-base entry points (`docs/knowledge-base/llms.txt`, `scripts/kb-search.py`) added as overlay rules. |
| `research-research-merger` | `research-merger` | HANDOFF_TARGETS = the requesting session; merges sub-reports without new fetching. No overlay. |

Three rows are containeromat flavor variants rather than direct role copies:
`operations-executor` is instantiated as the compose-flavored `compose-step`
(compose L1-L4 ladder, compose diagnostics, Dockhand deploy awareness),
`operations-format-normalizer` is instantiated as the ASCII batch executor
`ascii-step`, and `operations-ci-implementer` is instantiated as the
CI-flavored `ci-step` (CI/workflow/helper-script gate battery). The remaining
rows are direct instantiations with containeromat slot fills.

The `operations-ci-implementer` role carries a reference eval set: containeromat
hosts `eval-set-003.xml` and `ci-step-baseline.md` under
`.kilo/orchestrator/evals/`, and this library keeps a copy under
`evals/ops-ci-executor/`.

## Structural audit

containeromat gates the live pack with `scripts/verify-agents.py` (conduct and
doctrine byte-identity, element budgets, frontmatter contract). The library's
`tooling/check_instantiation.py` adds the structural audit:

```
python3 tooling/check_instantiation.py \
    --project-root <containeromat checkout> --library-root <agent-prompts checkout>
```

It checks block sequence, doctrine/conduct byte-identity against `fragments/`,
output-last, workflow prose and `hard_rules` bullet shape. Content differences
are intentional (containeromat vocabulary), so only structure is audited.

The eight `review-*` track templates use the scope-variant block order
(`<scope>` in place of `<workflow>`), so `check_instantiation` reports no
block-sequence divergence.

## Pin and exclusions (2026-10-26)

The consumer is pinned at library **2.6.0** (`b1ea951`) and instantiates 23 roles:
the eight review tracks, the three operations flavors, `reviewer`, `review-lead`,
`code-skeptic`, `docs-specialist`, `orchestrator`, plus the seven adopted on
2026-10-26 (`engineering-explorer`, `engineering-oracle`,
`orchestration-councillor`, `orchestration-council-synthesizer`,
`research-researcher`, `research-librarian`, `research-research-merger`).

Everything the consumer's OpenCode V2 surface deliberately does not carry is
recorded in `containeromat packs/containeromat/exclusions.yaml` with a class and a
reason (out-of-domain, draft, speculative, overlaps-registered-contract, deferred,
missing-runtime, not-portable, superseded-by-local-name). The consumer gate
`scripts/verify-agent-pack.py` fails when a library role, skill, command or preset
is neither adopted nor excluded, when an exclusion names something the library no
longer ships, and when an item is both adopted and excluded.

Two naming divergences, both recorded in that file rather than silently absorbed:
the neutral `commands/review.md` dispatcher ships in containeromat as
`commands/review-lead.md` (frontmatter binding `agent: review-lead` plus
`$ARGUMENTS`), and `skills/vendor/misakanet` is adopted by the consumer's dsh and
OMP surfaces but not by its OpenCode surface, which mounts no MisakaNet endpoint.

A consumer that needs these roles on OpenCode V2 transforms the neutral bodies
itself; the transform is documented in `docs/opencode-projection.md`.

## OMP consumer follow-up (2026-10-27, library 2.8.0)

The consumer's OMP surface lags the library projection: it holds the v1
six-entry `.omp/agents/` render and no `.omp/APPEND_SYSTEM.md`. The next consumer
change does five things in one commit:

1. Add the seven v2 pack entries (`oracle`, `consistency-reviewer`, `researcher`,
   `librarian`, `research-merger`, `councillor`, `council-synthesizer`) to
   `packs/containeromat/omp.yaml`; a catalog name with no pack entry fails the
   render.
2. Re-render `.omp/agents/` with the library renderer and bump the
   `agent-prompts` gitlink in the same commit, so the gitlink records the
   catalog the projection came from.
3. Render the main-session policy:

   ```bash
   python3 agent-prompts/tooling/render_omp.py --foreground \
       --pack packs/containeromat/omp.yaml --out .omp/APPEND_SYSTEM.md
   ```

4. Add a byte-compare step for it in `scripts/verify-omp-agents.py`
   (`--check --foreground --pack packs/containeromat/omp.yaml --out
   .omp/APPEND_SYSTEM.md`), so a stale or hand-edited policy fails the same gate
   as `.omp/agents/`.
5. Set the pack's `library_version` to 2.9.0 and re-run
   `scripts/ci-replica.sh --fast`.

No new pack entry is needed for the foreground slots: `PROJECT_ID`,
`PROJECT_RULES`, `VERIFICATION_COMMANDS` and `SAFETY_RULE` are already carried by
the per-agent entries, and the renderer takes the shared value.

## Wave 12 adoption gap (2026-11-02, library 2.10.0)

The consumer submodule is still pinned at library **2.6.0** (`b1ea951`) and its
OMP surface at 2.9.0, so its checkout carries nothing this library added in
Wave 12: no work-authorization, durable-effects, message-delivery or
agent-notification standard, no AS-13/AS-14, no model-surface registry, no
`operator-setup-interview` or `human-gated-config-change` skill. This section
records the gap; it is not evidence of adoption.

The next consumer change picks up, one line each with the owning library rule:

- `standards/work-authorization.md` WA-01..WA-12, with
  `standards/mandate.schema.json` and `tooling/check_mandate.py`: the
  gate/assessment split, the two-strength ladder, the immutable grant record,
  revalidation on resume, and the validator that holds the record shape.
- `standards/durable-effects.md` EF-01..EF-10: commit intent then execute, one
  row shape with one writer, domain-derived idempotency keys, three retry
  classes, terminal states that never resurrect.
- `standards/message-delivery.md` MD-01..MD-08: a written guarantee, durable
  receipt before transport, ordering per (unit, conversation), a closed `gone`
  set, dedup by originating event.
- `standards/agent-notification.md` NT-01..NT-10: default silence, the
  attention and deletion tests, the one-sentence ceiling, structured escalation,
  terminal honesty.
- `standards/prompt-assembly.md` AS-13/AS-14 with cache profile 1.1.0: volatile
  and derived layers last; every override names its source and the upgrade diff
  stays visible.
- `standards/verification-integrity.md` VI-15: a status is derived from stored
  facts by an ordered table, never stored.
- `standards/code-review-contract.md` CR-13: visual evidence for a UI change.
- `standards/agent-adapter.md` AD-11: probe the runtime as the agent runs it and
  degrade per capability.
- `standards/subagent-delegation.md` SD-12: delegation transfers no authority.
- `skills/general/operator-setup-interview/` and
  `skills/general/human-gated-config-change/`, with their `evals/trigger/*.json`
  and `evals/behavioral/*.json` cases, so the consumer's routing and behavioral
  gates exercise the new trigger vocabulary and the gated-change pressure cases.
- `standards/model-surface.json` through
  `tooling/check_model_surface.py --root <consumer>`: every model-visible
  consumer surface registered with a token budget and every cited rule ID
  resolved.

Four decisions stay with the consumer because the library has no source to
inspect, and each rule that defers them says so:

- Which identities may ask for work -- `standards/work-authorization.md` WA-03:
  identities belong to one source and are never mapped across sources, so the
  allowed list is that source's, not the library's.
- Which admission cells are `explicit` rather than `inferred` -- WA-02: the
  library defines the two strengths, and the cell that carries one is configured
  per receiving scope.
- The word ceiling -- `standards/agent-notification.md` NT-04: the standard sets
  the default and the hard ceiling, and the transport that rejects above it is
  the consumer's.
- The transport's `gone` set -- `standards/message-delivery.md` MD-04: the
  permanent class is closed and versioned with the channel kind, so the consumer
  names its own conditions and codes.

The consumer gate must add three commands: `check_mandate.py` over each grant
record it keeps, `check_model_surface.py --root <consumer>` over its tree, and
`check_behavioral_evals.py --root <consumer>` for the two new skills' cases
(trigger routing is already gated). A green consumer gate without them is not
adoption evidence.

The Wave 12 instruction is itself on file as a worked grant:
`provenance/mandate-wave12-autonomy-2026-11.json` states it as an
`agent-mandate/1` record -- explicit, addressed in the session console, scoped
to the adoption plan and its audit -- and `tooling/check_mandate.py` validates
it. That record demonstrates that a mandate is auditable after the fact: the
basis, scope and revalidation are recorded instead of being inferred from a
transcript.

The first pickup step is a decision, not code, and it is **decided**
(2026-11-01): `packs/containeromat-admission-cells.md` records the five answers --
no adapter in this wave, the operator's own identity as the only listed sender,
`ignore` for all three cells, an empty bot list -- plus the policy block those
answers produce, and the evidence that would prove a cell later. The decision is
closed; the implementation is not, so the gap above stays open.

## Wave 13 adoption (2026-11-03, library 2.12.0)

The consumer adopted the release: `saenta/containeromat` **`e1bf63cb`** (vendor
commit `c61379ac`, artifacts commit `e1bf63cb`), `agent-prompts` gitlink
**`34e8668`**, pack `library_commit` **`f58c748`** -- the bodies' commit, which is
what `omp/catalog.yaml` pins; the two values differ on purpose (checkout vs
canon). That checkout's own evidence, not this record:

| Surface | State after adoption |
|---|---|
| Pins | `packs/containeromat/{agents,omp,exclusions}.yaml` = 2.12.0 / f58c748; `verify-omp-agents.py` check 5 green |
| Bodies | 23 neutral agents re-rendered (0 drift); Kilo adapter re-rendered; `check_instantiation.py` 16/16 |
| OMP | 12 agents + `.omp/APPEND_SYSTEM.md`; `.omp/skills` 27 skills, 49 files |
| dsh / zcode | presets and HA prompts carry doctrine 1.5.0 (13 blocks); zcode port refreshed; both skill seeds bumped |
| Skills | `operator-setup-interview` and `human-gated-config-change` adopted (registry 27 names), exclusions pruned |
| Seed | `stacks/coder/seed-version` 2026-11-03.1; dsh/zcode `.seed-version` skills-2026-11-03a; coder + paseo surfaces regenerated |
| Loop gate | `check_plan_spec.py` + `check_loop_gate.py` wired into `scripts/ci-replica.sh` and `compose-validate.yml`; both skip loudly while `provenance/` carries no ledger |
| Battery | `ci-replica.sh --fast` PASS (197 s, and again after the rebase); the pre-push hook ran the same battery and allowed the push |

Deployment (2026-11-03): both images were built from `e1bf63cb` and redeployed.
`code` runs coder image `1a09dc7670d1` (built 09:18Z) and `code-seed` exited 0 on
that same image with `seed 2026-11-03.1 already applied -- no-op`, i.e. the copy
had already run against this image and the second invocation was a no-op; `paseo`
runs `c4285929dec4` with `/opt/paseo-config/agents/orchestrator.md` carrying
`Plan -> PlanReview` and 35 baked skills including the two adopted ones. The
coder bind was not readable from the adopting session (the daemon refuses
`exec`/`run`, and only `goose-harness` is mounted into the paseo shell), so the
operator proved it from the host: the deployed
`~/.config/kilo/agents/orchestrator.md` in the `code` container answers
`grep -c "Plan -> PlanReview"` with `1`, `/mnt/Datengrab/Apps/code/.seed-version`
reads `2026-11-03.1`, and the seeded tree carries exactly the shipped surface --
35 skills (both adopted ones included) and 23 agents. The seed marker is **not** under
`~/.config/kilo` -- `coder-seed.sh` writes `${TARGET}/.seed-version`, i.e. the
host path `/mnt/Datengrab/Apps/code/.seed-version`, one level above the binds the
container sees; that is why `cat ~/.config/kilo/.seed-version` reports "No such
file" on a correctly seeded host.

Still owned by the operator: the coder and paseo images are built by CI from the
pushed tree and deployed by the Dockhand webhook, so the seed run is the
deployment's own step. Verification is the deployed marker, not this file:
`docker exec code cat ~/.config/kilo/.seed-version` must read `2026-11-03.1`.
In the session that performed the adoption, `docker build` and `docker exec`
were refused by the daemon (no buildx, legacy builder and exec blocked by
administrative rules), so the live reseed could not be driven or observed from
there; the tree it bakes is the one the battery gated.

## Re-vendor checklist (library 2.12.0)

The wanted state is library **2.12.0**, catalog `omp-catalog/4`; the sha is the
release commit that carries Wave 13 (the plan-review gate) and is set here when
the wave is pushed.
The procedure, with a command and a pass condition per step, is
`docs/REVENDOR.md` (ten steps, including rollback); this section is the delta
and the decisions, not the order of work. This record is not evidence that the
consumer adopted anything: adoption is that checkout's own commits and its own
gate output.

Read the gitlink before starting. The pack record above says the consumer is
pinned at 2.6.0 (`b1ea951`); a containeromat checkout inspected on 2026-11-02
records `agent-prompts` gitlink `067546e` in `agents.yaml` while
`exclusions.yaml` still pins `42e462d`, so the three pin files disagree.
`067546e` already carries everything below except the Wave 12 rows, which is
why the operative delta there is the eight commits `067546e..17d05d0`.

| Area | Change since 2.6.0 | Consumer action | Verification |
|---|---|---|---|
| Submodule pin | release `17d05d0`; the pack, catalog and gitlink must name one sha | bump the gitlink, then copy the sha into `omp.yaml`, `agents.yaml`, `exclusions.yaml` | `verify-omp-agents.py` check 5 (pack pin equals catalog pin) |
| Fragments | conduct `1.1.0` (one new bullet: a stated rule is not an enforced one) across 41 carriers -- 38 agent templates and 3 task prompts; doctrine `1.5.0` adds the mandatory plan-review gate and the repeat-until-clean rule | re-render every carrier, never edit one; the consumer's own workflow prose has to name `PlanReview` where it enumerates phases | `tooling/check_fragments.py`; `scripts/verify-agents.py` |
| Standards | four new: work-authorization WA-01..WA-12 (+ `mandate.schema.json`), durable-effects EF-01..EF-10, message-delivery MD-01..MD-08, agent-notification NT-01..NT-10 | record an adopt/exclude decision per standard; coverage does not enumerate standards, so this is a record, not a gate row | the decision record plus every cited range resolving |
| Loop gates | `tooling/check_plan_spec.py` (six WL-15 checks over a spec, shape in `docs/PLAN-SPEC.md`), `tooling/check_loop_gate.py` (refuses Implement without a clean plan-review record, non-contiguous rounds, Push without verify), `docs/PLAN-SPEC.md`, `exemplars/plan-spec-example.md` | add both to `scripts/ci-replica.sh --fast` and require one spec + one plan-review verdict + one WL-08 row per unit; pass `--since` at the adoption date to grandfather older ledger rows | the two commands exit 0 on the vendored tree |
| Rule extensions | WL-15 (plan review, seven-phase loop), WL-07 amendment, VI-13 attempt semantics, CR-01 scope note, SG-01, SD-12, AS-13/AS-14, VI-15, CR-13, AD-11, AD-12 (loop gate as an admission capability) | re-read the section of any rule the consumer quotes; a quoted range may have changed | `scripts/verify-agents.py` on the consumer's own citations |
| Skills | `operator-setup-interview` and `human-gated-config-change`, with `evals/trigger/` and `evals/behavioral/` cases | adopt (copy into the runtime skill root, register in `scripts/skills-library.json`, regenerate `skills-manifest.py`) or exclude with a class and a reason | `scripts/verify-agent-pack.py` (coverage runs on the plain invocation; its header's `--coverage` flag does not exist), `scripts/verify-agents.py` |
| Model surface | `standards/model-surface.json` plus three new checkers (`check_model_surface.py`, `check_mandate.py`, `check_doc_ranges.py`); `--registry` so a consumer registry can live outside the scanned tree | register the consumer's own surfaces; keep a `standards` exposure at the `--root` (symlink or copy) because `rule_families` resolve there | `check_model_surface.py --root . --registry <consumer registry>`: `0 unresolved` |
| Role bodies | all 38 regenerated; registered max 1,163 tokens (`agents/**/*.md`) against a 1,200 budget | re-render through `packs/containeromat/agents.yaml`; refresh `packs/containeromat/agents.lock.json` in the same commit | `render_agents.py --check`; `validate_templates.py` |
| OMP projection | 12 catalog entries, refreshed `fragment_sha256` and `templates_sha256`, foreground module set `omp-foreground/1` | re-render `.omp/agents/` and `.omp/APPEND_SYSTEM.md`; `council-synthesizer` stays out (the library defers it) | `scripts/verify-omp-agents.py` |

Four decisions stay the consumer's own, because the library has no source to
inspect and each rule that defers them says so:

- **Admission cells** -- already decided, 2026-11-01, in
  `packs/containeromat-admission-cells.md`; WA-02 defines the two strengths, the
  cell that carries one is configured per receiving scope. The decision is
  closed; nothing implements it yet.
- **The identity list** -- WA-03: identities belong to one source and are never
  mapped across sources, so the list is that source's.
- **The word ceiling** -- NT-04: the standard sets the default and the hard
  ceiling; the transport that rejects above it is the consumer's.
- **The transport's `gone` set** -- MD-04: the permanent class is closed and
  versioned with the channel kind, so the consumer names its own conditions and
  codes.

Open on the library side: `fragments/agent-conduct.omp.md` is still `1.0.1`
and does not carry the 1.1.0 bullet, so the OMP surface renders 1.0.0-body
conduct with the OMP tool bullet. "Conduct 1.1.0 is re-vendored" is true of the
Kilo carriers only until the variant is regenerated.
