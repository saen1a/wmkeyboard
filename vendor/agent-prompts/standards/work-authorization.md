# Work authorization standard (WA-01..WA-12)

Status: ACTIVE (2026-11-02). Applies to any runtime where an agent can start
work on behalf of other people: a chat bot, a repository watcher, a ticket
worker, an orchestrator that dispatches subagents.

The workflow loop (`workflow-loop.md`) governs how one unit of work proceeds
once it is authorized. This standard governs the step before it: who may ask
for work, how far that work may go, and what happens when the rules change
while the work is in flight. Without it, "the agent acted" is an unexamined
claim, and a rewritten prompt becomes a permission.

Evidence: `../docs/knowledge-base/superagent-prototype-2026-11.md` (mechanism
table M1, M2, M4). Contract: `mandate.schema.json` covers the grant and its
lifecycle only; the refusal and decision records that WA-03 and WA-12 require are
runtime-owned and have no library schema on purpose (one consumer, no second
user yet), so their required fields are stated in prose in those two rules. Checker:
`../tooling/check_mandate.py`. Example: `../exemplars/mandate-example.json`.
Runtime-capability admission is a different question and stays in
`agent-adapter.md` (AD-01..AD-12). This standard uses "admission cell" for a
slot of the intake table, never for a capability verdict: a capability is
admitted or refused by AD-03, a message is admitted or refused by a cell.

## WA-01 -- Two layers, never merged

Authorization has a deterministic layer and a semantic layer, and they have
different jobs.

- The **gate** decides admissibility from typed facts only: which source the
  event came from, which identity sent it, whether it addresses the agent, which
  receiving scope it arrived in, whether the sender is listed, whether the bot
  sending it is listed. It returns a strength or a refusal code.
- The **assessment** decides intent and scope: whether the discussion asks for
  this change, whether a target is established, whether a product decision is
  still open. It returns a judgement with evidence.
- The gate never learns from the assessment, and the assessment cannot widen
  what the gate refused. A refusal is final for that event; only a new event
  re-enters the gate.
- A prompt edit may change the assessment. It must never change the gate. If a
  permission exists only in prompt text, it is advisory and must be labelled so
  (WA-11).

## WA-02 -- Strength is a two-value ladder, and it decides the ceiling

Every admissible event carries exactly one strength.

| Strength | Meaning | May authorize |
|---|---|---|
| `explicit` | A listed identity addresses the agent, or an explicitly configured admission cell | Work in the declared scope without further rules |
| `inferred` | A listed identity's unaddressed message, an admission cell configured as inferred, or a listed bot | Only work that a **enabled rule** matches, and only when proactive acceptance is enabled |

- `inferred` never becomes `explicit` by repetition, confidence, urgency or a
  second model's opinion.
- A batch of events takes the strongest strength present and records the event
  that carried it.
- Anything not on the ladder is refused, including messages from unlisted
  identities outside a configured admission cell.

## WA-03 -- The basis is recorded, never re-derived

A grant records how it was admitted, in the source's own vocabulary:

- `via: addressed` -- a listed identity addressed the agent in a listening scope.
- `via: followup` -- a message arrived in a conversation that already has work.
- `via: admission` -- an admission cell of the receiving scope decided it, with
  the cell named.
- `via: bot` -- an identity on the source's bot list produced an inferred
  candidate.

Rules:

- The sender identity is the source's identity. Identities are never mapped
  across sources; "the same person on two platforms" is prompt text, not a
  record.
- A refusal records its code. A refusal without a code is not auditable and is
  treated as a defect, not a silent drop.
- Refused events are still persisted with their refusal, so a later rule change
  can be audited against what was ignored.

## WA-04 -- One immutable grant per piece of work

`mandate.schema.json` defines the record. Required properties (the schema requires `schema` and `history` as well):

- `mandate_id`, `policy_version`, `strength`, `basis`, `scope`, `actor`,
  `granted_at`, `state`.
- `scope` names the bounded surface the work may touch and is the ceiling of
  every later instruction.
- The record is immutable after creation. Exactly three operations change its
  state: creation, a person's withdrawal, and a failed revalidation that revokes
  it.
- Wider scope is a **new grant with a new `mandate_id`**. Rewriting the scope of
  an existing grant is forbidden, even when the same person asks twice.
- A grant survives the end of the work. Ending work does not end the grant
  unless a person withdrew it or revalidation revoked it.

## WA-05 -- Delegation transfers no authority

- A dispatcher (orchestrator, router, parent agent) hands a unit to another
  agent together with the original request and routing facts. It does not mint
  authority, narrow the request into a plan, or add acceptance criteria.
- The receiving agent re-derives scope from the original material and the
  standing rules. "The dispatcher accepted it" is not evidence of scope.
- A receiver that finds the work outside the grant, or belonging to another
  unit, hands it back **once**, with a one-sentence reason, unacknowledged as
  done. It never silently drops a request.
- Rules configured for a class of work may narrow the scope. Nothing configured
  narrows a grant out of existence or widens it beyond the record.

## WA-06 -- Proactive work needs three independent facts

An inferred candidate is accepted only when all three hold, each with its own
evidence:

1. the discussion targets this project;
2. the participants express intent to have a specific change implemented;
3. the direction is settled enough for the smallest unit the scope allows.

Rules:

- A preference, a comparison with another product, a design debate or a
  hypothetical is not an intent fact, whatever vocabulary it shares with a rule.
- An unanswered alternative, an open product decision or an unsettled visual
  direction fails fact 3.
