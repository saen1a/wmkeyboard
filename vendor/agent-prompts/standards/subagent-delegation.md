# Subagent delegation standard

Status: ACTIVE (2026-10-23).

Class: prompt-generation and orchestration. Applies to any dispatch of a
subagent, worker, or parallel agent by a primary agent or orchestrator, in
coding, research, review, and operations work.

Evidence: `evidence/prompt-research-2026-10.md` (S6-S9, S11, S16). The rules below
are the operational form of that evidence. Each rule is written to be testable;
none relies on a runtime counter or loop state.

## Definitions

- **Orchestrator** -- the agent that owns the plan, the ledger, and the final
  integration.
- **Ledger** -- the durable record of dispatched units and their returns. In
  this repository it is the active `PLAN.md` wave entry or a `provenance/`
  record; it is never the orchestrator's context alone.
- **Subagent** -- an agent invoked with its own context window and a bounded
  task.
- **Handoff** -- the prompt the orchestrator gives the subagent.
- **Artifact** -- a file, patch, report, or structured record that survives the
  subagent's context.
- **Write** -- any mutation of shared state: files, branches, tickets, deploy
  targets, or accepted decisions.

## SD-01 -- Delegation is a cost decision

A subagent is not a free parallelism primitive. Expect roughly 4x chat token
use for one agent and up to 15x for a multi-agent system (S6). Delegate only
when the expected value exceeds that cost.

Record in the ledger: the reason for delegation, the expected token multiplier,
and the check that will decide whether the delegation paid off. If those three
cannot be stated, do not delegate.

## SD-02 -- Hard gate: write isolation

Pass this gate before any other.

- The subagent returns text, a plan, a diagnosis, a patch proposal, or an
  artifact; it does not mutate shared state concurrently with another writer.
- All writes are single-threaded. Parallelize reads, searches, and reviews,
  not writes to the same file, module, or decision space.
- If two units must both write, sequence them or give one unit ownership and
  the other a read-only review role.

Rationale: concurrent writes to the same or related files are a distinct
failure category, present in 26.5% of instances in one 2026 study and 62.9% for
one coding harness (S11). Parallel writer swarms fragment implicit decisions
(S7, S8).

A failing gate means: do not dispatch the unit as a writer. Re-scope it to a
read-only contribution or run it serially.

## SD-03 -- Hard gate: specifiability

Pass this gate before dispatch.

The orchestrator must be able to state, in one paragraph:

- the objective (outcome, not activity);
- the output artifact and its exact schema;
- the boundaries and non-goals;
- the check that decides done.

If the work cannot be specified without the subagent inventing implicit
decisions, it is not delegable yet. Do more planning first, or keep it in the
orchestrator.

Rationale: vague handoffs produced duplicated searches and missed areas in
Anthropic's system (S6). MAST groups delegation failures under system design,
inter-agent misalignment, and task verification, and better role specification
raised success by 9.4% (S9).

## SD-04 -- Positive gates: at least two must hold

After SD-02 and SD-03 pass, require at least two of:

1. **Breadth** -- at least two genuinely independent directions (sources,
   subsystems, hypotheses) that can be explored in parallel.
2. **Context volume** -- the work would exceed a comfortable single window or
   degrade the orchestrator's attention budget.
3. **Independent verification** -- a clean-context verifier can check the
   artifact without seeing the author's reasoning.
4. **Specialization or economics** -- a cheaper or more specialized model/tool
   can do the unit at a lower total cost, or the task value clearly justifies
   the multiplier.

If fewer than two hold, do the work in the orchestrator or use a tool call
instead of an agent. A single tool call is not a subagent.

## SD-05 -- Handoff contract

Every handoff contains these fields, in this order. Keep it short; the
subagent's context is the scarce resource.

```text
OBJECTIVE: <one sentence, outcome not activity>
PHASE: <Plan|PlanReview|Implement|Review|Fix|Verify|Push> and the gate this unit feeds
RUN STATE: <run-state path and checkpoint number, or "none" for a single unit>
CONTEXT: <files, URLs, tickets, and decisions already locked>
OUTPUT: <artifact path plus exact schema; summary length cap>
BOUNDARIES: <what not to touch; write permission, if any>
DONE WHEN: <the check the subagent must run and report>
ESCALATE: <decisions the subagent must return, not guess>
BUDGET: <tool-call or time ceiling; stop when evidence is sufficient>
RETURN: <artifact path, <=1-2k token summary, evidence labels, open questions>
```

Rules:

- Name the sources and tools to use, and the ones to avoid.
- State what is already decided so the subagent does not relitigate it.
- Give the subagent the smallest context slice that lets it start; do not dump
  the orchestrator's whole history.
- A verifier handoff must not include the author's reasoning or conclusion,
  only the artifact, the acceptance criteria, and the evidence commands.
- Name the loop position: which gate the unit feeds and what a pass returns.
  A Review or Verify unit returns findings/evidence, not a new task.
- A unit dispatched inside a long run carries the run-state path and the
  checkpoint it starts from; the subagent returns an artifact and findings and
  never edits run state (LH-02).

## SD-06 -- Return contract

A subagent returns:

- the artifact path (or a proposed patch), not a copy of the whole artifact in
  the message;
- a summary of at most 1,000-2,000 tokens;
- evidence labels: `checked` (command output or file:line from this run),
  `partial` (some checks missing), `unchecked` (no evidence). These are
  return-level labels; repo-wide claim labels (`verified`/`likely`/
  `unverified`) still apply to findings and citations;
