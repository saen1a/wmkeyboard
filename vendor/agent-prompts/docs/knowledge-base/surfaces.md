# Surface map -- every prompt, agent and skill surface

Audience: future agents and the operator. Goal: no tribal knowledge about where
prompt content lives, who reads it at runtime, and which gate protects it.

Citation convention: `containeromat:<path>` and `seifomat:<path>` are citations
into those checkouts (not links, they are outside this repository). Plain
markdown links are repository-relative to this library. Unprefixed script names
(`verify-agents.py`, `scripts/...`, `compose.yaml`, `init.sh`) refer to
containeromat paths. Line numbers are from the revision read while writing; the
current pin is library `b1ea951` (2026-10-26), so re-check a cited line
against it.

Related: [governance.md](governance.md) (the rules engine),
[integration-status.md](integration-status.md) (deployment + sync),
[evaluation.md](evaluation.md) (evals).

## 1. Runtime planes at a glance

| Plane | Live root | Load path (who reads it) | Sync relationship |
|---|---|---|---|
| Kilo worktree (containeromat) | `containeromat:.kilo/` | Kilo Code loads `AGENTS.md`, the generated `agent` block in `.kilo/kilo.json`, `.kilo/command/*.md`, `.openhands/skills/**` | Authoring source; shared blocks come from `containeromat:.kilo/templates/` |
| DSH (deepseek-harness) | `containeromat:stacks/deepseek-harness/config/` | init container seeds `$DSH_HOME` (presets, skills, settings) and bind-mounts `config/commands` read-only; dsh reads them at container start | Stack-paired -- runtime prompts stay with the deploying stack ([dsh/README.md](../../dsh/README.md)) |
| ZCode | `containeromat:stacks/zcode/config/` | `zcode-init` seeds `~/.zcode/{skills,agents,commands,AGENTS.md}` at container start | Ports of Kilo agents + skill copies (see `containeromat:docs/runbooks/zcode-deploy.md`) |
| OpenHands | `containeromat:.openhands/skills/` | agent-server project skill source (`{workspace}/.openhands/skills/`) | Canonical source of the skills since 2026-10-15; the canon moved out of .kilo/skills, which is retired |
| coder image | `containeromat:stacks/coder/` | Baked global skills at `/home/coder/.openhands/skills/shared/` in the image | 2 `*-skill/` source dirs + a pinned archify fetch (R-044) |
| Library (this repo) | `agents/ prompts/tasks/ commands/ dsh/ skills/` | Consumers select templates and instantiate them; skills are consumed as canon | Canon for 27 skills; re-vendors containeromat fragments |

## 2. Kilo worktree surfaces (containeromat)

| Path | Count | What it is | Governing gate |
|---|---|---|---|
| `containeromat:.kilo/agents/*.md` | 16 | Agent/subagent system prompts (authoring source; body = prompt). 2 primary, 14 subagents (8 hidden `review-*`) | `scripts/verify-agents.py` (R-042 AP-07) |
| `containeromat:.kilo/command/*.md` | 6 | Slash commands: `orchestrate`, `orch-status`, `review-lead`, `caveman`, `hallucination-check`, `sycophancy-check` | `verify-agents.py` doctrine scan + `check_command_doctrine` |
| `containeromat:.kilo/prompts/*.md` | 3 | Task prompts: `new-stack`, `harden-stack`, `full-audit-compose` (carry `Doctrine:` lines by convention; not gated) | Outside `COMMAND_GLOBS` |
| `containeromat:.openhands/skills/**/SKILL.md` | 25 | Canon skills for the repo (12 top-level + 13 under `shared/`) | `verify-agents.py` skill battery (names/dirs/copies/references/discipline) |
| `containeromat:.kilo/templates/*.md` | 3 | `agent-conduct.md`, `agent-doctrine.md` (canonical fragments), `oidc-stack-doc.md` (unrelated to prompts) | `check_conduct` / `check_doctrine` byte-identity |
| `containeromat:.kilo/rules/*.md` | 10 | Always-loaded core rules (incl. `40-english-only.md`, `12-halt-taxonomy.md`) | Loaded via the `instructions` key |
| `containeromat:.kilo/kilo.json` | 1 | Generated agent block (16 agents) | `scripts/render-agent-config.py --check` inside `check_mirror` |
| `containeromat:.kilo/orchestrator/` | specs + 3 eval sets + 3 reports + `decisions.md` | Orchestrator runtime state and prompt-eval artifacts | See [evaluation.md](evaluation.md) |

## 3. DSH surfaces (containeromat deepseek-harness stack)

