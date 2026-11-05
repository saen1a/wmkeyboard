"""Tests for the model-surface registry checker."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tooling" / "check_model_surface.py"
EXAMPLE = ROOT / "standards" / "model-surface.json"
SCHEMA = ROOT / "standards" / "model-surface.schema.json"
COPY = ("agents", "commands", "dsh", "fragments", "omp", "prompts", "skills", "standards")
TARGET = "agents/engineering/eng-api-developer.md"


def _load():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _copy_tree(tmp_path):
    for name in COPY:
        shutil.copytree(ROOT / name, tmp_path / name,
                        ignore=shutil.ignore_patterns("__pycache__"))
    return tmp_path


def _run(tmp_path, data, *extra):
    path = tmp_path / "standards" / "model-surface.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return subprocess.run([sys.executable, str(CHECK), "--root", str(tmp_path), *extra],
                          cwd=str(ROOT), capture_output=True, text=True)


def _append_citation(root, citation="AP-99"):
    path = root / TARGET
    path.write_text(path.read_text(encoding="utf-8") + "\nSee %s for details.\n" % citation,
                    encoding="utf-8")


def _allow(citation="AP-99", path=TARGET, review_by="2999-12-31"):
    return {"citation": citation, "path": path,
            "reason": "awaiting the rule that owns this citation", "review_by": review_by}


def test_repo_registry_clean():
    result = subprocess.run([sys.executable, str(CHECK)], cwd=str(ROOT),
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    assert "0 violation(s)" in result.stdout


def test_json_output_reports_counts(tmp_path):
    root = _copy_tree(tmp_path)
    result = _run(root, _load(), "--json")
    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    for key in ("surfaces", "files", "total_tokens", "citations", "unresolved",
                "violations", "warnings"):
        assert key in payload
    assert payload["violations"] == []
    assert payload["unresolved"] == 0


def test_unregistered_file_fails(tmp_path):
    root = _copy_tree(tmp_path)
    (root / "agents" / "notes.txt").write_text("Stray asset.\n", encoding="utf-8")
    result = _run(root, _load())
    assert result.returncode == 1
    assert "unregistered asset inside a registered root: agents/notes.txt" in result.stdout


def test_double_registration_fails(tmp_path):
    root = _copy_tree(tmp_path)
    data = _load()
    data["surfaces"].append({"id": "engineering-roles", "glob": "agents/engineering/*.md",
                             "kind": "role", "budget_tokens": 1500,
                             "measured_max_tokens": 1200,
                             "rationale": "overlapping slice for the test"})
    result = _run(root, data)
    assert result.returncode == 1
    assert "matched by more than one surface" in result.stdout


def test_glob_matching_nothing_fails(tmp_path):
    root = _copy_tree(tmp_path)
    data = _load()
    data["surfaces"].append({"id": "empty-root", "glob": "prompts/nothing/*.md",
                             "kind": "task", "budget_tokens": 100,
                             "measured_max_tokens": 10,
                             "rationale": "no files land here yet"})
    result = _run(root, data)
    assert result.returncode == 1
    assert "surface empty-root glob matches no file" in result.stdout


def test_over_budget_file_fails(tmp_path):
    root = _copy_tree(tmp_path)
    data = _load()
    for surface in data["surfaces"]:
        if surface["id"] == "commands":
            surface["budget_tokens"] = 10
    result = _run(root, data)
    assert result.returncode == 1
    assert "surface commands is over budget 10" in result.stdout
    assert "top offenders" in result.stdout


def test_dangling_citation_fails(tmp_path):
    root = _copy_tree(tmp_path)
    _append_citation(root)
    result = _run(root, _load())
    assert result.returncode == 1
    assert "citation AP-99 in %s does not resolve" % TARGET in result.stdout
    assert "standards/agent-prompt-standard.md" in result.stdout


def test_allowed_dangling_citation_passes(tmp_path):
    root = _copy_tree(tmp_path)
    _append_citation(root)
    data = _load()
    data["allow_unresolved"] = [_allow()]
    result = _run(root, data)
    assert result.returncode == 0, result.stdout


def test_stale_allow_entry_fails(tmp_path):
    root = _copy_tree(tmp_path)
    data = _load()
    data["allow_unresolved"] = [_allow()]
    result = _run(root, data)
    assert result.returncode == 1
    assert "allow_unresolved entry for AP-99 in %s is stale" % TARGET in result.stdout


def test_expired_review_by_fails(tmp_path):
    root = _copy_tree(tmp_path)
    _append_citation(root)
    data = _load()
    data["allow_unresolved"] = [_allow(review_by="2000-01-01")]
    result = _run(root, data)
    assert result.returncode == 1
    assert "expired on 2000-01-01" in result.stdout


def test_unnecessary_allow_entry_fails(tmp_path):
    root = _copy_tree(tmp_path)
    _append_citation(root, "AP-01")
    data = _load()
    data["allow_unresolved"] = [_allow(citation="AP-01")]
    result = _run(root, data)
    assert result.returncode == 1
    assert "is unnecessary" in result.stdout


def test_unknown_key_fails(tmp_path):
    root = _copy_tree(tmp_path)
    data = _load()
    data["owner"] = "someone"
    result = _run(root, data)
    assert result.returncode == 1
    assert "unknown top-level key: owner" in result.stdout


def test_unknown_surface_key_fails(tmp_path):
    root = _copy_tree(tmp_path)
    data = _load()
    data["surfaces"][0]["owner"] = "someone"
    result = _run(root, data)
    assert result.returncode == 1
    assert "surfaces[0] unknown key: owner" in result.stdout


def test_missing_family_file_fails(tmp_path):
    root = _copy_tree(tmp_path)
    data = _load()
    data["rule_families"]["ZZ"] = "standards/does-not-exist.md"
    result = _run(root, data)
    assert result.returncode == 1
    assert "missing rule family file for ZZ: standards/does-not-exist.md" in result.stdout


def test_unregistered_family_fails(tmp_path):
    root = _copy_tree(tmp_path)
    path = root / "standards" / "english-only.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n## ZZ-01 -- Test rule\n\nBody.\n",
                    encoding="utf-8")
    result = _run(root, _load())
    assert result.returncode == 1
    assert "rule family ZZ is defined in standards/english-only.md but not registered" \
        in result.stdout


def test_bad_budget_fails(tmp_path):
    root = _copy_tree(tmp_path)
    data = _load()
    data["surfaces"][0]["budget_tokens"] = 0
    result = _run(root, data)
    assert result.returncode == 1
    assert "budget_tokens must be a positive integer" in result.stdout


def test_bad_glob_fails(tmp_path):
    root = _copy_tree(tmp_path)
    data = _load()
    data["surfaces"][0]["glob"] = "../agents/*.md"
    result = _run(root, data)
    assert result.returncode == 1
    assert "glob is not a sane relative glob" in result.stdout


def test_unreadable_registry_exits_2(tmp_path):
    root = _copy_tree(tmp_path)
    (root / "standards" / "model-surface.json").write_text("{not json\n", encoding="utf-8")
    result = subprocess.run([sys.executable, str(CHECK), "--root", str(root)],
                            cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 2


def test_schema_required_keys_match_checker():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT / "tooling"))
    import check_model_surface

    assert sorted(schema["required"]) == sorted(check_model_surface.REQUIRED)
    assert sorted(schema["properties"]) == sorted(check_model_surface.TOP_KEYS)
    assert schema["properties"]["schema"]["const"] == check_model_surface.SCHEMA
    items = schema["properties"]["surfaces"]["items"]
    assert sorted(items["required"]) == sorted(check_model_surface.SURFACE_REQUIRED)
    assert sorted(items["properties"]) == sorted(check_model_surface.SURFACE_KEYS)
    allow = schema["properties"]["allow_unresolved"]["items"]
    assert sorted(allow["required"]) == sorted(check_model_surface.ALLOW_REQUIRED)
    assert sorted(allow["properties"]) == sorted(check_model_surface.ALLOW_KEYS)


def test_schema_enums_match_checker():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT / "tooling"))
    import check_model_surface

    items = schema["properties"]["surfaces"]["items"]
    assert tuple(items["properties"]["kind"]["enum"]) == check_model_surface.KINDS
    assert items["properties"]["glob"]["pattern"] == check_model_surface.GLOB_RE.pattern
    assert schema["properties"]["rule_families"]["additionalProperties"]["pattern"] \
        == check_model_surface.FAMILY_PATH_RE.pattern


def test_registry_example_declares_every_standard_family():
    data = _load()
    defined = set()
    for path in (ROOT / "standards").glob("*.md"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## ") and " -- " in line:
                rule = line[3:].split(" -- ")[0]
                if len(rule) == 5 and rule[2] == "-":
                    defined.add(rule[:2])
    assert defined <= set(data["rule_families"])


def _write_registry(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def _run_root(root, *extra):
    return subprocess.run([sys.executable, str(CHECK), "--root", str(root), *extra],
                          cwd=str(ROOT), capture_output=True, text=True)


def _run_with_registry(root, registry, *extra):
    return subprocess.run([sys.executable, str(CHECK), "--root", str(root),
                           "--registry", str(registry), *extra],
                          cwd=str(ROOT), capture_output=True, text=True)


def test_registry_outside_root_passes(tmp_path):
    root = _copy_tree(tmp_path / "tree")
    (root / "standards" / "model-surface.json").unlink()
    registry = _write_registry(tmp_path / "consumer" / "registry.json", _load())
    result = _run_with_registry(root, registry)
    assert result.returncode == 0, result.stdout
    assert "0 violation(s)" in result.stdout


def test_missing_registry_exits_2(tmp_path):
    root = _copy_tree(tmp_path / "tree")
    registry = tmp_path / "absent-registry.json"
    result = _run_with_registry(root, registry)
    assert result.returncode == 2
    assert str(registry) in result.stdout


def test_unparsable_registry_exits_2(tmp_path):
    root = _copy_tree(tmp_path / "tree")
    registry = tmp_path / "broken-registry.json"
    registry.write_text("{not json\n", encoding="utf-8")
    result = _run_with_registry(root, registry)
    assert result.returncode == 2
    assert str(registry) in result.stdout


def test_registry_override_checks_citations_against_root(tmp_path):
    root = _copy_tree(tmp_path / "tree")
    (root / "standards" / "consumer-rules.md").write_text(
        "# Consumer rules\n\n## QQ-01 -- Rule that exists in the scanned tree\n\nBody.\n",
        encoding="utf-8")
    _append_citation(root, "QQ-07")
    external = tmp_path / "consumer" / "standards"
    external.mkdir(parents=True)
    (external / "consumer-rules.md").write_text(
        "# Consumer rules\n\n## QQ-07 -- Consumer-only rule\n\nBody.\n", encoding="utf-8")
    data = _load()
    data["rule_families"]["QQ"] = "standards/consumer-rules.md"
    registry = _write_registry(tmp_path / "consumer" / "registry.json", data)
    result = _run_with_registry(root, registry)
    assert result.returncode == 1
    assert "citation QQ-07 in %s does not resolve to a definition in standards/consumer-rules.md" \
        % TARGET in result.stdout


def test_relative_registry_resolves_against_cwd(tmp_path):
    root = _copy_tree(tmp_path / "tree")
    _write_registry(tmp_path / "registry.json", _load())
    result = subprocess.run([sys.executable, str(CHECK), "--root", str(root),
                             "--registry", "registry.json"],
                            cwd=str(tmp_path), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


def test_json_output_carries_registry_path(tmp_path):
    root = _copy_tree(tmp_path / "tree")
    registry = _write_registry(tmp_path / "consumer" / "registry.json", _load())
    result = _run_with_registry(root, registry, "--json")
    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["registry"] == str(registry)
    for key in ("surfaces", "files", "total_tokens", "citations", "unresolved",
                "violations", "warnings"):
        assert key in payload
    assert payload["unresolved"] == 0


def test_json_output_registry_defaults_to_root_registry(tmp_path):
    root = _copy_tree(tmp_path / "tree")
    result = subprocess.run([sys.executable, str(CHECK), "--root", str(root), "--json"],
                            cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["registry"] == str(root / "standards" / "model-surface.json")


def test_table_defined_rule_resolves(tmp_path):
    """A standard may define a rule as a table row, not only as a heading."""
    root = _copy_tree(tmp_path / "table")
    standard = root / "standards" / "halt-taxonomy.md"
    assert standard.is_file()
    assert "## HF-01 -- " not in standard.read_text()
    asset = root / "agents" / "engineering" / "eng-api-developer.md"
    asset.write_text(asset.read_text() + "\nMaterial gaps stop the unit (HF-01).\n")
    result = _run_root(root)
    assert result.returncode == 0, result.stdout
    assert "0 unresolved" in result.stdout


def test_table_row_citation_that_is_absent_still_fails(tmp_path):
    root = _copy_tree(tmp_path / "absent")
    asset = root / "agents" / "engineering" / "eng-api-developer.md"
    asset.write_text(asset.read_text() + "\nMaterial gaps stop the unit (HF-99).\n")
    result = _run_root(root)
    assert result.returncode == 1
    assert "HF-99" in result.stdout
    assert "does not resolve to a definition" in result.stdout
