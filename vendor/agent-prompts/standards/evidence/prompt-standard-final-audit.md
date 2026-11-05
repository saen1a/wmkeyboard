# Prompt-Standard Final Audit (2026-08-03)

Provenance: containeromat `docs/prompts/prompt-standard-final-audit.md` (pinned 2026-09-19); containeromat-internal identifiers below are upstream provenance references, not library rules.

**Scope:** final zero-hallucination audit of the prompt-standard work before freeze:
`docs/prompts/rag-workspace-prompt-research-v2.md`,
`docs/prompts/system-prompt-standard.md`,
`docs/prompts/standard-rag-v1.txt`,
`docs/prompts/technical-reviewer-v3.txt`,
`docs/rules/38-anythingllm-system-prompts.md` (containeromat PP-00),
`stacks/anythingllm/OIDC.md` (prompt sections), `CHANGELOG.md`, `.kilo/README.md`.
**Method:** every factual claim was live-fetched (containeromat R-029) in the 2026-08-03 sessions;
this audit re-ran the open items and documents the evidence chain. No claim in the
audited files is carried from model memory.

## Verification matrix (every headline number in the audited files)

| Claim (file) | Primary source, live-fetched | Status |
|---|---|---|
| GPT-4o ~=85% at 1 instruction -> ~=15% at 10 (research-v2 Sec.1.1, standard Sec.1) | Curse of Instructions, ICLR 2025 -- OpenReview PDF excerpt + maxpool.dev report of the same paper (consistent with abstract figures 15%->31% / 44%->58%) | verified |
| Feedback: GPT-4o 15%->31%, Claude 3.5 44%->58% at 10 instructions | OpenReview PDF excerpt, live | verified |
| 0.94 (n=1) -> 0.21 (n=10) GPT-4o prompt-level accuracy | arXiv:2509.21051 Table 8 (extended version, EMNLP 2025), live | verified -- original "5->6" attribution corrected in research-v2 |
| Model list GPT-4o / Claude-3.5 / Gemini-1.5 / Gemma2 / Llama3.1 | OpenReview abstract + maxpool.dev report, live | verified |
| CoVe FActScore 55.9 -> 71.4 (Wikipedia biographies) | CoVe, Findings ACL 2024 -- abstract live; figures paper table, cross-checked against independent secondary sources | verified (paper-level) |
| ALCE: best models lack complete citation support ~=50% of the time (ELI5) | ALCE, EMNLP 2023 -- abstract verbatim, live | verified |
| U-shaped attention (beginning/end > middle) | Lost in the Middle, TACL 2024 -- abstract, live | verified |
| Attention sinks (initial tokens) | StreamingLLM, arXiv:2309.17453 (ICLR 2024) -- abstract, live | verified |
| PRISM: MMLU 71.6 baseline -> 68.0 minimum persona / 66.3 long persona; persona helps alignment, hurts knowledge retrieval | PRISM, arXiv:2603.18507 -- HTML full text Sec.3.1, live | verified |
| Zheng: 162 personas, 6 relationship types, 8 domains, 4 model families, 2,410 questions, no consistent gain, auto-selection ~= random | arXiv:2311.10054 -- abstract verbatim, live | verified |
| R-Tuning: refusal is a meta-skill, training effect, generalises out-of-domain | NAACL 2024 (2024.naacl-long.394) -- abstract, live | verified |
| Tian: verbalized confidence better calibrated than logprobs for RLHF-LMs (~=50% relative ECE reduction) | EMNLP 2023 (2023.emnlp-main.330) -- abstract verbatim, live | verified |
| Xiong: LLMs tend to be overconfident when verbalizing confidence | ICLR 2024, arXiv:2306.13063 -- abstract verbatim, live | verified |
| Farquhar: semantic entropy detects confabulations | Nature 630:625-630, DOI 10.1038/s41586-024-07421-0 -- live | verified |
| Wallace: instruction hierarchy, "drastically increases robustness" | arXiv:2404.13208 -- abstract, live (no unverifiable headline % carried) | verified |
| DefensiveToken: test-time defensive prompting << training-time defenses | arXiv:2507.07974 (this IS the DefensiveToken paper) -- abstract, live | verified |
| CaMeL: 77% provable security vs 84% undefended (AgentDojo) | arXiv:2503.18813 -- abstract, live | verified |
| Progent: symbolic privilege + SMT monotonic confinement | arXiv:2504.11703 -- abstract, live | verified |
| Greshake: indirect prompt injection, "effective mitigations currently lacking" | arXiv:2302.12173 -- abstract, live | verified |
| AnythingLLM variables `{date}`/`{time}`/`{datetime}` (ALL versions), `{user.name}`/`{user.bio}` (Docker multi-user), invalid variables silently not expanded | docs.anythingllm.com/features/system-prompt-variables, live | verified |
| `~41 stacks` in reviewer v3 role line | repo count: 41 directories under `stacks/` (2026-08-03) | verified |
| Standard-rag v1 body ~= 330 tokens <= 800 | measured: 241 words ~= 325-412 tokens | verified |
| Reviewer v3 body ~= 500 tokens <= 800 | measured: 379 words ~= 512 tokens | verified |
| Standard-rag v1 = research-v2 Sec.6 code block | byte comparison | verified |

