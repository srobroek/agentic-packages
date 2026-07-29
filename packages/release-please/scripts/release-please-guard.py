#!/usr/bin/env python3
"""Warn -- never block -- on manual release-please operations, and report config.

Two entry points in one process:

- no arguments: a PreToolUse:Bash hook reading a payload on stdin. On a repo
  managed by release-please, manually cutting a release, tagging a version,
  pushing tags, or hand-merging a release branch to a protected branch is the way
  to botch the release loop indefinitely: release-please then sees an
  untagged or mislabeled release and stops auto-tagging. The hook does not
  block -- it injects an advisory (`additionalContext`) so the model reconsiders
  and reads the release-please skill. The command still runs.
- ``detect [--json] [DIR]``: prints how the repo is configured and exits 0 when
  release-please manages it, 1 when it does not, 2 on a usage error. The skill's
  step-0 gate reads these facts.

The detector was a second script that parsed its own JSON with `grep -E` and
emitted more by string interpolation. It is folded in here rather than shipped
alongside, because the hook already ran it as a subprocess and read only its
exit code -- one process now answers both questions, and `json` replaces the
pattern matching.

Never emits `permissionDecision: "deny"` or `"ask"`: per the repo hook policy,
blocking decisions stall autonomous runs, and these operations are legitimate in
recovery scenarios. The note is the whole point.

The guard regexes are the load-bearing part and stay as close to the original
ERE as re.IGNORECASE and word-boundary substitutes allow, so behavior matches
the existing bats oracle.
"""

from __future__ import annotations

import sys

# Only `sys` at module scope. The hook path is a PreToolUse:Bash handler, so it
# runs on every shell command; everything else is imported inside the functions
# that need it.

CONFIG_NAMES = ("release-please-config.json", ".release-please-config.json")
MANIFEST_NAME = ".release-please-manifest.json"
WORKFLOW_MARKERS = ("release-please-action", "googleapis/release-please")


def extract(payload: str) -> tuple[str, str]:
    """Return (command, cwd). `tool_input` may be an object or a bare string."""
    import json

    data = json.loads(payload)
    if not isinstance(data, dict):
        return "", ""
    tool_input = data.get("tool_input")
    if isinstance(tool_input, str):
        command = tool_input
    elif isinstance(tool_input, dict):
        raw = tool_input.get("command")
        command = raw if isinstance(raw, str) else ""
    else:
        command = ""
    cwd = data.get("cwd")
    return command, cwd if isinstance(cwd, str) else ""


def detect(directory: str) -> dict:
    """How release-please is configured at `directory`.

    Reports `present`, `mode`, the config and manifest paths, the workflows that
    invoke the action, three load-bearing config values, and `package_count`.
    Every value is read with `json` rather than matched with a pattern, which is
    what the shell predecessor got wrong in two places -- see `_top_level_flag`
    and `package_count` below.
    """
    import os

    config_file = ""
    for name in CONFIG_NAMES:
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate):
            config_file = candidate
            break

    manifest_path = os.path.join(directory, MANIFEST_NAME)
    manifest_file = manifest_path if os.path.isfile(manifest_path) else ""

    workflow_files = _workflow_files(directory)

    if config_file and manifest_file:
        present, mode = True, "manifest"
    elif config_file:
        present, mode = True, "config-only"
    elif workflow_files:
        # No config file, but the action is wired into a workflow: release-please
        # can run purely from action inputs.
        present, mode = True, "inline-action"
    else:
        present, mode = False, "none"

    config = _load_json(config_file) if config_file else None
    manifest = _load_json(manifest_file) if manifest_file else None

    return {
        "present": present,
        "mode": mode,
        "config_file": config_file,
        "manifest_file": manifest_file,
        "workflow_files": ",".join(workflow_files),
        "separate_pull_requests": _top_level_flag(config, "separate-pull-requests"),
        "include_component_in_tag": _top_level_flag(config, "include-component-in-tag"),
        "tag_separator": _top_level_string(config, "tag-separator"),
        # DEFECT (shell): `grep -Ec '"[^"]+"[[:space:]]*:'` counted LINES that
        # hold at least one key, so a minified three-package manifest reported 1.
        "package_count": len(manifest) if isinstance(manifest, dict) else 0,
    }


