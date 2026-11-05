"""Tests for the agent-pack renderer (template + slots + overlay)."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tooling" / "render_agents.py"

TEMPLATE = """---
id: demo-role
version: 1.0.0
required_slots: [PROJECT_ID, PROJECT_RULES]
optional_slots: []
conduct_variant: kilo
---

<role>
Work on {{PROJECT_ID}}.
</role>

<hard_rules>
- Read {{PROJECT_RULES}}.
- Template rule.
</hard_rules>

<doctrine>
- stale doctrine
</doctrine>

<workflow>
Plan -- template. Implement -- template. Review -- template. Fix -- template.
</workflow>

<conduct>
- stale conduct
</conduct>

<output>
DEMO: {status}
</output>
"""

DOCTRINE = """<doctrine>
- Binding doctrine from the library.
</doctrine>
"""

CONDUCT = """<conduct>
- Binding conduct from the library.
</conduct>
"""

OVERLAY = """<hard_rules mode="append">
- Project rule.
</hard_rules>

<workflow mode="replace">
Plan -- project. Implement -- project. Review -- project. Fix -- project.
</workflow>
"""


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture(tmp_path):
    library = tmp_path / "library"
    project = tmp_path / "project"
    _write(library / "agents" / "demo.md", TEMPLATE)
    _write(library / "fragments" / "agent-doctrine.md", DOCTRINE)
    _write(library / "fragments" / "agent-conduct.md", CONDUCT)
    _write(project / "packs" / "overlays" / "demo.md", OVERLAY)
    _write(project / "packs" / "pack.yaml", """schema: agent-pack/1
agents:
  - name: demo
    template: agents/demo.md
    output: agents/demo.md
    slots:
      PROJECT_ID: demo-project
      PROJECT_RULES: AGENTS.md
    overlay: packs/overlays/demo.md
""")
    return library, project


def _run(pack, library, project, *extra):
    return subprocess.run([
        sys.executable, str(TOOL), "--pack", str(pack),
        "--library-root", str(library), "--project-root", str(project),
        *extra,
    ], cwd=str(ROOT), capture_output=True, text=True)


def test_write_and_check(tmp_path):
    library, project = _fixture(tmp_path)
    pack = project / "packs" / "pack.yaml"
    result = _run(pack, library, project, "--write")
    assert result.returncode == 0, result.stderr
    text = (project / "agents" / "demo.md").read_text(encoding="utf-8")
    assert "Work on demo-project." in text
    assert "Read AGENTS.md." in text
    assert "Template rule." in text
    assert "Project rule." in text
    assert "Binding doctrine from the library." in text
    assert "stale doctrine" not in text
    assert "Binding conduct from the library." in text
    assert "Plan -- project." in text
    assert "Plan -- template." not in text
    assert "{{" not in text
    result = _run(pack, library, project, "--check")
    assert result.returncode == 0, result.stdout


def test_check_detects_drift(tmp_path):
    library, project = _fixture(tmp_path)
    pack = project / "packs" / "pack.yaml"
    assert _run(pack, library, project, "--write").returncode == 0
    path = project / "agents" / "demo.md"
    path.write_text(path.read_text(encoding="utf-8") + "extra\n", encoding="utf-8")
    result = _run(pack, library, project, "--check")
    assert result.returncode == 1
    assert "DRIFT" in result.stderr


def test_missing_required_slot_is_an_input_error(tmp_path):
    library, project = _fixture(tmp_path)
    pack = project / "packs" / "pack.yaml"
    pack.write_text(pack.read_text(encoding="utf-8").replace(
        "      PROJECT_RULES: AGENTS.md\n", ""), encoding="utf-8")
    result = _run(pack, library, project, "--check")
    assert result.returncode == 2
    assert "missing required slot" in result.stderr


def test_overlay_may_not_set_doctrine(tmp_path):
    library, project = _fixture(tmp_path)
    _write(project / "packs" / "overlays" / "demo.md",
           "<doctrine>\n- project doctrine\n</doctrine>\n")
    result = _run(project / "packs" / "pack.yaml", library, project, "--check")
    assert result.returncode == 2
    assert "may not set <doctrine>" in result.stderr


def test_overlay_unknown_block_is_an_input_error(tmp_path):
    library, project = _fixture(tmp_path)
    _write(project / "packs" / "overlays" / "demo.md",
           "<unknown>\ntext\n</unknown>\n")
    result = _run(project / "packs" / "pack.yaml", library, project, "--check")
    assert result.returncode == 2
    assert "not in the template" in result.stderr


def test_only_filters_agents(tmp_path):
    library, project = _fixture(tmp_path)
    pack = project / "packs" / "pack.yaml"
    pack.write_text(pack.read_text(encoding="utf-8") + """  - name: other
    template: agents/demo.md
    output: agents/other.md
    slots: {PROJECT_ID: x, PROJECT_RULES: y}
