#!/usr/bin/env python3
"""Verify the vendored agent pack against its canon.

Checks:
  1. the vendor tree matches packs/wmkeyboard/vendor.lock.json
  2. the library pin agrees across VENDORED.md, agents.yaml, and the renderer
  3. the fragment hashes match the vendored manifest
  4. the neutral bodies re-render with zero drift
  5. the generated manifest has zero drift
  6. the live Kilo agents re-render with zero drift
  7. every vendored skill is byte-identical to its canon directory
  8. every project skill has a name and description
  9. no stale skill directory is left behind
 10. every live agent has frontmatter and no slot residue
 11. every write agent has a scoped edit and bash permission
 12. no project ops agent carries containeromat compose text

Exit 0 clean, 1 violation, 2 unreadable input.
"""

import hashlib
import re
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vendor_integrity

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "vendor" / "agent-prompts"
PACK = ROOT / "packs" / "wmkeyboard"
LIVE = ROOT / ".kilo" / "agents"
SKILLS = ROOT / ".kilo" / "skills"
COMMANDS = ROOT / ".kilo" / "command"
SLOT_RE = re.compile(r"\{\{[A-Z0-9_]+\}\}")

problems = []


def fail(message):
    problems.append(message)


def run(label, argv, cwd=ROOT):
    result = subprocess.run(
        argv, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    output = (result.stdout or "").strip()
    error = (result.stderr or "").strip()
    if result.returncode != 0:
        fail("%s: exit %d%s" % (
            label, result.returncode,
            (": " + (error or output)) if (error or output) else ""))
    else:
        print("ok   %s%s" % (label, (": " + output) if output else ""))


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("%s has no frontmatter" % path)
    lines = text.split("\n")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            data = yaml.safe_load("\n".join(lines[1:index])) or {}
            if not isinstance(data, dict):
                raise ValueError("%s frontmatter is not a mapping" % path)
            return data
    raise ValueError("%s has unclosed frontmatter" % path)


def tree(root):
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()).hexdigest()
    return files


def check_pin():
    for name in ("agents.yaml", "skills.yaml", "exclusions.yaml"):
        if not (PACK / name).is_file():
            fail("packs/wmkeyboard/%s is missing" % name)
            return
    try:
        vendored = (LIBRARY / "VENDORED.md").read_text(encoding="utf-8")
    except OSError as exc:
        fail("VENDORED.md: %s" % exc)
        return
    match = re.search(r"Pinned commit: `([0-9a-f]{40})`", vendored)
    if not match:
        fail("VENDORED.md: no pinned commit")
        return
    pin = match.group(1)
    manifest = yaml.safe_load((PACK / "agents.yaml").read_text(encoding="utf-8"))
    if manifest.get("library_commit") != pin:
        fail("agents.yaml: library_commit %r != %s"
             % (manifest.get("library_commit"), pin))
    skills = yaml.safe_load((PACK / "skills.yaml").read_text(encoding="utf-8"))
    if skills.get("library_commit") != pin:
        fail("skills.yaml: library_commit != %s" % pin)
    exclusions = yaml.safe_load(
        (PACK / "exclusions.yaml").read_text(encoding="utf-8"))
    if exclusions.get("library_commit") != pin:
        fail("exclusions.yaml: library_commit != %s" % pin)
    print("ok   library pin %s" % pin[:12])


def check_skills():
    if not SKILLS.is_dir():
        fail("skills: %s is missing" % SKILLS)
        return
    manifest = yaml.safe_load((PACK / "skills.yaml").read_text(encoding="utf-8"))
    for entry in manifest.get("library_skills", []):
        source = LIBRARY / "skills" / entry
        name = entry.split("/")[-1]
        target = SKILLS / name
        if not source.is_dir():
            fail("skills.yaml: missing canon %s" % entry)
            continue
        if not target.is_dir():
            fail("skills: missing %s" % name)
            continue
        if tree(source) != tree(target):
            fail("skills: %s differs from %s" % (name, entry))
    for name in manifest.get("project_skills", []):
        path = SKILLS / name / "SKILL.md"
        if not path.is_file():
            fail("project skill: missing %s/SKILL.md" % name)
            continue
        data = frontmatter(path)
        if not data.get("name") or not data.get("description"):
            fail("project skill %s: name or description missing" % name)
    expected = {entry.split("/")[-1]
                for entry in manifest.get("library_skills", [])}
    expected |= set(manifest.get("project_skills", []))
    actual = {path.name for path in SKILLS.iterdir() if path.is_dir()}
    for name in sorted(actual - expected):
        fail("skills: stale directory %s is not in skills.yaml" % name)
    print("ok   skills %d library, %d project"
          % (len(manifest.get("library_skills", [])),
             len(manifest.get("project_skills", []))))


