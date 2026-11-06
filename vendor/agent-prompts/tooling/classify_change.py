#!/usr/bin/env python3
"""Classify a change for the STOPP gate (SG-01..SG-09).

This is a checklist, not a risk model. It returns ``fast-path`` only for a
one-file cosmetic edit with a real verification command; everything else is
``full-stopp``; an exception conflict or a missing required fact is ``halt``.

Exit codes: 0 fast-path or full-stopp, 2 invalid input, 3 halt.

Usage:
    python3 tooling/classify_change.py --kind comment --files 1 --lines 1 \
        --verify-command "docker compose config -q"
    python3 tooling/classify_change.py --kind behavior --files 1 --lines 1 \
        --verify-command "make test" --json

The ``--kind`` value is declarative. SG-03 is a manual check: a one-line image
tag, port, healthcheck, permission, or dependency change must be declared as
``behavior``, not as a cosmetic kind.
"""

import argparse
import json
import sys

COSMETIC = {"comment", "format", "typo", "whitespace"}
KINDS = ("comment", "format", "typo", "whitespace", "behavior",
         "schema", "security", "deploy")
MAX_FILES = 1
MAX_LINES = 50
TRIVIAL_VERIFY = {"true", ":", "echo", "echo ok", "echo done"}


def classify(kind, files, lines, verify_command, exception_conflict=False,
             ambiguous=False, parsed_unchanged=False, path=""):
    reasons = []
    if exception_conflict:
        return "halt", ["exception-registry conflict: HALT and ask the operator"]
    if ambiguous:
        return "halt", ["missing required fact: HALT and ask before editing"]
    if kind not in COSMETIC:
        reasons.append("%s change is not cosmetic" % kind)
    if kind == "format" and not parsed_unchanged:
        reasons.append("formatting requires --parsed-unchanged")
    if files != MAX_FILES:
        reasons.append("%d files does not equal the fast-path limit of %d"
                       % (files, MAX_FILES))
    if lines > MAX_LINES:
        reasons.append("%d lines exceeds the fast-path limit of %d"
                       % (lines, MAX_LINES))
    if not verify_command.strip():
        reasons.append("no verification command")
    elif verify_command.strip().lower() in TRIVIAL_VERIFY:
        reasons.append("verification command is trivial")
    if reasons:
        return "full-stopp", reasons
    where = " in %s" % path if path else ""
    return "fast-path", ["one-file %s edit with verification%s" % (kind, where)]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Classify a change for the STOPP gate.")
    parser.add_argument("--kind", choices=KINDS, required=True)
    parser.add_argument("--path", default="", help="the one file being changed")
    parser.add_argument("--files", type=int, required=True)
    parser.add_argument("--lines", type=int, required=True)
    parser.add_argument("--verify-command", default="")
    parser.add_argument("--exception-conflict", action="store_true",
                        help="the change conflicts with an exception-registry row")
    parser.add_argument("--ambiguous", action="store_true",
                        help="a required fact is missing")
    parser.add_argument("--parsed-unchanged", action="store_true",
                        help="for --kind format: the parsed artifact is unchanged")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.files < 1 or args.lines < 0:
        print("classify-change: files must be >=1 and lines >=0")
        return 2
    gate, reasons = classify(
        args.kind, args.files, args.lines, args.verify_command,
        exception_conflict=args.exception_conflict,
        ambiguous=args.ambiguous,
        parsed_unchanged=args.parsed_unchanged,
        path=args.path)
    result = {
        "gate": gate,
        "kind": args.kind,
        "path": args.path,
        "files": args.files,
        "lines": args.lines,
        "verification": args.verify_command,
        "reasons": reasons,
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Gate: %s" % gate)
        print("Kind: %s" % args.kind)
        print("Path: %s" % (args.path or "-"))
        print("Files: %d" % args.files)
        print("Lines: %d" % args.lines)
        print("Verification: %s" % (args.verify_command or "-"))
        for reason in reasons:
            print("Reason: %s" % reason)
    return 3 if gate == "halt" else 0


if __name__ == "__main__":
    sys.exit(main())
