#!/usr/bin/env python3
"""Render a project agent pack from library templates and project overlays.

The library owns the role skeleton, the doctrine fragment, and the conduct
fragment. The project pack owns the slot values and any project behavior that is
not a slot. This tool composes them into a vendor-neutral agent body:

    template (library) + slots + overlay (project) -> agents/<name>.md

The output carries no YAML frontmatter. A vendor adapter (for example the Kilo
`.kilo/agents` block) is generated separately from the same body.

Usage:
    python3 tooling/render_agents.py --pack PACK [--write|--check]
        [--library-root DIR] [--project-root DIR] [--only GLOB] [--json]

PACK is a YAML manifest:

    schema: agent-pack/1
    agents:
      - name: review-security
        template: agents/review/review-tracks/rev-track-security.md
        output: agents/review-security.md
        slots: {PROJECT_ID: containeromat, PROJECT_RULES: "AGENTS.md"}
        overlay: packs/containeromat/overlays/review-security.md

An overlay holds the same block tags as the template. A tag may carry
`mode="replace"` (default) or `mode="append"`:

    <hard_rules mode="append">
    - Project-only rule.
    </hard_rules>

`doctrine` and `conduct` are library-owned and may not appear in an overlay.

Exit 0 clean, 1 drift or violation, 2 unreadable/invalid input.
"""

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

import yaml

BLOCK_RE = re.compile(r"<([a-z_]+)(?:\s+([^>]*))?>\n(.*?)\n</\1>", re.DOTALL)
TAG_RE = re.compile(r"^<([a-z_]+)(?:\s+([^>]*))?>$")
SLOT_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
LIBRARY_BLOCKS = {"doctrine", "conduct"}
CONDUCT_FRAGMENTS = {
    "kilo": "agent-conduct.md",
    "dsh-ha": "agent-conduct.dsh-ha.md",
    "dsh-preset": "agent-conduct.dsh-preset.md",
}
ORDER = ["role", "hard_rules", "doctrine", "workflow", "scope", "tiering",
         "dispatch", "merge", "conduct", "output"]


def fail(message):
    raise ValueError(message)


def contained(path, root, label):
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        fail("%s escapes %s: %s" % (label, root, path))
    return path


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    lines = text.split("\n")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            meta = yaml.safe_load("\n".join(lines[1:index])) or {}
            if not isinstance(meta, dict):
                fail("template frontmatter is not a mapping")
            return meta, "\n".join(lines[index + 1:])
    fail("template frontmatter is not closed")


def mode_of(attrs):
    text = (attrs or "").strip()
    if not text:
        return "replace"
    match = re.fullmatch(r"mode\s*=\s*(?:\"([a-z]+)\"|'([a-z]+)'|([a-z]+))",
                         text)
    if not match:
        fail("unsupported overlay attributes: %r" % text)
    mode = next(group for group in match.groups() if group)
    if mode not in ("replace", "append"):
        fail("unsupported overlay mode: %r" % mode)
    return mode


def blocks_of(text):
    found = []
    for match in BLOCK_RE.finditer(text):
        name, attrs, body = match.group(1), match.group(2), match.group(3)
        found.append((name, mode_of(attrs), body, match.group(0)))
    return found


def substitute(text, slots):
    missing = sorted(set(SLOT_RE.findall(text)) - set(slots))
    if missing:
        fail("missing slot(s): " + ", ".join(missing))
    return SLOT_RE.sub(lambda match: str(slots[match.group(1)]), text)


def fragment_block(fragments, name, variant="kilo"):
    filename = CONDUCT_FRAGMENTS.get(variant) if name == "conduct" else "agent-doctrine.md"
    if filename is None:
        fail("unknown conduct variant: %s" % variant)
    path = fragments / filename
    if not path.is_file():
        fail("missing fragment: %s" % path)
    for block_name, _, body, _ in blocks_of(path.read_text(encoding="utf-8")):
        if block_name == name:
            return body
    fail("fragment %s has no <%s> block" % (path, name))


def apply_overlay(template_blocks, overlay_text, overlay_path, slots):
    overlay_text = substitute(overlay_text, slots)
    overlay = blocks_of(overlay_text)
    by_name = {}
    for name, mode, body, _ in overlay:
        if name in by_name:
            fail("%s: duplicate overlay block <%s>" % (overlay_path, name))
        by_name[name] = (mode, body)
    for name, _, _, _ in overlay:
        if name in LIBRARY_BLOCKS:
            fail("%s: overlay may not set <%s>" % (overlay_path, name))
        if name not in {block[0] for block in template_blocks}:
            fail("%s: overlay block <%s> is not in the template" % (overlay_path, name))

    rendered = []
    for name, body in template_blocks:
        if name in by_name:
            mode, overlay_body = by_name[name]
            if mode == "replace":
                body = overlay_body
            elif mode == "append":
                body = body.rstrip() + "\n" + overlay_body.strip("\n")
            else:
                fail("%s: unsupported mode %r for <%s>" % (overlay_path, mode, name))
        rendered.append((name, body))
    return rendered


