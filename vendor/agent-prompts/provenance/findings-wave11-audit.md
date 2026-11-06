# Findings ledger: wave 11 audit (2026-10-31)

One row per finding from the four independent clean-context audits of the wave-11
work. Do not delete a row; change its state and append the resolution evidence.
Review passes only when no high or medium finding is `open` or `waived`.

Auditors (verifier identities, none of them the author):
`AuditStandards` (standards consistency), `AuditCheckers` (adversarial input),
`AuditClaims` (documentation versus repository), `AuditSkills` (skills, shape,
evals, routing).

| finding_id | severity | unit | file_line | evidence | acceptance_impact | owner | state | round | decision |
|---|---|---|---|---|---|---|---|---|---|
| F-1 | low | U1 | `standards/prompt-security.md:141` | AuditStandards: PS-10 restated VI-10 and VI-09 and drifted the medium cap | A1 | maintainer | fixed | 1 | PS-10 now cites VI-10 and VI-09, one line each |
| F-2 | low | U1 | `standards/long-horizon-runs.md:368` | AuditStandards: LH-09 restated VI-11 with a second reason vocabulary | A1 | maintainer | fixed | 1 | LH-09 cites VI-11 in one sentence |
| F-3 | low | U1 | `standards/verification-integrity.md:172` | AuditStandards: VI-13 restated WL-07 invariants | A1 | maintainer | fixed | 1 | VI-13 keeps only the record duty and names WL-07/VI-12 |
| F-4 | medium | U1 | `standards/verification-integrity.md:58` | AuditStandards: `warn` promised a pass on SHOULD criteria while the contract refuses every failing check | A2 | maintainer | fixed | 1 | VI-04 `warn` now closes `fix`; no record has to satisfy two rules |
| F-5 | medium | U1 | `standards/stop-gate.md:66` | AuditStandards: SG-04 routed a stub artifact and an unexplained skip to `Ready (unverified)` | A2 | maintainer | fixed | 1 | SG-04 routes skip to `hold`, stub to Fix, exemption to `Ready (unverified)` |
| F-6 | medium | U1 | `standards/verification-integrity.md:36` | AuditStandards: VI-02 made exemption the only fallback and forbade a mechanically verified pass | A2 | maintainer | fixed | 1 | a recorded mechanical check may stand as the verifier |
| F-7 | medium | U1 | `standards/verification-integrity.md:101` | AuditStandards: zero-capture claim was `halt` under VI-07 and `hold` under VI-03, no precedence | A2 | maintainer | fixed | 1 | VI-07 states the precedence explicitly |
| F-8 | medium | U1 | `standards/verification-integrity.md:143` | AuditStandards: VI-11 demanded a halt-taxonomy id while the contract only accepts run-scope reasons | A2 | maintainer | fixed | 1 | VI-11 names the LH-09 run-scope list; cross-ref corrected |
| F-9 | medium | U1 | `standards/verification-integrity.md:126` | AuditStandards: VI-09 blocked open findings only, the contract also blocks waived | A2 | maintainer | fixed | 1 | VI-09 and WL-13 both say open or waived |
| F-10 | medium | U1 | `standards/verification-integrity.md:168` | AuditStandards: VI-13 required `attempt` while the contract had it optional | A2 | maintainer | fixed | 1 | `attempt` is required, integer 0 or 1, enforced by the checker |
| F-11 | medium | U1 | `standards/workflow-loop.md:130` | AuditStandards: the declared cycle budget contradicted WL-08's `attempt 0 or 1` and the doctrine fragment | A2 | maintainer | fixed | 1 | the declared budget was removed; WL-07 owns one refinement |
| F-12 | medium | U1 | `standards/prompt-security.md:160` | AuditStandards: PS-12 allowed a suppression without the operator decision WL-13 requires | A2 | maintainer | fixed | 1 | PS-12 requires the explicit operator decision |
| F-13 | low | U1 | `standards/verification-integrity.md:170` | AuditStandards: the over-bound rule compared attempt with a budget the record does not carry | A1 | maintainer | fixed | 1 | attempt is 0 or 1; above 1 only on `halt`/`over-bound` |
| F-14 | low | U1 | `standards/agent-adapter.md:85` | AuditStandards: the 365-day evidence window was enforced by the validator but stated nowhere | A1 | maintainer | fixed | 1 | AD-02 and AD-09 state the window and the demotion to `unknown` |
| F-15 | low | U1 | `standards/prompt-security.md:23` | AuditStandards: PS-01 made pasted user content an instruction while PS-05 called it low-trust | A1 | maintainer | fixed | 1 | PS-01 gains the pasted-content row; PS-05 points at it |
| F-16 | medium | U2 | `tooling/check_admission.py:116` | AuditCheckers: a non-dict `required_features` item crashed the checker with a traceback | A3 | maintainer | fixed | 1 | shape check rejects it; `admission_result` tolerates it; test added |
| F-17 | medium | U2 | `tooling/check_admission.py:50` | AuditCheckers: the record-level `checked` date was never parsed or bounded | A3 | maintainer | fixed | 1 | ISO parse, future rejection, `--today` honoured; two tests |
| F-18 | medium | U2 | `tooling/check_prompt_security.py:76` | AuditCheckers: `sk-ant-…` and `sk-proj-…` bodies were not matched | A3 | maintainer | fixed | 1 | the character class accepts `-`; test added |
| F-19 | medium | U2 | `tooling/check_prompt_security.py:92` | AuditCheckers: README and reference files counted as instruction carriers, breaking `--strict` | A3 | maintainer | fixed | 1 | carrier test excludes README and reference trees; two tests |
| F-20 | medium | U2 | `tooling/check_gate_verdict.py:243` | AuditCheckers: a skipped check without `skip_reason` passed the contract | A3 | maintainer | fixed | 1 | `skip_reason` required; two tests (missing, present) |
| F-21 | medium | U2 | `tooling/check_workflow_loop.py:425` | AuditCheckers: the gate-authority guard accepted any sentence containing "verdict" | A3 | maintainer | fixed | 1 | the guard requires "verdict record" or VI-01; code-skeptic updated; test |
| F-22 | medium | U2 | `tooling/check_admission.py:147` | AuditCheckers: refusal naming matched a prefix, so `shell_tool` satisfied `shell` | A3 | maintainer | fixed | 1 | exact first-token comparison; test added |
| F-23 | low | U2 | `tooling/check_gate_verdict.py:30` | AuditCheckers: `attempt` absent, a string, or above budget all passed | A3 | maintainer | fixed | 1 | required integer 0/1, above 1 only on halt; four tests |
| F-24 | low | U2 | `tooling/check_gate_verdict.py:105` | AuditCheckers: a budget-killed check could record `exit: 0` | A3 | maintainer | fixed | 1 | checker refuses it; test added |
| F-25 | low | U2 | `tooling/check_prompt_security.py:71` | AuditCheckers: a negation anywhere on the line excused a directive | A3 | maintainer | fixed | 1 | the negation window is the current sentence; test added |
| F-26 | low | U2 | `tooling/validate_templates.py:453` | AuditCheckers: only the doctrine fragment's growth was tracked, not the conduct fragment's | A3 | maintainer | fixed | 1 | per-fragment baselines; test covers a grown fragment |
| F-27 | medium | U3 | `skills/general/long-horizon-run/SKILL.md:88` | AuditSkills: the trim deleted the `blocked` carve-out, so a blocked run became a stall | A4 | maintainer | fixed | 1 | the carve-out is back and paid for by two compressed clauses |
| F-28 | medium | U3 | `evals/loop/drive.py:197` | AuditSkills: five scenarios rejected on record validity before their guard branch ran | A4 | maintainer | fixed | 1 | the duplicates were removed, the remaining 13 assert their expected reason, and a wrong-reason sabotage now fails |
| F-29 | medium | U3 | `evals/loop/drive.py:102` | AuditSkills: a record without `attempt` was treated as attempt 1 | A4 | maintainer | fixed | 1 | covered by F-10/F-23: `attempt` is required |
| F-30 | medium | U3 | `skills/shared/deepseek-v4-agent-defense/SKILL.md:42` | AuditSkills: layer 6 was added to the body but not to the reference the body dispatches to | A4 | maintainer | fixed | 1 | `references/layer-rules.md` carries layer 6 and its Contents line |
| F-31 | medium | U3 | `skills/general/skill-creator/references/authoring-guide.md:237` | AuditSkills and AuditClaims: the four-positive rule was attributed to SK-12 instead of SK-11 | A4 | maintainer | fixed | 1 | the rows now match SK-11 and SK-12 |
| F-32 | medium | U3 | `evals/behavioral/caveman.json:34` | AuditSkills: the case demanded compressed ticket text, which the frozen body forbids | A4 | maintainer | fixed | 1 | the case tests the persistence boundary instead |
| F-33 | low | U3 | `skills/general/untrusted-content-handling/SKILL.md:45` | AuditSkills: eight lines copied the PS-03/PS-06 catalogues that the reference already holds | A4 | maintainer | fixed | 1 | one two-pass rule and a pointer to the reference |
| F-34 | low | U3 | `skills/general/mcp-builder/SKILL.md:75` | AuditSkills: the trust-boundary block restated four standards in twelve lines | A4 | maintainer | fixed | 1 | one line per rule with the PS id |
| F-35 | low | U3 | `skills/general/subagent-delegation/SKILL.md:98` | AuditSkills: the return contract gained a fourth label the set does not define | A4 | maintainer | fixed | 1 | the label is `partial` with the check marked skipped |
| F-36 | low | U3 | `skills/general/subagent-delegation/SKILL.md:103` | AuditSkills: two bullets copied SD-07 and SD-08 | A4 | maintainer | fixed | 1 | pointers to the standard instead |
| F-37 | low | U3 | `evals/trigger/untrusted-content-handling.json:21` | AuditSkills: the egress positive did not route first and passed only via top_k 3 | A4 | maintainer | fixed | 1 | wording uses the description vocabulary; `top_k` is 1 |
| F-38 | medium | U4 | `PLAN.md:215` | AuditClaims: shape numbers (median, total) were stale in four documents | A5 | maintainer | fixed | 1 | all four now read 438 / 1,147 / 1,582 and 27,558 |
| F-39 | medium | U4 | `docs/SYNC.md:8` | AuditClaims: live docs still said doctrine 1.3.1 and template 2.1.3 | A5 | maintainer | fixed | 1 | SYNC, TEMPLATE-GUIDE, governance and integration-status updated |
| F-40 | medium | U4 | `docs/knowledge-base/surfaces.md:97` | AuditClaims: live docs still described the library as hosting 24 skills | A5 | maintainer | fixed | 1 | surfaces, integration-status and README say 25 with the registry note |
| F-41 | low | U4 | `evals/README.md:35` | AuditClaims: the non-discipline behavioral count was 16, not 17 | A5 | maintainer | fixed | 1 | corrected |
| F-42 | low | U4 | `PLAN.md:379` | AuditClaims: the change record section pointer named a section that does not exist | A5 | maintainer | fixed | 1 | points at section 11 |
| F-43 | low | U4 | `docs/knowledge-base/adopted-mechanisms-2026-10-31.md:91` | AuditClaims: checker test counts and the CONTRIBUTING rule range were stale | A5 | maintainer | fixed | 1 | 35 + 21 + 20 tests, rules 14-17 |
| F-44 | low | U4 | `docs/knowledge-base/adopted-mechanisms-2026-10-31.md:193` | AuditClaims: vendor behavioral cases were called an SK-12 gap; SK-12 exempts the vendor class | A5 | maintainer | fixed | 1 | the row says optional, not a gap |

