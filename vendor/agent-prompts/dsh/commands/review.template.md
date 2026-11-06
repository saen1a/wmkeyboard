<!-- TEMPLATE -- the deployed instance lives in <project>/stacks/deepseek-harness/config/ and is paired with that stack. -->

---
description: review changes [uncommitted|staged|unpushed|branch|commit|worktree] [quick|deep]
input-hint: scope (uncommitted, staged, unpushed, branch <ref>, worktree, commit sha) plus effort flags (quick/--quick/-q, deep/--deep/-d, --effort 1-10)
---

Run the review skill for this scope: $ARGUMENTS

Resolve the scope per the skill (default: uncommitted changes). Review only -- do
not edit any file. The effort flags (quick, deep, --effort) map to the review
tiers in the skill's Tiers section. Track dispatch uses {{DSH_TOOLS}}; if it is
unavailable, run the review single-agent and say so. Finish with the report and
a recommendation, then offer the fix handoff to {{PROJECT_HANDOFF}}; do not
apply fixes until the operator asks.

Doctrine: this command serves the Review phase only; findings feed the Fix handoff and the operator owns Push.
