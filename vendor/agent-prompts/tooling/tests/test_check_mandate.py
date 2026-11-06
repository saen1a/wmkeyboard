"""Tests for the work-mandate checker (WA-02..WA-12)."""

import copy
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tooling" / "check_mandate.py"
EXAMPLE = ROOT / "exemplars" / "mandate-example.json"
SCHEMA = ROOT / "standards" / "mandate.schema.json"


def _load():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _run(tmp_path, data, *extra, name="mandate.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return subprocess.run([sys.executable, str(CHECK), str(path), *extra],
                          cwd=str(ROOT), capture_output=True, text=True)


def _inferred(data):
    """Turn the worked example into an admitted inferred grant."""
    data = copy.deepcopy(data)
    data["strength"] = "inferred"
    data["basis"] = {"via": "followup", "source": "repository", "sender": "octo-dev",
                     "scope_key": "issue:412",
                     "rules": [{"id": "label-polish", "instruction": "Rename misleading labels"}]}
    data["scope"]["accept_mode"] = "auto"
    return data


def test_example_passes():
    result = subprocess.run([sys.executable, str(CHECK), str(EXAMPLE)],
                            cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    assert "0 violation(s)" in result.stdout


def test_inferred_grant_passes(tmp_path):
    result = _run(tmp_path, _inferred(_load()))
    assert result.returncode == 0, result.stdout


def test_inferred_without_rules_fails(tmp_path):
    data = _inferred(_load())
    data["basis"]["rules"] = []
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "strength=inferred requires at least one matched rule" in result.stdout


def test_observe_mode_cannot_accept(tmp_path):
    data = _inferred(_load())
    data["scope"]["accept_mode"] = "observe"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "observe" in result.stdout


def test_explicit_requires_a_person_actor(tmp_path):
    data = _load()
    data["actor"]["kind"] = "bot"
    data["basis"]["via"] = "bot"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "strength=explicit requires actor.kind=person" in result.stdout


def test_addressed_requires_listed_sender(tmp_path):
    data = _load()
    data["basis"]["listed_sender"] = False
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "basis.via=addressed requires listed_sender=true" in result.stdout


def test_admission_requires_a_cell(tmp_path):
    data = _load()
    data["basis"]["via"] = "admission"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "requires basis.cell" in result.stdout


def test_actor_source_must_match_basis_source(tmp_path):
    data = _load()
    data["actor"]["source"] = "chat"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "identities are per source" in result.stdout


def test_unknown_key_fails(tmp_path):
    data = _load()
    data["principal"] = "octo-dev"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "unknown key: principal" in result.stdout


def test_withdrawn_requires_a_person(tmp_path):
    data = _load()
    data["state"] = "withdrawn"
    data["withdrawn_by"] = {"kind": "bot", "name": "auto", "at": "2026-10-31T08:00:00Z",
                            "reason_code": "duplicate"}
    data["history"].append({"at": "2026-10-31T08:00:00Z", "event": "withdrawn"})
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "withdrawn_by.kind must be person" in result.stdout


def test_state_must_match_last_history_event(tmp_path):
    data = _load()
    data["state"] = "withdrawn"
    data["withdrawn_by"] = {"kind": "person", "name": "octo-dev",
                            "at": "2026-10-31T08:00:00Z", "reason_code": "duplicate"}
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "state=withdrawn but the last history event is revalidated" in result.stdout


def test_history_must_open_with_granted(tmp_path):
    data = _load()
    data["history"][0]["event"] = "resumed"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "history[0] must be the granted event" in result.stdout


def test_history_is_append_only(tmp_path):
    data = _load()
    data["history"][1]["at"] = "2026-10-29T07:40:02Z"
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "goes backwards" in result.stdout


def test_future_grant_fails(tmp_path):
    data = _load()
    data["granted_at"] = "2099-01-01T00:00:00Z"
    data["history"] = [{"at": "2099-01-01T00:00:00Z", "event": "granted"}]
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "in the future" in result.stdout


def test_widening_requires_a_new_id(tmp_path):
    data = _load()
    data["supersedes"] = data["mandate_id"]
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "a wider grant is a new mandate" in result.stdout


def test_revoked_needs_a_revalidation_check(tmp_path):
    data = _load()
    data["state"] = "revoked"
    data["revocation"] = {"at": "2026-10-31T08:00:00Z", "failed_check": "felt_wrong",
                          "policy_version": "policy-8"}
    data["history"].append({"at": "2026-10-31T08:00:00Z", "event": "revoked"})
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "not a revalidation check" in result.stdout


def test_withdrawn_and_revoked_are_exclusive(tmp_path):
    data = _load()
    data["state"] = "withdrawn"
    data["withdrawn_by"] = {"kind": "person", "name": "octo-dev",
                            "at": "2026-10-31T08:00:00Z", "reason_code": "duplicate"}
    data["revocation"] = {"at": "2026-10-31T08:00:00Z",
                          "failed_check": "sender_not_listed", "policy_version": "policy-8"}
    data["history"].append({"at": "2026-10-31T08:00:00Z", "event": "withdrawn"})
    result = _run(tmp_path, data)
    assert result.returncode == 1
    assert "never both" in result.stdout


def test_json_output_reports_state(tmp_path):
    result = _run(tmp_path, _load(), "--json")
    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["state"] == "active"
    assert payload["violations"] == []


def test_schema_required_keys_match_checker():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT / "tooling"))
    import check_mandate

    assert sorted(schema["required"]) == sorted(check_mandate.REQUIRED)
    assert sorted(schema["properties"]) == sorted(check_mandate.TOP_KEYS)
    assert schema["properties"]["schema"]["const"] == check_mandate.SCHEMA


def test_schema_enums_match_checker():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT / "tooling"))
    import check_mandate

    props = schema["properties"]
    assert tuple(props["strength"]["enum"]) == check_mandate.STRENGTHS
    assert tuple(props["state"]["enum"]) == check_mandate.STATES
    assert tuple(props["basis"]["properties"]["via"]["enum"]) == check_mandate.VIAS
    assert tuple(props["basis"]["properties"]["cell"]["enum"]) == check_mandate.CELLS
    assert tuple(props["revocation"]["properties"]["failed_check"]["enum"]) \
        == check_mandate.FAILED_CHECKS
    assert tuple(props["history"]["items"]["properties"]["event"]["enum"]) \
        == check_mandate.EVENTS
