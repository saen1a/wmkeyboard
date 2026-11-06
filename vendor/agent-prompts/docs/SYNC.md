# Sync policy (anti-drift)

## Upstream authority

Wave 3 flipped the direction for skills: the library is the CANON for the
skills under `skills/` (containeromat gates runtime copies against this tree
via its `check_library_canon`). Since 2026-10-24 the library is also the
authoring source for `agent-doctrine.md` (v1.3.0; current 1.5.0 as of
2026-11-03, the plan-review gate). On 2026-10-26 `agent-conduct.md` became
library-canonical at 1.0.0 as well; containeromat re-vendors it like doctrine.
containeromat re-vendored the doctrine and 21 of the 24 then-existing library skills on
2026-10-25 (submodule `886f186`); `cache-aware-assembly`, `long-horizon-run`,
and `subagent-delegation` were registered and copied on 2026-10-26, which
moved the pin to `0490cb7`. The pin moved to `b1ea951` (library 2.6.0 at that pin) on
2026-10-26 (containeromat gitlink bump `0b433d97`), and the registration state
is 24/24: every library skill is named
in `containeromat:scripts/skills-library.json`
and copied to its runtime roots. `tooling/check_skill_routing.py` reports
`27 skills, 27 case files, 0 violations`: `untrusted-content-handling`
(2026-10-31) and the two Wave 12 skills (`human-gated-config-change`,
`operator-setup-interview`) are not in the consumer's registry yet, so its
registration stays 24/24 until the next re-vendor.

The library conforms to the containeromat prompt standard (R-042) and review
contract (R-043) as pinned at `2026-09-19`. When the library changes a fragment
or a rule, it bumps `fragment_versions` and regenerates the affected templates;
consumers re-vendor and re-instantiate.

## Rules

1. **Fragments are byte-exact against their canonical source.**
   `fragments/agent-conduct.md` is canonical in this library from v1.0.0
   onward (2026-10-26). `fragments/agent-doctrine.md` is canonical from v1.3.0
   onward; current 1.5.0. Both are pinned in
   `tooling/fragments.manifest.json`; `tooling/check_fragments.py` enforces the
   manifest hash.
2. **Consumers pin versions.** Each instantiation records
   `template_version` + `fragment_versions`. A drift check in the consumer
   compares its copies against the pinned library release.
3. **A fragment divergence is a bug, not a customization.** Project rules
   override template *behavior* via the slot system -- never via fragment
   edits.
4. **Template bumps are semver.** Any slot-contract or fragment change bumps
   the template `version`; consumers re-instantiate consciously.

## Vendor projections

A vendor projection maps a selection of `roles/**` to one runtime's prompt
format and lives in its own directory: `dsh/` for the deepseek-harness presets
and commands, `omp/` for the OMP subagent projection (`omp/catalog.yaml` plus
`tooling/render_omp.py`, see `omp/README.md`). A projection never redefines a
role body: it copies the neutral blocks, swaps the conduct variant and leaves
the project slots to the consumer, so `roles/**` and `fragments/**` stay the
only canon.

The conduct variant registry grew to four: `kilo`, `dsh-ha`, `dsh-preset` and
`omp`. `CONDUCT_VARIANT` (and the role frontmatter `conduct_variant`) accepts
`omp`, which selects `fragments/agent-conduct.omp.md` -- the same block text as
`agent-conduct.md` apart from the tool bullet, which names OMP's own tool names.
`tooling/validate_templates.py` and `tooling/check_instantiation.py` carry the
same mapping, and `tooling/fragments.manifest.json` pins its hash.

## Mechanics

- `tooling/check_fragments.py` -- consumer drift check: sha256-verifies every
  fragment against the pinned `tooling/fragments.manifest.json` (works in any
  checkout, no upstream needed). Maintainer legacy diagnostic:
  `python3 tooling/check_fragments.py --upstream /data/C0ding/.kilo/templates`
  byte-compares `agent-conduct.md` against a historical containeromat template.
  It is not a gate and does not define authority; both fragments are
  library-canonical (conduct 1.0.0, doctrine 1.5.0).
- `tooling/validate_templates.py` -- structure, budget, metadata, hygiene per
  template (see `PLAN.md` quality bar).
- Consumer-side drift checks stay in each project's own gate (containeromat:
  `scripts/verify-agents.py` `check_conduct` / `check_doctrine`).
