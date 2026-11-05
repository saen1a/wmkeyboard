# Integration status -- deployment and sync model

Audience: future agents and the operator. This file records how prompt content
travels from the library to every runtime, which gates fire along the way, and
what is currently in flight or advisory.

Citation convention: `containeromat:<path>` and `seifomat:<path>` are citations
into those checkouts (not links). Unprefixed script names (`verify-agents.py`,
`scripts/...`, `compose.yaml`, `init.sh`) refer to containeromat paths.
Revisions: containeromat `main`, library 2.6.0
(`b1ea951`, 2026-10-26). Skill routing is 25/25 case files with 0 violations
(`tooling/check_skill_routing.py`), and 24 of the 25 library skills are registered (`untrusted-content-handling` lands at the next re-vendor)
and copied in the consumer.

Related: [surfaces.md](surfaces.md), [governance.md](governance.md),
[evaluation.md](evaluation.md).

## 1. Content flow

```
library (this repo, canon for 27 skills + role templates)
  |
  |  git submodule `agent-prompts` (containeromat:.gitmodules:1-3)
  v
containeromat checkout
  |-- .openhands/skills/**            (copies + canon-derived, 25)
  |-- .openhands/skills/**       (copies, 13)
  |-- stacks/deepseek-harness/config/**  (dsh pack: 5 presets, 16 skills, 7 HA personas, 2 commands)
  |-- stacks/zcode/config/**     (4 agents, 22 skills, 8 commands, AGENTS.md)
  |-- stacks/coder/**            (2 baked skill sources + pinned archify fetch)
  |
  |  gates: check_library_canon, skills manifest, seed-marker drift,
  |         verify-agents battery, ci-replica battery
  v
runtime roots (loaded at container start / image build / session start)
```

Library -> containeromat is a **reviewed copy** for skills (canon first, then
propagate; the manifest hash changes force the copy update). For fragments, the
conduct fragment is re-vendored from containeromat; the doctrine fragment is
library-canonical from 1.3.0 (current 1.5.0) and propagates to containeromat. Containeromat ->
runtime is either a seed (dsh, ZCode), a build-time COPY (coder), a human copy
(OpenHands), or direct in-repo loading (Kilo worktree).

## 2. Canon directions

| Content | Canon | Consumers | Direction |
|---|---|---|---|
| 25 portable skills (24 registered) | library [skills/](../../skills/) | `.openhands/skills`, `.openhands/skills`, dsh skills, ZCode skills | library -> containeromat |
| Project-instance skills (`compose-*`, `forgejo-registry-image`, `kilo-review`, `seifomat-*`) | containeromat `.openhands/skills` / dsh pack | runtime copies | containeromat-internal by design ([PLAN.md](../../PLAN.md)) |
| Conduct fragment | `containeromat:.kilo/templates/agent-conduct.md` | Kilo agents, ZCode ports, dsh HA + presets, library templates | containeromat -> library (re-vendor, pinned hashes) |
| Doctrine fragment | library `fragments/agent-doctrine.md` | Kilo agents, ZCode ports, dsh HA + presets | library -> containeromat (re-vendor from 1.3.0 (current 1.5.0)) |
| Role templates | library [agents/](../../agents/) | containeromat live agents (adoption audited, not yet migrated) | library -> consumer, by selection ([CATALOG.md](../../CATALOG.md)) |
| dsh runtime prompts | the deploying stack config | dsh at container start | paired; never a library deploy ([dsh/README.md](../../dsh/README.md)) |
| OMP subagent prompts | the consuming project's `.omp/agents/` | OMP task discovery at session start | rendered from [omp/catalog.yaml](../../omp/catalog.yaml) by `tooling/render_omp.py`; generated, never hand-edited, never committed in the library ([omp/README.md](../../omp/README.md)) |

## 3. The carrier: submodule, registries, gates

