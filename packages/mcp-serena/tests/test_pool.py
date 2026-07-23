"""Regression tests for checkout-aware Serena pooling."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any

import pytest


PACKAGE = Path(__file__).resolve().parents[1]
LAUNCHER = PACKAGE / "scripts" / "serena-pool.py"

spec = importlib.util.spec_from_file_location("serena_pool", LAUNCHER)
assert spec is not None and spec.loader is not None
serena_pool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serena_pool)


def run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True, capture_output=True, text=True)


def init_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    run("git", "init", "-b", "main", cwd=repo)
    run("git", "config", "user.name", "Serena Pool Tests", cwd=repo)
    run("git", "config", "user.email", "serena-pool@example.invalid", cwd=repo)
    run("git", "config", "commit.gpgsign", "false", cwd=repo)
    (repo / "README.md").write_text("# fixture\n", encoding="utf-8")
    run("git", "add", "README.md", cwd=repo)
    run("git", "commit", "-m", "test: initialize fixture", cwd=repo)
    return repo


def add_worktree(repo: Path, name: str) -> Path:
    worktree = repo.parent / name
    run("git", "worktree", "add", "-b", name, str(worktree), cwd=repo)
    return worktree


def write_fake_commands(tmp_path: Path) -> tuple[Path, Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    serena_actions = tmp_path / "serena-actions.jsonl"
    proxy_actions = tmp_path / "proxy-actions.jsonl"

    serena = bin_dir / "serena"
    serena.write_text(
        """#!/usr/bin/env python3
import json
import os
import resource
import signal
import socket
import sys
import threading

args = sys.argv[1:]
port = int(args[args.index("--port") + 1])
project = args[args.index("--project") + 1]
context = args[args.index("--context") + 1]
record = {
    "pid": os.getpid(),
    "port": port,
    "project": project,
    "context": context,
    "nice": os.getpriority(os.PRIO_PROCESS, 0),
    "nofile": resource.getrlimit(resource.RLIMIT_NOFILE),
}
if hasattr(resource, "RLIMIT_AS"):
    record["address_space"] = resource.getrlimit(resource.RLIMIT_AS)
if hasattr(resource, "RLIMIT_NPROC"):
    record["processes"] = resource.getrlimit(resource.RLIMIT_NPROC)
with open(os.environ["FAKE_SERENA_ACTIONS"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(record) + "\\n")

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("127.0.0.1", port))
server.listen()
server.settimeout(0.2)

allocation = None
def allocate_memory():
    global allocation
    megabytes = int(os.environ.get("FAKE_SERENA_ALLOCATE_MB", "0"))
    if megabytes > 0:
        allocation = bytearray(megabytes * 1024 * 1024)

threading.Timer(0.2, allocate_memory).start()

def stop(_signum, _frame):
    server.close()
    raise SystemExit(0)

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
while True:
    try:
        connection, _address = server.accept()
    except socket.timeout:
        continue
    connection.close()
""",
        encoding="utf-8",
    )
    serena.chmod(0o755)

    proxy = bin_dir / "mcp-proxy"
    proxy.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys
import time

with open(os.environ["FAKE_PROXY_ACTIONS"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps({"pid": os.getpid(), "args": sys.argv[1:]}) + "\\n")
time.sleep(float(os.environ.get("FAKE_PROXY_SECONDS", "0")))
""",
        encoding="utf-8",
    )
    proxy.chmod(0o755)
    return bin_dir, serena_actions, proxy_actions


