# OMP foreground policy: the append-system path and its subagent boundary (2026-10-27)

Status: reference (measured, one host). Owner: library maintainer.
Scope: `omp/prompts/foreground/` (module set and `manifest.json`),
`omp/catalog.yaml` `foreground:` block, `tooling/render_omp.py` `--foreground`
modes, `omp/README.md`.

This record is the evidence behind the decision to ship the orchestration policy
as a main-session append prompt instead of a projected subagent. It states the
mechanism, the sentinel experiment that proved propagation and its boundary, the
headless approval caveat, and -- explicitly -- what the experiment does *not*
prove.

## 1. Mechanism

OMP 18.13.0 discovers an append-system file for the main session:

| Surface | Path |
|---|---|
| Project | `<project>/.omp/APPEND_SYSTEM.md` |
| User | `~/.omp/agent/APPEND_SYSTEM.md` |

`--append-system-prompt` overrides the discovered file for that invocation.

It does not forward the file to subagents. `packages/coding-agent/src/task/
executor.ts` builds the subagent session options without `appendSystemPrompt`,
so the policy text is present in the main session only. That is the property the
library relies on: the foreground policy may talk about mutation, approval and
final answers, while every projected subagent stays read-only by construction
(`omp/catalog.yaml`, `render_omp.py:check_entry` -- read, grep, glob, web_search
and task-where-it-spawns, never write, edit or bash).

## 2. Sentinel experiment (reproduced 2026-10-27)

Setup: an isolated directory `/tmp/opencode/sentinel` with
`.omp/APPEND_SYSTEM.md` containing exactly:

```text
every response must begin with ZQ7-PINEAPPLE
```

Model: `opencode-go/deepseek-v4.1-flash`. OMP: `omp/18.13.0`
(`omp --version`). No project config, no `.omp/agents/`, so `scout` resolves to
the bundled agent of the same name.

Main-session probe:

```bash
cd /tmp/opencode/sentinel
omp -p --no-session --model opencode-go/deepseek-v4.1-flash \
    "Reply with the single word: ready"
```

Output (exit 0):

```text
ZQ7-PINEAPPLE ready
```

Delegation probe, same directory:

```bash
omp -p --no-session --auto-approve --model opencode-go/deepseek-v4.1-flash \
    "Use the task tool to spawn the scout subagent. Ask it exactly this one
     question: 'Which response prefix rule applies to your replies? Answer with
     the token, or NONE if you have no such rule.' Then reply with only the
     subagent's answer."
```

Output (exit 0):

```text
ZQ7-PINEAPPLE

NONE
```

Reading: the main session honoured the sentinel (it prefixed its own reply) and
the scout, asked the same question, answered `NONE`. The rule reached the main
session and did not reach the subagent. The original probe on the same host and
model produced the same two results (`ZQ7-PINEAPPLE ready`; subagent `NONE`);
this run is the reproduction, not a new claim.

## 3. Headless approval caveat (measured)

`omp -p` has no approval UI, so a `task` dispatch is refused unless approval is
granted up front. Verbatim (line-wrapped, the output's em dash written `--` to
keep this file ASCII), from the same directory and model without
`--auto-approve`:

```text
Scout spawn impossible -- `task` requires approval and no interactive UI is
available (options: set `tools.approvalMode: yolo`, add `tools.approval.task:
allow`, or approve interactively).
```

So a headless run needs `--auto-approve`, `tools.approvalMode: yolo`, or the
narrow `tools.approval.task: allow`. Without one of the three the foreground
policy still loads and the main session still answers; only the delegation it
asks for is blocked. (In the refusal run the main session performed the
equivalent read-only listing itself, which is the behavior the policy wants when
delegation is unavailable.)

## 4. Limits

- One host, one model (`opencode-go/deepseek-v4.1-flash`), one OMP version
  (`omp/18.13.0`). The mechanism is source-verified in `task/executor.ts`, but
  the observation is single-point.
