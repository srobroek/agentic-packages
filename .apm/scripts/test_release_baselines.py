from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).with_name("check-release-baselines.py")
SPEC = importlib.util.spec_from_file_location("check_release_baselines", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_accepts_matching_latest_tag(monkeypatch, tmp_path):
    monkeypatch.setattr(MODULE, "_current_branch", lambda: "fix/example")
    monkeypatch.setattr(
        MODULE,
        "_component_versions",
        lambda component: {"1.2.2": (1, 2, 2), "1.2.3": (1, 2, 3)},
    )
    monkeypatch.setattr(
        MODULE,
        "CONFIG",
        _write_json(tmp_path, "config.json", {"packages": {".": {"component": "pkg"}}}),
    )
    monkeypatch.setattr(MODULE, "MANIFEST", _write_json(tmp_path, "manifest.json", {".": "1.2.3"}))

    assert MODULE.check_release_baselines() == []


def test_rejects_missing_and_downgraded_tags(monkeypatch, tmp_path):
    monkeypatch.setattr(MODULE, "_current_branch", lambda: "fix/example")
    monkeypatch.setattr(
        MODULE,
        "_component_versions",
        lambda component: {"1.2.2": (1, 2, 2), "1.2.3": (1, 2, 3)},
    )
    monkeypatch.setattr(
        MODULE,
        "CONFIG",
        _write_json(
            tmp_path,
            "config.json",
            {
                "packages": {
                    "missing": {"component": "pkg"},
                    "downgraded": {"component": "pkg"},
                }
            },
        ),
    )
    monkeypatch.setattr(
        MODULE,
        "MANIFEST",
        _write_json(
            tmp_path,
            "manifest.json",
            {"missing": "1.2.4", "downgraded": "1.2.2"},
        ),
    )

    assert MODULE.check_release_baselines() == [
        "missing: baseline 1.2.4 has no tag pkg--v1.2.4",
        "downgraded: baseline 1.2.2 is behind latest tag pkg--v1.2.3",
    ]


def test_allows_first_release_sentinel_without_tags(monkeypatch, tmp_path):
    monkeypatch.setattr(MODULE, "_current_branch", lambda: "fix/example")
    monkeypatch.setattr(MODULE, "_component_versions", lambda component: {})
    monkeypatch.setattr(
        MODULE,
        "CONFIG",
        _write_json(tmp_path, "config.json", {"packages": {"new": {"component": "new"}}}),
    )
    monkeypatch.setattr(
        MODULE, "MANIFEST", _write_json(tmp_path, "manifest.json", {"new": "0.0.0"})
    )

    assert MODULE.check_release_baselines() == []


def test_rejects_first_release_sentinel_after_publication(monkeypatch, tmp_path):
    monkeypatch.setattr(MODULE, "_current_branch", lambda: "fix/example")
    monkeypatch.setattr(MODULE, "_component_versions", lambda component: {"1.0.0": (1, 0, 0)})
    monkeypatch.setattr(
        MODULE,
        "CONFIG",
        _write_json(tmp_path, "config.json", {"packages": {"pkg": {"component": "pkg"}}}),
    )
    monkeypatch.setattr(
        MODULE, "MANIFEST", _write_json(tmp_path, "manifest.json", {"pkg": "0.0.0"})
    )

    assert MODULE.check_release_baselines() == [
        "pkg: first-release sentinel has published tag pkg--v1.0.0"
    ]


def test_skips_release_please_branch(monkeypatch):
    monkeypatch.setattr(MODULE, "_current_branch", lambda: "release-please--branches--main")

    assert MODULE.check_release_baselines() == []


def _write_json(tmp_path: Path, name: str, value: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(value), encoding="utf-8")
    return path
