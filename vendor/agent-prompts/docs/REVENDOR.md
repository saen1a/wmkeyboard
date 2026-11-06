# Re-vendor runbook: library 2.12.0 into containeromat

Status: instructions only. Nothing in the consumer checkout was modified while
this runbook was written. Every command below exists: each was checked with
`--help`, and the read-only ones were run against the library or a consumer
checkout on 2026-11-02 at library `the library commit you are re-vendoring (see step 1, never a literal in this file)`.

Audience: the operator (or the session the operator authorizes) in the
**consumer** checkout. All commands run from the consumer root unless a step
says otherwise. Two placeholders are used throughout:

- `<consumer>` -- the containeromat checkout (for example `/workspace/containeromat`).
- `agent-prompts/` -- the vendored library submodule inside that checkout.

The release this runbook installs is library **2.12.0** at commit **`the library commit you are re-vendoring (see step 1, never a literal in this file)`**,
catalog `omp/catalog.yaml` `schema: omp-catalog/4`. The pins that gate the
projection are content hashes (`fragment_sha256`, `templates_sha256`,
`omp/prompts/foreground/manifest.json`); `library_version` and `library_commit`
are labels. Only `library_commit` is compared across trees (step 4, check 5 of
`scripts/verify-omp-agents.py`).

Read the current gitlink before step 1: the pack record still says the
consumer is pinned at **2.6.0** (`b1ea951`), but a checkout inspected on
2026-11-02 records `gitlink 067546e` in `agents.yaml`, while
`exclusions.yaml` still pins `42e462d`/2.6.0. The three pin files disagree. Step
1 records the sha you actually start from; the delta table at the end of this
file is measured from `b1ea951`, and the Wave 12 rows are exactly what
`067546e` lacks.

## 1. Bump the gitlink and record it

```bash
git -C agent-prompts fetch origin
git -C agent-prompts checkout the library commit you are re-vendoring (see step 1, never a literal in this file)
git add agent-prompts
git commit -m "vendor(agent-prompts): 2.12.0 (the library commit you are re-vendoring (see step 1, never a literal in this file))"
git submodule status agent-prompts
```

Pass condition: `git submodule status agent-prompts` prints the new sha with
**no** `+` (out of sync) or `-` (not initialized) prefix.

Record the same short sha in all three pin files in this commit, so no file is
left naming a canon that is no longer checked out:

| File | Field |
|---|---|
| `packs/containeromat/omp.yaml` | `library_commit: the library commit you are re-vendoring (see step 1, never a literal in this file)` |
| `packs/containeromat/agents.yaml` | `library_commit: the library commit you are re-vendoring (see step 1, never a literal in this file)` |
| `packs/containeromat/exclusions.yaml` | `library_commit: the library commit you are re-vendoring (see step 1, never a literal in this file)` |

`omp.yaml`'s `library_commit` is not optional bookkeeping: step 4's verifier
compares it for equality against `agent-prompts/omp/catalog.yaml`, which this
release sets to `the library commit you are re-vendoring (see step 1, never a literal in this file)`. Bumping the gitlink alone leaves that gate red with
`library_commit pin drift`.

Failure means: a `+` prefix is a stale index entry, not a vendored library;
`git submodule update --init --recursive` fixes a `-`.

## 2. Re-vendor the fragments and prove byte identity

```bash
python3 agent-prompts/tooling/check_fragments.py
python3 scripts/verify-agents.py
```

Pass condition: `check_fragments.py` prints `OK` for all five pinned fragments
and exits 0, including `agent-conduct.md (v1.1.0)` and
`agent-doctrine.md (v1.5.0)`; `scripts/verify-agents.py` exits 0, so its
`check_conduct` / `check_doctrine` found every carrier byte-identical to canon.

`check_fragments.py` is the manifest-mode verifier the pack documents: it
sha256-verifies the fragments against
`tooling/fragments.manifest.json` inside the vendored copy and needs no
upstream checkout. `scripts/verify-agents.py` is the consumer-side verifier the
pack already names -- it is the check that covers the *rendered carriers*, not
only the fragment files, so it is the one that proves the re-vendor rather than
the checkout.

