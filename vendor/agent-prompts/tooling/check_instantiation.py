#!/usr/bin/env python3
"""Structural audit of a project's live agents against this library's templates.

This is a STRUCTURAL audit. Content differences between a live agent and its
template are intentional: a live agent carries project tuning (project
vocabulary, rule ids, handoff names, verification commands). This tool therefore
does NOT compare block content against the template. It checks:

1. Block sequence -- the live agent's recognized top-level blocks
   (<role>, <hard_rules>, <doctrine>, <workflow>, <conduct>, <output>) appear in
   the same order as the template's. Unknown extra blocks (for example
   containeromat's <scope> and <merge>) are ignored. A live agent may carry its
   role as a plain first paragraph instead of an explicit <role> tag wrapper;
   that is accepted as an implicit role block.
2. Fragment identity -- the <doctrine> block is byte-identical to
   fragments/agent-doctrine.md and the <conduct> block to the fragment for the
   template's conduct variant (containeromat: fragments/agent-conduct.md).
3. Output last -- no content after </output>.
4. Workflow prose -- no leading "- " or "N. " list markers inside <workflow>.
5. hard_rules shape -- top-level lines are "- " bullets; continuation lines are
   indented.

The MAPPING table is containeromat's runtime adoption record (see
packs/containeromat.md). Note one name difference: the template
review-track-correctness instantiates to the live agent review-business-logic,
because containeromat names its correctness/ordering/error-path track
business-logic.

Library-owned blocks are copied byte-exact at instantiation
(docs/INSTANTIATE.md), so a fragment divergence is a bug, not a customization.
A block-sequence divergence is reported and left for a human to classify.

Usage:
  python3 tooling/check_instantiation.py \
      --project-root /path/to/containeromat \
      --library-root /path/to/agent-prompts [--template <id>]

Prints one "OK <agent> -> <template>" or "FAIL <agent>: <violation>" line per
result and exits 0 when every selected mapping passes, 1 otherwise.
"""

import argparse
import re
import sys
from pathlib import Path

BLOCK_ORDER = ["role", "hard_rules", "doctrine", "workflow", "conduct", "output"]
KNOWN_BLOCK_TAGS = set(BLOCK_ORDER) | {"scope"}

LIST_MARKER_RE = re.compile(r"^\s*(?:- |\d+\. )")
TAG_LINE_RE = re.compile(r"<([A-Za-z_][A-Za-z0-9_]*)>")
CONDUCT_VARIANT_RE = re.compile(r"^conduct_variant:\s*(\S+)\s*$", re.MULTILINE)

CONDUCT_FRAGMENTS = {
    "kilo": "agent-conduct.md",
    "dsh-ha": "agent-conduct.dsh-ha.md",
    "dsh-preset": "agent-conduct.dsh-preset.md",
    "omp": "agent-conduct.omp.md",
}
CONDUCT_FRAGMENT_DEFAULT = "agent-conduct.md"

# containeromat runtime adoption record: (template id, template path under the
# library root, live agent filename under <project-root>/.kilo/agents/).
MAPPING = [
    ("orchestration-orchestrator", "agents/orchestration/orch-orchestrator.md", "orchestrator.md"),
    ("operations-ci-implementer", "agents/operations/ops-ci-implementer.md", "ci-step.md"),
    ("operations-executor", "agents/operations/ops-executor.md", "compose-step.md"),
    ("operations-format-normalizer", "agents/operations/ops-format-normalizer.md", "ascii-step.md"),
    ("review-reviewer", "agents/review/rev-reviewer.md", "reviewer.md"),
    ("review-review-lead", "agents/review/rev-review-lead.md", "review-lead.md"),
    ("review-code-skeptic", "agents/review/rev-code-skeptic.md", "code-skeptic.md"),
    ("documentation-doc-writer", "agents/documentation/doc-doc-writer.md", "docs-specialist.md"),
    ("review-track-security", "agents/review/review-tracks/rev-track-security.md", "review-security.md"),
    ("review-track-correctness", "agents/review/review-tracks/rev-track-correctness.md", "review-business-logic.md"),
    ("review-track-deploy-safety", "agents/review/review-tracks/rev-track-deploy-safety.md", "review-deploy-safety.md"),
    ("review-track-duplication", "agents/review/review-tracks/rev-track-duplication.md", "review-duplication.md"),
    ("review-track-dead-code", "agents/review/review-tracks/rev-track-dead-code.md", "review-dead-code.md"),
    ("review-track-quality", "agents/review/review-tracks/rev-track-quality.md", "review-quality.md"),
    ("review-track-structure", "agents/review/review-tracks/rev-track-structure.md", "review-structure.md"),
    ("review-track-simplicity", "agents/review/review-tracks/rev-track-simplicity.md", "review-simplicity.md"),
]


def default_library_root():
    return Path(__file__).resolve().parent.parent


def body_of(text):
    """Return the text after the closing frontmatter fence (or the full text)."""
    if not text.startswith("---"):
        return text
    lines = text.split("\n")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[index + 1:])
    return text


def extract_known_blocks(text):
    """Return (ordered known block names, name -> block text with tags).

    Only the six canonical block names count. Lines that are exactly one tag are
    matched, mirroring tooling/validate_templates.py. Unknown tags are ignored.
    """
    lines = text.split("\n")
    order = []
    blocks = {}
    index = 0
    total = len(lines)
    while index < total:
        stripped = lines[index].strip()
        match = re.fullmatch(r"<([A-Za-z_][A-Za-z0-9_]*)>", stripped)
        if match and match.group(1) in KNOWN_BLOCK_TAGS:
            name = match.group(1)
            close = None
            for cursor in range(index + 1, total):
                if lines[cursor].strip() == "</%s>" % name:
                    close = cursor
                    break
            if close is None:
                blocks[name] = "\n".join(lines[index:])
                order.append(name)
                break
            blocks[name] = "\n".join(lines[index:close + 1])
            order.append(name)
            index = close
        index += 1
    return order, blocks


