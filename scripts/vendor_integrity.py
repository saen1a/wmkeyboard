#!/usr/bin/env python3
"""Hash and verify the vendored agent-prompts tree.

The pin in VENDORED.md is a label. This module is the integrity check: every
file below vendor/agent-prompts is hashed into packs/wmkeyboard/vendor.lock.json
and compared before any vendored Python is imported.

    python scripts/vendor_integrity.py --write
    python scripts/vendor_integrity.py --check
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "vendor" / "agent-prompts"
LOCK = ROOT / "packs" / "wmkeyboard" / "vendor.lock.json"
EXCLUDE_NAMES = {"VENDORED.md"}
EXCLUDE_PARTS = {".git", ".forgejo", "__pycache__"}


def tree(root):
    files = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel in EXCLUDE_NAMES:
            continue
        if any(part in EXCLUDE_PARTS for part in path.parts):
            continue
        files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def document():
    return {
        "schema": "vendor-tree/1",
        "project": "wmkeyboard",
        "library": "agent-prompts",
        "files": tree(LIBRARY),
    }


def write_tree():
    lock = json.dumps(document(), indent=2, sort_keys=True) + "\n"
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(lock, encoding="utf-8")
    return len(document()["files"])


def verify_tree():
    if not LOCK.is_file():
        raise ValueError("missing %s" % LOCK.relative_to(ROOT))
    try:
        expected = json.loads(LOCK.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("%s: %s" % (LOCK.relative_to(ROOT), exc))
    wanted = expected.get("files")
    if not isinstance(wanted, dict) or not wanted:
        raise ValueError("%s: files map is missing or empty"
                         % LOCK.relative_to(ROOT))
    actual = tree(LIBRARY)
    missing = sorted(set(wanted) - set(actual))
    extra = sorted(set(actual) - set(wanted))
    changed = sorted(name for name in set(actual) & set(wanted)
                     if actual[name] != wanted[name])
    if missing or extra or changed:
        raise ValueError(
            "vendor tree drift: missing=%s extra=%s changed=%s"
            % (missing[:5], extra[:5], changed[:5]))
    return len(actual)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.write == args.check:
        print("choose exactly one of --write or --check", file=sys.stderr)
        return 2
    if not LIBRARY.is_dir():
        print("ERROR: %s is missing" % LIBRARY, file=sys.stderr)
        return 2
    try:
        if args.write:
            count = write_tree()
            print("wrote %s (%d files)"
                  % (LOCK.relative_to(ROOT), count))
        else:
            count = verify_tree()
            print("vendor tree: %d files verified" % count)
    except (OSError, ValueError) as exc:
        print("FAIL %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
