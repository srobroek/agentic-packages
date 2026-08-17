"""Seeded fuzz harness for landing-contract.py's waiter and recovery machines.

The script shells out to `bd`, `gh`, and `git`. Nothing here may reach a real
binary, a real beads store, or GitHub, so `_run` and `subprocess` are both
replaced: `Store` answers `bd` from an in-memory bead table that models the
subset of beads semantics the contract depends on (deterministic ids, claim
refusal when an assignee exists, `--set-metadata` merges, parent-child
dependency rows), and any unrouted argv raises rather than executing.

Four properties are asserted:

  P1  no state the contract can itself produce may wedge the merge slot for a
      DIFFERENT holder, and every such state has a recovery command that clears it.
  P2  a slot acquired by any code path is released on every exit from that path,
      including an exit through Fail.
  P3  malformed `bd`/`gh`/`git` output fails closed with a documented exit code
      (2, 10, 11, 12, 75) and never a traceback, and never reads as a passed check.
  P4  a retry after a transient failure at an unchanged head is not refused.

Run standalone for a larger corpus: FUZZ_CASES=20000 pytest <this file>
"""

from __future__ import annotations

import importlib.util
import json
import os
import random
import subprocess
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / ".apm"
    / "skills"
    / "pr-shepherd"
    / "scripts"
    / "landing-contract.py"
)
SEED = 20260817
CORPUS_SIZE = int(os.environ.get("FUZZ_CASES", "2000"))

HEAD = "a" * 40
STALE_HEAD = "b" * 40
MERGE_SHA = "c" * 40
REMOTE_BASE = "d" * 40
RECORDED_BASE = "e" * 40
DOCUMENTED_EXITS = frozenset({0, 2, 10, 11, 12, 75})


