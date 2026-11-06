# Plan spec: the shape the plan-review gate reads

WL-15 (`standards/workflow-loop.md`) makes a plan review mandatory before
Implement. A review that reads prose is a reading, not a gate, so the spec has a
machine-checked shape and two commands:

| Command | What it refuses |
|---|---|
| `python3 tooling/check_plan_spec.py PLAN.md` | a spec that fails one of the six WL-15 checks |
| `python3 tooling/check_loop_gate.py --ledger 'provenance/ledger-*.md' --verdict 'provenance/verdict-*.json'` | an implementation unit with no clean `plan-review` record, a round sequence that is not contiguous from 0, a finalize (Push, Ready, Done) with no verify pass, a spec edited after its review, an unparseable date, an illegal ledger `next` |

Both are `make gate` steps here, and both are consumer-runnable: no network, no
writes, exit 1 with the reason.

## The spec shape

Copy `exemplars/plan-spec-example.md`; the headings are the contract.

| Section | Read as |
|---|---|
| `## Goal` | one decidable sentence, no question mark, at least 40 characters |
| `## Scope boundaries` | at least one bullet stating what the unit will not touch |
| `## Request coverage` | a table mapping each request item to a unit id that `## Units` defines |
| `## Units` | `Unit | Acceptance | Verification | Owner`; every row carries `MUST` or `SHOULD` |
| `## Ownership and order` | a numbered order that names every unit exactly once, plus the writer |
| `## Risks and halts` | a table whose rows name the `HALT` path and the operator question, or a reasoned `None` |

A `Verification` cell must name a check that exists today: a known runner
(`python3`, `pytest`, `bash`, `make`, ...) or a file inside `--root`, and every
path the cell names must be a real file there. That is WL-15's rule, not a
convenience: a plan whose check does not exist yet has no check. Take the plan
back to Fix, or name the runner that exists (`bash tooling/gate.sh`).

## The gate record

A spec that passes the six checks is evidence, not the gate. The gate is the
`plan-review` verdict record (`exemplars/gate-verdict-plan-review.json`):

```bash
python3 tooling/check_gate_verdict.py provenance/verdict-plan-review-<unit>.json
```

It carries the six checks as criteria, a verifier that did not write the spec (or
the mechanical WL-15 path with provenance), coverage of every spec section, and
the findings. When the review finds something, the repair is a new round:

```text
PRIOR ROUND <n> FAILED: <check>
CHANGED: <what the spec now says>
```

Rounds are numbered from 0 and must be contiguous; the last round is the one the
loop gate reads. A round that states no new change is `halt` with reason
`stalled` (WL-07, WL-15).

## Wiring it into a consumer

1. Copy `tooling/check_plan_spec.py` and `tooling/check_loop_gate.py` (or vendor
   the library subtree) and run them where the change is committed.
2. Write one spec per unit, into `provenance/plan-<unit>.md` or wherever the
   consumer keeps plans; the checker takes any path.
3. Keep the plan-review verdict and one WL-08 ledger row per unit next to it.
   The row's `artifact` cell must name the reviewed spec: the gate binds a
   verdict to the artifact it reviewed and recomputes the hash, so a spec
   edited after a clean round needs another round.
4. Dates are real: `--since` and every row `timestamp` parse as ISO. A ledger
   whose newest row predates `--since` is history and is read for shape only; a
   mixed ledger is live and is checked row by row. A unit that predates the
   gate is grandfathered by name, never by a token inside the record:

   ```bash
   python3 tooling/check_loop_gate.py ... --grandfather <unit-id>
   ```

   A grandfathered unit stays unverified and can never close as `Done`.

   A consumer keeps its specs outside this library, so it points the gate at its
   own tree: `--root .` resolves the reviewed spec path and defaults the
   `provenance/` globs to the consumer's own directory.
5. Declare the enforcement honestly in the runtime's admission record:
   `standards/agent-adapter.md` AD-12, `loop_gate` = `supported` only with a
   pre-dispatch check, else `degraded` plus these commands as the CI carrier.
