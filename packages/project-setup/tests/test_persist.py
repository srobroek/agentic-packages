"""Tests for persist.py — .project-setup/sources.toml + answers.toml writers.

Key assertions:
- sources.toml round-trip: meta.skill_version + [[source]] records
- answers.toml round-trip: per-module values + parallel per-key provenance
- Provenance assignment: flag/home/project values are written correctly
- merge_module_answers_to_persist: runtime answers_to_persist fold in
- drift warning: when committed skill_version != current → non-None warning
- ensure_gitignore_pytest_entry: adds entries when absent; idempotent

Run via: uv run --with pytest pytest -q packages/project-setup/tests/test_persist.py
"""

from __future__ import annotations

import importlib.util
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


contracts = _load("contracts")
persist = _load("persist")

write_sources_toml = persist.write_sources_toml
write_answers_toml = persist.write_answers_toml
merge_module_answers_to_persist = persist.merge_module_answers_to_persist
ensure_gitignore_pytest_entry = persist.ensure_gitignore_pytest_entry
check_sources_drift = persist.check_sources_drift
Provenance = contracts.Provenance


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def _make_outcome(module_id, step_id="run", ok=True, answers_to_persist=None):
    """Build a minimal StepOutcome-like object for merge tests."""
    return SimpleNamespace(
        ok=ok,
        module_id=module_id,
        step_id=step_id,
        result={
            "answers_to_persist": answers_to_persist or {},
        } if ok else None,
    )


# --------------------------------------------------------------------------- #
# sources.toml                                                                 #
# --------------------------------------------------------------------------- #
def test_write_sources_toml_writes_meta_skill_version(tmp_path):
    (tmp_path / ".project-setup").mkdir()
    path = write_sources_toml(tmp_path, sources=[], skill_version="0.3.0")
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    assert data["meta"]["skill_version"] == "0.3.0"


def test_write_sources_toml_no_meta_when_no_version(tmp_path):
    (tmp_path / ".project-setup").mkdir()
    path = write_sources_toml(tmp_path, sources=[], skill_version="")
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    assert "meta" not in data


def test_write_sources_toml_writes_source_records(tmp_path):
    (tmp_path / ".project-setup").mkdir()
    sources = [
        {"locator": "github.com/me/mods", "ref": "main", "subdir": "modules"},
        {"locator": "github.com/other/tools", "ref": "v1.0"},
    ]
    path = write_sources_toml(tmp_path, sources=sources, skill_version="0.1.0")
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    assert len(data["source"]) == 2
    assert data["source"][0]["locator"] == "github.com/me/mods"
    assert data["source"][0]["ref"] == "main"
    assert data["source"][0]["subdir"] == "modules"
    assert data["source"][1]["locator"] == "github.com/other/tools"


def test_write_sources_toml_creates_parent_dir(tmp_path):
    # .project-setup/ does NOT exist yet
    path = write_sources_toml(tmp_path, sources=[], skill_version="1.0.0")
    assert path.exists()


def test_write_sources_toml_empty_sources(tmp_path):
    path = write_sources_toml(tmp_path, sources=[], skill_version="0.1.0")
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    assert "source" not in data


def test_write_sources_toml_omits_empty_ref_and_subdir(tmp_path):
    sources = [{"locator": "github.com/x/y"}]
    path = write_sources_toml(tmp_path, sources=sources)
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    assert data["source"][0]["locator"] == "github.com/x/y"
    # ref and subdir are optional; should not appear
    assert "ref" not in data["source"][0]
    assert "subdir" not in data["source"][0]


# --------------------------------------------------------------------------- #
# answers.toml                                                                 #
# --------------------------------------------------------------------------- #
def test_write_answers_toml_writes_module_values(tmp_path):
    answers = {
        "core-identity": {"name": "acme-api", "org": "acme"},
    }
    prov = {
        "core-identity": {"name": "flag", "org": "home"},
    }
    path = write_answers_toml(tmp_path, answers=answers, provenance_map=prov)
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    assert data["module"]["core-identity"]["name"] == "acme-api"
    assert data["module"]["core-identity"]["org"] == "acme"


def test_write_answers_toml_writes_parallel_provenance(tmp_path):
    answers = {"core-identity": {"name": "acme-api"}}
    prov = {"core-identity": {"name": "flag"}}
    path = write_answers_toml(tmp_path, answers=answers, provenance_map=prov)
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    assert data["module"]["core-identity"]["source"]["name"] == "flag"


def test_write_answers_toml_round_trip_list_value(tmp_path):
    answers = {"gitignore-generate": {"templates": ["macos", "linux", "python"]}}
    prov = {"gitignore-generate": {"templates": "derived"}}
    path = write_answers_toml(tmp_path, answers=answers, provenance_map=prov)
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    assert data["module"]["gitignore-generate"]["templates"] == ["macos", "linux", "python"]
    assert data["module"]["gitignore-generate"]["source"]["templates"] == "derived"


def test_write_answers_toml_persists_all_provenance_values(tmp_path):
    """flag, home, project provenance values are all written correctly."""
    answers = {
        "core-identity": {
            "name": "myproject",
            "org": "myorg",
            "license": "mit",
        }
    }
    prov = {
        "core-identity": {
            "name": "flag",
            "org": "home",
            "license": "project",
        }
    }
    path = write_answers_toml(tmp_path, answers=answers, provenance_map=prov)
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    src = data["module"]["core-identity"]["source"]
    assert src["name"] == "flag"
    assert src["org"] == "home"
    assert src["license"] == "project"


