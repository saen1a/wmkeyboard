# Agent adapter standard (AD-01..AD-12)

Status: ACTIVE (2026-10-31). Applies to every runtime projection of this
library: `omp/`, `dsh/`, a consumer's Kilo/Paseo/OpenCode adapters, and any
future projection.

The library is vendor-neutral; each runtime differs in what it can actually
enforce. A projection is therefore not "the same prompt in another format". It
is a capability claim, and a capability claim needs a state, a date, and a
refusal path when the state is bad.

Evidence: `docs/knowledge-base/adopted-mechanisms-2026-10-31.md` section 3.
Contract: `agent-admission.schema.json`. Checker:
`../tooling/check_admission.py`. Records: `../omp/admission.json`,
`../dsh/admission.json`.

## AD-01 -- One projection per runtime, from the neutral source only

A runtime projection reads `agents/`, `prompts/`, `skills/`, and `fragments/`.
It never becomes a second canon: no projection-local edit survives without the
same change in the neutral source. A project that needs a different behavior
changes the template or the overlay, not the rendered copy.

## AD-02 -- Capability state is four-valued

Every capability a projection relies on carries exactly one state:

| State | Meaning |
|---|---|
| `supported` | verified on the named runtime version, with evidence and a date no older than 365 days |
| `degraded` | available only as a named narrower behavior |
| `unsupported` | not available; the projection must not require it |
| `unknown` | no verification record for this runtime version |

`unknown` is not `supported`. Absence of evidence is not evidence of a feature.

## AD-03 -- Admission is computed, fail-closed

Admission is the result of a computation over the required features, not an
opinion:

- any required feature `unknown` -> refuse;
- any required feature `unsupported` -> refuse;
- a required feature `degraded` -> admit only when `degraded_behavior` names the
  narrower behavior the projection uses instead;
- a required feature `supported` -> admit only with a `checked` date inside the
  365-day window and an evidence pointer. A stale `supported` claim is treated as
  `unknown` by this computation, so the record refuses; the stored record still
  says `supported` until it is re-verified, and the violation is reported.

A projection whose admission is `refused` may still be published as a record;
it may not be deployed as if admitted. The record says which capability refused
it, by name.

## AD-04 -- Generation parity is not runtime admission

Rendering one neutral body into eleven runtimes proves the renderer works. It
proves nothing about whether any runtime enforces the constraints the body
states. Per-runtime evidence is required per runtime; a shared generator does not
transfer it.

## AD-05 -- No silent fallback to an unconstrained path

When the projection cannot express a constraint (remove write, remove shell,
remove a subagent), it refuses. It never falls back to the host's unconstrained
native default while the prompt claims the constraint holds.

A stated rule without an enforced permission is a preference; say so
(`agent-context-files.md` CF-10) rather than letting the projection imply
enforcement.

## AD-06 -- Identity mapping is explicit and one-to-one

- Every projected agent maps to exactly one neutral template id.
- A compatibility alias is read-only, closed, and cannot dispatch: it may return
  a redirect record, never work product.
- Two projected agents may not claim the same template id with different bodies.
- The mapping is recorded in the projection, not inferred at render time.

## AD-07 -- Pins, versions, and drift

The projection pins the source it was built from: template and fragment hashes,
the library version, and the runtime version it was verified against. A pin
that no check enforces is worse than no pin; either the check exists or the pin
is removed.

- A source change and the projection change ship together.
- A runtime version change invalidates `supported` claims until re-verified
  (AD-09).

## AD-08 -- Activation is explicit

A projected agent is never activated by host inference. No implicit spawn from a
task description, a file name, or a tool call: activation is an explicit
operator or orchestrator decision.

A runtime whose parser infers spawning from tool names carries an explicit
constraint (for example, omitting the task tool) instead of a hopeful prompt
line.

## AD-09 -- The gap register is dated

Every `unsupported` or `unknown` capability is recorded with:

- the runtime and its version;
- what the projection does instead (the refusal or the degraded path);
- the date of the last verification attempt (`checked`) and what it observed
  (`attempted`, free text: the command run or the observation made).

A gap with no date is a guess. Re-verify on runtime version change and when a
`supported` claim is older than 365 days -- an aged claim is demoted to `unknown`
until it is re-checked. Keep the previous record so the trajectory is visible.

## AD-10 -- Refuse by name

An unavailable or refused projection reports the missing capability by name, in
the message the operator reads: "subagent dispatch: unsupported on runtime X
(checked 2026-10-31); the projection refuses to spawn children". A generic
"adapter error" is a defect, and a silent degrade is a worse one.

## AD-11 -- Probe the runtime as the agent runs it, and degrade per capability

Verify a declared account or CLI by invoking it through the same wrapper the
agent will use: with the shim directory removed from `PATH`, non-interactively,
and with no inherited credential variables.

- A probe that succeeds only under the operator's richer identity -- the token
  cache, shell profile, or elevation the operator happens to hold -- verifies
  the operator, not the agent's capability.
- A readiness gate over the whole projection is fail-closed: any capability the
  projection requires and the probe could not confirm refuses admission (AD-03).
- A per-source failure disables only that source and names it (AD-10); it MUST
  NOT silently widen into a whole-projection refusal or shrink into a bare
  warning.
- Refuse a wrapper that permits a broader identity than the agent role needs;
  a probe is meaningful only when it runs as the identity the role will hold.

## AD-12 -- The loop gate is a declared capability, not a promise

A projection that can start an implementation unit MUST declare `loop_gate` in
its admission record, with the four-valued support of AD-02:

- `supported` -- a pre-dispatch check refuses a unit without a clean
  `plan-review` verdict (`workflow-loop.md` WL-15), and the evidence names the
  command or hook that does it.
- `degraded` -- the runtime cannot intercept the dispatch (a read-only leaf set,
  a host without a hook); the record names the narrower behavior and the CI
  command that carries the gate instead:
  `tooling/check_plan_spec.py` before implementation, `tooling/check_loop_gate.py`
  over the ledger and verdict artifacts after it.
- `unsupported` -- no enforcement exists and none can be named; the record names
  the refusal, and no projection may claim the loop is enforced.
- `unknown` -- not exercised; it refuses admission like every other unknown.

A projection's prose may describe the loop; only this cell says whether the
runtime enforces it. Claiming enforcement without the check is exactly the
"stated rule is not an enforced one" failure (WA-11).

## Applying this standard

Point an agent at this file and ask it to admit one runtime. It must:

1. Write one admission record per runtime under `agent-admission/1`.
2. Declare each required capability with its four-valued state, date, and
   evidence.
3. Name the degraded behavior for every `degraded` capability.
4. Compute admission fail-closed and record the refusal by name.
5. Cross-check that no projected tool relies on a capability marked
   `unsupported`.
6. Run `python3 tooling/check_admission.py PATH`.
7. HALT and report if the runtime cannot be exercised at all: then every
   capability is `unknown` and the record is refused, not blank.

## Cross-refs

- `tool-set.md` -- TS-07 version, pin, and cache epoch; a probe pins the wrapper
  it exercised
- `agent-prompt-standard.md` -- AP-10 least-privilege tools
- `agent-context-files.md` -- CF-10 rules versus enforced permissions
- `prompt-security.md` -- PS-04 tool metadata trust, PS-09 config as trust root;
  the probe never inherits the operator's credentials
- `agent-adapter.md` -- AD-03 computed fail-closed admission and AD-10 refuse by
  name (this file)
- `agent-admission.schema.json` -- record shape and enums
- `../tooling/check_admission.py` -- validator
- `../omp/README.md` -- the OMP projection and its drift gate
- `../dsh/README.md` -- dsh template pairing invariant
