# Loop guard exercise

`drive.py` runs the workflow-loop guards against verdict records. It is the
executable half of `standards/workflow-loop.md` (WL-02, WL-07, WL-10, WL-14) and
`standards/verification-integrity.md` (VI-01..VI-15).

```bash
python3 evals/loop/drive.py            # every scenario with its detail line
python3 evals/loop/drive.py --verify   # gate mode: only failures are printed
python3 evals/loop/drive.py --json     # machine-readable summary
```

`make gate` runs `--verify`. No network, no writes, ASCII only.

## What it covers

| Transition | Guard | Scenarios |
|---|---|---|
| Plan -> PlanReview | decision-complete spec carries goal, units, acceptance, verification | `plan_complete_spec`, `plan_missing_acceptance` |
| PlanReview -> Implement | a `plan-review` record with no open or waived high/medium finding; a diff record is not a plan record | `plan_review_clean`, `plan_review_without_record`, `plan_review_rejects_a_diff_record`, `plan_review_open_high_finding` |
| PlanReview -> Fix -> PlanReview | each round states a new `CHANGED` line; a repeat is `stalled` | `plan_review_round_states_a_change`, `plan_review_round_repeats_a_change`, `plan_review_round_without_a_change_line` |
| Review -> Verify | valid record, no open or waived high/medium finding | `review_clean_record`, `review_without_record`, `review_open_high_finding` |
| Verify -> Ready | valid record, no skipped check, no stub artifact, verifier not the author, coverage at or above the floor, attempt 0 or 1 | `verify_pass_complete`; the record-level rejections live in `tooling/tests/test_check_gate_verdict.py` |
| Verify -> Fix | failure with a named cause | `verify_failure_enters_fix` |
| Fix -> Plan | one spec-gap return per unit, then HALT | `fix_first_spec_gap_return`, `fix_second_spec_gap_return` |
| Fix -> PlanReview | a plan finding answered with a spec patch and a `CHANGED` line (same round guard as above) | covered by the PlanReview round scenarios |
| Ready -> Push | operator `go`, the record attached, publication proof for a Git finalize | `push_*` (four cases) |

## Why a scenario list instead of a checker

The loop is a state machine over artifacts, not over source text. A text checker
can confirm that a transition row exists; it cannot show that the guard rejects a
realistic bad record. Each scenario builds a record from
`exemplars/gate-verdict-example.json` and mutates exactly one property, so a
guard that stops reading that property fails here instead of in production.

## What this does not prove

- It does not prove an agent follows the loop, only that the written guards are
  consistent with the record contract and with each other.
- The attempt bound is not a parameter of the exercise: WL-07 fixes one
  refinement at the code gates and no round cap at the plan-review gate, and
  `tooling/tests/test_check_gate_verdict.py` enforces which gate may carry
  which `attempt` value.
- Publication proof is a boolean here. `WL-14` defines what the proof is; this
  exercise only shows the finalize refuses without one.
