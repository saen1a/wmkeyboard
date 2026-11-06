#!/usr/bin/env python3
"""Generate packs/wmkeyboard/agents.yaml from the vendored library canon.

The manifest is the adoption record: which library role becomes which live Kilo
agent, the slot values only this project can know, and the permission profile.
Run this after the library pin or a role list changes:

    python scripts/gen-agent-pack.py --write
    python scripts/gen-agent-pack.py --check

Exit 0 clean, 1 drift, 2 invalid input.
"""

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "vendor" / "agent-prompts"
OUTPUT = ROOT / "packs" / "wmkeyboard" / "agents.yaml"

VERIFICATION = "the verification commands in AGENTS.md"

SLOTS = {
    "PROJECT_ID": "wmkeyboard",
    "PROJECT_RULES": "AGENTS.md",
    "SAFETY_RULE": "Safety rule",
    "MUTATION_POLICY": "Mutation policy",
    "VERIFICATION_COMMANDS": VERIFICATION,
    "ROLLBACK_COMMAND": "git restore --source=HEAD -- <changed paths>",
    "HANDOFF_TARGETS": "the requesting session",
    "PROJECT_CI_GATES": (
        ".github/workflows/ci.yml and .github/workflows/agent-pack.yml "
        "(cargo test, unitTests, assemble, dex-limits, licenses, docs, "
        "agent pack)"
    ),
    "DESIGN_STANDARD": (
        "Material 3 + Jetpack Compose; review against .github/media/shots and "
        "the feature/ime surface"
    ),
    "ACCESSIBILITY_STANDARD": (
        "Android accessibility guidance and Compose semantics; touch targets "
        "in feature/ime"
    ),
    "PROJECT_DOCS_LAYOUT_RULE": "docs/CONTENT_GUIDE.md",
    "PROJECT_DOC_SCOPE": (
        "docs/**, README.md, SETTINGS_REDESIGN.md, release-notes/**"
    ),
    "API_CONVENTIONS": (
        "Kotlin public APIs under core/** stay source-compatible; a breaking "
        "change needs a migration note in release-notes/"
    ),
    "PROJECT_CI_ALLOWLIST": ".github/workflows/** and scripts/**",
    "PROJECT_EXCEPTION_REGISTRY": "none",
    "PROJECT_NORMALIZER_TOOLING": (
        "detekt and Android Lint through ./gradlew staticAnalysis"
    ),
    "PROJECT_REVIEW_CONTRACT": (
        "vendor/agent-prompts/standards/code-review-contract.md"
    ),
    "PROJECT_COMMENT_STANDARD": (
        "English, explain why not what; no plan-internal IDs; follow "
        "config/detekt/detekt.yml"
    ),
}

PROJECT_DESCRIPTIONS = {
    "wmk-native-engineer": (
        "Implement one approved change in the Rust text engine and its JNI "
        "bridge, keeping the engine Android-free and both builds green."
    ),
    "wmk-kotlin-engineer": (
        "Implement one approved change in the Kotlin and Compose surfaces, "
        "preserving the module layering and both channel source sets."
    ),
    "wmk-glide-researcher": (
        "Investigate one glide, context-model, or engine-measurement question "
        "with citations and a reproduction command."
    ),
    "wmk-release-engineer": (
        "Prepare one approved release note and store metadata, with the "
        "matching gate evidence."
    ),
}

