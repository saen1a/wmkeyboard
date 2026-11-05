# Governance -- the rules engine

Audience: future agents and the operator. This file condenses the normative
sources that govern every prompt surface (R-042, R-043) into one enforcement
map: what the rules require, and which gate catches which violation.

Citation convention: `containeromat:<path>` is a citation into that checkout
(not a link). Line numbers are from the revision read while writing
(containeromat `main`, 2026-09-20). The binding sources are
`containeromat:docs/rules/42-agent-prompt-standard.md` (R-042) and
`containeromat:docs/rules/43-code-review-subagent-contract.md` (R-043); the
library mirrors them as [standards/agent-prompt-standard.md](../../standards/agent-prompt-standard.md)
and [standards/code-review-contract.md](../../standards/code-review-contract.md).

Related: [surfaces.md](surfaces.md), [integration-status.md](integration-status.md),
[evaluation.md](evaluation.md).

## 1. Authority chain

`HALT (HF-01..HF-15) > STOPP (S-1..S-5) > communication > topic rules > user request`
(`containeromat:AGENTS.md:156-161`). A skill never overrides a HALT/STOPP rule
or the language mandate (R-042 AP-13.2). R-042 governs agent/subagent prompts;
R-038 governs AnythingLLM workspace prompts; R-040 the language mandate.

## 2. R-042 -- the prompt standard, AP-01..AP-14

### AP-01 Instruction budget

| Tier | Elements (hard) | Tokens (advisory) | Registered carriers |
|---|---|---|---|
| standard subagent | `<= 12` | `<= 1000` | 12 agents, incl. `ascii-step`, `ci-step`, `code-skeptic`, `docs-specialist` |
| dual-workflow subagent | `<= 15` | `<= 950` | `compose-step`, `reviewer` (`DUAL_WORKFLOW`, `verify-agents.py:87-89`) |
| primary / orchestrator / review lead | `<= 15` | `<= 1100` | `orchestrator`, `review-lead` |
| dsh preset persona, main kind | -- | `<= 1100` (fatal) | `config.text` / `prefix`+`suffix` (`verify-agents.py:104,830`) |
| dsh preset persona, subagent kind | -- | `<= 800` (fatal) | `agentOptions.persona` / `config.persona` |

Counting rules: count instruction-carrying elements (rules + procedure steps +
capability bullets + format items); the conduct and doctrine fragments are
invariant and each counts as ONE element with their bullets stripped before the
count; estimate tokens as `bytes / 4` (`containeromat:docs/rules/42-agent-prompt-standard.md:19-53`).
An element breach fails; a token overage is reported with a recorded reason
(`WARN`, not fatal). Token targets were raised from 650/800/900 to
1000/950/1100 on 2026-09-19 because the two invariant fragments are a fixed
~600-token cost. Skills are exempt from the AP-01 token budget (AP-01 itself
routes mechanics into skills); they are validated for frontmatter, description
length, AP-03 labels and copy identity instead. The calibration record for these
tiers is [standards/model-calibration.md](../../standards/model-calibration.md)
(MC-01..MC-04); the governing row is DeepSeek V4 Pro at roughly 750 constraints.

### AP-02 Required structure (order mandatory)

| Order | Blocks | Carriers |
|---|---|---|
| Standard | role -> hard_rules -> doctrine -> workflow -> conduct -> output (output LAST) | most agents, ports, HA prompts, preset personas |
| Review-track scope variant | role -> hard_rules -> doctrine -> scope -> conduct -> output (`<scope>` in place of `<workflow>`) | the 8 `review-*` tracks |
| Review-lead extended | role -> hard_rules -> doctrine -> workflow -> scope -> merge -> conduct -> output | `review-lead` only (`containeromat:.kilo/agents/review-lead.md:102-172`) |

The library validators enforce orders 1-2; `check_instantiation.py` treats
`scope` as a known extra tag and ignores `merge`
([tooling/check_instantiation.py:47-48](../../tooling/check_instantiation.py)).
Workflow/scope bodies are PROSE -- no `- ` or `1. ` list markers -- so they stay
inside the element budget. `<output>` must be the last top-level block
(`verify-agents.py:237-239`).