What changed here: `conduct 1.0.0 -> 1.1.0` (one new bullet: a stated rule is
not an enforced one) rendered into all 41 carriers -- 38 agent templates and 3
task prompts, `tooling/validate_templates.py` reports `41 file(s)` -- and
`doctrine 1.4.0 -> 1.5.0` (the mandatory plan-review gate: the loop line, the
gate bullet, and the repeat-until-clean rule). All four conduct variants carry the same
runtime-agnostic bullet, and `tooling/check_fragments.py` enforces that parity
(`shared_conduct_rules` in the fragment manifest), so an OMP or dsh projection
cannot ship a conduct block that is behind the kilo carriers.

Failure means: a `MISMATCH` line names a carrier that was hand-edited or not
re-rendered. Re-render it (step 3); never edit a carrier to match.

## 2b. Wire the loop gate into the consumer's CI

```bash
python3 agent-prompts/tooling/check_plan_spec.py <consumer>/provenance/plan-*.md
python3 agent-prompts/tooling/check_loop_gate.py --root . \
    --ledger 'provenance/ledger-*.md' \
    --verdict 'provenance/verdict-*.json' \
    --since <the date this consumer adopted the gate>
```

Pass condition: both exit 0. `check_plan_spec.py` reports the six WL-15 checks
over each spec; `check_loop_gate.py` refuses a unit that reached Implement
without a clean `plan-review` verdict, rounds that are not contiguous from 0, or
a finalize with no verify pass. Put both in `scripts/ci-replica.sh --fast`, and
declare the result honestly in the runtime admission record (`loop_gate`:
`supported` only with a pre-dispatch check, else `degraded` plus these commands,
AD-12). Without this step the loop is doctrine text in the consumer, whatever
the library says.

## 3. Re-render the neutral agent bodies

```bash
python3 agent-prompts/tooling/render_agents.py \
    --pack packs/containeromat/agents.yaml --write \
    --library-root agent-prompts --project-root .
python3 agent-prompts/tooling/render_agents.py \
    --pack packs/containeromat/agents.yaml --check \
    --library-root agent-prompts --project-root .
python3 agent-prompts/tooling/check_instantiation.py \
    --project-root . --library-root agent-prompts
```

Pass condition: the write run reports `agents: <N> rendered, 0 drift` (23 on
the checkout measured while writing this), the `--check` run repeats it with
exit 0, and `check_instantiation.py` exits 0 (block sequence, fragment
identity, output-last, workflow prose, `hard_rules` shape).

Regenerate `packs/containeromat/agents.lock.json` in the same commit as the
bodies it pins:

```bash
python3 scripts/verify-agent-pack.py --write-lock
```

Then re-check it with the plain run (step 5 uses the same command).

Failure means: `drift` names the outputs that differ; a slot residue means the
pack row lost a `{{SLOT}}` value, not that the template is wrong.

## 4. Re-render the OMP projection

Two outputs, two renderer invocations -- the agent projection and the
main-session policy:

```bash
python3 agent-prompts/tooling/render_omp.py \
    --pack packs/containeromat/omp.yaml --out .omp/agents
python3 agent-prompts/tooling/render_omp.py --foreground \
    --pack packs/containeromat/omp.yaml --out .omp/APPEND_SYSTEM.md
python3 scripts/verify-omp-agents.py
```

Pass condition: `scripts/verify-omp-agents.py` exits 0 and prints
`ok   library_commit the library commit you are re-vendoring (see step 1, never a literal in this file) matches in packs/containeromat/omp.yaml and
agent-prompts/omp/catalog.yaml`. That one command is the whole gate: it calls
the renderer three times in `--check` mode (`--check`, `--check --pack ... --out
.omp/agents`, `--check --foreground --pack ... --out .omp/APPEND_SYSTEM.md`),
compares the two pins, and then adds the checks a renderer cannot make
(frontmatter key set, slot residue, ASCII, non-vacuous output, the
consumer-owned `.omp/skills/` copy).

Do not hand-edit `.omp/agents/*.md` or `.omp/APPEND_SYSTEM.md`; both are
generated. `scripts/verify-omp-agents.py` has no `--pack`/`--out` flags -- the
renderer invocations above are the manual form of what it already runs. It also
gates two consumer-owned documents this re-vendor does not render:
`.omp/AGENTS.md` (the always-on brief, checked as a document because that is the
channel OMP loads) and `.omp/skills/` (checked by the consumer's
`scripts/render-omp-skills.py --check`).

Failure means: `pin drift` is step 1 (pack pin vs catalog pin); `DIFF` is a
stale render; `library canon missing` means the submodule is not initialized.

## 5. Adopt or exclude the two new skills

