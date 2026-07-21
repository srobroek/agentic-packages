#!/usr/bin/env python3
"""Resolve one release-queue-watch JSON record to an approved orchestrate node.

The script is read-only. It validates the watcher contract, matches an exact
repository/PR/head tuple in a supplied `bd list --json` snapshot, and emits one
normalized JSON result for the orchestrator.

Exit codes: 0 resolved/replay/duplicate/control record, 1 invalid input, 2 no
unique approved node.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPOSITORY_RE = re.compile(r"^[^/\s]+/[^/\s]+$")
HEAD_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
REQUIRED_PULL_REQUEST_FIELDS = {
    "repository",
    "number",
    "title",
    "headSha",
    "baseRef",
    "labels",
    "priority",
    "draft",
    "mergeable",
    "checks",
    "createdAt",
    "updatedAt",
    "state",
    "activeSince",
}


class ContractError(ValueError):
    """Raised when a watcher record violates the handoff contract."""


class ResolutionError(ValueError):
    """Raised when a valid dispatch does not map to one approved node."""


def _unwrap(value: Any) -> Any:
    if isinstance(value, dict) and "data" in value and "schema_version" in value:
        return value["data"]
    return value


def _read_json(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot read JSON from {path}: {error}") from error


def validate_record(record: Any) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        raise ContractError("watcher record must be a JSON object")
    record_type = record.get("type")
    if record_type != "dispatch":
        return None
    pull_request = record.get("pullRequest")
    if not isinstance(pull_request, dict):
        raise ContractError("dispatch.pullRequest must be a JSON object")
    missing = sorted(REQUIRED_PULL_REQUEST_FIELDS - pull_request.keys())
    if missing:
        raise ContractError(
            f"dispatch.pullRequest missing fields: {', '.join(missing)}"
        )

    repository = pull_request["repository"]
    number = pull_request["number"]
    head_sha = pull_request["headSha"]
    priority = pull_request["priority"]
    labels = pull_request["labels"]
    if not isinstance(repository, str) or not REPOSITORY_RE.fullmatch(repository):
        raise ContractError("repository must be OWNER/REPO")
    if type(number) is not int or number < 1:
        raise ContractError("number must be a positive integer")
    if not isinstance(head_sha, str) or not HEAD_SHA_RE.fullmatch(head_sha):
        raise ContractError("headSha must be a hexadecimal Git object id")
    if type(priority) is not int or not 0 <= priority <= 4:
        raise ContractError("priority must be an integer from 0 through 4")
    if not isinstance(labels, list) or not all(
        isinstance(label, str) for label in labels
    ):
        raise ContractError("labels must be an array of strings")
    for field in ("title", "baseRef", "createdAt", "updatedAt", "activeSince"):
        if not isinstance(pull_request[field], str) or not pull_request[field]:
            raise ContractError(f"{field} must be a non-empty string")
    if pull_request["draft"] is not False:
        raise ContractError("dispatch must describe a non-draft pull request")
    if pull_request["mergeable"] is not True:
        raise ContractError("dispatch must describe a mergeable pull request")
    if pull_request["checks"] != "pass":
        raise ContractError("dispatch checks must be pass")
    if pull_request["state"] != "active":
        raise ContractError("dispatch state must be active")
    return pull_request


def _labels(node: dict[str, Any]) -> set[str]:
    labels = node.get("labels", [])
    return {label for label in labels if isinstance(label, str)}


def _delivery_state(metadata: dict[str, Any], dispatch_key: str) -> str:
    if metadata.get("queue_dispatch_ack") == dispatch_key:
        return "ack"
    if metadata.get("queue_dispatch_sent") == dispatch_key:
        return "sent"
    if metadata.get("queue_dispatch_pending") == dispatch_key:
        return "pending"
    return "untracked"


def _handoff_result(
    node: dict[str, Any],
    metadata: dict[str, Any],
    repository: str,
    number: int,
    head_sha: str,
    dispatch_key: str,
    status: str,
    priority: int | None = None,
) -> dict[str, Any]:
    if not isinstance(node.get("id"), str) or not node["id"]:
        raise ResolutionError("approved node is missing its id")
    for field in ("branch", "base_sha"):
        if not isinstance(metadata.get(field), str) or not metadata[field]:
            raise ResolutionError(f"approved node is missing metadata.{field}")
    result = {
        "status": status,
        "deliveryState": _delivery_state(metadata, dispatch_key),
        "node": node["id"],
        "dispatchKey": dispatch_key,
        "repository": repository,
        "number": number,
        "headSha": head_sha,
        "branch": metadata["branch"],
        "baseSha": metadata["base_sha"],
    }
    if priority is not None:
        result["priority"] = priority
    return result


def resolve(record: Any, nodes_value: Any) -> dict[str, Any]:
    pull_request = validate_record(record)
    if pull_request is None:
        return {
            "status": "ignored",
            "recordType": record.get("type") if isinstance(record, dict) else None,
        }

    nodes = _unwrap(nodes_value)
    if not isinstance(nodes, list):
        raise ContractError("nodes snapshot must be a JSON array")
    repository = pull_request["repository"]
    number = pull_request["number"]
    head_sha = pull_request["headSha"]
    candidates: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict) or node.get("status") != "in_progress":
            continue
        if "state:approved" not in _labels(node):
            continue
        metadata = node.get("metadata")
        if not isinstance(metadata, dict):
            continue
        try:
            node_pr = int(metadata.get("pr"))
        except (TypeError, ValueError):
            continue
        if (
            metadata.get("repo") == repository
            and node_pr == number
            and metadata.get("head_sha") == head_sha
        ):
            candidates.append(node)

    if len(candidates) != 1:
        raise ResolutionError(
            f"expected one approved node for {repository}#{number}@{head_sha}, "
            f"found {len(candidates)}"
        )
    node = candidates[0]
    metadata = node["metadata"]
    dispatch_key = f"{repository}#{number}@{head_sha}"
    persisted_key = metadata.get("queue_dispatch")
    if metadata.get("queue_dispatch_ack") == dispatch_key:
        status = "duplicate"
    elif persisted_key == dispatch_key:
        status = "replay"
    else:
        status = "resolved"
    result = _handoff_result(
        node,
        metadata,
        repository,
        number,
        head_sha,
        dispatch_key,
        status,
        pull_request["priority"],
    )
    if status == "resolved":
        result["deliveryState"] = None
    return result


def replay_unacknowledged(nodes_value: Any) -> list[dict[str, Any]]:
    """Reconstruct approved handoffs whose current dispatch lacks an ack."""
    nodes = _unwrap(nodes_value)
    if not isinstance(nodes, list):
        raise ContractError("nodes snapshot must be a JSON array")
    handoffs: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict) or node.get("status") != "in_progress":
            continue
        if "state:approved" not in _labels(node):
            continue
        metadata = node.get("metadata")
        if not isinstance(metadata, dict):
            continue
        dispatch_key = metadata.get("queue_dispatch")
        if not isinstance(dispatch_key, str) or not dispatch_key:
            continue
        if metadata.get("queue_dispatch_ack") == dispatch_key:
            continue
        repository = metadata.get("repo")
        head_sha = metadata.get("head_sha")
        try:
            number = int(metadata.get("pr"))
        except (TypeError, ValueError) as error:
            raise ResolutionError("queued node has invalid metadata.pr") from error
        if number < 1:
            raise ResolutionError("queued node has invalid metadata.pr")
        if not isinstance(repository, str) or not REPOSITORY_RE.fullmatch(repository):
            raise ResolutionError("queued node has invalid metadata.repo")
        if not isinstance(head_sha, str) or not HEAD_SHA_RE.fullmatch(head_sha):
            raise ResolutionError("queued node has invalid metadata.head_sha")
        if dispatch_key != f"{repository}#{number}@{head_sha}":
            raise ResolutionError(
                "queued node dispatch key does not match its identity"
            )
        handoffs.append(
            _handoff_result(
                node,
                metadata,
                repository,
                number,
                head_sha,
                dispatch_key,
                "replay",
            )
        )
    return sorted(handoffs, key=lambda handoff: handoff["node"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nodes-file", required=True, help="bd list --json snapshot")
    parser.add_argument(
        "--replay-unacknowledged",
        action="store_true",
        help="emit approved dispatches that lack a matching ack",
    )
    args = parser.parse_args(argv)
    try:
        nodes = _read_json(args.nodes_file)
        if args.replay_unacknowledged:
            result = {
                "status": "replay",
                "dispatches": replay_unacknowledged(nodes),
            }
        else:
            record = json.load(sys.stdin)
            result = resolve(record, nodes)
    except json.JSONDecodeError as error:
        print(f"invalid watcher JSON: {error}", file=sys.stderr)
        return 1
    except ContractError as error:
        print(f"invalid watcher record: {error}", file=sys.stderr)
        return 1
    except ResolutionError as error:
        print(f"unresolved watcher dispatch: {error}", file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, separators=(",", ":"), sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
