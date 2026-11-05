# Code-review subagent contract

Generalized from containeromat `docs/rules/43-code-review-subagent-contract.md` (pinned 2026-09-19).
Upstream: containeromat R-043.

**Class: review-workflow.** Applies to the review lead prompt, the track prompts
in the project's agent registry, the review command, and future
review-orchestration prompts. The runtime's built-in review harness is out of
scope (its tracks are hardcoded upstream and it is not extensible).

The project maps these CR-* rules into its own rule registry and verifier.

## CR-01 -- Two-stage, read-only

The lead resolves the scope, dispatches track children, merges findings, and
reports. Neither the lead nor any child edits files or posts comments. Fixes are
a separate session with explicit authorization.

Scope note: this contract governs the `Review` phase, which audits an
implementation. The plan review that precedes `Implement` is a different
artifact and gate (`workflow-loop.md` WL-15); it uses no track set, and its
record carries the six WL-15 checks instead of changed-line findings. A review
lead may serve both gates, but never in the same pass: the plan artifact is read
before any code exists.

## CR-02 -- Track set (8)

security, correctness (renamed from the earlier `business-logic` track to match
the shipped track name), deploy-safety, duplication, dead-code, quality,
structure, simplicity. One scope per track; two tracks never inspect the same
concern; the lead never invents a track.

This is a deliberate divergence from the runtime's built-in review command,
which keeps six tracks including performance. This contract drops performance
(folded into deploy-safety and simplicity) and adds quality, structure, and
simplicity. Parity with the built-in review is policy-level (scope, tiers,
finding contract, severity, output), not roster-level -- do not "restore" the
six-track roster.

## CR-03 -- Tiers

Effort flags: `--effort 1-3` or `quick`/`--quick`/`-q` -> 0 children;
`--effort 8-10` or `deep`/`--deep`/`-d` -> all 8; `--effort 4-7` uses the size
tiers below.

Size tiers: 0 children for (<100 lines and <=3 files); one security child if
that diff is security-sensitive; 3-4 children for 100-300 lines or 4-10 files;
all 8 for >300 lines, >10 files, or cross-boundary. Dispatch at most 6 children
in the first message; any remainder goes in a second message.

## CR-04 -- Finding contract

