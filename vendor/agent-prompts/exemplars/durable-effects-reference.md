# Durable effects: worked reference

Status: reference, 2026-11-02. Companion to `../standards/durable-effects.md`
(EF-01..EF-10). This is a design sketch in pseudo-SQL and JSON, not a prompt and
not a library API. Adapt names and types to the store; keep the invariants.

The worked example uses a message effect because a message has a visible
transport with three outcomes: accepted, refused, and unknown. The same row,
guard, and retry ladder apply to launching a worker or any other effect.

## 1. The effect row

One table, nine columns, primary key `(kind, key)`. Only the queue writes it;
producers and handlers call the queue API.

| Column | Type | Meaning |
|---|---|---|
| `kind` | text | Effect class. Selects handler, transport, retry policy, and stream accessor |
| `key` | text | Idempotency key from domain facts (EF-03) |
| `payload` | json | Committed arguments. Immutable while `generation` is unchanged |
| `seq` | integer | Ordering position inside the stream, assigned once and kept across coalesce |
| `generation` | integer | Payload version. Enqueue of a live key increments it |
| `attempts` | integer | Transient failures since the last enqueue or coalesce |
| `error` | text | Last failure as `code: message`; null on a `done` row |
| `due` | timestamp | Earliest eligibility. While an attempt runs, the lease expiry. Null means terminal |
| `since` | timestamp | When the current attempt or terminal state began |

Terminal is derived, never stored (EF-07, VI-15):

- `due IS NULL AND error IS NULL` -> `done`
- `due IS NULL AND error IS NOT NULL` -> `failed` with the recorded reason
- `due IS NOT NULL` -> live

The stream is not a column. A kind declares an accessor that projects its stream
from `key` and `payload`; the example message kind uses
`(payload->>'unit', payload->>'conversation')`.

Illustrative row for a message:

```json
{
  "kind": "message.post",
  "key": "message.post:unit-41:evt-8802",
  "payload": {
    "unit": "unit-41",
    "conversation": "review-thread-7",
    "channel": "review",
    "text": "Started on the parser fix; the failing case is reproduced."
  },
  "seq": 3,
  "generation": 1,
  "attempts": 0,
  "error": null,
  "due": "2026-11-02T10:15:00Z",
  "since": "2026-11-02T10:15:00Z"
}
```

The key is the derived identity, not a hash of the row. The message id the
transport receives is the `key` (MD-02); a transport retry reuses it.

## 2. One enqueue

Enqueue in the same transaction as the decision record (EF-01). The transaction
returns only after the row commits; dispatch is a separate loop over committed
rows.

```json
{
  "op": "enqueue",
  "kind": "message.post",
  "key": "message.post:unit-41:evt-8802",
  "seq": 3,
  "payload": {
    "unit": "unit-41",
    "conversation": "review-thread-7",
    "channel": "review",
    "text": "Started on the parser fix; the failing case is reproduced."
  }
}
```

The queue's upsert keeps `seq` for a live key, bumps `generation`, replaces
`payload`, resets `attempts`, and leaves a running lease alone (EF-04):

```sql
INSERT INTO effect (kind, key, payload, seq, generation, attempts, error, due, since)
VALUES (:kind, :key, :payload, :seq, 1, 0, NULL, now(), now())
ON CONFLICT (kind, key) DO UPDATE
SET payload    = excluded.payload,
    generation = effect.generation + 1,
    attempts   = 0,
    error      = NULL,
    due        = CASE WHEN effect.due > now() THEN effect.due ELSE now() END
WHERE effect.due IS NOT NULL;
```

A zero-row result means the key is terminal; the caller derives a new request id
and a new key instead of resurrecting the old row (EF-07).

`seq` is assigned by the unit's monotonic counter inside the same transaction as
the unit row lock. Two effects of one unit never share a `seq`; two units may,
because their streams are independent (EF-06).

## 3. Completion guard

A handler completion matches the full identity it was claimed with (EF-04):

```sql
UPDATE effect
SET due   = NULL,
    error = :error,     -- NULL for done, 'code: message' for failed
    since = now()
WHERE kind       = :kind
  AND key        = :key
  AND seq        = :seq
  AND generation = :generation
  AND due IS NOT NULL;
```

Rows affected:

- `1` -- the completion applied and the row is terminal.
- `0` -- the completion is stale: the generation was bumped by a coalescing
  enqueue, or another attempt already settled the row. Discard it without error.
  It must not delete or rewrite the newer payload.

A duplicate delivery that reaches the handler twice calls this same statement
twice; the second call affects zero rows and changes nothing.

## 4. Retry classes

Every handler answer maps to exactly one class (EF-05). The kind names the
policy values; the numbers below are an example policy, not a requirement.

| Class | Trigger | Row effect | Counts as failure |
|---|---|---|---|
| `defer` | Not due: quiet hours, a named upstream pause, an ordering wait | `due = now() + defer_delay`; `attempts` and `error` unchanged | No |
| `transient` | Timeout, rate limit, 5xx, connection reset, unclassified error | `attempts += 1`; `error` set; `due = now() + backoff(attempts)` | Yes |
| `permanent` | Closed-set `gone` condition, validation refusal, `payload_too_large` | `due = NULL`; `error` set; terminal | Terminal |

Backoff shape for the example policy: `min(300 s, 5 s * 2^(n-1))` with jitter of
plus or minus 20 percent, where `n` is the attempt number after increment.

