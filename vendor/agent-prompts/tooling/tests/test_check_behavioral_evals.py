#!/usr/bin/env python3
"""Fixture-based tests for tooling/check_behavioral_evals.py.

Each test builds a miniature skill library plus a matching evals/behavioral and
evals/fixtures tree in a temporary directory, then drives the validator through
its CLI. No test reads the real skills tree and no test touches the network.
All fixture text is ASCII.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLING = Path(__file__).resolve().parent.parent
CHECK = TOOLING / "check_behavioral_evals.py"

REQUIRED = [
    "anti-entropy-governance",
    "anti-hallucination",
    "anti-sycophancy",
    "verification-before-completion",
    "git-guardrails",
]
PRESSURES = ["time", "sunk_cost", "authority"]


def write_skill(root, name):
    folder = root / "skills" / "shared" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(
        "---\nname: %s\ndescription: Fixture skill %s\n---\n\n# %s\n\nBody.\n"
        % (name, name, name),
        encoding="utf-8")


def eval_entry(eval_id, pressure, kind="dialogue", files=None):
    entry = {
        "id": eval_id,
        "kind": kind,
        "pressure": pressure,
        "prompt": "Prompt for %s" % eval_id,
        "expected_output": "Expected output for %s" % eval_id,
        "expectations": ["Expectation one for %s" % eval_id],
    }
    if files is not None:
        entry["files"] = files
    return entry


def write_case(root, skill, evals):
    cases = root / "evals" / "behavioral"
    cases.mkdir(parents=True, exist_ok=True)
    (cases / ("%s.json" % skill)).write_text(
        json.dumps({"skill": skill, "evals": evals}, indent=2), encoding="utf-8")


def write_fixture(root, rel, content="fixture\n"):
    target = root / "evals" / "fixtures" / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def valid_library(root):
    for skill in REQUIRED:
        write_skill(root, skill)
        write_case(root, skill, [
            eval_entry("%s-%s" % (skill, pressure), pressure)
            for pressure in PRESSURES
        ])


def run_tool(root, *extra):
    return subprocess.run(
        [sys.executable, str(CHECK), "--root", str(root), *extra],
        capture_output=True, text=True)


class CheckBehavioralEvalsTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_all_checks_pass(self):
        valid_library(self.root)
        result = run_tool(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 violation(s)", result.stdout)

    def test_missing_discipline_skill_fails(self):
        valid_library(self.root)
        (self.root / "evals" / "behavioral" / "anti-hallucination.json").unlink()
        result = run_tool(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing-skill: anti-hallucination", result.stdout)

    def test_unknown_skill_fails(self):
        valid_library(self.root)
        write_case(self.root, "not-a-skill", [
            eval_entry("not-a-skill-time", "time")])
        result = run_tool(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown-skill: not-a-skill", result.stdout)

    def test_invalid_kind_fails(self):
        valid_library(self.root)
        write_case(self.root, "anti-hallucination", [
            eval_entry("a", "time", kind="chat"),
            eval_entry("b", "sunk_cost"),
            eval_entry("c", "authority"),
        ])
        result = run_tool(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid-kind", result.stdout)

    def test_execution_missing_fixture_fails(self):
        valid_library(self.root)
        write_case(self.root, "verification-before-completion", [
            eval_entry("exec", "authority", kind="execution", files=["missing-dir"]),
            eval_entry("b", "time"),
            eval_entry("c", "sunk_cost"),
        ])
        result = run_tool(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing-fixture", result.stdout)

    def test_execution_with_fixture_passes(self):
        valid_library(self.root)
        write_fixture(self.root, "verification-before-completion")
        write_case(self.root, "verification-before-completion", [
            eval_entry("exec", "authority", kind="execution",
                       files=["verification-before-completion"]),
            eval_entry("b", "time"),
            eval_entry("c", "sunk_cost"),
        ])
        result = run_tool(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_pressure_coverage_fails(self):
        valid_library(self.root)
        write_case(self.root, "anti-sycophancy", [
            eval_entry("a", "time"),
            eval_entry("b", "time"),
            eval_entry("c", "time"),
        ])
        result = run_tool(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("pressure-coverage: anti-sycophancy", result.stdout)

    def test_eval_count_fails(self):
        valid_library(self.root)
        write_case(self.root, "anti-hallucination", [
            eval_entry("a", "time"),
            eval_entry("b", "sunk_cost"),
        ])
        result = run_tool(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("eval-count", result.stdout)

    def test_duplicate_eval_id_fails(self):
        valid_library(self.root)
        write_case(self.root, "anti-hallucination", [
            eval_entry("dup", "time"),
            eval_entry("dup", "sunk_cost"),
            eval_entry("c", "authority"),
        ])
        result = run_tool(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate-eval", result.stdout)

    def test_broken_json_fails(self):
        valid_library(self.root)
        (self.root / "evals" / "behavioral" / "anti-hallucination.json").write_text(
            "{not json", encoding="utf-8")
        result = run_tool(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid-case", result.stdout)

    def test_json_output(self):
        valid_library(self.root)
        result = run_tool(self.root, "--json")
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["cases"], len(REQUIRED))
        self.assertEqual(payload["violations"], [])


if __name__ == "__main__":
    unittest.main()
