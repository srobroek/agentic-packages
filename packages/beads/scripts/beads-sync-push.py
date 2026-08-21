#!/usr/bin/env python3
"""Publish bead state once at session end (SessionEnd on Claude, Stop on Codex).

The events differ because Codex has no SessionEnd; Stop is its nearest end-of-turn
signal.

WHY SESSION END AND NOT PER-COMMIT: an incremental push costs ~12s, of which ~8s is
process and container startup rather than data transfer (measured against a 311 MB,
4354-commit database: 12.2s incremental, 8.1s for a no-op invocation). That cost is
fixed per invocation, so pushing after every commit made a ten-commit session pay
two minutes for what one push covers. Dolt pushes are additive and idempotent, so a
single push at the end loses nothing.

WHY DETACHED: even 12s of session teardown is time the user waits on a network round
trip they do not care about, and the FIRST push of a database that has never synced
uploads its whole history -- measured at over 550s on that same repository. So this
starts the push and returns immediately.

HOW FAILURES STAY VISIBLE: a detached process cannot report to the session that
spawned it, and a silently failing push is the worst outcome here -- bead state would
look shared while sitting on one machine. So the push writes its outcome to
.beads/last-push.log and beads-sync-session.py reports what it finds there at the
next session start.

Ported from shell, whose detach path was `setsid ... & || nohup ... &` wrapping a
/bin/sh -c script that re-derived its own `timeout`/`gtimeout` bound. setsid does not
exist on macOS, so the primary branch never ran there. `subprocess.Popen` with
start_new_session=True is the same detachment on both platforms, and the child is a
Python function rather than a nested shell string, so no quoting layer can mangle a
path.

Fail open (exit 0) whenever state cannot be determined.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import UTC

import beads_sync  # noqa: E402

# Bound on the DETACHED push, not on this hook: the hook returns as soon as the
# background process starts, so a long bound costs the session nothing. Generous
# because a first push uploads accumulated history -- 90s was too low in practice
# and reported "did not complete" on a push that was simply still running. (Codex
# caps hook timeouts at 60s, which is fine for the same reason: what must finish
# inside the hook is the policy probe, not the push.)
PUSH_TIMEOUT = float(os.environ.get("BEADS_SYNC_PUSH_TIMEOUT", "600"))
PROBE_TIMEOUT = float(os.environ.get("BEADS_SYNC_PROBE_TIMEOUT", "30"))


def resolve_runner(cwd: str) -> str:
    """Executable that performs the push.

    A host that cannot push directly may still have a wrapper that runs bd somewhere
    with network access. Ask for one by name rather than hardcoding a tool:
    custom.bd-push-command names an executable that must accept bd's argv.

    The indirection is load-bearing: APM merges each package's hooks and records
    provenance per entry, so a machine-local package can ADD hooks but never remove
    or replace this one. Hardcoding `bd` would leave a host that needs a wrapper no
    way to redirect it.
    """
    import shutil

    configured = beads_sync.config(cwd, "custom.bd-push-command")
    if configured and shutil.which(configured):
        return configured
    return "bd"


def detach(runner: str, cwd: str, log: str) -> None:
    """Start the push in a new session and return without waiting."""
    import subprocess

    child = (
        "import subprocess,sys\n"
        "runner,cwd,log,timeout=sys.argv[1:5]\n"
        "try:\n"
        "    with open(log,'a',encoding='utf-8') as fh:\n"
        "        rc=subprocess.run([runner,'-C',cwd,'dolt','push'],stdout=fh,stderr=fh,\n"
        "            timeout=float(timeout),check=False).returncode\n"
        "        fh.write('ok: push complete\\n' if rc==0 else\n"
        "            f'failed: {runner} dolt push exited {rc} (output above)\\n')\n"
        "except Exception as error:\n"
        "    with open(log,'a',encoding='utf-8') as fh:\n"
        "        fh.write(f'failed: {type(error).__name__}: {error}\\n')\n"
    )
    environment = dict(os.environ)
    environment.update(beads_sync.BD_ENV)
    try:
        subprocess.Popen(  # noqa: S603
            [sys.executable, "-c", child, runner, cwd, log, str(PUSH_TIMEOUT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env=environment,
        )
    except (OSError, ValueError):
        _write(log, "failed: could not start the detached push process\n")


def _write(path: str, text: str, *, append: bool = False) -> None:
    try:
        with open(path, "a" if append else "w", encoding="utf-8") as handle:
            handle.write(text)
    except OSError:
        pass


def main() -> int:
    payload = sys.stdin.read()

    if not beads_sync.bd_available():
        return 0

    cwd = beads_sync.payload_cwd(payload, os.getcwd())
    beads = beads_sync.beads_dir(cwd)
    if not beads:
        return 0

    if not beads_sync.opt(cwd, "custom.dolt-auto-push"):
        return 0
    if not beads_sync.has_dolt_remote(cwd):
        return 0

    log = os.path.join(beads, "last-push.log")

    # A push needs a Dolt commit to carry. Auto-commit policy may be 'off' or
    # 'batch', in which case writes sit in the working set until something commits
    # them -- so commit first, and treat "nothing to commit" as fine. Cheap and
    # local, so it stays in the foreground where a failure is still visible.
    beads_sync.run(
        ["bd", "-C", cwd, "dolt", "commit", "-m", "beads: session state"],
        timeout=60,
        env=beads_sync.BD_ENV,
    )

    runner = resolve_runner(cwd)

    # Probe policy in the FOREGROUND: it is bounded and cheap, and its verdict
    # decides whether a detached push is worth starting at all. Spawning a
    # background push that will be refused, just to log the refusal for the next
    # session, is worse than recording it now.
    verdict = beads_sync.push_permitted(cwd, PROBE_TIMEOUT)

    if verdict == beads_sync.PUSH_REFUSED and runner == "bd":
        # A direct push will not go through, and with no wrapper configured there is
        # nothing to detach. Record why and stop.
        _write(
            log,
            "failed: a direct push does not go through from this host, and "
            "custom.bd-push-command is not set. Set it to a wrapper that can reach "
            "the remote, or use the JSONL path.\n",
        )
        return 0

    if verdict == beads_sync.PUSH_NO_VERDICT:
        # Unreachable, timed out, or no origin. Transient -- skip quietly and let the
        # next session try. State is committed locally, so nothing is lost.
        return 0

    from datetime import datetime

    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write(log, f"started: {stamp}\n")
    detach(runner, cwd, log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
