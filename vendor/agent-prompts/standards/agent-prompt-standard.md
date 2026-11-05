# Agent and subagent prompt standard

Generalized from containeromat `docs/rules/42-agent-prompt-standard.md` (pinned 2026-09-19).
Upstream: containeromat R-042.

**Class: prompt-generation.** Applies to prompts embedded in agent runtimes that
are NOT retrieval-workspace prompts (the workspace system-prompt standard governs
those):

- high-availability subagent prompts in a runtime config
- agent-preset personas
- skill bodies
- agent-registry entries (the project's agent files)
- any future agent/subagent system prompt

The project maps these AP-* rules into its own rule registry and verifier.

## AP-01 -- Instruction budget

- The scientific variable is instruction count, not tokens (Curse of Instructions,
  ICLR 2025; see the workspace system-prompt standard, principle 1). Count every
  instruction-carrying element (rules + procedure steps + capability bullets +
  format items). Estimate tokens as `bytes / 4`.
- Exact element count used by the library validator (mirrors
  `docs/TEMPLATE-GUIDE.md`): 1 (role) + every list-marker line (`^- ` /
  `^\d+. `) outside `<doctrine>` and `<conduct>` + 1 (doctrine) + 1 (workflow) +
  1 (conduct) + 1 (output). `<doctrine>` and `<conduct>` bullets are excluded
  from the marker scan and each block counts as its own single element; output
  list markers are already counted by the global marker scan, so the output
  block adds exactly its own 1 and no separate output term.
- The canonical conduct fragment (AP-08) and the canonical doctrine fragment
  (AP-14) are invariant across agents and each counts as one element; do not
  double-count their bullets.
- Tiers (instruction elements are the hard budget; tokens are a cost guardrail,
  reported per prompt in the project's changelog):
  - standard subagent: <= 12 elements; token target <= 1000.
  - subagent carrying two intrinsic workflows (e.g. change execution +
    diagnostics): <= 15 elements; token target <= 950, with the reason recorded
    in the changelog. A review role that carries two intrinsic output contracts
    (diff review + diagnostic review) is registered in this tier too.
  - primary agent / orchestrator / review lead: <= 15 elements; token target
    <= 1100.
  - An element breach blocks; a token overage is reported and justified.
  - Token targets were raised from 650/800/900 on 2026-09-19: the invariant
    conduct (AP-08) and doctrine (AP-14) fragments are a fixed ~600-token cost
    in every prompt, so the advisory guardrail moves with that baseline and
    stays meaningful.
- **Model-tier calibration (2026-10).** These tiers are calibrated to the weakest
  supported target, not a statement about model capability. The 2026 capacity
  replication (S2) shows the capacity ceiling is model-specific: DeepSeek V4 Pro
  starts dropping constraints near 750, while frontier models track thousands
  (`standards/evidence/prompt-research-2026-10.md`, S2). Do not raise a budget
  because a frontier model can absorb it. Record the target model and its
  measured capacity, and re-baseline when the model or harness changes. Raising
  a budget requires a paired eval, not an argument. The calibration record and
  protocol live in `standards/model-calibration.md` (MC-01..MC-04).
- Long operational runbooks do not belong in a prompt. Move mechanics into tool
  descriptions, skills or docs; keep only WHEN-triggers and constraints.
- Prefer merging over deleting: removing a behavioral requirement to save tokens
  is a regression, not an optimization.
- Preset personas are budgeted by **schema kind**: the persona-plugin prompt
  (`config.text`, or the `prefix`/`suffix` pair) is "main" (1100);
  `agentOptions.persona` or `config.persona` is "subagent" (800). Budget by
  kind, never by a node id. (Raised from 900/650 on 2026-09-19: the canonical
  doctrine fragment (AP-14) was added to every persona, and the preset token
  check is fatal, so the tier had to move with it.)
- Skills are **exempt from an AP-01 token budget** -- AP-01 itself routes
  mechanics into skills. A skill is validated instead for frontmatter
  (`name`/`description`), description length, AP-03 labels, and generated-copy
  identity; never impose a prompt budget on it. Skill shape is governed
  separately by `skill-system-standard.md` (SK-03) as a cost signal, not by
  this budget.

## AP-02 -- Required structure (order mandatory)

1. **Role** -- one sentence, function not persona, no adjectives.
2. **Hard rules / constraints** -- the highest-priority behavioral limits first,
   including the non-goals: what this role must not change, must not touch, and
   must not decide. A role with no stated non-goal reads as permission.
3. **Doctrine** -- the canonical orchestrated-workflow fragment (AP-14),
   verbatim; the one binding task workflow.
4. **Workflow** -- the role's phase map (which doctrine phases this role owns,
   what it hands off, written as prose -- no list markers, so it stays inside
   the AP-01 element budget); at most two workflows (AP-11); further workflows
   belong in a skill.
5. **Conduct** -- the canonical fragment (AP-08), verbatim.
6. **Output contract** -- exact schema/format plus the null-findings rule, LAST.

## AP-03 -- Evidence and severity

- Review/verifier roles define every severity level inline with one concrete
  criterion (e.g. H = broken/unsafe, M = rule/spec violation, L = drift) and cite
  evidence per finding.
- Research/claims label each claim `verified` (evidence from this run:
  path:line, URL, or command output), `likely` (partial evidence), or
  `unverified` (no evidence available). Never cite upstream facts from memory.
- No numeric confidence self-ratings.

## AP-04 -- No runtime control-flow markers

No round counters, loop state, "pass N of M", or numeric cycle limits in system
prompts -- they go stale on every run and can trigger abort behavior (see the
workspace system-prompt standard, derivation guide). Express the intent
behaviorally: "if unresolved, refine once or state the limit", not "after 2
cycles".

## AP-05 -- Language and hygiene

- English only (see the English-only mandate). ASCII only so greps and diffs
  stay clean.
- No plan-internal IDs in any prompt: legacy plan-phase markers and the modern
  `plan <10+ digits>` form are both caught by the project's plan-ID scan.
- Runtimes that can read the project's rule files: cite the rule ID and
  instruct reading the cited rule before applying it; inline definitions are not
  required because the rule set is available at runtime.
- Runtimes that cannot resolve rules (retrieval workspaces): every rule ID
  carries an inline one-line definition at first use.

## AP-06 -- Ownership and versioning

- Workspace prompts: new versioned file per change; never edit a released file
  in place.
- Runtime-generated files: seeds use a seed-version marker with a no-clobber
  copy between bumps. A generated file is backed up to a timestamped `.bak`
  before it is replaced; a bump that REPLACES seeded directories leaves no
  backup, so keep local customizations in a renamed/copied preset.
- When the runtime provider owns the file, use the documented hand-edit path.

## AP-07 -- Validation

- Workspace prompts: the project's workspace-prompt verifier runs the hard
  checks.
- Agent prompts: the project's agent verifier checks agent-registry prompts
  fully, the ported copies for conduct/ASCII, the track prompts for shared-block
  byte-identity, the runtime personas for the adapted conduct variant and their
  AP-01 budgets, and the review roster against the review contract -- and
  records the instruction-element count and token estimate in the project's
  changelog. It also runs the AP-13 skill-discipline scan over the skill bodies
  and their reference files.
- Coverage policy: every persona is either **required** (must carry the preset
  conduct variant) or **exempt** with a recorded reason (an anchored copy or an
  upstream copy); an unclassified preset fails, so a new preset cannot silently
  escape the policy. Exempt presets are still persona-counted and
  budget-checked. Skills are checked for frontmatter/description and AP-03
  labels, never for the conduct fragment.
- The project's verification closeout includes the prompt lint whenever prompts
  or ported prompt copies change.

## AP-08 -- Canonical conduct fragment

- The canonical conduct fragment file in the project's prompt library is the
  single source for the shared conduct block: injection guard, evidence duty,
  secret redaction, language/hygiene, and the tool-allowlist reminder.
- Every agent prompt includes that fragment verbatim. No agent restates, trims
  or edits it. The project's config renderer renders it into the generated
  runtime config; the project's verifier asserts byte-identity across the agent
  prompts and their ports.
- High-availability subagents use the same fragment with only the final tool
  bullet adapted: "Never call a tool outside the tool filter granted to you."
  The project's verifier derives and checks that variant; bump the seed-version
  marker whenever the fragment changes.
- Runtimes whose schema grants no per-subagent tool filter use the same fragment
  with a different final bullet, because that schema must not claim a filter it
  cannot grant: "Use only the tools your role needs; in a read-only role never
  write, edit or run a mutating command." That is the second and last documented
  adaptation; the verifier checks it per persona along with the AP-01 budget,
  and a persona that carries a conduct block but yields no persona fails rather
  than skipping.
- Every persona form is covered, including the `prefix`/`suffix` form collected
  as a "main" persona, so runtime-native presets are covered, not skipped. A
  skill is explicitly exempt from the fragment -- it executes inside a
  conduct-carrying agent and the fragment's tool-allowlist bullet would be wrong
  for it -- but a stray conduct block in a skill still fails unless it matches a
  known variant.

## AP-09 -- U-shaped ordering

Hard constraints first, output contract last (Lost in the Middle, TACL 2024;
attention sinks). Behavioral limits go before the workflow; the output schema
goes after it, so both ends of the prompt carry the rules that matter most.

## AP-10 -- Least-privilege tools

- Give each agent an explicit allowlist under a deny-by-default posture: an
  unnamed tool is unavailable, not optional. Never grant an unrestricted shell
  and never an unrestricted edit unless the agent's job requires it.
- Subagent dispatch allowlists name the permitted subagents only.
- Tool mechanics belong in tool descriptions, never duplicated in prose.

## AP-11 -- Two-workflow cap

At most two workflows per agent prompt. A third workflow is a signal to split
into a skill or a second agent.

## AP-12 -- Single source and anti-drift

- The project's agent registry files are the authoring source; the generated
  runtime config is produced by the project's config renderer and never
  hand-edited.
- The generated config strips frontmatter from the prompt (the body is the
  system prompt) and preserves each agent's model/variant.
- The project's verifier fails on a stale mirror, a missing conduct fragment, a
  plan-internal ID, or a budget breach.

## AP-13 -- Skill invocation discipline

Source: distilled from the Aegis `skills/using-aegis/references/skill-discipline.md`
(MIT, pinned `5b16eb9a`, adapted 2026-09-15). Host-only mechanics (a specific
skill-loader tool, task tracker, or workspace path) are dropped; the project
authority chain is kept.

- **AP-13.1 Trigger duty** -- invoke a skill when the user names it or the task
  clearly matches it, *before* acting. When relevance is uncertain, classify the
  task first and load only the matching skill; never load a skill to appear
  thorough.
- **AP-13.2 Precedence (project override)** -- the authority chain is
  `HALT (HF-01..HF-15) > STOPP (S-1..S-5; fast path per SG-01..SG-09) >
  communication > topic rules > user request`. A skill never overrides a HALT/STOPP rule or the English-only
  mandate. **Deliberate divergence from Aegis:** upstream ranks user
  instructions above skills above the system prompt; this library inverts that
  ordering. Importing the upstream user-first precedence unchecked would let a
  skill bypass a halt condition or the language mandate, so the project chain
  wins, and a skill that conflicts with it is wrong for the project.
- **AP-13.3 Context-pressure re-entry** -- after compaction/resume or a
  work-type change, run the 4-question re-entry check: what type of task is
  this; is a skill relevant; does it need skill discipline; load the smallest
  relevant skill, or state why the fast path holds. Do not broaden a skill's
  description to mask a missed trigger.
- **AP-13.4 Mode declaration** -- every skill declares `rigid: true|false` in
  its frontmatter. It is enforced for the skills in the project's mode-required
  set; existing skills are grandfathered and migrated opportunistically, so an
  unlisted skill does not fail. That set is the enforcement surface -- add a new
  gated skill to it explicitly, because the check cannot discover a skill that
  simply omits the key.
- **AP-13.5 Rationalization stop-list** -- the red flags that mean "stop and
  invoke the skill": "I already know this", "the task is too small for a
  process", "loading it would cost context", "I will follow the skill from
  memory", "the skill does not really apply". Each is a signal to classify and
  load, not a reason to skip.
- **AP-13.6 Host-neutral bodies** -- a skill body names no host-only tool or
  file (a specific skill loader, task tracker, or agent-workspace path).
  Different runtimes load skills through different facilities; a body written
  for one host must not break on the other. Ties to AP-05 (hygiene) and AP-10
  (tool mechanics live in tool descriptions).
- **AP-13.7 Validation** -- the project's skill-discipline check fails on: a
  mode-required skill whose frontmatter has no `rigid:` key; a forbidden
  upstream/host token in any `**/*.md` under a discipline root; non-ASCII bytes
  in those files; a vendored file (a `# Source:` line containing `vendored`, or
  a `# Vendored:` line) without a `# Source:` header. The scan roots are
  registry data (a skills-roots registry); add a new root explicitly. Copied
  `references/*.md` files are parity-checked against their canon. The scan
  surface is the markdown prompt surface -- `SKILL.md` and `**/*.md` resources
  -- not non-markdown helper scripts a skill may ship. Exemptions are
  name-keyed and self-pruning: one row grandfathers a skill across every copy
  in every discipline root, and a row still fails once its file disappears or
  no longer violates.
- **AP-13.8 Behavior-change evidence** -- a skill or behavior-shaping prompt
  edit needs a baseline run that shows the failure, then a post-change
  compliance check; record the rationalization the baseline exposed. Static
  gates alone do not prove the edit changed behavior. A new artifact, or a first
  structural edit of an existing artifact, may defer the baseline once, with a
  dated record that names the owner and the follow-up item in the evaluation
  doc; a deferral is not evidence and must be closed before the artifact is
  treated as validated.

## AP-14 -- Canonical doctrine fragment (orchestrated workflow loop)

Added 2026-09-19; loop revision 2026-10-24 (operator-directed doctrine: every
task runs the orchestrated loop); plan-review gate 2026-11-03 (doctrine 1.5.0:
every spec is reviewed before it is implemented).

- The canonical doctrine fragment file is the single source for the shared
  `<doctrine>` block: the seven phases (`Plan`, `PlanReview`, `Implement`,
  `Review`, `Fix`, `Verify`, `Push`), the loop transitions (PlanReview/Fix,
  Review/Fix and Verify/Fix back-edges), the refinement bound and its
  plan-review exception, and the responsibility rule (each prompt carries a
  per-role phase map; the orchestrating prompt owns the loop and ledger so no
  phase is skipped end-to-end). `Ready`, `Ready (unverified)`, `Done`, and
  `HALT` are outcomes, not phases.
- Vocabulary aliases are fixed: **Research is inside Plan** (the research gate
  ends at a decision-complete spec); **Plan review is the spec gate** (mandatory,
  repeating until clean, `workflow-loop.md` WL-15); **Review is the audit gate**;
  **Push is the finalize gate** (operator approval plus evidence, harness, model,
  and closeout). There is no separate Research or Finalize phase.
- Every **library** agent prompt, every ported copy, every high-availability
  subagent prompt and the repo-authored preset personas carry the fragment
  verbatim; the project's verifier asserts identity (exact match for the
  markdown/JSON surfaces, whitespace-normalized for YAML folded persona scalars).
  Live consumer copies are outside this repository and must be re-vendored; an
  upstream-copy persona may be exempt with a recorded reason.
