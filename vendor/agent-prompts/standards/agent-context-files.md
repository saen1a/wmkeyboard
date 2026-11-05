# Agent context file standard

Status: ACTIVE (2026-10-23).

Class: repository configuration. Applies to the always-loaded context file a
coding agent reads at the repository or package level: `AGENTS.md` or a
host-specific equivalent (`CLAUDE.md`, `GEMINI.md`, `.cursor/rules`).

Evidence: `evidence/prompt-research-2026-10.md` (S13-S15, S23).

## Purpose

A context file is a router, not a manual. It tells an agent where to start and
which local rules are non-obvious. It is always loaded, so every line spends
attention budget on every task. The evidence is consistent on this point:
repository-specific operational content can improve efficiency, while generic
overviews add cost without a reliable success gain (S13, S14, S15).

## CF-01 -- The file is a router

Every line must be one of:

1. an exact command the agent cannot infer (build, test, lint, run, verify);
2. a non-standard convention or trap that would otherwise be guessed wrong;
3. a pointer to a skill, doc, or gate that carries the detail.

If a line is none of these, delete it.

## CF-02 -- What belongs

- Build, test, lint, format, and verification commands, with the directory they
  run in.
- Non-standard repository conventions: generated files, ownership boundaries,
  forbidden paths, migration rules, release steps.
- The definition of done and the check that proves it.
- Known traps: flaky suites, required environment variables (names only, never
  values), ordering constraints.
- Short pointers to skills, docs, and CI gates.

## CF-03 -- What does not belong

- Architecture overviews, file trees, and tutorials. The ETH evaluation found
  repository overviews were not helpful (S13).
- Generic best practices ("write clean code", "add tests") that the model
  already follows.
- Long procedures with steps. Those belong in a skill, loaded on demand.
- Duplicated policy that also lives in a linter, test, or CI gate.
- Secrets, tokens, credentials, internal URLs with embedded auth, or customer
  data.
- Persona prose or motivational framing. It spends tokens without changing
  behavior.

## CF-04 -- Size and shape

- Target one screen, at most about 100-150 lines for the root file. There is no
  cross-host size contract (S23); hosts may truncate or skip long files, so
  treat length as a risk, not a budget.
- Prefer one line per fact. A command line, a convention line, a pointer.
- Use nested files for a monorepo, each a few dozen lines. The nearest file in
  the tree wins (S23, `verified`).
- If the file needs a table of contents, it is too long.

## CF-05 -- Layer map

| Layer | Content | Loaded | Enforced |
|---|---|---|---|
| Context file (`AGENTS.md`) | Commands, traps, non-standard conventions, pointers | Always | No |
| Skill (`SKILL.md`) | Repeatable procedures, with references and scripts | On demand | No |
| Executable gates (CI, hooks, linters, tests) | Anything decidable: types, tests, licenses, forbidden paths, secret scanning | At commit/CI | Yes |
| Docs and ADRs | Architecture, rationale, runbooks | By link | No |
| MCP resources or live APIs | Current data, schemas, catalogs | Host-selected | No |

The rule of placement:

- always true and cheap to state -> context file;
- a procedure with steps -> skill;
- decidable by a machine -> executable gate;
- everything else -> a linked doc.

No prose layer enforces anything. A model can ignore a context file; it cannot
ignore a failing test.

## CF-06 -- One canonical source

- Keep one canonical context file per scope. If a host requires a different
  name, make it a pointer, a symlink, or a generated copy with a header that
  names the source. Never maintain two edited copies.
- Do not duplicate the same rule in the context file, a skill, and a CI gate.
  State it once at the strongest layer that can carry it.
- Host-specific files (`CLAUDE.md`, `GEMINI.md`, `.cursor/rules`) are format
  variants, not additional policy layers. Their content should be a subset of,
  or a pointer to, the canonical file.

## CF-07 -- Format

- ASCII, short lines, imperative mood.
- Exact commands in fenced blocks, with the working directory.
- Stable headings, so a diff is readable.
- No plan-internal IDs, no runtime counters, no dates that will go stale
  without an owner.
- English is the project default; if a repository needs another language,
  record the exception in the file header.

## CF-08 -- Test before and after

Treat the context file as a prompt change with a cost. Use the paired method:

1. Select at least 20-30 real issues or tasks from the repository.
2. Run the same agent, model, and harness with and without the file.
3. Use at least three seeds where the harness is stochastic.
4. Record success, steps, input/output tokens, wall-clock, and cost.
5. Ablate sections (commands, conventions, overview) and keep only what moves
   a metric.

A 20-30 task set is enough to detect the cost penalty; a single-digit success
delta needs a larger set. If the file does not improve success, keep it only
as an efficiency and routing aid, and say so.

## CF-09 -- Maintenance

- Name an owner for the file.
- Review it when the build system, test command, package layout, or agent
  harness changes.
- Delete stale lines. A wrong command is worse than a missing one: it sends the
  agent down a path that costs tokens and erodes trust.
- Record material changes in the repository changelog, like code.

## CF-10 -- Security boundary

- A context file is not an injection defense. It cannot make untrusted content
  safe. Keep the data-not-instructions rule, least-privilege tools, and human
  gates for writes.
- Never put secrets in the file. Report environment variable names only.
- Do not let the file grant capabilities the harness does not enforce. A rule
  that says "never push" is weaker than a permission that removes push.

## Is there a better alternative?

No single format replaces the context file, because each candidate solves a
different problem:

- `AGENTS.md` is the portable, always-loaded entry point. Keep it for that.
- `SKILL.md` is the procedure layer. It is loaded on demand, so it cannot serve
  as the entry point.
- `CLAUDE.md`, `GEMINI.md`, and `.cursor/rules` are host-specific variants.
  Useful when a host requires them, but not a cross-vendor strategy.
- `llms.txt` is for publishing documentation to models, not for repository
  policy.
- MCP resources are host-selected live data, not a guaranteed instruction
  channel.
- CI gates, hooks, and tests are the only layer that enforces. They cannot
  express intent, so they complement the file rather than replace it.

The defensible architecture is the layer map in CF-05: a short context file
that routes to skills, docs, and gates.

## Cross-refs

- `agent-prompt-standard.md` -- prompt structure and budgets
- `subagent-delegation.md` -- delegation rules and handoff contract
- `evidence-duty.md` -- live-fetch and validation duty
- `../docs/AGENTS-TEMPLATE.md` -- the slot-marked router skeleton and checklist
- `../docs/INSTANTIATE.md` -- how a consumer instantiates this library
