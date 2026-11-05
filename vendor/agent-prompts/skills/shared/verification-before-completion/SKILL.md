---
name: verification-before-completion
description: Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running verification commands and confirming output before making any success claims; evidence before assertions always
rigid: true
---
<!-- Archetype copy imported from containeromat stacks/deepseek-harness/config/skills/verification-before-completion (pinned 2026-09-19). Canon switch deferred; see PLAN.md wave 2. -->
# Source: https://github.com/obra/superpowers (License: MIT)
# Vendored: 2026-07-15

# Verification Before Completion

## Overview and the Iron Law

Claiming work is complete without verification is dishonesty, not efficiency.

**Core principle:** Evidence before claims, always.

**Violating the letter of this rule is violating the spirit of this rule.**

```text
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

If you have not run the verification command in this message, you cannot
claim it passes.

The evidence is the command and its exit code from this run. When refusing a
claim, name both; "run the tests" without an exit code is not evidence. If you
cannot run it, ask explicitly: "Run `<command>` and give me the output and exit
code."

Refusal shape: "I can't claim fixed. Run `<command>` and paste the output and
exit code; without both, the status is unverified."

## The Gate Function

```text
BEFORE claiming any status or expressing satisfaction:

1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does output confirm the claim?
   - If NO: State actual status with evidence
   - If YES: State claim WITH evidence
5. ONLY THEN: Make the claim

Skip any step = lying, not verifying
```

## Claim vs evidence

| Claim | Requires (fresh, this message) | Not sufficient |
|-------|--------------------------------|----------------|
| "Tests pass" | test command output: 0 failures | previous run, "should pass" |
| "Linter clean" | linter output: 0 errors | partial check, extrapolation |
| "Build succeeds" | build command: exit 0 | linter passing, logs look good |
| "Bug fixed" | original symptom re-tested | code changed, assumed fixed |
| "Regression test works" | red-green cycle: run (pass) -> revert fix -> run (MUST FAIL) -> restore -> run (pass) | test passes once |
| "Agent completed" | VCS diff shows changes | agent reports "success" |
| "Requirements met" | line-by-line checklist | tests passing |
| "Should work now" | run the verification | rationalization |
| "I'm confident" | evidence | confidence is not evidence |
| "Just this once" | full verification | no exceptions |
| "Partial check is enough" | full run | partial proves nothing |
| "Agent said success" | verify independently | delegation is not verification |
| "Different words, so rule doesn't apply" | spirit over letter | paraphrase is not exemption |
| "No tests configured, so nothing to run" | skipped is not passed: record the reason, close as hold |
| "Here is the updated file" / body under 200 chars | narration is not an artifact; a stub fails the shape check |
| "No findings" with zero checks behind it | a fabricated verdict, not a pass |
| "I signed off on my own fix" | the verifier is named and is not the author; else Ready (unverified) |

**Stop phrases -- run the gate, never claim:** "should", "probably", "seems
to", satisfaction before verification ("Great!", "Perfect!", "Done!"), about
to commit/push/PR without verification, trusting agent success reports,
relying on partial verification, thinking "just this once",
tired-and-wanting-work-over -- ANY wording implying success without having
run verification.

## Repo gate and when to apply

In a consuming project the required gate is the project's closeout chain plus
its self-check table: run the project's verification commands fresh, quote the
exit codes, and emit the table inline before any completion or handoff claim.
The operator's push decision is the next step after Verify; a claim that
skips the evidence is not a completion report.

**ALWAYS before:**
- ANY variation of success/completion claims
- ANY expression of satisfaction
- ANY positive statement about work state
- Committing, PR creation, task completion
- Moving to next task
- Delegating to agents

**Rule applies to:**
- Exact phrases
- Paraphrases and synonyms
- Implications of success
- ANY communication suggesting completion/correctness

## Doctrine position

Serves Verify as its gate function: no completion claim without fresh verification evidence from the current message. It is the mandatory check before the operator's Push decision.

**The bottom line:** no shortcuts for verification. Run the command. Read the
output. THEN claim the result. This is non-negotiable.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I already ran it earlier in this session" | Earlier output predates the current change; only fresh output from this message is evidence. |
| "It worked for the similar case" | Similar is not identical; the claim is about THIS change. |
| "The change is too small to break anything" | Small diffs break builds; size is not evidence. |
| "CI will catch it" | CI runs after the claim; the gate requires evidence before the claim. |
| "The user can see it works" | Unverified claims transfer work to the operator. |
| "I'm confident in the fix" | Confidence is not exit-code evidence. |

## Red Flags

- "done/fixed/all green" without commands and exit codes in the same message
- Claims about file contents without a fresh read
- Exit codes reported from memory
- Verification delegated to the reviewer instead of the author
- "Should pass" future tense

## Verification

- Every completion claim is preceded by a fresh run of its proof command.
- The output and exit code are read, not assumed.
- Unverifiable claims are labelled "not yet verified" instead of asserted.
- Read `references/proof-integrity.md` when a command ran green but the verdict
  is still in doubt: skipped checks, stub artifacts, coverage floors, verifier
  identity, repair rounds (VI-01..VI-15, `tooling/check_gate_verdict.py`).
