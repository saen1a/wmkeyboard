"""Structural checks for the dsh preset personas.

The presets are YAML templates with a folded persona scalar. They are not
covered by ``validate_templates.py``, which only walks agents/ and prompts/tasks/ (legacy roles/ and tasks/ fallback), so
this test keeps the doctrine carrier parseable and byte-equivalent after
whitespace normalization.
"""

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
FRAGMENT = ROOT / "fragments" / "agent-doctrine.md"
PRESETS = sorted((ROOT / "dsh" / "presets").glob("*.template.yml"))


def normalize(text):
    return " ".join(text.split())


def doctrine_block(text):
    match = re.search(r"(?ms)^\s*<doctrine>.*?</doctrine>", text)
    assert match, "missing <doctrine> block"
    return match.group(0)


@pytest.mark.parametrize("path", PRESETS, ids=lambda p: p.name)
def test_preset_is_parseable_yaml(path):
    yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", PRESETS, ids=lambda p: p.name)
def test_preset_carries_canonical_doctrine(path):
    expected = normalize(doctrine_block(FRAGMENT.read_text(encoding="utf-8")))
    actual = normalize(doctrine_block(path.read_text(encoding="utf-8")))
    assert actual == expected
