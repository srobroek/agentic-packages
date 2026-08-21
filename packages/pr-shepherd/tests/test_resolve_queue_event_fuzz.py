#!/usr/bin/env python3
"""Seeded fuzz harness for resolve-queue-event.py.

The script decides which merge bead a watcher record wakes, and its two failure
modes are asymmetric: routing an event to the wrong bead merges the wrong PR,
while raising an unexpected exception aborts the whole drain. Four properties:

  P1  every input raises only ContractError or ResolutionError -- never a bare
      TypeError/AttributeError that escapes main()'s handlers as a traceback.
  P2  `resolve` never returns a `resolved`/`replay`/`duplicate` receipt whose
      repository/number disagree with the record it was handed.
  P3  a record type the script does not recognise is reported as `ignored`,
      never silently resolved against a bead.
  P4  `replay_unacknowledged` emits one receipt per unacknowledged shepherd
      event and rejects, rather than normalises, corrupt bead identity.

Axes generated: record type, every pullRequest field crossed with hostile
values, bead status/labels/metadata shapes -- seeded so a failure reproduces.

Run standalone for a larger corpus: FUZZ_CASES=40000 pytest <this file>
"""

from __future__ import annotations

import importlib.util
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / ".apm"
    / "skills"
    / "pr-shepherd"
    / "scripts"
    / "resolve-queue-event.py"
)
SEED = 20260817
CORPUS_SIZE = int(os.environ.get("FUZZ_CASES", "6000"))


def _load():
    spec = importlib.util.spec_from_file_location("resolve_queue_event_fuzz", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rq = _load()

SHA = "a" * 40

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
    "7",
    " 7 ",
    "+7",
    "\n",
    "o/r",
    "o/r/x",
    SHA,
    "x" * 300,
    [],
    {},
    [1],
    {"k": 1},
    10**20,
    "9" * 30,
)


def pull_request(**overrides):
    base = {
        "repository": "owner/repo",
        "number": 7,
        "title": "t",
        "headSha": SHA,
        "baseRef": "main",
        "labels": [],
        "priority": 2,
        "draft": False,
        "mergeable": True,
        "checks": "pass",
        "createdAt": "2026-08-17T00:00:00Z",
        "updatedAt": "2026-08-17T00:00:00Z",
        "state": "active",
        "activeSince": "2026-08-17T00:00:00Z",
    }
    base.update(overrides)
    return base


def dispatch(**overrides):
    return {"type": "dispatch", "pullRequest": pull_request(**overrides)}


def lifecycle(transition="updated", *, source="webhook", **overrides):
    record = {
        "type": "pr-lifecycle",
        "transition": transition,
        "source": source,
        "lifecycleKey": f"owner/repo#7#{transition}#opaque",
        "pullRequest": pull_request(**overrides),
    }
    if source == "webhook":
        record["deliveryId"] = "delivery-1"
        record["webhookAction"] = "synchronize"
    return record


def merge_bead(bead_id="mb-1", **metadata):
    return {
        "id": bead_id,
        "status": "open",
        "labels": ["agent:integrator"],
        "metadata": {"repo": "owner/repo", "pr": 7, **metadata},
    }


# --- P1: only contract vocabulary escapes -----------------------------------


# The membership tests `value not in {...}` raise TypeError on an unhashable
# value; that is its own xfailing case below, so the broad sweep draws hashable
# values for the four fields tested that way.
HASHABLE = tuple(value for value in HOSTILE if not isinstance(value, (list, dict)))


