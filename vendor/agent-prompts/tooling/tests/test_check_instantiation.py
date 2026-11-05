#!/usr/bin/env python3
"""Fixture-based tests for tooling/check_instantiation.py.

Every test builds a mini library (one template plus the two base fragments) and
a mini project (one live agent) in a temporary directory, then drives the tool
through its CLI with --template so only the fixture mapping is audited. The
tests never read the real templates.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLING = Path(__file__).resolve().parent.parent
CHECK = TOOLING / "check_instantiation.py"

TEMPLATE_ID = "orchestration-orchestrator"
TEMPLATE_REL = Path("agents") / "orchestration" / "orch-orchestrator.md"
AGENT_FILE = "orchestrator.md"

DOCTRINE_BODY = "Fixture doctrine line one.\nFixture doctrine line two.\n"
CONDUCT_BODY = "- Fixture conduct bullet.\n"

TEMPLATE_BODY = """<role>
Fixture role for {{PROJECT_ID}}.
</role>

<hard_rules>
- Work only in the fixture workspace.
- Keep the fixture tight.
</hard_rules>

<doctrine>
Fixture doctrine line one.
Fixture doctrine line two.
</doctrine>

<workflow>
Phase map (fixture), prose: Plan -- do the fixture thing, then verify it.
</workflow>

<conduct>
- Fixture conduct bullet.
</conduct>

<output>
REPORT: {status}
</output>
"""

CONFORMING_BODY = TEMPLATE_BODY.replace("{{PROJECT_ID}}", "fixture").replace(
    "Fixture role for fixture.", "Fixture role, project tuned.")


def write_library(root):
    fragments = Path(root) / "fragments"
    fragments.mkdir(parents=True, exist_ok=True)
    (fragments / "agent-doctrine.md").write_text(
        "<!-- fixture doctrine -->\n\n<doctrine>\n%s</doctrine>\n" % DOCTRINE_BODY,
        encoding="utf-8")
    (fragments / "agent-conduct.md").write_text(
        "<!-- fixture conduct -->\n\n<conduct>\n%s</conduct>\n" % CONDUCT_BODY,
        encoding="utf-8")
    template = Path(root) / TEMPLATE_REL
    template.parent.mkdir(parents=True, exist_ok=True)
    template.write_text(
        "---\nid: %s\nconduct_variant: kilo\n---\n\n%s" % (TEMPLATE_ID, TEMPLATE_BODY),
        encoding="utf-8")


def write_agent(project_root, body):
    agents = Path(project_root) / ".kilo" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / AGENT_FILE).write_text(body, encoding="utf-8")


def run_tool(project_root, library_root, *extra):
    return subprocess.run(
        [sys.executable, str(CHECK),
         "--project-root", str(project_root),
         "--library-root", str(library_root),
         "--template", TEMPLATE_ID, *extra],
        capture_output=True, text=True)


class CheckInstantiationTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.library = self.root / "library"
        self.project = self.root / "project"
        write_library(self.library)

    def tearDown(self):
        self._tmp.cleanup()

    def test_conforming_instantiation_passes(self):
        write_agent(self.project, CONFORMING_BODY)
        result = run_tool(self.project, self.library)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK orchestrator -> %s" % TEMPLATE_ID, result.stdout)
        self.assertNotIn("FAIL", result.stdout)

    def test_implicit_role_paragraph_passes(self):
        body = CONFORMING_BODY.replace(
            "<role>\nFixture role, project tuned.\n</role>\n\n",
            "Fixture role, project tuned.\n\n")
        write_agent(self.project, body)
        result = run_tool(self.project, self.library)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_block_fails(self):
        body = CONFORMING_BODY.replace(
            "<doctrine>\n%s</doctrine>\n\n" % DOCTRINE_BODY, "")
        write_agent(self.project, body)
        result = run_tool(self.project, self.library)
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL orchestrator:", result.stdout)
        self.assertIn("sequence differs", result.stdout)

    def test_output_not_last_fails(self):
        body = CONFORMING_BODY.replace(
            "<conduct>\n%s</conduct>\n\n<output>\nREPORT: {status}\n</output>\n"
            % CONDUCT_BODY,
            "<output>\nREPORT: {status}\n</output>\n\n<conduct>\n%s</conduct>\n"
            % CONDUCT_BODY)
        write_agent(self.project, body)
        result = run_tool(self.project, self.library)
        self.assertEqual(result.returncode, 1)
        self.assertIn("sequence differs", result.stdout)

    def test_content_after_output_fails(self):
        write_agent(self.project, CONFORMING_BODY + "\nTRAILING TEXT\n")
        result = run_tool(self.project, self.library)
        self.assertEqual(result.returncode, 1)
        self.assertIn("after </output>", result.stdout)

    def test_workflow_list_marker_fails(self):
        body = CONFORMING_BODY.replace(
            "Phase map (fixture), prose: Plan -- do the fixture thing, then verify it.",
            "- Plan the fixture.\n- Verify the fixture.")
        write_agent(self.project, body)
        result = run_tool(self.project, self.library)
        self.assertEqual(result.returncode, 1)
        self.assertIn("workflow block contains a list marker", result.stdout)

    def test_mutated_conduct_fails(self):
        body = CONFORMING_BODY.replace(
            CONDUCT_BODY, "- Changed conduct bullet.\n")
        write_agent(self.project, body)
        result = run_tool(self.project, self.library)
        self.assertEqual(result.returncode, 1)
        self.assertIn("byte-identical", result.stdout)

    def test_mutated_doctrine_fails(self):
        body = CONFORMING_BODY.replace(
            DOCTRINE_BODY, "Mutated doctrine text.\n")
        write_agent(self.project, body)
        result = run_tool(self.project, self.library)
        self.assertEqual(result.returncode, 1)
        self.assertIn("byte-identical", result.stdout)

    def test_missing_live_agent_fails(self):
        result = run_tool(self.project, self.library)
        self.assertEqual(result.returncode, 1)
        self.assertIn("live agent not found", result.stdout)

    def test_unknown_template_fails(self):
        write_agent(self.project, CONFORMING_BODY)
        result = subprocess.run(
            [sys.executable, str(CHECK),
             "--project-root", str(self.project),
             "--library-root", str(self.library),
             "--template", "does-not-exist"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown template id", result.stdout)


if __name__ == "__main__":
    unittest.main()
