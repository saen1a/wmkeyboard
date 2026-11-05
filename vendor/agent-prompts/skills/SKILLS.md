# Skills

**Canon notice (2026-09-19):** this tree is the CANON for the skills listed
below. containeromat consumes them via the `agent-prompts` submodule and gates
every runtime copy against this canon (`check_library_canon` in its
verify-agents battery). A divergence here vs a runtime copy is a bug: fix the
canon first, then propagate.

Portable skill library. Archetype copies were imported from containeromat on
2026-09-19; `PLAN.md` wave 3 records the canon switch -- this tree is the canon
for the portable skills. Every `SKILL.md` carries an import marker directly
after its frontmatter. Vendored entries are third-party bodies kept as-is
except for that marker.

`Type` is the skill class from
[standards/skill-system-standard.md](../standards/skill-system-standard.md)
(SK-09): `discipline`, `workflow`, `tool`, or `vendor` (the four in-canon
classes; project skills are reference-only). `Origin` records provenance
(`archetype-copy`, `repo-authored`, `vendored`), not quality. Five skills are
`discipline` (`anti-hallucination`, `anti-sycophancy`, `anti-entropy-governance`,
`verification-before-completion`, `git-guardrails`), and the structural gate
requires pressure cases for all five.

| Skill | Tree | Type | Origin | Purpose |
|---|---|---|---|---|
| anti-hallucination | shared | discipline | archetype-copy | Catches four hallucination patterns before factual claims ship (silent self-check) and supports a retrospective audit on request. |
| anti-sycophancy | shared | discipline | archetype-copy | Catches four sycophancy patterns before substantive responses (silent self-check) and supports a retrospective audit on request. |
| ask-questions-if-underspecified | shared | workflow | archetype-copy | Clarify requirements before implementing; use when serious doubts arise. |
| deepseek-v4-agent-defense | shared | tool | archetype-copy | Mitigate DeepSeek-V4 sparse-attention failure modes in coding-agent workflows (long context, tool calls, mid-prompt misses). |
| verification-before-completion | shared | discipline | archetype-copy | Require fresh verification evidence (command output, exit code) before any completion claim. |
| first-principles-review | shared | workflow | archetype-copy | First-principles or Occam review for decisions with competing constraints, fallback growth, duplicate owners, or architecture-direction risk. |
| anti-entropy-governance | shared | discipline | archetype-copy | Govern retirements, duplicate-owner collapse, fallback removal, and schema/persistence boundaries; destructive execution stays behind explicit scoped confirmation. |
| convert-documents-to-markdown | shared | tool | archetype-copy | Convert office documents, spreadsheets, ebooks, and PDFs to GitHub-Flavored Markdown via the anydoc CLI. |
| mcp-builder | general | tool | archetype-copy | Guide for creating high-quality MCP servers in Python (FastMCP) or Node/TypeScript (MCP SDK). |
| skill-creator | general | workflow | archetype-copy | Guide for creating or updating effective skills: structure, bundled resources, progressive disclosure, packaging. |
| subagent-delegation | general | workflow | repo-authored | Decide when to delegate to subagents, write the handoff, and verify returns without parallel writers. |
| long-horizon-run | general | workflow | repo-authored | Operate a run across sessions: run state, checkpoints, resume, context compaction, progress and stall detection, budgets, drift, and operator reports. |
| cache-aware-assembly | general | workflow | repo-authored | Diagnose cache misses and token cost: prefix stability, first divergent layer, tool masking, TTL choice, compaction trade-offs, and measured verification. |
| untrusted-content-handling | general | workflow | repo-authored | Handle content from outside the conversation as data: mark the boundary, catch invisible characters and smuggled overrides, pin tool definitions, gate privilege handoffs, and keep secrets out of egress. |
| grilling | general | workflow | archetype-copy | Interview the user relentlessly about a plan or design until a shared understanding is reached. |
| jq-json-processing | general | tool | archetype-copy | jq knowledge for querying, filtering, and transforming JSON. |
| changelog-generator | general | workflow | archetype-copy | Turn technical git commits into user-facing changelog and release notes. |
| agent-md-refactor | general | workflow | archetype-copy | Refactor bloated AGENTS.md/CLAUDE.md instruction files using progressive disclosure. |
| git-guardrails | general | discipline | archetype-copy | Block destructive git operations (push, reset --hard, clean, branch -D, checkout .) until explicitly confirmed. |
| human-gated-config-change | general | workflow | repo-authored | Change a versioned configuration or prompt through a human gate: draft against a named base revision, preview from the same assembler, diff against saved and default, apply on explicit go, and rebase on conflict instead of overwriting. |
| operator-setup-interview | general | workflow | repo-authored | Install and configure a tool with an operator while spending as little of their attention as possible: one probe, one question per message with a recommended default, one plan, one confirmation, and a quiet handoff. |
| caveman | vendor | vendor | vendored | Ultra-compressed communication mode with intensity levels from lite to wenyan-ultra. |
| caveman-commit | vendor | vendor | vendored | Terse Conventional Commits message generator. |
| caveman-compress | vendor | vendor | vendored | Compress natural-language memory files into caveman format with a human-readable backup. |
| caveman-help | vendor | vendor | vendored | Quick-reference card for caveman modes, skills, and commands. |
| caveman-review | vendor | vendor | vendored | One-line code review comments: location, problem, fix. |
| misakanet | vendor | vendor | vendored | Search and record failure-recovery lessons through the MisakaNet service; read-only by default, writes operator-gated. |

