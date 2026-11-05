# Durable effects standard (EF-01..EF-10)

Status: ACTIVE (2026-11-02). Applies to any runtime that performs a side effect
on behalf of a model: sending a message, launching a worker, relaunching work
after a crash.

Authorization decides whether an effect may happen (`work-authorization.md`);
the workflow loop decides how the unit that produced it proceeds
(`workflow-loop.md`). This standard governs the gap between a decided effect and
a performed one. That gap is where a process dies, a retry repeats work it
already did, and a caller's memory of "I sent it" replaces a fact. The rules
below make the effect a record first and an action second, so a restart can
finish the job without guessing.

Evidence: `../docs/knowledge-base/superagent-prototype-2026-11.md` (mechanism
table M6: store-then-do, domain-derived idempotency key, generation guard,
retry classes, per-stream ordering). Worked reference:
`../exemplars/durable-effects-reference.md`. The message case is
`message-delivery.md` (MD-01..MD-08).

Neighbouring rules: `long-horizon-runs.md` LH-12 owns crash recovery for the run
that produces effects; `verification-integrity.md` VI-15 owns the rule that a
status is derived from facts, which is why EF-02 stores facts and not a status.

## EF-01 -- Commit intent, then execute

The runtime MUST write the effect row in the same transaction as the decision
record that justifies it, and MUST dispatch only after that transaction commits.
The queue is the only path from a decided effect to the world: a worker reads
committed rows, never an in-memory notice passed from the deciding request.

Writing the goal in one transaction and the row in another is not equivalent.
The gap between them is exactly where a process dies, and an effect decided but
never recorded has no trace from which to resume. The reverse order is equally
wrong: an effect performed before its intent is durable cannot be deduplicated
after a crash, because nothing on disk says it was attempted.

The committed row is the durable unit of work. A decision that produced no row
is not a durable decision, and a runtime MUST NOT report it as scheduled. A row
that has not been dispatched is recoverable by design; it is the only shape a
crash can leave behind.

## EF-02 -- One row shape, one writer

Every effect uses one table and one row shape. The columns are fixed:

| Column | Holds |
|---|---|
| `kind` | The effect class. It selects the handler, the transport, the retry policy, and the stream key |
| `key` | The idempotency key derived by EF-03 |
| `payload` | The committed arguments of the effect, as data |
| `seq` | The ordering position inside the key's stream, assigned once |
| `generation` | The payload version, incremented by coalescing enqueue (EF-04) |
| `attempts` | Transient failures counted since the last enqueue or coalesce |
| `error` | The last failure: reason code plus message |
| `due` | The earliest time the row may run; while an attempt is in flight, the lease expiry. A null `due` marks a terminal row (EF-07) |
| `since` | When the current attempt or state began, for diagnosis and staleness reporting |

The primary key is `(kind, key)`. Only the queue writes this table: producers
enqueue through the queue API, workers complete through the queue API, and no
other component issues an insert, update, or delete against it. Readers may read
it; a reader that writes a status column turns a derived fact into a stored one
and violates VI-15.

One shape is what makes one completion guard possible (EF-04). A second table
for "special" effects, or an extra column owned by one handler, forks the guard
and the retry sweep, and the fork is discovered only when the two paths disagree
after a crash.

## EF-03 -- The idempotency key is derived from domain facts

The key MUST be a pure function of domain facts: the unit id, the effect kind,
and the request id that named the intent. It is computed at enqueue and again at
completion from values that survive a restart, so both sides agree without
sharing memory.

The key MUST be stable across retries and MUST NOT include anything that changes
between attempts: time, attempt number, process id, payload text, or random
bytes. A random key makes every retry a new effect, which is the failure the key
exists to prevent. Hashing the payload is also wrong: a reworded payload would
change the key and duplicate the effect.

Where the domain has no request id, the ingress event id assigned once when the
source event arrived serves as the request id. Where neither exists, the runtime
MUST assign one when the effect is first recorded, store it, and use the stored
value for every later attempt.

The key is an identity, not a secret and not a hash of the row. Two runtimes that
independently derive the same key for the same intent MUST reach the same row,
and a key that cannot be re-derived from the record is a defect in the record.

## EF-04 -- Enqueue upserts and coalesces