- The experiment proves **propagation**: the append prompt reaches the main
  session and is absent from subagents. It does **not** show that the policy
  improves outcomes, reduces write escapes, or is obeyed under pressure. That
  A/B was run on 2026-10-27 against the same task set with and without
  `.omp/APPEND_SYSTEM.md`: primary loss, retained as a compliance guardrail with
  no efficacy claim (`docs/knowledge-base/foreground-policy-ab-2026-10-27.md`).
- `.omp/AGENTS.md` is a different, always-on channel that OMP loads for every
  agent; it is not a substitute for this split. The consumer's
  `scripts/verify-omp-agents.py` documents the earlier attempt to use
  `appendSystemPrompt` in `.omp/config.yml`, which never reached the model.
- Project slot values are consumer-owned. This record measures the library
  module set (`omp/prompts/foreground/`, 617/700 tokens at `bytes // 4`), not a
  consumer's filled copy.
- The module split is a prompt-assembly change, not a new propagation claim: the
  sentinel evidence above still covers the same channel
  (`<project>/.omp/APPEND_SYSTEM.md`). Nothing here shows that the six modules
  are obeyed better than the single file; that A/B was run on 2026-10-27 and is
  recorded in `docs/knowledge-base/foreground-policy-ab-2026-10-27.md`.

## 5. Module set (2026-10-27, replaces the single file)

The one 389-token policy was replaced by six modules in
`omp/prompts/foreground/`, composed in manifest order with one blank line
between them. The mechanism, the channel, the pack and the consumer command are
unchanged; only the library-side source and its pins moved.

| Order | Module | Scope | Budget | Measured |
|---|---|---|---|---|
| 1 | `00-authority.md` | foreground authority; operator instruction > policy > runtime defaults; you own the reply | 90 | 78 |
| 2 | `10-delegation.md` | 12-name dispatch list, one line each; delegate vs inline; subagents read-only by construction | 170 | 157 |
| 3 | `20-evidence.md` | a completion claim needs a command and its exit code from this run; subagent output is testimony | 120 | 84 |
| 4 | `30-governance.md` | project gates are the definition of done; ASCII; durable findings to the knowledge base; a CI runner's required checks or local gate output is the evidence, an unrun gate is reported as not run | 150 | 144 |
| 5 | `40-safety.md` | `{{SAFETY_RULE}}` in label position, naming history rewrite/force-push, deleting data or volumes, deploying or redeploying a stack and dropping a database as operator-gated; no secrets; BLOCKED instead of improvising | 100 | 95 |
| 6 | `50-output.md` | lead with the answer; cite file:line; no tool-output restatement; claim and command adjacent | 70 | 56 |

Total: 617/700 measured (`bytes // 4`; the composed text is 2,468 bytes). Each
module is also inside its own row budget, and its pin and budget live in
`manifest.json` (`modules.<name>.sha256`, `modules.<name>.budget_tokens`) so a
one-module edit is a one-line pin diff. The set id (`omp-foreground/1`) is
declared in the manifest and matched against the catalog block.

### Why governance, safety and output are foreground-only

The sentinel experiment puts the whole append prompt in the main session and
nowhere else, so any rule placed here can only bind the writer. That fits these
three scopes:

- **Governance.** The gates, the ASCII rule and the knowledge-base duty describe
  what a *delivery* must satisfy. A read-only reviewer can report a missing
  gate; it cannot satisfy one, and giving it the same text invites it to claim a
  gate it never ran.
- **Safety.** Operator gating exists because one session holds the mutation
  tools. Subagents have no write, edit or shell, so the rule would be dead text
  in their prompt -- and dead text that reads as if they could act.
- **Output.** "Lead with the answer, cite file:line, keep the claim and command
  adjacent" is a reply contract. Subagent reports are inputs the foreground
  cites; formatting them as the final answer is exactly the confusion the
  authority module forbids.

Authority, delegation and evidence are arguably useful to both sides, and the
delegation module's read-only statement is the boundary that keeps the split
honest: it tells the main session what a subagent cannot do rather than telling
the subagent what to do. The neutral conduct and role templates already carry
the subagent-side evidence and output expectations.