The consumer's contract, enforced by `scripts/verify-agent-pack.py`'s
unconditional coverage pass: every library role, skill, command and preset is
either projected into the consumer surface or carries a row in
`packs/containeromat/exclusions.yaml` with a class and a reason. Neither adopted
nor excluded fails. An exclusion row that names something the library no longer
ships also fails.

Adopting a skill is three edits together -- copy, register, manifest:

```bash
cp -r agent-prompts/skills/general/operator-setup-interview \
      stacks/paseo/config/skills/
cp -r agent-prompts/skills/general/human-gated-config-change \
      stacks/paseo/config/skills/
# add one row per skill to scripts/skills-library.json
python3 scripts/skills-manifest.py
```

excluding it is one edit -- one row per skill:

```yaml
skills:
  - name: operator-setup-interview
    class: deferred
    reason: "<why this surface does not carry it>"
```

Pass condition, either way:

```bash
python3 scripts/verify-agent-pack.py
python3 scripts/verify-agents.py
```

Both exit 0. `verify-agent-pack.py` covers adoption/exclusion and the lock;
`verify-agents.py` covers `check_library_canon` for the copies you registered.

Notes measured on 2026-11-02:

- The library ships 27 skills; the consumer registry holds 25 at `067546e` and
  the paseo skill surface carries 33 directories (25 library copies plus local
  ones). `untrusted-content-handling` is already registered and copied there;
  the two Wave 12 skills are the gap.
- `packs/containeromat/exclusions.yaml`'s header documents
  `verify-agent-pack.py --coverage`. That flag does not exist in the current
  script (`argparse` rejects it, exit 2); coverage runs unconditionally on every
  plain invocation. Document the plain command, not the flag.
- Copy the whole skill directory, including `references/`; a body that routes to
  a missing file is a broken skill.

## 6. Adopt or exclude the four new standards

The standards are not skills: `verify-agent-pack.py`'s `library_items()`
enumerates roles, skills, commands and presets only. A standards decision is
therefore recorded, not coverage-checked -- see "Open questions".

Record the decision once, in the consumer's own record, one line per standard,
with the library rule range it adopts:

| Standard | Range | What the consumer must supply |
|---|---|---|
| `standards/work-authorization.md` | WA-01..WA-12 | the policy block: allowed list, admission cells per receiving scope, enabled rules -- already decided in that consumer's admission-cell record; `observe` is the starting mode (WA-07) |
| `standards/durable-effects.md` | EF-01..EF-10 | one effect row shape, one retry class per kind, the key derivation |
| `standards/message-delivery.md` | MD-01..MD-08 | the delivery guarantee it states, its transport's closed `gone` set, the stored unit |
| `standards/agent-notification.md` | NT-01..NT-10 | the word ceiling its transport rejects above, the disclosure line, the destination conversation |

The same step covers the rule extensions the release carries into standards the
consumer already cites: SD-12 (delegation transfers no authority), AS-13/AS-14
(volatile layers last; override provenance), VI-15 (a status is derived, never
stored), CR-13 (visual evidence for a UI change), AD-11 (probe as the agent
runs, degrade per capability). A consumer that cites an older rule range now
cites a range that changed; re-read the section before quoting it.

Pass condition: the four rows exist in the record and every rule ID the
consumer's own prompts cite still resolves --
`agent-prompts/tooling/check_model_surface.py` covers citations for the tree it
scans (step 7), and `scripts/verify-agents.py` covers the consumer's own
citations.

## 7. Register the model surface

Prerequisite, and the one that fails first: `--root` must contain the library
`standards/*.md`. The registry's `rule_families` map is a set of
`standards/<file>.md` paths resolved against `--root`, and every rule family
defined in that directory must be registered. Measured without it: exit 1 and
`FAIL missing rule family file for AD: standards/agent-adapter.md` (15 such
lines plus 7 glob misses on a tree that had only the registry).

Expose the standards without creating a second canon, then keep the registry
itself outside that directory:

```bash
ln -s agent-prompts/standards standards          # one-line exposure; no copy
python3 agent-prompts/tooling/check_model_surface.py \
    --root . --registry packs/containeromat/model-surface.json
```

Pass condition: exit 0 with `0 unresolved`. Measured on a probe tree carrying
the library standards plus `agents/**`: `1 surfaces, 38 files, 43433 tokens, 29
citation(s), 0 unresolved, 0 violation(s)`. The library's own registry at
`the library commit you are re-vendoring (see step 1, never a literal in this file)` reports `8 surfaces, 90 files, 117 citation(s), 0 unresolved`.

