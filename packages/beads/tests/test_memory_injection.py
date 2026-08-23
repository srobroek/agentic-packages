"""Coverage for key-prefix-scoped memory injection and the folded `bd prime`.

The leak test is the point of the file. `bd memories <term>` matches CONTENT as well
as keys, so scoping could not be delegated to bd's own search; these cases pin that
the Python-side key filter does not reproduce that leak.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import beads_sync  # noqa: E402

# A key that does not start with `arch-` but whose CONTENT names it: the exact shape
# that `bd memories arch-` returned and the key filter must reject.
MEMORY_MAP = {
    "schema_version": "1",
    "arch-formulas-lease": "worktrunk lease token lives in the checkout",
    "global-commit-style": "no AI attribution in commit messages",
    "orc-nxbz-anchor": "pour anchors against the epic",
    "unrelated-note": "this one merely mentions arch- and global- in its body",
}


def load(stem: str):
    path = SCRIPTS / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    assert spec and spec.loader, path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def bd_stub(tmp_path, monkeypatch):
    """Put a scripted `bd` on PATH. Returns a writer for its shell body."""
    stubbin = tmp_path / "bin"
    stubbin.mkdir()
    monkeypatch.setenv("PATH", f"{stubbin}{os.pathsep}{os.environ['PATH']}")

    def write(body: str):
        stub = stubbin / "bd"
        stub.write_text(body)
        stub.chmod(0o755)
        return stub

    return write


def memories_stub(bd_stub, payload: dict):
    """A `bd` that answers `where` and `memories --json`, and nothing else."""
    bd_stub(
        "#!/bin/sh\n"
        'for a in "$@"; do\n'
        '  case "$a" in\n'
        f"    memories) cat <<'EOF'\n{json.dumps(payload)}\nEOF\n"
        "      exit 0 ;;\n"
        "  esac\n"
        "done\n"
        "exit 0\n"
    )


# --- prefix filter ---------------------------------------------------------


def test_selects_only_keys_with_the_prefix(bd_stub, tmp_path):
    memories_stub(bd_stub, MEMORY_MAP)
    selected = beads_sync.memories(str(tmp_path), ["arch-"])
    assert list(selected) == ["arch-formulas-lease"]


def test_content_match_does_not_leak(bd_stub, tmp_path):
    """The `bd memories <term>` content-match leak, closed."""
    memories_stub(bd_stub, MEMORY_MAP)
    for prefix in ("arch-", "global-"):
        selected = beads_sync.memories(str(tmp_path), [prefix])
        assert "unrelated-note" not in selected


def test_schema_version_is_stripped(bd_stub, tmp_path):
    memories_stub(bd_stub, MEMORY_MAP)
    selected = beads_sync.memories(str(tmp_path), ["schema", "arch-"])
    assert "schema_version" not in selected
    assert "arch-formulas-lease" in selected


def test_several_prefixes_union(bd_stub, tmp_path):
    memories_stub(bd_stub, MEMORY_MAP)
    selected = beads_sync.memories(str(tmp_path), ["global-", "orc-nxbz-"])
    assert sorted(selected) == ["global-commit-style", "orc-nxbz-anchor"]


def test_no_prefixes_calls_nothing(bd_stub, tmp_path):
    """An unscoped actor must get silence, never the whole unfiltered store."""
    bd_stub("#!/bin/sh\nexit 1\n")
    assert beads_sync.memories(str(tmp_path), []) == {}


def test_timeout_degrades_to_empty(bd_stub, tmp_path):
    """A slow `bd memories` (measured 1.67s) yields nothing, not an exception."""
    bd_stub("#!/bin/sh\nsleep 10\n")
    assert beads_sync.memories(str(tmp_path), ["arch-"], timeout=0.5) == {}


def test_unparsable_output_degrades_to_empty(bd_stub, tmp_path):
    bd_stub("#!/bin/sh\nprintf 'not json'\n")
    assert beads_sync.memories(str(tmp_path), ["arch-"]) == {}


def test_prefixes_read_from_env(monkeypatch):
    monkeypatch.setenv("BEADS_MEMORY_PREFIXES", " arch- , orc-nxbz- ,, ")
    assert beads_sync.memory_prefixes() == ["arch-", "orc-nxbz-"]


def test_prefixes_absent_env_is_empty(monkeypatch):
    monkeypatch.delenv("BEADS_MEMORY_PREFIXES", raising=False)
    assert beads_sync.memory_prefixes() == []


def test_render_is_empty_without_selection():
    assert beads_sync.render_memories({}) == ""


def test_render_names_key_and_content():
    rendered = beads_sync.render_memories({"arch-a": "body text"})
    assert "arch-a" in rendered and "body text" in rendered


# --- orchestrator vs subagent ---------------------------------------------


def drive_session(payload: dict, monkeypatch, capsys):
    module = load("beads-sync-session")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    code = module.main()
    out = capsys.readouterr().out
    return code, (json.loads(out) if out.strip() else None)


@pytest.fixture
def primed(bd_stub, tmp_path):
    """A `bd` whose `prime` and `memories` outputs are distinguishable."""
    beads = tmp_path / ".beads"
    beads.mkdir()
    bd_stub(
        "#!/bin/sh\n"
        'for a in "$@"; do\n'
        '  case "$a" in\n'
        f"    where) printf '{beads}\\n'; exit 0 ;;\n"
        "    prime) printf 'FULL PRIME BLOCK\\n'; exit 0 ;;\n"
        f"    memories) cat <<'EOF'\n{json.dumps(MEMORY_MAP)}\nEOF\n"
        "      exit 0 ;;\n"
        "    config) exit 1 ;;\n"
        "  esac\n"
        "done\n"
        "exit 0\n"
    )
    return tmp_path


def context_of(result) -> str:
    assert result is not None
    return result["hookSpecificOutput"]["additionalContext"]


def test_orchestrator_gets_the_full_prime(primed, monkeypatch, capsys):
    monkeypatch.setenv("BEADS_MEMORY_PREFIXES", "arch-")
    code, out = drive_session({"cwd": str(primed)}, monkeypatch, capsys)
    assert code == 0
    assert "FULL PRIME BLOCK" in context_of(out)


def test_subagent_gets_scoped_memories_not_the_prime(primed, monkeypatch, capsys):
    monkeypatch.setenv("BEADS_MEMORY_PREFIXES", "arch-")
    code, out = drive_session(
        {"cwd": str(primed), "agent_id": "a1"}, monkeypatch, capsys
    )
    assert code == 0
    context = context_of(out)
    assert "FULL PRIME BLOCK" not in context
    assert "arch-formulas-lease" in context
    assert "unrelated-note" not in context


def test_subagent_without_prefixes_is_silent(primed, monkeypatch, capsys):
    monkeypatch.delenv("BEADS_MEMORY_PREFIXES", raising=False)
    code, out = drive_session(
        {"cwd": str(primed), "agent_id": "a1"}, monkeypatch, capsys
    )
    assert code == 0
    assert out is None


@pytest.mark.parametrize("raw", ["", "not json", "[]"])
def test_unparsable_payload_does_not_prime(primed, monkeypatch, capsys, raw):
    """A guessed cwd must not be primed -- it may be another project's workspace."""
    module = load("beads-sync-session")
    monkeypatch.chdir(primed)
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    assert module.main() == 0
    assert capsys.readouterr().out == ""


def test_is_subagent_reads_agent_id():
    assert beads_sync.is_subagent(json.dumps({"agent_id": "a1"}))
    assert not beads_sync.is_subagent(json.dumps({"cwd": "/tmp"}))
    assert not beads_sync.is_subagent("{oops")


# --- SubagentStart reminder ------------------------------------------------


def test_reminder_appends_scoped_memories(primed, monkeypatch):
    env = os.environ.copy()
    env["BEADS_MEMORY_PREFIXES"] = "global-"
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "beads-subagent-reminder.py")],
        input=json.dumps({"agent_id": "a1", "cwd": str(primed)}),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "bd close" in context
    assert "global-commit-style" in context
    assert "arch-formulas-lease" not in context