def render_agent(entry, manifest_path, library_root, project_root, fragments_root):
    name = entry.get("name")
    template_rel = entry.get("template")
    output_rel = entry.get("output")
    if not name or not template_rel or not output_rel:
        fail("%s: agent entries need name, template, and output" % manifest_path)
    template_path = contained(library_root / template_rel, library_root, "template")
    if not template_path.is_file():
        fail("%s: template not found: %s" % (manifest_path, template_rel))
    overlay_path = (contained(project_root / entry["overlay"], project_root, "overlay")
                    if entry.get("overlay") else None)
    if overlay_path and not overlay_path.is_file():
        fail("%s: overlay not found: %s" % (manifest_path, entry["overlay"]))

    meta, body = parse_frontmatter(template_path.read_text(encoding="utf-8"))
    required = meta.get("required_slots", [])
    slots = dict(entry.get("slots") or {})
    missing = sorted(set(required) - set(slots))
    if missing:
        fail("%s: %s missing required slot(s): %s"
             % (manifest_path, name, ", ".join(missing)))
    body = substitute(body, slots)
    template_blocks = [(block_name, block_body)
                       for block_name, _, block_body, _ in blocks_of(body)]
    if not template_blocks:
        fail("%s: template has no blocks: %s" % (manifest_path, template_rel))

    if overlay_path:
        template_blocks = apply_overlay(
            template_blocks, overlay_path.read_text(encoding="utf-8"),
            overlay_path, slots)

    variant = meta.get("conduct_variant", "kilo")
    fragments = fragments_root
    final = []
    for block_name, block_body in template_blocks:
        if block_name in LIBRARY_BLOCKS:
            block_body = fragment_block(fragments, block_name, variant)
        final.append((block_name, block_body.strip("\n")))

    order = {name: index for index, name in enumerate(ORDER)}
    final.sort(key=lambda item: order.get(item[0], len(ORDER)))
    text = "\n\n".join("<%s>\n%s\n</%s>" % (block, body, block)
                       for block, body in final) + "\n"
    if SLOT_RE.search(text):
        fail("%s: unsubstituted slot in %s" % (manifest_path, output_rel))
    output_path = contained(project_root / output_rel, project_root, "output")
    return output_path, text


def load_manifest(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if data.get("schema") != "agent-pack/1":
        fail("%s: schema must be agent-pack/1" % path)
    agents = data.get("agents")
    if not isinstance(agents, list) or not agents:
        fail("%s: agents must be a non-empty list" % path)
    names = [entry.get("name") for entry in agents if isinstance(entry, dict)]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        fail("%s: duplicate agent names: %s" % (path, ", ".join(duplicates)))
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True)
    parser.add_argument("--library-root", default=".")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--only", default=None, help="glob filter on agent name")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.write == args.check:
        print("choose exactly one of --write or --check", file=sys.stderr)
        return 2

    pack = Path(args.pack).resolve()
    library_root = Path(args.library_root).resolve()
    project_root = Path(args.project_root).resolve()
    try:
        data = load_manifest(pack)
        fragments_rel = data.get("fragments")
        fragments_root = (contained(project_root / fragments_rel, project_root,
                                    "fragments")
                          if fragments_rel else library_root / "fragments")
        rendered = []
        for entry in data["agents"]:
            name = entry.get("name", "")
            if args.only and not fnmatch.fnmatch(name, args.only):
                continue
            path, text = render_agent(entry, pack, library_root, project_root,
                                      fragments_root)
            rendered.append((name, path, text))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    if args.only and not rendered:
        print("ERROR: --only matched no agent", file=sys.stderr)
        return 2

    drift = []
    for name, path, text in rendered:
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        elif not path.is_file() or path.read_text(encoding="utf-8") != text:
            drift.append(str(path.relative_to(project_root)))
    if args.json:
        print(json.dumps({"agents": len(rendered), "drift": drift}, indent=2))
    elif args.check:
        if drift:
            print("DRIFT: " + ", ".join(drift), file=sys.stderr)
            return 1
        print("agents: %d rendered, 0 drift" % len(rendered))
    else:
        print("agents: wrote %d" % len(rendered))
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
