#!/usr/bin/env python3
"""Route MCP clients to one Serena backend per Git checkout."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
import uuid
from typing import Any, Iterator, TextIO


PROXY_VERSION = "0.12.0"

# `mcp-proxy` 0.12.0 declares `mcp>=1.17.0` with NO upper bound, and `mcp` 2.0.0
# removed `mcp.server.lowlevel.server.request_ctx`, which the proxy imports at
# module scope. So a fresh resolve pairs the two and every proxy start dies with
# `ImportError: cannot import name 'request_ctx'`. The failure is silent from the
# client's side: Serena is the only MCP server that reports "Failed to connect",
# and the agent simply has no semantic tools.
#
# Constrain `mcp` alongside the proxy so the resolver cannot pick 2.x. Verified:
# `uv run --with 'mcp-proxy==0.12.0' --with 'mcp>=1.17,<2'` imports cleanly.
PROXY_MCP_CONSTRAINT = "mcp>=1.17,<2"
STATE_VERSION = 1
HOST = "127.0.0.1"


class PoolError(RuntimeError):
    """A user-actionable Serena pool failure."""


def env_uint(
    name: str, default: int, *, minimum: int = 0, maximum: int | None = None
) -> int:
    value = os.environ.get(name, str(default))
    try:
        parsed = int(value)
    except ValueError as exc:
        raise PoolError(f"{name} must be an integer, got {value!r}") from exc
    if parsed < minimum:
        raise PoolError(f"{name} must be at least {minimum}, got {parsed}")
    if maximum is not None and parsed > maximum:
        raise PoolError(f"{name} must be at most {maximum}, got {parsed}")
    return parsed


def pool_home() -> Path:
    explicit = os.environ.get("SERENA_POOL_HOME")
    if explicit:
        return Path(explicit).expanduser().resolve()
    cache_home = os.environ.get("XDG_CACHE_HOME")
    if cache_home:
        return Path(cache_home).expanduser().resolve() / "serena" / "pools"
    home = os.environ.get("HOME")
    if not home:
        raise PoolError(
            "Serena pooling needs HOME, XDG_CACHE_HOME, or SERENA_POOL_HOME"
        )
    return Path(home).expanduser().resolve() / ".cache" / "serena" / "pools"


def run_git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise PoolError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def canonical(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def first_worktree(cwd: Path) -> Path:
    listing = run_git("worktree", "list", "--porcelain", cwd=cwd)
    for line in listing.splitlines():
        if line.startswith("worktree "):
            return canonical(line.removeprefix("worktree "))
    raise PoolError("git worktree list did not report a primary checkout")


def checkout(cwd: Path) -> dict[str, Any]:
    project_root = canonical(run_git("rev-parse", "--show-toplevel", cwd=cwd))
    common_dir = Path(
        run_git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd)
    )
    if not common_dir.is_absolute():
        common_dir = project_root / common_dir
    common_dir = canonical(common_dir)
    primary_root = first_worktree(project_root)
    kind = "primary" if project_root == primary_root else "worktree"
    return {
        "project_root": str(project_root),
        "primary_root": str(primary_root),
        "common_dir": str(common_dir),
        "kind": kind,
    }


def digest(*values: str) -> str:
    payload = "\0".join(values).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def package_context() -> Path:
    return Path(__file__).resolve().parents[1] / "contexts" / "shared-cli.yml"


def selected_context() -> str:
    override = os.environ.get("SERENA_MCP_CONTEXT")
    if override:
        candidate = Path(override).expanduser()
        return str(candidate.resolve()) if candidate.exists() else override
    context = package_context()
    if not context.is_file():
        raise PoolError(f"APM Serena context is missing: {context}")
    return str(context)


def paths_for(info: dict[str, Any], context: str) -> dict[str, Path]:
    home = pool_home()
    repo_key = digest(info["common_dir"])
    instance_key = digest(info["project_root"], context)
    repo_dir = home / repo_key
    instance_dir = repo_dir / instance_key
    return {
        "home": home,
        "pool_lock": home / "pool.lock",
        "monitor_lock": home / "monitor.lock",
        "repo_dir": repo_dir,
        "repo_lock": repo_dir / "pool.lock",
        "instance_dir": instance_dir,
        "state": instance_dir / "state.json",
        "leases": instance_dir / "leases",
        "log": instance_dir / "serena.log",
    }


@contextlib.contextmanager
def exclusive_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def try_exclusive_lock(path: Path) -> TextIO | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def process_command(pid: int) -> str:
    proc_cmdline = Path(f"/proc/{pid}/cmdline")
    if proc_cmdline.is_file():
        try:
            return (
                proc_cmdline.read_bytes()
                .replace(b"\0", b" ")
                .decode("utf-8", errors="replace")
            )
        except OSError:
            return ""
    result = subprocess.run(
        ["ps", "-ww", "-p", str(pid), "-o", "args="],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def process_start_token(pid: int) -> str:
    stat = Path(f"/proc/{pid}/stat")
    if stat.is_file():
        try:
            fields = stat.read_text(encoding="utf-8").split()
            return fields[21]
        except (OSError, IndexError):
            return ""
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart="],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    proc_stat = Path(f"/proc/{pid}/stat")
    if proc_stat.is_file():
        try:
            if proc_stat.read_text(encoding="utf-8").split()[2] == "Z":
                return False
        except (OSError, IndexError):
            pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    status = subprocess.run(
        ["ps", "-p", str(pid), "-o", "stat="],
        check=False,
        capture_output=True,
        text=True,
    )
    if status.returncode == 0 and status.stdout.lstrip().startswith("Z"):
        return False
    return True


def backend_matches(state: dict[str, Any]) -> bool:
    try:
        pid = int(state["pid"])
        port = int(state["port"])
        project_root = str(state["project_root"])
    except (KeyError, TypeError, ValueError):
        return False
    if not pid_alive(pid):
        return False
    command = process_command(pid)
    return (
        "serena" in command
        and "start-mcp-server" in command
        and str(port) in command
        and project_root in command
    )


def port_ready(port: int, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((HOST, port), timeout=timeout):
            return True
    except OSError:
        return False


def backend_healthy(state: dict[str, Any]) -> bool:
    return backend_matches(state) and port_ready(int(state["port"]))


def choose_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind((HOST, 0))
        return int(server.getsockname()[1])


def bounded_limit(limit_name: int, requested: int) -> tuple[int, int]:
    soft, hard = resource.getrlimit(limit_name)
    if requested <= 0:
        return soft, hard
    candidates = [requested]
    if soft != resource.RLIM_INFINITY and soft < 2**60:
        candidates.append(soft)
    if hard != resource.RLIM_INFINITY and hard < 2**60:
        candidates.append(hard)
    target = min(candidates)
    return target, target


def worktree_limits() -> dict[str, int]:
    return {
        "memory_mb": env_uint("SERENA_WORKTREE_MEMORY_MB", 1024),
        "open_files": env_uint("SERENA_WORKTREE_OPEN_FILES", 1024, minimum=64),
        "processes": env_uint("SERENA_WORKTREE_PROCESSES", 0, minimum=0),
        "cpu_seconds": env_uint("SERENA_WORKTREE_CPU_SECONDS", 0, minimum=0),
        "nice": env_uint("SERENA_WORKTREE_NICE", 10, minimum=0, maximum=19),
    }


def worktree_total_memory_mb() -> int:
    return env_uint("SERENA_WORKTREE_TOTAL_MEMORY_MB", 16384, minimum=1)


def resource_limiter(limits: dict[str, int]) -> Any:
    def apply() -> None:
        memory_bytes = limits["memory_mb"] * 1024 * 1024
        if (
            memory_bytes > 0
            and sys.platform.startswith("linux")
            and hasattr(resource, "RLIMIT_AS")
        ):
            resource.setrlimit(
                resource.RLIMIT_AS, bounded_limit(resource.RLIMIT_AS, memory_bytes)
            )
        resource.setrlimit(
            resource.RLIMIT_NOFILE,
            bounded_limit(resource.RLIMIT_NOFILE, limits["open_files"]),
        )
        if limits["processes"] > 0 and hasattr(resource, "RLIMIT_NPROC"):
            resource.setrlimit(
                resource.RLIMIT_NPROC,
                bounded_limit(resource.RLIMIT_NPROC, limits["processes"]),
            )
        if limits["cpu_seconds"] > 0 and hasattr(resource, "RLIMIT_CPU"):
            resource.setrlimit(
                resource.RLIMIT_CPU,
                bounded_limit(resource.RLIMIT_CPU, limits["cpu_seconds"]),
            )
        if limits["nice"] > 0:
            os.nice(limits["nice"])

    return apply


def idle_seconds(kind: str) -> int:
    name = (
        "SERENA_PRIMARY_IDLE_SECONDS"
        if kind == "primary"
        else "SERENA_WORKTREE_IDLE_SECONDS"
    )
    default = 1800 if kind == "primary" else 120
    return env_uint(name, default, minimum=1)


def startup_timeout() -> int:
    return env_uint("SERENA_POOL_STARTUP_SECONDS", 45, minimum=1)


def lease_alive(lease: dict[str, Any]) -> bool:
    try:
        pid = int(lease["pid"])
    except (KeyError, TypeError, ValueError):
        return False
    if not pid_alive(pid):
        return False
    token = str(lease.get("start_token", ""))
    return not token or process_start_token(pid) == token


def prune_leases(leases_dir: Path) -> list[Path]:
    if not leases_dir.is_dir():
        return []
    active: list[Path] = []
    for path in leases_dir.glob("*.json"):
        lease = read_json(path)
        if lease is not None and lease_alive(lease):
            active.append(path)
            continue
        with contextlib.suppress(OSError):
            path.unlink()
    return active


def terminate_backend(state: dict[str, Any], state_path: Path) -> None:
    if not backend_matches(state):
        with contextlib.suppress(OSError):
            state_path.unlink()
        return
    pid = int(state["pid"])
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, signal.SIGTERM)
    deadline = time.monotonic() + 5
    while pid_alive(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    if pid_alive(pid):
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pid, signal.SIGKILL)
    with contextlib.suppress(ChildProcessError):
        os.waitpid(pid, os.WNOHANG)
    with contextlib.suppress(OSError):
        state_path.unlink()


def process_group_rss_snapshot() -> dict[int, float]:
    result = subprocess.run(
        ["ps", "-axo", "pgid=,rss="],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {}
    rss_kb: dict[int, int] = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        try:
            pgid, rss = (int(field) for field in fields)
        except ValueError:
            continue
        rss_kb[pgid] = rss_kb.get(pgid, 0) + rss
    return {pgid: value / 1024 for pgid, value in rss_kb.items()}


def process_group_rss_mb(
    process_group: int, snapshot: dict[int, float] | None = None
) -> float:
    current = snapshot if snapshot is not None else process_group_rss_snapshot()
    return current.get(process_group, 0)


def append_log(state_path: Path, message: str) -> None:
    log_path = state_path.parent / "serena.log"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"serena-pool: {message}\n")


def prune_repo(repo_dir: Path) -> list[tuple[Path, dict[str, Any], list[Path]]]:
    active: list[tuple[Path, dict[str, Any], list[Path]]] = []
    if not repo_dir.is_dir():
        return active
    for state_path in repo_dir.glob("*/state.json"):
        state = read_json(state_path)
        if state is None or not backend_healthy(state):
            if state is not None:
                terminate_backend(state, state_path)
            else:
                with contextlib.suppress(OSError):
                    state_path.unlink()
            continue
        leases = prune_leases(state_path.parent / "leases")
        active.append((state_path, state, leases))
    return active


def prune_pool(pool_dir: Path) -> list[tuple[Path, dict[str, Any], list[Path]]]:
    active: list[tuple[Path, dict[str, Any], list[Path]]] = []
    if not pool_dir.is_dir():
        return active
    for state_path in pool_dir.glob("*/*/state.json"):
        state = read_json(state_path)
        if state is None or not backend_healthy(state):
            if state is not None:
                terminate_backend(state, state_path)
            else:
                with contextlib.suppress(OSError):
                    state_path.unlink()
            continue
        leases = prune_leases(state_path.parent / "leases")
        active.append((state_path, state, leases))
    return active


def worktree_in_use(state: dict[str, Any], leases: list[Path]) -> bool:
    protected_until = float(state.get("protected_until", 0))
    return bool(leases) or time.time() < protected_until


def worktree_rss(
    entry: tuple[Path, dict[str, Any], list[Path]],
    snapshot: dict[int, float] | None = None,
) -> float:
    return process_group_rss_mb(int(entry[1]["pid"]), snapshot)


def evict_idle_worktrees(
    worktrees: list[tuple[Path, dict[str, Any], list[Path]]],
    *,
    while_needed: Any,
    reason: str,
) -> list[tuple[Path, dict[str, Any], list[Path]]]:
    remaining = list(worktrees)
    idle = [item for item in remaining if not worktree_in_use(item[1], item[2])]
    idle.sort(key=lambda item: float(item[1].get("last_used", 0)))
    while while_needed(remaining) and idle:
        state_path, state, _ = idle.pop(0)
        append_log(state_path, reason)
        terminate_backend(state, state_path)
        remaining = [item for item in remaining if item[0] != state_path]
    return remaining


def enforce_worktree_capacity(repo_dir: Path, current_state_path: Path) -> None:
    maximum = env_uint("SERENA_WORKTREE_MAX_INSTANCES", 20, minimum=1)
    active = prune_repo(repo_dir)
    worktrees = [
        item
        for item in active
        if item[1].get("kind") == "worktree" and item[0] != current_state_path
    ]
    worktrees = evict_idle_worktrees(
        worktrees,
        while_needed=lambda entries: len(entries) >= maximum,
        reason=f"evicted idle backend at the {maximum}-instance repository limit",
    )

    if len(worktrees) >= maximum:
        roots = ", ".join(
            sorted(str(item[1].get("project_root")) for item in worktrees)
        )
        raise PoolError(
            f"Serena worktree capacity reached ({maximum}); active worktrees: {roots}"
        )


def enforce_worktree_memory_capacity(pool_dir: Path, current_state_path: Path) -> None:
    memory_budget = worktree_total_memory_mb()
    snapshot = process_group_rss_snapshot()
    worktrees = [
        item
        for item in prune_pool(pool_dir)
        if item[1].get("kind") == "worktree" and item[0] != current_state_path
    ]
    worktrees = evict_idle_worktrees(
        worktrees,
        while_needed=lambda entries: (
            sum(worktree_rss(item, snapshot) for item in entries) >= memory_budget
        ),
        reason=f"evicted idle backend at the {memory_budget} MiB global RSS budget",
    )
    total_rss = sum(worktree_rss(item, snapshot) for item in worktrees)
    if total_rss >= memory_budget:
        raise PoolError(
            "Serena global worktree memory budget reached "
            f"({total_rss:.1f} of {memory_budget} MiB in use)"
        )


def enforce_pool_memory_budget(
    worktrees: list[tuple[Path, dict[str, Any], list[Path]]],
    snapshot: dict[int, float],
) -> list[tuple[Path, dict[str, Any], list[Path]]]:
    remaining = []
    for item in worktrees:
        state_path, state, _ = item
        memory_mb = int((state.get("limits") or {}).get("memory_mb", 0))
        rss_mb = worktree_rss(item, snapshot)
        if memory_mb > 0 and rss_mb > memory_mb:
            append_log(
                state_path,
                f"stopped backend after RSS reached {rss_mb:.1f} MiB "
                f"(limit {memory_mb} MiB)",
            )
            terminate_backend(state, state_path)
            continue
        remaining.append(item)

    memory_budget = worktree_total_memory_mb()
    total_rss = sum(worktree_rss(item, snapshot) for item in remaining)
    if total_rss <= memory_budget:
        return remaining

    return evict_idle_worktrees(
        remaining,
        while_needed=lambda entries: (
            sum(worktree_rss(item, snapshot) for item in entries) > memory_budget
        ),
        reason=f"evicted idle backend because global worktree RSS exceeded "
        f"{memory_budget} MiB",
    )


def monitor_worktree_fleet(pool_dir: Path, current_state_path: Path) -> bool:
    with exclusive_lock(pool_dir / "pool.lock"):
        worktrees: list[tuple[Path, dict[str, Any], list[Path]]] = []
        for state_path in sorted(pool_dir.glob("*/*/state.json")):
            initial = read_json(state_path)
            if initial is None or initial.get("kind") != "worktree":
                continue
            repo_lock = state_path.parent.parent / "pool.lock"
            with exclusive_lock(repo_lock):
                state = read_json(state_path)
                if state is None or not backend_healthy(state):
                    if state is not None:
                        terminate_backend(state, state_path)
                    continue
                supervisor_pid = int(state.get("supervisor_pid", 0) or 0)
                if not pid_alive(supervisor_pid):
                    state["supervisor_pid"] = start_supervisor(state_path)
                    write_json(state_path, state)
                leases = prune_leases(state_path.parent / "leases")
                worktrees.append((state_path, state, leases))

        if all(item[0] != current_state_path for item in worktrees):
            return False
        snapshot = process_group_rss_snapshot()
        remaining = enforce_pool_memory_budget(worktrees, snapshot)
        return any(item[0] == current_state_path for item in remaining)


def serena_command(
    info: dict[str, Any], context: str, port: int
) -> tuple[list[str], str]:
    override = os.environ.get("SERENA_BIN")
    binary = override or shutil.which("serena")
    if not binary:
        raise PoolError("serena is not installed or not on PATH")
    command = [
        binary,
        "start-mcp-server",
        "--transport",
        "streamable-http",
        "--host",
        HOST,
        "--port",
        str(port),
        "--project",
        info["project_root"],
        "--context",
        context,
        "--open-web-dashboard",
        "false",
        "--enable-web-dashboard",
        "false",
    ]
    return command, binary


def start_supervisor(state_path: Path) -> int:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "supervise",
        str(state_path),
    ]
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    return process.pid


def start_backend(
    info: dict[str, Any], context: str, paths: dict[str, Path]
) -> dict[str, Any]:
    if info["kind"] == "worktree":
        enforce_worktree_capacity(paths["repo_dir"], paths["state"])
        enforce_worktree_memory_capacity(paths["home"], paths["state"])
        limits = worktree_limits()
    else:
        limits = {}

    paths["instance_dir"].mkdir(parents=True, exist_ok=True)
    paths["leases"].mkdir(parents=True, exist_ok=True)
    timeout = startup_timeout()
    last_error = ""

    for _ in range(3):
        port = choose_port()
        command, _ = serena_command(info, context, port)
        with paths["log"].open("ab") as log:
            try:
                process = subprocess.Popen(
                    command,
                    cwd=info["project_root"],
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    close_fds=True,
                    preexec_fn=resource_limiter(limits) if limits else None,
                )
            except subprocess.SubprocessError as exc:
                raise PoolError(
                    f"failed to apply Serena worktree resource limits: {exc}"
                ) from exc
        deadline = time.monotonic() + timeout
        while process.poll() is None and time.monotonic() < deadline:
            if port_ready(port):
                now = time.time()
                state: dict[str, Any] = {
                    **info,
                    "version": STATE_VERSION,
                    "pid": process.pid,
                    "port": port,
                    "url": f"http://{HOST}:{port}/mcp",
                    "context": context,
                    "limits": limits,
                    "started_at": now,
                    "last_used": now,
                    "protected_until": now + 10,
                    "idle_seconds": idle_seconds(info["kind"]),
                }
                write_json(paths["state"], state)
                state["supervisor_pid"] = start_supervisor(paths["state"])
                write_json(paths["state"], state)
                return state
            time.sleep(0.1)

        if process.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        last_error = (
            f"Serena exited with status {process.returncode}"
            if process.returncode is not None
            else f"Serena did not listen within {timeout} seconds"
        )

    raise PoolError(f"{last_error}; see {paths['log']}")


def ensure_backend(
    info: dict[str, Any], context: str, paths: dict[str, Path]
) -> dict[str, Any]:
    if info["kind"] == "worktree":
        with exclusive_lock(paths["pool_lock"]):
            return ensure_backend_locked(info, context, paths)
    return ensure_backend_locked(info, context, paths)


def ensure_backend_locked(
    info: dict[str, Any], context: str, paths: dict[str, Path]
) -> dict[str, Any]:
    with exclusive_lock(paths["repo_lock"]):
        state = read_json(paths["state"])
        if state is not None and backend_healthy(state):
            supervisor_pid = int(state.get("supervisor_pid", 0) or 0)
            if not pid_alive(supervisor_pid):
                state["supervisor_pid"] = start_supervisor(paths["state"])
            now = time.time()
            state["last_used"] = now
            state["protected_until"] = now + 10
            write_json(paths["state"], state)
            return state
        if state is not None:
            terminate_backend(state, paths["state"])
        return start_backend(info, context, paths)


def add_lease(paths: dict[str, Path]) -> Path:
    paths["leases"].mkdir(parents=True, exist_ok=True)
    lease_path = paths["leases"] / f"{os.getpid()}-{uuid.uuid4().hex}.json"
    write_json(
        lease_path,
        {
            "pid": os.getpid(),
            "start_token": process_start_token(os.getpid()),
            "created_at": time.time(),
        },
    )
    return lease_path


def release_lease(paths: dict[str, Path], lease_path: Path) -> None:
    with exclusive_lock(paths["repo_lock"]):
        with contextlib.suppress(OSError):
            lease_path.unlink()
        state = read_json(paths["state"])
        if state is not None:
            state["last_used"] = time.time()
            state["protected_until"] = 0
            write_json(paths["state"], state)


def proxy_command(url: str) -> list[str]:
    override = os.environ.get("SERENA_MCP_PROXY_COMMAND")
    if override:
        command = shlex.split(override)
    elif binary := shutil.which("mcp-proxy"):
        command = [binary]
    elif uvx := shutil.which("uvx"):
        command = [
            uvx,
            "--from",
            f"mcp-proxy=={PROXY_VERSION}",
            "--with",
            PROXY_MCP_CONSTRAINT,
            "mcp-proxy",
        ]
    else:
        raise PoolError("mcp-proxy or uvx is required for pooled Serena")
    return [*command, "--transport", "streamablehttp", url]


def run_proxy(url: str) -> int:
    process = subprocess.Popen(proxy_command(url))

    def forward(signum: int, _frame: Any) -> None:
        with contextlib.suppress(ProcessLookupError):
            process.send_signal(signum)

    previous = {
        signum: signal.signal(signum, forward)
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    }
    try:
        return process.wait()
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def connect() -> int:
    cwd = canonical(os.environ.get("SERENA_PROJECT_CWD", os.getcwd()))
    info = checkout(cwd)
    context = selected_context()
    paths = paths_for(info, context)
    state = ensure_backend(info, context, paths)
    lease_path = add_lease(paths)
    try:
        return run_proxy(str(state["url"]))
    finally:
        release_lease(paths, lease_path)


def supervise(state_path: Path) -> int:
    interval = float(os.environ.get("SERENA_POOL_SUPERVISOR_INTERVAL", "2"))
    if interval <= 0:
        raise PoolError("SERENA_POOL_SUPERVISOR_INTERVAL must be positive")
    repo_lock = state_path.parent.parent / "pool.lock"
    pool_dir = state_path.parent.parent.parent
    backend_pid = 0
    monitor_lock: TextIO | None = None

    try:
        while True:
            with exclusive_lock(repo_lock):
                state = read_json(state_path)
                if state is None:
                    return 0
                if backend_pid == 0:
                    backend_pid = int(state.get("pid", 0) or 0)
                if int(state.get("pid", 0) or 0) != backend_pid:
                    return 0
                if not backend_healthy(state):
                    terminate_backend(state, state_path)
                    return 0

                leases = prune_leases(state_path.parent / "leases")
                elapsed = time.time() - float(state.get("last_used", 0))
                idle = int(state.get("idle_seconds", 120))
                if not leases and elapsed >= idle:
                    terminate_backend(state, state_path)
                    return 0
                kind = str(state.get("kind", ""))

            if kind == "worktree":
                if monitor_lock is None:
                    monitor_lock = try_exclusive_lock(pool_dir / "monitor.lock")
                if monitor_lock is not None and not monitor_worktree_fleet(
                    pool_dir, state_path
                ):
                    return 0
            time.sleep(interval)
    finally:
        if monitor_lock is not None:
            monitor_lock.close()


def status() -> int:
    cwd = canonical(os.environ.get("SERENA_PROJECT_CWD", os.getcwd()))
    info = checkout(cwd)
    context = selected_context()
    paths = paths_for(info, context)
    with exclusive_lock(paths["repo_lock"]):
        state = read_json(paths["state"])
        if state is None or not backend_healthy(state):
            print(json.dumps({"running": False, **info}, sort_keys=True))
            return 1
        leases = prune_leases(paths["leases"])
        print(
            json.dumps(
                {
                    "running": True,
                    "clients": len(leases),
                    **state,
                },
                sort_keys=True,
            )
        )
        return 0


def stop() -> int:
    cwd = canonical(os.environ.get("SERENA_PROJECT_CWD", os.getcwd()))
    info = checkout(cwd)
    context = selected_context()
    paths = paths_for(info, context)
    with exclusive_lock(paths["repo_lock"]):
        state = read_json(paths["state"])
        if state is None:
            return 0
        leases = prune_leases(paths["leases"])
        if leases and os.environ.get("SERENA_POOL_FORCE_STOP") != "1":
            raise PoolError(f"Serena still has {len(leases)} attached client(s)")
        terminate_backend(state, paths["state"])
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action")
    subparsers.add_parser("connect", help="connect stdio to the checkout's pool")
    subparsers.add_parser("status", help="show the checkout's pool status")
    subparsers.add_parser("stop", help="stop an idle checkout pool")
    supervisor = subparsers.add_parser("supervise", help=argparse.SUPPRESS)
    supervisor.add_argument("state_path", type=Path)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        if args.action in (None, "connect"):
            return connect()
        if args.action == "status":
            return status()
        if args.action == "stop":
            return stop()
        if args.action == "supervise":
            return supervise(args.state_path)
        raise PoolError(f"unknown action: {args.action}")
    except PoolError as exc:
        print(f"serena-pool: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