def load():
    """A fresh module per test: the queue cache and armed holder are module state."""
    spec = importlib.util.spec_from_file_location("landing_contract_fuzz", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cp(stdout="", returncode=0):
    return subprocess.CompletedProcess([], returncode, stdout, None)


def _scalar(value):
    """Unhashable generated field values are compared as their repr, never dropped."""
    try:
        hash(value)
    except TypeError:
        return repr(value)
    return value


class Escaped(AssertionError):
    """An argv reached the real process boundary. Never acceptable in this suite."""


class NoSubprocess:
    PIPE = subprocess.PIPE
    DEVNULL = subprocess.DEVNULL
    STDOUT = subprocess.STDOUT
    CompletedProcess = subprocess.CompletedProcess

    def __init__(self, handler=None):
        self._handler = handler

    def run(self, argv, *args, **kwargs):
        if self._handler is not None:
            return self._handler(argv)
        raise Escaped(f"real subprocess.run: {argv}")


class Store:
    """An in-memory beads store plus a scriptable gh/git responder."""

    def __init__(self):
        self.beads: dict[str, dict] = {}
        self.slot = {"id": "slot-1", "available": True, "holder": ""}
        self.argv: list[tuple] = []
        self._clock = 0
        self._envelope = False
        self.gh_handler = None
        self.git_handler = None
        self.bd_filter = None

    # -- beads ----------------------------------------------------------------

    def _stamp(self) -> str:
        self._clock += 1
        return f"2026-01-01T00:00:{self._clock:02d}Z"

    def bead(self, ident, **overrides) -> dict:
        record = {
            "id": ident, "status": "open", "assignee": "", "labels": [],
            "created_at": self._stamp(), "metadata": {}, "dependencies": [],
            "comments": [],
        }
        record.update(overrides)
        self.beads[ident] = record
        return record

    def waiter(self, lc, holder, generation=1, *, actor="actor-a", linked=True,
               status="open", created_at=None) -> str:
        ident = lc.waiter_id("slot-1", holder, generation)
        self.bead(
            ident, status=status, labels=[lc.WAITER_LABEL],
            created_at=created_at or self._stamp(),
            metadata={
                "slot_id": "slot-1", "holder": holder, "generation": generation,
                "waiter_id": ident, "lease_actor": actor,
            },
            dependencies=(
                [{"type": "parent-child", "depends_on_id": "slot-1", "id": "slot-1"}]
                if linked else []
            ),
        )
        return ident

    def waiters(self) -> list[tuple[str, str]]:
        return sorted(
            (b["id"], b["status"]) for b in self.beads.values()
            if "gt:slot-waiter" in (b.get("labels") or [])
        )

    def bd(self, args, env_extra=None):
        if self.bd_filter is not None:
            forced = self.bd_filter(args)
            if forced is not None:
                return forced
        a = list(args)
        if a[:2] == ["merge-slot", "create"]:
            return cp()
        if a[:2] == ["merge-slot", "check"]:
            return cp(json.dumps(self.slot))
        if a[:2] == ["merge-slot", "acquire"]:
            if not self.slot["available"]:
                return cp("", 1)
            self.slot.update(available=False, holder=a[a.index("--holder") + 1])
            return cp()
        if a[:2] == ["merge-slot", "release"]:
            if self.slot["holder"] != a[a.index("--holder") + 1]:
                return cp("", 1)
            self.slot.update(available=True, holder="")
            return cp()
        if a[:2] == ["audit", "record"]:
            return cp()
        if a[0] == "where":
            return cp(json.dumps({"path": "/nonexistent-beads-dir", "prefix": "px"}))
        if a[0] == "create":
            return self._create(a)
        if a[0] in ("list", "ready"):
            return cp(json.dumps(self._query(a)))
        if a[0] == "show":
            record = self.beads.get(a[1])
            if record is None:
                return cp("", 1)
            payload = {"data": [record]} if self._envelope else [record]
            return cp(json.dumps(payload))
        if a[0] == "update":
            return self._update(a, env_extra)
        if a[0] == "close":
            record = self.beads.get(a[1])
            if record is None:
                return cp("", 1)
            record["status"] = "closed"
            return cp()
        if a[0] == "comment":
            record = self.beads.get(a[1])
            if record is None:
                return cp("", 1)
            rows = record.get("comments")
            record["comments"] = (rows if isinstance(rows, list) else []) + [a[2]]
            return cp()
        if a[0] == "comments":
            record = self.beads.get(a[1]) or {}
            return cp(json.dumps([{"text": t} for t in record.get("comments") or []]))
        if a[:2] == ["dep", "add"]:
            child = self.beads.get(a[2])
            if child is None:
                return cp("", 1)
            kind = a[a.index("--type") + 1] if "--type" in a else "blocks"
            rows = child.get("dependencies")
            child["dependencies"] = (rows if isinstance(rows, list) else []) + [
                {"type": kind, "depends_on_id": a[3], "id": a[3]}
            ]
            return cp()
        raise Escaped(f"unrouted bd call: {a}")

    def _create(self, a):
        if "--ephemeral" in a and "--id" not in a:
            return cp("", 1)
        ident = a[a.index("--id") + 1] if "--id" in a else f"auto-{len(self.beads)}"
        if ident in self.beads:
            return cp("", 1)
        self.bead(
            ident,
            labels=a[a.index("--labels") + 1].split(",") if "--labels" in a else [],
            metadata=json.loads(a[a.index("--metadata") + 1]) if "--metadata" in a else {},
        )
        return cp()

    def _update(self, a, env_extra):
        record = self.beads.get(a[1])
        if record is None:
            return cp("", 1)
        if "--claim" in a:
            if record.get("assignee"):
                return cp("", 1)
            actor = (env_extra or {}).get("BEADS_ACTOR") or os.environ.get("BEADS_ACTOR", "")
            record.update(assignee=actor, status="in_progress")
        if "--assignee" in a:
            record["assignee"] = a[a.index("--assignee") + 1]
        if "--status" in a:
            record["status"] = a[a.index("--status") + 1]
        for index, token in enumerate(a):
            if token == "--set-metadata":
                key, _, value = a[index + 1].partition("=")
                if not isinstance(record.get("metadata"), dict):
                    record["metadata"] = {}
                record["metadata"][key] = value
        return cp()

    def _query(self, a):
        # Every read is .get: a generated record may be missing any field, and the
        # store must model bd returning the row as stored, not raise on it.
        rows = list(self.beads.values())
        if "--id" in a:
            rows = [r for r in rows if r.get("id") == a[a.index("--id") + 1]]
        if "--label" in a:
            wanted = a[a.index("--label") + 1]
            rows = [r for r in rows if wanted in (r.get("labels") or [])]
        if "--label-any" in a:
            wanted = set(a[a.index("--label-any") + 1].split(","))
            rows = [
                r for r in rows
                if wanted & {_scalar(x) for x in (r.get("labels") or [])}
            ]
        if "--status" in a:
            wanted = set(a[a.index("--status") + 1].split(","))
            rows = [r for r in rows if _scalar(r.get("status")) in wanted]
        if "--unassigned" in a:
            rows = [r for r in rows if not r.get("assignee")]
        for index, token in enumerate(a):
            if token == "--metadata-field":
                key, _, value = a[index + 1].partition("=")
                rows = [r for r in rows if str((r.get("metadata") or {}).get(key)) == value]
        if "--all" not in a and "--status" not in a:
            rows = [r for r in rows if _scalar(r.get("status")) != "closed"]
        return rows

    # -- installation ---------------------------------------------------------

    def install(self, lc, subprocess_handler=None):
        def run(argv, env_extra=None, **kwargs):
            self.argv.append(tuple(argv))
            if argv[0] == "bd":
                self._envelope = bool(env_extra and env_extra.get("BD_JSON_ENVELOPE"))
                try:
                    return self.bd(argv[1:], env_extra)
                finally:
                    self._envelope = False
            if argv[0] == "gh":
                return self.gh_handler(lc, argv) if self.gh_handler else cp()
            if argv[0] == "git":
                return self.git_handler(argv) if self.git_handler else cp()
            if argv[0].endswith("merge-probe.sh"):
                return cp()
            raise Escaped(f"unrouted argv: {argv}")

        lc._run = run
        lc.subprocess = NoSubprocess(subprocess_handler)
        lc.git_bytes = lambda *args: cp(b"")
        return self


@pytest.fixture()
def actor(monkeypatch):
    monkeypatch.setenv("BEADS_ACTOR", "actor-a")
    return "actor-a"


@pytest.fixture()
def contract(actor):
    lc = load()
    store = Store().install(lc)
    return lc, store


def landing_holder(pr="7", head=HEAD, repo="o/r") -> str:
    """The holder land_pr derives. It is a function of head, so a retry reuses it."""
    return f"pr-shepherd:{repo}#{pr}@{head}"


# --- P1: no self-inflicted state may wedge another holder ---------------------


def test_a_healthy_foreign_waiter_at_the_front_only_queues_me(contract):
    """Contention is not an error: another holder ahead of me is exit 75, not a Fail."""
    lc, store = contract
    store.waiter(lc, "other-holder", actor="actor-z", created_at="2020-01-01T00:00:00Z")
    assert lc.acquire_slot("mine", "1", "0", "handoff", "resume") == lc.EXIT_SLOT_QUEUED


def test_two_holders_never_own_the_native_token_at_once(contract):
    lc, store = contract
    assert lc.acquire_slot("holder-a", "1", "0", "handoff", "resume") == 0
    held = store.slot["holder"]
    assert lc.acquire_slot("holder-b", "1", "0", "handoff", "resume") == lc.EXIT_SLOT_QUEUED
    assert store.slot["holder"] == held


def test_resuming_my_own_live_slot_is_idempotent_not_a_second_holder(contract):
    """The same holder and actor re-entering reports resumed=true and mutates nothing."""
    lc, store = contract
    holder = landing_holder()
    assert lc.acquire_slot(holder, "1", "0", "handoff", "resume") == 0
    token = store.slot["holder"]
    assert lc.acquire_slot(holder, "1", "0", "handoff", "resume") == 0
    assert store.slot["holder"] == token
    assert len(store.waiters()) == 1


def test_a_waiter_left_by_a_dead_session_is_recoverable_and_then_reusable(contract,
                                                                         monkeypatch):
    """A queued session that dies leaves a lease in a stale BEADS_ACTOR. The next
    session cannot resume it -- correct, the lease is not its own -- so
    recover-waiter must be able to clear it and requeue must then succeed."""
    lc, store = contract
    holder = landing_holder()
    store.slot.update(available=False, holder="a-foreign-token")
    assert lc.acquire_slot(holder, "1", "0", "handoff", "resume") == lc.EXIT_SLOT_QUEUED

    monkeypatch.setenv("BEADS_ACTOR", "actor-b")
    store.slot.update(available=True, holder="")
    with pytest.raises(lc.Fail, match="leased to another actor"):
        lc.acquire_slot(holder, "1", "0", "handoff", "resume")
    store.bead("m-1")
    assert lc.recover_waiter("m-1", holder, "session-1-transcript") == 0
    assert lc.acquire_slot(holder, "1", "0", "handoff", "requeue") == 0


def test_recover_waiter_clears_a_waiter_whose_generation_is_a_string(contract):
    """`bd --set-metadata` stores scalars as strings, so a repaired waiter can carry
    generation="1". valid_generation rejects it, which wedges the holder; the
    recovery command must still be able to close it."""
    lc, store = contract
    store.waiter(lc, "mine", generation="1")
    store.bead("m-1")
    assert lc.recover_waiter("m-1", "mine", "evidence") == 0
    assert store.waiters()[0][1] == "closed"


@pytest.mark.xfail(
    reason="DEFECT: an unlinked waiter wedges the slot for EVERY holder and no "
           "recovery command can clear it. `bd create` succeeding while the "
           "following `bd dep add` fails (bd crash, lock contention, killed "
           "process) leaves that state; first_waiter_record then aborts every "
           "acquire_slot, and recover-waiter, recover-slot and recover-claim all "
           "abort on the same linkage check. Only manual bd surgery clears it, "
           "even though ensure_waiter_link could repair the link.",
    strict=True,
)
def test_an_unlinked_waiter_is_recoverable(contract):
    lc, store = contract
    store.bd_filter = lambda args: cp("", 1) if list(args)[:2] == ["dep", "add"] else None
    with pytest.raises(lc.Fail):
        lc.acquire_slot("holder-a", "1", "0", "handoff", "resume")
    store.bd_filter = None
    assert store.waiters(), "the waiter bead exists"
    assert store.beads[store.waiters()[0][0]]["dependencies"] == []

    store.bead("m-1")
    for recover in (
        lambda: lc.recover_waiter("m-1", "holder-a", "evidence"),
        lambda: lc.recover_slot("m-1", "holder-a", "evidence"),
    ):
        try:
            recover()
        except lc.Fail:
            continue
        break
    else:
        pytest.fail("no recovery command clears an unlinked waiter")
    assert lc.acquire_slot("holder-b", "1", "0", "handoff", "requeue") == 0


def test_an_unlinked_waiter_blocks_an_unrelated_holder(contract):
    """The blast radius of the state above, pinned separately: the wedge is not
    confined to the holder that created it."""
    lc, store = contract
    store.bd_filter = lambda args: cp("", 1) if list(args)[:2] == ["dep", "add"] else None
    with pytest.raises(lc.Fail):
        lc.acquire_slot("holder-a", "1", "0", "handoff", "resume")
    store.bd_filter = None
    with pytest.raises(lc.Fail, match="invalid parent linkage"):
        lc.acquire_slot("holder-b", "1", "0", "handoff", "resume")


# --- P2: a slot acquired is a slot released ----------------------------------


def test_recover_claim_releases_its_internal_slot_on_success(contract):
    lc, store = contract
    store.bead("m-1", status="in_progress", assignee="dead-actor")
    assert lc.recover_claim("m-1", "dead-actor", "evidence") == 0
    assert store.slot["available"] is True


@pytest.mark.xfail(
    reason="DEFECT: recover_claim acquires an internal recovery slot with "
           "protection=handoff and releases it only on the success path, so any "
           "Fail after line 1857 -- an incomplete prior recovery receipt here, "
           "equally a bd hiccup in claim_state or finish_recovery -- leaves the "
           "merge slot held by pr-shepherd:claim-recovery:* forever. Retries "
           "re-resume the same lease and fail identically; release-sheepdog then "
           "returns 75 forever and no other shepherd can take the patrol.",
    strict=True,
)
def test_recover_claim_releases_its_internal_slot_when_it_aborts(contract):
    lc, store = contract
    store.bead(
        "m-1", status="in_progress", assignee="dead-actor",
        metadata={"recovery_key": "a-different-key", "recovery_phase": "prepared"},
    )
    with pytest.raises(lc.Fail):
        lc.recover_claim("m-1", "dead-actor", "evidence")
    assert store.slot["available"] is True, f"slot leaked to {store.slot['holder']}"


def test_a_leaked_recovery_slot_stalls_the_sheepdog_patrol(contract):
    """The blast radius of the leak above: the repo-wide patrol lease can neither
    be released nor taken over while the orphaned lease stands."""
    lc, store = contract
    store.bead(
        "m-1", status="in_progress", assignee="dead-actor",
        metadata={"recovery_key": "a-different-key", "recovery_phase": "prepared"},
    )
    assert lc.acquire_sheepdog("o/r") == 0
    with pytest.raises(lc.Fail):
        lc.recover_claim("m-1", "dead-actor", "evidence")
    assert lc.release_sheepdog("o/r") == lc.EXIT_SLOT_QUEUED


def test_an_operator_can_recover_a_leaked_recovery_slot_by_name(contract):
    """The escape hatch, pinned so a fix does not remove it: recover-slot against
    the internal holder name and a DIFFERENT merge bead clears the lease."""
    lc, store = contract
    store.bead(
        "m-1", status="in_progress", assignee="dead-actor",
        metadata={"recovery_key": "a-different-key", "recovery_phase": "prepared"},
    )
    with pytest.raises(lc.Fail):
        lc.recover_claim("m-1", "dead-actor", "evidence")
    store.bead("m-2")
    assert lc.recover_slot("m-2", "pr-shepherd:claim-recovery:m-1:dead-actor", "ev") == 0
    assert store.slot["available"] is True


# --- P3: malformed evidence fails closed with a documented code ---------------


TSV_JUNK = (
    "",
    "\n",
    "<html><body>502 Bad Gateway</body></html>",
    '{"message":"Not Found","documentation_url":"https://docs.github.com"}',
    "OPEN\tfalse\tMERGEABLE",
    "OPEN\tfalse\tMERGEABLE\tAPPROVED\tmain\t" + HEAD + "\tGREEN\tEXTRA",
    "OPEN\tfalse\tMERGEABLE\tAPPROVED\tmain\t" + HEAD + "\tGREEN\nOPEN\tx\n",
    "x" * 200_000,
)


@pytest.mark.parametrize("junk", TSV_JUNK, ids=range(len(TSV_JUNK)))
def test_junk_gh_output_fails_closed_rather_than_crashing(junk, contract):
    lc, store = contract
    store.gh_handler = lambda _lc, _argv: cp(junk)
    try:
        rc = lc.check_pr("o/r", "7", HEAD, "main")
    except lc.Fail:
        return
    assert rc in DOCUMENTED_EXITS
    assert rc != 0, "junk evidence must never read as a passed check"


@pytest.mark.parametrize(
    "command",
    [
        ["check-pr", "o/r", "7", HEAD, "main"],
        ["check-run", "o/r", "99", HEAD],
        ["verify-landed", "o/r", "7", "main", RECORDED_BASE, HEAD, MERGE_SHA],
    ],
    ids=["check-pr", "check-run", "verify-landed"],
)
def test_a_proxy_error_body_on_stdout_exits_with_a_documented_code(command, contract):
    """The same defect through the real entrypoint, because the exit CODE is the
    contract a shell caller reads. Currently exits 1 with a traceback."""
    lc, store = contract
    store.gh_handler = lambda _lc, _argv: cp("<html>502 Bad Gateway</html>")
    try:
        rc = lc.dispatch(command)
    except lc.Fail:
        rc = lc.EXIT_UNKNOWN
    except ValueError:
        pytest.xfail("gh_tsv arity crash reaches the entrypoint as exit 1")
    assert rc in DOCUMENTED_EXITS


def test_a_non_json_slot_check_fails_closed(contract):
    lc, store = contract
    store.bd_filter = lambda args: (
        cp("not json") if list(args)[:2] == ["merge-slot", "check"] else None
    )
    with pytest.raises(lc.Fail, match="merge slot"):
        lc.acquire_slot("mine", "1", "0", "handoff", "resume")


def test_a_missing_slot_id_fails_closed(contract):
    lc, store = contract
    store.slot = {"available": True}
    with pytest.raises(lc.Fail, match="merge-slot id"):
        lc.acquire_slot("mine", "1", "0", "handoff", "resume")


@pytest.mark.parametrize(
    "generation",
    [None, True, False, 0, -1, 1.5, "1", "", [], {}, [1], 10**30],
    ids=range(12),
)
def test_a_hostile_waiter_generation_never_becomes_a_valid_identity(generation, contract):
    """A generation that is not a positive integer must not derive a waiter id: the
    id IS the lock, so a coerced one would name a different lock."""
    lc, _store = contract
    if isinstance(generation, bool) or not isinstance(generation, (int, float)):
        with pytest.raises(lc.QueryError):
            lc.valid_generation(generation)
        return
    if generation < 1 or float(generation) != int(generation):
        with pytest.raises(lc.QueryError):
            lc.valid_generation(generation)
    else:
        assert lc.valid_generation(generation) == generation


def test_a_lone_surrogate_in_a_digest_payload_fails_closed(contract):
    lc, _store = contract
    assert lc.nul_payload("a\udcffb")


def test_an_unknown_bounce_phase_aborts_rather_than_defaulting(contract):
    lc, _store = contract
    for phase in ("", "preparing", "fix_ready", "parked", "commented", "complete"):
        assert isinstance(lc.bounce_phase_rank(phase), int)
    with pytest.raises(lc.Fail, match="unknown bounce receipt phase"):
        lc.bounce_phase_rank("nonsense")


def test_an_unknown_recovery_phase_aborts_rather_than_defaulting(contract):
    """Pinned against the shell regression the docstring records: a discarded abort
    took the mutating branch."""
    lc, _store = contract
    assert lc.recovery_phase_rank("prepared") == 1
    assert lc.recovery_phase_rank("complete") == 5
    for phase in ("", "PREPARED", "mutating", "0"):
        with pytest.raises(lc.Fail, match="unknown recovery receipt phase"):
            lc.recovery_phase_rank(phase)


def test_check_pr_never_reads_an_unknown_mergeable_state_as_ready(contract):
    lc, store = contract
    for mergeable in ("UNKNOWN", "", "CONFLICTING", "MAYBE"):
        store.gh_handler = lambda _lc, _argv, m=mergeable: cp(
            f"OPEN\tfalse\t{m}\tAPPROVED\tmain\t{HEAD}\tGREEN\n"
        )
        try:
            rc = lc.check_pr("o/r", "7", HEAD, "main")
        except lc.Fail:
            continue
        assert rc != 0, mergeable


def test_check_pr_requires_approval_in_github_mode(contract):
    lc, store = contract
    for review in ("NONE", "", "REVIEW_REQUIRED", "COMMENTED"):
        store.gh_handler = lambda _lc, _argv, r=review: cp(
            f"OPEN\tfalse\tMERGEABLE\t{r}\tmain\t{HEAD}\tGREEN\n"
        )
        assert lc.check_pr("o/r", "7", HEAD, "main", "github") == lc.EXIT_WAITING


def test_a_stale_head_is_never_landed(contract):
    lc, store = contract
    store.gh_handler = lambda _lc, _argv: cp(
        f"OPEN\tfalse\tMERGEABLE\tAPPROVED\tmain\t{STALE_HEAD}\tGREEN\n"
    )
    assert lc.check_pr("o/r", "7", HEAD, "main") == lc.EXIT_STALE


def test_require_sha_rejects_everything_that_is_not_a_full_hex_sha(contract):
    lc, _store = contract
    for value in ("", None, HEAD + "\n", " " + "a" * 39, "a" * 39, "a" * 41,
                  "a" * 39 + "g", "a" * 4000, "NONE"):
        with pytest.raises(lc.Fail):
            lc.require_sha(value, "probe")
    lc.require_sha(HEAD, "probe")


def test_an_uppercase_sha_is_accepted_then_compares_unequal(contract):
    """Documented, not asserted as correct: require_sha allows uppercase hex but
    every downstream comparison is case-sensitive against git's lowercase output,
    so an uppercase argument reports PR_STALE instead of a usage error."""
    lc, store = contract
    lc.require_sha("A" * 40, "probe")
    store.gh_handler = lambda _lc, _argv: cp(
        f"OPEN\tfalse\tMERGEABLE\tAPPROVED\tmain\t{HEAD}\tGREEN\n"
    )
    assert lc.check_pr("o/r", "7", "A" * 40, "main") == lc.EXIT_STALE


# --- P4: a retry at an unchanged head is not refused -------------------------


def land_gh_handler(*, pr_state_after="MERGED", ready=True):
    """A gh responder for the land path, sequenced: the pre-merge read is OPEN."""
    calls = {"merge_jq": 0}

    def handler(lc, argv):
        if argv[1:3] == ["pr", "view"]:
            jq = argv[argv.index("--jq") + 1]
            if jq == lc.PR_MERGE_JQ:
                calls["merge_jq"] += 1
                state = "OPEN" if calls["merge_jq"] == 1 else pr_state_after
                return cp(f"{state}\t{HEAD}\t{MERGE_SHA}\n")
            if jq == lc.PR_READY_JQ:
                review = "APPROVED" if ready else "NONE"
                return cp(f"OPEN\tfalse\tMERGEABLE\t{review}\tmain\t{HEAD}\tGREEN\n")
            if jq == lc.PR_ANCHOR_JQ:
                return cp("feat/x\tmain\thttps://example/pr\n")
        if argv[1:3] == ["api", "graphql"]:
            return cp("not-json-at-all")
        if argv[1] == "api":
            jq = argv[argv.index("--jq") + 1]
            if jq == ".object.sha":
                return cp(REMOTE_BASE + "\n")
            if jq == ".status":
                return cp("identical\n")
        return cp()

    return handler


@pytest.mark.xfail(
    reason="DEFECT: run_with_slot closes the waiter terminally for every non-WAITING "
           "outcome, and the holder is derived from repo#pr@head, so a retry at an "
           "unchanged head hits `terminal waiter ... requires explicit requeue` and "
           "exits 2 forever. Nothing in the shipped skill, agent, or reference sets "
           "SHEPHERD_WAITER_MODE=requeue (rg finds it only in the script and one "
           "sentence of landing-contract.md), so the documented escape is unreachable "
           "for a caller following the skill. Reached by a transient gh failure inside "
           "the slot, a merge-probe exit 2, or a merge-queue ejection followed by a CI "
           "re-run -- all cases where the correct next action is to try again.",
    strict=True,
)
def test_a_retry_after_a_transient_gh_failure_at_the_same_head_is_not_refused(contract):
    lc, store = contract
    store.bead("m-1", status="in_progress", assignee="actor-a",
               labels=["agent:integrator"], metadata={"pr": "7", "repo": "o/r"})
    failing = {"on": True}

    def handler(lc_, argv):
        if failing["on"] and argv[1:3] == ["pr", "view"]:
            jq = argv[argv.index("--jq") + 1]
            if jq == lc_.PR_MERGE_JQ:
                return cp("", 1)
        return land_gh_handler()(lc_, argv)

    store.gh_handler = handler
    with pytest.raises(lc.Fail, match="cannot read PR"):
        lc.land_pr("m-1", "o/r", "7", "main", "main", RECORDED_BASE, HEAD, "merge")
    assert store.waiters() == [(store.waiters()[0][0], "closed")]

    failing["on"] = False
    lc2 = load()
    store.install(lc2, subprocess_handler=lambda argv: cp())
    store.gh_handler = handler
    lc2.land_pr("m-1", "o/r", "7", "main", "main", RECORDED_BASE, HEAD, "merge")


def test_a_transient_failure_inside_the_slot_still_releases_the_slot(contract):
    """The armed release is the part that does work: whatever else the failure
    costs, the slot itself comes back."""
    lc, store = contract
    store.bead("m-1", status="in_progress", assignee="actor-a",
               labels=["agent:integrator"], metadata={})
    store.gh_handler = lambda _lc, argv: (
        cp("", 1) if argv[1:3] == ["pr", "view"] else cp()
    )
    with pytest.raises(lc.Fail):
        lc.land_pr("m-1", "o/r", "7", "main", "main", RECORDED_BASE, HEAD, "merge")
    lc.run_armed_release()
    assert store.slot["available"] is True


def test_requeue_creates_the_next_generation_after_a_terminal_waiter(contract):
    """The documented escape works when a caller reaches it."""
    lc, store = contract
    holder = landing_holder()
    assert lc.acquire_slot(holder, "1", "0", "handoff", "resume") == 0
    assert lc.release_slot(holder, "terminal") == 0
    with pytest.raises(lc.Fail, match="requires explicit requeue"):
        lc.acquire_slot(holder, "1", "0", "handoff", "resume")
    assert lc.acquire_slot(holder, "1", "0", "handoff", "requeue") == 0
    generations = sorted(
        b["metadata"]["generation"] for b in store.beads.values()
        if "gt:slot-waiter" in b["labels"]
    )
    assert generations == [1, 2]


# --- bounce receipts ---------------------------------------------------------


def test_a_bounce_parks_the_merge_bead_and_is_idempotent(contract):
    lc, store = contract
    store.bead("m-1", status="in_progress", assignee="actor-a")
    key = lc.failure_key("o/r", "ci", ["build"])
    assert lc.ensure_bounce("m-1", key, "agent:coder", "fix", '{"pr":"7"}', "d") == 0
    merge = store.beads["m-1"]
    assert (merge["status"], merge["assignee"]) == ("open", "")
    assert merge["metadata"]["bounce_phase"] == "complete"
    fixes = [b for b in store.beads.values() if "agent:coder" in b["labels"]]
    assert len(fixes) == 1
    assert merge["dependencies"], "the merge bead is parked behind the fix"

    assert lc.ensure_bounce("m-1", key, "agent:coder", "fix", '{"pr":"7"}', "d") == 0
    assert len([b for b in store.beads.values() if "agent:coder" in b["labels"]]) == 1


def test_a_bounce_never_loses_the_merge_bead(contract):
    """The bead must stay open and unassigned, never closed, whatever the receipt."""
    lc, store = contract
    key = lc.failure_key("o/r", "conflict", ["a.py", "b.py"])
    for phase in lc.BOUNCE_PHASES:
        store.beads.clear()
        store.bead("m-1", status="in_progress", assignee="actor-a",
                   metadata={"bounce_key": key, "bounce_phase": phase})
        try:
            lc.ensure_bounce("m-1", key, "agent:coder", "fix", "{}", "d")
        except lc.Fail:
            pass
        assert store.beads["m-1"]["status"] != "closed", phase


def test_a_receipt_naming_a_vanished_fix_bead_is_a_permanent_hard_failure(contract):
    """Documented, not asserted as correct: once bounce_fix names a bead that no
    longer answers the failure_key query, ensure_bounce aborts on every retry and
    the merge bead stays claimed. Deleting a fix bead is the way in."""
    lc, store = contract
    key = lc.failure_key("o/r", "ci", ["build"])
    store.bead("m-1", status="in_progress", assignee="actor-a",
               metadata={"bounce_key": key, "bounce_fix": "deleted-1",
                         "bounce_phase": "parked"})
    for _ in range(3):
        with pytest.raises(lc.Fail, match="bounce receipt fix changed"):
            lc.ensure_bounce("m-1", key, "agent:coder", "fix", "{}", "d")
    assert store.beads["m-1"]["status"] == "in_progress"


@pytest.mark.parametrize("metadata", ["", "null", "[]", "5", '"s"', "{", "not json"])
def test_invalid_bounce_metadata_fails_closed(metadata, contract):
    lc, store = contract
    store.bead("m-1")
    with pytest.raises(lc.Fail, match="invalid bounce metadata"):
        lc.ensure_bounce("m-1", "k", "agent:coder", "t", metadata, "d")


@pytest.mark.parametrize("kind", ["", "CI", "flake", "queue ", "ci\n"])
def test_an_unknown_failure_kind_fails_closed(kind, contract):
    lc, _store = contract
    with pytest.raises(lc.Fail):
        lc.failure_key("o/r", kind, ["detail"])


def test_a_failure_key_is_stable_and_detail_order_sensitive(contract):
    lc, _store = contract
    first = lc.failure_key("o/r", "conflict", ["a.py", "b.py"])
    assert first == lc.failure_key("o/r", "conflict", ["a.py", "b.py"])
    assert first != lc.failure_key("o/r", "conflict", ["b.py", "a.py"])
    assert first != lc.failure_key("o/R", "conflict", ["a.py", "b.py"])
    assert len(first) == 40


# --- merge queue -------------------------------------------------------------


def test_a_failed_queue_probe_is_never_read_as_a_landing(contract):
    lc, store = contract
    for stdout, rc in [("", 1), ("not json", 0), ("null", 0), ("{}", 0),
                       ('{"data":null}', 0), ('{"data":{"repository":null}}', 0),
                       ('{"data":{"repository":{"pullRequest":null}}}', 0)]:
        lc._queue_cache.clear()
        store.gh_handler = lambda _lc, _argv, s=stdout, r=rc: cp(s, r)
        assert lc.queue_state("o/r", "7") is None


def test_an_ejected_queue_entry_is_a_failure_not_a_landing(contract):
    lc, store = contract
    store.bead("m-1", metadata={"landing_state": lc.STATE_QUEUED})
    payload = {"data": {"repository": {"pullRequest": {
        "isMergeQueueEnabled": True, "isInMergeQueue": False, "mergeQueueEntry": None}}}}

    def handler(lc_, argv):
        if argv[1:3] == ["api", "graphql"]:
            return cp(json.dumps(payload))
        if argv[1:3] == ["pr", "view"]:
            return cp(f"OPEN\t{HEAD}\tNONE\n")
        return cp()

    store.gh_handler = handler
    rc = lc.resume_queued_landing("m-1", "o/r", "7", "main", "main", RECORDED_BASE, HEAD)
    assert rc == lc.EXIT_FAILED
    assert store.beads["m-1"]["metadata"]["landing_state"] == lc.STATE_EJECTED


def test_a_queued_landing_never_calls_gh_pr_merge(contract):
    """resume_queued_landing runs outside the slot, so it must not merge."""
    lc, store = contract
    store.bead("m-1", metadata={"landing_state": lc.STATE_QUEUED})
    payload = {"data": {"repository": {"pullRequest": {
        "isMergeQueueEnabled": True, "isInMergeQueue": True,
        "mergeQueueEntry": {"state": "QUEUED", "position": 2,
                            "headCommit": {"oid": HEAD}}}}}}

    def handler(lc_, argv):
        if argv[1:3] == ["api", "graphql"]:
            return cp(json.dumps(payload))
        if argv[1:3] == ["pr", "view"]:
            return cp(f"OPEN\t{HEAD}\tNONE\n")
        return cp()

    store.gh_handler = handler
    assert lc.land_pr("m-1", "o/r", "7", "main", "main",
                      RECORDED_BASE, HEAD, "merge") == lc.EXIT_WAITING
    assert not any(a[:3] == ("gh", "pr", "merge") for a in store.argv)
    assert store.slot["available"] is True, "the queued path holds no slot"


# --- landing proof cost ------------------------------------------------------


def test_the_content_proof_spawns_two_git_processes_per_changed_path(contract):
    """Pinned as a cost, not as correctness: verify_landed shells out `git ls-tree`
    once per path per tree. A 4,000-file PR is 8,000 spawns in one pass."""
    lc, store = contract
    paths = 300
    blob = b"\0".join(f"d{i}/f{i}.py".encode() for i in range(paths))
    lc.git_bytes = lambda *args: cp(blob)
    spawns = {"ls_tree": 0}

    def git_handler(argv):
        if argv[1] == "ls-tree":
            spawns["ls_tree"] += 1
            return cp("100644 blob abc\tp\n")
        if argv[1] == "rev-parse":
            return cp(REMOTE_BASE + "\n")
        return cp()

    store.git_handler = git_handler
    store.gh_handler = lambda _lc, argv: (
        cp(f"MERGED\t2026-01-01T00:00:00Z\t{MERGE_SHA}\tmain\t{HEAD}\thttps://u\n")
        if argv[1:3] == ["pr", "view"]
        else cp(REMOTE_BASE + "\n" if argv[argv.index("--jq") + 1] == ".object.sha"
                else "diverged\n")
    )
    assert lc.verify_landed("o/r", "7", "main", RECORDED_BASE, HEAD, MERGE_SHA) == 0
    assert spawns["ls_tree"] == 2 * paths


def test_an_empty_content_diff_fails_closed(contract):
    lc, store = contract
    lc.git_bytes = lambda *args: cp(b"")
    store.git_handler = lambda argv: (
        cp(REMOTE_BASE + "\n") if argv[1] == "rev-parse" else cp()
    )
    store.gh_handler = lambda _lc, argv: (
        cp(f"MERGED\t2026-01-01T00:00:00Z\t{MERGE_SHA}\tmain\t{HEAD}\thttps://u\n")
        if argv[1:3] == ["pr", "view"]
        else cp(REMOTE_BASE + "\n" if argv[argv.index("--jq") + 1] == ".object.sha"
                else "diverged\n")
    )
    with pytest.raises(lc.Fail, match="no changed paths"):
        lc.verify_landed("o/r", "7", "main", RECORDED_BASE, HEAD, MERGE_SHA)


# --- anchors ----------------------------------------------------------------


def test_a_merge_bead_anchored_to_another_pr_is_refused(contract):
    lc, store = contract
    store.bead("m-1", metadata={"pr": "9", "repo": "o/r"})
    assert lc.check_bead_anchors("m-1", "o/r", "7") == lc.EXIT_FAILED


def test_a_merge_bead_anchored_to_another_repo_is_refused(contract):
    lc, store = contract
    store.bead("m-1", metadata={"pr": "7", "repo": "other/repo"})
    assert lc.check_bead_anchors("m-1", "o/r", "7") == lc.EXIT_FAILED


def test_a_merge_bead_anchored_to_another_branch_is_refused(contract):
    lc, store = contract
    store.bead("m-1", metadata={"pr": "7", "repo": "o/r", "branch": "feat/other"})
    store.gh_handler = lambda _lc, _argv: cp("feat/x\tmain\thttps://u\n")
    assert lc.check_bead_anchors("m-1", "o/r", "7") == lc.EXIT_FAILED


def test_an_unavailable_bd_makes_anchors_unknown_not_ok(contract):
    lc, store = contract
    store.bd_filter = lambda args: cp("", 1) if list(args)[0] == "show" else None
    assert lc.check_bead_anchors("m-1", "o/r", "7") == lc.EXIT_UNKNOWN


def test_an_integer_anchored_pr_still_matches_a_string_argument(contract):
    """bd metadata may hold 7 or "7"; both name the same PR, so neither is a mismatch."""
    lc, store = contract
    store.bead("m-1", metadata={"pr": 7, "repo": "o/r"})
    assert lc.check_bead_anchors("m-1", "o/r", "7") == 0


# --- sheepdog ---------------------------------------------------------------


def test_a_second_shepherd_is_refused_the_patrol_without_a_crash(contract, monkeypatch):
    lc, store = contract
    assert lc.acquire_sheepdog("o/r") == 0
    monkeypatch.setenv("BEADS_ACTOR", "actor-b")
    assert lc.acquire_sheepdog("o/r") == lc.EXIT_SLOT_QUEUED
    wisp = lc.sheepdog_wisp("o/r")
    assert store.beads[wisp]["assignee"] == "actor-a"


def test_a_crashed_patrol_generation_is_taken_over_after_release(contract, monkeypatch):
    lc, store = contract
    assert lc.acquire_sheepdog("o/r") == 0
    assert lc.release_sheepdog("o/r") == 0
    monkeypatch.setenv("BEADS_ACTOR", "actor-b")
    assert lc.acquire_sheepdog("o/r") == 0


def test_sheepdog_recovery_refuses_a_stale_observation(contract, monkeypatch):
    lc, _store = contract
    assert lc.acquire_sheepdog("o/r") == 0
    monkeypatch.setenv("BEADS_ACTOR", "actor-b")
    with pytest.raises(lc.Fail, match="no longer belongs"):
        lc.recover_sheepdog("o/r", "actor-c", "evidence", "m-1")


def test_the_patrol_wisp_folds_repo_case_but_not_unicode(contract):
    lc, _store = contract
    assert lc.sheepdog_wisp("Owner/Repo") == lc.sheepdog_wisp("owner/repo")
    assert lc.sheepdog_wisp("owner/repÖ") != lc.sheepdog_wisp("owner/repö")


def test_a_heartbeat_never_changes_the_patrol_holder(contract, monkeypatch):
    lc, store = contract
    assert lc.acquire_sheepdog("o/r") == 0
    wisp = lc.sheepdog_wisp("o/r")
    assert lc.touch_sheepdog("o/r") == 0
    assert store.beads[wisp]["assignee"] == "actor-a"
    monkeypatch.setenv("BEADS_ACTOR", "actor-b")
    with pytest.raises(lc.Fail, match="not owned by"):
        lc.touch_sheepdog("o/r")
    assert store.beads[wisp]["assignee"] == "actor-a"


# --- dispatch ---------------------------------------------------------------


def test_every_command_has_an_arity_message_and_a_handler_or_a_branch(contract):
    lc, _store = contract
    assert set(lc.COMMANDS) == set(lc.ARITY_MESSAGE)
    for name, (minimum, maximum, handler) in lc.COMMANDS.items():
        assert maximum is None or minimum <= maximum, name
        if handler is None:
            assert name in ("acquire-slot", "with-slot", "failure-key"), name
        assert name in lc.USAGE, name


@pytest.mark.parametrize(
    "argv",
    [[], [""], ["nonsense"], ["--version"], ["check-pr"], ["land"],
     ["check-run", "o/r"], ["ready-ids", "extra"], ["with-slot", "h", "x"],
     ["acquire-slot", "h", "0"], ["acquire-slot", "h", "3", "-1"],
     ["acquire-slot", "h", "3", "1", "nonsense"], ["release-slot", "h", "nonsense"],
     ["check-pr", "o/r", "7", HEAD, "main", "nonsense"],
     ["land", "m", "o/r", "7", "main", "main", RECORDED_BASE, HEAD, "nonsense"]],
    ids=range(15),
)
def test_bad_arguments_fail_closed_with_a_documented_exit(argv, contract):
    lc, _store = contract
    try:
        rc = lc.dispatch(argv)
    except lc.Fail:
        return
    assert rc in DOCUMENTED_EXITS
    assert rc != 0 or argv == []


def test_help_prints_usage_and_exits_zero(contract, capsys):
    lc, _store = contract
    for flag in ("-h", "--help", "help"):
        assert lc.dispatch([flag]) == 0
    assert "landing-contract.py" in capsys.readouterr().out


# --- P3 corpus --------------------------------------------------------------


HOSTILE_SCALARS = (
    None, True, False, 0, -1, 1.5, "", " ", "\n", "\t", "\0", "NONE", "null",
    "x" * 8192, "brânch/ünicode", [], {}, [1], {"k": "v"},
)


def _hostile_bead(rng: random.Random, lc) -> dict:
    """A waiter record that is USUALLY well-formed, with fields spoiled.

    Starting from a valid record keeps the generator near the decision boundary,
    where an over-permissive identity check shows up.
    """
    holder = "holder-x"
    generation = 1
    ident = lc.waiter_id("slot-1", holder, generation)
    record = {
        "id": ident, "status": "open", "assignee": "", "labels": [lc.WAITER_LABEL],
        "created_at": "2026-01-01T00:00:00Z",
        "metadata": {"slot_id": "slot-1", "holder": holder, "generation": generation,
                     "waiter_id": ident, "lease_actor": "actor-a"},
        "dependencies": [{"type": "parent-child", "depends_on_id": "slot-1"}],
        "comments": [],
    }
    if rng.random() < 0.3:
        record["metadata"][rng.choice(
            ["slot_id", "holder", "generation", "waiter_id", "lease_actor"]
        )] = rng.choice(HOSTILE_SCALARS)
    if rng.random() < 0.15:
        record["status"] = rng.choice(
            ["open", "in_progress", "closed", "blocked", *HOSTILE_SCALARS]
        )
    if rng.random() < 0.15:
        record["assignee"] = rng.choice(["actor-a", "actor-z", *HOSTILE_SCALARS])
    if rng.random() < 0.15:
        record["dependencies"] = rng.choice([
            [], None, "nope", [None], [{"type": "blocks", "depends_on_id": "slot-1"}],
            [{"type": "parent-child", "depends_on_id": "other-slot"}],
            [{"type": "parent-child", "depends_on_id": "slot-1"}] * 2,
        ])
    if rng.random() < 0.1:
        record["created_at"] = rng.choice(HOSTILE_SCALARS)
    if rng.random() < 0.08:
        record.pop(rng.choice(list(record)), None)
    if rng.random() < 0.08:
        record["id"] = rng.choice(HOSTILE_SCALARS)
    return record


def test_a_hostile_waiter_record_never_grants_the_slot_and_never_crashes(actor):
    """P1 and P3 over the generated corpus: whatever a bead table holds, the run
    ends in a documented outcome and never in a foreign holder owning my token."""
    rng = random.Random(SEED)
    reached: set[str] = set()
    for index in range(CORPUS_SIZE):
        lc = load()
        store = Store().install(lc)
        record = _hostile_bead(rng, lc)
        store.beads[str(record.get("id") or f"anon-{index}")] = record
        try:
            rc = lc.acquire_slot("holder-x", "1", "0", "handoff", "resume")
        except lc.Fail:
            reached.add("fail")
            continue
        except (lc.QueryError, ValueError, TypeError, KeyError, AttributeError) as error:
            pytest.fail(f"case {index} raised {error!r} on {record!r}")
        reached.add(str(rc))
        assert rc in DOCUMENTED_EXITS, (index, rc)
        if rc == 0:
            # Owning the slot is only legitimate under MY derived native token.
            assert store.slot["available"] is False
            assert store.slot["holder"].startswith("pr-shepherd:")
    assert {"fail", "0"} <= reached, f"generator only reached {sorted(reached)}"


def test_the_script_is_committed_executable_with_a_python_shebang():
    assert SCRIPT.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3")
    assert os.access(SCRIPT, os.X_OK), "hook and skill scripts ship mode 755"


def test_no_test_in_this_file_reaches_a_real_binary(contract):
    """The isolation itself, asserted: an unrouted argv raises rather than running."""
    lc, _store = contract
    with pytest.raises(Escaped):
        lc._run(["curl", "https://example.com"])
    with pytest.raises(Escaped):
        lc.subprocess.run(["gh", "pr", "merge", "7"])
