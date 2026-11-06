---
schema_version: 1.2.0
run_id: docs-migration-example
goal: Move the operator handbook from one file to the documented section layout without losing any procedure.
status: active
phase: Implement
owner: orchestration-orchestrator
started: 2026-10-24
updated: 2026-10-25T02:00:00Z
units_total: 3
units_done: 2
checkpoint: 4
last_progress_at: 2026-10-24T23:45:00Z
progress_max_minutes: 180
next_action: Run Review on unit U3 with the diff and the link checker output.
stall_window: 3
branch: docs/handbook-migration
model: example-model
budget:
  tokens:
    limit: 400000
    used: 120000
  wall_clock_minutes:
    limit: 480
    used: 95
  tool_calls:
    limit: 400
    used: 110
  units:
    limit: 3
    used: 2
acceptance:
  - id: A1
    criterion: Every procedure in the old handbook has a destination page.
    state: verified
    evidence: tooling/check_handbook_links.py exit 0, 2026-10-24T22:10Z
  - id: A2
    criterion: The index links resolve and no page is orphaned.
    state: verified
    evidence: tooling/check_handbook_links.py exit 0, 2026-10-24T23:40Z
  - id: A3
    criterion: An operator can follow the migrated procedure end to end.
    state: pending
    evidence: ""
---

## Units

| unit_id | phase | gate | status | artifact | evidence | kind | next |
|---|---|---|---|---|---|---|
| U1 | Push | pass | Done | docs/handbook/index.md | check_handbook_links.py exit 0; commit 4a1c9e2 | delivery | U2 |
| U2 | Push | pass | Done | docs/handbook/procedures/ | check_handbook_links.py exit 0; commit 9b7d110 | delivery | U3 |
| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |

## Checkpoints

| n | at | unit | phase | gate | kind | progress | artifact | next_action |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-24T21:00:00Z | - | Plan | pass | progress | 0/3; spec accepted | docs/handbook/plan.md | Implement U1 |
| 2 | 2026-10-24T22:15:00Z | U1 | Verify | pass | progress | 1/3; index migrated | commit 4a1c9e2 | Implement U2 |
| 3 | 2026-10-24T23:45:00Z | U2 | Verify | pass | progress | 2/3; procedures split | commit 9b7d110 | Implement U3 |
| 4 | 2026-10-25T02:00:00Z | U3 | Implement | pass | cadence | 2/3; recovery draft written | docs/handbook/procedures/recovery.md | Run Review on unit U3 |

## Decisions

- 2026-10-24: keep the old handbook as `docs/handbook/legacy.md` until A3 passes.
- 2026-10-24: migrate one section per unit; no page rewrites in the same unit.

## Open findings

- F1 (medium, owner U3): the recovery procedure still references the old screen name.
- No unresolved high finding.

## In-flight

| intent | key | state | at |
|---|---|---|---|
| Write the recovery page | recovery-page | done | 2026-10-25T02:00:00Z |

## Operator

RUN docs-migration-example | active | units 2/3 | checkpoint 4 | tokens 120000/400000 | next Run Review on unit U3 with the diff and the link checker output.
