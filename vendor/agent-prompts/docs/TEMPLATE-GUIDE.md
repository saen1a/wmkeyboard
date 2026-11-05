# Template guide

Normative for every file under `agents/` and `prompts/tasks/` (fragments are pinned byte-exact). `commands/` are thin dispatchers: they carry a single `Doctrine: ` line and are not skeleton-validated.

## Metadata frontmatter (required fields)

```yaml
type: role | task              # role = agent template (default); task = task-shaped template
id: {domain}-{slug}            # domain: orchestration|engineering|design|review|research|documentation|operations|networking|tabletop
name: <human name>
domain: <domain>
purpose: <one line, matches the <role> sentence intent>
status: stable | draft | speculative
version: 2.4.0                 # semver; bump on slot-contract or fragment change
source_archetypes: ["<containeromat file:line>", "[NEW]"]
runtimes: [kilo, dsh]
budget_tier: standard | dual-workflow | primary   # elements <= 12 / 15 / 15; tokens <= 1000 / 950 / 1100 (advisory)
tool_profile: orchestrator | read-only | gated-write | doc-write | batch-write
owned_phases: [Plan, PlanReview, Implement, ...]  # artifact ownership, not permission; the plan-review gate sits before Implement; review-only roles list PlanReview and Review; read-only research may own non-mutating Implement/Fix; never Push
handoff: <where the role hands off>
evidence_style: none | claim-label | severity | both
required_slots: [PROJECT_ID, PROJECT_RULES, VERIFICATION_COMMANDS, ...]
optional_slots: [...]
conduct_variant: kilo | dsh-ha | dsh-preset | omp
fragment_versions: {doctrine: 1.5.0, conduct: 1.1.0}
suggested_projects: [containeromat, seifomat, pen-and-paper, network-architecture, general-research]
created: 2026-09-19
updated: 2026-09-19
```

## Body skeleton (order mandatory; `output` last)

```
<role>
{{ROLE_SENTENCE}} -- one sentence, function only, no persona adjectives.
</role>

<hard_rules>
- {{WORKSPACE_SCOPE_RULE}}: work only in the {{PROJECT_ID}} workspace; if the
  workspace is not {{PROJECT_ID}}, report and stop.
- {{PRECEDENCE_AND_RULES_RULE}}: read {{PROJECT_RULES}} before applying any
  cited rule; project rules > framework best practice > model memory.
- {{MUTATION_POLICY}}
- {{SAFETY_RULE}}: never echo secrets; never commit, push or deploy (unless the
  role owns Push).
- {{STOP_AND_ESCALATION_RULE}}: if the task exceeds ~3 files / ~50 net lines or
  acceptance criteria are ambiguous, emit BLOCKED with at most three questions;
  refine once before escalating. No counters.
</hard_rules>

<doctrine>
Binding workflow loop: Plan -> PlanReview -> Implement -> Review -> Fix -> Verify -> Push.
Run owned phases; the orchestrator owns the loop and ledger.
- Plan includes research: gather until the spec is decidable; blocked
  -> HALT. Implement with one writer per shared surface; no parallel writers.
- PlanReview is the spec gate and is never skipped: a verifier who did not write
  the spec checks goal, request coverage, acceptance, verification, ownership and
  order, and named halt risks; an open high/medium finding goes Fix -> PlanReview
  until a round is clean, each round stating CHANGED, and a round that changes
  nothing is HALT (stalled).
- Review is the audit gate: a clean-context verifier reads the artifact,
  acceptance, and evidence commands, not author reasoning;
  open high/medium findings go Fix -> Review.
- Verify runs the proof commands fresh and reads the output and exit code; a
  failure goes Fix -> Review -> Verify. A pass is a record: named verifier
  (never the author), command, exit, freshness; skipped work is unverified and
  narration or a stub is not an artifact.
- Push is finalize: only on operator "go"; record evidence, harness/model/closeout.
  Stop at Ready without go; HALT terminal.
One refinement per code gate, then escalate. The author is never sole verifier: use a
mechanical check or record an exemption; mark it unverified. Evidence at every transition.
</doctrine>

<workflow>
Phase map ({{ROLE_LABEL}}), prose: Plan -- ... PlanReview -- the spec gate, no
open high or medium plan finding ... Implement -- ... Review -- ... Fix -- ...
Verify -- ... Push -- ...
</workflow>

<conduct>
-- copy fragments/agent-conduct.md block, byte-exact (variant per conduct_variant) --
</conduct>

<output>
{{OUTPUT_CONTRACT}} -- exact schema; review/verifier roles define severity
H/M/L inline or use claim labels (verified/likely/unverified); null-findings
rule explicit.
</output>
```