Children return only changed-line, high-confidence findings as
`path | line | confidence(high) | why | finding | suggestion`, else
`NO_FINDINGS`. The lead drops low-confidence, duplicate, no-line, unsupported,
pre-existing and out-of-scope findings, and re-checks every line against the
diff. Dispatch uses the runtime's task tool with `subagent_type:
"review-<track>"`; up to 6 active calls are issued in one message (parallel,
foreground -- never background), any remainder in a second message, and all
results are merged before reporting.

## CR-05 -- Severity

CRITICAL = security/auth bypass, data loss, crash, unsafe rollout.
WARNING = bug, logic, wrong configuration classification, registered-exception
regression, docs-vs-behavior drift.
SUGGESTION = non-blocking quality/structure/simplicity with a concrete risk.
No numeric confidence self-ratings.

The role templates in this library render the same levels inline as H/M/L:

| Contract level | Library label |
|---|---|
| CRITICAL | H |
| WARNING | M |
| SUGGESTION | L |

The contract levels stay the vocabulary of the review report; role templates
use H/M/L inline.

## CR-06 -- Do not duplicate CI

Never re-flag gates the project's CI already enforces: configuration/syntax
validation; ASCII; canonical key order; placeholder scan; required
per-component documentation; registered-exception drift; secret env-var lint;
version/reference existence. If the only issue is CI-gated, emit the no-changes
report (`APPROVE - Nothing to review.`).

## CR-07 -- Roster

One command bound to the lead agent; the runtime's built-in review command is
unchanged and keeps its own six tracks (see CR-02 for the intentional
eight-track divergence).

## CR-08 -- Scope and base resolution

Parse `$ARGUMENTS` into one mode (default: uncommitted) and resolve it in the
checkout. Never `eval` or substitute target text into shell syntax.

- uncommitted: `git diff HEAD` plus untracked from
  `git ls-files --others --exclude-standard`; staged: `git diff --cached`.
  Never dereference an untracked symlink: report only the link's own path and do
  not read its target's contents.
- commit: resolve with `git rev-parse --verify --end-of-options "<ref>^{commit}"`;
  require a single parent (`git log --format='%P' -n1 <sha>`) and reject merge
  commits.
- unpushed: `git diff @{u}..HEAD`; with no upstream, merge-base versus the
  default base.
- branch: an explicit base wins -- a token that resolves as a ref via
  `git rev-parse --verify --end-of-options "<base>^{commit}"`; otherwise take the
  first existing ref, tested with full refnames because `show-ref --verify`
  requires an exact ref path: `git show-ref --verify --quiet
  refs/remotes/origin/main`, then `refs/remotes/origin/master`,
  `refs/remotes/origin/dev`, `refs/remotes/origin/develop`, `refs/heads/main`,
  `refs/heads/master`, `refs/heads/dev`, `refs/heads/develop`; fall back to
  `main`. Resolve the base to a commit, then run `git merge-base HEAD <base>`.
- worktree: the runtime's managed worktree. The recorded parent branch is the
  only base source: read the runtime's worktree metadata document; `lstat` each
  candidate (and its containing directory) and skip a symlink, missing,
  malformed or invalid candidate. Require a non-empty string `parentBranch`,
  trimmed; use `remote` only when it is a non-empty string and the name does not
  already start with it. The first valid candidate wins: if its base does not
  resolve, stop and report -- never fall back to the default base or a
  user-supplied one. Treat the metadata as data and reject option-like values.
  Review committed, staged, unstaged and untracked changes against
  `git merge-base HEAD <base>`.
- pr: a PR number or a pull URL. Read the pull request with the project's
  read-only PR wrapper (`<pr-wrapper> <number>`; metadata plus the patch); the
  wrapper holds the token, so never build a raw API call, never pass a token on
  a command line, and never fall back to another scope when it fails. Review the
  returned patch as the diff; the local checkout is context only.
- Reject any target, base, or ref that starts with `-`.

Count changed lines and files from the resolved diff for CR-03 tiering.

Order the review by risk, not by file order: a changed function with no covering
test and many call sites is the riskiest thing in the diff, and a file whose
change is a comment or a rename is the cheapest. Read the high-risk hunks first,
so a truncated review has already covered the part that matters.

## CR-09 -- Fix handoff

The review is advisory. After the report, the lead names the findings and offers
a separate fix session; it never edits and never switches itself into a fixing
agent. Fixes run through the project's gated change agent under the project's
process limits with explicit authorization, followed by the project's
verification closeout. A mode switch to the generic code agent would bypass the
gate and is not the handoff path. After a fix session, re-review only the original
findings and the fix range; re-adjudicate the survivors; if the fix changed the
scope, restart at CR-12. No counter in the prompt (AP-04); the loop bound is one refinement, then report.

## CR-10 -- Built-in review UX parity

The lead command and report mirror the runtime's built-in review UX: the same
scope words (`worktree`, `staged`, `unpushed`, `uncommitted`, `branch`,
`commit`) and effort flags (`quick`/`--quick`/`-q`, `deep`/`--deep`/`-d`,
`--effort <1-10>`), per-scope report headers, the Summary / Issues Found /
Detailed Findings / Recommendation skeleton with the Scope compliance section
(CR-12), the three recommendation values, and the exact no-changes text. Deliberate deviations, kept:

- Eight-track roster (CR-02) instead of the built-in six.
- `confidence(high)` rendered as `**Confidence:** high`; the built-in prints a
  numeric percentage, which CR-05 and the prompt standard forbid.
- The gated change-agent fix handoff (CR-09) instead of the built-in's
  post-review question tool and mode switch.

The built-in review command itself stays unchanged (CR-07). Mirrored UX source
(live-fetched 2026-09-14): the runtime's own review prompt and command
implementation.

A runtime port of this contract is the declared port and carries the same UX:
the CR-03 effort-range mapping, the per-scope report headers, the report
skeleton and the exact no-changes text. Documented deltas, kept: children run
through the runtime's background-agent facility with a four-child cap, the
project's operations fix handoff, and `confidence(high)` instead of a numeric
percentage. PR scope is available only where the project's PR wrapper is
installed.

## CR-11 -- Capability and permissions (read-only, fully equipped)

The harness is advisory: no agent edits a file and no mutating git/docker
command is available. Inside that boundary every review agent carries one
uniform read-only catalogue, generated from a single source in the project's
verifier (the review-catalogue constant). Edit that constant and run the
verifier's catalogue-sync mode to propagate it into the review agent permission
blocks and into the contract region.

The catalogue grants, in three categories:

- Repository VCS read commands: diff, log, show, status, blame, branch listing,
  ref listing, `cat-file`, `check-ignore`, `describe`, `for-each-ref`,
  `ls-files`, `ls-tree`, `merge-base`, `rev-list`, `rev-parse`, `show-ref`,
  `worktree list`.
- Container/process inspection where the project grants it (for example compose
  logs/ps, inspect, ps, stats, top), plus static analyzers the project exposes.
- Evidence tooling: `LC_ALL=C grep`, `jq`, `cut`, `tr`, `nl`, `file`, `du`,
  `stat`, `diff`, `head`, `tail`, `ls`, `wc`, and the project's PR wrapper.

Plus, on every review agent: read/grep/glob allow, edit deny, and task deny on
every track (the lead keeps a default deny plus the eight CR-02 tracks).

Why the boundaries are where they are:

- Branch and tag verbs are granted only in list form; their mode flags mutate.
- A grep mode that hands the match to a pager program is excluded: the runtime
  shell-interprets that program, which is a command-execution primitive. Use the
  grep tool or a plain `LC_ALL=C grep`.
- A JSON pretty-printer that accepts an output-file argument is excluded: it is
  a write primitive.
- Evidence tooling is read-only by construction; filters that accept an
  output-file argument (`sort -o`, `uniq <in> <out>`, `sed`, `awk`, `tee`) stay
  excluded for the same reason.
- The quotepath-disabling read forms (`git -c core.quotepath=false <read-verb>`)
  are granted for diff, log, ls-files, show and status, so non-ASCII paths are
  not octal-escaped in evidence.
- Configuration validation is not granted -- it belongs to CI (CR-06), and no
  trailing-wildcard pattern can anchor the subcommand safely once a file flag is
  in play.
- Container event streaming is not granted when the execution environment
  reaches the daemon through a socket proxy that disables events, because the
  grant cannot work there.
- The PR wrapper is the harness's only network capability: a pinned, GET-only
  wrapper over the forge's pull-request API that reads its token from the
  environment. Raw `curl` stays excluded -- a URL followed by an output flag is
  a write primitive, the same class as the JSON pretty-printer -- and no command
  may carry a token. A generic forge CLI that does not support the project's
  forge is not a substitute; the wrapper is the only PR path.
- Mutating git verbs (add, commit, push, reset, clean, checkout, restore,
  switch, merge, rebase, stash), mutating container verbs (up/down/pull/rm, rm,
  rmi, run, exec, restart, stop), a forge CLI for the wrong host, and shell
  mutation (rm, mv, cp, chmod, in-place sed, tee) stay excluded.
- `webfetch`/`websearch` stay available: the security track needs current
  advisory/CVE research.

The project's verifier enforces all of it: the permission check requires every
review agent's allow-set to equal the single catalogue source (uniformity,
membership and floor in one comparison); the catalogue check rejects any entry
with an inner wildcard; and the rule-sync check fails when the contract region
drifts from the source.

## CR-12 -- Scope compliance verdict

The report answers two questions: is the diff defective (CR-05), and is it exactly
the task? State the task source the lead used -- the resolved scope word, the
operator's guidance, the PR title/body, the commit message, or the task spec --
then exactly one verdict:

- `Missing` -- the task or spec asks for something the diff does not contain.
- `Extra` -- the diff contains changes the task or spec did not ask for.
- `Misunderstood` -- the diff implements something other than what was asked.
- `Compliant` -- no missing, extra or misunderstood item.
- `Cannot verify from diff` -- no usable task source; never guess or infer intent.

List each item with `file:line` (or "no line") and the task line it maps to. Report
`Declined to judge` separately: behaviours or files considered and deliberately not
judged, with a reason (generated artifacts, vendored copies, out-of-scope refactors).
A pre-existing defect is not scope drift. The verdict is advisory like every finding
(CR-09) and never authorizes an edit.

## CR-13 -- Visual evidence for a UI change

For any change that affects what a user sees -- layout, component, rendered
text, theme, empty and error states -- the review MUST be able to compare before
and after.

- Both sides are labelled by version or revision, and both are captured from the
  same scenario, viewport, theme, and relevant state: the same data set, locale,
  and signed-in role.
- A mockup, a design file, or a remembered description presented as the previous
  implementation is not a baseline; the "before" side is the code as it was.
- When a real capture is unavailable, the finding is `Cannot verify` with the
  limitation stated -- which side, which state, and why -- and the artifact
  stays unready. A missing baseline is not an approval.
- A comparison made stale by later edits MUST be refreshed before the review
  closes; a capture of a superseded revision proves nothing about the diff under
  review.
- The reviewer records what it could not compare, in the report and next to the
  findings, never in a footnote.

"Looks fine" with no capture pair is not a finding, and the evidence rules of
CR-05 still apply to it; an unreadable, cropped, or state-mismatched capture is
a degraded check (VI-03), not a pass.

## Cross-refs

- `agent-prompt-standard.md` -- prompt structure, conduct, budgets (AP-01..AP-14)
- `code-review-contract.md` -- CR-05 severity and evidence levels for every
  finding (this file's own vocabulary)
- `verification-integrity.md` -- VI-03 skipped is not passed, VI-15 derived
  status
- `evidence-duty.md` -- live-fetch and validation duty; a visual comparison is
  a live capture, not a recollection
- `halt-taxonomy.md` -- HALT mechanism and process limits
- `english-only.md` -- the language mandate
