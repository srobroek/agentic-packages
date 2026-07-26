#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""PreToolUse hook — orchestrator claim prohibition (run-marker gated).

T0 (the orchestrator session) never claims beads; it routes. This hook denies
any `bd ... --claim` issued while an orchestrate run is active. The run marker
(env ORCHESTRATE_RUN or ./.orchestration/.active-run) scopes it so ordinary
interactive sessions are untouched.

Decision: a PreToolUse deny with a diagnosis-only message. Fails open on
malformed input. Invoked directly via `uv run`.
Contract: specs/002-bead-as-brief/contracts/hook-io.md
"""

import json
import os
import re
import shlex
import sys

DENY_MSG = (
    "orchestrators route work, they never claim beads; only a worker command "
    "carrying matching BEADS_ACTOR and BD_ACTOR identities may claim"
)
VARIABLE_REF_RE = re.compile(r"^\$(?:([A-Za-z_][A-Za-z0-9_]*)|\{([A-Za-z_][A-Za-z0-9_]*)\})$")
LEAD_ACTOR_RE = re.compile(r"(?:^|[/.:_-])(lead|orchestrator|root|t0)(?:$|[/.:_-])", re.I)
WORKER_ACTOR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*[-/][A-Za-z0-9._/-]+$")


def emit_allow():
    sys.stdout.write("{}\n")
    sys.exit(0)


def run_active() -> bool:
    if os.environ.get("ORCHESTRATE_RUN"):
        return True
    marker = os.environ.get("ORCHESTRATE_MARKER_FILE", "")
    if marker and os.path.isfile(marker):
        return True
    return os.path.isfile("./.orchestration/.active-run")


def shell_segments(command: str) -> list[list[str]]:
    """Return shell command segments without interpreting quoted payload text."""
    segments: list[list[str]] = []
    command = command.replace("\\\n", " ")
    for line in command.splitlines() or [command]:
        try:
            lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|")
            lexer.whitespace_split = True
            lexer.commenters = ""
            tokens = list(lexer)
        except ValueError:
            continue
        current: list[str] = []
        for token in tokens:
            if token and not set(token).difference(";&|"):
                if current:
                    segments.append(current)
                    current = []
                continue
            current.append(token)
        if current:
            segments.append(current)
    return segments


def is_assignment(token: str) -> bool:
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", token))


def claim_envelope(segment: list[str]) -> dict[str, str] | None:
    values: dict[str, str] = {}
    index = 0
    while index < len(segment) and is_assignment(segment[index]):
        key, value = segment[index].split("=", 1)
        values[key] = value
        index += 1
    if index < len(segment) and segment[index] == "env":
        index += 1
        while index < len(segment):
            if is_assignment(segment[index]):
                key, value = segment[index].split("=", 1)
                values[key] = value
            elif not segment[index].startswith("-"):
                break
            index += 1
    if index < len(segment) and segment[index] in {"command", "builtin"}:
        index += 1
    if index >= len(segment) or os.path.basename(segment[index]) != "bd":
        return None
    if "--claim" not in segment[index + 1 :]:
        return None
    return values


def segment_invokes_bd_claim(segment: list[str]) -> bool:
    return claim_envelope(segment) is not None


def invokes_bd_claim(command: str) -> bool:
    return any(segment_invokes_bd_claim(segment) for segment in shell_segments(command))


def update_shell_assignments(segment: list[str], variables: dict[str, str]) -> bool:
    tokens = segment[1:] if segment and segment[0] == "export" else segment
    if not tokens or not all(is_assignment(token) for token in tokens):
        return False
    for token in tokens:
        key, value = token.split("=", 1)
        variables[key] = value
    return True


def resolve_actor(value: str | None, variables: dict[str, str]) -> str:
    if not value:
        return ""
    match = VARIABLE_REF_RE.fullmatch(value)
    if not match:
        return value
    return variables.get(match.group(1) or match.group(2), "")


def valid_worker_actor(actor: str) -> bool:
    return bool(actor and WORKER_ACTOR_RE.fullmatch(actor) and not LEAD_ACTOR_RE.search(actor))


def has_worker_actor_envelope(command: str) -> bool:
    variables: dict[str, str] = {}
    claim_count = 0
    for segment in shell_segments(command):
        if update_shell_assignments(segment, variables):
            continue
        values = claim_envelope(segment)
        if values is None:
            continue
        claim_count += 1
        scope = {**variables, **values}
        beads_actor = resolve_actor(values.get("BEADS_ACTOR"), scope)
        bd_actor = resolve_actor(values.get("BD_ACTOR"), scope)
        if not beads_actor or beads_actor != bd_actor:
            return False
        if not valid_worker_actor(beads_actor):
            return False
    return claim_count > 0


def main():
    if not run_active():
        emit_allow()  # not in a run -> never interfere
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        emit_allow()

    ti = payload.get("tool_input") or {}
    cmd = ti.get("command") if isinstance(ti, dict) else None
    cmd = cmd or (ti if isinstance(ti, str) else "") or payload.get("input", {}).get("command", "")
    if not cmd:
        emit_allow()

    if not invokes_bd_claim(cmd) or has_worker_actor_envelope(cmd):
        emit_allow()

    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": DENY_MSG,
                }
            }
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
