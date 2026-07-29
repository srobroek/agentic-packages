#!/usr/bin/env python3
"""Tests for pr-shepherd's watch-queue.py.

tests/watch-queue.bats drove the shell predecessor and was the parity oracle for
this port; every case it asserted is preserved here. The bucket precedence table
gets direct coverage, because the dashboard's section order and each PR's label
both derive from it and the bats cases pinned it only partially.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / ".apm/skills/pr-shepherd/scripts/watch-queue.py"
)
CONTEXTS = ["CI", "Lint", "Test"]


def _load():
    spec = importlib.util.spec_from_file_location("watch_queue_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wq = _load()


def test_script_is_committed_executable():
    assert SCRIPT.stat().st_mode & 0o111


def test_no_shell_helper_subprocess():
    """The port removed the jq/sed pipeline; keep it removed."""
    body = SCRIPT.read_text(encoding="utf-8")
    for tool in ('"jq"', '"sed"', '"awk"'):
        assert tool not in body


# --- remote parsing ---------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "git@github.com:owner/repo.git",
        "git@github.com:owner/repo",
        "https://github.com/owner/repo.git",
        "https://github.com/owner/repo",
        "ssh://git@github.com/owner/repo.git",
        "https://user@github.com/owner/repo.git",
    ],
)
def test_parse_remote_handles_every_github_form(url):
    assert wq.parse_remote(url) == "owner/repo"


def test_parse_remote_handles_an_enterprise_host():
    """The `sed -E 's|^.*github\\.com[:/]||'` tokenizer required the literal
    host `github.com`, so a GitHub Enterprise remote passed through unchanged
    and every later `gh api repos/<garbage>` call was made against nonsense.
    """
    assert wq.parse_remote("git@ghe.corp:team/proj.git") == "team/proj"


def test_parse_remote_is_not_fooled_by_a_path_segment():
    """The greedy `^.*github\\.com[:/]` matched the LAST occurrence anywhere in
    the URL, so a path segment named github.com hijacked the parse and yielded a
    bare name with no owner.
    """
    assert wq.parse_remote("https://gitlab.com/a/github.com/evil.git") != "evil"


def test_parse_remote_rejects_a_url_without_owner_and_repo():
    with pytest.raises(wq.Failure):
        wq.parse_remote("https://github.com/lonely")


# --- check state ------------------------------------------------------------


def check(entries):
    return wq.check_state(entries, "CI")


def test_absent_context():
    assert check([]) == "ABSENT"
    assert check([{"name": "Other", "status": "COMPLETED", "conclusion": "SUCCESS"}]) == (
        "ABSENT"
    )


def test_ambiguous_context_is_never_ok():
    """Two runs reporting one required name: which gates the merge is undecidable."""
    entries = [
        {"name": "CI", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"name": "CI", "status": "COMPLETED", "conclusion": "SUCCESS"},
    ]
    assert check(entries) == "AMBIGUOUS"


def test_running_context():
    assert check([{"name": "CI", "status": "IN_PROGRESS", "conclusion": None}]) == (
        "RUNNING"
    )
    assert check([{"name": "CI", "status": "QUEUED", "conclusion": None}]) == "RUNNING"


@pytest.mark.parametrize("conclusion", ["SUCCESS", "SKIPPED"])
def test_passing_conclusions(conclusion):
    assert check([{"name": "CI", "status": "COMPLETED", "conclusion": conclusion}]) == (
        "OK"
    )


@pytest.mark.parametrize(
    "conclusion", ["FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", None]
)
def test_failing_conclusions(conclusion):
    assert check([{"name": "CI", "status": "COMPLETED", "conclusion": conclusion}]) == (
        "FAIL"
    )


def test_non_dict_rollup_entries_are_ignored():
    assert wq.check_state(["junk", None, 7], "CI") == "ABSENT"


# --- bucket precedence ------------------------------------------------------
#
# The precedence order is the tool's contract. Each case below sets up a PR
# where two or more conditions hold and pins which one wins.


def test_bucket_order_is_the_documented_sequence():
    assert wq.BUCKET_ORDER == (
        "READY",
        "FAILING",
        "STUCK",
        "CONFLICT",
        "WAITING",
        "HELD",
    )


def test_held_outranks_every_other_condition():
    """A release or draft PR is HELD even when it is failing and conflicted."""
    assert wq.bucket_for(True, False, False, "DIRTY", ["FAIL", "ABSENT"]) == "HELD"
    assert wq.bucket_for(False, True, False, "DIRTY", ["FAIL", "ABSENT"]) == "HELD"


def test_ready_outranks_the_failure_buckets():
    assert wq.bucket_for(False, False, True, "CLEAN", ["OK", "OK"]) == "READY"


def test_conflict_outranks_failing_and_stuck():
    """A DIRTY tree is reported over a check result, because the conflict has to
    be resolved first and will re-run the checks anyway.
    """
    assert wq.bucket_for(False, False, False, "DIRTY", ["FAIL", "ABSENT"]) == "CONFLICT"


def test_failing_outranks_waiting_and_stuck():
    assert wq.bucket_for(False, False, False, "BLOCKED", ["FAIL", "RUNNING"]) == (
        "FAILING"
    )
    assert wq.bucket_for(False, False, False, "BLOCKED", ["FAIL", "ABSENT"]) == "FAILING"


def test_waiting_outranks_stuck():
    """A running check may yet report the absent one, so WAITING is not STUCK."""
    assert wq.bucket_for(False, False, False, "BLOCKED", ["RUNNING", "ABSENT"]) == (
        "WAITING"
    )


@pytest.mark.parametrize("state", ["ABSENT", "AMBIGUOUS"])
def test_stuck_covers_absent_and_ambiguous(state):
    assert wq.bucket_for(False, False, False, "BLOCKED", ["OK", state]) == "STUCK"


def test_all_ok_but_not_mergeable_is_waiting():
    """Every check passed while the merge state is not CLEAN: nothing is wrong
    with the PR, so the fallthrough is WAITING rather than STUCK.
    """
    assert wq.bucket_for(False, False, False, "BEHIND", ["OK", "OK"]) == "WAITING"


# --- classification ---------------------------------------------------------


def pr(**overrides):
    base = {
        "number": 42,
        "title": "test queue policy",
        "isDraft": False,
        "headRefName": "feature/test",
        "mergeStateStatus": "CLEAN",
        "statusCheckRollup": [
            {"name": name, "status": "COMPLETED", "conclusion": "SUCCESS"}
            for name in CONTEXTS
        ],
    }
    base.update(overrides)
    return base


def classify_one(**overrides):
    rows = wq.classify([pr(**overrides)], CONTEXTS, "^release-please--")
    return rows[0]


def test_green_clean_pr_is_ready():
    row = classify_one()
    assert row["ready"] is True
    assert row["bucket"] == "READY"
    assert row["done"] == 3
    assert row["total"] == 3


def test_release_branch_is_held():
    row = classify_one(headRefName="release-please--branches--main")
    assert row["release"] is True
    assert row["bucket"] == "HELD"
    assert row["ready"] is False


@pytest.mark.parametrize(
    "title",
    ["chore: release 1.2.3", "chore(main): release 2.0.0", "CHORE: RELEASE 3.0.0"],
)
def test_release_title_is_held(title):
    assert classify_one(title=title)["bucket"] == "HELD"


def test_release_looking_title_that_is_not_an_anchor():
    """The pattern is anchored, so prose mentioning a release is not one."""
    assert classify_one(title="fix: do not release the lock early")["bucket"] == "READY"


def test_draft_is_held():
    assert classify_one(isDraft=True)["bucket"] == "HELD"


def test_dirty_is_conflict():
    assert classify_one(mergeStateStatus="DIRTY")["bucket"] == "CONFLICT"


def test_missing_context_is_stuck():
    rollup = [
        {"name": name, "status": "COMPLETED", "conclusion": "SUCCESS"}
        for name in CONTEXTS[:2]
    ]
    assert classify_one(statusCheckRollup=rollup)["bucket"] == "STUCK"


def test_duplicate_context_is_stuck():
    rollup = [
        {"name": name, "status": "COMPLETED", "conclusion": "SUCCESS"}
        for name in CONTEXTS
    ]
    rollup.append(rollup[0])
    assert classify_one(statusCheckRollup=rollup)["bucket"] == "STUCK"


def test_pending_context_is_waiting():
    rollup = [
        {"name": name, "status": "COMPLETED", "conclusion": "SUCCESS"}
        for name in CONTEXTS[:2]
    ] + [{"name": "Test", "status": "IN_PROGRESS", "conclusion": None}]
    assert classify_one(statusCheckRollup=rollup)["bucket"] == "WAITING"


def test_failed_context_is_failing():
    rollup = [
        {"name": name, "status": "COMPLETED", "conclusion": "SUCCESS"}
        for name in CONTEXTS[:2]
    ] + [{"name": "Test", "status": "COMPLETED", "conclusion": "FAILURE"}]
    assert classify_one(statusCheckRollup=rollup)["bucket"] == "FAILING"


def test_extra_non_required_context_does_not_block_ready():
    rollup = [
        {"name": name, "status": "COMPLETED", "conclusion": "SUCCESS"}
        for name in CONTEXTS
    ] + [{"name": "optional", "status": "COMPLETED", "conclusion": "FAILURE"}]
    assert classify_one(statusCheckRollup=rollup)["bucket"] == "READY"


def test_title_is_truncated_to_the_dashboard_width():
    row = classify_one(title="x" * 200)
    assert len(row["title"]) == wq.TITLE_WIDTH


def test_non_dict_pr_entries_are_skipped():
    assert wq.classify(["junk", None], CONTEXTS, "^release-please--") == []


# --- end to end via stubs ---------------------------------------------------


STUB_GH = """#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "pr" && "$2" == "list" ]]; then cat "$PRSHEP_TEST_PRS"; exit 0; fi
if [[ "$1" == "api" ]]; then
  if [[ "$2" == *"/commits/"* ]]; then
    if [[ -n "${PRSHEP_TEST_MAIN_SHA_NEXT:-}" && -f "$TEST_ROOT/sha-read" ]]; then
      printf '%s\\n' "$PRSHEP_TEST_MAIN_SHA_NEXT"
    else
      : >"$TEST_ROOT/sha-read"
      printf '%s\\n' "$PRSHEP_TEST_MAIN_SHA"
    fi
    exit 0
  fi
  exit 1