### AP-03 Evidence and severity

| Label | Meaning |
|---|---|
| `verified` | source retrieved this session; `path:line` or URL |
| `likely` | derived from repo context, not directly observed |
| `unverified` | retrieval failed or unavailable |

Review/verifier roles define severity inline with one concrete criterion
(H = broken/unsafe, M = rule/spec violation, L = drift). No numeric confidence
self-ratings; the retired three-way `high/medium/low` taxonomy fails the
`check_claim_labels` scan (`verify-agents.py:144-151,936-941`).

### AP-04..AP-06, AP-09..AP-12 (condensed)

- **AP-04 No runtime control-flow markers** -- no round counters, "pass N of M",
  numeric cycle limits; express intent behaviorally ("refine once or state the
  limit").
- **AP-05 Language and hygiene** -- English only (R-040), ASCII only, no
  plan-internal IDs (`F-*` / `A-*` / `P-*` and `plan <10+ digits>`, caught by
  `PLAN_ID_RE`, `verify-agents.py:76`). In-repo agents cite rule IDs and read
  the cited rule; runtimes that cannot resolve rules (AnythingLLM) inline a
  one-line definition at first use.
- **AP-06 Ownership and versioning** -- plugin-generated files use seed-version
  markers with `cp -n` between bumps; `config/ha-orchestrator.config.seed-version`
  backs up the deployed file before replacing, `agent-presets/.seed-version`
  REPLACES preset dirs on a bump (R-042 records "no backup"; the init script
  also snapshots the replaced dir to `<name>.bak-<timestamp>` since 2026-09-18
  -- keep preset customizations in a renamed/copied preset regardless).
- **AP-09 U-shaped ordering** -- hard constraints first, output contract last.
- **AP-10 Least-privilege tools** -- explicit allowlists; never `bash: allow`,
  never unrestricted `edit` outside the documented set (`EDIT_ALLOWED =
  {"compose-step"}`, `verify-agents.py:90`); `task` allowlists name permitted
  subagents only.
- **AP-11 Two-workflow cap** -- at most two labeled workflows; a third is a
  signal to split into a skill or a second agent.
- **AP-12 Single source and anti-drift** -- `.kilo/agents/*.md` is the authoring
  source; `.kilo/kilo.json` is generated by `scripts/render-agent-config.py`
  and asserted with `--check` (`check_mirror`, `verify-agents.py:1606-1617`).
  Never hand-edit the generated block.

### AP-07 Validation

`python3 scripts/verify-agents.py` is the prompt lint (see the enforcement map
in section 5). It checks Kilo agents fully, the 4 ZCode ports, the 8 track
prompts, the 7 dsh HA prompts, the dsh preset personas, the dsh `kilo-review`
roster, model pins and the library canon, and records the element/token counts
in the CHANGELOG. Coverage policy: every preset persona is either required
(`orchestrator`, `reviewer`, `homelab`, `seifomat`) or exempt with a recorded
reason (`anchored-standard`); an unclassified preset fails
(`verify-agents.py:117-125,811-812`).

### AP-08 Conduct fragment and its three variants

Canonical source: [fragments/agent-conduct.md](../../fragments/agent-conduct.md)
(library-canonical from 1.0.0, 2026-10-26; containeromat re-vendors it).
Every carried prompt includes the fragment verbatim; the only documented
adaptations are the final tool bullet:

| Variant | Final bullet | Carriers |
|---|---|---|
| `kilo` (canonical) | "Observe the exact tool allowlist in your frontmatter; never call a forbidden tool." | Kilo agents, ZCode ports, library templates |
| `dsh-ha` | "Never call a tool outside the tool filter granted to you." | the 7 HA subagent prompts |
| `dsh-preset` | "Use only the tools your role needs; in a read-only role never write, edit or run a mutating command." | repo-authored dsh preset personas |

Exactly three variants may exist and each must appear somewhere
(`check_conduct_variants`, `verify-agents.py:944-967`); a stray `<conduct>`
that matches no variant fails. Skills are exempt from carrying the fragment but
still fail on a stray `<conduct>`. `check_conduct` asserts byte-identity for
Kilo agents and ZCode ports; `check_ha_conduct` and `check_preset_conduct`
assert the variants (exact, whitespace-normalized for YAML folded scalars).

### AP-13 Skill invocation discipline

1. **Trigger duty** -- invoke a skill when named or when the task clearly
   matches, before acting; classify first when unsure.
2. **Precedence (repo override)** -- the authority chain above; deliberate
   divergence from Aegis, which ranks user instructions above skills.
3. **Context-pressure re-entry** -- after compaction/resume run the 4-question
   check; load the smallest relevant skill or state why the fast path holds.
4. **Mode declaration** -- `rigid: true|false` in frontmatter, enforced for the
   skills in `SKILL_MODE_REQUIRED` (8 names: `anti-entropy-governance`,
   `first-principles-review`, `verification-before-completion`, `kilo-review`,
   `compose-step`, `seifomat-dev`, `seifomat-dev-debug`, `misakanet`;
   `verify-agents.py:1107-1116`). Unlisted skills are grandfathered.
5. **Rationalization stop-list** -- "I already know this", "too small for a
   process", "loading it would cost context", "follow it from memory", "does
   not really apply" are signals to load, not skip.
6. **Host-neutral bodies** -- no host-only tool/file names (`SKILL` tool,
   `TodoWrite`, `CLAUDE.md`, `.cursor/`, `docs/aegis/`).
7. **Validation** -- forbidden-token + non-ASCII + vendored-header scan over the
   registry's `discipline` roots, plus `references/*.md` parity
   (`verify-agents.py:1317-1379`). Exemptions are name-keyed and self-pruning:
   a row fails once the skill is clean everywhere or gone
   (`SKILL_DISCIPLINE_EXEMPT`, `verify-agents.py:1141-1161`).

### AP-14 Canonical doctrine fragment

Source: [fragments/agent-doctrine.md](../../fragments/agent-doctrine.md):8-26
(library-canonical from doctrine 1.3.0 (current 1.5.0); consumers re-vendor from this tree). The seven
phases (Plan -> PlanReview -> Implement -> Review -> Fix -> Verify -> Push),
their loop back-edges (PlanReview/Fix, Review/Fix and Verify/Fix), the
refinement bound and its plan-review exception, and the responsibility rule
(each prompt carries a per-role phase map; the orchestrating prompt owns the loop
and ledger). Coverage:

| Carrier | Requirement |
|---|---|
| Kilo agents + ZCode ports | fragment verbatim (exact match) |
| dsh HA subagent prompts | fragment verbatim in the JSON `systemPrompt` |
| repo-authored dsh preset personas | fragment verbatim, whitespace-normalized (`anchored-standard` exempt) |
| dsh skills | a `## Doctrine position` section naming served phases + handoffs (identity check only; `check_skill_doctrine`); vendor copies exempt per SK-10 |
| task-execution commands (Kilo, ZCode, dsh) | one `Doctrine:` line naming owned phases + handoff (`check_command_doctrine`) |
| style/status utilities | exempt via `COMMAND_DOCTRINE_EXEMPT` = `caveman`, `orch-status`; a stale exempt row fails (`verify-agents.py:107-112,1687-1697`) |

Per AP-02 the fragment sits at position 3 and the role's workflow becomes the
phase map at position 4 -- replace, never stack. The fragment counts as ONE
element.

### SK-01..SK-14 Skill system standard

Library-owned (2026-10-23), complementing AP-13/AP-14; it does not replace the
upstream R-042 skill rules. Full text:
[standards/skill-system-standard.md](../../standards/skill-system-standard.md).

| Rule group | Requirement | Gate or artifact |
|---|---|---|
| SK-01, SK-02 | One intent per skill; description is the router (25-70 words, user vocabulary, synonyms) | `check_skill_routing.py` + review |
| SK-03, SK-04 | Body <= 1,500 tokens advisory (target 1,200), <= 3 modules, depth in references | `report_skill_shape.py` (body/H2/reference/line metrics); module counts by review |
| SK-05..SK-08 | Canonical anatomy, cite norms instead of duplicating, doctrine position, host-neutral body | review + AP-13/AP-14 scans (vendor exempt per SK-10) |
| SK-09, SK-10 | Five classes (discipline, workflow, tool, vendor, project); vendor bodies frozen | `skills/SKILLS.md` Type column + review |
| SK-11 | >= 3 positive / 2 negative trigger cases per skill (4/2 for new) | `check_skill_routing.py --fail-on-warn` (rank/collision); minimum case counts by review |
| SK-12 | Pressure cases for discipline; dialogue/execution cases for other classes; vendor exempt | `check_behavioral_evals.py` (schema + five required discipline skills; all 19 non-vendor skills have files) |
| SK-13 | Paired no-skill baseline, one change at a time, model/harness/seed recorded | AP-13.8 + eval results |
| SK-14 | Propose, baseline, build, verify, record, retire-by-archive | `PLAN.md`, `skills/SKILLS.md`, `CHANGELOG.md` line |

The shape report is advisory; after R3 no non-vendor body is over the cap, so
promoting it to a failing gate is optional, not urgent. Do not fail a skill on
size alone.

### AS-01..AS-14 Prompt assembly and cache standard

Library-owned (2026-10-23; extended 2026-10-25). It defines where the blocks go,
not what they say: static system message, dynamic user turn, skills as separate
messages, references only when routed, a breakpoint on the last stable block,
stable tool ordering, untrusted data marked as data, measured cache read/write,
a dated minimum/TTL profile, layer order plus first divergent layer,
deterministic serialization, and append-only history with re-versioned
compaction. Full text:
[standards/prompt-assembly.md](../../standards/prompt-assembly.md). Static
checker:
[tooling/check_token_efficiency.py](../../tooling/check_token_efficiency.py).

### SG-01..SG-09 STOPP gate standard

Library-owned pilot (2026-10-23). It preserves the upstream STOPP limits and
adds one instrumented fast path for one-file comment/format/typo edits that
still verifies; the fast path is not yet measured in production.
HALT outranks both. Evidence: `docs/knowledge-base/stop-gate-experiment.md`;
classifier: `tooling/classify_change.py`; consumer patch:
`docs/knowledge-base/consumer-stopp-fastpath.md`.

## 3. R-043 -- the review subagent contract, CR-01..CR-13

| Clause | Requirement |
|---|---|
| CR-01 | Two-stage, read-only: the lead resolves scope, dispatches track children, merges findings, reports; neither lead nor child edits or posts comments |
| CR-02 | Fixed 8-track roster: security, business-logic, deploy-safety, duplication, dead-code, quality, structure, simplicity; deliberate divergence from the built-in 6-track `/review` (performance folded) |
| CR-03 | Effort flags + size tiers: 0 children (<100 lines and `<= 3` files) / 1 security child if sensitive / 3-4 children (100-300 lines or 4-10 files) / all 8 (>300 lines, >10 files, cross-boundary); at most 6 children in the first dispatch message |
| CR-04 | Finding contract `path \| line \| confidence(high) \| why \| finding \| suggestion`, else `NO_FINDINGS`; the lead drops low-confidence/duplicate/no-line/unsupported/pre-existing/out-of-scope findings |
| CR-05 | Severity: CRITICAL = security/auth bypass, data loss, crash, unsafe rollout; WARNING = bug, logic, wrong class/port, exception regression, docs drift; SUGGESTION = non-blocking with a concrete risk |
| CR-06 | Do not duplicate CI gates (compose config, ASCII, key order, placeholders, OIDC.md, R-014 drift, secret lint, tag existence); if CI-only, emit `APPROVE - Nothing to review.` |
| CR-07 | One command bound to the lead agent; the built-in `/review` stays unchanged |
| CR-08 | Scope resolution per mode (uncommitted, staged, commit, unpushed, branch, worktree, pr), exact-ref probing, no `eval`, reject `-`-prefixed targets, no fallback after a worktree metadata failure |
| CR-09 | Fix handoff: the review is advisory; fixes run through `compose-step` under STOPP with explicit authorization, then R-007 closeout |
| CR-10 | UX parity with the built-in `/review` (scope words, effort flags, report skeleton, recommendation values, exact no-changes text); kept deviations: 8 tracks, `**Confidence:** high`, compose-step handoff |
| CR-11 | Uniform read-only catalogue generated from `REVIEW_CATALOGUE` (`verify-agents.py:279-300`), propagated by `--sync-review-catalogue`; `edit: deny` and `task: deny` on tracks; the lead keeps `"*": deny` plus the 8 track names |

Contract enforcement: `check_review_lead`, `check_review_permissions`,
`check_review_rule_sync`, `check_track_consistency`, `check_tier_contract`,
`check_report_contract`, `check_scope_contract`, `check_dsh_roster`,
`check_dsh_scope` (see the map below).

## 4. Fragments: canon direction and byte-exactness

| Fragment | Upstream canon | Library copy | Direction |
|---|---|---|---|
| `agent-conduct.md` + the two dsh variants | library [fragments/agent-conduct.md](../../fragments/agent-conduct.md) | containeromat `.kilo/templates/` | library -> containeromat (re-vendor from 1.0.0) |
| `agent-doctrine.md` | library [fragments/agent-doctrine.md](../../fragments/agent-doctrine.md) | containeromat `.kilo/templates/` | library -> containeromat (re-vendor from 1.3.0 (current 1.5.0)) |
| 25 skill bodies | library [skills/](../../skills/) | runtime copies in containeromat | library -> containeromat (`check_library_canon`) |

Sync rules: fragments are pinned in
[tooling/fragments.manifest.json](../../tooling/fragments.manifest.json);
`tooling/check_fragments.py` verifies hashes in any checkout; `--upstream <dir>`
is a legacy diagnostic, not a gate. Both fragments are library-canonical
(conduct 1.0.0 from 2026-10-26, doctrine 1.5.0). A fragment divergence is a bug,
not a customization; project behavior is tuned through slots
([docs/SYNC.md](../SYNC.md)). The library conforms to R-042/R-043 as pinned at
2026-09-19 and re-vendors on upstream change.

## 5. Enforcement map -- which gate catches which violation

`containeromat:scripts/verify-agents.py` is the single prompt/content verifier;
its summary line names each surface count and every `FAIL <check>:` line names
the drift (`verify-agents.py:1795-1807`).

| Violation | Check (FAIL label) | Source |
|---|---|---|
| Missing/extra/mutated `<conduct>` or `<doctrine>` | `check_conduct` / `check_doctrine` (per agent name) | `verify-agents.py:194-209` |
| Element budget breach / token overage | `check_agent` (`WARN` for tokens) | `verify-agents.py:244-257` |
| Frontmatter missing `description`/`mode`; non-ASCII; plan IDs; output not last | `check_agent` | `verify-agents.py:212-276` |
| Unrestricted `bash`/`edit`/`task`; review tracks not hidden/read-only | `check_agent`, `check_review_permissions` | `verify-agents.py:259-274,331-371` |
| Review catalogue drift / CR-11 region drift | `review-permissions`, `review-rule` | `verify-agents.py:324-398` |
| Track rules/output not byte-identical or duplicate scopes | `review-tracks` | `verify-agents.py:495-519` |
| Lead task allowlist != CR-02; missing `subagent_type`; missing CR-08 citation | `review-lead` | `verify-agents.py:531-563` |
| Tier matrix / report UX / scope guards drift | `tier-contract`, `report-contract`, `scope-contract` | `verify-agents.py:599-689` |
| dsh roster mismatch; skill step-2 base list | `dsh-roster`, `dsh-scope` | `verify-agents.py:566-581,692-713` |
| HA conduct/doctrine variant drift | `dsh-ha` | `verify-agents.py:716-740` |
| Preset persona conduct/doctrine/budget drift; unclassified preset | `dsh-preset` | `verify-agents.py:773-838` |
| Model pin outside the entitlement set; settings.yaml drift | `models` | `verify-agents.py:852-890` |
| Retired three-way confidence label | `labels` | `verify-agents.py:936-941` |
| Conduct block matching no known variant / missing variant | `variants` | `verify-agents.py:944-967` |
| ZCode port missing `tools:` / conduct drift / non-ASCII | `zcode:<name>` | `verify-agents.py:469-489` |
| Bash pattern blocks flag forms; documented verb not allowed | `agent-bash` | `verify-agents.py:431-448` |
| coder global config re-defines project agents | `coder-config` | `verify-agents.py:451-466` |
| Duplicate skill names; skill dir without `SKILL.md` | `skill-names`, `skill-dirs` | `verify-agents.py:1164-1178,1294-1306` |
| Skill copy body diverges from `.kilo` canon | `skill-copies` | `verify-agents.py:1202-1241` |
| `references/*.md` diverges from canon | `skill-references` | `verify-agents.py:1248-1291` |
| `rigid:` missing on gated skill; forbidden host tokens; non-ASCII; vendored without source header | `skill-discipline` | `verify-agents.py:1317-1379` |
| Registry invalid / unregistered on-disk root / declared check derives no files | `skill-registry` | `verify-agents.py:1382-1432` |
| Runtime copy diverges from the library canon; missing mirrored file | `skill-library` | `verify-agents.py:1481-1554` |
| Dangling rule/agent/skill reference in a prompt | `references` | `verify-agents.py:1593-1603` |
| Generated `kilo.json` drift | `kilo.json` | `verify-agents.py:1606-1617` |
| SKILL.md frontmatter does not YAML-parse | per-file FAIL | `verify-agents.py:1447-1478` |
| dsh skill missing `## Doctrine position` | `dsh-skill:<name>` | `verify-agents.py:1658-1669` |
| Command missing `Doctrine:`; stale exempt row | `command:<rel>`, `command-doctrine-exempt:<name>` | `verify-agents.py:1672-1698` |

CI / local battery (`containeromat:scripts/ci-replica.sh --fast` replays the
compose-validate gates): shellcheck + `bash/sh -n` + CSC-21 Usage headers, shfmt
`-d -i 2 -ci -bn` (CSC-20), ASCII validation + normalization gate, ruff, Python
`py_compile`, helper contract tests (`.forgejo/scripts/tests/run.sh`), dependency
coverage, skills manifest, seed-marker drift, workflow hygiene. Prompt-related
steps: `Agent prompt lint (R-042/R-043)`, `Prompt drift hunt (F9)`,
`Prompt lint (R-038)`, `dsh skill seed-marker drift`, `Skill frontmatter`,
`Skills identity manifest`
(`containeromat:.forgejo/workflows/compose-validate.yml:114-131,456-492`;
`containeromat:scripts/ci-replica.sh:102-113,272-283`).

Seed gates: `scripts/verify-skills-seed-version.sh` fails a change under a
seeded skills root without a `.seed-version` bump
(`containeromat:scripts/verify-skills-seed-version.sh:1-33`);
`scripts/skills-manifest.py` verifies tree hashes per root.

## 6. Exemption registers (all self-pruning)

| Register | Location | Scope |
|---|---|---|
| `SKILL_COPY_EXEMPT` | `verify-agents.py:1096-1101` | documented copy divergences (2 rows) |
| `SKILL_MODE_REQUIRED` | `verify-agents.py:1107-1116` | skills that must declare `rigid:` (8) |
| `SKILL_DISCIPLINE_EXEMPT` | `verify-agents.py:1141-1161` | grandfather + shim rows (12) |
| `PRESET_CONDUCT_EXEMPT` | `verify-agents.py:121-123` | `anchored-standard` |
| `COMMAND_DOCTRINE_EXEMPT` | `verify-agents.py:109-112` | `caveman`, `orch-status` |
| `no-trigger-cases` (WARN by default) | [tooling/check_skill_routing.py](../../tooling/check_skill_routing.py) | a skill without a Tier-2 trigger case file; `--fail-on-warn` promotes it |

A stale row (no matching file or no longer violating) FAILS, so the lists prune
themselves; adding a silent skip is forbidden
(`containeromat:docs/runbooks/prompt-audit.md:60-63`).
