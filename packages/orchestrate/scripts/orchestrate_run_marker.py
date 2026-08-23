"""Active-run state and deny emission for the orchestrate guards. Imported, never run.

Both PreToolUse guards narrow themselves to an active run, so both need one
answer to "is a run still going". Marker presence is not that answer: a crashed
run leaves its marker behind, and every later session in the repository then
stayed under the protocol -- claim-deny refusing every `bd ... --claim`,
activation-guard refusing every unrecognised spawn -- until someone deleted the
file by hand.

Liveness costs a `bd` spawn, so it is deliberately NOT the entry gate. A guard
gates on `marker_present` (two stat calls) and reaches `emit_deny`, which
withholds the deny when the run has finished. Only a caller the guard was about
to refuse pays for the probe; a Bash call that claims nothing pays nothing. That
ordering is why `emit_deny` owns the check rather than each guard's `main`:
denial is these guards' only effect, so gating the emission makes a dead run
inert on every path at once, including ones added later.

Every uncertainty resolves toward live, because these functions only ever narrow
a guard. An unreadable or unparsable marker, an absent run id, the `pending`
sentinel that orchestrator-run-activate.py writes before the run epic exists, and
an unreachable or absent bd all read as live. A run is dead only when bd
positively reports its run bead terminal.
"""

import json
import os
import subprocess
import sys

BD = os.environ.get("BD_BIN", "bd")
DEFAULT_MARKER = "./.orchestration/.active-run"
TERMINAL_STATUS = frozenset({"closed", "tombstone"})


def emit_allow() -> None:
    sys.stdout.write("{}\n")
    raise SystemExit(0)


def emit_deny(reason: str) -> None:
    """Refuse the call, unless the run whose marker engaged the guard has finished."""
    if not run_live():
        emit_allow()
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
        + "\n"
    )
    raise SystemExit(0)


def marker_path() -> str:
    """Marker the run writes. ORCHESTRATE_MARKER_FILE wins outright when set."""
    return os.environ.get("ORCHESTRATE_MARKER_FILE", "") or DEFAULT_MARKER


def marker_present() -> bool:
    """Whether this repository is under an orchestrate run, ignoring liveness."""
    return bool(os.environ.get("ORCHESTRATE_RUN")) or os.path.isfile(marker_path())


def show_bead(bead_id: str, timeout: float = 10) -> dict | None:
    """One bead as bd reports it, or None when bd cannot answer."""
    try:
        proc = subprocess.run(
            [BD, "show", bead_id, "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={
                **os.environ,
                "BD_JSON_ENVELOPE": "1",
                "BD_NO_PAGER": "1",
                "BD_NON_INTERACTIVE": "1",
            },
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        value = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    if isinstance(value, dict) and "data" in value:
        value = value["data"]
    if isinstance(value, list):
        value = value[0] if value else None
    return value if isinstance(value, dict) else None


def active_run_id() -> str:
    """Run id the marker names; "" when the marker is absent or unreadable."""
    try:
        with open(marker_path(), encoding="utf-8") as handle:
            value = json.loads(handle.read())
    except (OSError, json.JSONDecodeError, TypeError):
        return ""
    if isinstance(value, dict):
        return str(value.get("run_id") or "")
    return ""


def run_live() -> bool:
    """Whether the run the marker names has not finished."""
    run_id = active_run_id()
    if not run_id or run_id == "pending":
        return True
    record = show_bead(run_id)
    if record is None:
        return True
    return str(record.get("status") or "").lower() not in TERMINAL_STATUS
