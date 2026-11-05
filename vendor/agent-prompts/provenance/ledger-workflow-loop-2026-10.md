# Ledger: workflow-loop-2026-10

One row per unit, per WL-08. This is the live ledger for the workflow-loop
change; update it at each gate rather than relying on chat memory.

| unit_id | phase | attempt | gate | status | artifact | findings | evidence | decision | owner | timestamp | next |
|---|---|---|---|---|---|---|---|---|---|---|---|
| workflow-loop | Push | 1 | pass | Done | b4cf400 | none (M: review/validator gaps closed; pytest 131 at merge) | check_workflow_loop exit 0; validate_templates exit 0; check_fragments exit 0; make gate exit 0; pytest 131 exit 0 (at b4cf400); current gate evidence is in ledger-long-horizon-2026-10.md; 2026-10-25; repo; deepseek-v4.1-flash | pass | library maintainer | 2026-10-25 | none |
| plan-review-gate | Verify | 1 | hold | Ready (unverified) | 41 carriers + 4 presets; WL-15; gate-verdict/run-state schemas 1.1.0/1.2.0; loop guards 20 | none (unverified; grandfathered: the unit predates the plan-review gate it introduced) | make gate exit 0 (2026-11-03); pytest 719 passed; loop-guards 20/20; long-horizon --verify OK; adversarial mutations rejected (row removed, Plan->Implement added, authority dropped, old doctrine line, ledger skip) | hold | library maintainer | 2026-11-03 | Push |

## Notes

- The pre-registered 1.3.0 A/B measured the pre-1.3.1 body and is 0.9907 vs 0.9723 (3 wins / 32 ties / 1 loss); it meets the registered non-inferiority bar but is one model and one task per role, not proof.
- The library layer is complete only after the consumer re-vendor and verifier
  run; those are outside this repository.

## Operator acceptance

The `check_fragments.py --upstream` narrowing (doctrine is library-canonical from
1.3.0; manifest hash remains the drift check) was accepted by the operator on
2026-10-24; the instruction and scope are recorded in
`provenance/operator-acceptance-2026-10-24.md`.
