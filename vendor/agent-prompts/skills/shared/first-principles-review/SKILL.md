---
name: first-principles-review
description: "Use when asked for a first-principles or Occam's-razor review, or when a decision has competing constraints, fallback growth, duplicate owners, or architecture-direction risk. Reduce the problem to load-bearing facts, name the evidence, and separate reversible from irreversible choices."
rigid: true
triggers:
  - first principles
  - occam
  - reasoning
  - review
---
<!-- Archetype copy imported from containeromat stacks/deepseek-harness/config/skills/first-principles-review (pinned 2026-09-19). Adapted 2026-10-23: long-form lenses moved to references/lenses.md. -->
# Source: https://github.com/GanyuanRan/Aegis (MIT) -- vendored 2026-09-15 @ 5b16eb9a

# First principles review

## Purpose, bindings, and instrument

Default instrument: the Five-Line Review below. Escalate to the Decision
Hygiene Review only when a stated signal appears (multiple plausible paths with
no selection criteria, a new or duplicate owner/fallback/compat carrier, a
stale owner or old path still carrying logic, an unverified assumption the
proposal depends on, vague "cleaner/stable" language, or a plan that could
encode the wrong owner, boundary, or retirement schedule, including a
reinterpretation that could remove a legitimate role). Use the Architecture
Integrity Lens only on its own signals (overlapping responsibility, a
caller-side fallback or adapter in the smallest diff, a source-of-truth or
contract that could solve the class of problem, or a long-term stability
claim). Never run all three by default; every escalation cites its trigger. The
Decision Hygiene Review and Architecture Integrity Lens are in
[references/lenses.md](references/lenses.md).

Use this as a lightweight decision review before a directional choice is made.
It is a compositional aid, not a standalone workflow: it cleans the decision
surface that planning, implementation, and review then act on. When the review
materially changes direction, name the first principle, dropped assumption,
smallest sufficient path, or owner/retirement falsifier in prose. It is
advisory and grants no approval or completion authority.

Repo bindings:

- No speculative fixes: name the failing behavior and its evidence first.
- No invented upstream solutions: verify stock upstream behavior before
  designing a custom fix, and cite the live source.

## Use and non-use

**Use when:**

- The user asks for first principles, first-principles thinking, or Occam's razor.
- A design, plan, or fix has multiple plausible paths and unclear selection criteria.
- The task has ambiguous goals, competing constraints, or architecture-direction risk.
- Debugging is drifting into repeated fixes, fallback growth, duplicate owners,
  consumer-side patches, or "just add another branch" reasoning.
- A review finds the implementation may be locally correct but directionally wrong.

**Do not use** for simple Q&A, status checks, tiny wording or config edits, or
clearly bounded single-owner changes. Do not use it as a required step for every
task or as mechanical execution of an approved plan, unless a new directional
conflict appears.

- Prefer evidence from current project files, baseline docs, tests, logs, and
  user requirements. If evidence is missing, mark the line as unknown rather
  than inventing a principle.
- Keep the result advisory. This skill may recommend escalation, but it does
  not create an authoritative gate, durable policy state, or completion
  authority.
- If the five-line review does not change the decision surface, return to the
  active workflow immediately.
- Authority or time pressure does not skip the instrument: output the five
  labeled lines, then state that the result is advisory.

## Five-line review

Answer only what is needed, usually in five short lines:

```text
First Principle: What irreducible outcome must this satisfy?
Non-negotiables: What constraints cannot be broken?
Assumptions to Drop: What is habit, inherited shape, or unproven preference?
Smallest Sufficient Path: What is the least complex path that satisfies the first principle?
Escalation Signal: What finding would require spec/design/architecture review?
```

When the direction depends on a new mechanism or an unfamiliar domain, insert
one line before the escalation: `Known Prior Art: <proven pattern and source, or
unknown>`.

For repair choices, "smallest" means the smallest sufficient stable repair, not
the smallest textual diff:

```text
Minimality Check:
- Smallest textual diff:
- Correct owner:
- Bug class fixed:
- New branch/fallback added:
- Old path retired or scheduled: <condition that retires it, or "none">
- Verdict: sufficient repair | local patch | needs first-principles review
```

When the proposal adds a fallback, second owner, or compat carrier, state the
specific retirement or falsifier condition; "needs one" or "decide later" is not
a condition.

## Doctrine position

Serves Review: a first-principles or Occam critique of a decision, architecture,
or diff. Findings feed the Fix phase; the skill never implements or pushes.

## Common Rationalizations

| Rationalization | Why it is wrong |
|---|---|
| "More fallbacks make it safer" | Fallback growth without an owner is complexity, not safety. |
| "The existing pattern already does this" | Pattern reuse can encode the wrong owner or boundary. |
| "We can decide the owner later" | Deferring ownership is how duplicate owners appear. |
| "It works, so the design is sound" | Functioning code can still encode the wrong architecture direction. |

## Red Flags

- A proposal adds a second owner, fallback, or compat carrier.
- A load-bearing assumption is unverified.
- Two plausible paths have no selection criteria.
- The review answers the proposal instead of the premise.

## Verification

- The Five-Line Review ran; escalation signals were checked.
- Each recommendation names the owner, boundary, or retirement it affects.
- The result is advisory and does not claim approval or completion.

## References

Read [references/lenses.md](references/lenses.md) when you need the full decision-hygiene lenses.

Shipped with the canon copy on the next consumer re-vendor:

- [references/lenses.md](references/lenses.md) -- Decision Hygiene Review and
  Architecture Integrity Lens, loaded only on an escalation signal