| Path | Count | What it is | Load / gate |
|---|---|---|---|
| `stacks/deepseek-harness/config/ha-orchestrator.config.json` | 1 file, 7 personas | HA subagent prompts: `reviewer`, `researcher`, `research-merger`, `code-skeptic`, `docs-specialist`, `homelab-ops`, `security-auditor` | Seeded with marker `ha-orchestrator.config.seed-version`; checked by `check_ha_conduct` (dsh-adapted conduct + doctrine) |
| `stacks/deepseek-harness/config/agent-presets/*/agent.cordis.yml` | 5 presets | `anchored-standard`, `homelab`, `orchestrator`, `reviewer`, `seifomat` | Seeded with `agent-presets/.seed-version`; `check_preset_conduct` + `check_model_pins` |
| `stacks/deepseek-harness/config/skills/*/SKILL.md` | 16 | dsh skill pack (copies + platform skills like `kilo-review`, `seifomat-dev`) | Seeded with `skills/.seed-version`; skills manifest + discipline scan |
| `stacks/deepseek-harness/config/commands/*.md` | 2 | `review`, `knowledge-qa` (bind-mounted read-only at `/etc/dsh/commands`, `compose.yaml:326`; plugin `dsh-command-md`, `webserver.patch.yml:206-211`) | `check_command_doctrine` |
| `stacks/deepseek-harness/config/settings.yaml`, `rules.yaml` | 2 | Runtime settings + permission rules (`rules.yaml` bind-mounted read-only at `/etc/dsh/rules.yaml`) | `check_model_pins` entitlement cross-check (`settings.yaml`) |
| `stacks/deepseek-harness/config/plugins/` | `bundles.list`, `bundles.disabled.list`, `pnpm-workspace.yaml` | dsh plugin supply surface (not prompts; recorded for completeness) | `verify-bundle-compat.py`, dependency-coverage allowlist |

Seed markers (all read from the init-only `/seed-state` mount, outside the
agent-writable home):

| Marker file | Value | Governs |
|---|---|---|
| `stacks/deepseek-harness/config/settings.seed-version` | `2026-09-15-commandcode-provider` | `settings.yaml` |
| `stacks/deepseek-harness/config/agent-presets/.seed-version` | `2026-09-19-preset-resync` | preset directories |
| `stacks/deepseek-harness/config/skills/.seed-version` | `2026-09-19-wave3-canon` | skill directories |
| `stacks/deepseek-harness/config/ha-orchestrator.config.seed-version` | `2026-09-19-eval-fixes` | HA orchestrator config in `$DSH_HOME` + `/workspace` |
| `stacks/deepseek-harness/config/plugins/pnpm-workspace.seed-version` | `2026-09-10-pnpm12` | pnpm profile workspace |

## 4. ZCode surfaces (containeromat zcode stack)

| Path | Count | What it is | Load / gate |
|---|---|---|---|
| `stacks/zcode/config/agents/*.md` | 4 | Subagent ports: `compose-step`, `reviewer`, `code-skeptic`, `docs-specialist` (frontmatter carries `name`, `description`, `tools:`) | `check_ports` (conduct/doctrine byte-identity + `tools:` key) |
| `stacks/zcode/config/commands/*.md` | 8 | `caveman`, `new-stack`, `hallucination-check`, `sycophancy-check`, `harden-stack`, `orch-status`, `full-audit-compose`, `orchestrate` | `check_command_doctrine` (6 carry `Doctrine:`; `caveman` + `orch-status` exempt) |
| `stacks/zcode/config/skills/*/SKILL.md` | 22 | ZCode skill copies (canon-derived + 4 platform skills) | Seeded with `skills/.seed-version` = `2026-09-19-wave4-cmd-ascii`; manifest + discipline + library canon |
| `stacks/zcode/config/AGENTS.md` | 1 | User-global rules (first boot only, operator-editable) | Seed snapshot/backup on replace (`init-root.sh:140-151`) |
| `stacks/zcode/config/plugins-manifest.json` | 9 pinned plugins | Vendored Claude-Code-compatible plugin set (not prompts) | Dependency-coverage allowlist row |
| `stacks/zcode/config/mcp-servers.json` | 3 seeded servers | MCP seed for headless runs | Boot seed (`zcode-deploy.md`) |

## 5. Other runtime surfaces

