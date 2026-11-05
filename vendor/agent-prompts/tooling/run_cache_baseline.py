#!/usr/bin/env python3
"""Measure a real prefix-cache hit rate for one cache profile (R4 / WP-04).

The static half of the assembly contract lives in
``tooling/check_token_efficiency.py``: it proves a prefix has no volatile bytes
and is above a profile minimum. It cannot prove that a provider caches it. This
runner does that with a live request pair -- a cold request that writes the
cache and a byte-identical warm request that reads it -- and records the usage
the provider reports.

Per seed it issues three requests over two user turns:

    turn 1 cold     system=<stable prefix>, user=<probe 1>        (write)
    turn 1 warm     the identical body, back-to-back              (read)
    turn 2 warm     <probe 1>, <reply 1>, <probe 2>               (read + tail)

Turn 2 has no cold leg: the prefix is already warm from turn 1, and a cold
continuation would need an idle wait longer than the profile TTL. It is reported
separately as ``continuation`` so it cannot be confused with the cold/warm pair.

Usage:
    python3 tooling/run_cache_baseline.py --dry-run
    python3 tooling/run_cache_baseline.py --prefix agents/tabletop/tt-lore-keeper.md
    python3 tooling/run_cache_baseline.py --fixture evals/cache/fixtures/kilo-anthropic-5m-sample.json

The API key is read from an environment variable and is never written to any
record. Raw per-request records go to ``evals/results/`` (git-ignored); only the
aggregate summary is meant to be committed.

Exit 0 when every seed completed and a live run agrees with the profile, 1 when
a request failed, 2 on a bad argument or a missing key, 3 when a live run
contradicts the profile (a cold leg read the cache, or a warm leg did not).
"""

import argparse
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "standards" / "cache-profiles.json"

DEFAULT_BASE_URL = "https://api.kilocode.ai/api/gateway/v1"
DEFAULT_MODEL = "anthropic/claude-haiku-5.5"
DEFAULT_HARNESS = "kilo-gateway"
DEFAULT_API_KEY_ENV = "KILO_API_KEY"
DEFAULT_PREFIX = "agents/tabletop/tt-lore-keeper.md"
DEFAULT_SEEDS = "401,409,419"
DEFAULT_OUT = "evals/results/cache-baseline"

PROBE_1 = "Reply with one sentence naming your primary responsibility."
PROBE_2 = "Reply with one sentence naming the first check you would run."

KINDS = ("cold", "warm", "continuation")

# A live run that contradicts either flag is an invalid record even when every
# request completed: the cold leg was warm, or the warm leg missed the cache.
CONSISTENCY_REQUIRED = ("cold_reads_zero", "warm_reads_cache")

LIMITS = [
    "One prefix, one model, one harness: this is not a general cache gain.",
    "The warm leg repeats an identical body, so the hit rate is an upper bound "
    "for a session that edits its stable prefix between turns.",
    "Cold and warm differ only in cache state; the model is deterministic and "
    "each seed is a repetition, not a sampling draw.",
    "Turn 2 is measured warm only; no cold continuation is recorded.",
    "Cost is the gateway's reported usage.cost, not a decomposed price table.",
]


# --- helpers ---------------------------------------------------------------


def body_of(text):
    """Strip YAML frontmatter; a carrier's frontmatter is not prompt content."""
    match = re.match(r"(?s)^---\s*\n.*?\n---\s*\n?(.*)$", text)
    return match.group(1) if match else text


