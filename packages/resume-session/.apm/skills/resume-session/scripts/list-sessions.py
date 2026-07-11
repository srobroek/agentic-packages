#!/usr/bin/env python3
"""List prior agent sessions for a repository, newest first.

Discovers Claude Code transcripts (~/.claude/projects/<encoded>/*.jsonl) and
Codex rollouts (~/.codex/sessions/**/rollout-*.jsonl) whose working directory
matches the target project, then prints a compact, selectable table.

Only the metadata needed to choose a session is emitted -- never full bodies.

Usage:
    list-sessions.py [--project PATH] [--agent claude|codex|all]
                     [--limit N] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

CLAUDE_ROOT = os.path.expanduser("~/.claude/projects")
CODEX_ROOT = os.path.expanduser("~/.codex/sessions")
LAST_SNIPPET_CHARS = 160  # high-level "where it left off" snippet per session


def default_project() -> str:
    """The repo the user is working in -- NOT the skill/script directory.

    A skill's scripts often run with cwd set to the skill folder, so a plain
    os.getcwd() points at the wrong place. The git toplevel resolves to the
    actual project root even when invoked from inside .claude/skills/...
    """
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return os.getcwd()


def encode_project(path: str) -> str:
    """Claude encodes a project path by replacing every non-alphanumeric
    character with '-' (so '/', '.', spaces, and '_' all become '-')."""
    return re.sub(r"[^a-zA-Z0-9]", "-", path)


def parse_ts(value) -> float | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        # Codex sometimes uses epoch seconds.
        return float(value)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def rel_time(epoch: float | None) -> str:
    if not epoch:
        return "unknown"
    delta = max(0, time.time() - epoch)
    for unit, secs in (("d", 86400), ("h", 3600), ("m", 60)):
        if delta >= secs:
            return f"{int(delta // secs)}{unit} ago"
    return "just now"


def abs_time(epoch: float | None) -> str:
    if not epoch:
        return "unknown"
    return datetime.fromtimestamp(epoch, timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# Worktree discovery
#
# A session for this project may live in ANY worktree of the same repo: the
# main checkout and every linked worktree each have their own cwd, so each gets
# its own ~/.claude/projects/<encoded> dir (and Codex rollouts tagged with that
# cwd). `git worktree list` from anywhere -- the main repo OR a linked worktree
# -- returns the whole family, so we enumerate it once and scan every member.
# ---------------------------------------------------------------------------

def list_worktrees(project: str) -> list[dict]:
    """Live worktrees of the repo containing `project`, main checkout first.

    Returns [{path, head, branch, detached, is_main}] for every worktree that
    still exists on disk and is not prunable. Returns [] when `project` is not
    inside a git repo (the caller then falls back to scanning `project` alone).
    """
    try:
        r = subprocess.run(
            ["git", "-C", project, "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []

    worktrees: list[dict] = []
    cur: dict = {}
    for line in r.stdout.splitlines():
        if not line.strip():
            if cur.get("path"):
                worktrees.append(cur)
            cur = {}
            continue
        if line.startswith("worktree "):
            cur = {"path": line[len("worktree "):], "head": "", "branch": "",
                   "detached": False, "prunable": False}
        elif line.startswith("HEAD "):
            cur["head"] = line[len("HEAD "):]
        elif line.startswith("branch "):
            ref = line[len("branch "):]
            # Keep multi-segment branch names intact (refs/heads/foo/bar -> foo/bar).
            cur["branch"] = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
        elif line == "detached":
            cur["detached"] = True
        elif line.startswith("prunable"):
            cur["prunable"] = True
    if cur.get("path"):
        worktrees.append(cur)

    out = []
    for idx, w in enumerate(worktrees):
        w["is_main"] = idx == 0  # porcelain always lists the main checkout first
        if w.get("prunable") or not os.path.isdir(w["path"]):
            continue
        out.append(w)
    return out


def commit_info(worktrees: list[dict], project: str) -> dict:
    """Map each worktree HEAD sha -> (commit_epoch, subject) in one git call.

    The recency of the last commit -- and its subject -- is the second signal
    (alongside transcript activity) for which worktree was last worked in.
    """
    heads = sorted({w["head"] for w in worktrees if w.get("head")})
    out: dict = {}
    if not heads:
        return out
    try:
        r = subprocess.run(
            ["git", "-C", project, "show", "-s", "--format=%H%x00%ct%x00%s", *heads],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return out
    if r.returncode != 0:
        return out
    for line in r.stdout.splitlines():
        parts = line.split("\x00")
        if len(parts) != 3:
            continue
        try:
            epoch = float(parts[1])  # %ct is integer epoch seconds
        except ValueError:
            epoch = None
        out[parts[0]] = (epoch, parts[2])
    return out


def is_dirty(path: str) -> bool:
    """True if the worktree has uncommitted changes -- a strong 'active' hint."""
    try:
        r = subprocess.run(
            ["git", "-C", path, "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and bool(r.stdout.strip())


def iter_json_lines(path: str):
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (ValueError, TypeError):
                continue
            # Records are scanned with .get(); a bare array/string/number line
            # would raise AttributeError and abort the whole listing. Skip them.
            if isinstance(obj, dict):
                yield obj


def _text_from_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") in ("text", "input_text"):
                parts.append(block.get("text", ""))
        return " ".join(p for p in parts if p)
    return ""


def _is_tool_result(content) -> bool:
    return isinstance(content, list) and any(
        isinstance(b, dict) and b.get("type") == "tool_result" for b in content
    )


def scan_claude(path: str) -> dict:
    """Extract selection metadata from one Claude transcript."""
    first_prompt = ""
    ai_title = ""
    branch = ""
    last_ts = None
    turns = 0
    last_assistant = ""
    session_id = os.path.splitext(os.path.basename(path))[0]
    for rec in iter_json_lines(path):
        rtype = rec.get("type")
        ts = parse_ts(rec.get("timestamp"))
        if ts:
            last_ts = ts if last_ts is None else max(last_ts, ts)
        if rec.get("gitBranch"):
            branch = rec["gitBranch"]
        if rtype == "ai-title" and rec.get("aiTitle"):
            ai_title = rec["aiTitle"]
        elif rtype == "user":
            content = rec.get("message", {}).get("content")
            if _is_tool_result(content):
                continue
            turns += 1
            if not first_prompt:
                text = _text_from_content(content).strip()
                if text and not text.startswith("<"):
                    first_prompt = text
        elif rtype == "assistant":
            turns += 1
            text = _text_from_content(rec.get("message", {}).get("content")).strip()
            if text:
                last_assistant = text  # keep the most recent assistant prose
    if last_ts is None:
        last_ts = os.path.getmtime(path)
    return {
        "agent": "claude",
        "session_id": session_id,
        "title": ai_title or first_prompt,
        "goal": first_prompt,
        "last": last_assistant,
        "branch": branch,
        "last_ts": last_ts,
        "turns": turns,
        "path": path,
    }


def collect_claude(project: str) -> list[dict]:
    proj_dir = os.path.join(CLAUDE_ROOT, encode_project(project))
    if not os.path.isdir(proj_dir):
        return []
    out = []
    for name in os.listdir(proj_dir):
        if name.endswith(".jsonl"):
            out.append(scan_claude(os.path.join(proj_dir, name)))
    return out


def collect_claude_worktrees(worktrees: list[dict]) -> list[dict]:
    """Scan the Claude transcript dir of every worktree, tagging each session
    with the worktree it belongs to (path + branch)."""
    out = []
    for w in worktrees:
        for entry in collect_claude(w["path"]):
            entry["wt_path"] = w["path"]
            entry["wt_branch"] = w["branch"]
            entry["wt_is_main"] = w.get("is_main", False)
            out.append(entry)
    return out


def scan_codex(path: str, accept: dict) -> dict | None:
    """Return metadata only if this rollout's cwd matches an accepted worktree.

    `accept` maps each worktree's realpath -> worktree dict; the rollout is
    tagged with whichever worktree its `session_meta.cwd` resolves to. Returns
    None for rollouts belonging to any other project.
    """
    meta_cwd = None
    session_id = ""
    first_prompt = ""
    last_agent = ""
    last_ts = None
    turns = 0
    wt = None
    for rec in iter_json_lines(path):
        rtype = rec.get("type")
        payload = rec.get("payload", {})
        ts = parse_ts(rec.get("timestamp"))
        if ts:
            last_ts = ts if last_ts is None else max(last_ts, ts)
        if rtype == "session_meta":
            meta_cwd = payload.get("cwd")
            session_id = payload.get("id", "")
            wt = accept.get(os.path.realpath(meta_cwd)) if meta_cwd else None
            if wt is None:
                return None  # cheap early-out before scanning the body
        elif rtype == "event_msg" and payload.get("type") == "user_message":
            turns += 1
            if not first_prompt:
                msg = (payload.get("message") or "").strip()
                if msg and not msg.startswith("<"):
                    first_prompt = msg
        elif rtype == "event_msg" and payload.get("type") == "agent_message":
            turns += 1
            msg = (payload.get("message") or "").strip()
            if msg:
                last_agent = msg
    if wt is None:
        return None
    if last_ts is None:
        last_ts = os.path.getmtime(path)
    return {
        "agent": "codex",
        "session_id": session_id or os.path.basename(path),
        "title": first_prompt,
        "goal": first_prompt,
        "last": last_agent,
        "branch": "",
        "last_ts": last_ts,
        "turns": turns,
        "path": path,
        "wt_path": wt["path"],
        "wt_branch": wt.get("branch", ""),
        "wt_is_main": wt.get("is_main", False),
    }


def collect_codex(worktrees: list[dict]) -> list[dict]:
    """Walk the Codex rollout tree once, keeping rollouts whose cwd matches any
    of the given worktrees. One walk handles all worktrees -- a per-worktree
    walk would rescan the entire tree N times."""
    if not os.path.isdir(CODEX_ROOT):
        return []
    accept = {os.path.realpath(w["path"]): w for w in worktrees}
    out = []
    for root, _, files in os.walk(CODEX_ROOT):
        for name in files:
            if name.startswith("rollout-") and name.endswith(".jsonl"):
                entry = scan_codex(os.path.join(root, name), accept)
                if entry:
                    out.append(entry)
    return out


def wt_label(e: dict) -> str:
    """Short, human label for the worktree a session/commit belongs to."""
    path = e.get("wt_path")
    if not path:
        return ""
    name = os.path.basename(path.rstrip("/")) or path
    return f"{name} (main)" if e.get("wt_is_main") else name


def render_git_activity(worktrees: list[dict], commits: dict, limit: int) -> list[str]:
    """Per-worktree git overview, most-recently-committed first.

    The recency and subject of each worktree's last commit is a second signal
    -- alongside transcript activity -- for which worktree is the live one. A
    `✎ dirty` mark means the worktree has uncommitted changes right now.
    """
    rows = []
    for w in worktrees:
        epoch, subject = commits.get(w.get("head", ""), (None, ""))
        rows.append((epoch or 0.0, w, subject))
    rows.sort(key=lambda r: r[0], reverse=True)

    lines = ["Worktree git activity (most recently committed first)"]
    shown = rows[:limit]
    for epoch, w, subject in shown:
        epoch = epoch or None
        label = wt_label({"wt_path": w["path"], "wt_is_main": w.get("is_main")})
        branch = w["branch"] or ("(detached)" if w.get("detached") else "?")
        subject = (subject or "").replace("\n", " ")
        if len(subject) > 60:
            subject = subject[:59] + "…"
        dirty = "  ✎ dirty" if is_dirty(w["path"]) else ""
        lines.append(
            f"  • {label:<26} [{branch}]  "
            f"{rel_time(epoch):<10} {abs_time(epoch)}  {subject}{dirty}"
        )
    if len(rows) > len(shown):
        lines.append(f"  … and {len(rows) - len(shown)} more worktree(s) not shown")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", default=None,
                    help="repo to list sessions for (default: the git repo root)")
    ap.add_argument("--agent", choices=["claude", "codex", "all"], default="all")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--no-worktrees", action="store_true",
                    help="scan only this project's transcript dir, not sibling worktrees")
    ap.add_argument("--no-git", action="store_true",
                    help="skip the per-worktree git-activity overview")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    limit = args.limit if args.limit > 0 else 20

    project = os.path.realpath(os.path.expanduser(args.project or default_project()))

    # Every worktree of the repo shares one transcript family: the main checkout
    # and each linked worktree have their own cwd and thus their own project dir.
    # `git worktree list` returns the whole set from any member, so the result
    # is identical whether we start in the main repo or in a linked worktree.
    worktrees = [] if args.no_worktrees else list_worktrees(project)
    if not worktrees:
        # Not a git repo, --no-worktrees, or git unavailable: scan project alone.
        worktrees = [{"path": project, "head": "", "branch": "",
                      "detached": False, "is_main": True}]

    entries: list[dict] = []
    if args.agent in ("claude", "all"):
        entries += collect_claude_worktrees(worktrees)
    if args.agent in ("codex", "all"):
        entries += collect_codex(worktrees)

    entries.sort(key=lambda e: e["last_ts"], reverse=True)
    entries = entries[:limit]

    commits = {} if args.no_git else commit_info(worktrees, project)

    if args.json:
        print(json.dumps({
            "project": project,
            "worktrees": [
                {**w, "head_commit": commits.get(w.get("head", ""), (None, ""))}
                for w in worktrees
            ],
            "sessions": entries,
        }, indent=2, default=str))
        return 0

    lines: list[str] = []
    if not args.no_git and len(worktrees) > 1:
        lines += render_git_activity(worktrees, commits, limit)
        lines.append("")

    scope = (f"across {len(worktrees)} worktrees"
             if len(worktrees) > 1 else "")
    if not entries:
        if scope:
            lines.append(f"No prior sessions found for {project} {scope}.")
        else:
            lines.append(f"No prior sessions found for project: {project}")
        lines.append("(searched Claude ~/.claude/projects and Codex ~/.codex/sessions)")
        print("\n".join(lines))
        return 0

    header = f"Prior sessions for {project}"
    if scope:
        header += f" {scope}"
    lines.append(f"{header}  (newest first, {len(entries)} shown)\n")
    for idx, e in enumerate(entries, 1):
        title = (e["title"] or "(no title)").replace("\n", " ")
        if len(title) > 68:
            title = title[:67] + "…"
        # Label with the branch the SESSION actually worked on (recorded in the
        # transcript), not the worktree's branch *now* -- a worktree that has
        # since switched branches would otherwise mislabel every past session
        # that ran in it. When the worktree has drifted, note where it is now so
        # the reader knows the files/branch may no longer match the transcript.
        recorded = e.get("branch") or ""
        wt_now = e.get("wt_branch") or ""
        if recorded and wt_now and recorded != wt_now:
            branch = f" [{recorded} → worktree now on {wt_now}]"
        elif recorded or wt_now:
            branch = f" [{recorded or wt_now}]"
        else:
            branch = ""
        lines.append(
            f"{idx:>2}. {e['agent']:<6} {e['session_id'][:8]}  "
            f"{rel_time(e['last_ts']):<10} {abs_time(e['last_ts'])}  "
            f"{e['turns']:>3} turns{branch}"
        )
        label = wt_label(e)
        if label and len(worktrees) > 1:
            lines.append(f"      worktree: {label}")
        lines.append(f"      {title}")
        last = (e.get("last") or "").replace("\n", " ").strip()
        if last and last != title:
            if len(last) > LAST_SNIPPET_CHARS:
                last = last[:LAST_SNIPPET_CHARS - 1] + "…"
            lines.append(f"      ↳ left off: {last}")
        lines.append(f"      id: {e['session_id']}")
    lines.append(
        "\nSelect one, then: read-session.py --session <id> "
        "(add --project if not run from the repo root). Sessions from any "
        "worktree resolve by id automatically."
    )
    body = "\n".join(lines)
    tokens = (len(body) + 3) // 4
    body += f"\n\nDiscovery cost: ~{tokens:,} uncached tokens (~{len(body):,} chars, estimated)."
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