def _load_json(path: str) -> object | None:
    """Parsed JSON, or None when the file is missing or malformed (fail open)."""
    import json

    try:
        # utf-8-sig, because `json` rejects a UTF-8 BOM outright: a config written
        # by a Windows editor parsed as nothing, and a three-package manifest then
        # reported package_count=0 rather than 3.
        with open(path, encoding="utf-8-sig", errors="replace") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _top_level_flag(config: object, key: str) -> str:
    """A top-level boolean as "true"/"false", or "unknown" when unset.

    DEFECT (shell): the pattern matched ANYWHERE in the file, so a per-package
    override reported itself as the top-level value. Reading the top-level key
    means a `packages` entry cannot answer for the repo.
    """
    if not isinstance(config, dict):
        return "unknown"
    value = config.get(key)
    if isinstance(value, bool):
        return "true" if value else "false"
    return "unknown"


def _top_level_string(config: object, key: str) -> str:
    if not isinstance(config, dict):
        return "unknown"
    value = config.get(key)
    return value if isinstance(value, str) and value else "unknown"


def _workflow_files(directory: str) -> list[str]:
    """Workflow paths, relative to `directory`, that reference the action."""
    import os

    workflows = os.path.join(directory, ".github", "workflows")
    if not os.path.isdir(workflows):
        return []
    found: list[str] = []
    for root, _dirs, names in os.walk(workflows):
        for name in sorted(names):
            path = os.path.join(root, name)
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    body = handle.read()
            except OSError:
                continue
            if any(marker in body for marker in WORKFLOW_MARKERS):
                found.append(os.path.relpath(path, directory))
    return sorted(found)


def is_release_please_repo(cwd: str) -> bool:
    """Whether release-please manages the repo at `cwd`."""
    return detect(cwd)["present"]


def violation(command: str, cwd: str) -> str | None:
    """Return the advisory text for `command`, or None to allow silently."""
    import re

    lowered = command.lower()

    # --- 1. Manual GitHub Release creation ----------------------------------
    if re.search(r"(^|\s)gh\s+release\s+create(\s|$)", lowered):
        return (
            "RELEASE-PLEASE REPO: this repo is managed by release-please, which "
            "creates GitHub Releases automatically when the release PR merges. "
            "Running 'gh release create' manually cuts a release release-please "
            "did not author -- it will not flip the autorelease:pending label to "
            "autorelease:tagged, which can stall auto-tagging on every future "
            "release. Prefer merging the release PR. Only cut a manual release as "
            "a deliberate, documented fallback. See the release-please skill "
            "(references/pitfalls-recovery.md)."
        )

    # --- 2. Manual version tag creation -------------------------------------
    if re.search(
        r"(^|\s)git(\s+-\S+(\s+\S+)?)*\s+tag(\s+-[a-z]+)*\s+v?\d+\.\d+\.\d+",
        lowered,
    ):
        return (
            "RELEASE-PLEASE REPO: release-please owns version tags and cuts them "
            "automatically when the release PR merges. Creating a version tag by "
            "hand can collide with the tag release-please will create "
            "(duplicate-tag failure) or desync the manifest from the tags. Let the "
            "release PR do it. See the release-please skill."
        )

    # Also catch pushing tags explicitly.
    if re.search(
        r"(^|\s)git(\s+-\S+)*\s+push(\s+\S+)*\s+(--tags|--follow-tags)(\s|$)",
        lowered,
    ):
        return (
            "RELEASE-PLEASE REPO: pushing tags manually (git push "
            "--tags/--follow-tags) can publish a version tag that collides with "
            "the one release-please cuts on release-PR merge. release-please "
            "pushes its own tags. See the release-please skill."
        )

    # --- 3. Manual merge to a protected branch (bypassing the release PR) ---
    git_prefix = r"git(\s+-\S+(\s+\S+)?)*\s+"
    if re.search(git_prefix + r"merge(\s|$)", lowered):
        if not re.search(r"(^|\s)--(abort|continue|quit)(\s|=|$)", lowered):
            cur_branch = _current_branch(cwd)
            if cur_branch in ("main", "master"):
                return (
                    f"RELEASE-PLEASE REPO + PROTECTED BRANCH: you are on "
                    f"'{cur_branch}'. Releases must flow through release-please's "
                    "release PR (merge it via the PR, which triggers the tag + "
                    "GitHub Release). Do NOT hand-merge a release branch "
                    f"(release-please--branches--*) into '{cur_branch}' -- that "
                    "bypasses the tagging step and can leave an untagged, merged "
                    "release PR that stalls the loop. Ordinary feature merges are "
                    "fine; releases are not. See the release-please skill."
                )
    return None


