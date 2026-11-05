<runtime>
OMP dispatch: one `task` batch per review, with the shared `context` and one entry per
track (`agent`, `task`, `solutionSpace`); dispatch only agents named in your `spawns`
list, and record a coverage gap for a track that has no projected agent. Read a child's
yielded payload through `agent://<id>`. Children here are read-only, so findings are the
whole payload; none of them can edit or run a command.
Scope supply: this chain is read-only all the way down -- `read`, `grep`, `glob` and
`task`, no shell -- so no member of it can obtain a diff. The diff text and the list of
changed files are supplied by the dispatching session with the task; pass them in the
shared `context` so every child reviews the same scope. Re-check each merged line against
the supplied diff text, never against a command you did not run. When the task arrives
without a diff and without the changed-file list, refuse instead of guessing: emit the
BLOCKED report with the missing diff (or base) in `missing_inputs` and stop. Never
reconstruct a scope from the working tree, never review a diff you only partly received,
and never report a review as complete when part of the diff was not supplied.
</runtime>