| Attempt | Delay before retry |
|---|---|
| 1 | 5 s |
| 2 | 10 s |
| 3 | 20 s |
| 4 | 40 s |
| 5 | 80 s |
| 6 | 160 s |
| 7 | 300 s (cap) |
| 8 | No retry: settles `permanent` with `retry_exhausted` |

The maximum is eight transient failures per payload generation: the eighth
failure settles as `permanent` instead of scheduling a ninth attempt. Coalescing
resets `attempts`, so a new payload gets a fresh ladder; the old ladder is not
inherited.

```sql
-- transient
UPDATE effect
SET attempts = attempts + 1,
    error    = :code || ': ' || :message,
    due      = now() + make_interval(secs => :delay),
    since    = now()
WHERE kind = :kind AND key = :key AND seq = :seq
  AND generation = :generation AND due IS NOT NULL;

-- defer
UPDATE effect
SET due = now() + make_interval(secs => :defer_delay), since = now()
WHERE kind = :kind AND key = :key AND seq = :seq
  AND generation = :generation AND due IS NOT NULL;

-- permanent
UPDATE effect
SET due = NULL, error = :code || ': ' || :message, since = now()
WHERE kind = :kind AND key = :key AND seq = :seq
  AND generation = :generation AND due IS NOT NULL;
```

`defer` must not touch `attempts` or `error`; otherwise a quiet night drives a
healthy row to `retry_exhausted` while nothing was wrong.

## 5. Per-stream ordering

The queue stores no stream column. Each kind declares an accessor; the message
kind's is a view:

```sql
CREATE VIEW message_stream AS
SELECT kind, key, payload, seq, generation, attempts, error, due, since,
       payload ->> 'unit'         AS unit_id,
       payload ->> 'conversation' AS conversation_id
FROM effect
WHERE kind = 'message.post';
```

Claim only the head of each stream, and only when the head is eligible:

```sql
SELECT s.kind, s.key, s.seq, s.generation
FROM message_stream s
WHERE s.due IS NOT NULL
  AND s.due <= now()
  AND NOT EXISTS (
      SELECT 1
      FROM message_stream h
      WHERE h.unit_id         = s.unit_id
        AND h.conversation_id = s.conversation_id
        AND h.seq < s.seq
        AND h.due IS NOT NULL
  )
ORDER BY s.seq;
```

The head blocks its stream while `due` is in the future: a running attempt holds
a lease, a deferred head holds its stream until it is due, and a terminal head
(`due IS NULL`) stops blocking. A stream with no eligible head contributes
nothing, and other streams are unaffected (EF-06).

Claiming moves the lease forward; it does not increment `attempts`:

```sql
UPDATE effect
SET due = now() + interval '60 seconds', since = now()
WHERE kind = :kind AND key = :key AND seq = :seq AND generation = :generation
  AND due IS NOT NULL AND due <= now();
```

A zero-row result means another dispatcher claimed the row first; the caller
moves on without dispatching.

## 6. Failure matrix

Assume the transport deduplicates by `key` (MD-02). The "visible effects" column
states what a human can observe.

| Crash point | State on disk | Restart behavior | Visible effects |
|---|---|---|---|
| Before commit | No decision row, no effect row | The request is retried by its own caller or is lost with its request; the queue has nothing to resume | None |
| After commit, before dispatch | Row present, `due <= now`, `attempts = 0`; transport never called | Claim and dispatch once | One |
| Mid-dispatch (call sent, completion not written) | Row leased (`due` in the future), no terminal outcome; delivery unknown | Lease expires; claim and dispatch the same `key` again | One, because the transport collapses the duplicate; duplicates are possible on a transport without dedupe |
| Double dispatch (two dispatchers, or retry racing a slow ack) | Two calls with the same `key`; one row | First guarded completion applies; the second affects zero rows | One per transport dedupe; the record still shows one terminal row |
| After completion | Terminal row (`due IS NULL`) | Nothing to resume; retry sweep skips it | One |

A restart therefore neither loses a committed effect nor creates a second
terminal row. It may perform the transport call more than once, which is why the
guarantee is at-least-once plus dedupe, never exactly-once (MD-01).

## 7. What this pattern does not prove

- It does not prove the transport deduplicates. That is a property of the
  channel, verified per transport and written into the delivery guarantee
  (MD-01). On a transport without dedupe, the mid-dispatch row is a visible
  duplicate, not an invisible one.
- It does not prove the handler performs exactly one side effect. A handler that
  sends two requests, or mutates local state before the guard, breaks the
  guarantee outside the queue's reach.
- It does not prove the key is correct for the domain. EF-03 states the
  derivation; only a domain review can show that a reworded intent keeps its
  key and a genuinely new intent does not collide with it.
- It does not provide global ordering. Ordering holds inside one stream of one
  queue; two queues or two streams interleave freely.
- It does not bound latency. Capped backoff can wait longer than a caller is
  willing to; the queue's job is durability, not responsiveness.
- It does not prove authorization. Who may cause the effect is
  `../standards/work-authorization.md` (WA-04); what a message may say is
  `../standards/agent-notification.md` (NT-04).
- It does not prove the restart test exists. EF-10 requires one that kills the
  process at each row of the failure matrix; this document describes what that
  test must assert, not that any repository runs it.
