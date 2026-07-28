"""Coverage for the PreToolUse spawn model-routing gate.

This guard denies, so its negative cases carry the weight: an explicit model, a
subagent type that pins one, a Codex profile that pins both model and effort, and
any unreadable payload all have to pass. A gate that blocks correct delegation is
worse than none, because the fallback is no delegation at all.

Ported from a bats suite that ran as the parity oracle first: the Python guard
reproduced all 30 of its behavioural cases before the suite was replaced. The
thirty-first checked `bash -n` on the script, which no longer applies.

Codex profiles are written into a tmp_path so the tests describe precedence rules
rather than the machine's installed agents.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parent.parent / "scripts" / "subagent-model-guard.py"


def run_guard(
    payload: object,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str | None, str]:
    """Run the guard; return (exit code, decision or None, reason text)."""
    if isinstance(payload, dict) and cwd is not None:
        payload = {**payload, "cwd": cwd}
    body = payload if isinstance(payload, str) else json.dumps(payload)

    import os

    environment = dict(os.environ)
    # A stray real CODEX_HOME would let the machine's own profiles answer for the
    # fixture, so every test gets an explicit one.
    environment.setdefault("CODEX_HOME", "/nonexistent-codex-home")
    if env:
        environment.update(env)

    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=body,
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )
    if not result.stdout.strip():
        return result.returncode, None, ""
    out = json.loads(result.stdout)["hookSpecificOutput"]
    return result.returncode, out["permissionDecision"], out.get("permissionDecisionReason", "")


def write_codex_agent(
    root: Path, name: str, model: str = "", effort: str = "", *, literal: bool = False
) -> None:
    """Write an agent profile, in basic or literal TOML string style."""
    quote = "'" if literal else '"'
    directory = root / ".codex" / "agents"
    directory.mkdir(parents=True, exist_ok=True)
    lines = [f"name = {quote}{name}{quote}", f"description = {quote}Test{quote}"]
    if model:
        lines.append(f"model = {quote}{model}{quote}")
    if effort:
        lines.append(f"model_reasoning_effort = {quote}{effort}{quote}")
    lines.append(f"developer_instructions = {quote}Work{quote}")
    (directory / f"{name}.toml").write_text("\n".join(lines) + "\n")


# --- Claude: what must pass ---------------------------------------------------


@pytest.mark.parametrize(
    "tool_input",
    [
        pytest.param({"model": "haiku", "subagent_type": "general-purpose"}, id="model-set"),
        pytest.param({"model": "opus"}, id="model-set-no-type"),
        pytest.param({"subagent_type": "workflow-coder"}, id="pinned-type-coder"),
        pytest.param({"subagent_type": "pr-reviewer"}, id="pinned-type-reviewer"),
    ],
)
def test_a_resolved_model_is_allowed(tool_input: dict) -> None:
    code, decision, _ = run_guard({"tool_name": "Agent", "tool_input": tool_input})

    assert code == 0
    assert decision is None, "an explicit or pinned model must pass silently"


# --- Claude: the types that inherit ------------------------------------------


@pytest.mark.parametrize(
    "subagent_type",
    [
        pytest.param("general-purpose", id="general-purpose"),
        pytest.param("Explore", id="explore"),
        pytest.param("Plan", id="plan"),
        pytest.param("claude", id="claude"),
        pytest.param("fork", id="fork"),
    ],
)
def test_an_inheriting_type_without_a_model_is_denied(subagent_type: str) -> None:
    code, decision, reason = run_guard(
        {"tool_name": "Agent", "tool_input": {"subagent_type": subagent_type}}
    )

    assert code == 0
    assert decision == "deny"
    assert "inherits the session model" in reason


def test_no_type_and_no_model_is_denied() -> None:
    _, decision, reason = run_guard({"tool_name": "Agent", "tool_input": {}})

    assert decision == "deny"
    assert "inherits the session model" in reason


def test_the_denial_tells_the_caller_what_to_do_instead() -> None:
    """A denial is agent-facing: it must name the corrected form, not just refuse."""
    _, _, reason = run_guard({"tool_name": "Agent", "tool_input": {}})

    assert "agent_type" in reason
    assert "model:" in reason
    # The task-specific type comes first, because it ships a pin.
    assert reason.index("agent_type") < reason.index("explicit model")
    assert "haiku" not in reason, "haiku is not an option this guard offers"
    assert len(reason.splitlines()) <= 4, "a denial the agent reads must stay terse"


# --- Claude: the inherit list is per-project overridable ---------------------


def test_an_override_can_add_a_type() -> None:
    _, decision, _ = run_guard(
        {"tool_name": "Agent", "tool_input": {"subagent_type": "custom-thing"}},
        env={"SUBAGENT_MODEL_GUARD_INHERIT_TYPES": "custom-thing"},
    )

    assert decision == "deny"


def test_an_override_can_remove_a_type() -> None:
    _, decision, _ = run_guard(
        {"tool_name": "Agent", "tool_input": {"subagent_type": "general-purpose"}},
        env={"SUBAGENT_MODEL_GUARD_INHERIT_TYPES": "something-else"},
    )

    assert decision is None


def test_an_override_list_tolerates_spaces() -> None:
    _, decision, _ = run_guard(
        {"tool_name": "Agent", "tool_input": {"subagent_type": "b"}},
        env={"SUBAGENT_MODEL_GUARD_INHERIT_TYPES": "a, b , c"},
    )

    assert decision == "deny"


# --- Codex: a named role must pin both model and effort ----------------------


def codex_spawn(agent_type: str) -> dict:
    """A Codex-shaped payload: `agent_type` is what marks it as one."""
    return {"tool_name": "Agent", "tool_input": {"agent_type": agent_type}}


@pytest.mark.parametrize("literal", [False, True], ids=["basic-strings", "literal-strings"])
def test_a_pinned_project_profile_is_allowed(tmp_path: Path, literal: bool) -> None:
    write_codex_agent(tmp_path, "researcher", "opus", "high", literal=literal)

    _, decision, _ = run_guard(codex_spawn("researcher"), cwd=str(tmp_path))

    assert decision is None


@pytest.mark.parametrize("literal", [False, True], ids=["basic-strings", "literal-strings"])
def test_a_pinned_global_profile_is_allowed(tmp_path: Path, literal: bool) -> None:
    home = tmp_path / "home"
    write_codex_agent(home, "researcher", "opus", "high", literal=literal)
    project = tmp_path / "project"
    project.mkdir()

    _, decision, _ = run_guard(
        codex_spawn("researcher"),
        cwd=str(project),
        env={"CODEX_HOME": str(home / ".codex")},
    )

    assert decision is None


def test_an_incomplete_project_profile_shadows_a_pinned_global_one(tmp_path: Path) -> None:
    """Precedence is project-first even when the project profile is worse.

    Silently falling through to the global pin would hide a broken project profile.
    """
    home = tmp_path / "home"
    write_codex_agent(home, "researcher", "opus", "high")
    project = tmp_path / "project"
    write_codex_agent(project, "researcher")  # no model, no effort

    _, decision, reason = run_guard(
        codex_spawn("researcher"),
        cwd=str(project),
        env={"CODEX_HOME": str(home / ".codex")},
    )

    assert decision == "deny"
    assert "shadows lower-precedence profiles" in reason


def test_an_unknown_codex_agent_type_is_denied(tmp_path: Path) -> None:
    _, decision, reason = run_guard(codex_spawn("nonexistent"), cwd=str(tmp_path))

    assert decision == "deny"
    assert "no project or global custom profile" in reason


def test_a_default_codex_agent_is_denied_with_create_guidance(tmp_path: Path) -> None:
    _, decision, reason = run_guard(codex_spawn("default"), cwd=str(tmp_path))

    assert decision == "deny"
    assert "No installed agent profiles were found" in reason


def test_a_default_codex_agent_lists_the_installed_catalog(tmp_path: Path) -> None:
    write_codex_agent(tmp_path, "researcher", "opus", "high")
    write_codex_agent(tmp_path, "scribe", "sonnet", "low")

    _, decision, reason = run_guard(codex_spawn("default"), cwd=str(tmp_path))

    assert decision == "deny"
    assert "researcher (opus/high)" in reason
    assert "scribe (sonnet/low)" in reason


def test_an_ad_hoc_codex_model_requires_an_opt_in(tmp_path: Path) -> None:
    payload = {
        "tool_name": "Agent",
        "tool_input": {"agent_type": "default", "model": "opus", "reasoning_effort": "high"},
    }

    _, denied, _ = run_guard(payload, cwd=str(tmp_path))
    _, allowed, _ = run_guard(
        payload, cwd=str(tmp_path), env={"SUBAGENT_MODEL_GUARD_ALLOW_AD_HOC": "1"}
    )

    assert denied == "deny", "without the opt-in an ad-hoc spawn is refused"
    assert allowed is None, "the opt-in must actually permit it"


# --- fail open ---------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("", id="empty"),
        pytest.param("not json {", id="malformed"),
        pytest.param("[]", id="not-an-object"),
        pytest.param('{"tool_name":"Bash","tool_input":{"command":"ls"}}', id="not-a-spawn"),
    ],
)
def test_unusable_input_allows(payload: str) -> None:
    code, decision, _ = run_guard(payload)

    assert code == 0
    assert decision is None


def test_a_bare_string_tool_input_is_still_judged() -> None:
    """A string payload carries no model, so the spawn would inherit one."""
    code, decision, _ = run_guard({"tool_name": "Agent", "tool_input": "do a thing"})

    assert code == 0
    assert decision == "deny"


def test_the_task_tool_name_is_also_a_spawn() -> None:
    """Both names are observed for a spawn across harnesses."""
    _, decision, _ = run_guard({"tool_name": "Task", "tool_input": {}})

    assert decision == "deny"


def test_an_unreadable_profile_reads_as_unpinned(tmp_path: Path) -> None:
    """A profile with a TOML syntax error must not be accepted as pinned.

    The shell version's hand-rolled scanner could half-parse one; tomllib rejects
    it outright, which is the safer direction.
    """
    directory = tmp_path / ".codex" / "agents"
    directory.mkdir(parents=True)
    (directory / "broken.toml").write_text('name = "broken\nmodel = opus\n')

    _, decision, _ = run_guard(codex_spawn("broken"), cwd=str(tmp_path))

    assert decision == "deny"
