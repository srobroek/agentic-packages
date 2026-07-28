"""Coverage for subagent-fork-guard.py -- the PreToolUse:Agent fork_turns deny
gate -- and subagent-fork-inject.py -- the SubagentStart discipline digest.

Ported from tests/guards.bats (bats suite deleted per contract rule 4: parity
proven against it before porting).

Guard contract (Codex-shaped spawns: payload has task_name/agent_type/
fork_turns/fork_context; Claude spawns pass through untouched):
  * fork_turns omitted on a Codex spawn        -> deny (omitted == "all")
  * fork_turns "none" / number <= max          -> allow (no output)
  * fork_turns "all"                           -> deny + corrected format
  * numeric fork_turns > max (default 3)       -> deny + corrected format
  * SUBAGENT_FORK_GUARD_MAX overrides the cap; junk override falls back to 3
  * Claude spawn shapes, non-spawn tools, malformed stdin
    -> allow (fail-open / out of scope)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
GUARD = PKG / "scripts" / "subagent-fork-guard.py"
INJECT = PKG / "scripts" / "subagent-fork-inject.py"


def run_guard(payload: str, env: dict | None = None) -> tuple[int, str]:
    import os

    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        env=full_env,
    )
    return result.returncode, result.stdout


def decision_of(output: str) -> str:
    if not output.strip():
        return ""
    return json.loads(output)["hookSpecificOutput"].get("permissionDecision", "")


def reason_of(output: str) -> str:
    if not output.strip():
        return ""
    return json.loads(output)["hookSpecificOutput"].get("permissionDecisionReason", "")


def run_inject(payload: str, env: dict | None = None) -> str:
    import os

    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    result = subprocess.run(
        [sys.executable, str(INJECT)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        env=full_env,
    )
    return result.stdout


# --- allow -------------------------------------------------------------------


def test_claude_spawn_shape_allows():
    status, output = run_guard(
        '{"tool_name":"Agent","tool_input":{"subagent_type":"coder","prompt":"do x","model":"sonnet"}}'
    )
    assert status == 0
    assert output == ""


def test_fork_turns_omitted_on_codex_spawn_denies():
    status, output = run_guard('{"tool_name":"Agent","tool_input":{"task_name":"code-reviewer"}}')
    assert status == 0
    assert decision_of(output) == "deny"
    reason = reason_of(output)
    assert "omitted" in reason
    assert 'fork_turns="none"' in reason


def test_fork_turns_none_allows():
    status, output = run_guard(
        '{"tool_name":"Agent","tool_input":{"task_name":"code-reviewer","fork_turns":"none"}}'
    )
    assert status == 0
    assert output == ""


def test_fork_turns_2_numeric_json_allows():
    status, output = run_guard('{"tool_name":"Agent","tool_input":{"task_name":"x","fork_turns":2}}')
    assert status == 0
    assert output == ""


def test_fork_turns_3_string_at_cap_allows():
    status, output = run_guard('{"tool_name":"Agent","tool_input":{"task_name":"x","fork_turns":"3"}}')
    assert status == 0
    assert output == ""


def test_non_spawn_tool_allows_even_with_fork_turns_all():
    status, output = run_guard('{"tool_name":"Bash","tool_input":{"command":"echo fork_turns=all"}}')
    assert status == 0
    assert output == ""


# --- deny --------------------------------------------------------------------


def test_fork_turns_all_denies_with_corrected_format():
    status, output = run_guard(
        '{"tool_name":"Agent","tool_input":{"task_name":"code-reviewer","fork_turns":"all"}}'
    )
    assert status == 0
    assert decision_of(output) == "deny"
    reason = reason_of(output)
    assert 'fork_turns="none"' in reason
    assert 'spawn_agent(task_name="code-reviewer", fork_turns="none")' in reason


def test_fork_turns_4_above_default_denies():
    _, output = run_guard('{"tool_name":"Agent","tool_input":{"task_name":"x","fork_turns":4}}')
    assert decision_of(output) == "deny"


def test_fork_turns_100_string_denies():
    _, output = run_guard('{"tool_name":"Agent","tool_input":{"task_name":"x","fork_turns":"100"}}')
    assert decision_of(output) == "deny"


def test_task_tool_alias_also_guarded():
    _, output = run_guard('{"tool_name":"Task","tool_input":{"task_name":"x","fork_turns":"all"}}')
    assert decision_of(output) == "deny"


# --- override ------------------------------------------------------------------


def test_override_max_10_allows_8():
    _, output = run_guard(
        '{"tool_name":"Agent","tool_input":{"task_name":"x","fork_turns":8}}',
        {"SUBAGENT_FORK_GUARD_MAX": "10"},
    )
    assert output == ""


def test_override_max_1_denies_2():
    _, output = run_guard(
        '{"tool_name":"Agent","tool_input":{"task_name":"x","fork_turns":2}}',
        {"SUBAGENT_FORK_GUARD_MAX": "1"},
    )
    assert decision_of(output) == "deny"


def test_junk_override_falls_back_to_3_denies_4():
    _, output = run_guard(
        '{"tool_name":"Agent","tool_input":{"task_name":"x","fork_turns":4}}',
        {"SUBAGENT_FORK_GUARD_MAX": "banana"},
    )
    assert decision_of(output) == "deny"


# --- fail-open -----------------------------------------------------------------


def test_empty_stdin_allows():
    status, output = run_guard("")
    assert status == 0
    assert output == ""


def test_malformed_json_allows():
    status, output = run_guard("{not json")
    assert status == 0
    assert output == ""


def test_tool_input_as_bare_string_allows_no_crash():
    status, output = run_guard('{"tool_name":"Agent","tool_input":"spawn something"}')
    assert status == 0
    assert output == ""


def test_fork_turns_0_allows_zero_turn_boundary():
    status, output = run_guard('{"tool_name":"Agent","tool_input":{"task_name":"x","fork_turns":0}}')
    assert status == 0
    assert output == ""


def test_fork_turns_json_null_denies_treated_as_omitted():
    _, output = run_guard('{"tool_name":"Agent","tool_input":{"task_name":"x","fork_turns":null}}')
    assert decision_of(output) == "deny"


# --- inject --------------------------------------------------------------------


def test_inject_subagent_gets_fork_turns_discipline():
    output = run_inject('{"agent_id":"abc123","agent_type":"coder"}')
    ctx = json.loads(output)["hookSpecificOutput"]["additionalContext"]
    assert 'fork_turns="none"' in ctx
    assert 'spawn_agent(task_name="code-reviewer", fork_turns="none")' in ctx


def test_inject_non_subagent_no_agent_id_no_output():
    output = run_inject('{"session_id":"s1"}')
    assert output == ""


def test_inject_digest_respects_override():
    output = run_inject(
        '{"agent_id":"abc","agent_type":"coder"}', {"SUBAGENT_FORK_GUARD_MAX": "7"}
    )
    ctx = json.loads(output)["hookSpecificOutput"]["additionalContext"]
    assert "above 7" in ctx
