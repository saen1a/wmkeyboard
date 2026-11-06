# Adopted mechanisms from three external agent systems (2026-10-31)

Status: change record, 2026-10-31. Owner: library maintainer.
Scope: what was taken from three upstream projects into this library, what was
rejected, and what the change does **not** prove.

## 1. Sources

| Source | Snapshot | What it is |
|---|---|---|
| https://github.com/hedgerow-dev/rowan | `6766dd9`, 2026-10-23 (0.4.2) | Python SAST engine with an explicit AI/agent security surface: `passes/instruction_smuggling.py`, `passes/agent_flow.py`, `passes/multiagent.py`, `core/agent_privilege.py`, `passes/pii_egress.py`, `core/mcp_config.py`, `ignore.py`, `baseline.py`, `core/rule_class.py` |
| https://github.com/hmanoor/kageops-core | `2357cc5`, 2026-08-01 | TypeScript agent orchestration engine: `src/orchestrator/acceptance-gate.ts`, `spec-rule-engine.ts`, `build-verification-gate.ts`, `retry-budget.ts`, `cost-tracker.ts`, `src/agents/verification-gate.ts`, `output-parser.ts`, `src/agents/risk-scorer.ts` |
| https://github.com/Spielewoy/autoprompt-skill | `fe1ded6`, 2026-10-04 (2.1.0) | Cross-provider agent workflow with machine-readable contracts: `agents/contracts/{roles,routes,gates,providers,state-machine,plain-language}.json` plus 32 JSON Schemas, `agents/<provider>/workflow/autoprompt-gate.js`, `agents/<provider>/native-projection.json` |

Method: read-only extraction pass per source (rule inventory, gate mechanics,
contract shapes, test methodology), then a gap matrix against this library's
surfaces (`standards/`, `skills/`, `agents/`, `tooling/`, `evals/`), then
implementation of the mechanisms that were portable and checkable. Nothing was
copied verbatim: each adopted item is restated as a project-neutral rule with a
deterministic check or a schema/example pair.

## 2. Adopted, by source

### 2.1 Rowan -> `standards/prompt-security.md`, `tooling/check_prompt_security.py`

| Mechanism (upstream) | Adopted as |
|---|---|
| Decode Tags block + invisibles, report an override phrase present only in the decoded shadow (`analysis/unicode_smuggling.py:47-96`) | PS-03 + checker two-pass detection, with the same deliberate refusal to blanket-NFKC |
| Instruction files and prose scanned as attacker-authored data, never forwarded as instructions (`file_scan.py:34-39`, `hunt_inventory.py:101`) | PS-02, PS-14 / VI-14 |
| Tool metadata TOCTOU: description/inputSchema changing after approval (`mcp_tool_metadata.py:109`) | PS-04 (pin the definition, re-approve on change) |
| Privilege asymmetry on multi-agent handoff, with a low-confidence, opt-in rule (`multiagent.py`, `core/agent_privilege.py`) | PS-05 (low-trust source -> high-privilege action needs a gate) |
| PII to third-party model egress; sanitizer exemption; local host exemption (`pii_egress.py:24-33`) | PS-06 (egress is deliberate; redact before, local is no licence) |
| MCP config as trust root: secret-shaped env, unscoped flags, root scope, `http://` (`core/mcp_config.py:174-246`) | PS-09 |
| Approval callbacks that never ask the user (`mcp_sampling_approval.py:120-136`) | PS-08 |
| Inventory vs vulnerability rule class (`core/rule_class.py:33-90`), severity cap for pattern-only evidence | PS-11, PS-10, VI-09 |
| Ignore entry = fingerprint or (rule + path glob) + reason + expiry that lapses silently (`ignore.py:46-115`) | PS-12 |
| Degraded/partial coverage: `summary.degraded`, "No findings, but the scan was INCOMPLETE", refuse a clean exit (`findings.py:119-121`, `cli.py:252-258`) | PS-10, VI-10 (report partial, refuse pass) |
| Instruction files excluded from LLM discovery prompts | VI-14 |

