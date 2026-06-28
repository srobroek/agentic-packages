"""Smoke + invariant tests for the frozen shared contracts and path resolution.

Imports the runner library by file path (the verified speckit-dag-hooks
precedent: no editable install, no pyproject on the test path). Run via:
    uv run --with pytest pytest -q packages/project-setup/tests/test_contracts.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # MUST register in sys.modules BEFORE exec_module: a module loaded by file
    # path is otherwise absent from sys.modules, and @dataclass on a class that
    # subclasses Exception (SetupError) resolves cls.__module__ via
    # sys.modules[...].__dict__ — which is None unless registered. This is a
    # contract requirement for EVERY import-by-path site (tests and module.py).
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


contracts = _load("contracts")
paths = _load("paths")


# --- canonical_json is byte-stable and matches the build_nodes precedent ----- #
def test_canonical_json_is_sorted_pretty_and_newline_terminated():
    out = contracts.canonical_json({"b": 1, "a": [2, 1]})
    assert out.endswith("\n")
    # sorted keys, 2-space indent
    assert out.index('"a"') < out.index('"b"')
    assert "\n  " in out
    # round-trips
    assert json.loads(out) == {"b": 1, "a": [2, 1]}


def test_canonical_json_is_deterministic_across_calls():
    payload = {"z": {"y": 2, "x": 1}, "a": ["m", "k"]}
    assert contracts.canonical_json(payload) == contracts.canonical_json(payload)


# --- error envelope carries multi-id participants ----------------------------- #
def test_setup_error_to_dict_has_module_ids_field():
    err = contracts.SetupError(
        error_code=contracts.ErrorCode.ID_COLLISION,
        expected="unique id",
        received="duplicate 'git-init'",
        how_to_fix="rename one module",
        module_ids=["/a/git-init", "/b/git-init"],
    )
    d = err.to_dict()
    assert d["error_code"] == "ID_COLLISION"
    assert d["module_ids"] == ["/a/git-init", "/b/git-init"]
    assert d["how_to_fix"]  # always populated


def test_gate_failure_batches_all_errors():
    errs = [
        contracts.SetupError(contracts.ErrorCode.MISSING_ANSWER, "x", "missing", "add x"),
        contracts.SetupError(contracts.ErrorCode.DEPENDENCY_CYCLE, "acyclic", "a->b->a", "break it"),
    ]
    gf = contracts.GateFailure(errs)
    assert len(gf.errors) == 2
    assert len(gf.to_dict()["errors"]) == 2


# --- provenance: modules may only self-report a restricted subset ------------- #
def test_module_emittable_provenance_excludes_assigned_sources():
    emittable = contracts.MODULE_EMITTABLE_PROVENANCE
    assert contracts.Provenance.DERIVED in emittable
    assert contracts.Provenance.AGENT_STEERED in emittable
    assert contracts.Provenance.DEFAULT in emittable
    # persistence-assigned sources must NOT be module-emittable
    assert contracts.Provenance.FLAG not in emittable
    assert contracts.Provenance.HOME not in emittable
    assert contracts.Provenance.PROJECT not in emittable


# --- forbidden fields enforce 'no priority' + reject superseded draft schema -- #
def test_forbidden_fields_include_priority_and_legacy_draft_fields():
    f = contracts.FORBIDDEN_MANIFEST_FIELDS
    for k in ("priority", "title", "entrypoint", "required_answers", "produces"):
        assert k in f


# --- module result shape: files_written is the canonical key ------------------ #
def test_module_result_uses_files_written_key():
    res = contracts.ModuleResult(module_id="m", step_id="s", files_written=[".gitignore"])
    d = res.to_dict()
    assert "files_written" in d and "files" not in d
    assert contracts.RESULT_REQUIRED_KEYS <= set(d.keys())


# --- paths: no absolute leakage, plugin root resolves to the skill dir -------- #
def test_plugin_root_contains_runner_and_modules_layout():
    root = paths.plugin_root()
    assert root.name == "project-setup"
    assert (root / "runner").is_dir()
    assert paths.sdk_path().name == "sdk.py"
    assert paths.sdk_path().parent.name == "runner"


def test_cache_and_frozen_plan_live_outside_project(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
    # frozen plan must be under the cache, never under a project's .project-setup/
    fp = paths.frozen_plan_path()
    psd = paths.project_setup_dir(tmp_path / "proj")
    assert str(psd) not in str(fp)
    assert "cache" in str(fp)
