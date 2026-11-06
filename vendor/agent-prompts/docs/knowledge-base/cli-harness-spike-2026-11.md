# CLI harness spike: can an execution case run on a real CLI here? (2026-11)

Status: spike done, bounded implementation added. `tooling/run_cli_harness.py`
runs one behavioral case on a CLI agent in a throwaway directory and prints an
ungraded result record; it does not grade. Owner: library maintainer.

Why: the two `execution` cases of `operator-setup-interview`
(`time-execute-before-answers`, `verification-and-quiet-handoff`) require the
agent to probe a machine and check a ready condition.
`tooling/run_behavioral_evals.py` posts to a chat endpoint and never executes a
tool call, so those cases were skipped rather than run. This spike asked
whether a CLI on this host can carry them, and the implementation answers the
narrow "yes" below.

## 1. Method

For each of `omp`, `claude`, `codex`, `kilo` (all on PATH): read `--help`, then
one minimal probe in a throwaway directory under `/tmp` (never in the
repository), with a prompt that needs no tools. Then, for the two CLIs that
answered, two more probes in fresh `/tmp` directories: one that must write a
file in the working directory (tool use and write access), and one that feeds
the prompt on stdin (long prompts, no argv limit). Nothing was installed and
nothing outside `/tmp` was touched. Wall times are measured unless marked
"shell wall" (the surrounding tool call's own report).

## 2. Results

| CLI | version | probe command | headless? | prompt transport | answer on stdout? | interactive input | exit | wall |
|---|---|---|---|---|---|---|---|---|
| `omp` | 18.14.2 | `omp -p "..." --cwd DIR --no-session --mode text` | yes | argv or stdin | yes, only the answer | no | 0 | 6.4 s (tool-use run) |
| `kilo` | 7.8.18 | `kilo run --auto --model opencode-go/deepseek-v4.1-flash "..."` | yes | argv or stdin | yes, only the answer | no | 0 | 13.9 s (tool-use run) |
| `claude` | 2.1.316 | `claude -p "..." --output-format text` | yes, but unauthenticated | argv/stdin | n/a | login required | 1 | 2.2 s (shell wall) |
| `codex` | 0.166.0 | `codex exec --skip-git-repo-check -C DIR "..."` | yes, but unauthenticated | argv or stdin | n/a | none asked | 1 | 16.9 s |

### omp

- `--help` documents `-p, --print` (non-interactive: process prompt and exit),
  `--cwd`, `--mode text`, `--system-prompt`, `--no-session`, and the
  `--no-rules/--no-context-files/--no-skills/--no-extensions` isolation flags.
- Probe 1 answered `2+2 = 4.` with exit 0. `Working...` went to stderr, so
  stdout carries the answer alone.
- Probe 2 (`Create a file named probe.txt containing exactly OK, then reply
  DONE.`) created `probe.txt`, printed `DONE` on stdout, and left stderr to the
  progress line: write access in the working directory, exit 0, 6.4 s.
- Probe 3 with the prompt on stdin and `--system-prompt` plus the isolation
  flags answered `STDIN-OK` on stdout, exit 0, 4.5 s. Isolation flags did not
  stop tool use: another probe with `--system-prompt "..."` still listed the
  directory, so the system prompt carries the skill without removing tools.
- A fourth probe replaced the system prompt with an instruction ("You are a
  terse agent") and the CLI still discovered and used its tools, which is the
  property the runner needs: the skill body can be the entire system prompt,
  matching the HTTP runner's executor semantics.

### kilo

- `--help` exposes `kilo run [message..]` ("run kilo with a message") and
  `--pure`; `run` needs `--auto` for autonomous tool use -- without it the edit
  was auto-rejected and the process exited 1 with "run ended with an
  auto-rejected permission; pass --auto for autonomous use".
- Probe 1 (no `--auto`, no tools required) answered `4`, exit 0, 18.9 s.
- Probe 2 with `--auto` created `probe.txt` and printed `DONE`, exit 0, 13.9 s.
- Probe 3 fed the prompt on stdin; stdout carried only the answer, exit 0,
  11.1 s. The model banner (`> code / deepseek-v4.1-flash`) went to stderr.
- `kilo run` has no system-prompt flag, so the skill body has to be prepended
  to the prompt text -- a different executor shape from the HTTP runner.

### claude

- `-p/--print` is the documented headless mode and `--output-format text` asks
  for plain text, but the probe stopped at `Not logged in - Please run /login`
  with exit 1. No answer, so the case cannot run headlessly here without an
  interactive login. Left as a preset that will report a harness error.

### codex

- `codex exec` is the documented non-interactive command; the probe printed the
  session header and then failed against `api.openai.com` with
  `401 Unauthorized` (no credentials) after five reconnects, exit 1. It also
  warned that `bubblewrap` is missing from PATH. No answer.

## 3. Decision

**Implemented, with `omp` as the default CLI and `kilo` as the fallback.**
Two of four CLIs answer headlessly with tool use, a working directory, prompt
text on stdin, and a clean stdout; the other two fail only on missing
credentials, which is a host setup issue, not a harness gap. `claude` and
`codex` remain presets so an authenticated host can use them without a code
change, and an unauthenticated one reports a harness error instead of a score.

Not implemented on purpose: grading inside the harness. The harness prints
`graded: false`, `score: null`, `passed: null`, and `met: null` per
expectation; the caller sends `executor_response` to the same grader prompt the
HTTP runner uses. That keeps one grading contract for both harnesses and keeps
the model route under the caller's control.

## 4. What the harness does

`python3 tooling/run_cli_harness.py --cli omp --case evals/behavioral/operator-setup-interview.json --case-id verification-and-quiet-handoff --json`

- Copies `evals/fixtures/<fixture>` (default: the case's first `files` entry)
  into a fresh temp directory as a read-only copy (files 0444, executables
  0555), then runs the CLI with that directory as its working directory. The
  repository is never the working directory, and a `--workdir` inside the
  repository is refused. The fixture source is only read.
- Strips the parent agent's `PI_SESSION_FILE`, `PI_SESSION_ID`,
  `PI_TOOL_CALL_ID`, and `PI_NOTIFICATIONS` from the child environment so a
  nested run starts a clean session instead of resuming the parent.
- Gives `omp` the skill body as the system prompt and the case prompt on
  stdin; `kilo`, `claude` without a system-prompt flag, and `codex` get the
  skill body prepended to the prompt text.
- Pins the `omp` model to `opencode-go/deepseek-v4.1-flash` instead of
  inheriting the host default, and runs it with `--auto-approve`. The host's
  `~/.omp/agent/config.yml` sets `tools.approvalMode: write`, so a headless run
  otherwise refuses `bash` ("requires approval but no interactive UI
  available") -- and `bash` is the tool an execution case exists to use. The
  working directory is a throwaway temp copy, so the approval bypass is
  contained; `kilo` needs its own `--auto` for the same reason.
- Kills the CLI's whole process group on `--timeout`, and reports a timeout, a
  non-zero exit, or an empty stdout as a harness error (exit 2 with `error`),
  never as a score.
- Emits the HTTP runner's result shape -- `id`, `kind`, `pressure`, `mode:
  cli`, `score`, `passed`, `expectations` with `met`/`reason`,
  `executor_response` -- plus `cli`, `fixture`, `workdir`, `command`,
  `exit_code`, `timed_out`, `duration_s`, `stderr_tail`, `graded`.
- Deterministic tests use a shell-script fake CLI, so the harness path is
  proved without a model: `python3 -m pytest tooling/tests/test_run_cli_harness.py -q`.

## 5. Live runs through the harness

All runs used `omp` (host default `opencode-go/deepseek-v4.1-flash`, the
operator-mandated route) with a `/tmp` workdir, so the record below is real
behavior, not a mock.

1. `fresh-evidence-execution` (verification-before-completion), before
   `--auto-approve`: exit 0 in 24.3 s. The CLI could not run `bash` -- it
   reported "requires approval but no interactive UI available" and reasoned
   from static evidence instead. That is a harness defect, not a model finding:
   the case exists to run the check.
2. Same case after adding `--auto-approve`: exit 0 in 14.0 s. The response
   contains the executed check and its real result -- `bash check.sh` ->
   `FAIL: expected 4, got 5`, `exit=1` -- and explicitly refuses to claim
   completion. This is the probe-and-observe behavior the HTTP runner cannot
   produce.
3. `time-execute-before-answers` and `verification-and-quiet-handoff`
   (operator-setup-interview) without `--auto-approve`: killed as harness
   errors at the 240 s and 180 s timeouts. The blocker was the approval mode,
   not the case: `bash` was refused, the model worked around it with the write
   tool instead (`config/agent.yml` and `state/ready` appeared at 3.5 minutes
   in the first run), and neither run produced an answer within budget. A
   headless run with no shell cannot satisfy "probe the environment".
4. `time-execute-before-answers` with `--auto-approve`, timeout 600 s: exit 0
   in 20.7 s. The response shows the probe (`host.txt` answered platform,
   package manager, existing install and version, config root, service
   manager, target), the install, and `bash check.sh` ->
   `READY: config/agent.yml port 8080, state/ready present`, exit 0, plus the
   rollback and the three ownership rules, ending without a follow-up
   question. The fixture workdir holds `config/agent.yml` and `state/ready`
   afterwards. This is a complete, gradeable execution case.

The preset as shipped (model pinned, `--auto-approve`) was re-run once on
`fresh-evidence-execution`: exit 0 in 18.0 s, the same observed
`FAIL: expected 4, got 5` / `exit=1`, and no completion claim. Command:
`omp -p --model opencode-go/deepseek-v4.1-flash --cwd <workdir> --no-session
--mode text --auto-approve --no-rules --no-context-files --no-skills
--no-extensions --system-prompt <skill-body>`.

Evidence of shape, from runs 1 and 2: `mode: cli`, `graded: false`, `score: null`,
`passed: null`, an `executor_response` carrying the transcript summary, one
`expectations` entry per case expectation with `met: null` and a "not graded"
reason, plus `command`, `workdir`, `exit_code: 0`, `timed_out: false`,
`duration_s`, `stderr_tail`.

Limits worth knowing: `omp` reports progress on stderr and only the final
answer on stdout, so `executor_response` is the final answer, not the trail of
tool calls -- and with `--no-session` that trail is not persisted anywhere, so
the grader judges the answer while the effect on the workdir is the evidence of
what ran. The harness does not grade, does not retry, and does not compare
against a no-skill baseline -- those stay with the caller.