# live name, template, mode, permission profile, handoff override, overlay
ROLES = [
    ("orchestrator", "agents/orchestration/orch-orchestrator.md",
     "primary", "orchestrator",
     "code-explorer, fixer, reviewer, review-lead, wmk-native-engineer, "
     "wmk-kotlin-engineer, docs-writer", None),
    ("councillor", "agents/orchestration/orch-councillor.md",
     "subagent", "read", None, None),
    ("council-synthesizer", "agents/orchestration/orch-council-synthesizer.md",
     "subagent", "synthesizer", None, None),

    ("code-explorer", "agents/engineering/eng-explorer.md",
     "subagent", "read", None, None),
    ("oracle", "agents/engineering/eng-oracle.md",
     "subagent", "read", None, None),
    ("fixer", "agents/engineering/eng-fixer.md",
     "subagent", "write-general", None, None),
    ("backend-developer", "agents/engineering/eng-backend-developer.md",
     "subagent", "write-general", None, None),
    ("frontend-developer", "agents/engineering/eng-frontend-developer.md",
     "subagent", "write-general", None, None),
    ("api-developer", "agents/engineering/eng-api-developer.md",
     "subagent", "write-general", None, None),
    ("database-developer", "agents/engineering/eng-database-developer.md",
     "subagent", "write-general", None, None),
    ("test-author", "agents/engineering/eng-test-author.md",
     "subagent", "write-tests", None, None),

    ("ui-reviewer", "agents/design/design-ui-reviewer.md",
     "subagent", "read", None, None),
    ("docs-writer", "agents/documentation/doc-doc-writer.md",
     "subagent", "write-docs", None, None),

    ("ci-implementer", "agents/operations/ops-ci-implementer.md",
     "subagent", "write-ci", None,
     "packs/wmkeyboard/overlays/ci-implementer.md"),
    ("ops-executor", "agents/operations/ops-executor.md",
     "subagent", "write-general", None,
     "packs/wmkeyboard/overlays/ops-executor.md"),
    ("format-normalizer", "agents/operations/ops-format-normalizer.md",
     "subagent", "write-batch", None, None),

    ("librarian", "agents/research/res-librarian.md",
     "subagent", "read", None, None),
    ("researcher", "agents/research/res-researcher.md",
     "subagent", "read", None, None),
    ("research-merger", "agents/research/res-research-merger.md",
     "subagent", "read", None, None),

    ("reviewer", "agents/review/rev-reviewer.md",
     "subagent", "read-bash", None, None),
    ("review-lead", "agents/review/rev-review-lead.md",
     "primary", "read-task",
     "the operator or the requesting session that owns the authorized fix",
     None),
    ("code-skeptic", "agents/review/rev-code-skeptic.md",
     "subagent", "read-bash", None, None),
    ("consistency-reviewer", "agents/review/rev-consistency-reviewer.md",
     "subagent", "read", None, None),
    ("security-reviewer", "agents/review/rev-security-reviewer.md",
     "subagent", "read", None, None),
    ("review-business-logic",
     "agents/review/review-tracks/rev-track-correctness.md",
     "subagent", "read", None, None),
    ("review-dead-code", "agents/review/review-tracks/rev-track-dead-code.md",
     "subagent", "read", None, None),
    ("review-deploy-safety",
     "agents/review/review-tracks/rev-track-deploy-safety.md",
     "subagent", "read", None, None),
    ("review-duplication",
     "agents/review/review-tracks/rev-track-duplication.md",
     "subagent", "read", None, None),
    ("review-quality", "agents/review/review-tracks/rev-track-quality.md",
     "subagent", "read", None, None),
    ("review-security", "agents/review/review-tracks/rev-track-security.md",
     "subagent", "read", None, None),
    ("review-simplicity", "agents/review/review-tracks/rev-track-simplicity.md",
     "subagent", "read", None, None),
    ("review-structure", "agents/review/review-tracks/rev-track-structure.md",
     "subagent", "read", None, None),

    ("wmk-native-engineer", "agents/engineering/eng-fixer.md",
     "subagent", "write-native", None,
     "packs/wmkeyboard/overlays/wmk-native-engineer.md"),
    ("wmk-kotlin-engineer", "agents/engineering/eng-fixer.md",
     "subagent", "write-kotlin", None,
     "packs/wmkeyboard/overlays/wmk-kotlin-engineer.md"),
    ("wmk-glide-researcher", "agents/research/res-researcher.md",
     "subagent", "read-bash", None,
     "packs/wmkeyboard/overlays/wmk-glide-researcher.md"),
    ("wmk-release-engineer", "agents/operations/ops-ci-implementer.md",
     "subagent", "write-release", None,
     "packs/wmkeyboard/overlays/wmk-release-engineer.md"),
]


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("%s has no frontmatter" % path)
    lines = text.split("\n")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return yaml.safe_load("\n".join(lines[1:index])) or {}
    raise ValueError("%s has unclosed frontmatter" % path)


def vendored():
    text = (LIBRARY / "VENDORED.md").read_text(encoding="utf-8")
    commit = re.search(r"Pinned commit: `([0-9a-f]{40})`", text)
    version = re.search(r"Library version: ([0-9]+\.[0-9]+\.[0-9]+)", text)
    if not commit or not version:
        raise ValueError("VENDORED.md: missing pinned commit or version")
    return commit.group(1), version.group(1)


def build():
    commit, version = vendored()
    entries = []
    for (name, template, mode, permission, handoff, overlay) in ROLES:
        meta = frontmatter(LIBRARY / template)
        required = meta.get("required_slots") or []
        slots = {}
        for slot in required:
            if slot == "HANDOFF_TARGETS" and handoff:
                slots[slot] = handoff
            elif slot in SLOTS:
                slots[slot] = SLOTS[slot]
            else:
                raise ValueError("%s needs unmapped slot %s" % (name, slot))
        entry = {
            "name": name,
            "template": template,
            "output": "packs/wmkeyboard/rendered/%s.md" % name,
            "mode": mode,
            "permission": permission,
            "slots": slots,
        }
        if overlay:
            entry["overlay"] = overlay
        if name in PROJECT_DESCRIPTIONS:
            entry["description"] = PROJECT_DESCRIPTIONS[name]
        entries.append(entry)
    document = {
        "schema": "agent-pack/1",
        "project": "wmkeyboard",
        "library_commit": commit,
        "library_version": version,
        "agents": entries,
    }
    return yaml.safe_dump(document, sort_keys=False, width=4096,
                          default_flow_style=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.write == args.check:
        print("choose exactly one of --write or --check", file=sys.stderr)
        return 2
    try:
        text = build()
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(text, encoding="utf-8")
        print("wrote %s (%d agents)"
              % (OUTPUT.relative_to(ROOT), len(ROLES)))
        return 0
    if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != text:
        print("DRIFT: %s" % OUTPUT.relative_to(ROOT), file=sys.stderr)
        return 1
    print("pack: %d agents, 0 drift" % len(ROLES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