fi
exit 2
"""

STUB_BD = """#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "ready" ]]; then cat "$PRSHEP_TEST_BD_JSON"; exit 0; fi
exit 1
"""

STUB_GIT = "#!/usr/bin/env bash\nprintf 'https://github.com/owner/repo.git\\n'\n"


@pytest.fixture()
def harness(tmp_path):
    """A stubbed gh/bd/git environment; returns a runner over the dashboard."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("gh", STUB_GH), ("bd", STUB_BD), ("git", STUB_GIT)):
        path = bin_dir / name
        path.write_text(body)
        path.chmod(0o755)

    prs_file = tmp_path / "prs.json"
    bd_file = tmp_path / "bd.json"
    prs_file.write_text(json.dumps([pr()]))
    bd_file.write_text("[]")

    env = dict(os.environ)
    env.update(
        PATH=f"{bin_dir}:/usr/bin:/bin",
        TEST_ROOT=str(tmp_path),
        PRSHEP_REPO="owner/repo",
        PRSHEP_DEFAULT_BRANCH="main",
        PRSHEP_REQUIRED_CONTEXTS="\n".join(CONTEXTS),
        PRSHEP_RELEASE_PATTERN="^release-please--",
        PRSHEP_TEST_PRS=str(prs_file),
        PRSHEP_TEST_BD_JSON=str(bd_file),
        PRSHEP_TEST_MAIN_SHA="a" * 40,
    )
    for leaked in ("PRSHEP_FCFS", "PRSHEP_STRICT_RANKING"):
        env.pop(leaked, None)

    class Harness:
        def __init__(self):
            self.env = env
            self.prs_file = prs_file
            self.bd_file = bd_file

        def set_prs(self, *rows):
            prs_file.write_text(json.dumps(list(rows)))

        def set_queue(self, *numbers):
            bd_file.write_text(
                json.dumps([{"metadata": {"pr": str(n)}} for n in numbers])
            )

        def run(self, *args):
            return subprocess.run(
                [sys.executable, str(SCRIPT), *args],
                capture_output=True,
                text=True,
                env=self.env,
            )

    return Harness()


