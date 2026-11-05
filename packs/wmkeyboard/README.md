# Project pack: wmkeyboard

Adoption record for the vendored `agent-prompts` library. The manifest is
`agents.yaml`; the rendered neutral bodies are in `rendered/`; the live Kilo
agents are in `.kilo/agents/`. Every write role carries a scoped permission
profile; no write role has an unrestricted `edit` or `bash` permission.

- Library: https://forgejo.hellgate.cc/saenta/agent-prompts
- Pin: `801c3f7424ecc96956f9fe88a3ca78bd44595711` (2.12.0, Wave 13)
- Canon checkout: `vendor/agent-prompts/` (never edit)
- Fragments: `agent-doctrine.md` 1.5.0, `agent-conduct.md` 1.1.0

## Flow

```sh
python scripts/gen-agent-pack.py --write
python vendor/agent-prompts/tooling/render_agents.py \
    --pack packs/wmkeyboard/agents.yaml --write \
    --library-root vendor/agent-prompts --project-root .
python scripts/render-kilo-agents.py --write
python scripts/verify-agent-pack.py
```

`gen-agent-pack.py` is the source of truth for the role list and slot values.
`agents.yaml` is generated; edit the generator, not the YAML.

## Slot fills

- `PROJECT_ID` = `wmkeyboard`
- `PROJECT_RULES` = `AGENTS.md`
- `VERIFICATION_COMMANDS` = the verification commands in `AGENTS.md`
- `SAFETY_RULE` / `MUTATION_POLICY` are slot labels; the template carries the
  rule text.
- `PROJECT_CI_GATES` = `.github/workflows/ci.yml` and
  `.github/workflows/agent-pack.yml`
- `PROJECT_REVIEW_CONTRACT` =
  `vendor/agent-prompts/standards/code-review-contract.md`
- `ROLLBACK_COMMAND` = `git restore --source=HEAD -- <changed paths>`

## Agent map

The authoritative generated map is `agents.yaml`; its source is
`gen-agent-pack.py`. The live names follow the project's existing vocabulary so
a project agent overrides a same-named global one. Run the precedence smoke
test in `.kilo/README.md` after a name change.

| Group | Live agents | Library templates |
|---|---|---|
| Orchestration | `orchestrator`, `councillor`, `council-synthesizer` | `orch-*` |
| Engineering | `code-explorer`, `oracle`, `fixer`, `backend-developer`, `frontend-developer`, `api-developer`, `database-developer`, `test-author` | `eng-*` |
| Design | `ui-reviewer` | `design-ui-reviewer` |
| Documentation | `docs-writer` | `doc-doc-writer` |
| Operations | `ci-implementer`, `ops-executor`, `format-normalizer` | `ops-*` |
| Research | `librarian`, `researcher`, `research-merger` | `res-*` |
| Review | `reviewer`, `review-lead`, `code-skeptic`, `consistency-reviewer`, `security-reviewer`, and the eight `review-*` tracks | `rev-*` |
| Project | `wmk-native-engineer`, `wmk-kotlin-engineer`, `wmk-glide-researcher`, `wmk-release-engineer` | `eng-fixer` (native and Kotlin), `res-researcher` (glide), `ops-ci-implementer` (release), plus overlays |

The four project agents reuse a library template and add project rules in
`overlays/`; they do not fork the doctrine or conduct blocks.

## Permission profiles

`scripts/render-kilo-agents.py` maps each manifest profile to a scoped Kilo
permission block:

| Profile | Edit scope |
|---|---|
| `write-native` | `native/**` |
| `write-kotlin` | `app/**`, `core/**`, `feature/**` |
| `write-general` | those plus `tools/**`, `native/**`, `scripts/**` |
| `write-tests` | `**/src/test/**`, `**/src/androidTest/**` |
| `write-docs` | `docs/**`, `README.md`, `SETTINGS_REDESIGN.md`, `release-notes/**` |
| `write-ci` | `.github/**`, `scripts/**` |
| `write-release` | `release-notes/**`, `fastlane/metadata/**`, `docs/**`, `README.md`, `gradle.properties` |
| `write-batch` | source and docs, unmatched paths ask |

Every profile denies `fastlane/play-service-account.json`, keystores, `.env*`,
and `local.properties`, and every `bash` map asks on an unmatched command and
denies `git push`, `rm`, `Remove-Item`, and `del`. The fallback is first in the
map, so a first-match runtime denies or asks rather than allowing by accident.

## Integrity

`packs/wmkeyboard/vendor.lock.json` hashes every file below
`vendor/agent-prompts`. `scripts/vendor_integrity.py --check` verifies it, and
`scripts/render-kilo-agents.py` refuses to import the vendored renderer before
the hash matches. A re-vendor uses delete-then-copy through
`scripts/vendor-agent-prompts.py`, never a copy-over.

## Exclusions

See `exclusions.yaml`. The library ships networking and tabletop roles that this
project does not have a surface for, and vendor skills that are either already
available globally or need a service this project does not mount.

## Verification

```sh
python scripts/vendor_integrity.py --check
python vendor/agent-prompts/tooling/check_fragments.py
python vendor/agent-prompts/tooling/render_agents.py \
    --pack packs/wmkeyboard/agents.yaml --check \
    --library-root vendor/agent-prompts --project-root .
python scripts/gen-agent-pack.py --check
python scripts/render-kilo-agents.py --check
python scripts/verify-agent-pack.py
```

A drift line names the file to regenerate. Never edit a rendered body by hand.
`.github/workflows/agent-pack.yml` runs the same gate on every push and pull
request.