def _random_record(rnd):
    fields = sorted(rq.REQUIRED_PULL_REQUEST_FIELDS)
    pr = {field: rnd.choice(HOSTILE) for field in fields}
    for field in ("checks", "state"):
        pr[field] = rnd.choice(HASHABLE)
    return {
        "type": rnd.choice(
            ["dispatch", "pr-lifecycle", "webhook-error", "reconcile-error", "x", None]
        ),
        "pullRequest": rnd.choice([pr, pull_request(), None, [], "s"]),
        "transition": rnd.choice([*sorted(rq.LIFECYCLE_TRANSITIONS), *HASHABLE]),
        "source": rnd.choice(["webhook", "reconciliation", None, "x"]),
        "lifecycleKey": rnd.choice(HOSTILE),
        "deliveryId": rnd.choice(HOSTILE),
        "webhookAction": rnd.choice(HOSTILE),
        "message": rnd.choice(HOSTILE),
        "repository": rnd.choice(HOSTILE),
    }


def _random_beads(rnd):
    return [
        {
            "id": rnd.choice(HOSTILE),
            "status": rnd.choice(["open", "in_progress", "blocked", "closed", None, 1]),
            "labels": rnd.choice([["agent:integrator"], [], ["other"], [1]]),
            "metadata": rnd.choice(
                [
                    {
                        "repo": rnd.choice(HOSTILE),
                        "pr": rnd.choice(HOSTILE),
                        "head_sha": rnd.choice(HOSTILE),
                        "integration_owner": rnd.choice(HOSTILE),
                        "shepherd_event": rnd.choice(HOSTILE),
                        "shepherd_event_type": rnd.choice(HASHABLE),
                        "shepherd_event_head": rnd.choice(HOSTILE),
                        "shepherd_event_transition": rnd.choice(HASHABLE),
                        "shepherd_event_ack": rnd.choice(HOSTILE),
                    },
                    None,
                    [],
                    "s",
                ]
            ),
        }
        for _ in range(rnd.randint(0, 3))
    ]


def test_fuzz_only_contract_errors_escape():
    """P1. main() converts ContractError/ResolutionError to exit 1/2; anything
    else reaches the operator as a traceback with no receipt written.

    Bead labels are constrained to lists here so the crash on `labels: null`
    -- the shape real `bd list --json` emits -- stays isolated in its own
    xfailing case below rather than swamping this sweep.
    """
    rnd = random.Random(SEED)
    escapes = []
    for _ in range(CORPUS_SIZE):
        record = _random_record(rnd)
        beads = _random_beads(rnd)
        for call in (
            lambda: rq.resolve(record, beads),
            lambda: rq.replay_unacknowledged(beads),
        ):
            try:
                call()
            except (rq.ContractError, rq.ResolutionError):
                pass
            except Exception as error:  # noqa: BLE001 - the property under test
                escapes.append(
                    (
                        type(error).__name__,
                        str(error),
                        json.dumps(record, default=str),
                        json.dumps(beads, default=str),
                    )
                )
    assert not escapes, escapes[:3]


@pytest.mark.parametrize("call", ["resolve", "replay"])
def test_null_labels_from_bd_snapshot_must_not_crash(call):
    snapshot = [
        {"id": "orc-0q0m", "status": "open", "labels": None, "metadata": None},
        merge_bead(),
    ]
    if call == "resolve":
        assert rq.resolve(dispatch(), snapshot)["bead"] == "mb-1"
    else:
        assert rq.replay_unacknowledged(snapshot) == []


@pytest.mark.parametrize("labels", [None, 7, 1.5])
def test_non_iterable_labels_are_skipped_not_fatal(labels):
    """A non-list `labels` must mean "this bead carries no labels"."""
    snapshot = [{"id": "x", "status": "open", "labels": labels, "metadata": {}}]
    with pytest.raises(rq.ResolutionError):
        rq.resolve(dispatch(), snapshot)


def test_a_string_labels_value_is_not_iterated_per_character() -> None:
    """A bare string in `labels` is malformed, not a sequence of one-character labels.

    The old behaviour iterated it per character, so `"agent:integrator"` became the
    label set {'a','g','e','n','t',':',...} -- which could match nothing real but did
    silently mean "this bead has labels". Now a non-list value yields no labels, so
    the bead simply carries none.
    """
    assert rq._labels({"labels": "agent:integrator"}) == set()


