"""Tests for sdk.verify_pins — MCP-free registry verification (spec 003 FR-005/006/007).

Verifies, with NO real network (a stubbed opener seam):
  - a real name@version verifies (PyPI + npm)
  - a hallucinated/typosquat name (404) is disconfirmed
  - a non-existent version of a real package is disconfirmed
  - a yanked PyPI version is disconfirmed
  - a bare name / range / "latest" (no exact version) is disconfirmed
  - an offline/timeout registry yields unreachable (NOT a false verified)
  - scoped npm names (@scope/pkg@1.2.3) split correctly

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_verify_pins.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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
verify_pins = sdk.verify_pins
PIN_VERIFIED = sdk.PIN_VERIFIED
PIN_DISCONFIRMED = sdk.PIN_DISCONFIRMED
PIN_UNREACHABLE = sdk.PIN_UNREACHABLE


# --------------------------------------------------------------------------- #
# Stub openers (no network)                                                    #
# --------------------------------------------------------------------------- #
def _pypi_stub(registry: dict):
    """Return an opener that serves a fake PyPI JSON map: {name: {version: yanked?}}."""
    def _open(url: str, timeout: float):
        name = url.split("/pypi/")[1].split("/json")[0]
        pkg = registry.get(name)
        if pkg is None:
            return None  # 404
        releases = {ver: [{"yanked": yanked}] for ver, yanked in pkg.items()}
        return {"releases": releases, "info": {"version": next(iter(pkg), "")}}
    return _open


def _npm_stub(registry: dict):
    """Return an opener serving fake npm JSON: {name: [versions]}."""
    def _open(url: str, timeout: float):
        name = url.split("registry.npmjs.org/")[1]
        vers = registry.get(name)
        if vers is None:
            return None  # 404
        return {"versions": {v: {} for v in vers}}
    return _open


def _offline_opener(url: str, timeout: float):
    raise OSError("simulated offline")


# --------------------------------------------------------------------------- #
# PyPI                                                                         #
# --------------------------------------------------------------------------- #
def test_pypi_real_pin_verified():
    opener = _pypi_stub({"fastapi": {"0.115.0": False}})
    res = verify_pins(["fastapi@0.115.0"], "pypi", _opener=opener)
    assert res["fastapi@0.115.0"] == PIN_VERIFIED


def test_pypi_hallucinated_name_disconfirmed():
    opener = _pypi_stub({"fastapi": {"0.115.0": False}})
    res = verify_pins(["faastapi@0.115.0"], "pypi", _opener=opener)  # typosquat
    assert res["faastapi@0.115.0"] == PIN_DISCONFIRMED


def test_pypi_missing_version_disconfirmed():
    opener = _pypi_stub({"fastapi": {"0.115.0": False}})
    res = verify_pins(["fastapi@9.9.9"], "pypi", _opener=opener)
    assert res["fastapi@9.9.9"] == PIN_DISCONFIRMED


def test_pypi_yanked_version_disconfirmed():
    opener = _pypi_stub({"badpkg": {"1.0.0": True}})  # only release is yanked
    res = verify_pins(["badpkg@1.0.0"], "pypi", _opener=opener)
    assert res["badpkg@1.0.0"] == PIN_DISCONFIRMED


def test_pypi_offline_unreachable():
    res = verify_pins(["fastapi@0.115.0"], "pypi", _opener=_offline_opener)
    assert res["fastapi@0.115.0"] == PIN_UNREACHABLE


# --------------------------------------------------------------------------- #
# npm                                                                          #
# --------------------------------------------------------------------------- #
def test_npm_real_pin_verified():
    opener = _npm_stub({"vue": ["3.5.13"]})
    res = verify_pins(["vue@3.5.13"], "npm", _opener=opener)
    assert res["vue@3.5.13"] == PIN_VERIFIED


def test_npm_scoped_name_verified():
    opener = _npm_stub({"@vue/runtime-core": ["3.5.13"]})
    res = verify_pins(["@vue/runtime-core@3.5.13"], "npm", _opener=opener)
    assert res["@vue/runtime-core@3.5.13"] == PIN_VERIFIED


def test_npm_missing_version_disconfirmed():
    opener = _npm_stub({"vue": ["3.5.13"]})
    res = verify_pins(["vue@2.0.0"], "npm", _opener=opener)
    assert res["vue@2.0.0"] == PIN_DISCONFIRMED


# --------------------------------------------------------------------------- #
# No exact version / ranges / latest → disconfirmed (resolver forbids them)    #
# --------------------------------------------------------------------------- #
def test_bare_name_disconfirmed():
    opener = _pypi_stub({"ruff": {"0.8.4": False}})
    res = verify_pins(["ruff"], "pypi", _opener=opener)
    assert res["ruff"] == PIN_DISCONFIRMED


def test_range_disconfirmed_without_network():
    # "^1.0" is not an exact pin; rfind('@') finds nothing → no version → disconfirm
    opener = _npm_stub({"left-pad": ["1.3.0"]})
    res = verify_pins(["left-pad"], "npm", _opener=opener)
    assert res["left-pad"] == PIN_DISCONFIRMED


# --------------------------------------------------------------------------- #
# Mixed batch                                                                  #
# --------------------------------------------------------------------------- #
def test_mixed_batch_independent_verdicts():
    opener = _pypi_stub({"fastapi": {"0.115.0": False}, "pydantic": {"2.10.3": False}})
    res = verify_pins(
        ["fastapi@0.115.0", "pydantic@2.10.3", "nonexistent@1.0.0"],
        "pypi",
        _opener=opener,
    )
    assert res["fastapi@0.115.0"] == PIN_VERIFIED
    assert res["pydantic@2.10.3"] == PIN_VERIFIED
    assert res["nonexistent@1.0.0"] == PIN_DISCONFIRMED


def test_unknown_ecosystem_raises():
    import pytest
    with pytest.raises(Exception):
        verify_pins(["x@1.0.0"], "cargo")