| Surface | Path | Count | Notes |
|---|---|---|---|
| OpenHands project skills | `containeromat:.openhands/skills/` | 13 skills | AUTO-loaded; skills without `triggers:` are injected into every conversation. Source is `.openhands/skills/shared/` (README at the root of that dir) |
| coder baked skills | `containeromat:stacks/coder/caveman-skill/`, `stacks/coder/docker-socket-proxy-skill/` | 2 source dirs | `COPY`ed to `/home/coder/.openhands/skills/shared/{caveman,docker-socket-proxy}/SKILL.md` (`Dockerfile:975,978`) |
| coder baked archify | fetched at image build (R-044) | 1 | Pinned SHA + zip digest in `stacks/coder/Dockerfile:990-999`; checked by `verify-archify-pins.py` |
| coder global config | `containeromat:stacks/coder/kilo-indexing.jsonc` | 1 | Must NOT re-define project agents (`check_coder_global_config`) |
| AnythingLLM workspace prompts (adjacent, R-038) | `containeromat:docs/prompts/` | 3 current + archive | Versioned `.txt`, manual paste; NOT R-042. `standard-rag-v3.txt`, `homelab-workspace-v27.txt`, `deep-research-generic-v10.txt` |
| Library workspace-prompt copies | [prompts/workspace/](../../prompts/workspace/) | 2 files | `standard-rag-v3.txt`, `deep-research-generic-v10.txt` (pinned copies) |

## 6. Library surfaces (this repository)

| Path | Count | What it is |
|---|---|---|
| [fragments/](../../fragments/) | 5 | `agent-conduct.md`, `agent-conduct.dsh-ha.md`, `agent-conduct.dsh-preset.md`, `agent-conduct.omp.md`, `agent-doctrine.md` (byte-exact, pinned) |
| [standards/](../../standards/) | 22 + 5 evidence + 2 cache data + tool-set, run-journal, gate-verdict and admission schemas | Prompt standard, workflow loop (WL-01..WL-15), long-horizon runs (LH-01..LH-14), verification integrity (VI-01..VI-15), prompt security (PS-01..PS-14), agent adapter (AD-01..AD-12), skill system, model calibration, prompt assembly, STOPP gate, subagent delegation, agent context files, review contract, evidence duty, halt taxonomy, English-only, system-prompt standard, work authorization, durable effects, message delivery, agent notification, model surface + evidence records |
| [agents/](../../agents/) | 38 templates, 9 domains | Engineering 8, design 1, documentation 1, networking 1, operations 3, orchestration 3, research 3, review 13 (incl. 8 `review-tracks/`), tabletop 5 ([CATALOG.md](../../CATALOG.md)) |
| [prompts/tasks/](../../prompts/tasks/) | 3 | `new-component`, `harden-deployment`, `audit-report` |
| [commands/](../../commands/) | 5 | `orchestrate`, `review`, `caveman`, `hallucination-check`, `sycophancy-check` |
| [dsh/](../../dsh/) | 4 presets + 2 commands + README | Parameterized archetypes; pairing invariant in [dsh/README.md](../../dsh/README.md) |
| [omp/](../../omp/) | catalog + 4 overlays + README | OMP vendor projection: `catalog.yaml` maps 12 roles (all read-only roles plus the orchestrator) to OMP agents and defers 11 with a reason, rendered by `tooling/render_omp.py`; the library commits no rendered projection ([omp/README.md](../../omp/README.md)) |
| [skills/](../../skills/) | 27 skills + [SKILLS.md](../../skills/SKILLS.md) | Canon for 27 portable skills (13 general, 8 shared, 6 vendor) |
| [evals/](../../evals/) | 2 + 27 trigger + 23 behavioral case files | `ops-ci-executor/` reference set + `trigger/` Tier-2 cases + `behavioral/` Tier-3 cases + `results-baseline.md` |
| [tooling/](../../tooling/) | 39 tools + 2 manifests + 41 test modules | `check_fragments.py`, `validate_templates.py`, `check_workflow_loop.py`, `check_instantiation.py`, `check_skill_routing.py`, `check_behavioral_evals.py`, `run_behavioral_evals.py`, `report_skill_shape.py`, `run_role_doctrine_experiment.py`, `summarize_behavioral_results.py`, `run_stop_gate_experiment.py`, `classify_change.py`, `run_refactor_ab.py`, `check_harness_telemetry.py`, `run_role_ab.py`, `summarize_role_ab.py`, `run_role_tools_ab.py`, `run_state.py`, `check_long_horizon.py`, `check_token_efficiency.py`, `check_tool_set.py`, `check_findings_ledger.py`, `check_run_journal.py`, `render_agents.py`, `render_omp.py`, `check_test_floor.py`, `check_failure_set.py`, `check_optimization_ledger.py`, `check_rebaseline.py`, `check_semantic_routing.py`, `run_cache_baseline.py`, `fragments.manifest.json`, `test-manifest.json` |
| [packs/](../../packs/) | 2 | `containeromat.md` -- template-to-live-agent adoption record, and `containeromat-admission-cells.md` -- its first pickup decision |
| [prompts/workspace/](../../prompts/workspace/), [exemplars/](../../exemplars/), [provenance/](../../provenance/) | 2 / 8 / 13 | Paste prompts, reference exemplars, migration records |
| [docs/](../) | 5 + this KB | `SYNC.md`, `INSTANTIATE.md`, `TEMPLATE-GUIDE.md`, `SKILL-TEMPLATE.md`, `neutral-layout.md` + `knowledge-base/` |

