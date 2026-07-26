#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Activate orchestrate enforcement before the lead can invoke a tool."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

INVOCATION_RE = re.compile(r"^\s*(?:/|\$)orchestrate(?:\s|$)")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


def emit(value: dict) -> None:
    sys.stdout.write(json.dumps(value) + "\n")


def prompt_text(payload: dict) -> str:
    for key in ("prompt", "user_prompt", "message", "input"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""


def marker_path() -> Path:
    configured = os.environ.get("ORCHESTRATE_MARKER_FILE")
    if configured:
        return Path(configured)
    return Path(".orchestration") / ".active-run"


def existing_run_id(path: Path) -> str:
    if not path.is_file():
        return "pending"
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return "pending"
    if not raw:
        return "pending"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(data, dict):
        return str(data.get("run_id") or "pending")
    return "pending"


def write_marker(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def activate(payload: dict) -> None:
    path = marker_path()
    state = {
        "schema_version": 1,
        "run_id": existing_run_id(path),
        "session_id": str(payload.get("session_id") or payload.get("thread_id") or "unknown"),
    }
    try:
        write_marker(path, state)
    except OSError as exc:
        emit(
            {
                "decision": "block",
                "reason": f"orchestrate run enforcement could not activate: {exc}",
            }
        )
        return
    emit({})


def bind_run(run_id: str) -> int:
    if not RUN_ID_RE.fullmatch(run_id):
        sys.stderr.write("run id must be a Beads identifier\n")
        return 2
    path = marker_path()
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"cannot read active-run marker: {exc}\n")
        return 2
    if not isinstance(state, dict):
        sys.stderr.write("active-run marker must be a JSON object\n")
        return 2
    current = str(state.get("run_id") or "pending")
    if current not in {"pending", run_id}:
        sys.stderr.write(f"active-run marker is already bound to {current!r}\n")
        return 2
    state.update({"schema_version": 1, "run_id": run_id})
    try:
        write_marker(path, state)
    except OSError as exc:
        sys.stderr.write(f"cannot bind active-run marker: {exc}\n")
        return 2
    return 0


def main() -> int:
    if len(sys.argv) > 1:
        if len(sys.argv) == 3 and sys.argv[1] == "bind":
            return bind_run(sys.argv[2])
        sys.stderr.write("usage: orchestrator-run-activate.py [bind <run-id>]\n")
        return 2
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, TypeError):
        emit({})
        return 0
    if not isinstance(payload, dict) or not INVOCATION_RE.match(prompt_text(payload)):
        emit({})
        return 0
    activate(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
