"""Coverage for the merge-bead gate on `gh pr create`.

The guard refuses a pull request whose merge bead cannot serve the merge queue: a
bead that is closed, mislabelled, assigned, or missing an anchor is discovered and
then skipped, so the pull request waits for a queue that will never take it.

It denies, so the cases that matter most are the ones it must let through: a
repository with no merge bead for the branch, a repository with no beads at all, a
missing `bd`, a lookup that cannot complete, and a `gh pr create` quoted inside a
commit message.

`bd` is stubbed on PATH and reads its answer from a fixture file, so these
describe the guard's logic rather than the machine's beads state.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parent.parent / "scripts" / "pr-merge-bead-guard.py"

BRANCH = "feat/thing"

# A merge bead the queue can act on. Each deny case below removes exactly one of
# these properties, so a failure names the property that guard lost.
HEALTHY = {
    "id": "bd-1",
    "status": "open",
    "labels": ["pr:merge", "agent:integrator"],
    "metadata": {
        "branch": BRANCH,
        "repo": "acme/widget",
        "origin_actor": "worker-1",
    },
}


def bead(**overrides) -> dict:
    """The healthy bead with top-level keys replaced."""
    record = json.loads(json.dumps(HEALTHY))
    record.update(overrides)
    return record


def without_metadata(name: str) -> dict:
    record = bead()
    del record["metadata"][name]
    return record


@pytest.fixture
def workspace(tmp_path: Path) -> dict:
    """A beads-enabled directory, plus a `bd` stub answering from a fixture file."""
    work = tmp_path / "work"
    (work / ".beads").mkdir(parents=True)

    fixture = tmp_path / "beads.json"
    fixture.write_text("[]")

    binary = tmp_path / "bin"
    binary.mkdir()
    stub = binary / "bd"
    # `where` decides whether beads is active; `list` supplies the candidate beads.
    stub.write_text(
        "#!/bin/sh\n"
        'for arg in "$@"; do\n'
        '  case "$arg" in\n'
        "    where) exit 0 ;;\n"
        '    list) exec cat "$BEADS_FIXTURE" ;;\n'
        "  esac\n"
        "done\n"
        "exit 0\n"
    )
    stub.chmod(0o755)

    environment = dict(os.environ)
    environment["PATH"] = f"{binary}:{environment['PATH']}"
    environment["BEADS_FIXTURE"] = str(fixture)
    return {"cwd": str(work), "env": environment, "bin": binary, "fixture": fixture}


def load(workspace: dict, records: list[dict]) -> None:
    workspace["fixture"].write_text(json.dumps(records))


def run_guard(command: str, workspace: dict) -> tuple[int, str | None, str]:
    payload = json.dumps({"cwd": workspace["cwd"], "tool_input": {"command": command}})
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=payload,
        capture_output=True,
        text=True,
        env=workspace["env"],
        timeout=30,
    )
    if not result.stdout.strip():
        return result.returncode, None, ""
    out = json.loads(result.stdout)["hookSpecificOutput"]
    return (
        result.returncode,
        out.get("permissionDecision"),
        out.get("permissionDecisionReason") or out.get("additionalContext", ""),
    )


def create(extra: str = "") -> str:
    return f"gh pr create --draft --title x --body y --head {BRANCH} {extra}".strip()


# --- a usable merge bead passes ----------------------------------------------


def test_a_healthy_merge_bead_is_allowed(workspace: dict) -> None:
    load(workspace, [bead()])

    code, decision, reason = run_guard(create(), workspace)

    assert code == 0
    assert decision is None, reason


# --- one refusal per defect --------------------------------------------------


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        pytest.param(bead(status="closed"), "closed", id="closed"),
        pytest.param(bead(status="in_progress"), "not open", id="not-open"),
        pytest.param(bead(labels=["agent:integrator"]), "pr:merge", id="missing-pr-merge"),
        pytest.param(
            bead(labels=["pr:merge"]), "agent:integrator", id="missing-agent-integrator"
        ),
        pytest.param(bead(labels=[]), "label", id="missing-both-labels"),
        pytest.param(bead(assignee="someone"), "assigned", id="assigned"),
        pytest.param(without_metadata("repo"), "repo", id="missing-repo-metadata"),
        pytest.param(
            without_metadata("origin_actor"), "origin_actor", id="missing-origin-actor"
        ),
    ],
)
def test_an_unusable_merge_bead_is_denied(
    record: dict, expected: str, workspace: dict
) -> None:
    load(workspace, [record])

    code, decision, reason = run_guard(create(), workspace)

    assert code == 0, "the decision travels in JSON, never in the exit code"
    assert decision == "deny"
    assert expected in reason, "a denial must name the defect, not just refuse"


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(f"gh -R acme/widget pr create --draft --head {BRANCH}", id="short-R"),
        pytest.param(
            f"gh --repo acme/widget pr create --draft --head {BRANCH}", id="long-repo"
        ),
        pytest.param(
            f"gh --repo=acme/widget pr create --draft --head {BRANCH}", id="attached-value"
        ),
        pytest.param(f"gh -Racme/widget pr create --draft --head {BRANCH}", id="attached-short"),
    ],
)
def test_a_flag_before_the_subcommand_does_not_bypass_the_guard(
    command: str, workspace: dict
) -> None:
    """`gh -R owner/repo pr create` is valid, and shifts the operand window."""
    load(workspace, [bead(status="closed")])

    _, decision, _ = run_guard(command, workspace)

    assert decision == "deny"


def test_two_merge_beads_for_one_branch_are_denied(workspace: dict) -> None:
    """The queue resolves by branch, so it cannot choose between two."""
    load(workspace, [bead(), bead(id="bd-2")])

    _, decision, reason = run_guard(create(), workspace)

    assert decision == "deny"
    assert "bd-1" in reason and "bd-2" in reason


def test_a_missing_merge_bead_is_denied_where_the_convention_is_used(
    workspace: dict,
) -> None:
    """One merge bead anywhere means the queue is in use, so this branch needs one."""
    other = bead(id="bd-9")
    other["metadata"]["branch"] = "feat/unrelated"
    load(workspace, [other])

    _, decision, reason = run_guard("gh pr create --draft --head feat/orphan", workspace)

    assert decision == "deny"
    assert "feat/orphan" in reason


def test_a_bead_whose_branch_metadata_is_absent_denies_the_branch(
    workspace: dict,
) -> None:
    """A bead that anchors nothing cannot answer for this branch."""
    load(workspace, [without_metadata("branch")])

    _, decision, reason = run_guard(create(), workspace)

    assert decision == "deny"
    assert "No merge bead anchors" in reason


def test_a_repository_with_no_merge_bead_at_all_is_untouched(workspace: dict) -> None:
    """Tracking work in beads does not imply a merge queue."""
    load(workspace, [])

    _, decision, _ = run_guard(create(), workspace)

    assert decision is None


@pytest.mark.parametrize(
    "head",
    [
        pytest.param("feat/thing-extra", id="branch-extends-the-anchor"),
        pytest.param("feat/thi", id="branch-is-a-prefix-of-the-anchor"),
    ],
)
def test_the_branch_match_is_exact_not_a_prefix(head: str, workspace: dict) -> None:
    """Rewriting matches_branch to a prefix comparison must fail here.

    The only bead present is defective, so a prefix match would reach it and refuse
    for the defect. An exact match reaches no bead, and the branch is refused for
    having none. The two refusals carry different reasons.
    """
    load(workspace, [bead(status="closed")])

    _, decision, reason = run_guard(f"gh pr create --draft --head {head}", workspace)

    assert decision == "deny"
    assert "No merge bead anchors" in reason, "a prefix match reached the wrong bead"


# --- the branch, and the directory it is read from ---------------------------


def test_the_branch_is_read_from_git_when_head_is_absent(workspace: dict) -> None:
    subprocess.run(
        ["git", "-C", workspace["cwd"], "init", "--initial-branch", BRANCH],
        check=True,
        capture_output=True,
    )
    load(workspace, [bead(status="closed")])

    _, decision, _ = run_guard("gh pr create --draft --title x --body y", workspace)

    assert decision == "deny"


def test_a_cd_prefix_selects_the_directory_judged(workspace: dict, tmp_path: Path) -> None:
    """A harness prefixes `cd <path> &&`; the guard must judge that repository."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    load(workspace, [bead(status="closed")])
    payload = json.dumps(
        {
            "cwd": str(elsewhere),
            "tool_input": {"command": f"cd -- {workspace['cwd']} && {create()}"},
        }
    )
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=payload,
        capture_output=True,
        text=True,
        env=workspace["env"],
        timeout=30,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


