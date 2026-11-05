#!/usr/bin/env python3
"""Fixture-based tests for tooling/check_skill_routing.py.

Each test builds a miniature skill library (SKILL.md files) and a matching
evals/trigger case-file set inside a temporary directory, then drives the tool
through its CLI. No test reads the real skills tree and no test touches the
network. All fixture text is ASCII.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLING = Path(__file__).resolve().parent.parent
CHECK = TOOLING / "check_skill_routing.py"

ALPHA = "Widget calibration and tuning of widget metrics"
BETA = "Gadget deployment and rollout to servers"
GAMMA = "Ledger accounting and reconciliation reports"


def write_skill(root, name, description):
    folder = root / "skills" / "shared" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(
        "---\nname: %s\ndescription: %s\n---\n\n# %s\n\nBody text.\n"
        % (name, description, name),
        encoding="utf-8")


def write_case(root, filename, data):
    cases = root / "evals" / "trigger"
    cases.mkdir(parents=True, exist_ok=True)
    (cases / filename).write_text(json.dumps(data, indent=2), encoding="utf-8")


def case(skill, positive=None, negative=None):
    return {"skill": skill, "positive": positive or [], "negative": negative or []}


def run_tool(root, *extra):
    return subprocess.run(
        [sys.executable, str(CHECK), "--root", str(root), *extra],
        capture_output=True, text=True)


class CheckSkillRoutingTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_all_routing_checks_pass(self):
        write_skill(self.root, "alpha", ALPHA)
        write_skill(self.root, "beta", BETA)
        write_skill(self.root, "gamma", GAMMA)
        write_case(self.root, "alpha.json", case(
            "alpha",
            [{"prompt": "widget calibration tuning metric", "top_k": 1}],
            [{"prompt": "gadget deployment rollout server", "owner": "beta"}]))
        write_case(self.root, "beta.json", case(
            "beta",
            [{"prompt": "gadget deployment rollout server", "top_k": 1}],
            [{"prompt": "widget calibration tuning metric", "owner": "alpha"}]))
        write_case(self.root, "gamma.json", case(
            "gamma",
            [{"prompt": "ledger accounting reconciliation report", "top_k": 1}],
            [{"prompt": "widget calibration tuning metric", "owner": "alpha"}]))

        result = run_tool(self.root, "--top-k", "1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("FAIL", result.stdout)
        self.assertIn("skill-routing: 3 skills, 3 case files, 0 violations",
                      result.stdout)

        machine = run_tool(self.root, "--top-k", "1", "--json")
        data = json.loads(machine.stdout)
        self.assertEqual(data["skills"], 3)
        self.assertEqual(data["cases"], 3)
        self.assertEqual(data["violations"], [])
        self.assertGreater(data["checks"], 0)

    def test_positive_prompt_ranking_wrong_skill_fails(self):
        write_skill(self.root, "alpha", "Completion claims require evidence")
        write_skill(self.root, "beta",
                    "Run the command and check output verify completion "
                    "claim evidence command output")
        write_skill(self.root, "gamma", GAMMA)
        write_case(self.root, "alpha.json", case(
            "alpha",
            [{"prompt": "check the output command evidence completion claim",
              "top_k": 1}]))

        result = run_tool(self.root, "--top-k", "1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("positive-rank", result.stdout)
        self.assertIn("ranked 2", result.stdout)

    def test_negative_prompt_triggers_named_skill_fails(self):
        write_skill(self.root, "alpha", ALPHA)
        write_skill(self.root, "beta",
                    "Completion claims require fresh evidence and "
                    "verification output")
        write_skill(self.root, "gamma", GAMMA)
        write_case(self.root, "beta.json", case(
            "beta",
            [{"prompt": "completion claim evidence verification output",
              "top_k": 1}],
            [{"prompt": "completion claim evidence verification output",
              "owner": "alpha"}]))

        result = run_tool(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("negative-trigger", result.stdout)

    def test_duplicate_case_file_fails(self):
        write_skill(self.root, "alpha", ALPHA)
        write_case(self.root, "alpha.json", case(
            "alpha", [{"prompt": "widget calibration tuning metric",
                       "top_k": 1}]))
        write_case(self.root, "alpha-copy.json", case("alpha"))

        result = run_tool(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate-case", result.stdout)

    def test_unknown_skill_case_file_fails(self):
        write_skill(self.root, "alpha", ALPHA)
        write_case(self.root, "alpha.json", case(
            "alpha", [{"prompt": "widget calibration tuning metric",
                       "top_k": 1}]))
        write_case(self.root, "ghost.json", case("ghost"))

        result = run_tool(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown-skill", result.stdout)

    def test_near_collision_descriptions_fail(self):
        write_skill(self.root, "alpha",
                    "Widget calibration and tuning of widget metrics for alpha")
        write_skill(self.root, "beta",
                    "Widget calibration and tuning of widget metrics for beta")

        result = run_tool(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("collision: alpha <-> beta", result.stdout)
        self.assertIn("jaccard=", result.stdout)

    def test_fail_on_warn_promotes_missing_case_file(self):
        write_skill(self.root, "alpha", ALPHA)
        write_skill(self.root, "beta", GAMMA)
        write_case(self.root, "alpha.json", case(
            "alpha", [{"prompt": "widget calibration tuning metric",
                       "top_k": 1}]))

        warn = run_tool(self.root)
        self.assertEqual(warn.returncode, 0, warn.stdout + warn.stderr)
        self.assertIn("WARN no-trigger-cases: beta", warn.stdout)
        self.assertIn("0 violations", warn.stdout)

        strict = run_tool(self.root, "--fail-on-warn")
        self.assertEqual(strict.returncode, 1)
        self.assertIn("FAIL no-trigger-cases: beta", strict.stdout)


if __name__ == "__main__":
    unittest.main()
