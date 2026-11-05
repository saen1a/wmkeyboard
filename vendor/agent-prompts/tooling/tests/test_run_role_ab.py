#!/usr/bin/env python3
"""Tests for the role-body A/B helpers."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

TOOLING = Path(__file__).resolve().parent.parent
TOOL = TOOLING / "run_role_ab.py"

spec = importlib.util.spec_from_file_location("role_ab", TOOL)
ab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ab)


class RoleABTestCase(unittest.TestCase):
    def test_paths_and_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "roles" / "engineering").mkdir(parents=True)
            (root / "roles" / "engineering" / "eng-x.md").write_text(
                "role body\n", encoding="utf-8")
            (root / "evals" / "role-ab" / "candidates").mkdir(parents=True)
            (root / "evals" / "role-ab" / "candidates" / "eng-x.md").write_text(
                "candidate\n", encoding="utf-8")
            (root / "evals" / "role-ab" / "tasks").mkdir(parents=True)
            (root / "evals" / "role-ab" / "tasks" / "eng-x.json").write_text(
                json.dumps({"prompt": "P", "expectations": ["E"]}),
                encoding="utf-8")
            self.assertEqual(ab.role_path(root, "eng-x").read_text(),
                             "role body\n")
            self.assertEqual(ab.candidate_path(root, "eng-x", root / "evals" / "role-ab" / "candidates").read_text(),
                             "candidate\n")
            self.assertEqual(ab.task(root, "eng-x")["prompt"], "P")

    def test_fill_slots_replaces_known_and_unknown(self):
        text = ab.fill_slots("Use {{PROJECT_ID}} and {{UNKNOWN_SLOT}}.")
        self.assertEqual(text, "Use fixture-project and project value for unknown_slot.")

    def test_missing_candidate_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                ab.candidate_path(Path(tmp), "missing", Path(tmp) / "evals" / "role-ab" / "candidates")

    def test_task_from_custom_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            alt = root / "evals" / "role-ab" / "tasks-injection"
            alt.mkdir(parents=True)
            (alt / "eng-x.json").write_text(
                json.dumps({"prompt": "INJECT", "expectations": ["E"]}),
                encoding="utf-8")
            self.assertEqual(ab.task(root, "eng-x", alt)["prompt"], "INJECT")
            with self.assertRaises(SystemExit):
                ab.task(root, "eng-x")

    def test_context_arm_prepends_context(self):
        arm = ab.with_context("  # router\n\nUse make test.\n", "role body\n")
        self.assertEqual(arm, "# router\n\nUse make test.\n\nrole body\n")

    def test_load_tasks_returns_legacy_single_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "evals" / "role-ab" / "tasks"
            base.mkdir(parents=True)
            (base / "eng-x.json").write_text(
                json.dumps({"prompt": "P", "expectations": ["E"]}),
                encoding="utf-8")
            self.assertEqual(ab.load_tasks(root, "eng-x"),
                             [(None, {"prompt": "P", "expectations": ["E"]})])
            self.assertEqual(ab.discover_roles(base), ["eng-x"])

    def test_load_tasks_returns_several_cases_per_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "evals" / "role-ab" / "tasks-foreground"
            base.mkdir(parents=True)
            for stem in ("02-second", "01-first", "03-third"):
                (base / ("%s.json" % stem)).write_text(
                    json.dumps({"role": "orch-x", "prompt": stem,
                                "expectations": ["E"]}), encoding="utf-8")
            (base / "04-other-role.json").write_text(
                json.dumps({"role": "orch-y", "prompt": "other",
                            "expectations": ["E"]}), encoding="utf-8")
            entries = ab.load_tasks(root, "orch-x", base)
            self.assertEqual([task_id for task_id, _ in entries],
                             ["01-first", "02-second", "03-third"])
            self.assertEqual([fixture["prompt"] for _, fixture in entries],
                             ["01-first", "02-second", "03-third"])
            self.assertEqual(ab.discover_roles(base), ["orch-x", "orch-y"])

    def test_load_tasks_rejects_a_fixture_without_expectations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "evals" / "role-ab" / "tasks"
            base.mkdir(parents=True)
            (base / "01-empty.json").write_text(
                json.dumps({"role": "eng-x", "prompt": "P",
                            "expectations": []}), encoding="utf-8")
            with self.assertRaises(SystemExit):
                ab.load_tasks(root, "eng-x")

    def test_dry_run_lists_every_task_of_a_multi_task_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "agents" / "orch").mkdir(parents=True)
            (root / "agents" / "orch" / "orch-x.md").write_text(
                "role body\n", encoding="utf-8")
            base = root / "evals" / "role-ab" / "tasks-foreground"
            base.mkdir(parents=True)
            for stem in ("01-a", "02-b"):
                (base / ("%s.json" % stem)).write_text(
                    json.dumps({"role": "orch-x", "prompt": stem,
                                "expectations": ["E"]}), encoding="utf-8")
            context = root / "context.md"
            context.write_text("# policy\n", encoding="utf-8")
            code = ab.main(["--root", str(root), "--roles", "orch-x",
                            "--tasks-dir", str(base),
                            "--context-file", str(context), "--dry-run"])
            self.assertEqual(code, 0)

    def test_display_path_is_repo_relative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(ab.display_path(root / "evals" / "x", root), "evals/x")
            self.assertEqual(ab.display_path(Path("/outside/x"), root), "/outside/x")

    def test_parse_header_accepts_colons_and_rejects_bad_lines(self):
        self.assertEqual(ab.parse_header("X-Trace: a:b:c"),
                         ("X-Trace", "a:b:c"))
        self.assertEqual(ab.parse_header("  User-Agent :  ab/1.0  "),
                         ("User-Agent", "ab/1.0"))
        for bad in ("no-colon", ": empty-name", "X: a\nb", "X: a\rb"):
            with self.assertRaises(SystemExit):
                ab.parse_header(bad)

    def test_request_headers_merge_generic_and_session(self):
        headers = ab.request_headers(
            ["User-Agent: ab/1.0", "X-Trace: t"],
            session_header=True, session_id="ses_123", env={})
        self.assertEqual(headers, {"User-Agent": "ab/1.0", "X-Trace": "t",
                                   "x-opencode-session": "ses_123"})
        self.assertEqual(ab.request_headers([]), {})

    def test_session_header_falls_back_to_the_environment(self):
        headers = ab.request_headers([], session_header=True,
                                     env={"OPENCODE_SESSION_ID": "ses_env"})
        self.assertEqual(headers, {"x-opencode-session": "ses_env"})
        with self.assertRaises(SystemExit):
            ab.request_headers([], session_header=True, env={})

    def test_run_one_forwards_headers_to_both_models(self):
        import types
        seen = []
        original = ab.RUNNER.chat

        def fake_chat(base_url, api_key, model, messages, timeout, max_tokens,
                      seed=None, extra_headers=None):
            seen.append((model, extra_headers))
            if len(seen) == 1:
                return "answer", {"completion_tokens": 2,
                                  "finish_reason": "stop"}
            return json.dumps({"results": [{"expectation": "E (paraphrased)",
                                            "met": True}]}), {}

        ab.RUNNER.chat = fake_chat
        try:
            args = types.SimpleNamespace(
                base_url="http://example.invalid/v1", executor_model="exec",
                grader_model="grade", timeout=1, max_tokens=16,
                grader_max_tokens=16, seed=311)
            result = ab.run_one(
                "orch-x", "body", {"prompt": "P", "expectations": ["E"]},
                args, "key", "current", headers={"x-opencode-session": "s"})
        finally:
            ab.RUNNER.chat = original
        self.assertTrue(result["passed"])
        self.assertEqual(seen, [("exec", {"x-opencode-session": "s"}),
                                ("grade", {"x-opencode-session": "s"})])
        entry = result["expectations"][0]
        self.assertEqual(entry["expectation"], "E")
        self.assertEqual(entry["grader_expectation"], "E (paraphrased)")


if __name__ == "__main__":
    unittest.main()