def token_estimate(text):
    return max(1, len(text.encode("utf-8")) // 4)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_profile(profile_id, path=None):
    data = json.loads(Path(path or PROFILES).read_text(encoding="utf-8"))
    for row in data.get("profiles", []):
        if row.get("id") == profile_id:
            return row
    raise SystemExit("unknown cache profile: %s" % profile_id)


def parse_seeds(text):
    seeds = []
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            seeds.append(int(part))
        except ValueError:
            raise SystemExit("seed is not an integer: %r" % part)
    if not seeds:
        raise SystemExit("at least one seed is required")
    return seeds


def load_prefix(root, source):
    path = Path(source)
    if not path.is_absolute():
        path = Path(root) / path
    if not path.is_file():
        raise SystemExit("prefix carrier not found: %s" % source)
    return body_of(path.read_text(encoding="utf-8"))


def build_messages(prefix, turn, reply=None):
    messages = [{"role": "system", "content": prefix},
                {"role": "user", "content": PROBE_1}]
    if turn == 2:
        messages.append({"role": "assistant", "content": reply or ""})
        messages.append({"role": "user", "content": PROBE_2})
    return messages


def plan_requests(seeds, turns=2):
    """Return the deterministic request plan as (seed, turn, kind) tuples."""
    plan = []
    for seed in seeds:
        plan.append((seed, 1, "cold"))
        plan.append((seed, 1, "warm"))
        if turns >= 2:
            plan.append((seed, 2, "continuation"))
    return plan


# --- clients ---------------------------------------------------------------


def _error_detail(exc):
    try:
        body = exc.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 - diagnostic body only
        body = ""
    body = " ".join(body.split())
    return body[:300] or str(getattr(exc, "reason", "") or "no body")


class GatewayClient:
    """One chat completion per call, with a bounded retry on 429 and 5xx."""

    def __init__(self, base_url, api_key, model, timeout=120, max_tokens=32,
                 retries=2, sleep=time.sleep):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.retries = retries
        self.sleep = sleep

    def __call__(self, messages, seed):
        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "seed": seed,
        }).encode("utf-8")
        headers = {"Authorization": "Bearer %s" % self.api_key,
                   "Content-Type": "application/json"}
        attempts = 0
        last = {"status": "error", "http_status": None, "error": "no attempt"}
        while attempts <= self.retries:
            attempts += 1
            request = urllib.request.Request(self.url, data=payload,
                                             headers=headers, method="POST")
            started = time.time()
            try:
                with urllib.request.urlopen(request,
                                            timeout=self.timeout) as response:
                    body = json.loads(response.read().decode("utf-8"))
                return {"status": "ok", "http_status": 200, "body": body,
                        "attempts": attempts,
                        "latency_ms": int((time.time() - started) * 1000)}
            except urllib.error.HTTPError as exc:
                last = {"status": "error", "http_status": exc.code,
                        "error": _error_detail(exc), "attempts": attempts,
                        "latency_ms": int((time.time() - started) * 1000)}
                if exc.code in (401, 402, 403, 404):
                    last["status"] = "blocked"
                    return last
                if (exc.code == 429 or exc.code >= 500) and attempts <= self.retries:
                    self.sleep(2 ** (attempts - 1))
                    continue
                return last
            except (OSError, ValueError) as exc:
                last = {"status": "error", "http_status": None,
                        "error": "%s: %s" % (type(exc).__name__, exc),
                        "attempts": attempts,
                        "latency_ms": int((time.time() - started) * 1000)}
                if attempts <= self.retries:
                    self.sleep(2 ** (attempts - 1))
                    continue
                return last
        return last


class FixtureClient:
    """Replay recorded responses so the matrix runs with no network.

    A fixture is ``{"responses": [...]}`` where each entry is either
    ``{"usage": {...}, "content": "..."}`` for a 200 or
    ``{"status": 429, "error": "..."}`` for a failure.
    """

    def __init__(self, fixture_path):
        data = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
        self.responses = list(data.get("responses") or [])
        if not self.responses:
            raise SystemExit("fixture has no responses: %s" % fixture_path)
        self.index = 0
        self.model = data.get("model")

    def __call__(self, messages, seed):
        if self.index >= len(self.responses):
            raise SystemExit("fixture exhausted after %d responses"
                             % len(self.responses))
        entry = self.responses[self.index]
        self.index += 1
        if entry.get("status", 200) != 200:
            return {"status": entry.get("status_name", "error"),
                    "http_status": entry.get("status"),
                    "error": entry.get("error", "fixture failure"),
                    "attempts": 1,
                    "latency_ms": int(entry.get("latency_ms", 0))}
        content = entry.get("content", "")
        body = {"model": entry.get("model", self.model),
                "choices": [{"index": 0, "message": {"role": "assistant",
                                                     "content": content},
                             "finish_reason": "stop"}],
                "usage": dict(entry.get("usage") or {})}
        return {"status": "ok", "http_status": 200, "body": body,
                "attempts": 1, "latency_ms": int(entry.get("latency_ms", 0))}


