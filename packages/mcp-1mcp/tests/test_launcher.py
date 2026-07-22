"""Regression tests for the shared 1MCP runtime launcher."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time


PACKAGE = Path(__file__).resolve().parents[1]


def launcher_script() -> Path:
    return PACKAGE / "scripts" / "launcher.sh"


def launcher_command() -> str:
    claude = json.loads((PACKAGE / ".mcp.json").read_text(encoding="utf-8"))
    codex = json.loads((PACKAGE / ".codex.mcp.json").read_text(encoding="utf-8"))
    claude_command = claude["mcpServers"]["1mcp"]["args"][1]
    codex_command = codex["1mcp"]["args"][1]
    assert claude_command == codex_command
    return claude_command


def test_manifest_delegates_to_inspectable_launcher_script() -> None:
    script = launcher_script()
    command = launcher_command()

    assert script.is_file()
    assert "scripts/launcher.sh" in command
    assert "launcher.lock.d" not in command
    assert len(command) < 1_000


def test_launcher_stays_small_and_uses_kernel_locks() -> None:
    script = launcher_script().read_text(encoding="utf-8")

    assert len(script.splitlines()) < 220
    assert "flock" in script
    assert "lockf" in script
    assert ".takeover" not in script
    assert ".publish" not in script
    assert "launcher.lock.d" not in script


def install_fake_commands(
    tmp_path: Path,
    *,
    initially_ready: bool = False,
    start_behavior: str = "success",
    status_behavior: str = "return",
    background_delay: float = 0,
    minimal_path: bool = False,
    include_node: bool = True,
    include_timeout: bool = True,
    include_perl: bool = False,
    lock_mode: str = "flock",
) -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    actions = state_dir / "actions"
    actions.touch()
    if initially_ready:
        (state_dir / "ready").touch()

    entry = tmp_path / "node_modules" / "@1mcp" / "agent" / "build" / "index.js"
    entry.parent.mkdir(parents=True)
    entry.write_text(
        """#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const state = process.env.FAKE_1MCP_STATE;
const args = process.argv.slice(2);
const leakedLauncherEnv = Object.keys(process.env).filter(
  (key) => key.startsWith("ONE_MCP_LAUNCHER_") || key.startsWith("MCP1_LAUNCHER_")
);
if (leakedLauncherEnv.length > 0) {
  fs.appendFileSync(
    path.join(state, "actions"),
    "env-leak " + leakedLauncherEnv.join(" ") + "\\n"
  );
  process.exit(87);
}
fs.appendFileSync(path.join(state, "actions"), args.join(" ") + "\\n");

const sleep = (milliseconds) => {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, milliseconds);
};
const hold = (ignoreTerm) => {
  if (ignoreTerm) process.on("SIGTERM", () => {});
  setInterval(() => {}, 1000);
};

