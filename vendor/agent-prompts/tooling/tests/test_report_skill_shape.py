#!/usr/bin/env python3
"""Fixture-based tests for tooling/report_skill_shape.py.

Each test builds a miniature skills tree in a temporary directory and drives
the report through its CLI. No test reads the real skills tree. All fixture
text is ASCII.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLING = Path(__file__).resolve().parent.parent
REPORT = TOOLING / "report_skill_shape.py"

ALPHA = """---
name: alpha
description: >-
  Calibrate widgets and tune widget metrics. Use when the user mentions widget
  calibration, widget drift, or widget metric regressions in a build.
rigid: true
---

# Alpha

Intro line.

## Module 1

Text.

## Module 2

Text.

## Doctrine position

Serves Plan.

## References

- `references/notes.md`
"""

BETA_HEAD = """---
name: beta
description: Deploy gadgets to servers and edge nodes.
---

# Beta

Intro.
"""


def write_skill(root, tree, name, text, refs=()):
    folder = root / "skills" / tree / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(text, encoding="utf-8")
    if refs:
        ref_dir = folder / "references"
        ref_dir.mkdir()
        for ref in refs:
            (ref_dir / ref).write_text("# note\n", encoding="utf-8")


def run_tool(root, *extra):
    return subprocess.run(
        [sys.executable, str(REPORT), "--root", str(root), *extra],
        capture_output=True, text=True)


class ReportSkillShapeTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def build(self):
        write_skill(self.root, "general", "alpha", ALPHA, refs=["notes.md"])
        # > 1,500 body tokens, > 8 H2 sections, no doctrine, no references.
        body = BETA_HEAD + "\n" + ("## Section\n\n" + ("word " * 150) + "\n") * 12
        write_skill(self.root, "shared", "beta", body)

    def test_json_report_has_metrics_and_advisories(self):
        self.build()
        result = run_tool(self.root, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["summary"]["skills"], 2)
        by_name = {row["name"]: row for row in data["skills"]}
        self.assertEqual(by_name["alpha"]["references"], 1)
        self.assertTrue(by_name["alpha"]["doctrine"])
        self.assertTrue(by_name["alpha"]["rigid"])
        self.assertGreater(by_name["alpha"]["description_words"], 10)
        beta = by_name["beta"]
        self.assertFalse(beta["doctrine"])
        self.assertFalse(beta["rigid"])
        self.assertGreater(beta["tokens_body"], 1500)
        self.assertGreater(beta["h2"], 8)
        self.assertEqual(
            sorted(beta["advisory"]),
            ["body-tokens", "h2-sections", "no-doctrine-position",
             "no-references"])
        self.assertEqual(data["skills"][0]["name"], "beta")

    def test_table_output_and_default_exit_zero(self):
        self.build()
        result = run_tool(self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skill-shape: 2 skills", result.stdout)
        self.assertIn("ADVISORY beta", result.stdout)
        self.assertIn("legend: doc=Doctrine position", result.stdout)

    def test_fail_on_advisory_promotes_breaches(self):
        self.build()
        result = run_tool(self.root, "--fail-on-advisory")
        self.assertEqual(result.returncode, 1)

    def test_clean_tree_passes_fail_on_advisory(self):
        write_skill(self.root, "general", "alpha", ALPHA, refs=["notes.md"])
        result = run_tool(self.root, "--fail-on-advisory")
        self.assertEqual(result.returncode, 0,
                         result.stdout + result.stderr)

    def test_missing_skills_dir_fails(self):
        result = run_tool(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL setup", result.stdout)

    def test_fenced_headings_are_not_sections(self):
        text = """---
name: fenced
description: Render examples with headings inside code fences.
---

# Fenced

Intro.

## Module 1

```markdown
## Example heading
## Another example
```

## Module 2

~~~text
## Tilde example
~~~

## Doctrine position

Serves Plan.
"""
        write_skill(self.root, "general", "fenced", text)
        result = run_tool(self.root, "--json")
        data = json.loads(result.stdout)
        row = data["skills"][0]
        self.assertEqual(row["h2"], 3)
        self.assertNotIn("h2-sections", row["advisory"])

    def test_indented_code_headings_are_not_sections(self):
        text = """---
name: indented
description: Show indented code blocks without counting their headings.
---

# Indented

Intro.

    ## Indented example

## Module 1

Body.
"""
        write_skill(self.root, "general", "indented", text)
        result = run_tool(self.root, "--json")
        row = json.loads(result.stdout)["skills"][0]
        self.assertEqual(row["h2"], 1)

    def test_singular_reference_directory_counts(self):
        write_skill(self.root, "general", "alpha", ALPHA, refs=["notes.md"])
        folder = self.root / "skills" / "general" / "alpha"
        # Move the directory to the singular spelling used by mcp-builder.
        (folder / "references").rename(folder / "reference")
        result = run_tool(self.root, "--json")
        row = json.loads(result.stdout)["skills"][0]
        self.assertEqual(row["references"], 1)

    def test_vendor_rows_do_not_fail_advisory_gate(self):
        vendor = BETA_HEAD.replace("name: beta", "name: frozen")
        vendor += "\n" + ("## Section\n\n" + ("word " * 150) + "\n") * 12
        write_skill(self.root, "vendor", "frozen", vendor)
        write_skill(self.root, "general", "alpha", ALPHA, refs=["notes.md"])
        result = run_tool(self.root, "--fail-on-advisory")
        self.assertEqual(result.returncode, 0,
                         result.stdout + result.stderr)

    def test_body_cap_boundary_is_exclusive(self):
        # A body exactly at the cap is not an advisory breach.
        head = "---\nname: edge\ndescription: Edge case for the body cap.\n---\n"
        prefix = "\n# Edge\n\n"
        pad = "x" * ((1500 * 4) - len(prefix.encode("utf-8")))
        write_skill(self.root, "general", "edge", head + prefix + pad)
        result = run_tool(self.root, "--json")
        row = json.loads(result.stdout)["skills"][0]
        self.assertLessEqual(row["tokens_body"], 1500)
        self.assertNotIn("body-tokens", row["advisory"])

    def test_missing_frontmatter_uses_directory_name(self):
        write_skill(self.root, "general", "bare", "# Bare\n\nNo frontmatter.\n")
        result = run_tool(self.root, "--json")
        row = json.loads(result.stdout)["skills"][0]
        self.assertEqual(row["name"], "bare")
        self.assertEqual(row["description_words"], 0)
        self.assertIn("description-words", row["advisory"])
        self.assertFalse(row["rigid"])

    def test_limit_truncates_table(self):
        self.build()
        result = run_tool(self.root, "--limit", "1")
        self.assertIn("... 1 more", result.stdout)


if __name__ == "__main__":
    unittest.main()
