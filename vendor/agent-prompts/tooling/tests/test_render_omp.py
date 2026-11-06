"""Tests for the OMP projection selection, budget and pin guards.

The guard cases build their own library tree (roles, fragments, catalog, the
foreground module set and its manifest) and call the checker functions
directly, so a failure is about the guard, not about the live catalog. Three
cases run the real `--check` / `--check --foreground` / render round trip: they
pin the shipped selection (12 entries and the measured description budget) and
the shipped foreground set (six modules, manifest order, per-module pin).
"""

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
RENDER = ROOT / "tooling" / "render_omp.py"

spec = importlib.util.spec_from_file_location("render_omp", RENDER)
render_omp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render_omp)

FG_SLOTS = ["PROJECT_ID", "PROJECT_RULES", "VERIFICATION_COMMANDS", "SAFETY_RULE"]
FG_SET_ID = "omp-foreground/1"
FG_MODULES = {
    "00-authority.md": "# Authority\n\nProject {{PROJECT_ID}} owns the reply "
                       "within {{PROJECT_RULES}}.\n",
    "10-delegation.md": "# Delegation\n\n- scout: locate a fact.\n"
                        "- reviewer: review a diff.\n",
    "20-evidence.md": "# Evidence\n\nVerify with {{VERIFICATION_COMMANDS}}.\n",
    "30-governance.md": "# Governance\n\n{{SAFETY_RULE}}\n",
}
FG_ORDER = list(FG_MODULES)
FG_BUDGETS = {"00-authority.md": 90, "10-delegation.md": 170,
              "20-evidence.md": 120, "30-governance.md": 150}
FG_VALUES = {"PROJECT_ID": "proj", "PROJECT_RULES": "rules",
             "VERIFICATION_COMMANDS": "verify", "SAFETY_RULE": "safety"}


def _role(tool_profile, purpose, body="fixture body"):
    return (
        "---\n"
        "type: role\n"
        "id: fixture\n"
        "purpose: %s\n"
        "tool_profile: %s\n"
        "---\n\n"
        "<role>\n%s\n</role>\n" % (purpose, tool_profile, body))


def _manifest(modules, order, budgets, total=700, set_id=FG_SET_ID):
    return {
        "schema": render_omp.FOREGROUND_SET_SCHEMA,
        "id": set_id,
        "order": list(order),
        "budget_tokens": total,
        "modules": {name: {
            "sha256": hashlib.sha256(modules[name].encode("utf-8")).hexdigest(),
            "budget_tokens": budgets[name],
        } for name in order},
    }


