#!/usr/bin/env python3
"""Post a macOS notification when the terminal running Claude is not in front.

No-op off Darwin. Suppressed when the frontmost application is the one running this
session, so working in the terminal does not generate notifications about itself.

Ported from shell, where three `jq` spawns read three fields and the notifier
arguments were assembled as a bash array. The message was passed through
`terminal-notifier` unquoted in the group name only, but the real gain here is
dropping three subprocesses from a hook that fires on every notification.
"""

from __future__ import annotations

import sys

# TERM_PROGRAM to bundle identifier. Used only when __CFBundleIdentifier is absent,
# which is the case when Claude runs from a shell not launched by a GUI app.
BUNDLE_IDS = {
    "zed": "dev.zed.Zed",
    "ghostty": "com.mitchellh.ghostty",
    "WezTerm": "com.github.wez.wezterm",
    "iTerm.app": "com.googlecode.iterm2",
    "Apple_Terminal": "com.apple.Terminal",
    "vscode": "com.microsoft.VSCode",
}

FRONTMOST_SCRIPT = (
    'tell application "System Events" to get bundle identifier of '
    "first process whose frontmost is true"
)


def frontmost() -> str:
    """Bundle identifier of the frontmost application, or empty when unknown."""
    import subprocess

    try:
        result = subprocess.run(
            ["osascript", "-e", FRONTMOST_SCRIPT],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def main() -> int:
    import platform

    if platform.system() != "Darwin":
        return 0

    payload = sys.stdin.read()

    import json
    import os

    message = ""
    title = ""
    if payload:
        try:
            data = json.loads(payload)
        except (ValueError, TypeError):
            data = None
        if isinstance(data, dict):
            message = data.get("message") or ""
            title = data.get("title") or ""

    if not message:
        message = os.environ.get("CLAUDE_NOTIFICATION_TITLE") or "Needs attention"

    cf_bundle = os.environ.get("__CFBundleIdentifier", "")
    term_program = os.environ.get("TERM_PROGRAM", "")
    bundle_id = cf_bundle or BUNDLE_IDS.get(term_program, "")

    # Suppress only for the exact application running this session, not for every
    # terminal: a notification is useful when Claude runs in a window behind another.
    if bundle_id and frontmost() == bundle_id:
        return 0

    app_name = term_program or "Terminal"
    if "-Preview" in cf_bundle:
        app_name = f"{app_name} Preview"

    subtitle = f"{app_name} - {title}" if title else app_name

    import shutil
    import subprocess
    import time

    if shutil.which("terminal-notifier") is None:
        return 0

    arguments = [
        "terminal-notifier",
        "-title",
        "Claude Code",
        "-subtitle",
        subtitle,
        "-message",
        message,
        "-sound",
        "default",
        # A unique group keeps notifications from replacing one another.
        "-group",
        f"claude-code-{time.time_ns()}",
    ]
    if bundle_id:
        arguments += ["-activate", bundle_id]

    try:
        subprocess.run(
            arguments,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