- what it did not check, and the open questions it refused to guess;
- for a verifier: severity (H/M/L), evidence, and the exact next gate.

A return that cannot be accepted or rejected by an independent check is not a
usable delegation result.

## SD-07 -- Fan-out and budget

- Default to 3-5 concurrent subagents. Scale up only when the task genuinely
  has more independent directions and the value justifies the tokens.
- Do not spawn a swarm for a bounded task. One 2026 study found dynamic
  concurrency gave little or negative benefit on bounded coding tasks and was
  at least 20% faster on only 12.6% of jointly solved tasks (S11).
- Stop when the evidence is sufficient. More agents after that point add cost,
  not coverage.
- If a subagent returns insufficient evidence, refine the handoff once. If it
  still fails, escalate or do the unit in the orchestrator.
- A subagent that reaches its budget stops, records the partial artifact, and
  returns partial evidence. It never claims completion from a partial run.
- Declare a leaf cap for the fan-out and a minimum budget to spawn: a child
  below the floor cannot finish its unit, so the spawn is refused and the unit
  is done in the orchestrator or split smaller. The cap and the floor are stated
  before the fan-out, not discovered during it.

## SD-08 -- Model and tool assignment

- The orchestrator should be at least as capable as the workers for planning
  and synthesis. A weaker model deciding when to escalate to a stronger one is
  the failure mode Cognition calls out in its "smart friend" pattern (S8).
- Use the cheapest model that passes the unit's check for read-only scouting,
  extraction, and mechanical review; use a stronger model for synthesis,
  contested decisions, and final verification.
- Give each subagent the minimum tool allowlist its unit needs, under a
  deny-by-default posture: an unnamed tool is unavailable.
- A subagent that only reads must not carry write tools.

## SD-09 -- Verification separation

- The generator and the verifier must not share the author's context or
  conclusion. Clean-context review is the best-supported pattern: it caught
  about 2 bugs per PR, 58% severe, in Cognition's deployment (S8).
- Prefer a mechanical check (test, linter, schema, exit code) over a
  judgment-only review. If no mechanical check exists, state that the result
  is unverifiable-by-command.
- Verification is not a vote. One verifier with evidence outranks several
  agents agreeing without evidence.
- Loop handling: a failed Review or Verify returns the exact finding or evidence
  and the next gate; the orchestrator routes Fix -> Review -> Verify. A
  subagent never marks its own finding fixed.
- At run scope, the orchestrator also runs the integrated acceptance gate. Unit
  evidence is not a substitute for the run-level proof (LH-10).

## SD-10 -- Anti-patterns

Do not:

- run parallel writers on the same artifact or decision space;
- delegate a task you cannot specify;
- give a subagent the orchestrator's full history "for context";
- ask the author to review its own work as the only verification;
- spawn more agents to compensate for a vague plan;
- let a subagent silently expand its scope;
- accept a summary as proof of a command that was not run;
- copy a large artifact through the orchestrator when an artifact path will
  do.

## SD-11 -- Evaluation and re-baseline

- Record model, harness, seed, date, token use, and wall-clock for every
  delegation experiment in the ledger.
- Measure against a single-agent baseline on the same model and harness. A
  multi-agent gain without a baseline is an anecdote.
- Re-run the baseline when the model or harness changes. Harness-induced
  variance can exceed model-induced variance (S16).
- Remove a delegation pattern that does not beat its baseline after the cost
  is counted.

## SD-12 -- Delegation transfers no authority

A dispatch is a routing act, not a grant (`work-authorization.md` WA-05).

- The handoff carries the original request verbatim plus routing facts: the
  source reference, the unit it belongs to, and an explicit constraint the
  requester stated. It carries no requirements, plan, acceptance criteria,
  example set or policy checklist the dispatcher invented.
- A routing note is bounded (30 words or fewer) and names background or a
  requester's constraint only. Anything longer is a plan.
- The receiving agent re-derives scope from the original material. "The
  dispatcher accepted it" never substitutes for reading the source, and a
  receiver that cannot reach the source reports that limitation instead of
  treating the note as complete.
- A receiver that finds the work outside its unit, or belonging to another
  unit, hands it back once with a one-sentence reason and does not acknowledge
  it as done. A dispatcher never re-attaches a handed-back item to the same
  unit.
- The dispatcher does not investigate the problem it routed, does not read code
  or logs to form an opinion, and does not turn a worker's question into its own
  technical decision.
- Evidence: `../docs/knowledge-base/superagent-prototype-2026-11.md` (mechanism
  table M3: a spawn record points at the parent's grant, never at a wider one).

## Failure-mode map

Use the MAST categories as a pre-dispatch checklist (S9):

| Category | Question before dispatch |
|---|---|
| System design | Is the role, tool set, and output schema specified? |
| Inter-agent misalignment | Could two units make conflicting implicit decisions or duplicate work? |
| Task verification | Is there an independent check, and who runs it? |

## Cross-refs

- `agent-prompt-standard.md` -- prompt structure, budgets, tool allowlists
- `agent-context-files.md` -- repository-level context file rules
- `code-review-contract.md` -- reviewer severity and evidence contract
- `evidence-duty.md` -- live-fetch and validation duty
- `../skills/general/subagent-delegation/SKILL.md` -- operational checklist
