---
description: Dispatch the read-only review tracks for a diff or scope
agent: review-lead
---

Scope: $ARGUMENTS

Resolve the scope (a diff, a commit, a branch, or a path). Select the tier,
dispatch the matching read-only tracks, and merge only high-confidence findings
on changed lines. Do not edit. Do not fix. Return one verdict with evidence.

For a plan review, review the spec, not a diff, and use the plan-review gate.
