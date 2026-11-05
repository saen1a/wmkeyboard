# Project agent surface

Kilo discovers everything in this directory. The canon lives in
`vendor/agent-prompts/`; this tree is the project's adapter.

## Prerequisites

- Python 3.10 or newer.
- `python -m pip install 'PyYAML>=6'`.
- The vendored tree must match `packs/wmkeyboard/vendor.lock.json`; the renderer
  refuses to import it otherwise.

| Path | Owner | Rule |
|---|---|---|
| `agents/` | generated | Do not edit. Source: `packs/wmkeyboard/agents.yaml`. |
| `skills/` | mixed | Library skills are byte-copies; project skills are maintained here. |
| `command/` | project | Slash commands. Edit freely. |
| `worktrees/` | Agent Manager | Separate checkouts. Never edit them from the main tree. |

## Regenerate

```sh
python scripts/gen-agent-pack.py --write
python vendor/agent-prompts/tooling/render_agents.py \
    --pack packs/wmkeyboard/agents.yaml --write \
    --library-root vendor/agent-prompts --project-root .
python scripts/render-kilo-agents.py --write
python scripts/verify-agent-pack.py
```

A re-vendor uses `python scripts/vendor-agent-prompts.py --library <checkout>
--commit <sha> --version <x.y.z>`; it deletes the old tree, copies the new one,
rewrites `VENDORED.md`, and refreshes `vendor.lock.json`.

## Permissions

Write roles are scoped by `scripts/render-kilo-agents.py`: `write-native`,
`write-kotlin`, `write-general`, `write-tests`, `write-docs`, `write-ci`,
`write-release`, `write-batch`. Each denies secrets and keystores, asks on an
unmatched command, and denies `git push` and destructive deletes. No write role
gets a bare `edit: allow` or `bash: allow`.

This is defense in depth, not a sandbox. A shell command can still do arbitrary
work, so the spec, the review and the operator's Push gate remain the real
controls. The permission map exists to stop the common accident, not a
determined bypass.

## Project skills

`wmk-architecture`, `wmk-build`, `wmk-docs`, `wmk-glide-eval`,
`wmk-languages`, `wmk-native-engine`, `wmk-release`.

## Library skills

The 21 `general/` and `shared/` skills are copied from the vendored library.
`scripts/verify-agent-pack.py` fails when a copy differs from canon. Vendor
skills are excluded: the caveman family is already in the operator's global
config, and `misakanet` needs a service this project does not mount.

### Duplicate names

Some of these skills also exist in the operator's global config. The project
copy is the pinned canon; it is not a copy of the global one and it is expected
to diverge when the library moves. Do not "fix" a divergence by copying the
global version back. The project scope is authoritative for this repository.

## Overrides

Project agents use the same names as the operator's global agents where the
surface matches (`code-explorer`, `oracle`, `review-*`, `researcher`,
`librarian`, `councillor`, `council-synthesizer`, `research-merger`,
`review-lead`, `orchestrator`, `code-skeptic`). The project file is the intended
override; the global file stays as the fallback for other repositories.

### Precedence smoke test

Run this after a name change and after a Kilo upgrade:

1. Select `orchestrator`, `review-lead`, `code-skeptic`, and `researcher`.
2. Ask each to print its `<role>` block.
3. Confirm each block names `wmkeyboard`, not a containeromat or seifomat
   workspace.

If a global definition wins, rename the project agent to `wmk-<name>` and update
`.kilo/command/orchestrate.md`, `.kilo/command/review.md`, `AGENTS.md`, and the
agent map in `packs/wmkeyboard/README.md`.
