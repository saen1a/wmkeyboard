# OpenCode V2 projection (consumer-owned)

OpenCode is a supported runtime for the neutral roles, but the library ships **no
projection directory for it** -- unlike `omp/` (catalog + overlays + renderer)
and `dsh/` (parameterized templates). This page records what a consumer has to
build, and why the library cannot build it once for everyone.

Live-fetched 2026-10-26 from the V2 documentation
(`https://opencode.ai/v2/docs/agents`, `/commands`, `/skills`) and measured
against a running `opencode v2.1.4`.

## What the runtime discovers

| Surface | Path | Unit |
|---|---|---|
| Agents | `~/.config/opencode/agents/<name>.md`, `.opencode/agents/<name>.md` | one file per agent; a nested path becomes part of the id (`team/reviewer`) |
| Commands | `~/.config/opencode/commands/<name>.md`, `.opencode/commands/<name>.md` | one file per command; only `.md`, nested paths become `/team/review` |
| Skills | `~/.config/opencode/skills`, `.opencode/skills`, plus the `.claude/skills` and `.agents/skills` compatibility roots | a directory holding `SKILL.md`, or a markdown file at the source root |

Skills are the one surface where the neutral canon is already the runtime format:
the skill id comes from the path, `name` is a display label only, and the body
needs no transform. Copy them verbatim.

## What the projection must enforce (AD-12)

OpenCode is the one supported runtime with no admission record in this library,
so no cell says whether it enforces the loop. A consumer that projects these
roles has to close that gap itself:

- write `standards/agent-admission.json` for its projection and give it a
  `loop_gate` cell (`standards/agent-adapter.md` AD-12). `supported` requires a
  pre-dispatch check -- a permission rule or hook that refuses a task without a
  clean `plan-review` verdict; otherwise record `degraded` and name the CI
  command that carries the gate (`tooling/check_plan_spec.py` before
  implementation, `tooling/check_loop_gate.py` over the ledger and verdicts);
- the session-level agent needs the loop sentence in its system prompt (the
  phase list without the gate is how a spec reaches implementation unreviewed);
- the per-agent `permissions` list is the tool allowlist, so a read-only role
  must not receive `edit`, `write` or `bash` there.

Run `python3 tooling/check_admission.py <record>` in the consumer's gate.

## What has to be transformed

An agent needs a V2 frontmatter block. V1 names are deprecated ("Do not use
legacy top-level fields such as `temperature`, `top_p`, `prompt`, `permission`,
`tools`, `disable` or `maxSteps` in new V2 agent configuration"), so a Kilo-shaped
`permission:` block has to be rewritten into the ordered `permissions` list:

| V1 / Kilo | V2 |
|---|---|
| `permission.bash.<pattern>` | `{action: shell, resource: <pattern>, effect: <allow\|ask\|deny>}` |
| `permission.task.<agent>` | `{action: subagent, resource: <agent>, effect: ...}` |
| `permission.edit` | `{action: edit, ...}` |
| `permission.read` / `.grep` / `.glob` | `{action: read\|grep\|glob, ...}` |
| `mode:` | `mode:` (`primary`, `subagent`, `all`; omitted means `primary`) |
| `hidden:` | `hidden: true` (visibility only, never a security boundary) |

Two ordering facts are load-bearing: the **last matching rule wins**, and global
top-level `permissions` are applied before agent-specific rules. A projection must
therefore emit a broad `*` rule first and every specific rule after it.

A command carries `description`, `agent`, `model` and `subagent` in frontmatter,
and the body is the template (`$ARGUMENTS` substitution). The neutral
`commands/*.md` in this library are dispatcher stubs with a `Use:` line and one
`Doctrine:` line and **no frontmatter**, per `standards/agent-prompt-standard.md`
(AP-14). A consumer that needs them discoverable adds the frontmatter itself; the
stub body is the part the library owns.

## Why this stays consumer-owned

The transform needs three inputs the library deliberately does not hold:

1. **Project slot values.** A neutral role carries `{{PROJECT_ID}}`,
   `{{PROJECT_RULES}}`, `{{MUTATION_POLICY}}` and friends. Only the consumer knows
   the fills.
2. **A tool grant.** A role declares a `tool_profile` (`read-only`, `gated-write`,
   `doc-write`, `batch-write`, `orchestrator`), not a per-pattern allowlist. The
   V2 `shell` action matches raw command text, so the grant has to be written in
   the consumer's own command vocabulary -- `cbm-query` or `forgejo-pr` mean
   nothing to a role template, and the library must not guess a project's binary
   names.
3. **A discovery root.** Whether the surface is baked into an image, seeded into a
   home directory, or committed under `.opencode/` is a deployment decision.

## Reference implementation

`containeromat` (`scripts/gen-paseo-opencode-surface.py`) is the worked example: it
renders `.kilo/agents` + `commands/` + the canonical skills into an image-baked
`~/.config/opencode` seed, translating the permission block exactly as the table
above describes, and gates the result with `--check` so the committed surface
cannot drift from its canon. Its pack (`packs/containeromat/agents.yaml`) supplies
the slot values; `packs/containeromat/exclusions.yaml` records which library roles,
skills, commands and presets that surface deliberately does not adopt.

## Known gap: presets

`dsh/presets/*.template.yml` are persona prefix/suffix documents. Neither the
OpenCode `agents` entry nor a Paseo `agentProfiles` entry has a field a persona
body can land in -- OpenCode takes its prompt from `instructions` plus the agent
body -- so a dsh preset has no OpenCode equivalent. A consumer that wants the
persona text must put it in an agent body or in the context file.
