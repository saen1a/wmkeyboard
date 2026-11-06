#!/usr/bin/env python3
"""Tests for the harness telemetry validator."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLING = Path(__file__).resolve().parent.parent
TOOL = TOOLING / "check_harness_telemetry.py"


def record():
    return {
        "schema": "agent-prompts-harness/1",
        "run": {"model": "deepseek-flash", "provider": "deepseek",
                "harness": "fixture", "seed": 7,
                "timestamp_utc": "2026-10-23T00:00:00+00:00"},
        "turn": {"gate": "fast-path", "gate_reasons": ["comment-only"],
                 "files": 1, "lines": 1,
                 "verification": {"command": "make test", "exit_code": 0}},
        "usage": {"input_tokens": 100, "output_tokens": 20,
                  "reasoning_tokens": 0, "cache_hit_tokens": 80,
                  "cache_miss_tokens": 20},
        "outcome": {"status": "pass", "escaped_defect": False,
                    "operator_interventions": 0, "duration_ms": 100},
    }


def run(data):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "record.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return subprocess.run([sys.executable, str(TOOL), str(path)],
                              capture_output=True, text=True)


class TelemetryTestCase(unittest.TestCase):
    def test_minimal_valid_record(self):
        result = run(record())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_fast_path_requires_exit_zero(self):
        data = record()
        data["turn"]["verification"]["exit_code"] = 1
        result = run(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("exit_code 0", result.stdout)

    def test_fast_path_requires_one_file(self):
        data = record()
        data["turn"]["files"] = 2
        self.assertEqual(run(data).returncode, 1)

    def test_halt_must_be_halted(self):
        data = record()
        data["turn"]["gate"] = "halt"
        data["turn"]["verification"] = {"command": "", "exit_code": None}
        self.assertEqual(run(data).returncode, 1)

    def test_missing_usage_field(self):
        data = record()
        del data["usage"]["cache_hit_tokens"]
        result = run(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("cache_hit_tokens", result.stdout)


def v2_record():
    data = record()
    data["schema"] = "agent-prompts-harness/2"
    data["usage"]["cache_read_tokens"] = 60
    data["usage"]["cache_write_tokens"] = 20
    data["cache"] = {
        "prefix_hash": "a" * 16,
        "breakpoints": 1,
        "ttl": "5m",
        "tool_set_version": "tools-1",
    }
    data["run"]["cache_epoch"] = {
        "model": "deepseek-flash", "harness": "fixture",
        "toolset_sha256": "b" * 16, "doctrine_version": "1.3.1",
    }
    data["turn"]["prefix_hash"] = "a" * 16
    data["turn"]["first_divergent_layer"] = "system"
    return data


class TelemetryV2TestCase(unittest.TestCase):
    def test_valid_v2(self):
        self.assertEqual(run(v2_record()).returncode, 0)

    def test_v2_requires_cache(self):
        data = v2_record()
        del data["cache"]
        result = run(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("requires cache", result.stdout)

    def test_v2_breakpoint_budget(self):
        data = v2_record()
        data["cache"]["breakpoints"] = 5
        result = run(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("0..4", result.stdout)

    def test_v2_compaction_shape(self):
        data = v2_record()
        data["cache"]["compaction"] = {"reason": "long turn",
                                       "before_tokens": 1000}
        result = run(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("after_tokens", result.stdout)


if __name__ == "__main__":
    unittest.main()


class TelemetryStrictnessTestCase(unittest.TestCase):
    def test_unknown_key_fails(self):
        data = v2_record()
        data["extra_unknown_key"] = 1
        result = run(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown top-level key", result.stdout)

    def test_wrong_type_fails_without_traceback(self):
        data = v2_record()
        data["run"] = [1]
        result = run(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("run must be an object", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_compaction_requires_hit_rates(self):
        data = v2_record()
        data["cache"]["compaction"] = {"reason": "long turn",
                                       "before_tokens": 1000,
                                       "after_tokens": 400}
        result = run(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("hit_rate_before", result.stdout)

    def test_first_divergent_layer_vocabulary(self):
        data = v2_record()
        data["turn"]["first_divergent_layer"] = "wat"
        result = run(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("tools|system|skills|messages", result.stdout)


class TelemetryOutcomeTestCase(unittest.TestCase):
    def test_wrong_outcome_type_fails_without_traceback(self):
        data = v2_record()
        data["outcome"] = ["x"]
        result = run(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("outcome must be an object", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_cache_epoch_unknown_key_fails(self):
        data = v2_record()
        data["run"]["cache_epoch"]["BOGUS"] = 1
        result = run(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown run.cache_epoch key", result.stdout)


class TelemetryCacheParityTestCase(unittest.TestCase):
    def test_prefix_hashes_must_agree(self):
        data = v2_record()
        data["turn"]["prefix_hash"] = "c" * 16
        result = run(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("disagree", result.stdout)

    def test_layer_hashes_are_typed(self):
        data = v2_record()
        data["cache"]["layer_hashes"] = {"tools": 5}
        result = run(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("layer_hashes.tools", result.stdout)