# --- what must pass ----------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("gh pr list --state open", id="pr-list"),
        pytest.param("gh pr view 42", id="pr-view"),
        pytest.param("gh issue create --title x", id="issue-not-pr"),
        pytest.param("gh pr ready 42", id="pr-ready"),
        pytest.param("ls -la", id="unrelated"),
        # Quoted prose is an argument, not a command.
        pytest.param(
            "git commit -m 'do not gh pr create by hand'", id="single-quoted-mention"
        ),
        pytest.param('echo "gh pr create is gated"', id="echoed-mention"),
    ],
)
def test_ordinary_work_is_allowed(command: str, workspace: dict) -> None:
    load(workspace, [bead(status="closed")])

    code, decision, _ = run_guard(command, workspace)

    assert code == 0
    assert decision is None, f"unexpected denial for: {command}"


# --- fail open ---------------------------------------------------------------


def test_without_a_beads_workspace_nothing_is_denied(workspace: dict) -> None:
    """This guard lives in the beads package; a repository without beads is untouched."""
    stub = workspace["bin"] / "bd"
    stub.write_text("#!/bin/sh\nexit 1\n")
    stub.chmod(0o755)

    _, decision, _ = run_guard(create(), workspace)

    assert decision is None


def test_without_bd_nothing_is_denied(workspace: dict) -> None:
    (workspace["bin"] / "bd").unlink()

    _, decision, _ = run_guard(create(), workspace)

    assert decision is None


