<!-- Canonical agent doctrine fragment (R-042 AP-14).
     The single source for the binding orchestrated task workflow loop
     (Plan -> PlanReview -> Implement -> Review -> Fix -> Verify -> Push). Rendered into
     every carrying prompt by the prompt authors; tooling/check_workflow_loop.py asserts identity across the library roles,
     tasks and the repo-authored dsh preset personas (whitespace-normalized).
     Edit only this file. ASCII only, English only (R-040). -->

<doctrine>
Binding workflow loop: Plan -> PlanReview -> Implement -> Review -> Fix -> Verify -> Push.
Run owned phases; the orchestrator owns the loop and ledger.
- Plan includes research: gather until the spec is decidable; blocked
  -> HALT. Implement with one writer per shared surface; no parallel writers.
- PlanReview is the spec gate and is never skipped: a verifier who did not write
  the spec checks goal, request coverage, acceptance, verification, ownership and
  order, and named halt risks; an open high/medium finding goes Fix -> PlanReview
  until a round is clean, each round stating CHANGED, and a round that changes
  nothing is HALT (stalled).
- Review is the audit gate: a clean-context verifier reads the artifact,
  acceptance, and evidence commands, not author reasoning;
  open high/medium findings go Fix -> Review.
- Verify runs the proof commands fresh and reads the output and exit code; a
  failure goes Fix -> Review -> Verify. A pass is a record: named verifier
  (never the author), command, exit, freshness; skipped work is unverified and
  narration or a stub is not an artifact.
- Push is finalize: only on operator "go"; record evidence, harness/model/closeout.
  Stop at Ready without go; HALT terminal.
One refinement per code gate, then escalate. The author is never sole verifier: use a
mechanical check or record an exemption; mark it unverified. Evidence at every transition.
</doctrine>
