#!/usr/bin/env python3
"""Verify the vendored fragments.

Two modes:

1. Manifest mode (default): sha256-check every fragment listed in
   ``tooling/fragments.manifest.json`` against ``fragments/``. This is the
   consumer-runnable drift check -- it needs no upstream checkout. The
   manifest pins the hash and version of every published fragment.

2. Legacy diagnostic (``--upstream <dir>``): byte-compare ``agent-conduct.md``
   against a historical containeromat templates directory. Both fragments are
   library-canonical as of 2026-10-26, so this mode is not a gate and does not
   define authority; the manifest is authoritative.

Prints one ``OK <fragment>`` / ``DIFF <fragment>`` line per check.
Exit 0 when all checks pass, 1 otherwise.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Both fragments are library-canonical; --upstream is a legacy diagnostic only.
UPSTREAM_FRAGMENTS = ["agent-conduct.md"]

# Runtime-agnostic conduct rules must be in every variant, not only in the one a
# given role carries: a consumer that projects the OMP or dsh surface would
# otherwise ship a conduct block missing a rule the library considers universal.
# The manifest declares them (`shared_conduct_rules`: fingerprint -> rule name) so
# a fixture manifest without that key is simply not subject to the rule.


def default_root():
    return Path(__file__).resolve().parent.parent


def default_manifest():
    return Path(__file__).resolve().parent / "fragments.manifest.json"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def check_manifest(root, manifest_path):
    ok = True
    if not manifest_path.is_file():
        print("DIFF manifest: not found at %s" % manifest_path)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("fragments", {})
    if not entries:
        print("DIFF manifest: no fragments listed")
        return 1
    doctrine_version = entries.get("agent-doctrine.md", {}).get("version")
    if manifest.get("version") != doctrine_version:
        print("DIFF manifest: top-level version %s does not match doctrine %s"
              % (manifest.get("version"), doctrine_version))
        ok = False
    actual = {path.name for path in (root / "fragments").glob("*.md")}
    if actual != set(entries):
        print("DIFF manifest: fragments on disk %s do not match entries %s"
              % (sorted(actual), sorted(entries)))
        ok = False
    variants = sorted(name for name in entries if name.startswith("agent-conduct"))
    shared = manifest.get("shared_conduct_rules", {})
    if not isinstance(shared, dict):
        print("DIFF manifest: shared_conduct_rules must be a mapping")
        ok = False
        shared = {}
    for fingerprint, rule in sorted(shared.items()):
        missing = [name for name in variants
                   if fingerprint not in (root / "fragments" / name).read_text(encoding="utf-8")]
        if missing:
            print("DIFF %s: shared conduct rule %r is missing from %s"
                  % ("conduct parity", rule, ", ".join(missing)))
            ok = False
        else:
            print("OK conduct parity: %s in all %d variant(s)" % (rule, len(variants)))
    for name, meta in sorted(entries.items()):
        local = root / "fragments" / name
        if not local.is_file():
            print("DIFF %s: fragment not found at %s" % (name, local))
            ok = False
            continue
        digest = sha256(local.read_bytes())
        if digest == meta.get("sha256"):
            print("OK %s (v%s)" % (name, meta.get("version", "?")))
        else:
            print("DIFF %s: sha256 mismatch (manifest %s, actual %s)"
                  % (name, meta.get("sha256", "?"), digest))
            ok = False
    return 0 if ok else 1


def check_upstream(root, upstream):
    ok = True
    for name in UPSTREAM_FRAGMENTS:
        local = root / "fragments" / name
        reference = upstream / name
        if not local.is_file():
            print("DIFF %s: local fragment not found at %s" % (name, local))
            ok = False
            continue
        if not reference.is_file():
            print("DIFF %s: upstream reference not found at %s" % (name, reference))
            ok = False
            continue
        if local.read_bytes() == reference.read_bytes():
            print("OK %s" % name)
        else:
            print("DIFF %s: differs from %s" % (name, reference))
            ok = False
    return 0 if ok else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--upstream", default=None,
                        help="legacy diagnostic: byte-compare agent-conduct.md against a historical containeromat directory")
    parser.add_argument("--manifest", default=None,
                        help="fragment manifest (default: tooling/fragments.manifest.json)")
    parser.add_argument("--root", default=str(default_root()), help="repo root (default: script parent)")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()

    if args.upstream:
        return check_upstream(root, Path(args.upstream).resolve())
    manifest_path = Path(args.manifest).resolve() if args.manifest else default_manifest()
    return check_manifest(root, manifest_path)


if __name__ == "__main__":
    sys.exit(main())