@pytest.mark.parametrize(
    "record",
    [
        {"type": "pr-lifecycle", "transition": []},
        {"type": "pr-lifecycle", "transition": {"a": 1}},
        {"type": "pr-lifecycle", "transition": ["updated"]},
        dispatch(checks=[]),
        dispatch(state={}),
    ],
    ids=["transition-list", "transition-dict", "transition-list-valid", "checks", "state"],
)
def test_unhashable_enum_field_is_a_contract_error(record):
    with pytest.raises(rq.ContractError):
        rq.resolve(record, [merge_bead()])


@pytest.mark.parametrize("field", ["shepherd_event_type", "shepherd_event_transition"])
def test_unhashable_persisted_event_field_is_a_resolution_error(field):
    with pytest.raises(rq.ResolutionError):
        rq.replay_unacknowledged([queued(**{field: []})])


# --- P2: receipts agree with the record --------------------------------------


def test_receipt_identity_matches_the_record():
    """P2. Every successful receipt names the record's own repo/number/head."""
    rnd = random.Random(SEED + 1)
    for _ in range(500):
        number = rnd.randint(1, 9999)
        head = "".join(rnd.choice("0123456789abcdef") for _ in range(40))
        record = dispatch(number=number, headSha=head)
        beads = [
            merge_bead("other", repo="owner/repo", pr=number + 1),
            merge_bead("target", repo="owner/repo", pr=number),
            merge_bead("elsewhere", repo="other/repo", pr=number),
        ]
        result = rq.resolve(record, beads)
        assert result["bead"] == "target"
        assert result["repository"] == "owner/repo"
        assert result["number"] == number
        assert result["headSha"] == head


@pytest.mark.parametrize("raw_pr", ["7", 7.9, " 7 ", "+7", "0x7" and "007"])
def test_string_and_float_metadata_pr_still_match_pr_7(raw_pr):
    """int() coercion is deliberately lenient about bd's metadata typing.

    Recorded, not asserted as good: `7.9` matching PR 7 is a truncation, and a
    caller that wrote `pr: 7.9` would be routed to PR 7's bead silently.
    """
    assert rq.resolve(dispatch(), [merge_bead(pr=raw_pr)])["bead"] == "mb-1"


def test_boolean_metadata_pr_never_matches():
    with pytest.raises(rq.ResolutionError):
        rq.resolve(dispatch(number=1), [merge_bead(pr=True)])


# --- P3: unknown records are ignored, never resolved -------------------------


@pytest.mark.parametrize(
    "record_type",
    ["dispatch ", "Dispatch", "DISPATCH", "pr_lifecycle", "prlifecycle", "", None, 7],
)
def test_near_miss_record_types_are_ignored_not_resolved(record_type):
    """P3. No near-miss type may reach a bead: an ignored record leaves the
    queue untouched, whereas a mistyped one silently resolving would merge on
    evidence the validator never checked.
    """
    record = {"type": record_type, "pullRequest": pull_request()}
    result = rq.resolve(record, [merge_bead()])
    assert result == {"status": "ignored", "recordType": record_type}


def test_bd_envelope_around_the_record_is_not_unwrapped():
    """`_unwrap` is applied to the beads snapshot only, so an enveloped record
    reads as an unknown type and is ignored rather than misread.
    """
    enveloped = {"schema_version": 1, "data": dispatch()}
    assert rq.resolve(enveloped, [merge_bead()])["status"] == "ignored"


def test_beads_envelope_is_unwrapped():
    envelope = {"schema_version": 1, "data": [merge_bead()]}
    assert rq.resolve(dispatch(), envelope)["bead"] == "mb-1"


# --- dispatch gating --------------------------------------------------------


@pytest.mark.parametrize(
    "override",
    [
        {"draft": True},
        {"mergeable": False},
        {"mergeable": None},
        {"checks": "pending"},
        {"checks": "fail"},
        {"state": "queued"},
        {"state": "blocked"},
        {"state": "closed"},
        {"activeSince": None},
        {"activeSince": ""},
    ],
)
def test_dispatch_requires_a_fully_ready_pull_request(override):
    with pytest.raises(rq.ContractError):
        rq.resolve(dispatch(**override), [merge_bead()])


