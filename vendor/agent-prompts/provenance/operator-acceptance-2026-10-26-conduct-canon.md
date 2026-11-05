# Operator acceptance: conduct is library-canonical

Date: 2026-10-26.

On 2026-10-26 the operator instructed:

> go 1-5

Item 5 of that list was "Decide whether `agent-conduct.md` becomes
library-canonical." This file records the decision.

## Decision

`fragments/agent-conduct.md` is library-canonical from version 1.0.0 onward.
Containeromat re-vendors it from this library, like `agent-doctrine.md`.
The fragment content did not change in this step, so the version and the
manifest hash stay at 1.0.0.

## Consequences

- The manifest hash in `tooling/fragments.manifest.json` is the authoritative
  drift gate for both fragments.
- `tooling/check_fragments.py --upstream <dir>` remains a legacy diagnostic
  against a historical containeromat template. It is not a gate and does not
  define authority.
- `docs/SYNC.md`, `docs/knowledge-base/governance.md`, and
  `docs/knowledge-base/evaluation.md` record the new direction.
- A future change to conduct is authored here, reviewed here, and re-vendored
  by consumers; it no longer starts in containeromat.

## Supersedes

This decision supersedes the 2026-10-24 narrowing that made only
`agent-doctrine.md` library-canonical and left `agent-conduct.md`
containeromat-owned. See `provenance/operator-acceptance-2026-10-24.md`.
