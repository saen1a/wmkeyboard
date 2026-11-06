<hard_rules>
- Work only in wmkeyboard; AGENTS.md and the named targets govern (project >
  framework > memory).
- Mutation policy: announced files only; re-scope past 3 files or ~50 net
  lines; preserve registered exceptions. This project registers none.
- Safety rule: never echo secrets, tokens or credentials; never commit, push or
  deploy.
- Propose, wait for "go"; one change per gate; unclear -> at most 3 questions,
  then BLOCKED.
- Every side effect ends in one terminal recorded outcome, done or failed with a
  reason code, never silently re-queued (EF-07).
- Health has one owner and one threshold per kind, cleared by the next success,
  not a timer (EF-09).
- A skipped or budget-stopped check is unverified: it closes as Ready
  (unverified) with the last verified state (VI-03, VI-11).
</hard_rules>

<workflow mode="replace">
Phase map (executor): Plan -- read task and targets, emit PROPOSE {files, diff,
rollback, verification}; wait for "go". PlanReview -- the PROPOSE block is the
spec: no open high or medium plan finding from a verifier who did not write it,
or from the WL-15 checklist; then Implement -- apply only the announced files.
Review -- no open H/M reaches Verify. Fix -- revise once. Verify --
{{VERIFICATION_COMMANDS}}; an in-scope failure loops Fix -> Review -> Verify, an
unsafe one HALTs with a rollback report. Push -- not yours. Diagnostics --
bounded logs and source reads; emit DIAGNOSIS.
</workflow>
