# AGENTS.md

This repository is a vendor-neutral library of agent prompts, role templates,
skills, and standards. It is not a runtime roster: projects select and
instantiate the assets they need.

## Canonical sources

| Need | Read |
|---|---|
| Project overview and layout | `README.md` |
| Agent/role definitions | `agents/<domain>/` |
| Task prompts | `prompts/tasks/` |
| Skills | `skills/` |
| Agent packs | `tooling/render_agents.py`, `docs/INSTANTIATE.md` |
| Normative rules | `standards/` |
| Long-horizon runs | `standards/long-horizon-runs.md`, `standards/run-state.schema.json`, `standards/run-journal.schema.json`, `tooling/run_state.py`, `tooling/check_run_journal.py` |
| Token/cache policy | `standards/prompt-assembly.md` AS-09..AS-12, `standards/cache-profiles.json`, `tooling/check_token_efficiency.py` |
| Tool-set stability | `standards/tool-set.md` TS-01..TS-10, `standards/tool-set.schema.json`, `tooling/check_tool_set.py` |
| Test identity guard | `tooling/check_test_floor.py`, `tooling/test-manifest.json` (add-only; `--write` merges, `--write --allow-removals` prunes) |
| Shared byte-exact blocks | `fragments/` |
| Commands | `commands/` |
| Evaluation cases | `evals/` |
| Failure set, proposal ledger, re-baseline trigger | `evals/optimization/`, `tooling/check_failure_set.py`, `tooling/check_optimization_ledger.py`, `tooling/check_rebaseline.py`, `docs/knowledge-base/optimization-loop-2026-10.md` |

## Rules

- `agents/`, `prompts/tasks/`, and `prompts/workspace/` are the only canonical roots;
  the legacy `roles/`, `tasks/`, and `workspace-prompts/` shims were removed in 2.0.0.
- Treat `.kilo/`, `.claude/`, `.cursor/`, and other vendor directories as
  consumer adapters, not as the source of truth. The neutral source is this
  repository's `agents/`, `prompts/tasks/`, `skills/`, and `standards/`.
- Read `standards/agent-prompt-standard.md` and
  `standards/workflow-loop.md` before changing a role, task, or fragment.
  Read `standards/long-horizon-runs.md` before changing run state, checkpoint,
  budget, or resume behavior, and validate any run state with
  `python3 tooling/run_state.py check RUN.md`.
- Run the gates in `CONTRIBUTING.md`; a fragment change also requires a
  template version bump.
- Do not edit a fragment in a consumer copy. Re-vendor from this tree and pin
  the hash.
- Keep ASCII and English in prompt assets.