### 2.2 KageOps -> `standards/verification-integrity.md`, `standards/gate-verdict.schema.json`, `tooling/check_gate_verdict.py`

| Mechanism (upstream) | Adopted as |
|---|---|
| Build plan resolution distinguishes "nothing configured" from "failed" (`build-verification-gate.ts:131-173`) | VI-03 (skipped is not passed; "nothing configured" is a fact, not proof) |
| Acceptance criteria extracted from the brief, `must` vs `should`; only `must` blocks (`spec-rule-engine.ts:79-210`, `acceptance-gate.ts:346-349`) | VI-05 (criteria from the request, MUST blocks, SHOULD advisory) |
| Per-suffix artifact shape check: reject chat-summary leads, prose where code is expected, `isLikelyArtifactContent` (`output-parser.ts:283-390`), F-391 gate (`verification-gate.ts:183-187`) | VI-06 (substance floor, per-kind signals, stub fails evidence) |
| Repair task with the anti-repeat clause (`sensei.ts:3938-3998`) | VI-12 (`PRIOR ATTEMPT n FAILED` / `CHANGED:`), bounded by WL-07 |
| Retry ladder: same agent -> alternate -> blocked + human, best-attempt restore (`sensei.ts:4556-4620`, `retry-budget.ts`) | VI-11 (exhaustion terminal, restore the last verified state) |
| Budget kill switch before the call, warn at 80%, budget failure never retries (`cost-tracker.ts:155-165`, `autonaut-agent.ts:993-996`) | VI-11 + LH-09 sentence (terminal, no retry) |
| Task-type evidence table: which evidence proves which kind of unit (`verification-gate.ts:37-53`) | VI-07 / VI-06 evidence matrix |
| Gate modes `block|warn|off` with a closed token vocabulary, default block (`gate-modes.ts:24-46`) | VI-04 |
| Intercept: pause / one-shot guidance / takeover / handback, replay from checkpoints (`sensei.ts:1631-1712`, `autonaut-agent.ts:2361-2410`) | LH-11 "Intercept and handback" |

### 2.3 Autoprompt -> `standards/agent-adapter.md`, `standards/agent-admission.schema.json`, `tooling/check_admission.py`, `omp/admission.json`, `dsh/admission.json`

| Mechanism (upstream) | Adopted as |
|---|---|
| Four-valued capability support and a fail-closed admission policy (`agents/contracts/providers.json:5-125`) | AD-02, AD-03, admission record + checker |
| Generation parity is not runtime admission; missing capability evidence blocks admission (`agents/README.md:3,33`) | AD-04, AD-05 |
| Gate provenance: PASS rejected on empty persona, substituted persona, missing artifact (`autoprompt-gate.js:1071-1085`) | VI-02 (named verifier, not the author) |
| Distinct implement/verify identity assertion (`autoprompt-gate.js:1044-1061`) | VI-02 |
| Stub/fake guards: body under 200 non-whitespace chars, "clean" claim with zero captures, claimed count with zero captures (`autoprompt-ledger-check.js:571-616`) | VI-06, VI-07 |
| Coverage floor with a verify failure below it; no unjustified severity downgrade (`autoprompt-gate.js:3786-3803, 4750-4754`) | VI-08, VI-09 |
| Role instruction schema including "what not to change"; deny-by-default tool policy | AP-02 addition, AP-10, SD-08 |
| Leaf cap plus minimum budget to spawn (`autoprompt-gate.js:232`) | SD-07 addition |
| Explicit activation only; no host-inferred spawn; aliases closed and read-only | AD-08, AD-06 |

## 3. Rejected, with reason

