> Paths in this record use the pre-2.0 `roles/` / `tasks/` names; current paths are `agents/` / `prompts/tasks/`.

# Token-warning triage (2026-10)

Status: triage record for the 15 AP-01 WARN rows emitted by
`tooling/validate_templates.py` on 2026-10-23. These are advisory overages, not
element breaches. No body was trimmed for this record.

The doctrine experiment
([role-doctrine-experiment.md](role-doctrine-experiment.md)) is the first lever:
if the compact variant passes, every low-phase role drops about 210 tokens
before any prose is touched. Trim prose only after that result.

## Decision table

| File | Tokens | Target | Over | Decision |
|---|---:|---:|---:|---|
| `roles/review/rev-review-lead.md` | 1,464 | 1,100 | +364 | Trim after doctrine A/B; keep merge rules |
| `roles/operations/ops-executor.md` | 1,174 | 950 | +224 | Trim runbook duplicates after doctrine A/B |
| `roles/review/rev-reviewer.md` | 1,116 | 950 | +166 | Merge dual-workflow prose after doctrine A/B |
| `roles/engineering/eng-frontend-developer.md` | 1,116 | 1,000 | +116 | Merge framework guidance after doctrine A/B |
| `roles/networking/net-network-architect.md` | 1,124 | 1,000 | +124 | Merge overlapping constraints |
| `roles/orchestration/orch-orchestrator.md` | 1,152 | 1,100 | +52 | Trim prose; keep sequencing rules |
| `roles/engineering/eng-api-developer.md` | 1,089 | 1,000 | +89 | Defer; no duplicate owner identified |
| `roles/engineering/eng-database-developer.md` | 1,086 | 1,000 | +86 | Defer; schema rules are load-bearing |
| `roles/engineering/eng-backend-developer.md` | 1,060 | 1,000 | +60 | Defer |
| `roles/operations/ops-ci-implementer.md` | 1,051 | 1,000 | +51 | Defer |
| `roles/engineering/eng-test-author.md` | 1,046 | 1,000 | +46 | Defer |
| `roles/review/rev-code-skeptic.md` | 1,025 | 1,000 | +25 | Defer |
| `roles/operations/ops-format-normalizer.md` | 1,012 | 1,000 | +12 | Defer |
| `tasks/harden-deployment.md` | 1,014 | 1,000 | +14 | Defer; task prompts are not always loaded |
| `tasks/new-component.md` | 1,008 | 1,000 | +8 | Defer; task prompts are not always loaded |

## Rules

- Do not delete a behavioral requirement to clear a WARN (AP-01).
- Do not trim a role body in the same change that tests the doctrine variant.
- Re-run this triage after the doctrine experiment and after any model or
  harness change (MC-03).
- A role over target with no duplicate prose gets a recorded exemption, not a
  forced edit.