@pytest.fixture
def pool_env(tmp_path: Path) -> tuple[dict[str, str], Path, Path, Path]:
    bin_dir, serena_actions, proxy_actions = write_fake_commands(tmp_path)
    pool_home = tmp_path / "pool"
    env = dict(os.environ)
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "SERENA_POOL_HOME": str(pool_home),
            "SERENA_POOL_STARTUP_SECONDS": "5",
            "SERENA_POOL_SUPERVISOR_INTERVAL": "0.05",
            "SERENA_PRIMARY_IDLE_SECONDS": "60",
            "SERENA_WORKTREE_IDLE_SECONDS": "60",
            "FAKE_SERENA_ACTIONS": str(serena_actions),
            "FAKE_PROXY_ACTIONS": str(proxy_actions),
        }
    )
    yield env, pool_home, serena_actions, proxy_actions

    if pool_home.is_dir():
        for state_path in pool_home.glob("*/*/state.json"):
            state = read_json(state_path)
            for key in ("pid", "supervisor_pid"):
                pid = int(state.get(key, 0) or 0)
                if pid <= 0:
                    continue
                try:
                    os.killpg(pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    pass


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def run_launcher(
    cwd: Path,
    env: dict[str, str],
    *args: str,
    timeout: float = 10,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LAUNCHER), *args],
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def wait_until(predicate: Any, timeout: float = 5) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition did not become true before timeout")


def state_files(pool_home: Path) -> list[Path]:
    return sorted(pool_home.glob("*/*/state.json"))


def test_generated_clients_delegate_to_the_apm_launcher() -> None:
    claude = read_json(PACKAGE / ".mcp.json")
    codex = read_json(PACKAGE / ".codex.mcp.json")
    claude_command = claude["mcpServers"]["serena"]["args"][1]
    codex_command = codex["serena"]["args"][1]

    assert claude_command == codex_command
    assert "packages/mcp-serena/scripts/serena-pool.py" in claude_command
    assert "serena start-mcp-server" not in claude_command
    assert len(claude_command) < 1_000


