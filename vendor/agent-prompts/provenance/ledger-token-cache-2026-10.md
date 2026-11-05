# Token/cache layer ledger (2026-10-25)

Unit: `token-cache`. Rules: WL-08 (ledger), AS-09..AS-12.

| unit_id | phase | attempt | gate | status | artifact | findings | evidence | decision | owner | timestamp | next |
|---|---|---|---|---|---|---|---|---|---|---|---|
| token-cache | Verify | 1 | pass | Ready | 9ab0be2 | none (M: static checks cover only prefix shape; runtime hit rate is harness telemetry) | make gate exit 0; pytest 257 exit 0; check_token_efficiency exit 0; 2026-10-25; repo; deepseek-v4.1-flash | pass | library maintainer | 2026-10-25 | Push |

## Notes

- The static checker proves prefix shape, not cache hits; the runtime schema
  `/2` carries the read/write split and prefix hash.
- The artifact is the code commit whose tree passed the gate; the ledger-pin
  commit changes only this file.
