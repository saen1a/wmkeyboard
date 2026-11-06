# OMP vendor projection

The OMP runtime adapter for the neutral roles under `agents/**`. It is a
projection, not a second canon: the bodies stay in `agents/**`, the selection and
the OMP-specific fields live in [`catalog.yaml`](catalog.yaml), and the renderer
copies the neutral blocks while swapping in the OMP conduct variant and the
project-owned slot values.

Same posture as [`dsh/`](../dsh/README.md): this directory never ships a runtime
prompt. A consumer renders its own copy into the directory OMP discovers, so the
library carries no project slot values and no generated agents.

## What OMP reads

Live-fetched 2026-10-26 from the oh-my-pi repository (branch `main`): the README
tool table, `docs/task-agent-discovery.md`, `docs/agent-hub.md` and the bundled
`scout` and `reviewer` agent definitions. The pinned runtime for this project is
`@oh-my-pi/pi-coding-agent` 18.12.6.

| Surface | Path |
|---|---|
| Project agents | `<project>/.omp/agents/*.md` |
| User agents | `~/.omp/agent/agents/*.md` |
| Project config | `<project>/agent/config.yml`; user config `~/.omp/agent/config.yml` |

Discovery is first-wins by exact `name`: a project file shadows a user file of
the same name, and both shadow the bundled agents. `scout`, `reviewer` and
`security-reviewer` are bundled OMP names, so this projection shadows them on
purpose with a read-only, no-shell definition.

## Files

| File | What it is | Owner |
|---|---|---|
| `catalog.yaml` | role -> OMP agent mapping (name, model role selectors, tools, spawns, thinkingLevel, optional output schema, optional overlay) plus the version, commit and sha256 pins | library |
| `overlays/<name>.md` | OMP-only body addition: exactly one `<runtime>` block, inserted before `<conduct>`. Either dispatch mechanics for an entry with `spawns`, or a runtime constraint for a read-only role whose canon text assumes a shell | library |
| `../fragments/agent-conduct.omp.md` | the OMP conduct variant (`CONDUCT_VARIANT` = `omp`) | library |
| `../tooling/render_omp.py` | renderer and drift gate | library |
| `admission.json` | runtime admission record (`agent-admission/1`): four-valued support per required capability, the fail-closed result, the projection's tool mapping, and dated gaps. Validated by `../tooling/check_admission.py`; the rules are `../standards/agent-adapter.md` (AD-01..AD-12) | library |
| `<project>/.omp/agents/*.md` | the rendered projection OMP discovers | consumer |
| `prompts/foreground/*.md` | the main-session policy as self-contained modules: plain Markdown, `{{SLOT}}`-marked where a project value is needed | library |
| `prompts/foreground/manifest.json` | the module set contract: set id, compose order, per-module sha256 pins, per-module budgets, total budget | library |
| `<project>/.omp/APPEND_SYSTEM.md` | the composed, slot-filled policy OMP loads for the main session only | consumer |

## Admission before deployment

A rendered projection is not an admitted one. `admission.json` states what this
runtime demonstrably enforces: `tool_allowlist` and the three read tools are
`supported`, `subagent_dispatch` and `task` are `degraded` (orchestrator and
review-lead only), a shell tool and host-inferred spawn are `unsupported`, and
MCP resources are `unknown`. Admission is admitted because every required
capability is supported or degraded with a named narrower behavior.

A consumer that dumps the outbound `tools` array (TS-01) replaces the `evidence`
pointer with that dump and moves the `checked` date. A host version change makes
the `supported` rows unverified until re-checked (AD-07, AD-09); do not bump
`runtime_version` without re-verifying, and do not deploy a projection whose
record computes `refused`.

## Regenerate

Run from the consumer project root; the renderer resolves the library root from its
own path, so no `cd` into the library is needed:

```bash
# consumer render: writes <project>/.omp/agents/<name>.md
python3 agent-prompts/tooling/render_omp.py \
    --pack packs/containeromat/omp.yaml --out .omp/agents

# consumer drift gate: the renderer in both modes plus the frontmatter key set
# and the slot-residue check; exit 1 on a stale, missing, orphaned or hand-edited
# file, exit 0 with a SKIP line when the library submodule is not checked out
python3 scripts/verify-omp-agents.py

# library gate: catalog shape, tool posture, block order and the pins
python3 agent-prompts/tooling/render_omp.py --check
```

`--check` without `--out` is the library-side structure and pin gate: it needs
no pack, writes nothing, and fails when a selected role, the conduct fragment or
a foreground module no longer matches its pin. `--check` with `--out` additionally
compares the committed projection byte-for-byte against a fresh render, so a
hand-edited `.omp/agents/` file goes red. Exit codes: 0 clean, 1 drift or
validation failure, 2 unreadable input or bad usage.

