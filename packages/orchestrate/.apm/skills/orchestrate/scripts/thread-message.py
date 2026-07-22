#!/usr/bin/env python3
"""Create and inspect Beads-native orchestration message threads.

The helper emits a JSON envelope on stdout for success and failure. It uses
message wisps linked by ``replies-to`` dependencies and does not wake agents.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any

PROTOCOL = "replies-to"
SCHEMA_VERSION = 1
IDENTITY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@/+:-]{0,254}$")


class MessageError(Exception):
    """A deterministic protocol or Beads integration failure."""

    def __init__(
        self, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise MessageError("usage", message)


def _identity(value: str, field: str) -> str:
    if not IDENTITY_RE.fullmatch(value):
        raise MessageError(
            "invalid_identity",
            f"{field} must be a non-empty identity token without whitespace",
            {"field": field},
        )
    return value


def _nonempty(value: str, field: str) -> str:
    if not value.strip():
        raise MessageError(
            "invalid_value", f"{field} must not be empty", {"field": field}
        )
    return value


class Beads:
    def __init__(self, executable: str) -> None:
        self.executable = executable

    def run(self, args: list[str], actor: str | None = None) -> Any:
        env = os.environ.copy()
        env.update(
            {
                "BD_JSON_ENVELOPE": "1",
                "BD_NO_PAGER": "1",
                "BD_NON_INTERACTIVE": "1",
            }
        )
        if actor is not None:
            env["BEADS_ACTOR"] = actor

        try:
            process = subprocess.run(
                [self.executable, *args, "--json"],
                capture_output=True,
                text=True,
                env=env,
                timeout=60,
            )
        except FileNotFoundError as exc:
            raise MessageError("bd_unavailable", "bd executable was not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise MessageError("bd_timeout", "bd command timed out") from exc

        try:
            envelope = json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            raise MessageError(
                "invalid_bd_json",
                "bd did not return a valid JSON envelope",
                {"operation": args[0]},
            ) from exc

        if (
            not isinstance(envelope, dict)
            or envelope.get("schema_version") != SCHEMA_VERSION
            or "data" not in envelope
        ):
            raise MessageError(
                "invalid_bd_json",
                "bd returned an unsupported JSON envelope",
                {"operation": args[0]},
            )

        data = envelope["data"]
        if process.returncode:
            bd_error = data.get("error") if isinstance(data, dict) else None
            raise MessageError(
                "bd_command_failed",
                "bd command failed",
                {
                    "operation": args[0],
                    "returncode": process.returncode,
                    "bd_error": bd_error or "unavailable",
                },
            )
        return data

    def show(self, issue_id: str, *, dependents: bool = False) -> dict[str, Any]:
        _identity(issue_id, "issue")
        args = ["show", f"--id={issue_id}"]
        if dependents:
            args.append("--include-dependents")
        try:
            data = self.run(args)
        except MessageError as exc:
            if exc.code == "bd_command_failed" and "no issue" in str(
                exc.details.get("bd_error", "")
            ):
                raise MessageError(
                    "issue_not_found", "issue does not exist", {"issue": issue_id}
                ) from exc
            raise
        if (
            not isinstance(data, list)
            or len(data) != 1
            or not isinstance(data[0], dict)
        ):
            raise MessageError(
                "invalid_bd_json",
                "bd show returned an unexpected result",
                {"issue": issue_id},
            )
        return data[0]


def _metadata(issue: dict[str, Any]) -> dict[str, Any]:
    metadata = issue.get("metadata")
    if metadata is None:
        raise MessageError(
            "invalid_message_metadata",
            "message metadata is missing",
            {"message": issue.get("id", "unknown")},
        )
    if not isinstance(metadata, dict):
        raise MessageError(
            "invalid_bd_json",
            "bd returned non-object message metadata",
            {"message": issue.get("id", "unknown")},
        )
    return metadata


def _relation_ids(issue: dict[str, Any], field: str, dependency_type: str) -> list[str]:
    relations = issue.get(field, [])
    if not isinstance(relations, list) or any(
        not isinstance(relation, dict) for relation in relations
    ):
        raise MessageError(
            "invalid_bd_json",
            f"bd returned malformed {field}",
            {"issue": issue.get("id", "unknown")},
        )

    ids: list[str] = []
    for relation in relations:
        relation_type = relation.get("dependency_type")
        if relation_type is not None and not isinstance(relation_type, str):
            raise MessageError(
                "invalid_bd_json",
                f"bd returned malformed {field} dependency type",
                {"issue": issue.get("id", "unknown")},
            )
        if relation_type != dependency_type:
            continue
        relation_id = relation.get("id")
        if not isinstance(relation_id, str):
            raise MessageError(
                "invalid_bd_json",
                f"bd returned malformed {field} issue id",
                {"issue": issue.get("id", "unknown")},
            )
        ids.append(relation_id)
    return ids


def _validate_message(
    issue: dict[str, Any],
    *,
    run: str | None = None,
    bead: str | None = None,
) -> dict[str, Any]:
    message_id = issue.get("id")
    if not isinstance(message_id, str):
        raise MessageError("invalid_bd_json", "bd returned malformed message id")
    _identity(message_id, "message")
    issue_type = issue.get("issue_type")
    if not isinstance(issue_type, str):
        raise MessageError(
            "invalid_bd_json",
            "bd returned malformed message type",
            {"message": message_id},
        )
    if issue_type != "message":
        raise MessageError(
            "parent_not_message",
            "the selected issue is not a message",
            {"issue": message_id},
        )

    metadata = _metadata(issue)
    protocol = metadata.get("protocol")
    if protocol is not None and not isinstance(protocol, str):
        raise MessageError(
            "invalid_bd_json",
            "bd returned malformed message protocol",
            {"message": message_id},
        )
    if protocol != PROTOCOL:
        raise MessageError(
            "invalid_message_protocol",
            "message does not use the replies-to protocol",
            {"message": message_id},
        )

    for field in ("actor", "assignee", "run", "bead"):
        if field not in metadata:
            raise MessageError(
                "invalid_message_metadata",
                f"message metadata is missing {field}",
                {"message": message_id, "field": field},
            )
        value = metadata[field]
        if not isinstance(value, str):
            raise MessageError(
                "invalid_bd_json",
                f"bd returned malformed message metadata field {field}",
                {"message": message_id},
            )
        _identity(value, field)

    issue_assignee = issue.get("assignee")
    if not isinstance(issue_assignee, str):
        raise MessageError(
            "invalid_bd_json",
            "bd returned malformed message assignee",
            {"message": message_id},
        )
    if issue_assignee != metadata["assignee"]:
        raise MessageError(
            "recipient_mismatch",
            "message assignee does not match its metadata",
            {"message": message_id},
        )
    created_by = issue.get("created_by")
    if created_by is not None and not isinstance(created_by, str):
        raise MessageError(
            "invalid_bd_json",
            "bd returned malformed message creator",
            {"message": message_id},
        )
    if created_by and created_by != metadata["actor"]:
        raise MessageError(
            "actor_mismatch",
            "message creator does not match its metadata",
            {"message": message_id},
        )
    if run is not None and metadata["run"] != run:
        raise MessageError(
            "run_mismatch",
            "message belongs to a different run",
            {"message": message_id, "expected": run},
        )
    if bead is not None and metadata["bead"] != bead:
        raise MessageError(
            "bead_mismatch",
            "message belongs to a different work bead",
            {"message": message_id, "expected": bead},
        )
    return metadata


def _replies_to(issue: dict[str, Any]) -> str:
    parent_ids = _relation_ids(issue, "dependencies", PROTOCOL)
    message_id = str(issue.get("id", ""))
    if len(parent_ids) != 1:
        raise MessageError(
            "invalid_parent_count",
            "message must have exactly one replies-to parent",
            {"message": message_id, "count": len(parent_ids)},
        )
    parent = parent_ids[0]
    _identity(parent, "parent")
    if parent == message_id:
        raise MessageError(
            "self_reference",
            "message cannot reply to itself",
            {"message": message_id},
        )
    return parent


def _validate_work(
    client: Beads, run: str, bead: str, *, require_active: bool
) -> dict[str, Any]:
    _identity(run, "run")
    _identity(bead, "bead")
    run_issue = client.show(run)
    run_type = run_issue.get("issue_type")
    if not isinstance(run_type, str):
        raise MessageError("invalid_bd_json", "bd returned malformed run type")
    if run_type != "epic":
        raise MessageError(
            "invalid_run", "run identity must refer to an epic", {"run": run}
        )
    run_status = run_issue.get("status")
    if not isinstance(run_status, str):
        raise MessageError("invalid_bd_json", "bd returned malformed run status")
    if require_active and run_status != "open":
        raise MessageError("run_closed", "run epic is not open", {"run": run})

    work = client.show(bead)
    work_type = work.get("issue_type")
    if not isinstance(work_type, str):
        raise MessageError("invalid_bd_json", "bd returned malformed work type")
    if work_type == "message":
        raise MessageError(
            "invalid_work_bead", "work bead cannot be a message", {"bead": bead}
        )
    parent_ids = set(_relation_ids(work, "dependencies", "parent-child"))
    direct_parent = work.get("parent")
    if direct_parent is not None and not isinstance(direct_parent, str):
        raise MessageError("invalid_bd_json", "bd returned malformed work parent")
    if direct_parent != run and run not in parent_ids:
        raise MessageError(
            "bead_run_mismatch",
            "work bead is not a child of the run epic",
            {"run": run, "bead": bead},
        )
    work_status = work.get("status")
    if not isinstance(work_status, str):
        raise MessageError("invalid_bd_json", "bd returned malformed work status")
    if require_active and work_status not in {"open", "in_progress"}:
        raise MessageError(
            "work_bead_closed", "work bead is not active", {"bead": bead}
        )
    return work


def _parent_issue(client: Beads, issue: dict[str, Any]) -> dict[str, Any]:
    parent_id = _replies_to(issue)
    try:
        return client.show(parent_id)
    except MessageError as exc:
        if exc.code == "issue_not_found":
            raise MessageError(
                "parent_not_found",
                "message parent does not exist",
                {"message": issue.get("id"), "parent": parent_id},
            ) from exc
        raise


def _root_and_work(
    client: Beads,
    seed: dict[str, Any],
    run: str,
    bead: str,
    *,
    require_active: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    visited: set[str] = set()
    current = seed
    while True:
        metadata = _validate_message(current, run=run, bead=bead)
        message_id = str(current["id"])
        if message_id in visited:
            raise MessageError(
                "thread_cycle",
                "message thread contains a cycle",
                {"message": message_id},
            )
        visited.add(message_id)
        parent = _parent_issue(client, current)
        if parent.get("issue_type") == "message":
            current = parent
            continue
        if parent.get("id") != metadata["bead"]:
            raise MessageError(
                "thread_root_mismatch",
                "thread root does not reply to its declared work bead",
                {"message": message_id, "parent": parent.get("id")},
            )
        work = _validate_work(client, run, bead, require_active=require_active)
        return current, work


def _message_record(issue: dict[str, Any], parent: str, depth: int) -> dict[str, Any]:
    metadata = _validate_message(issue)
    text_fields: dict[str, str] = {}
    for field in ("description", "created_at", "status", "title"):
        value = issue.get(field, "")
        if not isinstance(value, str):
            raise MessageError(
                "invalid_bd_json",
                f"bd returned malformed message {field}",
                {"message": issue["id"]},
            )
        text_fields[field] = value
    return {
        "actor": metadata["actor"],
        "assignee": metadata["assignee"],
        "bead": metadata["bead"],
        "body": text_fields["description"],
        "created_at": text_fields["created_at"],
        "depth": depth,
        "id": issue["id"],
        "parent": parent,
        "run": metadata["run"],
        "status": text_fields["status"],
        "subject": text_fields["title"],
    }


def _thread_records(
    client: Beads, root: dict[str, Any], run: str, bead: str
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(issue: dict[str, Any], parent: str, depth: int) -> None:
        message_id = str(issue["id"])
        if message_id in visiting:
            raise MessageError(
                "thread_cycle",
                "message thread contains a cycle",
                {"message": message_id},
            )
        if message_id in visited:
            raise MessageError(
                "multiple_parents",
                "message is reachable from more than one parent",
                {"message": message_id},
            )
        _validate_message(issue, run=run, bead=bead)
        actual_parent = _replies_to(issue)
        if actual_parent != parent:
            raise MessageError(
                "parent_mismatch",
                "message edge does not match the rendered parent",
                {"message": message_id, "expected": parent},
            )

        visiting.add(message_id)
        records.append(_message_record(issue, parent, depth))
        with_dependents = client.show(message_id, dependents=True)
        child_ids = set(_relation_ids(with_dependents, "dependents", PROTOCOL))
        children = [client.show(child_id) for child_id in child_ids]
        for child in children:
            _message_record(child, message_id, depth + 1)
        children.sort(
            key=lambda child: (child.get("created_at", ""), child.get("id", ""))
        )
        for child in children:
            visit(child, message_id, depth + 1)
        visiting.remove(message_id)
        visited.add(message_id)

    visit(root, bead, 0)
    return records


def _create_message(
    client: Beads,
    *,
    operation: str,
    actor: str,
    assignee: str,
    run: str,
    bead: str,
    parent: str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    metadata = json.dumps(
        {
            "actor": actor,
            "assignee": assignee,
            "bead": bead,
            "protocol": PROTOCOL,
            "run": run,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    created = client.run(
        [
            "create",
            "--title",
            subject,
            "--description",
            body,
            "--type",
            "message",
            "--assignee",
            assignee,
            "--metadata",
            metadata,
            "--ephemeral",
        ],
        actor,
    )
    if not isinstance(created, dict) or not isinstance(created.get("id"), str):
        raise MessageError("invalid_bd_json", "bd create returned an unexpected result")
    message_id = created["id"]
    try:
        client.run(["dep", "add", message_id, parent, "--type", PROTOCOL], actor)
    except MessageError as exc:
        rolled_back = False
        try:
            client.run(
                ["close", message_id, "--reason", f"{operation} link failed"], actor
            )
            rolled_back = True
        except MessageError:
            pass
        raise MessageError(
            "link_failed",
            "message was created but could not be linked",
            {"message": message_id, "rolled_back": rolled_back},
        ) from exc
    return client.show(message_id)


def send(client: Beads, args: argparse.Namespace) -> dict[str, Any]:
    actor = _identity(args.actor, "actor")
    assignee = _identity(args.assignee, "assignee")
    run = _identity(args.run, "run")
    bead = _identity(args.bead, "bead")
    _validate_work(client, run, bead, require_active=True)
    message = _create_message(
        client,
        operation="send",
        actor=actor,
        assignee=assignee,
        run=run,
        bead=bead,
        parent=bead,
        subject=_nonempty(args.subject, "subject"),
        body=_nonempty(args.body, "body"),
    )
    return {"message": _message_record(message, bead, 0)}


def reply(client: Beads, args: argparse.Namespace) -> dict[str, Any]:
    actor = _identity(args.actor, "actor")
    assignee = _identity(args.assignee, "assignee")
    run = _identity(args.run, "run")
    bead = _identity(args.bead, "bead")
    parent_id = _identity(args.parent, "parent")
    try:
        parent = client.show(parent_id)
    except MessageError as exc:
        if exc.code == "issue_not_found":
            raise MessageError(
                "parent_not_found", "reply parent does not exist", {"parent": parent_id}
            ) from exc
        raise
    _validate_message(parent, run=run, bead=bead)
    _root_and_work(client, parent, run, bead, require_active=True)
    if parent.get("status") != "open":
        raise MessageError(
            "message_closed", "cannot reply to a closed message", {"parent": parent_id}
        )
    message = _create_message(
        client,
        operation="reply",
        actor=actor,
        assignee=assignee,
        run=run,
        bead=bead,
        parent=parent_id,
        subject=_nonempty(args.subject, "subject"),
        body=_nonempty(args.body, "body"),
    )
    return {"message": _message_record(message, parent_id, 0)}


def inbox(client: Beads, args: argparse.Namespace) -> dict[str, Any]:
    actor = _identity(args.actor, "actor")
    if (args.run is None) != (args.bead is None):
        raise MessageError("usage", "inbox filters require both --run and --bead")
    run = _identity(args.run, "run") if args.run else None
    bead = _identity(args.bead, "bead") if args.bead else None
    data = client.run(
        [
            "list",
            "--include-infra",
            "--type",
            "message",
            "--assignee",
            actor,
            "--status",
            "open",
            "--sort",
            "created",
            "--limit",
            "0",
        ]
    )
    if not isinstance(data, list):
        raise MessageError("invalid_bd_json", "bd list returned an unexpected result")

    records: list[dict[str, Any]] = []
    invalid: list[dict[str, str]] = []
    for summary in data:
        if not isinstance(summary, dict) or not isinstance(summary.get("id"), str):
            raise MessageError(
                "invalid_bd_json", "bd list returned a malformed message entry"
            )
        message_id = summary["id"]
        try:
            issue = client.show(message_id)
            metadata = _validate_message(issue)
            if metadata["assignee"] != actor:
                raise MessageError(
                    "recipient_mismatch",
                    "inbox returned a message for another actor",
                    {"message": issue["id"]},
                )
            if run is not None and (metadata["run"] != run or metadata["bead"] != bead):
                continue
            _root_and_work(client, issue, metadata["run"], metadata["bead"])
            records.append(_message_record(issue, _replies_to(issue), 0))
        except MessageError as exc:
            if exc.code == "invalid_bd_json":
                raise
            invalid.append({"code": exc.code, "id": message_id})
    records.sort(key=lambda record: (record["created_at"], record["id"]))
    invalid.sort(key=lambda record: record["id"])
    return {"actor": actor, "invalid": invalid, "messages": records}


def show(client: Beads, args: argparse.Namespace) -> dict[str, Any]:
    message_id = _identity(args.message, "message")
    try:
        issue = client.show(message_id)
    except MessageError as exc:
        if exc.code == "issue_not_found":
            raise MessageError(
                "message_not_found", "message does not exist", {"message": message_id}
            ) from exc
        raise
    metadata = _validate_message(issue)
    root, work = _root_and_work(client, issue, metadata["run"], metadata["bead"])
    result: dict[str, Any] = {
        "message": _message_record(issue, _replies_to(issue), 0),
        "root": root["id"],
        "work_bead": {"id": work["id"], "status": work.get("status", "")},
    }
    if args.thread:
        result["thread"] = _thread_records(
            client, root, metadata["run"], metadata["bead"]
        )
    return result


def acknowledge(client: Beads, args: argparse.Namespace) -> dict[str, Any]:
    actor = _identity(args.actor, "actor")
    run = _identity(args.run, "run")
    bead = _identity(args.bead, "bead")
    message_id = _identity(args.message, "message")
    try:
        issue = client.show(message_id)
    except MessageError as exc:
        if exc.code == "issue_not_found":
            raise MessageError(
                "message_not_found", "message does not exist", {"message": message_id}
            ) from exc
        raise
    metadata = _validate_message(issue, run=run, bead=bead)
    _, work = _root_and_work(client, issue, run, bead)
    if metadata["assignee"] != actor:
        raise MessageError(
            "recipient_mismatch",
            "only the message assignee may acknowledge it",
            {"message": message_id},
        )
    if issue.get("status") == "closed":
        return {
            "already_closed": True,
            "message": _message_record(issue, _replies_to(issue), 0),
            "work_bead": {"id": work["id"], "status": work.get("status", "")},
        }
    if issue.get("status") != "open":
        raise MessageError(
            "invalid_message_status",
            "message must be open or closed",
            {"message": message_id, "status": issue.get("status")},
        )
    client.run(["close", message_id, "--reason", f"acknowledged by {actor}"], actor)
    closed = client.show(message_id)
    return {
        "already_closed": False,
        "message": _message_record(closed, _replies_to(closed), 0),
        "work_bead": {"id": work["id"], "status": work.get("status", "")},
    }


def _parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(prog="thread-message.py")
    parser.add_argument("--bd", default="bd", help="bd executable (default: bd)")
    commands = parser.add_subparsers(dest="operation", required=True)

    send_parser = commands.add_parser("send", aliases=["root"])
    reply_parser = commands.add_parser("reply")
    for command in (send_parser, reply_parser):
        command.add_argument("--actor", required=True)
        command.add_argument("--assignee", required=True)
        command.add_argument("--run", required=True)
        command.add_argument("--bead", required=True)
        command.add_argument("--subject", required=True)
        command.add_argument("--body", required=True)
    reply_parser.add_argument("--parent", required=True)

    inbox_parser = commands.add_parser("inbox")
    inbox_parser.add_argument("--actor", required=True)
    inbox_parser.add_argument("--run")
    inbox_parser.add_argument("--bead")

    show_parser = commands.add_parser("show", aliases=["thread"])
    show_parser.add_argument("--message", required=True)
    show_parser.add_argument("--thread", action="store_true")

    ack_parser = commands.add_parser("acknowledge", aliases=["ack"])
    ack_parser.add_argument("--actor", required=True)
    ack_parser.add_argument("--run", required=True)
    ack_parser.add_argument("--bead", required=True)
    ack_parser.add_argument("--message", required=True)
    return parser


def _dispatch(client: Beads, args: argparse.Namespace) -> dict[str, Any]:
    if args.operation in {"send", "root"}:
        return send(client, args)
    if args.operation == "reply":
        return reply(client, args)
    if args.operation == "inbox":
        return inbox(client, args)
    if args.operation in {"show", "thread"}:
        if args.operation == "thread":
            args.thread = True
        return show(client, args)
    if args.operation in {"acknowledge", "ack"}:
        return acknowledge(client, args)
    raise MessageError("usage", "unknown operation")


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    operation = "unknown"
    try:
        args = _parser().parse_args(argv)
        operation = args.operation
        result = _dispatch(Beads(args.bd), args)
        _emit(
            {
                "data": result,
                "ok": True,
                "operation": operation,
                "schema_version": SCHEMA_VERSION,
            }
        )
        return 0
    except MessageError as exc:
        error: dict[str, Any] = {"code": exc.code, "message": exc.message}
        if exc.details:
            error["details"] = exc.details
        _emit(
            {
                "error": error,
                "ok": False,
                "operation": operation,
                "schema_version": SCHEMA_VERSION,
            }
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