def _write_set(root, modules, manifest):
    directory = root / render_omp.FOREGROUND_SET_DIR
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in modules.items():
        (directory / name).write_text(text, encoding="utf-8")
    (directory / render_omp.FOREGROUND_MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return directory


def _library(tmp_path, roles, agents, deferred, modules=None, manifest=None,
             catalog_modules=None, catalog_id=None):
    """Write a library tree with the given roles, fragment pins and catalog."""
    root = tmp_path
    for rel, spec in roles.items():
        profile, purpose = spec[0], spec[1]
        body = spec[2] if len(spec) > 2 else "fixture body"
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_role(profile, purpose, body), encoding="utf-8")
    fragments = {}
    for key, name in (("doctrine", "agent-doctrine.md"),
                      ("conduct", "agent-conduct.omp.md")):
        path = root / "fragments" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<%s>\nfixture\n</%s>\n" % (key, key), encoding="utf-8")
        fragments[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    pins = {rel: hashlib.sha256((root / rel).read_bytes()).hexdigest() for rel in roles}
    modules = dict(FG_MODULES if modules is None else modules)
    manifest = manifest or _manifest(modules, FG_ORDER, FG_BUDGETS)
    _write_set(root, modules, manifest)
    catalog = {
        "schema": render_omp.CATALOG_SCHEMA,
        "library": "agent-prompts",
        "library_version": "0.0.0",
        "library_commit": "fixture",
        "fragment_sha256": fragments,
        "templates_sha256": pins,
        "foreground": {
            "id": catalog_id or FG_SET_ID,
            "modules": list(manifest["order"] if catalog_modules is None
                            else catalog_modules),
            "slots": list(FG_SLOTS),
        },
        "agents": agents,
        "deferred": deferred,
    }
    path = root / "omp" / "catalog.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    return root, path


def _pack(path, slots, name="ro"):
    """Write a minimal consumer pack; `slots` fills one entry named `name`."""
    path.write_text(yaml.safe_dump(
        {"schema": "agent-pack/1", "agents": [{"name": name, "slots": slots}]},
        sort_keys=False), encoding="utf-8")
    return path


def _entry(role, name, tools=None):
    return {"role": role, "name": name, "model": ["@slow", "@smol"],
            "tools": tools or ["read", "grep", "glob"]}


def _roles(**pairs):
    """Return {role path: (tool_profile, purpose)} from (path, profile, purpose) pairs."""
    roles = {}
    for value in pairs.values():
        path, profile, purpose = value[:3]
        roles[path] = (profile, purpose) + tuple(value[3:])
    return roles


def _foreground_errors(root, path):
    errors, _, _ = render_omp.check_catalog(root, path)
    return errors


READ_ONLY = "read-only"
GATED = "gated-write"
FIXTURE_PURPOSE = "Read a fixture."


def test_write_capable_entry_fails_with_clear_message(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE),
                   write=("agents/eng/write.md", GATED, "Write a fixture."))
    root, _ = _library(
        tmp_path, roles,
        [_entry("agents/eng/ro.md", "ro"), _entry("agents/eng/write.md", "writer")],
        [])
    errors = []
    render_omp.check_coverage(root, [_entry("agents/eng/ro.md", "ro"),
                                     _entry("agents/eng/write.md", "writer")], [], errors)
    assert len(errors) == 1, errors
    assert "write-capable" in errors[0]
    assert "agents/eng/write.md" in errors[0]
    assert "gated-write" in errors[0]


def test_unaccounted_read_only_role_fails(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE),
                   orphan=("agents/eng/orphan.md", READ_ONLY, FIXTURE_PURPOSE))
    root, _ = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")], [])
    errors = []
    render_omp.check_coverage(root, [_entry("agents/eng/ro.md", "ro")], [], errors)
    assert len(errors) == 1, errors
    assert "agents/eng/orphan.md" in errors[0]
    assert "neither projected under agents: nor listed under deferred:" in errors[0]


def test_deferred_role_accounts_for_a_read_only_role(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE),
                   later=("agents/eng/later.md", READ_ONLY, FIXTURE_PURPOSE))
    root, _ = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")],
                       [{"role": "agents/eng/later.md", "reason": "fixture reason"}])
    errors = []
    render_omp.check_coverage(root, [_entry("agents/eng/ro.md", "ro")],
                              ["agents/eng/later.md"], errors)
    assert errors == []


def test_role_that_declares_no_tools_must_be_deferred(tmp_path):
    body = ("<hard_rules>\n"
            "- {{MUTATION_POLICY}}: no tools -- synthesize from the provided "
            "responses only.\n"
            "</hard_rules>")
    roles = _roles(ro=("agents/orch/ro.md", READ_ONLY, FIXTURE_PURPOSE),
                   quiet=("agents/orch/quiet.md", READ_ONLY,
                          "Merge the provided responses.", body))
    entries = [_entry("agents/orch/ro.md", "ro"),
               _entry("agents/orch/quiet.md", "quiet")]
    root, _ = _library(tmp_path, roles, entries, [])
    errors = []
    render_omp.check_coverage(root, entries, [], errors)
    assert len(errors) == 1, errors
    assert "declares no tools" in errors[0]
    assert "agents/orch/quiet.md" in errors[0]
    assert "deferred:" in errors[0]
    assert "broad default" in errors[0]

    errors = []
    render_omp.check_coverage(root, entries[:1], ["agents/orch/quiet.md"], errors)
    assert errors == []