# --- usage extraction ------------------------------------------------------


def usage_fields(body):
    """Normalize the provider usage block to the fields R4 records."""
    usage = (body or {}).get("usage") or {}
    details = usage.get("prompt_tokens_details") or {}
    cached = details.get("cached_tokens")
    if cached is None:
        cached = usage.get("cached_tokens")
    return {
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "cached_tokens": int(cached or 0),
        "cache_creation_input_tokens": int(usage.get("cache_creation_input_tokens") or 0),
        "output_tokens": int(usage.get("completion_tokens") or 0),
        "cost_usd": float(usage.get("cost") or 0.0),
    }


def reply_of(body):
    choices = (body or {}).get("choices") or [{}]
    message = choices[0].get("message") or {}
    return message.get("content") or ""


# --- measurement -----------------------------------------------------------


def measure(plan, client, prefix, meta, gap=2.0, ttl_wait=0.0, sleep=time.sleep,
            clock=utc_now, now=time.time):
    """Run the planned requests and return one record per request.

    ``ttl_wait`` is idle time inserted before the first request of every seed
    after the first, so that seed's cold leg really starts from an expired
    cache. Without it a repeated byte-identical prefix is still warm and the
    "cold" leg records a hit; the profile-consistency flags then report that.
    """
    records = []
    last_at = {}
    replies = {}
    seen_seeds = set()
    for seed, turn, kind in plan:
        if kind == "warm" and seed not in replies:
            # The cold leg did not complete: a warm leg would measure an
            # unknown cache state. Record the skip so the plan and the record
            # count stay aligned instead of dropping the request silently.
            records.append({
                "schema": "agent-prompts-cache-baseline/1",
                "seq": len(records) + 1, "seed": seed, "turn": turn,
                "kind": kind, "timestamp_utc": clock(),
                "model": meta["model"], "provider": meta["provider"],
                "harness": meta["harness"], "profile": meta["profile"],
                "prefix_source": meta["prefix_source"],
                "prefix_sha256": meta["prefix_sha256"],
                "status": "skipped", "http_status": None, "attempts": 0,
                "latency_ms": 0, "seconds_since_last_request": None,
                "error": "cold leg did not complete",
                "usage": {"prompt_tokens": 0, "cached_tokens": 0,
                          "cache_creation_input_tokens": 0,
                          "output_tokens": 0, "cost_usd": 0.0},
            })
            continue
        if seed not in seen_seeds:
            if seen_seeds and ttl_wait > 0:
                sleep(ttl_wait)
            seen_seeds.add(seed)
        if kind == "warm" and gap > 0:
            sleep(gap)
        previous = last_at.get(seed)
        gap_seconds = None if previous is None else round(now() - previous, 3)
        messages = build_messages(prefix, turn, replies.get(seed))
        result = client(messages, seed)
        last_at[seed] = now()
        record = {
            "schema": "agent-prompts-cache-baseline/1",
            "seq": len(records) + 1,
            "seed": seed,
            "turn": turn,
            "kind": kind,
            "timestamp_utc": clock(),
            "model": meta["model"],
            "provider": meta["provider"],
            "harness": meta["harness"],
            "profile": meta["profile"],
            "prefix_source": meta["prefix_source"],
            "prefix_sha256": meta["prefix_sha256"],
            "status": result["status"],
            "http_status": result.get("http_status"),
            "attempts": result.get("attempts", 1),
            "latency_ms": result.get("latency_ms", 0),
            "seconds_since_last_request": gap_seconds,
            "usage": {"prompt_tokens": 0, "cached_tokens": 0,
                      "cache_creation_input_tokens": 0, "output_tokens": 0,
                      "cost_usd": 0.0},
        }
        if result["status"] == "ok":
            body = result["body"]
            record["usage"] = usage_fields(body)
            record["prefix_hash"] = meta["prefix_sha256"]
            if turn == 1:
                replies[seed] = reply_of(body)
            if record["usage"]["cached_tokens"]:
                record["first_divergent_layer"] = None
            elif kind in ("warm", "continuation"):
                record["first_divergent_layer"] = "system"
        else:
            record["error"] = result.get("error", "unknown error")
        records.append(record)
    return records


