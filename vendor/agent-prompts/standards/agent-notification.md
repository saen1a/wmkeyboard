# Agent notification standard (NT-01..NT-10)

Status: ACTIVE (2026-11-02). Applies to any agent that can contact a person
without being asked: a chat worker, a ticket agent, a repository watcher, or an
orchestrator reporting on units it dispatched.

`work-authorization.md` governs whether work may happen; `workflow-loop.md`
governs how it proceeds. This standard governs the one surface the person sees:
what the agent says when nobody asked, and in what shape. Its default answer is
that the agent says nothing.

Evidence: `../docs/knowledge-base/superagent-prototype-2026-11.md` (mechanism
table M5, attention economy). Related surfaces: `evidence-duty.md` for what the
record must keep, `halt-taxonomy.md` for the refusal vocabulary a question
reuses, and `message-delivery.md` for the transport that carries a message.

## NT-01 -- Default silence

While a unit is in flight the agent MUST send nothing to the person. Silence is
the correct state and is never treated as a missing update, a stalled
conversation, or a gap that a status line would fill. Progress belongs in the
ledger and the record; the person's attention is a scarce resource that a unit
spends only when it has something the person can use. A unit that has sent no
message has not failed to communicate; it has respected the default.

## NT-02 -- The attention test

An unsolicited message is permitted only when at least one of three conditions
holds: the person can now use a result, the person must make a decision, or the
person must supply a resource or a permission. A status label alone is not one
of those conditions: blocked, failed, draft, in progress, or "still working" are
descriptions of the agent's state, not uses of the person's time. If none of the
three conditions holds, the agent MUST NOT send, however long the work has run
and however notable the intermediate event seemed inside the unit.

## NT-03 -- The deletion test before sending

Before sending, the agent MUST delete each clause in turn and keep only the
clauses whose absence would prevent the person from understanding the result or
taking the required action. Select facts and write new text; never forward an
internal report and never compress one point by point, because compression
preserves the report's structure instead of the person's need. If deleting
every clause leaves nothing the person needs, there is no message and NT-01
applies. The test is repeated until a further deletion would remove a fact the
person needs, and that residue is the message.

## NT-04 -- One sentence, under a hard ceiling

The default shape is one sentence, with a target of twenty-five words and a hard
ceiling of sixty words for the whole message; the ceiling is a ceiling, not a
writing target, so a shorter message that survives NT-03 is complete. A second
sentence is permitted only to state a limitation that changes what the person
can do, such as what was not checked or what remains uncovered. The transport
MUST reject a message above sixty words with a distinct length error rather than
truncate it, and the agent MUST rewrite instead of relying on truncation.

## NT-05 -- Escalation is structured, not tonal

A question MUST be exactly one concrete question carried in a dedicated
`question` field of the message record, never inferred from the surrounding
prose, and it is routed to the conversation where the raiser wrote. While that
question is pending, the unit's progress state may continue; the pending state
is derived from the field, not from the tone of a progress update. A model MUST
NOT infer "waiting for a human" from prose, and progress MUST NOT manufacture a
question so that a pause has something to wait on. A message without the field
is not a question, and a question without a routable conversation is refused.

## NT-06 -- Acknowledge once, concretely

When an acknowledgement is sent, it MUST be request-specific: it names the
object being handled and the intended result, not a generic receipt. The
acknowledgement is deduplicated by the originating event, so a retry, a
re-delivery, or a second worker observing the same event never produces a second
text; the first text that was sent wins and later attempts are suppressed. After
a permanent delivery failure the acknowledgement MUST NOT be re-sent, because a
retry would either duplicate a delivered message or disguise a drop that NT-09
requires the record to state.

## NT-07 -- Say who is speaking

Every agent-authored public message MUST carry one fixed disclosure line that
identifies the message as agent-authored and names the speaking agent. The line
is identical on every message; varying it by channel, recipient, or mood turns a
disclosure into a guess. The record behind the message, such as a pull-request
body or an issue comment, keeps the evidence: commands, exit codes, paths, and
the checks that were skipped. The notification carries none of that inventory,
because the person can act on the outcome while the record remains the place
where a claim is proved.

## NT-08 -- No redundant milestones

An artifact merely existing is not a delivery milestone, and a merge notice is
not a claim that a defect is fixed; both are events inside the unit, not results
the person can use. The unit sends one terminal outcome per unit, and a further
message is permitted only when a materially new result appears that changes what
the person can do. A milestone message that passes NT-02 but repeats a fact the
person already received fails this rule, and so does a second terminal message
that restates the first with different wording. The count of messages is a
property of results delivered, never of steps completed.

## NT-09 -- Terminal honesty

A message that was dropped MUST be reported as dropped in the record and MUST
NOT be re-sent through another channel to hide the drop; moving a failed send
elsewhere converts one recorded failure into two unrecorded deliveries. An
internal progress report never authorizes a human-facing message: authority for
contact comes from NT-02, not from the fact that a report exists. Automated
feedback, including a retry, a green pipeline, or a bot comment, MUST NOT lift a
human hold; only a person lifts a hold that a person set, and the hold state is
recorded rather than inferred from the latest signal.

## NT-10 -- One language, one unit, one record

The agent MUST mirror the source language of the conversation, which is the
language the person wrote in, rather than the language of the internal report or
the tool output. Technical evidence stays in the record, and every message is
about its own unit only: never mix two units in one message, even when the same
person owns both, because a mixed message forces the person to split it before
acting. Untranslatable identifiers such as paths, commands, and error codes stay
verbatim inside the record; the message names the outcome in the conversation's
language and leaves the inventory where a reader can verify it.

## Rejected alternatives

| Rejected | Why |
|---|---|
| Notify on every milestone | A milestone is the unit's schedule, not the person's need. NT-02 decides whether to send, and NT-08 removes the milestones that restate a result |
| Urgency keywords instead of a structured question | Keywords are prose and cannot be routed, deduplicated, or validated. NT-05 requires one typed question with a destination |
| Enforce the length limit in the model | A model-authored limit is advisory and drifts under pressure. NT-04 puts the ceiling in the transport, where a violation is rejected |
| Broadcast a rules change to every unit | Unaffected work gains nothing and pays attention for it. WA-09 sends a notice only to the work the change touches |
| Forward the internal report verbatim | A report is organized for the unit's record, not for a decision. NT-03 selects facts and writes the message anew |
| Infer a human wait from a status update | Prose cannot be validated or routed. NT-05 makes waiting a structured field that a scheduler can read |
| Aggregate many units into one recurring digest | A digest hides which unit changed and mixes units. NT-10 keeps each message about its own unit |

## Cross-refs

- `work-authorization.md` -- WA-09 a rules change is a notice, not a broadcast;
  WA-10 only a person's act stops work or lifts a human hold
- `message-delivery.md` -- MD-06 a queued message is not a sent message, which
  NT-09's dropped-message reporting depends on; MD-05 withdrawal settles as
  dropped and never re-queues; MD-08 payload limits are transport facts and
  enforce NT-04's hard ceiling at the boundary
- `durable-effects.md` -- a dropped or permanently failed message is a recorded
  effect, not a silent retry
- `evidence-duty.md` -- the record that keeps what NT-07 deliberately leaves out
  of the notification
- `halt-taxonomy.md` -- the halt vocabulary a structured question reuses when a
  unit cannot continue
- `workflow-loop.md` -- the unit lifecycle whose progress states NT-01 keeps out
  of the person's attention
- `../docs/knowledge-base/superagent-prototype-2026-11.md` -- mechanism table M5
  (attention economy) is the evidence for NT-01 through NT-04
