"""Guardrail test: SC-006 — home config is NOT authoritative for existing projects.

Layering precedence (lowest → highest):
  module manifest default < home config < project committed answers < user choice

Rules under test:
  (a) With a home default present and NO committed project answer, resolve_final_answers
      proposes the home value and attributes provenance = "home".
  (b) With a committed project answer present, the committed value WINS over the
      home default; provenance = "project".
  (c) The home value cannot silently override an existing project's committed answer.

All tests exercise answers.resolve_final_answers() directly — no pipeline needed.
Import-by-path; hermetic (no network, no filesystem side-effects beyond in-memory
data structures).

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_home_not_authoritative.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"


# --------------------------------------------------------------------------- #
# Import-by-path bootstrap (mirrors test_contracts.py pattern)                #
# --------------------------------------------------------------------------- #

def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader, f"Cannot load runner module: {name}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


contracts = _load("contracts")
manifest_mod = _load("manifest")
answers_mod = _load("answers")

resolve_final_answers = answers_mod.resolve_final_answers
Provenance = contracts.Provenance
InputType = manifest_mod.InputType
InputSpec = manifest_mod.InputSpec
ModuleManifest = manifest_mod.ModuleManifest


# --------------------------------------------------------------------------- #
# Minimal manifest fixture builder                                             #
# --------------------------------------------------------------------------- #

def _make_manifest(
    module_id: str,
    inputs: list[InputSpec],
) -> ModuleManifest:
    """Build a minimal ModuleManifest with the given inputs."""
    return ModuleManifest(
        meta={"repository": "github.com/test/repo", "author": "test"},
        module={
            "id": module_id,
            "name": "Test",
            "version": "1.0.0",
            "description": "test",
            "reconcile": False,
        },
        order={"requires": [], "after": [], "before": []},
        tools={"required": []},
        inputs=inputs,
        steps=[],
        errors=[],
    )


def _string_input(key: str, default: Any = None) -> InputSpec:
    return InputSpec(key=key, type=InputType.STRING, prompt=key, default=default)


def _bool_input(key: str, default: Any = None) -> InputSpec:
    return InputSpec(key=key, type=InputType.BOOL, prompt=key, default=default)


# --------------------------------------------------------------------------- #
# (a) Home default seeds a new project's interview                             #
# --------------------------------------------------------------------------- #

def test_home_default_seeds_new_project_when_no_committed_answer():
    """With home config present and no committed project answer, the home value
    is used and attributed with provenance 'home'."""
    mod_id = "core-identity"
    manifests = [_make_manifest(mod_id, [_string_input("org")])]

    home = {mod_id: {"org": "my-home-org"}}
    project_committed: dict = {}
    user_choices: dict = {}

    final, provenance, errors = resolve_final_answers(
        manifests, home, project_committed, user_choices
    )

    assert errors == []
    assert final[mod_id]["org"] == "my-home-org", (
        "Expected home value 'my-home-org' when no committed answer exists"
    )
    assert provenance[mod_id]["org"] == Provenance.HOME.value, (
        f"Expected provenance 'home', got {provenance[mod_id]['org']!r}"
    )


def test_home_default_proposes_value_for_multiple_inputs():
    """Home config seeds all declared inputs that are present in it."""
    mod_id = "core-identity"
    manifests = [_make_manifest(mod_id, [
        _string_input("org"),
        _string_input("author_name"),
    ])]

    home = {mod_id: {"org": "acme", "author_name": "alice"}}
    project_committed: dict = {}
    user_choices: dict = {}

    final, provenance, errors = resolve_final_answers(
        manifests, home, project_committed, user_choices
    )

    assert errors == []
    assert final[mod_id]["org"] == "acme"
    assert final[mod_id]["author_name"] == "alice"
    assert provenance[mod_id]["org"] == Provenance.HOME.value
    assert provenance[mod_id]["author_name"] == Provenance.HOME.value


# --------------------------------------------------------------------------- #
# (b) Committed project answer wins over home default                          #
# --------------------------------------------------------------------------- #

def test_committed_project_answer_wins_over_home_default():
    """When a committed project answer exists, it MUST override the home default.
    This is the core SC-006 invariant: home is NOT authoritative for existing projects."""
    mod_id = "core-identity"
    manifests = [_make_manifest(mod_id, [_string_input("org")])]

    home = {mod_id: {"org": "home-org"}}
    project_committed = {mod_id: {"org": "committed-org"}}
    user_choices: dict = {}

    final, provenance, errors = resolve_final_answers(
        manifests, home, project_committed, user_choices
    )

    assert errors == []
    assert final[mod_id]["org"] == "committed-org", (
        f"Committed project answer must win over home default. "
        f"Got {final[mod_id]['org']!r}, expected 'committed-org'"
    )
    assert provenance[mod_id]["org"] == Provenance.PROJECT.value, (
        f"Expected provenance 'project', got {provenance[mod_id]['org']!r}"
    )


def test_home_cannot_silently_change_existing_project_answer():
    """Changing a home config value MUST NOT silently change a committed answer.

    This simulates a developer who changes their ~/.config/project-setup/config.toml
    after having already committed answers to an existing project. The committed
    value must be unaffected.
    """
    mod_id = "core-identity"
    manifests = [_make_manifest(mod_id, [_string_input("org")])]

    # Simulate: developer's home config changed to a new org
    home_changed = {mod_id: {"org": "new-home-org"}}
    # But the project already has a committed answer from first run
    project_committed = {mod_id: {"org": "original-committed-org"}}
    user_choices: dict = {}

    final, provenance, errors = resolve_final_answers(
        manifests, home_changed, project_committed, user_choices
    )

    assert errors == []
    assert final[mod_id]["org"] == "original-committed-org", (
        "Home config change must not silently override a committed project answer"
    )
    assert provenance[mod_id]["org"] == Provenance.PROJECT.value


def test_committed_answer_wins_over_home_for_bool_type():
    """Bool inputs follow the same layering: project > home."""
    mod_id = "git-init"
    manifests = [_make_manifest(mod_id, [_bool_input("init_git", default=True)])]

    home = {mod_id: {"init_git": True}}
    project_committed = {mod_id: {"init_git": False}}
    user_choices: dict = {}

    final, provenance, errors = resolve_final_answers(
        manifests, home, project_committed, user_choices
    )

    assert errors == []
    assert final[mod_id]["init_git"] is False, (
        "Committed False must win over home True"
    )
    assert provenance[mod_id]["init_git"] == Provenance.PROJECT.value


# --------------------------------------------------------------------------- #
# (c) Full layering chain: manifest default < home < project < user choice     #
# --------------------------------------------------------------------------- #

def test_manifest_default_is_lowest_precedence():
    """When only the manifest default is present (no home, project, or user),
    the default value is used with provenance 'default'."""
    mod_id = "core-identity"
    manifests = [_make_manifest(mod_id, [_string_input("layout", default="single")])]

    final, provenance, errors = resolve_final_answers(
        manifests,
        home={},
        project_committed={},
        user_choices={},
    )

    assert errors == []
    assert final[mod_id]["layout"] == "single"
    assert provenance[mod_id]["layout"] == Provenance.DEFAULT.value


def test_home_overrides_manifest_default():
    """Home config overrides the manifest-declared default."""
    mod_id = "core-identity"
    manifests = [_make_manifest(mod_id, [_string_input("layout", default="single")])]

    home = {mod_id: {"layout": "monorepo"}}

    final, provenance, errors = resolve_final_answers(
        manifests, home, project_committed={}, user_choices={}
    )

    assert errors == []
    assert final[mod_id]["layout"] == "monorepo"
    assert provenance[mod_id]["layout"] == Provenance.HOME.value


def test_user_choice_is_highest_precedence():
    """User choice (CLI flag / interview answer) beats all layers including project."""
    mod_id = "core-identity"
    manifests = [_make_manifest(mod_id, [_string_input("org")])]

    home = {mod_id: {"org": "home-org"}}
    project_committed = {mod_id: {"org": "project-org"}}
    user_choices = {mod_id: {"org": "user-org"}}

    final, provenance, errors = resolve_final_answers(
        manifests, home, project_committed, user_choices
    )

    assert errors == []
    assert final[mod_id]["org"] == "user-org"
    # Provenance for user choice is FLAG (the CLI "flag" layer — highest priority)
    assert provenance[mod_id]["org"] == Provenance.FLAG.value


def test_full_layering_chain_each_layer_overrides_previous():
    """Explicit four-layer test: default < home < project < user, each overriding."""
    mod_id = "test-mod"

    # 4 inputs, one per layer
    inputs = [
        _string_input("d_key", default="d_val"),   # only default
        _string_input("h_key"),                     # home overrides (no default)
        _string_input("p_key"),                     # project overrides
        _string_input("u_key"),                     # user overrides all
    ]
    manifests = [_make_manifest(mod_id, inputs)]

    home = {mod_id: {"h_key": "h_val", "p_key": "h_p", "u_key": "h_u"}}
    project_committed = {mod_id: {"p_key": "p_val", "u_key": "p_u"}}
    user_choices = {mod_id: {"u_key": "u_val"}}

    final, provenance, errors = resolve_final_answers(
        manifests, home, project_committed, user_choices
    )

    assert errors == []

    # Each layer wins at its level
    assert final[mod_id]["d_key"] == "d_val"
    assert provenance[mod_id]["d_key"] == Provenance.DEFAULT.value

    assert final[mod_id]["h_key"] == "h_val"
    assert provenance[mod_id]["h_key"] == Provenance.HOME.value

    assert final[mod_id]["p_key"] == "p_val"
    assert provenance[mod_id]["p_key"] == Provenance.PROJECT.value

    assert final[mod_id]["u_key"] == "u_val"
    assert provenance[mod_id]["u_key"] == Provenance.FLAG.value


def test_home_config_for_unrelated_module_does_not_bleed():
    """Home config for module B must not affect module A's answers."""
    mod_a = "module-a"
    mod_b = "module-b"
    manifests = [
        _make_manifest(mod_a, [_string_input("color")]),
        _make_manifest(mod_b, [_string_input("color")]),
    ]

    home = {mod_b: {"color": "blue"}}  # only set for B
    project_committed: dict = {}
    user_choices: dict = {}

    final, provenance, errors = resolve_final_answers(
        manifests, home, project_committed, user_choices
    )

    assert errors == []
    # Module A should not have a value (no default, no home, no project, no user)
    assert final[mod_a].get("color") is None, (
        "Home config for module-b must not bleed into module-a"
    )
    # Module B gets the home value
    assert final[mod_b]["color"] == "blue"
    assert provenance[mod_b]["color"] == Provenance.HOME.value
