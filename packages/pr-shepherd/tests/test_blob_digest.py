"""Parity guard: the Python blob digest must equal `git hash-object --stdin`.

That digest IS the waiter id, the native holder token, the failure key, the
recovery key, and the sheepdog wisp id. One byte of drift renames every live
waiter and orphans in-flight state, so this compares against the real git
binary rather than against a second hand-rolled implementation.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / ".apm/skills/pr-shepherd/scripts/landing-contract.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("landing_contract", CONTRACT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git_hash_object(payload: bytes) -> str:
    return subprocess.run(
        ["git", "hash-object", "--stdin"],
        input=payload,
        capture_output=True,
        check=True,
    ).stdout.decode().strip()


PAYLOADS = [
    b"",
    b"hello",
    b"slot-1\0pr-shepherd:owner/repo#7@" + b"a" * 40 + b"\0" + b"1\0",
    b"pr-shepherd:owner/repo#7\0" + b"12\0" + b"actor-a\0slot-1-waiter-abcdef123456\0",
    b"owner/repo\0conflict\0path/with\ttab.txt\0path/with\nnewline.txt\0",
    b"sheepdog\0owner/repo\0",
    b"\0\0\0",
    b"\xff\xfe\x00binary",
    bytes(range(256)),
    b"x" * 100_000,
]


def test_known_git_blob_hash():
    """The published anchor value, so a broken local git cannot hide drift."""
    module = _load()
    assert module.blob_digest(b"hello") == "b6fc4c620b67d95f953a5c1c1230aaab5db5a1b0"


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
@pytest.mark.parametrize("payload", PAYLOADS, ids=range(len(PAYLOADS)))
def test_matches_real_git(payload):
    module = _load()
    assert module.blob_digest(payload) == _git_hash_object(payload)


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_identity_payload_helpers_match_git():
    """The four digest call sites, end to end through their own helpers."""
    module = _load()
    slot, holder, generation, actor = "slot-1", "pr-shepherd:owner/repo#7", 3, "actor-a"

    waiter = module.waiter_id(slot, holder, generation)
    expected = _git_hash_object(f"{slot}\0{holder}\0{generation}\0".encode())
    assert waiter == f"{slot}-waiter-{expected[:12]}"

    token = module.native_holder_token(
        holder,
        {"id": waiter, "metadata": {"generation": generation, "lease_actor": actor}},
    )
    expected = _git_hash_object(f"{holder}\0{generation}\0{actor}\0{waiter}\0".encode())
    assert token == f"pr-shepherd:{expected}"

    key = module.failure_key("owner/repo", "conflict", ["a\tb.txt", "c.txt"])
    assert key == _git_hash_object(b"owner/repo\0conflict\0a\tb.txt\0c.txt\0")

    key = module.recovery_key("claim", "dead-actor", "session-registry:dead")
    assert key == _git_hash_object(b"claim\0dead-actor\0session-registry:dead\0")


# --- fuzz: the identity digests and the landing-state machine ---------------
#
# Deterministic combinatorial corpus, matching the house style in
# packages/hooks-git-safety/tests/test_git_safety_fuzz.py. The digest is the
# highest-risk surface in this script: one byte of drift renames every live
# waiter, so the field encoding is fuzzed against the real git binary rather
# than against a second Python implementation.

# Field values chosen for the ways a shell round trip loses data: embedded NUL,
# tab, newline, backslash, quote, non-ASCII, empty, and a leading dash.
HOSTILE_FIELDS = (
    "",
    "plain",
    "with space",
    "with\ttab",
    "with\nnewline",
    "with\\backslash",
    'with"quote',
    "with'apostrophe",
    "--leading-dash",
    "ünïcøde",
    "trailing-nul-ish\\0",
    "a" * 300,
)


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_fuzz_nul_payload_encoding_matches_git():
    """Every field combination must encode to what git hashes."""
    module = _load()
    checked = 0
    for first in HOSTILE_FIELDS:
        for second in HOSTILE_FIELDS:
            checked += 1
            payload = module.nul_payload(first, second)
            assert payload.endswith(b"\0")
            assert module.blob_digest(payload) == _git_hash_object(payload)
    assert checked == len(HOSTILE_FIELDS) ** 2


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_fuzz_waiter_ids_are_collision_free_and_git_exact():
    """A distinct (slot, holder, generation) triple must yield a distinct waiter id."""
    module = _load()
    seen: dict[str, tuple] = {}
    for holder in HOSTILE_FIELDS:
        for generation in (1, 2, 10, 999):
            triple = ("slot-1", holder, generation)
            waiter = module.waiter_id(*triple)
            expected = _git_hash_object(f"slot-1\0{holder}\0{generation}\0".encode())
            assert waiter == f"slot-1-waiter-{expected[:12]}"
            assert waiter not in seen or seen[waiter] == triple, (
                f"waiter id collision: {triple} and {seen[waiter]}"
            )
            seen[waiter] = triple


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_fuzz_failure_key_is_order_and_detail_sensitive():
    """Conflict paths hash in order, so a reordering must change the key."""
    module = _load()
    paths = ["a\tb.txt", "b.txt", "c\nd.txt", "ünïcøde.txt"]
    key = module.failure_key("owner/repo", "conflict", paths)
    assert key == _git_hash_object(
        b"owner/repo\0conflict\0" + b"".join(p.encode() + b"\0" for p in paths)
    )
    assert key != module.failure_key("owner/repo", "conflict", list(reversed(paths)))
    assert key != module.failure_key("owner/repo", "ci", paths)
    assert key != module.failure_key("Owner/repo", "conflict", paths)


def test_landing_states_are_distinct_and_named():
    """The dependent follow-up matches these exact strings and codes."""
    module = _load()
    assert module.STATE_QUEUED == "queued"
    assert module.STATE_EJECTED == "ejected"
    assert module.EXIT_WAITING == 10
    assert module.EXIT_FAILED == 12
    # The beads merge slot is a separate concept and must not be conflated.
    assert module.EXIT_SLOT_QUEUED == 75
    assert module.STATE_QUEUED != module.STATE_EJECTED


def test_recovery_phase_rank_rejects_every_unknown_phase():
    """An unknown phase aborts. In shell this discarded the exit and mutated."""
    module = _load()
    for phase, rank in zip(module.RECOVERY_PHASES, range(1, 6)):
        assert module.recovery_phase_rank(phase) == rank
    for bad in ("", "not-a-real-phase", "PREPARED", "complete ", "0", None):
        with pytest.raises(module.Fail):
            module.recovery_phase_rank(bad)


def test_bounce_phase_rank_rejects_every_unknown_phase():
    module = _load()
    for bad in ("not-a-phase", "COMPLETE", "parked "):
        with pytest.raises(module.Fail):
            module.bounce_phase_rank(bad)


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_fuzz_canonical_repo_folds_only_ascii_case():
    """The wisp id folds case, so Owner/Repo and owner/repo are one shepherd."""
    module = _load()
    for repo in ("Owner/Repo", "owner/repo", "OWNER/REPO", "oWnEr/rEpO"):
        assert module.canonical_repo(repo) == "owner/repo"
    # Non-ASCII must NOT fold: the digest is an identity, not a display string.
    assert module.canonical_repo("Ünïcøde/Repo") == "Ünïcøde/repo"
