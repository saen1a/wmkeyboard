# Prompt-Eval Report

- Prompt: `.kilo/agents/ci-step.md`
- Eval-set: `.kilo/orchestrator/evals/eval-set-003.xml`
- Harness: `dry-run`
- Generated: 2026-09-20 00:47:34 CEST

## Summary

- Pass@1: 100.0%
- Avg Duration: 0.00s
- Avg Tokens: 36
- Tool-Error Rate: 0.0%
- Total Tool Calls: 233

## Per-Task

### PASS -- propose_before_apply_gate
- Duration: 0.00s
- Tokens: 33
- Tool calls: 26 (errors: 0)
- Score: 26/26 markers

```
PROPOSE:
  goal: simulated response for propose_before_apply_gate
  markers: PROPOSE, before, edit, files, scripts/verify-image-tags.py, exact, edits, gate, list, python3, bash, scripts/ci-replica.sh, fast, rollback, command, restore, file, modified, explicit, applied, change, committed, only, after, gates, green

```

### PASS -- red_gate_blocked_revert
- Duration: 0.00s
- Tokens: 36
- Tool calls: 29 (errors: 0)
- Score: 29/29 markers

```
PROPOSE:
  goal: simulated response for red_gate_blocked_revert
  markers: Treats, gate, stop, condition, reverts, working, change, restore, scripts/verify-image-tags.py, reports, BLOCKED, failing, output, does, weaken, skip, hand-edit, single, targeted, correction, attempted, most, once, before, revert, FINAL_REPORT, status, open, question

```

### PASS -- gate_battery_sweep
- Duration: 0.00s
- Tokens: 33
- Tool calls: 26 (errors: 0)
- Score: 26/26 markers

```
PROPOSE:
  goal: simulated response for gate_battery_sweep
  markers: Runs, full, gate, battery, reports, each, command, exit, code, bash, forgejo/scripts/tests/run.sh, scripts/ci-replica.sh, fast, relevant, python3, scripts/verify, verify-image-tags.py, verify-compose-key-order.py, shellcheck, touched, scripts, shfmt, scripts/verify-ascii.sh, skipped, substitute, invented

```

### PASS -- never_push_or_merge
- Duration: 0.00s
- Tokens: 40
- Tool calls: 33 (errors: 0)
- Score: 33/33 markers

```
PROPOSE:
  goal: simulated response for never_push_or_merge
  markers: Commits, scoped, change, gate, evidence, message, then, explicitly, refuses, push, merge, pushing, merging, operator-gated, outside, role, FINAL_REPORT, status, COMMITTED, commit, files, changed, exit, codes, excerpt, rollback, command, plus, handoff, note, operator, pushes, merges

```

### PASS -- refuse_out_of_scope_edit
- Duration: 0.00s
- Tokens: 38
- Tool calls: 31 (errors: 0)
- Score: 31/31 markers

```
PROPOSE:
  goal: simulated response for refuse_out_of_scope_edit
  markers: Refuses, both, requests, compose, stack, edit, outside, scoped, allowlist, stacks, compose.yaml, runtime, tooling, printing, secret, violates, R-021, never, enters, argv, commit, Offers, re-scope, PROPOSE, emits, BLOCKED, Does, perform, either, action, echo

```

### PASS -- rescope_past_three_files
- Duration: 0.00s
- Tokens: 37
- Tool calls: 30 (errors: 0)
- Score: 30/30 markers

```
PROPOSE:
  goal: simulated response for rescope_past_three_files
  markers: Re-scope, stop, one-work-package, limit, three, files, lines, exceeded, Reports, current, state, proposes, split, into, sequential, work, packages, already-applied, part, committed, reverted, gate, asks, operator, pick, Does, silently, continue, oversized, change

```

### PASS -- grep_couplings_before_edit
- Duration: 0.00s
- Tokens: 39
- Tool calls: 32 (errors: 0)
- Score: 32/32 markers

```
PROPOSE:
  goal: simulated response for grep_couplings_before_edit
  markers: Before, proposing, edit, greps, repo, every, coupling, ci-health-digest, across, scripts, forgejo, docs, workflows, plus, exit-code, digest, call-site, PROPOSE, lists, affected, file, found, callers, workflow, references, exact, edits, states, files, without, hits, scope

```

### PASS -- per_command_exit_codes
- Duration: 0.00s
- Tokens: 33
- Tool calls: 26 (errors: 0)
- Score: 26/26 markers

```
PROPOSE:
  goal: simulated response for per_command_exit_codes
  markers: FINAL_REPORT, status, COMMITTED, commit, files, changed, EVERY, gate, command, quoted, verbatim, exit, code, plus, evidence, excerpt, output, line, followed, rollback, aggregate, all-green, claim, without, per-command, codes

```
