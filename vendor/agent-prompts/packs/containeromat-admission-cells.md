# Admission cells: containeromat's first pickup decision

Status: **decided 2026-11-01 by the operator; still not an adoption record.**
Nothing in this file changes the consumer tree, and nothing here is evidence that
the consumer adopted the autonomy layer.

The gap section of `packs/containeromat.md` names the pickup order. The first
step is not code: before a consumer can enforce `standards/work-authorization.md`
(WA-01..WA-12), it has to decide **which messages may start work at all**. That
decision is data (three cells per receiving scope plus an accept mode), and every
later artifact -- the gate, the mandate record, the notice on a rules change --
is derived from it. Writing an enforcement path before the cells exist produces a
gate with nothing to gate.

## The decision

Five questions, answered by the operator on 2026-11-01. The recommendations in
this file were accepted unchanged, so the start is deliberately narrow.

| Question | Answer | What it means |
|---|---|---|
| Does an adapter exist in this wave? | **No, decision only** | The cells are recorded as the specification a later adapter must implement. Nothing reads Forgejo events, so `observe` has no gate to observe with yet -- stated here so nobody mistakes this record for working enforcement |
| Who is on the list? | **The operator's Forgejo identity only** | One identity, extended after a week of recorded decisions rather than before |
| `unlistedAddressed` | **`ignore`** | The list is the only entrance; addressing the agent does not bypass it |
| `listedUnaddressed` | **`ignore`** | No enabled rule exists, so `inferred` could only record "no rule matched" at attention cost |
| Bot list | **Empty** | No bot produces candidates, not even `inferred` |

What follows from the answers, in order: nothing to build now (no adapter), a
five-line policy block when one exists, and one recorded `observe` week before
any cell is widened. Widening is a rules change and therefore a notice to live
units (WA-09), not a quiet edit.

## What the rules force, before any consumer choice

| Rule | Consequence for this decision |
|---|---|
| WA-01 | The gate decides from typed facts only: source, sender identity, whether the message addresses the agent, receiving scope, sender on the list, bot on the list. The model's opinion is not an input |
| WA-02 | Two strengths only. `explicit` = a listed identity addresses the agent, or a cell configured as explicit. `inferred` = needs an enabled rule **and** proactive acceptance |
| WA-03 | The basis is recorded per source in that source's identities; identities are never mapped across sources |
| WA-07 | `observe` is the starting mode: assessments run, decisions are recorded as "would accept", nothing is accepted |
| WA-03 | A refusal is a record, so "we ignore everything" is a visible state, not a silence |

## What is evidenced about this consumer today

- The consumer works on **Forgejo**: PRs, CI, and an operator merge gate
  (recorded in `packs/containeromat.md`; the CI battery is
  `.forgejo/scripts/tests/run.sh` plus `scripts/ci-replica.sh --fast`).
- Work is requested by the **operator** in a session; an agent-authored change
  reaches main only through a PR the operator merges.
- The consumer ships **no source adapter** today: there is no watcher reading a
  Forgejo event stream, no bot identity, and no admission table in its gate. The
  cells below are therefore a *design decision for a future adapter*, and the
  correct current state of every inferred-authority cell is "not applicable,
  nothing receives".
- The consumer checkout is not present in this environment, so no identity list,
  bot account, or scope inventory could be read. Anything about a login in this
  file would be invented; there is none.

## The three cells, per receiving scope

A cell exists only where the scope can receive that kind of message (`observed`);
a scope that receives addressed messages only cannot have an unaddressed cell
(WA-01).

