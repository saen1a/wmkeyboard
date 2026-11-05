#!/usr/bin/env python3
"""Re-vendor agent-prompts with delete-then-copy semantics.

A copy-over leaves files the upstream removed. This tool deletes the old tree
(except VENDORED.md), copies the new one, rewrites VENDORED.md, and refreshes
the tree hash.

    python scripts/vendor-agent-prompts.py --library <checkout> \
        --commit <sha> --version <x.y.z>
    python scripts/vendor-agent-prompts.py --library <checkout> --check

Exit 0 clean, 1 drift or invalid source, 2 unreadable input.
"""

import argparse
import datetime
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "vendor" / "agent-prompts"
VENDORED = LIBRARY / "VENDORED.md"
IGNORE = shutil.ignore_patterns(".git", ".forgejo", "__pycache__")
EXCLUDE_PARTS = {".git", ".forgejo", "__pycache__"}

TEMPLATE = """# Vendored: agent-prompts

Source: {source}
Pinned commit: `{commit}`
Commit date: {date}
Library version: {version}
Vendored: {today}

This directory is a byte copy of the library at the pinned commit, excluding
`.git/`, `.forgejo/` and `__pycache__/`. It is the canon for the project's
skills, fragments, role templates, standards, prompts, and tooling.

## Rules

- Never edit a file below `vendor/agent-prompts/`. A divergence is drift, not a
  customization.
- Project behavior belongs in `packs/wmkeyboard/` (slots and overlays),
  `.kilo/agents/` (generated), `.kilo/skills/` (project skills), or `AGENTS.md`.
- A library change arrives by re-vendoring this directory and bumping the
  pinned commit in `packs/wmkeyboard/agents.yaml` and `packs/wmkeyboard/README.md`.

## Update procedure

From the project root:

```sh
git -C <library> fetch origin
git -C <library> checkout <new-commit>
python scripts/vendor-agent-prompts.py --library <library> \\
    --commit <new-commit> --version <x.y.z>
```

The tool deletes the old tree (except `VENDORED.md`), copies the new one,
rewrites this file, and refreshes `packs/wmkeyboard/vendor.lock.json`. Then run:

```sh
python scripts/gen-agent-pack.py --write
python vendor/agent-prompts/tooling/render_agents.py \\
    --pack packs/wmkeyboard/agents.yaml --write \\
    --library-root vendor/agent-prompts --project-root .
python scripts/render-kilo-agents.py --write
python scripts/verify-agent-pack.py
```

## Integrity

- Fragment hashes: `vendor/agent-prompts/tooling/fragments.manifest.json`.
- Whole-tree hashes: `packs/wmkeyboard/vendor.lock.json`.
- Rendered agent bodies: `packs/wmkeyboard/rendered/`.
- Live Kilo agents: `.kilo/agents/`.
- Output hashes: `packs/wmkeyboard/agents.lock.json`.

`scripts/verify-agent-pack.py` checks all four.
"""


def tree(root):
    files = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "VENDORED.md":
            continue
        if any(part in EXCLUDE_PARTS for part in path.parts):
            continue
        rel = path.relative_to(root).as_posix()
        files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def validate(source):
    required = [
        "tooling/render_agents.py",
        "fragments/agent-doctrine.md",
        "fragments/agent-conduct.md",
        "skills/general",
        "skills/shared",
        "agents",
    ]
    missing = [name for name in required if not (source / name).exists()]
    if missing:
        raise ValueError("%s: missing %s" % (source, ", ".join(missing)))


def clear(destination):
    for path in destination.iterdir():
        if path == VENDORED:
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def write_vendored(commit, version, date):
    text = TEMPLATE.format(
        source="https://forgejo.hellgate.cc/saenta/agent-prompts",
        commit=commit,
        date=date,
        version=version,
        today=datetime.date.today().isoformat(),
    )
    VENDORED.write_text(text, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", required=True)
    parser.add_argument("--commit")
    parser.add_argument("--version")
    parser.add_argument("--date", default="unknown")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    source = Path(args.library).resolve()
    try:
        validate(source)
    except (OSError, ValueError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2

    if args.check:
        if tree(source) != tree(LIBRARY):
            print("DRIFT: vendor/agent-prompts differs from %s" % source,
                  file=sys.stderr)
            return 1
        print("vendor: tree matches %s" % source)
        return 0

    if not args.commit or not args.version:
        print("ERROR: --commit and --version are required to write",
              file=sys.stderr)
        return 2
    try:
        clear(LIBRARY)
        shutil.copytree(source, LIBRARY, dirs_exist_ok=True, ignore=IGNORE)
        write_vendored(args.commit, args.version, args.date)
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import vendor_integrity
        count = vendor_integrity.write_tree()
    except (OSError, ValueError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    print("vendored %s at %s (%d files, hash refreshed)"
          % (args.version, args.commit[:12], count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