def implicit_role(body):
    """Return the leading plain paragraph before the first tag line, or None."""
    lines = body.split("\n")
    for index, line in enumerate(lines):
        if re.fullmatch(r"<[A-Za-z_][A-Za-z0-9_]*>", line.strip()):
            head = "\n".join(lines[:index]).strip()
            return head or None
    head = body.strip()
    return head or None


def fragment_block(library_root, fragment_name, block_name):
    path = library_root / "fragments" / fragment_name
    if not path.is_file():
        return None, path
    _, blocks = extract_known_blocks(path.read_text(encoding="utf-8", errors="replace"))
    return blocks.get(block_name), path


def conduct_variant(template_text):
    match = CONDUCT_VARIANT_RE.search(template_text)
    if not match:
        return "kilo"
    return match.group(1)


def block_lines(block):
    """Content lines of a tagged block (tags dropped)."""
    lines = block.split("\n")
    if lines and lines[0].strip().startswith("<"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("</"):
        lines = lines[:-1]
    return lines


def audit(mapping, project_root, library_root):
    template_id, template_rel, agent_file = mapping
    template_path = library_root / template_rel
    if not template_path.is_file() and template_rel.startswith("agents/"):
        legacy = library_root / ("roles/" + template_rel[len("agents/"):])
        if legacy.is_file():
            print("WARN legacy root: %s missing; using %s" % (template_path, legacy))
            template_path = legacy
    agent_path = project_root / ".kilo" / "agents" / agent_file
    violations = []

    if not agent_path.is_file():
        return ["live agent not found: %s" % agent_path]
    if not template_path.is_file():
        return ["template not found: %s" % template_path]

    template_text = template_path.read_text(encoding="utf-8", errors="replace")
    agent_text = agent_path.read_text(encoding="utf-8", errors="replace")

    template_order, _ = extract_known_blocks(body_of(template_text))
    agent_order, agent_blocks = extract_known_blocks(body_of(agent_text))

    if "role" not in agent_blocks:
        head = implicit_role(body_of(agent_text))
        if head:
            agent_order = ["role"] + agent_order
            agent_blocks["role"] = "<role>\n%s\n</role>" % head

    if agent_order != template_order:
        violations.append(
            "block sequence differs from template: live=[%s], template=[%s]"
            % (", ".join(agent_order) or "none", ", ".join(template_order) or "none")
        )

    doctrine, doctrine_path = fragment_block(library_root, "agent-doctrine.md", "doctrine")
    live_doctrine = agent_blocks.get("doctrine")
    if live_doctrine is None:
        violations.append("missing <doctrine> block")
    elif doctrine is None:
        violations.append("doctrine fragment has no <doctrine> block: %s" % doctrine_path)
    elif live_doctrine != doctrine:
        violations.append("<doctrine> is not byte-identical to %s" % doctrine_path.name)

    fragment_name = CONDUCT_FRAGMENTS.get(
        conduct_variant(template_text), CONDUCT_FRAGMENT_DEFAULT)
    conduct, conduct_path = fragment_block(library_root, fragment_name, "conduct")
    live_conduct = agent_blocks.get("conduct")
    if live_conduct is None:
        violations.append("missing <conduct> block")
    elif conduct is None:
        violations.append("conduct fragment has no <conduct> block: %s" % conduct_path)
    elif live_conduct != conduct:
        violations.append("<conduct> is not byte-identical to %s" % conduct_path.name)

    output_close = agent_text.rfind("</output>")
    if output_close == -1:
        violations.append("missing </output> close tag")
    else:
        tail = agent_text[output_close + len("</output>"):]
        if tail.strip():
            violations.append("content found after </output>; output must be the last block")

    live_workflow = agent_blocks.get("workflow")
    if live_workflow is not None:
        for line in block_lines(live_workflow):
            if LIST_MARKER_RE.match(line):
                violations.append(
                    "workflow block contains a list marker: %r" % line.strip())
                break

    live_hard_rules = agent_blocks.get("hard_rules")
    if live_hard_rules is None:
        violations.append("missing <hard_rules> block")
    else:
        bullets = 0
        for line in block_lines(live_hard_rules):
            if not line.strip() or line[0].isspace():
                continue
            if line.startswith("- "):
                bullets += 1
            else:
                violations.append("hard_rules line is not a bullet: %r" % line.strip())
        if bullets == 0:
            violations.append("hard_rules carries no bullet markers")

    return violations


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Structural audit of live agents against library templates.")
    parser.add_argument("--project-root", required=True,
                        help="project checkout that holds .kilo/agents/")
    parser.add_argument("--library-root", default=str(default_library_root()),
                        help="agent-prompts checkout (defaults to this repo)")
    parser.add_argument("--template", default=None,
                        help="audit only this template id")
    args = parser.parse_args(argv)

    project_root = Path(args.project_root)
    library_root = Path(args.library_root)

    if args.template is None:
        selected = MAPPING
    else:
        selected = [mapping for mapping in MAPPING if mapping[0] == args.template]
        if not selected:
            print("FAIL --template: unknown template id %r" % args.template)
            return 1

    failed = False
    for mapping in selected:
        agent_name = mapping[2][:-3] if mapping[2].endswith(".md") else mapping[2]
        violations = audit(mapping, project_root, library_root)
        if not violations:
            print("OK %s -> %s" % (agent_name, mapping[0]))
            continue
        failed = True
        for violation in violations:
            print("FAIL %s: %s" % (agent_name, violation))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