## 7. Integration matrix -- 16 agents x 4 planes

Legend: **P** = present (live prompt in that plane) | **A** = absent, no
carve-out needed (plane does not carry this role) | **C** = carve-out
(deliberately not carried; reason recorded in the Carve-outs section) | **T** =
library template exists (the template column is the library-template plane).

| Agent (Kilo) | Kilo | DSH | ZCode | Library template | Notes |
|---|---|---|---|---|---|
| `orchestrator` | P (primary) | P (preset main persona) | C | T `orchestration-orchestrator` | ZCode primary-agent role; DSH orchestrator preset owns the persona |
| `compose-step` | P | P (skill + HA `homelab-ops` lens) | P (port) | T `operations-executor` (flavor) | Three different carriers, one role |
| `ascii-step` | P | A | C | T `operations-format-normalizer` (flavor) | Repo-local normalizer tooling |
| `ci-step` | P (new 2026-09-19) | A | C | T `operations-ci-implementer` + eval set | Under evaluation; library mapping audited 2026-09-20 |
| `reviewer` | P | P (preset + HA persona) | P (port) | T `review-reviewer` | |
| `code-skeptic` | P | P (HA persona) | P (port) | T `review-code-skeptic` | |
| `docs-specialist` | P | P (HA persona) | P (port) | T `documentation-doc-writer` | |
| `review-lead` | P (primary) | P (as `kilo-review` skill + reviewer preset) | C | T `review-review-lead` | dsh review is skill-driven, 4-child cap |
| `review-security` | P (hidden) | P (HA `security-auditor` lens + skill track) | C | T `review-track-security` | Track set is `.kilo/agents`-only on ZCode |
| `review-business-logic` | P (hidden) | P (skill track) | C | T `review-track-correctness` | Containeromat names it business-logic |
| `review-deploy-safety` | P (hidden) | P (skill track) | C | T `review-track-deploy-safety` | |
| `review-duplication` | P (hidden) | P (skill track) | C | T `review-track-duplication` | |
| `review-dead-code` | P (hidden) | P (skill track) | C | T `review-track-dead-code` | |
| `review-quality` | P (hidden) | P (skill track) | C | T `review-track-quality` | |
| `review-structure` | P (hidden) | P (skill track) | C | T `review-track-structure` | |
| `review-simplicity` | P (hidden) | P (skill track) | C | T `review-track-simplicity` | |

Matrix sources: the 16 agents in `containeromat:.kilo/agents/` and the
generated `agent` block (`containeromat:.kilo/kilo.json:37-853`); the dsh roster
in `config/ha-orchestrator.config.json:8-50`, presets under
`config/agent-presets/`, and the `kilo-review` skill; the ZCode ports at
`stacks/zcode/config/agents/*.md`; the mapping table in
[tooling/check_instantiation.py](../../tooling/check_instantiation.py) (16 rows)
and [packs/containeromat.md](../../packs/containeromat.md) (16 rows including
`ci-step`).

`ci-step` note: `operations-ci-implementer` was added to the
`check_instantiation.py` `MAPPING` on 2026-09-20, so the structural audit now
covers all 16 live agents (16/16 OK).

## 8. Documented carve-outs

ZCode carve-out set (recorded 2026-09-19, `zcode-deploy.md:154-163`):

| Kilo surface | Reason (documented) |
|---|---|
| `orchestrator` (primary) | Its role lives in the ZCode primary agent + `AGENTS.md`, not a subagent (`zcode-deploy.md:157-158`) |
| `ascii-step` | Repo-local ASCII-normalizer tooling; ASCII work is a containeromat-worktree-only concern (`zcode-deploy.md:159-160`) |
| `ci-step` | Added 2026-09-19, under evaluation -- not ported; `zcode` is inactive with no return date (2026-10-27), so the port is not tracked as pending demand (`zcode-deploy.md:161`) |
| `review-lead` + the 8 `review-*` tracks | The R-043 review harness is `.kilo/agents`-only; ZCode review is the single `reviewer` port (`zcode-deploy.md:162-163`) |

