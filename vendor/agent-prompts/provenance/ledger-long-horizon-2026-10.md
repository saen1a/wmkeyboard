# Long-horizon layer ledger (2026-10-25)

Unit: `long-horizon`. Rules: WL-08 (ledger), LH-01..LH-13.

| unit_id | phase | attempt | gate | status | artifact | findings | evidence | decision | owner | timestamp | next |
|---|---|---|---|---|---|---|---|---|---|---|---|
| long-horizon | Verify | 1 | pass | Ready | 3bb64a1 | none (LH-01..LH-13 packet: schema, tool, skill, evidence register, docs; audit rounds fixed) | make gate exit 0; pytest 229 exit 0; check_long_horizon exit 0; 2026-10-25; repo; deepseek-v4.1-flash | pass | library maintainer | 2026-10-25 | Push |

## Notes

- The artifact is the code commit whose tree passed the gate; the follow-up
  ledger-pin commit changes only this file. The PR records the final hash.
- This ledger is run evidence, not a template. It carries the same WL-08 shape
  as `ledger-workflow-loop-2026-10.md`.
