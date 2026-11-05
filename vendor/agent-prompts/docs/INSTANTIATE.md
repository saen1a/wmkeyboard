# Instantiating a template

A template is a skeleton with named `{{SLOTS}}`. Instantiation fills the
project-owned slots and copies the library-owned blocks verbatim.

## Slot contract

| Slot | Filled by | Notes |
|---|---|---|
| `PROJECT_ID` / `WORKSPACE` | project | Workspace name + root; drives the "not this project -> report and stop" rule |
| `PROJECT_RULES` | project | Rule IDs/paths the role must read before applying; or "none" |
| `VERIFICATION_COMMANDS` | project | The project's proof commands + expected exit codes |
| `ROLLBACK_COMMAND` | project | Required for gated-write roles: the command that reverts the change after a failed verify |
| `HANDOFF_TARGETS` | project | Subagent/role names this role may hand off to |
| `MUTATION_POLICY` | project | Edit scope for write roles; read-only roles: none |
| `SAFETY_RULE` | project | Secrets/destructive constraints (library default provided) |
| `PROJECT_DOC_SCOPE` | project | Documentation surfaces a doc-write role may edit (doc-writer template) |
| `GAME_SYSTEM` | project | Named rules system the scenario must be playable under (scenario-writer template) |
| `PHASE_MAP` | project (role-shaped default in the template) | Prose only -- no list markers (element budget) |
| `CONDUCT_VARIANT` | project | `kilo`, `dsh-ha`, `dsh-preset` or `omp` fragment variant |
| `MODEL_HINT` | project (optional) | Model/variant bias |

Library-owned blocks are copied **byte-exact** and never edited per project:

- `<doctrine>` from `fragments/agent-doctrine.md`
- `<conduct>` from `fragments/agent-conduct.md` (one of the four registered
  variants -- pick by runtime; the variant differences are the tool bullet and
  the closing hygiene bullet only)

The runtime layer (authorization, durable effects, message delivery,
notification, model surface) is not a slot. It is a second instantiation, per
consumer, described in `## Instantiating the autonomy layer` below.

## Runtime mapping

| Slot | Kilo Code | DSH | OMP |
|---|---|---|---|
| Mutation policy | `permission.edit` frontmatter | tool filter / persona constraint bullet | `tools:` frontmatter (read-only vocabulary only) |
| Tool allowlist | `permission.bash` / `permission.task` | tool filter block | `tools:` frontmatter list |
| Handoffs | `permission.task` names | subagent roster / `subagent_*` tools | `spawns:` frontmatter plus `task` |
| Model | `model` / `variant` frontmatter | `agentOptions.provider/model` | `model:` list of `@role` selectors, resolved through `modelRoles` |

The OMP column is the `omp` conduct variant plus the projection rendered from
`omp/catalog.yaml` by `tooling/render_omp.py` (see `omp/README.md`). OMP
frontmatter carries `name`, `description`, `tools`, `spawns`, `model`,
`thinkingLevel` and an optional `output` schema; the library never commits a
rendered projection, because the slots are project-owned.

## Instantiating the autonomy layer

The runtime layer is instantiated the way a template is: the library owns the
shape and the invariants, and the consumer fills the small set of facts that
only it can know. This section names those artifacts and the order to fill
them; it does not add slots to the contract above.

### What a consumer instantiates

