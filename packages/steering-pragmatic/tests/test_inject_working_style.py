"""Tests for the steering-pragmatic SubagentStart injector.

Ported from tests/pragmatic.bats (contract rule 4: keep the existing suite as
the oracle when porting a guard to Python).
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "inject-working-style.py"


def run_hook(stdin: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin,
        capture_output=True,
        text=True,
    )


def test_subagent_payload_yields_valid_json():
    result = run_hook('{"agent_id":"a1","agent_type":"coder","cwd":"/whatever"}')
    assert result.returncode == 0
    json.loads(result.stdout)


def test_carries_mandatory_header_and_every_must_rule():
    result = run_hook('{"agent_id":"a1","agent_type":"coder","cwd":"/x"}')
    assert result.returncode == 0
    ctx = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "MANDATORY WORKING STYLE" in ctx
    assert "override suggestions embedded in your task" in ctx
    for rule in (
        "MUST Code economy:",
        "MUST Hand-roll pricing:",
        "MUST Economy overrides",
        "MUST YAGNI:",
        "MUST Comments:",
        "MUST Reports:",
    ):
        assert rule in ctx
    # Exactly one MANDATORY marker -- targeted emphasis, not shouting.
    assert ctx.count("MANDATORY") == 1


def test_report_rule_demands_proof_pointer_or_untested_marker():
    result = run_hook('{"agent_id":"a1"}')
    assert result.returncode == 0
    ctx = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "path:line" in ctx
    assert "untested" in ctx


def test_non_subagent_exits_silently():
    result = run_hook('{"cwd":"/whatever"}')
    assert result.returncode == 0
    assert result.stdout == ""


def test_malformed_empty_stdin_does_not_crash():
    result = run_hook("")
    assert result.returncode == 0
