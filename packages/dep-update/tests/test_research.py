#!/usr/bin/env python3
"""Tests for dep-update's research.py classification and registry handling.

tests/dep-update.bats drives research.py end to end against fixture registries
and remains the integration oracle. This module covers the version ordering and
failure statuses directly, where a table is cheaper than a fixture per case.
"""

from __future__ import annotations

import importlib.util
import json
import urllib.error
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / ".apm/skills/dep-update/scripts/research.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("research_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


research = _load()


def test_script_is_committed_executable():
    assert SCRIPT.stat().st_mode & 0o111


# --- version handling -------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.2.3", (1, 2, 3)),
        ("v1.2.3", (1, 2, 3)),
        ("1.2", (1, 2, 0)),
        ("1", (1, 0, 0)),
        ("2.0.0rc1", (2, 0, 0)),
        ("not-a-version", None),
        ("", None),
    ],
)
def test_normalize_version(raw, expected):
    assert research.normalize_version(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.2.3", False),
        ("2.0.0rc1", True),
        ("2.0.0b2", True),
        ("1.0.0.dev3", True),
        ("2.0.0.post1", True),
        ("1.0.0-alpha.1", True),
    ],
)
def test_is_prerelease(raw, expected):
    assert research.is_prerelease(raw) is expected


@pytest.mark.parametrize(
    ("installed", "latest", "expected"),
    [
        ("1.2.3", "1.2.4", "PATCH-SAFE"),
        ("1.2.3", "1.3.0", "MINOR-CHECK"),
        ("1.2.3", "2.0.0", "MAJOR-ADVISORY"),
        ("1.2.3", "1.2.3", "CURRENT"),
        ("1.2.4", "1.2.3", "CURRENT"),
        ("not-a-version", "1.2.3", "MINOR-CHECK"),
        ("1.2.3", "not-a-version", "MINOR-CHECK"),
    ],
)
def test_classify(installed, latest, expected):
    assert research.classify(installed, latest) == expected


def test_pick_stable_skips_a_prerelease_latest():
    versions = ["1.0.0", "1.1.0", "2.0.0rc1"]
    assert research.pick_stable("2.0.0rc1", "1.0.0", versions) == "1.1.0"


def test_pick_stable_keeps_a_prerelease_when_installed_is_one():
    versions = ["1.0.0", "2.0.0rc1"]
    assert research.pick_stable("2.0.0rc1", "1.9.0b1", versions) == "2.0.0rc1"


def test_pick_stable_keeps_the_prerelease_when_no_stable_exists():
    assert research.pick_stable("1.0.0rc1", "0.9.0", ["1.0.0rc1"]) == "1.0.0rc1"


# --- registry records -------------------------------------------------------


def write_fixture(fixture_dir: Path, ecosystem: str, name: str, body: dict) -> None:
    safe = name.replace("/", "__").replace("@", "__at__")
    (fixture_dir / f"{ecosystem}_{safe}.json").write_text(json.dumps(body))


@pytest.fixture()
def fixtures(tmp_path, monkeypatch):
    monkeypatch.setenv("DEP_UPDATE_FIXTURE_DIR", str(tmp_path))
    return tmp_path


def test_pypi_record_is_classified(fixtures):
    write_fixture(
        fixtures,
        "pypi",
        "requests",
        {"info": {"version": "2.32.3"}, "releases": {"2.32.3": [{"yanked": False}]}},
    )
    record = research.query_registry("pypi", "requests", "2.32.0")
    assert record["status"] == "OK"
    assert record["latest"] == "2.32.3"
    assert record["class"] == "PATCH-SAFE"


def test_pypi_all_files_yanked_is_disconfirmed(fixtures):
    write_fixture(
        fixtures,
        "pypi",
        "requests",
        {"info": {"version": "2.32.3"}, "releases": {"2.32.3": [{"yanked": True}]}},
    )
    record = research.query_registry("pypi", "requests", "2.31.0")
    assert record["status"] == "DISCONFIRMED"
    assert "yanked" in record["reason"]


def test_npm_record_is_classified(fixtures):
    write_fixture(
        fixtures,
        "npm",
        "express",
        {"dist-tags": {"latest": "5.0.0"}, "versions": {"4.18.3": {}, "5.0.0": {}}},
    )
    record = research.query_registry("npm", "express", "4.18.3")
    assert record["status"] == "OK"
    assert record["class"] == "MAJOR-ADVISORY"


def test_npm_without_a_latest_dist_tag_is_unresolvable(fixtures):
    write_fixture(fixtures, "npm", "express", {"dist-tags": {}, "versions": {}})
    record = research.query_registry("npm", "express", "4.18.3")
    assert record["status"] == "UNRESOLVABLE"
    assert record["reason"] == "no dist-tags.latest"


def test_scoped_npm_name_maps_to_its_fixture(fixtures):
    write_fixture(
        fixtures,
        "npm",
        "@scope/pkg",
        {"dist-tags": {"latest": "1.0.1"}, "versions": {"1.0.1": {}}},
    )
    record = research.query_registry("npm", "@scope/pkg", "1.0.0")
    assert record["status"] == "OK"


def test_missing_fixture_simulates_offline(fixtures):
    record = research.query_registry("pypi", "absent", "1.0.0")
    assert record["status"] == "UNRESOLVABLE"
    assert "network error" in record["reason"]


@pytest.mark.parametrize("ecosystem", ["cargo", "go", "rubygems", "packagist"])
def test_unsupported_ecosystems_are_advisory_only(fixtures, ecosystem):
    record = research.query_registry(ecosystem, "x", "1.0.0")
    assert record["status"] == "UNRESOLVABLE"
    assert "advisory-only" in record["reason"]


def test_http_error_maps_to_a_reason(fixtures, monkeypatch):
    def boom(*_args, **_kwargs):
        raise urllib.error.HTTPError("u", 403, "Forbidden", {}, None)

    monkeypatch.setattr(research, "fetch_json", boom)
    record = research.query_registry("pypi", "private", "1.0.0")
    assert record["status"] == "UNRESOLVABLE"
    assert record["reason"] == "auth-required"


def test_unexpected_exception_fails_open_with_the_reason(fixtures, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(research, "fetch_json", boom)
    record = research.query_registry("pypi", "x", "1.0.0")
    assert record["status"] == "UNRESOLVABLE"
    assert record["reason"] == "kaboom"


# --- driver -----------------------------------------------------------------


def test_missing_target_directory_exits_two(tmp_path):
    assert research.main(["research.py", str(tmp_path / "nope")]) == 2


def test_stdin_mode_emits_one_record_per_dependency(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("DEP_UPDATE_FIXTURE_DIR", str(tmp_path))
    monkeypatch.setenv("RESEARCH_USE_STDIN", "1")
    write_fixture(
        tmp_path,
        "pypi",
        "requests",
        {"info": {"version": "2.32.3"}, "releases": {"2.32.3": [{"yanked": False}]}},
    )
    monkeypatch.setattr(
        "sys.stdin",
        type("S", (), {"read": staticmethod(lambda: "pypi\trequests\t2.32.0\n\n")})(),
    )
    assert research.main(["research.py", str(tmp_path)]) == 0
    lines = [l for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["name"] == "requests"


def test_blank_and_short_lines_are_skipped(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DEP_UPDATE_FIXTURE_DIR", str(tmp_path))
    monkeypatch.setenv("RESEARCH_USE_STDIN", "1")
    monkeypatch.setattr(
        "sys.stdin",
        type("S", (), {"read": staticmethod(lambda: "\nonlyone\n\t\n")})(),
    )
    assert research.main(["research.py", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == ""
