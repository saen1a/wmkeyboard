# Migration record (2026-09-19)

The portable prompt library was migrated out of the containeromat repository on
2026-09-19: workspace prompts, long-form exemplars, and provenance records were
imported from containeromat `docs/prompts/` and `docs/research/` into
`workspace-prompts/`, `exemplars/`, and `provenance/` (batch B4). The governing
operator decision, recorded in [`PLAN.md`](../PLAN.md), is that every DSH
runtime prompt stays paired with its deploying stack and context inside
containeromat, while this repository holds only the portable library layer;
`PLAN.md` also carries the remaining batches, the full asset classification,
and the deferred skills wave. The imported files are pinned copies (2026-09-19)
and do not follow later containeromat edits automatically.
