#!/usr/bin/env python3
"""Tests for the tool-enabled role harness helpers (no network)."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

TOOLING = Path(__file__).resolve().parent.parent
TOOL = TOOLING / "run_role_tools_ab.py"

spec = importlib.util.spec_from_file_location("role_tools", TOOL)
tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools)


class RoleToolsTestCase(unittest.TestCase):
    def test_command_allowlist(self):
        self.assertTrue(tools.allowed("python3 scripts/verify_ascii.py README.md"))
        self.assertTrue(tools.allowed("git status --porcelain"))
        self.assertFalse(tools.allowed("curl example.com"))
        self.assertFalse(tools.allowed("git push"))

    def test_read_file_blocks_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "a.txt").write_text("ok", encoding="utf-8")
            self.assertEqual(
                tools.execute_tool("read_file", {"path": "a.txt"}, workspace), "ok")
            self.assertIn(
                "escapes workspace",
                tools.execute_tool("read_file", {"path": "../x"}, workspace))

    def test_disallowed_command_is_not_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = tools.execute_tool(
                "run_command", {"command": "echo nope"}, Path(tmp))
            self.assertIn("not allowed", result)


if __name__ == "__main__":
    unittest.main()
