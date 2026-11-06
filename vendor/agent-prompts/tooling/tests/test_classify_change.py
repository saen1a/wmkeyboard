#!/usr/bin/env python3
"""Tests for the STOPP gate classifier."""

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

TOOLING = Path(__file__).resolve().parent.parent
TOOL = TOOLING / "classify_change.py"

spec = importlib.util.spec_from_file_location("classify_change", TOOL)
classify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(classify)


def run(*args):
    return subprocess.run([sys.executable, str(TOOL), *args],
                          capture_output=True, text=True)


class ClassifyChangeTestCase(unittest.TestCase):
    def c(self, kind="comment", files=1, lines=1, verify="make test",
          exception_conflict=False, ambiguous=False, parsed_unchanged=False,
          path=""):
        return classify.classify(kind, files, lines, verify,
                                 exception_conflict, ambiguous,
                                 parsed_unchanged, path)

    def test_one_file_comment_with_verification_is_fast(self):
        gate, reasons = self.c()
        self.assertEqual(gate, "fast-path")
        self.assertTrue(reasons)

    def test_whitespace_is_fast(self):
        self.assertEqual(self.c(kind="whitespace")[0], "fast-path")

    def test_behavior_is_never_fast(self):
        self.assertEqual(self.c(kind="behavior")[0], "full-stopp")

    def test_schema_security_deploy_are_full(self):
        for kind in ("schema", "security", "deploy"):
            self.assertEqual(self.c(kind=kind)[0], "full-stopp")

    def test_two_files_are_full(self):
        self.assertEqual(self.c(files=2)[0], "full-stopp")

    def test_large_cosmetic_is_full(self):
        self.assertEqual(self.c(lines=51)[0], "full-stopp")

    def test_missing_verification_is_full(self):
        self.assertEqual(self.c(verify="")[0], "full-stopp")

    def test_trivial_verification_is_full(self):
        for command in ("true", ":", "echo", "echo ok"):
            self.assertEqual(self.c(verify=command)[0], "full-stopp")

    def test_format_requires_parsed_unchanged(self):
        self.assertEqual(self.c(kind="format")[0], "full-stopp")
        self.assertEqual(
            self.c(kind="format", parsed_unchanged=True)[0], "fast-path")

    def test_exception_conflict_halts(self):
        self.assertEqual(self.c(exception_conflict=True)[0], "halt")

    def test_missing_fact_halts(self):
        self.assertEqual(self.c(ambiguous=True)[0], "halt")

    def test_cli_json_and_exit_codes(self):
        result = run("--kind", "comment", "--files", "1", "--lines", "1",
                     "--verify-command", "make test", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["gate"], "fast-path")

        halt = run("--kind", "comment", "--files", "1", "--lines", "1",
                   "--verify-command", "make test", "--ambiguous")
        self.assertEqual(halt.returncode, 3)

        bad = run("--kind", "comment", "--files", "0", "--lines", "1",
                  "--verify-command", "make test")
        self.assertEqual(bad.returncode, 2)

        missing = run("--kind", "comment", "--verify-command", "make test")
        self.assertEqual(missing.returncode, 2)


if __name__ == "__main__":
    unittest.main()
