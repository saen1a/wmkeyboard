#!/usr/bin/env python3
"""Offline tests for the cache-baseline runner (no network)."""

import importlib.util
import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
TOOL = ROOT / "tooling" / "run_cache_baseline.py"
FIXTURE = ROOT / "evals" / "cache" / "fixtures" / "kilo-anthropic-5m-sample.json"

spec = importlib.util.spec_from_file_location("cache_baseline", TOOL)
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)


def usage(cached=0, created=1479, cost=0.000187, prompt=1483, out=4):
    return {
        "prompt_tokens": prompt,
        "completion_tokens": out,
        "cost": cost,
        "prompt_tokens_details": {"cached_tokens": cached},
        "cache_creation_input_tokens": created,
    }


def ok(cached=0, created=1479, cost=0.000187, content="I keep the setting coherent.",
       prompt=1483):
    return {"usage": usage(cached=cached, created=created, cost=cost, prompt=prompt),
            "content": content, "latency_ms": 1200}


def sample_responses():
    responses = []
    for _ in range(3):
        responses.append(ok())
        responses.append(ok(cached=1479, created=0, cost=1.7e-05))
        responses.append(ok(cached=1479, created=0, cost=2.4e-05, content="Continuity first."))
    return responses


def write_fixture(path, responses):
    Path(path).write_text(json.dumps({"model": cb.DEFAULT_MODEL,
                                      "responses": responses}), encoding="utf-8")


class PlanTestCase(unittest.TestCase):
    def test_plan_shape(self):
        plan = cb.plan_requests([401, 409, 419], turns=2)
        self.assertEqual(len(plan), 9)
        self.assertEqual([kind for _, _, kind in plan],
                         ["cold", "warm", "continuation"] * 3)
        self.assertEqual(cb.plan_requests([7], turns=1),
                         [(7, 1, "cold"), (7, 1, "warm")])

    def test_parse_seeds(self):
        self.assertEqual(cb.parse_seeds("401, 409,419"), [401, 409, 419])
        with self.assertRaises(SystemExit):
            cb.parse_seeds("")
        with self.assertRaises(SystemExit):
            cb.parse_seeds("a,b")

    def test_body_strips_frontmatter(self):
        text = "---\nid: x\n---\nbody\n"
        self.assertEqual(cb.body_of(text), "body\n")
        self.assertEqual(cb.body_of("plain\n"), "plain\n")

    def test_prefix_hash_is_stable_and_content_addressed(self):
        first = cb.sha256_text("prefix")
        self.assertEqual(first, cb.sha256_text("prefix"))
        self.assertNotEqual(first, cb.sha256_text("prefix "))
        self.assertEqual(len(first), 64)

    def test_load_profile_reads_the_committed_table(self):
        row = cb.load_profile("anthropic-5m")
        self.assertEqual(row["min_tokens"], 512)
        self.assertEqual(row["write_multiplier"], 1.25)
        self.assertEqual(row["read_multiplier"], 0.1)
        with self.assertRaises(SystemExit):
            cb.load_profile("no-such-profile")

    def test_load_prefix_rejects_missing_file(self):
        with self.assertRaises(SystemExit):
            cb.load_prefix(ROOT, "agents/does-not-exist.md")