def hit_rate(record):
    usage = record["usage"]
    if not usage["prompt_tokens"]:
        return None
    return usage["cached_tokens"] / float(usage["prompt_tokens"])


def summarize(records, profile, meta, plan):
    """Aggregate per-request records into the committed summary."""
    by_kind = {}
    for kind in KINDS:
        rows = [r for r in records if r["kind"] == kind]
        ok = [r for r in rows if r["status"] == "ok"]
        entry = {"requests": len(rows), "ok": len(ok), "failed": len(rows) - len(ok)}
        if ok:
            rates = [hit_rate(r) for r in ok if hit_rate(r) is not None]
            entry.update({
                "prompt_tokens_mean": round(mean(r["usage"]["prompt_tokens"] for r in ok), 1),
                "cached_tokens_mean": round(mean(r["usage"]["cached_tokens"] for r in ok), 1),
                "cache_creation_tokens_mean": round(
                    mean(r["usage"]["cache_creation_input_tokens"] for r in ok), 1),
                "output_tokens_mean": round(mean(r["usage"]["output_tokens"] for r in ok), 1),
                "hit_rate": round(mean(rates), 6) if rates else None,
                "cost_usd_mean": round(mean(r["usage"]["cost_usd"] for r in ok), 10),
                "cost_usd_total": round(sum(r["usage"]["cost_usd"] for r in ok), 10),
                "latency_ms_mean": round(mean(r["latency_ms"] for r in ok), 1),
                "latency_ms_median": round(median(r["latency_ms"] for r in ok), 1),
            })
            gaps = [r["seconds_since_last_request"] for r in ok
                    if r["seconds_since_last_request"] is not None]
            entry["seconds_since_last_request_max"] = round(max(gaps), 3) if gaps else None
        by_kind[kind] = entry

    cold = by_kind["cold"]
    warm = by_kind["warm"]
    ratio = None
    if cold.get("cost_usd_mean") and warm.get("cost_usd_mean"):
        ratio = round(cold["cost_usd_mean"] / warm["cost_usd_mean"], 2)

    cold_rows = [r for r in records if r["kind"] == "cold" and r["status"] == "ok"]
    warm_rows = [r for r in records if r["kind"] == "warm" and r["status"] == "ok"]
    consistency = {
        "cold_writes_cache": bool(cold_rows) and all(
            r["usage"]["cache_creation_input_tokens"] > 0 for r in cold_rows),
        "cold_reads_zero": bool(cold_rows) and all(
            r["usage"]["cached_tokens"] == 0 for r in cold_rows),
        "warm_reads_cache": bool(warm_rows) and all(
            r["usage"]["cached_tokens"] > 0 for r in warm_rows),
        "warm_writes_zero": bool(warm_rows) and all(
            r["usage"]["cache_creation_input_tokens"] == 0 for r in warm_rows),
    }

    seeds_requested = sorted({seed for seed, _, _ in plan})
    seeds_complete = sorted({r["seed"] for r in records
                             if r["status"] == "ok" and r["kind"] == "cold"
                             and any(w["seed"] == r["seed"] and w["status"] == "ok"
                                     and w["kind"] == "warm" for w in records)})
    failed = [r for r in records if r["status"] != "ok"]
    # The largest single-request cacheable block is not the prefix when a
    # continuation writes a tail: 1,487 read + 21 written is one block, but the
    # prefix itself is 1,487. Keep both numbers under names that say which one
    # is which.
    max_block = max([r["usage"]["cached_tokens"] +
                     r["usage"]["cache_creation_input_tokens"] for r in records]
                    or [0])
    prefix_tokens = max([max(r["usage"]["cached_tokens"],
                             r["usage"]["cache_creation_input_tokens"])
                         for r in records] or [0])
    attempts = sum(int(r.get("attempts") or 0) for r in records)
    retries = sum(max(0, int(r.get("attempts") or 0) - 1) for r in records)
    rate_limited = sum(1 for r in records if r.get("http_status") == 429)
    return {
        "schema": "agent-prompts-cache-baseline/1",
        "generated_utc": utc_now(),
        "profile": profile["id"],
        "profile_row": profile,
        "model": meta["model"],
        "provider": meta["provider"],
        "harness": meta["harness"],
        "prefix": {
            "source": meta["prefix_source"],
            "sha256": meta["prefix_sha256"],
            "chars": meta["prefix_chars"],
            "estimated_tokens": meta["prefix_tokens_estimate"],
        },
        "seeds_requested": seeds_requested,
        "seeds_complete": seeds_complete,
        "turns_per_seed": meta["turns"],
        "requests": len(records),
        "coverage": {
            "seeds_requested": len(seeds_requested),
            "seeds_complete": len(seeds_complete),
            "requests_ok": len(records) - len(failed),
            "requests_failed": len(failed),
        },
        "below_minimum": prefix_tokens < int(profile.get("min_tokens") or 0),
        "prefix_tokens_observed": prefix_tokens,
        "max_cacheable_block_observed": max_block,
        "attempts": attempts,
        "retries": retries,
        "rate_limited": rate_limited,
        "per_kind": by_kind,
        "cold_over_warm_cost_ratio": ratio,
        "profile_consistency": consistency,
        "failures": [{"seq": r["seq"], "seed": r["seed"], "kind": r["kind"],
                      "status": r["status"], "http_status": r["http_status"],
                      "error": r.get("error")} for r in failed],
        "limits": LIMITS,
    }