| Candidate | Reason |
|---|---|
| KageOps' full six-phase product lifecycle and the Autonauts roster | Product model, not a portable prompt rule; this library has its own six-phase loop and no roster (`WL-01`, CATALOG notice) |
| Autoprompt's 82-transition state machine and 32 physical role ids | A runtime implementation with a generator and provider-specific launchers; the portable part is the invariants (admission, provenance, distinct identity), all adopted. Carrying the machine would duplicate `run-journal.schema.json` |
| Autoprompt `plain-language.json` forbidden-term map | Style enforcement with no functional claim; the useful half (one canonical description per user-visible code) has no counterpart surface in a prompt library |
| KageOps `speciality-matrix` EMA routing and model router fallback | Runtime learning state; nothing checkable in a static library, and a fixed fallback risks silently downgrading a model (cf. `MC-02`) |
| Rowan's SCA/OSV integration, CVSS4 scoring, web-exploit agent | Application-security product surface, not a prompt-system rule |
| Rowan's full taint engine | Cannot be restated as a prompt-surface check; the portable half is the asymmetry rule (PS-05) |
| Rowan finding fingerprints in the findings ledger | The ledger's identity is already stable by `F-<n>` and never reused (WL-13). Adding a fingerprint column would change the ledger contract for marginal gain; a fingerprint matters for a baseline diff, which this library does not keep |
| Copying Rowan rule YAML or Autoprompt JSON contracts verbatim | Licence and drift risk; every adopted rule is restated in this library's vocabulary and pinned by its own check |

## 4. What changed in this repository

New standards: `verification-integrity.md` (VI-01..VI-14), `prompt-security.md`
(PS-01..PS-14), `agent-adapter.md` (AD-01..AD-10).

New contracts and examples: `gate-verdict.schema.json` +
`exemplars/gate-verdict-example.json`, `agent-admission.schema.json` +
`omp/admission.json` + `dsh/admission.json`.

New checkers in `make gate`: `check_gate_verdict.py`, `check_admission.py`,
`check_prompt_security.py`, each with a pytest module (40 + 20 + 24 tests).

New skill: `untrusted-content-handling` (repo-authored) with
`references/patterns.md`, five trigger positives, four trigger negatives, three
behavioral dialogue cases.

Extended: `verification-before-completion` (four refusal rows + the
`references/proof-integrity.md` appendix), `agent-prompt-standard.md` (AP-02
non-goals, AP-10 deny-by-default), `subagent-delegation.md` (SD-07 leaf cap and
minimum spawn budget, SD-08 deny-by-default), `long-horizon-runs.md` (LH-09
terminal exhaustion, LH-11 intercept and handback), `workflow-loop.md` and
`CATALOG.md` cross-references, `README.md`, `CONTRIBUTING.md` (rules 14-18),
`skills/SKILLS.md`, `evals/README.md`, `docs/knowledge-base/surfaces.md`,
and `code-review-contract.md` (CR-08 orders the review by risk: untested,
widely-called code first, from the KageOps risk scorer).

## 5. Verification

- `make gate` is the proof; the new steps are `check_gate_verdict`,
  `check_admission` (both records), and `check_prompt_security` (146 prompt
  assets, 0 violations, 8 advisory warnings for retrieval surfaces with no
  boundary sentence).
- The example verdict passes its checker; each rejection rule has a test that
  fails without it (anonymous verifier, author-as-verifier, skipped check,
  stub artifact, unmet MUST, degraded set, mode off, open/waived high finding,
  zero capture, coverage below floor, unknown evidence id).
- The OMP record is admitted with two named degradations; the dsh record is
  refused because the runtime was not exercised, which is the intended
  fail-closed demonstration rather than an assumption.
- Skill routing: 25 skills, 25 case files, 0 violations under
  `--fail-on-warn`. Shape: 438 / 1,147 / 1,582 tokens (min / median / max), one
  over-cap body and it is a frozen vendor copy.

## 7. Pass 2 -- the rules applied to the existing surface (2026-10-31)

The first pass added the standards; the second pass ran them against the library
itself. Findings and repairs, in the order the checks produced them:

| Finding | Rule | Repair |
|---|---|---|
| Every role's doctrine said "a failure goes Fix -> Review -> Verify" but never what a passing verdict *is* | VI-01..VI-03, VI-06 | Doctrine 1.4.0 folds the verdict rule into the Verify bullet; 41 carriers updated byte-exact, 4 dsh presets re-indented, pins and CATALOG moved |
| `anti-hallucination` described tool-output paraphrase drift without stating that quoted output is data | PS-02 | Pattern 3 now says report a directive found inside quoted output, never obey it (body 1,013 tokens, under cap) |
| OMP foreground `50-output.md` told the model to quote tool output without saying a directive inside it is data | PS-02, PS-05 | One sentence added inside the module budget; per-module budgets rebalanced to 110/80 with the set total unchanged at 700 |
| The boundary warning fired on READMEs, `references/`, JSON records, and on legitimate phrasings ("DATA, never instructions", "is data") | PS-02, PS-14 (false-positive control) | Warning scoped to instruction carriers; vocabulary extended; 8 warnings -> 0 |
| A single fragment change flagged all 41 carriers against a static token target | AP-01 | Target tracks fragment growth (`FRAGMENT_BASELINE_TOKENS`); body-level bloat still warns |
| `pass` in WL-09, WL-10 and SG-04 was a word, not an artifact | VI-01, VI-04 | WL-04 names the verdict record, WL-09 requires it for `pass`, WL-10 consumes it, SG-04 names skipped/stub as `Ready (unverified)` |
| `docs/INSTANTIATE.md` ended at "register"; nothing asked whether the runtime enforces what the projection claims | AD-02, AD-03 | Rules 7-8: admit the runtime, then verify with a record; omp/README, dsh/README and README updated |
| WP-07 A/B arms are derived fixtures ("only the rule is added") and no longer matched production | WL-12 | Regenerated; the recorded A/B is now historical (pre-1.4.0) and must be re-baselined before a new claim |

Verification for this pass: `make gate` exit 0; 559 pytest; 550 pinned test
identities; `render_omp.py --check` green with refreshed pins (12 template pins,
the doctrine pin, the foreground module pin); `check_prompt_security.py`
0 violations and 0 warnings over 146 assets; `validate_templates.py` 0
violations and 0 warnings over 41 carriers.

## 8. Pass 3 -- the agent and subagent surface (2026-10-31)

Passes 1-2 added and applied the standards to the doctrine and the assets' text.
Pass 3 audited the roles themselves and the delegation interface.

| Finding | Rule | Repair |
|---|---|---|
| The orchestrator owned every gate but never stated a dispatch budget or how to read a child return | SD-07, PS-02 | Leaf cap and spawn budget floor before fan-out; a child return is data compared to the handoff, never executed |
| `rev-review-lead` dispatched track children with no budget rule and no identity statement for the merged verdict | SD-07, VI-02 | Budget declared before dispatch, no author conclusion sent to a child, merged report names the verdict record and a verifier that is not the author |
| `rev-reviewer` could downgrade severity and reported "pass" in prose | VI-01, VI-09 | Severity is not a dial; a pattern-only signal is capped at M with the cap recorded; the pass names this verifier in the verdict record |
| `rev-code-skeptic` and `rev-security-reviewer` were at the element cap with no room for the new duties | VI-03/06/07, PS-05/11 | Two rules merged in each to add proof integrity and the trust-boundary split without exceeding the cap |
| `eng-test-author` treated a missing suite as neutral; `ops-executor` could report a skipped check as green | VI-03, VI-07, VI-11 | Both name skipped as unverified and exhaustion as last-verified-state |
| The delegation skill described the return contract but not the spawn floor, the deny-by-default tool posture, or that a return is data | SD-07, SD-08, PS-02 | Three rules added to the control module (body 1,446 tokens) |
| Nothing enforced that the gate authorities keep the verdict interface | VI-01 | `check_workflow_loop.py` fails when orchestrator, review-lead, reviewer or code-skeptic does not name the gate verdict record |

