#!/usr/bin/env python3
"""Deterministic token-efficiency and cache-prefix checks.

This is the static half of AS-01..AS-12. It cannot measure a cache hit rate;
it can prove that the assembled static prompt has no volatile bytes, no repeated
instruction lines, a declared profile set, and a stable policy pin.

Usage:
    python3 tooling/check_token_efficiency.py [--json] [--root PATH]

Exit 0 when clean, 1 on any violation. Warnings do not fail the gate.
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "standards" / "cache-profiles.json"
PROFILE_PIN = ROOT / "standards" / "cache-profiles.pin.json"
ASSEMBLY = ROOT / "standards" / "prompt-assembly.md"
CATALOG = ROOT / "CATALOG.md"
VOLATILE = [
    (re.compile(r"\b20\d{2}-\d{2}-\d{2}\b"), "ISO date"),
    (re.compile(r"\b20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}"), "timestamp"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "UUID"),
    (re.compile(r"\blocalhost:\d+\b", re.I), "localhost port"),
    (re.compile(r"(?<![\w/])/tmp/"), "temp path"),
    (re.compile(r"\bpid=\d+\b", re.I), "PID"),
    (re.compile(r"\bseed=\d+\b", re.I), "seed"),
    (re.compile(r"\b(?:created|updated):\s*\S+", re.I), "frontmatter date in body"),
    (re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b", re.I), "month-name date"),
    (re.compile(r"\b\d{4}/\d{1,2}/\d{1,2}\b"), "slash date"),
    (re.compile(r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b", re.I), "day-first date"),
    (re.compile(r"\b(?:today'?s date|current time|hostname\s*=|cwd\s*=|epoch\s*=\s*\d+)", re.I), "runtime metadata"),
    (re.compile(r"\b\d{1,2}:\d{2}\s*(?:UTC|GMT)\b", re.I), "clock time"),
]
TTLS = {"5m", "1h", "30m", "12h", "implicit", "best-effort", "lru", "none"}
RULE_IDS = ["AS-%02d" % number for number in range(1, 15)]


def body_of(text):
    match = re.match(r"(?s)^---\s*\n.*?\n---\s*\n?(.*)$", text)
    return match.group(1) if match else text


def token_estimate(text):
    return max(1, len(text.encode("utf-8")) // 4)


def block_hashes(body):
    layers = {}
    for tag in ("role", "hard_rules", "doctrine", "workflow", "conduct", "output"):
        match = re.search(r"(?ms)^\s*<%s>.*?</%s>" % (tag, tag), body)
        if match:
            layers[tag] = hashlib.sha256(match.group(0).encode("utf-8")).hexdigest()
    return layers


def normalized(line):
    value = re.sub(r"[^a-z0-9 ]", "", line.lower())
    return re.sub(r"\s+", " ", value).strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--hash", action="store_true",
                        help="print each carrier's prefix hash and layer hashes")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--update-pin", action="store_true",
                        help="rewrite cache-profiles.pin.json after a reviewed profile change")
    args = parser.parse_args(argv)
    if args.update_pin:
        root = Path(args.root).resolve()
        digest = hashlib.sha256((root / "standards" / "cache-profiles.json").read_bytes()).hexdigest()
        (root / "standards" / "cache-profiles.pin.json").write_text(
            json.dumps({"sha256": digest}, indent=2) + "\n")
        print("cache profile pin updated: %s" % digest)
        return 0
    root = Path(args.root).resolve()
    errors = []
    warnings = []

    try:
        profiles = json.loads((root / "standards" / "cache-profiles.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("FAIL cache profiles: %s" % exc)
        return 1
    version = profiles.get("version")
    if not isinstance(version, str) or not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+$", version):
        errors.append("cache-profiles.json version must be semver")
    try:
        pin = json.loads((root / "standards" / "cache-profiles.pin.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        errors.append("cache-profiles.pin.json: %s" % exc)
        pin = {}
    actual_hash = hashlib.sha256(
        (root / "standards" / "cache-profiles.json").read_bytes()).hexdigest()
    if pin.get("sha256") != actual_hash:
        errors.append("cache-profiles.json does not match cache-profiles.pin.json")
    if profiles.get("max_breakpoints") != 4:
        errors.append("cache-profiles.json max_breakpoints must be 4")
    default_min = profiles.get("min_tokens_default")
    if not isinstance(default_min, int) or default_min < 1:
        errors.append("cache-profiles.json min_tokens_default must be positive")
    for key in ("as_of", "review_by"):
        value = profiles.get(key)
        try:
            date.fromisoformat(value)
        except (TypeError, ValueError):
            errors.append("cache-profiles.json %s must be an ISO date" % key)
    if isinstance(profiles.get("review_by"), str):
        try:
            if date.fromisoformat(profiles["review_by"]) < date.today():
                warnings.append("cache profile review_by %s has passed" % profiles["review_by"])
        except ValueError:
            pass
    profile_rows = profiles.get("profiles", [])
    if not isinstance(profile_rows, list) or len(profile_rows) < 4:
        errors.append("cache-profiles.json needs at least 4 profiles")
    required_profiles = {"anthropic-5m", "openai-30m", "gemini-2.5", "vllm-apc"}
    seen_profiles = set()
    for profile in profile_rows:
        pid = profile.get("id")
        if pid in seen_profiles:
            errors.append("cache profile duplicate id: %s" % pid)
        seen_profiles.add(pid)
        for key in ("id", "vendor", "min_tokens", "write_multiplier",
                    "read_multiplier", "ttl"):
            if key not in profile:
                errors.append("cache profile missing %s" % key)
        if not isinstance(profile.get("min_tokens"), int) or profile.get("min_tokens", 0) < 1:
            errors.append("cache profile %s min_tokens must be positive" % pid)
        if profile.get("ttl") not in TTLS:
            errors.append("cache profile %s ttl is not canonical" % pid)
        for key in ("evidence", "claim"):
            if key not in profile:
                errors.append("cache profile %s missing %s" % (pid, key))
        if profile.get("claim") not in ("stated", "likely", "unverified"):
            errors.append("cache profile %s claim is not canonical" % pid)
    missing_profiles = sorted(required_profiles - seen_profiles)
    if missing_profiles:
        errors.append("cache profiles missing required ids: %s"
                      % ", ".join(missing_profiles))

    assembly_path = root / "standards" / "prompt-assembly.md"
    if not assembly_path.is_file():
        errors.append("missing standards/prompt-assembly.md")
    else:
        assembly = assembly_path.read_text(encoding="utf-8")
        required_anchors = {
            "AS-01": ["identical across requests", "no timestamps"],
            "AS-02": ["user turn", "static prefix"],
            "AS-03": ["separate message", "prefix"],
            "AS-04": ["reference file", "only when"],
            "AS-05": ["at most four breakpoints", "volatile"],
            "AS-07": ["retrieved", "secrets"],
            "AS-08": ["cache read tokens", "prefix hash"],
            "AS-06": ["mask", "tool-set version"],
            "AS-09": ["read the model minimum", "do not pad a prefix"],
            "AS-10": ["declare the cache layers", "first divergent layer, not just the file"],
            "AS-11": ["deterministic serialization: no timestamps", "byte-identical logical prompt"],
            "AS-12": ["never rewrite, reorder, delete", "hit-rate delta"],
            "AS-13": ["regenerated", "tail"],
            "AS-14": ["base", "default updated"],
        }
        for rule in RULE_IDS:
            if not re.search(r"(?m)^## %s -- " % re.escape(rule), assembly):
                errors.append("prompt-assembly missing rule %s" % rule)
                continue
            match = re.search(r"(?ms)^## %s -- [^\n]*\n(.*?)(?=^## |\Z)" % re.escape(rule), assembly)
            body = " ".join(match.group(1).lower().split()) if match else ""
            if len(body) < 120:
                errors.append("prompt-assembly %s body is too short (%d chars)"
                              % (rule, len(body)))
            for needle in required_anchors.get(rule, []):
                if needle not in body:
                    errors.append("prompt-assembly %s body missing anchor: %s"
                                  % (rule, needle))

    catalog = (root / "CATALOG.md").read_text(encoding="utf-8") \
        if (root / "CATALOG.md").is_file() else ""
    if version and ("Cache policy: %s" % version) not in catalog:
        errors.append("CATALOG.md missing 'Cache policy: %s' pin" % version)

    carriers = sorted(list((root / "agents").rglob("*.md"))
                      + list((root / "prompts" / "tasks").glob("*.md")))
    if not carriers:
        errors.append("no carriers found")
    tokens = []
    hashes = {}
    for path in carriers:
        text = path.read_text(encoding="utf-8")
        body = body_of(text)
        rel = path.relative_to(root).as_posix()
        for pattern, label in VOLATILE:
            for line_no, line in enumerate(body.splitlines(), 1):
                if pattern.search(line):
                    errors.append("%s:%d volatile %s in static prefix"
                                  % (rel, line_no, label))
                    break
        seen = {}
        for line in body.splitlines():
            key = normalized(line)
            if len(key.split()) < 8:
                continue
            if key in seen:
                errors.append("%s duplicates an instruction line: %s"
                              % (rel, key[:60]))
                break
            seen[key] = True
        estimate = token_estimate(body)
        tokens.append(estimate)
        hashes[rel] = {"prefix": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                       "tokens": estimate, "layers": block_hashes(body)}
        if isinstance(default_min, int) and estimate < default_min:
            warnings.append("%s static prefix is %d tokens, below default minimum %d"
                            % (rel, estimate, default_min))
        if not body.strip():
            errors.append("%s has an empty body" % rel)

    for path in sorted((root / "prompts" / "workspace").glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(root).as_posix()
        for line in text.splitlines():
            if line.lstrip().startswith("#"):
                continue
            for pattern, label in VOLATILE:
                if pattern.search(line):
                    errors.append("%s volatile %s in workspace prompt" % (rel, label))
                    break

    for skill in sorted((root / "skills").glob("**/SKILL.md")):
        rel = skill.relative_to(root).as_posix()
        if "/vendor/" in "/" + rel:
            continue
        text = skill.read_text(encoding="utf-8")
        estimate = token_estimate(body_of(text))
        if estimate > 1500:
            errors.append("%s body is %d tokens, over the 1500 token cap"
                          % (rel, estimate))
        desc = re.search(r"(?ms)^description:\s*(.*?)(?=\n[a-z_]+:)", text)
        if desc:
            words = len(desc.group(1).split())
            if words > 90:
                errors.append("%s description is %d words, over 90" % (rel, words))
            elif words > 70:
                warnings.append("%s description is %d words, over 70" % (rel, words))
            elif words < 25:
                warnings.append("%s description is %d words, below 25" % (rel, words))

    coverage = {
        profile["id"]: sum(1 for value in tokens if value >= profile["min_tokens"])
        for profile in profile_rows if isinstance(profile, dict)
    }
    summary = {
        "carriers": len(carriers),
        "hashes": hashes,
        "coverage_by_profile": coverage,
        "prefix_tokens": {
            "min": min(tokens) if tokens else 0,
            "median": int(median(tokens)) if tokens else 0,
            "max": max(tokens) if tokens else 0,
        },
        "errors": errors,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        if args.hash:
            for rel, value in sorted(hashes.items()):
                print("HASH %s %s %d" % (rel, value["prefix"], value["tokens"]))
                for tag, digest in sorted(value["layers"].items()):
                    print("LAYER %s %s %s" % (rel, tag, digest))
        for error in errors:
            print("FAIL " + error)
        for warning in warnings:
            print("WARN " + warning)
        coverage_text = ", ".join("%s %d/%d" % (key, value, len(carriers))
                                  for key, value in sorted(coverage.items()))
        print("token-efficiency: %d carriers, prefix tokens %d/%d/%d, %d violation(s), %d warning(s)"
              % (len(carriers), summary["prefix_tokens"]["min"],
                 summary["prefix_tokens"]["median"], summary["prefix_tokens"]["max"],
                 len(errors), len(warnings)))
        print("profile coverage: " + coverage_text)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
