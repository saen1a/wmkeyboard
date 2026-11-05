"""Smoke test for the workflow-loop invariant gate."""

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tooling" / "check_workflow_loop.py"

spec = importlib.util.spec_from_file_location("workflow_loop", CHECK)
loop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loop)


def test_workflow_loop_gate_passes_on_repo():
    result = subprocess.run(
        [sys.executable, str(CHECK)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 violations" in result.stdout


def test_illegal_transition_is_not_allowed():
    assert ("Verify", "Done") not in loop.ALLOWED_TRANSITIONS
    assert ("Verify", "Ready") in loop.ALLOWED_TRANSITIONS


def test_ledger_row_rejects_attempt_over_bound_and_bad_next():
    record = {
        "unit_id": "u",
        "phase": "Verify",
        "attempt": "9",
        "gate": "pass",
        "status": "Done",
        "artifact": "x",
        "findings": "f",
        "evidence": "e",
        "decision": "hold",
        "owner": "o",
        "timestamp": "t",
        "next": "Done",
    }
    errors = loop.validate_ledger_row(record)
    assert any("attempt" in error for error in errors)
    assert any("next" in error for error in errors)


def _copy_tree(tmp_path):
    for name in ("fragments", "standards", "agents", "prompts", "dsh", "omp",
                 "commands", "provenance", "tooling", "skills"):
        shutil.copytree(ROOT / name, tmp_path / name)
    shutil.copy2(ROOT / "CATALOG.md", tmp_path / "CATALOG.md")
    return tmp_path / "tooling" / "check_workflow_loop.py"


def test_cli_rejects_illegal_transition(tmp_path):
    check = _copy_tree(tmp_path)
    standard = tmp_path / "standards" / "workflow-loop.md"
    standard.write_text(standard.read_text() + "\n| Verify | probe | Done |\n")
    result = subprocess.run([sys.executable, str(check)], cwd=str(tmp_path),
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "illegal transition" in result.stdout


def test_cli_rejects_missing_ledger(tmp_path):
    check = _copy_tree(tmp_path)
    (tmp_path / "provenance" / "ledger-workflow-loop-2026-10.md").unlink()
    result = subprocess.run([sys.executable, str(check)], cwd=str(tmp_path),
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "ledger instance missing" in result.stdout


def test_cli_accepts_legacy_roots_with_warning(tmp_path):
    for name in ("fragments", "standards", "dsh", "omp", "commands",
                 "provenance", "tooling", "skills"):
        shutil.copytree(ROOT / name, tmp_path / name)
    shutil.copytree(ROOT / "agents", tmp_path / "roles")
    shutil.copytree(ROOT / "prompts" / "tasks", tmp_path / "tasks")
    shutil.copy2(ROOT / "CATALOG.md", tmp_path / "CATALOG.md")
    check = tmp_path / "tooling" / "check_workflow_loop.py"
    result = subprocess.run([sys.executable, str(check)], cwd=str(tmp_path),
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARN legacy root" in result.stdout


def _run_copy(check, tmp_path):
    return subprocess.run([sys.executable, str(check)], cwd=str(tmp_path),
                          capture_output=True, text=True)


def test_cli_rejects_ghost_legacy_root(tmp_path):
    check = _copy_tree(tmp_path)
    shutil.copytree(tmp_path / "agents", tmp_path / "roles")
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "legacy roles/ exists" in result.stdout


def test_cli_rejects_missing_carrier(tmp_path):
    check = _copy_tree(tmp_path)
    (tmp_path / "prompts" / "tasks" / "audit-report.md").unlink()
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "expected 38 agents + 3 tasks" in result.stdout


def test_cli_rejects_missing_presets(tmp_path):
    check = _copy_tree(tmp_path)
    for path in (tmp_path / "dsh" / "presets").glob("*.template.yml"):
        path.unlink()
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "expected 4 dsh presets" in result.stdout


def test_cli_rejects_foreign_ledger_row(tmp_path):
    check = _copy_tree(tmp_path)
    ledger = tmp_path / "provenance" / "ledger-workflow-loop-2026-10.md"
    ledger.write_text(ledger.read_text() + "\n| unit-x | Verify | 1 | meh | Ready | a | f | e | pass | o | t | Push |\n")
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "gate is not canonical" in result.stdout


def test_cli_rejects_malformed_ledger_row(tmp_path):
    check = _copy_tree(tmp_path)
    ledger = tmp_path / "provenance" / "ledger-workflow-loop-2026-10.md"
    ledger.write_text(ledger.read_text() + "\n| unit-x | Verify | 1 | pass | Ready | a | f | e | pass | o | t |\n")
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "ledger row has 11 cells" in result.stdout


def test_ledger_row_rejects_hold_with_transition():
    record = {
        "unit_id": "u", "phase": "Verify", "attempt": "0", "gate": "hold",
        "status": "Verify", "artifact": "x", "findings": "f",
        "evidence": "e", "decision": "hold", "owner": "o", "timestamp": "t",
        "next": "Push",
    }
    errors = loop.validate_ledger_row(record)
    assert any("hold must keep next equal to status" in error for error in errors)


def test_cli_rejects_workspace_prompts_root(tmp_path):
    check = _copy_tree(tmp_path)
    (tmp_path / "workspace-prompts").mkdir()
    (tmp_path / "workspace-prompts" / "x.txt").write_text("x")
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "legacy workspace-prompts/" in result.stdout


def test_cli_rejects_missing_catalog_pin(tmp_path):
    check = _copy_tree(tmp_path)
    catalog = tmp_path / "CATALOG.md"
    catalog.write_text(catalog.read_text().replace("Doctrine: 1.5.0", "Doctrine: 9.9.9"))
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "Doctrine: 1.5.0" in result.stdout


def test_ledger_requires_gate_decision_match():
    record = {
        "unit_id": "u", "phase": "Verify", "attempt": "0", "gate": "pass",
        "status": "Ready", "artifact": "x", "findings": "f", "evidence": "e",
        "decision": "fix", "owner": "o", "timestamp": "t", "next": "Push",
    }
    errors = loop.validate_ledger_row(record)
    assert any("gate and decision differ" in error for error in errors)


def test_ledger_halt_must_be_terminal():
    record = {
        "unit_id": "u", "phase": "Verify", "attempt": "0", "gate": "halt",
        "status": "Verify", "artifact": "x", "findings": "f", "evidence": "e",
        "decision": "halt", "owner": "o", "timestamp": "t", "next": "Push",
    }
    errors = loop.validate_ledger_row(record)
    assert any("halt gate must be terminal" in error for error in errors)


def test_ledger_ready_unverified_requires_hold():
    record = {
        "unit_id": "u", "phase": "Verify", "attempt": "0", "gate": "pass",
        "status": "Ready (unverified)", "artifact": "x", "findings": "f",
        "evidence": "e", "decision": "pass", "owner": "o", "timestamp": "t",
        "next": "Push",
    }
    errors = loop.validate_ledger_row(record)
    assert any("Ready (unverified) requires gate=decision=hold" in error
               for error in errors)


def test_cli_rejects_missing_exemption_rows(tmp_path):
    check = _copy_tree(tmp_path)
    standard = tmp_path / "standards" / "workflow-loop.md"
    text = standard.read_text()
    for row in ("| Verify | A recorded exemption covers the missing check; claim marked unverified | Ready (unverified) |",
                "| Ready (unverified) | Explicit operator `go` | Push |",
                "| Ready (unverified) | Explicit operator decline | HALT |"):
        text = text.replace(row + "\n", "")
    standard.write_text(text)
    result = subprocess.run([sys.executable, str(check)], cwd=str(tmp_path),
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "Ready (unverified)" in result.stdout


def test_cli_rejects_duplicate_carrier_id(tmp_path):
    check = _copy_tree(tmp_path)
    source = tmp_path / "agents" / "research" / "res-librarian.md"
    target = tmp_path / "agents" / "research" / "res-researcher.md"
    target.write_text(source.read_text())
    result = subprocess.run([sys.executable, str(check)], cwd=str(tmp_path),
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "duplicate carrier ids" in result.stdout


def test_cli_rejects_terminal_row_with_forward_next(tmp_path):
    check = _copy_tree(tmp_path)
    standard = tmp_path / "standards" / "workflow-loop.md"
    standard.write_text(standard.read_text() + "\n| Done | probe | Plan |\n")
    result = subprocess.run([sys.executable, str(check)], cwd=str(tmp_path),
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "illegal transition" in result.stdout


def test_cli_rejects_quoted_read_only_push(tmp_path):
    check = _copy_tree(tmp_path)
    path = tmp_path / "agents" / "operations" / "ops-ci-implementer.md"
    text = path.read_text().replace("tool_profile: gated-write",
                                    'tool_profile: "read-only"')
    path.write_text(text)
    result = subprocess.run([sys.executable, str(check)], cwd=str(tmp_path),
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "read-only role owns Push" in result.stdout


def test_cli_rejects_workflow_phase_drift(tmp_path):
    check = _copy_tree(tmp_path)
    path = tmp_path / "agents" / "engineering" / "eng-explorer.md"
    text = path.read_text().replace("Phase map (explorer), prose: Plan --",
                                    "Phase map (explorer), prose: Plan -- x. Implement -- write the patch. Plan --")
    path.write_text(text)
    result = subprocess.run([sys.executable, str(check)], cwd=str(tmp_path),
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "workflow performs Implement" in result.stdout


def test_ledger_accepts_ready_unverified_hold():
    record = {
        "unit_id": "u", "phase": "Verify", "attempt": "1", "gate": "hold",
        "status": "Ready (unverified)", "artifact": "x", "findings": "none (exemption: no browser)",
        "evidence": "e", "decision": "hold", "owner": "o", "timestamp": "t",
        "next": "Push",
    }
    assert loop.validate_ledger_row(record) == []


def test_ledger_accepts_report_ready_none():
    record = {
        "unit_id": "u", "phase": "Verify", "attempt": "1", "gate": "pass",
        "status": "Ready", "artifact": "x", "findings": "none (handed to parent)",
        "evidence": "e", "decision": "pass", "owner": "o", "timestamp": "t",
        "next": "none",
    }
    assert loop.validate_ledger_row(record) == []


def test_ledger_done_rejects_open_medium_finding():
    record = {
        "unit_id": "u", "phase": "Push", "attempt": "1", "gate": "pass",
        "status": "Done", "artifact": "x", "findings": "F9 medium open",
        "evidence": "e", "decision": "pass", "owner": "o", "timestamp": "t",
        "next": "none",
    }
    errors = loop.validate_ledger_row(record)
    assert any("open high/medium finding" in error for error in errors)


def test_cli_rejects_push_label_in_review_surface(tmp_path):
    check = _copy_tree(tmp_path)
    path = tmp_path / "agents" / "engineering" / "eng-oracle.md"
    body = path.read_text()
    phase = re.search(r"Phase map \(oracle\), prose: [^\n]*", body).group(0)
    text = body.replace(phase, phase + " Push -- commit and push to main.")
    path.write_text(text)
    result = subprocess.run([sys.executable, str(check)], cwd=str(tmp_path),
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "workflow performs Push" in result.stdout


def test_cli_rejects_block_scalar_read_only_push(tmp_path):
    check = _copy_tree(tmp_path)
    path = tmp_path / "agents" / "operations" / "ops-ci-implementer.md"
    text = path.read_text().replace("tool_profile: gated-write",
                                    "tool_profile: >-\n  read-only")
    path.write_text(text)
    result = subprocess.run([sys.executable, str(check)], cwd=str(tmp_path),
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "read-only role owns Push" in result.stdout


def test_cli_rejects_duplicate_catalog_row(tmp_path):
    check = _copy_tree(tmp_path)
    catalog = tmp_path / "CATALOG.md"
    text = catalog.read_text()
    row = next(line for line in text.splitlines()
               if line.startswith("| `design-ui-reviewer` |"))
    catalog.write_text(text.replace(row, row + "\n" + row, 1))
    result = subprocess.run([sys.executable, str(check)], cwd=str(tmp_path),
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "CATALOG duplicate ids" in result.stdout


def test_ledger_done_rejects_abbreviated_open_finding():
    record = {
        "unit_id": "u", "phase": "Push", "attempt": "1", "gate": "pass",
        "status": "Done", "artifact": "x", "findings": "H: none; M: 2 open",
        "evidence": "e", "decision": "pass", "owner": "o", "timestamp": "t",
        "next": "none",
    }
    errors = loop.validate_ledger_row(record)
    assert any("open high/medium finding" in error for error in errors)


def test_named_findings_ledger_with_no_rows_fails(tmp_path):
    check = _copy_tree(tmp_path)
    ledger = tmp_path / "provenance" / "findings-external-scan-2026-10.md"
    lines = [line for line in ledger.read_text(encoding="utf-8").splitlines()
             if line.startswith("#") or line.startswith("| finding_id |")
             or line.startswith("|---")]
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "ledger has no finding row" in result.stdout


def test_gate_authority_must_name_the_record_not_just_the_word(tmp_path):
    check = _copy_tree(tmp_path)
    role = tmp_path / "agents" / "review" / "rev-reviewer.md"
    role.write_text(re.sub(r"(?i)verdict record|VI-01", "verdict", role.read_text()),
                    encoding="utf-8")
    result = subprocess.run([sys.executable, str(check)], cwd=str(tmp_path),
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "gate verdict record" in result.stdout


def test_plan_to_implement_is_not_a_legal_transition():
    assert ("Plan", "Implement") not in loop.ALLOWED_TRANSITIONS
    assert ("Plan", "PlanReview") in loop.ALLOWED_TRANSITIONS
    assert ("PlanReview", "Implement") in loop.ALLOWED_TRANSITIONS
    assert ("Fix", "PlanReview") in loop.ALLOWED_TRANSITIONS


def test_ledger_rejects_plan_skipping_the_plan_review():
    record = {
        "unit_id": "u", "phase": "Plan", "attempt": "0", "gate": "pass",
        "status": "Plan", "artifact": "x", "findings": "none", "evidence": "e",
        "decision": "pass", "owner": "o", "timestamp": "t", "next": "Implement",
    }
    errors = loop.validate_ledger_row(record)
    assert any("next is not legal from Plan" in error for error in errors)


def test_ledger_accepts_the_plan_review_frontier():
    record = {
        "unit_id": "u", "phase": "Plan", "attempt": "0", "gate": "pass",
        "status": "Plan", "artifact": "spec.md", "findings": "none",
        "evidence": "e", "decision": "pass", "owner": "o", "timestamp": "t",
        "next": "PlanReview",
    }
    assert loop.validate_ledger_row(record) == []


def test_ledger_accepts_a_plan_review_round_and_its_repair():
    record = {
        "unit_id": "u", "phase": "PlanReview", "attempt": "3", "gate": "pass",
        "status": "PlanReview", "artifact": "spec.md", "findings": "none",
        "evidence": "e", "decision": "pass", "owner": "o", "timestamp": "t",
        "next": "Implement",
    }
    assert loop.validate_ledger_row(record) == []
    repair = dict(record, gate="fix", decision="fix", next="Fix",
                  findings="none (repair round 4, see the ledger history)")
    assert loop.validate_ledger_row(repair) == []


def test_ledger_rejects_plan_review_jump_to_verify():
    record = {
        "unit_id": "u", "phase": "PlanReview", "attempt": "2", "gate": "pass",
        "status": "PlanReview", "artifact": "x", "findings": "none",
        "evidence": "e", "decision": "pass", "owner": "o", "timestamp": "t",
        "next": "Verify",
    }
    errors = loop.validate_ledger_row(record)
    assert any("next is not legal from PlanReview" in error for error in errors)


def test_cli_rejects_missing_plan_review_transition(tmp_path):
    check = _copy_tree(tmp_path)
    standard = tmp_path / "standards" / "workflow-loop.md"
    text = standard.read_text().replace(
        "| Plan | Decision-complete spec: goal, units, acceptance, verification, "
        "research sources/dates | PlanReview |\n", "")
    standard.write_text(text)
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "missing transition Plan -> PlanReview" in result.stdout


def test_cli_rejects_plan_review_authority_without_the_gate(tmp_path):
    check = _copy_tree(tmp_path)
    path = tmp_path / "agents" / "review" / "rev-review-lead.md"
    path.write_text(path.read_text().replace(
        "owned_phases: [PlanReview, Review]", "owned_phases: [Review]"))
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "does not own PlanReview" in result.stdout


def test_mutations_render_a_workflow_clause_per_carrier():
    for path in sorted(list((ROOT / "agents").rglob("*.md"))
                       + list((ROOT / "prompts" / "tasks").glob("*.md"))):
        text = path.read_text()
        if "<workflow>" in text:
            block = re.search(r"(?ms)^<workflow>.*?</workflow>", text).group(0)
            assert "PlanReview" in block, path


def test_a_command_without_a_doctrine_line_fails(tmp_path):
    check = _copy_tree(tmp_path)
    path = tmp_path / "commands" / "review.md"
    path.write_text("Use: /review <scope>\n")
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "missing a single 'Doctrine:' line" in result.stdout


def test_a_doctrine_line_naming_no_phase_fails(tmp_path):
    check = _copy_tree(tmp_path)
    path = tmp_path / "commands" / "review.md"
    text = path.read_text().replace(
        "this command serves the Review phase only; findings feed a separate Fix "
        "handoff, and Push stays with the operator.",
        "this command serves the project as configured and reports to the caller.")
    path.write_text(text)
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "names no owned phase" in result.stdout


def test_a_missing_exempt_command_fails(tmp_path):
    check = _copy_tree(tmp_path)
    (tmp_path / "commands" / "caveman.md").unlink()
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "the set is self-pruning" in result.stdout


def test_an_exempt_command_that_becomes_a_dispatcher_fails(tmp_path):
    check = _copy_tree(tmp_path)
    path = tmp_path / "commands" / "caveman.md"
    text = path.read_text().replace("toggles reply style only",
                                    "serves the Push phase only")
    path.write_text(text)
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "became a dispatcher" in result.stdout


def test_foreground_policy_must_name_the_plan_review_gate(tmp_path):
    check = _copy_tree(tmp_path)
    path = tmp_path / "omp" / "prompts" / "foreground" / "30-governance.md"
    text = path.read_text()
    path.write_text("\n".join(line for line in text.splitlines()
                              if "PlanReview" not in line
                              and "plan-review" not in line) + "\n")
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "never names the plan-review gate" in result.stdout


def test_foreground_policy_must_state_the_gate_once(tmp_path):
    check = _copy_tree(tmp_path)
    path = tmp_path / "omp" / "prompts" / "foreground" / "20-evidence.md"
    path.write_text(path.read_text() +
                    "\nThe loop is `Plan -> PlanReview -> Implement`, and no plan\n"
                    "reaches Implement without a plan-review verdict.\n")
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "state it once" in result.stdout


def test_a_bare_mention_does_not_satisfy_the_gate_statement(tmp_path):
    check = _copy_tree(tmp_path)
    path = tmp_path / "omp" / "prompts" / "foreground" / "30-governance.md"
    text = path.read_text()
    path.write_text("\n".join(line for line in text.splitlines()
                              if "Plan -> PlanReview -> Implement" not in line
                              and "plan-review verdict" not in line)
                    + "\nA plan review is optional here.\n")
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "never names the plan-review gate" in result.stdout


def test_a_manifest_module_escaping_the_directory_fails(tmp_path):
    check = _copy_tree(tmp_path)
    manifest = tmp_path / "omp" / "prompts" / "foreground" / "manifest.json"
    data = json.loads(manifest.read_text())
    data["order"][0] = "../../README.md"
    manifest.write_text(json.dumps(data, indent=2) + "\n")
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "is not a plain .md file of this set" in result.stdout


def test_two_doctrine_lines_fail(tmp_path):
    check = _copy_tree(tmp_path)
    path = tmp_path / "commands" / "review.md"
    path.write_text(path.read_text() + "Doctrine: also implements everything itself.\n")
    result = _run_copy(check, tmp_path)
    assert result.returncode == 1
    assert "carries 2 'Doctrine:' lines" in result.stdout