| Element | Path | Role |
|---|---|---|
| Submodule | `containeromat:.gitmodules` (`agent-prompts`, Forgejo URL) | Carries the library into every containeromat checkout; CI uses `submodules: true` (`compose-validate.yml:30`) |
| Library registry | `containeromat:scripts/skills-library.json` | `schema skills-library/1`, `canonRoot: agent-prompts`, 24 name -> dir rows. The library hosts 27 skills; 24 are registered and copied. `untrusted-content-handling` and the two Wave 12 skills (`human-gated-config-change`, `operator-setup-interview`) land at the next re-vendor, so the registry stays at 24 until then |
| R2/R3 skill changes (Wave 9) | `containeromat:.openhands/skills/`, dsh and ZCode skill copies | Nine bodies changed and seven added a reference file in the canon: `jq-json-processing`, `skill-creator`, `first-principles-review`, `mcp-builder`, `anti-entropy-governance`, `deepseek-v4-agent-defense`, `agent-md-refactor`, `ask-questions-if-underspecified`, `verification-before-completion`. Consumer copies were re-vendored at `b1ea951` (library 2.6.0 at that pin); all 24 names are registered, copied, and routing 24/24 with 0 violations |
| Canon check | `containeromat:scripts/verify-agents.py:1481-1554` | Every runtime copy must contain the library canon body (import marker stripped, folded) and mirror every non-`SKILL.md` file byte-for-byte; fail-closed unless `--allow-missing-library` |
| Roots registry | `containeromat:scripts/skills-roots.json` (schema v2, 5 roots) | Which checks each root joins: `names`, `dirs`, `copies`, `references`, `discipline`; exactly one `role: canon` root |
| Identity manifest | `containeromat:scripts/skills-manifest.json` | Tree hash + file count per skill per root (109 skills, 5 roots); `skills-manifest.py --write` regenerates |
| Seed markers | `stacks/{deepseek-harness,zcode}/config/**/.seed-version` | Gate `scripts/verify-skills-seed-version.sh`: a governed change without a marker bump fails |
| Generated config | `containeromat:.kilo/kilo.json` | Rendered from `.kilo/agents/*.md` by `scripts/render-agent-config.py`; `--check` gate |
| Prompt verifier | `containeromat:scripts/verify-agents.py` | The whole R-042/R-043 battery ([governance.md](governance.md) section 5) |
| Drift hunt | `containeromat:scripts/check-prompt-drift.sh` | Runs the verifier, then prints a per-skill parity digest (canon sha12 / copy sha12 / identical-transformed) across ZCode, dsh, OpenHands copies |
| Local battery | `containeromat:scripts/ci-replica.sh --fast` | Replays the compose-validate gates with CI-exact commands (incl. the prompt, seed-marker, manifest and skill-frontmatter steps) |

## 4. Runtime deploy mechanics

### DSH (deepseek-harness)

1. `./config` is bind-mounted read-only at `/seed` (`compose.yaml:120`) and the
   init container runs `/seed/init.sh` (`compose.yaml:121-122`).
2. `init.sh` publishes to `$DSH_HOME` (= `/dsh-home`) with a seed-version marker
   per surface: `settings.yaml` (mv to `.bak-<ts>` + replace on bump),
   `agent-presets/*` (snapshot to `<name>.bak-<ts>` + replace on a bump; the
   rule still advises keeping customizations in a renamed/copied preset),
   `skills/*` (replace with no per-dir backup), and
   `dsh-ha-orchestrator.config.json` into `$DSH_HOME` + `/workspace`
   (`config/init.sh:93-199,201-267,293-336`). Markers live on the init-only
   `/seed-state` mount, outside the agent-writable home
   (`config/init.sh:72-91`).
3. Slash commands are NOT seeded: `./config/commands` is bind-mounted read-only
   at `/etc/dsh/commands` (`compose.yaml:322-326`) and read by the
   `dsh-command-md` plugin row (`webserver.patch.yml:206-211`).
4. `rules.yaml` is bind-mounted read-only at `/etc/dsh/rules.yaml`; the old
   seeded copy and its marker are inert (`config/init.sh:281-292`).
5. A changed composition loads only after a restart, then a new session
   (`agent-presets/orchestrator/agent.cordis.yml:29-30`).

### ZCode

1. The image bakes the seed at `/opt/zcode-seed/` from `stacks/zcode/config/`
   (`config/init-root.sh:5-8`).
2. `zcode-init` compares `/opt/zcode-seed/skills/.seed-version` with the
   persistent `/data/home/.zcode/.seed-state/seed-version`
   (`init-root.sh:32-44`): changed/absent -> replace skills/agents/commands +
   AGENTS.md after snapshotting the overwritten trees to
   `.seed-state/backups/<timestamp>/` (`init-root.sh:74-90`); unchanged ->
   `cp -n`, so operator/UI edits survive redeploys.
3. The marker only advances when every copy succeeded; a symlinked managed root
   skips the seed entirely (`init-root.sh:46-68,153-161`).
4. To ship a ZCode skill/agent/command change: bump
   `stacks/zcode/config/skills/.seed-version` in the same change (gate above).
5. Subagents take effect in a new session only (no hot reload).

### Kilo worktree

No seed: `.kilo/agents/*.md` is the live authoring source. After an agent edit,
run `scripts/render-agent-config.py` (or verify with `--check`); worktrees must
initialize the `agent-prompts` submodule
(`containeromat:scripts/setup-checkout.sh`), and the submodule must be clean
(`containeromat:scripts/verify-submodule-clean.sh`, the wave-3 lesson).

