#!/usr/bin/env python3
"""Static prompt-surface security checks (standards/prompt-security.md).

What this proves, deterministically and offline:

1. PS-03 -- no invisible or smuggling character in any instruction asset. The
   Tags block, zero-width characters, bidi controls, BOM, and the line/paragraph
   separators are reported with codepoint and line; a tags-decoded shadow is
   additionally searched for an override phrase that is absent from the raw text
   (the smuggling case).
2. PS-02 -- no "follow the instructions in <file/page/url>" directive in an
   instruction asset. An instruction asset may quote the pattern; it may not
   issue it.
3. PS-06/PS-09/PS-13 -- no secret-shaped literal. Placeholder forms
   (`sk-<redacted>`, `${VAR}`) are accepted; a marker with a real-looking body is
   a finding.
   A carrier that must quote the payload verbatim ends the line with
   `[ps-02-quoted-payload]`; the marker is reviewed, the exemption is not silent.
4. WARN PS-02 -- an instruction carrier that names a retrieval surface (web,
   fetch, browser, tool output, memory page, subagent return) but states no data
   boundary. Carriers are the files a runtime loads as instructions: agent and
   task prompts, `SKILL.md` bodies, the `references/` files a `SKILL.md` orders
   the runtime to read, commands, dsh templates, foreground modules. READMEs, the
   vendored `reference/` tree, JSON and YAML records are documentation and
   configuration, not instruction carriers, so the warning does not apply.

The phrase and secret rules skip `standards/`, `docs/`, `provenance/`,
`evals/`, `exemplars/`, `tooling/` and `agent-*` test fixtures: those are where
this library documents and tests the patterns, so quoting one is the point.

This is the static half. It cannot prove a runtime boundary exists; it catches
the asset that ships the payload or the directive.

Usage:
    python3 tooling/check_prompt_security.py [--root PATH] [--json] [--strict]

Exit 0 when clean, 1 on any FAIL. A WARN never fails unless `--strict`.
"""

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

SCAN_ROOTS = ["agents", "prompts", "skills", "fragments", "commands",
              "omp", "dsh", "standards"]
SUFFIXES = {".md", ".json", ".yaml", ".yml"}
# Directories whose text documents or tests the hostile patterns on purpose.
QUOTE_OK = ("standards/", "docs/", "provenance/", "evals/", "exemplars/",
            "tooling/")

TAG_BASE = 0xE0000
TAG_LAST = 0xE007F
INVISIBLE = frozenset(
    "\u200b\u200c\u200d\u2060\ufeff"      # ZWSP ZWNJ ZWJ WJ BOM
    "\u200e\u200f"                        # LRM RLM
    "\u202a\u202b\u202c\u202d\u202e"      # bidi embeddings / overrides
    "\u2066\u2067\u2068\u2069"            # bidi isolates
    "\u2028\u2029"                        # line / paragraph separator
)
OVERRIDE_PATTERNS = [re.compile(p, re.IGNORECASE) for p in (
    r"ignore (?:all )?(?:previous|prior) instructions",
    r"disregard (?:all )?(?:previous|prior) instructions",
    r"do anything now",
    r"developer mode",
    r"stay in character",
)]
FOLLOW_DIRECTIVE = re.compile(
    r"(?i)\bfollow (?:the )?(?:instructions|directives|commands)\s+"
    r"(?:in|from|inside|within)\s+(?:this|that|the)\s+"
    r"(?:file|page|url|link|document|website|site|text|message|content)\b")
# A directive preceded by a prohibition on the same line is documentation of the
# pattern ("never write: follow the instructions in this file"), not an
# instruction. The negation must appear before the match.
NEGATION = re.compile(r"(?i)\b(?:never|do not|don't|must not|avoid|refuse)\b")
# A prohibition only excuses a directive it governs. "Never write: follow ..." is
# documentation; "Do not panic: follow ..." is not, because the prohibition's verb
# is not about producing text. Both sit before a colon, so the verb decides.
# Only a documentation frame excuses a directive: the prohibition's verb must sit
# immediately before the colon ("never write:"). Ambiguous verbs (print, include,
# copy, paste) are excluded: "Do not print secrets: follow ..." is an instruction.
DOC_FRAME = re.compile(r"(?i)\b(?:never|do not|don't|must not|avoid|refuse)\b[^:]{0,40}"
                       r"\b(?:write|writes|say|says|name|names|quote|quotes|document"
                       r"|documents|describe|describes)\b\s*:$")
# A security carrier sometimes has to quote the payload verbatim. It declares that
# with this trailer, so the exemption is reviewed instead of silent (PS-13).
PAYLOAD_MARKER = "[ps-02-quoted-payload]"
SECRET_PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), "provider key"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "github token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "github pat"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "aws access key id"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"), "slack token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"\bBearer [A-Za-z0-9._\-]{24,}"), "bearer token"),
]
RETRIEVAL_TERMS = re.compile(
    r"(?i)\b(web search|web fetch|fetch(?:es|ed|ing)? (?:the )?(?:url|page|site)|"
    r"browser|tool output|tool result|mcp (?:resource|tool)|memory page|"
    r"retrieved (?:content|document|page)|subagent return)\b")
