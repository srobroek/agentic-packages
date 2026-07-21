"""Regression tests for the 1MCP client launcher."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import time


PACKAGE = Path(__file__).resolve().parents[1]


def launcher_command() -> str:
    claude = json.loads((PACKAGE / ".mcp.json").read_text(encoding="utf-8"))
    codex = json.loads((PACKAGE / ".codex.mcp.json").read_text(encoding="utf-8"))
    claude_command = claude["mcpServers"]["1mcp"]["args"][1]
    codex_command = codex["1mcp"]["args"][1]
    assert claude_command == codex_command
    return claude_command


def install_fake_commands(
    tmp_path: Path,
    *,
    initially_ready: bool = False,
    start_succeeds: bool = True,
    start_unready: bool = False,
    minimal_path: bool = False,
) -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    actions = state_dir / "actions"
    actions.touch()
    if initially_ready:
        (state_dir / "ready").touch()

    fake = bin_dir / "1mcp"
    fake.write_text(
        "#!/bin/sh\n"
        "state=$FAKE_1MCP_STATE\n"
        "printf '%s\\n' \"$*\" >>\"$state/actions\"\n"
        "case \"$1 $2\" in\n"
        "  'serve --status') [ -f \"$state/ready\" ]; exit $? ;;\n"
        "  'serve --background')\n"
        "    printf 'background diagnostic\\n' >>\"$state/server.log\"\n"
        "    [ \"$FAKE_1MCP_STARTS\" = unready ] && exit 0\n"
        "    [ \"$FAKE_1MCP_STARTS\" = success ] || exit 1\n"
        "    touch \"$state/ready\"\n"
        "    exit 0\n"
        "    ;;\n"
        "  'serve --background-bootstrap')\n"
        "    [ \"$FAKE_1MCP_STARTS\" = hold ] || exit 2\n"
        "    sleep 30\n"
        "    ;;\n"
        "  'serve --stop') exit 99 ;;\n"
        "  'proxy ') exit 0 ;;\n"
        "esac\n"
        "exit 2\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)

    env = dict(os.environ)
    env["FAKE_1MCP_STATE"] = str(state_dir)
    env["FAKE_1MCP_STARTS"] = (
        "unready" if start_unready else ("success" if start_succeeds else "failure")
    )
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    env["ONE_MCP_LAUNCHER_WAIT_SECONDS"] = "1"
    if minimal_path:
        for command in (
            "awk",
            "date",
            "mkdir",
            "mv",
            "ps",
            "rm",
            "rmdir",
            "sed",
            "sleep",
            "touch",
            "tr",
        ):
            target = subprocess.run(
                ["bash", "-lc", f"command -v {command}"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            (bin_dir / command).symlink_to(target)
        env["PATH"] = str(bin_dir)
    else:
        env["PATH"] = f"{bin_dir}:{env['PATH']}"
    return env, actions


def run_launcher(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", "-c", launcher_command()],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def action_count(actions: Path, action: str) -> int:
    return actions.read_text(encoding="utf-8").splitlines().count(action)


def write_pid_file(config_home: Path, pid: int) -> Path:
    runtime_dir = config_home / "1mcp"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    pid_file = runtime_dir / "server.pid"
    pid_file.write_text(
        json.dumps(
            {
                "pid": pid,
                "url": "http://127.0.0.1:3050/mcp",
                "port": 3050,
                "host": "127.0.0.1",
                "transport": "http",
                "startedAt": "2026-07-21T00:00:00Z",
                "configDir": str(runtime_dir),
            }
        ),
        encoding="utf-8",
    )
    return pid_file


def process_start_identity(pid: int) -> str:
    proc_stat = Path(f"/proc/{pid}/stat")
    if proc_stat.is_file():
        after_comm = proc_stat.read_text(encoding="utf-8").rsplit(") ", 1)[1]
        return f"linux:{after_comm.split()[19]}"
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart="],
        capture_output=True,
        text=True,
        check=True,
    )
    return f"ps:{result.stdout.strip()}"


def write_mkdir_lock(config_home: Path, pid: int, start_identity: str) -> Path:
    lock_dir = config_home / "1mcp" / "launcher.lock.d"
    lock_dir.mkdir(parents=True)
    (lock_dir / "owner").write_text(
        f"pid={pid}\nstart={start_identity}\n",
        encoding="utf-8",
    )
    return lock_dir


def test_launcher_has_no_runtime_signal_path() -> None:
    command = launcher_command()

    assert "serve --stop" not in command
    assert " kill " not in command


def test_ready_runtime_connects_without_starting(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path, initially_ready=True)

    result = run_launcher(env)

    assert result.returncode == 0, result.stderr
    assert action_count(actions, "serve --background") == 0
    assert action_count(actions, "proxy") == 1


def test_concurrent_launchers_start_once_and_both_connect(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path)
    command = launcher_command()

    first = subprocess.Popen(["/bin/bash", "-c", command], env=env, text=True)
    second = subprocess.Popen(["/bin/bash", "-c", command], env=env, text=True)

    assert first.wait(timeout=5) == 0
    assert second.wait(timeout=5) == 0
    assert action_count(actions, "serve --background") == 1
    assert action_count(actions, "proxy") == 2


def test_mismatched_reused_pid_is_quarantined_without_signalling_process(
    tmp_path: Path,
) -> None:
    env, actions = install_fake_commands(tmp_path)
    unrelated = subprocess.Popen(["sleep", "30"])
    pid_file = write_pid_file(Path(env["XDG_CONFIG_HOME"]), unrelated.pid)

    try:
        result = run_launcher(env)

        assert result.returncode == 0, result.stderr
        assert unrelated.poll() is None
        assert action_count(actions, "serve --stop") == 0
        assert action_count(actions, "serve --background") == 1
        assert not pid_file.exists()
        quarantined = list(pid_file.parent.glob("server.pid.stale.*"))
        assert len(quarantined) == 1
        assert json.loads(quarantined[0].read_text(encoding="utf-8"))["pid"] == unrelated.pid
    finally:
        unrelated.send_signal(signal.SIGTERM)
        unrelated.wait(timeout=5)


def test_empty_scope_starts_and_connects(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path)

    result = run_launcher(env)

    assert result.returncode == 0, result.stderr
    assert action_count(actions, "serve --background") == 1
    assert action_count(actions, "proxy") == 1


def test_genuine_unhealthy_runtime_is_not_signalled(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path)
    genuine = subprocess.Popen(
        [str(tmp_path / "bin" / "1mcp"), "serve", "--background-bootstrap"],
        env={**env, "FAKE_1MCP_STARTS": "hold"},
    )
    pid_file = write_pid_file(Path(env["XDG_CONFIG_HOME"]), genuine.pid)

    try:
        time.sleep(0.05)
        result = run_launcher(env)

        assert result.returncode == 1
        assert "operator intervention" in result.stderr
        assert action_count(actions, "serve --stop") == 0
        assert action_count(actions, "serve --background") == 0
        assert genuine.poll() is None
        assert pid_file.exists()
    finally:
        if genuine.poll() is None:
            genuine.terminate()
            genuine.wait(timeout=5)


def test_spoofed_1mcp_process_is_never_signalled(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path)
    spoof = subprocess.Popen(
        ["bash", "-c", "exec -a '1mcp serve --background-bootstrap' sleep 30"],
    )
    pid_file = write_pid_file(Path(env["XDG_CONFIG_HOME"]), spoof.pid)

    try:
        result = run_launcher(env)

        assert result.returncode == 1
        assert action_count(actions, "serve --stop") == 0
        assert action_count(actions, "serve --background") == 0
        assert spoof.poll() is None
        assert pid_file.exists()
    finally:
        spoof.terminate()
        spoof.wait(timeout=5)


def test_start_failure_is_bounded_and_preserves_diagnostics(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path, start_succeeds=False)

    started = time.monotonic()
    result = run_launcher(env)
    elapsed = time.monotonic() - started

    assert result.returncode == 1
    assert elapsed < 3
    assert action_count(actions, "serve --background") == 1
    assert "background diagnostic" in (tmp_path / "state" / "server.log").read_text(encoding="utf-8")
    assert "serve --status" in result.stderr


def test_launcher_works_without_flock(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path, minimal_path=True)

    result = run_launcher(env)

    assert result.returncode == 0, result.stderr
    assert action_count(actions, "serve --background") == 1
    assert action_count(actions, "proxy") == 1


def test_stale_mkdir_lock_is_quarantined_and_retried_once(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path, minimal_path=True)
    lock_dir = write_mkdir_lock(Path(env["XDG_CONFIG_HOME"]), 999_999_999, "linux:1")

    result = run_launcher(env)

    assert result.returncode == 0, result.stderr
    assert not lock_dir.exists()
    assert len(list(lock_dir.parent.glob("launcher.lock.d.stale.*"))) == 1
    assert action_count(actions, "serve --background") == 1


def test_live_mkdir_lock_owner_is_preserved(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path, minimal_path=True)
    owner = subprocess.Popen(["sleep", "30"])
    lock_dir = write_mkdir_lock(
        Path(env["XDG_CONFIG_HOME"]),
        owner.pid,
        process_start_identity(owner.pid),
    )

    try:
        result = run_launcher(env)

        assert result.returncode == 1
        assert "lock-timeout" in result.stderr
        assert owner.poll() is None
        assert lock_dir.exists()
        assert action_count(actions, "serve --background") == 0
    finally:
        owner.terminate()
        owner.wait(timeout=5)


def test_term_exits_without_continuing_startup(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path, start_unready=True, minimal_path=True)
    launcher = subprocess.Popen(
        ["/bin/bash", "-c", launcher_command()],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 3
    while (
        action_count(actions, "serve --background") == 0
        and time.monotonic() < deadline
    ):
        time.sleep(0.01)

    launcher.terminate()
    _, stderr = launcher.communicate(timeout=5)

    assert launcher.returncode == 143, stderr
    assert action_count(actions, "proxy") == 0
    lock_dir = Path(env["XDG_CONFIG_HOME"]) / "1mcp" / "launcher.lock.d"
    assert not lock_dir.exists()
