# Superagent prototype: mechanism adoption record (2026-11-02)

Status: adoption record, 2026-11-02. Owner: library maintainer.
Scope: eight adopted mechanism rows taken from a research prototype into this
library, the mechanisms deliberately not taken, and what the adoption does not
prove.

The prototype is a research artifact: a ticket/assignment runtime that accepts
work from sources, authorizes it, executes one unit per worker, performs side
effects through a durable queue, and exposes an operator panel. It is not
vendored here and is not a dependency. It was read as a source of mechanisms;
the portable part of each was restated as a project-neutral rule with a schema
or a checker, and the rest was left with the runtime.

## What was analyzed

| Subsystem | Examined for |
|---|---|
| Source intake | How an event becomes a candidate unit: source identity, receiving scope, addressing, and the point where an unlisted sender is refused |
| Authorization | The split between a deterministic gate over typed facts and a semantic assessment with evidence; the grant record, its basis, revalidation, and stop |
| Worker executor | One unit per worker, the handoff and return contract, what a child may spend, and what the parent records |
| Durable effect queue | Store-then-do, the idempotency key, the completion guard, retry classification, ordering, and restart behavior |
| Operator panel | What the operator is shown, what an intentional stop means, and how a status is derived and delivered |

Methods, 2026-11-02: a read-only extraction pass per subsystem (module
inventory in dependency order, then the call sites of the gate, the queue, the
notification path, and the surface registry); the numbered design documents read
in order and each claim mapped to a module; a gap matrix against this library's
surfaces (`standards/`, `skills/`, `agents/`, `tooling/`, `evals/`); then
check-first authoring, where a mechanism was adopted only after its check or
schema existed. No prototype count is quoted below, because the prototype is not
in this tree and a number from it could not be reproduced here. Every number in
this record is a count of an artifact in this repository and names its command.

## Adopted mechanisms

The standards cite these rows as the mechanism table. The ids are M1 gate,
M2 mandate record, M3 executor and delegation, M4 revalidation and stop,
M5 attention economy, M6 durable delivery (the queue and the channel),
M7 derived status, M8 model-surface lint, and M9 override provenance. One row
may carry more than one id when the prototype implemented the parts together.

| mechanism | prototype evidence | adopted as | what it does NOT prove |
|---|---|---|---|
| M1, M2, M4: Gate and assessment split, with a mandate record and its lifecycle | A deterministic gate over source, identity, and scope facts, separate from an assessment that returns a judgement with evidence; an immutable grant carrying strength, basis, and state; revalidation on resume instead of re-derivation | `standards/work-authorization.md` WA-01..WA-12, `standards/mandate.schema.json`, `tooling/check_mandate.py` | That a consumer's admission cells are right for its sources; that an assessment's judgement is correct; the checker validates the record shape and state invariants, not the decision |
| M6: Durable effect queue | Write the effect row before dispatch, derive the idempotency key from domain facts, guard completion by `(kind, key, seq, generation)`, classify every answer into three retry classes, and order per stream | `standards/durable-effects.md` EF-01..EF-10 | Exactly-once execution; handler idempotency; that a transport deduplicates; no runtime measurement here, because the guarantee is a design plus a test contract |
| M6: Receipt-backed channel delivery | A receipt written before the transport call; delivered, read, and acted-on kept as three separate facts; withdraw and settle owned by the receipt; deduplication by originating event, not by text | `standards/message-delivery.md` MD-01..MD-08 | That the remote platform accepts or honours the receipt; that a read receipt means a human read it; that per-transport payload limits are stable |
| M5: Attention economy | Default silence, an attention gate for unsolicited contact, a one-sentence ceiling, escalation as a structured record, terminal honesty | `standards/agent-notification.md` NT-01..NT-10 | That a human reads a notification; that the gate's threshold matches a team's interruption cost; no measured reduction in noise |
| M3: Delegation without authority | A spawn record points at the parent's grant; delegation does not mint a wider grant; the parent remains the authority for the child's scope | `standards/subagent-delegation.md` SD-12 | That a host enforces the scope at the tool layer; that a subagent runtime checks the grant pointer; delegation is a cost decision, not proof of containment |
| M7: Derived status | Status computed from stored facts by an ordered, first-match table; retry eligibility is a row in that table, not a flag | `standards/verification-integrity.md` VI-15 | That the fact table is complete and mutually exclusive for a consumer's states; that every consumer recomputes instead of caching the derived value |
| M8: Model-surface lint | Every model-visible string registered as a surface with a token budget; every rule ID a surface cites resolves to a heading in its owning standard | `standards/model-surface.json`, `tooling/check_model_surface.py` | That the registry lists every model input, because a new file must be added by hand; that a registered surface stays in budget at runtime; a budget is a bound, not a quality measure |
| M9: Override provenance | Volatile and derived layers ordered last, each override naming its source, and an upgrade diff that stays visible | `standards/prompt-assembly.md` AS-13, AS-14 | That a consumer's override is applied in the intended order; that visibility causes anyone to read the diff |

Worked references that pair with the rules:
`exemplars/mandate-example.json` (a validating grant),
`exemplars/durable-effects-reference.md` (one effect row, its guard and retry
shape), and `exemplars/control-plane-script.md` (the stop and status contract
the queue sits behind).