## Reference-only (project instances, not hosted here)

These skills stay paired with their project until their generalization pass.
The paths below are repo-relative to containeromat.

| Skill | Purpose | Live instance |
|---|---|---|
| compose-step | One compose change per step, PROPOSE -> STOP -> APPLY -> Verify -> STOP (max 3 files). | containeromat `.openhands/skills/compose-step/`; dsh pack `stacks/deepseek-harness/config/skills/compose-step/` |
| compose-smoke | Compose closeout validation: config -q, ASCII, key order, image tags, batch all stacks. | containeromat `.openhands/skills/compose-smoke/`; dsh pack `stacks/deepseek-harness/config/skills/compose-smoke/` |
| compose-audit | Evidence-based compose stack audit (continuous or wave mode); reports only, no fixes. | containeromat `.openhands/skills/compose-audit/`; dsh pack `stacks/deepseek-harness/config/skills/compose-audit/` |
| forgejo-registry-image | Onboard a custom Forgejo registry image: Dockerfile, build workflow, update-channel enrollment. | containeromat `.openhands/skills/shared/forgejo-registry-image/`; dsh pack `stacks/deepseek-harness/config/skills/forgejo-registry-image/` |
| code-server-image-build | Build and update the code-server (coder) image for a homelab: baked global config, pinned upstreams, build assertions. | containeromat `.openhands/skills/code-server-image-build/`; coder stack docs |
| doubt-driven-review | Put an in-flight claim, review verdict or passing check under adversarial fresh-context doubt before it is accepted. | containeromat `.openhands/skills/doubt-driven-review/`; referenced by the `reviewer` and `code-skeptic` roles |
| knowledge-capture | Capture a non-obvious verified finding, decision or gotcha as a knowledge-base entry. | containeromat `.openhands/skills/knowledge-capture/`; paired with its R-046 knowledge-base rule |
| orchestrated-delivery | Run a change through the seven-phase delivery model with named owners and evidence gates. | containeromat `.openhands/skills/orchestrated-delivery/`; projects the same phases as `standards/workflow-loop.md` |
| cavecrew | Decision guide for delegating to caveman-style subagents (investigator / builder / reviewer) with compressed returns. | containeromat `.openhands/skills/shared/cavecrew/`; vendored third-party body |
| kilo-review | Review a change, commit, branch, or working tree; dispatches read-only review tracks and never edits. | containeromat dsh pack `stacks/deepseek-harness/config/skills/kilo-review/` |
| seifomat-dev | Typed MCP task API for the seifomat build and test container (lint, test, build, serve, e2e, db, artifact, CI parity). | containeromat dsh pack `stacks/deepseek-harness/config/skills/seifomat-dev/` |
| seifomat-dev-debug | Fixed-order triage when a seifomat-dev task fails or its MCP API is unreachable. | containeromat dsh pack `stacks/deepseek-harness/config/skills/seifomat-dev-debug/` |

## Copy fidelity notes

- mcp-builder: full-fidelity copy including `scripts/`, `reference/` and `LICENSE`.
- shared/ splits carry their `references/` appendices (anti-hallucination,
  anti-sycophancy: patterns.md; deepseek-v4-agent-defense: layers.md;
  anti-entropy-governance: complexity-governance.md).