## Foreground orchestration

The subagent projection is read-only by construction, so the policy that lets a
session delegate, mutate with approval and verify has to reach the main session
only. OMP gives exactly that split:

| Surface | Path |
|---|---|
| Project append prompt | `<project>/.omp/APPEND_SYSTEM.md` |
| User append prompt | `~/.omp/agent/APPEND_SYSTEM.md` |

OMP discovers one of those files for the main session (`--append-system-prompt`
overrides it) and does not forward it to subagents:
`packages/coding-agent/src/task/executor.ts` builds subagent session options
without `appendSystemPrompt`. Measured on OMP 18.13.0 (2026-10-27) with a
sentinel line in `.omp/APPEND_SYSTEM.md`: the main session answered
`ZQ7-PINEAPPLE ready`, and a `scout` subagent asked about the same rule answered
`NONE`. Record and limits:
[`docs/knowledge-base/omp-foreground-policy-2026-10-27.md`](../docs/knowledge-base/omp-foreground-policy-2026-10-27.md).

The library owns the module set under [`prompts/foreground/`](prompts/foreground/).
Each module is plain Markdown with no frontmatter and carries only its own
concern; [`manifest.json`](prompts/foreground/manifest.json) is the contract that
ties them together:

| Order | Module | Scope | Budget |
|---|---|---|---|
| 1 | `00-authority.md` | foreground authority; operator instruction > this policy > runtime defaults; you own the reply | 90 |
| 2 | `10-delegation.md` | the 12-name dispatch list with one-line routing; delegate vs inline; subagents are read-only by construction | 170 |
| 3 | `20-evidence.md` | a completion claim needs a command and its exit code from this run; subagent output is testimony | 120 |
| 4 | `30-governance.md` | project gates are the definition of done; ASCII; durable findings go to the knowledge base; a CI runner's required checks or local gate output is the evidence, and an unrun gate is reported as not run | 150 |
| 5 | `40-safety.md` | history rewrite or force-push, deleting data or volumes, deploying or redeploying a stack and dropping a database are operator-gated; never print secrets; stop and report BLOCKED | 100 |
| 6 | `50-output.md` | lead with the answer; cite file:line; do not restate tool output; keep claims and commands adjacent | 70 |

**Compose order.** `manifest.json` `order` is the compose order. The renderer
joins the modules in exactly that order with exactly one blank line between
them, then fills the slots on the composed text. `catalog.yaml` `foreground:`
names the same modules in the same order; a missing, extra or reordered module
fails `--check` with its own message, and the manifest order wins by definition.

**Pins.** Each module has its own sha256 in `manifest.json`
(`modules.<name>.sha256`), so editing one module is a one-line pin diff. The set
id (`omp-foreground/1`) is declared in both the manifest and the catalog and
must match. A stale pin prints the computed hash as the copy-paste line
`"<module>": "<hash>"`.

**Slots.** The set uses `PROJECT_ID`, `PROJECT_RULES`,
`VERIFICATION_COMMANDS` and `SAFETY_RULE`; the catalog declares that union and
`--check` fails on a declared-but-unused or a used-but-undeclared slot. The
library never carries project slot values.

**Budgets.** Two levels, both in the manifest: `modules.<name>.budget_tokens`
per module and `budget_tokens` for the composed set, with
`FOREGROUND_BUDGET` in `render_omp.py` as the renderer ceiling. `--check` and
`--check --foreground` print per-module usage and the total, e.g.
`BUDGET 617/700 foreground tokens (omp/prompts/foreground, 6 modules, 4 slots)`.

> **Raising either budget is a deliberate decision.** A budget is a ceiling, not
> a target. To raise a per-module cap or the total, state the reason in a
> rationale line in this README (what the new text buys and why it cannot be
> trimmed), then update `manifest.json` (and `catalog.yaml`, if the module list
> changed) in the same change. Raising the total past `FOREGROUND_BUDGET` also
> means raising that constant and saying so in the same rationale line. The
> Wave 7 audit recorded the earlier gap: the budget error pointed at this README
> while this README never said what raising a budget requires.
>
> **Rationale, 2026-11-03 (30-governance 150 -> 232, total 700 -> 726).** The
> module now carries the loop line and the plan-review rule (`WL-15`), because a
> main-session policy that names the phases but not the gate is how a spec
> reaches implementation unreviewed. It is one statement, in one module: six
> copies would duplicate a pinned policy for nothing. The total rises to 726
> because the text has to live somewhere; `FOREGROUND_BUDGET` moves with it.

