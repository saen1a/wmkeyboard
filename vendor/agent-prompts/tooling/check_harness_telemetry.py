#!/usr/bin/env python3
"""Validate one harness telemetry record against the shared contract.

Checks the required shape and the gate consistency rules that make the record
useful: a fast-path claim must name a real verification with exit 0, and a HALT
must be recorded as halted.

Usage:
    python3 tooling/check_harness_telemetry.py record.json
    python3 tooling/check_harness_telemetry.py record.json --json

Exit 0 clean, 1 violations, 2 unreadable/invalid JSON.
"""

import argparse
import json
import re
import sys
from pathlib import Path

GATES = {"fast-path", "full-stopp", "halt", "none"}
STATUSES = {"pass", "fail", "halted", "error"}
ALLOWED = {
    "root": ["schema", "run", "turn", "usage", "outcome", "cache"],
    "run": ["model", "provider", "harness", "seed", "timestamp_utc",
            "skill_versions", "prompt_version", "cache_epoch"],
    "turn": ["gate", "gate_reasons", "files", "lines", "verification",
             "prefix_hash", "first_divergent_layer", "seconds_since_last_request"],
    "usage": ["input_tokens", "output_tokens", "reasoning_tokens",
              "cache_hit_tokens", "cache_miss_tokens", "cache_read_tokens",
              "cache_write_tokens", "cache_write_ttl_class"],
    "outcome": ["status", "escaped_defect", "operator_interventions",
                "duration_ms", "cost_usd"],
    "cache": ["prefix_hash", "breakpoints", "ttl", "tool_set_version",
              "layer_hashes", "min_tokens", "compaction"],
    "cache_epoch": ["model", "harness", "toolset_sha256", "doctrine_version",
                    "template_version"],
    "compaction": ["reason", "before_tokens", "after_tokens",
                   "hit_rate_before", "hit_rate_after"],
}
REQUIRED = {
    "run": ["model", "provider", "harness", "seed", "timestamp_utc"],
    "turn": ["gate", "gate_reasons", "files", "lines", "verification"],
    "usage": ["input_tokens", "output_tokens", "reasoning_tokens",
              "cache_hit_tokens", "cache_miss_tokens"],
    "outcome": ["status", "escaped_defect", "operator_interventions",
                "duration_ms"],
}


