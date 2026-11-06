> Paths in this record use the pre-2.0 `roles/` / `tasks/` names; current paths are `agents/` / `prompts/tasks/`.

# Role-body A/B (2026-10)

Status: first role piloted and applied; the remaining over-target roles are not
trimmed yet.

## Why

The AP-01 token WARN is advisory, but trimming a role without evidence can delete
a requirement. This A/B tests a trimmed candidate against the current body on the
same task, model, and seeds.

## Method

- Current body: `roles/**/<role>.md`.
- Candidate: `evals/role-ab/candidates/<role>.md`, same frontmatter and
  byte-exact fragments; only role, hard rules, workflow, and output prose change.
- Task: `evals/role-ab/tasks/<role>.json` with a synthetic workspace and explicit
  verification.
- Arms: current vs candidate, 3 seeds, same executor/grader.
- Slots are filled with fixture values before the run; an unfilled template is
  not a fair prompt.

## Pilot: eng-frontend-developer

| Arm | Mean score | Passed | Executor tokens | Body tokens |
|---|---:|---:|---:|---:|
| Current | 0.889 | 2/3 | 14,596 | 1,116 |
| Candidate | **1.000** | **3/3** | 14,279 | **963** |

The candidate keeps the two-file boundary, `TableSkeleton`/token reuse,
accessibility verification, and rollback. It shaved 153 body tokens and closed
one AP-01 WARN. Applied to
`roles/engineering/eng-frontend-developer.md`.

The first candidate lost the two-file boundary and primitive reuse; the A/B
caught it. The final version names both explicitly. This is why the tool exists.

## Remaining WARNs

14 warnings remain (13 roles + 2 tasks; frontend is now clean). Do not trim them
without the same test. The next candidates, in order of overage, are:

1. `review-lead` (+364)
2. `ops-executor` (+224)
3. `reviewer` (+166)
4. `network-architect` (+124)
5. `orchestrator` (+52)
6. `api-developer` (+89), `database-developer` (+86), `backend-developer` (+60),
   `ci-implementer` (+51), `test-author` (+46), `code-skeptic` (+25),
   `format-normalizer` (+12)
7. `tasks/new-component` (+8), `tasks/harden-deployment` (+14)

The small ones may be trimmed with a short task fixture; the four big ones need
real role tasks.

## Limits

- One role, one task, 3 seeds; not enough to generalize.
- Executor needs `--max-tokens 4096` for reasoning output; the default 2048 can
  return empty content.
- The task is synthetic and read-only.

Harness: `tooling/run_role_ab.py`. Raw results:
`evals/results/role-ab-*/` (gitignored).

## Additional pilots (3 seeds each)

| Role | Current | Candidate | Body old -> new | Tokens current / candidate | Decision |
|---|---:|---:|---:|---:|---|
| `eng-frontend-developer` | 0.889 | 1.000 | 1,116 -> 963 | 14,596 / 14,279 | applied |
| `orch-orchestrator` | 1.000 | 1.000 | 1,152 -> 1,093 | 25,847 / 25,877 | applied |
| `net-network-architect` | 1.000 | 1.000 | 1,124 -> 998 | 25,922 / 23,540 | applied |

AP-01 WARN count: 15 -> 12.

`orch-orchestrator` and `net-network-architect` needed `--max-tokens 8192`;
4096 truncated the reasoning output. Result files are now written per role
(`<role>.role-ab-<seed>.json`) so a second role does not overwrite the first.

## Big-role pass (3 seeds)

| Role | Current | Candidate | Body old -> new | Decision |
|---|---:|---:|---:|---|
| `rev-reviewer` | 1.000 | 1.000 | 1,116 -> 867 | applied |
| `ops-executor` | 0.889 | 1.000 | 1,174 -> 930 | applied |
| `rev-review-lead` | 0.779 | 0.889 | 1,464 -> 1,041 | applied |

AP-01 WARN count: 12 -> 9.

The review-lead fixture still has one expectation both arms miss
("states the high-confidence merge filter and the no-edit rule"), so that row is
a lower bound, not a clean pass. The candidate is still non-inferior to current.

Remaining warnings (9): `api-developer`, `database-developer`, `backend-developer`,
`ci-implementer`, `test-author`, `code-skeptic`, `format-normalizer`, and the two
task templates.

## Small-role sweep (3 seeds)

| Role | Current | Candidate | Body old -> new | Decision |
|---|---:|---:|---:|---|
| `eng-database-developer` | 1.000 | 1.000 | 1,086 -> 995 | applied |
| `rev-code-skeptic` | 1.000 | 1.000 | 1,025 -> 991 | applied |
| `eng-backend-developer` | 0.554 | 0.667 | 1,060 -> 998 | applied |
| `eng-api-developer` | 0.889 | 0.779 | 1,089 -> 980 | not applied |
| `eng-test-author` | 0.780 | 0.668 | 1,046 -> 988 | not applied |
| `ops-ci-implementer` | 0.890 | 0.779 | 1,051 -> 947 | not applied |
| `ops-format-normalizer` | 0.332 | 0.332 | 1,012 -> 983 | not applied |

AP-01 WARN count: 9 -> 4. Tasks `new-component` and `harden-deployment` were
trimmed directly (not behavior roles).

The four unapplied candidates are smaller but scored lower on the current
fixtures; the failures are expectation-level (for example "names contract tests
and exit codes"), so they need better fixtures before a decision, not a forced
apply. They remain warnings, not silent drops.

## Final warning sweep (3 seeds)

| Role | Current | Candidate | Body | Decision |
|---|---:|---:|---:|---|
| `eng-api-developer` | 1.000 | 1.000 | 1,089 -> 980 | applied |
| `eng-test-author` | 0.890 | 0.890 | 1,046 -> 988 | applied |
| `ops-ci-implementer` | 1.000 | 1.000 | 1,051 -> 947 | applied |
| `ops-format-normalizer` | 0.332 | 0.332 | 1,012 -> 983 | not applied |

The CI fixture now supplies the workflow file, allowlist, gate, and rollback as
current state; without them the role correctly blocked and the test was not
discriminating.

AP-01 WARN count: 4 -> 0.

`ops-format-normalizer` needed a tool-enabled harness: the role must read,
normalize, verify, and commit. `tooling/run_role_tools_ab.py` gives it a
temporary workspace and an allowlisted tool surface. Result over 3 seeds: both
arms 1.000/3, candidate used fewer turns (36 avg vs 42) and was applied.

## Score optimization (3 seeds)

| Role | Before | After | Body | Decision |
|---|---:|---:|---:|---|
| `rev-review-lead` | 0.889 | **1.000** | 1,041 -> 1,051 | improved candidate applied |
| `eng-backend-developer` | 0.667 | **1.000** | 998 | fixture now asks for the test command/exit code; candidate not applied (0.779 vs 1.000) |
| `eng-test-author` | 0.890 | **1.000** | 988 | current body reached 1.000; candidate not needed |

The backend and test-author jumps came from removing fixture ambiguity (asking
for the test command and exit code), not from deleting role content. The
review-lead improvement came from an explicit no-edit/high-confidence merge rule.

All role A/B rows now score 1.000 on their current fixtures.
