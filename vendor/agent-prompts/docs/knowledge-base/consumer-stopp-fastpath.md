# Consumer STOPP fast-path adoption

Status: exact patch instructions. The consumer checkout was not modified.

Evidence: `docs/knowledge-base/stop-gate-experiment.md` (72 runs). STOPP scored
0.963 on the safety subset; direct execution 0.334. The only measured
over-fire was comment-only work, which the fast path covers.

## Patch 1 -- `containeromat:AGENTS.md`

Append this paragraph to the existing STOPP section; leave the S-1..S-5 text
and the explicit-`go` list untouched:

```markdown
Fast path (one edit only): a comment-only, whitespace-only, formatting-only
(parsed artifact unchanged), or spelling-only change in exactly one file and at
most ~50 changed lines may skip PROPOSE/STOP **only if** it changes no behavior,
schema, persistence, auth, network, dependency, or deploy surface, has a
verification command, and has no exception-registry conflict.
Run verification in the same step, then stop. A missing required fact or a
registered exception is HALT, not full STOPP; anything else is full STOPP.
Classify with `agent-prompts/tooling/classify_change.py` and record its output.
```

Keep the HALT section unchanged. HALT outranks both paths.

## Patch 2 -- `containeromat:docs/rules/41-process.md`

In "Micro-step planning", replace "Doc-only change -> size limits waived." with:

```markdown
- Doc-only, comment-only, formatting-only, or spelling-only change in one file
  and at most ~50 changed lines -> size limits waived **and** eligible for the
  STOPP fast path, provided the edit changes no
  behavior/schema/persistence/auth/network/dependency/deploy surface, a
  verification command runs in the same step, and no exception conflict
  applies. Formatting-only means the parsed artifact is unchanged.
```

Add after the step template:

```markdown
### STOPP fast path

Use full STOPP for behavior. The fast path is a closed list (SG-02/SG-03 in
`agent-prompts/standards/stop-gate.md`):

1. one file and at most ~50 changed lines;
2. comment/whitespace/formatting (parsed unchanged)/spelling only;
3. no behavior, schema, persistence, auth, network, dependency, or deploy change;
4. verification runs in the same step;
5. no exception-registry conflict and no missing fact (a missing fact is HALT).

If any item is unknown, use full STOPP. A one-line behavior change is not
eligible. The fast path skips PROPOSE/STOP, not verification.
```

## Optional -- compose-step

`compose-step` is already a gated write skill and should stay full STOPP for
behavior changes. Do **not** fast-path image tags, healthchecks, ports, users,
permissions, volumes, or any deploy behavior, even at one line (SG-03). A
comment-only or whitespace-only edit in `compose.yaml` that leaves the parsed
configuration unchanged is eligible, because that is the case the experiment
measured; anything that changes the parsed document is full STOPP.

## Verification after the patch

- `python3 scripts/verify-agents.py` passes.
- The rule text still contains S-1..S-5 and the explicit-`go` list.
- A comment-only fixture classifies `fast-path`:
  `python3 agent-prompts/tooling/classify_change.py --kind comment --files 1 --lines 1 --verify-command "docker compose config -q"`.
- A behavior fixture classifies `full-stopp`:
  `python3 agent-prompts/tooling/classify_change.py --kind behavior --files 1 --lines 1 --verify-command "docker compose config -q"`.

## Rollback

Revert the two text blocks. The fast path is opt-in; removing it restores the
prior always-on behavior with no schema or data migration.
