#!/usr/bin/env python3
"""Replay real historical commands through the rtk guard and measure the delta.

This answers the HALF of the A/B question that does not need an agent. Pull the
shell commands an agent actually ran out of transcript history, ask the guard
which it would route, run those both ways, and compare the bytes each returned.

Why this is worth having alongside the agent A/B: an agent run is
nondeterministic, so a token difference between two runs mixes the filter's
effect with variance in what the agent chose to do. Replay holds the command set
fixed, so the filter's effect is isolated and repeatable. What it CANNOT see is
the behavioral half -- whether a filtered result costs the agent an extra turn.
That needs `tokenmeter.py compare` over real runs, and the two are complements
rather than substitutes.

Only read-only commands are replayed. The allowlist is all read-only by
construction, and `--dry-run` lists what would run without running anything.

Reported per command and in aggregate: bytes before, bytes after, and whether
the filtered output still CONTAINS the unfiltered output's distinguishing lines.
A size win that loses content is not a win, so fidelity is reported next to it
rather than assumed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

GUARD = Path(__file__).resolve().parents[3] / "scripts" / "rtk-rewrite-guard.py"

# A replayed command that hangs would stall the whole sweep.
COMMAND_TIMEOUT_SECONDS = 60


def harvest(transcript_dir: Path, limit: int) -> list[str]:
    """Collect distinct Bash commands from transcript history, most recent first."""
    seen: dict[str, None] = {}
    files = sorted(transcript_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in files:
        try:
            handle = path.open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with handle:
            for line in handle:
                if '"tool_use"' not in line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                message = obj.get("message")
                if not isinstance(message, dict):
                    continue
                content = message.get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    if block.get("name") != "Bash":
                        continue
                    command = (block.get("input") or {}).get("command")
                    if isinstance(command, str) and command.strip():
                        seen.setdefault(command.strip(), None)
        if len(seen) >= limit:
            break
    return list(seen)[:limit]


def guard_decision(command: str, cwd: Path) -> str | None:
    """Ask the shipped guard whether it would route this command."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)})
    proc = subprocess.run(
        [sys.executable, str(GUARD)], input=payload, capture_output=True, text=True
    )
    out = proc.stdout.strip()
    if not out:
        return None
    try:
        return json.loads(out)["hookSpecificOutput"]["updatedInput"]["command"]
    except (ValueError, KeyError, TypeError):
        return None


def run(command: str, cwd: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.SubprocessError:
        return -1, ""


def fidelity(before: str, after: str) -> dict:
    """Did the filtered output keep the distinguishing content?

    Compares the SET of non-empty stripped lines. rtk reorders nothing but drops
    decoration and truncates, so a dropped line is the signal that matters. A
    truncation rtk announced (`+N more`, a tee log path) is reported separately
    from a silent one, because an announced omission the agent can act on is a
    different risk from one it cannot see.
    """
    before_lines = {line.strip() for line in before.splitlines() if line.strip()}
    after_lines = {line.strip() for line in after.splitlines() if line.strip()}
    missing = before_lines - after_lines
    announced = any(
        marker in after
        for marker in ("more in", "omitted", "tee/", "full output:", "remaining:")
    )
    return {
        "lines_before": len(before_lines),
        "lines_after": len(after_lines),
        "lines_missing": len(missing),
        "truncation_announced": announced,
        "silent_loss": bool(missing) and not announced,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True, help="working directory to replay in")
    parser.add_argument(
        "--transcripts", help="transcript dir to harvest commands from (default: --repo's own)"
    )
    parser.add_argument("--limit", type=int, default=200, help="max distinct commands to consider")
    parser.add_argument("--dry-run", action="store_true", help="list what would run, run nothing")
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args(argv)

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"not a directory: {repo}", file=sys.stderr)
        return 1

    if args.transcripts:
        transcript_dir = Path(args.transcripts).expanduser()
    else:
        slug = str(repo).replace("/", "-")
        transcript_dir = Path.home() / ".claude" / "projects" / slug
    if not transcript_dir.is_dir():
        print(f"no transcripts at {transcript_dir}", file=sys.stderr)
        return 1

    commands = harvest(transcript_dir, args.limit)
    routed = [(c, r) for c in commands if (r := guard_decision(c, repo))]

    if args.dry_run:
        print(f"{len(commands)} distinct commands, {len(routed)} would be routed:")
        for original, rewritten in routed:
            print(f"  {original}\n    -> {rewritten}")
        return 0

    results = []
    for original, rewritten in routed:
        before_code, before = run(original, repo)
        after_code, after = run(rewritten, repo)
        if before_code != 0 and after_code != 0:
            # Both failed: the command is not replayable here (wrong branch,
            # missing file). Measuring its filter delta would be noise.
            continue
        record = {
            "command": original,
            "bytes_before": len(before),
            "bytes_after": len(after),
            "saved_pct": round((1 - len(after) / len(before)) * 100, 1) if before else 0.0,
            "exit_before": before_code,
            "exit_after": after_code,
            **fidelity(before, after),
        }
        results.append(record)

    total_before = sum(r["bytes_before"] for r in results)
    total_after = sum(r["bytes_after"] for r in results)
    summary = {
        "commands_seen": len(commands),
        "commands_routed": len(routed),
        "commands_measured": len(results),
        "bytes_before": total_before,
        "bytes_after": total_after,
        "saved_pct": round((1 - total_after / total_before) * 100, 1) if total_before else 0.0,
        "est_tokens_saved": int((total_before - total_after) / 4),
        "silent_loss_count": sum(1 for r in results if r["silent_loss"]),
        "exit_code_changed": sum(1 for r in results if r["exit_before"] != r["exit_after"]),
    }

    if args.markdown:
        print(f"# rtk replay: {repo.name}\n")
        print(
            f"{summary['commands_measured']} of {summary['commands_seen']} distinct commands routed "
            f"and measured. {summary['saved_pct']}% fewer bytes "
            f"(~{summary['est_tokens_saved']} est. tokens).\n"
        )
        if summary["silent_loss_count"]:
            print(
                f"**{summary['silent_loss_count']} command(s) lost lines with no announcement.** "
                f"Those belong out of the allowlist.\n"
            )
        if summary["exit_code_changed"]:
            print(f"**{summary['exit_code_changed']} command(s) changed exit code.**\n")
        print("| Command | Before | After | Saved | Lines lost | Announced |")
        print("| --- | --- | --- | --- | --- | --- |")
        for r in sorted(results, key=lambda r: -(r["bytes_before"] - r["bytes_after"])):
            command = r["command"] if len(r["command"]) <= 48 else r["command"][:45] + "..."
            print(
                f"| `{command}` | {r['bytes_before']} | {r['bytes_after']} | {r['saved_pct']}% "
                f"| {r['lines_missing']} | {'yes' if r['truncation_announced'] else 'no'} |"
            )
    else:
        print(json.dumps({"summary": summary, "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