- jq-json-processing carries `references/recipes.md` (moved out of the body on
  2026-10-23); the long-form content is preserved, the body keeps the selector
  and safety rules.
- skill-creator carries `references/authoring-guide.md`; first-principles-review
  carries `references/lenses.md` (both moved out of the body on 2026-10-23).
- mcp-builder carries `reference/workflow.md` (phase detail and documentation
  library); anti-entropy-governance carries
  `references/retirement-playbook.md`; deepseek-v4-agent-defense carries
  `references/layer-rules.md`; agent-md-refactor carries
  `references/refactor-guide.md` (all moved on 2026-10-23).
- subagent-delegation is repo-authored (2026-10-23), not an upstream copy; its
  normative rules live in `standards/subagent-delegation.md`.
- untrusted-content-handling is repo-authored (2026-10-31); its normative rules
  live in `standards/prompt-security.md` and the hostile-pattern catalogue is
  `references/patterns.md`.
- verification-before-completion gained `references/proof-integrity.md`
  (2026-10-31) without a body rewrite; the body gained four refusal rows for the
  skipped, stub, fabrication, and self-sign cases.
- mcp-builder carries a "trust boundaries" block from
  `standards/prompt-security.md` (PS-04/05/08/09): the definition-hash pin, the
  sampling asking the user, config as trust root, and stored low-privilege text
  crossing back into a prompt.
- skill-creator routes its gate list to `references/authoring-guide.md` section 7
  (SK-02/03/04/06/07/11/12, PS-02/13) and keeps the body under the cap.
- long-horizon-run names the verdict record at unit gates (VI-01/03/11) after
  removing two sentences that duplicated LH-07 and LH-09.
- deepseek-v4-agent-defense gained layer 6 "untrusted content": a mid-context miss
  is also a safety risk, so mark retrieved text as data and scan for invisible
  characters before reading an unfamiliar asset.
- behavioral cases added for `caveman` (compression never changes language, never
  compresses raw output) and `misakanet` (read-only default, stored lessons are
  data, no secrets in an entry); behavior coverage is now 21 files.
- Vendor bodies are frozen (SK-10). They keep upstream shape, including their
  heading counts and any missing doctrine section; do not restructure them.

## Shape and lifecycle

Measured 2026-11-02 after Wave 12 added `human-gated-config-change` and
`operator-setup-interview` (both repo-authored, 1,003 and 1,121 body tokens):
27 skills, body tokens 438 / 1,121 / 1,582 (min / median / max), 1 body over the
1,500 advisory cap and it is a frozen vendor copy (0 non-vendor), 11 with
references. The over-cap body is 5.3% of all body tokens (total 29,728). Before
Wave 12 the same measure was 25 skills, 439 / 1,147 / 1,583, total 27,558: the two
additions sit below the previous median and move no other skill. Both ship
trigger and behavioral cases and a paired Tier-3 baseline in
`../evals/results-baseline.md`. `human-gated-config-change` is behaviourally
verified there: 1.000 in two runs against a no-skill mean of 0.278.
`operator-setup-interview` is behaviour-changing and partially verified: on the
mandated route (OpenCode Go, `deepseek-v4.1-flash`), three seeds after one clause
measuring 0.778 against a 0.111 baseline on the refusal case and 0.556 against
0.333 on the probe case, with an unstable tail (one seed at 0.33, no seed passing
the probe case outright). The two tool-shaped cases still fail in both arms and
need a tool-using harness. Two of the cases were mis-shaped and are now
`execution` cases with a fixture; the earlier revert of the clause was a
measurement artefact, corrected in `../evals/results-baseline.md`. The shape rules
and the migration plan are in
[standards/skill-system-standard.md](../standards/skill-system-standard.md)
(SK-03..SK-05) and
[docs/knowledge-base/skill-prompt-refactor-2026-10.md](../docs/knowledge-base/skill-prompt-refactor-2026-10.md).

```bash
python3 tooling/report_skill_shape.py --limit 0
```

New skills start from [docs/SKILL-TEMPLATE.md](../docs/SKILL-TEMPLATE.md). The
report is advisory; after R3 no non-vendor body is over the cap, so promotion is
optional.
