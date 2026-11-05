"""Tests for the loop ordering gate (WL-02, WL-10, WL-15)."""

import copy
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tooling" / "check_loop_gate.py"
VERIFY_EXAMPLE = ROOT / "exemplars" / "gate-verdict-example.json"
PLAN_EXAMPLE = ROOT / "exemplars" / "gate-verdict-plan-review.json"
HEADER = ("| unit_id | phase | attempt | gate | status | artifact | findings | "
          "evidence | decision | owner | timestamp | next |\n"
          "|---|---|---|---|---|---|---|---|---|---|---|---|\n")


def plan_pass(unit="U1", attempt=0, findings=None):
    data = json.loads(PLAN_EXAMPLE.read_text(encoding="utf-8"))
    data = copy.deepcopy(data)
    data["unit"] = unit
    data["attempt"] = attempt
    if findings is not None:
        data["findings"] = findings
    if attempt >= 1:
        data["notes"] = ("PRIOR ROUND %d FAILED: goal.\nCHANGED: the goal states one outcome."
                         % (attempt - 1))
    return data


def plan_fix(unit="U1", attempt=0):
    data = plan_pass(unit, attempt)
    data["verdict"] = "fix"
    data["findings"] = [{"id": "F-1", "severity": "high", "state": "open",
                         "file_line": "spec.md:4", "evidence": "goal is a question"}]
    if attempt >= 1:
        data["notes"] = ("PRIOR ROUND %d FAILED: goal.\nCHANGED: rewrote the goal."
                         % (attempt - 1))
    return data


def verify_pass(unit="U1"):
    data = json.loads(VERIFY_EXAMPLE.read_text(encoding="utf-8"))
    data = copy.deepcopy(data)
    data["unit"] = unit
    return data


def ledger_row(status, next_phase, timestamp="2026-11-03", attempt="1",
               findings="none", unit="U1"):
    phase = {"Ready": "Verify", "Ready (unverified)": "Verify",
             "Done": "Push"}.get(status, status)
    gate = "hold" if status == "Ready (unverified)" else "pass"
    return ("| %s | %s | %s | %s | %s | docs/handbook/specs/recovery-rename.md | "
            "%s | make gate exit 0 | %s | "
            "maintainer | %s | %s |\n"
            % (unit, phase, attempt, gate, status, findings, gate, timestamp,
               next_phase))


def _run(tmp_path, ledger_text, verdicts, *extra):
    ledger = tmp_path / "ledger-probe.md"
    ledger.write_text("# Ledger: probe\n\n" + HEADER + ledger_text, encoding="utf-8")
    paths = []
    for index, verdict in enumerate(verdicts):
        path = tmp_path / ("verdict-%d.json" % index)
        path.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
        paths.append(str(path))
    command = [sys.executable, str(TOOL), "--ledger", str(ledger)]
    if paths:
        command += ["--verdict", *paths]
    return subprocess.run(command + list(extra), cwd=str(ROOT),
                          capture_output=True, text=True)


def test_implement_without_a_plan_review_fails(tmp_path):
    result = _run(tmp_path, ledger_row("Implement", "Review"), [])
    assert result.returncode == 1
    assert "no plan-review verdict" in result.stdout


def test_implement_with_a_clean_plan_review_passes(tmp_path):
    result = _run(tmp_path, ledger_row("Implement", "Review"), [plan_pass()])
    assert result.returncode == 0, result.stdout


def test_ready_without_a_verify_pass_fails(tmp_path):
    result = _run(tmp_path, ledger_row("Ready", "Push"), [plan_pass()])
    assert result.returncode == 1
    assert "no verify or acceptance pass" in result.stdout


def test_ready_with_plan_and_verify_passes(tmp_path):
    result = _run(tmp_path, ledger_row("Ready", "Push"),
                  [plan_pass(), verify_pass()])
    assert result.returncode == 0, result.stdout


def test_rounds_must_be_contiguous(tmp_path):
    result = _run(tmp_path, ledger_row("Ready", "Push"),
                  [plan_pass(attempt=2), verify_pass()])
    assert result.returncode == 1
    assert "not contiguous from 0" in result.stdout


