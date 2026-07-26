#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Enforce two-phase claim-holder spawn and resource-bound activation."""

import json
import os
import re
import subprocess
import sys

CLAIM_HOLDERS = {
    "advisor",
    "researcher",
    "reviewer",
    "scribe",
    "shepherd",
}
# Non-claim-holder types a run may dispatch freely: read-only helpers and the
# bundled quality guards. Anything outside both sets is unrecognised, and an
# unrecognised type must not silently skip activation -- see unguarded_dispatch.
EPHEMERAL_AGENTS = {
    "Explore",
    "Plan",
    "data-metrics-summarizer",
    "docs-guard",
    "general-purpose",
    "lint-guard",
    "maintenance-metrics-reader",
    "reviewer-mechanics",
}
RESOURCE_TOKEN = r"[A-Za-z0-9][A-Za-z0-9._:-]*"
QUEUE_TOKEN = r"[A-Za-z0-9][A-Za-z0-9._:=+-]*"
CLAIM_RE = re.compile(rf"^CLAIM (?P<resource>{RESOURCE_TOKEN})$")
QUEUE_CLAIM_RE = re.compile(rf"^CLAIM queue:(?P<queue>{QUEUE_TOKEN})$")
CHECKOUT_WAIT_RE = re.compile(
    rf"^WAIT checkout=(?P<checkout>/[^\n]+)\n"
    rf"RESOURCE (?P<resource>{RESOURCE_TOKEN})\n"
    r"Do not invoke tools or start work\.\n"
    rf"The controlling parent will release you with exactly CLAIM "
    rf"(?P=resource)\.$"
)
QUEUE_WAIT_RE = re.compile(
    rf"^WAIT checkout=(?P<checkout>/[^\n]+)\n"
    rf"QUEUE (?P<queue>{QUEUE_TOKEN})\n"
    r"Do not invoke tools or start work\.\n"
    rf"The controlling parent will release you with exactly CLAIM "
    rf"queue:(?P=queue)\.$"
)
BD = os.environ.get("BD_BIN", "bd")


def emit_allow() -> None:
    sys.stdout.write("{}\n")
    raise SystemExit(0)


def emit_deny(reason: str) -> None:
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
        + "\n"
    )
    raise SystemExit(0)


def run_active() -> bool:
    if os.environ.get("ORCHESTRATE_RUN"):
        return True
    marker = os.environ.get("ORCHESTRATE_MARKER_FILE", "")
    if marker and os.path.isfile(marker):
        return True
    return os.path.isfile("./.orchestration/.active-run")


