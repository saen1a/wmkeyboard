"""Tests for the long-horizon run-state validator."""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tooling" / "run_state.py"
EXEMPLAR = ROOT / "exemplars" / "run-state-example.md"

spec = importlib.util.spec_from_file_location("run_state", TOOL)
run_state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_state)


def _write(tmp_path, text):
    path = tmp_path / "run.md"
    path.write_text(text, encoding="utf-8")
    return path


def _exemplar():
    return EXEMPLAR.read_text(encoding="utf-8")


def _run_gate():
    return ("run_gate:\n"
            "  command: make test\n"
            "  exit: 0\n"
            "  at: 2026-10-25T02:00:00Z\n"
            "  evidence: make test exit 0\n")


def _finalize(text):
    text = text.replace(
        "- F1 (medium, owner U3): the recovery procedure still references the old screen name.\n- No unresolved high finding.",
        "- No unresolved high or medium finding.")
    text = text.replace(
        "| 4 | 2026-10-25T02:00:00Z | U3 | Implement | pass | cadence | 2/3; recovery draft written | docs/handbook/procedures/recovery.md | Run Review on unit U3 |",
        "| 4 | 2026-10-25T02:00:00Z | U3 | Verify | pass | progress | 3/3; recovery verified | docs/handbook/procedures/recovery.md | Review |")
    text = text.replace("last_progress_at: 2026-10-24T23:45:00Z",
                        "last_progress_at: 2026-10-25T02:00:00Z")
    text = text.replace("acceptance:\n", _run_gate() + "acceptance:\n", 1)
    return text


def _close_units(text):
    text = text.replace(
        "| 4 | 2026-10-25T02:00:00Z | U3 | Implement | pass | cadence | 2/3; recovery draft written | docs/handbook/procedures/recovery.md | Run Review on unit U3 |",
        "| 4 | 2026-10-25T02:00:00Z | U3 | Verify | pass | progress | 3/3; recovery verified | docs/handbook/procedures/recovery.md | Review |")
    return text.replace("last_progress_at: 2026-10-24T23:45:00Z",
                        "last_progress_at: 2026-10-25T02:00:00Z")


def _run(path, *extra):
    return subprocess.run([sys.executable, str(TOOL), "check", str(path), *extra],
                          cwd=str(ROOT), capture_output=True, text=True)


def _approval(ids="[A3]"):
    return ("push_approval:\n"
            "  operator: library-maintainer\n"
            "  at: 2026-10-25T02:00:00Z\n"
            "  ids: %s\n"
            "  scope: approved at the Push gate\n" % ids)


def test_exemplar_is_valid():
    result = run_state.check(EXEMPLAR)
    assert result["ok"], result["errors"]
    assert result["units"] == 3
    assert result["checkpoints"] == 4


def test_cli_check_and_status_and_next(tmp_path):
    result = _run(EXEMPLAR)
    assert result.returncode == 0, result.stdout
    assert "run-state: OK" in result.stdout
    status = subprocess.run([sys.executable, str(TOOL), "status", str(EXEMPLAR)],
                             cwd=str(ROOT), capture_output=True, text=True)
    assert status.returncode == 0
    assert "units 2/3" in status.stdout
    assert status.stdout.strip().startswith("RUN docs-migration-example | active")
    nxt = subprocess.run([sys.executable, str(TOOL), "next", str(EXEMPLAR)],
                          cwd=str(ROOT), capture_output=True, text=True)
    assert nxt.returncode == 0
    assert nxt.stdout.strip().startswith("Run Review")


