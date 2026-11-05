# External scan ledger (2026-10-25)

Unit: `external-scan`. Rules: WL-08 (ledger), WL-13 (findings), WL-14
(publication proof).

| unit_id | phase | attempt | gate | status | artifact | findings | evidence | decision | owner | timestamp | next |
|---|---|---|---|---|---|---|---|---|---|---|---|
| external-scan | Verify | 1 | pass | Ready | 078e0ac | findings-external-scan-2026-10.md (20 fixed; publication proof pending) | make gate exit 0; pytest 312 exit 0; check_findings_ledger exit 0; check_run_journal exit 0; 2026-10-25; repo; deepseek-v4.1-flash | pass | library maintainer | 2026-10-25 | Push |

## Notes

- Adopted from stepbook: the append-only journal and replay.
- Adopted from RunWield: stable finding ids and publication proof.
- Rejected JulianFlux: the benchmark labels and detector share the same
  synthetic signal; see `docs/knowledge-base/external-project-scan-2026-10.md`.
- The gate ran on the working tree. The artifact field is pinned by the
  follow-up ledger commit after Push, and the artifact commit is the code
  commit whose tree passed the gate.
- `Ready`, not `Done`: the branch is not yet landed. WL-14 applies to this
  unit.
