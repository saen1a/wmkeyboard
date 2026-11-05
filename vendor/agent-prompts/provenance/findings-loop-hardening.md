# Findings ledger: loop-hardening

One row per finding, per WL-13. Round 0 is the plan review of
`provenance/plan-loop-hardening-2026-11.md`; round 1 is the re-review after the
spec was repaired. No finding is deleted.

| finding_id | severity | unit | file_line | evidence | acceptance_impact | owner | state | round | decision |
|---|---|---|---|---|---|---|---|---|---|
| F-1 | high | loop-hardening | `provenance/plan-loop-hardening-2026-11.md:56` | Round 0: one verdict path for a two-round unit, round order undefined. Round 1: U2 now takes a list and orders by `attempt`, contiguous from 0 | U2 | library-maintainer | fixed | 1 | fixed with evidence |
| F-2 | high | loop-hardening | `provenance/plan-loop-hardening-2026-11.md:58` | Round 0: verification pointed at an artifact the unit creates, so the check could not exist at review time. Round 1: the contract distinguishes the runner (must exist) from a declared unit artifact | U2 | library-maintainer | fixed | 1 | fixed with evidence |
| F-3 | medium | loop-hardening | `provenance/plan-loop-hardening-2026-11.md:57` | Round 0: "every OMP module" duplicates a pinned policy. Round 1: the composed foreground set must state the gate exactly once | U3 | library-maintainer | fixed | 1 | fixed with evidence |
| F-4 | medium | loop-hardening | `provenance/plan-loop-hardening-2026-11.md:59` | Round 0: no acceptance named the measured-state refresh. Round 1: U5 carries it as a MUST criterion | U5 | library-maintainer | fixed | 1 | fixed with evidence |
| F-5 | low | loop-hardening | `provenance/plan-loop-hardening-2026-11.md:55` | Round 0: effective-date default unstated. Round 1: U2 names the default and the `--since` override | U2 | library-maintainer | fixed | 1 | fixed with evidence |
| F-6 | high | loop-hardening | `tooling` line 65 | Round 2 (implementation review): U6's own check cannot pass as written -- one verdict path where two rounds exist. Round 3: the cell names the glob form, and the gate rejects a single-file verdict set | U6 | library-maintainer | fixed | 3 | fixed with evidence |
| F-7 | high | loop-hardening | `tooling` line 48 | Review: FINAL omitted Push, so a finalize without a verify record passed. Fixed: VERIFY_REQUIRED covers Push, with a test | U2 | library-maintainer | fixed | 3 | fixed with evidence |
| F-8 | high | loop-hardening | `tooling` line 98 | Review: a Ready (unverified) row waived the plan review on a free-text token. Fixed: the branch is gone; grandfathering is an explicit --grandfather unit id, never self-declared, never Done | U2 | library-maintainer | fixed | 3 | fixed with evidence |
| F-9 | medium | loop-hardening | `tooling` line 158 | Review: the effective date was a raw string compare. Fixed: both dates parse as ISO and a ledger is history only when its newest row predates the gate | U2 | library-maintainer | fixed | 3 | fixed with evidence |
| F-10 | medium | loop-hardening | `tooling` line 94 | Review: plan-review evidence matched by bare unit string. Fixed: the ledger artifact cell must name the reviewed spec and the last round's hash is recomputed | U2 | library-maintainer | fixed | 3 | fixed with evidence |
| F-11 | medium | loop-hardening | `tooling` line 217 | Review: a missing check file was 'pending' and passed. Fixed: a missing file fails; the pending concept is gone | U1 | library-maintainer | fixed | 3 | fixed with evidence |
| F-12 | medium | loop-hardening | `tooling` line 152 | Review: the Owner column was never read and a section preamble satisfied the writer rule. Fixed: every unit needs an owner | U1 | library-maintainer | fixed | 3 | fixed with evidence |
| F-13 | medium | loop-hardening | `tooling` line 216 | Review: AD-12 accepted a claim no command backed ('hook', 'gate' anywhere). Fixed: the evidence must cite a file that exists in the tree | U4 | library-maintainer | fixed | 3 | fixed with evidence |
| F-14 | medium | loop-hardening | `tooling` line 124 | Review: an absolute or escaping check path was accepted. Fixed: tokens are confined to the root and must be files | U1 | library-maintainer | fixed | 3 | fixed with evidence |
| F-15 | low | loop-hardening | `tooling` line 239 | Review: only the first Doctrine line was read. Fixed: exactly one is required | U3 | library-maintainer | fixed | 3 | fixed with evidence |
| F-16 | low | loop-hardening | `tooling` line 279 | Review: manifest module names unvalidated and any mention satisfied the gate. Fixed: plain .md names of the set and the canonical sentence are required | U3 | library-maintainer | fixed | 3 | fixed with evidence |
| F-17 | low | loop-hardening | `tooling` line 194 | Review: a MUST: TBD criterion passed. Fixed: placeholders are refused in the Acceptance cell | U1 | library-maintainer | fixed | 3 | fixed with evidence |
