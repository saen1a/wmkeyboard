---
name: skill-creator
description: >-
  Guide for creating effective, high-quality skills that extend agent
  capabilities with specialized knowledge, workflows, and resources. Use when
  authoring a new skill or updating an existing one: SKILL.md structure,
  frontmatter, bundled scripts and reference files.
metadata:
  category: development
  source.repository: 'https://github.com/ComposioHQ/awesome-claude-skills'
  source.path: skill-creator
  source.license_path: skill-creator/LICENSE.txt
  source.commit: 92568c1edaff1bde5371154f036d959346c145a8
triggers:
  - skill
  - skill-creator
  - progressive disclosure
---
<!-- Archetype copy imported from containeromat .openhands/skills/skill-creator (pinned 2026-09-19). Adapted 2026-10-23: long-form anatomy and process moved to references/authoring-guide.md. -->

# Skill creator

A skill is a just-in-time procedure, not a document shelf. Author the smallest
body that makes another agent act correctly, and put conditional depth in a
reference that loads only when needed.

**A monolith is a routing failure.** When asked to put everything in one
`SKILL.md`, do not comply: keep the decision gate, the common-case procedure,
and verification in the body, and route platform commands, thresholds, worked
examples, and incident notes to references with explicit read conditions.

## When to use

| Use this skill when... | Do not use it when... |
|---|---|
| Creating a new skill for a recurring task | The procedure is a one-off; write a doc |
| Updating a skill that misroutes or overflows | The task is a role prompt or an AGENTS.md file |
| Deciding what belongs in the body vs references | The skill already exists and only a typo changes |
| Adding trigger cases or a verification step | You need a runtime tool description, not a skill |

For an existing skill, check the catalog and the target's skill root first: a
second skill that owns the same intent is a routing bug, not coverage.

## Decision gate

Before writing, answer these in one paragraph. If you cannot, the skill is not
ready.

1. **Recurrence**: which two projects (or listed planned project) will use it?
2. **Class**: discipline, workflow, tool/domain, or vendor (SK-09).
3. **Owner**: which existing skill is the nearest competitor, and why is this
   a different intent?
4. **Trigger**: what would a user say, including synonyms, that should load
   this skill?
5. **Check**: what observable behavior proves the skill worked?

Then apply the library's gates in `references/authoring-guide.md` section 7:
description width, trigger coverage, behavioral evidence, cited norms, and the
doctrine position.

## Workflow

1. **Collect concrete examples.** Ask for two or three real prompts and the
   artifact each produced. A skill without examples encodes preferences.
2. **Choose resources.** Repeated deterministic code goes to `scripts/`;
   schemas, variants, and long examples go to `references/`; output templates
   go to `assets/`.
3. **Scaffold.** Create the directory and `SKILL.md` (manual is fine; the
   upstream `init_skill.py` is not vendored here). Keep one H1.
4. **Write the body.** Description = what + when. Body = decision gate,
   procedure, verification. Put every conditional detail in a reference the
   body routes to. When proposing a shape, state the description (what + when,
   with two or three concrete trigger phrases), the observable check that
   proves it works, and when each reference is read. When refusing a monolith or
   a short description, still show the target description, the check, and a
   routing case (a user utterance and whether it loads).
5. **Verify.** Run the shape report and the routing/behavioral gates. A
   behavioral case for the skill class is part of done; do not defer it. Check
   that the body is self-sufficient for the common case and that every
   reference is routed.
6. **Iterate from use.** After real runs, fix the step that failed; do not
   add a section for every surprise.

Read [references/authoring-guide.md](references/authoring-guide.md) when you are
scaffolding a new skill, choosing between `scripts/`, `references/`, and
`assets/`, or packaging one; it carries the detailed anatomy, the resource
examples, and the original six-step narrative.

**Project constraints:**

- English only and ASCII only.
- No populated secrets; use `${VAR}` placeholders.
- Evidence duty: live-fetch every cited URL or path and record the fetch date.
- Prefer narrow, focused skills: the focused-bundle result is the reason this
  library caps the body at three modules (S10).
- Normative rules are cited, not copied: SK-01..SK-14 and AP-13/AP-14.

## Common Rationalizations

| Rationalization | Why it is wrong |
|---|---|
| "The description can be short" | The description is the discovery surface; without what + when the skill never loads. |
| "Progressive disclosure can wait" | Long bodies belong in `references/`; burying detail reduces adherence. |
| "I'll write the body first" | Start from the workflow and its failure modes, not prose that reads well. |
| "Scripts are optional" | Deterministic steps belong in bundled scripts, not improvised per run. |

## Red Flags

- The description has no trigger, or claims two intents.
- The body carries detail that belongs in a reference.
- The skill duplicates an existing skill's workflow.
- No verification step is defined.

## Verification

- Frontmatter has `name`, `description` (with a trigger), and `rigid` when gated.
- The description passes `check_skill_routing.py`; the class-required behavioral
  case exists (SK-11, SK-12).
- No real secret, internal hostname or customer record appears in the skill, its
  references or a case file; a hostile payload lives in `evals/` labelled as a
  payload, never inside the body a runtime loads (PS-13).
- Text quoted from a tool result or a fetched page is marked as data, and the body
  never tells the model to obey a directive it reads in a file (PS-02).

## Doctrine position

Serves Implement and Verify for skill authoring: writing the skill is Implement,
and the frontmatter, description, shape, and case gates are Verify. Push stays
with the operator.

## References

Shipped with the canon copy on the next consumer re-vendor:

- [references/authoring-guide.md](references/authoring-guide.md) -- read when
  scaffolding, choosing resources, or packaging; anatomy, resource examples,
  six-step process, init/package details
- `standards/skill-system-standard.md` -- SK-01..SK-14, the shape and evidence
  rules; `standards/prompt-security.md` -- PS-02, PS-13 for hostile material
