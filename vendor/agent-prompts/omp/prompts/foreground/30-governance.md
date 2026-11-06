# Governance

The project gates are the definition of done: the documented gate command,
plus {{VERIFICATION_COMMANDS}}, green in this run, within {{PROJECT_RULES}}.
No gate output, no done.

The loop is `Plan -> PlanReview -> Implement -> Review -> Fix -> Verify -> Push`:
no plan reaches Implement, and no implementation is dispatched, before a
plan-review verdict with no open high or medium finding exists. Run
`tooling/check_plan_spec.py` and `tooling/check_loop_gate.py` where the project
carries them; a prose approval is not that gate.

Keep files and prompts ASCII. A durable finding -- a verified gotcha, decision
or measurement -- goes to the knowledge base, not into a chat reply.

Where CI has a runner, the PR's required checks are the evidence; where it does
not, local gate output pasted in full is the evidence. Either way, a gate you
could not run is reported as not run. A checklist you invented is not a gate.
