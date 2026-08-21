"""Tests for chezmoi-sync.py.

Moved here with the script when it folded into hooks-chezmoi-guard: the PostToolUse
advisory and the PreToolUse guard answer the same question about the same paths, so
they belong to one package.
"""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(stem: str):
    """Import a hyphenated hook script as a module."""
    path = SCRIPTS / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    assert spec and spec.loader, path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def drive(module, payload, monkeypatch):
    """Run a hook's main() against a payload string."""
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    return module.main()


def test_chezmoi_sync_never_runs_a_write_command():
    """ADVISORY ONLY is the whole contract: no add, commit, stage, or push."""
    body = (SCRIPTS / "chezmoi-sync.py").read_text(encoding="utf-8")
    for banned in ('"add"', '"commit"', '"push"', '"re-add"', '"apply"'):
        assert banned not in body, f"chezmoi-sync must not invoke {banned}"


def test_chezmoi_sync_recognises_a_dot_directory_file():
    """The shell version tested `[[ "$relative" == .*//* ]]`, needing a literal
    double slash, so this branch never fired and ~/.ssh/config went unrecognised."""
    module = load("chezmoi-sync")
    assert module.is_config_path(Path(".ssh/config"))
    assert module.is_config_path(Path(".config/fish/config.fish"))
    assert module.is_config_path(Path(".zshrc"))
    assert not module.is_config_path(Path("Documents/notes.txt"))


def test_chezmoi_sync_ignores_known_noise():
    module = load("chezmoi-sync")
    home = Path("/home/u")
    assert module.is_ignored(home / ".cache/x", Path(".cache/x"), "")
    assert module.is_ignored(home / ".local/share/y", Path(".local/share/y"), "")
    assert module.is_ignored(home / ".config/a.swp", Path(".config/a.swp"), "")
    assert not module.is_ignored(home / ".config/fish/config.fish", Path(".config/fish/config.fish"), "")


def test_chezmoi_sync_skips_missing_file(monkeypatch, capsys):
    module = load("chezmoi-sync")
    payload = json.dumps({"tool_input": {"file_path": "/nonexistent/nope.conf"}})
    assert drive(module, payload, monkeypatch) == 0
    assert capsys.readouterr().out == ""


def test_chezmoi_sync_skips_project_dirs(tmp_path, monkeypatch, capsys):
    module = load("chezmoi-sync")
    project = tmp_path / "personal" / "dev" / "x.toml"
    project.parent.mkdir(parents=True)
    project.write_text("x = 1")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    called = []
    monkeypatch.setattr(module, "chezmoi", lambda *a: called.append(a) or "")
    payload = json.dumps({"tool_input": {"file_path": str(project)}})
    assert drive(module, payload, monkeypatch) == 0
    assert called == [], "project files must bail before chezmoi is consulted"
    assert capsys.readouterr().out == ""


def test_chezmoi_sync_recognises_config_names():
    module = load("chezmoi-sync")
    assert module.looks_like_config("settings.json")
    assert module.looks_like_config(".gitconfig")
    assert module.looks_like_config("foo.toml")
    assert module.looks_like_config(".zshrc")
    assert not module.looks_like_config("photo.png")


def test_chezmoi_sync_extracts_codex_patch_targets(tmp_path, monkeypatch, capsys):
    module = load("chezmoi-sync")
    home = tmp_path / "home"
    target = home / ".config" / "settings.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}")
    source = tmp_path / "source"
    source.mkdir()
    source_target = source / "dot_config" / "settings.json"
    source_target.parent.mkdir()
    source_target.write_text("{}")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(
        module,
        "chezmoi",
        lambda *args: (
            str(source)
            if args == ("source-path",)
            else str(source_target)
        ),
    )
    payload = json.dumps(
        {
            "tool_name": "apply_patch",
            "tool_input": {
                "patch": (
                    f"*** Update File: {target}\n"
                    f"*** Move to: {home / '.config' / 'renamed.json'}\n"
                    "@@\n-{}\n+{}\n"
                )
            },
        }
    )

    assert drive(module, payload, monkeypatch) == 0
    assert "chezmoi re-add" in capsys.readouterr().out
