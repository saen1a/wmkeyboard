# Vendored: agent-prompts

Source: https://forgejo.hellgate.cc/saenta/agent-prompts
Pinned commit: `801c3f7424ecc96956f9fe88a3ca78bd44595711`
Commit date: 2026-11-03 20:06:12 +0100
Library version: 2.12.0
Vendored: 2026-11-05

This directory is a byte copy of the library at the pinned commit, excluding
`.git/`, `.forgejo/` and `__pycache__/`. It is the canon for the project's
skills, fragments, role templates, standards, prompts, and tooling.

## Rules

- Never edit a file below `vendor/agent-prompts/`. A divergence is drift, not a
  customization.
- Project behavior belongs in `packs/wmkeyboard/` (slots and overlays),
  `.kilo/agents/` (generated), `.kilo/skills/` (project skills), or `AGENTS.md`.
- A library change arrives by re-vendoring this directory and bumping the
  pinned commit in `packs/wmkeyboard/agents.yaml` and `packs/wmkeyboard/README.md`.

## Update procedure

From the project root:

```sh
git -C <library> fetch origin
git -C <library> checkout <new-commit>
python scripts/vendor-agent-prompts.py --library <library> \
    --commit <new-commit> --version <x.y.z>
```

The tool deletes the old tree (except `VENDORED.md`), copies the new one,
rewrites this file, and refreshes `packs/wmkeyboard/vendor.lock.json`. Then run:

```sh
python scripts/gen-agent-pack.py --write
python vendor/agent-prompts/tooling/render_agents.py \
    --pack packs/wmkeyboard/agents.yaml --write \
    --library-root vendor/agent-prompts --project-root .
python scripts/render-kilo-agents.py --write
python scripts/verify-agent-pack.py
```

## Integrity

- Fragment hashes: `vendor/agent-prompts/tooling/fragments.manifest.json`.
- Whole-tree hashes: `packs/wmkeyboard/vendor.lock.json`.
- Rendered agent bodies: `packs/wmkeyboard/rendered/`.
- Live Kilo agents: `.kilo/agents/`.
- Output hashes: `packs/wmkeyboard/agents.lock.json`.

`scripts/verify-agent-pack.py` checks all four.