class MeasureTestCase(unittest.TestCase):
    def run_matrix(self, responses, turns=2, seeds=(401, 409, 419)):
        tmp = tempfile.mkdtemp()
        path = Path(tmp) / "fixture.json"
        write_fixture(path, responses)
        client = cb.FixtureClient(path)
        prefix = "stable prefix body\n"
        meta = {
            "model": cb.DEFAULT_MODEL, "provider": "kilo",
            "harness": cb.DEFAULT_HARNESS, "profile": "anthropic-5m",
            "prefix_source": "test", "prefix_sha256": cb.sha256_text(prefix),
            "prefix_chars": len(prefix), "prefix_tokens_estimate": 4,
            "seeds": list(seeds), "turns": turns,
        }
        plan = cb.plan_requests(list(seeds), turns)
        records = cb.measure(plan, client, prefix, meta, gap=0, ttl_wait=0,
                             sleep=lambda _seconds: None)
        profile = cb.load_profile("anthropic-5m")
        return records, cb.summarize(records, profile, meta, plan)

    def test_records_every_required_field(self):
        records, _ = self.run_matrix(sample_responses())
        self.assertEqual(len(records), 9)
        required = {"seq", "seed", "turn", "kind", "timestamp_utc", "model",
                    "provider", "harness", "profile", "prefix_source",
                    "prefix_sha256", "status", "http_status", "latency_ms",
                    "seconds_since_last_request", "usage"}
        for record in records:
            self.assertTrue(required.issubset(record), record)
            for key in ("prompt_tokens", "cached_tokens",
                        "cache_creation_input_tokens", "output_tokens",
                        "cost_usd"):
                self.assertIn(key, record["usage"])
            self.assertEqual(record["harness"], cb.DEFAULT_HARNESS)
            self.assertRegex(record["timestamp_utc"], r"^\d{4}-\d{2}-\d{2}T")

    def test_cold_and_warm_split(self):
        _, summary = self.run_matrix(sample_responses())
        cold = summary["per_kind"]["cold"]
        warm = summary["per_kind"]["warm"]
        self.assertEqual(cold["hit_rate"], 0.0)
        self.assertEqual(cold["cache_creation_tokens_mean"], 1479)
        self.assertAlmostEqual(warm["hit_rate"], 1479 / 1483, places=6)
        self.assertEqual(warm["cached_tokens_mean"], 1479)
        self.assertEqual(warm["cache_creation_tokens_mean"], 0)
        self.assertEqual(summary["cold_over_warm_cost_ratio"], 11.0)

    def test_continuation_reported_separately(self):
        records, summary = self.run_matrix(sample_responses())
        continuation = summary["per_kind"]["continuation"]
        self.assertEqual(continuation["ok"], 3)
        self.assertEqual(continuation["cached_tokens_mean"], 1479)
        self.assertTrue(any(r["kind"] == "continuation" and r["turn"] == 2
                            for r in records))

    def test_consistency_flags_on_a_clean_run(self):
        _, summary = self.run_matrix(sample_responses())
        self.assertEqual(summary["profile_consistency"],
                         {"cold_writes_cache": True, "cold_reads_zero": True,
                          "warm_reads_cache": True, "warm_writes_zero": True})
        self.assertFalse(summary["below_minimum"])
        self.assertEqual(summary["prefix_tokens_observed"], 1479)
        self.assertEqual(summary["max_cacheable_block_observed"], 1479)
        self.assertEqual(summary["coverage"]["seeds_complete"], 3)

    def test_prefix_and_largest_block_are_reported_separately(self):
        # A continuation writes a 21-token tail: the largest cacheable block is
        # 1,487 + 21, but the prefix is still 1,487.
        responses = []
        for _ in range(3):
            responses.append(ok())
            responses.append(ok(cached=1479, created=0, cost=1.7e-05))
            responses.append(ok(cached=1479, created=21, prompt=1503))
        _, summary = self.run_matrix(responses)
        self.assertEqual(summary["prefix_tokens_observed"], 1479)
        self.assertEqual(summary["max_cacheable_block_observed"], 1500)

    def test_attempts_retries_and_rate_limit_are_recorded(self):
        _, summary = self.run_matrix(sample_responses())
        self.assertEqual(summary["attempts"], 9)
        self.assertEqual(summary["retries"], 0)
        self.assertEqual(summary["rate_limited"], 0)

    def test_cold_leg_that_is_warm_is_visible(self):
        # Every leg reads the cache: the profile flags say so instead of
        # silently reporting a cold hit rate.
        responses = [ok(cached=1479, created=0, cost=1.7e-05)] * 9
        _, summary = self.run_matrix(responses)
        self.assertAlmostEqual(summary["per_kind"]["cold"]["hit_rate"],
                               1479 / 1483, places=6)
        self.assertFalse(summary["profile_consistency"]["cold_reads_zero"])
        self.assertFalse(summary["profile_consistency"]["cold_writes_cache"])

    def test_failure_is_recorded_and_completed_runs_are_kept(self):
        responses = [ok(), ok(cached=1479, created=0, cost=1.7e-05),
                     ok(cached=1479, created=0, cost=2.4e-05),
                     {"status": 429, "error": "Free model usage limit reached"},
                     ok(cached=1479, created=0, cost=1.7e-05),
                     ok(cached=1479, created=0, cost=2.4e-05)]
        records, summary = self.run_matrix(responses, seeds=(401, 409))
        self.assertEqual(len(records), 6)
        failed = [r for r in records if r["status"] != "ok"]
        self.assertEqual(len(failed), 2)
        self.assertEqual(sorted(r["status"] for r in failed),
                         ["error", "skipped"])
        self.assertEqual([r["http_status"] for r in failed if r["status"] == "error"],
                         [429])
        self.assertEqual(summary["coverage"]["requests_ok"], 4)
        self.assertEqual(summary["coverage"]["requests_failed"], 2)
        self.assertEqual(summary["failures"][0]["error"],
                         "Free model usage limit reached")
        # seed 409 never completed a cold/warm pair, seed 401 did
        self.assertEqual(summary["coverage"]["seeds_complete"], 1)

    def test_below_minimum_is_marked_not_failed(self):
        records, summary = self.run_matrix([ok(prompt=600, created=596)] * 3, turns=1,
                                           seeds=(1,))
        profile = cb.load_profile("gemini-3")
        summary = cb.summarize(records, profile, {
            "model": "m", "provider": "p", "harness": "h", "profile": "gemini-3",
            "prefix_source": "t", "prefix_sha256": "0" * 64, "prefix_chars": 1,
            "prefix_tokens_estimate": 1, "seeds": [1], "turns": 1},
            cb.plan_requests([1], turns=1))
        self.assertTrue(summary["below_minimum"])

    def test_below_minimum_uses_the_prefix_not_the_largest_block(self):
        # A continuation can make the largest cacheable block exceed the
        # profile minimum while the prefix itself is still under it. The flag
        # must follow the prefix, or a sub-minimum prefix would read as fine.
        # gemini-3 declares min_tokens 4096; prefix 3,000, block 5,000.
        responses = [ok(created=3000, prompt=3000),
                     ok(cached=3000, created=0, prompt=3000),
                     ok(cached=3000, created=2000, prompt=5000, cost=2.4e-05)]
        records, _ = self.run_matrix(responses, turns=2, seeds=(1,))
        profile = cb.load_profile("gemini-3")
        summary = cb.summarize(records, profile, {
            "model": "m", "provider": "p", "harness": "h", "profile": "gemini-3",
            "prefix_source": "t", "prefix_sha256": "0" * 64, "prefix_chars": 1,
            "prefix_tokens_estimate": 1, "seeds": [1], "turns": 2},
            cb.plan_requests([1], turns=2))
        self.assertEqual(summary["prefix_tokens_observed"], 3000)
        self.assertEqual(summary["max_cacheable_block_observed"], 5000)
        self.assertTrue(summary["below_minimum"])

    def test_ttl_wait_runs_once_between_seeds(self):
        tmp = Path(tempfile.mkdtemp())
        path = tmp / "fixture.json"
        write_fixture(path, sample_responses())
        sleeps = []
        prefix = "stable prefix body\n"
        meta = {"model": "m", "provider": "p", "harness": "h",
                "profile": "anthropic-5m", "prefix_source": "t",
                "prefix_sha256": "0" * 64, "prefix_chars": 1,
                "prefix_tokens_estimate": 1, "seeds": [1, 2], "turns": 2}
        plan = cb.plan_requests([1, 2], turns=2)
        cb.measure(plan, cb.FixtureClient(path), prefix, meta, gap=2,
                   ttl_wait=330, sleep=lambda seconds: sleeps.append(seconds))
        # one warm gap per seed plus one TTL wait before the second seed
        self.assertEqual(sorted(sleeps), [2, 2, 330])

    def test_fixture_exhaustion_is_loud(self):
        with self.assertRaises(SystemExit):
            self.run_matrix([ok()])

    def test_empty_fixture_is_rejected(self):
        tmp = Path(tempfile.mkdtemp()) / "empty.json"
        tmp.write_text(json.dumps({"responses": []}), encoding="utf-8")
        with self.assertRaises(SystemExit):
            cb.FixtureClient(tmp)


