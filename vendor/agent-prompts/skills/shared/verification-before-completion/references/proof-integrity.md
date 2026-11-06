# Proof integrity: making a verdict hard to fake

Depth for `verification-before-completion`. The skill says run the command and
read the output. This appendix covers the cases where the command ran, the output
looked fine, and the verdict is still wrong. Normative rules:
`standards/verification-integrity.md` (VI-01..VI-15). Validator:
`python3 tooling/check_gate_verdict.py verdict.json`.

## Contents

1. Skipped is not passed
2. Criteria come from the request, split MUST and SHOULD
3. Shape-check the artifact
4. Two contradictions that mean the verdict is fabricated
5. Coverage and severity
6. Identity and provenance of the verdict
7. Repair rounds and exhaustion
8. What a good verdict record looks like
9. Status, and what you may say about it

## 1. Skipped is not passed

Before any claim, classify each check:

| State | Meaning | Verdict effect |
|---|---|---|
| ran, exit 0 | executed in this attempt, output read | supports `pass` |
| ran, exit non-zero | executed and failed | `fix` |
| skipped | nothing was configured, or the check could not run | `hold`; criteria stay unverified |
| budget | stopped by a budget or timeout | `halt`, never retried |

"Nothing configured" is the trap: no test script, no build script, no linter
config, no acceptance criteria. That is a fact about the repository, not proof of
correctness. Record `skipped` with the reason and close the gate as `hold`. A
verdict with zero checks is `hold`, not `pass`.

## 2. Criteria come from the request, split MUST and SHOULD

Write the table before implementing, from the request and the approved spec:

```text
A1 MUST  the recovery page names the new screen and links resolve
A2 MUST  the index links to the recovery page
A3 SHOULD the old screen name stays as a search alias
```

Only MUST blocks. A SHOULD failure is recorded as advisory and may still pass -
but it is never deleted, and it is never silently promoted to MUST either. A
unit with no criterion is `skipped`.

## 3. Shape-check the artifact

An artifact is substance, not narration. Reject before hash-and-claim:

- **Narration**: "here is the updated file", "done", "no changes needed", "task
  complete", or a description of what the file would contain.
- **Stub**: fewer than 200 non-whitespace characters, or the right extension with
  no kind signal.

Kind signals that must appear in the first lines of a real artifact:

| Kind | Signal |
|---|---|
| html | a tag such as `<html`, `<div`, `<section`, `<!doctype` |
| css | `{`, `}`, `@media`, `@import`, a custom property |
| js / ts | a code line: `import`, `export`, `const`, `let`, `function`, `class`, `interface`, `type` |
| json | starts with `{` or `[` and parses |
| markdown | a heading, list, quote, or fence; or more than 200 characters of prose |
| python / shell / sql / yaml | a language keyword line, not a sentence about the code |

A stub flips the unit's evidence to failed. The repair is new content, not a
re-run of the same check.

## 4. Two contradictions that mean the verdict is fabricated

- a "clean" or "no findings" claim with zero captures: nothing was inspected;
- a claimed count (files changed, findings, tests) with zero captures behind it.

Both are `halt`, not `fix`. A capture is a command with exit code and output
digest, or an artifact record. "I will check later" is not a capture.

## 5. Coverage and severity

- Declare the surface, measure it, and record a floor. Default floor for a
  delivery gate: 95 percent. A green subset below the floor is not a pass.
- A clean partial result is reported as partial, with the gap named in the same
  message: "no findings in the covered surface; the vendor scanner was not run".
- Severity is not a dial: a high or medium finding stays high or medium, and a
  pattern-only signal is capped at medium with the cap recorded. Lowering a
  severity to clear a gate is an operator decision with a rationale.

## 6. Identity and provenance of the verdict

A `pass` names its verifier, and the verifier is not the author.

- Empty or anonymous verdict: fabricated attestation.
- Verifier identity equals the implementer: verification theatre.
- The author alone, with no second context and no mechanical check: record the
  WL-05 exemption and close as `Ready (unverified)`. Never as `pass`.
- A verdict record carries the gate, the attempt, and the mode
  (`block`/`warn`/`off`). `off` means the gate did not run: `hold`.

## 7. Repair rounds and exhaustion

The repair message before re-entering the gate:

```text
PRIOR ATTEMPT 1 FAILED: A1 - anchor /recovery-old does not resolve
CHANGED: replaced the anchor with /recovery-v2, no other edit
```

A repeat of the same change is not a new attempt. Observe the refinement bound
(WL-07) and the per-gate cycle budget (VI-13): the verify budget never exceeds
the implement budget. On exhaustion, restore the last verified state, report it
as the current state, and close `halt` with a taxonomy reason. Never ship the
last failing attempt as the result, and never let a passing check on other
criteria "resolve" an exhausted one.

## 8. What a good verdict record looks like

See `exemplars/gate-verdict-example.json`: verifier differs from implementer,
each check has command, exit, freshness and an output digest, MUST criteria are
met, the SHOULD row is honestly unmet, coverage is measured with its basis, and
every claim in the report points at a field. Then run the validator; a verdict
that cannot pass its own validator cannot support a completion claim.

## 9. Status, and what you may say about it

A status is derived from facts, never stored and never narrated (VI-15). Before
you state one, name the facts and the table row:

| Row | Facts that select it | What it entitles you to say |
|---|---|---|
| waiting on a person | a structured question is open, or a result awaits review | "ready for review", with the link |
| waiting on a trigger | the turn ended with nothing outstanding | nothing unsolicited |
| working | an assignment is running, or background work is unsettled | nothing unsolicited |
| ended | the result is merged, closed or dropped | one terminal sentence |

Two consequences decide the wording. First, a status label alone is not a
message: "blocked" without a concrete question is not an attention request
(`standards/agent-notification.md` NT-02, NT-05). Second, an ended status is the
only one that authorizes a completion sentence (NT-08): a draft is reported as a
draft, and a merge notice never claims a defect is fixed. If the facts do not
select a row, you have no status to report, and the correct output is silence
with the missing fact named in your own record.