def test_a_failed_lookup_advises_rather_than_denying(workspace: dict) -> None:
    """A slow or unhealthy database must not read as "that bead does not exist"."""
    stub = workspace["bin"] / "bd"
    stub.write_text(
        "#!/bin/sh\n"
        'for arg in "$@"; do\n'
        "  case \"$arg\" in\n"
        "    where) exit 0 ;;\n"
        '    list) echo "database is locked" >&2; exit 1 ;;\n'
        "  esac\n"
        "done\n"
        "exit 0\n"
    )
    stub.chmod(0o755)

    _, decision, reason = run_guard(create(), workspace)

    assert decision is None
    assert "not verified" in reason


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("", id="empty"),
        pytest.param("not json {", id="malformed"),
        pytest.param("[]", id="not-an-object"),
        pytest.param('{"tool_input": null}', id="null-tool-input"),
        # Unbalanced quotes: the shell would reject this command too.
        pytest.param(
            '{"tool_input":{"command":"gh pr create --title \'x"}}', id="unbalanced-quotes"
        ),
    ],
)
def test_an_unusable_payload_allows(payload: str, workspace: dict) -> None:
    load(workspace, [bead(status="closed")])
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=payload,
        capture_output=True,
        text=True,
        env=workspace["env"],
        timeout=30,
    )

    assert result.returncode == 0
    assert not result.stdout.strip()


def test_a_non_string_cwd_does_not_crash(workspace: dict) -> None:
    """The wrapper exits 0 on any internal defect, so a crash would read as a pass."""
    load(workspace, [])
    payload = json.dumps({"cwd": 7, "tool_input": {"command": create()}})
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=payload,
        capture_output=True,
        text=True,
        env=workspace["env"],
        timeout=30,
    )

    assert result.returncode == 0
    assert "Traceback" not in result.stderr


def test_never_emits_ask(workspace: dict) -> None:
    """`ask` waits for a human, which stalls an autonomous run."""
    for records in ([], [bead()], [bead(status="closed")]):
        load(workspace, records)
        _, decision, _ = run_guard(create(), workspace)
        assert decision != "ask"