def active_run_id() -> str:
    marker = os.environ.get("ORCHESTRATE_MARKER_FILE", "")
    path = marker or "./.orchestration/.active-run"
    try:
        value = json.loads(open(path, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError, TypeError):
        return ""
    if isinstance(value, dict):
        return str(value.get("run_id") or "")
    return ""


def require_bound_run() -> None:
    if active_run_id() == "pending":
        emit_deny(
            "claim-holder dispatch is blocked until the active-run marker is "
            "bound to the created run epic"
        )


def claim_holder(agent_type: str) -> bool:
    return agent_type in CLAIM_HOLDERS or agent_type.startswith("domain-specialist")


def unguarded_dispatch(agent_type: str) -> None:
    """Deny a task-bearing spawn whose agent type the contract does not recognise.

    A literal claim-holder set cannot enumerate every agent a harness resolves, so
    an unrecognised name used to skip activation entirely. A stale `workflow-*`
    agent left installed by an older release ran a whole fixture that way: the
    WAIT grammar, resource liveness, exact-CLAIM routing and bound-marker checks
    all no-opped because the type matched nothing. Fail closed instead, and name
    the recognised alternatives so the lead can self-correct.
    """
    emit_deny(
        f"agent type {agent_type!r} is not a recognised orchestrate role, so its "
        "activation cannot be verified. Dispatch a claim-holder role "
        "(domain-specialist, researcher, reviewer, advisor, scribe, shepherd) "
        "through the two-phase WAIT/CLAIM contract, or an ephemeral read-only "
        "helper. A stale agent from an older release resolves in the harness but "
        "is unknown to this contract."
    )


def metadata(record: dict) -> dict:
    value = record.get("metadata") or {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def load_resource(resource_id: str) -> dict | None:
    try:
        proc = subprocess.run(
            [BD, "show", resource_id, "--json"],
            capture_output=True,
            text=True,
            timeout=10,
            env={
                **os.environ,
                "BD_JSON_ENVELOPE": "1",
                "BD_NO_PAGER": "1",
                "BD_NON_INTERACTIVE": "1",
            },
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        value = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    if isinstance(value, dict) and "data" in value:
        value = value["data"]
    if isinstance(value, list):
        value = value[0] if value else None
    return value if isinstance(value, dict) else None


def require_live_resource(resource_id: str) -> dict:
    record = load_resource(resource_id)
    if record is None:
        emit_deny(f"CLAIM resource {resource_id!r} is not a live Beads bead or wisp")
    if str(record.get("status") or "").lower() in {"closed", "tombstone"}:
        emit_deny(f"CLAIM resource {resource_id!r} is terminal")
    return record


def validate_wait(prompt: str) -> None:
    queue_match = QUEUE_WAIT_RE.fullmatch(prompt)
    if queue_match:
        return
    match = CHECKOUT_WAIT_RE.fullmatch(prompt)
    if not match:
        emit_deny(
            "claim-holder spawn must contain only the canonical WAIT bootstrap; "
            "task data and activation authority belong on a Beads resource"
        )
    resource_id = match.group("resource")
    record = require_live_resource(resource_id)
    if record.get("assignee"):
        emit_deny(f"WAIT resource {resource_id!r} is already claimed")
    checkout = match.group("checkout")
    resource_metadata = metadata(record)
    stamped_checkout = str(resource_metadata.get("worktree") or "")
    lease = resource_metadata.get("lease_token")
    if not stamped_checkout or os.path.realpath(stamped_checkout) != os.path.realpath(checkout):
        emit_deny(f"WAIT checkout does not match resource {resource_id!r}")
    if not lease:
        emit_deny(f"WAIT resource {resource_id!r} has no prepared lease")


def runtime_recipient(tool_input: dict) -> str:
    for key in ("to", "recipient", "target", "agent_id", "id", "thread_id"):
        value = tool_input.get(key)
        if value:
            return str(value)
    return ""


def validate_claim(message: str, tool_input: dict) -> None:
    if QUEUE_CLAIM_RE.fullmatch(message):
        return
    match = CLAIM_RE.fullmatch(message)
    if not match:
        emit_deny(
            "claim activation must contain only CLAIM resource-id; do not "
            "combine WAIT, task data, commands, or repair instructions with it"
        )
    resource_id = match.group("resource")
    record = require_live_resource(resource_id)
    recipient = runtime_recipient(tool_input)
    resource_metadata = metadata(record)
    stamped_handle = str(resource_metadata.get("runtime_handle") or "")
    stamped_context = str(resource_metadata.get("runtime_context") or "")
    if not stamped_handle:
        emit_deny(f"CLAIM resource {resource_id!r} has no bound runtime handle")
    if not stamped_context:
        emit_deny(f"CLAIM resource {resource_id!r} has no hook context handshake")
    if not recipient or stamped_handle != recipient:
        emit_deny(f"CLAIM resource {resource_id!r} is not bound to the target runtime handle")


def main() -> None:
    if not run_active():
        emit_allow()
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        emit_allow()

    tool_name = str(payload.get("tool_name") or payload.get("tool") or "")
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        emit_allow()

    if tool_name in {"Agent", "Task", "spawn_agent", "agents.spawn_agent"}:
        agent_type = str(
            tool_input.get("subagent_type")
            or tool_input.get("agent_type")
            or tool_input.get("role")
            or ""
        )
        if not claim_holder(agent_type):
            if agent_type and agent_type not in EPHEMERAL_AGENTS:
                unguarded_dispatch(agent_type)
            emit_allow()
        require_bound_run()
        prompt = str(tool_input.get("prompt") or tool_input.get("message") or "")
        validate_wait(prompt.strip())
        emit_allow()

    if tool_name in {
        "SendMessage",
        "send_message",
        "agents.send_message",
        "followup_task",
        "agents.followup_task",
        "send_input",
        "agents.send_input",
        "multi_agent_v1send_input",
    }:
        message = str(
            tool_input.get("message") or tool_input.get("content") or tool_input.get("prompt") or ""
        ).strip()
        if "CLAIM" not in message:
            emit_allow()
        require_bound_run()
        validate_claim(message, tool_input)
    emit_allow()


if __name__ == "__main__":
    main()
