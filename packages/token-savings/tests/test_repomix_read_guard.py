"""Coverage for repomix-read-guard.py, the deny gate on reading a repomix pack.

The gate exists because a full pack of a 4,107-file repository is 6,349,248
tokens: reading it cannot succeed, it truncates or ends the session. The pack is
a SEARCH target, so the guard denies the read and names the search.

The allow cases matter as much as the denials. A guard that blocks `rg` on the
pack breaks the only thing the pack is for, and this repository's constitution
puts every guard on a fail-open footing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "repomix-read-guard.py"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository holding a pack large enough to trip the size gate."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "-C", str(repo_dir), "init", "-q"], check=True, capture_output=True)
    with (repo_dir / "repomix-full.xml").open("w") as handle:
        for index in range(3000):
            handle.write(f'<file path="src/f{index}.rs">\n' + "x" * 400 + "\n</file>\n")
    (repo_dir / "small.xml").write_text("<tiny/>\n")
    (repo_dir / "src").mkdir()
    (repo_dir / "src" / "main.rs").write_text("fn main() {}\n")
    return repo_dir


def _run(tool: str, tool_input, repo: Path, override: str | None = None) -> str:
    environment = dict(os.environ)
    environment.pop("TOKEN_SAVINGS_ALLOW_PACK_READ", None)
    if override is not None:
        environment["TOKEN_SAVINGS_ALLOW_PACK_READ"] = override
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps({"tool_name": tool, "tool_input": tool_input, "cwd": str(repo)}),
        capture_output=True,
        text=True,
        env=environment,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def _denied(out: str) -> bool:
    if not out:
        return False
    emitted = json.loads(out)["hookSpecificOutput"]
    return emitted.get("permissionDecision") == "deny"


# --- denied: reads that cannot fit -----------------------------------------


def test_reading_a_pack_with_the_read_tool_is_denied(repo):
    assert _denied(_run("Read", {"file_path": "repomix-full.xml"}, repo))


@pytest.mark.parametrize(
    "command",
    [
        "cat repomix-full.xml",
        "bat repomix-full.xml",
        "less repomix-full.xml",
        "more repomix-full.xml",
        "nl repomix-full.xml",
        "cd /tmp && cat repomix-full.xml",
    ],
)
def test_whole_file_readers_are_denied(command, repo):
    assert _denied(_run("Bash", {"command": command}, repo))


@pytest.mark.parametrize(
    "command",
    ["head -100000 repomix-full.xml", "tail -50000 repomix-full.xml", "head -n 99999 repomix-full.xml"],
)
def test_an_oversized_head_or_tail_is_denied(command, repo):
    """A large count is a slurp wearing a sampler's clothes."""
    assert _denied(_run("Bash", {"command": command}, repo))


def test_an_oversized_head_piped_into_a_searcher_is_still_denied(repo):
    """The pipe does not save it: `head -100000` has already read the pack."""
    assert _denied(_run("Bash", {"command": "head -100000 repomix-full.xml | rg x"}, repo))


def test_an_mcp_file_reader_is_denied(repo):
    assert _denied(_run("mcp__repomix__read_repomix_output", {"path": "repomix-full.xml"}, repo))


def test_the_denial_names_the_search_commands(repo):
    """A denial is written to the model, so it must say what to do instead."""
    reason = json.loads(_run("Read", {"file_path": "repomix-full.xml"}, repo))[
        "hookSpecificOutput"
    ]["permissionDecisionReason"]
    assert "rg" in reason
    assert "awk" in reason
    assert "tokens" in reason


# --- allowed: the pack's intended use --------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "rg pattern repomix-full.xml",
        "grep -n pattern repomix-full.xml",
        "rg -o 'path=\"[^\"]*main[^\"]*\"' repomix-full.xml",
        "awk '/<file path=\"src\\/main.rs\">/,/close/' repomix-full.xml",
        "sed -n '1,50p' repomix-full.xml",
        "wc -l repomix-full.xml",
        "cat repomix-full.xml | rg pattern",
        "jq . repomix-full.xml",
    ],
)
def test_searching_a_pack_is_allowed(command, repo):
    """Searching is the whole reason the pack exists."""
    assert not _denied(_run("Bash", {"command": command}, repo))


@pytest.mark.parametrize(
    "command", ["head -20 repomix-full.xml", "tail -30 repomix-full.xml", "head repomix-full.xml"]
)
def test_sampling_the_shape_is_allowed(command, repo):
    assert not _denied(_run("Bash", {"command": command}, repo))


def test_a_small_pack_is_readable(repo):
    """A tiny repository packs to a few thousand tokens; denying that obstructs."""
    assert not _denied(_run("Read", {"file_path": "small.xml"}, repo))


def test_reading_a_source_file_is_untouched(repo):
    assert not _denied(_run("Read", {"file_path": "src/main.rs"}, repo))


@pytest.mark.parametrize("value", ["1", "true", "yes"])
def test_the_override_allows_reading_the_whole_pack(value, repo):
    """A deny with no escape hatch is a guard that gets deleted the first time it
    is wrong. Sometimes the whole pack IS what the caller wants."""
    assert not _denied(_run("Read", {"file_path": "repomix-full.xml"}, repo, override=value))


@pytest.mark.parametrize("value", ["", "0", "false"])
def test_a_falsey_override_still_denies(value, repo):
    assert _denied(_run("Read", {"file_path": "repomix-full.xml"}, repo, override=value))


def test_the_denial_names_the_override(repo):
    """A denial the caller cannot act on is a wall, not a guard."""
    reason = json.loads(_run("Read", {"file_path": "repomix-full.xml"}, repo))[
        "hookSpecificOutput"
    ]["permissionDecisionReason"]
    assert "TOKEN_SAVINGS_ALLOW_PACK_READ" in reason


def test_a_pack_that_does_not_exist_is_untouched(repo):
    """Size gates the decision, so an absent file cannot be judged."""
    assert not _denied(_run("Read", {"file_path": "repomix.json"}, repo))


# --- fail-open -------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "not json",
        "[]",
        "null",
        '{"tool_name":"Read"}',
        '{"tool_name":"Read","tool_input":42}',
        '{"tool_name":"Bash","tool_input":{"command":null}}',
    ],
)
def test_malformed_payloads_fail_open(raw):
    proc = subprocess.run([sys.executable, str(SCRIPT)], input=raw, capture_output=True, text=True)
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_a_string_tool_input_is_accepted(repo):
    """Some callers send tool_input as a bare string."""
    assert _denied(_run("Bash", "cat repomix-full.xml", repo))


def test_a_payload_naming_no_pack_exits_before_parsing(repo):
    """The cheap bail: no pack name in the bytes means no work."""
    assert _run("Bash", {"command": "ls -la"}, repo) == ""


def test_emits_no_ask_and_no_claude_only_fields(repo):
    """Constitution III bans `ask`; a target: all package must not emit
    Claude-only fields, which are silent no-ops under Codex."""
    emitted = json.loads(_run("Read", {"file_path": "repomix-full.xml"}, repo))[
        "hookSpecificOutput"
    ]
    assert emitted["permissionDecision"] == "deny"
    assert emitted["hookEventName"] == "PreToolUse"
    assert "systemMessage" not in emitted
    assert "suppressOutput" not in emitted