""", encoding="utf-8")
    result = _run(pack, library, project, "--check", "--only", "other")
    assert result.returncode == 1
    assert "agents/other.md" in result.stderr
    assert "agents/demo.md" not in result.stderr


def test_json_output(tmp_path):
    library, project = _fixture(tmp_path)
    result = _run(project / "packs" / "pack.yaml", library, project, "--check", "--json")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["agents"] == 1
    assert payload["drift"] == ["agents/demo.md"]


def test_project_fragments_override_library_fragments(tmp_path):
    library, project = _fixture(tmp_path)
    pack = project / "packs" / "pack.yaml"
    pack.write_text(pack.read_text(encoding="utf-8").replace(
        "schema: agent-pack/1\n",
        "schema: agent-pack/1\nfragments: fragments\n"), encoding="utf-8")
    _write(project / "fragments" / "agent-doctrine.md",
           "<doctrine>\n- Project-vendored doctrine.\n</doctrine>\n")
    _write(project / "fragments" / "agent-conduct.md",
           "<conduct>\n- Project-vendored conduct.\n</conduct>\n")
    result = _run(pack, library, project, "--write")
    assert result.returncode == 0, result.stderr
    text = (project / "agents" / "demo.md").read_text(encoding="utf-8")
    assert "Project-vendored doctrine." in text
    assert "Binding doctrine from the library." not in text
    assert "Project-vendored conduct." in text


def test_overlay_slot_is_an_input_error(tmp_path):
    library, project = _fixture(tmp_path)
    _write(project / "packs" / "overlays" / "demo.md",
           '<hard_rules mode="append">\n- {{MISSING}}\n</hard_rules>\n')
    result = _run(project / "packs" / "pack.yaml", library, project, "--check")
    assert result.returncode == 2
    assert "missing slot(s): MISSING" in result.stderr


def test_unknown_mode_is_an_input_error(tmp_path):
    library, project = _fixture(tmp_path)
    _write(project / "packs" / "overlays" / "demo.md",
           '<hard_rules mode="bogus">\n- x\n</hard_rules>\n')
    result = _run(project / "packs" / "pack.yaml", library, project, "--check")
    assert result.returncode == 2
    assert "unsupported overlay mode" in result.stderr


def test_single_quoted_append_mode_is_accepted(tmp_path):
    library, project = _fixture(tmp_path)
    _write(project / "packs" / "overlays" / "demo.md",
           "<hard_rules mode='append'>\n- Project rule.\n</hard_rules>\n")
    result = _run(project / "packs" / "pack.yaml", library, project, "--write")
    assert result.returncode == 0, result.stderr
    text = (project / "agents" / "demo.md").read_text(encoding="utf-8")
    assert "Template rule." in text
    assert "Project rule." in text


def test_missing_fragment_is_an_input_error(tmp_path):
    library, project = _fixture(tmp_path)
    (library / "fragments" / "agent-conduct.md").unlink()
    result = _run(project / "packs" / "pack.yaml", library, project, "--check")
    assert result.returncode == 2
    assert "missing fragment" in result.stderr


def test_output_may_not_escape_the_project(tmp_path):
    library, project = _fixture(tmp_path)
    pack = project / "packs" / "pack.yaml"
    pack.write_text(pack.read_text(encoding="utf-8").replace(
        "    output: agents/demo.md\n", "    output: ../../escape.md\n"),
        encoding="utf-8")
    result = _run(pack, library, project, "--write")
    assert result.returncode == 2
    assert "output escapes" in result.stderr


def test_only_with_no_match_is_an_input_error(tmp_path):
    library, project = _fixture(tmp_path)
    result = _run(project / "packs" / "pack.yaml", library, project,
                  "--check", "--only", "nope-*")
    assert result.returncode == 2
    assert "--only matched no agent" in result.stderr


def test_overlay_may_not_set_conduct(tmp_path):
    library, project = _fixture(tmp_path)
    _write(project / "packs" / "overlays" / "demo.md",
           "<conduct>\n- project conduct\n</conduct>\n")
    result = _run(project / "packs" / "pack.yaml", library, project, "--check")
    assert result.returncode == 2
    assert "may not set <conduct>" in result.stderr


def test_overlay_slots_are_substituted(tmp_path):
    library, project = _fixture(tmp_path)
    _write(project / "packs" / "overlays" / "demo.md",
           '<hard_rules mode="append">\n- Project {{PROJECT_ID}} rule.\n</hard_rules>\n')
    result = _run(project / "packs" / "pack.yaml", library, project, "--write")
    assert result.returncode == 0, result.stderr
    text = (project / "agents" / "demo.md").read_text(encoding="utf-8")
    assert "Project demo-project rule." in text


def test_duplicate_overlay_block_is_an_input_error(tmp_path):
    library, project = _fixture(tmp_path)
    _write(project / "packs" / "overlays" / "demo.md",
           '<hard_rules mode="append">\n- one\n</hard_rules>\n\n'
           '<hard_rules mode="append">\n- two\n</hard_rules>\n')
    result = _run(project / "packs" / "pack.yaml", library, project, "--check")
    assert result.returncode == 2
    assert "duplicate overlay block" in result.stderr


def test_template_may_not_escape_the_library(tmp_path):
    library, project = _fixture(tmp_path)
    pack = project / "packs" / "pack.yaml"
    pack.write_text(pack.read_text(encoding="utf-8").replace(
        "    template: agents/demo.md\n", "    template: ../SECRET.md\n"),
        encoding="utf-8")
    result = _run(pack, library, project, "--check")
    assert result.returncode == 2
    assert "template escapes" in result.stderr


def test_overlay_may_not_escape_the_project(tmp_path):
    library, project = _fixture(tmp_path)
    pack = project / "packs" / "pack.yaml"
    pack.write_text(pack.read_text(encoding="utf-8").replace(
        "    overlay: packs/overlays/demo.md\n", "    overlay: ../../etc/passwd\n"),
        encoding="utf-8")
    result = _run(pack, library, project, "--check")
    assert result.returncode == 2
    assert "overlay escapes" in result.stderr


def test_slot_value_with_slot_residue_is_an_input_error(tmp_path):
    library, project = _fixture(tmp_path)
    pack = project / "packs" / "pack.yaml"
    pack.write_text(pack.read_text(encoding="utf-8").replace(
        "      PROJECT_ID: demo-project\n", "      PROJECT_ID: '{{X}}'\n"),
        encoding="utf-8")
    result = _run(pack, library, project, "--check")
    assert result.returncode == 2
    assert "unsubstituted slot" in result.stderr
