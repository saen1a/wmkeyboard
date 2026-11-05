#!/usr/bin/env python3
"""Tests for summarize_behavioral_results.py (no network)."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

TOOLING = Path(__file__).resolve().parent.parent
TOOL = TOOLING / "summarize_behavioral_results.py"

spec = importlib.util.spec_from_file_location("summarize", TOOL)
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


def write(path, skill, mode, seed, passed, score, tokens=10):
    data = {
        "skill": skill,
        "schema": "behavioral-run/2",
        "run": {"skill": skill, "mode": mode, "seed": seed},
        "results": [{
            "id": "c1", "passed": passed, "score": score,
            "executor_usage": {"total_tokens": tokens,
                               "prompt_cache_hit_tokens": 8,
                               "prompt_cache_miss_tokens": 2},
            "grader_usage": {"total_tokens": tokens},
        }],
    }
    path.write_text(json.dumps(data), encoding="utf-8")


class SummarizeTestCase(unittest.TestCase):
    def test_pairs_and_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "a.skill.grading.json", "alpha", "skill", 7, True, 1.0)
            write(root / "a.no-skill.grading.json", "alpha", "no-skill", 7, False, 0.5)
            rows = summary.load(root)
            result = summary.summarize(rows)
            self.assertEqual(result[0]["skill"], "alpha")
            self.assertEqual(result[0]["delta"], 0.5)
            self.assertEqual(result[0]["arms"]["skill"]["passed"], 1)
            self.assertEqual(result[0]["arms"]["skill"]["cache_rate"], 0.8)


if __name__ == "__main__":
    unittest.main()
