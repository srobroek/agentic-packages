"""Cross-package fuzz suite for the two absolute hook rules.

Constitution III and the hook contract's reliability rules give every guard the
same two obligations, regardless of what it guards:

  R1  FAIL OPEN. An unreadable payload, a wrong-typed field, or an unexpected
      exception exits 0 (or 2 with a reason on stderr, the documented deny form)
      and never prints a traceback. A guard that crashes closed wedges the agent.
  R2  NEVER emit permissionDecision "ask". It waits for a human, so it stalls an
      autonomous run, and Codex marks the hook run failed and continues anyway.

Both are asserted for every hook a MANIFEST registers, discovered from the hook
json rather than listed, so a newly registered hook is covered the day it lands
instead of the day someone remembers to add it here. The corpus is the payload
shapes that have actually broken guards: a bare-string `tool_input`
(`.tool_input.command // .tool_input` throws on a string in jq and silently
bypasses the guard), wrong types in every field, truncated JSON, and oversized
commands.

The static half of R2 is NOT repeated here: `.apm/scripts/check-hook-contract.py`
already rejects `permissionDecision: "ask"` as an emitted value in either
language, and a plain substring search over the source flags the three hooks whose
docstrings state the ban.

Seed 20260729. FUZZ_HOOK_CASES raises the generated corpus. Runtime is one
subprocess per hook per payload, so it is minutes rather than seconds; see the
package suites for the per-hook depth.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SEED = 20260729
GENERATED_CASES = int(os.environ.get("FUZZ_HOOK_CASES", "40"))

def guard_scripts() -> list[Path]:
    """Every Python script a hook manifest actually registers as a command.

    Discovered from the manifests rather than from a scripts/ glob: that glob also
    matches generators, shared modules, and test harnesses, which have no stdin
    protocol and would make the suite fail on files that are not hooks.
    """
    import re

    manifests = [
        *REPO.glob("packages/*/hooks/*.json"),
        *REPO.glob("packages/*/.apm/hooks/*.json"),
        *REPO.glob(".apm/hooks/*.json"),
    ]
    names: set[str] = set()
    for manifest in manifests:
        try:
            body = manifest.read_text(encoding="utf-8")
        except OSError:
            continue
        for command in re.findall(r'"command"\s*:\s*"([^"]+)"', body):
            for token in re.findall(r"[\w.-]+\.py", command):
                names.add(token)

    found: dict[str, Path] = {}
    for pattern in ("packages/*/scripts/*.py", "packages/*/.apm/hooks/scripts/*.py", ".apm/hooks/scripts/*.py"):
        for path in sorted(REPO.glob(pattern)):
            if path.name in names:
                found.setdefault(path.name, path)
    return [found[name] for name in sorted(found)]


SCRIPTS = guard_scripts()

# Payload shapes that have broken real guards, plus the plainly malformed.
FIXED_PAYLOADS: dict[str, str] = {
    "empty": "",
    "whitespace": "   \n",
    "not-json": "not json at all",
    "truncated": '{"tool_name":',
    "array": "[]",
    "null": "null",
    "number": "42",
    "bare-string": '"text"',
    "empty-object": "{}",
    # A bare-string tool_input: the documented jq trap.
    "tool-input-string": json.dumps({"tool_name": "Bash", "tool_input": "git commit -m x"}),
    "tool-input-null": json.dumps({"tool_name": "Bash", "tool_input": None}),
    "tool-input-list": json.dumps({"tool_name": "Bash", "tool_input": ["git", "commit"]}),
    "tool-input-number": json.dumps({"tool_name": "Bash", "tool_input": 7}),
    "command-null": json.dumps({"tool_name": "Bash", "tool_input": {"command": None}}),
    "command-number": json.dumps({"tool_name": "Bash", "tool_input": {"command": 42}}),
    "command-list": json.dumps({"tool_name": "Bash", "tool_input": {"command": ["git"]}}),
    "command-dict": json.dumps({"tool_name": "Bash", "tool_input": {"command": {}}}),
    "tool-name-null": json.dumps({"tool_name": None, "tool_input": {"command": "git commit"}}),
    "tool-name-dict": json.dumps({"tool_name": {}, "tool_input": {"command": "git commit"}}),
    "no-tool-name": json.dumps({"tool_input": {"command": "git commit -m x"}}),
    "response-string": json.dumps({"tool_name": "Bash", "tool_response": "boom"}),
    "response-null": json.dumps({"tool_name": "Bash", "tool_response": None}),
    "cwd-null": json.dumps({"cwd": None, "tool_input": {"command": "git commit"}}),
    "cwd-number": json.dumps({"cwd": 1, "tool_input": {"command": "git commit"}}),
    "huge-command": json.dumps({"tool_name": "Bash", "tool_input": {"command": "x" * 40000}}),
    "newlines": json.dumps({"tool_name": "Bash", "tool_input": {"command": "a\nb\nc\n"}}),
    "deep-nesting": json.dumps({"tool_input": {"command": "git commit"}, "n": [[[[[[1]]]]]]}),
    "file-path-null": json.dumps({"tool_name": "Edit", "tool_input": {"file_path": None}}),
    "file-path-number": json.dumps({"tool_name": "Edit", "tool_input": {"file_path": 3}}),
}

HOSTILE_VALUES = (None, True, False, 0, -1, 1.5, "", " ", "\n", "-x", "x" * 5000, [], {}, [{}])
TOOL_NAMES = ("Bash", "Edit", "Write", "Agent", "Task", "apply_patch", "", None, 42)
FIELDS = ("command", "file_path", "content", "description", "prompt", "subagent_type")


def generated_payloads() -> dict[str, str]:
    """Random field/type crossings, seeded so a failure is reproducible."""
    rng = random.Random(SEED)
    cases: dict[str, str] = {}
    for index in range(GENERATED_CASES):
        tool_input: dict = {}
        for field in rng.sample(FIELDS, rng.randint(1, 3)):
            tool_input[field] = rng.choice(HOSTILE_VALUES)
        body: dict = {"tool_name": rng.choice(TOOL_NAMES), "tool_input": tool_input}
        for extra in ("cwd", "session_id", "hook_event_name", "agent_id", "model"):
            if rng.random() < 0.3:
                body[extra] = rng.choice(HOSTILE_VALUES)
        cases[f"generated-{index}"] = json.dumps(body)
    return cases


PAYLOADS = {**FIXED_PAYLOADS, **generated_payloads()}


def _run(script: Path, payload: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=REPO,
        # A guard must not need any of these to answer; several read them.
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(REPO)},
    )


def test_guard_scripts_were_discovered():
    """A glob that matches nothing would make this whole suite vacuously green."""
    assert len(SCRIPTS) >= 15, [str(p) for p in SCRIPTS]


def _check(script: Path, case: str, payload: str) -> list[str]:
    """Every contract violation this payload produced, so one run reports them all."""
    result = _run(script, payload)
    problems: list[str] = []

    # R1: exit 0 (allow), or 2 (the documented deny-with-reason form). Anything
    # else is an unhandled error surfacing as a decision.
    if result.returncode not in (0, 2):
        problems.append(f"{case}: exit {result.returncode} -- {result.stderr[-200:]!r}")
    if "Traceback" in result.stderr:
        problems.append(f"{case}: raised -- {result.stderr.strip().splitlines()[-1][:200]}")

    # R2: never stall on a human.
    if '"ask"' in result.stdout or "'ask'" in result.stdout:
        problems.append(f"{case}: emitted ask")

    # Structured output must parse, or the tool ignores the decision entirely.
    if result.stdout.strip():
        try:
            parsed = json.loads(result.stdout)
        except ValueError:
            problems.append(f"{case}: non-JSON stdout -- {result.stdout[:200]!r}")
        else:
            if isinstance(parsed, dict):
                specific = parsed.get("hookSpecificOutput")
                if isinstance(specific, dict) and specific.get("permissionDecision") == "ask":
                    problems.append(f"{case}: permissionDecision ask")
    return problems


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_every_guard_fails_open_and_never_asks(script: Path):
    """One case per hook rather than per payload: a hook that breaks usually breaks
    on several payloads, and reporting them together beats 70 near-identical ids."""
    problems: list[str] = []
    for case in sorted(PAYLOADS):
        problems.extend(_check(script, case, PAYLOADS[case]))
    assert not problems, f"{script.name} violated the hook contract:\n" + "\n".join(problems)
