# Consumer re-vendor: Wave 9 skill changes

Status: instructions only. The consumer checkout was not modified.

Runtime status note (2026-10-27): dsh and zcode are inactive and will not be
deployed in this cycle (`dsh` regains usage in November; `zcode` has no date and
is not applicable this cycle). Their skill roots in step 3 below
(`stacks/deepseek-harness/config/skills/` and `stacks/zcode/config/skills/`) and
the seed markers in step 4 are therefore inert: no re-copy, no seed-marker bump
and no gate work is an outstanding task, and the roots are not removed. The
procedure stays as written for when those runtimes return.

Nine library skill bodies changed in Wave 9 and seven gained a reference file:

| Skill | Change |
|---|---|
| `jq-json-processing` | body split; `references/recipes.md` |
| `skill-creator` | body split; `references/authoring-guide.md` |
| `first-principles-review` | body split; `references/lenses.md` |
| `mcp-builder` | body split; `reference/workflow.md` |
| `anti-entropy-governance` | body split; `references/retirement-playbook.md` |
| `deepseek-v4-agent-defense` | body split; `references/layer-rules.md`; `references/layers.md` text updated |
| `agent-md-refactor` | body split; `references/refactor-guide.md` |
| `ask-questions-if-underspecified` | H2 trim only |
| `verification-before-completion` | H2 trim only |

## Order

1. Merge the library commit first. The library is the canon; do not edit a
   consumer copy and back-port it.
2. In the consumer, update the submodule pointer to that commit.
3. Copy each changed skill tree from
   `agent-prompts/skills/**/<skill>/` to the consumer roots:
   - `.openhands/skills/`
   - `stacks/deepseek-harness/config/skills/`
   - `stacks/zcode/config/skills/`
   Copy the whole directory, including `references/` or `reference/`; a body
   that routes to a missing file is a broken skill.
4. Bump the seed markers whose trees changed:
   - `stacks/deepseek-harness/config/skills/.seed-version`
   - `stacks/zcode/config/skills/.seed-version` if ZCode carries the skill
5. Run the consumer gates:
   - `python3 scripts/verify-agents.py` (library canon, skill copies,
     references, discipline)
   - `scripts/skills-manifest.py` (tree hashes)
   - `scripts/verify-skills-seed-version.sh` (bump present)
   - the compose-validate workflow's prompt/skill steps
6. Re-run `check_library_canon`; it must report zero divergence and zero missing
   mirrored files.

## Checks that must pass

- Every changed skill body is byte-identical to the library canon.
- Every new `references/*.md` or `reference/*.md` file exists in the consumer.
- The registry has a row for each library skill. As of 2026-10-27 both sides are
  24/24: `python3 -c "import json; print(len(json.load(open('scripts/skills-library.json'))['skills']))"`
  in the consumer and `find agent-prompts/skills -name SKILL.md | wc -l` in the
  library each report 24. Re-run both before relying on this line; add any
  missing row before `check_library_canon` can pass.
- No consumer edits a canon body; local behavior goes through slots or a fork.

## Rollback

Revert the submodule pointer and restore the prior skill trees from git. Seed
bumps are monotonic; do not lower a marker to "undo" a bad copy.

## Doctrine 1.3.1 / template 2.0.1 re-vendor (2026-10-25)

The workflow-loop change is a fragment change, so every consumer that carries
the doctrine must re-vendor, not just the skills.

1. Update the consumer submodule pointer to the library commit that contains
   doctrine 1.3.1.
2. Copy `fragments/agent-doctrine.md` byte-for-byte into the consumer's
   canonical template location (currently `.kilo/templates/`).
3. Re-instantiate or regenerate every role/task that carries the fragment; do
   not hand-edit a consumer copy.
4. Re-vendor the 4 dsh preset personas from `dsh/presets/`.
5. Run the consumer verifier (`scripts/verify-agents.py`), the rendered-config
   check (`scripts/render-agent-config.py --check`), and the seed-version bump.
6. Record the doctrine version in the consumer's pin file.

The library is the authoring source for doctrine 1.3.1 (see `docs/SYNC.md`);
the consumer is still the source for its own role selection and project slots.
Until this step is complete, the claim "every agent and subagent" is a library
claim only.

For the neutral folder target (`agents/` + `prompts/` instead of vendor
directories), see `docs/neutral-layout.md`.

## 1.3.0 consumer run attempt (2026-10-24)

The available checkout at `/home/paseo/tmp/uc` is not a git repository and its
`agent-prompts` submodule directory is empty (0 files). `python3
scripts/verify-agents.py` exits 1, first on `skill-library` missing
`skills/general/agent-md-refactor`, and cannot validate the doctrine because no
library copy is present. No re-vendor was performed.

This is a blocked environment, not a pass. A real consumer run requires the
containeromat checkout with its submodule initialized and a git history to
commit the pointer/seed bump.

## 2.0.0 layout re-vendor (2026-10-24)

The library moved to `agents/`, `prompts/tasks/`, and `prompts/workspace/` and
removed the legacy shims in 2.0.0.

1. Update the consumer submodule pointer to the 2.0.0 library commit.
2. Change any consumer path that read `agent-prompts/roles/` or
   `agent-prompts/tasks/` to `agent-prompts/agents/` and
   `agent-prompts/prompts/tasks/`.
3. Re-instantiate/regenerate the live `.kilo/agents/` from the 2.0.2 templates;
   do not copy the old paths.
4. Run `scripts/verify-agents.py` and `scripts/render-agent-config.py --check`.
5. Bump the seed markers and record `template_version 2.0.2` plus
   `fragment_versions {doctrine: 1.3.1, conduct: 1.0.0}`.
