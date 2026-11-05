#!/usr/bin/env python3
"""Tests for the old-vs-new skill-body A/B helpers."""

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

TOOLING = Path(__file__).resolve().parent.parent
TOOL = TOOLING / "run_refactor_ab.py"

spec = importlib.util.spec_from_file_location("refactor_ab", TOOL)
ab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ab)


class RefactorABTestCase(unittest.TestCase):
    def test_old_body_reads_the_ref_not_the_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "t@example.invalid"],
                           cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True)
            path = root / "skills" / "shared" / "alpha" / "SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_text("old body\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "old"], cwd=root, check=True)
            path.write_text("new body\n", encoding="utf-8")

            self.assertEqual(ab.old_body(root, "HEAD", "skills/shared/alpha/SKILL.md"),
                             "old body\n")
            self.assertEqual(path.read_text(encoding="utf-8"), "new body\n")

    def test_load_cases_requires_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "evals" / "behavioral").mkdir(parents=True)
            (root / "evals" / "behavioral" / "alpha.json").write_text(
                json.dumps({"skill": "alpha", "evals": [{"id": "c1"}]}),
                encoding="utf-8")
            self.assertEqual(ab.load_cases(root, "alpha")[0]["id"], "c1")


if __name__ == "__main__":
    unittest.main()
