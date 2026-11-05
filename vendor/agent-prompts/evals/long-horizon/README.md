# Long-horizon run exercise (WP-09)

A local, two-session exercise of the run layer in
`standards/long-horizon-runs.md` and its two contracts:
`standards/run-state.schema.json` and `standards/run-journal.schema.json`.

This is not a benchmark and not a deployed run. It answers a narrower question:
does the checked-in state machine and journal actually hold together across a
session boundary, and does the tooling detect the failures the standard says it
must? The answer is yes for the local files, and nothing here is evidence about
a live harness. See `docs/knowledge-base/long-horizon-agents-2026-10.md`
section 6.1 for the result and the block.

## Run it

```bash
python3 evals/long-horizon/drive.py            # session A, session B, probes
python3 evals/long-horizon/drive.py --verify   # revalidate the committed artifacts
```

`drive.py` starts session A and session B as two separate OS processes that
share nothing but the files in this directory. Session A never tells session B
anything: session B reads `run-state.md` and `events.jsonl` and derives its clock
from the journal's first event.

## Rerunning replaces the committed artifacts

A default run (`python3 evals/long-horizon/drive.py`) **is destructive to this
directory**: it deletes and rewrites `run-state.md`, `events.jsonl`,
`session-a.txt`, `session-b.txt`, `session-b-replay.txt`, `work/` and `probes/`.
The new files carry the local process ids, the local timestamps, the current
`branch` value and the current HEAD's contract hashes. Run it only when you mean
to replace the committed exercise; if you want a throwaway run, copy this
directory to a scratch path outside the repository first.

`--verify` is the read-only path and the one the gate uses. It revalidates the
committed view and journal, replays the journal, and re-runs both probes; it
rewrites `probes/report.txt` only when the probe bytes change, and every path in
that report is repository-relative, so a rerun in a different checkout leaves
the tree clean.

## Layout

| Path | What it is |
|---|---|
| `drive.py` | The driver: both sessions, the replay comparison, and the two probes |
| `run-state.md` | The committed state view at checkpoint 5 (`status: done`) |
| `events.jsonl` | The append-only journal, 14 events, `start` .. `done` |
| `session-a.txt` | Session A transcript (process, units, gates, checkpoints) |
| `session-b.txt` | Session B transcript (replay first, then units U2 and U3) |
| `session-b-replay.txt` | The replay-to-view comparison written before session B works |
| `work/` | The unit artifacts; each is derived from a checked-in contract |
| `probes/tampered-state.md` | The same view with one evidence cell hand-edited |
| `probes/dangling-action.jsonl` | A journal with an `action_started` that has no receipt |
| `probes/report.txt` | Both probe results; rewritten only when the probe bytes change, with repository-relative paths |

## What ran

2026-10-27, 12:19-12:21 UTC, on the live library checkout, with no model call, no
network access, and no container.

| Unit | Work | Gate |
|---|---|---|
| U1 | `work/frontmatter-keys.txt`, the required frontmatter keys read from the schema | Recompute from the schema and compare bytes |
| U2 | `work/journal-kinds.txt`, the canonical event kinds read from the journal schema | Recompute and compare bytes |
| U3 | `work/sections.txt`, the required body sections read from the run-state schema | Recompute and compare bytes |

Progress is a verified artifact, not elapsed time. Every checkpoint writes the
view, validates it with `tooling/run_state.py`, and only then appends the
`checkpoint` event with the SHA-256 of the bytes it wrote. Session A ends at
checkpoint 2 (1/3), so session B has to resume rather than continue.

Validator output from the committed artifacts:

```text
$ python3 tooling/run_state.py check evals/long-horizon/run-state.md
run-state: OK lh-contract-exercise (3 units, 5 checkpoints)

$ python3 tooling/check_run_journal.py evals/long-horizon/events.jsonl \
    --state evals/long-horizon/run-state.md
run-journal: 14 events, 0 violation(s)
```

Session B, before doing any work, replayed the journal and compared it with the
view:

```text
replay: 5 events, 2 checkpoints
replay: committed U1 at Verify (gate pass)
replay: next_action = Resume in a new session and execute U2
view:   checkpoint 2, units_done 1/3
view:   next_action = Resume in a new session and execute U2
hash:   view 9915aee07e6b..., last checkpoint seq 5 records 9915aee07e6b...
AGREE
```

