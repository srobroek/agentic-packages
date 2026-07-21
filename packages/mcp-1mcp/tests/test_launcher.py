"""Regression tests for the 1MCP client launcher."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


PACKAGE = Path(__file__).resolve().parents[1]


def launcher_command() -> str:
    claude = json.loads((PACKAGE / ".mcp.json").read_text(encoding="utf-8"))
    codex = json.loads((PACKAGE / ".codex.mcp.json").read_text(encoding="utf-8"))
    claude_command = claude["mcpServers"]["1mcp"]["args"][1]
    codex_command = codex["1mcp"]["args"][1]
    assert claude_command == codex_command
    return claude_command


def install_fake_commands(tmp_path: Path, status: str) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "1mcp"
    fake.write_text(
        "#!/bin/sh\n"
        "case \"$1 $2\" in\n"
        "  'serve --background') exit 1 ;;\n"
        f"  'serve --status') exit {status} ;;\n"
        "  'proxy ') exit 0 ;;\n"
        "esac\n"
        "exit 2\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    sleep = bin_dir / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    sleep.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    return env


def test_concurrent_start_loser_attaches_when_runtime_becomes_ready(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        ["bash", "-lc", launcher_command()],
        env=install_fake_commands(tmp_path, "0"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_launcher_fails_when_runtime_never_becomes_ready(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", "-lc", launcher_command()],
        env=install_fake_commands(tmp_path, "1"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
