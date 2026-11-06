# Skill system standard

Status: ACTIVE (2026-10-23).

Applies to every `SKILL.md` and bundled reference under `skills/**`, and to
consumer copies derived from that canon. SK-05 (anatomy) and SK-12 (class
evidence) apply to new and structurally edited skills; existing bodies are
grandfathered until a structural edit.

Relationship to the prompt standard: AP-13 governs skill invocation discipline,
AP-14 requires the `## Doctrine position` section, and AP-01 exempts skills from
a prompt element/token budget. This standard adds the shape, taxonomy, and
lifecycle rules that AP-13/AP-14 leave open. It does not restate them.

Evidence: `evidence/prompt-research-2026-10.md` (S8-S10, S17, S24-S26).

## Purpose

A skill system is a just-in-time procedure library, not a document shelf. It has
three layers with different costs:

| Layer | Loaded | Cost | Belongs here |
|---|---|---|---|
| Metadata (`name`, `description`) | Always, for every skill | Small but permanent; about 100 words per skill | Trigger vocabulary and the one job the skill does |
| Body (`SKILL.md`) | Only when the skill triggers | One context hit per invocation | Decision gate, procedure, check, anti-patterns |
| References (`references/*.md`) | Only when the body points at them | Zero until read | Long tables, variants, worked examples, API depth |

A body that carries reference material pays that cost on every invocation. A
body that omits the decision gate is not a skill, it is documentation.

## SK-01 -- One job per skill

A skill owns one intent cluster: one class of task, one decision procedure, one
output shape. If two tasks would not share a trigger description, they are two
skills. If a body needs more than three modules, the fourth module is either a
reference or a second skill.

## SK-02 -- The description is the router

- State what the skill does and the concrete situations that trigger it. All
  "when to use" information belongs in the description, not the body.
- Target 25-70 words, advisory range 5-90. Non-vendor descriptions currently
  run 9-51 words; the short end is routing debt, not a virtue.
- Use the words users actually say, including the common synonyms that the
  routing case file tests.
- Models under-trigger skills; a description that is accurate but too narrow is
  a routing bug (S25). Do not broaden it to mask a missed trigger (AP-13.3).
- No host-only tool names, paths, or project names (AP-13.6).
- One description must not claim two unrelated intents; that is what creates
  routing collisions.

## SK-03 -- Shape budget (advisory)

- Target: body <= 1,200 tokens (`bytes / 4`), at most 3 modules, under 500
  lines. Cap: 1,500 body tokens (hard for non-vendor bodies; advisory for
  frozen vendor copies), 8 H2 sections (S25). A module is one
  H2 section in the canonical anatomy; legacy bodies without module labels are
  measured by H2 count.
- Whole-file size (body plus references) is unbounded when the references are
  genuinely conditional.
- This is a shape signal, not an AP-01 prompt budget. Do not fail a skill for
  size alone; measure it, then improve it in a paired refactor.
- `tooling/report_skill_shape.py` is the measurement instrument. Run it before
  and after any shape change and keep both outputs in the change record.

## SK-04 -- Put depth in references

- Move tables, exhaustive checklists, framework variants, long worked examples,
  and API specifics into `references/<topic>.md`.
- The body must say when to read each reference and what decision it informs.
  A reference that the body never routes to is dead weight.
- A reference over 300 lines opens with a table of contents (S25).
- Organize multi-variant skills by variant: `references/aws.md`, `gcp.md`,
  `azure.md`, with the body selecting one (S25).

## SK-05 -- Canonical anatomy

```text
---
name: <lowercase-hyphen-name>
description: <what + when, 25-70 words>
rigid: <true|false>          # required for mode-gated skills
metadata:
  category: <domain>         # optional
---
<!-- provenance line: source, date, canon pointer -->

# <Title>

<One paragraph: what the skill buys, what it costs, when not to use it.>

## Module 1 - <decision gate>
## Module 2 - <procedure>
## Module 3 - <verification / failure handling>

## Doctrine position

<Phases served, entry/exit handoffs, what it does not do.>

## References

<Repo-only note when the references are library paths.>
```

One H1. No second H1, no `# Source:` in a repo-authored skill (that marker is
for vendored copies). Headings are stable so links and diffs stay clean.

Applies to new and structurally edited skills. The enforced subset is: one body
H1, `## Doctrine position`, at most eight H2 sections, the body cap, and
references routed from the body. Module labels, the exact `## References`
heading, and the 25-70-word description target are migration goals, not a claim
that every existing body already conforms. Imported `# Source:`/`# Vendored:`
header lines are legacy provenance, not body H1s (SK-10).

## SK-06 -- Cite norms, do not duplicate them

A skill may restate a rule only as a one-line operational reminder. The
normative copy lives in `standards/`. Two edited copies of the same gate drift;
a skill that needs the full rule points at the rule ID. Operational tables that
exist only to execute the procedure are allowed.

## SK-07 -- Doctrine position is mandatory

Every non-vendor runtime skill carries `## Doctrine position` per AP-14: the
phases it serves, its entry and exit handoffs, and what it does not do. A skill
with no phase position is a reference document. Vendor copies are exempt under
SK-10, which AP-14 records as the one exception.

