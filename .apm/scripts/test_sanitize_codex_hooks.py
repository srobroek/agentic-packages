"""Regression tests for the installed Codex hook sanitizer."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("sanitize-codex-hooks.py")
SPEC = importlib.util.spec_from_file_location("sanitize_codex_hooks", SCRIPT)
assert SPEC and SPEC.loader
sanitize_codex_hooks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sanitize_codex_hooks)


def test_sanitize_normalizes_released_codex_contract(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    keep_command = f"{hooks_dir}/hooks-bash-safety/scripts/guard.sh"
    keep_script = Path(keep_command)
    keep_script.parent.mkdir(parents=True)
    keep_script.write_text("#!/bin/sh\n", encoding="utf-8")
    future_command = f"{hooks_dir}/agent-builder/scripts/future-legitimate-hook.sh"
    future_script = Path(future_command)
    future_script.parent.mkdir(parents=True, exist_ok=True)
    future_script.write_text("#!/bin/sh\n", encoding="utf-8")
    config = {
        "metadata": {"owner": "apm"},
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": keep_command,
                            "async": True,
                            "if": "Bash(git commit*)",
                        },
                        {
                            "type": "prompt",
                            "prompt": "unsupported",
                        },
                        {
                            "type": "command",
                            "command": (
                                f"{hooks_dir}/agent-builder/scripts/coder-delegation-reminder.sh"
                            ),
                        },
                        {
                            "type": "command",
                            "command": future_command,
                        },
                    ],
                }
            ],
            "WorktreeCreate": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": (f"{hooks_dir}/hooks-worktree/scripts/create.sh"),
                        }
                    ]
                }
            ],
        },
    }

    clean, counts = sanitize_codex_hooks.sanitize(config)

    assert clean["metadata"] == {"owner": "apm"}
    assert set(clean["hooks"]) == {"PreToolUse"}
    assert clean["hooks"]["PreToolUse"] == [
        {
            "matcher": "Bash",
            "hooks": [
                {
                    "type": "command",
                    "command": keep_command,
                    "timeout": 30,
                },
                {
                    "type": "command",
                    "command": future_command,
                    "timeout": 30,
                },
            ],
        }
    ]
    assert counts == {
        "events_removed": 1,
        "handlers_removed": 2,
        "duplicate_groups_removed": 0,
        "async_converted": 1,
        "if_removed": 1,
        "timeouts_added": 2,
    }


def test_sanitize_preserves_valid_timeout() -> None:
    config = {
        "hooks": {
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": sys.executable,
                            "timeout": 10,
                        }
                    ]
                }
            ]
        }
    }

    clean, counts = sanitize_codex_hooks.sanitize(config)

    assert clean == config
    assert counts["timeouts_added"] == 0


def test_sanitize_preserves_current_codex_tool_matchers() -> None:
    handler = {
        "type": "command",
        "command": sys.executable,
        "timeout": 10,
    }
    config = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [handler]},
                {"matcher": "apply_patch", "hooks": [handler]},
                {"matcher": "Agent", "hooks": [handler]},
                {"matcher": "mcp__server__local_function", "hooks": [handler]},
            ]
        }
    }

    clean, counts = sanitize_codex_hooks.sanitize(config)

    assert clean == config
    assert counts["handlers_removed"] == 0


def test_sanitize_drops_missing_absolute_script() -> None:
    config = {
        "hooks": {
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "/definitely/missing/hook.sh",
                            "timeout": 10,
                        }
                    ]
                }
            ]
        }
    }

    clean, counts = sanitize_codex_hooks.sanitize(config)

    assert clean["hooks"] == {}
    assert counts["handlers_removed"] == 1


def test_sanitize_removes_legacy_claude_only_subagent_model_guard() -> None:
    config = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Agent",
                    "hooks": [
                        {
                            "type": "command",
                            "command": (
                                "/tmp/hooks/hooks-subagent-model/scripts/subagent-model-guard.sh"
                            ),
                        }
                    ],
                }
            ]
        }
    }

    clean, counts = sanitize_codex_hooks.sanitize(config)

    assert clean["hooks"] == {}
    assert counts["handlers_removed"] == 1


def test_sanitize_resolves_relative_script_from_config_workspace(
    tmp_path: Path,
) -> None:
    live = tmp_path / ".codex" / "hooks" / "live.sh"
    live.parent.mkdir(parents=True)
    live.write_text("#!/bin/sh\n", encoding="utf-8")
    config = {
        "hooks": {
            "PreToolUse": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": ".codex/hooks/live.sh",
                        }
                    ]
                },
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": ".codex/hooks/missing.sh",
                        }
                    ]
                },
            ]
        }
    }

    clean, counts = sanitize_codex_hooks.sanitize(config, tmp_path)

    assert len(clean["hooks"]["PreToolUse"]) == 1
    assert clean["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == (".codex/hooks/live.sh")
    assert counts["handlers_removed"] == 1


def test_sanitize_deduplicates_identical_groups_after_normalization() -> None:
    handler = {
        "type": "command",
        "command": sys.executable,
        "timeout": 10,
    }
    config = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [handler],
                },
                {
                    "matcher": "Bash",
                    "hooks": [handler],
                },
            ],
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": sys.executable,
                            "async": True,
                        }
                    ]
                },
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": sys.executable,
                            "timeout": 30,
                        }
                    ]
                },
            ],
        }
    }

    clean, counts = sanitize_codex_hooks.sanitize(config)

    assert clean["hooks"]["PreToolUse"] == [
        {
            "matcher": "Bash",
            "hooks": [handler],
        }
    ]
    assert clean["hooks"]["Stop"] == [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": sys.executable,
                    "timeout": 30,
                }
            ]
        }
    ]
    assert counts["duplicate_groups_removed"] == 2


def test_sanitize_deduplicates_legacy_group_and_keeps_apm_owner() -> None:
    handler = {
        "type": "command",
        "command": sys.executable,
        "timeout": 10,
    }
    legacy_group = {
        "matcher": "Bash",
        "hooks": [handler],
    }
    managed_group = {
        "matcher": "Bash",
        "hooks": [handler],
        "_apm_source": "hooks-bash-safety",
    }
    config = {
        "hooks": {
            "PreToolUse": [
                legacy_group,
                managed_group,
            ],
            "PostToolUse": [
                managed_group,
                legacy_group,
            ],
        }
    }

    clean, counts = sanitize_codex_hooks.sanitize(config)

    assert clean["hooks"]["PreToolUse"] == [managed_group]
    assert clean["hooks"]["PostToolUse"] == [managed_group]
    assert counts["duplicate_groups_removed"] == 2


def test_prune_removes_only_unreferenced_top_level_entries(
    tmp_path: Path,
) -> None:
    hooks_dir = tmp_path / "hooks"
    keep_dir = hooks_dir / "hooks-bash-safety" / "scripts"
    keep_dir.mkdir(parents=True)
    (keep_dir / "guard.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (keep_dir / "helper.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    stale_dir = hooks_dir / "hooks-worktree" / "scripts"
    stale_dir.mkdir(parents=True)
    (stale_dir / "create.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    stale_file = hooks_dir / "legacy-guard.sh"
    stale_file.write_text("#!/bin/sh\n", encoding="utf-8")
    referenced_file = hooks_dir / "direct-hook.sh"
    referenced_file.write_text("#!/bin/sh\n", encoding="utf-8")
    config = {
        "hooks": {
            "PreToolUse": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"{keep_dir}/guard.sh",
                        },
                        {
                            "type": "command",
                            "command": str(referenced_file),
                        },
                    ]
                }
            ]
        }
    }

    pending = sanitize_codex_hooks.prune_stale_entries(
        config,
        hooks_dir,
        check=True,
    )
    assert [path.name for path in pending] == [
        "hooks-worktree",
        "legacy-guard.sh",
    ]
    assert stale_dir.is_dir()
    assert stale_file.is_file()

    removed = sanitize_codex_hooks.prune_stale_entries(config, hooks_dir)

    assert [path.name for path in removed] == [
        "hooks-worktree",
        "legacy-guard.sh",
    ]
    assert (keep_dir / "helper.sh").is_file()
    assert referenced_file.is_file()
    assert not stale_dir.exists()
    assert not stale_file.exists()


def test_cli_reports_pruned_entry_count(tmp_path: Path) -> None:
    config_path = tmp_path / "hooks.json"
    hooks_dir = tmp_path / "hooks"
    keep_script = hooks_dir / "keep" / "scripts" / "guard.sh"
    keep_script.parent.mkdir(parents=True)
    keep_script.write_text("#!/bin/sh\n", encoding="utf-8")
    stale_script = hooks_dir / "legacy.sh"
    stale_script.write_text("#!/bin/sh\n", encoding="utf-8")
    config_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": str(keep_script),
                                    "timeout": 10,
                                }
                            ]
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(config_path),
            "--prune-stale",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "stale_entries_removed=1" in result.stdout
    assert keep_script.is_file()
    assert not stale_script.exists()