- The judgement records one entry **per enabled rule**, matched or not. A
  negative judgement is a record, not an omission. Deriving positives from a
  smaller set (only the matches) is a defect.
- One accepted candidate produces at most one unit of work. Continuing an
  existing unit is a follow-up, not a second grant.

## WA-07 -- Classify failure honestly, and default to observing

- `unavailable` is not `ignore`. A missing tool, a permission error, a model
  failure or an unreadable attachment records `unavailable`, keeps the event
  queued for a bounded number of retries, and reports a health problem. It never
  records "does not qualify".
- Retries are bounded. The last attempt records a terminal `unavailable` with
  the reason; an unbounded re-evaluation loop is a defect.
- Proactive acceptance has three modes: `off` (nothing inferred is admitted),
  `observe` (assessments run and are recorded as "would accept", nothing is
  accepted) and `auto` (a positive assessment accepts).
- `observe` is the default for a new deployment. Moving to `auto` requires
  reading recorded decisions first.

## WA-08 -- Revalidation before resume, never re-derivation

Work that resumes after an end must be revalidated against the **current** rules
using its recorded basis:

| Recorded basis | Passes today only when |
|---|---|
| `addressed` | the source still listens to the conversation |
| `followup` | the source still listens, and the conversation still has work |
| `admission` | the cell still admits at least the recorded strength for that sender's current membership |
| `bot` | the identity is still on the bot list, proactive acceptance is enabled, and the matched rules are still enabled |
| `inferred` (any) | proactive acceptance is enabled and every matched rule is still enabled |

- A failed revalidation revokes the grant. The work stays ended, the pending
  messages are treated as reaching no unit, and further work needs a new grant.
- Revalidation is not a re-assessment: it reads the record, it does not ask a
  model again. A silent re-derivation turns a revoked grant into a live one.

## WA-09 -- A rules change is a notice, not a revocation

- Changing the rules discards in-flight assessments and re-queues their
  events under the new version.
- Live work receives a notice that names what changed for it: a matched rule's
  new text, a matched rule that no longer applies, a requester that may no
  longer start work, or proactive acceptance that is no longer enabled.
- Unaffected work receives nothing. A broadcast to every unit is noise and
  violates `agent-notification.md` (NT-01).
- The change does not cancel live work. Cancelling leaves half-finished changes;
  the notice is delivered and the unit decides within its grant.
- Every notice names the policy version it was computed under.

## WA-10 -- A stop is a person's act

- Only a person's explicit instruction ends work with a "stopped" outcome. An
  executor may report blocked, failed or dropped; it may not declare that a
  person asked to stop.
- A stop is terminal for that unit. Later messages there do not resume it; they
  enter the gate as new candidates unless another unit still owns them.
- A machine-originated pause (rate limit, budget, provider failure) is a
  different state: it holds delivery, it does not withdraw a grant, and it is
  lifted by the same machinery that set it.
- A pause authorised by a person stays until a person lifts it. No automated
  signal, retry or new message lifts it.

## WA-11 -- Instruction is not enforcement

- Every rule that must hold is enforced where the actor cannot edit it: tool
  allow-lists, argument validation, origin checks, resource-level reads
  (PS-09, AD-05, CF-10).
- A limit that lives only in prompt text is declared **advisory** in both the
  standard that owns it and the prompt that states it, so an auditor knows what
  a violation would prove.
- Prompt-level authorization text may restate the grant for the actor's
  benefit. It may never be the only place the grant exists.

## WA-12 -- Every decision is a record with a code

- A decision carries a closed code plus its values, never free prose alone:
  accept, stop, ignore, unavailable, with the reason codes the runtime defines.
- The record is queryable per event: which gate cells applied, which assessment
  ran, which unit it reached, and who handed it back.
- An unknown code at a boundary is refused, not stored. A stored decision that
  cannot be explained later is a defect in the record, not in the reader.
- `check_mandate.py` validates the record shape and the state invariants; it does
  not and cannot validate that the semantic judgement was right.

## Rejected alternatives

| Rejected | Why |
|---|---|
| A principal or membership entity, with identities mapped across sources | A person is event metadata; the allowed list belongs to one source. A cross-source mapping is prompt text, and a stored mapping goes stale silently |
| Checks on the follow-up path instead of at the grant | Context delivery is not authorization. The grant is the only thing that grants; anything delivered under it stays bounded by it |
| Revoking live grants when a rule is weakened | A revocation lands mid-change. Record and deliver the change instead, and revalidate at the next resume |
| One live unit per conversation | A conversation can carry independent pieces of work; duplicate suppression belongs to the assessment reading the existing units |
| Inferring "waiting for a person" from a report's prose | Prose cannot be validated. Waiting is a structured field (`agent-notification.md` NT-05) |
| Numeric confidence scores as authority | A score has no ceiling and no audit trail. Two strengths plus a recorded basis are checkable |
| Treating an orchestrator's acceptance as proof of scope | The dispatcher sees a card, not the source. Only the receiver reads the source |

## Cross-refs

- `workflow-loop.md` -- what happens inside one authorized unit (WL-01..WL-15)
- `agent-notification.md` -- what the unit may say, and to whom (NT-01..NT-10)
- `durable-effects.md` -- how a granted decision survives a crash (EF-01..EF-10)
- `prompt-security.md` -- PS-09 config as trust root, PS-05 privilege asymmetry
- `halt-taxonomy.md` -- the refusal vocabulary a decision reuses (HF-01..HF-15)
- `subagent-delegation.md` -- SD-12 delegation transfers no authority
- `../tooling/check_mandate.py` -- record validator
- `../exemplars/mandate-example.json` -- worked grant