def test_two_rounds_fix_then_pass_are_accepted(tmp_path):
    result = _run(tmp_path, ledger_row("Ready", "Push"),
                  [plan_fix(attempt=0), plan_pass(attempt=1), verify_pass()])
    assert result.returncode == 0, result.stdout


def test_open_plan_finding_blocks_the_unit(tmp_path):
    data = plan_pass()
    data["findings"] = [{"id": "F-2", "severity": "medium", "state": "open",
                         "file_line": "spec.md:9", "evidence": "unrunnable check"}]
    result = _run(tmp_path, ledger_row("Implement", "Review"), [data])
    assert result.returncode == 1
    assert ("not a clean pass" in result.stdout
            or "still open" in result.stdout
            or "no plan-review verdict" in result.stdout)


def test_rows_before_the_effective_date_are_grandfathered(tmp_path):
    result = _run(tmp_path, ledger_row("Done", "none", timestamp="2026-10-25"),
                  [])
    assert result.returncode == 0, result.stdout
    assert "0 row(s) at or after" in result.stdout


def test_since_override_moves_the_effective_date(tmp_path):
    result = _run(tmp_path, ledger_row("Implement", "Review"), [],
                  "--since", "2026-10-01")
    assert result.returncode == 1
    assert "no plan-review verdict" in result.stdout


def test_an_invalid_verdict_is_refused(tmp_path):
    broken = plan_pass()
    broken["criteria"] = [item for item in broken["criteria"]
                          if item["id"] != "goal"]
    broken["claims"] = [claim for claim in broken["claims"]
                        if "goal" not in str(claim.get("evidence"))]
    result = _run(tmp_path, ledger_row("Implement", "Review"), [broken])
    assert result.returncode == 1
    assert "missing the WL-15 checks" in result.stdout


def test_an_illegal_ledger_next_is_refused(tmp_path):
    result = _run(tmp_path, ledger_row("Implement", "Review") +
                  "| U2 | Plan | 0 | pass | Plan | spec.md | none | e | pass | o | "
                  "2026-11-03 | Implement |\n",
                  [plan_pass()])
    assert result.returncode == 1
    assert "next is not legal from Plan" in result.stdout