### Verified counts

Measured on this tree on 2026-11-02; each row names the command used.

| Fact | Value | Command |
|---|---:|---|
| Work-authorization rules | 12 | `grep -c '^## WA-' standards/work-authorization.md` |
| Durable-effect rules | 10 | `grep -c '^## EF-' standards/durable-effects.md` |
| Message-delivery rules | 8 | `grep -c '^## MD-' standards/message-delivery.md` |
| Notification rules | 10 | `grep -c '^## NT-' standards/agent-notification.md` |
| Assembly rules cited here | 2 | `grep -c '^## AS-1[34] --' standards/prompt-assembly.md` |
| Delegation rule cited here | 1 | `grep -c '^## SD-12 --' standards/subagent-delegation.md` |
| Status rule cited here | 1 | `grep -c '^## VI-15 --' standards/verification-integrity.md` |
| Registered model surfaces | 8 | `python3 -c "import json;print(len(json.load(open('standards/model-surface.json'))['surfaces']))"` |
| Rule families in the registry | 21 | `python3 -c "import json;print(len(json.load(open('standards/model-surface.json'))['rule_families']))"` |
| Model-visible files scanned | 90 | `python3 tooling/check_model_surface.py` |
| Model-visible tokens | 89,732 | `python3 tooling/check_model_surface.py` |
| Rule citations resolved | 100, 0 unresolved | `python3 tooling/check_model_surface.py` |

The last three values come from the checker summary line; the checker exits 0 on
this tree. The mandate example validates with
`python3 tooling/check_mandate.py exemplars/mandate-example.json`, exit 0.

## Rejected

| Candidate | Reason |
|---|---|
| Source-specific adapters (chat platform, ticket tracker, code host) | The portable part is the typed gate; an adapter per source is ingress code that belongs to the consumer, and this library has no source to adapt. Shipping one adapter would make the other sources look unsupported |
| The runtime's storage schema (tables, columns, migrations, ORM models) | A library ships a record contract, not a database. A schema with no migration path and no owner is a liability, and `mandate.schema.json` already states the fields a consumer must persist |
| Operator panel mechanics (screens, buttons, live views) | Product surface, not a prompt rule. Nothing in this repository can check a panel, and copying it would make the library own a runtime |
| The prototype's prompt-corpus size | Volume is not a mechanism. The accumulated prompt text is project-specific, would add dead weight, and would reintroduce vocabulary this library forbids |
| Unenforced prompt-level limits | Some prototype limits existed only in prompt text, which is exactly the failure WA-11 names. The adoption is the opposite: enforce where the actor cannot edit, or label the limit advisory. Copying the prompt-only form would import the defect |
| The prototype's retry timings and backoff constants | Tuning tied to one deployment. Three retry classes and a named cap are portable; the constants are not |
| The operator's chat thread as the only control interface | A notification channel is not a control plane. The control contract is an exit code plus a status line, as `exemplars/control-plane-script.md` shows |

## Method

A re-run of this record must do all of the following and report the diff, not a
fresh agreement with this text.

1. Clone the prototype, or obtain its snapshot, and record the revision. This
   record names no revision because the snapshot was not kept in this tree; a
   re-run must record one, or it cannot be repeated.
2. Count the mechanisms, not the lines. For each subsystem list the modules and
   the call sites of the gate, the queue, the notification path, and the
   surface registry. Record each command and its output next to the count.
3. Read the numbered design documents in order and map each claim to a module.
   A claim with no module behind it is not evidence for a row and must not be
   cited as prototype evidence.
4. Replay the citation check: `python3 tooling/check_model_surface.py` must
   report 0 unresolved and 0 violations, and
   `python3 tooling/check_mandate.py exemplars/mandate-example.json` must report
   0 violations. Both exit 0 on this tree today.
5. Compare adoption status. For each row, the `adopted as` heading must exist;
   `grep -c '^## WA-' standards/work-authorization.md` and the sibling counts
   above are the cheap form. A rule that was removed is marked withdrawn in the
   table, never deleted, so the audit trail keeps the decision.
6. Re-run the restart test EF-10 requires if the prototype is available: kill
   the effect process before commit, after commit before dispatch, mid-dispatch,
   and after dispatch before completion, then assert every committed effect
   exists exactly once at the handler. This record does not claim that test ran
   here.

## What this record does not prove

- No runtime measurement. None of the adopted mechanisms has an A/B, a live
  harness result, or an incident replay in this repository. A rule that is
  checked is not a rule that improves outcomes, and this record claims only the
  former.
- The prototype evidence is design evidence. The prototype was read, not
  benchmarked; nothing here says its mechanisms produced a measured gain in the
  prototype itself.
- The checkers prove shape, not judgement. `check_mandate.py` validates the
  record's shape and state invariants, which WA-12 states is its whole job, not
  the decision. `check_model_surface.py` validates registration, budgets, and
  citations, not whether a surface is well written.
- The budgets are caps set just above the measured maxima of the current tree,
  not targets set by outcome evidence. They catch drift; they do not prove a
  shorter surface is better.
- The rejection list is scoped to this library's shape. A runtime that needs
  source adapters or a storage layer should take those from its own product, not
  read this table as a verdict on them.