- Per AP-02, the fragment sits at position 3 and the existing workflow content
  becomes the role's phase map at position 4 -- replace, never stack, so the
  AP-01 element and token budgets hold.
- Fragment bullets are stripped before the element count (mirroring the AP-08
  conduct stripping) and the fragment counts as ONE element.
- Runtime skills carry a `## Doctrine position` section instead (phases the
  skill serves + entry/exit handoffs); skills are exempt from fragment identity
  and the AP-01 budget, but the section is mandatory and checked. Vendor copies
  are the one exception (SK-10): a frozen third-party body is not required to
  carry the section.
- Task-execution commands carry one `Doctrine:` line naming owned phases +
  handoff. Style/status utilities are exempt via a self-pruning exemption set;
  a missing row for a new command fails, so an exempt command must be named.

## Cross-refs

- `workflow-loop.md` -- canonical loop state machine (WL-01..WL-15)
- `code-review-contract.md` -- review subagent contract (CR-01..CR-13)
- `skill-system-standard.md` -- skill anatomy, classes, and lifecycle (SK-01..SK-14)
- `stop-gate.md` -- STOPP fast path and gate classifier (SG-01..SG-09)
- `model-calibration.md` -- target model capacity and re-baseline protocol (MC-01..MC-04)
- `prompt-assembly.md` -- static prefix, dynamic user turn, cache contract (AS-01..AS-14)
- `subagent-delegation.md` -- delegation gates and handoff contract (SD-01..SD-12)
- `agent-context-files.md` -- repository context file rules (CF-01..CF-10)
- `halt-taxonomy.md` -- HALT mechanism and STOPP interaction (HF-01..HF-15)
- `english-only.md` -- the language mandate (EN-01..EN-04)
- `evidence-duty.md` -- live-fetch and validation duty
- `verification-integrity.md` -- what a gate verdict must contain (VI-01..VI-15)
- `prompt-security.md` -- trust classes and untrusted-data handling (PS-01..PS-14)
- `agent-adapter.md` -- runtime projection and capability admission (AD-01..AD-12)
- `system-prompt-standard.md` -- workspace prompt standard (the 7 principles)
- `../fragments/agent-conduct.md`, `../fragments/agent-doctrine.md` -- the
  canonical fragments (AP-08, AP-14)
