#!/usr/bin/env python3
"""Validate the workflow-loop invariants and carrier coverage.

Checks:
1. The canonical fragment contains the seven phases, the plan-review gate, the
   audit/finalize aliases, all back-edges, the refinement bound and its
   plan-review exception, and the verifier rule.
2. Every role/task carries the fragment byte-for-byte.
3. `owned_phases` uses only canonical phases; read-only roles never claim Push
   (non-mutating Implement/Fix artifacts are allowed); every phase has an owner,
   and the plan-review gate has a named authority. The standard contains the
   Ready/HALT rows, Fix->Plan, Fix->PlanReview, and the gate vocabulary.
4. The four dsh preset personas parse as YAML and carry the fragment after
   whitespace normalization.
5. The subagent handoff contract names PHASE and the loop position.
6. CATALOG pins doctrine 1.5.0, library 2.12.0, template 2.0.4.
7. The plan-review gate has a named authority that owns it (WL-15).
7. Every gate-authority role names the gate verdict record (VI-01).

Exit 0 when clean, 1 on any violation. ASCII-only output.
"""

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PHASES = ["Plan", "PlanReview", "Implement", "Review", "Fix", "Verify", "Push"]
OUTCOMES = ["Ready", "Ready (unverified)", "Done", "HALT"]
REQUIRED_TRANSITIONS = {
    # No ("Plan", "Implement"): the plan-review gate is the only way in (WL-15).
    ("Plan", "PlanReview"), ("Plan", "HALT"),
    ("PlanReview", "Implement"), ("PlanReview", "Fix"), ("PlanReview", "HALT"),
    ("Implement", "Review"), ("Implement", "HALT"),
    ("Review", "Verify"), ("Review", "Fix"), ("Review", "HALT"),
    ("Fix", "Review"), ("Fix", "PlanReview"), ("Fix", "Plan"), ("Fix", "HALT"),
    ("Verify", "Ready"), ("Verify", "Ready (unverified)"),
    ("Verify", "Fix"), ("Verify", "HALT"),
    ("Ready", "Push"), ("Ready", "HALT"),
    ("Ready (unverified)", "Push"), ("Ready (unverified)", "HALT"),
    ("Push", "Done"), ("Push", "HALT"),
}
ALLOWED_TRANSITIONS = REQUIRED_TRANSITIONS | {
    # A skipped check with no exemption stays put (VI-03, SG-04); `hold` is a
    # decision, not a phase, so it appears only as a transition target.
    ("Verify", "hold"), ("Review", "hold"), ("Fix", "hold"),
    ("Ready", "Ready"), ("Verify", "Ready (unverified)"),
    ("Ready (unverified)", "Push"), ("Ready (unverified)", "HALT"),
    ("Done", "none"), ("HALT", "none"),
}
FRAGMENT = ROOT / "fragments" / "agent-doctrine.md"
# Roles that can close a Review or Verify gate. Each must name the gate verdict
# record, so the interface cannot drift back to a prose "pass".
GATE_AUTHORITIES = (
    "agents/orchestration/orch-orchestrator.md",
    "agents/review/rev-review-lead.md",
    "agents/review/rev-reviewer.md",
    "agents/review/rev-code-skeptic.md",
)
# Roles that must own and name the plan-review gate (WL-15), so the gate cannot
# drift to a role that never reviews specs.
PLAN_REVIEW_AUTHORITIES = (
    "agents/orchestration/orch-orchestrator.md",
    "agents/review/rev-review-lead.md",
)
# Commands that are style or status utilities, not task dispatchers (AP-14).
# The set is closed and self-pruning: a row fails once the file is gone or once
# it starts carrying a Doctrine line anyway.
COMMAND_EXEMPT = ("caveman.md",)


def extract(text, tag):
    match = re.search(r"(?ms)^\s*<%s>.*?</%s>" % (tag, tag), text)
    return match.group(0) if match else None


def normalize(text):
    return " ".join(text.split())


def frontmatter_value(text, key):
    match = re.match(r"(?ms)^---\s*\n(.*?)\n---", text)
    if not match:
        return None
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    return data.get(key) if isinstance(data, dict) else None


def read_required(path, violations):
    if not path.is_file():
        violations.append("missing required file: %s" % path.relative_to(ROOT).as_posix())
        return ""
    return path.read_text(encoding="utf-8")