BOUNDARY_TERMS = re.compile(
    r"(?i)\b(untrusted|as data|not instructions|never instructions|"
    r"not an instruction|data boundary|quarantine|never follow|"
    r"treated as data|treat as data|is data|stay data|never an instruction"
    r"|data, never)\b")
CARRIER_PATTERNS = (
    "agents/*.md",
    "agents/**/*.md",
    "prompts/*.md",
    "prompts/**/*.md",
    "skills/**/SKILL.md",
    "skills/**/references/*.md",
    "commands/*.md",
    "dsh/**/*.template.md",
    "dsh/**/*.template.yml",
    "omp/prompts/**/*.md",
)


def is_quoted_context(relative):
    return relative.startswith(QUOTE_OK)


def is_instruction_carrier(root, path):
    """AD-01 in miniature: the files a runtime loads as instructions."""
    relative = path.relative_to(root).as_posix()
    lowered = relative.lower()
    if path.name.lower().startswith("readme"):
        return False
    if "/reference/" in "/" + lowered:
        # The vendored upstream reference tree keeps its upstream shape (SK-10).
        return False
    return any(fnmatch.fnmatch(relative, pattern) for pattern in CARRIER_PATTERNS)


def decode_shadow(text):
    """Tags block to ASCII, invisibles removed. Targets documented smuggling
    encodings only; never NFKC."""
    out = []
    for char in text:
        code = ord(char)
        if TAG_BASE <= code <= TAG_LAST:
            ascii_code = code - TAG_BASE
            if 0x20 <= ascii_code <= 0x7E:
                out.append(chr(ascii_code))
            continue
        if char in INVISIBLE:
            continue
        out.append(char)
    return "".join(out)


def invisible_hits(text):
    """(line, codepoint) for every invisible or Tags-block character."""
    hits = []
    for index, line in enumerate(text.splitlines(), start=1):
        for char in line:
            code = ord(char)
            if TAG_BASE <= code <= TAG_LAST or char in INVISIBLE:
                hits.append((index, code))
                break
    return hits


def smuggled_overrides(text):
    if not invisible_hits(text):
        return []
    decoded = decode_shadow(text)
    found = []
    for pattern in OVERRIDE_PATTERNS:
        match = pattern.search(decoded)
        if match and not pattern.search(text):
            found.append(match.group(0))
    return found


def scan_file(path, root, violations, warnings, carrier=True):
    relative = path.relative_to(root).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        violations.append(("PS-03", relative, 0, "unreadable as UTF-8: %s" % exc))
        return
    for line, code in invisible_hits(text):
        violations.append(("PS-03", relative, line,
                           "invisible character U+%04X" % code))
    for phrase in smuggled_overrides(text):
        violations.append(("PS-03", relative, 1,
                           "override phrase visible only after decoding: %r" % phrase))
    if is_quoted_context(relative):
        return
    for index, line in enumerate(text.splitlines(), start=1):
        match = FOLLOW_DIRECTIVE.search(line)
        excused = False
        if match:
            # The governing clause runs since the last sentence or clause break.
            clause = re.split(r"(?<=[.!?;])\s+", line[:match.start()])[-1]
            head, colon, _ = clause.partition(":")
            if colon:
                excused = bool(DOC_FRAME.search(head + ":"))
            else:
                excused = bool(NEGATION.search(clause))
            if PAYLOAD_MARKER in line:
                excused = True
        if match and not excused:
            violations.append(("PS-02", relative, index,
                               "instruction smuggled into data position: %r" % match.group(0)))
        for pattern, label in SECRET_PATTERNS:
            hit = pattern.search(line)
            if hit:
                violations.append(("PS-06", relative, index,
                                   "secret-shaped literal (%s): %r"
                                   % (label, hit.group(0)[:24])))
    if carrier and RETRIEVAL_TERMS.search(text) and not BOUNDARY_TERMS.search(text):
        warnings.append(("PS-02", relative, 0,
                         "names a retrieval surface without a data-boundary statement"))


def iter_files(root):
    for scan_root in SCAN_ROOTS:
        base = root / scan_root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix.lower() in SUFFIXES:
                yield path


def run(root):
    violations, warnings = [], []
    count = 0
    for path in iter_files(root):
        count += 1
        scan_file(path, root, violations, warnings, is_instruction_carrier(root, path))
    return count, violations, warnings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as failures")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print("prompt-security: not a directory: %s" % root)
        return 2
    count, violations, warnings = run(root)
    if args.json:
        print(json.dumps({
            "root": str(root),
            "files": count,
            "violations": [{"rule": r, "path": p, "line": l, "detail": d}
                           for r, p, l, d in violations],
            "warnings": [{"rule": r, "path": p, "line": l, "detail": d}
                         for r, p, l, d in warnings],
        }, indent=2))
    else:
        for rule, path, line, detail in violations:
            print("FAIL %s %s:%d %s" % (rule, path, line, detail))
        for rule, path, line, detail in warnings:
            print("WARN %s %s:%d %s" % (rule, path, line, detail))
        print("prompt-security: %d files, %d violation(s), %d warning(s)"
              % (count, len(violations), len(warnings)))
    failed = bool(violations) or (args.strict and bool(warnings))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
