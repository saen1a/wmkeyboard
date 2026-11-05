"""Tests for the LH-14 append-only run journal checker."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tooling" / "check_run_journal.py"
EXAMPLE = ROOT / "exemplars" / "run-journal-example.jsonl"
SCHEMA = ROOT / "standards" / "run-journal.schema.json"


def _run(path, *extra):
    return subprocess.run([sys.executable, str(CHECK), str(path), *extra],
                          cwd=str(ROOT), capture_output=True, text=True)


def _events():
    return [json.loads(line) for line in
            EXAMPLE.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(tmp_path, events):
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n",
                    encoding="utf-8")
    return path


def test_example_passes():
    result = _run(EXAMPLE)
    assert result.returncode == 0, result.stdout
    assert "0 violation(s)" in result.stdout


def test_gap_in_sequence_fails(tmp_path):
    events = _events()
    events[-1]["seq"] = 9
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "expected 5" in result.stdout


def test_decreasing_timestamp_fails(tmp_path):
    events = _events()
    events[1]["at"] = "2026-10-24T20:00:00Z"
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "before the previous event" in result.stdout


def test_unknown_kind_fails(tmp_path):
    events = _events()
    events[0]["kind"] = "resume"
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "kind is not canonical" in result.stdout


def test_action_started_without_action_id_fails(tmp_path):
    events = _events()
    del events[2]["action_id"]
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "action event needs action_id" in result.stdout


def test_action_result_without_evidence_fails(tmp_path):
    events = _events()
    events[3]["evidence"] = ""
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "action_result needs evidence" in result.stdout


def test_done_without_evidence_fails(tmp_path):
    events = _events()
    events[-1]["evidence"] = ""
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "done needs evidence" in result.stdout


def test_stop_without_reason_fails(tmp_path):
    events = _events()
    events[-1]["kind"] = "stop"
    events[-1]["phase"] = "HALT"
    events[-1]["gate"] = "halt"
    events[-1].pop("reason", None)
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "stop needs reason" in result.stdout


def test_unterminated_journal_fails(tmp_path):
    events = _events()
    events[-1]["kind"] = "note"
    events[-1]["result"] = "still working"
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "must end at checkpoint, done, or stop" in result.stdout


def test_unknown_key_fails(tmp_path):
    events = _events()
    events[0]["operator_note"] = "hand edit"
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "unknown key" in result.stdout


def test_bad_state_hash_fails(tmp_path):
    events = _events()
    events[1]["state_sha256"] = "not-a-hash"
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "state_sha256 is not a sha256" in result.stdout


def test_invalid_json_line_fails(tmp_path):
    path = tmp_path / "events.jsonl"
    lines = EXAMPLE.read_text(encoding="utf-8").splitlines()
    path.write_text(lines[0] + "\nnot json\n" + "\n".join(lines[1:]) + "\n",
                    encoding="utf-8")
    result = _run(path)
    assert result.returncode == 1
    assert "is not JSON" in result.stdout


def test_empty_journal_fails(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text("", encoding="utf-8")
    result = _run(path)
    assert result.returncode == 1
    assert "journal has no events" in result.stdout


def test_missing_journal_is_exit_two(tmp_path):
    result = _run(tmp_path / "missing.jsonl")
    assert result.returncode == 2
    assert "cannot read" in result.stdout


def test_json_output_reports_counts(tmp_path):
    result = _run(EXAMPLE, "--json")
    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["events"] == 5
    assert payload["violations"] == []


def test_done_must_be_phase_done_and_pass(tmp_path):
    events = _events()
    events[-1]["phase"] = "HALT"
    events[-1]["gate"] = "halt"
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "done phase must be Done" in result.stdout
    assert "done gate must be pass" in result.stdout


def test_event_after_done_fails(tmp_path):
    events = _events()
    extra = dict(events[1])
    extra["seq"] = 6
    extra["at"] = "2026-10-24T22:30:00Z"
    events.append(extra)
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "follows the terminal event" in result.stdout


def test_checkpoint_without_state_hash_fails(tmp_path):
    events = _events()
    del events[1]["state_sha256"]
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "checkpoint needs state_sha256" in result.stdout


def test_action_result_without_start_fails(tmp_path):
    events = _events()
    events[3]["action_id"] = "a-99"
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "has no action_started" in result.stdout


def test_duplicate_action_receipt_fails(tmp_path):
    events = _events()
    extra = dict(events[3])
    extra["seq"] = 5
    extra["at"] = "2026-10-24T22:19:00Z"
    events.insert(4, extra)
    events[-1]["seq"] = 6
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "already has a receipt" in result.stdout


def test_empty_unit_fails(tmp_path):
    events = _events()
    events[2]["unit"] = ""
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "unit is empty" in result.stdout


def test_gate_none_is_not_canonical(tmp_path):
    events = _events()
    events[0]["gate"] = "none"
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "gate is not canonical" in result.stdout


def test_withheld_action_needs_reason(tmp_path):
    events = _events()
    events[3]["kind"] = "action_withheld"
    events[3]["evidence"] = ""
    events[3]["reason"] = ""
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "action_withheld needs reason" in result.stdout


def test_start_must_be_first(tmp_path):
    events = _events()
    events[0]["kind"] = "checkpoint"
    events[0]["state_sha256"] = "a" * 64
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "line 1 must be a start event" in result.stdout


def test_checker_and_schema_agree_on_contract_sets():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    fixture = _events()[0]
    base = set(fixture) - {"gate", "action_id", "state_sha256", "reason"}
    assert set(schema["required"]) == base
    assert set(schema["properties"]) == base | {
        "gate", "action_id", "state_sha256", "reason"}
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]["kind"]["enum"]) == {
        "start", "checkpoint", "action_started", "action_result",
        "action_withheld", "note", "stop", "done"}
    assert set(schema["properties"]["phase"]["enum"]) == {
        "Plan", "Implement", "Review", "Fix", "Verify", "Push",
        "Ready", "Ready (unverified)", "Done", "HALT"}
    assert set(schema["properties"]["gate"]["enum"]) == {
        "pass", "fix", "hold", "halt"}


def test_gate_runs_both_new_checkers():
    gate = (ROOT / "tooling" / "gate.sh").read_text(encoding="utf-8")
    assert "check_run_journal.py exemplars/run-journal-example.jsonl" in gate
    assert "check_findings_ledger.py exemplars/findings-ledger-example.md" in gate
    assert "for ledger in provenance/findings-*.md" in gate
    assert "evals/long-horizon/drive.py --verify" in gate


def test_boolean_seq_fails(tmp_path):
    events = _events()
    events[0]["seq"] = True
    result = _run(_write(tmp_path, events))
    assert result.returncode == 1
    assert "seq is not an integer" in result.stdout


def test_schema_conditionals_and_minlength_are_pinned():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    all_of = schema["allOf"]
    kinds = {entry["if"]["properties"]["kind"]["const"] for entry in all_of}
    assert kinds == {"checkpoint", "start", "done", "stop"}
    checkpoint = next(entry for entry in all_of
                      if entry["if"]["properties"]["kind"]["const"] == "checkpoint")
    assert set(checkpoint["then"]["required"]) == {"gate", "state_sha256"}
    start = next(entry for entry in all_of
                 if entry["if"]["properties"]["kind"]["const"] == "start")
    assert start["then"]["properties"]["unit"]["const"] == "run"
    done = next(entry for entry in all_of
                if entry["if"]["properties"]["kind"]["const"] == "done")
    assert done["then"]["properties"]["phase"]["const"] == "Done"
    assert done["then"]["properties"]["gate"]["const"] == "pass"
    stop = next(entry for entry in all_of
                if entry["if"]["properties"]["kind"]["const"] == "stop")
    assert stop["then"]["properties"]["phase"]["const"] == "HALT"
    assert stop["then"]["required"] == ["reason"]
    assert schema["properties"]["unit"]["minLength"] == 1
    assert schema["properties"]["reason"]["minLength"] == 1


def _hash_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_state_flag_accepts_the_view_the_journal_committed(tmp_path):
    state = tmp_path / "RUN.md"
    state.write_text("---\nrun_id: t\n---\n\n## Operator\n", encoding="utf-8")
    events = _events()
    events[1]["state_sha256"] = _hash_file(state)
    result = _run(_write(tmp_path, events), "--state", str(state))
    assert result.returncode == 0, result.stdout
    assert "0 violation(s)" in result.stdout


def test_state_flag_rejects_a_stale_view(tmp_path):
    state = tmp_path / "RUN.md"
    state.write_text("---\nrun_id: t\n---\n", encoding="utf-8")
    events = _events()
    events[1]["state_sha256"] = _hash_file(state)
    journal = _write(tmp_path, events)
    state.write_text("---\nrun_id: t\nnext_action: something else\n---\n",
                     encoding="utf-8")
    result = _run(journal, "--state", str(state))
    assert result.returncode == 1
    assert "stale view" in result.stdout
    assert _hash_file(state) in result.stdout


def test_state_flag_reports_a_missing_state_file(tmp_path):
    result = _run(EXAMPLE, "--state", str(tmp_path / "absent.md"))
    assert result.returncode == 1
    assert "cannot read" in result.stdout


def test_state_flag_needs_a_checkpoint(tmp_path):
    events = _events()
    events = [events[0], events[2], events[3], events[4]]
    for index, event in enumerate(events, 1):
        event["seq"] = index
    state = tmp_path / "RUN.md"
    state.write_text("---\nrun_id: t\n---\n", encoding="utf-8")
    result = _run(_write(tmp_path, events), "--state", str(state))
    assert result.returncode == 1
    assert "no checkpoint" in result.stdout


def test_stale_view_is_only_visible_with_the_state_flag(tmp_path):
    state = tmp_path / "RUN.md"
    state.write_text("---\nrun_id: t\n---\n", encoding="utf-8")
    events = _events()
    events[1]["state_sha256"] = _hash_file(state)
    journal = _write(tmp_path, events)
    state.write_text("---\nrun_id: t\ntampered: yes\n---\n", encoding="utf-8")
    assert _run(journal).returncode == 0
    assert _run(journal, "--state", str(state)).returncode == 1


def test_unreceipted_action_is_a_warning_not_a_violation(tmp_path):
    events = _events()
    events.insert(4, {
        "schema": "agent-run-journal/1", "seq": 5,
        "at": "2026-10-24T22:19:00Z", "kind": "action_started", "unit": "U1",
        "phase": "Verify", "action": "run the link checker", "result": "",
        "evidence": "intent recorded", "action_id": "a-18"})
    for index, event in enumerate(events, 1):
        event["seq"] = index
    result = _run(_write(tmp_path, events))
    assert result.returncode == 0, result.stdout
    assert "WARN action_id a-18 started at seq 5 has no receipt" in result.stdout
    assert "0 violation(s)" in result.stdout


def test_receipted_actions_produce_no_warning(tmp_path):
    result = _run(EXAMPLE)
    assert "WARN" not in result.stdout


def test_json_output_carries_warnings(tmp_path):
    events = _events()
    events[3]["kind"] = "action_withheld"
    events[3].pop("action_id")
    result = _run(_write(tmp_path, events), "--json")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["warnings"] == [
        "action_id a-17 started at seq 3 has no receipt; "
        "resolve the side effect before replaying"]
