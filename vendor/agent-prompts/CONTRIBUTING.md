# Contributing

1. **Justify the role.** A new template must recur in at least two target
   projects (or serve a planned project explicitly listed in `PLAN.md`) and
   have a distinguishable phase map + tool profile.
2. **Pick the domain** (orchestration, engineering, design, review, research,
   documentation, operations, networking, tabletop) and the id
   (`{domain}-{slug}`).
3. **Cite archetypes** (`source_archetypes` frontmatter: `file:line` of the
   assets the template generalizes) or mark `[NEW]`. `status: draft` means the
   template generalizes an existing archetype whose shape is settled;
   `status: speculative` means it was authored from first principles. Both
   require the validator gate green, and a template becomes `stable` only after
   a project uses it end-to-end.
4. **Follow the skeleton** (see any existing template): metadata frontmatter,
   role, hard_rules, doctrine (byte-exact from `fragments/`), workflow (prose
   phase map, no list markers), conduct (byte-exact variant), output last.
5. **Respect budgets**: <=12 elements standard tier (15 dual/primary);
   fragments count once each. Prefer merging over stacking.
6. **No runtime control-flow markers** (counters, "pass N of M"). Behavioral
   wording only.
7. **ASCII + English.** No plan-internal IDs. No host-only tool references.
8. Run `make gate` (or `tooling/gate.sh`) -- it runs template validation,
   fragment hashes, workflow-loop checks, the long-horizon gate, the findings
   ledger check, the run journal check, the token-efficiency gate, the tool-set
   gate, pytest, the test floor, skill routing, behavioral schema, and the
   skill-shape report. All must pass. A fragment or slot-contract change bumps the template `version` and
   the `updated` date. Update `CATALOG.md` (selection matrix row + index
   entry). Review-domain templates follow
   `standards/code-review-contract.md` (CR-01..CR-13).
9. A change to `standards/long-horizon-runs.md` or
   `standards/run-state.schema.json` must keep `check_long_horizon` green and
   update the schema version, the standard, `CATALOG.md`, and
   `exemplars/run-state-example.md` together.
10. Install `requirements-dev.txt`; `.forgejo/workflows/gate.yml` runs
    `make gate` on push and pull request.
11. A change to `standards/prompt-assembly.md` or
    `standards/cache-profiles.json` must keep `check_token_efficiency` green and
    update the profile version, the date, the CATALOG pin, and the profile pin:
    `python3 tooling/check_token_efficiency.py --update-pin`.
12. A change to `standards/run-journal.schema.json`,
    `tooling/check_run_journal.py`, or `tooling/check_findings_ledger.py` must
    keep both example checks green and keep the schema/checker contract sets in
    parity (`tooling/tests/test_check_run_journal.py`).
13. A rule range quoted in a live document must match its standard:
    `python3 tooling/check_doc_ranges.py` fails when a range claims a rule that
    does not exist, and when a `XX-01..XX-NN` range ends short of the family's
    real count. A deliberately partial range of that shape carries the literal
    marker `[subset]` on the same line -- for example when a rule means "every
    rule except the finalize one". Historical records (`CHANGELOG.md`, `PLAN.md`,
    `standards/evidence/`, `provenance/`, `packs/`, frozen role-AB arms, dated
    knowledge-base records) are not scanned.
14. A change to `standards/tool-set.schema.json` or
    `tooling/check_tool_set.py` must keep the example manifest valid:
    `python3 tooling/check_tool_set.py exemplars/tool-set-example.json`.
14. A change to `standards/verification-integrity.md`,
    `standards/gate-verdict.schema.json`, or `tooling/check_gate_verdict.py`
    must keep the worked verdict valid:
    `python3 tooling/check_gate_verdict.py exemplars/gate-verdict-example.json`,
    and the schema/checker contract sets in parity
    (`tooling/tests/test_check_gate_verdict.py`).
