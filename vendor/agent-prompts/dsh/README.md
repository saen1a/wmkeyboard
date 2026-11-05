<!-- TEMPLATE -- the deployed instance lives in <project>/stacks/deepseek-harness/config/ and is paired with that stack. -->

# dsh templates

Parameterized archetypes of the prompts that run inside the deepseek-harness
(dsh) stack. A project instantiates its own copy as part of that stack's
config; this directory never ships runtime prompts directly.

## Admission

`admission.json` records this runtime as **refused**, not admitted: the templates
are parameterized archetypes and no deployed instance was exercised, so every
required capability is `unknown` (`standards/agent-adapter.md` AD-02/AD-03). That
is the honest state and the intended fail-closed example: a projection with no
evidence is not admitted. Re-verify when the stack is deployed -- dump the
outbound `tools` array per TS-01, record the result and the date, then move the
capability rows from `unknown` to their measured state.

## Pairing invariant

Runtime prompts live in the deploying stack's config
(`stacks/deepseek-harness/config/`), paired with that stack: the stack owns the
seed, the version marker and the deployment. This directory holds the
parameterized archetypes only -- the source a new project instantiates from.
When an archetype changes, port the change into the stack config as a reviewed
change (and bump the stack's seed or copy version there); never treat the
library copy as deployed, and never let the two drift silently.

## Files

| File | Template of | Slots |
|---|---|---|
| `presets/orchestrator-persona.template.yml` | orchestrator preset main persona | PROJECT_ID, PROJECT_RULES, PROJECT_TOOLS, HANDOFF_TARGETS |
| `presets/generalist-prefix.template.yml` | generalist preset prefix persona | PROJECT_ID, PROJECT_RULES, PROJECT_DOCS_LAYOUT_RULE |
| `presets/seifomat-prefix.template.yml` | seifomat preset prefix persona | PROJECT_ID, PROJECT_RULES, PROJECT_LANG, PROJECT_VERIFICATION |
| `presets/reviewer-prefix.template.yml` | reviewer preset prefix persona | PROJECT_ID, PROJECT_RULES, PROJECT_REVIEW_SKILL, DSH_TOOLS, HANDOFF_TARGETS |
| `commands/review.template.md` | dsh review command | DSH_TOOLS, PROJECT_HANDOFF |
| `commands/knowledge-qa.template.md` | dsh knowledge-qa command | DSH_TOOLS, PROJECT_CORPUS |

Every file starts with the pairing banner, and the persona and prefix texts use
dsh runtime variables (`{{model}}`, `{{cwd}}`) alongside the library slots:
instantiate the slots, keep the runtime variables.

## Loop gate

`admission.json` records `loop_gate: unknown`, and the record is refused: this
runtime was not exercised in this cycle, the presets carry doctrine text but no
tool allowlist, and no pre-dispatch check could be probed. A dsh deployment that
claims plan-review enforcement has to close that cell first
(`standards/agent-adapter.md` AD-12) and run
`tooling/check_plan_spec.py` plus `tooling/check_loop_gate.py` in its own gate.
