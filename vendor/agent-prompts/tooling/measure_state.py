#!/usr/bin/env python3
"""Measure the numbers the library's documents quote, and keep them honest.

Documentation drifts faster than code: in the 2026-10-31 audit, 41 of 70 checked
claims in live documents were wrong, several of them numbers the author had
written and then invalidated with his own later edits. A rule ("measure, then
write") does not prevent that. A generated file does.

`docs/measured-state.md` is that file. It holds every number a live document is
allowed to quote; the documents say the value or point at this file, and this
checker fails when the file disagrees with the tree.

Usage:
    python3 tooling/measure_state.py            # print the measurements
    python3 tooling/measure_state.py --write    # rewrite docs/measured-state.md
    python3 tooling/measure_state.py --check    # gate mode: fail on drift

Exit 0 clean, 1 drift, 2 cannot measure.
"""

import argparse
import importlib.util
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "docs" / "measured-state.md"
TOOLING = ROOT / "tooling"
sys.path.insert(0, str(TOOLING))

import check_admission  # noqa: E402
import check_gate_verdict  # noqa: E402
import check_prompt_security  # noqa: E402
import render_omp  # noqa: E402
import validate_templates as vt  # noqa: E402


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def carriers():
    total = 0
    for pattern in ("agents/**/*.md", "prompts/**/*.md"):
        for path in ROOT.glob(pattern):
            if "<doctrine>" in path.read_text(encoding="utf-8"):
                total += 1
    return total


def versions():
    pins = {}
    for line in (ROOT / "CATALOG.md").read_text(encoding="utf-8").splitlines():
        match = re.match(r"^- (Library|Role templates|Task prompts|Template|"
                         r"Orchestrator template|Doctrine|Conduct): (.+)$", line)
        if match:
            pins[match.group(1)] = match.group(2)
    return pins


def skill_shape():
    """Token values come from `report_skill_shape.measure`, so the report and the
    measured state can never disagree about the same file."""
    import report_skill_shape
    base = ROOT / "skills"
    rows = []
    for path in sorted(base.rglob("SKILL.md")):
        row = report_skill_shape.measure(path, base)
        rows.append((path, row["tokens_body"]))
    tokens = sorted(t for _, t in rows)
    over = [p for p, t in rows if t > 1500]
    return {
        "count": len(rows),
        "vendor": len(list((ROOT / "skills" / "vendor").glob("*/SKILL.md"))),
        "min": tokens[0],
        "median": int(statistics.median(tokens)),
        "max": tokens[-1],
        "total": sum(tokens),
        "over_cap": len(over),
        "over_cap_non_vendor": len([p for p in over if "vendor" not in p.parts]),
        "with_references": len([p for p in (ROOT / "skills").rglob("SKILL.md")
                                if (p.parent / "references").is_dir()]),
    }


def counts():
    drive = _load("loop_drive", "evals/loop/drive.py")
    import yaml
    catalog = yaml.safe_load((ROOT / "omp" / "catalog.yaml").read_text(encoding="utf-8"))
    projected = len(catalog.get("agents") or [])
    deferred = len(catalog.get("deferred") or [])
    return {
        "agents": len(list((ROOT / "agents").rglob("*.md"))),
        "task_prompts": len(list((ROOT / "prompts" / "tasks").glob("*.md"))),
        "workspace_prompts": len([p for p in (ROOT / "prompts" / "workspace").glob("*")
                                  if p.is_file()]),
        "carriers": carriers(),
        "trigger_cases": len(list((ROOT / "evals" / "trigger").glob("*.json"))),
        "behavioral_cases": len(list((ROOT / "evals" / "behavioral").glob("*.json"))),
        "loop_scenarios": len(drive.scenarios()),
        "prompt_assets": len(list(check_prompt_security.iter_files(ROOT))),
        "omp_projected": projected,
        "omp_deferred": deferred,
        "tooling_scripts": len(list((ROOT / "tooling").glob("*.py"))),
        "tooling_tests": len(list((ROOT / "tooling" / "tests").glob("test_*.py"))),
        "exemplars": len(list((ROOT / "exemplars").glob("*"))),
        "provenance_files": len([p for p in (ROOT / "provenance").glob("*") if p.is_file()]),
        "standards": len(list((ROOT / "standards").glob("*.md"))),
        "evidence_records": len(list((ROOT / "standards" / "evidence").glob("*"))),
    }


def suites():
    manifest = json.loads((ROOT / "tooling" / "test-manifest.json").read_text(encoding="utf-8"))
    collected = subprocess.run([sys.executable, "-m", "pytest", str(ROOT / "tooling" / "tests"),
                                "--collect-only", "-q"], cwd=str(ROOT),
                               capture_output=True, text=True)
    if collected.returncode != 0:
        raise RuntimeError("pytest collection failed (rc %d): %s"
                           % (collected.returncode,
                              (collected.stdout or collected.stderr).strip()[-400:]))
    count = sum(1 for line in collected.stdout.splitlines() if "::" in line)
    if count == 0:
        raise RuntimeError("pytest collected no tests; refusing to record 0")
    per_checker = {}
    for name in ("check_gate_verdict", "check_admission", "check_prompt_security"):
        path = ROOT / "tooling" / "tests" / ("test_%s.py" % name)
        text = path.read_text(encoding="utf-8")
        per_checker[name] = len(re.findall(r"(?m)^def test_", text))
    return {
        "pytest": count,
        "identities": sum(len(v) for v in manifest["tests"].values()),
        "check_gate_verdict": per_checker["check_gate_verdict"],
        "check_admission": per_checker["check_admission"],
        "check_prompt_security": per_checker["check_prompt_security"],
    }