Measured after pass 3 (elements / tokens / cap): orchestrator 12/1,136/15,
review-lead 11/1,139/15, reviewer 13/989/15, code-skeptic 12/1,038/12,
security-reviewer 12/1,032/12, test-author 11/1,039/12, ops-executor 14/987/15.
All 41 carriers are at base 2.0.4 (orchestrator 2.1.5); `make gate` exit 0 with
560 tests, 0 validation warnings, and the projection pins refreshed.

## 9. Pass 4 -- the loop (2026-10-31)

| Finding | Rule | Repair |
|---|---|---|
| WL-07 ("one refinement per gate") and the new VI-13 ("declare a per-gate cycle budget: plan 2, implement 2, ...") were two norms with no authority | WL-07 owns cycles; VI-13 owns verdict content | WL-07 rewritten as the single authority with three invariants; VI-13 reduced to `attempt` handling and `over-bound` refusal |
| The transition table's guards were prose (`no open high or medium finding`), so a gate could be crossed with a sentence | VI-01, VI-03, VI-08 | WL-02 guards name the verdict record and its content for Review -> Verify, Verify -> Ready, Verify -> Fix and Ready -> Push |
| The record schema had a `gate` enum with no content expectation per gate type | VI-05, VI-10, LH-10 | WL-09 gains a per-gate minimum table; `check_gate_verdict` enforces three of them (verify needs a check, acceptance needs a MUST criterion, review needs a listed subject) |
| Nothing executed the loop, so a guard could rot silently | WL-12 (a change without a check is an anecdote) | `evals/loop/drive.py`: 13 scenarios with declared expectations, wired into `make gate`; 5 pytest cases import the guards directly |

Sabotage evidence for the layer split: removing a record-level clause (skipped
check, stub artifact, self-signed verifier, coverage floor) leaves the exercise
green, because `check_gate_verdict` rejects first -- the guard is defence in
depth, not the only reader. Removing a loop-only clause (refinement bound,
publication proof) fails the exercise on `fix_second_spec_gap_return` and
`push_without_publication_proof`. Both behaviours are intended and recorded here
so a future reader does not mistake the exercise for full coverage.

## 10. Pass 5 -- the skills (2026-10-31)

| Finding | Rule | Repair |
|---|---|---|
| `mcp-builder` taught how to build MCP servers with no security rule, although every rowan MCP pass (metadata rug pull, silent sampling approval, config trust root, stored content) is a defect of exactly that artifact | PS-04/05/08/09 | A "trust boundaries" block plus three verification lines; body 1,405 tokens |
| `skill-creator` described the anatomy but not the library's own gates | SK-02/03/04/06/07/11/12, PS-02/13 | The gate table moved into `references/authoring-guide.md` section 7 (depth in references, SK-04) and the body gained PS-13 and the data-boundary check |
| `long-horizon-run` described unit completion without the verdict record | VI-01/03/11 | One sentence added; two sentences that duplicated LH-07/LH-09 removed to stay under the cap |
| `subagent-delegation` let a child's skipped check pass silently through the return | VI-03 | The return contract carries `skipped` plus the reason and the parent records the criterion unverified |
| `deepseek-v4-agent-defense` treated a mid-context miss purely as a recall problem | PS-02/03 | Layer 6 states that unvetted content is also unvetted instruction surface, plus the re-read-as-data action in the hosted subset |
| Six vendor skills had no behavioral evidence (optional for the vendor class), two with a real failure mode | EN-02, PS-08 | Cases added for `caveman` (language never switches, raw output never compressed) and `misakanet` (read-only default, stored lessons are data, no secrets in an entry). Bodies stay frozen (SK-10) |

