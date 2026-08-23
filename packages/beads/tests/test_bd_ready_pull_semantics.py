"""The `bd ready` behaviours a pull-model queue depends on, pinned against upgrades.

Workers pull work by racing `bd ready --label <l> --claim` at one queue instead of
being handed a bead. That only distributes work if `--claim` hands each caller a
different bead, skips beads another actor holds, and refuses rather than silently
widens when asked for someone else's queue. Nothing in this repository implements
those rules -- `bd` does -- so a `bd` upgrade can change them with no local diff.
These assertions are the tripwire, measured against bd 1.2.2.

Every command runs against a throwaway `bd init` in a temp directory, addressed by
an explicit `-C`, so no assertion can read or write the repository's own beads.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("bd") is None, reason="bd not available")

# The claim conflict is reported in prose. Match the part that names the conflict,
# not the sentence, so a reworded bd error does not read as a behaviour change.
CLAIM_CONFLICT = "cannot be combined"


def bd(root: Path, *args: str, actor: str | None = None) -> subprocess.CompletedProcess:
    """Run bd against `root`, as `actor`.

    `--actor` is passed in argv rather than via $BEADS_ACTOR so a host-set actor
    cannot shadow it, and `-C` is always explicit so no result depends on cwd.
    """
    command = ["bd", "-C", str(root)]
    if actor:
        command += ["--actor", actor]
    return subprocess.run(
        [*command, *args, "--json"], capture_output=True, text=True, timeout=180, check=False
    )


def ids(result: subprocess.CompletedProcess) -> list[str]:
    assert result.returncode == 0, result.stderr or result.stdout
    return [record["id"] for record in json.loads(result.stdout)]


def create(root: Path, title: str, *extra: str) -> str:
    result = bd(root, "create", title, *extra, actor="setup")
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)["id"]


def show(root: Path, bead: str) -> dict:
    result = bd(root, "show", bead)
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)[0]


def init(root: Path) -> Path:
    """A git repo with its own beads database, or skip."""
    root.mkdir(parents=True, exist_ok=True)
    for command in (
        ["git", "init", "-q", "-b", "main", "."],
        # `bd init` commits, and a global commit.gpgsign makes that BLOCK (not fail)
        # while the 1Password agent is unreachable. Nothing here is worth signing.
        ["git", "config", "commit.gpgsign", "false"],
        ["git", "config", "tag.gpgsign", "false"],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
    ):
        subprocess.run(command, cwd=root, check=True, capture_output=True)
    # `bd -C` refuses a directory with no project yet, so init alone runs with cwd.
    # --skip-hooks keeps a fixture from wiring hooks for the host.
    started = subprocess.run(
        ["bd", "init", "--prefix", "tb", "--skip-hooks"],
        cwd=root,
        capture_output=True,
        timeout=300,
        check=False,
    )
    if started.returncode != 0:
        pytest.skip("bd init failed")
    return root


@pytest.fixture(scope="module")
def queue(tmp_path_factory) -> Path:
    """One database shared by every test here; `bd init` costs seconds.

    Each test creates its own beads under a label only it uses, so the tests do not
    compete for each other's work and order does not matter.
    """
    return init(tmp_path_factory.mktemp("queue") / "repo")


@pytest.fixture(scope="module")
def held_elsewhere(tmp_path_factory) -> tuple[Path, str]:
    """A database whose only bead is assigned to another actor.

    Separate from `queue` because the assertion is about `--claim` with no filter at
    all, which would otherwise reach beads the other tests created.
    """
    root = init(tmp_path_factory.mktemp("held") / "repo")
    bead = create(root, "assigned elsewhere")
    assert bd(root, "update", bead, "--assignee", "other-worker", actor="setup").returncode == 0
    return root, bead


# --- claiming distributes work ------------------------------------------------


def test_each_worker_claims_a_different_bead_and_an_empty_queue_yields_nothing(
    queue: Path,
) -> None:
    """The whole pull model rests on this: one bead cannot go to two workers."""
    queued = {create(queue, f"drain {n}", "-l", "q-drain") for n in (1, 2)}

    first = ids(bd(queue, "ready", "--label", "q-drain", "--claim", actor="w1"))
    second = ids(bd(queue, "ready", "--label", "q-drain", "--claim", actor="w2"))
    third = bd(queue, "ready", "--label", "q-drain", "--claim", actor="w3")

    assert len(first) == 1 and len(second) == 1, "a claim hands over one bead"
    assert {*first, *second} == queued, "two claims drained the queue, each a different bead"
    assert third.returncode == 0, "a drained queue is not an error"
    assert ids(third) == [], "the third worker must be told there is no work, not given some"


def test_a_bead_assigned_to_another_actor_is_invisible_to_an_unfiltered_claim(
    held_elsewhere: tuple[Path, str],
) -> None:
    """Held work is skipped by `--claim` itself, not by a filter the caller passes."""
    root, bead = held_elsewhere

    assert ids(bd(root, "ready", actor="w1")) == [bead], "the bead is otherwise ready"
    assert ids(bd(root, "ready", "--claim", actor="w1")) == [], "so --claim skipped it"

    after = show(root, bead)
    assert (after["status"], after["assignee"]) == ("open", "other-worker"), "and left it alone"


def test_claiming_on_behalf_of_another_assignee_is_refused(queue: Path) -> None:
    """`--assignee` selects whose work to list; claiming is always for the caller.

    Accepting both would silently claim for the wrong actor, so bd must refuse.
    """
    bead = create(queue, "not yours", "-l", "q-reject")

    refused = bd(
        queue, "ready", "--label", "q-reject", "--claim", "--assignee", "someone-else"
    )

    assert refused.returncode == 1
    assert CLAIM_CONFLICT in (refused.stdout + refused.stderr)
    untouched = show(queue, bead)
    assert (untouched["status"], untouched.get("assignee")) == ("open", None), (
        "a refused command must claim nothing"
    )


# --- claiming is the only thing that starts work -----------------------------


def test_assigning_a_bead_does_not_start_it_but_claiming_does(queue: Path) -> None:
    """An orchestrator can pin a bead to a worker without marking it underway."""
    assigned = create(queue, "pinned")
    bd(queue, "update", assigned, "--assignee", "w4", actor="setup")

    pinned = show(queue, assigned)
    assert pinned["status"] == "open", "--assignee alone leaves the bead claimable"
    assert pinned["assignee"] == "w4"
    assert pinned.get("started_at") is None

    create(queue, "claimed", "-l", "q-start")
    claimed = json.loads(
        bd(queue, "ready", "--label", "q-start", "--claim", actor="w5").stdout
    )[0]

    assert claimed["status"] == "in_progress"
    assert claimed["assignee"] == "w5"
    assert claimed["started_at"], "a claim also records when work started"


# --- the two filters a queue is built from -----------------------------------


def test_parent_filters_to_descendants_at_any_depth(queue: Path) -> None:
    """A run scopes its workers to one epic with --parent, so it must not leak."""
    epic = create(queue, "epic root", "-t", "epic")
    child = create(queue, "child", "--parent", epic)
    sibling = create(queue, "sibling", "--parent", epic)
    grandchild = create(queue, "grandchild", "--parent", child)
    outsider = create(queue, "outsider")

    descendants = ids(bd(queue, "ready", "--parent", epic))

    assert set(descendants) == {child, sibling, grandchild}
    assert epic not in descendants, "--parent selects below the bead, not the bead"
    assert outsider not in descendants
    assert ids(bd(queue, "ready", "--parent", child)) == [grandchild]


def test_setting_metadata_merges_per_key(queue: Path) -> None:
    """Workers write their own keys onto a shared bead; a replace would erase peers."""
    bead = create(queue, "carries metadata")

    bd(queue, "update", bead, "--metadata", '{"a": "1", "keep": "yes"}', actor="setup")
    bd(queue, "update", bead, "--metadata", '{"b": "2", "a": "9"}', actor="setup")

    assert show(queue, bead)["metadata"] == {"a": "9", "b": "2", "keep": "yes"}
