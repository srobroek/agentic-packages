"""Shared contracts for the project-setup runner + modules.

This module is the SINGLE source of truth for every shape that crosses a
subsystem boundary: the structured error envelope and its codes, the module
result JSON, the answer-provenance enum, and the canonical JSON serializer.
Every subsystem (manifest, validate, plan, sdk, executor, sources, persist) and
every module's `module.py` imports from here so the contracts cannot drift.

Frozen by Phase 0 of the implementation plan; see
`specs/001-project-setup-modular/contracts/shared-contracts.md`. Standard library
only (runs under uv's Python >= 3.11).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Bumped only when a wire shape (error envelope, result JSON, frozen plan)
# changes incompatibly. The runner refuses a frozen plan whose schema_version it
# does not understand (see plan.py); modules echo the version they were built
# against in their result.
SCHEMA_VERSION = 1


# --------------------------------------------------------------------------- #
# Error codes (the closed set; every gate emits one of these)                  #
# --------------------------------------------------------------------------- #
class ErrorCode(str, Enum):
    """Closed enumeration of every structured-error code the runner emits.

    Inherits ``str`` so a code is JSON-serializable as its value and compares
    equal to the bare string in tests and logs.
    """

    # Preflight / runtime
    UV_MISSING = "UV_MISSING"
    # Discovery / ordering
    ID_COLLISION = "ID_COLLISION"
    DEPENDENCY_CYCLE = "DEPENDENCY_CYCLE"
    MISSING_REQUIRES = "MISSING_REQUIRES"
    # Validate-closed gate
    MISSING_ANSWER = "MISSING_ANSWER"
    MISSING_REQUIRED_TOOL = "MISSING_REQUIRED_TOOL"
    # Manifest parsing
    FORBIDDEN_FIELD = "FORBIDDEN_FIELD"
    UNKNOWN_FIELD = "UNKNOWN_FIELD"
    INPUT_VALUE_INVALID = "INPUT_VALUE_INVALID"
    MANIFEST_MALFORMED = "MANIFEST_MALFORMED"
    # Plan / result gates
    PLAN_MALFORMED = "PLAN_MALFORMED"
    RESULT_SHAPE = "RESULT_SHAPE"
    # Enablement
    UNKNOWN_MODULE = "UNKNOWN_MODULE"
    # Safety / sources
    PATH_ESCAPE = "PATH_ESCAPE"
    FETCH_FAILED = "FETCH_FAILED"
    ORG_SOURCE_UNPINNED = "ORG_SOURCE_UNPINNED"
    SOURCES_SCHEMA_INVALID = "SOURCES_SCHEMA_INVALID"


# Manifest fields that, if present, are a hard error. `priority` enforces the
# "no priority" rule (spec C3); the rest are superseded legacy/FR-009-draft
# fields whose presence means the author followed an out-of-date schema.
FORBIDDEN_MANIFEST_FIELDS = (
    "priority",
    "title",
    "entrypoint",
    "required_answers",
    "optional_answers",
    "produces",
    "creates",
)


# --------------------------------------------------------------------------- #
# Structured error envelope                                                    #
# --------------------------------------------------------------------------- #
@dataclass
class SetupError(Exception):
    """The one structured-error envelope every gate emits.

    ``module_ids`` carries the participants of multi-id errors (ID_COLLISION =
    the two colliding paths/ids; DEPENDENCY_CYCLE = the cycle path) so consumers
    can machine-read them rather than parsing free text. ``how_to_fix`` is always
    populated with the concrete next action.
    """

    error_code: ErrorCode
    expected: str
    received: str
    how_to_fix: str
    module_id: str | None = None
    module_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Make it a usable Exception message too.
        super().__init__(f"[{self.error_code.value}] {self.how_to_fix}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code.value,
            "module_id": self.module_id,
            "module_ids": list(self.module_ids),
            "expected": self.expected,
            "received": self.received,
            "how_to_fix": self.how_to_fix,
        }


class GateFailure(Exception):
    """Raised ONLY by the validate-closed gate, carrying every accumulated
    problem at once (FR-017 'all problems at once'). Ordering/manifest code
    collects ``SetupError`` instances and the gate raises this with the batch;
    nothing else raises mid-pipeline.
    """

    def __init__(self, errors: list[SetupError]) -> None:
        self.errors = list(errors)
        codes = ", ".join(sorted({e.error_code.value for e in self.errors}))
        super().__init__(f"validate-closed failed with {len(self.errors)} problem(s): {codes}")

    def to_dict(self) -> dict[str, Any]:
        return {"gate": "validate-closed", "errors": [e.to_dict() for e in self.errors]}


# --------------------------------------------------------------------------- #
# Answer provenance                                                            #
# --------------------------------------------------------------------------- #
class Provenance(str, Enum):
    """Where an answer value came from.

    Modules may emit only DEFAULT / DERIVED / AGENT_STEERED; the persistence
    layer assigns FLAG / HOME / PROJECT (it alone knows the config layer a value
    won at). See shared-contracts.md §5.
    """

    DEFAULT = "default"          # module manifest default
    FLAG = "flag"                # CLI flag (assigned by persistence)
    HOME = "home"                # home config (assigned by persistence)
    PROJECT = "project"          # committed answers.toml on re-run (persistence)
    DERIVED = "derived"          # computed by the module at runtime
    AGENT_STEERED = "agent-steered"  # a Tier-2 agent decision


# Provenance values a module is allowed to self-report in its result.
MODULE_EMITTABLE_PROVENANCE = frozenset(
    {Provenance.DEFAULT, Provenance.DERIVED, Provenance.AGENT_STEERED}
)


# --------------------------------------------------------------------------- #
# Module result JSON (the result gate validates this)                          #
# --------------------------------------------------------------------------- #
@dataclass
class Diff:
    """A single proposed/applied filesystem change a module reports."""

    path: str                       # repo-relative
    kind: str                       # "create" | "modify" | "skip"
    preview: str = ""               # human-readable summary (optional)

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "kind": self.kind, "preview": self.preview}


@dataclass
class ModuleResult:
    """The EXACTLY-ONE JSON object a module prints to stdout per step.

    The canonical key for written files is ``files_written`` (never ``files``).
    On an ``--inspect`` dry pass the same shape is emitted with files_written /
    diffs populated but NOTHING written; for Tier-1 (kind=python) the inspect
    preview is guaranteed identical to the real write.
    """

    module_id: str
    step_id: str
    status: str = "ok"              # "ok" | "error"
    files_written: list[str] = field(default_factory=list)
    diffs: list[Diff] = field(default_factory=list)
    # key -> {"value": Any, "source": Provenance-value}; modules emit only
    # default/derived/agent-steered sources (MODULE_EMITTABLE_PROVENANCE).
    answers_to_persist: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    message: str = ""
    error: dict[str, Any] | None = None
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "module_id": self.module_id,
            "step_id": self.step_id,
            "status": self.status,
            "files_written": list(self.files_written),
            "diffs": [d.to_dict() for d in self.diffs],
            "answers_to_persist": self.answers_to_persist,
            "warnings": list(self.warnings),
            "message": self.message,
            "error": self.error,
        }


# Required keys the result gate checks a parsed module result against.
RESULT_REQUIRED_KEYS = frozenset(
    {"schema_version", "module_id", "step_id", "status", "files_written", "diffs"}
)


# --------------------------------------------------------------------------- #
# Canonical JSON serializer (the ONE serializer for the frozen plan & results) #
# --------------------------------------------------------------------------- #
def canonical_json(data: Any) -> str:
    """The single canonical JSON serialization used for byte-stable artifacts.

    Exactly mirrors the verified in-repo precedent
    (``packages/speckit-dag-hooks/scripts/build_nodes.py``): pretty-printed,
    key-sorted, unicode-preserving, with a trailing newline. Every frozen plan
    and every persisted JSON artifact MUST go through this so two runs / two
    subsystems produce identical bytes.
    """

    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


# --------------------------------------------------------------------------- #
# Decision rendering (shared by gate-message composition + --refresh diff)     #
# --------------------------------------------------------------------------- #
def render_answer_block(answers: dict[str, Any]) -> str:
    """Render an answer map as a compact, key-sorted human-readable block.

    Used by two-phase execution (Settled Decision H of spec 003): a ``kind=gate``
    step whose ``message`` contains the ``{decision}`` token has it replaced with
    this rendering of the module's resolved answers (so a Tier-2 pin-table gate
    can show the agent's frozen decision through the bare gate primitive), and the
    ``--refresh`` flow uses it for the old-vs-new diff. Generic: it renders
    whatever keys a module's answers carry, with no resolver-specific knowledge.
    Empty / None / empty-list values are omitted so the block stays signal-only.
    """
    lines: list[str] = []
    for key in sorted(answers):
        val = answers[key]
        if val is None or val == "" or val == []:
            continue
        if isinstance(val, (list, tuple)):
            rendered = ", ".join(str(x) for x in val)
        else:
            rendered = str(val)
        lines.append(f"  - {key}: {rendered}")
    return "\n".join(lines) if lines else "  (no decision values)"
