# First-principles lenses

Loaded from `SKILL.md` when an escalation signal appears. Both lenses are
advisory: they sharpen a decision, they do not approve, gate, or implement it.

## Contents

- Decision Hygiene Review: invariants, preservation, owner/retirement matrix,
  falsification gates, verdict
- Architecture Integrity Lens: invariant, canonical owner, overlap,
  simplification, retirement, verdict

## Decision Hygiene Review

Use this escalation only when a design, fix, or plan needs endorsement before it
is written into a spec or implementation plan.

Escalate from the five-line review when any of these risk signals appear:

- multiple plausible paths and no clear selection criteria
- a new owner, duplicate owner, fallback, adapter, or compat-only carrier
- an old path that may need delete-first handling or a retirement trigger
- an unverified assumption that the proposal depends on
- user language such as "more elegant", "long-term stable", "first
  principles", or "Occam"
- a plan could encode the wrong owner, abstraction, compatibility boundary, or
  retirement schedule
- an existing object, behavior, responsibility, contract, or relationship may
  be reinterpreted, narrowed, replaced, or retired, and the proposal could lose
  a legitimate role or explicit reference while removing invalid authority

Use this compact shape:

```text
First-principles invariants:
- Non-negotiable goal:
- Non-negotiable constraints:
- Historical assumptions to delete:

Bounded preservation reminder:
- Evidence-backed behavior that must remain correct:
- Highest-risk counterexample:
- Material unknown / uninspected surface:
- Known explicit anchors / upstream-downstream refs and disposition:
- Role-before-value ambiguity, if any:

Owner / retirement matrix:
- New canonical owner:
- Old owner:
- Compat-only carrier:
- Delete-first / retirement trigger:

Falsification matrix (evaluate in order; stop at the first failing gate):
- Gate 0 - Premise evidence (stage-graded): design stage accepts spec/logic
  refs; implementation/runtime stage requires log, telemetry, or test
  evidence. No evidence -> park as watch-listed, do not enter value
  evaluation.
- Gate 1 - Decidability: no obtainable evidence to judge it -> park as a
  watched falsifier, do not act.
- Gate 2 - Value (any one): lowers future fix probability / shrinks the
  solution set / exposes a missing actionable acceptance criterion / the same
  broken assumption is reused elsewhere. Passing here still requires
  gates 3-5.
- Gate 3 - Cost match: change cost vs business priority, costed at the
  current stage; a valid but deferred counterexample is recorded in the owner
  doc, never parked orally.
- Gate 4 - Goal regression: the constrained solution still meets the original
  goal; re-read the accepted-constraint list at existing checkpoints (design
  review, plan approval, pre-completion verification).
- Gate 5 - Minimize then classify: boundary-shaped destructive claims must be
  minimized first; premise attacks classify as destructive directly.
  Classes: destructive (refactor/retirement track) | supplementary (boundary
  constraint) | watch-listed (falsifier). Conflicting counterexamples are
  decided by business-goal ranking, never by stacking constraints.
- Gate 6 - Adoption trace: the cheapest checkable form (regression test for
  destructive; contract, assertion, or checklist line for supplementary),
  written into the existing owner doc.

Verdict:
- Adopt / revise / reject / needs evidence:
- Blocking gaps:
- Next evidence:
```

## Architecture Integrity Lens

Use this narrower lens when a proposal is executable but may still encode the
wrong owner, abstraction, contract boundary, or retirement path. It is advisory
and may be embedded inside `Decision Hygiene Review` when that is enough.

Trigger it when any of these appear before approach selection, task
decomposition, review, or completion-risk reporting:

- responsibilities may overlap or a canonical owner is unclear
- the smallest diff adds a caller-side fallback, guard, adapter, or compat-only
  carrier
- an existing source-of-truth or contract could solve the class of problem at a
  higher level
- a stale owner, fallback, or old path may keep carrying real logic
- the work makes a long-term stability, "cleaner architecture", or
  higher-level simplification claim

Use this compact shape:

```text
Architecture Integrity Lens:
- Invariant: What must remain true for the system to be coherent?
- Canonical owner / contract: Which owner, contract, or source-of-truth should carry the behavior?
- Responsibility overlap: What duplicate owner, caller-side patch, fallback, or stale path might still carry real logic?
- Higher-level simplification: Can the problem be solved at the owner / contract / source-of-truth layer instead of by another local branch?
- Retirement / falsifier: What old path retires, or what evidence would disprove this architecture judgment?
- Responsibility / capability boundary: Which invalid authority retires, and
  does the same carrier still serve a separately evidenced legitimate role?
- Verdict: proceed | revise design | split owner | return to baseline | needs ADR/baseline sync
```

`Bounded preservation reminder` is a risk-triggered reasoning aid, not a
universal artifact or an exhaustive behavior inventory. Inspect the smallest
relevant contract, consumer, test, or history evidence. Preserve, rebind,
retire, or reject each known explicit reference; state unresolved relationships
as unknown instead of re-inferring them or claiming semantic completeness. This
lens does not build an authoritative relationship graph, prove referential
integrity or input lineage, calculate complete behavior coverage, or issue a
runtime gate.

Do not run this lens for every low-risk task. If it does not change the
decision surface, return to the active workflow immediately.

