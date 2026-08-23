#!/usr/bin/env python3
"""SessionStart hook: hydrate bead state, prime workflow context, report growth.

Folds beads-sync-hydrate.sh and beads-maintenance-check.sh into one script, per the
hook contract's rule 5: both bound SessionStart with the same empty matcher, so they
paid two process startups and two payload parses to answer questions about the same
workspace. Their advisories are now emitted as one message. `bd prime` is folded in
for the same reason -- see prime().

HYDRATION, native first, always:
  1. `bd dolt pull` where a Dolt remote exists and custom.dolt-auto-pull is on.
     This is the real sync path: it moves Dolt commits, not merely issue rows.
  2. `bd import` of .beads/issues.jsonl, and only where that file differs from what
     this database would export. Identical content means the file has nothing to
     give, so importing would be wasted work at every session start.
A successful pull does not skip step 2: a peer without push access may have
committed JSONL the Dolt remote has never seen, so the file can still be ahead.

This hook only receives. Publishing is beads-sync-push.py, which runs at session
end -- at session start there is nothing new to send.

MAINTENANCE REPORTS ONLY. Every command it names is destructive and irreversible,
so the decision stays with the operator. `bd prune` deletes closed beads, `bd purge`
deletes closed wisps, and `bd flatten` discards ALL Dolt commit history. A hook that
ran them on a threshold would eventually delete work somebody wanted, silently and
permanently.

COMMIT COUNT is the growth signal, not bead count. Measured on a real repository at
311 MB with 207 open beads: the export payload was 2.8 MB, .dolt/noms/ was 199 MB,
and the git-remote-cache was 96 MB. The beads were 1% of it; 4354 Dolt commits were
the rest, because each create/update/comment/close writes one and nothing is
collected by default. On that same repository `bd prune --older-than 90d` matched
nothing at all, so a prune-based threshold would have stayed silent throughout.

Fail open (exit 0) throughout: a sync or maintenance notice must never be the reason
a session cannot start.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import beads_sync  # noqa: E402

# Longest a session start may wait on the network: `bd dolt pull` against an
# unreachable remote does not always fail fast.
PULL_TIMEOUT = float(os.environ.get("BEADS_SYNC_PULL_TIMEOUT", "60"))

# Commit count that warrants mentioning. Deliberately high: this fires once per
# session and a false alarm trains people to ignore it.
COMMIT_THRESHOLD = int(os.environ.get("BEADS_MAINTENANCE_COMMIT_THRESHOLD", "2000"))

# `bd prime` reads the database only, so this bounds a hung read, not a network call.
PRIME_TIMEOUT = float(os.environ.get("BEADS_PRIME_TIMEOUT", "20"))


def report_previous_push(beads: str, notes: list[str]) -> None:
    """Surface the verdict the previous session's detached push left behind.

    beads-sync-push.py detaches, so it cannot report to the session that spawned
    it. It writes a verdict line here instead. Reporting it now is the only thing
    keeping a failed push from being silent -- state would look published while
    sitting on one machine.
    """
    log = os.path.join(beads, "last-push.log")
    if not os.path.isfile(log):
        return
    try:
        with open(log, encoding="utf-8", errors="replace") as handle:
            lines = [line for line in handle.read().splitlines() if line.strip()]
    except OSError:
        return

    last = lines[-1] if lines else ""
    if last.startswith("failed:"):
        notes.append(
            "the last session's beads push FAILED -- state is committed locally but "
            f"not published. See {log}; rerun the push when the cause is fixed."
        )
    elif last.startswith("started:"):
        # Only a start line: the push was cut off before writing a verdict, so the
        # machine slept or the process was killed mid-transfer.
        notes.append(
            f"the last session's beads push did not finish (no result recorded in {log}); "
            "it may need rerunning."
        )

    # Clear it either way: a stale verdict must not be re-reported every session.
    # This is the ONLY reader, so consuming the file loses nothing.
    try:
        os.unlink(log)
    except OSError:
        pass


def hydrate(cwd: str, beads: str, notes: list[str]) -> None:
    """Pull native Dolt state, then import JSONL when it has something to give."""
    if beads_sync.has_dolt_remote(cwd) and beads_sync.opt(cwd, "custom.dolt-auto-pull"):
        pulled = beads_sync.run(
            ["bd", "-C", cwd, "dolt", "pull"],
            timeout=PULL_TIMEOUT,
            env=beads_sync.BD_ENV,
        )
        if pulled is None or pulled.returncode != 0:
            # Non-fatal: the remote may be empty (nothing pushed yet) or
            # unreachable. The JSONL step below is the fallback for exactly these.
            notes.append(
                "bd dolt pull did not complete (remote empty, unreachable, or "
                "blocked); using JSONL if present."
            )

    if not beads_sync.opt(cwd, "custom.jsonl-git-sync"):
        return

    source = os.path.join(beads, "issues.jsonl")
    try:
        if not os.path.getsize(source):
            return
    except OSError:
        return

    # Compare against a fresh export instead of timestamps. bd exposes no
    # database-wide commit time (`bd history` needs an issue id; `bd vc status`
    # gives a hash with no date), and file mtime is unreliable after a checkout --
    # git sets it to clone time regardless of content age. Byte comparison is exact
    # and cheap, and bd's export is deterministic.
    probe = f"{source}.hydrate-probe.{os.getpid()}"
    differs = True
    if beads_sync.export_all(cwd, probe):
        import filecmp

        try:
            differs = not filecmp.cmp(probe, source, shallow=False)
        except OSError:
            differs = True
    try:
        os.unlink(probe)
    except OSError:
        pass

    if not differs:
        return

    # The union merge driver leaves duplicate ids in the file on concurrent edits;
    # that is deliberate. Git moves bytes, the importer decides which row wins by
    # updated_at.
    imported = beads_sync.run(
        ["bd", "-C", cwd, "import", "--json", source],
        timeout=180,
        env={**beads_sync.BD_ENV, "BD_JSON_ENVELOPE": "1"},
    )
    if imported is None or not imported.stdout.strip():
        return

    data = beads_sync.envelope(imported.stdout)
    if not data:
        return
    stale = data.get("stale_skipped_ids")
    if not isinstance(stale, list) or not stale:
        return

    # Report a stale skip only. Routine hydration is not worth a line in every
    # session: `created` counts rows processed, not rows changed. A stale skip is
    # different -- the committed file is BEHIND this database, so the next export
    # overwrites whatever a peer committed.
    joined = ", ".join(str(item) for item in stale)
    notes.append(
        f"issues.jsonl is BEHIND this database (stale rows: {joined}); local state "
        "kept. Commit a fresh export before pulling peer changes."
    )


def count(cwd: str, command: list[str], key: str) -> int:
    """Read one integer count from a bd dry-run's JSON output."""
    result = beads_sync.run(
        ["bd", "-C", cwd, *command],
        timeout=120,
        env={**beads_sync.BD_ENV, "BD_JSON_ENVELOPE": "1"},
    )
    if result is None or not result.stdout.strip():
        return 0
    data = beads_sync.envelope(result.stdout)
    if not data:
        return 0
    value = data.get(key)
    return value if isinstance(value, int) and value >= 0 else 0


