# OMP projection: selection policy and read-only expansion (2026-10-27)

Status: reference. Owner: library maintainer.
Scope: `omp/catalog.yaml`, `tooling/render_omp.py`, `omp/README.md`.

This record backs the v2 selection: twelve OMP entries, every one of them a
read-only role template or the single orchestrator. It states what was measured,
what the write-posture constraint blocks, what the descriptions cost, which
guards enforce the policy, and which read-only roles are deferred and why.

Update (2026-10-27, same day): `council-synthesizer` moved from `agents:` to
`deferred:`. Its canon says `{{MUTATION_POLICY}}: no tools -- synthesize from
the provided responses only`, and OMP cannot express that: `task/executor.ts`
applies `tools` only `if (agent.tools)`, so an absent list means the broad
default, and `read-only-policy.ts` treats an empty list as not read-only. A
non-empty list would grant tools the canon forbids, so the role is not
projectable under the read-only posture. The selection is now 12 projected
entries and 11 deferred read-only roles; the description sum is 420 tokens. A
`--check` guard now fails any projected role whose canon declares no tools.

## 1. Inventory measured

`agents/**` holds 38 markdown files with role frontmatter. Eight of them are
`agents/review/review-tracks/*`, the progressive-disclosure children the review
lead dispatches; the other 30 are standalone role templates. The task brief
quoted "30 role templates; 14 read-only, 8 gated-write, 6 doc-write, 1
batch-write, 1 orchestrator", which is exactly the 30-template set (the 38-file
count includes the eight tracks, and the read-only count is 22 with them). Both
readings are recorded here so the numbers reconcile.

| Template | tool_profile | Name | Purpose tokens | v2 state |
|---|---|---|---|---|
| `design-ui-reviewer` | read-only | UI Reviewer | 35 | deferred |
| `documentation-doc-writer` | doc-write | Doc Writer | 36 | out of posture |
| `engineering-api-developer` | gated-write | API Developer | 36 | out of posture |
| `engineering-backend-developer` | gated-write | Backend Developer | 36 | out of posture |
| `engineering-database-developer` | gated-write | Database Developer | 35 | out of posture |
| `engineering-explorer` | read-only | Explorer | 28 | projected `scout` |
| `engineering-fixer` | gated-write | Fixer | 23 | out of posture |
| `engineering-frontend-developer` | gated-write | Frontend Developer | 32 | out of posture |
| `engineering-oracle` | read-only | Oracle | 29 | projected `oracle` |
| `engineering-test-author` | gated-write | Test Author | 26 | out of posture |
| `networking-network-architect` | read-only | Network Architect | 36 | deferred |
| `operations-ci-implementer` | gated-write | CI implementer | 38 | out of posture |
| `operations-executor` | gated-write | Operations executor | 35 | out of posture |
| `operations-format-normalizer` | batch-write | Format normalizer | 25 | out of posture |
| `orchestration-council-synthesizer` | read-only | Council synthesizer | 26 | deferred: canon declares no tools |
| `orchestration-councillor` | read-only | Councillor | 27 | projected `councillor` |
| `orchestration-orchestrator` | orchestrator | Orchestrator | 62 | projected `orchestrator` |
| `research-librarian` | read-only | Librarian | 35 | projected `librarian` |
| `research-research-merger` | read-only | Research Merger | 31 | projected `research-merger` |
| `research-researcher` | read-only | Researcher | 32 | projected `researcher` |
| `review-code-skeptic` | read-only | Verification Skeptic | 32 | projected `code-skeptic` |
| `review-consistency-reviewer` | read-only | Consistency Reviewer | 33 | projected `consistency-reviewer` |
| `review-review-lead` | read-only | Review Lead | 33 | projected `review-lead` |
| `review-reviewer` | read-only | Change Reviewer | 36 | projected `reviewer` |
| `review-security-reviewer` | read-only | Security Reviewer | 42 | projected `security-reviewer` |
| `review-track-correctness` | read-only | Correctness Track | 30 | deferred |
| `review-track-dead-code` | read-only | Dead Code Track | 30 | deferred |
| `review-track-deploy-safety` | read-only | Deploy Safety Track | 29 | deferred |
| `review-track-duplication` | read-only | Duplication Track | 28 | deferred |
| `review-track-quality` | read-only | Quality Track | 28 | deferred |
| `review-track-security` | read-only | Security Track | 27 | deferred |
| `review-track-simplicity` | read-only | Simplicity Track | 26 | deferred |
| `review-track-structure` | read-only | Structure Track | 32 | deferred |
| `tabletop-lore-keeper` | doc-write | Lore Keeper | 35 | out of posture |
| `tabletop-prose-editor` | doc-write | Prose Editor | 33 | out of posture |
| `tabletop-rules-designer` | doc-write | Rules Designer | 28 | out of posture |
| `tabletop-scenario-writer` | doc-write | Scenario Writer | 42 | out of posture |
| `tabletop-worldbuilder` | doc-write | Worldbuilder | 37 | out of posture |

Projected: 11 read-only plus the orchestrator. Deferred: 11 read-only (3 named
roles plus the 8 tracks). Out of posture: 15 write-capable templates.

## 2. The write-posture constraint

`render_omp.py:check_entry` admits only `READ_ONLY_TOOLS` (read, grep, glob,
web_search) plus `task`, and only where the entry declares `spawns`. The
projection therefore cannot carry a write-capable role without widening the tool
vocabulary: no `write`, no `edit`, no `bash`. That is the deliberate posture, not
an oversight -- a projected prompt would get an executor its canon text was never
audited for, and the grant would be one line in a catalog diff.

