<hard_rules>
- Work only in wmkeyboard; AGENTS.md governs (project > framework > memory).
  Mutation policy: only .github/workflows/** and scripts/** and the files the
  brief names, one change per gate; re-scope past ~3 files or ~50 net lines.
- Safety rule: never echo secrets, tokens or credentials; never commit, push or
  deploy. A secret never enters argv, a commit or a log.
- Change CI only through committed workflows, scripts and schemas; never weaken,
  skip or silence a gate.
- Keep the F-Droid assembly and the offline build green: a workflow change that
  needs a Google SDK on the compile classpath is a channel change, not a CI fix.
- Every side effect ends in a terminal recorded outcome, done or failed with a
  reason code, never re-queued (EF-07); health has one owner and one threshold,
  cleared by the next success (EF-09).
</hard_rules>
