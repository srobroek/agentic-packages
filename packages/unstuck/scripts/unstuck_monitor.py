#!/usr/bin/env python3
"""Unstuck monitor (stdlib-only): outcome-gated stuck detection.

One script, four phases, selected by an argv token (in the hook *command*
string -- Codex ignores the hooks.json "args" field):

  edit     PostToolUse Edit|Write|MultiEdit (+ apply_patch on Codex).
           Tracks re-edits and content flip-flops of source files.
  bash     PostToolUse Bash. Tracks per-command failure streaks; a passing
           test runner or git commit fully resets state.
  gate     PreToolUse Edit|Write|MultiEdit. After the third alert, emits an
           advisory once per stuck episode (edit still proceeds).
  release  Claude PreToolUse Skill / Codex UserPromptSubmit. Invoking the
           unstuck or diagnose skill lifts the gate.

Detection is outcome-gated: alerts fire only when failure evidence exists
(a failing test runner, a command failing repeatedly, or a content
flip-flop). Any green test run or commit zeroes everything, so healthy
TDD/refactor churn never fires.

Escalation ladder: alert 1 = advisory nudge; alert 2 = directive with the
unstuck workflow inlined; alert 3 = advisory suggesting the agent step back
and change approach (edit still proceeds; not a hard gate).
Escape hatch: UNSTUCK_GATE_OFF=1.

Never blocks on errors: malformed input, missing git, or corrupt state all
exit 0 silently (a crashing PreToolUse hook would block every tool call).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time

STATE_VERSION = 2
STATE_PREFIX = "/tmp/claude-stuck-"
MAX_HASH_BYTES = 1024 * 1024

SOURCE_EXT = (
    "py ts tsx js jsx go rs c cpp h hpp cs java rb swift vue svelte zig hs "
    "ex exs kt scala sh bash zsh sql tf tfvars toml yaml yml"
).split()
EXCLUDE_RE = re.compile(
    r"(^|/)(dist|build|node_modules)/"
    r"|(^|/)(package-lock\.json|pnpm-lock\.yaml|go\.sum)$"
    r"|\.lock$"
    r"|\.min\.[a-z]+$"
)

# Commands whose success means progress (full reset). Prefix match on the
# env-stripped command; mirrors the v1 stuck-reset list.
PROGRESS_PREFIXES = (
    "git commit", "pytest", "python -m pytest", "uv run pytest",
    "npm test", "pnpm test", "pnpm run test", "cargo test", "cargo nextest",
    "go test", "vitest", "jest", "mocha", "just test", "task test",
    "make test", "pre-commit run",
)
# Commands that legitimately repeat/fail: never counted in failure streaks.
STREAK_EXCLUDE_RE = re.compile(r"--watch\b|^watch\s|\btail\s+-f\b|^sleep\s")

RELEASE_SKILLS_RE = re.compile(r"\b(unstuck|diagnose)\b", re.IGNORECASE)


def _env_int(name, default):
    try:
        return int(os.environ.get(name, ""))
    except ValueError:
        return default


def fresh_state():
    return {
        "v": STATE_VERSION,
        "files": {},
        "cmds": {},
        "re_edits": 0,
        "last_test_failed": False,
        "fire_count": 0,
        "last_fired": 0,
        "gated": False,
        "gate_notified": False,
    }


def state_path(payload):
    cwd = payload.get("cwd") or os.getcwd()
    try:
        repo = subprocess.check_output(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8", "replace").strip() or cwd
    except (OSError, subprocess.CalledProcessError):
        repo = cwd
    key = "%s:%s" % (repo, payload.get("session_id") or "")
    return STATE_PREFIX + hashlib.md5(key.encode()).hexdigest() + ".json"


def sweep_stale():
    cutoff = time.time() - 86400
    try:
        for name in os.listdir("/tmp"):
            if name.startswith("claude-stuck-") and name.endswith(".json"):
                p = os.path.join("/tmp", name)
                try:
                    if os.path.getmtime(p) < cutoff:
                        os.unlink(p)
                except OSError:
                    pass
    except OSError:
        pass


def load_state(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            st = json.load(fh)
        if isinstance(st, dict) and st.get("v") == STATE_VERSION:
            return st
    except (OSError, ValueError):
        pass
    return fresh_state()


def save_state(path, st):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(st, fh)
        os.replace(tmp, path)
    except OSError:
        pass


def tracked(path):
    if EXCLUDE_RE.search(path):
        return False
    ext = path.rsplit(".", 1)[-1] if "." in path else ""
    return ext in SOURCE_EXT


def edited_files(payload):
    """File paths from Edit/Write/MultiEdit or a Codex apply_patch body."""
    tool = payload.get("tool_name") or payload.get("tool") or ""
    ti = payload.get("tool_input")
    if tool.endswith("apply_patch"):
        if isinstance(ti, str):
            patch = ti
        elif isinstance(ti, dict):
            patch = ti.get("patch") or ti.get("input") or ""
        else:
            patch = ""
        return re.findall(r"^\*\*\* (?:Update|Add) File: (.+)$", patch, re.M)
    if isinstance(ti, dict):
        fp = ti.get("file_path")
        return [fp] if fp else []
    return []


def file_hash(path):
    try:
        if os.path.getsize(path) > MAX_HASH_BYTES:
            return None
        with open(path, "rb") as fh:
            return hashlib.md5(fh.read()).hexdigest()
    except OSError:
        return None


def normalize_cmd(cmd):
    cmd = re.sub(r"^(\s*[A-Za-z_][A-Za-z0-9_]*=\S+\s+)*", "", cmd)
    return re.sub(r"\s+", " ", cmd).strip()


def failure_evidence(st):
    if st["last_test_failed"]:
        return True
    if any(c.get("n", 0) >= 2 for c in st["cmds"].values()):
        return True
    if any(f.get("flipflops", 0) >= 1 for f in st["files"].values()):
        return True
    return False


def activity(st):
    return (
        st["re_edits"]
        + sum(c.get("n", 0) for c in st["cmds"].values())
        + sum(f.get("flipflops", 0) for f in st["files"].values())
    )


def evidence_summary(st):
    parts = []
    if st["files"]:
        hot, info = max(st["files"].items(), key=lambda kv: kv[1]["edits"])
        nfiles = len(st["files"])
        parts.append(
            "%s edited %dx (%d re-edits across %d source files)"
            % (hot, info["edits"], st["re_edits"], nfiles)
        )
    flips = [
        "%s (%dx)" % (p, f["flipflops"])
        for p, f in st["files"].items()
        if f.get("flipflops", 0) > 0
    ]
    if flips:
        parts.append(
            "content flip-flops (edits reverting earlier versions): "
            + ", ".join(sorted(flips))
        )
    if st["cmds"]:
        h, c = max(st["cmds"].items(), key=lambda kv: kv[1].get("n", 0))
        if c.get("n", 0) >= 2:
            parts.append(
                "'%s' failed %dx in a row" % (c.get("excerpt", "?"), c["n"])
            )
    if st["last_test_failed"]:
        parts.append("last test run failed; no green test or commit since")
    return "; ".join(parts)


WORKFLOW_INLINE = (
    "Unstuck workflow: 1) gather only observable facts -- exact failing "
    "command and error, smallest reproduction, recent changes (git diff "
    "--stat); 2) name the current leading assumption and the evidence for "
    "it; 3) generate 1-3 alternative hypotheses that explain all "
    "observations; 4) run the smallest check that can disprove the leading "
    "assumption; 5) if still stuck, brief the adversarial-challenger agent "
    "with the facts only -- never the preferred theory."
)


def alert_message(st):
    evidence = evidence_summary(st)
    if st["fire_count"] <= 1:
        return (
            "STUCK DETECTOR: " + evidence + ". If the next step is another "
            "variation of the same fix, stop: use the unstuck skill to "
            "challenge the leading assumption (it can escalate to the "
            "adversarial-challenger agent), or the diagnose skill first if "
            "there is no trusted reproduction yet. This advisory backs off "
            "after firing -- act on it now."
        )
    if st["fire_count"] == 2:
        return (
            "STUCK DETECTOR (second alert): " + evidence + ". Stop the "
            "current approach. Invoke the unstuck skill NOW, before any "
            "further edits. " + WORKFLOW_INLINE
        )
    return (
        "STUCK DETECTOR (repeated alerts, no progress): " + evidence + ". "
        "The agent appears stuck. This edit is proceeding, but continuing "
        "the same approach is unlikely to help. Step back: invoke the "
        "unstuck or diagnose skill, ask for help, or try a fundamentally "
        "different approach. " + WORKFLOW_INLINE
    )


GATE_REASON = (
    "STUCK DETECTOR ADVISORY: repeated alerts with no green test or commit "
    "since. This edit is proceeding, but the pattern strongly suggests the "
    "agent is stuck. Invoke the unstuck skill (or diagnose) to challenge "
    "the current approach, or produce a passing test run / commit. "
    "Override to suppress this advisory: set UNSTUCK_GATE_OFF=1."
)


def emit_context(event, msg):
    json.dump(
        {"hookSpecificOutput": {"hookEventName": event, "additionalContext": msg}},
        sys.stdout,
    )
    sys.stdout.write("\n")


def maybe_fire(st, event):
    """Evaluate triggers; on a fire, advance the ladder and emit the alert."""
    if not failure_evidence(st):
        return
    t_total = _env_int("UNSTUCK_THRESHOLD", 8)
    t_file = _env_int("UNSTUCK_FILE_THRESHOLD", 4)
    t_cmd = _env_int("UNSTUCK_CMD_THRESHOLD", 4)
    t_flip = _env_int("UNSTUCK_FLIPFLOP_THRESHOLD", 2)

    hot_reedits = max(
        (f["edits"] - 1 for f in st["files"].values()), default=0
    )
    max_streak = max((c.get("n", 0) for c in st["cmds"].values()), default=0)
    max_flips = max(
        (f.get("flipflops", 0) for f in st["files"].values()), default=0
    )
    triggered = (
        st["re_edits"] >= t_total
        or hot_reedits >= t_file
        or max_streak >= t_cmd
        or max_flips >= t_flip
    )
    if not triggered:
        return
    # Back off after a fire; re-arm only after another full threshold of
    # combined activity (re-edits + failures + flip-flops).
    act = activity(st)
    if st["last_fired"] and act < st["last_fired"] + t_total:
        return
    st["fire_count"] += 1
    st["last_fired"] = max(act, 1)
    if st["fire_count"] >= 3:
        st["gated"] = True
    emit_context(event, alert_message(st))


def phase_edit(payload, st):
    touched = False
    for path in edited_files(payload):
        if not path or not tracked(path):
            continue
        touched = True
        info = st["files"].setdefault(
            path, {"edits": 0, "hashes": [], "flipflops": 0}
        )
        info["edits"] += 1
        if info["edits"] > 1:
            st["re_edits"] += 1
        h = file_hash(path)
        if h:
            hashes = info["hashes"]
            if not hashes or h != hashes[-1]:
                if len(hashes) == 2 and h == hashes[0]:
                    info["flipflops"] += 1
                hashes.append(h)
                del hashes[:-2]
    if touched:
        maybe_fire(st, payload.get("hook_event_name") or "PostToolUse")
    return touched


def phase_bash(payload, st):
    ti = payload.get("tool_input") or {}
    cmd = ti.get("command") if isinstance(ti, dict) else ""
    if not cmd:
        return False
    resp = payload.get("tool_response") or {}
    code = resp.get("exit_code", resp.get("exitCode", 0))
    try:
        code = int(code)
    except (TypeError, ValueError):
        code = 0

    norm = normalize_cmd(cmd)
    is_progress = norm.startswith(PROGRESS_PREFIXES)
    if code == 0:
        if is_progress:
            # Full reset: progress clears all signals and lifts the gate.
            st.clear()
            st.update(fresh_state())
        else:
            st["cmds"].pop(hashlib.md5(norm.encode()).hexdigest(), None)
        return True
    # Failure path.
    if is_progress:
        st["last_test_failed"] = True
    if STREAK_EXCLUDE_RE.search(norm):
        return True
    entry = st["cmds"].setdefault(
        hashlib.md5(norm.encode()).hexdigest(),
        {"n": 0, "excerpt": norm[:80]},
    )
    entry["n"] += 1
    maybe_fire(st, payload.get("hook_event_name") or "PostToolUse")
    return True


def phase_gate(payload, st):
    if not st.get("gated") or os.environ.get("UNSTUCK_GATE_OFF") == "1":
        return False
    if any(tracked(p) for p in edited_files(payload) if p):
        if not st.get("gate_notified"):
            emit_context("PreToolUse", GATE_REASON)
            st["gate_notified"] = True
            return True  # state is dirty; persist the notified flag
    return False


def phase_release(payload, st):
    ti = payload.get("tool_input")
    text = ""
    if isinstance(ti, dict):
        text = str(ti.get("skill") or ti.get("command_name") or "")
    text = text or str(payload.get("prompt") or "")
    if st.get("gated") and RELEASE_SKILLS_RE.search(text):
        st["gated"] = False
        st["gate_notified"] = False
        return True
    return False


def main():
    phase = "edit"
    for arg in sys.argv[1:]:
        if arg in ("edit", "bash", "gate", "release"):
            phase = arg
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0

    sweep_stale()
    path = state_path(payload)
    st = load_state(path)

    try:
        if phase == "edit":
            dirty = phase_edit(payload, st)
        elif phase == "bash":
            dirty = phase_bash(payload, st)
        elif phase == "gate":
            dirty = phase_gate(payload, st)
        else:
            dirty = phase_release(payload, st)
    except Exception:
        return 0
    if dirty:
        save_state(path, st)
    return 0


if __name__ == "__main__":
    sys.exit(main())