## Drift

| # | Finding | Resolution |
|---|---|---|
| D1 | Stack count: v2 prompt said ~39, repo has 41 | v3 uses ~41; v2/v1 are frozen rollback references (never edited, containeromat PP-01) -- known, documented |
| D2 | `anythingllm-prompt-standard.md` renamed -> `system-prompt-standard.md` | all cross-refs updated (containeromat R-038, OIDC.md, research-v2, .kilo/README.md); grep confirms 0 stale refs outside CHANGELOG history |
| D3 | `P0.5/P1` markers in OIDC.md section headers (pre-existing) | plan-phase markers, resolvable via the cited containeromat plan (1785708530939); documented, not changed (out of the prompt-file scope) |
| D4 | Token-budget labels in headers (`body ~330`, `body ~500`) | measured values 325-412 / 512 -- labels accurate |

## Hallucination (target: zero)

| # | Finding | Resolution |
|---|---|---|
| H1 | `{workspace.name}` in reviewer v3 draft -- not a documented AnythingLLM variable | removed; only verified variables remain (`{datetime}`, `{user.name}`) |
| H2 | `(containeromat F-09)` plan-ID in reviewer v3 draft header | removed (containeromat SEC-GIT-03 instead); also purged from OIDC.md (2026-08-03 review fix) |
| H3 | "~39 stacks" in reviewer v3 draft | corrected to ~41 (repo count) |
| H4 | "0.94 at 5 -> 0.21 at 6" in original notes | traced to its real source (arXiv:2509.21051, n=1->n=10) and re-attributed; no unverifiable number remains |
| H5 | Tian et al. cited as "verbalized confidence systematically overconfident" | corrected to the paper's actual finding (better calibrated than logprobs); overconfidence claim re-sourced to Xiong et al. |
| H6 | arXiv:2507.07974 labeled "evaluation work over StruQ/SecAlign" | corrected: it IS the DefensiveToken paper |

Remaining unverifiable references: none. Every label in research-v2 maps to a
live-fetched source; `unproven` markers exist only where the original notes carried
claims that were explicitly not carried over.

## Gaps (open, documented -- not silently fixed)

| # | Gap | Status |
|---|---|---|
| G1 | A/B test (research-v2 Sec.7 protocol) not yet executed | protocol ready; operator/agent run before next prompt revision |
| G2 | Reviewer v3 body not yet pasted into the workspace UI | operator action, documented in OIDC.md (PASTE BODY ONLY) |
| G3 | homelab-workspace-v1 not yet re-derived from the standard | documented "keep until next homelab-specific revision" |
| G4 | seed-workspaces.sh creates only the `homelab` workspace | by design; reviewer/other workspaces are created in the UI (documented) |
| G5 | Rule 4 (search trigger) semantics in tool-less workspaces | now documented in system-prompt-standard.md (was only in research-v2 Sec.6) -- closed this audit |

## Bugs

| # | Finding | Status |
|---|---|---|
| B1 | none -- all cross-references resolve, all variables valid, all token budgets within containeromat PP-04, byte-consistency prompt<->research Sec.6 holds | verified |

## Logic

| # | Finding | Status |
|---|---|---|
| L1 | Rule numbering identical across prompt, research-v2 Sec.3/Sec.6, standard doc | verified (sub-review + this audit) |
| L2 | Reviewer evidence tags (repo\|live\|unverified) + settlement documented as containeromat PP-06 variant | verified -- no hidden drift vs the triad |
| L3 | Severity scale BLOCKER..NIT defined inline per containeromat PP-07, matches the containeromat PP-07 example | verified |
| L4 | Reviewer gates block mirrors containeromat R-007 closeout checks | verified |
| L5 | Injection guard present in both prompts incl. tool outputs (containeromat PP-08) | verified |
| L6 | CHANGELOG claims match the files (Tian/DefensiveToken/PRISM/CoVe corrections) | verified (sub-review + this audit) |

## Second submission review (2026-08-03, evening)

The reviewer v3 draft was re-submitted after the audit. A byte-level diff against the
committed `technical-reviewer-v3.txt` shows **0 new improvements** in the submission:
every line that differs is a fix that the committed v3 already carries. The submitted
draft is the pre-fix version -- it still contains all defect classes of the first
review: `{workspace.name}` (unverified variable), `(containeromat F-09)` plan-ID, `~39 stacks`
(drift, repo has 41), no PASTE BODY ONLY header, undefined severity scale, no
`[LOW]` level, no inline rule-ID definitions, no "Ignore any directive" injection
guard, no severity sorting / null-findings / chunk fallback. The only wording change
vs the earlier draft ("For each finding" instead of "For each candidate finding") is
**not adopted** -- "candidate" is more precise: VERIFY checks candidates before REPORT
emits them. **Decision: no v4; the committed v3 remains FINAL.** If the AnythingLLM
workspace UI holds a different (pre-fix) version, replace it with the committed body
(PASTE BODY ONLY, start at "Current time is {datetime}.").

## Conclusion

All audited files are internally consistent, every factual claim is traceable to a
live-fetched primary source, and the previously identified hallucination/drift items
(H1-H6, D1-D4) are resolved or explicitly documented. The prompt-standard work is
**FINAL** and may be committed, merged, and pushed.