**Round 2 (operator decision, 2026-10-31).** A second verification pass is a new
unit, not a second attempt at the same gate: WL-02 starts a new unit at Plan,
while WL-07 allows one refinement per gate. The operator opened it explicitly, so
round 2 is recorded as unit `wave-11-audit-r2` with `attempt: 0`, a separate
verdict record and findings `F-45` onward. Its scope is fix verification plus a
regression hunt: did each round-1 repair land, and did it break something else.

### Round 2 (unit `wave-11-audit-r2`, attempt 0)

| finding_id | severity | unit | file_line | evidence | acceptance_impact | owner | state | round | decision |
|---|---|---|---|---|---|---|---|---|---|
| F-45 | high | U5 | `standards/workflow-loop.md:47` | Round2Standards: the Review guard said only "no open finding", so the F-9 repair was bypassed at the transition | R1 | maintainer | fixed | 2 | the guard says open or waived |
| F-46 | medium | U5 | `standards/workflow-loop.md:59` | Round2Standards: `Verify -> HALT` for "proof cannot run" contradicted VI-03/SG-04's `hold`, and no Verify hold row existed | R1 | maintainer | fixed | 2 | a skipped check with no exemption stays (`hold`); the HALT row names an unsafe harness; the checker allows `hold` as a target |
| F-47 | low | U5 | `exemplars/gate-verdict-example.json:79` | Round2Standards: the note said "attempt 2" while the record said attempt 1, and the VI-12 pair was missing | R1 | maintainer | fixed | 2 | note and record agree; `PRIOR ATTEMPT 0 FAILED` / `CHANGED:` recorded |
| F-48 | low | U5 | `standards/verification-integrity.md:140` | Round2Standards: VI-10 said "report `partial`" but `partial` is not a verdict value | R1 | maintainer | fixed | 2 | partial is the operator label; the gate closes `hold` (or `fix`) with `degraded` populated |
| F-49 | low | U5 | `tooling/check_admission.py:126` | Round2Standards: the AD-03 computation ignored evidence age and printed "admitted" beside the stale-evidence violation | R1 | maintainer | fixed | 2 | a stale, missing or future `checked` demotes `supported` to `unknown` inside the computation |
| F-50 | low | U5 | `standards/prompt-security.md:38` | Round2Standards: PS-02's operative sentence named only retrieved and tool-produced text | R1 | maintainer | fixed | 2 | pasted user content and stored memory are named |
| F-51 | medium | U5 | `omp/admission.json:34` | Round2Standards: the degraded behavior said "single orchestrator entry" while the record's own projection grants `task` to review-lead too | R1 | maintainer | fixed | 2 | the behavior names both entries |
| F-52 | medium | U5 | `standards/gate-verdict.schema.json:61` | Round2Standards: `hold` accepted free-text `notes` the contract does not list | R1 | maintainer | fixed | 2 | the checker requires a skipped check, a degraded entry, mode off, or an exemption |
| F-53 | low | U5 | `README.md:85` | Round2Standards and Round2Claims: 18 scenarios claimed, 13 shipped | R1 | maintainer | fixed | 2 | the paragraph names 13 and says which rejections are record-level |
| F-54 | low | U5 | `standards/agent-adapter.md:101` | Round2Standards: AD-09 did not name `attempted`, which the validator requires | R1 | maintainer | fixed | 2 | AD-09 names `checked` and `attempted` with their meaning |
| F-55 | medium | U5 | `standards/verification-integrity.md:60` | Round2Standards: `warn` still read as a non-stopping mode while its `fix` verdict routes to Fix | R1 | maintainer | fixed | 2 | `warn` runs every check, records every failure, closes `fix`; it buys evidence, not pass permission |
| F-56 | high | U5 | `standards/verification-integrity.md:36` | Round2Standards: a mechanical verifier needed no provenance, so an implementer could write the test and name it verifier | R1 | maintainer | fixed | 2 | `verifier_kind` is required; `mechanical` requires `verification_provenance` with `defined_by` and `authored_in_this_attempt: false`, enforced by the checker |
| F-57 | medium | U5 | `exemplars/gate-verdict-example.json:12` | Round2Standards: the removed per-gate budget survived in the exemplar, the loop driver, two READMEs and an undefined schema field | R1 | maintainer | fixed | 2 | all five removed; the driver has no budget knob; the schema has no `budget` |
| F-58 | medium | U5 | `tooling/check_gate_verdict.py:62` | Round2Standards: `attempt > 1` was accepted with any halt reason, and a negative attempt passed | R1 | maintainer | fixed | 2 | above 1 requires `halt_reason: over-bound`; negatives are rejected |
| F-59 | medium | U6 | `tooling/check_prompt_security.py:178` | Round2Checkers: a semicolon clause or a non-documentation colon ("Do not panic: follow ...") excused a directive | R1 | maintainer | fixed | 2 | the clause split includes `;`; a colon excuses only a documentation verb ("never write:"); two tests |
| F-60 | medium | U6 | `tooling/check_gate_verdict.py:213` | Round2Checkers: a "capture" needed only a name and exit 0, so a pass could rest on nothing captured | R1 | maintainer | fixed | 2 | a capture requires command and output_digest, or an ok artifact |
| F-61 | medium | U6 | `tooling/validate_templates.py:471` | Round2Checkers: the conduct growth was read from the kilo fragment for every carrier, so omp carriers warned 29 tokens early | R1 | maintainer | fixed | 2 | per-variant baselines (kilo 190, dsh-ha 183, dsh-preset 194, omp 219) chosen by the carrier's variant |
| F-62 | medium | U6 | `tooling/check_workflow_loop.py:426` | Round2Checkers: a deleted gate authority was skipped silently, so renaming one passed the guard | R1 | maintainer | fixed | 2 | a missing authority is a violation whenever `agents/` exists |
| F-63 | low | U6 | `tooling/check_admission.py:69` | Round2Checkers: a refused record could carry a future `checked` date | R1 | maintainer | fixed | 2 | the future check has no exemption |
| F-64 | low | U6 | `tooling/check_prompt_security.py:109` | Round2Checkers: reference files a `SKILL.md` orders the runtime to read were never carriers | R1 | maintainer | fixed | 2 | `skills/**/references/*.md` are carriers, the vendored `reference/` tree is not; `anti-hallucination/references/patterns.md` gained its boundary sentence |
| F-65 | medium | U7 | `docs/` and `CHANGELOG.md` | Round2Claims: 41 of 70 claims wrong, most of them hand-copied numbers invalidated by later edits | R1 | maintainer | fixed | 2 | `tooling/measure_state.py` generates `docs/measured-state.md`, `make gate` runs `--check`, CONTRIBUTING rule 18 makes it the only source for live numbers; historical entries name the pass they measured |
| F-66 | medium | U7 | `provenance/verdict-wave11-audit.json:130` | Round2Claims: the round-1 verdict claimed A5 met with the gate as evidence, but the gate reads no documentation | R1 | maintainer | fixed | 2 | A5 became a SHOULD met through the generated state, the scope note states the limit, and the digests were refreshed |