### coder image

`stacks/coder/Dockerfile` `COPY`s the two `*-skill/` dirs to
`/home/coder/.openhands/skills/shared/` (`Dockerfile:975,978`) and fetches the pinned
archify skill (R-044, `Dockerfile:990-999`). A skill change reaches the image
only through a rebuild.

### OpenHands

`.openhands/skills/` is auto-loaded from the workspace; copies are hand-synced
from `.openhands/skills/shared/` (`containeromat:.openhands/skills/README.md:7-8`).
The discipline scan (AP-13) still covers the root.

## 5. Deployment actions that load content

| Change | Action to reach runtime |
|---|---|
| Kilo agent/command/skill edit | None beyond the worktree; regenerate `kilo.json` for agent changes |
| dsh preset/skill/HA/settings edit | Bump the matching `.seed-version` + redeploy the deepseek-harness stack (init seed), then restart dsh and start a new session |
| ZCode skill/agent/command/AGENTS.md edit | Bump `stacks/zcode/config/skills/.seed-version` + rebuild/redeploy the zcode image (the seed is baked) |
| coder baked skill edit | Rebuild the coder image (`containeromat:.forgejo/workflows/build-coder.yml` per R-019) |
| OpenHands skill edit | Re-copy into `.openhands/skills/` in the repo |
| Library skill canon edit | Copy into every runtime root that carries the name, regenerate the skills manifest; containeromat CI (`check_library_canon`) fails until copies match |
| Library role-template edit | No runtime effect until a consumer instantiates it |

## 6. Seifomat adoption status

Seifomat adopted the neutral layout on 2026-10-26 and merged PRs #4-#8. Its
canonical sources are `agents/`, `commands/`, `skills/`, `fragments/`, and
`rules/`; `.kilo/agents`, `.kilo/command`, `.kilo/skills`, `.kilo/templates`,
`.kilo/rules`, and the `.kilo/kilo.json` agent block are generated adapters.
The library pin is `f84cd2e` (at that commit: library 2.5.2, agent templates 2.0.2, orchestrator 2.1.3, doctrine 1.3.1, conduct
1.0.0). The earlier `kilo/agent-pack` branch is obsolete and can be deleted.
Seifomat is the second library consumer after containeromat.

## 7. Current advisories (verified at this revision)

| Item | Evidence | Status |
|---|---|---|
| Token-budget WARNs (advisory, not fatal) | `containeromat:CHANGELOG.md:335-336` | `compose-step` ~966/950, `reviewer` ~954/950, `review-lead` ~1792/1100 -- reported, justified by the invariant fragments; element budgets hold |
| `ci-step` in the library instantiation mapping | [tooling/check_instantiation.py](../../tooling/check_instantiation.py) `MAPPING` (16 rows) vs [packs/containeromat.md](../../packs/containeromat.md) (16 rows) | Resolved 2026-09-20: the `operations-ci-implementer` row was added; structural audit covers 16/16 live agents |
| dsh command-seed comment is stale | `containeromat:stacks/deepseek-harness/webserver.patch.yml:202-203` says the init container seeds commands; `compose.yaml:326` bind-mounts them read-only and `init.sh` has no commands block | Deployed mechanism = bind mount; do not re-add a seed |
| `.kilo/README.md` stale skill row | `containeromat:.kilo/README.md:75` lists `skills/theia-image-build/SKILL.md`; the directory is `code-server-image-build/` | Documentation drift outside this KB's ownership |
| Wave-5 eval surfaces | `evals/trigger/` (25 case files, one per portable skill) and [tooling/check_skill_routing.py](../../tooling/check_skill_routing.py) | Shipped 2026-09-20; Tier-2 runs blocking in containeromat CI (`--fail-on-warn`). Tier-3 runner shipped (2026-10-23); library paired baselines are recorded in `evals/results-baseline.md`, while live consumer-harness validation is deferred to November (`dsh`) and not applicable this cycle (`zcode`) |
| dsh and zcode runtimes inactive | operator statement, 2026-10-27 | **Not applicable this cycle.** `dsh` regains usage in November; `zcode` has no date. Only `opencode-go` is active, on `deepseek-v4.1-flash`. Their skill roots stay in the consumer but are inert: no re-vendor, seed-marker bump or gate work is owed, and no live harness validation can be claimed from file presence |

No unconditional deployment claim is made here: the deployed host state is
verified per R-035 via `docker inspect` or the Dockhand UI before being cited.
