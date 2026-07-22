#!/usr/bin/env python3
"""Atomically claim one Beads node admitted to a generic worker queue.

The queue label is the coordinator-proven capability contract. Selection and
claim happen in one filtered ``bd ready --claim`` operation; this helper never
lists candidates or clears ownership.

Exit codes: 0 CLAIMED/NO_WORK, 2 invalid or unsafe claim result, 3 Beads
failure, 130 interrupted. Every result is deterministic JSON.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import signal
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable, Sequence, TextIO

EVIDENCE_MODES = {"artifact", "comment", "external", "git"}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
BEAD_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class PullWorkerError(RuntimeError):
    """A safe refusal whose exit code and reconciliation need are explicit."""

    def __init__(
        self,
        kind: str,
        message: str,
        *,
        exit_code: int = 2,
        reconcile_required: bool = False,
        bead: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.exit_code = exit_code
        self.reconcile_required = reconcile_required
        self.bead = bead


class StopRequested(BaseException):
    """Raised when shutdown must stop before any retry can be attempted."""


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise PullWorkerError("arguments", message)


@dataclass(frozen=True)
class QueueContract:
    epic: str
    queue: str
    task_kind: str
    evidence: str
    actor: str
    capabilities: tuple[str, ...]

    @property
    def queue_label(self) -> str:
        return f"agent:{self.queue}"


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _slug(value: str, field: str) -> str:
    if not SLUG_RE.fullmatch(value):
        raise PullWorkerError("arguments", f"{field} must be a lowercase label slug")
    return value


def make_contract(args: argparse.Namespace) -> QueueContract:
    queue = args.queue.removeprefix("agent:")
    if not BEAD_RE.fullmatch(args.epic):
        raise PullWorkerError("arguments", "epic must be a Beads identifier")
    _slug(queue, "queue")
    _slug(args.task_kind, "task-kind")
    _slug(args.actor, "actor")
    if args.evidence not in EVIDENCE_MODES:
        raise PullWorkerError("arguments", "unsupported evidence mode")
    capabilities = tuple(
        sorted({_slug(item, "capability") for item in args.capability})
    )
    return QueueContract(
        epic=args.epic,
        queue=queue,
        task_kind=args.task_kind,
        evidence=args.evidence,
        actor=args.actor,
        capabilities=capabilities,
    )


def build_claim_command(bd_command: str, contract: QueueContract) -> list[str]:
    """Build the sole mutating command with all compatibility filters applied."""
    if not bd_command or "\x00" in bd_command:
        raise PullWorkerError("arguments", "bd command must be non-empty")
    return [
        bd_command,
        "--actor",
        contract.actor,
        "ready",
        "--parent",
        contract.epic,
        "--label",
        "orc-node",
        "--label",
        contract.queue_label,
        "--metadata-field",
        f"execution_kind={contract.task_kind}",
        "--metadata-field",
        f"execution_evidence={contract.evidence}",
        "--unassigned",
        "--sort",
        "priority",
        "--claim",
        "--json",
    ]


def _decode_claim(stdout: str) -> list[Any]:
    if not stdout.strip():
        raise PullWorkerError(
            "beads_json",
            "bd returned no JSON after the atomic claim command",
            reconcile_required=True,
        )
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise PullWorkerError(
            "beads_json",
            f"bd returned malformed JSON: {error.msg}",
            reconcile_required=True,
        ) from error
    if isinstance(value, dict) and "schema_version" in value and "data" in value:
        value = value["data"]
    if not isinstance(value, list):
        raise PullWorkerError(
            "beads_json",
            "bd ready --claim JSON must be an array",
            reconcile_required=True,
        )
    if len(value) > 1:
        raise PullWorkerError(
            "beads_json",
            "bd ready --claim returned more than one issue",
            reconcile_required=True,
        )
    return value


def _string(value: Any, field: str, bead: str | None = None) -> str:
    if not isinstance(value, str) or not value:
        raise PullWorkerError(
            "routing_envelope",
            f"claimed issue is missing {field}",
            reconcile_required=True,
            bead=bead,
        )
    return value


def _string_list(value: Any, field: str, bead: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise PullWorkerError(
            "routing_envelope",
            f"claimed issue {field} must be a non-empty string array",
            reconcile_required=True,
            bead=bead,
        )
    return value


def validate_claim(issue: Any, contract: QueueContract) -> dict[str, Any]:
    """Verify the result after atomic filters established descendant membership."""
    if not isinstance(issue, dict):
        raise PullWorkerError(
            "beads_json",
            "claimed issue must be a JSON object",
            reconcile_required=True,
        )
    bead = _string(issue.get("id"), "id")
    assignee = issue.get("assignee")
    if assignee != contract.actor:
        raise PullWorkerError(
            "claim_lost",
            f"claimed issue belongs to {assignee or 'no actor'}, not {contract.actor}",
            reconcile_required=True,
            bead=bead,
        )
    if issue.get("status") != "in_progress":
        raise PullWorkerError(
            "claim_lost",
            "claimed issue is not in_progress",
            reconcile_required=True,
            bead=bead,
        )
    labels = _string_list(issue.get("labels"), "labels", bead)
    label_set = set(labels)
    required_labels = {"orc-node", contract.queue_label}
    if not required_labels.issubset(label_set):
        raise PullWorkerError(
            "routing_envelope",
            "claimed issue is missing its generic queue labels",
            reconcile_required=True,
            bead=bead,
        )
    other_queues = sorted(
        label
        for label in label_set
        if label.startswith("agent:") and label != contract.queue_label
    )
    if other_queues:
        raise PullWorkerError(
            "routing_envelope",
            "claimed issue has more than one agent route",
            reconcile_required=True,
            bead=bead,
        )

    metadata = issue.get("metadata")
    if not isinstance(metadata, dict):
        raise PullWorkerError(
            "routing_envelope",
            "claimed issue metadata must be an object",
            reconcile_required=True,
            bead=bead,
        )
    scope = _string_list(metadata.get("scope"), "metadata.scope", bead)
    if metadata.get("execution_kind") != contract.task_kind:
        raise PullWorkerError(
            "routing_envelope",
            "claimed issue task kind does not match the queue activation",
            reconcile_required=True,
            bead=bead,
        )
    if metadata.get("execution_evidence") != contract.evidence:
        raise PullWorkerError(
            "routing_envelope",
            "claimed issue evidence does not match the queue activation",
            reconcile_required=True,
            bead=bead,
        )

    raw_capabilities = metadata.get("execution_capabilities")
    if not isinstance(raw_capabilities, list) or not all(
        isinstance(item, str) and SLUG_RE.fullmatch(item) for item in raw_capabilities
    ):
        raise PullWorkerError(
            "routing_envelope",
            "claimed issue execution_capabilities must be a string array",
            reconcile_required=True,
            bead=bead,
        )
    required_capabilities = set(raw_capabilities)
    mirrored_capabilities = {
        label.removeprefix("cap:") for label in label_set if label.startswith("cap:")
    }
    if required_capabilities != mirrored_capabilities:
        raise PullWorkerError(
            "routing_envelope",
            "claimed issue capability metadata and labels differ",
            reconcile_required=True,
            bead=bead,
        )
    missing = sorted(required_capabilities - set(contract.capabilities))
    if missing:
        raise PullWorkerError(
            "routing_envelope",
            f"worker lacks required capabilities: {', '.join(missing)}",
            reconcile_required=True,
            bead=bead,
        )

    dispatch = metadata.get("execution_dispatch")
    selected_agent = metadata.get("execution_agent")
    if dispatch not in (None, "", "generic") or selected_agent not in (
        None,
        "",
        "workflow-pull-worker",
    ):
        raise PullWorkerError(
            "routing_envelope",
            "claimed issue is reserved for an explicit or specialised route",
            reconcile_required=True,
            bead=bead,
        )

    git_evidence = contract.evidence == "git"
    result: dict[str, Any] = {
        "actor": contract.actor,
        "bead": bead,
        "completion": {
            "commit_required": git_evidence,
            "output_ref_required": not git_evidence,
        },
        "execution_evidence": contract.evidence,
        "execution_kind": contract.task_kind,
        "ordering": {
            "policy": "priority",
            "tie_break": "beads-ready-order",
        },
        "queue": contract.queue_label,
        "required_capabilities": sorted(required_capabilities),
        "scope": scope,
        "status": "CLAIMED",
    }
    return result


def run_claim(
    contract: QueueContract,
    *,
    bd_command: str = "bd",
    timeout: float = 15.0,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    command = build_claim_command(bd_command, contract)
    try:
        process = runner(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**os.environ, "BEADS_ACTOR": contract.actor},
        )
    except subprocess.TimeoutExpired as error:
        raise PullWorkerError(
            "beads_timeout",
            f"bd ready --claim exceeded {timeout:g}s",
            exit_code=3,
            reconcile_required=True,
        ) from error
    except OSError as error:
        raise PullWorkerError(
            "beads_command",
            f"cannot execute {bd_command}: {error}",
            exit_code=3,
        ) from error
    except KeyboardInterrupt as error:
        raise StopRequested from error

    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip() or "no error output"
        raise PullWorkerError(
            "beads_command",
            f"bd ready --claim exited {process.returncode}: {detail}",
            exit_code=3,
            reconcile_required=True,
        )
    claimed = _decode_claim(process.stdout)
    if not claimed:
        return {
            "actor": contract.actor,
            "ordering": {
                "policy": "priority",
                "tie_break": "beads-ready-order",
            },
            "queue": contract.queue_label,
            "status": "NO_WORK",
        }
    return validate_claim(claimed[0], contract)


def _emit(value: dict[str, Any], stream: TextIO) -> None:
    stream.write(json.dumps(value, sort_keys=True, separators=(",", ":")))
    stream.write("\n")


def _parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(description=__doc__)
    parser.add_argument("--epic", required=True)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--task-kind", required=True)
    parser.add_argument("--evidence", required=True, choices=sorted(EVIDENCE_MODES))
    parser.add_argument("--actor", required=True)
    parser.add_argument("--capability", action="append", default=[])
    parser.add_argument("--bd", default="bd", help="bd executable path")
    parser.add_argument("--timeout", type=float, default=15.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise PullWorkerError("arguments", "timeout must be positive")
        result = run_claim(
            make_contract(args), bd_command=args.bd, timeout=args.timeout
        )
    except StopRequested:
        _emit(
            {
                "kind": "interrupt",
                "message": "claim interrupted; reconcile Beads before retry",
                "reconcile_required": True,
                "status": "STOPPED",
            },
            sys.stderr,
        )
        return 130
    except PullWorkerError as error:
        result = {
            "kind": error.kind,
            "message": str(error),
            "reconcile_required": error.reconcile_required,
            "status": "ERROR",
        }
        if error.bead:
            result["bead"] = error.bead
        _emit(result, sys.stderr)
        return error.exit_code
    _emit(result, sys.stdout)
    return 0


def _stop(_signum: int, _frame: Any) -> None:
    raise StopRequested


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _stop)
    raise SystemExit(main())