## SK-08 -- Host neutrality

No host-only tool, loader, task tracker, or workspace path in the body
(AP-13.6). If a procedure needs a host capability, name the capability, not the
product. Vendor skills are the documented exception (SK-10).

## SK-09 -- Taxonomy classes

| Class | Job | Edit rights | Evidence tier |
|---|---|---|---|
| discipline | Enforce a behavioral invariant under pressure | Repo-authored; shape-standard applies | Tier 3 pressure cases required |
| workflow | Execute a multi-step procedure with a handoff | Repo-authored; shape-standard applies | Tier 3 dialogue case + paired baseline |
| tool/domain | Mechanics for a tool, format, or API | Repo-authored or adapted; shape-standard applies | Execution case when a fixture is possible |
| vendor | Third-party body kept as-is | Marker and source only; no structural edits | Upstream-owned; one trigger case (dialogue or execution) |
| project | One project's local procedure | Not hosted in this canon | Consumer-owned |

The class is a routing and evidence decision, not a prestige label. A vendor
skill that needs restructuring is forked under a new name with provenance
recorded, never edited in place.

## SK-10 -- Vendor freeze

Vendored skills are frozen as imported: the only permitted local change is the
import marker and source header. Documented adaptations already recorded in the
source header (for example an ASCII folding or a default intensity) are
grandfathered; do not add new ones. Vendor copies do not need
`## Doctrine position`, and they are exempt from the SK-03/SK-05 shape targets
and from SK-07. Their trigger cases exist so the library can prove the copy is
reachable, not to judge upstream content.

## SK-11 -- Routing evidence

- Every skill ships `evals/trigger/<skill>.json` with at least 3 positive
  prompts and 2 negative prompts owned by another skill. New skills start at 4
  positive and 2 negative.
- Positive prompts use user vocabulary, not the skill's internal terms.
- Negative prompts name the skill that should own the request, so a misroute is
  attributable.
- The lexical gate is the free CI check. A semantic or judge check is an
  additional experiment, not a replacement, until it is deterministic enough
  for CI (G-12).

## SK-12 -- Behavioral and execution evidence

- Every behavioral file carries at least 3 cases; the structural gate enforces
  that minimum.
- Discipline class: 3 pressure cases (time, sunk cost, authority) that argue
  for skipping the rule; expectations are observable behaviors.
- Workflow class: 3 dialogue cases; one exercises the handoff or return
  contract.
- Tool/domain class: 3 execution cases with fixtures when the tool is available
  in CI; otherwise 3 dialogue cases that check the command sequence.
- Vendor class: exempt from behavioral cases because the body is frozen (SK-10);
  the SK-11 trigger cases prove the copy is reachable.
- Applies to new and structurally edited skills. All 19 non-vendor skills now
  carry a file with at least 3 cases; the structural gate enforces schema and
  the five required discipline names. A new skill without cases is not
  validated.

## SK-13 -- Paired efficacy and metadata

A shape change (split, merge, trim, reference move) is an experiment:

1. Run the skill's cases with the skill and without it, same model/harness,
   at least 3 seeds where the runner supports seeds.
2. Record model, harness, seed, date, token use, wall clock, pass rate.
3. Change one thing.
4. Re-run the same cases and report the delta, including cost.
5. If the skill does not beat the no-skill baseline after cost is counted,
   fix or retire it. A smaller file is not a result.

No shape change is accepted on token count alone. AP-13.8 still governs the
baseline-or-deferral decision.

## SK-14 -- Lifecycle

| Stage | Required output |
|---|---|
| Propose | The recurring task, the class, and why an existing skill is not the owner |
| Baseline | Trigger cases, the no-skill result, and the current shape report |
| Build | Canonical anatomy, description, cases, references |
| Verify | `check_skill_routing.py --fail-on-warn`, `check_behavioral_evals.py`, shape report |
| Record | `skills/SKILLS.md` row, `PLAN.md` wave entry, and a `CHANGELOG.md` line |
| Retire | Archive note naming the replacement; no silent deletion |

A skill is never added "for completeness". A repo-authored workflow or tool
skill must recur in at least two target projects or serve a listed planned
project, matching the role-template rule in `CONTRIBUTING.md`. Vendor copies
and project-class skills are out of scope for that recurrence test.

## Refactor protocol

1. Measure: `python3 tooling/report_skill_shape.py --json`.
2. Classify: discipline, workflow, tool/domain, vendor, or project.
3. Pick the smallest change that fixes one advisory flag.
4. Write the reference file first, then cut the body, so nothing is lost.
5. Re-run the shape report and the three gates.
6. Record the before/after numbers and the paired result.

## Cross-refs

- `agent-prompt-standard.md` -- AP-13 invocation, AP-14 doctrine position
- `subagent-delegation.md` -- delegation gates and handoff contract
- `agent-context-files.md` -- repository context file rules
- `../docs/SKILL-TEMPLATE.md` -- copyable skeleton
- `../docs/knowledge-base/skill-prompt-refactor-2026-10.md` -- measured analysis
- `../skills/SKILLS.md` -- the current catalog and class assignment
