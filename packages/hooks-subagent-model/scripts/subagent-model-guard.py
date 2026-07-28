#!/usr/bin/env python3
"""Deny a subagent spawn that would silently inherit an expensive parent model.

The parent session often runs a top-tier model. A spawn that omits `model` and
names a subagent type with no pinned model in its definition inherits whatever the
parent is running, so expensive capacity goes to work a cheaper tier would do.

Codex policy: a named semantic role must resolve project-first, then globally, to a
custom agent TOML pinning both `model` and `model_reasoning_effort`. A project
profile deliberately shadows a same-named global one even when incomplete. Ad-hoc
and default agents are denied, because the hook cannot infer role instructions from
task prose.

Claude policy: allow an explicit model, or a subagent type whose definition pins
one; deny the types known to inherit.

The inherit-by-default list is small and overridable per project through
SUBAGENT_MODEL_GUARD_INHERIT_TYPES, so a project can add its own unpinned types
without waiting for a package release.

Ported from shell, where the profile reader was a hand-rolled TOML string parser --
40 lines tracking quote style and escape state by hand. `tomllib` is in the
standard library and reads the real grammar, so the whole class of parse gap goes
away. Fail-open on anything unreadable: a broken guard must never block delegation.
"""

from __future__ import annotations

import sys

# Only `sys` at module scope. This is a PreToolUse hook, and the overwhelming
# majority of calls are not spawns, so the bail in main() runs before anything
# expensive is imported.

# Both names are observed for a spawn across harnesses.
SPAWN_TOOLS = frozenset({"Agent", "Task"})

# Types with no pinned model in their definition: an unspecified spawn rides
# whatever the parent session runs.
DEFAULT_INHERIT_TYPES = "general-purpose,Explore,Plan,claude,fork"

# Fields whose presence marks the payload as Codex-shaped rather than Claude-shaped.
CODEX_MARKERS = ("agent_type", "task_name", "fork_turns", "reasoning_effort")

# How many profiles to name in a deny message. A catalog listing exists to help the
# agent choose, and an unbounded list stops being readable.
CATALOG_LIMIT = 12

CLAUDE_REASON = (
    "This agent type inherits the session model. Re-issue with either:\n"
    "- a task-specific agent_type from the available agent types (preferred -- "
    "they ship a model pin), or\n"
    "- an explicit model: opus, or sonnet for mechanical reading (log/metric "
    "summarising, lint and doc gathering, diff smoke checks)."
)


def deny(reason: str) -> None:
    import json

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )


def profile_fields(path) -> dict:
    """Read one agent profile's scalar metadata, or {} when it cannot be read.

    `tomllib` replaces the shell version's hand-rolled string scanner. It also
    means a profile with a syntax error reads as empty rather than as a partially
    parsed set of values, which is the safer failure here: an unreadable profile
    should be reported as unpinned, not silently accepted.
    """
    import tomllib

    try:
        with open(path, "rb") as handle:
            data = tomllib.load(handle)
    except (OSError, ValueError, tomllib.TOMLDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def agent_directories(cwd):
    """Every `.codex/agents` directory in scope, project-first then global.

    Project ancestry outranks the global directory so a project profile shadows a
    same-named global one.
    """
    import os

    from pathlib import Path

    start = Path(cwd) if cwd and Path(cwd).is_dir() else Path.cwd()
    try:
        start = start.resolve()
    except OSError:
        pass

    for directory in (start, *start.parents):
        yield directory / ".codex" / "agents"

    codex_home = os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
    yield Path(codex_home) / "agents"


def find_profile(cwd: str, wanted: str):
    """The highest-precedence profile whose `name` matches, or None."""
    for directory in agent_directories(cwd):
        if not directory.is_dir():
            continue
        for profile in sorted(directory.glob("*.toml")):
            fields = profile_fields(profile)
            if fields.get("name") == wanted:
                return profile, fields
    return None


def installed_catalog(cwd: str) -> list[str]:
    """Installed profiles as display strings, project profiles shadowing global."""
    seen: dict[str, str] = {}
    for directory in agent_directories(cwd):
        if not directory.is_dir():
            continue
        for profile in sorted(directory.glob("*.toml")):
            fields = profile_fields(profile)
            name = fields.get("name")
            if not isinstance(name, str) or not name or name in seen:
                continue
            model = fields.get("model")
            effort = fields.get("model_reasoning_effort")
            if model and effort:
                seen[name] = f"{name} ({model}/{effort})"
            elif model:
                seen[name] = f"{name} ({model})"
            else:
                seen[name] = name
    return [seen[name] for name in sorted(seen)][:CATALOG_LIMIT]


def extract(payload: str) -> dict:
    """Pull the fields this guard judges from a hook payload."""
    import json

    data = json.loads(payload)
    if not isinstance(data, dict):
        return {}
    tool_input = data.get("tool_input")
    fields = tool_input if isinstance(tool_input, dict) else {}

    def text(*names: str) -> str:
        for name in names:
            value = fields.get(name)
            if isinstance(value, str) and value and value != "null":
                return value
        return ""

    return {
        "tool": data.get("tool_name") or "",
        "cwd": data.get("cwd") if isinstance(data.get("cwd"), str) else "",
        "model": text("model"),
        "effort": text("reasoning_effort", "model_reasoning_effort"),
        "subagent_type": text("agent_type", "subagent_type"),
        "is_codex": any(marker in fields for marker in CODEX_MARKERS),
    }


def judge_codex(spawn: dict) -> str | None:
    """The Codex policy: a named role pinning both model and effort, or nothing."""
    import os

    subagent_type = spawn["subagent_type"]

    if not subagent_type or subagent_type == "default":
        if (
            os.environ.get("SUBAGENT_MODEL_GUARD_ALLOW_AD_HOC") == "1"
            and spawn["model"]
            and spawn["effort"]
        ):
            return None
        catalog = installed_catalog(spawn["cwd"])
        if catalog:
            return (
                "Codex agent selection blocked: choose a configured agent_type "
                "instead of default/ad-hoc delegation. Choose a configured "
                f"agent_type from the installed catalog: {', '.join(catalog)}. Pick "
                "the profile whose role best matches the task. Each selected "
                "profile must pin both model and model_reasoning_effort."
            )
        return (
            "Codex agent selection blocked: choose a configured agent_type instead "
            "of default/ad-hoc delegation. No installed agent profiles were found. "
            "Define a project or global agent profile in .codex/agents/ that pins "
            "model and model_reasoning_effort, then retry with its name as "
            "agent_type."
        )

    found = find_profile(spawn["cwd"], subagent_type)
    if found is None:
        return (
            f"Codex agent selection blocked: agent_type '{subagent_type}' has no "
            "project or global custom profile. Choose an available semantic agent "
            "whose profile pins model and model_reasoning_effort; do not fall back "
            "to an inherited/default agent."
        )

    profile, fields = found
    if not fields.get("model") or not fields.get("model_reasoning_effort"):
        return (
            f"Codex agent selection blocked: '{profile}' shadows lower-precedence "
            "profiles but does not pin both model and model_reasoning_effort. "
            "Regenerate it from its package agent-models.yml, then retry with the "
            "semantic agent_type."
        )
    return None


def judge_claude(spawn: dict) -> str | None:
    """The Claude policy: an explicit model, or a type that pins one."""
    import os

    if spawn["model"]:
        return None

    configured = os.environ.get("SUBAGENT_MODEL_GUARD_INHERIT_TYPES")
    raw = configured if configured else DEFAULT_INHERIT_TYPES
    inherit_types = {item.strip() for item in raw.split(",") if item.strip()}

    subagent_type = spawn["subagent_type"]
    if subagent_type and subagent_type not in inherit_types:
        return None
    return CLAUDE_REASON


def main() -> int:
    payload = sys.stdin.read()
    if not payload.strip():
        return 0

    try:
        spawn = extract(payload)
    except (ValueError, TypeError):
        return 0
    if spawn.get("tool") not in SPAWN_TOOLS:
        return 0

    reason = judge_codex(spawn) if spawn["is_codex"] else judge_claude(spawn)
    if reason:
        deny(reason)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open: a broken guard must never block all delegation.
        raise SystemExit(0)