The registry is per-tree, not a copy of the library's: every glob resolves
against `--root`, so a copied `standards/model-surface.json` registers
`agents/**`, `prompts/tasks/*`, `omp/prompts/foreground/*` and `dsh/presets/*`
-- library paths -- and fails with `glob matches no file` on a consumer tree.
Register the consumer's own model-visible surfaces (its neutral `agents/**`,
`.kilo/agents/**`, `commands/**`, `.omp/agents/*`, `.omp/APPEND_SYSTEM.md`,
`skills/**`), each with a budget and a `measured_max_tokens`, and keep the
`rule_families` keys and paths unchanged.

Do not write through the symlink: a registry written to `standards/model-surface.json`
follows the link and overwrites the library's registry. Keep it at
`packs/containeromat/model-surface.json` -- a file this step creates; the
consumer tree has no `standards/` directory today, which is why the exposure in
the command above is a symlink.

The release's own reference point for a role body budget is the library
registry: `role-templates` is `agents/**/*.md` with `budget_tokens: 1200` and
`measured_max_tokens: 1163`.

## 8. Add the three gate commands

A green consumer gate that does not run these is not adoption evidence. Add
them to the consumer's gate battery, not to a scratch script:

```bash
# 1. one grant record per accepted unit (WA-04)
python3 agent-prompts/tooling/check_mandate.py <grant-record.json>

# 2. the consumer's registered model surface (AP-01, SK-03)
python3 agent-prompts/tooling/check_model_surface.py \
    --root . --registry packs/containeromat/model-surface.json

# 3. the behavioral cases for the adopted skills
python3 agent-prompts/tooling/check_behavioral_evals.py \
    --root . --skills-dir stacks/paseo/config/skills --cases-dir evals/behavioral
```

Pass conditions: `check_mandate.py` exits 0 with `<id>/<strength>, 0
violation(s)` per record (a clean example is the library's
`exemplars/mandate-example.json`, which reports `active/explicit, 0
violation(s)`); `check_model_surface.py` is step 7; `check_behavioral_evals.py`
exits 0 with `0 violation(s)`.

Two measured traps in the third command:

- Bare `--root .` fails with `FAIL setup: <consumer>/skills: skills directory
  not found` -- the consumer keeps skills under `stacks/paseo/config/skills`,
  so pass `--skills-dir`.
- Pointing `--cases-dir` at `agent-prompts/evals/behavioral` validates the
  library's whole case set and fails on any case whose skill the consumer does
  not adopt (`FAIL unknown-skill: misakanet: no skills/**/SKILL.md declares
  misakanet`). Keep the adopted cases in a consumer-owned `evals/behavioral/`.

If the consumer keeps no grant record yet, `check_mandate.py` has no input: it
is a required gate command with zero rows, and that state is "the standard is
not adopted", not "green".

## 9. Verify

```bash
bash .forgejo/scripts/tests/run.sh
bash scripts/ci-replica.sh --fast
(cd agent-prompts && make gate)
```

Pass condition: all three exit 0. The first two are the consumer's own battery
(`.forgejo/scripts/tests/run.sh` is the mandatory local CI-context gate;
`ci-replica.sh --fast` is the compose-validate battery with the network-bound
subset skipped). The third is the library's full gate run inside the vendored
copy: 25 steps, ending in `all library gates passed`.

Then one smoke line per surface, each fast enough to run by hand:

| Surface | Command | Pass |
|---|---|---|
| Agent bodies | `python3 agent-prompts/tooling/validate_templates.py` | `checked 41 file(s); 0 violation(s)` |
| Live agents | `python3 scripts/verify-agents.py` | exit 0 |
| Skills | `python3 scripts/check-skill-routing.py` | exit 0, no routing violation |
| OMP policy + agents | `python3 scripts/verify-omp-agents.py` | `OK omp-agents: <N> agent file(s), .omp/APPEND_SYSTEM.md and the .omp/AGENTS.md` |
| Model surface | `python3 agent-prompts/tooling/check_model_surface.py --root . --registry packs/containeromat/model-surface.json` | `0 unresolved` |

## 10. Rollback

The gitlink and the rendered outputs are one unit. Revert them in one commit:

```bash
git checkout <old-sha> -- agent-prompts .omp/agents .omp/APPEND_SYSTEM.md \
    agents .kilo/agents packs/containeromat/agents.lock.json
git commit -m "Revert vendor(agent-prompts): 2.12.0"
```

Then restore the pin fields to the old sha in `omp.yaml`, `agents.yaml` and
`exclusions.yaml` (`library_commit`, plus `library_version` where the step
bumped it) and remove the skill copies, registry rows and exclusion rows the
change added.

What stays stale if only one side reverts:

| Only the gitlink reverts | Only the renders revert |
|---|---|
| `render_omp.py --check` reports byte drift for every role whose body changed (the catalog's `templates_sha256` now describes the old tree, the outputs describe the new one); `workflow-loop` and conduct/doctrine identity checks fail if the old commit carries the old fragment text | The same drift in the other direction: the pack and catalog pins describe the new canon, the outputs are old |
| The two new skills stay copied and registered while canon no longer ships them -> `verify-agents.py`'s canon check fails on missing library sources | `packs/containeromat/agents.lock.json` no longer matches its bodies -> `verify-agent-pack.py` fails |
| The model-surface registry still registers surfaces the old tree does not have -> `check_model_surface.py` `glob matches no file` | The registry still passes if the tree is unchanged, so a stale render can hide behind a green model-surface run |

Seed markers and `scripts/skills-library.json` are monotonic: do not lower a
marker to "undo" a copy; remove the row and the directory instead.

## What each surface must end up carrying

| Area | Change since 2.6.0 | Consumer action | Verification |
|---|---|---|---|
| Fragments | conduct `1.1.0`, doctrine `1.5.0`; 41 carriers re-rendered | step 2 | `check_fragments.py`, `verify-agents.py` |
| Standards | four new: work-authorization WA-01..12, durable-effects EF-01..10, message-delivery MD-01..08, agent-notification NT-01..10 | step 6 | record + cited ranges resolve |
| Rule extensions | SD-12, AS-13/AS-14, VI-15, CR-13, AD-11 | step 6 | `verify-agents.py` |
| Skills | `operator-setup-interview`, `human-gated-config-change` (+ trigger and behavioral cases) | step 5 | `verify-agent-pack.py`, `check_behavioral_evals.py` |
| Model surface | `standards/model-surface.json`, `check_model_surface.py`, `check_doc_ranges.py`, `check_mandate.py` | steps 7-8 | `check_model_surface.py`, `check_mandate.py` |
| Role bodies | all 38 regenerated; registered max 1,316 tokens (`agents/**/*.md`), budget 1,360; doctrine 1.5.0 adds the plan-review gate and every carrier's phase map names it | step 3 | `render_agents.py --check`, `validate_templates.py` |
| OMP projection | 12 catalog entries; refreshed `fragment_sha256` and `templates_sha256`; foreground module set | step 4 | `verify-omp-agents.py` |
| Pins | `library_commit` now `the library commit you are re-vendoring (see step 1, never a literal in this file)` in the library catalog | step 1 | `verify-omp-agents.py` check 5 |

## Open questions for the consumer

1. **Which sha is canon.** Two commits are in play across three records:
   `agents.yaml` and the gitlink say `067546e`, `exclusions.yaml` says
   `42e462d`, and this pack's own record says 2.6.0/`b1ea951`. Step 1 resolves
   it by copying one sha into all of them; whether `exclusions.yaml` should keep
   a pin at all is the consumer's call.
2. **Conduct parity is settled, not open.** All four variants carry the 1.1.0
   bullet and `tooling/check_fragments.py` fails if any variant drops a rule the
   manifest declares shared (`shared_conduct_rules`), so a projection cannot ship
   a conduct block behind the kilo carriers. This entry stays only to record that
   the earlier release had the gap.
3. **Standards adoption evidence.** Coverage enumerates roles, skills, commands
   and presets, so a standard's adopt/exclude decision is not machine-checked.
   Either the consumer extends coverage or the decision stays a documented
   record.
4. **Grant records.** `check_mandate.py` needs one record per accepted unit; the
   consumer keeps none today. Until it writes one, the gate command has no rows
   and the work-authorization standard is specified, not enforced.
5. **Registry budgets.** The consumer chooses its own `budget_tokens` and
   `measured_max_tokens` per surface; the library's 1,360/1,316 role figure is
   a reference, not a requirement for a consumer body that carries its own
   slots and overlays.