```bash
# consumer render: composes the modules and writes <project>/.omp/APPEND_SYSTEM.md
python3 agent-prompts/tooling/render_omp.py --foreground \
    --pack packs/containeromat/omp.yaml --out .omp/APPEND_SYSTEM.md

# library gate: manifest, set id, compose order, per-module pins, slot union,
# per-module and total budgets
python3 agent-prompts/tooling/render_omp.py --check --foreground

# consumer byte gate: the committed file equals a fresh compose + fill
python3 agent-prompts/tooling/render_omp.py --check --foreground \
    --pack packs/containeromat/omp.yaml --out .omp/APPEND_SYSTEM.md
```

The render writes plain Markdown and refuses to run when a declared slot has no
value in the pack, when pack entries disagree about a project-level value, or
when any `{{SLOT}}` remains. The four slots are project-level, so they are read
from the same per-agent pack the projection uses: the shared value, with a
dedicated `name: foreground` pack entry taking precedence. A plain `--check`
validates the module set too, so a module edit without a pin refresh fails the
library gate with the line to paste.

Headless caveat: `omp -p` refuses a `task` dispatch without an approval UI
(`task` requires approval and no interactive UI is available). A headless run
needs `--auto-approve`, `tools.approvalMode: yolo`, or the narrow
`tools.approval.task: allow`. Without one, the policy still loads and the main
session still answers; the delegation is what gets blocked.

## Selection (v2)

Twelve entries: every read-only role template plus the single orchestrator,
except the three deferred roles justified below. Read-only means the role's
`tool_profile`; the renderer enforces the split (see "Selection guards").

| OMP agent | Neutral role | model | tools | spawns | thinkingLevel |
|---|---|---|---|---|---|
| `scout` | `agents/engineering/eng-explorer.md` | `@smol` | read, grep, glob | none | medium |
| `oracle` | `agents/engineering/eng-oracle.md` | `@slow`, `@smol` | read, grep, glob | none | unset |
| `reviewer` | `agents/review/rev-reviewer.md` | `@slow`, `@smol` | read, grep, glob | none | unset |
| `security-reviewer` | `agents/review/rev-security-reviewer.md` | `@slow`, `@smol` | read, grep, glob | none | unset |
| `code-skeptic` | `agents/review/rev-code-skeptic.md` | `@slow`, `@smol` | read, grep, glob | none | unset |
| `consistency-reviewer` | `agents/review/rev-consistency-reviewer.md` | `@slow`, `@smol` | read, grep, glob | none | unset |
| `review-lead` | `agents/review/rev-review-lead.md` | `@slow` | read, grep, glob, task | reviewer, security-reviewer, code-skeptic | unset |
| `researcher` | `agents/research/res-researcher.md` | `@slow`, `@smol` | read, grep, glob, web_search | none | unset |
| `librarian` | `agents/research/res-librarian.md` | `@slow`, `@smol` | read, grep, glob | none | unset |
| `research-merger` | `agents/research/res-research-merger.md` | `@slow`, `@smol` | read, grep, glob | none | unset |
| `councillor` | `agents/orchestration/orch-councillor.md` | `@slow`, `@smol` | read, grep, glob | none | unset |
| `orchestrator` | `agents/orchestration/orch-orchestrator.md` | `@default`, `@slow` | read, grep, glob, task | scout, reviewer, security-reviewer, code-skeptic, review-lead | unset |

Tool posture is read-only across the selection. `write`, `edit` and `bash` are
never granted: these prompts review, advise and dispatch, they do not execute.
`task` is granted exactly to the two entries that declare `spawns`, and the
renderer enforces that pairing in both directions. `web_search` is granted only
to `researcher`, whose canon declares a live upstream lookup. `thinkingLevel` is
set only where a measured value exists: `scout` mirrors the bundled agent of the
same name (`thinking-level: medium`), which this projection shadows.

Model selectors follow one rule: a read-only role lists `@slow` then `@smol`, so
the reasoning selector is preferred and the small selector is the fallback.
`scout` is `@smol` only because it is the fast locator and shadows the bundled
agent; the orchestrator is `@default` then `@slow` because it owns the loop.
`@default` is not used for a review or research seat.

### Deferred read-only roles

`catalog.yaml` carries a `deferred:` block: every read-only role that is not
projected, each with a one-line reason. A read-only role that is neither
projected nor deferred fails `--check`, so "we skipped it" is always a recorded
decision rather than an omission. A role whose canon forbids tools cannot be
projected because OMP's absent-tools default is broader, not narrower: no tool
list means the broad default, and any non-empty list grants a tool the canon
denies.