## What this proves

- The checkpoint protocol is executable as written: five checkpoints, each a
  validated view plus a hash-pinned journal event, in the documented order.
- A cold process rebuilds the committed units, the checkpoint count and the
  `next_action` from `events.jsonl` alone, and reaches the same conclusion as the
  hand-written view (`AGREE`). The view is a view; the journal is the history.
- Journal state and view state can be compared mechanically. Probe 1 edits one
  acceptance evidence cell: `run_state.py check` still exits 0 because the view
  is internally consistent, while `check_run_journal.py --state` exits 1 with
  `stale view`. Before this change nothing reported that.
- A side effect with no receipt is visible before replay. Probe 2 ends a valid
  journal with a `WARN action_id a-02 started at seq 3 has no receipt`.
- The `--state` comparison is now a gate: `tooling/check_long_horizon.py`
  validates this state, this journal and their hash agreement on every
  `make gate`, and fails if any of the three drift.

## What it does not prove

- **No deployed harness.** dsh and zcode are inactive and will not be deployed
  in this cycle (`dsh` regains usage in November; `zcode` has no date), so this
  is a deferral, not a blocked operator action. Neither is deployed on this
  host: no container by those names exists (`docker ps -a` is empty for `dsh`,
  `zcode`, `deepseek-harness` and `goose-harness`), and the Docker endpoint is a
  read-only socket proxy (`paseo-ds-proxy`, `CONTAINERS=1`, `POST=0`, `EXEC=0`,
  `BUILD=0`), so no harness can be started from here. Starting or restarting a
  production container is also outside this work package. The live run and the
  LH-13 A/B are **deferred to November**, not done, and no live metric is
  claimed.
- **No LH-13 metrics.** Units per hour, tokens per verified unit, checkpoint
  recovery time, stall count, drift events and escaped defects are not measured.
  There is no model in the loop, so the `budget` numbers in the view are declared
  constants, not telemetry.
- **No recovery time.** Both sessions ran back to back on one machine. Nothing
  crashed, nothing was compacted, and no restart was induced.
- **No concurrency.** One writer, one machine, no contention. Nothing here says
  two sessions writing one state file are safe.
- **No real interruption.** Probe 2 fabricates the shape of an interrupted side
  effect; it does not produce one.
- **No task difficulty.** The units derive a list from a JSON contract on
  purpose. The exercise tests the state machine and the journal, not endurance,
  planning quality or model reliability.
- **No proof of existence or timing.** The validator reads files. It cannot prove
  that an agent wrote the state before compaction, that an idempotency key was
  honoured, or that two checkpoints are not the same work counted twice.

## Runtime decision: recorded fields stay recorded

The exercise answers the WP-09 question with evidence rather than preference.

`lease`, `## In-flight` and idempotency stay **recorded fields with mechanical
checks at the file layer**, not runtime services:

- The run is single-writer and file-based. The validator already rejects a
  `status: done` run with a side effect left `planned`, an expired `lease`, a
  non-canonical in-flight state, and a duplicate `action_id` in the journal.
  Those are the failures a local run can actually produce.
- Exclusivity, key honesty and checkpoint timing need an owner the library does
  not have: a supervisor, a lock, or a durable queue. The only place that owner
  could live today is the deployed harness, and that harness is blocked. Adding a
  service would be an unowned dependency, not a stronger contract.
- One enforcement gap was closable without a service: nothing compared the view
  with the journal it claims to materialize. `check_run_journal.py --state` now
  does, and `check_long_horizon.py` gates on it. That is detection, not locking,
  which is exactly the layer this library can own.

Two contract findings are recorded rather than fixed, because both would be
schema migrations:

- `F1` (low): the journal has no `resume` kind. A resume is a `note` plus the
  replay, as in `events.jsonl` seq 6.
- `F2` (low): a `checkpoint` event has no `next_action` field, although LH-14
  says replay rebuilds it. The convention used here is that the checkpoint
  `result` ends with `; next <action>`, and `--verify` fails if the rebuilt value
  disagrees with the view.

No phase was added to the loop by the long-horizon layer and no runtime service
was introduced.
