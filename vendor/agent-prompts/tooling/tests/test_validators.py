#!/usr/bin/env python3
"""Fixture-based tests for tooling/validate_templates.py and check_fragments.py.

Every test builds its own tree in a temporary directory; the tests never read
the real fragments or the real templates. The validators are exercised through
their CLI with ``--root`` so the tests cover the documented interface.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLING = Path(__file__).resolve().parent.parent
VALIDATE = TOOLING / "validate_templates.py"
CHECK_FRAGMENTS = TOOLING / "check_fragments.py"

DOCTRINE_BODY = "Fixture doctrine line one.\nFixture doctrine line two.\n"
CONDUCT_BODY = "- Fixture conduct bullet.\n"
DSH_HA_CONDUCT_BODY = "- Fixture dsh-ha conduct bullet.\n"
DSH_PRESET_CONDUCT_BODY = "- Fixture dsh-preset conduct bullet.\n"
OMP_CONDUCT_BODY = "- Fixture omp conduct bullet.\n"

HANDOFF_LINE = "handoff: find the fixture handoff target\n"

FRONTMATTER = """---
id: engineering-min
name: Minimal Template
domain: engineering
purpose: Do the minimal thing for the fixture.
status: stable
version: {version}
source_archetypes: ["[NEW]"]
runtimes: {runtimes}
budget_tier: standard
tool_profile: {tool_profile}
owned_phases: {owned_phases}
handoff: find the fixture handoff target
evidence_style: none
required_slots: {required_slots}
optional_slots: {optional_slots}
conduct_variant: {conduct_variant}
fragment_versions: {{doctrine: 1.0.0, conduct: 1.0.0}}
suggested_projects: [containeromat]
created: 2026-09-19
updated: 2026-09-19
---
"""


def build_template(tool_profile="gated-write", required_slots="[PROJECT_ID]",
                   order=("role", "hard_rules", "doctrine", "workflow", "conduct", "output"),
                   hard_rules=("- Work only in the {{PROJECT_ID}} workspace.",),
                   doctrine_body=DOCTRINE_BODY,
                   conduct_body=CONDUCT_BODY,
                   output="REPORT: {status}",
                   role="Do the minimal thing for {{PROJECT_ID}}.",
                   workflow_body="Phase map (min), prose: Plan -- do the minimal thing.\n",
                   version="1.0.0",
                   runtimes="[kilo, dsh]",
                   owned_phases="[Plan]",
                   optional_slots="[]",
                   conduct_variant="kilo"):
    blocks = {
        "role": "<role>\n%s\n</role>" % role,
        "hard_rules": "<hard_rules>\n%s\n</hard_rules>" % "\n".join(hard_rules),
        "doctrine": "<doctrine>\n%s</doctrine>" % doctrine_body,
        "workflow": "<workflow>\n%s</workflow>" % workflow_body,
        "conduct": "<conduct>\n%s</conduct>" % conduct_body,
        "output": "<output>\n%s\n</output>" % output,
    }
    body = "\n\n".join(blocks[key] for key in order)
    frontmatter = FRONTMATTER.format(
        tool_profile=tool_profile,
        required_slots=required_slots,
        version=version,
        runtimes=runtimes,
        owned_phases=owned_phases,
        optional_slots=optional_slots,
        conduct_variant=conduct_variant,
    )
    return frontmatter + "\n" + body + "\n"


def write_fragments(root, doctrine_body=DOCTRINE_BODY, conduct_body=CONDUCT_BODY,
                    dsh_ha_body=DSH_HA_CONDUCT_BODY,
                    dsh_preset_body=DSH_PRESET_CONDUCT_BODY,
                    omp_body=OMP_CONDUCT_BODY):
    fragments = Path(root) / "fragments"
    fragments.mkdir(parents=True, exist_ok=True)
    for name, body in (
        ("agent-doctrine.md", doctrine_body),
        ("agent-conduct.md", conduct_body),
        ("agent-conduct.dsh-ha.md", dsh_ha_body),
        ("agent-conduct.dsh-preset.md", dsh_preset_body),
        ("agent-conduct.omp.md", omp_body),
    ):
        (fragments / name).write_text(
            "<!-- fixture -->\n\n<%s>\n%s</%s>\n"
            % ("doctrine" if name.endswith("doctrine.md") else "conduct", body,
               "doctrine" if name.endswith("doctrine.md") else "conduct"),
            encoding="utf-8")


def write_template(root, text, name="min.md"):
    directory = Path(root) / "roles" / "engineering"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(text, encoding="utf-8")


def run_validator(root, *extra):
    return subprocess.run(
        [sys.executable, str(VALIDATE), "--root", str(root), *extra],
        capture_output=True, text=True)


class ValidatorTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        write_fragments(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_valid_minimal_template_passes(self):
        write_template(self.root, build_template())
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("FAIL", result.stdout)

    def test_token_target_is_warn_not_fail(self):
        write_template(self.root, build_template(
            hard_rules=("- " + "word " * 3000,)))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WARN", result.stdout)
        self.assertIn("target", result.stdout)
        self.assertNotIn("FAIL", result.stdout)

    def test_wrong_block_order_fails(self):
        text = build_template(order=("role", "hard_rules", "output", "doctrine", "workflow", "conduct"))
        write_template(self.root, text)
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("block order", result.stdout)

    def test_mutated_doctrine_fails(self):
        write_template(self.root, build_template(doctrine_body="Mutated doctrine text.\n"))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("doctrine", result.stdout)
        self.assertIn("byte-identical", result.stdout)

    def test_mutated_conduct_fails(self):
        write_template(self.root, build_template(conduct_body="Mutated conduct text.\n"))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("conduct", result.stdout)
        self.assertIn("does not match", result.stdout)

    def test_over_budget_fails(self):
        bullets = tuple("- Rule number %d." % i for i in range(10))
        write_template(self.root, build_template(hard_rules=bullets))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("element budget", result.stdout)

    def test_budget_boundary_exact_cap_passes_cap_plus_one_fails(self):
        exact = tuple("- Rule number %d." % i for i in range(7))
        write_template(self.root, build_template(hard_rules=exact))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        over = tuple("- Rule number %d." % i for i in range(8))
        write_template(self.root, build_template(hard_rules=over))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("element budget", result.stdout)

    def test_doctrine_and_conduct_markers_excluded_from_budget(self):
        big_doctrine = "".join("- Doctrine line %d.\n" % i for i in range(20))
        big_conduct = "".join("- Conduct line %d.\n" % i for i in range(20))
        write_fragments(self.root, doctrine_body=big_doctrine, conduct_body=big_conduct)
        write_template(self.root, build_template(
            doctrine_body=big_doctrine, conduct_body=big_conduct))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_workflow_list_marker_fails(self):
        write_template(self.root, build_template(
            workflow_body="- Step one.\n- Step two.\n"))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("workflow block must be prose", result.stdout)

    def test_content_after_output_fails(self):
        write_template(self.root, build_template() + "\nTRAILING TEXT\n")
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("after </output>", result.stdout)

    def test_missing_required_handoff_fails(self):
        text = build_template().replace(HANDOFF_LINE, "")
        write_template(self.root, text)
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing required frontmatter key: handoff", result.stdout)

    def test_invalid_owned_phase_fails(self):
        write_template(self.root, build_template(owned_phases="[Deploy]"))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("owned_phases", result.stdout)

    def test_invalid_runtime_fails(self):
        write_template(self.root, build_template(runtimes="[kilo, python]"))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("runtimes", result.stdout)

    def test_invalid_version_fails(self):
        write_template(self.root, build_template(version="1.0"))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("version", result.stdout)

    def test_optional_slots_string_fails(self):
        write_template(self.root, build_template(optional_slots="MODEL_HINT"))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("optional_slots must be an inline list", result.stdout)

    def test_conduct_variant_dsh_ha_matches_fragment(self):
        write_template(self.root, build_template(
            conduct_variant="dsh-ha", conduct_body=DSH_HA_CONDUCT_BODY))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_conduct_variant_dsh_preset_matches_fragment(self):
        write_template(self.root, build_template(
            conduct_variant="dsh-preset", conduct_body=DSH_PRESET_CONDUCT_BODY))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_conduct_variant_omp_matches_fragment(self):
        write_template(self.root, build_template(
            conduct_variant="omp", conduct_body=OMP_CONDUCT_BODY))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_conduct_variant_omp_with_dsh_preset_block_fails(self):
        write_template(self.root, build_template(
            conduct_variant="omp", conduct_body=DSH_PRESET_CONDUCT_BODY))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not match", result.stdout)

    def test_conduct_variant_kilo_with_dsh_ha_block_fails(self):
        write_template(self.root, build_template(
            conduct_variant="kilo", conduct_body=DSH_HA_CONDUCT_BODY))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("conduct", result.stdout)
        self.assertIn("does not match", result.stdout)

    def test_non_ascii_fails(self):
        write_template(self.root, build_template(role="Do the minimal thing for {{PROJECT_ID}} caf\u00e9."))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("non-ASCII", result.stdout)

    def test_counter_fails(self):
        write_template(self.root, build_template(hard_rules=("- Work only after pass 2 of 3 gates.",)))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("control-flow counter", result.stdout)

    def test_read_only_output_with_git_push_fails(self):
        write_template(self.root, build_template(
            tool_profile="read-only", output="REPORT: then git push to main"))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("mutating verb", result.stdout)
        self.assertIn("git push", result.stdout)

    def test_read_only_output_prose_write_fails(self):
        write_template(self.root, build_template(
            tool_profile="read-only",
            output='State the next gate. Write exactly "none" for an empty section.'))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("mutating verb", result.stdout)
        self.assertIn("Write", result.stdout)

    def test_read_only_output_prose_output_exactly_passes(self):
        write_template(self.root, build_template(
            tool_profile="read-only",
            output='State the next gate. Output exactly "none" for an empty section.'))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_non_utf8_file_reports_filename(self):
        directory = Path(self.root) / "roles" / "engineering"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "broken.md").write_bytes(b"---\nid: x\n---\n\xff\xfe\n")
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("broken.md", result.stdout)
        self.assertNotIn("FAIL FAIL", result.stdout)

    def test_undeclared_slot_fails(self):
        write_template(self.root, build_template(
            hard_rules=("- Work only in the {{PROJECT_ID}} workspace and {{NOT_DECLARED}}.",)))
        result = run_validator(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("{{NOT_DECLARED}}", result.stdout)

    def test_instantiated_residue_only_fails_in_instantiate_mode(self):
        text = build_template(required_slots="[PROJECT_ID]")
        write_template(self.root, text, name="min.instantiated.md")
        clean = run_validator(self.root)
        self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
        dirty = run_validator(self.root, "--instantiate")
        self.assertEqual(dirty.returncode, 1)
        self.assertIn("slot residue", dirty.stdout)

    def test_instantiate_scans_every_discovered_file(self):
        write_template(self.root, build_template(required_slots="[PROJECT_ID]"))
        clean = run_validator(self.root)
        self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
        dirty = run_validator(self.root, "--instantiate")
        self.assertEqual(dirty.returncode, 1)
        self.assertIn("slot residue", dirty.stdout)



    def test_fragment_growth_is_measured_per_fragment_and_variant(self):
        """Growth is the fragment's own delta over its baseline, for the conduct
        variant the carrier embeds (doctrine and kilo/omp conduct differ)."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "vt_under_test", Path(__file__).resolve().parents[1] / "validate_templates.py")
        vt = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vt)
        root = Path(self.root)
        (root / "fragments").mkdir(parents=True, exist_ok=True)
        doctrine = root / "fragments" / "agent-doctrine.md"
        conduct = root / "fragments" / "agent-conduct.md"
        omp = root / "fragments" / "agent-conduct.omp.md"
        doctrine.write_text("<doctrine>\n" + ("word " * 400) + "\n</doctrine>\n")
        conduct.write_text("<conduct>\n" + ("word " * 190 * 4) + "\n</conduct>\n")
        omp.write_text("<conduct>\n" + ("word " * 260 * 4) + "\n</conduct>\n")
        doctrine_growth = vt._fragment_growth(root, "kilo") - 0
        self.assertGreater(doctrine_growth, 300)  # 400 words over the 225 baseline
        self.assertEqual(vt._fragment_growth(root, "kilo"),
                         vt._fragment_growth(root, "kilo"),
                         "the measurement must be deterministic")
        omp_growth = vt._fragment_growth(root, "omp")
        self.assertNotEqual(omp_growth, vt._fragment_growth(root, "dsh-ha"),
                            "each conduct variant has its own baseline")

    def test_frontmatter_must_yaml_parse(self):
        """A bare ': ' in a plain scalar parses in the minimal parser and breaks
        every real YAML loader; the validator must reject it."""
        write_template(self.root, build_template().replace(
            "purpose: ", "purpose: note that x: y and ", 1))
        result = run_validator(self.root)
        assert result.returncode == 1
        assert "does not YAML-parse" in result.stdout or "not a YAML mapping" in result.stdout

    @staticmethod
    def _warnings_for(result, needle):
        return sum(1 for line in result.stdout.splitlines()
                   if line.startswith("WARN") and needle in line)


class FragmentTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        self.upstream = Path(self._tmp.name) / "upstream"
        (self.root / "fragments").mkdir(parents=True)
        (self.upstream).mkdir(parents=True)
        for name, content in (
            ("agent-doctrine.md", "<!-- fixture -->\n\n<doctrine>\n%s</doctrine>\n" % DOCTRINE_BODY),
            ("agent-conduct.md", "<!-- fixture -->\n\n<conduct>\n%s</conduct>\n" % CONDUCT_BODY),
        ):
            (self.root / "fragments" / name).write_text(content, encoding="utf-8")
            (self.upstream / name).write_text(content, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def run_check(self):
        return subprocess.run(
            [sys.executable, str(CHECK_FRAGMENTS),
             "--root", str(self.root), "--upstream", str(self.upstream)],
            capture_output=True, text=True)

    def test_identical_fragments_pass(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK agent-conduct.md", result.stdout)
        self.assertNotIn("agent-doctrine.md", result.stdout)

    def test_mutated_fragment_fails(self):
        (self.upstream / "agent-conduct.md").write_text(
            "<!-- fixture -->\n\n<conduct>\nChanged upstream.\n</conduct>\n", encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("DIFF agent-conduct.md", result.stdout)

    def test_upstream_ignores_doctrine(self):
        (self.upstream / "agent-doctrine.md").write_text(
            "<!-- fixture -->\n\n<doctrine>\nChanged upstream.\n</doctrine>\n", encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("agent-doctrine.md", result.stdout)

    def write_manifest(self, root, entries):
        import json
        manifest = {"version": "1.0.0", "fragments": entries}
        path = root / "tooling"
        path.mkdir(parents=True, exist_ok=True)
        (path / "fragments.manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path / "fragments.manifest.json"

    def manifest_entries(self):
        import hashlib
        entries = {}
        for name in ("agent-doctrine.md", "agent-conduct.md"):
            data = (self.root / "fragments" / name).read_bytes()
            entries[name] = {"sha256": hashlib.sha256(data).hexdigest(), "version": "1.0.0"}
        return entries

    def run_manifest_check(self, entries):
        import json, sys
        manifest = {"version": "1.0.0", "fragments": entries}
        manifest_path = self.root / "tooling" / "fragments.manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                 encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(CHECK_FRAGMENTS),
             "--root", str(self.root), "--manifest", str(manifest_path)],
            capture_output=True, text=True)

    def test_manifest_mode_passes_on_intact_fragments(self):
        result = self.run_manifest_check(self.manifest_entries())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK agent-doctrine.md", result.stdout)

    def test_manifest_mode_detects_mutation(self):
        entries = self.manifest_entries()
        (self.root / "fragments" / "agent-conduct.md").write_text(
            "<!-- fixture -->\n\n<conduct>\nMutated body.\n</conduct>\n", encoding="utf-8")
        result = self.run_manifest_check(entries)
        self.assertEqual(result.returncode, 1)
        self.assertIn("DIFF agent-conduct.md: sha256 mismatch", result.stdout)

    def test_whitespace_only_upstream_mutation_fails(self):
        original = (self.root / "fragments" / "agent-conduct.md").read_text(encoding="utf-8")
        (self.upstream / "agent-conduct.md").write_text(
            original.replace("Fixture conduct bullet.", "Fixture  conduct bullet."),
            encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("DIFF agent-conduct.md", result.stdout)


if __name__ == "__main__":
    unittest.main()
