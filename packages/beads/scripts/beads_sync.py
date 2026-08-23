"""Shared helpers for the beads sync hooks. Imported, never run directly.

Ported from beads-sync-lib.sh, which was sourced by three scripts. The shell
version's helpers were thin wrappers over `bd` and `git`; what is preserved here is
the reasoning each one encodes, because that reasoning is the expensive part.

Every function fails toward "do nothing": a sync hook that cannot determine state
must not block a session or invent a verdict.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

# Truthy spellings accepted for a `bd config` opt-in flag.
TRUTHY = frozenset({"true", "1", "yes", "on"})

# Outcomes of a push-policy probe.
PUSH_PERMITTED = 0
PUSH_REFUSED = 1
PUSH_NO_VERDICT = 2

# Remote messages that mean "no answer" rather than "refused". Git resolves the
# host BEFORE running pre-push hooks, so an unreachable URL yields no verdict
# either way.
TRANSIENT_MARKERS = (
    "could not resolve host",
    "unable to access",
    "connection refused",
    "could not read from remote",
    "timed out",
    "terminated",
)

# Messages that mean a push from here is durably refused. The refused/no-verdict
# split matters: a refusal calls for a different route, an unreachable remote calls
# for retrying later. Collapsing them would advise changing a sync strategy over a
# dropped connection.
REFUSAL_MARKERS = (
    "pre-push hook declined",
    "blocked your push",
    "not currently on the allow list",
)

# bd reads these to stay non-interactive and unpaged inside a hook.
BD_ENV = {"BD_NO_PAGER": "1", "BD_NON_INTERACTIVE": "1"}


def run(
    command: list[str],
    *,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
    stdout_to=None,
) -> subprocess.CompletedProcess[str] | None:
    """Run a command, returning None when it cannot run or exceeds its bound.

    Replaces the shell's `beads_bounded`, which shelled out to `timeout` and fell
    back to `gtimeout`, then to running unbounded when neither existed -- so on a
    stock macOS host without coreutils the bound silently disappeared and a hung
    Dolt network call could hang a session start. `subprocess` takes the timeout
    directly, so the bound always applies.
    """
    merged = None
    if env:
        merged = dict(os.environ)
        merged.update(env)
    try:
        return subprocess.run(
            command,
            capture_output=stdout_to is None,
            stdout=stdout_to,
            stderr=subprocess.DEVNULL if stdout_to is not None else None,
            text=True,
            check=False,
            timeout=timeout,
            env=merged,
            cwd=cwd,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def bd_available() -> bool:
    """Whether the bd CLI is on PATH."""
    return shutil.which("bd") is not None


def beads_dir(cwd: str) -> str:
    """Path of the active .beads directory, or empty when there is no workspace."""
    result = run(["bd", "-C", cwd, "where"], timeout=15)
    if result is None or result.returncode != 0:
        return ""
    first = result.stdout.strip().splitlines()
    if not first:
        return ""
    candidate = first[0].strip()
    return candidate if candidate and os.path.isdir(candidate) else ""


def opt(cwd: str, key: str) -> bool:
    """Whether a `bd config` key is set to a truthy value."""
    result = run(["bd", "-C", cwd, "config", "get", key], timeout=15)
    if result is None or result.returncode != 0:
        return False
    return result.stdout.strip().lower() in TRUTHY


def config(cwd: str, key: str) -> str:
    """Value of a `bd config` key, or empty when unset.

    bd prints a "not set" sentence rather than failing for a missing key, so that
    phrasing has to be treated as empty. The shell version pattern-matched
    `*"not set"*` for the same reason.
    """
    result = run(["bd", "-C", cwd, "config", "get", key], timeout=15)
    if result is None or result.returncode != 0:
        return ""
    value = result.stdout.strip()
    return "" if not value or "not set" in value.lower() else value


def has_dolt_remote(cwd: str) -> bool:
    """Whether a Dolt remote is configured."""
    result = run(["bd", "-C", cwd, "dolt", "remote", "list"], timeout=30)
    if result is None or result.returncode != 0:
        return False
    output = result.stdout.strip()
    return bool(output) and "no remotes configured" not in output.lower()


def envelope(raw: str):
    """Unwrap a BD_JSON_ENVELOPE payload to the data object it carries.

    bd wraps output as {"data": {...}} under BD_JSON_ENVELOPE and returns the bare
    object without it, so both shapes have to be accepted -- the shell version did
    this with `(.data // .)` in every jq expression.
    """
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    data = parsed.get("data")
    return data if isinstance(data, dict) else parsed


def export_all(cwd: str, destination: str, *, timeout: float = 120) -> bool:
    """Write a full bead export to destination. True only on a non-empty export.

    An empty export means something went wrong; treating it as success would let a
    caller overwrite a good committed file with nothing.
    """
    try:
        with open(destination, "w", encoding="utf-8") as handle:
            result = run(
                ["bd", "-C", cwd, "export", "--all"],
                timeout=timeout,
                env=BD_ENV,
                stdout_to=handle,
            )
    except OSError:
        return False
    if result is None or result.returncode != 0:
        return False
    try:
        return os.path.getsize(destination) > 0
    except OSError:
        return False


def push_permitted(cwd: str, timeout: float = 30) -> int:
    """Whether a push from here would go through.

    Probes with `git push --dry-run`, which runs the same pre-push path as a real
    push while transferring nothing and mutating no remote.

    Reads the outcome from the MESSAGE, not the exit status: a dry run exits
    non-zero for many ordinary reasons (no upstream, unreachable network, nothing
    to push), so status alone cannot separate a refusal from "try later".
    """
    inside = run(["git", "-C", cwd, "rev-parse", "--git-dir"], timeout=10)
    if inside is None or inside.returncode != 0:
        return PUSH_NO_VERDICT
    origin = run(["git", "-C", cwd, "remote", "get-url", "origin"], timeout=10)
    if origin is None or origin.returncode != 0:
        return PUSH_NO_VERDICT

    probe = run(
        [
            "git",
            "-C",
            cwd,
            "push",
            "--dry-run",
            "origin",
            "HEAD:refs/heads/beads-sync-probe",
        ],
        timeout=timeout,
    )
    if probe is None:
        # Timed out or could not start: transient by definition.
        return PUSH_NO_VERDICT

    combined = f"{probe.stdout}\n{probe.stderr}".lower()
    if any(marker in combined for marker in TRANSIENT_MARKERS):
        return PUSH_NO_VERDICT
    if any(marker in combined for marker in REFUSAL_MARKERS):
        return PUSH_REFUSED
    return PUSH_PERMITTED


def payload(raw: str) -> dict:
    """Hook payload as a dict, empty when it is missing or unparseable."""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def payload_cwd(raw: str, default: str) -> str:
    """Directory the hook should act on, from the payload with a fallback."""
    candidate = payload(raw).get("cwd")
    if isinstance(candidate, str) and candidate and os.path.isdir(candidate):
        return candidate
    return default


def is_subagent(raw: str) -> bool:
    """Whether the payload describes a spawned subagent rather than the operator."""
    return bool(payload(raw).get("agent_id"))


def memory_prefixes() -> list[str]:
    """Memory key prefixes this actor may receive, from BEADS_MEMORY_PREFIXES.

    Spawn-time env rather than `bd config`, because two actors sharing one workspace
    need different prefixes. `global-` is recall-only and belongs in no actor's list.
    """
    raw = os.environ.get("BEADS_MEMORY_PREFIXES", "")
    return [part for part in (item.strip() for item in raw.split(",")) if part]


def memories(cwd: str, prefixes: list[str], *, timeout: float = 10) -> dict[str, str]:
    """Memories whose KEY starts with one of prefixes.

    Scoping happens here, on the key, over the full map: `bd memories <term>` matches
    CONTENT as well as keys, so a memory whose body merely mentions a prefix comes
    back, and `bd prime --memories-only` is unfiltered entirely.

    Returns {} on any failure including the bound -- the call measured 1.67s, and
    injecting nothing beats failing a session start.
    """
    if not prefixes:
        return {}
    result = run(["bd", "-C", cwd, "memories", "--json"], timeout=timeout, env=BD_ENV)
    if result is None or result.returncode != 0:
        return {}
    data = envelope(result.stdout)
    if not data:
        return {}
    # Flat key:content map carrying a schema_version stamp at the same level.
    return {
        key: value
        for key, value in data.items()
        if key != "schema_version"
        and isinstance(value, str)
        and any(key.startswith(prefix) for prefix in prefixes)
    }


def render_memories(selected: dict[str, str]) -> str:
    """One text block for the selected memories, empty when there are none."""
    if not selected:
        return ""
    lines = "\n".join(f"- {key}: {value}" for key, value in sorted(selected.items()))
    return (
        "Scoped beads memories (update in place with `bd remember --key <key>`):\n"
        + lines
    )


def emit(event: str, context: str) -> None:
    """Print a hook advisory for the given event."""
    import sys

    json.dump(
        {"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}},
        sys.stdout,
    )
    sys.stdout.write("\n")