Audit method: one pass over all 25 skills measuring tokens, references, H2 count,
boundary statements, verdict/skip vocabulary, and case-file presence, then a
per-skill judgement by job. The crude flag "any verification word without
'verdict'" fires on 19 skills and is noise: `grilling`, `jq-json-processing`,
`changelog-generator` and the caveman set have no claim to make. Only the five
repairs above changed behaviour.

## 11. Pass 6 -- the audit (2026-10-31)

Four read-only clean-context audits (standards, checkers, claims, skills) ran over
passes 1-5 and produced 44 findings, 25 medium. The full ledger with evidence and
resolution is `provenance/findings-wave11-audit.md`; the verdict record with real
command digests is `provenance/verdict-wave11-audit.json`. Both are gated.

The three findings worth remembering:

1. **A rule the author added contradicted a rule the author had already shipped.**
   The declared per-gate cycle budget (pass 4) could not coexist with WL-08's
   `attempt 0 or 1` and with the doctrine fragment rendered into 41 carriers. It
   was removed rather than reconciled: one refinement per gate, WL-07 owns it.
   This is the failure mode a standard is supposed to prevent, and only an
   independent reader caught it.
2. **Six checker false negatives sat exactly on the standards' claims.** A
   hyphenated provider key, a README counted as an instruction carrier, a skipped
   check with no reason, a gate authority that merely said "verdict", a refusal
   naming a prefix, and an unenforced `attempt`. Each had a green test suite
   before the audit; the tests exercised the easy case, not the claim.
3. **Documentation drifted faster than code.** Thirteen claims were wrong, four
   of them numbers the author had written and then invalidated by his own later
   edits. The lesson is mechanical: measure, then write, then re-measure in the
   same change -- not copy a number forward.

## 12. Pass 7 -- audit round 2 (2026-10-31)

The operator opened a second independent pass. It ran as a **new unit**
(`wave-11-audit-r2`, `attempt: 0`), not as a second attempt at round 1's gate:
WL-02 starts a new unit at Plan, WL-07 allows one refinement per gate. Records:
`provenance/verdict-wave11-audit-r2.json`, ledger rows F-45..F-66.

Round 1 was too generous about its own work. Four repairs did not hold, ten new
defects existed, six checker holes were open, and 41 of 70 documentation claims
were wrong. Two lessons are structural rather than textual:

1. **A repair needs the same adversarial treatment as the original defect.** Round
   1 fixed F-25 (a negation excusing an injected directive) by narrowing the
   window to a sentence; round 2 showed a semicolon clause and a
   non-documentation colon still excused it. The fix looked correct because the
   test only exercised a full stop.
2. **A number that is copied will drift.** The cure is not care, it is
   generation: `tooling/measure_state.py` writes `docs/measured-state.md`, the
   gate compares it, and CONTRIBUTING makes it the only legal source for a live
   number. Dated changelog entries keep their own measurement and state which pass
   they measured.

A third pattern is worth naming because it recurred three times: a rule was
tightened in one place and left loose in its echo (VI-09 said open-or-waived while
WL-02's guard said open; VI-13 said `over-bound` while the checker accepted any
halt reason; WL-07 removed the budget while the exemplar still carried it). A
cross-reference is only as good as the other copy.

## 13. What this does not prove

- No runtime measurement. The three standards are static rules plus static
  checks; none of them has an A/B or a live-harness result. A rule that is
  checked is not a rule that improves outcomes, and this record claims only the
  former.
- The static prompt-security check cannot prove a runtime boundary exists. It
  catches the asset that ships a payload or a directive; it cannot see a tool
  result at run time.
- The admission records describe declared and mechanically cross-checked
  capability, not observed enforcement inside a host. The `omp` record's
  evidence is the projection and its checker, which is weaker than a wire dump;
  a consumer that dumps the outbound `tools` array should replace it (TS-01).
- The rejected items are rejected for this library's shape. A runtime project
  that needs a retry ladder or a state machine should take them from the
  upstream repositories, which remain the better source for runtime code.