def check_live_agents():
    manifest = yaml.safe_load((PACK / "agents.yaml").read_text(encoding="utf-8"))
    expected = {entry["name"] for entry in manifest["agents"]}
    actual = {path.stem for path in LIVE.glob("*.md")}
    for name in sorted(expected - actual):
        fail("live agent: missing %s" % name)
    for name in sorted(actual - expected):
        fail("live agent: %s is not in the pack" % name)
    for name in sorted(expected & actual):
        path = LIVE / ("%s.md" % name)
        text = path.read_text(encoding="utf-8")
        if SLOT_RE.search(text):
            fail("live agent %s: slot residue" % name)
        try:
            text.encode("ascii")
        except UnicodeEncodeError:
            fail("live agent %s: non-ASCII" % name)
        try:
            data = frontmatter(path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            fail("live agent %s: %s" % (name, exc))
            continue
        if not data.get("description") or not data.get("mode"):
            fail("live agent %s: description or mode missing" % name)
    print("ok   live agents %d" % len(expected))


def check_permissions():
    write_profiles = {
        "write-native", "write-kotlin", "write-general", "write-tests",
        "write-docs", "write-ci", "write-release", "write-batch",
    }
    manifest = yaml.safe_load((PACK / "agents.yaml").read_text(encoding="utf-8"))
    checked = 0
    for entry in manifest["agents"]:
        if entry.get("permission") not in write_profiles:
            continue
        checked += 1
        path = LIVE / ("%s.md" % entry["name"])
        try:
            data = frontmatter(path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            fail("permission %s: %s" % (entry["name"], exc))
            continue
        permission = data.get("permission") or {}
        if not isinstance(permission.get("edit"), dict):
            fail("permission %s: edit is %r, expected a scoped map"
                 % (entry["name"], permission.get("edit")))
        if not isinstance(permission.get("bash"), dict):
            fail("permission %s: bash is %r, expected an allowlist map"
                 % (entry["name"], permission.get("bash")))
    print("ok   scoped permissions %d" % checked)


def check_project_content():
    project_agents = ["ci-implementer", "ops-executor", "wmk-release-engineer"]
    markers = ("compose stack", "docker compose", "deployed state file")
    for name in project_agents:
        path = LIVE / ("%s.md" % name)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").lower()
        if any(marker in text for marker in markers):
            fail("project agent %s: containeromat compose text remains" % name)
    for path in LIVE.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        if "wmkeyboard" not in text:
            fail("live agent %s: no project marker" % path.stem)
    print("ok   project content")


def check_commands():
    if not COMMANDS.is_dir():
        fail("commands: %s is missing" % COMMANDS)
        return
    for path in sorted(COMMANDS.glob("*.md")):
        try:
            data = frontmatter(path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            fail("command %s: %s" % (path.name, exc))
            continue
        if not data.get("description"):
            fail("command %s: description missing" % path.name)
    print("ok   commands %d" % len(list(COMMANDS.glob("*.md"))))


def main():
    if not LIBRARY.is_dir():
        print("ERROR: %s is missing" % LIBRARY, file=sys.stderr)
        return 2
    try:
        count = vendor_integrity.verify_tree()
        print("ok   vendor tree %d files" % count)
    except (OSError, ValueError) as exc:
        print("FAIL %s" % exc, file=sys.stderr)
        return 1
    check_pin()
    run("fragments", [sys.executable, "tooling/check_fragments.py"], LIBRARY)
    run("neutral render", [
        sys.executable, str(LIBRARY / "tooling" / "render_agents.py"),
        "--pack", "packs/wmkeyboard/agents.yaml", "--check",
        "--library-root", "vendor/agent-prompts", "--project-root", "."])
    run("manifest", [sys.executable, "scripts/gen-agent-pack.py", "--check"])
    run("kilo render", [sys.executable, "scripts/render-kilo-agents.py",
                        "--check"])
    check_skills()
    check_live_agents()
    check_permissions()
    check_project_content()
    check_commands()
    if problems:
        print("", file=sys.stderr)
        for problem in problems:
            print("FAIL %s" % problem, file=sys.stderr)
        return 1
    print("agent pack: verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
