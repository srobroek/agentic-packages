"""Regression tests for the installed Claude hook sanitizer."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


SCRIPT = Path(__file__).with_name("sanitize-claude-hooks.py")
SPEC = importlib.util.spec_from_file_location("sanitize_claude_hooks", SCRIPT)
assert SPEC and SPEC.loader
sanitize_claude_hooks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sanitize_claude_hooks)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _make_script(hooks_dir: Path, package: str, name: str) -> Path:
    script = hooks_dir / package / "scripts" / name
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    return script


def test_clean_events_drops_only_dead_path_handlers(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    live = _make_script(hooks_dir, "live-pkg", "real.sh")
    obsolete = _make_script(
        hooks_dir,
        "agent-coder",
        "coder-delegation-reminder.sh",
    )
    future_agent_coder_hook = _make_script(
        hooks_dir,
        "agent-coder",
        "future-legitimate-hook.sh",
    )
    events = {
        "PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": str(live)}]},
            {
                "matcher": "Edit",
                "hooks": [{"type": "command", "command": str(obsolete)}],
            },
            {
                "matcher": "Stop",
                "hooks": [{"type": "command", "command": str(future_agent_coder_hook)}],
            },
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"{hooks_dir}/dead-pkg/scripts/gone.sh",
                    }
                ],
            },
            # Inline commands and non-command handlers are never flagged.
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo hi"}]},
            {"matcher": "Bash", "hooks": [{"type": "prompt", "prompt": "x"}]},
        ],
        "Stop": [{"hooks": [{"type": "command", "command": f"{hooks_dir}/gone/x.sh"}]}],
    }

    removed = sanitize_claude_hooks.clean_events(events)

    assert removed == 3
    assert "Stop" not in events  # emptied event is deleted
    commands = [
        handler["command"]
        for group in events["PreToolUse"]
        for handler in group["hooks"]
        if "command" in handler
    ]
    assert str(live) in commands
    assert "echo hi" in commands
    assert str(obsolete) not in commands
    assert str(future_agent_coder_hook) in commands
    assert not any("dead-pkg" in c for c in commands)


def test_tilde_commands_are_resolved(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    events = {
        "SessionStart": [
            {"hooks": [{"type": "command", "command": "~/hooks/missing-reminder"}]}
        ]
    }
    assert sanitize_claude_hooks.clean_events(events) == 1
    assert events == {}


def test_prune_stale_removes_unreferenced_hook_dirs(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    live = _make_script(hooks_dir, "live-pkg", "real.sh")
    _make_script(hooks_dir, "orphan-pkg", "old.sh")
    loose = hooks_dir / "loose-script.sh"
    loose.write_text("#!/bin/sh\n", encoding="utf-8")

    events = {
        "PreToolUse": [
            {"hooks": [{"type": "command", "command": str(live)}]},
            {"hooks": [{"type": "command", "command": str(loose)}]},
        ]
    }

    stale = sanitize_claude_hooks.prune_stale_entries([events], hooks_dir, check=True)
    assert [entry.name for entry in stale] == ["orphan-pkg"]

    sanitize_claude_hooks.prune_stale_entries([events], hooks_dir)
    assert sorted(p.name for p in hooks_dir.iterdir()) == [
        "live-pkg",
        "loose-script.sh",
    ]


def test_cli_end_to_end_settings_sidecar_and_symlink(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    live = _make_script(hooks_dir, "live-pkg", "real.sh")
    _make_script(hooks_dir, "orphan-pkg", "old.sh")
    dead = f"{hooks_dir}/dead-pkg/scripts/gone.sh"

    real_settings = tmp_path / "real" / "settings-target.json"
    _write_json(
        real_settings,
        {
            "model": "opus",
            "hooks": {
                "PreToolUse": [
                    {"hooks": [{"type": "command", "command": str(live)}]},
                    {"hooks": [{"type": "command", "command": dead}]},
                ]
            },
        },
    )
    settings = tmp_path / "settings.json"
    settings.symlink_to(real_settings)

    sidecar = tmp_path / "apm-hooks.json"
    _write_json(
        sidecar,
        {
            "PreToolUse": [
                {
                    "hooks": [{"type": "command", "command": dead}],
                    "_apm_source": "dead-pkg",
                }
            ]
        },
    )

    argv = [
        sys.executable,
        str(SCRIPT),
        "--settings",
        str(settings),
        "--sidecar",
        str(sidecar),
        "--hooks-dir",
        str(hooks_dir),
        "--prune-stale",
    ]

    check = subprocess.run(
        [*argv, "--check"], capture_output=True, text=True, check=False
    )
    assert check.returncode == 1  # stale wiring detected

    apply = subprocess.run(argv, capture_output=True, text=True, check=False)
    assert apply.returncode == 0

    assert settings.is_symlink()  # chezmoi symlink must survive the write
    cleaned = json.loads(real_settings.read_text(encoding="utf-8"))
    assert cleaned["model"] == "opus"  # non-hook keys untouched
    commands = [
        handler["command"]
        for groups in cleaned["hooks"].values()
        for group in groups
        for handler in group["hooks"]
    ]
    assert commands == [str(live)]
    assert json.loads(sidecar.read_text(encoding="utf-8")) == {}
    assert sorted(p.name for p in hooks_dir.iterdir()) == ["live-pkg"]

    rerun = subprocess.run(
        [*argv, "--check"], capture_output=True, text=True, check=False
    )
    assert rerun.returncode == 0  # idempotent: nothing left to clean


def test_cli_missing_files_is_a_noop(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--settings",
            str(tmp_path / "absent.json"),
            "--sidecar",
            str(tmp_path / "absent-sidecar.json"),
            "--hooks-dir",
            str(tmp_path / "hooks"),
            "--prune-stale",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
