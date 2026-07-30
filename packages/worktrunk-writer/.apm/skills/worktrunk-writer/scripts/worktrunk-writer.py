#!/usr/bin/env python3
"""Prepare and validate product-owned Worktrunk writer leases."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


class ContractError(RuntimeError):
    pass


CONTEXT_ACK_RE = re.compile(r"^WAIT context=(?P<context>\S+)$")
WORKTRUNK_VAR_KEY_RE = re.compile(r"^[A-Za-z0-9-]+$")
RUNTIME_BINDINGS_KEY = "runtime-bindings"
LEGACY_RUNTIME_BINDINGS_KEY = "runtime_bindings"
RESOURCE_TOKEN = r"[A-Za-z0-9][A-Za-z0-9._:-]*"
QUEUE_TOKEN = r"[A-Za-z0-9][A-Za-z0-9._:=+-]*"
GENERIC_WAIT_RE = re.compile(
    r"^WAIT checkout=(?P<checkout>/[^\n]+)\n"
    r"Do not invoke tools or start work\.\n"
    r"The controlling parent will send your task after binding your Worktrunk lease\.$"
)
RESOURCE_WAIT_RE = re.compile(
    rf"^WAIT checkout=(?P<checkout>/[^\n]+)\n"
    rf"RESOURCE {RESOURCE_TOKEN}\n"
    r"Do not invoke tools or start work\.\n"
    rf"The controlling parent will release you with exactly CLAIM {RESOURCE_TOKEN}\.$"
)
QUEUE_WAIT_RE = re.compile(
    rf"^WAIT checkout=(?P<checkout>/[^\n]+)\n"
    rf"QUEUE {QUEUE_TOKEN}\n"
    r"Do not invoke tools or start work\.\n"
    rf"The controlling parent will release you with exactly CLAIM queue:{QUEUE_TOKEN}\.$"
)
SPAWN_TOOLS = {"Agent", "spawn_agent", "agents.spawn_agent"}
CONTINUATION_TOOLS = {
    "SendMessage",
    "send_message",
    "agents.send_message",
    "followup_task",
    "agents.followup_task",
    "send_input",
    "agents.send_input",
    "multi_agent_v1send_input",
    "resume_agent",
    "agents.resume_agent",
    "multi_agent_v1resume_agent",
}
MUTATION_TOOLS = {
    "Bash",
    "apply_patch",
    "functions.apply_patch",
    "Edit",
    "Write",
    "MultiEdit",
}


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


def normalize_inventory(payload: Any) -> list[dict[str, Any]]:
    """Return a flat item list from either Worktrunk JSON schema.

    Schema 2 wraps items in an envelope and nests worktree facts; schema 1 is
    a bare array with those facts at the top level. Callers read a single
    shape, so schema-2 items are flattened onto the schema-1 field names.
    """
    if isinstance(payload, dict):
        items = payload.get("items")
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            raise ContractError("Worktrunk inventory envelope has no JSON array of items")
        flattened = []
        for item in items:
            merged = dict(item)
            worktree = item.get("worktree")
            if isinstance(worktree, dict):
                if isinstance(worktree.get("path"), str):
                    merged["path"] = worktree["path"]
                merged["is_main"] = bool(worktree.get("main"))
            flattened.append(merged)
        return flattened
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ContractError("Worktrunk inventory is not a JSON array of items")
    return payload


def wt_inventory(repo: Path, *, full: bool = False) -> list[dict[str, Any]]:
    command = [
        "wt",
        "-C",
        str(repo),
        # Pin the schema so a future Worktrunk default flip cannot change the
        # parsed shape underneath the contract.
        "--config-set",
        "list.json-schema=2",
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
    return normalize_inventory(payload)


def item_path(item: dict[str, Any]) -> Path | None:
    value = item.get("path")
    if not value:
        worktree = item.get("worktree")
        value = worktree.get("path") if isinstance(worktree, dict) else None
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
    contexts.update(binding["context"] for binding in runtime_bindings(item))
    return contexts


def runtime_bindings(item: dict[str, Any]) -> list[dict[str, str]]:
    variables = worktrunk_vars(item)
    raw = variables.get(RUNTIME_BINDINGS_KEY)
    if raw is None:
        raw = variables.get(LEGACY_RUNTIME_BINDINGS_KEY)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = []
    bindings: list[dict[str, str]] = []
    if isinstance(raw, list):
        for value in raw:
            if not isinstance(value, dict):
                continue
            handle = value.get("handle")
            context = value.get("context")
            if isinstance(handle, str) and handle and isinstance(context, str) and context:
                bindings.append({"handle": handle, "context": context})
    return bindings


def bound_handles(item: dict[str, Any]) -> set[str]:
    return {binding["handle"] for binding in runtime_bindings(item)}


def parse_context_ack(value: str) -> str:
    match = CONTEXT_ACK_RE.fullmatch(value.strip())
    if not match:
        raise ContractError("context acknowledgement must be exactly WAIT context=<runtime-id>")
    return match.group("context")


def bound_resource(item: dict[str, Any]) -> str | None:
    variables = worktrunk_vars(item)
    for key in ("resource", "bead"):
        value = variables.get(key)
        if isinstance(value, str) and value:
            return value
    return None


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


def tracks_bead(metadata: dict[str, Any], bead: str) -> bool:
    """True when `metadata` belongs to a bead that tracks `bead` rather than competing with it.

    A merge bead names the same branch as the implementer whose work it lands, and
    declares that relationship through `tracks_beads`/`closes_beads`. It holds no
    lease and no checkout, so it is not a second writer -- but a branch-keyed
    conflict scan cannot tell the two apart, and refuses the implementer its own
    lease.
    """
    for key in ("tracks_beads", "closes_beads"):
        value = metadata.get(key)
        if isinstance(value, str):
            if value == bead:
                return True
        elif isinstance(value, (list, tuple)) and bead in value:
            return True
    return False


def active_bead_conflicts(repo: Path, bead: str, branch: str, path: Path) -> list[str]:
    payload = beads_json(["list", "--all", "--json"], repo)
    conflicts = []
    for issue in payload:
        if issue.get("id") == bead or issue.get("status") == "closed":
            continue
        metadata = issue.get("metadata") or {}
        other_path = metadata.get("worktree_path") or metadata.get("worktree")
        shares_path = bool(other_path) and Path(str(other_path)).resolve() == path.resolve()
        # A tracking merge bead is exempt on branch alone; a shared checkout is
        # still a genuine conflict no matter who tracks whom.
        if shares_path or (metadata.get("branch") == branch and not tracks_bead(metadata, bead)):
            conflicts.append(issue.get("id", "unknown"))
    return conflicts


def validate_bead_worktree(metadata: dict[str, Any], expected: Path, bead: str) -> None:
    anchors = {key: metadata.get(key) for key in ("worktree", "worktree_path") if metadata.get(key)}
    if not anchors:
        raise ContractError(
            f"Bead {bead} metadata worktree is missing; expected {str(expected.resolve())!r}"
        )
    for key, value in anchors.items():
        if Path(str(value)).resolve() != expected.resolve():
            raise ContractError(
                f"Bead {bead} metadata {key}={value!r}; expected {str(expected.resolve())!r}"
            )


def validate_bead_artifacts(metadata: dict[str, Any], worktree: Path, bead: str) -> None:
    if metadata.get("execution_kind") != "artifact":
        return
    value = metadata.get("artifacts_dir")
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise ContractError(
            f"Bead {bead} requires an absolute artifacts_dir outside its disposable worktree"
        )
    artifacts = Path(value).resolve()
    try:
        artifacts.relative_to(worktree.resolve())
    except ValueError:
        return
    raise ContractError(
        f"Bead {bead} artifacts_dir must be outside its disposable worktree: {artifacts}"
    )


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
        if bound_resource(item) != bead:
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


def assert_activation_resource_available(
    repo: Path,
    resource: str,
    actor: str,
    branch: str,
    lease: str,
    inventory: list[dict[str, Any]],
    path: Path,
    *,
    handle: str,
    context: str,
) -> dict[str, Any]:
    issue = one_bead(repo, resource)
    if issue.get("status") != "open":
        raise ContractError(
            f"activation resource {resource} status is {issue.get('status')!r}; expected open"
        )
    if issue.get("assignee") not in {None, ""}:
        raise ContractError(
            f"activation resource {resource} is already claimed by "
            f"{issue.get('assignee')!r}; keep it unassigned until worker claim"
        )
    metadata = issue.get("metadata") or {}
    validate_bead_worktree(metadata, path, resource)
    validate_bead_artifacts(metadata, path, resource)
    expected = {
        "branch": branch,
        "actor": actor,
        "lease_token": lease,
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ContractError(
                f"activation resource {resource} metadata {key}={metadata.get(key)!r}; "
                f"expected {value!r}"
            )
    for key, value in (("runtime_handle", handle), ("runtime_context", context)):
        existing = metadata.get(key)
        if existing and existing != value:
            raise ContractError(
                f"activation resource {resource} metadata {key}={existing!r}; refusing {value!r}"
            )
    for item in inventory:
        joined = bound_resource(item)
        if joined != resource:
            continue
        if item.get("branch") != branch or item_path(item) != path.resolve():
            raise ContractError(
                f"activation resource {resource} is already joined to "
                f"Worktrunk branch {item.get('branch')!r}"
            )
    assert_envelope_complete(resource, metadata)
    conflicts = active_bead_conflicts(repo, resource, branch, path)
    if conflicts:
        raise ContractError("active Beads share this branch or path: " + ", ".join(conflicts))
    assert_merge_beads_owned(repo, resource, metadata)
    return issue


# Stamped before dispatch, in the order a dispatcher forgets them. `scope` and the
# execution_* fields route and bound the work; `artifacts_dir` is separately
# range-checked by validate_bead_artifacts.
REQUIRED_ENVELOPE_FIELDS = (
    "scope",
    "base_ref",
    "base_sha",
    "execution_task_kind",
    "execution_kind",
    "execution_dispatch",
    "execution_agent",
    "complexity_tier",
)


def assert_envelope_complete(resource: str, metadata: dict[str, Any]) -> None:
    """Fail at bind when the brief envelope is incomplete.

    A field missing here does not surface until the actor trips over it mid-task,
    as a denial that names a lease problem rather than the absent stamp. Bind is
    the last moment the dispatcher is still holding the resource, so it is the
    cheapest place to say which field is missing.
    """
    missing = [key for key in REQUIRED_ENVELOPE_FIELDS if not metadata.get(key)]
    if missing:
        raise ContractError(
            f"activation resource {resource} metadata is incomplete; stamp and read back "
            + ", ".join(missing)
        )


def assert_merge_beads_owned(repo: Path, resource: str, metadata: dict[str, Any]) -> None:
    """Require `integration_owner` on the merge beads this run's work depends on.

    A merge bead without it is fair game for the repository-global `pr-shepherd`,
    which drains queues across runs and cannot know a run still owns the PR. The
    result is a mid-run landing nobody sequenced. Only the run that created the
    edge can supply the owner, so the check runs while it is still dispatching.
    """
    run_id = metadata.get("run_id")
    if not run_id or not beads_active(repo):
        return
    try:
        issues = beads_json(["list", "--all", "--json"], repo)
    except ContractError:
        return
    if not isinstance(issues, list):
        return
    unowned = []
    for issue in issues:
        if not isinstance(issue, dict) or issue.get("status") == "closed":
            continue
        labels = issue.get("labels") or []
        if "agent:integrator" not in labels and "pr:merge" not in labels:
            continue
        other = issue.get("metadata") or {}
        if other.get("run_id") != run_id:
            continue
        if not other.get("integration_owner"):
            unowned.append(str(issue.get("id") or "unknown"))
    if unowned:
        raise ContractError(
            "merge beads in this run lack metadata.integration_owner, so the "
            "repository-global shepherd may drain them mid-run: " + ", ".join(sorted(unowned))
        )


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
    joined_resource = bound_resource(item)
    if bead and joined_resource not in {None, bead}:
        raise ContractError(f"Worktrunk resource={joined_resource!r}; expected {bead!r}")
    if not variables.get("actor") or not variables.get("lease"):
        raise ContractError("writer worktree is missing actor or lease vars")

    conflicts: list[str] = []
    if check_beads and beads_active(repo) and (bead or joined_resource):
        bead_id = bead or str(joined_resource)
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
        validate_bead_worktree(metadata, path, bead_id)
        validate_bead_artifacts(metadata, path, bead_id)
        expected_metadata = {
            "branch": branch,
            "actor": variables["actor"],
            "lease_token": variables["lease"],
        }
        for key, expected in expected_metadata.items():
            actual = metadata.get(key)
            if actual != expected:
                raise ContractError(
                    f"Bead {bead_id} metadata {key}={actual!r}; expected {expected!r}"
                )

    return {
        "status": "valid",
        "inventory_contract": "worktrunk-schema-2",
        "branch": branch,
        "path": str(path.resolve()),
        "actor": variables["actor"],
        "lease": variables["lease"],
        "bead": bead or joined_resource,
        "conflicts": conflicts,
    }


def set_var(repo: Path, branch: str, key: str, value: str | None) -> None:
    if value is None:
        return
    if not WORKTRUNK_VAR_KEY_RE.fullmatch(key):
        raise ContractError(
            f"invalid Worktrunk variable key {key!r}; keys use only letters, digits, and hyphens"
        )
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


def clear_var(repo: Path, branch: str, key: str) -> None:
    if not WORKTRUNK_VAR_KEY_RE.fullmatch(key):
        raise ContractError(
            f"invalid Worktrunk variable key {key!r}; keys use only letters, digits, and hyphens"
        )
    run(
        [
            "wt",
            "-C",
            str(repo),
            "config",
            "state",
            "vars",
            "clear",
            key,
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
    if getattr(args, "bead", None):
        raise ContractError(
            "prepare is parent-managed and does not accept --bead; keep the activation "
            "resource unassigned and stamp the returned anchors before spawning"
        )
    for name in ("branch", "base", "source", "actor", "lease", "runtime", "agent"):
        if not getattr(args, name).strip():
            raise ContractError(f"--{name} must not be empty")
    if shutil.which("wt") is None:
        raise ContractError("wt is not installed")
    initial_inventory = wt_inventory(repo)
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

        projected = {
            "lease": args.lease,
            "actor": args.actor,
            "runtime": args.runtime,
            "agent": args.agent,
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

    result.update(
        {
            "status": "ready",
            "base_sha": base_sha,
            "copy_ignored": copied,
            "logs": str(log_root / "wt" / "logs"),
        }
    )
    return result


def bind(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo).resolve()
    path = Path(args.path).resolve()
    if getattr(args, "bead", None):
        raise ContractError(
            "bind does not accept claimed --bead state; pass the unclaimed --resource "
            "or omit task-system integration"
        )
    if getattr(args, "context", None):
        raise ContractError(
            "bind requires --ack from the actor completion notification; "
            "a raw context or spawn handle is not handshake evidence"
        )
    ack = str(getattr(args, "ack", None) or "").strip()
    if not ack:
        raise ContractError(
            "bind requires --ack from the actor completion notification; "
            "do not infer runtime context from the spawn handle"
        )
    context = parse_context_ack(ack)
    handle = str(getattr(args, "handle", None) or "").strip()
    if not handle:
        raise ContractError("bind requires the parent-visible routing handle from the spawn result")
    resource = str(getattr(args, "resource", None) or "").strip() or None
    inventory = wt_inventory(repo)
    result = validate(
        repo,
        path,
        actor=args.actor,
        lease=args.lease,
        inventory=inventory,
    )
    item = find_item(inventory, path=path)
    branch = str(item["branch"])
    variables = worktrunk_vars(item)
    if resource:
        if not beads_active(repo):
            raise ContractError("--resource requires an active Beads workspace")
        assert_activation_resource_available(
            repo,
            resource,
            args.actor,
            branch,
            args.lease,
            inventory,
            path,
            handle=handle,
            context=context,
        )
    for other in inventory:
        if other is item:
            continue
        if context in bound_contexts(other):
            raise ContractError(
                f"runtime context {context!r} is already bound to branch {other.get('branch')!r}"
            )
        if handle in bound_handles(other):
            raise ContractError(
                f"runtime handle {handle!r} is already bound to branch {other.get('branch')!r}"
            )
    bindings = runtime_bindings(item)
    for binding in bindings:
        if binding["handle"] == handle and binding["context"] != context:
            raise ContractError(f"runtime handle {handle!r} is already bound to another context")
        if binding["context"] == context and binding["handle"] != handle:
            raise ContractError(f"runtime context {context!r} is already bound to another handle")
    if {"handle": handle, "context": context} not in bindings:
        bindings.append({"handle": handle, "context": context})
    contexts = bound_contexts(item)
    contexts.add(context)
    set_var(
        repo,
        branch,
        RUNTIME_BINDINGS_KEY,
        json.dumps(
            sorted(bindings, key=lambda value: (value["context"], value["handle"])),
            separators=(",", ":"),
            sort_keys=True,
        ),
    )
    if resource:
        set_var(repo, branch, "resource", resource)
    if not variables.get("context"):
        set_var(repo, branch, "context", context)
    set_var(repo, branch, "contexts", json.dumps(sorted(contexts), separators=(",", ":")))
    if resource:
        run(
            [
                "bd",
                "-C",
                str(repo),
                "update",
                resource,
                "--metadata",
                json.dumps(
                    {"runtime_handle": handle, "runtime_context": context},
                    separators=(",", ":"),
                ),
            ],
            env=os.environ.copy(),
        )
    result.update(
        {
            "status": "bound",
            "handle": handle,
            "context": context,
            "contexts": sorted(contexts),
            "resource": resource,
        }
    )
    return result


def release(args: argparse.Namespace) -> dict[str, Any]:
    """Clear a checkout's runtime binding, keeping the lease and the work.

    `bind` writes `context`/`contexts`/`runtime-bindings`; nothing used to unwrite
    them. When a bound agent died its binding still named a dead session, so
    `assert_bound_handle` refused every replacement and the only recovery was
    hand-editing `.git/worktrees/*/HEAD` and the Worktrunk vars. This is the
    supported path: the orchestrator releases, then binds a fresh agent to the
    same prepared checkout.

    Deliberately explicit rather than timer-driven. Liveness is not observable
    from inventory -- a slow agent and a dead one look identical -- so reaping
    stays an orchestrator decision, gated on the matching actor and lease so it
    cannot be used to take over someone else's checkout.
    """
    repo = Path(args.repo).resolve()
    path = Path(args.path).resolve()
    inventory = wt_inventory(repo)
    # validate() enforces the actor/lease match before anything is cleared.
    validate(
        repo,
        path,
        actor=args.actor,
        lease=args.lease,
        check_beads=False,
        inventory=inventory,
    )
    item = find_item(inventory, path=path)
    branch = str(item["branch"])
    variables = worktrunk_vars(item)
    released = sorted(bound_contexts(item))
    for key in ("context", "contexts", RUNTIME_BINDINGS_KEY):
        clear_var(repo, branch, key)
    if variables.get(LEGACY_RUNTIME_BINDINGS_KEY) is not None:
        clear_var(repo, branch, LEGACY_RUNTIME_BINDINGS_KEY)
    return {
        "status": "released",
        "inventory_contract": "worktrunk-schema-2",
        "path": str(path),
        "branch": branch,
        "actor": variables.get("actor"),
        "lease": variables.get("lease"),
        "released_contexts": released,
    }


def lifecycle(args: argparse.Namespace) -> int:
    """Worktrunk lifecycle hook entry point. Never blocks ordinary worktree work.

    Two invariants, because a hook that can break `wt switch` is worse than a
    missing stamp:

    * An UNLEASED checkout is none of our business -- exit 0, do nothing. The test
      is the checkout's own `actor`/`lease` vars, never "is an orchestrator
      running": the run marker is unreliable, and `pr-shepherd`, standalone
      reviewers, and humans all use leases without one.
    * Any internal error fails OPEN. Missing `wt`, unreadable inventory, or a
      malformed var must not stop a worktree from starting.

    `pre-switch` is the exception that returns non-zero: refusing a branch change
    on a leased checkout is the whole point. The stamped `branch` IS the lease
    identity -- merge beads, PRs, and `active_bead_conflicts` all key on it -- so a
    silent switch strands every anchor pointing at that checkout and locks the
    actor out of its own tools one call later.
    """
    event = args.event
    repo = Path(args.repo).resolve()
    path = Path(args.path).resolve() if args.path else Path.cwd().resolve()
    try:
        inventory = wt_inventory(repo)
        item = containing_item(inventory, path)
        variables = worktrunk_vars(item) if item else {}
        if not variables.get("lease") or not variables.get("actor"):
            return 0
        branch = str(item.get("branch") or "")
        stamped_actor = str(variables["actor"])
        stamped_lease = str(variables["lease"])

        if event == "pre-switch":
            target = str(getattr(args, "target", None) or "").strip()
            if target and branch and target != branch:
                print(
                    f"worktrunk-writer: refusing to switch {path} from its leased branch "
                    f"{branch!r} to {target!r}. That branch is the lease identity for actor "
                    f"{stamped_actor!r}; changing it strands the merge bead, PR, and lease "
                    "anchors, and the guard will deny every later tool call. Report a BOUNCE "
                    "or BLOCKED on the resource instead, or ask the orchestrator to re-prepare "
                    "a checkout on the branch you need.",
                    file=sys.stderr,
                )
                return 1
            return 0

        if event in {"pre-remove", "pre-start"}:
            contexts = sorted(bound_contexts(item))
            if not contexts:
                return 0
            if event == "pre-start" and not stale_binding(repo, item):
                return 0
            for key in ("context", "contexts", RUNTIME_BINDINGS_KEY):
                clear_var(repo, branch, key)
            reason = "worktree removal" if event == "pre-remove" else "a stale binding"
            print(
                f"worktrunk-writer: released {len(contexts)} runtime binding(s) on {branch!r} "
                f"({stamped_actor}/{stamped_lease}) for {reason}. Branch, path, actor, and "
                "lease are unchanged; bind a replacement actor to reuse this checkout.",
                file=sys.stderr,
            )
        return 0
    except (ContractError, OSError, ValueError, json.JSONDecodeError) as error:
        # Fail open: never let lease bookkeeping block a worktree operation.
        print(f"worktrunk-writer: lifecycle {event} skipped ({error})", file=sys.stderr)
        return 0


def stale_binding(repo: Path, item: dict[str, Any]) -> bool:
    """Whether a bound resource says its actor is finished with this checkout.

    Liveness is not observable, so this never guesses from a timestamp -- a slow
    agent and a dead one look identical. It asks the task system instead: a
    binding whose activation resource is closed, or is unassigned and no longer in
    progress, is provably done and safe to clear. Anything else is left alone.
    """
    resource = bound_resource(item)
    if not resource or not beads_active(repo):
        return False
    try:
        issues = beads_json(["show", str(resource), "--json"], repo)
    except ContractError:
        return False
    issue = issues[0] if isinstance(issues, list) and issues else issues
    if not isinstance(issue, dict):
        return False
    status = str(issue.get("status") or "")
    if status == "closed":
        return True
    return not issue.get("assignee") and status not in {"in_progress", "blocked"}


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


def allocation_checkout(prompt: str) -> Path | None:
    normalized = prompt.strip()
    for pattern in (GENERIC_WAIT_RE, RESOURCE_WAIT_RE, QUEUE_WAIT_RE):
        match = pattern.fullmatch(normalized)
        if match:
            return Path(match.group("checkout")).resolve()
    return None


def runtime_recipient(tool_input: dict[str, Any]) -> str:
    for key in (
        "resume",
        "resume_id",
        "to",
        "recipient",
        "target",
        "agent_id",
        "id",
        "thread_id",
    ):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def leased_items(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in inventory if worktrunk_vars(item).get("lease")]


def orchestration_active(cwd: Path) -> bool:
    if os.environ.get("ORCHESTRATE_RUN"):
        return True
    marker = os.environ.get("ORCHESTRATE_MARKER_FILE")
    path = Path(marker) if marker else cwd / ".orchestration" / ".active-run"
    if not path.is_file():
        return False
    return marker_run_live(cwd, path)


def marker_run_live(cwd: Path, marker: Path) -> bool:
    """Whether the marker names a run that is still going.

    A crashed run leaves its marker behind, and a stale marker used to hold the
    repository under the protocol indefinitely. Unreadable marker, unparseable
    run id, or an absent task system all read as live: this narrows a guard, so
    every uncertainty resolves toward keeping it on.
    """
    try:
        payload = json.loads(marker.read_text())
    except (OSError, json.JSONDecodeError):
        return True
    run_id = payload.get("run_id") if isinstance(payload, dict) else None
    if not run_id or run_id == "pending":
        return True
    if not beads_active(cwd):
        return True
    try:
        issues = beads_json(["show", str(run_id), "--json"], cwd)
    except ContractError:
        return True
    issue = issues[0] if isinstance(issues, list) and issues else issues
    if not isinstance(issue, dict):
        return True
    return issue.get("status") != "closed"


def protocol_engaged(
    payload: dict[str, Any],
    inventory: list[dict[str, Any]],
    cwd: Path,
    *,
    expected_lease: str | None = None,
) -> bool:
    """Report whether this caller is inside the writer protocol.

    The hook is repository-global, so it must stay inert for ordinary
    delegation: a repository that merely contains writer leases does not put
    every unrelated agent under the contract. Enforcement engages only on
    positive evidence -- an operator opt-in, an external writer stamp, a
    caller whose runtime context already holds a lease, a caller running
    inside a leased checkout, an allocation that speaks the WAIT grammar, or
    an active orchestration run that owns the whole handshake.
    """
    if expected_lease or os.environ.get("WORKTRUNK_WRITER_ENFORCE"):
        return True
    context = runtime_context(payload)
    if context and any(context in bound_contexts(item) for item in inventory):
        return True
    if containing_item(leased_items(inventory), cwd) is not None:
        return True
    tool_input = payload.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    prompt = str(tool_input.get("prompt") or tool_input.get("message") or "")
    if allocation_checkout(prompt) is not None:
        return True
    # An orchestration run engages the protocol only where a lease could be
    # implicated. The marker alone used to be sufficient, which turned the
    # documented advise-not-deny default into a deny for every spawn made from the
    # primary checkout during a run -- including read-only work aimed at an
    # entirely different repository. The four checks above already catch a caller
    # that holds or occupies a lease, so reaching here means this call touches
    # none: leave it to the advisory.
    return orchestration_active(cwd) and repo_has_leases(inventory)


def repo_has_leases(inventory: list[dict[str, Any]]) -> bool:
    return bool(leased_items(inventory))


def assert_bound_handle(inventory: list[dict[str, Any]], handle: str) -> dict[str, Any]:
    matches = [item for item in inventory if handle in bound_handles(item)]
    if len(matches) > 1:
        raise ContractError(f"runtime handle {handle!r} is bound more than once")
    if not matches:
        raise ContractError(
            f"runtime handle {handle!r} has no writer lease; load worktrunk-writer "
            "and complete its context handshake before resuming the agent"
        )
    return matches[0]


def resolve_checkout_repo(checkout: Path) -> Path | None:
    """Return the git root that owns `checkout`, or None if it is not one.

    Used only to pick which repo's Worktrunk inventory to query -- it does not
    itself grant anything, so it cannot be spoofed into a lease.
    """
    result = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "--show-toplevel"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if result.returncode:
        return None
    return Path(result.stdout.strip()).resolve()


def spawner_lease(
    payload: dict[str, Any], inventory: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """The leased checkout the SPAWNING context already holds, if any.

    Decided from the binding recorded in Worktrunk vars, never from
    `subagent_type` or an agent name: those are free-form strings a hook cannot
    resolve to read-or-write, and classifying by them is the defect that got the
    1.x deny gate reverted in 3bb87228.
    """
    context = runtime_context(payload)
    if not context:
        return None
    holders = [item for item in inventory if context in bound_contexts(item)]
    if len(holders) != 1:
        return None
    return holders[0] if worktrunk_vars(holders[0]).get("lease") else None


def assert_spawn_allocation(
    tool_input: dict[str, Any],
    inventory: list[dict[str, Any]],
    payload: dict[str, Any] | None = None,
    *,
    repo: Path | None = None,
) -> dict[str, Any]:
    handle = runtime_recipient(tool_input)
    if handle:
        return assert_bound_handle(inventory, handle)
    prompt = str(tool_input.get("prompt") or tool_input.get("message") or "")
    checkout = allocation_checkout(prompt)

    # A claim-holder may spawn bounded implementation children inside its own
    # checkout, sharing its actor and lease and never receiving `--bead`. Both
    # SKILL.md files promised this and the code had no branch for it, so a
    # delegation-first specialist could not delegate and did its own bulk work.
    #
    # The child is still wait-only: the parent binds its returned id to the same
    # path, actor, and lease before releasing the brief. Admitting a task-bearing
    # child here would be a false kindness -- an unbound context is refused by
    # assert_runtime_lease on its first Bash or Edit, so it would spawn and then
    # be unable to act.
    parent = spawner_lease(payload or {}, inventory)
    if parent is not None:
        parent_path = item_path(parent)
        if checkout == parent_path:
            return parent
        if checkout is None:
            raise ContractError(
                "child spawn must be wait-only: send the canonical WAIT for your own "
                f"checkout {str(parent_path)!r}, bind the returned id to your path, actor, "
                "and lease, then release the brief. A task-bearing child holds no lease "
                "and is denied on its first repository tool."
            )
        # A WAIT naming any other path is an attempt to leave the parent's lease.
        raise ContractError(
            f"child spawn must stay in its parent's leased checkout {str(parent_path)!r}; "
            f"refusing an allocation for {str(checkout)!r}. Only the orchestrator "
            "prepares a separate checkout."
        )

    if checkout is None:
        raise ContractError(
            "tool-using agent spawn is not parent-prepared; the parent must load "
            "worktrunk-writer and complete its PREPARE, WAIT, notification, and BIND "
            "sequence before task delivery; the child cannot establish its own lease"
        )
    item = containing_item(inventory, checkout)
    if (item is None or item_path(item) != checkout) and repo is not None:
        # The lease may live in a different repository than the parent's own
        # cwd -- a dep-repo-worker or external-repo-worker manages its own
        # checkout elsewhere, and an orchestrate run must be able to dispatch
        # it. Re-derive the checkout's OWN git root and check THAT repo's
        # Worktrunk inventory instead of trusting anything the caller
        # asserted: `wt -C <checkout-repo> list` is ground truth for whichever
        # repo actually owns the path, so a checkout that no `prepare` call
        # ever leased in ITS OWN repo still finds no match here -- there is no
        # claim to forge, only a real lease to look up under the right root.
        # A same-repo path is unaffected: its git root equals `repo`, so no
        # second lookup runs and the original inventory's answer stands.
        checkout_repo = resolve_checkout_repo(checkout)
        if checkout_repo is not None and checkout_repo != repo:
            try:
                item = containing_item(wt_inventory(checkout_repo), checkout)
            except ContractError:
                item = None
    variables = worktrunk_vars(item) if item else {}
    if item is None or item_path(item) != checkout or not variables.get("lease"):
        raise ContractError("agent WAIT checkout is not a prepared writer lease")
    if not variables.get("actor"):
        raise ContractError("agent WAIT checkout has no writer actor")
    return item


def leading_cd_target(command: str, cwd: Path) -> Path | None:
    first_line = next((line.strip() for line in command.splitlines() if line.strip()), "")
    if not first_line:
        return None
    lexer = shlex.shlex(first_line, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        return None
    segment: list[str] = []
    for token in tokens:
        if token in {";", "&&", "||", "&", "|"}:
            break
        segment.append(token)
    if segment[:1] != ["cd"]:
        return None
    args = segment[1:]
    if args[:1] == ["--"]:
        args = args[1:]
    if len(args) != 1 or args[0] in {"", "-"}:
        return None
    target = Path(args[0])
    return (target if target.is_absolute() else cwd / target).resolve()


def bash_redirection_targets(command: str, cwd: Path) -> list[Path]:
    base = leading_cd_target(command, cwd) or cwd
    targets: list[Path] = []
    heredoc_end = ""
    for line in command.splitlines():
        if heredoc_end:
            if line.strip() == heredoc_end:
                heredoc_end = ""
            continue
        lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|<>")
        lexer.whitespace_split = True
        lexer.commenters = ""
        try:
            tokens = list(lexer)
        except ValueError:
            continue
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token in {"<<", "<<<"}:
                if token == "<<" and index + 1 < len(tokens):
                    heredoc_end = tokens[index + 1]
                index += 2
                continue
            if ">" not in token or token.startswith("<<"):
                index += 1
                continue
            if index + 1 >= len(tokens):
                break
            raw = tokens[index + 1]
            if raw == "&" and index + 2 < len(tokens):
                index += 3
                continue
            if raw.startswith("&") or raw.isdigit():
                index += 2
                continue
            target = Path(raw)
            targets.append((target if target.is_absolute() else base / target).resolve())
            index += 2
    return targets


# Read-only argv heads, and the read-only subcommands of tools that do both.
# Deliberately an ALLOWLIST: anything unrecognised counts as mutating, so a new
# or obscure writer is governed by default rather than slipping through. The
# point of the exemption is narrow — a lease-invalid actor must keep enough tool
# surface to report a BOUNCE and release its binding, which means read-only
# inspection plus `bd`.
READ_ONLY_HEADS = frozenset(
    {
        "cat", "head", "tail", "wc", "grep", "rg", "egrep", "fgrep", "find", "ls",
        "pwd", "echo", "printf", "true", "false", "test", "stat", "file", "which",
        "command", "type", "basename", "dirname", "realpath", "readlink", "date",
        "env", "sort", "uniq", "cut", "tr", "diff", "cmp", "md5", "md5sum",
        "sha1sum", "sha256sum", "jq", "yq", "column", "less", "more", "nl", "seq",
        "bd", "gh", "wt",
    }
)
READ_ONLY_SUBCOMMANDS = {
    "git": frozenset(
        {
            "status", "log", "show", "diff", "grep", "cat-file", "rev-parse",
            "rev-list", "ls-files", "ls-tree", "describe", "blame", "shortlog",
            "merge-base", "cherry", "config", "remote", "symbolic-ref",
            "for-each-ref", "check-ignore", "merge-tree", "var", "help",
        }
    ),
}


def command_segments(command: str) -> list[list[str]] | None:
    """Split a command into argv segments. `None` when it cannot be parsed."""
    segments: list[list[str]] = []
    current: list[str] = []
    for line in command.replace("\\\n", " ").splitlines():
        lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        try:
            tokens = list(lexer)
        except ValueError:
            return None
        for token in tokens:
            if token and not set(token).difference(";&|"):
                if current:
                    segments.append(current)
                    current = []
                continue
            current.append(token)
        if current:
            segments.append(current)
            current = []
    return segments


def command_mutates(command: str) -> bool:
    """Whether a shell command may write, judged conservatively.

    Only a command whose every segment is a recognised read-only invocation is
    treated as non-mutating. An unparseable command, an unknown argv head, or any
    redirection means "assume it writes".
    """
    if not command.strip():
        return False
    if re.search(r"(?<![0-9<>])>>?", command):
        return True
    segments = command_segments(command)
    if segments is None:
        return True
    for segment in segments:
        tokens = [token for token in segment if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", token)]
        while tokens and tokens[0] in {
            "env",
            "command",
            "builtin",
            "exec",
            "time",
            "sudo",
            "nohup",
            "xargs",
        }:
            tokens = tokens[1:]
        if not tokens:
            continue
        head = os.path.basename(tokens[0])
        if head in {"cd", "export", "set", "unset", "shift", ":"}:
            continue
        if head in READ_ONLY_SUBCOMMANDS:
            args = [token for token in tokens[1:] if not token.startswith("-")]
            # A bare `git` or an unrecognised subcommand is not provably read-only.
            if not args or args[0] not in READ_ONLY_SUBCOMMANDS[head]:
                return True
            continue
        if head not in READ_ONLY_HEADS:
            return True
    return False


def mutation_targets(payload: dict[str, Any], cwd: Path) -> list[Path]:
    tool_input = payload.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    tool = payload.get("tool_name") or payload.get("tool")
    raw_targets: list[str | Path] = []
    if tool == "Bash":
        command = tool_input.get("command")
        if isinstance(command, str):
            # A leading `cd` is kept as a target even for read-only commands:
            # that is how the guard CONFINES an actor to its own checkout, which
            # is a separate job from protecting writes.
            checkout = leading_cd_target(command, cwd)
            if checkout:
                raw_targets.append(checkout)
            raw_targets.extend(bash_redirection_targets(command, cwd))
    elif tool in {"apply_patch", "functions.apply_patch"}:
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
        target = tool_input.get("workdir") or tool_input.get("file_path") or tool_input.get("path")
        raw_targets.append(target or cwd)
    targets = []
    for raw in raw_targets:
        target = Path(str(raw).strip())
        targets.append(target if target.is_absolute() else cwd / target)
    return targets


def artifact_target_allowed(repo: Path, item: dict[str, Any], target: Path) -> bool:
    resource = bound_resource(item)
    if not resource:
        return False
    issue = one_bead(repo, resource)
    variables = worktrunk_vars(item)
    metadata = issue.get("metadata") or {}
    if issue.get("status") != "in_progress" or issue.get("assignee") != variables.get("actor"):
        raise ContractError(f"artifact resource {resource} has no live claim for this actor")
    if metadata.get("execution_kind") != "artifact":
        return False
    worktree = item_path(item)
    if worktree is None:
        raise ContractError("writer worktree has no path")
    validate_bead_worktree(metadata, worktree, resource)
    validate_bead_artifacts(metadata, worktree, resource)
    expected = {
        "branch": item.get("branch"),
        "actor": variables.get("actor"),
        "lease_token": variables.get("lease"),
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ContractError(
                f"Bead {resource} metadata {key}={metadata.get(key)!r}; expected {value!r}"
            )
    runtime = metadata.get("runtime_context")
    if runtime and runtime not in bound_contexts(item):
        raise ContractError(f"artifact resource {resource} has a different runtime context")
    artifacts = Path(str(metadata["artifacts_dir"])).resolve()
    try:
        relative = target.resolve().relative_to(artifacts)
    except ValueError:
        return False
    return bool(relative.parts)


def assert_runtime_lease(
    payload: dict[str, Any],
    inventory: list[dict[str, Any]],
    target: Path,
    *,
    expected_lease: str | None = None,
    expected_actor: str | None = None,
    repo: Path | None = None,
) -> dict[str, Any] | None:
    context = runtime_context(payload)
    bound = [item for item in inventory if context and context in bound_contexts(item)]
    if len(bound) > 1:
        raise ContractError(f"runtime context {context!r} is bound more than once")
    if context and not bound:
        raise ContractError(f"runtime context {context!r} has no writer lease")

    item = containing_item(inventory, target)
    variables = worktrunk_vars(item) if item else {}
    if item is None or not variables.get("lease"):
        if bound and repo and artifact_target_allowed(repo, bound[0], target):
            return bound[0]
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


def hook_advise(message: str) -> int:
    """Allow the call, but put guidance in front of the model.

    Enforcement engages only once a caller is inside the writer protocol, so
    the parent that most needs the contract -- one that never followed the
    steering pointer -- is the one no gate reaches. An advisory restores a
    mechanical cue without denying ordinary delegation.
    """
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": message,
                }
            }
        )
    )
    return 0


SPAWN_ADVISORY = (
    "worktrunk-writer: this spawn delivers a task to an agent with no prepared "
    "Worktrunk lease, so the child shares this checkout and its work gets no "
    "lifecycle record. If it will edit the repository, load the worktrunk-writer "
    "skill and complete PREPARE -> WAIT -> BIND -> CLAIM first. A read-only or "
    "non-tool-using child needs no lease."
)


def advises_spawn(tool_input: dict[str, Any]) -> bool:
    """Report whether a spawn should carry the unleased-delegation advisory."""
    if runtime_recipient(tool_input):
        return False
    prompt = str(tool_input.get("prompt") or tool_input.get("message") or "")
    if not prompt.strip():
        return False
    return allocation_checkout(prompt) is None


def hook() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    if payload.get("hook_event_name") != "PreToolUse":
        return 0
    tool = payload.get("tool_name") or payload.get("tool")
    if tool not in SPAWN_TOOLS | CONTINUATION_TOOLS | MUTATION_TOOLS:
        return 0
    cwd = Path(payload.get("cwd") or os.getcwd()).resolve()
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
    tool_input = payload.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    if not protocol_engaged(payload, inventory, cwd, expected_lease=expected_lease):
        if tool in SPAWN_TOOLS and advises_spawn(tool_input):
            return hook_advise(SPAWN_ADVISORY)
        return 0
    try:
        if tool in SPAWN_TOOLS:
            assert_spawn_allocation(tool_input, inventory, payload, repo=repo)
            return 0
        if tool in CONTINUATION_TOOLS:
            handle = runtime_recipient(tool_input)
            if not handle:
                raise ContractError("agent continuation has no runtime handle")
            assert_bound_handle(inventory, handle)
            return 0
    except ContractError as error:
        return hook_deny(error)
    targets = mutation_targets(payload, cwd)
    try:
        for target in targets:
            item = assert_runtime_lease(
                payload,
                inventory,
                target,
                expected_lease=expected_lease,
                expected_actor=expected_actor,
                repo=repo,
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
    for name in ("run", "node", "model", "effort"):
        prep.add_argument(f"--{name}")
    prep.add_argument("--bead", help=argparse.SUPPRESS)
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
    for name in ("repo", "path", "actor", "lease"):
        binding.add_argument(f"--{name}", required=True)
    binding.add_argument("--ack")
    binding.add_argument("--handle")
    binding.add_argument("--resource")
    binding.add_argument("--context", help=argparse.SUPPRESS)
    binding.add_argument("--bead", help=argparse.SUPPRESS)
    freeing = sub.add_parser("release")
    for name in ("repo", "path", "actor", "lease"):
        freeing.add_argument(f"--{name}", required=True)
    life = sub.add_parser("lifecycle")
    life.add_argument("--event", required=True, choices=("pre-start", "pre-switch", "pre-remove"))
    life.add_argument("--repo", required=True)
    life.add_argument("--path")
    life.add_argument("--target", help="branch a pre-switch is moving to")
    fleet = sub.add_parser("inventory")
    fleet.add_argument("--repo", required=True)
    fleet.add_argument("--full", action="store_true")
    sub.add_parser("hook")
    return root


def main() -> int:
    args = parser().parse_args()
    if args.command == "hook":
        return hook()
    if args.command == "lifecycle":
        return lifecycle(args)
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "bind":
            result = bind(args)
        elif args.command == "release":
            result = release(args)
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
