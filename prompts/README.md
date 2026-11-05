# Task prompts

Reusable briefs for this project. They are not auto-loaded; paste one into a
session or pass it to the orchestrator. The library's neutral prompts remain
under `vendor/agent-prompts/prompts/`.

Every prompt follows the same contract:

- Goal and scope, including the paths in and out of scope.
- Acceptance criteria that a verifier can check.
- Verification commands with expected exit codes.
- Named halt conditions, so the agent stops instead of guessing.

The binding loop is Plan -> PlanReview -> Implement -> Review -> Fix -> Verify ->
Push. A task prompt never skips the plan review, and Push stays with the
operator.

| Prompt | Use when |
|---|---|
| `tasks/feature.md` | A new user-visible feature with a decidable spec |
| `tasks/bugfix.md` | A reproducible defect with a failing case |
| `tasks/native-engine-change.md` | Rust engine, JNI, or native gate work |
| `tasks/glide-experiment.md` | A measured glide or WMLM experiment |
| `tasks/docs-page.md` | A docs page or a settings reference |
| `tasks/release-cut.md` | A release note and store metadata |
| `workspace/wmk-session.txt` | A compact session brief for a new workspace |

The agent that owns implementation is chosen by the layer, not by the prompt:
Kotlin and Compose to `wmk-kotlin-engineer`, Rust and JNI to
`wmk-native-engineer`, research to `wmk-glide-researcher`, review to
`review-lead`.
