#!/usr/bin/env python3
"""Render the Kilo agent adapter from packs/wmkeyboard/agents.yaml.

The library renderer owns the neutral body; this script adds the Kilo
frontmatter (mode, permissions, description) and writes `.kilo/agents/`.
Every write profile is scoped and its fallback is safe: an unmatched edit is
denied, an unmatched command asks.

    python scripts/render-kilo-agents.py --write
    python scripts/render-kilo-agents.py --check

Exit 0 clean, 1 drift or invalid output, 2 unreadable input.
"""

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vendor_integrity

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "vendor" / "agent-prompts"
PACK = ROOT / "packs" / "wmkeyboard" / "agents.yaml"
LIVE_DIR = ROOT / ".kilo" / "agents"
LOCK = ROOT / "packs" / "wmkeyboard" / "agents.lock.json"

SAFE_BASH = {
    "*": "ask",
    "git status*": "allow",
    "git diff*": "allow",
    "git log*": "allow",
    "git show*": "allow",
    "git branch*": "allow",
    "cargo *": "allow",
    "./gradlew *": "allow",
    "gradlew *": "allow",
    "python *": "allow",
    "python3 *": "allow",
    "npm *": "allow",
    "git commit*": "ask",
    "git push*": "deny",
    "rm *": "deny",
    "Remove-Item *": "deny",
    "del *": "deny",
}

SECRET_DENY = {
    "fastlane/play-service-account.json": "deny",
    "**/*.jks": "deny",
    "**/*.keystore": "deny",
    "**/*.p12": "deny",
    "**/*.pem": "deny",
    "**/*.pk8": "deny",
    ".env*": "deny",
    "local.properties": "deny",
}

READ = {
    "read": "allow",
    "grep": "allow",
    "glob": "allow",
    "webfetch": "allow",
    "edit": "deny",
    "bash": "deny",
    "task": "deny",
}
READ_BASH = dict(READ, bash=dict(SAFE_BASH))
READ_TASK = dict(READ, bash=dict(SAFE_BASH), task="allow")
ORCHESTRATOR = {
    "read": "allow",
    "grep": "allow",
    "glob": "allow",
    "webfetch": "allow",
    "edit": {"*": "deny", ".kilo/orchestrator/**": "allow"},
    "bash": dict(SAFE_BASH),
    "task": "allow",
}
SYNTHESIZER = {
    "read": "allow",
    "grep": "deny",
    "glob": "deny",
    "webfetch": "deny",
    "edit": "deny",
    "bash": "deny",
    "task": "deny",
}


def write_profile(allowed, fallback="deny"):
    edit = {"*": fallback}
    edit.update({pattern: "allow" for pattern in allowed})
    edit.update(SECRET_DENY)
    return {
        "read": "allow",
        "grep": "allow",
        "glob": "allow",
        "webfetch": "deny",
        "edit": edit,
        "bash": dict(SAFE_BASH),
        "task": "deny",
    }


PROFILES = {
    "read": READ,
    "read-bash": READ_BASH,
    "read-task": READ_TASK,
    "orchestrator": ORCHESTRATOR,
    "synthesizer": SYNTHESIZER,
    "write-native": write_profile(["native/**"]),
    "write-kotlin": write_profile(["app/**", "core/**", "feature/**"]),
    "write-general": write_profile([
        "app/**", "core/**", "feature/**", "tools/**", "native/**",
        "scripts/**",
    ]),
    "write-tests": write_profile([
        "**/src/test/**", "**/src/androidTest/**",
    ]),
    "write-docs": write_profile([
        "docs/**", "README.md", "SETTINGS_REDESIGN.md", "release-notes/**",
    ]),
    "write-ci": write_profile([".github/**", "scripts/**"]),
    "write-release": write_profile([
        "release-notes/**", "fastlane/metadata/**", "docs/**", "README.md",
        "gradle.properties",
    ]),
    "write-batch": write_profile([
        "app/**", "core/**", "feature/**", "tools/**", "native/**",
        "scripts/**", "docs/**",
    ], fallback="ask"),
}


def load_renderer():
    vendor_integrity.verify_tree()
    path = LIBRARY / "tooling" / "render_agents.py"
    spec = importlib.util.spec_from_file_location("library_render_agents", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build():
    renderer = load_renderer()
    manifest = yaml.safe_load(PACK.read_text(encoding="utf-8"))
    if manifest.get("schema") != "agent-pack/1":
        raise ValueError("%s: schema must be agent-pack/1" % PACK)
    outputs = {}
    for entry in manifest["agents"]:
        name = entry["name"]
        if entry.get("permission") not in PROFILES:
            raise ValueError("%s: unknown permission %r"
                             % (name, entry.get("permission")))
        _rendered_path, body = renderer.render_agent(
            entry, PACK, LIBRARY, ROOT, LIBRARY / "fragments")
        meta, _ = renderer.parse_frontmatter(
            (LIBRARY / entry["template"]).read_text(encoding="utf-8"))
        description = (entry.get("description") or meta.get("purpose")
                       or meta.get("name") or name)
        front = {
            "description": " ".join(str(description).split()),
            "mode": entry.get("mode", "subagent"),
            "permission": PROFILES[entry["permission"]],
        }
        text = ("---\n"
                + yaml.safe_dump(front, sort_keys=False, width=4096)
                + "---\n\n"
                + body)
        try:
            text.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError("%s: non-ASCII output: %s" % (name, exc))
        outputs[name] = {
            "text": text,
            "template": entry["template"],
            "rendered_sha256": sha256(body),
            "live_sha256": sha256(text),
        }
    return outputs


def lock_document(outputs, library_commit):
    return {
        "schema": "agent-pack-lock/1",
        "project": "wmkeyboard",
        "library_commit": library_commit,
        "agents": {
            name: {
                "template": item["template"],
                "rendered_sha256": item["rendered_sha256"],
                "live_sha256": item["live_sha256"],
            }
            for name, item in sorted(outputs.items())
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.write == args.check:
        print("choose exactly one of --write or --check", file=sys.stderr)
        return 2
    try:
        outputs = build()
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2

    drift = []
    for name, item in sorted(outputs.items()):
        path = LIVE_DIR / ("%s.md" % name)
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item["text"], encoding="utf-8")
        elif not path.is_file() or path.read_text(encoding="utf-8") != item["text"]:
            drift.append(str(path.relative_to(ROOT)))

    manifest = yaml.safe_load(PACK.read_text(encoding="utf-8"))
    lock = json.dumps(
        lock_document(outputs, manifest["library_commit"]),
        indent=2, sort_keys=True) + "\n"
    if args.write:
        LOCK.write_text(lock, encoding="utf-8")
    elif not LOCK.is_file() or LOCK.read_text(encoding="utf-8") != lock:
        drift.append(str(LOCK.relative_to(ROOT)))

    if drift:
        print("DRIFT: " + ", ".join(drift), file=sys.stderr)
        return 1
    print("kilo agents: %d rendered, 0 drift" % len(outputs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