| Deferred role | Why |
|---|---|
| `agents/design/design-ui-reviewer.md` | needs `DESIGN_STANDARD`; neither target project ships a UI standard, so the slot would be invented. |
| `agents/networking/net-network-architect.md` | needs `NETWORK_CONSTRAINTS`; compose network work is covered by the compose skills. |
| `agents/orchestration/orch-council-synthesizer.md` | its canon declares no tools; OMP applies a broad default when the tool list is absent, and a non-empty list would grant tools the canon forbids, so it is not projectable under the read-only posture. |
| the eight `agents/review/review-tracks/*` | child tracks of the projected `review-lead`, which dispatches specialist reviewers directly; a second entry would duplicate the lead's dispatch surface and spend description budget on eight near-identical lines. |

Write-capable roles are not deferred entries; they are outside the projection's
posture. Thirty role templates exist under `agents/**` (38 files counting the
eight review tracks): 14 read-only, 8 gated-write, 6 doc-write, 1 batch-write,
1 orchestrator. Only the 14 read-only roles and the orchestrator are selection
candidates; the 15 write-capable templates need an executor posture this
projection deliberately does not grant.

### Selection guards

`render_omp.py --check` enforces three things beyond the pins:

1. **Coverage.** Every role under `agents/**` whose frontmatter `tool_profile` is
   `read-only` must appear in `agents:` or in `deferred:`. Every `agents:` entry
   must be `read-only`, or the single orchestrator: a write-capable entry fails
   with the role path and its `tool_profile`, so the posture cannot be widened
   one entry at a time. A projected role whose canon declares no tools also
   fails: neither the absent-tools default nor a non-empty list honours that
   canon, so the role must be deferred.
2. **Description budget.** The frontmatter `description` is the role's `purpose`
   line, so every projected entry is paid for in every parent session's prompt.
   The summed cost is estimated as bytes // 4 (the library convention) and must
   stay under **700 tokens**. `--check` prints the current usage
   (`BUDGET 420/700 description tokens (12 projected entries)`); the cap exists
   so a future addition has to justify itself instead of drifting in.
3. **Shape and pins.** Catalog keys, the tool vocabulary, `spawns`/`task`
   pairing, block order, and the role and fragment sha256 pins.

Measured description cost: 233 tokens at the six entries of v1, 446 at the
thirteen of v2, 420 at the twelve once `council-synthesizer` is deferred, 517 if
all 14 read-only roles plus the orchestrator were projected, and 1014 if all 30
templates were (they cannot be: 15 are write-capable). The three named deferred
roles cost 97 tokens together.

### Tool posture and overlays

The tool list is never widened to make a canon sentence executable. Where a
read-only role's canon text assumes a shell -- the security reviewer's scanner
permission, the code skeptic's proof commands, the review lead's diff re-check,
the orchestrator's dispatch -- the projection adds a runtime constraint overlay
instead: one `<runtime>` block that names the dispatcher as the source of the
command output or of the diff, tells the agent to ask for the command, its
output and its exit code (or for the diff text and the file list), and keeps
`tools` exactly as it was. Widening `tools` would hand a prompt an executor its
canon text was never audited for, and the grant is invisible in the review of a
role that only mentions a scanner in passing. The overlay keeps the gap visible
and makes the agent request the evidence instead of implying it produced it.
Follow this rule for the next read-only role whose canon text assumes a command:
overlay first, tool list unchanged.

### Pin refresh procedure

A role edit or a new entry fails `--check` with the computed hash. To refresh:

1. Paste the printed hash into `templates_sha256` under the role path (the error
   message prints the exact `role: hash` line to copy), or add the pin for a new
   entry.
2. Re-run `python3 tooling/render_omp.py --check` until green.
3. Regenerate the consumer projection in the same change as the pin refresh, so
   the gitlink the consumer records matches the catalog it was rendered from.
   Never refresh a pin without re-rendering: the pin is the drift gate, not
   paperwork.

## Frontmatter emitted

Exactly the keys OMP parses for a subagent, in this order, nothing else:

| Key | When |
|---|---|
| `name` | always |
| `description` | always, one line, taken from the role frontmatter `purpose` |
| `tools` | always |
| `spawns` | only when the catalog entry declares it |
| `model` | always, a list of `@role` selectors in priority order |
| `thinkingLevel` | only where the catalog sets it |
| `output` | only where the catalog declares it: `properties.<key>.metadata.description` plus `enum` |

The body keeps the neutral block order (role, hard_rules, doctrine, workflow,
conduct, output; `<scope>` where the role carries it), the conduct block comes
from `fragments/agent-conduct.omp.md`, and an overlay is inserted as a
`<runtime>` block immediately before `<conduct>`. Slots are substituted from the
pack until stable; a rendered file that still carries `{{...}}` is never
written.

