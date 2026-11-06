# Vendored assets -- NOTICE

This notice records third-party assets vendored into the consuming projects
(currently containeromat) and referenced by this library. The vendored copies
live in those projects; the paths below are repo-relative to that project. Each
asset is kept verbatim or with the minimal edits recorded in its own header,
never generalized: rewriting an upstream artifact would fork it, break update
parity, and weaken the upstream attribution trail.

## anchored-standard preset (dsh-anchored-standard)

- **What is vendored:** the "Standard" agent preset published as
  `dsh-anchored-standard`, carried as the `anchored-standard` persona next to
  the deepseek-harness stack config
  (`stacks/deepseek-harness/config/agent-presets/anchored-standard/`,
  together with its own upstream NOTICE).
- **Source:** https://github.com/xiaobright/dsh-anchored-standard, commit
  `47f9438` (adapted copy; the fork derives from deepseek-ai/deepseek-harness).
- **License:** MIT; Copyright (c) 2026 xiaobright, Portions Copyright (c) 2026
  DeepSeek. The upstream permission notice travels with the vendored copy.
- **Why not generalized:** the preset is an upstream standard copy, not
  library-authored content, and upstream declared it frozen; it is pinned
  as-is and re-verified on dsh upgrades instead of being rewritten.

## caveman skills

- **What is vendored:** the caveman compression skill family (for example
  `caveman`, `caveman-help`, `caveman-compress`, `caveman-review`,
  `caveman-commit`), vendored into consumer skill roots and the zcode stack
  config (`stacks/zcode/config/skills/`).
- **Source:** https://github.com/JuliusBrussee/caveman, baseline tag `v2.2.0`.
  The main `caveman` skill was vendored 2026-08-21; the `caveman-commit`,
  `caveman-compress`, `caveman-help` and `caveman-review` sub-skills were
  vendored 2026-07-15. Individual consumers may pin a later release through
  their own lockfiles.
- **License:** the repository root declares MIT, but the sub-skill license is
  not independently verified here and is recorded as unverified; the upstream
  BSL-1.1 engine-linked directories are outside the vendored skill set.
- **Why not generalized:** the skills are self-contained upstream artifacts;
  local edits are limited to the adaptations recorded in the vendored copy
  (lite default, English-only language clause, dropped caveman-compress
  reference), and rewording the rules would break parity with upstream
  updates.

## misakanet skill

- **What is vendored:** the `misakanet` SKILL.md (MisakaNet failure-memory
  search/record workflow), vendored next to the deepseek-harness stack config
  (`stacks/deepseek-harness/config/skills/misakanet/`).
- **Source:** https://github.com/Ikalus1988/MisakaNet (`skills/misakanet/SKILL.md`),
  vendored 2026-09-15 at commit `b38653c32863606085b4f91affccd4c0fb65f535`;
  also distributed as the npm bundle `misakanet@2.30.2`.
- **License:** Apache-2.0.
- **Why not generalized:** the skill documents a third-party MCP service and
  is upstream-owned content; local changes are limited to the safety edits
  recorded in its header (ASCII folding, MCP namespace note, helper scripts
  and endpoints removed, write/intake path operator-gated).
