#!/usr/bin/env python3
"""Guard agent-issued ``gh pr create`` commands.

Two rules with two different decisions, because they carry different cost:

* Draft-first is denied. It is unrecoverable in the sense that matters -- a
  non-draft PR has already notified reviewers and started CI by the time anyone
  notices, and `gh pr ready` cannot un-send that.
* Merge-queue bead linkage is advised, never denied, and only inside an
  orchestrate run or under an explicit PR_MERGE_QUEUE_ENFORCE opt-in. A PR body
  is editable with `gh pr edit`, and the shepherd re-checks the linkage before it
  merges anything.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from typing import Any


CONTROL = {";", "&&", "||", "|", "&", "(", ")"}
SHELLS = {"bash", "sh", "zsh", "dash", "fish", "ksh"}
WRAPPERS = {"command", "env", "exec", "nice", "nohup", "sudo", "time", "timeout"}
COMMAND_KEYWORDS = {"if", "then", "elif", "else", "while", "until", "do", "!", "{"}

WRAPPER_OPTIONS_WITH_VALUE = {
    "env": {"-u", "--unset", "-C", "--chdir", "--argv0"},
    "exec": {"-a"},
    "nice": {"-n", "--adjustment"},
    "nohup": set(),
    "sudo": {
        "-u",
        "--user",
        "-g",
        "--group",
        "-h",
        "--host",
        "-p",
        "--prompt",
        "-C",
        "--close-from",
        "-D",
        "--chdir",
        "-R",
        "--chroot",
        "-T",
        "--command-timeout",
        "-r",
        "--role",
        "-t",
        "--type",
    },
    "time": {"-f", "--format", "-o", "--output"},
    "timeout": {"-k", "--kill-after", "-s", "--signal"},
}


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def advise(context: str) -> None:
    """Allow the command but tell the model what could not be verified.

    Used where the guard cannot reach a verdict: an unparsable command, or a
    `bd` lookup that failed for reasons unrelated to the bead existing. Denying
    on an inconclusive check turns every parser gap and every slow database into
    a blocked PR, which is the opposite of what a guard is for.
    """
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "additionalContext": context,
                }
            }
        )
    )


def payload_command(payload: Any) -> tuple[str, Path]:
    if isinstance(payload, str):
        return payload, Path.cwd()
    if not isinstance(payload, dict):
        return "", Path.cwd()
    tool_input = payload.get("tool_input", "")
    if isinstance(tool_input, dict):
        command = tool_input.get("command", "")
    else:
        command = tool_input
    raw_cwd = payload.get("cwd") or os.getcwd()
    cwd = Path(raw_cwd)
    if not cwd.is_dir():
        cwd = Path.cwd()
    command = command if isinstance(command, str) else ""
    return command, effective_cwd(command, cwd)


def effective_cwd(command: str, session_cwd: Path) -> Path:
    """Resolve the directory the command actually runs in.

    The payload `cwd` is the session's directory, but a Bash call routinely starts
    with `cd <path> &&`. Resolving beads against the session directory instead of
    the command's directory made this guard deny a valid PR whose merge bead lived
    in the target repository, and no `cd` prefix could correct it.
    """
    try:
        tokens = shell_tokens(command)
    except ValueError:
        return session_cwd
    segment: list[str] = []
    for token in tokens:
        if token in {";", "&&", "||", "&", "|"}:
            break
        segment.append(token)
    if segment[:1] != ["cd"]:
        return session_cwd
    args = [token for token in segment[1:] if token != "--"]
    if len(args) != 1 or args[0] in {"", "-"}:
        return session_cwd
    target = Path(args[0]).expanduser()
    if not target.is_absolute():
        target = session_cwd / target
    try:
        resolved = target.resolve()
    except OSError:
        return session_cwd
    return resolved if resolved.is_dir() else session_cwd


def shell_tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = "#"
    normalized: list[str] = []
    for token in lexer:
        if token and all(character in ";&|()" for character in token):
            index = 0
            while index < len(token):
                pair = token[index : index + 2]
                if pair in {"&&", "||"}:
                    normalized.append(pair)
                    index += 2
                else:
                    normalized.append(token[index])
                    index += 1
        else:
            normalized.append(token)
    return normalized


def unwrap_command(tokens: list[str], index: int) -> int | None:
    """Return the executable token after command wrappers and their options."""
    while index < len(tokens):
        token = tokens[index]
        if "=" in token and not token.startswith("=") and not token.startswith("-"):
            index += 1
            continue
        wrapper = os.path.basename(token)
        if wrapper not in WRAPPERS:
            return index
        index += 1
        if wrapper == "command":
            while index < len(tokens) and tokens[index].startswith("-"):
                option = tokens[index]
                if "v" in option[1:] or "V" in option[1:]:
                    return None
                index += 1
            continue
        if (
            wrapper == "env"
            and index < len(tokens)
            and (
                tokens[index] in {"-S", "--split-string"}
                or tokens[index].startswith("-S")
                or tokens[index].startswith("--split-string=")
            )
        ):
            return index - 1
        options_with_value = WRAPPER_OPTIONS_WITH_VALUE[wrapper]
        while index < len(tokens):
            option = tokens[index]
            if option == "--":
                index += 1
                break
            if wrapper == "env" and "=" in option and not option.startswith("-"):
                index += 1
                continue
            if not option.startswith("-") or option == "-":
                break
            name = option.split("=", 1)[0]
            index += 1
            if name in options_with_value and "=" not in option:
                index += 1
        if wrapper == "timeout" and index < len(tokens):
            index += 1
        continue
    return None


def env_split_invocation(
    tokens: list[str], index: int, depth: int
) -> tuple[list[list[str]], int] | None:
    """Expand env -S/--split-string into the command it executes."""
    while index < len(tokens):
        token = tokens[index]
        if "=" in token and not token.startswith("=") and not token.startswith("-"):
            index += 1
            continue
        break
    if index >= len(tokens) or os.path.basename(tokens[index]) != "env":
        return None
    cursor = index + 1
    while cursor < len(tokens) and tokens[cursor] not in CONTROL:
        option = tokens[cursor]
        split_command: str | None = None
        if option in {"-S", "--split-string"} and cursor + 1 < len(tokens):
            split_command = tokens[cursor + 1]
            cursor += 2
        elif option.startswith("-S") and len(option) > 2:
            split_command = option[2:]
            cursor += 1
        elif option.startswith("--split-string="):
            split_command = option.split("=", 1)[1]
            cursor += 1
        if split_command is not None:
            end = cursor
            while end < len(tokens) and tokens[end] not in CONTROL:
                end += 1
            if cursor < end:
                split_command = f"{split_command} {shlex.join(tokens[cursor:end])}"
            return invocation_spans(split_command, depth + 1), end
        if option in {"-u", "--unset", "-C", "--chdir", "--argv0"}:
            cursor += 2
            continue
        if option == "--" or not option.startswith("-"):
            return None
        cursor += 1
    return None


def gh_create_arguments(tokens: list[str], index: int) -> tuple[list[str], int] | None:
    """Normalize a gh PR create invocation, including gh global repo options."""
    cursor = index + 1
    while cursor < len(tokens) and tokens[cursor] not in CONTROL:
        option = tokens[cursor]
        if option in {"-R", "--repo", "--hostname"}:
            cursor += 2
            continue
        if option.startswith("-R") and len(option) > 2:
            cursor += 1
            continue
        if option.startswith("--repo=") or option.startswith("--hostname="):
            cursor += 1
            continue
        break
    if tokens[cursor : cursor + 2] != ["pr", "create"]:
        return None
    end = cursor + 2
    while end < len(tokens) and tokens[end] not in CONTROL:
        end += 1
    return [tokens[index], "pr", "create", *tokens[cursor + 2 : end]], end


def invocation_spans(command: str, depth: int = 0) -> list[list[str]]:
    if depth > 4:
        raise ValueError("nested shell command depth exceeds policy limit")
    tokens = shell_tokens(command)
    found: list[list[str]] = []

    index = 0
    command_start = True
    while index < len(tokens):
        token = tokens[index]
        if token in CONTROL or token in COMMAND_KEYWORDS:
            command_start = True
            index += 1
            continue
        if not command_start:
            index += 1
            continue
        if split := env_split_invocation(tokens, index, depth):
            nested, end = split
            found.extend(nested)
            command_start = False
            index = end
            continue
        executable = unwrap_command(tokens, index)
        if executable is None:
            command_start = False
            index += 1
            continue
        index = executable
        if split := env_split_invocation(tokens, index, depth):
            nested, end = split
            found.extend(nested)
            command_start = False
            index = end
            continue
        basename = os.path.basename(tokens[index])
        if basename in SHELLS:
            option_index = index + 1
            while option_index < len(tokens) and tokens[option_index] not in CONTROL:
                option = tokens[option_index]
                if option.startswith("-") and "c" in option[1:]:
                    if option_index + 1 < len(tokens):
                        found.extend(
                            invocation_spans(tokens[option_index + 1], depth + 1)
                        )
                    break
                option_index += 1
            command_start = False
            index = option_index + 2
            continue
        if basename == "gh" and (parsed := gh_create_arguments(tokens, index)):
            invocation, end = parsed
            found.append(invocation)
            command_start = False
            index = end
            continue
        command_start = False
        index += 1
    return found


def argument(invocation: list[str], long: str, short: str) -> str | None:
    args = invocation[3:]
    for index, token in enumerate(args):
        if token in {long, short}:
            return args[index + 1] if index + 1 < len(args) else None
        if token.startswith(f"{long}=") or token.startswith(f"{short}="):
            return token.split("=", 1)[1]
    return None


def draft_enabled(invocation: list[str]) -> bool:
    enabled = False
    true_values = {"1", "t", "true", "yes", "y", "on"}
    for token in invocation[3:]:
        if token in {"--draft", "-d"}:
            enabled = True
        if token.startswith("--draft=") or token.startswith("-d="):
            enabled = token.split("=", 1)[1].lower() in true_values
    return enabled


def orchestration_active(cwd: Path) -> bool:
    """Whether an orchestrate run owns this session.

    The same signals `orchestrator-claim-deny.py` and
    `orchestrator-activation-guard.py` read, so the three guards cannot disagree
    about whether a run is live. The marker is resolved against the command's
    directory rather than the process cwd, because a hook fires from wherever
    the session sits while the command may run in a worktree.
    """
    if os.environ.get("ORCHESTRATE_RUN"):
        return True
    marker = os.environ.get("ORCHESTRATE_MARKER_FILE", "")
    if marker:
        return Path(marker).is_file()
    return (cwd / ".orchestration" / ".active-run").is_file()


def merge_queue_enforced(cwd: Path) -> bool:
    """Whether the merge-bead contract applies to this PR.

    The contract exists to keep the PR-shepherd merge queue discoverable, so it
    binds the runs that feed that queue -- an orchestrate run, or a caller who
    opts in with PR_MERGE_QUEUE_ENFORCE. It deliberately does not bind every
    beads repository: a repository cannot distinguish an orchestrated PR from a
    human's PR in the same repository, and treating the repository as the
    trigger demanded merge beads from three unrelated projects in one session.

    Unlike the worktrunk writer's equivalent gate, the run marker alone is
    enough here: this hook fires only on `gh pr create`, and every PR opened
    during a run is a PR that run's shepherd must land. `beads_workspace` stays
    as the second condition because a run's marker lives in the primary
    checkout while the command may target a different repository entirely, and
    a repository with no bead store can hold no merge bead.
    """
    if os.environ.get("PR_MERGE_QUEUE_ENFORCE"):
        return beads_workspace(cwd)
    return orchestration_active(cwd) and beads_workspace(cwd)


def beads_workspace(cwd: Path) -> bool:
    """Report whether beads is actually initialised for this directory.

    Ask `bd` rather than walking for a `.beads` directory. A workspace in a shared
    ancestor -- `~/.beads` is common -- made every repository under the home
    directory look beads-enabled, so this guard demanded bead trailers from
    projects that track no beads at all. `bd where` resolves the same workspace the
    later lookups will use, so the gate and the lookups cannot disagree.
    """
    if not shutil.which("bd"):
        return False
    try:
        result = subprocess.run(
            ["bd", "-C", str(cwd), "where"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        # An unreachable `bd` is not evidence of a beads workspace, so the bead
        # trailer requirements below are skipped rather than demanded blindly.
        return False
    return result.returncode == 0


def trailer_ids(body: str, name: str) -> list[str]:
    prefix = f"{name}:"
    ids: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith(prefix):
            continue
        value = stripped[len(prefix) :].strip()
        if value and all(
            character.isalnum() or character in "._-" for character in value
        ):
            ids.append(value)
    return ids


MISS_MESSAGE = re.compile(
    r"no issue(s)? found|not found|no such|does not exist|unknown (bead|issue)", re.I
)


class BeadUnavailable(Exception):
    """`bd` could not answer, so absence of a record proves nothing.

    Raised instead of returning None when the lookup itself failed: binary
    missing, timeout, crash, or unparsable output. The caller turns this into an
    advisory rather than a denial, because a slow or unhealthy database must not
    read as "that bead does not exist".
    """


def bead_record(cwd: Path, bead_id: str) -> dict[str, Any] | None:
    """Return the bead record, None when the bead genuinely does not exist.

    Raises BeadUnavailable when the lookup could not be completed. The timeout is
    generous because `bd` is Dolt-backed: a healthy call still takes about a
    second, and system load pushes it well past that. One retry absorbs a
    transient stall.
    """
    if not shutil.which("bd"):
        raise BeadUnavailable("bd is not installed")
    last_error = "unknown error"
    for attempt in range(2):
        try:
            result = subprocess.run(
                ["bd", "-C", str(cwd), "show", bead_id, "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                check=False,
            )
        except subprocess.TimeoutExpired:
            last_error = "bd show timed out"
            continue
        except OSError as error:
            raise BeadUnavailable(f"could not run bd: {error}") from error

        stdout = result.stdout.decode("utf-8", "replace").strip()
        stderr = result.stderr.decode("utf-8", "replace").strip()
        if result.returncode != 0:
            # An explicit "no such bead" is a genuine miss. Anything else --
            # schema skew, a locked database, a crash -- is an unavailable
            # lookup, and must not read as "that bead does not exist". A bare
            # non-zero exit with no message is treated as a miss, because that is
            # how the simplest callers report one.
            if not stderr or MISS_MESSAGE.search(stderr):
                return None
            last_error = stderr.splitlines()[0]
            continue

        if not stdout:
            return None
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            last_error = "bd returned unparsable JSON"
            continue
        # bd reports an unknown id as {"error": ...} on stdout with exit 0.
        if isinstance(payload, dict) and payload.get("error"):
            # An error object on a zero exit is how bd reports an unknown id.
            return None
        if isinstance(payload, list):
            return payload[0] if payload and isinstance(payload[0], dict) else None
        if isinstance(payload, dict):
            return payload
        return None
    raise BeadUnavailable(last_error)


def validate(invocation: list[str], cwd: Path) -> str | None:
    """Return a denial reason, or None when the invocation may proceed."""
    if not draft_enabled(invocation):
        return (
            "Agent-authored PRs must start as drafts. Re-run every gh pr create "
            "invocation with --draft; use gh pr ready only after implementation, "
            "local validation, and required review are complete."
        )
    return None


def merge_queue_findings(invocation: list[str], cwd: Path) -> list[str]:
    """Report every merge-queue trailer defect in an inline PR body.

    Advisory rather than denial: a PR body is editable with `gh pr edit`, so no
    defect here is catastrophic or unrecoverable, and the shepherd's own queue
    pass rejects a body/DAG mismatch anyway
    (packages/pr-shepherd/.apm/skills/pr-shepherd/SKILL.md:23). Denying instead
    blocked ordinary bounded work until a shepherd landed an unrelated PR.

    Only an inline `--body` is inspected. `--body-file` is deliberately not read:
    the hook runs before the command, so a file the same command is about to
    write does not exist yet, and an absent file is indistinguishable from a
    not-yet-written one. Every failed rule is reported together, because
    stopping at the first one hid the more fixable ones behind it.
    """
    body = argument(invocation, "--body", "-b")
    if not body:
        return []
    tracks = trailer_ids(body, "Tracks-Bead")
    closes = trailer_ids(body, "Closes-Bead")
    merges = trailer_ids(body, "Merge-Bead")
    if not (tracks or closes or merges):
        return [
            "PR body carries no bead trailers. A PR opened during an orchestrate "
            "run needs exactly one Merge-Bead: <id> line so the shepherd can "
            "cross-check its merge bead."
        ]
    findings: list[str] = []
    if not tracks:
        findings.append("PR body must include at least one exact Tracks-Bead: <id> line.")
    if len(merges) != 1:
        findings.append("PR body must include exactly one Merge-Bead: <id> line.")
        return findings
    merge_id = merges[0]
    merge_record = bead_record(cwd, merge_id)
    if merge_record is None:
        findings.append(
            f"Merge-Bead '{merge_id}' is not resolvable from this repository."
        )
        return findings
    labels = set(merge_record.get("labels", []))
    if merge_record.get("status") != "open" or not {
        "pr:merge",
        "agent:integrator",
    }.issubset(labels):
        findings.append(
            f"Merge-Bead '{merge_id}' must be open and labeled pr:merge "
            "and agent:integrator."
        )
    if merge_record.get("assignee"):
        findings.append(
            f"Merge-Bead '{merge_id}' must be unassigned for PR Shepherd discovery."
        )
    metadata = merge_record.get("metadata")
    if not isinstance(metadata, dict) or any(
        not metadata.get(name) for name in ("branch", "repo", "origin_actor")
    ):
        findings.append(
            f"Merge-Bead '{merge_id}' must have branch, repo, and origin_actor "
            "metadata before PR creation."
        )
    for bead_id in tracks:
        if bead_record(cwd, bead_id) is None:
            findings.append(
                f"Tracks-Bead '{bead_id}' is not resolvable from this repository."
            )
    for bead_id in closes:
        if bead_id not in tracks:
            findings.append(f"Closes-Bead '{bead_id}' must also appear as Tracks-Bead.")
        work_record = bead_record(cwd, bead_id)
        if work_record is None:
            findings.append(
                f"Closes-Bead '{bead_id}' is not resolvable from this repository."
            )
            continue
        if work_record.get("status") == "closed":
            findings.append(
                f"Closes-Bead '{bead_id}' is already closed; a late closing edge "
                "cannot be honoured."
            )
        dependencies = work_record.get("dependencies", [])
        edge_exists = any(
            dependency.get("id") == merge_id
            and dependency.get("dependency_type") == "blocks"
            for dependency in dependencies
            if isinstance(dependency, dict)
        )
        if not edge_exists:
            findings.append(
                f"Closes-Bead '{bead_id}' should depend on Merge-Bead "
                f"'{merge_id}' before review freezes the graph "
                f"(bd dep add {bead_id} {merge_id})."
            )
    return findings


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = raw
    command, cwd = payload_command(payload)
    if not command:
        return 0
    # Cheap bail before tokenizing. This hook is registered on every Bash call,
    # and the shell wrapper that used to do this filtering is gone. A strict
    # superset of the real trigger, so it cannot hide a command the parser would
    # have flagged.
    if not all(word in command for word in ("gh", "pr", "create")):
        return 0
    try:
        invocations = invocation_spans(command)
    except ValueError as error:
        # Allow, do not deny. PR bodies carry markdown: apostrophes, backticks,
        # and nested quotes all make the tokenizer give up, and a command this
        # guard cannot read is not evidence of a policy breach.
        advise(
            f"PR policy not verified: this command could not be parsed ({error}). "
            "Ensure the invocation uses --draft, and during an orchestrate run "
            "that the body carries its Merge-Bead trailer."
        )
        return 0
    for invocation in invocations:
        if reason := validate(invocation, cwd):
            deny(reason)
            return 0
    if not merge_queue_enforced(cwd):
        return 0
    findings: list[str] = []
    for invocation in invocations:
        try:
            findings.extend(merge_queue_findings(invocation, cwd))
        except BeadUnavailable as error:
            advise(
                f"Merge-queue linkage not verified: a bead lookup could not complete "
                f"({error}). The trailer requirements still apply; re-check the bead "
                "state if the PR is rejected downstream."
            )
            return 0
    if findings:
        advise(
            "Merge-queue linkage is incomplete; fix it with gh pr edit and bd before "
            "requesting review:\n- " + "\n- ".join(findings)
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open, per the hook contract: an unexpected exception allows rather
        # than blocking. Without this, a payload whose `cwd` was not a string raised
        # TypeError and exited 1 instead of exiting 0 quietly.
        raise SystemExit(0)
