#!/usr/bin/env python3
"""gh-api.py — Rate-limited GitHub API wrapper.

Thin proxy around the `gh` CLI that mechanically enforces GitHub's rate limits:
- 1s minimum between mutative requests
- 80 content-creating requests per minute
- 500 content-creating requests per hour
- Retry with backoff on 403/429/5xx
- File-locked state for multi-agent safety

Usage:
    gh-api.py gh <any gh args...>                # Passthrough (auto-classifies read/mutate)
    gh-api.py rest <METHOD> <path> [--data JSON]  # REST via gh api
    gh-api.py graphql -f query='...'              # GraphQL via gh api graphql
    gh-api.py graphql --query-file <path>         # GraphQL from file
    gh-api.py batch < operations.jsonl            # Sequential batch from stdin
    gh-api.py check                               # Show rate limit status
    gh-api.py help                                # Show this help
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

XDG_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
STATE_DIR = XDG_CONFIG_HOME / "agentic-tools" / "tmp"
STATE_FILE = STATE_DIR / "gh-rate-state.json"
LOCK_FILE = STATE_DIR / "gh-rate.lock"

MIN_MUTATE_INTERVAL = 1.0       # seconds between mutative requests
MAX_PER_MINUTE = 78             # slightly under 80 for safety margin
MAX_PER_HOUR = 490              # slightly under 500 for safety margin
MAX_CONSECUTIVE_403 = 3         # hard stop after this many
MAX_RETRIES = 4                 # for 5xx backoff
DEFAULT_RETRY_AFTER = 60        # seconds when no retry-after header

# gh subcommands that are read-only
READ_ONLY_ACTIONS = frozenset({
    "list", "view", "status", "checks", "diff", "search", "watch", "download",
})

# gh top-level commands that are always read-only or local
READ_ONLY_COMMANDS = frozenset({
    "auth", "config", "help", "version", "status",
    "ssh-key", "gpg-key", "completion",
})

# gh top-level commands where we check the action
RESOURCE_COMMANDS = frozenset({
    "issue", "pr", "release", "label", "project", "run", "repo",
    "gist", "secret", "variable", "cache", "ruleset",
})

# gh project subcommands that are read-only
PROJECT_READ_ONLY = frozenset({
    "list", "view", "item-list", "field-list",
})

# REST methods that are mutative
MUTATIVE_METHODS = frozenset({"POST", "PATCH", "PUT", "DELETE"})


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg: str):
    print(f"[gh-api] {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# State management (file-locked for multi-agent safety)
# ---------------------------------------------------------------------------

def ensure_state_dir():
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {"timestamps": []}
    except (json.JSONDecodeError, OSError):
        return {"timestamps": []}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def prune_timestamps(state: dict, now: float) -> dict:
    cutoff = now - 3600
    state["timestamps"] = [t for t in state["timestamps"] if t > cutoff]
    return state


def count_recent(timestamps: list[float], now: float, window: float) -> int:
    cutoff = now - window
    return sum(1 for t in timestamps if t > cutoff)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def is_mutative_gh(args: list[str]) -> bool:
    """Classify a gh CLI command as mutative. Conservative: unknown = mutative."""
    if not args:
        return True

    top = args[0]

    # Local-only commands
    if top in READ_ONLY_COMMANDS:
        return False

    # gh api — always treated as mutative (GraphQL or REST mutation)
    if top == "api":
        return True

    # gh project — special subcommand names
    if top == "project":
        action = args[1] if len(args) > 1 else ""
        return action not in PROJECT_READ_ONLY

    # gh run — mostly read-only
    if top == "run":
        action = args[1] if len(args) > 1 else ""
        return action not in {"list", "view", "watch", "download"}

    # Standard resource commands: gh <resource> <action>
    if top in RESOURCE_COMMANDS and len(args) > 1:
        return args[1] not in READ_ONLY_ACTIONS

    # Unknown = mutative
    return True


# ---------------------------------------------------------------------------
# Throttling
# ---------------------------------------------------------------------------

def throttle_if_needed(state: dict, now: float) -> float:
    """Enforce rate limits. Returns the time after any required sleeping."""
    timestamps = state["timestamps"]

    # Per-minute cap
    per_minute = count_recent(timestamps, now, 60)
    if per_minute >= MAX_PER_MINUTE:
        recent = [t for t in timestamps if t > now - 60]
        oldest = min(recent)
        wait = 60 - (now - oldest) + 0.5
        log(f"rate: {per_minute}/{MAX_PER_MINUTE} per minute — sleeping {wait:.1f}s")
        time.sleep(wait)
        now = time.time()

    # Per-hour cap
    per_hour = count_recent(timestamps, now, 3600)
    if per_hour >= MAX_PER_HOUR:
        recent = [t for t in timestamps if t > now - 3600]
        oldest = min(recent)
        wait = 3600 - (now - oldest) + 0.5
        log(f"rate: {per_hour}/{MAX_PER_HOUR} per hour — sleeping {wait:.1f}s")
        time.sleep(wait)
        now = time.time()

    # Minimum interval between mutative requests
    if timestamps:
        elapsed = now - max(timestamps)
        if elapsed < MIN_MUTATE_INTERVAL:
            time.sleep(MIN_MUTATE_INTERVAL - elapsed)
            now = time.time()

    return now


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def run_gh(args: list[str], input_data: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["gh"] + args,
        input=input_data,
        capture_output=True,
        text=True,
    )


def execute_with_retry(
    gh_args: list[str],
    input_data: str | None = None,
    *,
    mutative: bool = True,
) -> int:
    """Execute a gh command with rate limiting and retry. Returns exit code."""
    ensure_state_dir()

    # Read-only: pass through immediately
    if not mutative:
        result = run_gh(gh_args, input_data)
        sys.stdout.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
        return result.returncode

    # Mutative: lock → throttle → execute → record → unlock
    consecutive_403 = 0
    retries = 0

    while True:
        with open(LOCK_FILE, "w") as lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                state = load_state()
                now = time.time()
                state = prune_timestamps(state, now)
                now = throttle_if_needed(state, now)

                result = run_gh(gh_args, input_data)

                state["timestamps"].append(time.time())
                save_state(state)
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)

        # Success
        if result.returncode == 0:
            sys.stdout.write(result.stdout)
            if result.stderr:
                sys.stderr.write(result.stderr)
            return 0

        # Classify error
        stderr_lower = result.stderr.lower()
        is_rate_limited = any(s in stderr_lower for s in ("403", "429", "rate limit", "secondary", "abuse"))
        is_server_error = any(f"{c}" in stderr_lower for c in range(500, 600))

        # Rate limit → retry with wait
        if is_rate_limited:
            consecutive_403 += 1
            if consecutive_403 >= MAX_CONSECUTIVE_403:
                log(f"CRITICAL: {consecutive_403} consecutive rate limit errors — aborting to prevent ban")
                sys.stdout.write(result.stdout)
                sys.stderr.write(result.stderr)
                return 2

            # Try to extract retry-after duration
            wait = DEFAULT_RETRY_AFTER
            for line in result.stderr.splitlines():
                if "retry" in line.lower():
                    m = re.search(r"(\d+)", line)
                    if m:
                        wait = int(m.group(1))
                        break

            log(f"rate limited (attempt {consecutive_403}/{MAX_CONSECUTIVE_403}) — waiting {wait}s")
            time.sleep(wait)
            continue

        # Server error → exponential backoff
        if is_server_error and retries < MAX_RETRIES:
            retries += 1
            wait = 2 ** retries
            log(f"server error (retry {retries}/{MAX_RETRIES}) — backoff {wait}s")
            time.sleep(wait)
            continue

        # Non-retryable error
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        return result.returncode


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_gh(args: list[str]) -> int:
    """Passthrough: wraps any gh CLI command with rate limiting."""
    mutative = is_mutative_gh(args)
    if mutative:
        log(f"mutative: gh {' '.join(args[:3])}...")
    return execute_with_retry(args, mutative=mutative)


def cmd_rest(args: list[str]) -> int:
    """REST API call via gh api."""
    if len(args) < 2:
        log("usage: gh-api.py rest <METHOD> <path> [--data JSON]")
        return 1

    method = args[0].upper()
    path = args[1]

    # Parse --data flag
    data = None
    i = 2
    while i < len(args):
        if args[i] == "--data" and i + 1 < len(args):
            data = args[i + 1]
            i += 2
        else:
            i += 1

    gh_args = ["api", path, "--method", method]
    input_data = None
    if data:
        gh_args.extend(["--input", "-"])
        input_data = data

    return execute_with_retry(gh_args, input_data=input_data, mutative=method in MUTATIVE_METHODS)


def _graphql_is_mutation(args: list[str]) -> bool:
    """Check if GraphQL args contain a mutation. Conservative: unknown = mutative."""
    for i, arg in enumerate(args):
        if arg == "-f" and i + 1 < len(args):
            val = args[i + 1]
            if val.startswith("query="):
                query_text = val[6:].strip()
                # Queries start with "query", "query{", or bare "{" (anonymous query)
                if query_text.startswith(("query ", "query{", "{")):
                    return False
        if arg == "--query-file" and i + 1 < len(args):
            try:
                query_text = Path(args[i + 1]).read_text().strip()
                if query_text.startswith(("query ", "query{", "{")):
                    return False
            except OSError:
                pass
    return True


def cmd_graphql(args: list[str]) -> int:
    """GraphQL call via gh api graphql. Mutations throttled, queries pass through."""
    gh_args = ["api", "graphql"]
    mutative = _graphql_is_mutation(args)

    i = 0
    while i < len(args):
        if args[i] == "--query-file" and i + 1 < len(args):
            query = Path(args[i + 1]).read_text()
            gh_args.extend(["-f", f"query={query}"])
            i += 2
        else:
            gh_args.append(args[i])
            i += 1

    if mutative:
        log("mutative: graphql mutation")
    return execute_with_retry(gh_args, mutative=mutative)


def cmd_batch() -> int:
    """Batch mode: read JSONL from stdin, execute sequentially with throttling."""
    dispatch = {"rest": _batch_rest, "graphql": _batch_graphql, "gh": _batch_gh}
    errors = 0
    count = 0

    for line_num, line in enumerate(sys.stdin, 1):
        line = line.strip()
        if not line:
            continue

        try:
            op = json.loads(line)
        except json.JSONDecodeError as e:
            log(f"batch line {line_num}: invalid JSON — {e}")
            errors += 1
            continue

        op_type = op.get("type", "")
        handler = dispatch.get(op_type)
        if not handler:
            log(f"batch line {line_num}: unknown type '{op_type}'")
            errors += 1
            continue

        count += 1
        log(f"batch [{count}]: {op_type}")

        rc = handler(op)
        if rc == 2:
            log(f"batch aborted at line {line_num} — rate limit hard stop")
            return 2
        elif rc != 0:
            errors += 1
            log(f"batch [{count}]: failed (exit {rc})")

    log(f"batch complete: {count} operations, {errors} errors")
    return 1 if errors > 0 else 0


def _batch_rest(op: dict) -> int:
    method = op.get("method", "POST")
    path = op.get("path", "")
    data = op.get("data")
    args = [method, path]
    if data:
        args.extend(["--data", json.dumps(data)])
    return cmd_rest(args)


def _batch_graphql(op: dict) -> int:
    return cmd_graphql(["-f", f"query={op.get('query', '')}"])


def _batch_gh(op: dict) -> int:
    return cmd_gh(op.get("args", []))


def cmd_check() -> int:
    """Show current rate limit status (GitHub API + local tracking)."""
    result = run_gh(["api", "rate_limit"])
    if result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            core = data.get("resources", {}).get("core", {})
            graphql = data.get("resources", {}).get("graphql", {})
            print(json.dumps({
                "github": {
                    "rest": {"remaining": core.get("remaining"), "limit": core.get("limit"), "reset": core.get("reset")},
                    "graphql": {"remaining": graphql.get("remaining"), "limit": graphql.get("limit"), "reset": graphql.get("reset")},
                }
            }, indent=2))
        except json.JSONDecodeError:
            sys.stdout.write(result.stdout)
    else:
        sys.stderr.write(result.stderr)
        return result.returncode

    # Local state
    ensure_state_dir()
    state = load_state()
    now = time.time()
    state = prune_timestamps(state, now)
    per_min = count_recent(state["timestamps"], now, 60)
    per_hr = count_recent(state["timestamps"], now, 3600)
    print(json.dumps({
        "local": {
            "mutative_last_minute": per_min,
            "mutative_last_hour": per_hr,
            "minute_cap": MAX_PER_MINUTE,
            "hour_cap": MAX_PER_HOUR,
        }
    }, indent=2))
    return 0


def cmd_help() -> int:
    print(__doc__)
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

COMMANDS = {
    "gh": cmd_gh,
    "rest": cmd_rest,
    "graphql": cmd_graphql,
    "batch": lambda _: cmd_batch(),
    "check": lambda _: cmd_check(),
    "help": lambda _: cmd_help(),
    "--help": lambda _: cmd_help(),
    "-h": lambda _: cmd_help(),
}


def main() -> int:
    if len(sys.argv) < 2:
        return cmd_help()

    subcmd = sys.argv[1]
    handler = COMMANDS.get(subcmd)

    if handler is None:
        log(f"unknown subcommand: {subcmd}")
        return cmd_help()

    # Commands that take args vs commands that don't
    if subcmd in ("gh", "rest", "graphql"):
        return handler(sys.argv[2:])
    else:
        return handler(None)


if __name__ == "__main__":
    sys.exit(main())