## Hard rules

1. Project-owned text uses `{{SLOTS}}`; library-owned text is resolved prose.
   Templates may carry slots; instantiations must not.
2. `<workflow>` is PROSE -- no `- ` / `1. ` markers. The element count is
   exact: 1 (role) + every list-marker line (`^- ` / `^\d+. `) outside
   `<doctrine>` and `<conduct>` + 1 (doctrine) + 1 (workflow) + 1 (conduct) +
   1 (output), <= 12 standard tier. Output list markers are already counted by
   the global marker scan, so the output block adds exactly its own 1 and no
   separate output term.
3. `<doctrine>` and `<conduct>` are copied byte-exact from `fragments/`;
   never edited. The conduct variant differences are the tool bullet and the
   closing hygiene bullet only.
4. ASCII + English. No plan-internal IDs. No host-only tool references. No
   runtime control-flow markers (counters, "pass N of M").
5. Read-only roles (`tool_profile: read-only`) must not describe mutating
   tools in their contracts. Offensive security is out of scope everywhere;
   security roles are defensive read-only review.
6. At most two labeled workflows inside the phase map.
7. Review/verifier roles: null-findings rule explicit in `<output>`.

## Rejected alternatives

Every new or changed role template, task template, and standard records the
alternatives it deliberately did not take, each with the reason. The corpus was
not retrofitted: 4 of 22 standards carry such a section, and no validator
enforces its presence, so a missing section in an untouched file is not a defect. A rejected
alternative that carries a reason is a durable design decision: the next reader
sees why the obvious-looking option was refused and does not reopen it. An
unrecorded rejection is re-litigated every quarter, usually by someone who has
the same good idea the author already tested and discarded.

Record it in whichever of the two shapes fits the artifact. A standard or a long
template uses a table:

| rejected | why |
|---|---|
| Put project-owned commands in the library body | A command that names one host leaks into every instantiation and cannot be reused without editing the shared text, which defeats the slot contract |
| Let the model choose the output schema per run | A schema that is not fixed cannot be graded, so evidence from two runs cannot be compared |

A short template uses a bullet list, one line per alternative:

- Put project-owned commands in the library body -- a command that names one
  host leaks into every instantiation and defeats the slot contract.
- Let the model choose the output schema per run -- a schema that is not fixed
  cannot be graded, so evidence from two runs cannot be compared.

Record an alternative only when someone actually proposed it: the author, a
reviewer, an operator, or a named upstream source. A hypothetical objection
invented to fill the section is noise and defeats the purpose, which is to stop
a real proposal from returning. State the reason as the property that makes the
alternative fail, not as a preference.

## Skills

Skills are not role templates: they are loaded on demand and validated by a
different gate. Use [SKILL-TEMPLATE.md](SKILL-TEMPLATE.md) and
[standards/skill-system-standard.md](../standards/skill-system-standard.md)
(SK-01..SK-14). The short version: description 25-70 words and is the router;
body target 1,200 tokens (1,500 advisory cap), at most three modules; depth in
`references/`; `## Doctrine position` present; cite standard IDs instead of
copying them. Measure with `python3 tooling/report_skill_shape.py`.

## Worked instantiation example

See `CATALOG.md` (frontend-developer row) and `provenance/` for the full
worked `eng-frontend-developer` instantiation used to calibrate the skeleton.