@pytest.mark.parametrize(
    "override",
    [
        {"checks": "PASS"},
        {"checks": "passed"},
        {"state": "ACTIVE"},
        {"priority": 5},
        {"priority": -1},
        {"priority": True},
        {"priority": 2.0},
        {"number": 0},
        {"number": True},
        {"number": "7"},
        {"repository": "owner/repo/extra"},
        {"repository": "owner repo"},
        {"repository": "/repo"},
        {"headSha": "xyz"},
        {"headSha": "a" * 6},
        {"headSha": "a" * 65},
        {"labels": ["ok", 1]},
        {"title": ""},
        {"draft": 0},
    ],
)
def test_dispatch_field_validation_is_exact(override):
    with pytest.raises(rq.ContractError):
        rq.resolve(dispatch(**override), [merge_bead()])


def test_head_anchor_mismatch_is_unresolved():
    with pytest.raises(rq.ResolutionError):
        rq.resolve(dispatch(), [merge_bead(head_sha="b" * 40)])


def test_head_anchor_comparison_is_case_sensitive():
    """Git object ids are lowercase from every gh/git read path, so an
    uppercase anchor is a corrupt anchor, not an equal one.
    """
    with pytest.raises(rq.ResolutionError):
        rq.resolve(dispatch(headSha=SHA), [merge_bead(head_sha=SHA.upper())])


# --- lifecycle gating -------------------------------------------------------


@pytest.mark.parametrize(
    "record",
    [
        lifecycle("failed", checks="pass"),
        lifecycle("merged", state="active"),
        lifecycle("closed", state="active"),
        lifecycle("merged", source="reconciliation", state="closed"),
        lifecycle("opened", source="nowhere"),
    ],
)
def test_impossible_lifecycle_combinations_are_rejected(record):
    with pytest.raises(rq.ContractError):
        rq.resolve(record, [merge_bead()])


@pytest.mark.parametrize("field", ["deliveryId", "webhookAction"])
def test_webhook_lifecycle_requires_delivery_provenance(field):
    record = lifecycle("updated")
    record[field] = ""
    with pytest.raises(rq.ContractError):
        rq.resolve(record, [merge_bead()])


@pytest.mark.parametrize("key", [None, "", 7, []])
def test_lifecycle_key_must_be_a_non_empty_string(key):
    record = lifecycle("updated")
    record["lifecycleKey"] = key
    with pytest.raises(rq.ContractError):
        rq.resolve(record, [merge_bead()])


def test_lifecycle_key_is_the_whole_dedupe_identity():
    """Two DIFFERENT transitions sharing one lifecycleKey collapse to one
    event, so the second is reported as an already-handled duplicate.

    ln mints a key per transition (`owner/repo#42#<transition>#<opaque>`), so
    this is only reachable from a producer that reuses a key -- recorded
    because nothing in this script enforces the producer's convention.
    """
    key = "owner/repo#7"
    bead = merge_bead(shepherd_event=f"lifecycle:{key}", shepherd_event_ack=f"lifecycle:{key}")
    updated = lifecycle("updated")
    updated["lifecycleKey"] = key
    merged = lifecycle("merged", state="closed")
    merged["lifecycleKey"] = key
    assert rq.resolve(updated, [bead])["status"] == "duplicate"
    assert rq.resolve(merged, [bead])["status"] == "duplicate"


# --- ownership and delivery state -------------------------------------------


def test_orchestrate_ownership_wins_over_a_generic_duplicate():
    beads = [
        merge_bead("orch", integration_owner="orchestrate"),
        merge_bead("generic"),
    ]
    assert rq.resolve(dispatch(), beads)["status"] == "ignored"


@pytest.mark.parametrize("status", ["closed", "done", None, "OPEN"])
def test_inactive_beads_are_not_candidates(status):
    bead = merge_bead()
    bead["status"] = status
    with pytest.raises(rq.ResolutionError):
        rq.resolve(dispatch(), [bead])


