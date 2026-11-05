# HALT taxonomy (failure / halt)

Generalized from containeromat `.kilo/rules/12-halt-taxonomy.md` (pinned 2026-09-19).
Upstream: containeromat R-016.

When a trigger fires: **HALT**, state the rule ID, request operator input.
Never emit a partial artifact.

**Interacts with the process limits (STOPP):** S-1 one idea per step | S-2 <=3
files | S-3 ~50-line diff | S-4 no speculative fixes | S-5 wait for explicit
`go`. The universal limits apply alongside the halt triggers; an approval is
never implicit. The measured fast path for one-file comment/format/typo edits
is in `stop-gate.md` (SG-01..SG-09); it still verifies and still honors HALT.

## Generic halt triggers

| ID | Condition | Action |
|----|-----------|--------|
| HF-01 | Material gap in the task specification (required inputs, identifiers, auth, domain, storage, artifact class) | HALT. Ask the operator. |
| HF-02 | New artifact: live research unavailable OR fewer than two mandatory sources (docs + registry/source) | HALT. No emit. |
| HF-04 | A verification pass returns FAIL | In-scope and safe: Fix -> Review -> Verify. Unsafe, out of scope, or proof unavailable: HALT. |
| HF-05 | ASCII validation fails on an emitted or edited file | HALT. Fix the characters, re-validate. |
| HF-06 | Unresolved placeholders or an empty required dependency block in the final artifact | HALT. Fix before emit. |
| HF-09 | A version pin or external reference lacks live proof recorded as a source comment | HALT. Run the live query, add the source comment. |
| HF-13 | The operator explicitly declines the Push/approval gate | HALT. Record the declined approval; no answer is hold/Ready, not HALT. |
| HF-14 | The one-refinement bound is exhausted at a gate | HALT. Record the gate, both attempts, and the unresolved decision. |
| HF-15 | The request is unsafe, destructive, or outside the authorized scope | HALT. State the unsafe element and the safe alternative, if one exists. |

## When NOT to HALT

- Editing an artifact that carries a registered exception -- follow the
  registry, do not "fix" to defaults.
- A skipped research step when the operator supplied all upstream facts -- log
  the skip in the setup notes.
- Structural/documentation questions about rules only -- no artifact emit
  needed.

## Response format on HALT

```
HALT -- {HF-ID}: {one-line reason}
Need from operator: {specific question}
```

Never claim PASS or "done" while HALT is active.

## Appendix A -- containeromat-specific HALT rows (compose domain)

These rows apply only in the origin project (containeromat). They are recorded
here as provenance for the extension pattern; do not port them into another
project unless its domain matches.

| ID | Condition | Action |
|----|-----------|--------|
| HF-03 | Upstream requires a PUID/PGID-only user model | HALT. Operator picks the documented option A or B. |
| HF-07 | A capability grant or a healthcheck without a source citation | HALT. |
| HF-08 | `cap_drop: [ALL]` on a service that uses gosu/su-exec without the mandatory capability audit | HALT. Run the audit, add the required capabilities. |
| HF-10 | A top-level key out of relative canonical order | HALT. Report the offending key + expected position. |
| HF-11 | A service-level key out of relative canonical order | HALT. Report service name, key, expected context. |
| HF-12 | An obsolete `version:` key present in a compose file | HALT. Remove it. |

Containeromat also applies the generic rows to compose artifacts: HF-01 checks
the stack brief (image, slug, auth, domain, storage, class), HF-02 requires the
two mandatory source URLs per image, HF-04 is the audit-pass gate, HF-05 covers
compose/`.env` ASCII, HF-06 covers template markers and empty `depends_on`, and
HF-09 requires registry proof for every image tag.

## Cross-refs

- `evidence-duty.md` -- live research (HF-02, HF-09 roots)
- `agent-prompt-standard.md` -- prompt hygiene (HF-05, HF-06 roots)
- `code-review-contract.md` -- review severity; HALT outranks review output
