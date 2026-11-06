Use: `/orchestrate <task>` -- dispatch the project's orchestrator agent with the task.

Doctrine: the orchestrator owns the loop Plan -> PlanReview (spec) -> Implement -> Review (audit) -> Fix -> Verify -> Push (finalize), including the PlanReview/Fix, Review/Fix and Verify/Fix back-edges; no unit reaches Implement without a clean plan review; this command only hands off the task, and Push stays with the operator.