def test_ambiguous_ownership_is_unresolved():
    with pytest.raises(rq.ResolutionError):
        rq.resolve(dispatch(), [merge_bead("a"), merge_bead("b")])


def test_resolved_receipt_carries_the_full_metadata_write_set():
    result = rq.resolve(dispatch(), [merge_bead()])
    assert result["status"] == "resolved"
    assert result["deliveryState"] is None
    assert set(result["requiredMetadata"]) == {
        "shepherd_event",
        "shepherd_event_head",
        "shepherd_event_pending",
        "shepherd_event_transition",
        "shepherd_event_type",
    }


@pytest.mark.parametrize(
    ("tracked", "expected"),
    [
        ("shepherd_event_ack", "ack"),
        ("shepherd_event_sent", "sent"),
        ("shepherd_event_pending", "pending"),
    ],
)
def test_replay_reports_the_recorded_delivery_state(tracked, expected):
    key = f"dispatch:owner/repo#7@{SHA}"
    bead = merge_bead(shepherd_event=key, **{tracked: key})
    result = rq.resolve(dispatch(), [bead])
    assert (result["status"], result["deliveryState"]) == (
        "duplicate" if expected == "ack" else "replay",
        expected,
    )


def test_bead_without_an_id_is_unresolved():
    bead = merge_bead()
    bead["id"] = ""
    with pytest.raises(rq.ResolutionError):
        rq.resolve(dispatch(), [bead])


# --- watcher error records --------------------------------------------------


@pytest.mark.parametrize("record_type", ["webhook-error", "reconcile-error"])
def test_watcher_error_becomes_an_explicit_fallback(record_type):
    result = rq.resolve({"type": record_type, "message": "boom", "repository": "owner/repo"}, [])
    assert result["status"] == "fallback"
    assert result["action"] == "gate-check-and-pass"


@pytest.mark.parametrize("bad", [None, "", 7, [], {"k": 1}])
def test_watcher_error_without_a_message_is_invalid(bad):
    with pytest.raises(rq.ContractError):
        rq.resolve({"type": "webhook-error", "message": bad}, [])


def test_watcher_error_repository_must_be_owner_repo():
    with pytest.raises(rq.ContractError):
        rq.resolve({"type": "webhook-error", "message": "m", "repository": "nope"}, [])


# --- P4: replay of unacknowledged events ------------------------------------


def queued(bead_id="mb-1", **overrides):
    metadata = {
        "shepherd_event": f"dispatch:owner/repo#7@{SHA}",
        "shepherd_event_type": "dispatch",
        "shepherd_event_head": SHA,
        "shepherd_event_transition": "ready",
    }
    metadata.update(overrides)
    return merge_bead(bead_id, **metadata)


def test_replay_emits_one_receipt_per_unacknowledged_event():
    """P4. Receipts are sorted by bead id so a caller's ack loop is stable."""
    other = queued("b2", pr=8, shepherd_event=f"dispatch:owner/repo#8@{SHA}")
    results = rq.replay_unacknowledged([other, queued("b1")])
    assert [r["bead"] for r in results] == ["b1", "b2"]
    assert all(r["status"] == "replay" for r in results)


def test_replay_skips_acknowledged_events():
    key = f"dispatch:owner/repo#7@{SHA}"
    assert rq.replay_unacknowledged([queued(shepherd_event_ack=key)]) == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"shepherd_event": f"dispatch:owner/repo#8@{SHA}"},
        {"shepherd_event": "lifecycle:x", "shepherd_event_type": "dispatch"},
        {"shepherd_event_type": "ready"},
        {"shepherd_event_type": None},
        {"shepherd_event_head": "zzz"},
        {"shepherd_event_head": None},
        {"repo": "nope"},
        {"pr": "x"},
        {"pr": None},
        {"pr": True},
        {"pr": 0},
        {"shepherd_event_type": "pr-lifecycle", "shepherd_event": "notlifecycle:x"},
        {
            "shepherd_event_type": "pr-lifecycle",
            "shepherd_event": "lifecycle:x",
            "shepherd_event_transition": None,
        },
    ],
)
def test_replay_rejects_corrupt_queued_identity(overrides):
    """Corrupt persisted identity must stop the drain, not be normalised: the
    receipt is what a later ack is matched against.
    """
    with pytest.raises(rq.ResolutionError):
        rq.replay_unacknowledged([queued(**overrides)])