def has_open_finding(findings):
    for line in str(findings).splitlines():
        low = line.lower()
        severe = (re.search(r"\b(high|medium)\b", low)
                  or re.search(r"\(\s*[hm]\s*[,)]", low)
                  or re.search(r"\|\s*(high|medium|h|m)\s*\|", low)
                  or re.search(r"\b[hm]\s*:\s*(?!none\b)(?:open|high|medium|[1-9])", low))
        if not severe:
            continue
        if re.match(r"^\s*(?:[-*]|\d+\.)?\s*no\s+(?:unresolved\s+)?(?:open\s+)?(?:high|medium)\b.*(?:finding|remain)", low):
            continue
        if re.match(r"^\s*(?:[-*]|\d+\.)?\s*none\.?\s*$", low):
            continue
        return True
    return False


def validate_ledger_row(record):
    errors = []
    if record.get("phase") not in PHASES:
        errors.append("phase is not a phase: %s" % record.get("phase"))
    if record.get("status") not in PHASES + OUTCOMES:
        errors.append("status is not a phase/outcome: %s" % record.get("status"))
    status = record.get("status")
    phase = record.get("phase")
    expected_phase = {"Ready": "Verify", "Ready (unverified)": "Verify",
                      "Done": "Push"}.get(status, status)
    if status in PHASES + ["Ready", "Ready (unverified)", "Done"] and phase != expected_phase:
        errors.append("phase %s does not match status %s" % (phase, status))
    if record.get("gate") not in ("pass", "fix", "hold", "halt"):
        errors.append("gate is not canonical: %s" % record.get("gate"))
    if record.get("decision") not in ("pass", "fix", "hold", "halt"):
        errors.append("decision is not canonical: %s" % record.get("decision"))
    if record.get("gate") != record.get("decision"):
        errors.append("gate and decision differ: %s/%s"
                      % (record.get("gate"), record.get("decision")))
    for field in ("unit_id", "artifact", "findings", "evidence", "owner",
                  "timestamp"):
        if not str(record.get(field, "")).strip():
            errors.append("%s is empty" % field)
    findings = str(record.get("findings", "")).strip()
    names = sorted(set(re.findall(r"findings-[A-Za-z0-9._-]+\.md", findings)))
    if names:
        if len(names) > 1:
            errors.append("findings cell names more than one ledger")
        import check_findings_ledger as findings_check
        for name in names:
            path = ROOT / "provenance" / name
            if not path.is_file():
                errors.append("findings ledger does not exist: %s" % name)
                continue
            try:
                rows, ledger_errors = findings_check.parse(path)
            except OSError as exc:
                errors.append("findings ledger unreadable: %s: %s" % (name, exc))
                continue
            for error in ledger_errors:
                errors.append("%s: %s" % (name, error))
            if record.get("status") == "Done":
                open_rows = [row for row in rows
                             if row.get("state") == "open"
                             and row.get("severity") in ("high", "medium")]
                if open_rows:
                    errors.append("%s has an open high/medium finding" % name)
    elif not re.match(r"^none\b", findings, re.I):
        errors.append("findings cell must record none or name findings-<task>.md")
    attempt = record.get("attempt", "")
    if not attempt.isdigit():
        errors.append("attempt must be a non-negative integer: %s" % attempt)
    elif int(attempt) > 1 and record.get("phase") != "PlanReview":
        errors.append("attempt %s is above the one-refinement bound; only a "
                      "PlanReview row carries a round number (WL-07, WL-15)"
                      % attempt)
    next_phase = record.get("next")
    allowed_next = {
        "Plan": ("PlanReview", "HALT"),
        "PlanReview": ("Implement", "Fix", "HALT"),
        "Implement": ("Review", "HALT"),
        "Review": ("Verify", "Fix", "HALT"),
        "Fix": ("Review", "PlanReview", "Plan", "HALT"),
        "Verify": ("Ready", "Ready (unverified)", "Fix", "HALT"),
        "Ready": ("Push", "HALT", "none"),
        "Ready (unverified)": ("Push", "HALT", "none"),
        "Push": ("Done", "HALT"),
        "Done": ("none",),
        "HALT": ("none",),
    }
    if record.get("status") == "HALT" and record.get("gate") != "halt":
        errors.append("HALT status requires gate halt")
    if record.get("status") == "Done":
        if record.get("gate") != "pass":
            errors.append("Done status requires gate pass")
        if has_open_finding(record.get("findings", "")):
            errors.append("Done row has an open high/medium finding")
    if record.get("gate") == "halt" and (record.get("status") != "HALT"
                                         or next_phase != "none"):
        errors.append("halt gate must be terminal (HALT -> none)")
    if record.get("gate") == "fix":
        if next_phase not in ("Fix", "PlanReview", "Plan", "HALT"):
            errors.append("fix gate must point to Fix, Plan, or HALT: %s" % next_phase)
    if record.get("gate") == "pass" and next_phase in ("Fix", "Plan"):
        errors.append("pass gate cannot point to %s" % next_phase)
    if record.get("status") == "Ready (unverified)":
        if record.get("gate") != "hold" or record.get("decision") != "hold":
            errors.append("Ready (unverified) requires gate=decision=hold")
        if next_phase not in ("Push", "HALT", "Ready (unverified)"):
            errors.append("Ready (unverified) next must be Push, HALT, or stay")
        findings = str(record.get("findings", "")).lower()
        if "exemption" not in findings and "unverified" not in findings:
            errors.append("Ready (unverified) needs an exemption record")
    if (record.get("decision") == "hold" and next_phase != record.get("status")
            and record.get("status") != "Ready (unverified)"):
        errors.append("hold must keep next equal to status: %s" % next_phase)
    if next_phase not in PHASES + OUTCOMES + ["none"]:
        errors.append("next is not a phase/outcome: %s" % next_phase)
    elif (next_phase not in allowed_next.get(record.get("status"), ())
          and not (record.get("decision") == "hold" and next_phase == record.get("status")
                   and record.get("status") not in ("Done", "HALT"))):
        errors.append("next is not legal from %s: %s" % (record.get("status"), next_phase))
    return errors


