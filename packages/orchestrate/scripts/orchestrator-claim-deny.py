#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""PreToolUse hook — orchestrator claim prohibition (run-marker gated).

T0 (the orchestrator session) never claims beads; it routes. This hook denies
any `bd ... --claim` issued while an orchestrate run is active. The run marker
(env ORCHESTRATE_RUN or ./.orchestration/.active-run) scopes it so ordinary
interactive sessions are untouched. ORCHESTRATE_RUN only arms the hook;
ORCHESTRATE_RUN_ID names the run bead whose status can retire it.

On an allowed worker claim it also snapshots the bead's metadata as of the
claim into metadata.claim_metadata_baseline, which is what lets the
SubagentStop evaluator tell a value the role wrote from one another actor
stamped before the claim (astro-plan-indxl).

Decision: a PreToolUse deny with a diagnosis-only message. Fails open on
malformed input. Invoked directly via `uv run`.
Contract: specs/002-bead-as-brief/contracts/hook-io.md
"""

import json
import os
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrate_run_marker import (  # noqa: E402
    BD,
    emit_allow,
    emit_deny,
    marker_present,
    show_bead,
)

CLAIM_BASELINE_KEY = "claim_metadata_baseline"
# Global flags that consume the next token, which would otherwise read as the
# subcommand or the bead id.
VALUE_FLAGS = frozenset({"-C", "--actor", "--db", "--directory", "--dolt-auto-commit"})

DENY_MSG = (
    "orchestrators route work, they never claim beads; only a worker command "
    "carrying matching BEADS_ACTOR and BD_ACTOR identities may claim"
)
VARIABLE_REF_RE = re.compile(r"^\$(?:([A-Za-z_][A-Za-z0-9_]*)|\{([A-Za-z_][A-Za-z0-9_]*)\})$")
LEAD_ACTOR_RE = re.compile(r"(?:^|[/.:_-])(lead|orchestrator|root|t0)(?:$|[/.:_-])", re.I)
WORKER_ACTOR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*[-/][A-Za-z0-9._/-]+$")


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


def claim_bead_ids(segment: list[str]) -> list[str]:
    """Bead ids in `bd [flags] <subcommand> <id...> --claim`.

    `bd update` takes `[id...]` and claims every one of them, so every
    positional after the subcommand is a candidate. A positional that is really
    a subcommand flag value resolves to no bead and is skipped by the caller.
    """
    start = next((i for i, t in enumerate(segment) if os.path.basename(t) == "bd"), -1)
    if start < 0:
        return []
    positionals: list[str] = []
    skip = False
    for token in segment[start + 1 :]:
        if skip:
            skip = False
            continue
        if token in VALUE_FLAGS:
            skip = True
            continue
        if token.startswith("-"):
            continue
        positionals.append(token)
    return positionals[1:]


def bead_metadata(bead_id: str) -> dict[str, str] | None:
    payload = show_bead(bead_id, timeout=8)
    if payload is None:
        return None
    metadata = payload.get("metadata")
    return dict(metadata) if isinstance(metadata, dict) else {}


def snapshot_claim_baseline(command: str) -> None:
    """Record each claimed bead's pre-claim metadata.

    Best effort: an absent snapshot degrades the stop-time authority check to
    presence, which is the behaviour that predates it. The first snapshot for a
    bead wins; a later claim of the same bead leaves it alone, so an idempotent
    re-claim cannot re-baseline a key the role wrote after the first claim.
    """
    for segment in shell_segments(command):
        if not segment_invokes_bd_claim(segment):
            continue
        for bead_id in claim_bead_ids(segment):
            metadata = bead_metadata(bead_id)
            if metadata is None:
                continue
            if metadata.get(CLAIM_BASELINE_KEY):
                continue
            metadata.pop(CLAIM_BASELINE_KEY, None)
            try:
                subprocess.run(
                    [
                        BD,
                        "update",
                        bead_id,
                        "--metadata",
                        json.dumps({CLAIM_BASELINE_KEY: json.dumps(metadata, sort_keys=True)}),
                    ],
                    capture_output=True,
                    timeout=8,
                )
            except Exception:
                continue


def main():
    if not marker_present():
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

    if not invokes_bd_claim(cmd):
        emit_allow()
    if has_worker_actor_envelope(cmd):
        try:
            snapshot_claim_baseline(cmd)
        except Exception:
            pass
        emit_allow()

    emit_deny(DENY_MSG)


if __name__ == "__main__":
    main()
