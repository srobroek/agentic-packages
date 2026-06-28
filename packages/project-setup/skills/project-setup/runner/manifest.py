"""Module manifest parser (module.toml → ModuleManifest).

Parses a ``module.toml`` file via ``tomllib`` (stdlib, Python >= 3.11) and
validates it against the schema in shared-contracts.md §1. Returns a
``ModuleManifest`` dataclass or accumulates ``SetupError`` instances — it does
NOT raise. Raising is reserved for the validate-closed gate (validate.py).

Standard library only.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# Sibling runner modules import by plain name; the runner dir is on sys.path via
# the entry point (cli.py / conftest.py / executor PYTHONPATH — spec 005 OQ-2).
import contracts as _contracts

SetupError = _contracts.SetupError
ErrorCode = _contracts.ErrorCode
FORBIDDEN_MANIFEST_FIELDS = _contracts.FORBIDDEN_MANIFEST_FIELDS


# --------------------------------------------------------------------------- #
# Input / Step enums + dataclasses                                             #
# --------------------------------------------------------------------------- #
class InputType(str, Enum):
    STRING = "string"
    TEXT = "text"
    INT = "int"
    BOOL = "bool"
    CHOICE = "choice"
    MULTICHOICE = "multichoice"
    PATH = "path"
    LIST = "list"


@dataclass
class InputSpec:
    key: str
    type: InputType
    prompt: str
    choices: list[Any] | None = None
    default: Any | None = None
    required: bool = False
    # G8 escape hatch (spec 004 FR-019): when true, a value matching a secret shape
    # is NOT refused for this input (rare — only for inputs that legitimately carry a
    # secret-shaped non-secret). Default false: secret-shaped values are refused.
    allow_secret: bool = False


@dataclass
class StepSpec:
    id: str
    kind: str           # "python" | "agent" | "gate"
    steering: str | None = None   # required when kind=agent
    message: str | None = None    # required when kind=gate
    # Gate enrichment (spec 004). Only meaningful when kind=gate; ignored otherwise.
    hardness: str = "hard"        # "hard" | "soft" | "informational" (default hard
                                  # = backward-compatible with every pre-004 gate)
    allow_flag: str | None = None # hard gates: the CLI flag that opts INTO the action in CI
    skip_flag: str | None = None  # soft gates: the --no-… flag that opts OUT in CI
    when: str | None = None       # predicate ("key" | "key == v" | "key != v");
                                  # false at build ⟹ the gate step is dropped from the plan
    init_only: bool = False       # gate prompts at init only; on plain reproduce it
                                  # auto-PROCEEDS (no prompt, no block) so the consented
                                  # frozen decision replays byte-identically
    reproduce_only: bool = False  # agent step: skip at init, INVOKE on reproduce
                                  # (spec 012 FR-009; inverse of init_only).
                                  # --refresh overrides: a named module/key re-invokes
                                  # even at init (OQ-1 / Q2 resolution).


@dataclass
class ModuleManifest:
    meta: dict[str, str]
    module: dict[str, Any]
    order: dict[str, list[str]]
    tools: dict[str, list[str]]
    inputs: list[InputSpec]
    steps: list[StepSpec]
    errors: list[SetupError] = field(default_factory=list)

    # Convenience accessors
    @property
    def id(self) -> str:
        return self.module.get("id", "")

    @property
    def version(self) -> str:
        return self.module.get("version", "")

    @property
    def reconcile(self) -> bool:
        return bool(self.module.get("reconcile", False))

    @property
    def default_enabled(self) -> bool | None:
        return self.module.get("default_enabled")


# --------------------------------------------------------------------------- #
# Known top-level sections + field-level constants                             #
# --------------------------------------------------------------------------- #
# ``schema_version`` is an optional top-level manifest-format version (mirrors
# speckit extension.yml and the shared-contracts.md example). Allowed but not
# required; reserved for future manifest-format evolution.
_KNOWN_TOP_LEVEL = frozenset(
    {"schema_version", "meta", "module", "order", "tools", "inputs", "steps"}
)

_REQUIRED_META_KEYS = frozenset({"repository", "author"})

_KNOWN_MODULE_KEYS = frozenset({
    "id", "name", "version", "description", "reconcile", "default_enabled",
})
_REQUIRED_MODULE_KEYS = frozenset({"id", "name", "version", "description", "reconcile"})

_VALID_STEP_KINDS = frozenset({"python", "agent", "gate"})
_VALID_GATE_HARDNESS = frozenset({"hard", "soft", "informational"})
_VALID_INPUT_TYPES = frozenset(i.value for i in InputType)

# Fields that, at any level, trigger FORBIDDEN_FIELD when present.
_FORBIDDEN_TOP_LEVEL = frozenset(FORBIDDEN_MANIFEST_FIELDS)
# module-level kind is also forbidden (tier is step-scoped only)
_FORBIDDEN_MODULE_KEYS = frozenset({"kind"})


# --------------------------------------------------------------------------- #
# Parser                                                                       #
# --------------------------------------------------------------------------- #
def parse_manifest(toml_path: Path) -> ModuleManifest:
    """Parse ``module.toml`` at *toml_path* and return a ``ModuleManifest``.

    Errors are accumulated in ``manifest.errors``; this function never raises.
    Callers should inspect ``manifest.errors`` before using the result.
    """
    errors: list[SetupError] = []
    module_id: str | None = None

    try:
        with open(toml_path, "rb") as fh:
            data = tomllib.load(fh)
    except Exception as exc:
        errors.append(SetupError(
            error_code=ErrorCode.MANIFEST_MALFORMED,
            expected="valid TOML",
            received=str(exc),
            how_to_fix=f"Fix the TOML syntax in {toml_path}",
        ))
        return _empty_manifest(errors)

    # ── top-level forbidden fields ────────────────────────────────────────── #
    for key in data:
        if key in _FORBIDDEN_TOP_LEVEL:
            errors.append(SetupError(
                error_code=ErrorCode.FORBIDDEN_FIELD,
                expected="absent",
                received=f"top-level key '{key}'",
                how_to_fix=f"Remove the '{key}' field — it is not part of the module.toml schema",
            ))

    # ── unknown top-level keys ────────────────────────────────────────────── #
    for key in data:
        if key not in _KNOWN_TOP_LEVEL and key not in _FORBIDDEN_TOP_LEVEL:
            errors.append(SetupError(
                error_code=ErrorCode.UNKNOWN_FIELD,
                expected=f"one of {sorted(_KNOWN_TOP_LEVEL)}",
                received=f"unknown top-level key '{key}'",
                how_to_fix=f"Remove or rename the top-level key '{key}'",
            ))

    # ── [meta] ────────────────────────────────────────────────────────────── #
    meta_raw = data.get("meta", {})
    if not isinstance(meta_raw, dict):
        errors.append(SetupError(
            error_code=ErrorCode.MANIFEST_MALFORMED,
            expected="[meta] table",
            received=str(type(meta_raw)),
            how_to_fix="[meta] must be a TOML table",
        ))
        meta_raw = {}
    for key in _REQUIRED_META_KEYS:
        if key not in meta_raw:
            errors.append(SetupError(
                error_code=ErrorCode.MANIFEST_MALFORMED,
                expected=f"[meta].{key}",
                received="missing",
                how_to_fix=f"Add '{key}' to the [meta] table",
            ))

    # ── [module] ──────────────────────────────────────────────────────────── #
    module_raw = data.get("module", {})
    if not isinstance(module_raw, dict):
        errors.append(SetupError(
            error_code=ErrorCode.MANIFEST_MALFORMED,
            expected="[module] table",
            received=str(type(module_raw)),
            how_to_fix="[module] must be a TOML table",
        ))
        module_raw = {}

    module_id = module_raw.get("id") or None

    # Forbidden keys inside [module]
    for key in module_raw:
        if key in _FORBIDDEN_MODULE_KEYS:
            errors.append(SetupError(
                error_code=ErrorCode.FORBIDDEN_FIELD,
                module_id=module_id,
                expected="absent",
                received=f"[module].{key}",
                how_to_fix=(
                    f"Remove '[module].{key}' — tier is step-scoped "
                    f"(set kind on each [[steps]] entry, not on the module)"
                ),
            ))
    # Forbidden legacy fields inside [module] (e.g. 'produces', 'creates', ...)
    for key in module_raw:
        if key in _FORBIDDEN_TOP_LEVEL and key not in _FORBIDDEN_MODULE_KEYS:
            errors.append(SetupError(
                error_code=ErrorCode.FORBIDDEN_FIELD,
                module_id=module_id,
                expected="absent",
                received=f"[module].{key}",
                how_to_fix=f"Remove '[module].{key}' — it is a forbidden field",
            ))

    for key in _REQUIRED_MODULE_KEYS:
        if key not in module_raw:
            errors.append(SetupError(
                error_code=ErrorCode.MANIFEST_MALFORMED,
                module_id=module_id,
                expected=f"[module].{key}",
                received="missing",
                how_to_fix=f"Add '{key}' to the [module] table",
            ))

    # reconcile must be bool
    if "reconcile" in module_raw and not isinstance(module_raw["reconcile"], bool):
        errors.append(SetupError(
            error_code=ErrorCode.MANIFEST_MALFORMED,
            module_id=module_id,
            expected="bool for [module].reconcile",
            received=str(type(module_raw["reconcile"])),
            how_to_fix="Set [module].reconcile to true or false",
        ))

    # default_enabled must be bool if present
    if "default_enabled" in module_raw and not isinstance(module_raw["default_enabled"], bool):
        errors.append(SetupError(
            error_code=ErrorCode.MANIFEST_MALFORMED,
            module_id=module_id,
            expected="bool for [module].default_enabled",
            received=str(type(module_raw["default_enabled"])),
            how_to_fix="Set [module].default_enabled to true or false (or omit it)",
        ))

    # Unknown keys inside [module]
    _known_with_forbidden = _KNOWN_MODULE_KEYS | _FORBIDDEN_MODULE_KEYS | _FORBIDDEN_TOP_LEVEL
    for key in module_raw:
        if key not in _known_with_forbidden:
            errors.append(SetupError(
                error_code=ErrorCode.UNKNOWN_FIELD,
                module_id=module_id,
                expected=f"one of {sorted(_KNOWN_MODULE_KEYS)}",
                received=f"unknown [module] key '{key}'",
                how_to_fix=f"Remove or rename [module].{key}",
            ))

    # ── [order] ───────────────────────────────────────────────────────────── #
    order_raw = data.get("order", {})
    if not isinstance(order_raw, dict):
        order_raw = {}
    order = {
        "requires": list(order_raw.get("requires", [])),
        "after": list(order_raw.get("after", [])),
        "before": list(order_raw.get("before", [])),
    }

    # ── [tools] ───────────────────────────────────────────────────────────── #
    tools_raw = data.get("tools", {})
    if not isinstance(tools_raw, dict):
        tools_raw = {}
    tools = {"required": list(tools_raw.get("required", []))}

    # ── [[inputs]] ────────────────────────────────────────────────────────── #
    inputs_raw = data.get("inputs", [])
    if not isinstance(inputs_raw, list):
        inputs_raw = []
    inputs = _parse_inputs(inputs_raw, module_id, errors)

    # ── [[steps]] ─────────────────────────────────────────────────────────── #
    steps_raw = data.get("steps", [])
    if not isinstance(steps_raw, list):
        steps_raw = []
    # Pass the declared input keys so a gate `when` predicate referencing an
    # undeclared key is caught as an authoring error (spec 004 OQ-2).
    input_keys = frozenset(s.key for s in inputs)
    steps = _parse_steps(steps_raw, module_id, errors, input_keys)

    return ModuleManifest(
        meta=dict(meta_raw),
        module=dict(module_raw),
        order=order,
        tools=tools,
        inputs=inputs,
        steps=steps,
        errors=errors,
    )


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def _empty_manifest(errors: list[SetupError]) -> ModuleManifest:
    """Return a structurally valid but empty ``ModuleManifest`` with *errors* set.

    Used as the fast-exit when the TOML file cannot be parsed at all, so callers
    always receive a ``ModuleManifest`` (never a raw exception).
    """
    return ModuleManifest(
        meta={},
        module={},
        order={"requires": [], "after": [], "before": []},
        tools={"required": []},
        inputs=[],
        steps=[],
        errors=errors,
    )


def _parse_inputs(
    raw: list[Any],
    module_id: str | None,
    errors: list[SetupError],
) -> list[InputSpec]:
    result = []
    for i, inp in enumerate(raw):
        if not isinstance(inp, dict):
            errors.append(SetupError(
                error_code=ErrorCode.MANIFEST_MALFORMED,
                module_id=module_id,
                expected="dict for [[inputs]] entry",
                received=str(type(inp)),
                how_to_fix=f"Fix [[inputs]] entry #{i} — must be a TOML table",
            ))
            continue

        key = inp.get("key", f"<input#{i}>")
        type_str = inp.get("type", "")
        prompt = inp.get("prompt", "")
        choices = inp.get("choices")
        default = inp.get("default")
        required = bool(inp.get("required", False))
        allow_secret = bool(inp.get("allow_secret", False))

        if type_str not in _VALID_INPUT_TYPES:
            errors.append(SetupError(
                error_code=ErrorCode.MANIFEST_MALFORMED,
                module_id=module_id,
                expected=f"input type in {sorted(_VALID_INPUT_TYPES)}",
                received=f"'{type_str}' for input '{key}'",
                how_to_fix=(
                    f"Set [[inputs]].type for '{key}' to one of: "
                    + ", ".join(sorted(_VALID_INPUT_TYPES))
                ),
            ))
            continue

        input_type = InputType(type_str)

        # choice / multichoice require choices list + default ∈ choices
        if input_type in (InputType.CHOICE, InputType.MULTICHOICE):
            if not choices or not isinstance(choices, list):
                errors.append(SetupError(
                    error_code=ErrorCode.MANIFEST_MALFORMED,
                    module_id=module_id,
                    expected=f"non-empty 'choices' list for input '{key}'",
                    received="missing or non-list",
                    how_to_fix=f"Add a 'choices' list to input '{key}'",
                ))
                continue

            if default is not None:
                if input_type == InputType.CHOICE:
                    if default not in choices:
                        errors.append(SetupError(
                            error_code=ErrorCode.MANIFEST_MALFORMED,
                            module_id=module_id,
                            expected=f"default ∈ choices for input '{key}'",
                            received=f"default={default!r} not in choices={choices!r}",
                            how_to_fix=(
                                f"Set default for '{key}' to one of: {choices!r}"
                            ),
                        ))
                elif input_type == InputType.MULTICHOICE:
                    if isinstance(default, list):
                        bad = [v for v in default if v not in choices]
                        if bad:
                            errors.append(SetupError(
                                error_code=ErrorCode.MANIFEST_MALFORMED,
                                module_id=module_id,
                                expected=f"all defaults ∈ choices for input '{key}'",
                                received=f"default values {bad!r} not in choices={choices!r}",
                                how_to_fix=(
                                    f"Set default for '{key}' to values from: {choices!r}"
                                ),
                            ))
                    else:
                        # single-value default for multichoice — check membership
                        if default not in choices:
                            errors.append(SetupError(
                                error_code=ErrorCode.MANIFEST_MALFORMED,
                                module_id=module_id,
                                expected=f"default ∈ choices for input '{key}'",
                                received=f"default={default!r} not in choices={choices!r}",
                                how_to_fix=(
                                    f"Set default for '{key}' to one of: {choices!r}"
                                ),
                            ))

        result.append(InputSpec(
            key=key,
            type=input_type,
            prompt=prompt,
            choices=choices,
            default=default,
            required=required,
            allow_secret=allow_secret,
        ))
    return result


def _parse_steps(
    raw: list[Any],
    module_id: str | None,
    errors: list[SetupError],
    input_keys: frozenset[str] | None = None,
) -> list[StepSpec]:
    result = []
    for i, step in enumerate(raw):
        if not isinstance(step, dict):
            errors.append(SetupError(
                error_code=ErrorCode.MANIFEST_MALFORMED,
                module_id=module_id,
                expected="dict for [[steps]] entry",
                received=str(type(step)),
                how_to_fix=f"Fix [[steps]] entry #{i} — must be a TOML table",
            ))
            continue

        step_id = step.get("id", f"<step#{i}>")
        kind = step.get("kind", "")

        if kind not in _VALID_STEP_KINDS:
            errors.append(SetupError(
                error_code=ErrorCode.MANIFEST_MALFORMED,
                module_id=module_id,
                expected=f"step kind in {sorted(_VALID_STEP_KINDS)}",
                received=f"'{kind}' for step '{step_id}'",
                how_to_fix=(
                    f"Set [[steps]].kind for '{step_id}' to one of: "
                    + ", ".join(sorted(_VALID_STEP_KINDS))
                ),
            ))
            continue

        steering = step.get("steering")
        message = step.get("message")

        if kind == "agent" and not steering:
            errors.append(SetupError(
                error_code=ErrorCode.MANIFEST_MALFORMED,
                module_id=module_id,
                expected=f"'steering' for kind=agent step '{step_id}'",
                received="missing",
                how_to_fix=f"Add a 'steering' path to [[steps]] entry '{step_id}'",
            ))

        if kind == "gate" and not message:
            errors.append(SetupError(
                error_code=ErrorCode.MANIFEST_MALFORMED,
                module_id=module_id,
                expected=f"'message' for kind=gate step '{step_id}'",
                received="missing",
                how_to_fix=f"Add a 'message' to [[steps]] entry '{step_id}'",
            ))

        # ── Gate enrichment (spec 004): hardness / allow_flag / skip_flag / when /
        #    init_only. These are gate-only; validate the value space here so the
        #    data-driven resolver in executor.run_gate_step never sees a bad value.
        hardness = step.get("hardness", "hard")
        if hardness not in _VALID_GATE_HARDNESS:
            errors.append(SetupError(
                error_code=ErrorCode.MANIFEST_MALFORMED,
                module_id=module_id,
                expected=f"gate hardness in {sorted(_VALID_GATE_HARDNESS)}",
                received=f"'{hardness}' for step '{step_id}'",
                how_to_fix=(
                    f"Set [[steps]].hardness for '{step_id}' to one of: "
                    + ", ".join(sorted(_VALID_GATE_HARDNESS))
                ),
            ))
            hardness = "hard"  # fall back so downstream resolution is well-defined

        when = step.get("when")
        if when is not None:
            # OQ-2: validate the predicate key against the module's declared inputs
            # at parse time so a typo'd key is an authoring error, not a silently
            # always-false (gate-dropped) gate. A declared-but-unset optional input
            # is fine — it resolves to false (gate dropped) at build, by design.
            pred_key = _when_key(when)
            if not pred_key:
                errors.append(SetupError(
                    error_code=ErrorCode.MANIFEST_MALFORMED,
                    module_id=module_id,
                    expected="when = \"<key>\" | \"<key> == <v>\" | \"<key> != <v>\"",
                    received=f"'{when}' for step '{step_id}'",
                    how_to_fix=(
                        f"Fix [[steps]].when for '{step_id}' — use one of: "
                        f"\"key\", \"key == value\", \"key != value\""
                    ),
                ))
            elif input_keys is not None and pred_key not in input_keys:
                errors.append(SetupError(
                    error_code=ErrorCode.MANIFEST_MALFORMED,
                    module_id=module_id,
                    expected=f"when key referencing a declared input {sorted(input_keys)}",
                    received=f"'{pred_key}' for step '{step_id}'",
                    how_to_fix=(
                        f"[[steps]].when for '{step_id}' references undeclared input "
                        f"'{pred_key}' — add it to [[inputs]] or fix the key"
                    ),
                ))

        result.append(StepSpec(
            id=step_id,
            kind=kind,
            steering=steering,
            message=message,
            hardness=hardness,
            allow_flag=step.get("allow_flag"),
            skip_flag=step.get("skip_flag"),
            when=when,
            init_only=bool(step.get("init_only", False)),
            reproduce_only=bool(step.get("reproduce_only", False)),  # spec 012 FR-009
        ))
    return result


# --------------------------------------------------------------------------- #
# Gate `when` predicate (spec 004 FR-006, Settled Decision D)                  #
# --------------------------------------------------------------------------- #
# A minimal, dependency-free predicate over a module's resolved answers, used to
# conditionally include a gate step. Three forms only (no expression language):
#   "key"            → truthy(answers[key])
#   "key == value"   → str(answers[key]) == "value"
#   "key != value"   → str(answers[key]) != "value"
# Evaluated at build_plan against frozen answers, so init and reproduce drop or
# keep the IDENTICAL set of gates (deterministic — Subtlety 3). A missing key is
# falsey (the gate is dropped); parse-time validation (above) catches typo'd keys.
def _when_key(when: str) -> str | None:
    """Return the answer key a ``when`` predicate references, or None if malformed."""
    if not isinstance(when, str):
        return None
    text = when.strip()
    if not text:
        return None
    for op in ("==", "!="):
        if op in text:
            key = text.split(op, 1)[0].strip()
            return key or None
    # bare-key form: must be a single token (no operators, no spaces)
    return text if text and " " not in text else None


def _truthy_answer(value: Any) -> bool:
    """Truthiness for a bare-key ``when`` predicate, matching answer coercion.

    A TOML bool is used directly; a string is truthy unless it is empty or a
    recognized false token ("false"/"no"/"0"); other types use Python truthiness.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in ("", "false", "no", "0")
    return bool(value)


def eval_when(when: str | None, answers: dict[str, Any]) -> bool:
    """Evaluate a gate ``when`` predicate against a module's resolved *answers*.

    Returns True when the predicate holds (gate is KEPT). A None predicate is
    always True (unconditional gate). A missing referenced key is False (gate
    dropped) — a gate must never fire on an unknown condition.
    """
    if when is None:
        return True
    text = when.strip()
    for op in ("==", "!="):
        if op in text:
            raw_key, raw_val = (s.strip() for s in text.split(op, 1))
            if raw_key not in answers:
                return False
            # Compare as rendered strings (answers may be bool/str/int); strip
            # surrounding quotes on the literal so when = 'fmt == "json"' works.
            actual = _render_value(answers[raw_key])
            expected = raw_val.strip().strip("'\"")
            return (actual == expected) if op == "==" else (actual != expected)
    # bare-key form
    if text not in answers:
        return False
    return _truthy_answer(answers[text])


def _render_value(value: Any) -> str:
    """Render an answer value to the canonical string a ``when`` literal compares to.

    A Python bool renders lowercase (``true``/``false``) to match the TOML-style
    literal a manifest author writes (``when = "public == true"``); everything else
    uses ``str()``.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