def _current_branch(cwd: str) -> str:
    import subprocess

    try:
        completed = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
            text=True,
        )
    except (subprocess.SubprocessError, OSError):
        return ""
    return completed.stdout.strip()


FIELD_ORDER = (
    "present",
    "mode",
    "config_file",
    "manifest_file",
    "workflow_files",
    "separate_pull_requests",
    "include_component_in_tag",
    "tag_separator",
    "package_count",
)


def detect_cli(argv: list[str]) -> int:
    """`detect [--json] [DIR]`: 0 when managed, 1 when not, 2 on a usage error."""
    import json
    import os
    import subprocess

    as_json = False
    directory = ""
    for arg in argv:
        if arg == "--json":
            as_json = True
        elif arg in ("--help", "-h"):
            print(__doc__.strip())
            return 0
        elif arg.startswith("-"):
            print(f"detect: unknown option: {arg}", file=sys.stderr)
            return 2
        elif directory:
            print("detect: too many arguments", file=sys.stderr)
            return 2
        else:
            directory = arg

    if not directory:
        # Prefer git's toplevel so the gate works from any subdirectory.
        try:
            completed = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
                text=True,
            )
            directory = completed.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            directory = ""
        directory = directory or os.getcwd()

    if not os.path.isdir(directory):
        print(f"detect: not a directory: {directory}", file=sys.stderr)
        return 2

    facts = detect(directory)
    if as_json:
        print(json.dumps({key: facts[key] for key in FIELD_ORDER}))
    else:
        for key in FIELD_ORDER:
            value = facts[key]
            if isinstance(value, bool):
                value = "true" if value else "false"
            print(f"{key}={value}")
    return 0 if facts["present"] else 1


def main() -> int:
    if len(sys.argv) > 1:
        if sys.argv[1] != "detect":
            print(f"release-please-guard: unknown command: {sys.argv[1]}", file=sys.stderr)
            return 2
        return detect_cli(sys.argv[2:])

    payload = sys.stdin.read()
    if not payload:
        return 0
    # Cheap bail on the raw bytes: every rule below fires on a `git` or `gh`
    # invocation. A strict superset of the real trigger, so it cannot hide one the
    # regex checks would have caught.
    if "git" not in payload and "gh" not in payload:
        return 0

    try:
        command, cwd = extract(payload)
    except (ValueError, TypeError):
        return 0
    if not command:
        return 0

    import os

    if not cwd or not os.path.isdir(cwd):
        cwd = os.getcwd()

    if not is_release_please_repo(cwd):
        return 0

    context = violation(command, cwd)
    if context is None:
        return 0

    import json

    json.dump(
        {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": context}},
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open: an advisory-only guard must never turn an unexpected
        # exception into a stalled command.
        raise SystemExit(0)
