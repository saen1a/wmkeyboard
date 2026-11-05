#!/usr/bin/env python3
"""Unit tests for the role-doctrine A/B helpers (no network calls)."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

TOOLING = Path(__file__).resolve().parent.parent
TOOL = TOOLING / "run_role_doctrine_experiment.py"

spec = importlib.util.spec_from_file_location("role_doctrine", TOOL)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class RoleDoctrineHelpersTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "fragments").mkdir()
        (self.root / "fragments" / "agent-doctrine.md").write_text(
            "<!-- fixture -->\n\n<doctrine>\nFULL DOCTRINE\n</doctrine>\n",
            encoding="utf-8")
        folder = self.root / "roles" / "engineering"
        folder.mkdir(parents=True)
        (folder / "eng-fixture.md").write_text(
            "---\nid: engineering-fixture\n---\n\n"
            "<role>\nFixture role.\n</role>\n\n"
            "<doctrine>\nFULL DOCTRINE\n</doctrine>\n\n"
            "<output>\nREPORT\n</output>\n", encoding="utf-8")
        (self.root / "evals" / "role-doctrine").mkdir(parents=True)
        (self.root / "evals" / "role-doctrine" / "compact-doctrine.txt").write_text(
            "COMPACT DOCTRINE\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_fragment_returns_doctrine_block(self):
        self.assertEqual(tool.load_fragment_doctrine(self.root),
                         "<doctrine>\nFULL DOCTRINE\n</doctrine>")

    def test_compact_is_wrapped_as_a_doctrine_block(self):
        self.assertEqual(tool.load_compact(self.root),
                         "<doctrine>\nCOMPACT DOCTRINE\n</doctrine>")

    def test_build_system_replaces_only_the_doctrine_block(self):
        system = tool.build_system("eng-fixture", self.root,
                                   "<doctrine>\nCOMPACT\n</doctrine>")
        self.assertIn("<doctrine>\nCOMPACT\n</doctrine>", system)
        self.assertNotIn("FULL DOCTRINE", system)
        self.assertIn("Fixture role.", system)
        self.assertIn("REPORT", system)


if __name__ == "__main__":
    unittest.main()