class CommandTestCase(unittest.TestCase):
    def test_dry_run_prints_a_plan_and_returns_zero(self):
        buffer = io.StringIO()
        with mock.patch("sys.stdout", buffer):
            code = cb.main(["--dry-run"])
        self.assertEqual(code, 0)
        text = buffer.getvalue()
        self.assertIn("dry run", text)
        self.assertIn("prefix sha256", text)
        self.assertIn("requests: 9", text)

    def test_missing_key_exits_two_without_a_fixture(self):
        with mock.patch.dict(os.environ, {"KILO_API_KEY": ""}, clear=False):
            buffer = io.StringIO()
            with mock.patch("sys.stdout", buffer):
                code = cb.main(["--prefix", "agents/tabletop/tt-lore-keeper.md"])
        self.assertEqual(code, 2)
        self.assertIn("KILO_API_KEY is not set", buffer.getvalue())

    def test_fixture_run_writes_raw_records_and_summary(self):
        tmp = Path(tempfile.mkdtemp())
        fixture = tmp / "fixture.json"
        write_fixture(fixture, sample_responses())
        summary_path = tmp / "summary.json"
        buffer = io.StringIO()
        with mock.patch("sys.stdout", buffer):
            code = cb.main(["--fixture", str(fixture), "--gap", "0",
                            "--out", str(tmp / "raw"),
                            "--summary", str(summary_path), "--json"])
        self.assertEqual(code, 0)
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertEqual(summary["mode"], "fixture")
        self.assertEqual(summary["coverage"]["requests_ok"], 9)
        raw = list((tmp / "raw").glob("*/requests.jsonl"))
        self.assertEqual(len(raw), 1)
        self.assertEqual(len(raw[0].read_text(encoding="utf-8").strip().splitlines()), 9)

    def test_exit_code_contract_for_completed_runs(self):
        summary = {"mode": "live", "coverage": {"requests_failed": 0},
                   "profile_consistency": {"cold_reads_zero": True,
                                           "warm_reads_cache": True}}
        self.assertEqual(cb.exit_code_for(summary), 0)
        summary["profile_consistency"]["cold_reads_zero"] = False
        self.assertEqual(cb.exit_code_for(summary), 3)
        summary["profile_consistency"]["cold_reads_zero"] = True
        summary["profile_consistency"]["warm_reads_cache"] = False
        self.assertEqual(cb.exit_code_for(summary), 3)
        # A fixture is synthetic: the same shape stays deterministic at 0.
        summary["mode"] = "fixture"
        self.assertEqual(cb.exit_code_for(summary), 0)
        # A request failure outranks the consistency exit.
        summary["mode"] = "live"
        summary["coverage"]["requests_failed"] = 1
        self.assertEqual(cb.exit_code_for(summary), 1)

    def test_live_run_with_a_warm_cold_leg_exits_three(self):
        tmp = Path(tempfile.mkdtemp())
        fixture = tmp / "fixture.json"
        write_fixture(fixture, [ok(cached=1479, created=0, cost=1.7e-05)] * 9)
        replay = cb.FixtureClient(fixture)
        with mock.patch.dict(os.environ, {"KILO_API_KEY": "fake"}, clear=False):
            with mock.patch.object(cb, "GatewayClient", return_value=replay):
                with mock.patch("sys.stdout", io.StringIO()):
                    code = cb.main(["--prefix",
                                    "agents/tabletop/tt-lore-keeper.md",
                                    "--gap", "0", "--out", str(tmp / "raw")])
        self.assertEqual(code, 3)

    def test_live_run_that_matches_the_profile_exits_zero(self):
        tmp = Path(tempfile.mkdtemp())
        fixture = tmp / "fixture.json"
        write_fixture(fixture, sample_responses())
        replay = cb.FixtureClient(fixture)
        with mock.patch.dict(os.environ, {"KILO_API_KEY": "fake"}, clear=False):
            with mock.patch.object(cb, "GatewayClient", return_value=replay):
                with mock.patch("sys.stdout", io.StringIO()):
                    code = cb.main(["--prefix",
                                    "agents/tabletop/tt-lore-keeper.md",
                                    "--gap", "0", "--out", str(tmp / "raw")])
        self.assertEqual(code, 0)

    def test_summary_never_carries_the_api_key(self):
        tmp = Path(tempfile.mkdtemp())
        fixture = tmp / "fixture.json"
        write_fixture(fixture, sample_responses())
        buffer = io.StringIO()
        with mock.patch("sys.stdout", buffer):
            cb.main(["--fixture", str(fixture), "--gap", "0",
                     "--out", str(tmp / "raw"),
                     "--summary", str(tmp / "s.json"), "--json"])
        text = (tmp / "s.json").read_text(encoding="utf-8")
        self.assertNotIn("Authorization", text)
        self.assertNotIn("Bearer", text)
        self.assertNotIn("sk-", text)
        summary = json.loads(text)
        self.assertEqual(summary["api_key_env"], "KILO_API_KEY")
        self.assertFalse(any("api_key" == key or "key" == key.lower()
                             for key in summary))


