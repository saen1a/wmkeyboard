# Agent context file template

Copy the skeleton below into a repository's `AGENTS.md` and fill the
`{{SLOTS}}`. The rules behind it are in
[standards/agent-context-files.md](../standards/agent-context-files.md)
(CF-01..CF-10). A host that requires a different file name gets a pointer to the
canonical file, not a second edited copy (CF-06).

The file is a router, not a manual: every line is an exact command, a
non-standard convention or trap, or a pointer. Delete every line that does not
apply. Target one screen. Do not add an overview, a file tree, a tutorial, or a
generic best practice (CF-03).

````markdown
# {{PROJECT_ID}} agent router

Owner: {{CONTEXT_FILE_OWNER}}

## Commands

Run from {{PROJECT_ROOT}}.

```bash
{{BUILD_COMMAND}}          # build
{{TEST_COMMAND}}           # test (one file: {{SINGLE_TEST_COMMAND}})
{{LINT_COMMAND}}           # lint and format check
{{VERIFICATION_COMMANDS}}  # full check before handoff
```

## Conventions

{{NON_STANDARD_CONVENTIONS}}

## Verification

- Done means {{DEFINITION_OF_DONE}}; prove it with {{PROOF_COMMAND}}.
{{KNOWN_TRAPS}}

## Pointers

- Rules: {{RULES_POINTER}}
- Skills: {{SKILLS_POINTER}}
- Runbooks: {{RUNBOOKS_POINTER}}
- CI gates: {{CI_GATES_POINTER}}
````

## Slots

| Slot | Required | Content |
|---|---|---|
| `PROJECT_ID` | yes | Repository or package name the file scopes |
| `CONTEXT_FILE_OWNER` | yes | Role that reviews the file when build, test or layout changes |
| `PROJECT_ROOT` | yes | Directory the commands run in (usually `.`) |
| `BUILD_COMMAND` | yes | Exact build command |
| `TEST_COMMAND` | yes | Exact test command |
| `SINGLE_TEST_COMMAND` | no | Only when the single-file form is non-obvious; else delete the parenthetical |
| `LINT_COMMAND` | no | Delete when the build already runs it |
| `VERIFICATION_COMMANDS` | yes | The full check and the exit code it must return |
| `NON_STANDARD_CONVENTIONS` | yes | One `- ` bullet per convention. Include generated paths plus the regenerate command, the ownership boundary, and forbidden paths |
| `DEFINITION_OF_DONE` | yes | The state that ends the task |
| `PROOF_COMMAND` | yes | The command whose output proves the definition of done |
| `KNOWN_TRAPS` | no | One `- Trap:` bullet per trap (flaky suite, required environment variable names, ordering constraint); delete the line when none |
| `RULES_POINTER` | yes | Link to the project rules or ADRs |
| `SKILLS_POINTER` | no | Link to the skill index, when the project has one |
| `RUNBOOKS_POINTER` | no | Link to operational runbooks |
| `CI_GATES_POINTER` | yes | Link to the gate definition or workflow list |

## Checklist

- [ ] Every line is a command, a non-standard convention or trap, or a pointer
      (CF-01).
- [ ] Every command was copied from the repository and run once; a wrong command
      is worse than a missing one (CF-09).
- [ ] No overview, tutorial, persona, or rule that a linter, test or CI gate
      already enforces (CF-03, CF-06).
- [ ] One screen, no table of contents (CF-04).
- [ ] ASCII, English, short lines; no secrets, environment variable names only
      (CF-07, CF-10).
- [ ] One canonical file per scope; host-specific names point here (CF-06).

## Adoption test

Treat the file as a prompt change with a cost. Before adopting it, run the
paired method in CF-08: at least 20-30 real tasks, three seeds where the harness
is stochastic, with and without the file, recording success, steps, tokens,
wall-clock and cost. Keep a section only when it moves a metric. If the file
does not improve success, keep it as a routing and efficiency aid and say so.
