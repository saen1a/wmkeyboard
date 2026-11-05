# Plan: rename the recovery screen

Status: example. Effective: 2026-11-03. This file is the copyable shape the
`tooling/check_plan_spec.py` gate reads; `make gate` validates it, so a format
change cannot drift away from an example that no longer passes.

## Goal

Rename the recovery screen in the handbook and the index so an operator finds it
by its new name without losing the old one as a search alias.

## Scope boundaries

- in scope: the two handbook pages and their internal links
- out of scope: the product UI, the API and any translation

## Request coverage

| Request item | Unit | Why |
|---|---|---|
| R1: the screen is renamed everywhere it is documented | U1 | both pages are edited in one unit |
| R2: existing links keep working | U2 | the link check is its own unit because it can fail alone |

## Units

| Unit | Acceptance | Verification | Owner |
|---|---|---|---|
| U1 | MUST: both pages name the new screen; SHOULD: the old name stays as an alias | `python3 tooling/check_doc_ranges.py` | doc-writer |
| U2 | MUST: every internal link resolves after the rename | `python3 tooling/check_doc_ranges.py` | doc-writer |

## Ownership and order

One writer for the unit (doc-writer): both pages share the index, so a second
writer would need a sequence for no gain.

1. U1 -- the text first, because the links U2 checks are produced by the rename.
2. U2 -- the link check runs against the renamed pages.

## Risks and halts

| Risk | Halt path | Operator question |
|---|---|---|
| the old screen name also appears in a published URL | HALT | may the alias redirect, or must the old path stay? |
