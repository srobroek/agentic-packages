#!/usr/bin/env python3
"""Write an rtk config that keeps a recovery log for every filtered command.

WHAT THIS BUYS. rtk truncates. When it does, the omitted text is recoverable only
if rtk wrote a tee log, and the default `tee.mode = "failures"` writes one only
when the command FAILED. A successful `pytest` run showing 10 of 30 failures, or
a `grep` showing 25 of 400 matches, is exactly the case where the agent may need
the rest -- and exactly the case the default does not cover.

`mode = "always"` closes that gap for every filter that tees at all.

WHAT IT DOES NOT BUY, measured on 0.44.1: the `git log` filter never writes a tee
log under EITHER mode, so `git log` truncating 25 commits to 10 stays
unrecoverable. That is why `rtk-rewrite-guard.py` refuses unbounded `git log`
regardless of this setting. Do not read this script as making rtk safe; it widens
the recoverable set, and the guard still handles the rest.

CONFIG PARSING GOTCHA. rtk's TOML deserializer requires EVERY field of a section
it reads, not just the ones being overridden: a file containing only
`[tee]\\nmode = "always"` fails with `missing field 'max_files'` and rtk then
falls back to defaults, so a partial override silently does nothing. This writes
complete sections.

Idempotent, and refuses to clobber a config it did not write unless `--force` is
passed.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

MARKER = "# managed by agentic-packages token-savings"

# Complete sections, because a partial one is rejected and silently ignored.
# Values other than `tee.mode` are rtk 0.44.1's own defaults, restated so the
# file parses; `rtk config` prints them if they ever drift.
CONFIG = f"""{MARKER}
# `mode = "always"` keeps a recovery log for every filtered command, not only
# failures, so a truncated-but-successful run stays retrievable.

[tracking]
enabled = true
history_days = 90

[tee]
enabled = true
mode = "always"
max_files = 50
max_file_size = 1048576

[telemetry]
enabled = false
"""


def config_path() -> Path:
    """rtk's platform-native config location.

    macOS uses `~/Library/Application Support/rtk`, not `~/.config/rtk`. Note the
    SPACE in that path: anything parsing rtk's printed log paths must not split
    on whitespace.
    """
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "rtk" / "config.toml"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "rtk" / "config.toml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="overwrite a hand-written config")
    parser.add_argument("--print", action="store_true", dest="show", help="print the config and exit")
    parser.add_argument("--verify", action="store_true", help="report whether the setting is live")
    args = parser.parse_args(argv)

    if args.show:
        print(CONFIG, end="")
        return 0

    path = config_path()

    if args.verify:
        effective = subprocess.run(
            ["rtk", "config"], capture_output=True, text=True, check=False
        ).stdout
        live = 'mode = "always"' in effective
        print(f"config: {path}")
        print(f"exists: {path.exists()}")
        print(f"tee.mode = always in effect: {live}")
        if not live:
            print("run without --verify to write it", file=sys.stderr)
        return 0 if live else 1

    if path.exists():
        existing = path.read_text(encoding="utf-8", errors="replace")
        if MARKER not in existing and not args.force:
            print(
                f"{path} exists and was not written by this script.\n"
                "Inspect it and merge by hand, or re-run with --force.",
                file=sys.stderr,
            )
            return 1
        if existing == CONFIG:
            print(f"already current: {path}")
            return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    # Write via a temp file and rename so a concurrent rtk never reads a partial
    # config and fall back to defaults.
    temporary = path.with_suffix(".toml.part")
    temporary.write_text(CONFIG, encoding="utf-8")
    temporary.replace(path)
    print(f"wrote {path}")

    # rtk rejects an incomplete section, so prove the file parses rather than
    # leaving a config that silently does nothing.
    result = subprocess.run(["rtk", "config"], capture_output=True, text=True, check=False)
    if 'mode = "always"' not in result.stdout:
        print(
            "WARNING: rtk did not report tee.mode = always after writing.\n"
            f"rtk said:\n{result.stdout}{result.stderr}",
            file=sys.stderr,
        )
        return 1
    print("verified: rtk reports tee.mode = always")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
