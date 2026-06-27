"""Guardrail tests: FR-039 (input types) + FR-043 (no secret type).

(a) InputType enum is EXACTLY the 8 allowed members:
      {string, text, int, bool, choice, multichoice, path, list}
    and there is NO 'secret' member.

(b) A module.toml declaring type="secret" MUST fail manifest parsing with
    an error whose error_code is MANIFEST_MALFORMED (invalid input type).

(c) Manifests that declare any of the FORBIDDEN fields (priority, title,
    entrypoint, required_answers, produces) MUST fail with FORBIDDEN_FIELD.

Import-by-path; hermetic (no network, fixtures in tmp_path).

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_input_types_and_secrets.py
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"


# --------------------------------------------------------------------------- #
# Import-by-path bootstrap                                                     #
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

parse_manifest = manifest_mod.parse_manifest
InputType = manifest_mod.InputType
ErrorCode = contracts.ErrorCode


# --------------------------------------------------------------------------- #
# TOML fixture helpers                                                         #
# --------------------------------------------------------------------------- #

_MINIMAL_BASE = """\
[meta]
repository = "github.com/test/repo"
author = "test"

[module]
id = "test-module"
name = "Test"
version = "1.0.0"
description = "test"
reconcile = false
"""


def _write_toml(tmp_path: Path, content: str, filename: str = "module.toml") -> Path:
    p = tmp_path / filename
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


def _minimal_with_input(input_block: str) -> str:
    """Return a complete minimal module.toml with one [[inputs]] block appended."""
    return _MINIMAL_BASE + "\n" + textwrap.dedent(input_block)


# --------------------------------------------------------------------------- #
# (a) InputType enum membership                                                #
# --------------------------------------------------------------------------- #

_EXPECTED_INPUT_TYPES = frozenset({
    "string", "text", "int", "bool", "choice", "multichoice", "path", "list"
})

_ALLOWED_COUNT = 8


def test_input_type_enum_has_exactly_8_members():
    """InputType MUST have exactly 8 members (FR-039)."""
    actual = {m.value for m in InputType}
    assert len(actual) == _ALLOWED_COUNT, (
        f"Expected {_ALLOWED_COUNT} InputType members, got {len(actual)}: {sorted(actual)}"
    )


def test_input_type_enum_contains_all_allowed_types():
    """All 8 allowed type strings must be present as InputType members."""
    actual = {m.value for m in InputType}
    missing = _EXPECTED_INPUT_TYPES - actual
    assert not missing, f"InputType is missing expected members: {missing}"


def test_input_type_enum_contains_no_extra_types():
    """InputType must not contain any types beyond the 8 allowed."""
    actual = {m.value for m in InputType}
    extra = actual - _EXPECTED_INPUT_TYPES
    assert not extra, (
        f"InputType has unexpected extra members: {extra}. "
        "No type beyond the 8 allowed types (string|text|int|bool|choice|multichoice|path|list) "
        "is permitted."
    )


def test_input_type_enum_has_no_secret_member():
    """'secret' MUST NOT be a member of InputType (FR-043)."""
    values = {m.value for m in InputType}
    assert "secret" not in values, (
        "InputType must not contain 'secret' — secrets must never be accepted "
        "as input values (FR-043 / shared-contracts.md §1)"
    )


def test_input_type_string_is_accessible():
    """Smoke-check: each of the 8 types is accessible by value."""
    for type_str in _EXPECTED_INPUT_TYPES:
        # Should not raise
        t = InputType(type_str)
        assert t.value == type_str


# --------------------------------------------------------------------------- #
# (b) type="secret" in module.toml fails manifest parse with MANIFEST_MALFORMED
# --------------------------------------------------------------------------- #

def test_secret_input_type_fails_manifest_parse(tmp_path):
    """A module.toml with type='secret' MUST produce a MANIFEST_MALFORMED error."""
    toml = _minimal_with_input("""\
        [[inputs]]
        key = "api_token"
        type = "secret"
        prompt = "Enter your API token"
    """)
    p = _write_toml(tmp_path, toml)
    m = parse_manifest(p)

    codes = [e.error_code for e in m.errors]
    assert ErrorCode.MANIFEST_MALFORMED in codes, (
        f"Expected MANIFEST_MALFORMED for type='secret', got error codes: "
        f"{[c.value for c in codes]}"
    )


def test_secret_input_type_error_references_the_key(tmp_path):
    """The MANIFEST_MALFORMED error for type='secret' should identify the offending input."""
    toml = _minimal_with_input("""\
        [[inputs]]
        key = "my_secret"
        type = "secret"
        prompt = "Enter secret"
    """)
    p = _write_toml(tmp_path, toml)
    m = parse_manifest(p)

    malformed_errors = [e for e in m.errors if e.error_code == ErrorCode.MANIFEST_MALFORMED]
    assert malformed_errors, "Expected at least one MANIFEST_MALFORMED error"

    # At least one error message should reference 'secret' or the key name
    all_text = " ".join(
        f"{e.received} {e.expected} {e.how_to_fix}" for e in malformed_errors
    )
    assert "secret" in all_text or "my_secret" in all_text, (
        f"Expected error text to reference 'secret' or 'my_secret', got: {all_text!r}"
    )


def test_secret_input_type_no_input_spec_produced(tmp_path):
    """When type='secret' fails, no InputSpec should be added to the manifest inputs."""
    toml = _minimal_with_input("""\
        [[inputs]]
        key = "bad_secret"
        type = "secret"
        prompt = "Enter secret"
    """)
    p = _write_toml(tmp_path, toml)
    m = parse_manifest(p)

    # The invalid input should not appear in the parsed inputs list
    input_keys = [i.key for i in m.inputs]
    assert "bad_secret" not in input_keys, (
        "An input with type='secret' must not produce an InputSpec in the manifest"
    )


def test_valid_input_types_parse_without_error(tmp_path):
    """All 8 allowed input types parse cleanly (regression guard)."""
    # Types that don't require 'choices'
    simple_types = ["string", "text", "int", "bool", "path", "list"]
    for type_str in simple_types:
        toml = _minimal_with_input(f"""\
            [[inputs]]
            key = "test_key"
            type = "{type_str}"
            prompt = "Test prompt"
        """)
        subdir = tmp_path / type_str
        subdir.mkdir(exist_ok=True)
        p = subdir / "module.toml"
        p.write_text(textwrap.dedent(toml), encoding="utf-8")
        m = parse_manifest(p)
        input_errors = [
            e for e in m.errors
            if e.error_code == ErrorCode.MANIFEST_MALFORMED
            and "type" in e.received.lower()
        ]
        assert not input_errors, (
            f"type='{type_str}' should be valid but got: "
            f"{[e.received for e in input_errors]}"
        )

    # choice and multichoice require choices list
    for type_str in ["choice", "multichoice"]:
        toml = _minimal_with_input(f"""\
            [[inputs]]
            key = "test_key"
            type = "{type_str}"
            prompt = "Test prompt"
            choices = ["a", "b"]
            default = "a"
        """)
        subdir = tmp_path / type_str
        subdir.mkdir(exist_ok=True)
        p = subdir / "module.toml"
        p.write_text(textwrap.dedent(toml), encoding="utf-8")
        m = parse_manifest(p)
        input_errors = [
            e for e in m.errors
            if e.error_code == ErrorCode.MANIFEST_MALFORMED
            and "type" in e.received.lower()
        ]
        assert not input_errors, (
            f"type='{type_str}' should be valid but got: "
            f"{[e.received for e in input_errors]}"
        )


# --------------------------------------------------------------------------- #
# (c) Forbidden fields produce FORBIDDEN_FIELD errors                          #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("forbidden_field,field_value", [
    ("priority", "10"),
    ("title", '"My Module"'),
    ("entrypoint", '"module.py"'),
    ("required_answers", '["name"]'),
    ("produces", '["file.txt"]'),
])
def test_forbidden_top_level_field_produces_forbidden_field_error(
    tmp_path, forbidden_field, field_value
):
    """Top-level forbidden fields MUST produce FORBIDDEN_FIELD errors (FR-009)."""
    toml = _MINIMAL_BASE + f"\n{forbidden_field} = {field_value}\n"
    subdir = tmp_path / forbidden_field
    subdir.mkdir(exist_ok=True)
    p = subdir / "module.toml"
    p.write_text(toml, encoding="utf-8")

    m = parse_manifest(p)
    codes = [e.error_code for e in m.errors]
    assert ErrorCode.FORBIDDEN_FIELD in codes, (
        f"Expected FORBIDDEN_FIELD for top-level '{forbidden_field}', "
        f"got: {[c.value for c in codes]}"
    )


def test_forbidden_field_error_identifies_the_field(tmp_path):
    """FORBIDDEN_FIELD error MUST name the offending field in its received/how_to_fix text."""
    toml = _MINIMAL_BASE + '\npriority = "high"\n'
    p = _write_toml(tmp_path, toml)
    m = parse_manifest(p)

    forbidden_errors = [e for e in m.errors if e.error_code == ErrorCode.FORBIDDEN_FIELD]
    assert forbidden_errors, "Expected at least one FORBIDDEN_FIELD error"

    all_text = " ".join(
        f"{e.received} {e.how_to_fix}" for e in forbidden_errors
    )
    assert "priority" in all_text, (
        f"FORBIDDEN_FIELD error must mention 'priority', got: {all_text!r}"
    )


@pytest.mark.parametrize("forbidden_field,field_value", [
    ("priority", '"high"'),
    ("title", '"My Module"'),
    ("entrypoint", '"module.py"'),
])
def test_forbidden_module_level_field_produces_forbidden_field_error(
    tmp_path, forbidden_field, field_value
):
    """Forbidden fields inside [module] also produce FORBIDDEN_FIELD (e.g. [module].priority)."""
    # Inject the forbidden field into the [module] section
    toml = (
        "[meta]\n"
        'repository = "github.com/test/repo"\n'
        'author = "test"\n'
        "\n"
        "[module]\n"
        'id = "test-module"\n'
        'name = "Test"\n'
        'version = "1.0.0"\n'
        'description = "test"\n'
        "reconcile = false\n"
        f"{forbidden_field} = {field_value}\n"
    )
    subdir = tmp_path / f"mod_{forbidden_field}"
    subdir.mkdir(exist_ok=True)
    p = subdir / "module.toml"
    p.write_text(toml, encoding="utf-8")

    m = parse_manifest(p)
    codes = [e.error_code for e in m.errors]
    assert ErrorCode.FORBIDDEN_FIELD in codes, (
        f"Expected FORBIDDEN_FIELD for [module].{forbidden_field}, "
        f"got: {[c.value for c in codes]}"
    )


def test_unknown_top_level_field_produces_unknown_field_error(tmp_path):
    """An unrecognized top-level field MUST produce UNKNOWN_FIELD (not a silent ignore)."""
    toml = _MINIMAL_BASE + '\ncustom_thing = "value"\n'
    p = _write_toml(tmp_path, toml)
    m = parse_manifest(p)

    codes = [e.error_code for e in m.errors]
    assert ErrorCode.UNKNOWN_FIELD in codes, (
        f"Expected UNKNOWN_FIELD for unknown top-level key, got: {[c.value for c in codes]}"
    )


def test_multiple_forbidden_fields_all_reported(tmp_path):
    """All forbidden fields in a manifest must be reported, not just the first."""
    toml = (
        _MINIMAL_BASE
        + '\npriority = "high"\n'
        + 'title = "Bad Title"\n'
    )
    p = _write_toml(tmp_path, toml)
    m = parse_manifest(p)

    forbidden_errors = [e for e in m.errors if e.error_code == ErrorCode.FORBIDDEN_FIELD]
    assert len(forbidden_errors) >= 2, (
        f"Expected at least 2 FORBIDDEN_FIELD errors (priority + title), "
        f"got {len(forbidden_errors)}: {[e.received for e in forbidden_errors]}"
    )
