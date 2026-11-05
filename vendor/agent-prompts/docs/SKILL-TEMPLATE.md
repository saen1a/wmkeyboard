# Skill template

Copy this skeleton for a new repository-authored skill. The rules behind it are
in [standards/skill-system-standard.md](../standards/skill-system-standard.md)
(SK-01..SK-14); the invocation and doctrine rules are in
[standards/agent-prompt-standard.md](../standards/agent-prompt-standard.md)
(AP-13, AP-14).

```markdown
---
name: <lowercase-hyphen-name>
description: <What it does in one sentence. Use when <concrete contexts, user vocabulary, synonyms> - covers <the decision, artifact, or check it produces>.>
rigid: true
metadata:
  category: <development|review|operations|research|documentation|design>
---
<!-- Repo-authored <YYYY-MM-DD>. Canon: this file. Rules: standards/<owning-standard>.md. -->

# <Title>

<One paragraph: what the skill buys, what it costs, and when not to use it.>

## Module 1 - <decision gate>

<The check that decides whether the procedure applies. Conditions to stop.>

## Module 2 - <procedure>

<The shortest sequence that produces the artifact. Prose or a compact table.>

## Module 3 - <verification and failure handling>

<The mechanical check, the evidence to return, and what to do when it fails.>

## Doctrine position

Serves <Plan|Implement|Review|Fix|Verify|Push>: <what it decides or produces>.
It implements nothing and hands <artifact> to <next phase or role>.

## References

Repo-only (not shipped with a canon copy):

- `standards/<owning-standard>.md` -- normative rules
- `references/<topic>.md` -- <when to read it>
```

## Checklist

- [ ] One job; one intent cluster; a trigger description that a user would say.
- [ ] Description 25-70 words, no host-only names, no second intent.
- [ ] Body target <= 1,200 tokens; at most 3 modules; 8 H2 sections maximum.
- [ ] Deep tables, variants, and examples in `references/`, routed from the body.
- [ ] `## Doctrine position` present; phases and handoffs named.
- [ ] Normative rules cited by ID, not copied.
- [ ] ASCII, English, single H1, no runtime counters (AP-04/AP-05).
- [ ] `evals/trigger/<skill>.json` with at least 4 positive, 2 negative cases.
- [ ] Behavioral or execution cases for the skill class (SK-12).
- [ ] Shape report before and after any change (SK-13).
- [ ] `skills/SKILLS.md` row, class, and reference list updated.

## Measure

```bash
python3 tooling/report_skill_shape.py --json
python3 tooling/check_skill_routing.py --fail-on-warn
python3 tooling/check_behavioral_evals.py
```