def test_a_directory_argument_expands(tmp_path):
    result = _run(tmp_path, ledger_row("Implement", "Review"), [plan_pass()])
    assert result.returncode == 0, result.stdout
    directory = subprocess.run(
        [sys.executable, str(TOOL), "--ledger", str(tmp_path),
         "--verdict", str(tmp_path), "--since", "2026-11-03"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert directory.returncode == 0, directory.stdout


def test_live_artifacts_pass_the_loop_gate():
    """The repository's own ledgers and verdicts satisfy the gate."""
    result = subprocess.run([sys.executable, str(TOOL),
                             "--grandfather", "plan-review-gate"],
                            cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    assert "0 violation(s)" in result.stdout


def test_json_summary_counts_rows(tmp_path):
    result = _run(tmp_path, ledger_row("Implement", "Review"), [plan_pass()], "--json")
    data = json.loads(result.stdout)
    assert data["rows_checked"] == 1
    assert data["violations"] == []


def test_push_without_a_verify_pass_fails(tmp_path):
    result = _run(tmp_path, ledger_row("Push", "Done"), [plan_pass()])
    assert result.returncode == 1
    assert "no verify or acceptance pass" in result.stdout


def test_an_exemption_cannot_waive_the_plan_review(tmp_path):
    row = ledger_row("Ready (unverified)", "Push",
                     findings="none (exemption: no second context)")
    result = _run(tmp_path, row, [])
    assert result.returncode == 1
    assert "no plan-review verdict" in result.stdout


def test_grandfathering_is_explicit_and_never_done(tmp_path):
    row = ledger_row("Ready (unverified)", "Push",
                     findings="none (unverified; grandfathered: predates the gate)")
    without = _run(tmp_path, row, [])
    assert without.returncode == 1
    with_flag = _run(tmp_path, row, [], "--grandfather", "U1")
    assert with_flag.returncode == 0, with_flag.stdout
    assert "grandfathered by --grandfather" in with_flag.stdout


def test_a_bad_timestamp_is_refused(tmp_path):
    result = _run(tmp_path, ledger_row("Implement", "Review",
                                       timestamp="not-a-date"), [plan_pass()])
    assert result.returncode == 1
    assert "is not an ISO date" in result.stdout


def test_a_bad_since_value_exits_two(tmp_path):
    result = _run(tmp_path, ledger_row("Implement", "Review"), [plan_pass()],
                  "--since", "2026-13-45")
    assert result.returncode == 2
    assert "invalid --since" in result.stdout


def test_a_live_ledger_cannot_hide_a_row_behind_an_old_date(tmp_path):
    rows = (ledger_row("Implement", "Review", timestamp="2026-10-01", unit="U2")
            + ledger_row("Verify", "Ready", timestamp="2026-11-03"))
    result = _run(tmp_path, rows, [plan_pass()])
    assert result.returncode == 1
    assert "unit U2 reached Implement with no plan-review verdict" in result.stdout


def test_the_plan_review_must_name_the_ledger_spec(tmp_path):
    ledger = ledger_row("Implement", "Review")
    result = _run(tmp_path, ledger, [plan_pass()])
    assert result.returncode == 0, result.stdout
    other = plan_pass()
    other["artifacts"][0]["path"] = "docs/other-spec.md"
    other["claims"] = [claim if claim.get("evidence") !=
                       "docs/handbook/specs/recovery-rename.md" else
                       {"claim": claim["claim"], "evidence": "docs/other-spec.md"}
                       for claim in other["claims"]]
    result = _run(tmp_path, ledger, [other])
    assert result.returncode == 1
    assert "names no reviewed spec" in result.stdout


def test_a_spec_edited_after_the_review_fails(tmp_path):
    ledger = ledger_row("Implement", "Review").replace(
        "docs/handbook/specs/recovery-rename.md", "docs/PLAN-SPEC.md")
    record = plan_pass()
    record["artifacts"][0]["path"] = "docs/PLAN-SPEC.md"
    record["artifacts"][0]["sha256"] = "0" * 64
    record["claims"] = [claim if claim.get("evidence") !=
                        "docs/handbook/specs/recovery-rename.md" else
                        {"claim": claim["claim"], "evidence": "docs/PLAN-SPEC.md"}
                        for claim in record["claims"]]
    result = _run(tmp_path, ledger, [record])
    assert result.returncode == 1
    assert "changed after the plan review" in result.stdout


def test_root_moves_the_spec_freshness_check(tmp_path):
    """A consumer points --root at its own tree, so the reviewed spec resolves."""
    (tmp_path / "specs").mkdir()
    spec = tmp_path / "specs" / "unit.md"
    spec.write_text("# spec\n\n" + "x" * 400 + "\n")
    digest = __import__("hashlib").sha256(spec.read_bytes()).hexdigest()
    ledger = ledger_row("Implement", "Review").replace(
        "docs/handbook/specs/recovery-rename.md", "specs/unit.md")
    ledger_path = tmp_path / "ledger-probe.md"
    ledger_path.write_text("# Ledger\n\n" + HEADER + ledger)
    record = plan_pass()
    record["artifacts"][0] = {"path": "specs/unit.md", "sha256": digest,
                              "bytes": len(spec.read_bytes()),
                              "non_whitespace_chars": 400, "shape": "ok"}
    record["claims"] = [{"claim": "spec", "evidence": "specs/unit.md"}]
    verdict_path = tmp_path / "verdict.json"
    verdict_path.write_text(json.dumps(record))
    command = [sys.executable, str(TOOL), "--ledger", str(ledger_path),
               "--verdict", str(verdict_path), "--root", str(tmp_path)]
    clean = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True)
    assert clean.returncode == 0, clean.stdout
    spec.write_text(spec.read_text() + "edited after the review\n")
    stale = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True)
    assert stale.returncode == 1
    assert "changed after the plan review" in stale.stdout
