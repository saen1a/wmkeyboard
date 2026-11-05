# STOPP gate standard

Status: PILOT (2026-10-23). The fast path is evidence-backed by the STOPP
comparison, but the fast path itself has not yet been measured in production.

Class: process gating for change execution. It preserves the upstream STOPP
limits and adds one measured fast path. It does not override HALT: HALT still
outranks every gate.

Evidence: `docs/knowledge-base/stop-gate-experiment.md` (72 graded runs, seeds
7/11/23). STOPP scored 0.963 on the safety subset vs 0.334 for direct execution;
the gate over-fired on comment-only edits. The fast path is an
**instrumented hypothesis** derived from that result (SG-09), not a measured
variant yet.

Upstream: `containeromat:AGENTS.md` STOPP S-1..S-5 and
`docs/rules/41-process.md`. This standard is adopted only when the consumer
opts in.

## The four regimes

| Regime | Use | Cost |
|---|---|---|
| HALT | A halt trigger fires | Stop, ask, no artifact |
| Full STOPP | Default for behavior change and any risk trigger | PROPOSE -> STOP -> APPLY -> Verify -> STOP |
| Fast path | One-file comment/format/typo edit with verification | Apply -> Verify, no PROPOSE/STOP |
| Direct | Not allowed for changes under this standard | Measured quality loss |

## SG-01 -- Full STOPP is the default

Behavioral, schema, persistence, security, network, deploy, or multi-file work
uses full STOPP. A missing required fact is HALT (HF-01), not full STOPP. The five upstream limits still apply: one idea,
at most three files, about 50 lines per file, no speculative fixes, and wait
for explicit `go`.

Full STOPP is a safety wrapper around the workflow loop, not a replacement:
PROPOSE is `Plan` plus the `PlanReview` gate (WL-15), APPLY is Implement, and
Verify is the proof loop. A Verify failure re-enters Fix -> Review -> Verify;
the final STOP records the gate. Only the closed fast path (SG-01..SG-09) may
skip a separate Review, and the fast path carries no Plan phase, so it neither
writes a spec nor reviews one (WL-11).

## SG-02 -- Fast-path eligibility is a closed list

All of these must hold:

1. exactly one file and at most 50 changed lines (`--lines`);
2. the edit is comment-only, whitespace-only, formatting-only (parsed artifact
   unchanged), or a spelling fix in a comment or prose;
3. no behavior, schema, persistence, auth, network, dependency, or deploy
   surface changes;
4. the verification command exists and runs in the same step;
5. no exception-registry conflict and no missing required fact. A missing fact
   is HALT. Coverage by an exception without a conflict downgrades to full
   STOPP; a conflict is HALT.

If any condition is unknown, use full STOPP. "Small diff" alone is not
eligibility.

## SG-03 -- Never fast-path behavior

A one-line behavior change is still behavior. A dependency bump, key rename,
port change, healthcheck change, image tag change, or permission change is full
STOPP even at one line.

## SG-04 -- Verification is not optional

A skipped check is `hold` with its reason; a stub artifact is a failed artifact
and returns to Fix; only a recorded exemption closes `Ready (unverified)`
(`verification-integrity.md` VI-02, VI-03, VI-06; WL-05).

The fast path skips PROPOSE/STOP, not verification. Run the project's proof
command, quote the exit code, and record the result. A fast-path edit without a
verification command is full STOPP.

## SG-05 -- HALT and the exception registry always apply

Coverage by an exception registry downgrades the fast path to full STOPP; a
conflict between the edit and a registered exception is HALT. Do not override
an exception because the edit looks cosmetic.

## SG-06 -- Classify before editing

State the classification and its reasons before touching the file:

```text
Gate: fast-path | full-stopp | halt
Files: ...
Kind: comment | format | typo | behavior | schema | security | deploy
Verification: <command>
Reason: <one line>
```

A fast-path classification without a verification command is invalid; full
STOPP and HALT may record `-`.

## SG-07 -- One fast-path step, then stop

The fast path covers one edit and its verification. It does not chain edits.
The next change is classified again.

## SG-08 -- No free-form risk judgment

Use the checklist in SG-02/SG-03. The experiment's free-form "risk" arm was
more permissive than STOPP and lost the file-scope and verification cases; do
not replace the checklist with a model's opinion.

## SG-09 -- Measure the gate

Track fast-path usage, escaped defects, and verification failures. Re-baseline
when the model or harness changes (MC-03). If fast-path escapes appear, remove
the eligibility class that caused them.

## Consumer adoption

The consumer keeps its own S-1..S-5 text and adds the fast-path paragraph plus
the classifier output. This library does not edit the consumer's `AGENTS.md`;
see `docs/knowledge-base/consumer-stopp-fastpath.md` for the exact patch.

## Cross-refs

- `halt-taxonomy.md` -- HALT and STOPP interaction
- `agent-prompt-standard.md` -- AP-13.2 authority chain
- `../tooling/classify_change.py` -- the checklist implementation
- `code-review-contract.md` -- review and fix handoff
- `../docs/knowledge-base/stop-gate-experiment.md` -- evidence
- `../docs/knowledge-base/consumer-stopp-fastpath.md` -- adoption steps