def command_findings(root=None):
    """AP-14: every task command carries one Doctrine line, exempt ones do not."""
    root = root or ROOT
    directory = root / "commands"
    results = []
    if not directory.is_dir():
        return results
    for name in COMMAND_EXEMPT:
        if not (directory / name).is_file():
            results.append(("commands/" + name, False,
                            "exempt command is missing; drop the exemption row "
                            "(the set is self-pruning)"))
    for path in sorted(directory.glob("*.md")):
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        lines = re.findall(r"(?m)^Doctrine: (.+)$", text)
        line = lines[0] if len(lines) == 1 else None
        if len(lines) > 1:
            results.append((relative, False,
                            "carries %d 'Doctrine:' lines; a command names its "
                            "phases and handoff once (AP-14)" % len(lines)))
            continue
        if path.name in COMMAND_EXEMPT:
            if line and any(phase in line for phase in PHASES):
                results.append((relative, False,
                                "exempt command now names a phase, so it became a "
                                "dispatcher; remove the exemption row instead of "
                                "letting it drift"))
            continue
        if not line:
            results.append((relative, False,
                            "missing a single 'Doctrine:' line (AP-14)"))
            continue
        body = line
        if not any(phase in body for phase in PHASES):
            results.append((relative, False,
                            "the Doctrine line names no owned phase"))
        elif not re.search(r"(?i)handoff|hand off|operator", body):
            results.append((relative, False,
                            "the Doctrine line names no handoff or operator gate"))
    return results


def foreground_findings(root=None):
    """The composed OMP foreground policy states the plan-review gate once."""
    root = root or ROOT
    directory = root / "omp" / "prompts" / "foreground"
    manifest_path = directory / "manifest.json"
    relative = "omp/prompts/foreground/manifest.json"
    if not manifest_path.is_file():
        return [(relative, False, "missing the foreground module manifest")]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [(relative, False, "unreadable manifest: %s" % exc)]
    order = manifest.get("order") or list(manifest.get("modules") or {})
    if not order:
        return [(relative, False, "the manifest names no modules")]
    results = []
    carriers = []
    for name in order:
        if (not str(name).endswith(".md") or "/" in str(name)
                or ".." in str(name) or name not in (manifest.get("modules") or {})):
            results.append((relative, False,
                            "module name %r is not a plain .md file of this set"
                            % str(name)[:60]))
            continue
        path = directory / name
        if not path.is_file():
            results.append(("omp/prompts/foreground/" + name, False,
                            "module named in the manifest is missing"))
            continue
        text = path.read_text(encoding="utf-8")
        # The canonical statement, not a mention: the loop arrow plus the rule.
        if ("Plan -> PlanReview -> Implement" in text
                and re.search(r"(?i)plan-review verdict", text)):
            carriers.append(name)
    if not carriers:
        results.append((relative, False,
                        "the composed foreground set never names the plan-review "
                        "gate (WL-15); a main session would run the loop without it"))
    elif len(carriers) > 1:
        results.append((relative, False,
                        "the plan-review gate is stated in %d modules (%s); state "
                        "it once, in the governance module"
                        % (len(carriers), ", ".join(carriers))))
    return results


