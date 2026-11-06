# Retirement playbook

Loaded from `SKILL.md` when a retirement crosses a class boundary, needs a
guard card, or hits a post-deletion gap. It carries the detailed class rules,
guards, declarations, gap taxonomy, and completion semantics.

## Contents

- Deletion classes
- Default path by class
- Hard stops
- Data destruction guard
- Anti-entropy declaration
- Retirement decision
- Verification plan
- Gap taxonomy
- Gap closure
- Compat exception gate
- Completion semantics
- Common mistakes

## Deletion Classes

Classify the deletion target first:

- `code-retirement`
  - source code
  - internal triggers
  - duplicate owners
  - stale fallback branches
  - compat-only carriers
  - dead tests or config tied to removed internal behavior

- `contract-carrying code`
  - schema definition files
  - migration files
  - public API contract code
  - host install or discovery code
  - persistence read/write logic

- `live-state mutation surface`
  - code or commands that would mutate live databases, object stores, queues,
    or other persistent state

- `derived-state`
  - rebuildable caches
  - generated indexes
  - temporary exports
  - recomputable artifacts

- `persistent-state`
  - live database tables, columns, rows
  - source-of-truth object storage files
  - user records
  - permission, identity, membership records
  - audit, billing, irreversible business records
  - non-rebuildable queue or event contents

## Default Path By Class

- `code-retirement` -> `delete-first`
- `contract-carrying code` -> classify by the core principle in `SKILL.md`; internal-only
  retirement uses `delete-first` with high-risk verification
- `live-state mutation surface` -> inspect and classify; destructive execution
  still requires confirmation when it reaches persistent-state
- `derived-state` -> verify rebuildability first, then decide
- `persistent-state` -> `confirmation-first`

## Hard Stops

If the target is `persistent-state` or another irreversible source-of-truth
object:

- do not execute deletion automatically
- do not emit a runnable destructive command as the next action
- do not call a destructive tool
- do not interpret generic agreement as confirmation
- ask for explicit scoped user confirmation
- request a backup, rollback, or migration note when relevant

Examples that require confirmation:

- `DROP TABLE`
- `DROP COLUMN`
- `TRUNCATE`
- bulk delete of real business data
- deleting source-of-truth uploaded files
- deleting permission, identity, audit, billing, or membership records
- purging non-rebuildable queues or event streams

## Data Destruction Guard

When `confirmation-first` protects persistent-state or an irreversible
source-of-truth object, stop the normal retirement flow and emit:

```text
Data Destruction Guard:
- Target Class:
- Exact Target(s):
- Environment:
- Why Irreversible:
- Backup / Rollback Note:
- Allowed Read-Only Next Steps:
- Blocked Destructive Steps:
- Confirmation Required: yes
- Status: awaiting scoped confirmation
```

Only explicit scoped confirmation can continue. Broad assent such as "OK",
"continue", or "sounds good" is insufficient. If scope changes at all, the
previous confirmation is invalid and fresh confirmation is required.

## Anti-Entropy Declaration

Before deletion, state:

```text
Anti-Entropy Declaration:
- Deletion Class:
- Old Path/Object:
- Invalid Responsibility / Authority:
- Legitimate Capability Remaining on Carrier:
- New Canonical Owner:
- Expected Preserved Behavior:
- Expected Retired Behavior:
- External Boundary Touched: no | yes
- Source-of-Truth Data Risk: none | possible | confirmed
- User Confirmation Required: no | yes
```

If `User Confirmation Required: yes`, stop the normal delete-first flow.
Persistent-state or irreversible targets enter `Data Destruction Guard`;
external-unknown code stays in the `Retirement Decision` hold below.
This declaration, with the Retirement Decision and the Verification Plan,
is the single reporting shape; expand it only when task risk requires it.
When anti-entropy materially shapes a completed task, its preserved and
retired behavior, deletion class, retained boundary, verification plan and
residual risk flow into the project's self-check table.

## Retirement Decision

Choose one path only:

```text
Retirement Decision:
- Path: delete-first | compat-exception | confirmation-first
- Why:
- Non-edits:
```

Rules:

- choose `delete-first` for internal retirement unless a stronger boundary blocks it
- choose `compat-exception` only when an external dependency is proven
- choose `confirmation-first` for irreversible targets, or proven distribution
  whose consumers cannot be observed

If `Path = confirmation-first`, no destructive execution may happen until
scoped confirmation is received. For external-unknown code, earlier generic
deletion instructions do not count; disclose the risk first.

## Verification Plan

Do not verify only by "tests are green". Verify that the old logic actually
died and the new owner actually carries the behavior. The plan is discharged
through the project's closeout chain and self-check table.

```text
Verification Plan:
- Main-path check:
- Lingering-reference check:
- Negative check:
- Boundary check:
```

Meaning:

- `Main-path check`: the new canonical owner still satisfies intended behavior
- `Lingering-reference check`: the retired responsibility is no longer active;
  when its carrier was deleted, the old path is no longer referenced on the
  main path
- `Negative check`: the retired trigger or path really stopped working
- `Boundary check`: host, API, schema, or persistence boundary was not
  accidentally broken

## Gap Taxonomy

If a gap appears after deletion, classify it before repairing:

- `expected-retirement`
- `missing-owner-logic`
- `stale-internal-consumer`
- `baseline-gap`
- `external-compat`
- `persistent-state-risk`

`persistent-state-risk` is a stop condition, not a normal repair branch.

## Gap Closure

Repair order:

- `expected-retirement`
  - update tests, docs, or caller expectations
- `missing-owner-logic`
  - fix the new canonical owner
- `stale-internal-consumer`
  - migrate the internal consumer
- `baseline-gap`
  - correct requirement, spec, or baseline first
- `external-compat`
  - allow compat only if active external dependency evidence exists
- `persistent-state-risk`
  - stop and ask for user confirmation

Use this contract:

```text
Gap Closure:
- Gap Found:
- Gap Type:
- Repair Action:
- Reintroduced Compat: no | yes
- If yes, External Dependency Evidence:
- Retirement Trigger:
```

If `Gap Type = persistent-state-risk`, stop and return to the confirmation
gate. Do not improvise a destructive repair.

## Compat Exception Gate

Retention is allowed only if all are true:

- an external boundary is touched
- current active dependency evidence exists
- deletion would break a published or documented contract
- the current slice cannot complete owner repair or consumer migration
- an observation metric exists
- a retirement trigger exists
- an exception-registry row records the exception and its source

Without these, do not retain compat.

## Completion Semantics

Completion claims must reflect the real outcome:

- internal retirement with old compat preserved -> `bounded mitigation` or
  `deferred debt`, not clean retirement
- external compat retained with full evidence -> `bounded compatibility exception`
- persistent-state deletion without scoped confirmation -> not complete

Record the outcome in the project's self-check table row for the touched stack,
so the retirement decision and its evidence are visible at closeout.

## Common Mistakes

Do not:

- treat unknown dependency as proof of dependency
- treat missing active-dependency evidence as proof that deletion is safe across
  a proven external boundary
- keep both owners active "for safety"
- add a fallback before checking whether the gap belongs in the new owner
- confuse migration-file deletion with live database deletion
- treat source-of-truth data cleanup as ordinary code retirement
- call a task "cleaned up" when old logic still carries main-path behavior
- delete a carrier merely because one authority on it was invalid when a
  separately evidenced legitimate role remains
- treat a warning or guard card as destructive authorization

