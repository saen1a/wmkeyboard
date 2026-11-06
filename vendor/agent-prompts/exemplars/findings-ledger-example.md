# Findings ledger: example

One row per finding. Do not delete a finding; change its state and append the
resolution evidence. Review passes only when no high or medium finding is
`open`.

| finding_id | severity | unit | file_line | evidence | acceptance_impact | owner | state | round | decision |
|---|---|---|---|---|---|---|---|---|---|
| F-1 | high | U1 | `docs/handbook/index.md:12` | Review R1: stale link; re-review R2 confirms the link resolves | A1 | rev-reviewer | fixed | 2 | fixed with evidence |
| F-2 | medium | U2 | `docs/handbook/procedures/recovery.md:8` | Review R2: old screen name; no re-review yet | A3 | rev-reviewer | open | 2 | pending |
| F-3 | low | U3 | `docs/handbook/procedures/recovery.md:22` | Review R2: wording only | none | rev-reviewer | waived | 2 | operator waived; cosmetic |
