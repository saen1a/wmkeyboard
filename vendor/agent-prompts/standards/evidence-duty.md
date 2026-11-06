# Evidence duty -- live research and cross-validation

Generalized from containeromat `.kilo/rules/29-live-research-and-validation.md` (pinned 2026-09-19).
Upstream: containeromat R-029.

Every artifact an agent produces -- config files, runbooks, rules, code,
diagrams -- must be traceable to a **live source fetched in this session**.
Cited-by-memory sources are a violation. The goal is zero fabricated or stale
guidance in the project.

## Failure mode

The pattern this duty prevents: ungrounded memory substituting for a live source
fetch. Observed classes:

- an artifact declared PASS by a parse check while structural bugs remained --
  the project's own validator would have caught every one, but validation was
  deferred to CI that did not exist yet or lagged behind the commit;
- a design decision flipped repeatedly because each pass cited a different
  official source, and the deciding page was only read in the final pass;
- a placeholder secret treated as "real enough" and deferred to a manual
  deploy-time edit -- a re-pull drift hazard;
- an override file invented for a platform whose documented path reads the
  standard file directly.

The origin project's session error log (18 lessons with commit references) stays
runtime-side in containeromat; this standard carries the durable duties, not the
incident history.

## When this duty applies

Any agent action that produces an artifact the operator will read, deploy, or
act on:

- new / edited / replaced config files (application config, CI workflows, JSON
  schemas, policy files)
- documentation (rules, runbooks, decision records, changelog entries)
- plans
- reviews / assessments / recommendations

It does **not** apply to:

- pure conversational responses that quote no artifact
- re-formatting, typo fixes, or other low-risk editorial edits where the
  underlying source is already in-tree and current

## Required workflow

### 1. Fetch first, then act

Before producing any artifact, fetch the relevant authoritative source in the
current session. Record each fetched source in the session log so the artifact
can be traced back. The fetch must be:

- **Live**, not from training-data memory
- **Current** -- for vendor projects, use the latest stable docs URL or the
  canonical source URL with a year-aware cache check
- **Specific** -- fetch the page(s) whose content the artifact cites, not a
  generic landing page

What counts as authoritative, by artifact class:

| Artifact class | Authoritative source(s) |
|---|---|
| Configuration files | Vendor docs page for the tool + the registry tags API for version verification |
| Routing / proxy config | Vendor docs for the matched middleware + a runtime verification pass |
| Platform behavior | The platform's own manual, direct URL, not memory |
| Identity / auth integration | The vendor integration page for the specific client |
| Unix / shell patterns | Live `--help` or `man` output, not memory of flags |

### 2. Derive before write

After fetching, derive the artifact in chat or in a scratch file:

- For each non-default config field, the line in the documentation that
  supports it (cite the URL or `doc/section#anchor`)
- For each workaround / deviation from an upstream default, the reason specific
  to **this project** (test scope vs production, decision-record reference)
- For each variable name, the matching naming convention from the docs -- not
  from memory

### 3. Cross-validate before commit

Before any non-trivial commit, run the project's own validation tool against the
artifact:

| Artifact | Validation command |
|---|---|
| Container / stack config | The runtime's `config` validation command |
| Application configuration | The application's own `validate-config` subcommand |
| YAML / JSON schema | The language's parser / schema check |
| Custom config format | The tool's own `validate-config` subcommand if it exists |

A "PASS" / exit code 0 must be shown in the commit message body or the
conversation immediately before the push. **Deferrals of the form "this is fine,
CI will validate later" are not acceptable** for new work. The closeout-skip
exception is reserved for **in-place typo fixes where the underlying source is
already current and the change is low-risk**.

### 4. If CI validates the same artifact, run the check locally first

Do not rely on CI as the first line of validation: CI feedback lags behind the
local commit, and the loop-back cost is operator attention. Run the validator
locally and paste the exit code into the chat log before commit.

### 5. Emit all artifacts with explicit traceability

Every runbook / decision record / commented config field that cites a vendor or
upstream claim must carry:

- `# source: <URL or upstream document path>` (inline comment in code)
- a decision-record appendix with full citations

Cite or omit: every non-trivial external claim carries a source marker; a claim
that cannot be sourced is not emitted. If a vendor doc URL changes between the
agent's session and the operator's deploy date, the citation in-repo is the
single source of truth and must remain accurate. Re-fetch before any commit that
references external docs unless the in-tree citation links to a
machine-readable source the agent can verify locally.

## What this duty does not change

- The read-first anti-hallucination rules -- this standard extends them, it does
  not replace them.
- The project's closeout validation -- this standard makes the validation step
  mandatory for new work, in addition to closeout.
- The exception registry -- this standard does not weaken it; documented
  exceptions remain authoritative.

## Self-check before commit

Run through this list before any non-trivial commit:

1. [ ] Every URL / file path cited as `# source:` was fetched in this session
2. [ ] Every artifact validated locally with the project's own validation tool
   (paste exit code in the commit body)
3. [ ] Every new file has a clear owner (runbook, in-repo rule, or comment in
   the file explaining why it is there)
4. [ ] No file in the diff has an unclear reason to exist
5. [ ] The changelog entry references the upstream source if the change is
   informed by one
6. [ ] If flipping a decision, the old decision is in-tree (commit history +
   decision record), and the new commit cites the source that resolved the flip.
   The superseded record carries `status: superseded`, `as_of` and
   `superseded_by`; conflicting sources are `status: disputed` until resolved

A "no" on any item blocks the commit until resolved.