DSH-side absences are by design, not carve-outs: the HA roster is a closed
seven-persona set (`ha-orchestrator.config.json:8-50`) and the review tracks run
as skill modes inside `kilo-review`, not as separate agents. `ascii-step` and
`ci-step` have no dsh counterpart because both are containeromat-repo-local
executors.

## 9. Command-surface consolidation (2026-09-19)

`.kilo/command/` is the client-documented load path (project config
`.kilo/command/*.md`) and the single governed command surface. `.kilo/commands/`
was a legacy second directory; its three files (`orchestrate`, `orch-status`,
`review-lead`) were merged into `.kilo/command/` in wave 4 (2026-09-19).
`.kilo/commands/` no longer exists. `scripts/verify-agents.py` scans only
`.kilo/command/*.md`, `stacks/zcode/config/commands/*.md` and
`stacks/deepseek-harness/config/commands/*.md`
(`containeromat:scripts/verify-agents.py:135-143`;
`containeromat:docs/runbooks/prompt-audit.md:19-25`).

## 10. dsh preset inventory and library templates

| Preset | Kind | Library archetype | Resync status |
|---|---|---|---|
| `anchored-standard` | Upstream dsh standard copy | none -- exempt (`PRESET_CONDUCT_EXEMPT`, `verify-agents.py:121-123`) | Not repo-authored |
| `homelab` | Repo-authored prefix persona | [dsh/presets/generalist-prefix.template.yml](../../dsh/presets/generalist-prefix.template.yml) | Re-synced 2026-09-19 (`preset-resync`); gained the `Read {{PROJECT_RULES}}` bullet |
| `orchestrator` | Repo-authored main persona | [dsh/presets/orchestrator-persona.template.yml](../../dsh/presets/orchestrator-persona.template.yml) | Re-synced 2026-09-19; councillor detail + handoff wording |
| `reviewer` | Repo-authored prefix persona | [dsh/presets/reviewer-prefix.template.yml](../../dsh/presets/reviewer-prefix.template.yml) | Re-synced 2026-09-19; gained the `Read {{PROJECT_RULES}}` bullet |
| `seifomat` | Repo-authored prefix persona | [dsh/presets/seifomat-prefix.template.yml](../../dsh/presets/seifomat-prefix.template.yml) | Added wave 3 (2026-09-19); archetype exists in [dsh/presets/](../../dsh/presets/) |

Coverage statement: the 2026-09-19 re-sync covered 3 of 5 presets
(`orchestrator`, `homelab`, `reviewer`); the seifomat archetype also ships in
[dsh/presets/](../../dsh/presets/) (4th preset with an archetype);
`anchored-standard` is exempt as an upstream copy. `PRESET_CONDUCT_REQUIRED`
lists the four repo-authored presets (`verify-agents.py:120`), so an
unclassified new preset fails.

## 11. Skill surfaces (root x count x role x gate)

| Root | Skills | Role | Count source | Gates |
|---|---|---|---|---|
| `containeromat:.openhands/skills` | 31 | canon | `scripts/skills-roots.json` | names, dirs, copies, references, discipline |
| `containeromat:stacks/deepseek-harness/config/skills` | 18 | copy (seeded) | `skills-roots.json` | names, dirs, copies, references, discipline |
| `containeromat:stacks/zcode/config/skills` | 27 | copy (seeded) | `skills-roots.json` | names, dirs, copies, discipline |
| `containeromat:stacks/paseo/config/skills` | 31 | copy | `skills-roots.json` | names, dirs, copies, discipline |
| `containeromat:stacks/coder` (`*-skill/`) | 2 | copy | `skills-roots.json` | dirs, discipline |
| Library `skills/` (this repo) | 24 | external canon | `containeromat:scripts/skills-library.json` | `check_library_canon` in containeromat `verify-agents.py`; the registry lists all 24 names |

Counts: 109 skill directories across 5 roots (`containeromat:scripts/skills-manifest.json`).
The library is the canon for all 24 registered names; runtime copies of those
names must contain the canon body and mirror non-`SKILL.md` files
(`check_library_canon`, `verify-agents.py:1481-1554`). Root-by-root counts above
are the manifest entries; see [integration-status.md](integration-status.md) for
the full gate chain.