| Layer | Artifact the consumer fills | Library source | Validation command |
|---|---|---|---|
| Work authorization | A policy block: each source's allowed list, its admission cells (listed/unlisted x addressed/unaddressed) and the enabled rules. Which cells are `explicit` is the consumer's decision; `observe` is the documented starting mode (WA-07) | `standards/work-authorization.md` (WA-01..WA-12) | Rule review against WA-02 and WA-07; no library checker for the block itself |
| The grant record | One `agent-mandate/1` record per accepted unit, stored with the unit | `standards/mandate.schema.json`, `exemplars/mandate-example.json` (WA-04) | `python3 tooling/check_mandate.py PATH` |
| Durable effects | The effect kinds the consumer's runtime can perform, and the retry class (`defer`, `transient`, `permanent`) each kind maps to | `standards/durable-effects.md` (EF-02, EF-05) | No library checker; the consumer gate asserts one row shape and one retry class per kind |
| Message delivery | The transport, the permanent `gone` conditions it can return, and the payload limit with the unit that limit is measured in | `standards/message-delivery.md` (MD-04, MD-08) | No library checker; the consumer gate asserts the closed `gone` set and the stored unit |
| Notification | The word ceiling, the one fixed disclosure line, and the conversation a result returns to | `standards/agent-notification.md` (NT-04, NT-07; NT-05 for a question's destination) | No library checker; the transport rejects a message above the ceiling rather than truncating it (NT-04) |
| Model surface | A registry listing every model-visible asset with a measured budget, plus the rule-family map | `standards/model-surface.json`, `tooling/check_model_surface.py` (AP-01, SK-03) | `python3 tooling/check_model_surface.py --root <consumer> [--registry <path>]` |

### Order of work

1. Read WA-01..WA-12 and decide the admission cells: for each source, which
   (listed, addressed) combination is `explicit`, which is `inferred`, and which
   is refused.
2. Write the policy block with the allowed list and the enabled rules, and give
   it a version; every grant records the `policy_version` it was admitted under
   (WA-03, WA-04).
3. Add the mandate record for the unit to the consumer's unit store, one record
   per accepted unit, and validate it before the unit starts (WA-04).
4. Map each effect kind to its retry class and record that mapping beside the
   queue's kind configuration, including `base`, `cap` and the maximum attempt
   count for a `transient` kind (EF-05).
5. Set the notification limits: the ceiling in the transport, the disclosure
   line, and the destination conversation (NT-04, NT-07).
6. Register every model-visible asset with a measured budget and the
   rule-family map, then measure again after any prompt change (AP-01, SK-03).
7. Run each validator in the consumer gate, so a bad record fails at the same
   place as a bad template.
8. Only then enable `auto`: `observe` is the default for a new deployment, and
   moving to `auto` requires reading the recorded "would accept" decisions
   first (WA-07).

### Start with the admission cells

A consumer's first artifact is the admission-cell decision, not an enforcement
path: which identities may ask, which cells are explicit, and which scopes can
receive unaddressed messages at all (WA-01, WA-02, WA-07). The cells are data;
the gate, the mandate record and the notice on a rules change are all derived
from them, so writing enforcement first produces a gate with nothing to gate.
`packs/containeromat-admission-cells.md` is a worked decision record: the cell
table with the consequence of each value, the policy-block shape whose three cell
names are the `basis.cell` values of `standards/mandate.schema.json`, the open questions with one
recommended default each, and the evidence that would prove a cell later.

### What the library cannot decide for a consumer

| Decision | Owner |
|---|---|
| Which identities may ask for work | The consumer's source owner. The allowed list belongs to one source; a cross-source mapping is prompt text (WA-02) |
| Which admission cells are `explicit` rather than `inferred` | The consumer's policy owner. The library defines the two strengths, not which cell carries one (WA-02) |
| The notification ceiling value | The consumer's channel owner, inside the hard ceiling NT-04 sets |
| The transport's `gone` set | The transport owner. The set is versioned with the channel kind, and adding a condition needs evidence that retrying cannot succeed (MD-04) |
| The budget numbers per surface | The consumer's prompt owner. The library ships measured maxima for its own tree, not a budget for an unmeasured one (AP-01) |

### A worked command block

The consumer's `--root` must contain the library `standards/*.md`: rule families
resolve as `root / standards/<file>`, so a vendored submodule alone is not enough
(copy or symlink those files, or point `--root` at a tree that holds both).

A consumer checkout that vendors this library as a submodule named
`agent-prompts` runs the validators from its own root:

```sh
python3 agent-prompts/tooling/check_mandate.py mandates/UNIT.json
python3 agent-prompts/tooling/check_model_surface.py \
    --root . --registry standards/model-surface.json
python3 agent-prompts/tooling/check_behavioral_evals.py --root .
python3 agent-prompts/tooling/check_skill_routing.py --root . --fail-on-warn
```

## Rules

1. Never edit a fragment; a divergence is a bug (see `docs/SYNC.md`).
2. Keep the block order: role, hard_rules, doctrine, workflow, conduct,
   output last.
3. Prose phase maps -- no `- ` or `1. ` markers inside `<workflow>`
   (instruction-element budget).
4. Instantiated files must contain no `{{...}}` slots.
5. Record the pinned versions in your registry:
   `template_version` + `fragment_versions` from the template frontmatter.
6. Check the instantiation: `python3 tooling/validate_templates.py --root <project> --instantiate`
   scans `**/*.instantiated.md` for slot residue and validates structure/budget.
7. Admit the runtime before trusting the instantiation
   (`standards/agent-adapter.md`, AD-02/AD-03): write one
   `agent-admission/1` record per runtime with a four-valued state per required
   capability, compute admission fail-closed, and refuse rather than fall back
   to the host's unconstrained default. Validate with
   `python3 tooling/check_admission.py <record>`. A refused record is a valid
   answer; an unrecorded runtime is not admitted.
8. Verify with a record, not a sentence (`standards/verification-integrity.md`,
   VI-01): the first gate verdict after instantiation is a
   `gate-verdict.schema.json` record validated by
   `python3 tooling/check_gate_verdict.py`.

A runtime that adopts the authorization, effect, delivery and notification
rules instantiates them as a second, separate layer; see
`## Instantiating the autonomy layer` for the artifacts and their order.

## Pack manifests and overlays

A project can drive instantiation from one manifest instead of copying templates
by hand. `tooling/render_agents.py` composes:

    library template + project slots + project overlay + fragments
        -> agents/<name>.md

Manifest shape:

```yaml
schema: agent-pack/1
project: <project>
fragments: <project-relative fragment dir>   # optional; default: library fragments/
agents:
  - name: <output name>
    template: agents/<domain>/<template>.md  # library-relative
    output: agents/<name>.md                 # project-relative
    slots: {PROJECT_ID: <project>, ...}
    overlay: packs/<project>/overlays/<name>.md
```

The overlay uses the same block tags as the template. `mode="replace"` is the
default; `mode="append"` adds project bullets to a shared block:

```text
<hard_rules mode="append">
- Project-only rule.
</hard_rules>

<scope mode="replace">
Project-specific scope text.
</scope>
```

`<doctrine>` and `<conduct>` are library-owned and may not appear in an overlay.
Set `fragments` to a project directory only while the project still carries its
own vendored copies; remove it after re-vendoring the library fragments.

Commands:

```bash
python3 tooling/render_agents.py --pack packs/<project>/agents.yaml --write
python3 tooling/render_agents.py --pack packs/<project>/agents.yaml --check
python3 tooling/render_agents.py --pack packs/<project>/agents.yaml --check --only 'review-*'
```

The output is a vendor-neutral body: no YAML frontmatter. A vendor adapter is a
separate generator (for example a Kilo `.kilo/agents` renderer).
