# English-only mandate (the language mandate)

Generalized from containeromat `.kilo/rules/40-english-only.md` (pinned 2026-09-19).
Upstream: containeromat R-040.

**Class: language-mandate.** Single source for the language policy. Created
after drift: non-English changelog entries and non-English chat output despite
an "English only" line in the project instructions. This mandate makes the
policy explicit and enforceable across every artifact class.

## Rule

- **EN-01** -- All persisted artifacts are English: docs, changelog, README,
  runbooks, rule files, prompts, plans, agent prompts, config comments.
- **EN-02** -- Chat output is English, always. Do not mirror the operator's
  language. Compressed styles (e.g. caveman) compress style only -- they never
  change language. No single-language override: even an explicit request for a
  non-English reply does not switch the reply language.
- **EN-03** -- Commit messages, PR bodies, review comments: English.
- **EN-04** -- No translated user-facing strings exist in this repository; do
  not invent any. A project that ships a frontend owns its own i18n policy.

Answer-language behavior is separate from artifact language: a workspace prompt
may instruct the model to answer in the language of the question (a runtime
behavior). That does not relax EN-01..EN-04 for any persisted artifact.

## Enforcement

- The project's closeout self-check carries a row: "Language: English-only
  (EN-01..EN-04)".
- Non-English content in any persisted artifact blocks the commit until
  converted. Existing legacy content is converted opportunistically when the
  file is touched, not in bulk.

## Cross-refs

- `agent-prompt-standard.md` -- AP-05 (language and hygiene)
- `evidence-duty.md` -- validation duty behind the enforcement
- `system-prompt-standard.md` -- language-of-question behavior for workspace
  answers
