"""Tests for answers.py — deep-merge, defaults layering, coercion, provenance.

Import-by-path pattern from test_contracts.py.
Run via: uv run --with pytest pytest -q packages/project-setup/tests/test_answers.py
"""

from __future__ import annotations

import importlib.util
import sys
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
answers_mod = _load("answers")

resolve_final_answers = answers_mod.resolve_final_answers
Provenance = contracts.Provenance
ErrorCode = contracts.ErrorCode


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def make_input(key, type_str, default=None, required=False):
    return SimpleNamespace(
        key=key,
        type=SimpleNamespace(value=type_str),
        default=default,
        required=required,
        choices=None,
    )


def make_manifest(id: str, inputs=()):
    return SimpleNamespace(id=id, inputs=list(inputs))



# --------------------------------------------------------------------------- #
# Defaults layering                                                            #
# --------------------------------------------------------------------------- #
def test_manifest_default_lowest_precedence():
    """Manifest default is overridden by all other layers."""
    m = make_manifest("mod", inputs=[make_input("k", "string", default="manifest")])
    answers, prov, errors = resolve_final_answers(
        [m],
        home={"mod": {"k": "home"}},
        project_committed={},
        user_choices={},
    )
    assert answers["mod"]["k"] == "home"
    assert prov["mod"]["k"] == Provenance.HOME.value
    assert errors == []


def test_project_overrides_home():
    m = make_manifest("mod", inputs=[make_input("k", "string", default="manifest")])
    answers, prov, errors = resolve_final_answers(
        [m],
        home={"mod": {"k": "home"}},
        project_committed={"mod": {"k": "project"}},
        user_choices={},
    )
    assert answers["mod"]["k"] == "project"
    assert prov["mod"]["k"] == Provenance.PROJECT.value


def test_user_choice_highest_precedence():
    m = make_manifest("mod", inputs=[make_input("k", "string", default="manifest")])
    answers, prov, errors = resolve_final_answers(
        [m],
        home={"mod": {"k": "home"}},
        project_committed={"mod": {"k": "project"}},
        user_choices={"mod": {"k": "user"}},
    )
    assert answers["mod"]["k"] == "user"
    assert prov["mod"]["k"] == Provenance.FLAG.value


def test_manifest_default_used_when_no_override():
    m = make_manifest("mod", inputs=[make_input("k", "string", default="from-manifest")])
    answers, prov, errors = resolve_final_answers(
        [m], home={}, project_committed={}, user_choices={},
    )
    assert answers["mod"]["k"] == "from-manifest"
    assert prov["mod"]["k"] == Provenance.DEFAULT.value


def test_none_default_not_injected():
    """Inputs with default=None should not appear in the answer map."""
    m = make_manifest("mod", inputs=[make_input("k", "string", default=None)])
    answers, prov, errors = resolve_final_answers(
        [m], home={}, project_committed={}, user_choices={},
    )
    assert "k" not in answers.get("mod", {})


# --------------------------------------------------------------------------- #
# Coercion                                                                     #
# --------------------------------------------------------------------------- #
def test_coerce_int_from_string():
    m = make_manifest("mod", inputs=[make_input("n", "int")])
    answers, _, errors = resolve_final_answers(
        [m], home={}, project_committed={}, user_choices={"mod": {"n": "42"}},
    )
    assert answers["mod"]["n"] == 42
    assert errors == []


def test_coerce_bool_from_string_true():
    m = make_manifest("mod", inputs=[make_input("flag", "bool")])
    answers, _, errors = resolve_final_answers(
        [m], home={}, project_committed={}, user_choices={"mod": {"flag": "true"}},
    )
    assert answers["mod"]["flag"] is True
    assert errors == []


def test_coerce_bool_from_string_false():
    m = make_manifest("mod", inputs=[make_input("flag", "bool")])
    answers, _, errors = resolve_final_answers(
        [m], home={}, project_committed={}, user_choices={"mod": {"flag": "false"}},
    )
    assert answers["mod"]["flag"] is False
    assert errors == []


def test_coerce_list_from_scalar():
    m = make_manifest("mod", inputs=[make_input("items", "list")])
    answers, _, errors = resolve_final_answers(
        [m], home={}, project_committed={}, user_choices={"mod": {"items": "single"}},
    )
    assert answers["mod"]["items"] == ["single"]
    assert errors == []


def test_coerce_multichoice_from_list():
    m = make_manifest("mod", inputs=[make_input("picks", "multichoice")])
    answers, _, errors = resolve_final_answers(
        [m], home={}, project_committed={}, user_choices={"mod": {"picks": ["a", "b"]}},
    )
    assert answers["mod"]["picks"] == ["a", "b"]
    assert errors == []


def test_coerce_path_returns_string():
    m = make_manifest("mod", inputs=[make_input("p", "path")])
    answers, _, errors = resolve_final_answers(
        [m], home={}, project_committed={}, user_choices={"mod": {"p": "/some/path"}},
    )
    assert isinstance(answers["mod"]["p"], str)
    assert errors == []


def test_invalid_int_produces_error():
    m = make_manifest("mod", inputs=[make_input("n", "int")])
    answers, _, errors = resolve_final_answers(
        [m], home={}, project_committed={}, user_choices={"mod": {"n": "not-a-number"}},
    )
    assert any(e.error_code == ErrorCode.INPUT_VALUE_INVALID for e in errors)


def test_invalid_bool_produces_error():
    m = make_manifest("mod", inputs=[make_input("flag", "bool")])
    answers, _, errors = resolve_final_answers(
        [m], home={}, project_committed={}, user_choices={"mod": {"flag": "maybe"}},
    )
    assert any(e.error_code == ErrorCode.INPUT_VALUE_INVALID for e in errors)


# --------------------------------------------------------------------------- #
# Provenance attribution                                                       #
# --------------------------------------------------------------------------- #
def test_provenance_map_has_all_keys():
    m = make_manifest("mod", inputs=[
        make_input("a", "string", default="x"),
        make_input("b", "string"),
    ])
    answers, prov, errors = resolve_final_answers(
        [m],
        home={},
        project_committed={"mod": {"b": "y"}},
        user_choices={},
    )
    assert prov["mod"]["a"] == Provenance.DEFAULT.value
    assert prov["mod"]["b"] == Provenance.PROJECT.value


def test_no_provenance_for_unknown_key():
    """Keys not declared in inputs still get coercion-bypassed (type unknown)."""
    m = make_manifest("mod", inputs=[])
    answers, prov, errors = resolve_final_answers(
        [m], home={}, project_committed={}, user_choices={"mod": {"extra": "v"}},
    )
    # The key gets the user's value even without an input declaration
    assert answers["mod"].get("extra") == "v"


# --------------------------------------------------------------------------- #
# Multi-module                                                                 #
# --------------------------------------------------------------------------- #
def test_resolve_final_answers_multiple_modules():
    """Each module's answers are independent."""
    m1 = make_manifest("mod1", inputs=[make_input("k", "string", default="d1")])
    m2 = make_manifest("mod2", inputs=[make_input("k", "string", default="d2")])
    answers, prov, errors = resolve_final_answers(
        [m1, m2], home={}, project_committed={}, user_choices={},
    )
    assert answers["mod1"]["k"] == "d1"
    assert answers["mod2"]["k"] == "d2"
    assert errors == []
