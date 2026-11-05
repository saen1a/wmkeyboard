---
name: grilling
description: >-
  Interview the user relentlessly about a plan or design. Use when the user
  wants to stress-test a plan before building, or uses any 'grill' trigger
  phrases.
metadata:
  category: development
  source.repository: 'https://github.com/mattpocock/skills'
  source.path: skills/productivity/grilling
  source.license_path: LICENSE
  source.commit: 8370e760d0251a3738e006aeacec6d1cb31dd208
triggers:
  - grilling
  - interview
  - requirements
  - spec
---
<!-- Archetype copy imported from containeromat .openhands/skills/grilling (pinned 2026-09-19). Canon switch deferred; see PLAN.md wave 2. -->

# Grilling

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time, waiting for feedback on each question before continuing. Asking multiple questions at once is bewildering.

If a question can be answered by exploring the codebase, explore the codebase instead.

## Common Rationalizations

| Rationalization | Why it's wrong |
|---|---|
| "The plan is clear enough" | The point is to surface what the plan never says; clarity is the hypothesis under test. |
| "I'll stop after a few questions" | Relentless means until the plan is decision-complete, not until it feels polite. |
| "This question is too basic" | Basic unstated assumptions are what derail the build. |
| "The user agreed, so it's settled" | Agreement is not a decision record; the answer goes into the plan. |


## Red Flags

- Questions are softening into approval.
- A load-bearing assumption went unchallenged.
- You stopped before the open decisions were resolved or explicitly out of scope.
- The plan still has competing constraints with no resolution.


## Verification

- Each resolved decision is recorded in the plan or explicitly out of scope.
- Remaining uncertainties are named, not hidden.

## Doctrine position

Serves Plan: it stress-tests a plan until it is decision-complete, and its answers
feed the spec that the PlanReview gate checks before Implement (WL-15).
Implement, Review, Verify and Push belong to the authoring session.