def maintenance(cwd: str, notes: list[str]) -> None:
    """Report when the database has grown enough to be worth trimming."""
    # Opt-in, like the sync hooks: a repository that does not want maintenance
    # nagging says nothing and gets nothing.
    if not beads_sync.opt(cwd, "custom.maintenance-check"):
        return

    # `bd flatten --dry-run --json` reports commit_count and changes nothing. It is
    # the only machine-readable size signal bd exposes: `bd status --json` returns
    # an empty summary, and `bd vc status` gives a hash with no counts.
    commits = count(cwd, ["flatten", "--dry-run", "--json"], "commit_count")
    if commits < COMMIT_THRESHOLD:
        return

    # Count what is actually reclaimable, so the notice names real numbers rather
    # than sending someone to read three --help pages. Both are dry runs. Field
    # names verified against live output, not guessed: prune reports `prune_count`
    # and purge reports `purged_count`.
    prunable = count(
        cwd, ["prune", "--older-than", "90d", "--dry-run", "--json"], "prune_count"
    )
    purgeable = count(
        cwd, ["purge", "--older-than", "30d", "--dry-run", "--json"], "purged_count"
    )

    message = f"{commits} Dolt commits (threshold {COMMIT_THRESHOLD})."
    if purgeable:
        message += (
            f" {purgeable} closed wisp(s) older than 30d -- 'bd purge --older-than "
            "30d --force' is the safe first step; wisps have no value once closed."
        )
    if prunable:
        message += (
            f" {prunable} closed bead(s) older than 90d could go with 'bd prune "
            "--older-than 90d --force'."
        )
    message += (
        " Deleting rows does NOT shrink storage on its own -- commit history is the "
        "bulk, and only 'bd flatten --force' reclaims it, which discards ALL history "
        "irreversibly. Review with --dry-run first; none of this is automatic."
    )
    notes.append(f"maintenance: {message}")


def prime(cwd: str, subagent: bool) -> str:
    """Workflow context for this session start.

    Folded in here rather than bound as its own hook, for the reason in the module
    docstring: a second SessionStart entry with the same empty matcher would pay a
    second process start and payload parse over the same workspace. `bd prime
    --hook-json` would also emit a competing envelope; this returns text so the one
    advisory below carries everything.

    A subagent already has the contract from beads-subagent-reminder.py, so it gets
    only its scoped memories -- measured 5714 chars for a full prime against 1273 for
    memories alone.
    """
    if subagent:
        return beads_sync.render_memories(
            beads_sync.memories(cwd, beads_sync.memory_prefixes())
        )
    result = beads_sync.run(
        ["bd", "-C", cwd, "prime"], timeout=PRIME_TIMEOUT, env=beads_sync.BD_ENV
    )
    if result is None or result.returncode != 0:
        return ""
    return result.stdout.strip()


def main() -> int:
    raw = sys.stdin.read()

    if not beads_sync.bd_available():
        return 0

    cwd = beads_sync.payload_cwd(raw, os.getcwd())
    beads = beads_sync.beads_dir(cwd)
    if not beads:
        return 0

    notes: list[str] = []
    report_previous_push(beads, notes)
    hydrate(cwd, beads, notes)
    maintenance(cwd, notes)

    sections: list[str] = []
    if notes:
        sections.append("beads sync: " + " ".join(notes))
    # No parseable payload means no stated workspace, so the cwd here is a guess from
    # whatever spawned the hook. Syncing a guessed workspace is safe; priming it is
    # not -- it would inject another project's context.
    if beads_sync.payload(raw):
        context = prime(cwd, beads_sync.is_subagent(raw))
        if context:
            sections.append(context)

    if sections:
        beads_sync.emit("SessionStart", "\n\n".join(sections))
    return 0


if __name__ == "__main__":
    sys.exit(main())