# --- reporting -------------------------------------------------------------


def render_plan(plan, meta):
    lines = ["cache baseline plan",
             "  harness: %s" % meta["harness"],
             "  provider: %s" % meta["provider"],
             "  model: %s" % meta["model"],
             "  profile: %s (min_tokens=%s, ttl=%s, write=%sx, read=%sx)"
             % (meta["profile"], meta["min_tokens"], meta["ttl"],
                meta["write_multiplier"], meta["read_multiplier"]),
             "  prefix: %s" % meta["prefix_source"],
             "  prefix sha256: %s" % meta["prefix_sha256"],
             "  prefix chars: %d (estimated %d tokens)"
             % (meta["prefix_chars"], meta["prefix_tokens_estimate"]),
             "  seeds: %s" % ", ".join(str(seed) for seed in meta["seeds"]),
             "  turns per seed: %d" % meta["turns"],
             "  requests: %d" % len(plan)]
    for seed, turn, kind in plan:
        lines.append("    seed %s turn %s %s" % (seed, turn, kind))
    lines.append("  dry run: no request was sent")
    return "\n".join(lines)


def render_summary(summary):
    cold = summary["per_kind"]["cold"]
    warm = summary["per_kind"]["warm"]
    cont = summary["per_kind"]["continuation"]
    lines = ["cache baseline (%s, %s via %s)"
             % (summary["profile"], summary["model"], summary["harness"]),
             "  prefix: %s (%s)" % (summary["prefix"]["source"],
                                    summary["prefix"]["sha256"][:12]),
             "  coverage: %d/%d seeds, %d/%d requests ok"
             % (summary["coverage"]["seeds_complete"],
                summary["coverage"]["seeds_requested"],
                summary["coverage"]["requests_ok"],
                summary["requests"]),
             "  cold: hit rate %s, write %s tok, %s usd/run, %s ms"
             % (cold.get("hit_rate"), cold.get("cache_creation_tokens_mean"),
                cold.get("cost_usd_mean"), cold.get("latency_ms_median")),
             "  warm: hit rate %s, read %s tok, %s usd/run, %s ms"
             % (warm.get("hit_rate"), warm.get("cached_tokens_mean"),
                warm.get("cost_usd_mean"), warm.get("latency_ms_median")),
             "  continuation: hit rate %s, %s usd/run, %s ms"
             % (cont.get("hit_rate"), cont.get("cost_usd_mean"),
                cont.get("latency_ms_median")),
             "  cold/warm cost ratio: %s" % summary["cold_over_warm_cost_ratio"],
             "  attempts: %s (retries %s, rate-limited %s)"
             % (summary["attempts"], summary["retries"],
                summary["rate_limited"])]
    if summary["below_minimum"]:
        lines.append("  measured below minimum: prefix %d < %d tokens"
                     % (summary["prefix_tokens_observed"],
                        summary["profile_row"]["min_tokens"]))
    for failure in summary["failures"]:
        lines.append("  failed: seed %s turn %s %s -> %s HTTP %s %s"
                     % (failure["seed"], failure["kind"], failure["status"],
                        failure["http_status"], failure["error"]))
    return "\n".join(lines)