def test_write_answers_toml_multiple_modules(tmp_path):
    answers = {
        "core-identity": {"name": "proj"},
        "gitignore-generate": {"templates": ["macos"]},
    }
    prov = {
        "core-identity": {"name": "flag"},
        "gitignore-generate": {"templates": "derived"},
    }
    path = write_answers_toml(tmp_path, answers=answers, provenance_map=prov)
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    assert "core-identity" in data["module"]
    assert "gitignore-generate" in data["module"]


def test_write_answers_toml_empty_answers(tmp_path):
    path = write_answers_toml(tmp_path, answers={}, provenance_map={})
    assert path.exists()


# --------------------------------------------------------------------------- #
# merge_module_answers_to_persist                                              #
# --------------------------------------------------------------------------- #
def test_merge_folds_runtime_answers_to_persist(tmp_path):
    answers = {"core-identity": {"name": "old"}}
    prov = {"core-identity": {"name": "flag"}}

    outcome = _make_outcome(
        "core-identity",
        answers_to_persist={"name": {"value": "new-from-module", "source": "derived"}},
    )
    merged_answers, merged_prov = merge_module_answers_to_persist(answers, prov, [outcome])

    assert merged_answers["core-identity"]["name"] == "new-from-module"
    assert merged_prov["core-identity"]["name"] == "derived"


def test_merge_adds_new_key_from_module(tmp_path):
    answers = {"gitignore-generate": {}}
    prov = {"gitignore-generate": {}}

    outcome = _make_outcome(
        "gitignore-generate",
        answers_to_persist={"dynamic_fetch": {"value": True, "source": "derived"}},
    )
    merged_answers, merged_prov = merge_module_answers_to_persist(answers, prov, [outcome])

    assert merged_answers["gitignore-generate"]["dynamic_fetch"] is True
    assert merged_prov["gitignore-generate"]["dynamic_fetch"] == "derived"


def test_merge_skips_failed_outcomes(tmp_path):
    answers = {"mod": {"key": "original"}}
    prov = {"mod": {"key": "flag"}}

    failed = _make_outcome("mod", ok=False)
    merged_answers, _ = merge_module_answers_to_persist(answers, prov, [failed])

    assert merged_answers["mod"]["key"] == "original"


def test_merge_handles_empty_outcomes(tmp_path):
    answers = {"mod": {"key": "value"}}
    prov = {"mod": {"key": "flag"}}
    merged_answers, merged_prov = merge_module_answers_to_persist(answers, prov, [])
    assert merged_answers == answers
    assert merged_prov == prov


def test_merge_creates_module_entry_if_absent(tmp_path):
    """If a module wasn't in pre-flight answers, merge creates its entry."""
    answers: dict = {}
    prov: dict = {}
    outcome = _make_outcome(
        "new-mod",
        answers_to_persist={"computed": {"value": "x", "source": "derived"}},
    )
    merged_answers, merged_prov = merge_module_answers_to_persist(answers, prov, [outcome])
    assert merged_answers["new-mod"]["computed"] == "x"


# --------------------------------------------------------------------------- #
# drift warning                                                                #
# --------------------------------------------------------------------------- #
def test_check_sources_drift_warns_on_version_mismatch(tmp_path):
    psd = tmp_path / ".project-setup"
    psd.mkdir()
    (psd / "sources.toml").write_text("[meta]\nskill_version = '0.1.0'\n")
    warning = check_sources_drift(tmp_path, current_skill_version="0.3.0")
    assert warning is not None
    assert "0.1.0" in warning
    assert "0.3.0" in warning


def test_check_sources_drift_no_warning_when_versions_match(tmp_path):
    psd = tmp_path / ".project-setup"
    psd.mkdir()
    (psd / "sources.toml").write_text("[meta]\nskill_version = '0.3.0'\n")
    warning = check_sources_drift(tmp_path, current_skill_version="0.3.0")
    assert warning is None


def test_check_sources_drift_no_warning_when_no_sources_toml(tmp_path):
    warning = check_sources_drift(tmp_path, current_skill_version="0.3.0")
    assert warning is None


def test_check_sources_drift_no_warning_when_no_current_version(tmp_path):
    psd = tmp_path / ".project-setup"
    psd.mkdir()
    (psd / "sources.toml").write_text("[meta]\nskill_version = '0.1.0'\n")
    warning = check_sources_drift(tmp_path, current_skill_version=None)
    assert warning is None


# --------------------------------------------------------------------------- #
# ensure_gitignore_pytest_entry                                                #
# --------------------------------------------------------------------------- #
def test_ensure_gitignore_adds_missing_entries(tmp_path):
    (tmp_path / ".gitignore").write_text("*.pyc\n")
    modified = ensure_gitignore_pytest_entry(tmp_path)
    assert modified is True
    content = (tmp_path / ".gitignore").read_text()
    assert ".pytest_cache/" in content
    assert "__pycache__/" in content


def test_ensure_gitignore_is_idempotent(tmp_path):
    (tmp_path / ".gitignore").write_text(".pytest_cache/\n__pycache__/\n")
    modified = ensure_gitignore_pytest_entry(tmp_path)
    assert modified is False


def test_ensure_gitignore_no_op_when_no_gitignore(tmp_path):
    modified = ensure_gitignore_pytest_entry(tmp_path)
    assert modified is False


def test_ensure_gitignore_adds_only_missing_entry(tmp_path):
    (tmp_path / ".gitignore").write_text(".pytest_cache/\n")
    ensure_gitignore_pytest_entry(tmp_path)
    content = (tmp_path / ".gitignore").read_text()
    # .pytest_cache already there; __pycache__ added
    assert "__pycache__/" in content
    # Only one .pytest_cache/ entry
    assert content.count(".pytest_cache/") == 1