## Loop gate

`admission.json` carries `loop_gate: degraded` (AD-12): this projection has no
pre-dispatch hook, so the orchestrator can pass a spec to a `task` child without
a verdict check. The gate is the project's CI step
(`tooling/check_plan_spec.py`, `tooling/check_loop_gate.py`), and the foreground
policy (`prompts/foreground/30-governance.md`) states the rule the runtime cannot
enforce. Read that cell before claiming the loop is enforced here.

## Drift gate

`catalog.yaml` pins `library_version`, `library_commit`, `fragment_sha256`
(doctrine and the OMP conduct variant) and `templates_sha256` (every selected
role); `prompts/foreground/manifest.json` pins every foreground module and the
set id. A role or module edit therefore fails `render_omp.py --check` until the
projection is regenerated and the pin refreshed, which is what keeps the
projection from drifting away from `agents/**` and `omp/prompts/foreground/`
without a visible change. The role-level gates stay where they are:
`tooling/validate_templates.py` for the canon, and a consumer-side lock over
`.omp/agents/` and `.omp/APPEND_SYSTEM.md` for its own checkout.

There is deliberately no `projection_commit`. It once named the commit a
projection was authored at, but no gate read it -- `TOP_REQUIRED` checks only
`library_version` and `library_commit` -- so it drifted away from the submodule
HEAD unseen and every reader who trusted it was misled. The consumer's gitlink is
the record of which projection it holds; `library_commit` stays because the pin
gate does check it, and a consumer-side gate now also compares the pack's
`library_commit` with this one. A pin nothing validates is worse than no pin.

## What a consumer must provide

A render needs a pack entry per catalog `name`, carrying that agent's `slots`.
The pack is consumer-owned: containeromat keeps its copy at
`containeromat:packs/containeromat/omp.yaml` (the library carries no pack file).
At the v1 pin it has the six names of that selection (`scout`, `reviewer`,
`security-reviewer`, `code-skeptic`, `review-lead`, `orchestrator`). The v2
catalog carries twelve, so that pack needs the six new entries -- `oracle`,
`consistency-reviewer`, `researcher`, `librarian`, `research-merger`,
`councillor` -- before its next render, and it must drop its
`council-synthesizer` entry in the same wave because that name is no longer
selected; a catalog name with no pack entry fails the render with
`pack has no entry for agent '<name>'`.

That pack update and the consumer gitlink bump are a separate consumer change
(PLAN, WP-12 closeout). A pack entry for a name the catalog does not select is
inert at render time, but the pack still should drop `council-synthesizer` so it
mirrors the selection rather than carrying a dead name.

Two slot values need OMP-shaped content in that pack: `HANDOFF_TARGETS` names the
session that owns the next authorized step -- the orchestrator or requesting
session a report returns to, and, for `review-lead`, the operator or requester
who owns the fix, never the reviewer children it dispatches -- and
`MUTATION_POLICY` for a read-only role stays a read-only statement. Dispatch
targets come from `spawns`, not from this slot; only the orchestrator's canon
uses the slot for its unit owners, so there it must mirror `spawns`.

The foreground module set needs no separate pack entry: it reads `PROJECT_ID`,
`PROJECT_RULES`, `VERIFICATION_COMMANDS` and `SAFETY_RULE` from the same
per-agent entries, and the current pack already carries all four. A dedicated
`name: foreground` entry overrides that union if a project wants different
values in the main session than in the subagents. The render command and the
output path are unchanged by the module split, so a consumer's render and byte
compare keep working; only the library-side pins moved into the manifest.

## Out of scope

- Project slot values. They belong to the consumer pack, never to the library.
- `AGENTS.md`, rules, skills and command projection. OMP loads those from the
  repository by design; this directory covers subagent prompts only.
- Memory tools (`retain`, `recall`, `reflect`, `memory_edit`) and `prewalk`:
  gated by OMP settings, not by a prompt.
- `structured: true`, `blocking`, `autoloadSkills` and the other optional agent
  fields. The `output` schema is inert unless the parent session runs structured
  tasks.
- A committed projection in this repository, and a live-session claim about
  `.omp/agents/`: that OMP loads those files at session start is the documented
  behavior of the tool's writer but not yet observed in a live session here. The
  append-system path is separately measured (see "Foreground orchestration").
- The role frontmatter `runtimes` enum, which still reads `[kilo, dsh]` on every
  selected role. Those roles are canon; adding `omp` there is an upstream change
  and is tracked outside this projection.
