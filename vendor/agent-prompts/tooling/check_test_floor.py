#!/usr/bin/env python3
"""Fail when a collected test disappears from the add-only test-identity manifest.

A count floor is a weak guard. At 441 collected tests a `FLOOR = 330` leaves 111
tests of headroom, so a hundred deleted tests still pass the gate, and raising
the constant only buys the next hundred. The guard that actually holds is
identity: `tooling/test-manifest.json` names every collected test function per
module, and a plain run fails when the manifest names a test the collection no
longer contains, printing the module and the test.

Additions stay cheap: a new test passes without a manifest edit and is reported
as new, so ordinary work needs no bookkeeping. `--write` merges the new names
into the manifest and exits 0. It never prunes: a name the collection no longer
has is kept and reported, because removing a test must be a reviewable diff
line. `--write --allow-removals` is the only way to drop a name, and it prints
every removal.

The count floor survives as a secondary backstop, not the primary guard: a
manifest that was gutted (or hand-edited down) would otherwise pass the identity
check with nothing left to compare. `FLOOR` catches that; the identity check
catches everything else. A plain run never writes the manifest.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_SCHEMA = "agent-prompts-test-manifest/1"
DEFAULT_MANIFEST = "tooling/test-manifest.json"
DEFAULT_TESTS = "tooling/tests"
# Secondary backstop against a gutted manifest, not the primary guard.
FLOOR = 330
PARAM_SUFFIX_RE = re.compile(r"\[[^\]]*\]$")


def collect(root, tests):
    """Return (module -> sorted names, errors) for the collected node ids.

    A node id is `<path>::<name>`, where `<name>` may carry a class path
    (`TestCase::test_x`) and a parametrization suffix (`test_x[1-a]`). The
    suffix is dropped so one parametrized test is one name; the class path is
    kept so two same-named methods stay distinct.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(tests), "--collect-only", "-q"],
        cwd=str(root), capture_output=True, text=True)
    if result.returncode != 0:
        return {}, ["could not collect %s\n%s" % (tests, (result.stdout or result.stderr)[-2000:])]
    modules = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if "::" not in line or line.startswith("="):
            continue
        module, _, rest = line.partition("::")
        name = PARAM_SUFFIX_RE.sub("", rest)
        if not name:
            continue
        path = Path(module)
        if path.is_absolute():
            try:
                module = path.resolve().relative_to(Path(root).resolve()).as_posix()
            except ValueError:
                module = path.as_posix()
        else:
            module = path.as_posix()
        modules.setdefault(module, set()).add(name)
    if not modules:
        return {}, ["could not collect %s: no test node ids in the output" % tests]
    return {module: sorted(names) for module, names in sorted(modules.items())}, []


def load_manifest(path, allow_missing=False):
    """Return (module -> names, errors) for a manifest file."""
    if not path.is_file():
        if allow_missing:
            return {}, []
        return {}, ["%s is missing; run --write to create it" % path.name]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, ["cannot read %s: %s" % (path, exc)]
    if not isinstance(data, dict):
        return {}, ["%s is not a JSON object" % path.name]
    if data.get("schema") != MANIFEST_SCHEMA:
        return {}, ["%s schema is not %s" % (path.name, MANIFEST_SCHEMA)]
    tests = data.get("tests")
    if not isinstance(tests, dict):
        return {}, ["%s has no tests mapping" % path.name]
    errors = []
    modules = {}
    for module, names in tests.items():
        if not isinstance(module, str) or not module:
            errors.append("%s has a non-string module key" % path.name)
            continue
        if not isinstance(names, list) or not all(isinstance(name, str) and name for name in names):
            errors.append("%s: %s is not a list of test names" % (path.name, module))
            continue
        modules[module] = sorted(set(names))
    return modules, errors