| Cell | Values | Recommended here | What the choice authorizes | What breaks if chosen wrong |
|---|---|---|---|---|
| `listedUnaddressed` | `inferred`, `ignore` | `ignore` (WA-02 allows `inferred`; with no enabled rule it only records 'no rule matched') | a listed identity's unaddressed message becomes a candidate that needs an enabled rule | `inferred` in a busy channel turns ordinary discussion into assessments; `ignore` loses the follow-up that a rule would have matched |
| `unlistedAddressed` | `explicit`, `inferred`, `ignore` | `ignore` | whether someone outside the list can open work by addressing the agent | `explicit` makes the list decorative, and the operator inherits work they never sanctioned |
| `unlistedUnaddressed` | `inferred`, `ignore` | `ignore` | whether an unlisted identity's ordinary message can ever become a candidate | `inferred` on a public scope is a work queue anyone can fill; it needs a matched rule plus `auto` to act, but it still costs attention |

Follow-up strength (WA-02) is separate: a message on a conversation that already
has a unit is judged by that unit's receiver, and an explicit cell still wins for
an unlisted sender.

## The decision, stated as fields

The consumer writes one policy block per source. The three cell names are the
values `standards/mandate.schema.json` uses in `basis.cell`, so a saved cell and a
recorded basis cannot disagree about vocabulary (the block is the consumer's
settings, not the grant record):

```json
{
  "source": "forgejo",
  "accept_mode": "observe",
  "scopes": [
    {
      "scope_key": "repo:owner/name",
      "observed": ["issue", "pull_request", "pull_request_review_comment", "branch_ci"],
      "cells": {
        "listedUnaddressed": "ignore",
        "unlistedAddressed": "ignore",
        "unlistedUnaddressed": "ignore"
      }
    }
  ],
  "listed": ["<operator identity on forgejo>"],
  "bots": []
}
```

Rules the block must satisfy, checkable by inspection:

- `accept_mode` is `observe` until decisions have been read (WA-07).
- `observed` lists only scopes the adapter really reads; every cell outside it is
  absent, not `ignore` by accident.
- `listed` holds identities of that source only (WA-03).
- `bots` is empty until a bot's messages are wanted as *inferred* candidates; a
  bot never produces `explicit` (WA-02).
- `branch_ci` has no sender, so its only meaningful cell is the unaddressed one.

## The questions, as they were put

Kept for the audit trail: each had one recommended answer so the operator could
reply in one word, which is the shape
`skills/general/operator-setup-interview` prescribes.

1. **Does the adapter exist in this wave?** -- answered: no. A cell table with no
   receiver is a document, and `observe` needs a gate to observe with.
2. **Who is on `listed`?** -- answered: the operator's own identity, nothing else.
   A second identity is added after the first week of recorded decisions.
3. **`unlistedAddressed`:** -- answered `ignore`. `explicit` is the setting that
   makes the list meaningless.
4. **`listedUnaddressed`:** -- answered `ignore` until a rule exists. With no
   enabled rule, `inferred` produces assessments that can only ever record
   "no rule matched".
5. **Bot list:** -- answered empty. Adding a bot is a later, separate decision
   with its own rule.

## How the decision would be proven later

| Claim | Evidence that counts | Evidence that does not |
|---|---|---|
| a cell admits an event | a recorded gate outcome naming the cell and the strength for a crafted event | "the config says so" |
| a cell refuses an event | a stored refusal with its code (WA-03) | an absent log line |
| `observe` records without acting | a Decision marked "would accept" and no unit created | a mode string in a file |
| the list is what the operator meant | the operator reading one page of recorded decisions | a reviewer's opinion |
| a grant matches its basis | `check_mandate.py` passing on the record the runtime produced | a hand-written record |

The proof step for an accepted unit is the mandate record: one
`agent-mandate/1` record per unit, carrying the cell that admitted it and the
enabled rules that matched. `provenance/mandate-wave12-autonomy-2026-11.json` is
a worked record from this library, not from the consumer.

## What this record does not claim

- The consumer has not adopted WA-01..WA-12; the gap section stays open.
- The cell values are approved; the *implementation* is not. No adapter exists,
  so nothing enforces them yet.
- No consumer gate command was added, and no consumer file was edited.
- The library gains no validator for a policy block: a checker for a format with
  one user is complexity ahead of need, and the mandate record is the artifact
  that already has one.