const main = () => {
if (args[0] === "serve" && args[1] === "--status") {
  if (process.env.FAKE_1MCP_STATUS === "hang") {
    hold(false);
    return;
  }
  if (process.env.FAKE_1MCP_STATUS === "ignore") {
    hold(true);
    return;
  }
  process.exit(fs.existsSync(path.join(state, "ready")) ? 0 : 1);
}

if (args[0] === "serve" && args[1] === "--background") {
  fs.appendFileSync(path.join(state, "server.log"), "background diagnostic\\n");
  if (!process.argv[1].endsWith(".js")) process.exit(88);
  if (process.env.FAKE_1MCP_STARTS === "hang") {
    hold(false);
    return;
  }
  if (process.env.FAKE_1MCP_STARTS === "ignore") {
    hold(true);
    return;
  }
  sleep(Number(process.env.FAKE_1MCP_BACKGROUND_DELAY) * 1000);
  if (process.env.FAKE_1MCP_STARTS === "failure") process.exit(1);
  if (process.env.FAKE_1MCP_STARTS === "unready") process.exit(0);
  fs.writeFileSync(path.join(state, "ready"), "");
  process.exit(0);
}

if (args[0] === "serve" && args[1] === "--background-bootstrap") {
  if (process.env.FAKE_1MCP_STARTS !== "hold") process.exit(2);
  hold(false);
  return;
}

if (args[0] === "serve" && args[1] === "--stop") process.exit(99);
if (args[0] === "proxy") process.exit(0);
process.exit(2);
};
main();
""",
        encoding="utf-8",
    )
    entry.chmod(0o755)
    (bin_dir / "1mcp").symlink_to(entry)

    env = dict(os.environ)
    env["FAKE_1MCP_STATE"] = str(state_dir)
    env["FAKE_1MCP_STARTS"] = start_behavior
    env["FAKE_1MCP_STATUS"] = status_behavior
    env["FAKE_1MCP_BACKGROUND_DELAY"] = str(background_delay)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    env["MCP1_LAUNCHER_WAIT_SECONDS"] = "5"
    env["MCP1_LAUNCHER_KILL_GRACE_SECONDS"] = "1"

    if not minimal_path:
        env["PATH"] = f"{bin_dir}:{env['PATH']}"
        return env, actions

    commands = ["bash", "date", "env", "mkdir", "mv", "ps", "sleep", "tr"]
    if include_node:
        commands.append("node")
    if include_timeout:
        commands.append("timeout")
    if include_perl:
        commands.append("perl")
    if lock_mode == "flock":
        commands.append("flock")
    for command in commands:
        target = shutil.which(command)
        assert target is not None, command
        (bin_dir / command).symlink_to(target)

    if lock_mode == "lockf":
        real_flock = shutil.which("flock")
        assert real_flock is not None
        lockf = bin_dir / "lockf"
        lockf.write_text(
            "#!/bin/sh\n"
            "seconds=$2\n"
            "file=$3\n"
            "shift 3\n"
            'exec "$FAKE_REAL_FLOCK" -w "$seconds" "$file" "$@"\n',
            encoding="utf-8",
        )
        lockf.chmod(0o755)
        env["FAKE_REAL_FLOCK"] = real_flock

    env["PATH"] = str(bin_dir)
    return env, actions


def run_launcher(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(launcher_script())],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def action_count(actions: Path, prefix: str) -> int:
    return sum(
        line == prefix or line.startswith(f"{prefix} ")
        for line in actions.read_text(encoding="utf-8").splitlines()
    )


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


def wait_for_action(actions: Path, prefix: str, timeout: float = 3) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if action_count(actions, prefix):
            return
        time.sleep(0.01)
    raise AssertionError(f"action never observed: {prefix}")


def test_launcher_has_no_runtime_signal_path() -> None:
    script = launcher_script().read_text(encoding="utf-8")

    assert "serve --stop" not in script
    assert 'kill "$pid"' not in script


def test_ready_runtime_connects_without_locking_or_starting(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path, initially_ready=True)

    result = run_launcher(env)

    assert result.returncode == 0, result.stderr
    assert action_count(actions, "serve --background") == 0
    assert action_count(actions, "proxy") == 1
    assert not (Path(env["XDG_CONFIG_HOME"]) / "1mcp" / "launcher.lock").exists()


def test_empty_scope_starts_async_runtime_and_connects(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path)

    result = run_launcher(env)

    assert result.returncode == 0, result.stderr
    lines = actions.read_text(encoding="utf-8")
    assert action_count(actions, "serve --background") == 1
    assert "--enable-async-loading" in lines
    assert "--async-min-servers 1" in lines
    assert "--async-timeout 5000" in lines
    assert action_count(actions, "proxy") == 1


def test_background_launch_resolves_npm_bin_symlink(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path)

    result = run_launcher(env)

    assert result.returncode == 0, result.stderr
    assert action_count(actions, "serve --background") == 1


def test_legacy_launcher_tuning_is_supported_but_not_leaked_to_1mcp(
    tmp_path: Path,
) -> None:
    env, actions = install_fake_commands(tmp_path)
    env.pop("MCP1_LAUNCHER_WAIT_SECONDS")
    env["ONE_MCP_LAUNCHER_WAIT_SECONDS"] = "4"

    result = run_launcher(env)

    assert result.returncode == 0, result.stderr
    assert "env-leak" not in actions.read_text(encoding="utf-8")


def test_concurrent_launchers_start_once_and_both_connect(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path, background_delay=0.5)
    command = ["bash", str(launcher_script())]

    first = subprocess.Popen(command, env=env)
    second = subprocess.Popen(command, env=env)

    assert first.wait(timeout=8) == 0
    assert second.wait(timeout=8) == 0
    assert action_count(actions, "serve --background") == 1
    assert action_count(actions, "proxy") == 2


def test_stale_pid_for_reused_process_is_quarantined_without_signal(
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
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=5)


def test_malformed_pid_file_is_quarantined(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path)
    pid_file = Path(env["XDG_CONFIG_HOME"]) / "1mcp" / "server.pid"
    pid_file.parent.mkdir(parents=True)
    pid_file.write_text("not json", encoding="utf-8")

    result = run_launcher(env)

    assert result.returncode == 0, result.stderr
    assert action_count(actions, "serve --background") == 1
    assert len(list(pid_file.parent.glob("server.pid.stale.*"))) == 1


def test_launcher_self_pid_is_treated_as_stale(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path)
    pid_file = Path(env["XDG_CONFIG_HOME"]) / "1mcp" / "server.pid"
    pid_file.parent.mkdir(parents=True)
    env["FAKE_PID_FILE"] = str(pid_file)
    env["FAKE_LAUNCHER"] = str(launcher_script())
    command = (
        "printf '{\"pid\":%s,\"url\":\"http://127.0.0.1:3050/mcp\","
        "\"port\":3050,\"host\":\"127.0.0.1\",\"transport\":\"http\","
        "\"startedAt\":\"x\",\"configDir\":\"x\"}' \"$$\" "
        '>"$FAKE_PID_FILE"; exec bash "$FAKE_LAUNCHER"'
    )

    result = subprocess.run(
        ["bash", "-c", command],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert action_count(actions, "serve --background") == 1
    assert len(list(pid_file.parent.glob("server.pid.stale.*"))) == 1


def test_genuine_unhealthy_runtime_is_preserved_and_not_signalled(
    tmp_path: Path,
) -> None:
    env, actions = install_fake_commands(tmp_path, start_behavior="hold")
    env["MCP1_LAUNCHER_WAIT_SECONDS"] = "2"
    runtime_env = dict(env)
    runtime_env.pop("MCP1_LAUNCHER_WAIT_SECONDS")
    runtime_env.pop("MCP1_LAUNCHER_KILL_GRACE_SECONDS")
    genuine = subprocess.Popen(
        [str(tmp_path / "bin" / "1mcp"), "serve", "--background-bootstrap"],
        env=runtime_env,
    )
    pid_file = write_pid_file(Path(env["XDG_CONFIG_HOME"]), genuine.pid)

    try:
        time.sleep(0.05)
        result = run_launcher(env)

        assert result.returncode == 1
        assert "operator intervention" in result.stderr
        assert genuine.poll() is None
        assert pid_file.exists()
        assert action_count(actions, "serve --stop") == 0
        assert action_count(actions, "serve --background") == 0
    finally:
        genuine.terminate()
        genuine.wait(timeout=5)


def test_process_with_runtime_words_in_one_argument_is_not_trusted(
    tmp_path: Path,
) -> None:
    env, actions = install_fake_commands(tmp_path)
    spoof = subprocess.Popen(
        ["bash", "-c", "exec -a '1mcp serve --background-bootstrap' sleep 30"],
    )
    pid_file = write_pid_file(Path(env["XDG_CONFIG_HOME"]), spoof.pid)

    try:
        result = run_launcher(env)

        assert result.returncode == 0, result.stderr
        assert spoof.poll() is None
        assert action_count(actions, "serve --background") == 1
        assert not pid_file.exists()
    finally:
        spoof.terminate()
        spoof.wait(timeout=5)


def test_stale_legacy_lock_artifacts_cannot_block_startup(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path)
    runtime_dir = Path(env["XDG_CONFIG_HOME"]) / "1mcp"
    old_lock = runtime_dir / "launcher.lock.d"
    old_lock.mkdir(parents=True)
    (old_lock / "owner").write_text("dead owner", encoding="utf-8")
    (runtime_dir / "launcher.lock").write_text("stale contents", encoding="utf-8")

    result = run_launcher(env)

    assert result.returncode == 0, result.stderr
    assert action_count(actions, "serve --background") == 1


def test_failed_background_start_is_bounded_and_diagnostic(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path, start_behavior="failure")
    env["MCP1_LAUNCHER_WAIT_SECONDS"] = "2"

    started = time.monotonic()
    result = run_launcher(env)
    elapsed = time.monotonic() - started

    assert result.returncode == 1
    assert elapsed < 4
    assert "startup failed" in result.stderr
    assert action_count(actions, "serve --background") == 1
    assert "background diagnostic" in (
        tmp_path / "state" / "server.log"
    ).read_text(encoding="utf-8")


def test_hung_status_is_bounded_without_starting(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path, status_behavior="hang")
    env["MCP1_LAUNCHER_WAIT_SECONDS"] = "2"

    started = time.monotonic()
    result = run_launcher(env)
    elapsed = time.monotonic() - started

    assert result.returncode == 1
    assert elapsed < 4
    assert action_count(actions, "serve --background") == 0
    assert action_count(actions, "proxy") == 0


def test_hung_background_start_is_bounded(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path, start_behavior="hang")
    env["MCP1_LAUNCHER_WAIT_SECONDS"] = "3"

    started = time.monotonic()
    result = run_launcher(env)
    elapsed = time.monotonic() - started

    assert result.returncode == 1
    assert elapsed < 5
    assert action_count(actions, "serve --background") == 1
    assert action_count(actions, "proxy") == 0


def test_term_releases_kernel_lock_for_next_launcher(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path, start_behavior="hang")
    env["MCP1_LAUNCHER_WAIT_SECONDS"] = "3"
    first = subprocess.Popen(
        ["bash", str(launcher_script())],
        env=env,
        start_new_session=True,
    )
    wait_for_action(actions, "serve --background")

    os.killpg(first.pid, signal.SIGTERM)
    first.wait(timeout=5)
    env["FAKE_1MCP_STARTS"] = "success"
    env["MCP1_LAUNCHER_WAIT_SECONDS"] = "6"

    second = run_launcher(env)

    assert second.returncode == 0, second.stderr
    assert action_count(actions, "serve --background") == 2
    assert action_count(actions, "proxy") == 1


def test_lockf_fallback_serializes_startup(tmp_path: Path) -> None:
    env, actions = install_fake_commands(
        tmp_path,
        minimal_path=True,
        lock_mode="lockf",
    )

    result = run_launcher(env)

    assert result.returncode == 0, result.stderr
    assert action_count(actions, "serve --background") == 1
    assert action_count(actions, "proxy") == 1


def test_perl_timeout_fallback_is_supported(tmp_path: Path) -> None:
    env, actions = install_fake_commands(
        tmp_path,
        minimal_path=True,
        include_timeout=False,
        include_perl=True,
    )

    result = run_launcher(env)

    assert result.returncode == 0, result.stderr
    assert action_count(actions, "serve --background") == 1


def test_missing_1mcp_fails_with_actionable_error(tmp_path: Path) -> None:
    env, _ = install_fake_commands(tmp_path, minimal_path=True)
    (tmp_path / "bin" / "1mcp").unlink()

    result = run_launcher(env)

    assert result.returncode == 1
    assert "1mcp-not-installed" in result.stderr


def test_missing_node_fails_with_actionable_error(tmp_path: Path) -> None:
    env, _ = install_fake_commands(
        tmp_path,
        minimal_path=True,
        include_node=False,
    )

    result = run_launcher(env)

    assert result.returncode == 1
    assert "node-not-installed" in result.stderr


def test_missing_timeout_implementation_fails_closed(tmp_path: Path) -> None:
    env, _ = install_fake_commands(
        tmp_path,
        minimal_path=True,
        include_timeout=False,
        include_perl=False,
    )

    result = run_launcher(env)

    assert result.returncode == 1
    assert "needs-timeout-gtimeout-or-perl" in result.stderr


def test_missing_kernel_lock_implementation_fails_closed(tmp_path: Path) -> None:
    env, actions = install_fake_commands(
        tmp_path,
        minimal_path=True,
        lock_mode="none",
    )

    result = run_launcher(env)

    assert result.returncode == 1
    assert "needs-flock-or-lockf" in result.stderr
    assert action_count(actions, "serve --background") == 0


def test_invalid_tuning_values_fail_before_startup(tmp_path: Path) -> None:
    env, actions = install_fake_commands(tmp_path)
    env["MCP1_LAUNCHER_WAIT_SECONDS"] = "not-a-number"

    result = run_launcher(env)

    assert result.returncode == 1
    assert "invalid-wait-seconds" in result.stderr
    assert actions.read_text(encoding="utf-8") == ""