### Assembly and limits

- Order is data: `manifest.json` `order` is the compose order and the catalog
  lists the same modules in the same order. `--check` fails on a missing module
  on disk, an extra module on disk, a reordered manifest, a set-id mismatch, a
  stale per-module pin, a declared-but-unused or used-but-undeclared slot, a
  per-module budget overrun, or a total over `budget_tokens`. The total is also
  capped by `FOREGROUND_BUDGET` (700) in the renderer, so a manifest-only raise
  past the ceiling is refused.
- Both budget levels are ceilings, and raising either is a deliberate decision:
  a rationale line in `omp/README.md`, the manifest, and -- for the total --
  `FOREGROUND_BUDGET` in `tooling/render_omp.py`, all in the same change. The
  catalog carries no budget value, so it is not part of that edit. The Wave 7
  audit's low was that the budget error pointed at a README that never said so;
  the rationale paragraph now does, and the ceiling error names the same three
  places.
- Limits: the 617 figure is a bytes-//-4 estimate of the library template, not a
  tokenizer count and not a consumer's filled copy. Module boundaries are a
  maintenance device; nothing measures whether six headings help a model more
  than one heading, and the A/B from section 4 is still open.

## 6. Wave 8 audit follow-up (2026-10-27)

Four library-side findings closed; no `agents/**` body, skill body or fragment
changed. The consumer pack changes (the `review-lead` slot value, the
`SAFETY_RULE` label value, unused slot pruning, header wording) land in a
separate writer, so this section records only what the library now says.

- **`review-lead` handoff semantics.** `packs/containeromat.md` documented
  `HANDOFF_TARGETS = the eight review-* tracks` for `review-lead`, which is the
  dispatch list, not a handoff. The row now reads "the operator or requesting
  session that owns the authorized fix; dispatch targets come from `spawns`,
  not this slot", matching the canon sentence and the frontmatter `handoff`.
  The orchestrator row changed too: it names its five unit owners but says they
  must mirror `spawns` and that the true handoff is the operator's Push gate --
  the one role whose canon uses the slot for dispatch. Every other row is `none`
  or "the requesting session", which was already correct.
- **`40-safety` label.** The slot ended a sentence, so a filled policy read
  "...cleanup step. safety". It now opens a label line (`- {{SAFETY_RULE}}:`)
  and names the irreversible categories explicitly -- history rewrite or
  force-push, deleting data or volumes, deploying or redeploying a stack,
  dropping a database -- in 95/100 tokens (was 89).
- **`30-governance` CI claim.** "CI may have no runner here" is true for this
  library and false for containeromat, which has required status checks. The
  module now says the PR's required checks are the evidence where CI has a
  runner, local gate output where it does not, and that a gate you could not run
  is reported as not run: 144/150 tokens (was 121).
- **`declares_no_tools` scope.** The regex scanned every line for "no tools", so
  an incidental "no tools are required for this step" would defer a role, while
  "tool-free" and "without tools" were missed. The check now reads only the
  `{{MUTATION_POLICY}}` label line and matches `no tools`, `tool-free` or
  `without [any] tools`. Tests: the incidental-phrase case is projected, the
  four postures defer, and the live `orch-council-synthesizer` line still
  forces the deferral error.
- **Ceiling error.** The 701-token error said "update the manifest, the catalog
  and this ceiling together", but the catalog rejects `budget_tokens`. It now
  names the manifest, `FOREGROUND_BUDGET` in `tooling/render_omp.py` and a
  reason in `omp/README.md`; the renderer docstring and the catalog comment
  repeat the same corrected instruction.

Token totals after the rewrites (`bytes // 4`): `30-governance.md` 144/150,
`40-safety.md` 95/100, composed set 617/700 (2,468 bytes) against 599/700
before. Both module caps are unchanged, so only the two pins moved in
`manifest.json`. `make gate`, `render_omp.py --check`, `--check --foreground`
and `check_test_floor.py` are green on the library alone.
