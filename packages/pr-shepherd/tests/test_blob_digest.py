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
