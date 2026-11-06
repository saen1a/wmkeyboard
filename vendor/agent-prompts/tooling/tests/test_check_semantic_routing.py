#!/usr/bin/env python3
"""Fixture and unit tests for tooling/check_semantic_routing.py.

Every CLI test builds a miniature skill library and trigger-case set in a
temporary directory, then drives the tool with ``--judge fixture``. No test
reads the real skills tree and no test touches the network: the gateway path
is exercised only far enough to prove a missing key is a BLOCKED setup error.
All fixture text is ASCII.
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLING = Path(__file__).resolve().parent.parent
TOOL = TOOLING / "check_semantic_routing.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("check_semantic_routing",
                                                  TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


semantic = load_tool()

ALPHA = "Widget calibration and tuning of widget metrics"
BETA = "Gadget deployment and rollout to servers"
GAMMA = "Ledger accounting and reconciliation reports"


def write_skill(root, name, description):
    folder = root / "skills" / "shared" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(
        "---\nname: %s\ndescription: %s\n---\n\n# %s\n\nBody text.\n"
        % (name, description, name), encoding="utf-8")


def write_case(root, name, positives, negatives):
    cases = root / "evals" / "trigger"
    cases.mkdir(parents=True, exist_ok=True)
    data = {
        "skill": name,
        "positive": [{"prompt": prompt, "top_k": 3} for prompt in positives],
        "negative": negatives,
    }
    (cases / ("%s.json" % name)).write_text(json.dumps(data, indent=2),
                                            encoding="utf-8")


def write_fixture(root, responses):
    path = root / "judge-fixture.json"
    path.write_text(json.dumps({"responses": responses}, indent=2),
                    encoding="utf-8")
    return path


def run_tool(root, *extra, fixture=None, env=None):
    command = [sys.executable, str(TOOL), "--root", str(root)]
    if fixture is not None:
        command += ["--judge", "fixture", "--fixture", str(fixture)]
    command += list(extra)
    return subprocess.run(command, capture_output=True, text=True,
                          env=env or os.environ.copy(), check=False)


class ParseSelectionTestCase(unittest.TestCase):
    KNOWN = frozenset({"alpha", "beta", "gamma"})

    def test_fenced_object(self):
        ranked, unknown = semantic.parse_selection(
            '```json\n{"ranked": ["alpha", "beta"]}\n```', self.KNOWN, 3)
        self.assertEqual(ranked, ["alpha", "beta"])
        self.assertEqual(unknown, [])

    def test_bare_list_and_object_entries(self):
        for reply in ('["beta", "alpha"]',
                      '[{"id": "beta"}, {"skill": "alpha"}]'):
            ranked, _ = semantic.parse_selection(reply, self.KNOWN, 3)
            self.assertEqual(ranked, ["beta", "alpha"])

    def test_alternate_keys(self):
        ranked, _ = semantic.parse_selection(
            '{"skills": ["gamma"]}', self.KNOWN, 3)
        self.assertEqual(ranked, ["gamma"])

    def test_unknown_names_are_dropped_and_reported(self):
        ranked, unknown = semantic.parse_selection(
            '{"ranked": ["delta", "alpha", "delta"]}', self.KNOWN, 3)
        self.assertEqual(ranked, ["alpha"])
        self.assertEqual(unknown, ["delta"])

    def test_limit_is_applied(self):
        ranked, _ = semantic.parse_selection(
            '{"ranked": ["alpha", "beta", "gamma"]}', self.KNOWN, 2)
        self.assertEqual(ranked, ["alpha", "beta"])

    def test_garbage_raises(self):
        for reply in ("", "no json here", '{"ranked": []}', "{}"):
            with self.assertRaises(ValueError):
                semantic.parse_selection(reply, self.KNOWN, 3)


class TransportTestCase(unittest.TestCase):
    """The transport classifies provider failures without touching the wire."""

    def call_with(self, error):
        module = semantic
        original = module.urllib.request.urlopen

        def boom(request, timeout=None):
            raise error

        module.urllib.request.urlopen = boom
        try:
            with self.assertRaises(module.JudgeError) as caught:
                module.chat("https://example.invalid/v1", "key", "judge",
                            [{"role": "user", "content": "hi"}], 1.0, 64,
                            retries=1, sleep=lambda seconds: None)
        finally:
            module.urllib.request.urlopen = original
        return caught.exception

    def test_socket_timeout_is_transient(self):
        exc = self.call_with(TimeoutError("timed out"))
        self.assertNotIsInstance(exc, semantic.JudgeBlocked)
        self.assertIn("network error", str(exc))

    def test_401_is_blocked(self):
        error = semantic.urllib.error.HTTPError(
            "https://example.invalid/v1", 401, "Unauthorized", {},
            io.BytesIO(b'{"error":"bad key"}'))
        exc = self.call_with(error)
        self.assertIsInstance(exc, semantic.JudgeBlocked)
        self.assertIn("HTTP 401", str(exc))

    def test_429_is_transient(self):
        error = semantic.urllib.error.HTTPError(
            "https://example.invalid/v1", 429, "Too Many Requests", {},
            io.BytesIO(b'{"error":"rate limit"}'))
        exc = self.call_with(error)
        self.assertNotIsInstance(exc, semantic.JudgeBlocked)
        self.assertIn("HTTP 429", str(exc))

    def test_402_and_404_are_blocked(self):
        for code in (402, 404):
            error = semantic.urllib.error.HTTPError(
                "https://example.invalid/v1", code, "blocked", {},
                io.BytesIO(b"{}"))
            exc = self.call_with(error)
            self.assertIsInstance(exc, semantic.JudgeBlocked)
            self.assertIn("HTTP %d" % code, str(exc))


class FixtureReportTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for name, description in (("alpha", ALPHA), ("beta", BETA),
                                  ("gamma", GAMMA)):
            write_skill(self.root, name, description)
        write_case(
            self.root, "alpha",
            positives=["Calibrate the widget metrics for the run.",
                       "Tune widget calibration."],
            negatives=[
                {"prompt": "Roll the gadget out to servers.", "owner": "beta"},
                {"prompt": "Reconcile the ledger accounts.", "owner": "gamma"},
            ])
        write_case(
            self.root, "beta",
            positives=["Deploy the gadget to every server."],
            negatives=[{"prompt": "Tune the widget metrics.", "owner": "alpha"}])

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_run_reports_zero_findings(self):
        fixture = write_fixture(self.root, {
            "alpha/positive/1": ["alpha", "beta"],
            "alpha/positive/2": ["alpha"],
            "alpha/negative/1": ["beta", "gamma"],
            "alpha/negative/2": ["gamma"],
            "beta/positive/1": ["beta", "alpha"],
            "beta/negative/1": ["alpha"],
        })
        result = run_tool(self.root, fixture=fixture)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("false negatives", result.stdout)
        self.assertIn(": 0\n", result.stdout)
        self.assertIn("near-collisions: 0", result.stdout)
        self.assertIn("coverage: 6/6 prompts judged (100.0%)", result.stdout)

    def test_false_negative_is_advisory(self):
        fixture = write_fixture(self.root, {
            "alpha/positive/1": ["beta", "gamma"],
            "alpha/positive/2": ["alpha"],
            "alpha/negative/1": ["beta"],
            "alpha/negative/2": ["gamma"],
            "beta/positive/1": ["beta"],
            "beta/negative/1": ["alpha"],
        })
        result = run_tool(self.root, fixture=fixture)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("false negatives (positive prompt not in top-k): 1",
                      result.stdout)
        self.assertIn("FN alpha: alpha/positive/1", result.stdout)

    def test_rank_one_near_miss_is_reported(self):
        fixture = write_fixture(self.root, {
            "alpha/positive/1": ["beta", "alpha"],
            "alpha/positive/2": ["alpha"],
            "alpha/negative/1": ["beta"],
            "alpha/negative/2": ["gamma"],
            "beta/positive/1": ["beta"],
            "beta/negative/1": ["alpha"],
        })
        result = run_tool(self.root, fixture=fixture)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("rank-1 near misses (expected skill in top-k, not "
                      "first): 1", result.stdout)
        self.assertIn("NEAR alpha: alpha/positive/1", result.stdout)
        self.assertIn("false negatives (positive prompt not in top-k): 0",
                      result.stdout)

    def test_false_positive_and_missed_owner(self):
        fixture = write_fixture(self.root, {
            "alpha/positive/1": ["alpha"],
            "alpha/positive/2": ["alpha"],
            "alpha/negative/1": ["alpha", "gamma"],
            "alpha/negative/2": ["gamma"],
            "beta/positive/1": ["beta"],
            "beta/negative/1": ["alpha"],
        })
        result = run_tool(self.root, fixture=fixture)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("false positives (case skill routed for another "
                      "owner): 1", result.stdout)
        self.assertIn("FP alpha: alpha/negative/1 (owner beta)", result.stdout)
        self.assertIn("missed owners (negative prompt where owner did not "
                      "rank first): 1", result.stdout)
        self.assertIn("OWNER beta: alpha/negative/1", result.stdout)

    def test_mutual_cross_picks_are_a_near_collision(self):
        fixture = write_fixture(self.root, {
            "alpha/positive/1": ["beta"],
            "alpha/positive/2": ["beta"],
            "alpha/negative/1": ["beta"],
            "alpha/negative/2": ["gamma"],
            "beta/positive/1": ["alpha"],
            "beta/negative/1": ["alpha"],
        })
        result = run_tool(self.root, fixture=fixture)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("near-collisions: 1", result.stdout)
        self.assertIn("PAIR alpha <-> beta: cross-picks=3", result.stdout)

    def test_json_report_shape(self):
        fixture = write_fixture(self.root, {
            "alpha/positive/1": ["alpha"],
            "alpha/positive/2": ["beta"],
            "alpha/negative/1": ["beta"],
            "alpha/negative/2": ["gamma"],
            "beta/positive/1": ["beta"],
            "beta/negative/1": ["alpha"],
        })
        result = run_tool(self.root, "--json", fixture=fixture)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["skills"], 3)
        self.assertEqual(data["case_files"], 2)
        self.assertEqual(data["prompts"], 6)
        self.assertEqual(data["judged"], 6)
        self.assertAlmostEqual(data["coverage"], 1.0)
        self.assertEqual(data["judge"]["mode"], "fixture")
        rows = {row["skill"]: row for row in data["per_skill"]}
        self.assertEqual(rows["alpha"]["positives"], 2)
        self.assertEqual(rows["alpha"]["hit_at_k"], 1)
        self.assertEqual(len(data["false_negatives"]), 1)
        self.assertEqual(data["judge_errors"], [])

    def test_case_filter_limits_rows(self):
        fixture = write_fixture(self.root, {
            "alpha/positive/1": ["alpha"],
            "alpha/positive/2": ["alpha"],
            "alpha/negative/1": ["beta"],
            "alpha/negative/2": ["gamma"],
        })
        result = run_tool(self.root, "--case", "alpha", fixture=fixture)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("3 skills, 1 case files, 4 prompts", result.stdout)
        self.assertNotIn("beta/positive/1", result.stdout)

    def test_dry_run_makes_no_calls_and_needs_no_key(self):
        env = {key: value for key, value in os.environ.items()
               if key != "KILO_API_KEY"}
        result = run_tool(self.root, "--dry-run", env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("dry-run complete: no judge calls made", result.stdout)
        self.assertIn("prompts: 6 (3 positive, 3 negative)", result.stdout)
        self.assertIn("key env KILO_API_KEY", result.stdout)

    def test_missing_fixture_response_is_an_input_error(self):
        fixture = write_fixture(self.root, {
            "alpha/positive/1": ["alpha"],
        })
        result = run_tool(self.root, fixture=fixture)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("fixture has no response for alpha/positive/2",
                      result.stdout)

    def test_missing_gateway_key_is_blocked(self):
        env = {key: value for key, value in os.environ.items()
               if key != "KILO_API_KEY"}
        result = run_tool(self.root, "--dry-run", env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = run_tool(self.root, env=env)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("BLOCKED semantic-routing: KILO_API_KEY is not set",
                      result.stdout)

    def test_unreadable_fixture_is_a_setup_error(self):
        result = run_tool(self.root, fixture=self.root / "absent.json")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("FAIL setup: fixture", result.stdout)

    def test_unknown_owner_is_an_input_error(self):
        write_case(self.root, "gamma",
                   positives=["Reconcile ledgers."],
                   negatives=[{"prompt": "Tune widgets.", "owner": "delta"}])
        fixture = write_fixture(self.root, {"default": ["alpha"]})
        result = run_tool(self.root, fixture=fixture)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("FAIL input:", result.stdout)
        self.assertIn("unknown 'owner' 'delta'", result.stdout)

    def test_missing_skills_directory_is_a_setup_error(self):
        empty = Path(self._tmp.name) / "empty"
        empty.mkdir()
        result = subprocess.run(
            [sys.executable, str(TOOL), "--root", str(empty), "--dry-run"],
            capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("FAIL setup: skills directory not found", result.stdout)

    def test_unknown_skill_in_case_file_is_an_input_error(self):
        write_case(self.root, "delta", positives=["Anything."], negatives=[])
        fixture = write_fixture(self.root, {"default": ["alpha"]})
        result = run_tool(self.root, fixture=fixture)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("unknown skill 'delta'", result.stdout)


if __name__ == "__main__":
    unittest.main()