def test_ready_and_ranked_pr_is_the_candidate(harness):
    harness.set_queue(42)
    result = harness.run()
    assert result.returncode == 0
    assert "-- READY  (1) --" in result.stdout
    assert "next merge is #42" in result.stdout


def test_empty_required_contexts_fails_closed(harness):
    harness.env["PRSHEP_REQUIRED_CONTEXTS"] = ""
    result = harness.run()
    assert result.returncode != 0
    assert "Fail-closed" in result.stderr


def test_undiscoverable_required_contexts_fails_closed(harness):
    del harness.env["PRSHEP_REQUIRED_CONTEXTS"]
    result = harness.run()
    assert result.returncode != 0
    assert "Fail-closed" in result.stderr


def test_unknown_argument_exits_two(harness):
    result = harness.run("--bogus")
    assert result.returncode == 2


def test_main_moving_during_inspection_holds_the_gate(harness):
    harness.env["PRSHEP_TEST_MAIN_SHA_NEXT"] = "b" * 40
    harness.set_queue(42)
    result = harness.run()
    assert result.returncode == 0
    assert "moved during inspection" in result.stdout
    assert "next merge" not in result.stdout


def test_unranked_ready_pr_warns_and_still_recommends(harness):
    result = harness.run()
    assert "UNRANKED AND READY: #42" in result.stdout
    assert "next merge is #42" in result.stdout


