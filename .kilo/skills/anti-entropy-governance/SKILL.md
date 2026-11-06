---
name: anti-entropy-governance
description: "Use when retiring old logic, collapsing duplicate owners, removing fallbacks, or touching schema, persistence, or source-of-truth boundaries. Destructive execution still requires explicit scoped confirmation, an evidence-backed retirement plan, and a verifiable rollback."
rigid: true
triggers:
  - entropy
  - drift
  - retire
  - duplicate owners
  - cleanup
---
<!-- Archetype copy imported from containeromat stacks/deepseek-harness/config/skills/anti-entropy-governance (pinned 2026-09-19). Adapted 2026-10-23: detailed class rules and guards moved to references/retirement-playbook.md. -->
# Source: https://github.com/GanyuanRan/Aegis (MIT) -- vendored 2026-09-15 @ 5b16eb9a

# Anti-entropy governance

Use this skill when the task is not merely "change code" but "remove old paths
safely without growing entropy". It chooses the retirement path; the repo's own
closeout rules verify it.

## When to use

Use when:

- old logic, duplicate owners, or stale fallbacks should be retired
- the choice is "delete the old path" versus "add another fallback"
- a new canonical owner exists and the old one may still carry behavior
- a cleanup or migration touches schema, persistence, source-of-truth, or an
  external compatibility boundary
- code retirement could be confused with live data deletion

Do not use for pure additive work, tiny edits, status checks, or bug fixes with
no owner collapse, fallback cleanup, or deletion choice.

## Core checklist

1. **Classify the target** before editing:

   | Class | Default path |
   |---|---|
   | `code-retirement` | `delete-first` |
   | `contract-carrying code` | classify by the principle; internal-only uses `delete-first` with high-risk verification |
   | `live-state mutation surface` | inspect; persistent-state reaches the confirmation gate |
   | `derived-state` | verify rebuildability, then decide |
   | `persistent-state` | `confirmation-first` |

2. **Choose one path**: `delete-first` for internal retirement;
   `compat-exception` only with active external dependency evidence;
   `confirmation-first` for irreversible targets or proven distribution whose
   consumers cannot be observed.
3. **Emit one contract**: the Anti-Entropy Declaration plus the Retirement
   Decision and the Verification Plan. That triple is the reporting shape.
4. **Do not execute destructively before the gate.** A warning or guard card is
   never destructive authorization.
5. **Verify the retirement**, not just "tests are green": main-path,
   lingering-reference, negative, and boundary checks.

**Permanent additions are gated.** A fallback, shim, or second owner needs
scoped confirmation of owner, activation, retirement, and cost; an override
records them. "Quickly" is not confirmation.

The detailed declaration, guard, gap, and completion templates are in
[references/retirement-playbook.md](references/retirement-playbook.md). Read it
before classifying a boundary target, emitting a guard card, classifying a gap,
or claiming completion.

## Core principle and hard stops

Default to reducing internal entropy, not preserving internal history.
Retirement is responsibility-scoped before it is carrier-scoped: name the
obsolete or duplicated authority first. If the same carrier has a separately
evidenced legitimate role, remove the invalid responsibility and keep only that
role. Internal code retirement is `delete-first`; external compatibility needs
active dependency evidence; persistent state needs scoped confirmation.

Without explicit scoped confirmation:

- no irreversible deletion is executed
- no runnable destructive command is emitted as the next action
- no broad assent ("OK", "continue") is treated as approval

If the scope changes, the previous confirmation is invalid. Unknown consumers
do not justify keeping an internal carrier; proven distribution does not justify
deleting without confirmation.

**Repo bindings.**

- The project's exception registry is the retirement authority. A retained
  `compat-exception` needs a registry row (class, rationale, source) before it
  stays; never remove an exception without operator approval plus a registry
  update.
- The project's closeout checks are the verification plan. A retirement closes
  only with fresh evidence in the self-check table.

## Complexity budget

For artifact-class budgets, the 800+/1200-line pressure signals, phase rules,
and `Complexity Closure`, read `references/complexity-governance.md` when
classifying an artifact or closing a major complexity follow-up.

## Doctrine position

Serves Review and Fix for retirement and collapse changes: audits duplicate
owners, fallbacks, and boundary risks before anything is removed (Review), and
gates destructive execution behind explicit scoped operator confirmation (Fix
discipline). Plan and Implement stay with the change spec; Push stays with the
operator.

## Common Rationalizations

| Rationalization | Why it is wrong |
|---|---|
| "The code is unused, I can just delete it" | Choose the deletion class first; contract-carrying or persistent-state paths need confirmation, not deletion. |
| "I'll keep the fallback as a safety net" | A fallback without a named owner is entropy; own it explicitly or retire it. |
| "The duplicate owner is harmless" | Two owners of one truth diverge; collapse to one owner or record why both remain. |

## Red Flags

- You are deleting without naming the deletion class.
- A compat exception has no external-dependency evidence.
- You are about to touch persistent state without a confirmation.
- Two components still own the same truth after the change.

## Verification

- The class, path, and one contract are recorded.
- The four checks ran with fresh evidence: main path, lingering reference,
  negative, boundary.
- A retained compat exception has an active dependency, an observation metric, a
  retirement trigger, and a registry row.
- The completion claim matches the outcome (`bounded mitigation` or
  `deferred debt` when old compat remains).

Shipped with the canon copy on the next consumer re-vendor:

- [references/retirement-playbook.md](references/retirement-playbook.md) --
  class rules, guards, declarations, gap taxonomy, completion semantics
- [references/complexity-governance.md](references/complexity-governance.md) --
  artifact-class budgets and pressure signals
