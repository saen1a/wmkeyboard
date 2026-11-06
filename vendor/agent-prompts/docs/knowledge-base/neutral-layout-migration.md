# Neutral layout migration plan (agents/ + prompts/)

Status: completed in 2.0.0; legacy shims removed.

## Decision

Adopt `agents/` and `prompts/` as the visible, vendor-neutral canonical names
for 2.0.0. The old `roles/`, `tasks/`, and `workspace-prompts/` roots were moved
and their compatibility shims were removed at the 2.0.0 release.

The move is a cross-cutting rename, not a prompt fix:

- 7 tooling sites resolve `roles/` or `tasks/` directly.
- 17 documentation/config files reference the paths.
- `evals/role-ab` is keyed by role basename and its historical results record
  `roles/...` strings.
- The consumer pins this tree as a submodule and maps `.kilo/agents/*` to
  `roles/<domain>/`; a rename changes its re-vendor contract.

## Target layout

```text
AGENTS.md                 # neutral router
agents/<domain>/          # canonical agent/role definitions
prompts/tasks/            # task prompts
prompts/workspace/        # paste-style workspace prompts
skills/                   # skill packages
standards/                # normative rules
fragments/                # byte-exact shared blocks
commands/                 # command dispatchers
evals/                    # cases, arms, results
dsh/                      # runtime adapters
packs/                    # project adoption records
provenance/               # migration/evidence records
```

The `dsh/`, `packs/`, `exemplars/`, `fragments/`, and `provenance/` surfaces
stay at the top level; they are not agent or prompt definitions.

## Migration steps

1. **Add the new roots.** Done: `agents/`, `prompts/tasks/`, and
   `prompts/workspace/` are canonical; the legacy shims were removed in 2.0.0.
2. **Teach the tooling both roots.** Update, with a deprecation warning for the
   old path:
   - `tooling/validate_templates.py` discovery
   - `tooling/check_instantiation.py`
   - `tooling/check_workflow_loop.py`
   - `tooling/run_role_ab.py` role lookup
   - `tooling/run_role_doctrine_experiment.py`
   - the matching tests
3. **Keep eval keys stable.** `evals/role-ab/tasks/<role>.json` and
   `arms/<arm>/<role>.md` use role basenames, so no data migration is needed.
4. **Update the docs and registry.** `AGENTS.md`, `README.md`, `CATALOG.md`,
   `PLAN.md`, `docs/TEMPLATE-GUIDE.md`, `docs/SYNC.md`,
   `docs/neutral-layout.md`, `provenance/`, and the consumer re-vendor
   instructions.
5. **Version the break.** Bump the template major (`2.0.0`) and the consumer
   pin; re-vendor into `.kilo/agents` through the consumer generator, never by
   hand.
6. **Test the dual root.** Golden tests cover a fixture with only
   `agents/`+`prompts/` and one with only `roles/`+`tasks/`; both pass, and the
   legacy fixture asserts the warning. The fallback remains for old consumer
   checkouts, so a stale-only path is warned about, not rejected.
7. **Remove the shim.** Done in 2.0.0; the old paths and deprecation fallback
   are no longer part of the local tree.

## Compatibility and rollback

- The legacy shims were removed in 2.0.0; the new roots are the only paths.
- Consumers must re-vendor against a 2.0.0 library release; older pins still
  work with their own checked-out copy.
- Rollback is a revert of the root move and the resolver changes, or a checkout
  of the prior release; 2.0.0 has no local shim.
- Consumer rollback is the prior submodule pin; seed markers are monotonic.

## Why this layout

- `AGENTS.md` at the root is the ratified cross-vendor instruction file.
- `agents/` and `prompts/` are the common visible names for agent definitions
  and prompt assets; they are not owned by a vendor.
- `.agents/` is an emerging draft convention and a useful compatibility target,
  but it is hidden and not ratified. Do not make it the only source.
- Vendor directories (`.kilo/`, `.claude/`, `.cursor/`) are adapters generated
  from, or checked against, the neutral source.

## Open decision

If a consumer requires `.agents/`, generate it from this layout rather than
making it canonical. The library remains visible and reviewable.
