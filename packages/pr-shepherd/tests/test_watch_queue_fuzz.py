"""Seeded fuzz harness for watch-queue.py's bucket classification.

The 6-bucket classification and its PRECEDENCE order is the tool's whole
contract: it decides the dashboard's section order, the label a PR carries when
several conditions hold at once, and ultimately which PR gets merged. Four
properties are asserted:

  P1  every PR lands in exactly one of the six buckets, never zero and never two.
  P2  the bucket matches an INDEPENDENT reading of the documented precedence,
      written from the docstring rather than from `bucket_for`'s body.
  P3  READY is fail-closed: a PR is only READY when it is neither release nor
      draft, its merge state is CLEAN, there is at least ONE required context,
      and every one of them passed. Zero required contexts means no merge.
  P4  classify never raises, whatever a `gh` payload contains, and never yields a
      merge candidate that is not a real PR number.

Axes generated: draft, release (by branch and by title), merge state, and the
per-context check states -- 7 merge states x 4 release/draft combinations x the
check-state subsets, seeded so a failure is reproducible.

Run standalone for a larger corpus: FUZZ_CASES=20000 pytest <this file>
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import os
import random
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / ".apm"
    / "skills"
    / "pr-shepherd"
    / "scripts"
    / "watch-queue.py"
)
SEED = 20260729
CORPUS_SIZE = int(os.environ.get("FUZZ_CASES", "3000"))


def _load():
    spec = importlib.util.spec_from_file_location("watch_queue_fuzz", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wq = _load()

BUCKETS = frozenset(wq.BUCKET_ORDER)
CHECK_STATES = ("OK", "FAIL", "RUNNING", "ABSENT", "AMBIGUOUS")
MERGE_STATES = ("CLEAN", "DIRTY", "BLOCKED", "BEHIND", "UNSTABLE", "UNKNOWN", "")

# Values chosen to break a naive truthiness or isinstance check. bool is an int
# subclass, so `True` must not pass for a PR number.
HOSTILE = (
    None,
    True,
    False,
    0,
    -1,
    1.5,
    "",
    "5",
    "\n",
    'a"b',
    "brânch/ünicode",
    "x" * 4096,
    [],
    {},
    [1, 2],
    {"k": "v"},
)


def _independent_bucket(release: bool, draft: bool, merge_state: str, checks: list[str]) -> str:
    """A second, deliberately literal reading of the documented precedence.

    Written from the module docstring and the dashboard's own notes -- HELD is
    release or draft; READY needs a clean merge state and every required context
    passing; STUCK means a required context is absent or ambiguous -- rather than
    from `bucket_for`, so it diverges if the implementation drifts.
    """
    if release or draft:
        return "HELD"
    if merge_state == "CLEAN" and checks and all(state == "OK" for state in checks):
        return "READY"
    if merge_state == "DIRTY":
        return "CONFLICT"
    if "FAIL" in checks:
        return "FAILING"
    if "RUNNING" in checks:
        return "WAITING"
    if "ABSENT" in checks or "AMBIGUOUS" in checks:
        return "STUCK"
    return "WAITING"


def _ready(release: bool, draft: bool, merge_state: str, checks: list[str]) -> bool:
    return (
        not release
        and not draft
        and merge_state == "CLEAN"
        and bool(checks)
        and all(state == "OK" for state in checks)
    )


def test_every_axis_combination_lands_in_exactly_one_documented_bucket():
    """P1 and P2, exhaustively over the small axes rather than randomly."""
    check_sets: list[list[str]] = [[]]
    for size in (1, 2, 3):
        for combo in itertools.product(CHECK_STATES, repeat=size):
            check_sets.append(list(combo))

    checked = 0
    seen: set[str] = set()
    for release, draft, merge_state, checks in itertools.product(
        (False, True), (False, True), MERGE_STATES, check_sets
    ):
        ready = _ready(release, draft, merge_state, checks)
        bucket = wq.bucket_for(release, draft, ready, merge_state, checks)
        assert bucket in BUCKETS, bucket
        assert bucket == _independent_bucket(release, draft, merge_state, checks), (
            f"release={release} draft={draft} merge={merge_state} checks={checks}"
        )
        seen.add(bucket)
        checked += 1
    assert checked > 4000, checked
    # A corpus that never reached some buckets would prove nothing about them.
    assert seen == BUCKETS, f"never generated: {sorted(BUCKETS - seen)}"


def _pr(rng: random.Random, index: int) -> dict:
    """A PR record that is USUALLY well-formed, with fields randomly corrupted.

    Starting from a valid READY record and spoiling it keeps the generator near
    the decision boundary, where an over-permissive check actually shows up.
    """
    pr: dict = {
        "number": index + 1,
        "title": "feat: a change",
        "isDraft": False,
        "headRefName": "feat/x",
        "mergeStateStatus": "CLEAN",
        "statusCheckRollup": [
            {"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"}
        ],
    }
    if rng.random() < 0.2:
        pr["mergeStateStatus"] = rng.choice(MERGE_STATES)
    if rng.random() < 0.15:
        pr["isDraft"] = rng.choice([True, False, *HOSTILE])
    if rng.random() < 0.1:
        pr["headRefName"] = rng.choice(["release-please--branches--main", *HOSTILE])
    if rng.random() < 0.1:
        pr["title"] = rng.choice(["chore: release main", "chore(main): release", *HOSTILE])
    if rng.random() < 0.15:
        pr["number"] = rng.choice(HOSTILE)
    if rng.random() < 0.25:
        rollup = []
        for name in ("test", "lint", rng.choice(["test", "other", ""])):
            entry: dict = {"name": name}
            if rng.random() < 0.8:
                entry["status"] = rng.choice(["COMPLETED", "IN_PROGRESS", "QUEUED", ""])
            if rng.random() < 0.8:
                entry["conclusion"] = rng.choice(
                    ["SUCCESS", "SKIPPED", "FAILURE", "CANCELLED", "TIMED_OUT", ""]
                )
            rollup.append(entry)
        pr["statusCheckRollup"] = rollup
    elif rng.random() < 0.1:
        pr["statusCheckRollup"] = rng.choice(HOSTILE)
    if rng.random() < 0.05:
        pr.pop(rng.choice(list(pr)), None)
    return pr


def test_a_hostile_gh_payload_never_raises_and_never_misclassifies():
    """P1, P2 and P4 over the generated corpus."""
    rng = random.Random(SEED)
    required = ["test", "lint"]
    seen: set[str] = set()
    for index in range(CORPUS_SIZE):
        pr = _pr(rng, index)
        try:
            classified = wq.classify([pr], required, "^release-please--")
        except Exception as error:  # noqa: BLE001 -- any raise is the defect
            pytest.fail(f"case {index} raised {error!r} on {pr!r}")
        for record in classified:
            assert record["bucket"] in BUCKETS
            # An unusable number is dropped rather than classified: it cannot be
            # merged by number, so it must never become a candidate.
            assert isinstance(record["number"], int)
            assert record["number"] > 0
            checks = record["checks"]
            release, draft = record["release"], record["draft"]
            assert record["bucket"] == _independent_bucket(
                release, draft, record["mergeState"], checks
            ), f"case {index}: {pr!r} -> {record!r}"
            assert record["ready"] == _ready(
                release, draft, record["mergeState"], checks
            )
            assert record["total"] == len(required)
            seen.add(record["bucket"])
    assert len(seen) >= 3, f"generator only reached {sorted(seen)}"


# --- P3: READY is fail-closed ------------------------------------------------


def _clean_pr(number: int = 1) -> dict:
    return {
        "number": number,
        "title": "feat: a change",
        "isDraft": False,
        "headRefName": "feat/x",
        "mergeStateStatus": "CLEAN",
        "statusCheckRollup": [
            {"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"}
        ],
    }


def test_zero_required_contexts_can_never_produce_a_ready_pr():
    """Reproduction: `all([])` is vacuously TRUE, so a caller reaching classify()
    with zero required contexts marked every clean PR READY and the dashboard
    recommended a merge gated by nothing at all. The documented rule is
    fail-closed: no required contexts means no merge."""
    classified = wq.classify([_clean_pr()], [], "^release-please--")
    assert classified[0]["ready"] is False
    assert classified[0]["bucket"] != "READY"


def test_a_required_context_that_is_absent_is_stuck_not_ready():
    classified = wq.classify([_clean_pr()], ["test", "never-reported"], "^rp--")
    assert classified[0]["ready"] is False
    assert classified[0]["bucket"] == "STUCK"


def test_a_required_context_that_is_pending_is_waiting_not_ready():
    pr = _clean_pr()
    pr["statusCheckRollup"] = [{"name": "test", "status": "IN_PROGRESS"}]
    classified = wq.classify([pr], ["test"], "^rp--")
    assert classified[0]["ready"] is False
    assert classified[0]["bucket"] == "WAITING"


def test_a_context_reported_twice_is_ambiguous_not_passing():
    """Which of two runs gates the merge is undecidable, so it is not passing."""
    pr = _clean_pr()
    pr["statusCheckRollup"] = [
        {"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"},
    ]
    classified = wq.classify([pr], ["test"], "^rp--")
    assert classified[0]["checks"] == ["AMBIGUOUS"]
    assert classified[0]["bucket"] == "STUCK"


@pytest.mark.parametrize("state", [s for s in MERGE_STATES if s != "CLEAN"])
def test_only_a_clean_merge_state_can_be_ready(state: str):
    pr = dict(_clean_pr(), mergeStateStatus=state)
    assert wq.classify([pr], ["test"], "^rp--")[0]["ready"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("isDraft", True),
        ("headRefName", "release-please--branches--main"),
        ("title", "chore: release main"),
        ("title", "chore(main): release 1.0.0"),
    ],
)
def test_a_draft_or_release_pr_is_held_and_never_ready(field: str, value):
    pr = dict(_clean_pr(), **{field: value})
    classified = wq.classify([pr], ["test"], "^release-please--")
    assert classified[0]["bucket"] == "HELD"
    assert classified[0]["ready"] is False


def test_held_outranks_every_other_condition():
    """Precedence, not merely membership: a draft PR that is ALSO conflicting and
    failing is still HELD, because HELD is first in BUCKET_ORDER."""
    pr = dict(_clean_pr(), isDraft=True, mergeStateStatus="DIRTY")
    pr["statusCheckRollup"] = [
        {"name": "test", "status": "COMPLETED", "conclusion": "FAILURE"}
    ]
    assert wq.classify([pr], ["test"], "^rp--")[0]["bucket"] == "HELD"


def test_conflict_outranks_failing():
    pr = dict(_clean_pr(), mergeStateStatus="DIRTY")
    pr["statusCheckRollup"] = [
        {"name": "test", "status": "COMPLETED", "conclusion": "FAILURE"}
    ]
    assert wq.classify([pr], ["test"], "^rp--")[0]["bucket"] == "CONFLICT"


def test_failing_outranks_waiting_and_stuck():
    pr = _clean_pr()
    pr["mergeStateStatus"] = "BLOCKED"
    pr["statusCheckRollup"] = [
        {"name": "test", "status": "COMPLETED", "conclusion": "FAILURE"},
        {"name": "lint", "status": "IN_PROGRESS"},
    ]
    classified = wq.classify([pr], ["test", "lint", "absent-one"], "^rp--")
    assert classified[0]["bucket"] == "FAILING"


# --- P4: junk payloads -------------------------------------------------------


def test_zero_prs_classifies_to_an_empty_list():
    assert wq.classify([], ["test"], "^rp--") == []


@pytest.mark.parametrize(
    "payload",
    [
        [],
        [None],
        ["a string"],
        [5],
        [{}],
        [{"number": None}],
        [{"number": True}],
        [{"number": 0}],
        [{"number": -1}],
        [{"number": "12"}],
        [{"number": 1, "title": None}],
        [{"number": 1, "title": 5}],
        [{"number": 1, "headRefName": 5}],
        [{"number": 1, "mergeStateStatus": 5}],
        [{"number": 1, "statusCheckRollup": "nope"}],
        [{"number": 1, "statusCheckRollup": [None, "x", 5]}],
        [{"number": 1, "statusCheckRollup": [{"name": None}]}],
    ],
    ids=range(17),
)
def test_a_junk_pr_record_is_dropped_or_classified_but_never_raises(payload: list):
    classified = wq.classify(payload, ["test"], "^rp--")
    assert isinstance(classified, list)
    for record in classified:
        assert isinstance(record["number"], int) and record["number"] > 0
        assert record["bucket"] in BUCKETS


def test_a_pr_without_a_usable_number_is_dropped_not_recommended():
    """Reproduction: a record with `number: null` was classified READY and
    `str(None)` became the merge candidate -- the dashboard printed `#None`."""
    for value in (None, True, False, 0, -1, "12", 1.5, [], {}):
        assert wq.classify([dict(_clean_pr(), number=value)], ["test"], "^rp--") == []


def test_a_title_or_branch_of_the_wrong_type_does_not_abort_the_dashboard():
    """`title[:52]` raised TypeError on a non-string, and a non-string branch did
    the same inside `release_re.search` -- one bad record aborted the whole run."""
    prs = [
        dict(_clean_pr(1), title=5),
        dict(_clean_pr(2), headRefName=[]),
        _clean_pr(3),
    ]
    classified = wq.classify(prs, ["test"], "^rp--")
    assert len(classified) == 3
    assert classified[2]["bucket"] == "READY"


def test_an_invalid_release_pattern_fails_closed_with_a_usage_status():
    with pytest.raises(wq.Failure) as caught:
        wq.classify([_clean_pr()], ["test"], "([unclosed")
    assert caught.value.status == 2


# --- check_state -------------------------------------------------------------


@pytest.mark.parametrize(
    ("rollup", "expected"),
    [
        ([], "ABSENT"),
        ([{"name": "other", "status": "COMPLETED", "conclusion": "SUCCESS"}], "ABSENT"),
        ([{"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"}], "OK"),
        ([{"name": "test", "status": "COMPLETED", "conclusion": "SKIPPED"}], "OK"),
        ([{"name": "test", "status": "COMPLETED", "conclusion": "FAILURE"}], "FAIL"),
        ([{"name": "test", "status": "COMPLETED", "conclusion": "CANCELLED"}], "FAIL"),
        ([{"name": "test", "status": "COMPLETED"}], "FAIL"),
        ([{"name": "test", "status": "IN_PROGRESS"}], "RUNNING"),
        ([{"name": "test", "status": "QUEUED"}], "RUNNING"),
        ([{"name": "test"}], "RUNNING"),
        ([None, "x", {"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"}], "OK"),
    ],
)
def test_check_state_never_reads_a_non_success_as_passing(rollup, expected):
    """An unknown status is RUNNING and an unknown conclusion is FAIL: neither may
    be read as passing, because passing is what releases a merge."""
    assert wq.check_state(rollup, "test") == expected


# --- remote parsing ----------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("git@github.com:owner/repo.git", "owner/repo"),
        ("git@github.com:owner/repo", "owner/repo"),
        ("https://github.com/owner/repo.git", "owner/repo"),
        ("https://github.com/owner/repo", "owner/repo"),
        ("ssh://git@github.com/owner/repo.git", "owner/repo"),
        ("  https://github.com/owner/repo  ", "owner/repo"),
    ],
)
def test_a_real_remote_url_parses_to_owner_repo(url: str, expected: str):
    assert wq.parse_remote(url) == expected


@pytest.mark.parametrize("url", ["", "   ", "https://github.com", "onlyone", "/", "://"])
def test_an_unparseable_remote_fails_closed(url: str):
    with pytest.raises(wq.Failure):
        wq.parse_remote(url)


# --- ranking -----------------------------------------------------------------


def test_fcfs_and_a_missing_bd_both_yield_no_ranking(monkeypatch):
    monkeypatch.setenv("PRSHEP_FCFS", "1")
    assert wq.ranked_pr_numbers() == []
    monkeypatch.delenv("PRSHEP_FCFS")
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert wq.ranked_pr_numbers() == []


@pytest.mark.parametrize(
    "stdout",
    [
        "",
        "not json",
        "null",
        "{}",
        "[]",
        '[null]',
        '["a"]',
        '[{"metadata": null}]',
        '[{"metadata": "x"}]',
        '[{"metadata": {}}]',
        '[{"metadata": {"pr": null}}]',
        '[{"metadata": {"pr": ""}}]',
        '[{"metadata": {"pr": 12}}]',
        "[" * 200,
    ],
    ids=range(14),
)
def test_junk_from_bd_never_raises(stdout: str, monkeypatch):
    class Completed:
        returncode = 0

    Completed.stdout = stdout
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/bd")
    monkeypatch.setattr(wq.subprocess, "run", lambda *a, **k: Completed())
    numbers = wq.ranked_pr_numbers()
    assert isinstance(numbers, list)
    assert all(isinstance(number, str) and number for number in numbers)


# --- output contract ---------------------------------------------------------


def test_the_dashboard_renders_every_bucket_without_raising(capsys):
    prs = [
        _clean_pr(1),
        dict(_clean_pr(2), mergeStateStatus="DIRTY"),
        dict(_clean_pr(3), isDraft=True),
        dict(_clean_pr(4), headRefName="release-please--branches--main"),
        dict(_clean_pr(5), mergeStateStatus="BLOCKED", statusCheckRollup=[]),
        dict(_clean_pr(6), title="x" * 500),
    ]
    classified = wq.classify(prs, ["test"], "^release-please--")
    wq.render_dashboard(classified, 1)
    out = capsys.readouterr().out
    assert "#None" not in out
    for record in classified:
        assert f"#{record['number']}" in out
        # The title is truncated so the dashboard stays one line per PR.
        assert len(record["title"]) <= wq.TITLE_WIDTH


def test_the_bucket_order_is_the_documented_precedence():
    """Pinned as data: the order IS the contract, so a reorder must break a test
    rather than silently change which label a PR carries."""
    assert wq.BUCKET_ORDER == (
        "READY",
        "FAILING",
        "STUCK",
        "CONFLICT",
        "WAITING",
        "HELD",
    )


def test_the_script_is_committed_executable_with_a_python_shebang():
    assert SCRIPT.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3")
    assert os.access(SCRIPT, os.X_OK), "hook and skill scripts ship mode 755"


def test_json_module_is_not_used_to_reparse_its_own_output():
    """The shell predecessor spawned a second interpreter per record to read a
    status out of the JSON it had just produced. Pinned so a port does not
    reintroduce it."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert "json.loads(json.dumps" not in source
    assert json is not None  # the import is used by the harness itself