class GatewayClientTestCase(unittest.TestCase):
    def respond(self, payload):
        return io.BytesIO(json.dumps(payload).encode("utf-8"))

    def test_retries_a_429_then_succeeds(self):
        calls = []

        def fake_urlopen(request, timeout=None):
            calls.append(request)
            if len(calls) == 1:
                raise urllib.error.HTTPError(
                    request.full_url, 429, "Too Many Requests", {},
                    io.BytesIO(b'{"error":"rate limited"}'))
            return self.respond({"choices": [{"message": {"content": "ack"}}],
                                 "usage": usage(cached=1479, created=0)})

        client = cb.GatewayClient("https://example.invalid/v1", "fake-key",
                                  "m", retries=2,
                                  sleep=lambda _seconds: None)
        with mock.patch("urllib.request.urlopen", fake_urlopen):
            result = client([{"role": "user", "content": "hi"}], 401)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(len(calls), 2)

    def test_auth_error_blocks_without_retry(self):
        calls = []

        def fake_urlopen(request, timeout=None):
            calls.append(request)
            raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized",
                                         {}, io.BytesIO(b'{"error":"bad key"}'))

        client = cb.GatewayClient("https://example.invalid/v1", "fake-key",
                                  "m", retries=2,
                                  sleep=lambda _seconds: None)
        with mock.patch("urllib.request.urlopen", fake_urlopen):
            result = client([{"role": "user", "content": "hi"}], 401)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["http_status"], 401)
        self.assertEqual(len(calls), 1)


class CommittedFixtureTestCase(unittest.TestCase):
    def test_committed_fixture_replays_the_recorded_matrix(self):
        self.assertTrue(FIXTURE.is_file(), FIXTURE)
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(data["responses"]), 9)
        for entry in data["responses"]:
            self.assertIn("usage", entry)
            usage_row = entry["usage"]
            self.assertIn("prompt_tokens", usage_row)
            self.assertIn("cache_creation_input_tokens", usage_row)
            details = usage_row.get("prompt_tokens_details") or {}
            self.assertIn("cached_tokens", details)

    def test_committed_fixture_has_no_secret(self):
        text = FIXTURE.read_text(encoding="utf-8")
        self.assertNotIn("sk-", text)
        self.assertNotIn("Bearer", text)
        self.assertNotIn("KILO_API_KEY=", text)


if __name__ == "__main__":
    unittest.main()