def test_checkout_classifies_primary_and_linked_worktree(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    worktree = add_worktree(repo, "feature")

    primary = serena_pool.checkout(repo)
    linked = serena_pool.checkout(worktree)

    assert primary["kind"] == "primary"
    assert linked["kind"] == "worktree"
    assert linked["primary_root"] == str(repo.resolve())
    assert linked["common_dir"] == primary["common_dir"]


def test_primary_clients_reuse_one_backend(
    tmp_path: Path, pool_env: tuple[dict[str, str], Path, Path, Path]
) -> None:
    env, pool_home, serena_actions, proxy_actions = pool_env
    repo = init_repo(tmp_path)

    first = run_launcher(repo, env)
    second = run_launcher(repo, env)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    starts = read_json_lines(serena_actions)
    proxies = read_json_lines(proxy_actions)
    assert len(starts) == 1
    assert len(proxies) == 2
    assert proxies[0]["args"][-1] == proxies[1]["args"][-1]

    state = read_json(state_files(pool_home)[0])
    assert state["kind"] == "primary"
    assert state["limits"] == {}
    assert state["context"] == str(PACKAGE / "contexts" / "shared-cli.yml")


def test_concurrent_primary_clients_start_one_backend(
    tmp_path: Path, pool_env: tuple[dict[str, str], Path, Path, Path]
) -> None:
    env, _pool_home, serena_actions, _proxy_actions = pool_env
    env["FAKE_PROXY_SECONDS"] = "0.4"
    repo = init_repo(tmp_path)
    command = [sys.executable, str(LAUNCHER)]

    first = subprocess.Popen(command, cwd=repo, env=env)
    second = subprocess.Popen(command, cwd=repo, env=env)

    assert first.wait(timeout=10) == 0
    assert second.wait(timeout=10) == 0
    assert len(read_json_lines(serena_actions)) == 1


def test_linked_worktree_gets_isolated_limited_backend(
    tmp_path: Path, pool_env: tuple[dict[str, str], Path, Path, Path]
) -> None:
    env, pool_home, serena_actions, _proxy_actions = pool_env
    repo = init_repo(tmp_path)
    worktree = add_worktree(repo, "feature")

    assert run_launcher(repo, env).returncode == 0
    linked = run_launcher(worktree, env)

    assert linked.returncode == 0, linked.stderr
    starts = read_json_lines(serena_actions)
    assert len(starts) == 2
    assert starts[0]["port"] != starts[1]["port"]
    worktree_start = next(item for item in starts if item["project"] == str(worktree))
    assert worktree_start["nice"] >= 10
    assert worktree_start["nofile"][0] <= 1024

    states = [read_json(path) for path in state_files(pool_home)]
    worktree_state = next(state for state in states if state["kind"] == "worktree")
    assert worktree_state["project_root"] == str(worktree)
    assert worktree_state["limits"] == {
        "cpu_seconds": 0,
        "memory_mb": 1024,
        "nice": 10,
        "open_files": 1024,
        "processes": 0,
    }


def test_worktree_capacity_rejects_a_second_active_backend(
    tmp_path: Path, pool_env: tuple[dict[str, str], Path, Path, Path]
) -> None:
    env, pool_home, serena_actions, _proxy_actions = pool_env
    env["FAKE_PROXY_SECONDS"] = "2"
    env["SERENA_WORKTREE_MAX_INSTANCES"] = "1"
    repo = init_repo(tmp_path)
    first_worktree = add_worktree(repo, "first")
    second_worktree = add_worktree(repo, "second")

    first = subprocess.Popen(
        [sys.executable, str(LAUNCHER)],
        cwd=first_worktree,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_until(
        lambda: (
            len(read_json_lines(serena_actions)) == 1
            and any(
                path.parent.joinpath("leases").glob("*.json")
                for path in state_files(pool_home)
            )
        )
    )

    second = run_launcher(second_worktree, env)

    assert second.returncode == 1
    assert "Serena worktree capacity reached (1)" in second.stderr
    assert first.wait(timeout=10) == 0


def test_idle_worktree_backend_is_reaped(
    tmp_path: Path, pool_env: tuple[dict[str, str], Path, Path, Path]
) -> None:
    env, pool_home, _serena_actions, _proxy_actions = pool_env
    env["SERENA_WORKTREE_IDLE_SECONDS"] = "1"
    repo = init_repo(tmp_path)
    worktree = add_worktree(repo, "feature")

    result = run_launcher(worktree, env)
    assert result.returncode == 0, result.stderr
    state_path = state_files(pool_home)[0]
    pid = int(read_json(state_path)["pid"])

    wait_until(lambda: not state_path.exists(), timeout=5)
    assert not serena_pool.pid_alive(pid)


def test_worktree_memory_cap_stops_the_backend(
    tmp_path: Path, pool_env: tuple[dict[str, str], Path, Path, Path]
) -> None:
    env, pool_home, serena_actions, proxy_actions = pool_env
    env["SERENA_WORKTREE_MEMORY_MB"] = "128"
    env["FAKE_SERENA_ALLOCATE_MB"] = "192"
    env["FAKE_PROXY_SECONDS"] = "2"
    repo = init_repo(tmp_path)
    worktree = add_worktree(repo, "feature")
    client = subprocess.Popen([sys.executable, str(LAUNCHER)], cwd=worktree, env=env)
    wait_until(lambda: len(read_json_lines(proxy_actions)) == 1)
    pid = int(read_json_lines(serena_actions)[0]["pid"])

    wait_until(lambda: not state_files(pool_home), timeout=5)

    assert not serena_pool.pid_alive(pid)
    assert client.wait(timeout=10) == 0


def test_fleet_monitor_restarts_a_missing_worktree_supervisor(
    tmp_path: Path, pool_env: tuple[dict[str, str], Path, Path, Path]
) -> None:
    env, pool_home, _serena_actions, _proxy_actions = pool_env
    first_repo = init_repo(tmp_path, "first-repo")
    second_repo = init_repo(tmp_path, "second-repo")
    first_worktree = add_worktree(first_repo, "first")
    second_worktree = add_worktree(second_repo, "second")

    assert run_launcher(first_worktree, env).returncode == 0
    assert run_launcher(second_worktree, env).returncode == 0
    state_path = next(
        path
        for path in state_files(pool_home)
        if read_json(path)["project_root"] == str(second_worktree)
    )
    original_pid = int(read_json(state_path)["supervisor_pid"])
    os.killpg(original_pid, signal.SIGTERM)
    wait_until(lambda: not serena_pool.pid_alive(original_pid))

    wait_until(
        lambda: (
            state_path.exists()
            and int(read_json(state_path).get("supervisor_pid", 0)) != original_pid
            and serena_pool.pid_alive(
                int(read_json(state_path).get("supervisor_pid", 0))
            )
        )
    )


def test_global_memory_budget_evicts_an_idle_backend(
    tmp_path: Path, pool_env: tuple[dict[str, str], Path, Path, Path]
) -> None:
    env, pool_home, serena_actions, proxy_actions = pool_env
    env["SERENA_WORKTREE_MEMORY_MB"] = "256"
    env["SERENA_WORKTREE_TOTAL_MEMORY_MB"] = "150"
    env["FAKE_SERENA_ALLOCATE_MB"] = "80"
    first_repo = init_repo(tmp_path, "first-repo")
    second_repo = init_repo(tmp_path, "second-repo")
    first_worktree = add_worktree(first_repo, "first")
    second_worktree = add_worktree(second_repo, "second")

    first = run_launcher(first_worktree, env)
    assert first.returncode == 0, first.stderr
    first_pid = int(read_json_lines(serena_actions)[0]["pid"])
    wait_until(lambda: serena_pool.process_group_rss_mb(first_pid) >= 80)

    env["FAKE_PROXY_SECONDS"] = "2"
    second = subprocess.Popen(
        [sys.executable, str(LAUNCHER)], cwd=second_worktree, env=env
    )
    wait_until(lambda: len(read_json_lines(proxy_actions)) == 2)
    wait_until(lambda: not serena_pool.pid_alive(first_pid))
    wait_until(
        lambda: all(
            read_json(path)["project_root"] != str(first_worktree)
            for path in state_files(pool_home)
        )
    )

    states = [read_json(path) for path in state_files(pool_home)]
    assert all(state["project_root"] != str(first_worktree) for state in states)
    assert any(state["project_root"] == str(second_worktree) for state in states)
    assert second.wait(timeout=10) == 0


def test_global_memory_budget_rejects_new_backend_when_all_are_leased(
    tmp_path: Path, pool_env: tuple[dict[str, str], Path, Path, Path]
) -> None:
    env, _pool_home, serena_actions, proxy_actions = pool_env
    env["SERENA_WORKTREE_MEMORY_MB"] = "256"
    env["SERENA_WORKTREE_TOTAL_MEMORY_MB"] = "64"
    env["FAKE_SERENA_ALLOCATE_MB"] = "80"
    env["FAKE_PROXY_SECONDS"] = "2"
    first_repo = init_repo(tmp_path, "first-repo")
    second_repo = init_repo(tmp_path, "second-repo")
    first_worktree = add_worktree(first_repo, "first")
    second_worktree = add_worktree(second_repo, "second")

    first = subprocess.Popen(
        [sys.executable, str(LAUNCHER)], cwd=first_worktree, env=env
    )
    wait_until(lambda: len(read_json_lines(proxy_actions)) == 1)
    first_pid = int(read_json_lines(serena_actions)[0]["pid"])
    wait_until(lambda: serena_pool.process_group_rss_mb(first_pid) >= 64)

    second = run_launcher(second_worktree, env)

    assert second.returncode == 1
    assert "Serena global worktree memory budget reached" in second.stderr
    assert first.wait(timeout=10) == 0


def test_status_reports_shared_client_count(
    tmp_path: Path, pool_env: tuple[dict[str, str], Path, Path, Path]
) -> None:
    env, _pool_home, _serena_actions, proxy_actions = pool_env
    env["FAKE_PROXY_SECONDS"] = "1"
    repo = init_repo(tmp_path)
    client = subprocess.Popen([sys.executable, str(LAUNCHER)], cwd=repo, env=env)
    wait_until(lambda: len(read_json_lines(proxy_actions)) == 1)

    status = run_launcher(repo, env, "status")

    assert status.returncode == 0, status.stderr
    payload = json.loads(status.stdout)
    assert payload["running"] is True
    assert payload["clients"] == 1
    assert payload["kind"] == "primary"
    assert client.wait(timeout=10) == 0