def test_unranked_ready_pr_in_strict_mode_holds_the_gate(harness):
    result = harness.run("--strict-ranking")
    assert "STRICT: gate held" in result.stdout
    assert "next merge" not in result.stdout


def test_strict_mode_via_environment(harness):
    harness.env["PRSHEP_STRICT_RANKING"] = "1"
    result = harness.run()
    assert "STRICT: gate held" in result.stdout


def test_fcfs_mode_skips_ranking(harness):
    harness.env["PRSHEP_FCFS"] = "1"
    result = harness.run()
    assert "FCFS mode" in result.stdout
    assert "next merge is #42" in result.stdout


def test_only_the_first_ranked_ready_pr_is_the_candidate(harness):
    harness.set_prs(pr(number=7), pr(number=42))
    harness.set_queue(42, 7)
    result = harness.run()
    assert "next merge is #42" in result.stdout


def test_ranked_pr_with_no_ready_prs_reaches_the_merge_gate(harness):
    """Regression: an empty READY set aborted the shell mid-output under
    `set -u`, and the EXIT trap masked it as exit 0 with a truncated dashboard.
    """
    harness.set_prs(pr(mergeStateStatus="DIRTY"))
    harness.set_queue(42)
    result = harness.run()
    assert result.returncode == 0
    assert "MERGE GATE" in result.stdout
    assert "unbound variable" not in result.stdout + result.stderr


def test_unranked_ready_pr_reaches_the_merge_gate(harness):
    """The mirror case: a non-empty READY set with an empty bead queue."""
    result = harness.run()
    assert result.returncode == 0
    assert "MERGE GATE" in result.stdout


def test_no_open_prs_still_reports_the_gate(harness):
    harness.set_prs()
    result = harness.run()
    assert result.returncode == 0
    assert "MERGE GATE" in result.stdout
    assert "nothing ranked is READY" in result.stdout


def test_bucket_sections_appear_in_precedence_order(harness):
    harness.set_prs(
        pr(number=1, isDraft=True),
        pr(number=2, mergeStateStatus="DIRTY"),
        pr(number=3),
    )
    result = harness.run()
    positions = [
        result.stdout.index(f"-- {bucket}  ")
        for bucket in ("READY", "CONFLICT", "HELD")
    ]
    assert positions == sorted(positions)


def test_malformed_bead_queue_is_ignored(harness):
    harness.bd_file.write_text("{not json")
    result = harness.run()
    assert result.returncode == 0
    assert "queue empty" in result.stdout
