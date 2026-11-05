"""Tests for the mechanical plan-spec gate (WL-15)."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tooling" / "check_plan_spec.py"

SPEC = """# Plan: probe

## Goal

Ship the probe unit so its verification command runs in one step.

## Scope boundaries

- in scope: the probe tool only
- out of scope: everything else

## Request coverage

| Request item | Unit | Why |
|---|---|---|
| R1 | U1 | the only unit |

## Units

| Unit | Acceptance | Verification | Owner |
|---|---|---|---|
| U1 | MUST: the tool exits 0 on a valid spec | `python3 tooling/check_plan_spec.py exemplars/plan-spec-example.md` | maintainer |

## Ownership and order

One writer for the unit (maintainer).

1. U1 -- first because nothing depends on it.

## Risks and halts

| Risk | Halt path | Operator question |
|---|---|---|
| none material | HALT | none needed |
"""


def _write(tmp_path, text, name="spec.md"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _run(path, *extra):
    return subprocess.run([sys.executable, str(TOOL), str(path), *extra],
                          cwd=str(ROOT), capture_output=True, text=True)


def test_valid_spec_meets_all_six_checks(tmp_path):
    result = _run(_write(tmp_path, SPEC))
    assert result.returncode == 0, result.stdout
    assert "6/6 checks met" in result.stdout


def test_json_output_is_verdict_shaped(tmp_path):
    result = _run(_write(tmp_path, SPEC), "--json")
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert [item["id"] for item in data["checks"]] == [
        "goal", "request-coverage", "acceptance", "verification",
        "ownership-order", "risk-halt"]
    assert all(item["state"] == "met" for item in data["checks"])


def test_question_in_the_goal_fails(tmp_path):
    bad = SPEC.replace("Ship the probe unit so its verification command runs in one step.",
                       "Should the probe ship, and does it run in one step?")
    result = _run(_write(tmp_path, bad))
    assert result.returncode == 1
    assert "question mark" in result.stdout


def test_short_goal_fails(tmp_path):
    bad = SPEC.replace("Ship the probe unit so its verification command runs in one step.",
                       "Do the probe.")
    result = _run(_write(tmp_path, bad))
    assert result.returncode == 1
    assert "goal is" in result.stdout


def test_missing_scope_boundaries_fails(tmp_path):
    bad = SPEC.replace("""## Scope boundaries

- in scope: the probe tool only
- out of scope: everything else

""", "")
    result = _run(_write(tmp_path, bad))
    assert result.returncode == 1
    assert "Scope boundaries" in result.stdout


def test_uncovered_unit_fails(tmp_path):
    bad = SPEC.replace("| R1 | U1 | the only unit |", "| R1 | U2 | the only unit |")
    result = _run(_write(tmp_path, bad))
    assert result.returncode == 1
    assert "request-coverage" in result.stdout
    assert "U2" in result.stdout


def test_unit_without_a_severity_criterion_fails(tmp_path):
    bad = SPEC.replace("| U1 | MUST: the tool exits 0 on a valid spec |",
                       "| U1 | the tool should work |")
    result = _run(_write(tmp_path, bad))
    assert result.returncode == 1
    assert "no MUST/SHOULD" in result.stdout


def test_placeholder_verification_fails(tmp_path):
    for placeholder in ("TBD", "-", "none"):
        bad = SPEC.replace("`python3 tooling/check_plan_spec.py exemplars/plan-spec-example.md`",
                           placeholder)
        result = _run(_write(tmp_path, bad, "spec-%s.md" % placeholder))
        assert result.returncode == 1, placeholder
        assert "verification" in result.stdout


def test_unknown_runner_fails(tmp_path):
    bad = SPEC.replace("`python3 tooling/check_plan_spec.py exemplars/plan-spec-example.md`",
                       "`run-the-probe.sh`")
    result = _run(_write(tmp_path, bad))
    assert result.returncode == 1
    assert "not a known runner" in result.stdout


def test_a_missing_check_file_fails(tmp_path):
    bad = SPEC.replace("`python3 tooling/check_plan_spec.py exemplars/plan-spec-example.md`",
                       "`python3 -m pytest tooling/tests/test_new_thing.py -q`")
    result = _run(_write(tmp_path, bad))
    assert result.returncode == 1
    assert "does not exist" in result.stdout
    assert "tooling/tests/test_new_thing.py" in result.stdout


def test_an_escaping_check_path_fails(tmp_path):
    bad = SPEC.replace("`python3 tooling/check_plan_spec.py exemplars/plan-spec-example.md`",
                       "`python3 ../../etc/passwd`")
    result = _run(_write(tmp_path, bad))
    assert result.returncode == 1
    assert "outside the root" in result.stdout


def test_an_unbalanced_quote_fails_without_a_traceback(tmp_path):
    bad = SPEC.replace("`python3 tooling/check_plan_spec.py exemplars/plan-spec-example.md`",
                       "pytest -k 'don")
    result = _run(_write(tmp_path, bad))
    assert result.returncode == 1
    assert "unbalanced quote" in result.stdout


def test_a_placeholder_criterion_fails(tmp_path):
    bad = SPEC.replace("| U1 | MUST: the tool exits 0 on a valid spec |",
                       "| U1 | MUST: TBD |")
    result = _run(_write(tmp_path, bad))
    assert result.returncode == 1
    assert "placeholder criterion" in result.stdout


def test_a_unit_without_an_owner_fails(tmp_path):
    bad = SPEC.replace("| U1 | MUST: the tool exits 0 on a valid spec | `python3 tooling/check_plan_spec.py exemplars/plan-spec-example.md` | maintainer |",
                       "| U1 | MUST: the tool exits 0 on a valid spec | `python3 tooling/check_plan_spec.py exemplars/plan-spec-example.md` |  |")
    result = _run(_write(tmp_path, bad))
    assert result.returncode == 1
    assert "has no owner" in result.stdout


def test_existing_path_is_accepted_as_the_check(tmp_path):
    spec = SPEC.replace("`python3 tooling/check_plan_spec.py exemplars/plan-spec-example.md`",
                        "`tooling/check_plan_spec.py`")
    result = _run(_write(tmp_path, spec))
    assert result.returncode == 0, result.stdout


def test_order_must_name_every_unit_once(tmp_path):
    bad = SPEC.replace("1. U1 -- first because nothing depends on it.",
                       "1. U9 -- first because nothing depends on it.")
    result = _run(_write(tmp_path, bad))
    assert result.returncode == 1
    assert "does not name exactly the Units" in result.stdout


def test_risk_row_without_a_halt_path_fails(tmp_path):
    bad = SPEC.replace("| none material | HALT | none needed |",
                       "| none material | monitor | none needed |")
    result = _run(_write(tmp_path, bad))
    assert result.returncode == 1
    assert "HALT path" in result.stdout


def test_reasoned_none_is_accepted(tmp_path):
    spec = SPEC.replace("""| Risk | Halt path | Operator question |
|---|---|---|
| none material | HALT | none needed |""",
                        "None: the unit touches one file and no shared surface.")
    result = _run(_write(tmp_path, spec))
    assert result.returncode == 0, result.stdout


def test_unreadable_spec_exits_two(tmp_path):
    result = _run(tmp_path / "missing.md")
    assert result.returncode == 2


def test_live_unit_spec_passes():
    result = _run(ROOT / "provenance" / "plan-loop-hardening-2026-11.md",
                  "--root", str(ROOT))
    assert result.returncode == 0, result.stdout