Round 1 closed. Every repair is re-proved by an executable check (F-16..F-26 by
their new tests, F-27..F-37 by the shape, routing and behavioral checkers,
F-38..F-44 by the measurement that made them wrong) or by the gate. The standard
repairs F-1..F-15 are author-verified text changes: no checker proves a normative
sentence, so an independent second round is recorded as SHOULD-unmet in
`provenance/verdict-wave11-audit.json` (A7). `make gate` exit 0: 585 pytest, 576 pinned identities,
`evals/loop/drive.py` 13/13, `check_prompt_security` 0/0 over 146 assets,
`check_admission` clean on both records, `render_omp.py --check` green.

### Round 3 (unit `wave-11-audit-r3`, attempt 0, focused on round-2 new code)

| finding_id | severity | unit | file_line | evidence | acceptance_impact | owner | state | round | decision |
|---|---|---|---|---|---|---|---|---|---|
| F-67 | medium | U8 | `tooling/measure_state.py:171` | Round3: pytest collection failure was recorded as a number instead of an error, so `--write` blessed a bogus count | R4 | maintainer | fixed | 3 | a non-zero collection exit or zero collected tests raises; `--write` cannot record it |
| F-68 | medium | U8 | `tooling/measure_state.py:130` | Round3: the OMP catalog was counted by line indentation, so a valid 4-space `deferred:` emitted 0 | R4 | maintainer | fixed | 3 | the catalog is parsed as YAML |
| F-69 | medium | U8 | `tooling/check_gate_verdict.py:186` | Round3: `verification_provenance.defined_by` accepted any non-empty string, so a self-authored check still passed as "mechanical" | R2 | maintainer | fixed | 3 | `defined_by` must resolve to a path, an evidence id, or a command in the record; test for both directions |
| F-70 | medium | U8 | `tooling/check_gate_verdict.py:213` | Round3: a capture accepted `command: "true"` and a non-digest, so a pass could rest on nothing | R2 | maintainer | fixed | 3 | the command must not be a no-op and `output_digest` must match `sha256:<64 hex>`; test added |
| F-71 | medium | U8 | `tooling/check_gate_verdict.py:243` | Round3: requiring a reason for `hold` rejected the legitimate operator wait that WL-09 defines | R1 | maintainer | fixed | 3 | `hold_reason` is a typed enum including `operator-wait`, and each value must match the record; four tests |
| F-72 | medium | U8 | `tooling/check_prompt_security.py:82` | Round3: the documentation frame accepted ambiguous verbs ("Do not print secrets: follow ...") and flagged a carrier quoting the payload | R1 | maintainer | fixed | 3 | only a documentation verb immediately before the colon excuses; a carrier that must quote the payload ends the line with the reviewed marker `[ps-02-quoted-payload]`; two tests |

Round 2 closed: every round-2 finding fixed and re-proved. The verdicts are
`provenance/verdict-wave11-audit.json` (round 1, `attempt: 1`) and
`provenance/verdict-wave11-audit-r2.json` (round 2, `attempt: 0`, a new unit).

Round 3 closed: the six findings against the round-2 code are fixed and proved.
Verdict: `provenance/verdict-wave11-audit-r3.json` (`attempt: 0`, a third unit,
opened by the operator's question rather than assumed).