def test_replay_rejects_duplicate_ownership_before_reading_events():
    with pytest.raises(rq.ResolutionError):
        rq.replay_unacknowledged([merge_bead("a"), merge_bead("b")])


def test_replay_ignores_orchestrate_owned_and_unlabelled_beads():
    others = [
        queued("orch", integration_owner="orchestrate"),
        {"id": "plain", "status": "open", "labels": ["agent:coder"], "metadata": {}},
    ]
    assert [r["bead"] for r in rq.replay_unacknowledged([*others, queued("mine")])] == ["mine"]


def test_replay_normalises_a_legacy_bead_without_a_pending_marker():
    result = rq.replay_unacknowledged([queued()])[0]
    assert result["deliveryState"] == "untracked"
    assert result["requiredMetadata"] == {"shepherd_event_pending": f"dispatch:owner/repo#7@{SHA}"}


# --- bounded work -----------------------------------------------------------


def test_large_snapshot_stays_linear():
    """A 200k-bead snapshot resolves in one pass; the target is last so a
    quadratic scan or early-exit bug shows up as time, not a wrong answer.
    """
    snapshot = [
        {
            "id": f"x{i}",
            "status": "open",
            "labels": ["agent:integrator"],
            "metadata": {"repo": "owner/other", "pr": i + 1},
        }
        for i in range(200_000)
    ]
    snapshot.append(merge_bead())
    assert rq.resolve(dispatch(), snapshot)["bead"] == "mb-1"
    assert rq.replay_unacknowledged(snapshot) == []


# --- CLI surface ------------------------------------------------------------


def _run(record: str, beads_path: Path, *extra: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--beads-file", str(beads_path), *extra],
        input=record,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_exit_codes(tmp_path):
    beads = tmp_path / "beads.json"
    beads.write_text(json.dumps([merge_bead()]), encoding="utf-8")
    assert _run(json.dumps(dispatch()), beads).returncode == 0
    assert _run("not json", beads).returncode == 1
    assert _run("", beads).returncode == 1
    assert _run(json.dumps(dispatch(draft=True)), beads).returncode == 1
    assert _run(json.dumps(dispatch(number=99)), beads).returncode == 2


def test_cli_reports_a_missing_snapshot_as_invalid_input(tmp_path):
    completed = _run(json.dumps(dispatch()), tmp_path / "absent.json")
    assert completed.returncode == 1
    assert "cannot read JSON" in completed.stderr


def test_cli_reports_a_non_utf8_snapshot_as_invalid_input(tmp_path):
    beads = tmp_path / "beads.bin"
    beads.write_bytes(b"\xff\xfe[]")
    completed = _run(json.dumps(dispatch()), beads)
    assert completed.returncode == 1
    assert "Traceback" not in completed.stderr


def test_cli_stdin_that_is_not_utf8_is_invalid_input(tmp_path):
    beads = tmp_path / "beads.json"
    beads.write_text("[]", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--beads-file", str(beads)],
        input=b"\xff\xfe",
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 1


def test_cli_emits_deterministic_sorted_json(tmp_path):
    beads = tmp_path / "beads.json"
    beads.write_text(json.dumps([merge_bead()]), encoding="utf-8")
    first = _run(json.dumps(dispatch()), beads).stdout
    assert first == _run(json.dumps(dispatch()), beads).stdout
    payload = json.loads(first)
    assert list(payload) == sorted(payload)


def test_script_is_executable():
    assert SCRIPT.stat().st_mode & 0o111
