---
name: operator-setup-interview
description: >-
  Install or configure a tool with the operator while spending little of their
  attention: probe the environment yourself, then ask one question per message,
  each with a recommended default they can accept in one word. Use when the
  user says help me set this up, install this with me, or walk me through
  configuring it, and when credentials, paths, or choices cannot be inferred.
rigid: true
metadata:
  category: operations
---
<!-- Repo-authored 2026-11-02. Canon: this file. Rules: standards/skill-system-standard.md. -->

# Operator setup interview

An installation costs the operator attention, which is the scarce resource.
This skill turns a configuration conversation into a short sequence: one probe,
one question at a time, one plan, one confirmation. Use it when the answers
live with a human; it is the wrong tool when the environment already answers
the question, when a single known gap is all that blocks work, or when the goal
is to pressure-test a plan rather than install something.

## Module 1 - Decision gate

Apply when an install, upgrade, or configuration needs facts or consent that
only a human can supply: a host name, a token policy, a target directory, a
pinned version, a restart window. The gate closes when a probe answers the
question. Do not apply it to a single known gap (`ask-questions-if-underspecified`)
and do not apply it to interrogate a plan (`grilling`): a plan gets grilled, an
install gets interviewed.

## Module 2 - Procedure

Probe once before the first message and keep the result to yourself. The
operator should not re-read the environment for you; state a probed fact only
where it becomes a question default.

One question per message. A message is a prompt, not a report: under 300 words,
one decision, one recommended default the operator can accept with a single
word such as `default`, `yes`, `no`, or a name. Each message carries one
sentence of why the choice matters, so the constraint is taught question by
question instead of dumped in a preamble. Recommend from the probe, the owning
standard, and the safer reversible option.

These steps are not the operator's to waive. When asked to skip the probe, to
batch every question into one message, or to install with guessed defaults,
refuse once in one sentence that names what the shortcut costs, then offer the
compressed form: the same protocol with one-word defaults and the one or two
answers that cannot be defaulted (HF-01). Agreeing to the shortcut and then acting on invented values is the
failure this skill exists to prevent.

Never execute while asking. No writes, installs, service restarts, or file
edits between the first question and the last answer. Collect every answer
first; an unanswered question stays open rather than being silently defaulted.
A setup question is a reply inside an active conversation, so the 300-word
ceiling governs it rather than the notification shape in NT-04.

Then send exactly one plan: the steps, the files and services touched, the
ready condition, the rollback, and the operator-only steps. Ask for one
confirmation. A plan carrying new questions is a second interview and a defect.

Never ask for a secret in chat. Secrets, credential pastes, console logins, and
anything only the operator can perform go into one message with exact commands
and where their output goes.

## Module 3 - Verification and handoff

After execution, probe again and compare against the plan, not against the
conversation. State the observable ready condition with the command or check
that proves it, plus the rollback that reverses the install.

Hand over the three rules the operator now owns, in plain language: how to tell
it is running, where the configuration and logs live, and how to upgrade or
remove it without help. Stop there: no satisfaction survey, no follow-up
question, no offer to configure more. Default silence is the correct close
(NT-01), because a finished install has given the operator nothing further to
decide.

If the probe fails or differs from the plan, report the gap and the next safe
step; do not open a new round of setup questions.

## Doctrine position

Serves Plan: its entry handoff is the installation request, it collects the
operator's decisions, and it produces one plan plus one set of operator-only
steps; Implement starts only after a single confirmation. Its exit handoff is
the installed tool, the ready condition, and the three ownership rules given to
the operator. It implements nothing itself, never substitutes for the PlanReview or Review
gate, and never claims Done.

## References

Repo-only (not shipped with a canon copy):

- `standards/skill-system-standard.md` -- shape, description, and evidence rules for this skill
- `standards/agent-notification.md` -- NT-01 default silence, NT-02 attention test, and NT-05 for one structured question per message
- `standards/workflow-loop.md` -- operator gates and the Ready/Push handoff
