#!/usr/bin/env python3
"""Unit tests for the non-network helpers in run_behavioral_evals.py.

The API path is not exercised here; these tests pin the paired-mode contract:
the baseline must not contain the skill text, and each mode writes its own
metadata-bearing result file.
"""

import importlib.util
import types
import unittest
from pathlib import Path

TOOLING = Path(__file__).resolve().parent.parent
RUNNER = TOOLING / "run_behavioral_evals.py"

spec = importlib.util.spec_from_file_location("run_behavioral_evals", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class PairedModeTestCase(unittest.TestCase):
    def args(self, **overrides):
        values = {
            "executor_model": "executor-model",
            "grader_model": "grader-model",
            "base_url": "https://example.invalid/v1",
            "seed": 7,
        }
        values.update(overrides)
        return types.SimpleNamespace(**values)

    def test_skill_mode_returns_skill_text(self):
        self.assertEqual(runner.executor_system("SKILL BODY", "skill"),
                         "SKILL BODY")

    def test_no_skill_mode_is_neutral_and_never_leaks_skill_text(self):
        system = runner.executor_system("SKILL BODY", "no-skill")
        self.assertEqual(system, runner.BASELINE_SYSTEM)
        self.assertNotIn("SKILL BODY", system)

    def test_result_paths_are_per_mode(self):
        base = Path("/tmp/results")
        skill = runner.result_path(base, "alpha", "skill")
        baseline = runner.result_path(base, "alpha", "no-skill")
        self.assertNotEqual(skill, baseline)
        self.assertEqual(skill.name, "alpha.skill.grading.json")
        self.assertEqual(baseline.name, "alpha.no-skill.grading.json")

    def test_run_metadata_names_model_harness_seed_and_time(self):
        meta = runner.run_metadata(self.args(), "alpha", "skill")
        self.assertEqual(meta["skill"], "alpha")
        self.assertEqual(meta["mode"], "skill")
        self.assertEqual(meta["executor_model"], "executor-model")
        self.assertEqual(meta["grader_model"], "grader-model")
        self.assertEqual(meta["harness"], "openai-compatible-chat")
        self.assertEqual(meta["seed"], 7)
        self.assertEqual(meta["temperature"], 0)
        self.assertTrue(meta["timestamp_utc"].endswith("+00:00"))
        self.assertNotIn("api_key", meta)

    def test_run_case_no_skill_uses_baseline_and_records_usage(self):
        calls = []

        def fake_chat(base_url, api_key, model, messages, timeout, max_tokens,
                      seed=None, retries=2, extra_headers=None):
            calls.append(messages)
            if len(calls) == 1:
                return "baseline answer", {"total_tokens": 11}
            return ('{"results": [{"expectation": "x", "met": true, '
                    '"reason": "ok"}], "score": 1.0}', {"total_tokens": 5})

        args = types.SimpleNamespace(
            executor_model="executor-model", grader_model="grader-model",
            base_url="https://example.invalid/v1", seed=7, timeout=1,
            max_tokens=10, grader_max_tokens=10)
        case = {"id": "c1", "kind": "dialogue", "prompt": "P",
                "expectations": ["x"]}
        original = runner.chat
        runner.chat = fake_chat
        try:
            result = runner.run_case("alpha", "SKILL BODY", case, args, "k",
                                     "no-skill")
        finally:
            runner.chat = original
        self.assertEqual(calls[0][0]["content"], runner.BASELINE_SYSTEM)
        self.assertNotIn("SKILL BODY", calls[0][0]["content"])
        self.assertEqual(result["mode"], "no-skill")
        self.assertEqual(result["executor_usage"], {"total_tokens": 11})
        self.assertEqual(result["grader_usage"], {"total_tokens": 5})
        self.assertTrue(result["passed"])


if __name__ == "__main__":
    unittest.main()


class MandatedRouteTest(unittest.TestCase):
    """Pin the operator's mandated route and the header plumbing it needs."""

    def test_defaults_are_the_mandated_route(self):
        self.assertEqual(runner.DEFAULT_BASE_URL,
                         "https://opencode.ai/inference/go/v1")
        self.assertEqual(runner.DEFAULT_KEY_ENV, "OPENCODE_API_KEY")
        self.assertEqual(runner.DEFAULT_MODEL, "deepseek-v4.1-flash")

    def test_parse_header_accepts_equals_and_colon(self):
        self.assertEqual(runner.parse_header("A=b"), ("A", "b"))
        self.assertEqual(runner.parse_header("A: b"), ("A", "b"))

    def test_parse_header_rejects_garbage(self):
        with self.assertRaises(SystemExit):
            runner.parse_header("nonsense")

    def test_user_agent_is_never_python_urllib(self):
        headers = runner.request_headers(env={})
        self.assertIn("User-Agent", headers)
        self.assertNotIn("Python-urllib", headers["User-Agent"])

    def test_session_header_from_argument(self):
        headers = runner.request_headers(session_header=True, session_id="abc", env={})
        self.assertEqual(headers["x-opencode-session"], "abc")

    def test_session_header_from_environment(self):
        headers = runner.request_headers(session_header=True,
                                         env={"OPENCODE_SESSION_ID": "env-id"})
        self.assertEqual(headers["x-opencode-session"], "env-id")

    def test_session_header_without_a_value_stops(self):
        with self.assertRaises(SystemExit):
            runner.request_headers(session_header=True, env={})

    def test_extra_header_overrides_the_default_user_agent(self):
        headers = runner.request_headers(["User-Agent=custom/9"], env={})
        self.assertEqual(headers["User-Agent"], "custom/9")


class ScoreDerivationTest(unittest.TestCase):
    """The score is the fraction of votes, never the grader's own number."""

    def test_score_follows_the_votes(self):
        graded = {"results": [{"expectation": "a", "met": True, "reason": "ok"},
                              {"expectation": "b", "met": True, "reason": "ok"},
                              {"expectation": "c", "met": False, "reason": "no"}],
                  "score": 0.3333}
        results, score, claimed = runner.derive_score(graded)
        self.assertAlmostEqual(score, 2 / 3)
        self.assertEqual(claimed, 0.3333)

    def test_agreeing_grader_score_is_not_flagged(self):
        graded = {"results": [{"expectation": "a", "met": True, "reason": "ok"}],
                  "score": 1.0}
        results, score, claimed = runner.derive_score(graded)
        self.assertEqual(score, 1.0)
        self.assertIsNone(claimed)
