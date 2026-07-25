#!/usr/bin/env python3
"""Prepare and validate product-owned Worktrunk writer leases."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


class ContractError(RuntimeError):
    pass


def run(
    argv: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise ContractError(f"{' '.join(argv)}: {detail}")
    return result


def wt_inventory(repo: Path, *, full: bool = False) -> list[dict[str, Any]]:
    command = [
        "wt",
        "-C",
        str(repo),
        "list",
        "--format=json",
        "--branches",
    ]
    if full:
        command.append("--full")
    try:
        payload = json.loads(run(command).stdout)
    except json.JSONDecodeError as error:
        raise ContractError(f"Worktrunk returned invalid JSON: {error}") from error
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ContractError("Worktrunk inventory is not a JSON array of items")
    return payload


def item_path(item: dict[str, Any]) -> Path | None:
    value = item.get("path")
    return Path(value).resolve() if value else None


def find_item(
    payload: list[dict[str, Any]],
    *,
    branch: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    resolved = path.resolve() if path else None
    matches = []
    for item in payload:
        if branch is not None and item.get("branch") != branch:
            continue
        if resolved is not None and item_path(item) != resolved:
            continue
        matches.append(item)
    if len(matches) != 1:
        anchor = f"branch={branch!r} path={str(resolved)!r}"
        raise ContractError(f"expected one Worktrunk item for {anchor}; found {len(matches)}")
    return matches[0]


def containing_item(payload: list[dict[str, Any]], path: Path) -> dict[str, Any] | None:
    resolved = path.resolve()
    matches: list[tuple[int, dict[str, Any]]] = []
    for item in payload:
        root = item_path(item)
        if root is None:
            continue
        try:
            resolved.relative_to(root)
        except ValueError:
            continue
        matches.append((len(root.parts), item))
    return max(matches, default=(0, None), key=lambda pair: pair[0])[1]


def worktrunk_vars(item: dict[str, Any]) -> dict[str, Any]:
    value = item.get("vars")
    return value if isinstance(value, dict) else {}


def bound_contexts(item: dict[str, Any]) -> set[str]:
    variables = worktrunk_vars(item)
    contexts = set()
    legacy = variables.get("context")
    if isinstance(legacy, str) and legacy:
        contexts.add(legacy)
    raw = variables.get("contexts")
    if isinstance(raw, list):
        contexts.update(value for value in raw if isinstance(value, str) and value)
    elif isinstance(raw, str) and raw:
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            decoded = []
        if isinstance(decoded, list):
            contexts.update(value for value in decoded if isinstance(value, str) and value)
    return contexts


def beads_active(repo: Path) -> bool:
    if shutil.which("bd") is None:
        return False
    result = subprocess.run(
        ["bd", "-C", str(repo), "where"],
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def beads_json(argv: list[str], repo: Path, actor: str | None = None) -> Any:
    env = os.environ.copy()
    if actor:
        env["BEADS_ACTOR"] = actor
    output = run(["bd", "-C", str(repo), *argv], env=env).stdout
    try:
        return json.loads(output)
    except json.JSONDecodeError as error:
        raise ContractError(f"Beads returned invalid JSON: {error}") from error


def one_bead(repo: Path, bead: str) -> dict[str, Any]:
    payload = beads_json(["show", bead, "--json"], repo)
    if isinstance(payload, list) and len(payload) == 1:
        return payload[0]
    if isinstance(payload, dict):
        return payload
    raise ContractError(f"expected one Bead for {bead}")


def active_bead_conflicts(repo: Path, bead: str, branch: str, path: Path) -> list[str]:
    payload = beads_json(["list", "--all", "--json"], repo)
    conflicts = []
    for issue in payload:
        if issue.get("id") == bead or issue.get("status") == "closed":
            continue
        metadata = issue.get("metadata") or {}
        other_path = metadata.get("worktree_path") or metadata.get("worktree")
        if metadata.get("branch") == branch or (
            other_path and Path(other_path).resolve() == path.resolve()
        ):
            conflicts.append(issue.get("id", "unknown"))
    return conflicts


def assert_bead_lease_available(
    repo: Path,
    bead: str,
    actor: str,
    branch: str,
    lease: str,
    inventory: list[dict[str, Any]],
    path: Path | None = None,
) -> dict[str, Any]:
    issue = one_bead(repo, bead)
    if issue.get("status") not in {"open", "in_progress"}:
        raise ContractError(
            f"Bead {bead} status is {issue.get('status')!r}; expected open or in_progress"
        )
    if issue.get("assignee") != actor:
        raise ContractError(
            f"Bead {bead} is assigned to {issue.get('assignee')!r}; expected actor {actor!r}"
        )

    metadata = issue.get("metadata") or {}
    if path is None and (
        metadata.get("lease_token") or metadata.get("worktree") or metadata.get("worktree_path")
    ):
        raise ContractError(f"Bead {bead} already has an active writer lease")
    expected = {"branch": branch, "lease_token": lease}
    if path is not None:
        expected["worktree"] = str(path.resolve())
        expected["worktree_path"] = str(path.resolve())
    for key, value in expected.items():
        existing = metadata.get(key)
        if (
            existing
            and key in {"worktree", "worktree_path"}
            and Path(str(existing)).resolve() != Path(str(value)).resolve()
        ):
            raise ContractError(f"Bead {bead} already has {key}={existing!r}; refusing {value!r}")
        if existing and key not in {"worktree", "worktree_path"} and existing != value:
            raise ContractError(f"Bead {bead} already has {key}={existing!r}; refusing {value!r}")

    for item in inventory:
        variables = worktrunk_vars(item)
        if variables.get("bead") != bead:
            continue
        if path is None:
            raise ContractError(
                f"Bead {bead} is already joined to Worktrunk branch {item.get('branch')!r}"
            )
        existing_path = item_path(item)
        if item.get("branch") != branch or (path is not None and existing_path != path.resolve()):
            raise ContractError(
                f"Bead {bead} is already joined to Worktrunk branch "
                f"{item.get('branch')!r} at {str(existing_path)!r}"
            )
        if variables.get("lease") and variables.get("lease") != lease:
            raise ContractError(f"Bead {bead} is already joined to another lease")

    if path is not None:
        conflicts = active_bead_conflicts(repo, bead, branch, path)
        if conflicts:
            raise ContractError("active Beads share this branch or path: " + ", ".join(conflicts))
    return issue


def validate(
    repo: Path,
    path: Path,
    *,
    actor: str | None = None,
    lease: str | None = None,
    bead: str | None = None,
    check_beads: bool = True,
    inventory: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = inventory or wt_inventory(repo)
    item = find_item(payload, path=path)
    branch = item.get("branch")
    if not branch:
        raise ContractError("writer worktree has no branch")
    variables = worktrunk_vars(item)
    required = {"actor": actor, "lease": lease}
    for key, expected in required.items():
        if expected is not None and variables.get(key) != expected:
            raise ContractError(
                f"Worktrunk var {key}={variables.get(key)!r}; expected {expected!r}"
            )
    if bead and variables.get("bead") not in {None, bead}:
        raise ContractError(
            f"Worktrunk var bead={variables.get('bead')!r}; expected {bead!r}"
        )
    if not variables.get("actor") or not variables.get("lease"):
        raise ContractError("writer worktree is missing actor or lease vars")

    conflicts: list[str] = []
    if check_beads and beads_active(repo) and (bead or variables.get("bead")):
        bead_id = bead or str(variables["bead"])
        issue = assert_bead_lease_available(
            repo,
            bead_id,
            str(variables["actor"]),
            branch,
            str(variables["lease"]),
            payload,
            path,
        )
        metadata = issue.get("metadata") or {}
        expected_metadata = {
            "branch": branch,
            "worktree": str(path.resolve()),
            "worktree_path": str(path.resolve()),
        }
        if variables.get("bead"):
            expected_metadata.update(
                {"actor": variables["actor"], "lease_token": variables["lease"]}
            )
        for key, expected in expected_metadata.items():
            actual = metadata.get(key)
            if key in {"worktree", "worktree_path"} and actual:
                matches = Path(str(actual)).resolve() == Path(str(expected)).resolve()
            else:
                matches = actual == expected
            if not matches:
                raise ContractError(
                    f"Bead {bead_id} metadata {key}={actual!r}; expected {expected!r}"
                )

    return {
        "status": "valid",
        "inventory_contract": "worktrunk-0.62-array",
        "branch": branch,
        "path": str(path.resolve()),
        "actor": variables["actor"],
        "lease": variables["lease"],
        "bead": bead or variables.get("bead"),
        "conflicts": conflicts,
    }


def set_var(repo: Path, branch: str, key: str, value: str | None) -> None:
    if value is None:
        return
    run(
        [
            "wt",
            "-C",
            str(repo),
            "config",
            "state",
            "vars",
            "set",
            f"{key}={value}",
            f"--branch={branch}",
        ]
    )


def copy_result(output: str) -> str:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return "done"
    numbers = [value for value in walk_values(payload) if isinstance(value, int)]
    return "done" if any(value > 0 for value in numbers) else "noop"


def walk_values(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_values(child)
    else:
        yield value


def rollback_created_worktree(
    repo: Path,
    branch: str,
    initial_inventory: list[dict[str, Any]],
    path: Path | None,
) -> str | None:
    initial_paths = {item_path(item) for item in initial_inventory if item_path(item)}
    candidates: list[Path] = []
    if path and path not in initial_paths:
        candidates.append(path)
    else:
        try:
            current = wt_inventory(repo)
        except ContractError as error:
            return f"cannot inspect Worktrunk inventory: {error}"
        for item in current:
            candidate = item_path(item)
            if (
                item.get("branch") == branch
                and candidate
                and candidate not in initial_paths
                and not item.get("is_main")
            ):
                candidates.append(candidate)
    candidates = list(dict.fromkeys(candidates))
    if not candidates:
        return None
    if len(candidates) != 1:
        return f"expected one new checkout for {branch!r}; found {len(candidates)}"
    try:
        run(
            [
                "wt",
                "-C",
                str(repo),
                "remove",
                "--foreground",
                "--force-delete",
                str(candidates[0]),
            ]
        )
    except ContractError as error:
        return str(error)
    return None


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo).resolve()
    for name in ("branch", "base", "source", "actor", "lease", "runtime", "agent"):
        if not getattr(args, name).strip():
            raise ContractError(f"--{name} must not be empty")
    if shutil.which("wt") is None:
        raise ContractError("wt is not installed")
    initial_inventory = wt_inventory(repo)
    if beads_active(repo) and args.bead:
        assert_bead_lease_available(
            repo,
            args.bead,
            args.actor,
            args.branch,
            args.lease,
            initial_inventory,
        )
    command = ["wt", "-C", str(repo)]
    if args.worktree_path:
        command.extend(["--config-set", f"worktree-path={json.dumps(args.worktree_path)}"])
    command.extend(
        [
            "switch",
            "--create",
            args.branch,
            "--base",
            args.base,
            "--no-cd",
            "--format=json",
        ]
    )
    path: Path | None = None
    try:
        try:
            switch_result = json.loads(run(command).stdout)
        except json.JSONDecodeError as error:
            raise ContractError(f"Worktrunk switch returned invalid JSON: {error}") from error
        if not isinstance(switch_result, dict):
            raise ContractError("Worktrunk switch did not return a JSON object")
        actual_branch = switch_result.get("branch")
        raw_path = switch_result.get("path")
        if actual_branch != args.branch or not isinstance(raw_path, str) or not raw_path:
            raise ContractError(
                "Worktrunk switch returned unexpected anchors: "
                f"branch={actual_branch!r} path={raw_path!r}"
            )
        path = Path(raw_path).resolve()
        created_inventory = wt_inventory(repo)
        find_item(created_inventory, branch=actual_branch, path=path)
        if not path.is_dir() or not os.access(path, os.W_OK):
            raise ContractError("created Worktrunk path is not writable")
        checked_out = run(["git", "-C", str(path), "branch", "--show-current"]).stdout.strip()
        if checked_out != actual_branch:
            raise ContractError(f"created path checks out {checked_out!r}, not {actual_branch!r}")
        base_sha = run(["git", "-C", str(path), "rev-parse", "HEAD"]).stdout.strip()
        copied = copy_result(
            run(
                [
                    "wt",
                    "-C",
                    str(repo),
                    "step",
                    "copy-ignored",
                    "--from",
                    args.source,
                    "--to",
                    actual_branch,
                    "--require-include",
                    "--format=json",
                ]
            ).stdout
        )

        if beads_active(repo) and args.bead:
            assert_bead_lease_available(
                repo,
                args.bead,
                args.actor,
                actual_branch,
                args.lease,
                created_inventory,
                path,
            )

        projected = {
            "lease": args.lease,
            "actor": args.actor,
            "runtime": args.runtime,
            "agent": args.agent,
            "bead": args.bead,
            "run": args.run,
            "node": args.node,
        }
        for key, value in projected.items():
            set_var(repo, actual_branch, key, value)

        log_root = Path(
            run(["git", "-C", str(repo), "rev-parse", "--git-common-dir"]).stdout.strip()
        )
        if not log_root.is_absolute():
            log_root = (repo / log_root).resolve()
        result = validate(repo, path, actor=args.actor, lease=args.lease, check_beads=False)
    except ContractError as error:
        rollback_error = rollback_created_worktree(repo, args.branch, initial_inventory, path)
        if rollback_error:
            raise ContractError(f"{error}; rollback failed: {rollback_error}") from error
        raise

    try:
        if beads_active(repo) and args.bead:
            assert_bead_lease_available(
                repo,
                args.bead,
                args.actor,
                actual_branch,
                args.lease,
                wt_inventory(repo),
                path,
            )
            metadata = {
                "branch": actual_branch,
                "worktree": str(path),
                "worktree_path": str(path),
                "base_sha": base_sha,
                "runtime": args.runtime,
                "agent": args.agent,
                "actor": args.actor,
                "lease_token": args.lease,
                "copy_ignored": copied,
            }
            if args.model:
                metadata["model"] = args.model
            if args.effort:
                metadata["effort"] = args.effort
            run(
                [
                    "bd",
                    "-C",
                    str(repo),
                    "update",
                    args.bead,
                    "--metadata",
                    json.dumps(metadata, separators=(",", ":")),
                ],
                env={**os.environ, "BEADS_ACTOR": args.actor},
            )
            result = validate(repo, path, actor=args.actor, lease=args.lease, bead=args.bead)
        result.update(
            {
                "status": "ready",
                "base_sha": base_sha,
                "copy_ignored": copied,
                "logs": str(log_root / "wt" / "logs"),
            }
        )
        return result
    except ContractError as error:
        rollback_error = rollback_created_worktree(repo, args.branch, initial_inventory, path)
        if rollback_error:
            raise ContractError(f"{error}; rollback failed: {rollback_error}") from error
        raise


def bind(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo).resolve()
    path = Path(args.path).resolve()
    context = args.context.strip()
    if not context:
        raise ContractError("--context must not be empty")
    inventory = wt_inventory(repo)
    result = validate(
        repo,
        path,
        actor=args.actor,
        lease=args.lease,
        bead=args.bead,
        inventory=inventory,
    )
    item = find_item(inventory, path=path)
    branch = str(item["branch"])
    variables = worktrunk_vars(item)
    for other in inventory:
        if other is item:
            continue
        if context in bound_contexts(other):
            raise ContractError(
                f"runtime context {context!r} is already bound to branch {other.get('branch')!r}"
            )
    contexts = bound_contexts(item)
    contexts.add(context)
    if not variables.get("context"):
        set_var(repo, branch, "context", context)
    set_var(repo, branch, "contexts", json.dumps(sorted(contexts), separators=(",", ":")))
    if beads_active(repo) and args.bead:
        assert_bead_lease_available(
            repo, args.bead, args.actor, branch, args.lease, inventory, path
        )
        run(
            [
                "bd",
                "-C",
                str(repo),
                "update",
                args.bead,
                "--metadata",
                json.dumps({"runtime_context": context}, separators=(",", ":")),
            ],
            env={**os.environ, "BEADS_ACTOR": args.actor},
        )
    result.update({"status": "bound", "context": context, "contexts": sorted(contexts)})
    return result


def runtime_context(payload: dict[str, Any]) -> str | None:
    for key in ("agent_id", "subagent_id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    if payload.get("agent_type") or payload.get("subagent_type"):
        value = payload.get("session_id")
        if isinstance(value, str) and value:
            return value
    return None


def mutation_targets(payload: dict[str, Any], cwd: Path) -> list[Path]:
    tool_input = payload.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    tool = payload.get("tool_name") or payload.get("tool")
    raw_targets: list[str | Path] = []
    if tool in {"apply_patch", "functions.apply_patch"}:
        command = tool_input.get("command")
        if isinstance(command, str):
            matches = re.findall(
                r"^\*\*\* (?:Update|Add|Delete) File: (.+)$|^\*\*\* Move to: (.+)$",
                command,
                re.M,
            )
            raw_targets.extend(part for pair in matches for part in pair if part)
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        raw_targets.extend(
            edit["file_path"]
            for edit in edits
            if isinstance(edit, dict)
            and isinstance(edit.get("file_path"), str)
            and edit["file_path"]
        )
    if not raw_targets:
        raw_targets.append(
            tool_input.get("workdir")
            or tool_input.get("file_path")
            or tool_input.get("path")
            or cwd
        )
    targets = []
    for raw in raw_targets:
        target = Path(str(raw).strip())
        targets.append(target if target.is_absolute() else cwd / target)
    return targets


def assert_runtime_lease(
    payload: dict[str, Any],
    inventory: list[dict[str, Any]],
    target: Path,
    *,
    expected_lease: str | None = None,
    expected_actor: str | None = None,
) -> dict[str, Any] | None:
    context = runtime_context(payload)
    bound = [
        item for item in inventory if context and context in bound_contexts(item)
    ]
    if len(bound) > 1:
        raise ContractError(f"runtime context {context!r} is bound more than once")
    if context and not bound:
        raise ContractError(f"runtime context {context!r} has no writer lease")

    item = containing_item(inventory, target)
    variables = worktrunk_vars(item) if item else {}
    if item is None or not variables.get("lease"):
        if expected_lease or bound:
            raise ContractError("writer mutation targets an unleased checkout")
        return None

    if not variables.get("actor") or not bound_contexts(item):
        raise ContractError("writer worktree is missing actor or runtime context")
    if context:
        if context not in bound_contexts(item):
            raise ContractError(f"runtime context {context!r} does not own this writer worktree")
    elif expected_lease:
        if variables["lease"] != expected_lease:
            raise ContractError("writer process lease does not match this worktree")
        if expected_actor and variables["actor"] != expected_actor:
            raise ContractError("writer process actor does not match this worktree")
    else:
        raise ContractError("leased writer mutation has no bound runtime context")
    return item


def hook_deny(error: ContractError) -> int:
    reason = f"Blocked by worktrunk-writer lease validation: {error}"
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
    return 0


def hook() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    if payload.get("hook_event_name") != "PreToolUse":
        return 0
    tool = payload.get("tool_name") or payload.get("tool")
    if tool not in {
        "Bash",
        "apply_patch",
        "functions.apply_patch",
        "Edit",
        "Write",
        "MultiEdit",
    }:
        return 0
    cwd = Path(payload.get("cwd") or os.getcwd()).resolve()
    targets = mutation_targets(payload, cwd)
    repo = cwd
    if not repo.exists() or shutil.which("wt") is None:
        return 0
    if subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode:
        return 0
    expected_lease = os.environ.get("WORKTRUNK_WRITER_LEASE")
    expected_actor = os.environ.get("WORKTRUNK_WRITER_ACTOR")
    if bool(expected_lease) != bool(expected_actor):
        return hook_deny(
            ContractError(
                "external writer context requires both WORKTRUNK_WRITER_LEASE "
                "and WORKTRUNK_WRITER_ACTOR"
            )
        )
    try:
        inventory = wt_inventory(repo)
    except ContractError as error:
        if not expected_lease and not runtime_context(payload):
            return 0
        return hook_deny(error)
    try:
        for target in targets:
            item = assert_runtime_lease(
                payload,
                inventory,
                target,
                expected_lease=expected_lease,
                expected_actor=expected_actor,
            )
            if item is None:
                continue
            variables = worktrunk_vars(item)
            validate(
                repo,
                item_path(item) or repo,
                actor=str(variables["actor"]),
                lease=str(variables["lease"]),
                bead=str(variables["bead"]) if variables.get("bead") else None,
                check_beads=False,
                inventory=inventory,
            )
        return 0
    except ContractError as error:
        return hook_deny(error)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    for name in ("repo", "branch", "base", "source", "actor", "lease", "agent"):
        prep.add_argument(f"--{name}", required=True)
    prep.add_argument("--runtime", required=True, choices=("claude", "codex"))
    for name in ("bead", "run", "node", "model", "effort"):
        prep.add_argument(f"--{name}")
    prep.add_argument(
        "--worktree-path",
        help="Run-scoped Worktrunk path template override for sandbox reachability",
    )
    check = sub.add_parser("validate")
    check.add_argument("--repo", required=True)
    check.add_argument("--path", required=True)
    check.add_argument("--actor")
    check.add_argument("--lease")
    check.add_argument("--bead")
    binding = sub.add_parser("bind")
    for name in ("repo", "path", "actor", "lease", "context"):
        binding.add_argument(f"--{name}", required=True)
    binding.add_argument("--bead")
    fleet = sub.add_parser("inventory")
    fleet.add_argument("--repo", required=True)
    fleet.add_argument("--full", action="store_true")
    sub.add_parser("hook")
    return root


def main() -> int:
    args = parser().parse_args()
    if args.command == "hook":
        return hook()
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "bind":
            result = bind(args)
        elif args.command == "validate":
            result = validate(
                Path(args.repo).resolve(),
                Path(args.path).resolve(),
                actor=args.actor,
                lease=args.lease,
                bead=args.bead,
            )
        else:
            result = wt_inventory(Path(args.repo).resolve(), full=args.full)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except ContractError as error:
        print(json.dumps({"status": "invalid", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