The consequence is measured, not argued: the 15 write-capable templates (8
gated-write, 6 doc-write, 1 batch-write) cannot be projected at all. The five
operations/engineering roles that would benefit most from a runtime agent
(`ops-executor`, `ops-ci-implementer`, `format-normalizer`, the developers) stay
in the Kilo/dsh adapters, where their write gate exists. Widening the posture was
rejected: it would make every projection review a write-permission review, and
the OMP surface this library ships is review, advice and dispatch.

The orchestrator is the one non-read-only entry. It is projected because the loop
owner has to dispatch units through `task`; its tool list is still read, grep,
glob, task -- it writes specs, decisions and gate rulings into its reply, and
every source edit leaves through a dispatched unit.

## 3. Description cost

The OMP frontmatter `description` is the role's `purpose` line verbatim, so every
projected entry is paid for in every parent session. Tokens are estimated as
`bytes // 4`, the library convention in `standards/agent-prompt-standard.md`;
`tooling/report_skill_shape.py` and `tooling/check_token_efficiency.py` use the
same rule.

| Selection | Entries | Description tokens |
|---|---|---|
| v1 (six entries) | 6 | 233 |
| v2 (all read-only except three, plus orchestrator) | 12 | 420 |
| all 14 read-only templates plus the orchestrator | 15 | 517 |
| all 30 role templates | 30 | 1014 (not reachable: 15 are write-capable) |

The brief's "~519 if all read-only plus the orchestrator" reproduces: 517 at
`bytes // 4` for the 14 read-only templates plus the orchestrator, confirming
its read-only set excluded the eight review tracks. Its "~788 if all 30 are
projected" does not reproduce: the 30 purposes measure 1014 tokens at
`bytes // 4` (572 words; 744 tokens at a words x 1.3 heuristic). The higher
figure is recorded here rather than repeated, because it is the number the 700
cap has to be judged against.

The cap is 700 tokens. v2 uses 420, which leaves 280 tokens of headroom: enough
for the three named deferred roles together (35 + 36 + 26 = 97) and not enough
for the track set on top (230 more, 747 in total with the three named roles --
the exact case that makes the guard fire). `--check` prints the current sum, so a
future addition either fits visibly or its author argues for the cap.

## 4. Guardrails added

`python3 tooling/render_omp.py --check` now enforces, beyond catalog shape, tool
posture, block order and the pins:

1. **Coverage guard.** Every `agents/**` role whose frontmatter `tool_profile`
   is `read-only` must appear in `agents:` or in `deferred:`. Every `agents:`
   entry must be `read-only` or the single orchestrator (at most one). A
   write-capable entry fails naming the role and its `tool_profile`; an
   unaccounted read-only role fails naming the path. The `deferred:` block is a
   required top-level key, each entry carries `role` and a non-empty one-line
   `reason`, and a role may not be both projected and deferred.
2. **No-tools guard.** A projected role whose canon declares no tools fails,
   naming the role: OMP applies a broad default when the tool list is absent and
   a non-empty list would grant tools the canon forbids, so that role must be
   deferred. The check matches the `no tools` phrase on the `{{MUTATION_POLICY}}`
   line or an equivalent anywhere in the canon.
3. **Budget guard.** The summed `purpose` estimate must stay under 700 tokens;
   `--check` prints `BUDGET <n>/700 description tokens (<entries> projected
   entries)` on every run and fails above the cap.
4. **Pin message.** A stale `templates_sha256` entry now prints the computed hash
   and the exact `role: hash` line to paste, so pin refresh is copy-paste instead
   of a second hashing step. Fragment drift prints the same way.

Guard tests: `tooling/tests/test_render_omp.py` (29 tests) covers a
write-capable entry, an unaccounted read-only role, a deferred role that accounts
for one, a projected role whose canon declares no tools, a second orchestrator, a
missing and an empty deferred reason, an unknown deferred key, the copy-paste pin
message, the budget under and over the cap, and the live 12-entry green run.

## 5. Deferred roles

| Role | Reason |
|---|---|
| `agents/design/design-ui-reviewer.md` | Needs `DESIGN_STANDARD`; neither target project ships a UI standard, so the projection would have to invent the slot. |
| `agents/networking/net-network-architect.md` | Needs `NETWORK_CONSTRAINTS`; compose network work is covered by the compose skills, so the slot would be decorative. |
| `agents/orchestration/orch-council-synthesizer.md` | Its canon declares no tools; OMP's absent-tools default is broader, not narrower, and a non-empty list would grant tools the canon forbids, so it is not projectable under the read-only posture. |
| the eight `agents/review/review-tracks/*` | Child tracks of the projected `review-lead`, which dispatches `reviewer`, `security-reviewer` and `code-skeptic` directly. Projecting them would duplicate that dispatch surface and add 230 description tokens for eight near-identical descriptions. |

The last row is why the `deferred:` block carries eleven entries rather than the
three named in the brief: the literal guard ("every read-only role must be
projected or deferred with a reason") covers all 22 read-only files. Listing the
tracks as deferred with a reason is more honest than carving them out of the scan
silently. If a target project later needs track-level review seats, the decision
is visible in one place and the budget line shows the cost.

## 6. Follow-up

- Consumer projection re-render and gitlink bump (containeromat), together with
  the six new pack entries the render now requires and the removal of its
  `council-synthesizer` entry in the same wave. Out of scope here; the library
  side is green without it.
- If a project adopts a UI or network standard, move the matching role from
  `deferred:` to `agents:` and re-measure the budget.
- No prompt body, skill body, fragment or `agents/**` file changed in this
  projection change: the expansion is catalog, guards and documentation only.