def admissions():
    out = {}
    for runtime in ("omp", "dsh"):
        data = json.loads((ROOT / runtime / "admission.json").read_text(encoding="utf-8"))
        result, reasons = check_admission.admission_result(data)
        out[runtime] = {"admission": result, "reasons": reasons}
    return out


def measure():
    return {
        "versions": versions(),
        "counts": counts(),
        "skills": skill_shape(),
        "suites": suites(),
        "admissions": admissions(),
        "vendict_contract": check_gate_verdict.load_contract().get("contract"),
    }


def render(data):
    c, s, t = data["counts"], data["skills"], data["suites"]
    v = data["versions"]
    a = data["admissions"]
    lines = [
        "# Measured state",
        "",
        "Generated by `python3 tooling/measure_state.py --write` and enforced by",
        "`--check` in `make gate`. A live document quotes the values below or points",
        "here; it never restates a number it did not read from this file. Historical",
        "records (dated changelog entries, pass reports) keep their own measurement and",
        "say which pass they measured.",
        "",
        "## Version pins",
        "",
        "| Pin | Value |",
        "|---|---|",
    ]
    for key in sorted(v):
        lines.append("| %s | %s |" % (key, v[key]))
    lines += [
        "",
        "## Inventory",
        "",
        "| Item | Count |",
        "|---|---|",
    ]
    labels = {
        "agents": "role templates", "task_prompts": "task prompts",
        "workspace_prompts": "workspace prompts", "carriers": "doctrine carriers",
        "trigger_cases": "trigger case files", "behavioral_cases": "behavioral case files",
        "loop_scenarios": "loop guard scenarios", "prompt_assets": "prompt assets scanned",
        "omp_projected": "OMP projected agents", "omp_deferred": "OMP deferred agents",
        "tooling_scripts": "tooling scripts", "tooling_tests": "tooling test modules",
        "exemplars": "exemplar files", "provenance_files": "provenance files",
        "standards": "standards", "evidence_records": "evidence records",
    }
    for key in c:
        lines.append("| %s | %d |" % (labels[key], c[key]))
    lines += [
        "",
        "## Skills",
        "",
        "| Measure | Value |",
        "|---|---|",
        "| skills hosted | %d |" % s["count"],
        "| vendor skills (frozen) | %d |" % s["vendor"],
        "| non-vendor skills | %d |" % (s["count"] - s["vendor"]),
        "| body tokens min / median / max | %d / %d / %d |" % (s["min"], s["median"], s["max"]),
        "| body tokens total | %d |" % s["total"],
        "| bodies over the 1,500 cap | %d (non-vendor %d) |" % (s["over_cap"], s["over_cap_non_vendor"]),
        "| skills with a references tree | %d |" % s["with_references"],
        "",
        "## Test suites",
        "",
        "| Suite | Value |",
        "|---|---|",
        "| pytest collected | %d |" % t["pytest"],
        "| pinned test identities | %d |" % t["identities"],
        "| `check_gate_verdict` tests | %d |" % t["check_gate_verdict"],
        "| `check_admission` tests | %d |" % t["check_admission"],
        "| `check_prompt_security` tests | %d |" % t["check_prompt_security"],
        "",
        "## Runtime admission",
        "",
        "| Runtime | Computed admission | Refusing capability |",
        "|---|---|---|",
    ]
    for runtime in sorted(a):
        reasons = "; ".join(a[runtime]["reasons"]) or "none"
        lines.append("| %s | %s | %s |" % (runtime, a[runtime]["admission"], reasons))
    lines += ["", "Contract: `%s`." % data["vendict_contract"], ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        data = measure()
    except Exception as exc:  # noqa: BLE001 - a measurement failure is exit 2
        print("measured-state: cannot measure: %s" % exc)
        return 2
    rendered = render(data)
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
        return 0
    if args.write:
        STATE.write_text(rendered)
        print("measured-state: wrote %s" % STATE.relative_to(ROOT).as_posix())
        return 0
    if args.check:
        if not STATE.is_file():
            print("measured-state: missing %s; run --write" % STATE.relative_to(ROOT).as_posix())
            return 1
        current = STATE.read_text()
        if current != rendered:
            diff = [line for line in rendered.splitlines()
                    if line not in current.splitlines()]
            print("measured-state: %s is stale; run --write" % STATE.relative_to(ROOT).as_posix())
            for line in diff[:10]:
                print("  now: " + line)
            return 1
        print("measured-state: %s matches the tree" % STATE.relative_to(ROOT).as_posix())
        return 0
    print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
