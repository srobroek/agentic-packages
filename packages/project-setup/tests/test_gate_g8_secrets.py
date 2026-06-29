"""Spec 004 Phase 6 — G8 secret-detected abort (FR-018/019, SC-010).

- sdk.looks_like_secret matches known credential shapes only (no entropy heuristic).
- the interview boundary refuses a secret-shaped value: it is never persisted, the
  user is told to rotate; a required input then fails as MISSING_ANSWER downstream.
- an input declaring allow_secret=true opts out (the false-positive escape hatch).

Run via:
  uv run --with pytest pytest -q packages/project-setup/tests/test_gate_g8_secrets.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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


sdk = _load("sdk")
manifest = _load("manifest")
pipeline = _load("pipeline")


# --------------------------------------------------------------------------- #
# looks_like_secret — known shapes match; non-secrets do not                   #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("value,expect", [
    ("ghp_" + "a" * 30, "GitHub token"),
    ("ghs_" + "b" * 30, "GitHub token"),
    ("sk-" + "a" * 24, "OpenAI/Anthropic-style key"),
    ("AKIA" + "A" * 16, "AWS access key id"),
    ("glpat-" + "x" * 20, "GitLab PAT"),
    ("xoxb-" + "1" * 20, "Slack token"),
    ("-----BEGIN OPENSSH PRIVATE KEY-----", "PEM private key"),
])
def test_secret_shapes_detected(value, expect):
    assert sdk.looks_like_secret(value) == expect


@pytest.mark.parametrize("value", [
    "my-project", "3.13", "core@your-marketplace", "fastapi@0.115.0",
    "", "   ", "a-normal-description", "bun@1.1.38",
])
def test_non_secrets_pass(value):
    assert sdk.looks_like_secret(value) is None


def test_non_string_values_pass():
    assert sdk.looks_like_secret(True) is None
    assert sdk.looks_like_secret(42) is None
    assert sdk.looks_like_secret(None) is None


# --------------------------------------------------------------------------- #
# Interview boundary refuses the secret; allow_secret opts out                 #
# --------------------------------------------------------------------------- #
class _IO:
    """Scripted IO returning a fixed value for the one input, recording notifies."""

    def __init__(self, value):
        self._value = value
        self.log = []

    def ask(self, input_spec, default):
        return self._value

    def notify(self, msg):
        self.log.append(msg)


def _module_with_input(*, allow_secret: bool):
    InputSpec = manifest.InputSpec
    InputType = manifest.InputType

    class _M:
        inputs = [InputSpec(
            key="token", type=InputType.STRING, prompt="Token?",
            allow_secret=allow_secret,
        )]

    return _M()


def test_interview_refuses_secret_value_not_persisted():
    m = _module_with_input(allow_secret=False)
    io = _IO("ghp_" + "z" * 30)
    collected = pipeline._interview_module(m, {}, io, non_interactive=False)
    # the secret-shaped value was dropped — never collected
    assert "token" not in collected
    # the user was told to rotate
    assert any("looks like a secret" in msg for msg in io.log), io.log
    assert any("rotate" in msg.lower() for msg in io.log)


def test_interview_allows_secret_when_opted_out():
    m = _module_with_input(allow_secret=True)
    io = _IO("ghp_" + "z" * 30)
    collected = pipeline._interview_module(m, {}, io, non_interactive=False)
    # allow_secret=true → the value passes through
    assert collected.get("token") == "ghp_" + "z" * 30


def test_interview_non_secret_passes():
    m = _module_with_input(allow_secret=False)
    io = _IO("my-token-name")
    collected = pipeline._interview_module(m, {}, io, non_interactive=False)
    assert collected.get("token") == "my-token-name"


def test_allow_secret_parsed_from_manifest(tmp_path):
    toml = tmp_path / "module.toml"
    toml.write_text(
        '[meta]\nrepository = "github.com/t/t"\nauthor = "T"\n'
        '[module]\nid = "m"\nname = "M"\nversion = "1.0.0"\ndescription = "d"\nreconcile = false\n'
        '[[inputs]]\nkey = "tok"\ntype = "string"\nprompt = "Token?"\nallow_secret = true\n',
        encoding="utf-8",
    )
    m = manifest.parse_manifest(toml)
    assert not m.errors, [e.to_dict() for e in m.errors]
    assert m.inputs[0].allow_secret is True