def transition_pairs(text):
    pairs = set()
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0] in PHASES + ["Ready", "Ready (unverified)",
                                                     "Done", "HALT"]:
            pairs.add((cells[0], cells[2]))
    return pairs


def main():
    violations = []
    fragment = read_required(FRAGMENT, violations)
    block = extract(fragment, "doctrine")
    if not block:
        violations.append("canonical doctrine block missing")
        block = ""
    checks = {
        "Plan -> PlanReview -> Implement": "Plan -> PlanReview -> Implement" in block,
        "plan review is the spec gate": "PlanReview is the spec gate" in block,
        "plan review is never skipped": "never skipped" in block,
        "PlanReview -> Fix": "Fix -> PlanReview" in block,
        "round states CHANGED": "CHANGED" in block,
        "no-progress is stalled": "stalled" in block,
        "Review is the audit gate": "Review is the audit gate" in block,
        "Push is finalize": "Push is finalize" in block,
        "Review -> Fix": "Fix -> Review" in block,
        "Verify -> Fix": "Fix -> Review -> Verify" in block,
        "one refinement per code gate": "One refinement per code gate" in block,
        "independent verifier": "author is never sole verifier" in block.lower(),
        "Ready outcome": "Ready" in block,
        "HALT outcome": "HALT" in block,
    }
    standard = read_required(ROOT / "standards" / "workflow-loop.md", violations)
    ap14 = read_required(ROOT / "standards" / "agent-prompt-standard.md", violations)
    for outcome in OUTCOMES:
        if outcome not in ap14:
            violations.append("AP-14 missing outcome: %s" % outcome)
    pairs = transition_pairs(standard)
    for pair in sorted(REQUIRED_TRANSITIONS):
        if pair not in pairs:
            violations.append("workflow-loop standard missing transition %s -> %s" % pair)
    for pair in sorted(pairs - ALLOWED_TRANSITIONS):
        violations.append("workflow-loop standard has illegal transition %s -> %s" % pair)
    for needle in ("pass | fix | hold | halt", "## WL-08 -- Ledger",
                   "## WL-13 -- Findings ledger",
                   "## WL-14 -- Publication proof"):
        if needle not in standard:
            violations.append("workflow-loop standard missing: %s" % needle)
    expected = ["unit_id", "phase", "attempt", "gate", "status", "artifact",
                "findings", "evidence", "decision", "owner", "timestamp", "next"]
    anchor = ROOT / "provenance" / "ledger-workflow-loop-2026-10.md"
    if not anchor.is_file():
        violations.append("ledger instance missing: %s"
                          % anchor.relative_to(ROOT).as_posix())
    ledgers = sorted((ROOT / "provenance").glob("ledger-*.md"))
    if not ledgers:
        violations.append("no provenance ledger instance found")
    for ledger in ledgers:
        label = ledger.relative_to(ROOT).as_posix()
        lines = ledger.read_text(encoding="utf-8").splitlines()
        header = next((line for line in lines if line.startswith("| unit_id |")), "")
        columns = [cell.strip() for cell in header.strip().strip("|").split("|")]
        if columns != expected:
            violations.append("%s: ledger header does not match WL-08" % label)
            continue
        rows = []
        for line in lines:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if line.startswith("|") and cells and cells[0] not in ("unit_id", "---"):
                rows.append(line)
        if not rows:
            violations.append("%s: ledger has no unit row" % label)
        unit_ids = []
        for row in rows:
            cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
            if len(cells) != len(expected):
                violations.append("%s: ledger row has %d cells, expected %d"
                                  % (label, len(cells), len(expected)))
                continue
            record = dict(zip(expected, cells))
            unit_ids.append(record["unit_id"])
            for error in validate_ledger_row(record):
                violations.append("%s: %s" % (label, error))
        duplicates = sorted({item for item in unit_ids if unit_ids.count(item) > 1})
        if duplicates:
            violations.append("%s: duplicate unit ids: %s"
                              % (label, ", ".join(duplicates)))
    orchestration_dir = ROOT / "agents"
    if not orchestration_dir.is_dir():
        orchestration_dir = ROOT / "roles"
    orchestrator = read_required(orchestration_dir / "orchestration" / "orch-orchestrator.md",
                                 violations)
    if "gate: pass|fix|hold|halt" not in orchestrator:
        violations.append("orchestrator output missing canonical gate vocabulary")
    for name, ok in checks.items():
        if not ok:
            violations.append("doctrine missing invariant: %s" % name)

    role_root = ROOT / "agents"
    if role_root.is_dir() and (ROOT / "roles").exists():
        violations.append("legacy roles/ exists alongside agents/; remove it")
    if not role_root.is_dir():
        role_root = ROOT / "roles"
        print("WARN legacy root: agents/ missing; using roles/")
    task_root = ROOT / "prompts" / "tasks"
    if task_root.is_dir() and (ROOT / "tasks").exists():
        violations.append("legacy tasks/ exists alongside prompts/tasks/; remove it")
    if (ROOT / "workspace-prompts").exists():
        violations.append("legacy workspace-prompts/ exists; remove it")
    if not task_root.is_dir():
        task_root = ROOT / "tasks"
        print("WARN legacy root: prompts/tasks/ missing; using tasks/")
    files = sorted(list(role_root.rglob("*.md")) + list(task_root.glob("*.md")))
    agent_count = len(list(role_root.rglob("*.md")))
    task_count = len(list(task_root.glob("*.md")))
    if (agent_count, task_count) != (38, 3):
        violations.append("expected 38 agents + 3 tasks, found %d + %d"
                          % (agent_count, task_count))
    owners = {phase: 0 for phase in PHASES}
    carrier_ids = []
    catalog_carrier_ids = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        id_match = re.search(r"(?m)^id:\s*(\S+)\s*$", text)
        if not id_match:
            violations.append("%s: missing id" % rel)
        else:
            carrier_ids.append(id_match.group(1))
            if role_root in path.parents:
                catalog_carrier_ids.append(id_match.group(1))
        carrier = extract(text, "doctrine")
        if carrier is None:
            violations.append("%s: missing <doctrine>" % rel)
        elif carrier != block:
            violations.append("%s: doctrine is not byte-identical" % rel)
        match = re.search(r"^owned_phases:\s*\[(.*?)\]", text, re.M)
        if not match:
            violations.append("%s: missing owned_phases" % rel)
            continue
        phases = [item.strip() for item in match.group(1).split(",") if item.strip()]
        unknown = [phase for phase in phases if phase not in PHASES]
        if unknown:
            violations.append("%s: unknown phases %s" % (rel, unknown))
        for phase in phases:
            if phase in owners:
                owners[phase] += 1
        profile_value = frontmatter_value(text, "tool_profile") or ""
        profile_value = str(profile_value).strip()
        if profile_value == "read-only":
            # Read-only research/report roles may still own non-mutating
            # Implement/Fix artifacts; no read-only role may own Push.
            if "Push" in phases:
                violations.append("%s: read-only role owns Push" % rel)
        review_surface = (rel.startswith(("agents/review/", "roles/review/"))
                          or rel.endswith("design-ui-reviewer.md")
                          or rel.endswith("eng-oracle.md"))
        if review_surface and "Fix" in phases:
            violations.append("%s: review role owns Fix" % rel)
        if rel in PLAN_REVIEW_AUTHORITIES:
            if "PlanReview" not in phases:
                violations.append("%s: plan-review authority does not own PlanReview"
                                  % rel)
            if not re.search(r"(?i)plan.review|WL-15", text.replace(block, "")):
                violations.append("%s: plan-review authority does not name the gate"
                                  % rel)
        workflow = extract(text, "workflow")
        if workflow:
            scan_phases = (("Implement", "Push") if review_surface
                           else ("PlanReview", "Implement", "Review", "Fix",
                                 "Verify", "Push"))
            for phase in scan_phases:
                marker = "%s --" % phase
                for match in re.finditer(re.escape(marker), workflow):
                    window = workflow[match.start():match.start() + 140].lower()
                    allowed = any(word in window for word in (
                        "not yours", "belongs", "downstream", "operator",
                        "parent", "requesting session", "never", "handoff"))
                    if phase not in phases and not allowed:
                        violations.append("%s: workflow performs %s not in owned_phases"
                                          % (rel, phase))
                        break
    for phase, count in owners.items():
        if count == 0:
            violations.append("no owner for phase %s" % phase)
    duplicates = sorted({item for item in carrier_ids if carrier_ids.count(item) > 1})
    if duplicates:
        violations.append("duplicate carrier ids: %s" % ", ".join(duplicates))
    catalog = read_required(ROOT / "CATALOG.md", violations)
    index_section = catalog.split("## Index", 1)[-1].split("\n## ", 1)[0]
    catalog_id_list = re.findall(r"(?m)^\| `([a-z][a-z0-9-]+)` \|", index_section)
    catalog_ids = set(catalog_id_list)
    catalog_dupes = sorted({item for item in catalog_id_list
                            if catalog_id_list.count(item) > 1})
    if catalog_dupes:
        violations.append("CATALOG duplicate ids: %s" % ", ".join(catalog_dupes))
    if set(catalog_carrier_ids) != catalog_ids:
        missing = sorted(set(catalog_carrier_ids) - catalog_ids)
        extra = sorted(catalog_ids - set(catalog_carrier_ids))
        if missing:
            violations.append("CATALOG missing ids: %s" % ", ".join(missing))
        if extra:
            violations.append("CATALOG lists unknown ids: %s" % ", ".join(extra))

    presets = sorted((ROOT / "dsh" / "presets").glob("*.template.yml"))
    if len(presets) != 4:
        violations.append("expected 4 dsh presets, found %d" % len(presets))
    try:
        import yaml
    except ImportError:
        violations.append("PyYAML is required to validate dsh presets")
    else:
        for path in presets:
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(ROOT).as_posix()
            try:
                yaml.safe_load(text)
            except Exception as exc:
                violations.append("%s: invalid YAML: %s" % (rel, exc))
            carrier = extract(text, "doctrine")
            if carrier is None:
                violations.append("%s: missing <doctrine>" % rel)
            elif normalize(carrier) != normalize(block):
                violations.append("%s: doctrine differs after normalization" % rel)

    subagent_standard = read_required(ROOT / "standards" / "subagent-delegation.md",
                                      violations)
    subagent_skill = read_required(
        ROOT / "skills" / "general" / "subagent-delegation" / "SKILL.md", violations)
    for label, text in (("standards/subagent-delegation.md", subagent_standard),
                        ("skills/general/subagent-delegation/SKILL.md", subagent_skill)):
        if "PHASE:" not in text:
            violations.append("%s: handoff missing PHASE" % label)
        if "loop position" not in text.lower():
            violations.append("%s: handoff missing loop position" % label)

    for relative in GATE_AUTHORITIES:
        path = ROOT / relative
        if not path.is_file():
            # The legacy-roots fixture has no agents/ at all; a real tree that
            # lost a gate authority must fail rather than pass silently.
            if (ROOT / "agents").is_dir():
                violations.append("missing gate authority: %s" % relative)
            continue
        role_text = read_required(path, violations)
        if not re.search(r"(?i)verdict record|VI-01", role_text):
            violations.append("%s: gate authority does not name the gate verdict "
                              "record (VI-01)" % relative)

    for relative, ok, message in command_findings():
        if not ok:
            violations.append("%s: %s" % (relative, message))

    for relative, ok, message in foreground_findings():
        if not ok:
            violations.append("%s: %s" % (relative, message))

    catalog = read_required(ROOT / "CATALOG.md", violations)
    if "Doctrine: 1.5.0" not in catalog:
        violations.append("CATALOG.md: missing 'Doctrine: 1.5.0' pin")
    if "Library: 2.12.0" not in catalog:
        violations.append("CATALOG.md: missing 'Library: 2.12.0' pin")
    if "Conduct: 1.1.0" not in catalog:
        violations.append("CATALOG.md: missing 'Conduct: 1.1.0' pin")
    if "Tool-set: 1.0.0" not in catalog:
        violations.append("CATALOG.md: missing 'Tool-set: 1.0.0' pin")
    if "Template: 2.0.4" not in catalog:
        violations.append("CATALOG.md: missing 'Template: 2.0.4' pin")
    if "Role templates: 38" not in catalog:
        violations.append("CATALOG.md: missing 'Role templates: 38'")
    if "Task prompts: 3" not in catalog:
        violations.append("CATALOG.md: missing 'Task prompts: 3'")

    if violations:
        for violation in violations:
            print("FAIL " + violation)
        print("workflow-loop: %d violation(s)" % len(violations))
        return 1
    print("workflow-loop: %d carriers, %d phases, %d presets, 0 violations"
          % (len(files), len(PHASES), len(presets)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