def test_incidental_no_tools_phrase_outside_the_mutation_policy_line_is_not_a_declaration(tmp_path):
    body = ("<hard_rules>\n"
            "- {{MUTATION_POLICY}}: read-only -- report only.\n"
            "</hard_rules>\n\n"
            "<workflow>\n"
            "Step 3 -- no tools are required for this step; read the diff and\n"
            "report the finding to the requesting session.\n"
            "</workflow>")
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE),
                   chatty=("agents/eng/chatty.md", READ_ONLY,
                           "Report a finding.", body))
    entries = [_entry("agents/eng/ro.md", "ro"),
               _entry("agents/eng/chatty.md", "chatty")]
    root, _ = _library(tmp_path, roles, entries, [])
    assert render_omp.declares_no_tools(root, "agents/eng/chatty.md") is False
    errors = []
    render_omp.check_coverage(root, entries, [], errors)
    assert errors == [], errors


@pytest.mark.parametrize("rule", ["no tools -- merge only.",
                                  "tool-free -- merge only.",
                                  "without tools -- merge only.",
                                  "without any tools -- merge only."])
def test_tool_free_postures_on_the_mutation_policy_line_are_recognised(tmp_path, rule):
    body = "<hard_rules>\n- {{MUTATION_POLICY}}: %s\n</hard_rules>" % rule
    roles = _roles(quiet=("agents/orch/quiet.md", READ_ONLY,
                          "Merge the provided responses.", body))
    root, _ = _library(tmp_path, roles, [], [])
    assert render_omp.declares_no_tools(root, "agents/orch/quiet.md") is True


def test_live_council_synthesizer_mutation_policy_still_declares_no_tools(tmp_path):
    role = "agents/orchestration/orch-council-synthesizer.md"
    line = next(text for text in
                (ROOT / role).read_text(encoding="utf-8").splitlines()
                if "{{MUTATION_POLICY}}" in text)
    assert "no tools" in line, line
    assert render_omp.declares_no_tools(ROOT, role) is True
    # The shipped line, in a fixture body, still forces the deferral error.
    body = "<hard_rules>\n%s\n</hard_rules>" % line
    roles = _roles(quiet=("agents/orch/quiet.md", READ_ONLY,
                          "Merge the provided responses.", body))
    quiet = _entry("agents/orch/quiet.md", "quiet")
    root, _ = _library(tmp_path, roles, [quiet], [])
    errors = []
    render_omp.check_coverage(root, [quiet], [], errors)
    assert any("declares no tools" in message for message in errors), errors


def test_second_orchestrator_entry_fails(tmp_path):
    roles = _roles(orch=("agents/orch/one.md", "orchestrator", "Own the loop."),
                   orch2=("agents/orch/two.md", "orchestrator", "Own the loop."))
    root, _ = _library(tmp_path, roles,
                       [_entry("agents/orch/one.md", "one"),
                        _entry("agents/orch/two.md", "two")], [])
    errors = []
    render_omp.check_coverage(root, [_entry("agents/orch/one.md", "one"),
                                     _entry("agents/orch/two.md", "two")], [], errors)
    assert any("at most one is allowed" in message for message in errors), errors


def test_deferred_reason_is_required(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")],
                          [{"role": "agents/eng/ro.md", "reason": "   "}])
    errors, entries, deferred = render_omp.check_catalog(root, path)
    assert any("needs a one-line reason" in message for message in errors), errors
    assert any("both projected in agents: and deferred" in message for message in errors), errors


def test_deferred_reason_key_is_required(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")],
                          [{"role": "agents/eng/ro.md"}])
    errors, _, _ = render_omp.check_catalog(root, path)
    assert any("missing required key 'reason'" in message for message in errors), errors