def write_manifest(path, modules):
    data = {"schema": MANIFEST_SCHEMA,
            "tests": {module: list(modules[module]) for module in sorted(modules)}}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def diff_names(manifest, collected):
    """Return (missing, new) as sorted [(module, name)] pairs."""
    missing = []
    new = []
    for module in sorted(manifest):
        present = set(collected.get(module, ()))
        for name in manifest[module]:
            if name not in present:
                missing.append((module, name))
    for module in sorted(collected):
        known = set(manifest.get(module, ()))
        for name in collected[module]:
            if name not in known:
                new.append((module, name))
    return missing, new


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(ROOT),
                        help="tree the manifest paths are relative to (default: the library root)")
    parser.add_argument("--tests", default=DEFAULT_TESTS,
                        help="test path relative to --root (default: %s)" % DEFAULT_TESTS)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST,
                        help="manifest path relative to --root (default: %s)" % DEFAULT_MANIFEST)
    parser.add_argument("--write", action="store_true",
                        help="merge the new names into the manifest and exit 0")
    parser.add_argument("--allow-removals", action="store_true",
                        help="with --write, also drop names the collection no longer has")
    args = parser.parse_args(argv)
    if args.allow_removals and not args.write:
        print("test-floor: --allow-removals needs --write")
        return 2

    root = Path(args.root).resolve()
    manifest_path = root / args.manifest
    collected, errors = collect(root, args.tests)
    for message in errors:
        print("test-floor: FAIL %s" % message)
    if errors:
        return 1
    manifest, errors = load_manifest(manifest_path, allow_missing=args.write)
    for message in errors:
        print("test-floor: FAIL %s" % message)
    if errors:
        return 1

    missing, new = diff_names(manifest, collected)
    manifest_total = sum(len(names) for names in manifest.values())
    count = sum(len(names) for names in collected.values())

    if args.write:
        merged = {module: list(names) for module, names in manifest.items()}
        for module in collected:
            merged.setdefault(module, [])
            merged[module] = sorted(set(merged[module]) | set(collected[module]))
        removed = []
        if args.allow_removals:
            removed = missing
            for module, name in removed:
                print("test-floor: removed %s::%s" % (module, name))
            removed_set = set(removed)
            merged = {module: [name for name in names
                               if (module, name) not in removed_set]
                      for module, names in merged.items()}
            merged = {module: names for module, names in merged.items() if names}
        write_manifest(manifest_path, merged)
        print("test-floor: wrote %s (%d added, %d removed, %d names)"
              % (args.manifest, len(new), len(removed),
                 sum(len(names) for names in merged.values())))
        if missing and not args.allow_removals:
            print("test-floor: kept %d name(s) the collection no longer has; "
                  "pruning needs --write --allow-removals" % len(missing))
        return 0

    failed = False
    if missing:
        print("test-floor: identity FAILED: %d manifest test(s) not collected"
              % len(missing))
        for module, name in missing:
            print("  missing %s::%s" % (module, name))
        failed = True
    else:
        print("test-floor: identity OK: %d manifest name(s) all collected"
              % manifest_total)
    if new:
        print("test-floor: %d new test(s) not yet in the manifest (additions are allowed)"
              % len(new))
    else:
        print("test-floor: 0 new tests")
    if count < manifest_total:
        print("test-floor: count backstop FAILED: %d collected, manifest carries %d"
              % (count, manifest_total))
        failed = True
    # The floor is a repository-level backstop, so it is evaluated for the
    # repository's own suite only. A fixture tree passed through --tests is by
    # definition smaller and must not trip a repo-level constant.
    own_suite = Path(args.tests).resolve() == (root / DEFAULT_TESTS).resolve()
    if own_suite and count < FLOOR:
        print("test-floor: FLOOR backstop FAILED: %d collected, floor is %d"
              % (count, FLOOR))
        failed = True
    if failed:
        return 1
    print("test-floor: %d distinct tests collected, %d pinned (floor %d backstop)"
          % (count, manifest_total, FLOOR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