def exit_code_for(summary):
    """Map a completed run to its process exit code.

    A request failure is exit 1. A live run that completed every request but
    contradicts the profile is exit 3: the record is not a cache measurement, so
    it must not be committed as a clean run. Fixture runs keep exit 0 because a
    fixture can be synthetic and is not a provider observation.
    """
    if summary["coverage"]["requests_failed"]:
        return 1
    if summary.get("mode") == "live":
        flags = summary.get("profile_consistency") or {}
        if any(not flags.get(name) for name in CONSISTENCY_REQUIRED):
            return 3
    return 0


# --- entry point -----------------------------------------------------------


def build_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Measure a prefix-cache cold/warm pair on a live provider.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", default="anthropic-5m",
                        help="profile id from standards/cache-profiles.json")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX,
                        help="stable-prefix carrier (default: %s)" % DEFAULT_PREFIX)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--harness", default=DEFAULT_HARNESS,
                        help="route label recorded in every run (default: %s)"
                             % DEFAULT_HARNESS)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV)
    parser.add_argument("--seeds", default=DEFAULT_SEEDS)
    parser.add_argument("--turns", type=int, default=2, choices=(1, 2))
    parser.add_argument("--gap", type=float, default=2.0,
                        help="seconds between the cold and the warm request")
    parser.add_argument("--ttl-wait", type=float, default=0.0,
                        help="idle seconds before each seed after the first, so "
                             "its cold leg starts from an expired cache")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--fixture", default=None,
                        help="replay a recorded response fixture instead of the "
                             "network")
    parser.add_argument("--out", default=DEFAULT_OUT,
                        help="directory for raw per-request records (git-ignored)")
    parser.add_argument("--summary", default=None,
                        help="write the aggregate summary to this path")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan and send nothing")
    parser.add_argument("--json", action="store_true",
                        help="print the summary as JSON")
    parser.add_argument("--root", default=str(ROOT))
    return parser.parse_args(argv)


def main(argv=None):
    args = build_args(argv)
    root = Path(args.root).resolve()
    profile = load_profile(args.profile, root / "standards" / "cache-profiles.json")
    seeds = parse_seeds(args.seeds)
    prefix = load_prefix(root, args.prefix)
    plan = plan_requests(seeds, args.turns)
    meta = {
        "model": args.model,
        "provider": "kilo",
        "harness": args.harness,
        "profile": profile["id"],
        "min_tokens": profile["min_tokens"],
        "ttl": profile["ttl"],
        "write_multiplier": profile["write_multiplier"],
        "read_multiplier": profile["read_multiplier"],
        "prefix_source": args.prefix,
        "prefix_sha256": sha256_text(prefix),
        "prefix_chars": len(prefix),
        "prefix_tokens_estimate": token_estimate(prefix),
        "seeds": seeds,
        "turns": args.turns,
    }
    if args.dry_run:
        print(render_plan(plan, meta))
        return 0

    if args.fixture:
        client = FixtureClient(root / args.fixture
                               if not Path(args.fixture).is_absolute()
                               else args.fixture)
    else:
        key = (os.environ.get(args.api_key_env) or "").strip()
        if not key:
            print("cache-baseline: %s is not set; cannot call %s"
                  % (args.api_key_env, args.base_url))
            return 2
        client = GatewayClient(args.base_url, key, args.model,
                               timeout=args.timeout, max_tokens=args.max_tokens,
                               retries=args.retries)

    started = utc_now()
    records = measure(plan, client, prefix, meta, gap=args.gap,
                      ttl_wait=args.ttl_wait)
    summary = summarize(records, profile, meta, plan)
    summary["started_utc"] = started
    summary["base_url"] = args.base_url
    summary["api_key_env"] = args.api_key_env
    summary["ttl_wait_seconds"] = args.ttl_wait
    summary["mode"] = "fixture" if args.fixture else "live"

    stamp = started.replace(":", "").replace("-", "")
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir = out_dir / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "requests.jsonl"
    with raw_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    if args.summary:
        target = Path(args.summary)
        if not target.is_absolute():
            target = root / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(render_summary(summary))
        print("raw records: %s" % raw_path)
    return exit_code_for(summary)


if __name__ == "__main__":
    raise SystemExit(main())