def test_unknown_deferred_key_fails(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")], [])
    catalog = yaml.safe_load(path.read_text(encoding="utf-8"))
    catalog["deferred"] = [{"role": "agents/eng/ro.md", "reason": "x", "note": "y"}]
    path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    errors, _, _ = render_omp.check_catalog(root, path)
    assert any("unknown deferred key" in message for message in errors), errors


def test_stale_pin_prints_the_expected_hash(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")], [])
    catalog = yaml.safe_load(path.read_text(encoding="utf-8"))
    catalog["templates_sha256"]["agents/eng/ro.md"] = "0" * 64
    path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    expected = hashlib.sha256((root / "agents/eng/ro.md").read_bytes()).hexdigest()
    errors, _, _ = render_omp.check_catalog(root, path)
    assert len(errors) == 1, errors
    assert "role drift" in errors[0]
    assert "computed %s" % expected in errors[0]
    assert "templates_sha256 with `agents/eng/ro.md: %s`" % expected in errors[0]


def test_description_budget_is_measured_and_enforced(tmp_path, monkeypatch):
    roles = _roles(alpha=("agents/eng/alpha.md", READ_ONLY, "a" * 400),
                   beta=("agents/eng/beta.md", READ_ONLY, "b" * 400))
    root, _ = _library(tmp_path, roles,
                       [_entry("agents/eng/alpha.md", "alpha"),
                        _entry("agents/eng/beta.md", "beta")], [])
    entries = [_entry("agents/eng/alpha.md", "alpha"), _entry("agents/eng/beta.md", "beta")]
    monkeypatch.setattr(render_omp, "DESCRIPTION_BUDGET", 250)
    errors = []
    total = render_omp.check_description_budget(root, entries, errors)
    assert total == 200, total
    assert errors == []

    monkeypatch.setattr(render_omp, "DESCRIPTION_BUDGET", 150)
    errors = []
    total = render_omp.check_description_budget(root, entries, errors)
    assert total == 200
    assert len(errors) == 1, errors
    assert "description budget exceeded" in errors[0]
    assert "200 tokens, cap is 150" in errors[0]


def test_live_catalog_check_is_green_with_12_entries():
    result = subprocess.run([sys.executable, str(RENDER), "--check"],
                            cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "12 projected entries" in result.stdout
    assert "BUDGET " in result.stdout and "/%d description tokens" % render_omp.DESCRIPTION_BUDGET in result.stdout
    assert "12 entries" in result.stdout
    assert re.search(r"BUDGET \d+/\d+ foreground tokens "
                     r"\(omp/prompts/foreground, 6 modules, 4 slots\)",
                     result.stdout), result.stdout
    for module in render_omp.read_foreground_manifest(ROOT)["order"]:
        assert "foreground module tokens (%s)" % module in result.stdout


def test_foreground_compose_order_matches_the_manifest(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")], [])
    _, _, text = render_omp.read_foreground(root, path)
    expected = "\n\n".join(FG_MODULES[name].strip("\n") for name in FG_ORDER) + "\n"
    assert text == expected
    assert text.count("\n\n# ") == len(FG_ORDER) - 1


def test_foreground_render_fills_every_slot_and_leaves_no_residue(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")], [])
    pack = _pack(tmp_path / "pack.yaml", FG_VALUES)
    text = render_omp.render_foreground(render_omp.read_foreground(root, path), pack)
    for value in FG_VALUES.values():
        assert value in text, value
    assert "{{" not in text
    assert "}}" not in text
    assert not text.lstrip().startswith("---")
    assert text.startswith("# Authority")
    assert [line for line in text.splitlines() if line.startswith("# ")] == [
        "# Authority", "# Delegation", "# Evidence", "# Governance"]


def test_foreground_missing_slot_fails_with_the_slot_name(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")], [])
    slots = dict(FG_VALUES)
    del slots["SAFETY_RULE"]
    pack = _pack(tmp_path / "pack.yaml", slots)
    with pytest.raises(ValueError) as excinfo:
        render_omp.render_foreground(render_omp.read_foreground(root, path), pack)
    assert "SAFETY_RULE" in str(excinfo.value)
    assert "no value for foreground slot" in str(excinfo.value)


def test_foreground_pack_disagreement_fails_with_the_slot_name(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")], [])
    pack = tmp_path / "pack.yaml"
    pack.write_text(yaml.safe_dump({"schema": "agent-pack/1", "agents": [
        {"name": "ro", "slots": dict(FG_VALUES)},
        {"name": "other", "slots": dict(FG_VALUES, PROJECT_ID="other")},
    ]}, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        render_omp.render_foreground(render_omp.read_foreground(root, path), pack)
    assert "disagree" in str(excinfo.value)
    assert "PROJECT_ID" in str(excinfo.value)


def test_stale_foreground_module_pin_names_the_module_and_prints_the_refresh_line(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")], [])
    manifest = render_omp.read_foreground_manifest(root)
    manifest["modules"]["20-evidence.md"]["sha256"] = "0" * 64
    (root / render_omp.FOREGROUND_SET_DIR / render_omp.FOREGROUND_MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    expected = hashlib.sha256(
        (root / render_omp.FOREGROUND_SET_DIR / "20-evidence.md").read_bytes()).hexdigest()
    errors = _foreground_errors(root, path)
    assert len(errors) == 1, errors
    assert "foreground module drift" in errors[0]
    assert "20-evidence.md" in errors[0]
    assert "computed %s" % expected in errors[0]
    assert '"20-evidence.md": "%s"' % expected in errors[0]
    assert "00-authority.md" not in errors[0]


def test_missing_foreground_module_fails_with_a_distinct_message(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")], [])
    (root / render_omp.FOREGROUND_SET_DIR / "20-evidence.md").unlink()
    errors = _foreground_errors(root, path)
    assert len(errors) == 1, errors
    assert "missing module omp/prompts/foreground/20-evidence.md on disk" in errors[0]
    assert "order" in errors[0]


def test_extra_foreground_module_on_disk_fails_with_a_distinct_message(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")], [])
    (root / render_omp.FOREGROUND_SET_DIR / "60-stray.md").write_text(
        "# Stray\n", encoding="utf-8")
    errors = _foreground_errors(root, path)
    assert len(errors) == 1, errors
    assert "carries module omp/prompts/foreground/60-stray.md on disk" in errors[0]
    assert "order does not list" in errors[0]


def test_reordered_foreground_manifest_fails_with_a_distinct_message(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")], [])
    manifest = render_omp.read_foreground_manifest(root)
    manifest["order"] = list(reversed(manifest["order"]))
    (root / render_omp.FOREGROUND_SET_DIR / render_omp.FOREGROUND_MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    errors = _foreground_errors(root, path)
    assert len(errors) == 1, errors
    assert "order is reordered" in errors[0]
    assert "first divergence is position 1" in errors[0]
    assert "manifest order is the compose order" in errors[0]


def test_catalog_foreground_module_absent_from_the_manifest_fails(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")], [],
                          catalog_modules=FG_ORDER + ["40-safety.md"])
    errors = _foreground_errors(root, path)
    assert len(errors) == 1, errors
    assert "foreground.modules lists 40-safety.md" in errors[0]
    assert "manifest.json order does not" in errors[0]


def test_foreground_set_id_mismatch_fails(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")], [],
                          catalog_id="omp-foreground/2")
    errors = _foreground_errors(root, path)
    assert len(errors) == 1, errors
    assert "foreground set id mismatch" in errors[0]
    assert "omp-foreground/2" in errors[0] and "omp-foreground/1" in errors[0]


def test_foreground_block_is_required_and_declares_used_slots(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")], [])
    catalog = yaml.safe_load(path.read_text(encoding="utf-8"))
    catalog["foreground"]["slots"] = list(FG_SLOTS) + ["UNUSED_SLOT"]
    path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    errors, _, _ = render_omp.check_catalog(root, path)
    assert any("UNUSED_SLOT" in message and "does not use" in message
               for message in errors), errors

    del catalog["foreground"]
    path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    errors, _, _ = render_omp.check_catalog(root, path)
    assert any("no foreground block" in message for message in errors), errors


def test_used_but_undeclared_foreground_slot_fails(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")], [])
    catalog = yaml.safe_load(path.read_text(encoding="utf-8"))
    catalog["foreground"]["slots"] = ["PROJECT_ID", "PROJECT_RULES",
                                      "VERIFICATION_COMMANDS"]
    path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    errors = _foreground_errors(root, path)
    assert len(errors) == 1, errors
    assert "uses {{SAFETY_RULE}}" in errors[0]
    assert "does not declare" in errors[0]


def test_foreground_module_budget_is_enforced(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")], [])
    manifest = render_omp.read_foreground_manifest(root)
    manifest["modules"]["10-delegation.md"]["budget_tokens"] = 3
    (root / render_omp.FOREGROUND_SET_DIR / render_omp.FOREGROUND_MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    errors = _foreground_errors(root, path)
    assert len(errors) == 1, errors
    assert "foreground module budget exceeded: 10-delegation.md" in errors[0]
    assert "cap is 3" in errors[0]
    assert "omp/README.md" in errors[0]


def test_foreground_total_budget_is_enforced(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")], [])
    manifest = render_omp.read_foreground_manifest(root)
    manifest["budget_tokens"] = 1
    (root / render_omp.FOREGROUND_SET_DIR / render_omp.FOREGROUND_MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    errors = _foreground_errors(root, path)
    assert len(errors) == 1, errors
    assert "foreground budget exceeded: the composed set estimates" in errors[0]
    assert "cap is 1" in errors[0]
    assert "omp/README.md" in errors[0]


def test_foreground_budget_above_the_renderer_ceiling_fails(tmp_path):
    roles = _roles(ro=("agents/eng/ro.md", READ_ONLY, FIXTURE_PURPOSE))
    root, path = _library(tmp_path, roles, [_entry("agents/eng/ro.md", "ro")], [])
    manifest = render_omp.read_foreground_manifest(root)
    manifest["budget_tokens"] = render_omp.FOREGROUND_BUDGET + 1
    (root / render_omp.FOREGROUND_SET_DIR / render_omp.FOREGROUND_MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    errors = _foreground_errors(root, path)
    assert len(errors) == 1, errors
    assert "raised past the renderer ceiling" in errors[0]
    assert "deliberate decision" in errors[0]
    assert "`FOREGROUND_BUDGET` in `tooling/render_omp.py`" in errors[0]
    assert "record the reason in `omp/README.md`" in errors[0]
    assert "catalog" not in errors[0]


def test_live_safety_module_places_the_rule_in_label_position():
    text = (ROOT / render_omp.FOREGROUND_SET_DIR / "40-safety.md").read_text(
        encoding="utf-8")
    label_lines = [line for line in text.splitlines() if "{{SAFETY_RULE}}" in line]
    assert label_lines, "the safety module no longer carries the slot"
    for line in label_lines:
        assert line.startswith("- {{SAFETY_RULE}}:"), line
    for phrase in ("force-push", "deleting data or volumes",
                   "deploying or redeploying a stack", "dropping a database"):
        assert phrase in text, phrase
    # The rendered policy must not degenerate into a trailing label.
    rendered = text.replace("{{SAFETY_RULE}}", "safety")
    assert "- safety: " in rendered
    assert "step. safety" not in rendered


def test_live_governance_module_covers_a_ci_runner_and_a_local_only_repo():
    text = (ROOT / render_omp.FOREGROUND_SET_DIR / "30-governance.md").read_text(
        encoding="utf-8")
    assert "Where CI has a runner" in text
    assert "required checks" in text
    assert "local gate output" in text
    assert "reported as not run" in text
    assert "may have no runner" not in text


def test_live_foreground_set_has_six_headings_in_compose_order():
    manifest = render_omp.read_foreground_manifest(ROOT)
    label, slots, text = render_omp.read_foreground(
        ROOT, ROOT / "omp" / "catalog.yaml")
    assert label == render_omp.FOREGROUND_SET_DIR
    assert sorted(slots) == sorted(FG_SLOTS)
    headings = [line for line in text.splitlines() if line.startswith("# ")]
    assert headings == ["# Authority", "# Delegation", "# Evidence",
                        "# Governance", "# Safety", "# Output"]
    for module in manifest["order"]:
        assert ("# " + Path(module).stem.split("-", 1)[1].capitalize()) in headings
    assert text == "\n\n".join(
        (ROOT / render_omp.FOREGROUND_SET_DIR / name).read_text(
            encoding="utf-8").strip("\n") for name in manifest["order"]) + "\n"


def test_live_foreground_set_is_plain_markdown_with_read_only_delegation():
    catalog = yaml.safe_load((ROOT / "omp" / "catalog.yaml").read_text(encoding="utf-8"))
    _, _, text = render_omp.read_foreground(ROOT, ROOT / "omp" / "catalog.yaml")
    for module in render_omp.read_foreground_manifest(ROOT)["order"]:
        module_text = (ROOT / render_omp.FOREGROUND_SET_DIR / module).read_text(
            encoding="utf-8")
        assert not module_text.lstrip().startswith("---"), module
    assert not text.lstrip().startswith("---")
    assert sorted(set(render_omp.SLOT_RE.findall(text))) == sorted(FG_SLOTS)
    assert sorted(catalog["foreground"]["slots"]) == sorted(FG_SLOTS)
    # Delegation lines are `- <agent>: <when>`; a `- {{SLOT}}: <text>` line is a
    # policy label (safety), not a dispatched agent.
    dispatched = [line[2:].split(":")[0] for line in text.splitlines()
                  if line.startswith("- ") and not line.startswith("- {{")]
    entries = {entry["name"]: entry for entry in catalog["agents"]}
    assert sorted(dispatched) == sorted(entries), dispatched
    profiles = render_omp.role_profiles(ROOT)
    allowed = set(render_omp.READ_ONLY_TOOLS) | {render_omp.DISPATCH_TOOL}
    for name in dispatched:
        entry = entries[name]
        assert set(entry["tools"]) <= allowed, entry["tools"]
        assert profiles[entry["role"]] in (render_omp.READ_ONLY_PROFILE,
                                           render_omp.ORCHESTRATOR_PROFILE)
    # No tool grant: the policy never hands the main session a tool list, and
    # the only mutation words are in the read-only statement.
    assert not re.search(r"(?m)^\s*(tools|write|edit|bash|shell)\s*:", text)
    assert "read-only" in text
    assert "no write, edit or shell" in text


def test_live_foreground_render_and_byte_compare_round_trip(tmp_path):
    pack = _pack(tmp_path / "pack.yaml", {
        "PROJECT_ID": "proj", "PROJECT_RULES": "rules",
        "VERIFICATION_COMMANDS": "make gate", "SAFETY_RULE": "No prod writes."})
    out = tmp_path / "APPEND_SYSTEM.md"
    first = subprocess.run(
        [sys.executable, str(RENDER), "--foreground", "--pack", str(pack),
         "--out", str(out)], cwd=str(ROOT), capture_output=True, text=True)
    assert first.returncode == 0, first.stdout + first.stderr
    second = subprocess.run(
        [sys.executable, str(RENDER), "--check", "--foreground", "--pack", str(pack),
         "--out", str(out)], cwd=str(ROOT), capture_output=True, text=True)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "OK foreground policy omp/prompts/foreground matches" in second.stdout
    text = out.read_text(encoding="utf-8")
    assert "{{" not in text and "}}" not in text
    assert text.count("\n\n# ") == 5