An enqueue for an existing non-terminal key MUST coalesce instead of inserting a
second row. Coalescing keeps `seq` because the ordering position belongs to the
effect, bumps `generation`, replaces `payload`, resets `attempts` and `error`,
and sets `due` to the current time unless `due` already lies in the future, in
which case the running lease or backoff is left to finish so two generations
never run at once for one key.

Completion MUST be guarded by the full identity `(kind, key, seq, generation)`:
the settle statement matches all four and affects at most one row. A worker that
finishes generation `g` after an enqueue produced generation `g + 1` MUST NOT
delete or overwrite the newer payload; its completion is stale and is discarded
without error. `seq` guards ordering and `generation` guards the payload, and
both are required: either alone lets a slow retry erase work it never saw.

An enqueue against a terminal row is refused (EF-07). The caller that wants to
repeat a finished effect derives a new request id and therefore a new key; it
does not resurrect the old row by resetting its fields.

## EF-05 -- Three retry classes, and only three

Every dispatch answer MUST be classified as one of `defer`, `transient`, or
`permanent`.

- `defer` means not due yet: an ordering wait, a quiet-hours window, or a named
  upstream condition. The row is rescheduled and the event does not count as a
  failure. `attempts` and the health counter are untouched.
- `transient` means retryable. The row is rescheduled with capped exponential
  backoff -- `min(cap, base * 2^(attempts - 1))`, with `attempts` counted after
  the increment, plus jitter -- `attempts` increments, and `error` records the
  last failure. The kind MUST name its `base`, its `cap`, and its maximum
  attempt count in configuration; an unbounded ladder is a defect, and an
  exhausted ladder converts the outcome to `permanent` with the reason code
  `retry_exhausted`.
- `permanent` means terminal. The row records the reason code and the last
  error, and it is never retried.

A failure that matches no declared class MUST be treated as `transient` and
recorded as such. Defaulting an unknown error to `permanent` silently discards
work the runtime merely failed to understand; the safe default retries and keeps
the name of the error, so the next reader can classify it.

## EF-06 -- Ordering per stream, not per queue

An ordered kind MUST consider only its oldest row per stream, and MUST wait
behind a row of that stream that is still in flight or backing off. That state
is the head's own `due`: while it lies in the future, the stream is blocked;
only a head with `due <= now()` is eligible. The stream key is a domain fact
named by the kind: for a message it is `(unit, conversation)` (MD-03); for a
worker launch it is the worker slot or the unit that owns the launch.

A blocked stream MUST NOT delay another stream. Selection filters by stream
before it takes the head, and a global first-in-first-out head that blocks the
whole queue behind one stuck row is a defect. A `defer` on the head blocks its
own stream only; every other stream keeps draining. A `permanent` outcome on the
head MUST settle that row so the stream advances, which is why a terminal row is
never left in place (EF-07).

An unordered kind MAY run rows concurrently. Two rows that address the same
domain fact still collide on the key, so concurrency is bounded by EF-04 rather
than by a lock in the handler.

## EF-07 -- Terminal states, and no resurrection

Every row MUST end in exactly one terminal outcome: `done`, meaning the effect
was performed and the transport acknowledged it, or `failed`, meaning a permanent
reason code was recorded. Both are final for that `(kind, key)`.

Terminal is derived from the row, not stored as a status: `due` is null, `since`
is the time the outcome was recorded, and `error` is null for `done` or carries
the reason code and message for `failed` (VI-15). A retry sweep selects on
`due IS NOT NULL`, so a terminal row is invisible to it without a separate flag.

A terminal row MUST NOT be re-queued by an enqueue, a retry sweep, a restart, or
an operator reset. A later intent for the same domain fact is a new request id
and therefore a new key (EF-03); the old row stays as the audit trail of what
happened. Re-queueing a failed row would erase the reason and repeat an effect
the transport already refused.

`done` MUST be recorded from the performing party's answer -- the transport, for
a message -- never from the caller's assumption, and never before the answer
arrives (MD-06). The reason code comes from a closed vocabulary owned by the
kind and is stored with `error`, so a repeated failure is diagnosable without
the process that first saw it.

## EF-08 -- Delivered, read, and acted-on are three facts

The runtime MUST record three separate observations, each written by the party
that made it:

- handover, when the transport accepted the payload for delivery;
- a read, when the consumer entered a step with that payload;
- an acted-on result, when a report or a turn end followed that step.

The three are not derivable from one another. Transport acceptance says nothing
about whether a model received the text; a consumer starting a step says nothing
about whether it finished one; a finished step that produced no report is not
evidence that a human saw anything. A runtime that reports "handled" from the
handover timestamp alone is claiming the third fact from the first.

These observations are recorded as dated facts beside the effect, keyed by the
same effect identity; they do not add a status column or a new field to the row
(EF-02, VI-15). The message kind keeps them on its receipt (MD-02), and its
status is recomputed from them when asked. A fact that no component observed is
absent, never defaulted to the time of a neighbouring fact.

## EF-09 -- Health has one owner and one threshold

Each kind has exactly one health owner -- the queue's health surface -- and one
threshold per kind, named in configuration as a count of consecutive transient
failures. When the count reaches the threshold, the owner reports exactly one
problem naming the kind, the count, and the last `error`. It MUST NOT emit a new
problem for every subsequent failure, and it MUST NOT clear itself on a timer.

The counter resets on the next success for that kind, and the problem clears in
the same write that records the success. A problem that clears because time
passed hides a dead transport behind a healthy-looking dashboard.

`defer` outcomes do not feed the counter: a deferred row did not fail. `permanent`
outcomes are reported once through the row's reason code and do not feed the
consecutive-failure count either; they are a refusal, not an outage. Health is a
property of the kind, never of a worker process: a restarted worker inherits the
kind's state instead of starting from zero and hiding an ongoing failure.

## EF-10 -- Shutdown and restart prove the guarantee

On shutdown, the runtime MUST leave in-flight rows untouched: no delete, no
`attempts` reset, no marking failed. On start, the queue MUST resume them: a row
whose `due` is still in the future is leased or waiting for its backoff, and it
becomes eligible when `due` passes. A crashed attempt therefore costs at most
one lease interval of delay, and the row's committed intent survives.

Resumption is not replay by hope. The effect is performed again only because the
transport deduplicates by key (EF-03), and a duplicate dispatch in the middle of
a crash is the expected shape of at-least-once execution, not a bug to hide.
Completion then passes the guard (EF-04), so a duplicate that finishes late
cannot settle a newer payload.

The restart path MUST be proven by a test that kills the process in four places
-- before commit, after commit before dispatch, mid-dispatch, and after dispatch
before completion -- then restarts and asserts that every committed effect
reaches exactly one terminal outcome, that a terminal row is never dispatched
again, and that no committed effect was lost. A restart that merely "looks fine"
is not evidence; EF-07 and EF-04 are the assertions the test must exercise.

## Rejected alternatives

| Rejected | Why |
|---|---|
| An in-memory queue between the decision and the dispatch | A crash loses the effect with no trace, and the retry has no row to compare against. The row is the only thing that survives the process |
| At-most-once everywhere | Dropping a committed effect is an unreported failure. Where loss is unacceptable the choice is at-least-once plus a dedupe key, not silent loss |
| Unbounded retry | One poison payload consumes the worker forever and hides the failure. A named cap converts it into a recorded permanent outcome |
| Retrying on the caller's thread | The caller has the shortest lifetime in the system; retries die with the request and block the request path while they wait |
| Claiming exactly-once | A crash between dispatch and the completion write makes exactly-once unprovable. The honest pair is at-least-once execution plus an idempotency key and a guarded completion |
| A bespoke table per effect kind | The shapes drift, the completion guard is written twice, and the two paths disagree only after a crash |

## Cross-refs

- `long-horizon-runs.md` -- LH-12 crash, failure, and idempotency for the run that produces effects
- `verification-integrity.md` -- VI-15 status is derived from stored facts, never carried
- `message-delivery.md` -- MD-01..MD-08 the message kind, its guarantee, classification, and withdraw path
- `work-authorization.md` -- WA-04 the immutable grant a committed decision cites, WA-12 decision records with codes
- `workflow-loop.md` -- WL-04 evidence at every transition, including the effect's outcome
- `../exemplars/durable-effects-reference.md` -- worked row, enqueue, guard, backoff shape, failure matrix
