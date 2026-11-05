---
name: human-gated-config-change
description: >-
  Use when a stored, versioned configuration or prompt must change through a human
  gate: edit a system prompt's wording, update a policy rule so only a named caller may
  ask, edit a delivery or settings section, or apply a draft revision. Covers base
  revision, preview and diff, explicit go, conflict merge, and copy-forward rollback.
rigid: true
metadata:
  category: operations
---
<!-- Repo-authored 2026-11-02. Canon: this file. Rules: standards/work-authorization.md WA-11, standards/prompt-assembly.md AS-14. -->

# Human-gated config change

A stored prompt or policy is live behavior, so an edit is a release, not a save.
This skill buys a named base, a rendered preview, and a recorded origin; it
costs one extra review turn. It does not cover source edits or destructive git,
which other skills own.

## Module 1 - Decision gate

Use this when the change lands in a stored, versioned artifact that a runtime
reads: a system prompt part, a settings block, a policy rule, a routing table,
or an agent instruction file. The tell is that the live value is fetched by
revision, not rebuilt from source.

Stop and hand off when:

- the edit is source code, a build file, or a schema migration: an engineering
  task, planned as ordinary work;
- the command is destructive git: `git-guardrails`;
- the deliverable is the release note: `changelog-generator`;
- the run itself needs checkpointing: `long-horizon-run`.

A prompt change is not a permission change. If the edit would widen what may be
asked or who may ask, the grant belongs in the enforcement layer, not only in
the text (WA-11); refuse to ship it as text alone.

## Module 2 - Procedure

1. Read the current revision first. Record its id or hash as the named base; a
   base you did not read is a guess.
2. Hold the edit as a draft against that base. The draft carries the base, an
   operator-visible summary, and nothing the save path will not replay.
3. Render the preview with the assembler that produces the live artifact. A
   hand-built preview proves nothing; the same code path must produce both.
4. Diff the draft against the saved revision and against the default, and show
   both. The default diff answers "deliberate override or drift", and a draft
   identical to its default is dropped (AS-14).
5. Apply only on an explicit go from the person who owns the artifact, sending
   the base revision with the save. Silence, urgency, or a nearby "sounds good"
   is not a go.
6. On a conflict, reload the current revision, run a three-way merge against the
   base, and re-show the draft. Never overwrite blind, and never force the save
   to clear the error.

The save is store-then-do: record the revision before announcing success, and
make the apply idempotent so a retry cannot produce a second live change.

## Module 3 - Verification and failure

After the save, re-read the revision from the store. Confirm the rendered
artifact equals the preview you approved byte for byte; a mismatch is a failed
change, not a formatting detail.

Record the change with its new revision, the base it was derived from, the
origin (draft, import, or restore), and the operator who gave the go. Name what
did not change: untouched parts, skipped sections, and anything the preview did
not cover.

Rollback is copy-forward. Restore by saving an earlier revision as the next
revision and re-running the checks; never edit or delete history to undo a
change. A failed verification leaves the previous revision live and the draft
open.

When the store rejects the base as stale, treat it as a conflict, not an error
to retry. When the preview tool is unavailable, stop at the draft and report the
blocker; a blind save is not a fallback.

## Doctrine position

Serves Implement: turns an approved intent into one saved revision with a named
base and a rendered preview. It implements no enforcement and hands the saved
revision, its origin, and the preview match to Verify. A verification failure
returns the change to Implement as a new draft; rollback stays copy-forward.

## References

Repo-only (not shipped with a canon copy):

- `standards/work-authorization.md` -- WA-11: a text-only grant is advisory,
  never enforcement.
- `standards/prompt-assembly.md` -- AS-14: default provenance and upgrade
  visibility for an overridden part.
- `standards/stop-gate.md` -- STOPP propose, stop, and apply limits for a
  behavior change.