def test_next_without_frontmatter_fails_cleanly(tmp_path):
    path = _write(tmp_path, "## Units\n")
    result = subprocess.run([sys.executable, str(TOOL), "next", str(path)],
                            cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 1
    assert "FAIL" in result.stdout
    assert "Traceback" not in result.stderr


def test_missing_frontmatter_fails(tmp_path):
    path = _write(tmp_path, "## Units\n")
    result = run_state.check(path)
    assert not result["ok"]
    assert "missing YAML frontmatter" in result["errors"]


def test_schema_version_must_match(tmp_path):
    path = _write(tmp_path, _exemplar().replace("schema_version: 1.2.0",
                                                "schema_version: 0.9.0", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("schema_version" in error for error in result["errors"])


def test_units_done_counter_must_match_table(tmp_path):
    path = _write(tmp_path, _exemplar().replace("units_done: 2", "units_done: 1", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("units_done" in error for error in result["errors"])


def test_budget_over_limit_fails(tmp_path):
    path = _write(tmp_path, _exemplar().replace("used: 120000", "used: 500000", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("exceeds limit" in error for error in result["errors"])


def test_budget_units_must_match_progress(tmp_path):
    path = _write(tmp_path, _exemplar().replace(
        "  units:\n    limit: 3\n    used: 2", "  units:\n    limit: 3\n    used: 1", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("budget.units.used" in error for error in result["errors"])


def test_active_cannot_claim_done_phase(tmp_path):
    path = _write(tmp_path, _exemplar().replace("phase: Implement", "phase: Done", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("not legal for status" in error for error in result["errors"])


def test_halted_requires_reason(tmp_path):
    text = (_exemplar()
            .replace("status: active", "status: halted", 1)
            .replace("phase: Implement", "phase: HALT", 1))
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("halted reason is not canonical" in error for error in result["errors"])


def test_done_with_pending_acceptance_fails(tmp_path):
    text = (_exemplar()
            .replace("status: active", "status: done", 1)
            .replace("phase: Implement", "phase: Done", 1)
            .replace("units_done: 2", "units_done: 3", 1)
            .replace("| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |",
                     "| U3 | Push | pass | Done | docs/handbook/procedures/recovery.md | check exit 0 | delivery | none |"))
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("unresolved acceptance" in error for error in result["errors"])


def test_done_with_unverified_acceptance_requires_approval(tmp_path):
    text = (_exemplar()
            .replace("status: active", "status: done", 1)
            .replace("phase: Implement", "phase: Done", 1)
            .replace("units_done: 2", "units_done: 3", 1)
            .replace("| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |",
                     "| U3 | Push | pass | Done | docs/handbook/procedures/recovery.md | check exit 0 | delivery | none |")
            .replace('  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: pending\n    evidence: ""',
                     '  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: unverified\n    evidence: "exemption: no browser automation in this harness"'))
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("requires push_approval" in error for error in result["errors"])


def test_done_with_unverified_acceptance_and_approval_passes(tmp_path):
    text = (_exemplar()
            .replace("status: active", "status: done", 1)
            .replace("phase: Implement", "phase: Done", 1)
            .replace("units_done: 2", "units_done: 3", 1)
            .replace("| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |",
                     "| U3 | Push | pass | Done | docs/handbook/procedures/recovery.md | check exit 0 | delivery | none |")
            .replace('  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: pending\n    evidence: ""',
                     '  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: unverified\n    evidence: "exemption: no browser automation in this harness"')
            .replace("    used: 2", "    used: 3", 1)
            .replace("next_action: Run Review on unit U3 with the diff and the link checker output.",
                     _approval() + "next_action: none.")
            .replace("RUN docs-migration-example | active | units 2/3 | checkpoint 4 | tokens 120000/400000 | next Run Review on unit U3 with the diff and the link checker output.",
                     "RUN docs-migration-example | done | units 3/3 | checkpoint 4 | tokens 120000/400000 | next none."))
    text = _finalize(text)
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert result["ok"], result["errors"]


def test_report_only_unit_can_close_a_done_run(tmp_path):
    text = (_exemplar()
            .replace("status: active", "status: done", 1)
            .replace("phase: Implement", "phase: Done", 1)
            .replace("units_done: 2", "units_done: 3", 1)
            .replace("| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |",
                     "| U3 | Verify | pass | Ready | docs/handbook/procedures/recovery.md | report handed to parent | report | none |")
            .replace('  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: pending\n    evidence: ""',
                     '  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: verified\n    evidence: "manual walkthrough, 2026-10-24"')
            .replace("    used: 2", "    used: 3", 1)
            .replace("next_action: Run Review on unit U3 with the diff and the link checker output.",
                     _approval("[]") + 'next_action: ""')
            .replace("RUN docs-migration-example | active | units 2/3 | checkpoint 4 | tokens 120000/400000 | next Run Review on unit U3 with the diff and the link checker output.",
                     "RUN docs-migration-example | done | units 3/3 | checkpoint 4 | tokens 120000/400000 | next none."))
    text = _finalize(text)
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert result["ok"], result["errors"]


def test_waiting_cannot_hide_pending_acceptance(tmp_path):
    text = (_exemplar()
            .replace("status: active", "status: waiting", 1)
            .replace("phase: Implement", "phase: Ready", 1))
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("unresolved acceptance" in error for error in result["errors"])


def test_duplicate_unit_id_fails(tmp_path):
    path = _write(tmp_path, _exemplar().replace(
        "| U3 | Implement | pass | Implement |",
        "| U1 | Implement | pass | Implement |", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("duplicate unit_id" in error for error in result["errors"])


def test_checkpoint_counter_must_match_table(tmp_path):
    path = _write(tmp_path, _exemplar().replace("checkpoint: 4", "checkpoint: 5", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("checkpoint counter" in error for error in result["errors"])


def test_progress_stall_is_detected(tmp_path):
    text = _exemplar()
    lines = text.splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith("| n |"))
    replacement = [
        "| 2 | 2026-10-24T22:15:00Z | U1 | Implement | pass | progress | 2/3 | same.md | Review U3 |",
        "| 3 | 2026-10-24T23:45:00Z | U2 | Implement | pass | progress | 2/3 | same.md | Review U3 |",
        "| 4 | 2026-10-25T02:00:00Z | U3 | Implement | pass | progress | 2/3 | same.md | Review U3 |",
    ]
    lines[start + 3:start + 6] = replacement
    path = _write(tmp_path, "\n".join(lines) + "\n")
    result = run_state.check(path)
    assert not result["ok"]
    assert any("stalled" in error for error in result["errors"])


def test_cadence_checkpoints_do_not_trip_stall(tmp_path):
    text = _exemplar()
    lines = text.splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith("| n |"))
    replacement = [
        "| 2 | 2026-10-24T22:15:00Z | U1 | Implement | pass | cadence | 1/3 | same.md | Review U3 |",
        "| 3 | 2026-10-24T23:45:00Z | U2 | Implement | pass | cadence | 2/3 | same.md | Review U3 |",
        "| 4 | 2026-10-25T02:00:00Z | U3 | Implement | pass | cadence | 2/3 | same.md | Review U3 |",
    ]
    lines[start + 3:start + 6] = replacement
    text = "\n".join(lines).replace("last_progress_at: 2026-10-24T23:45:00Z",
                                    "last_progress_at: 2026-10-24T21:00:00Z")
    text = text.replace("progress_max_minutes: 180", "progress_max_minutes: 600")
    path = _write(tmp_path, text + "\n")
    result = run_state.check(path)
    assert result["ok"], result["errors"]


def test_stall_window_must_be_at_least_two(tmp_path):
    path = _write(tmp_path, _exemplar().replace("stall_window: 3", "stall_window: 1", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("stall_window" in error for error in result["errors"])


def test_checkpoints_must_be_monotonic(tmp_path):
    path = _write(tmp_path, _exemplar().replace(
        "| 4 | 2026-10-25T02:00:00Z |", "| 4 | 2026-10-24T20:00:00Z |", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("before the previous" in error for error in result["errors"])


def test_bad_checkpoint_kind_fails(tmp_path):
    path = _write(tmp_path, _exemplar().replace(
        "| 4 | 2026-10-25T02:00:00Z | U3 | Implement | pass | cadence |",
        "| 4 | 2026-10-25T02:00:00Z | U3 | Implement | pass | sometimes |", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("kind is not canonical" in error for error in result["errors"])


def test_bad_units_columns_fail(tmp_path):
    path = _write(tmp_path, _exemplar().replace(
        "| unit_id | phase | gate | status | artifact | evidence | kind | next |",
        "| unit_id | phase | gate | status | artifact | next |", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("Units columns" in error for error in result["errors"])


def test_stale_state_fails_only_when_asked(tmp_path):
    path = _write(tmp_path, _exemplar())
    assert run_state.check(path)["ok"]
    result = run_state.check(path, max_age_hours=0)
    assert not result["ok"]
    assert any("stale" in error for error in result["errors"])


def test_checkpoint_unknown_unit_fails(tmp_path):
    path = _write(tmp_path, _exemplar().replace(
        "| 4 | 2026-10-25T02:00:00Z | U3 |", "| 4 | 2026-10-25T02:00:00Z | U9 |", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("unknown unit" in error for error in result["errors"])


def test_bad_in_flight_state_fails(tmp_path):
    path = _write(tmp_path, _exemplar().replace(
        "| Write the recovery page | recovery-page | done |",
        "| Write the recovery page | recovery-page | maybe |", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("In-flight" in error for error in result["errors"])


def test_unknown_frontmatter_key_fails(tmp_path):
    path = _write(tmp_path, _exemplar().replace("acceptance:\n",
                                                "budgett: {}\nacceptance:\n", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("unknown frontmatter key" in error for error in result["errors"])


def test_checkpoint_base_supports_archiving(tmp_path):
    text = (_exemplar()
            .replace("checkpoint: 4", "checkpoint: 6\ncheckpoint_base: 2\ncheckpoint_archive: archive.md", 1)
            .replace("| 1 | 2026-10-24T21:00:00Z |", "| 3 | 2026-10-24T21:00:00Z |", 1)
            .replace("| 2 | 2026-10-24T22:15:00Z |", "| 4 | 2026-10-24T22:15:00Z |", 1)
            .replace("| 3 | 2026-10-24T23:45:00Z |", "| 5 | 2026-10-24T23:45:00Z |", 1)
            .replace("| 4 | 2026-10-25T02:00:00Z |", "| 6 | 2026-10-25T02:00:00Z |", 1)
            .replace("checkpoint 4 | tokens", "checkpoint 6 | tokens", 1))
    (tmp_path / "archive.md").write_text("## Checkpoints\n\n| n | at |\n|---|---|\n| 1 | 2026-10-24T21:00:00Z |\n")
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert result["ok"], result["errors"]


def test_blocked_requires_reason(tmp_path):
    path = _write(tmp_path, _exemplar().replace("status: active", "status: blocked", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("status blocked requires a non-empty dependency reason" in error
               for error in result["errors"])


def test_changed_files_must_be_paths(tmp_path):
    path = _write(tmp_path, _exemplar().replace(
        "acceptance:\n", "changed_files:\n  - docs/handbook/index.md\n  - 3\nacceptance:\n", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("changed_files" in error for error in result["errors"])


def test_lease_field_is_accepted(tmp_path):
    lease = ("lease:\n"
             "  resource: docs/handbook\n"
             "  owner: orchestration-orchestrator\n"
             "  expires: 2026-10-25T03:00:00Z\n")
    path = _write(tmp_path, _exemplar().replace("acceptance:\n", lease + "acceptance:\n", 1))
    result = run_state.check(path)
    assert result["ok"], result["errors"]


def test_done_requires_approval_even_when_verified(tmp_path):
    text = (_exemplar()
            .replace("status: active", "status: done", 1)
            .replace("phase: Implement", "phase: Done", 1)
            .replace("units_done: 2", "units_done: 3", 1)
            .replace("| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |",
                     "| U3 | Push | pass | Done | docs/handbook/procedures/recovery.md | check exit 0 | delivery | none |")
            .replace('  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: pending\n    evidence: ""',
                     '  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: verified\n    evidence: "manual walkthrough"')
            .replace("    used: 2", "    used: 3", 1)
            .replace("next_action: Run Review on unit U3 with the diff and the link checker output.",
                     "next_action: none."))
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("status done requires push_approval" in error for error in result["errors"])


def test_approval_ids_must_cover_unverified_rows(tmp_path):
    text = (_exemplar()
            .replace("status: active", "status: done", 1)
            .replace("phase: Implement", "phase: Done", 1)
            .replace("units_done: 2", "units_done: 3", 1)
            .replace("| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |",
                     "| U3 | Push | pass | Done | docs/handbook/procedures/recovery.md | check exit 0 | delivery | none |")
            .replace('  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: pending\n    evidence: ""',
                     '  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: unverified\n    evidence: "exemption: no browser"')
            .replace("    used: 2", "    used: 3", 1)
            .replace("next_action: Run Review on unit U3 with the diff and the link checker output.",
                     _approval("[A1]") + "next_action: none."))
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("does not cover unverified" in error for error in result["errors"])


def test_delivery_unit_cannot_close_at_ready(tmp_path):
    text = (_exemplar()
            .replace("status: active", "status: done", 1)
            .replace("phase: Implement", "phase: Done", 1)
            .replace("units_done: 2", "units_done: 3", 1)
            .replace("| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |",
                     "| U3 | Ready | pass | Ready | docs/handbook/procedures/recovery.md | handed off | delivery | none |")
            .replace('  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: pending\n    evidence: ""',
                     '  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: verified\n    evidence: "manual walkthrough"')
            .replace("    used: 2", "    used: 3", 1)
            .replace("next_action: Run Review on unit U3 with the diff and the link checker output.",
                     "next_action: none."))
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("units_done" in error or "every unit closed" in error
               for error in result["errors"])


def test_same_artifact_with_increasing_count_is_progress(tmp_path):
    text = _exemplar()
    lines = text.splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith("| n |"))
    replacement = [
        "| 2 | 2026-10-24T22:15:00Z | U1 | Implement | pass | progress | 1/3 | same.md | Review U3 |",
        "| 3 | 2026-10-24T23:45:00Z | U2 | Implement | pass | progress | 2/3 | same.md | Review U3 |",
        "| 4 | 2026-10-25T02:00:00Z | U3 | Implement | pass | progress | 2/3 | same.md | Review U3 |",
    ]
    lines[start + 3:start + 6] = replacement
    text = "\n".join(lines).replace("last_progress_at: 2026-10-24T23:45:00Z",
                                    "last_progress_at: 2026-10-24T23:45:00Z")
    path = _write(tmp_path, text + "\n")
    result = run_state.check(path)
    assert result["ok"], result["errors"]


def test_stale_progress_age_is_stalled(tmp_path):
    path = _write(tmp_path, _exemplar().replace(
        "updated: 2026-10-25T02:00:00Z", "updated: 2026-10-25T05:00:00Z", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("no progress for" in error for error in result["errors"])


def test_stale_operator_line_fails(tmp_path):
    path = _write(tmp_path, _exemplar().replace(
        "RUN docs-migration-example | active | units 2/3",
        "RUN docs-migration-example | active | units 3/3", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("Operator status line is stale" in error for error in result["errors"])


def test_halted_reason_must_be_canonical(tmp_path):
    text = (_exemplar()
            .replace("status: active", "status: halted", 1)
            .replace("phase: Implement", "phase: HALT", 1))
    text = text.replace("next_action:", "reason: because I said so\nnext_action:", 1)
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("halted reason is not canonical" in error for error in result["errors"])


def test_unit_budget_may_exceed_the_plan(tmp_path):
    path = _write(tmp_path, _exemplar().replace(
        "  units:\n    limit: 3\n    used: 2", "  units:\n    limit: 5\n    used: 2", 1))
    result = run_state.check(path)
    assert result["ok"], result["errors"]


def test_blocked_with_dependency_passes(tmp_path):
    text = _exemplar().replace("status: active", "status: blocked", 1)
    text = text.replace("next_action:", "reason: vendor API outage\nnext_action:", 1)
    text = text.replace("RUN docs-migration-example | active |", "RUN docs-migration-example | blocked |", 1)
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert result["ok"], result["errors"]


def test_blocked_cannot_be_at_push(tmp_path):
    text = (_exemplar()
            .replace("status: active", "status: blocked", 1)
            .replace("phase: Implement", "phase: Push", 1))
    text = text.replace("next_action:", "reason: vendor API outage\nnext_action:", 1)
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("not legal for status" in error for error in result["errors"])


def test_waiting_with_unverified_and_all_units_closed_passes(tmp_path):
    text = (_exemplar()
            .replace("status: active", "status: waiting", 1)
            .replace("phase: Implement", "phase: Ready", 1)
            .replace("units_done: 2", "units_done: 3", 1)
            .replace("| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |",
                     "| U3 | Push | pass | Done | docs/handbook/procedures/recovery.md | check exit 0 | delivery | none |")
            .replace('  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: pending\n    evidence: ""',
                     '  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: unverified\n    evidence: "exemption: no browser"')
            .replace("    used: 2", "    used: 3", 1)
            .replace("RUN docs-migration-example | active | units 2/3",
                     "RUN docs-migration-example | waiting | units 3/3", 1))
    text = _close_units(text)
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert result["ok"], result["errors"]


def test_lease_missing_key_fails(tmp_path):
    lease = ("lease:\n"
             "  resource: docs/handbook\n"
             "  owner: orchestration-orchestrator\n")
    path = _write(tmp_path, _exemplar().replace("acceptance:\n", lease + "acceptance:\n", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("lease missing expires" in error for error in result["errors"])


def test_progress_max_minutes_is_required(tmp_path):
    text = _exemplar().replace("progress_max_minutes: 180\n", "")
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("progress_max_minutes" in error for error in result["errors"])


def test_checkpoint_base_requires_archive_path(tmp_path):
    text = (_exemplar()
            .replace("checkpoint: 4", "checkpoint: 4\ncheckpoint_base: 2", 1))
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("checkpoint_archive" in error for error in result["errors"])


def test_delivery_ready_none_is_rejected_in_active_run(tmp_path):
    text = (_exemplar().replace(
        "| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |",
        "| U3 | Ready | pass | Ready | docs/handbook/procedures/recovery.md | handed off | delivery | none |"))
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("delivery but closes" in error for error in result["errors"])


def test_max_age_only_applies_to_active_runs(tmp_path):
    text = (_exemplar()
            .replace("status: active", "status: waiting", 1)
            .replace("phase: Implement", "phase: Ready", 1)
            .replace("units_done: 2", "units_done: 3", 1)
            .replace("| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |",
                     "| U3 | Push | pass | Done | docs/handbook/procedures/recovery.md | check exit 0 | delivery | none |")
            .replace('  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: pending\n    evidence: ""',
                     '  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: unverified\n    evidence: "exemption: no browser"')
            .replace("    used: 2", "    used: 3", 1)
            .replace("RUN docs-migration-example | active | units 2/3",
                     "RUN docs-migration-example | waiting | units 3/3", 1))
    text = _close_units(text)
    path = _write(tmp_path, text)
    result = run_state.check(path, max_age_hours=0)
    assert result["ok"], result["errors"]


def test_terminal_empty_next_action_renders_as_none(tmp_path):
    text = (_exemplar()
            .replace("status: active", "status: done", 1)
            .replace("phase: Implement", "phase: Done", 1)
            .replace("units_done: 2", "units_done: 3", 1)
            .replace("| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |",
                     "| U3 | Push | pass | Done | docs/handbook/procedures/recovery.md | check exit 0 | delivery | none |")
            .replace('  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: pending\n    evidence: ""',
                     '  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: verified\n    evidence: "manual walkthrough"')
            .replace("    used: 2", "    used: 3", 1)
            .replace("next_action: Run Review on unit U3 with the diff and the link checker output.",
                     _approval("[]") + 'next_action: ""')
            .replace("RUN docs-migration-example | active | units 2/3 | checkpoint 4 | tokens 120000/400000 | next Run Review on unit U3 with the diff and the link checker output.",
                     "RUN docs-migration-example | done | units 3/3 | checkpoint 4 | tokens 120000/400000 | next none"))
    text = _finalize(text)
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert result["ok"], result["errors"]


def test_zero_units_is_rejected(tmp_path):
    text = (_exemplar()
            .replace("units_total: 3", "units_total: 0")
            .replace("units_done: 2", "units_done: 0")
            .replace("  units:\n    limit: 3\n    used: 2",
                     "  units:\n    limit: 1\n    used: 0"))
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("units_total must be at least 1" in error for error in result["errors"])


def test_future_updated_defeats_max_age(tmp_path):
    path = _write(tmp_path, _exemplar().replace(
        "updated: 2026-10-25T02:00:00Z", "updated: 2099-01-01T00:00:00Z", 1))
    result = run_state.check(path, max_age_hours=1)
    assert not result["ok"]
    assert any("future" in error.lower() or "updated is after" in error
               for error in result["errors"])


def test_duplicate_yaml_key_is_rejected(tmp_path):
    path = _write(tmp_path, _exemplar().replace(
        "status: active", "status: active\nstatus: done", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("duplicate key" in error for error in result["errors"])


def test_duplicate_section_is_rejected(tmp_path):
    text = _exemplar() + "\n## Units\n\n| unit_id |\n|---|\n| U9 |\n"
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("duplicate section" in error for error in result["errors"])


def test_done_requires_run_gate(tmp_path):
    text = _finalize(_exemplar()
                     .replace("status: active", "status: done", 1)
                     .replace("phase: Implement", "phase: Done", 1)
                     .replace("units_done: 2", "units_done: 3", 1)
                     .replace("| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |",
                              "| U3 | Push | pass | Done | docs/handbook/procedures/recovery.md | check exit 0 | delivery | none |")
                     .replace('  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: pending\n    evidence: ""',
                              '  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: verified\n    evidence: "manual"')
                     .replace("    used: 2", "    used: 3", 1)
                     .replace("next_action: Run Review on unit U3 with the diff and the link checker output.",
                              _approval("[]") + 'next_action: ""'))
    text = text.replace("run_gate:\n  command: make test\n  exit: 0\n  at: 2026-10-25T02:00:00Z\n  evidence: make test exit 0\n", "")
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("status done requires run_gate" in error for error in result["errors"])


def test_done_with_open_medium_finding_is_rejected(tmp_path):
    text = _finalize(_exemplar()
                     .replace("status: active", "status: done", 1)
                     .replace("phase: Implement", "phase: Done", 1)
                     .replace("units_done: 2", "units_done: 3", 1)
                     .replace("| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |",
                              "| U3 | Push | pass | Done | docs/handbook/procedures/recovery.md | check exit 0 | delivery | none |")
                     .replace('  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: pending\n    evidence: ""',
                              '  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: verified\n    evidence: "manual"')
                     .replace("    used: 2", "    used: 3", 1)
                     .replace("next_action: Run Review on unit U3 with the diff and the link checker output.",
                              _approval("[]") + 'next_action: ""'))
    text = text.replace("- No unresolved high or medium finding.",
                        "- F9 (medium, owner U3): unresolved.")
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("open high/medium finding" in error for error in result["errors"])


def test_done_with_planned_in_flight_is_rejected(tmp_path):
    text = _finalize(_exemplar()
                     .replace("status: active", "status: done", 1)
                     .replace("phase: Implement", "phase: Done", 1)
                     .replace("units_done: 2", "units_done: 3", 1)
                     .replace("| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |",
                              "| U3 | Push | pass | Done | docs/handbook/procedures/recovery.md | check exit 0 | delivery | none |")
                     .replace('  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: pending\n    evidence: ""',
                              '  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: verified\n    evidence: "manual"')
                     .replace("    used: 2", "    used: 3", 1)
                     .replace("next_action: Run Review on unit U3 with the diff and the link checker output.",
                              _approval("[]") + 'next_action: ""'))
    text = text.replace("| Write the recovery page | recovery-page | done |",
                        "| Write the recovery page | recovery-page | planned |")
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("planned In-flight" in error for error in result["errors"])


def test_expired_lease_is_rejected(tmp_path):
    lease = ("lease:\n"
             "  resource: docs/handbook\n"
             "  owner: orchestration-orchestrator\n"
             "  expires: 2026-10-24T00:00:00Z\n")
    path = _write(tmp_path, _exemplar().replace("acceptance:\n", lease + "acceptance:\n", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("lease is expired" in error for error in result["errors"])


def test_budget_overrun_allowed_only_at_budget_halt(tmp_path):
    text = _exemplar().replace("status: active", "status: halted", 1)
    text = text.replace("phase: Implement", "phase: HALT", 1)
    text = text.replace("next_action:", "reason: budget\nnext_action:", 1)
    text = text.replace("used: 120000", "used: 500000", 1)
    text = text.replace("RUN docs-migration-example | active |", "RUN docs-migration-example | halted |", 1)
    text = text.replace("tokens 120000/400000", "tokens 500000/400000", 1)
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert result["ok"], result["errors"]


def test_push_phase_requires_approval(tmp_path):
    path = _write(tmp_path, _exemplar().replace("phase: Implement", "phase: Push", 1))
    result = run_state.check(path)
    assert not result["ok"]
    assert any("phase Push requires push_approval" in error for error in result["errors"])


def test_max_age_covers_blocked_runs(tmp_path):
    text = _exemplar().replace("status: active", "status: blocked", 1)
    text = text.replace("updated: 2026-10-25T02:00:00Z", "updated: 2026-10-25T05:00:00Z", 1)
    text = text.replace("next_action:", "reason: vendor API outage\nnext_action:", 1)
    text = text.replace("RUN docs-migration-example | active |", "RUN docs-migration-example | blocked |", 1)
    path = _write(tmp_path, text)
    result = run_state.check(path, max_age_hours=1)
    assert not result["ok"]
    assert any("stale" in error for error in result["errors"])


def test_report_unit_ready_unverified_can_close(tmp_path):
    text = (_exemplar()
            .replace("status: active", "status: waiting", 1)
            .replace("phase: Implement", "phase: Ready", 1)
            .replace("units_done: 2", "units_done: 3", 1)
            .replace("| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |",
                     "| U3 | Verify | hold | Ready (unverified) | docs/handbook/procedures/recovery.md | exemption recorded | report | none |")
            .replace('  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: pending\n    evidence: ""',
                     '  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: unverified\n    evidence: "exemption: no browser"')
            .replace("    used: 2", "    used: 3", 1)
            .replace("RUN docs-migration-example | active | units 2/3",
                     "RUN docs-migration-example | waiting | units 3/3", 1))
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert result["ok"], result["errors"]


def test_unit_done_from_plan_is_rejected(tmp_path):
    text = _exemplar().replace(
        "| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |",
        "| U3 | Plan | pass | Done | docs/handbook/procedures/recovery.md | ok | delivery | none |")
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("status Done has phase Plan" in error for error in result["errors"])


def test_open_finding_abbreviation_is_rejected_at_done(tmp_path):
    text = _finalize(_exemplar()
                     .replace("status: active", "status: done", 1)
                     .replace("phase: Implement", "phase: Done", 1)
                     .replace("units_done: 2", "units_done: 3", 1)
                     .replace("| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |",
                              "| U3 | Push | pass | Done | docs/handbook/procedures/recovery.md | check exit 0 | delivery | none |")
                     .replace('  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: pending\n    evidence: ""',
                              '  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: verified\n    evidence: "manual"')
                     .replace("    used: 2", "    used: 3", 1)
                     .replace("next_action: Run Review on unit U3 with the diff and the link checker output.",
                              _approval("[]") + 'next_action: ""'))
    text = text.replace("- No unresolved high or medium finding.",
                        "- F9 (H, owner U3): push bypass still open")
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("open high/medium finding" in error for error in result["errors"])


def test_missing_archive_file_is_rejected(tmp_path):
    text = (_exemplar()
            .replace("checkpoint: 4", "checkpoint: 6\ncheckpoint_base: 2\ncheckpoint_archive: missing.md", 1)
            .replace("| 1 | 2026-10-24T21:00:00Z |", "| 3 | 2026-10-24T21:00:00Z |", 1)
            .replace("| 2 | 2026-10-24T22:15:00Z |", "| 4 | 2026-10-24T22:15:00Z |", 1)
            .replace("| 3 | 2026-10-24T23:45:00Z |", "| 5 | 2026-10-24T23:45:00Z |", 1)
            .replace("| 4 | 2026-10-25T02:00:00Z |", "| 6 | 2026-10-25T02:00:00Z |", 1)
            .replace("checkpoint 4 | tokens", "checkpoint 6 | tokens", 1))
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("does not exist" in error for error in result["errors"])


def _done_base():
    return _finalize(_exemplar()
                     .replace("status: active", "status: done", 1)
                     .replace("phase: Implement", "phase: Done", 1)
                     .replace("units_done: 2", "units_done: 3", 1)
                     .replace("| U3 | Implement | pass | Implement | docs/handbook/procedures/recovery.md | draft written; review not run | delivery | Review |",
                              "| U3 | Push | pass | Done | docs/handbook/procedures/recovery.md | check exit 0 | delivery | none |")
                     .replace('  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: pending\n    evidence: ""',
                              '  - id: A3\n    criterion: An operator can follow the migrated procedure end to end.\n    state: verified\n    evidence: "manual"')
                     .replace("    used: 2", "    used: 3", 1)
                     .replace("next_action: Run Review on unit U3 with the diff and the link checker output.",
                              _approval("[]") + 'next_action: ""')
                     .replace("RUN docs-migration-example | active | units 2/3 | checkpoint 4 | tokens 120000/400000 | next Run Review on unit U3 with the diff and the link checker output.",
                              "RUN docs-migration-example | done | units 3/3 | checkpoint 4 | tokens 120000/400000 | next none"))


def test_nonzero_run_gate_needs_run_coverage(tmp_path):
    text = _done_base().replace("  exit: 0", "  exit: 1", 1)
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("no push_approval coverage" in error for error in result["errors"])


def test_nonzero_run_gate_passes_with_run_scope(tmp_path):
    text = _done_base().replace("  exit: 0", "  exit: 1", 1)
    text = text.replace("scope: approved at the Push gate",
                        "scope: run gate approved at Push")
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert result["ok"], result["errors"]


def test_done_open_finding_case_variant_fails(tmp_path):
    text = _done_base().replace("## Open findings", "## open findings")
    text = text.replace("- No unresolved high or medium finding.",
                        "- F9 (high, owner U3): open gap.")
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("open high/medium finding" in error for error in result["errors"])


def test_done_open_finding_not_hidden_by_no_prefix(tmp_path):
    text = _done_base().replace("- No unresolved high or medium finding.",
                                "- No fix yet for the finding (high, owner U3).")
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("open high/medium finding" in error for error in result["errors"])


def test_done_open_finding_shorthand_is_rejected(tmp_path):
    text = _done_base().replace("- No unresolved high or medium finding.",
                                "- H: none; M: 2 open")
    path = _write(tmp_path, text)
    result = run_state.check(path)
    assert not result["ok"]
    assert any("open high/medium finding" in error for error in result["errors"])