15. A change to `standards/prompt-security.md` or
    `tooling/check_prompt_security.py` must keep
    `python3 tooling/check_prompt_security.py` clean over every prompt asset; a
    new hostile-pattern family is added to the checker, its tests, and
    `skills/general/untrusted-content-handling/references/patterns.md` in the
    same change. A pattern that fires is fixed in the asset, not exempted; the
    quote exemption list is closed and may not grow to hide a real hit.
16. A change to `standards/workflow-loop.md`, `standards/gate-verdict.schema.json`,
    or `tooling/check_gate_verdict.py` must keep the loop guards executable:
    `python3 evals/loop/drive.py --verify` is a gate step, every scenario in it
    states its expected decision, and a guard that stops rejecting a bad record
    fails the exercise. A new transition or gate type adds its scenario there and
    its per-gate minimum in the WL-09 table in the same change.
17. A change to `standards/agent-adapter.md`,
    `standards/agent-admission.schema.json`, or `tooling/check_admission.py`
    must keep every record valid:
    `python3 tooling/check_admission.py omp/admission.json` and the same for
    `dsh/admission.json`. A runtime version change invalidates its `supported`
    claims until re-verified; adding a projection means adding its record.

Rule references inside templates use project slots (`{{PROJECT_RULES}}`) --
never another project's rule IDs.

## Adding a skill

1. Justify the class and the gap: a repo-authored workflow or tool skill must
   recur in at least two target projects (or a listed planned project), cover
   one intent cluster, and own an intent no existing description claims. A
   one-off procedure is a doc, not a skill.
2. Start from `docs/SKILL-TEMPLATE.md` and follow
   `standards/skill-system-standard.md` (SK-01..SK-14): description 25-70
   words, body target 1,200 tokens (1,500 cap; hard for non-vendor, advisory for vendor), at most three modules,
   depth in `references/`, `## Doctrine position`, no duplicated norms.
3. Ship `evals/trigger/<skill>.json` with at least 3 positive and 2 negative
   cases (4 positive for a new skill), and a behavioral or execution case for
   the class (SK-12).
4. Run `python3 tooling/report_skill_shape.py`, `check_skill_routing.py
   --fail-on-warn`, `check_behavioral_evals.py`, and `validate_templates.py`.
5. Record the before/after shape and the paired baseline in the change record
   (SK-13, AP-13.8). A shape change without a baseline is a style change.
6. Add the row, Type, and references to `skills/SKILLS.md`; add a `PLAN.md`
   wave entry.

## Coupling policy

Frontmatter `suggested_projects` MAY name projects (advisory metadata), and
`source_archetypes` citations MAY cite upstream paths. Everything else in bodies
and standards must be project-neutral: no project name, path, rule ID or host
fact outside those two fields. Index documents (`skills/SKILLS.md`) may name
live instance paths in their reference-only sections, and `dsh/README.md` may
name the deployed stack layout in its pairing text.

Consumers gate their instantiations with
`python3 tooling/validate_templates.py --root <project> --instantiate`
(see docs/INSTANTIATE.md).
19. A change that touches the loop must keep the two loop gates green:
    `python3 tooling/check_plan_spec.py` on every `provenance/plan-*.md` and the
    example spec, and `python3 tooling/check_loop_gate.py --ledger
    'provenance/ledger-*.md' --verdict 'provenance/verdict-*.json'`. A new unit
    writes its spec (WL-15 shape, `docs/PLAN-SPEC.md`), its plan-review rounds
    (`exemplars/gate-verdict-plan-review.json`), and one WL-08 row; a unit that
    reached Implement without a clean plan-review record fails the gate.
18. A live document quotes a number from `docs/measured-state.md`, or points at
    it -- never a value copied by hand. After a change that moves any measured
    quantity (tests, shapes, carriers, cases, assets, versions), run
    `python3 tooling/measure_state.py --write`; `make gate` runs `--check` and
    fails on drift. Dated changelog entries keep their own measurement and name
    the pass they measured.
