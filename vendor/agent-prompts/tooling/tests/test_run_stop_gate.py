#!/usr/bin/env python3
"""Tests for the stop-gate experiment harness (no network)."""

import importlib.util
import json
import unittest
from pathlib import Path

TOOLING = Path(__file__).resolve().parent.parent
TOOL = TOOLING / "run_stop_gate_experiment.py"
FIXTURES = TOOLING.parent / "evals" / "stop-gate"

spec = importlib.util.spec_from_file_location("stop_gate", TOOL)
stop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stop)


class StopGateTestCase(unittest.TestCase):
    def test_four_arms_and_common_no_tool_rule(self):
        self.assertEqual(set(stop.ARMS), {"stopp", "light", "direct", "risk"})
        for system in stop.ARMS.values():
            self.assertIn("no tools are available", system)

    def test_fixtures_are_complete(self):
        fixtures = stop.load_fixtures(TOOLING.parent)
        self.assertEqual(len(fixtures), 6)
        for fixture in fixtures:
            self.assertIn("id", fixture)
            self.assertIn("prompt", fixture)
            self.assertGreaterEqual(len(fixture["expectations"]), 3)


if __name__ == "__main__":
    unittest.main()