def check(record):
    violations = []

    def fail(message):
        violations.append(message)

    schema = record.get("schema")
    if schema not in ("agent-prompts-harness/1", "agent-prompts-harness/2"):
        fail("schema must be agent-prompts-harness/1 or /2")
    for key in record:
        if key not in ALLOWED["root"]:
            fail("unknown top-level key: %s" % key)
    for section, keys in REQUIRED.items():
        value = record.get(section)
        if not isinstance(value, dict):
            fail("%s must be an object" % section)
            continue
        for key in value:
            if key not in ALLOWED[section]:
                fail("unknown %s key: %s" % (section, key))
        for key in keys:
            if key not in value:
                fail("%s.%s is required" % (section, key))

    run = record.get("run") if isinstance(record.get("run"), dict) else {}
    for key in ("model", "provider", "harness", "timestamp_utc"):
        if not isinstance(run.get(key), str) or not run.get(key).strip():
            fail("run.%s must be a non-empty string" % key)
    if run.get("seed") is not None and not isinstance(run.get("seed"), int):
        fail("run.seed must be an integer or null")
    if not isinstance(run.get("timestamp_utc"), str) or len(run.get("timestamp_utc", "")) < 10:
        fail("run.timestamp_utc must be a string of at least 10 characters")
    if "skill_versions" in run and not isinstance(run["skill_versions"], dict):
        fail("run.skill_versions must be an object")
    if "prompt_version" in run and not isinstance(run["prompt_version"], str):
        fail("run.prompt_version must be a string")

    turn = record.get("turn") if isinstance(record.get("turn"), dict) else {}
    gate = turn.get("gate")
    if gate not in GATES:
        fail("turn.gate must be one of %s" % sorted(GATES))
    if not isinstance(turn.get("gate_reasons"), list):
        fail("turn.gate_reasons must be a list")
    elif not all(isinstance(item, str) for item in turn["gate_reasons"]):
        fail("turn.gate_reasons items must be strings")
    for key in ("files", "lines"):
        value = turn.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            fail("turn.%s must be a non-negative integer" % key)
    verification = turn.get("verification")
    if not isinstance(verification, dict):
        fail("turn.verification must be an object")
        verification = {}
    command = verification.get("command", "")
    exit_code = verification.get("exit_code")
    if not isinstance(command, str):
        fail("turn.verification.command must be a string")
    if exit_code is not None and (not isinstance(exit_code, int)
                                 or isinstance(exit_code, bool)):
        fail("turn.verification.exit_code must be an integer or null")

    if gate == "fast-path":
        if turn.get("files") != 1:
            fail("fast-path requires exactly one file")
        if not command.strip():
            fail("fast-path requires a verification command")
        if exit_code != 0:
            fail("fast-path requires verification exit_code 0")
        if not turn.get("gate_reasons"):
            fail("fast-path requires at least one gate reason")

    usage = record.get("usage") if isinstance(record.get("usage"), dict) else {}
    for key in REQUIRED["usage"]:
        value = usage.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            fail("usage.%s must be a non-negative integer" % key)
    for key in ("cache_read_tokens", "cache_write_tokens"):
        if key in usage:
            value = usage[key]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                fail("usage.%s must be a non-negative integer" % key)
    ttl_class = usage.get("cache_write_ttl_class")
    if ttl_class is not None and ttl_class not in (
            "5m", "1h", "30m", "12h", "implicit", "best-effort", "lru", "unknown"):
        fail("usage.cache_write_ttl_class is not canonical")

    cache = record.get("cache")
    if schema == "agent-prompts-harness/2":
        if not isinstance(cache, dict):
            fail("schema /2 requires cache")
        for key in ("cache_read_tokens", "cache_write_tokens"):
            if key not in usage:
                fail("schema /2 requires usage.%s" % key)
    if cache is not None:
        if not isinstance(cache, dict):
            fail("cache must be an object")
        else:
            for key in cache:
                if key not in ALLOWED["cache"]:
                    fail("unknown cache key: %s" % key)
            for key in ("prefix_hash", "breakpoints", "ttl", "tool_set_version"):
                if key not in cache:
                    fail("cache.%s is required" % key)
            prefix_hash = cache.get("prefix_hash")
            if not isinstance(prefix_hash, str) or not re.match(r"^[0-9a-f]{8,64}$", prefix_hash):
                fail("cache.prefix_hash must be a hex hash")
            breakpoints = cache.get("breakpoints")
            if (not isinstance(breakpoints, int) or isinstance(breakpoints, bool)
                    or breakpoints < 0 or breakpoints > 4):
                fail("cache.breakpoints must be an integer 0..4")
            if cache.get("ttl") not in ("5m", "1h", "30m", "12h", "implicit",
                                        "best-effort", "lru", "none"):
                fail("cache.ttl is not canonical")
            if (cache.get("ttl") in ("5m", "1h", "30m", "12h")
                    and ttl_class in ("5m", "1h", "30m", "12h")
                    and cache.get("ttl") != ttl_class):
                fail("cache.ttl and usage.cache_write_ttl_class disagree")
            if not isinstance(cache.get("tool_set_version"), str) or not cache["tool_set_version"].strip():
                fail("cache.tool_set_version must be a non-empty string")
            if "min_tokens" in cache and (not isinstance(cache["min_tokens"], int)
                                          or isinstance(cache["min_tokens"], bool)
                                          or cache["min_tokens"] < 0):
                fail("cache.min_tokens must be a non-negative integer")
            layers = cache.get("layer_hashes")
            if layers is not None:
                if not isinstance(layers, dict):
                    fail("cache.layer_hashes must be an object")
                else:
                    for key, value in layers.items():
                        if key not in ("tools", "system", "skills", "messages"):
                            fail("cache.layer_hashes key is not a layer: %s" % key)
                        if not isinstance(value, str) or not re.match(r"^[0-9a-f]{8,64}$", value):
                            fail("cache.layer_hashes.%s must be a hex hash" % key)
            compaction = cache.get("compaction")
            if compaction is not None:
                if not isinstance(compaction, dict):
                    fail("cache.compaction must be an object")
                else:
                    for key in compaction:
                        if key not in ALLOWED["compaction"]:
                            fail("unknown cache.compaction key: %s" % key)
                    for key in ("reason", "before_tokens", "after_tokens",
                                "hit_rate_before", "hit_rate_after"):
                        if key not in compaction:
                            fail("cache.compaction.%s is required" % key)
                    for key in ("before_tokens", "after_tokens"):
                        if key in compaction and (not isinstance(compaction[key], int)
                                                  or isinstance(compaction[key], bool)
                                                  or compaction[key] < 0):
                            fail("cache.compaction.%s must be non-negative" % key)
                    if (isinstance(compaction.get("before_tokens"), int)
                            and isinstance(compaction.get("after_tokens"), int)
                            and compaction["after_tokens"] > compaction["before_tokens"]):
                        fail("cache.compaction must not grow the context")
                    for key in ("hit_rate_before", "hit_rate_after"):
                        value = compaction.get(key)
                        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                                or value < 0 or value > 1):
                            fail("cache.compaction.%s must be a ratio 0..1" % key)

    epoch = run.get("cache_epoch")
    if epoch is not None:
        if not isinstance(epoch, dict):
            fail("run.cache_epoch must be an object")
        else:
            for key in epoch:
                if key not in ALLOWED["cache_epoch"]:
                    fail("unknown run.cache_epoch key: %s" % key)
            for key in ("model", "harness", "toolset_sha256", "doctrine_version"):
                if key not in epoch:
                    fail("run.cache_epoch.%s is required" % key)
            tool_hash = epoch.get("toolset_sha256")
            if not isinstance(tool_hash, str) or not re.match(r"^[0-9a-f]{8,64}$", tool_hash):
                fail("run.cache_epoch.toolset_sha256 must be a hex hash")
            for key in ("model", "harness", "doctrine_version"):
                if not isinstance(epoch.get(key), str) or not epoch.get(key).strip():
                    fail("run.cache_epoch.%s must be a non-empty string" % key)
            if "template_version" in epoch and not isinstance(epoch["template_version"], str):
                fail("run.cache_epoch.template_version must be a string")

    prefix_hash = turn.get("prefix_hash")
    if prefix_hash is not None and (not isinstance(prefix_hash, str)
                                    or not re.match(r"^[0-9a-f]{8,64}$", prefix_hash)):
        fail("turn.prefix_hash must be a hex hash")
    if (prefix_hash and isinstance(cache, dict) and cache.get("prefix_hash")
            and prefix_hash != cache.get("prefix_hash")):
        fail("turn.prefix_hash and cache.prefix_hash disagree")
    divergent = turn.get("first_divergent_layer")
    if divergent is not None and divergent not in ("tools", "system", "skills", "messages"):
        fail("turn.first_divergent_layer must be tools|system|skills|messages")
    gap = turn.get("seconds_since_last_request")
    if gap is not None and (not isinstance(gap, (int, float)) or isinstance(gap, bool) or gap < 0):
        fail("turn.seconds_since_last_request must be non-negative")
    outcome = record.get("outcome") if isinstance(record.get("outcome"), dict) else {}
    cost = outcome.get("cost_usd")
    if cost is not None and (not isinstance(cost, (int, float)) or isinstance(cost, bool) or cost < 0):
        fail("outcome.cost_usd must be non-negative")
    if outcome.get("status") not in STATUSES:
        fail("outcome.status must be one of %s" % sorted(STATUSES))
    if not isinstance(outcome.get("escaped_defect"), bool):
        fail("outcome.escaped_defect must be a boolean")
    for key in ("operator_interventions", "duration_ms"):
        value = outcome.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            fail("outcome.%s must be a non-negative integer" % key)
    if gate == "halt" and outcome.get("status") != "halted":
        fail("halt gate requires outcome.status halted")
    if gate != "halt" and outcome.get("status") == "halted":
        fail("halted outcome requires gate halt")

    return violations


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate one harness telemetry record.")
    parser.add_argument("path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        record = json.loads(Path(args.path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("telemetry: cannot read %s: %s" % (args.path, exc))
        return 2
    if not isinstance(record, dict):
        print("telemetry: record must be a JSON object")
        return 2
    violations = check(record)
    if args.json:
        print(json.dumps({"path": args.path, "violations": violations}))
    else:
        for violation in violations:
            print("FAIL %s" % violation)
        print("telemetry: %d violation(s)" % len(violations))
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
