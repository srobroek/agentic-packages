"""Answer layering and coercion.

Implements the config-layering model from shared-contracts.md §8 and FR-020/FR-026.

Layering precedence (lowest → highest):
  module manifest default < home config < project committed answers < user choice

Standard library only (tomllib for reading TOML).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Sibling runner modules import by plain name; the runner dir is on sys.path via
# the entry point (cli.py / conftest.py / executor PYTHONPATH — spec 005 OQ-2).
import contracts as _contracts

SetupError = _contracts.SetupError
ErrorCode = _contracts.ErrorCode
Provenance = _contracts.Provenance


# --------------------------------------------------------------------------- #
# Defaults extraction from manifests                                           #
# --------------------------------------------------------------------------- #
def _manifest_defaults(manifests: list) -> dict[str, dict[str, Any]]:
    """Build a per-module dict of manifest-declared defaults."""
    defaults: dict[str, dict[str, Any]] = {}
    for m in manifests:
        mod_defaults: dict[str, Any] = {}
        for inp in m.inputs:
            if inp.default is not None:
                mod_defaults[inp.key] = inp.default
        defaults[m.id] = mod_defaults
    return defaults


# --------------------------------------------------------------------------- #
# Coercion                                                                     #
# --------------------------------------------------------------------------- #
def _coerce_value(
    key: str,
    value: Any,
    input_type: str,
    module_id: str | None,
) -> tuple[Any, SetupError | None]:
    """Coerce *value* to *input_type*. Returns (coerced, error_or_None)."""
    try:
        if input_type == "string":
            return str(value), None
        elif input_type == "text":
            return str(value), None
        elif input_type == "int":
            if isinstance(value, bool):
                raise ValueError("bool is not an int")
            return int(value), None
        elif input_type == "bool":
            if isinstance(value, bool):
                return value, None
            if isinstance(value, str):
                if value.lower() in ("true", "1", "yes"):
                    return True, None
                if value.lower() in ("false", "0", "no"):
                    return False, None
            raise ValueError(f"cannot coerce {value!r} to bool")
        elif input_type == "choice":
            return str(value), None
        elif input_type == "multichoice":
            if isinstance(value, list):
                return [str(v) for v in value], None
            return [str(value)], None
        elif input_type == "path":
            return str(value), None
        elif input_type == "list":
            if isinstance(value, list):
                return list(value), None
            return [value], None
        else:
            return value, None
    except Exception as exc:
        error = SetupError(
            error_code=ErrorCode.INPUT_VALUE_INVALID,
            module_id=module_id,
            expected=f"value of type '{input_type}' for input '{key}'",
            received=repr(value),
            how_to_fix=(
                f"Provide a valid '{input_type}' value for '{key}' "
                f"in module '{module_id}': {exc}"
            ),
        )
        return value, error


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #
def resolve_final_answers(
    manifests: list,
    home: dict[str, dict[str, Any]],
    project_committed: dict[str, dict[str, Any]],
    user_choices: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]], list[SetupError]]:
    """Resolve the final coerced answer map for all enabled modules.

    Parameters
    ----------
    manifests:
        Enabled ``ModuleManifest`` instances.
    home:
        Answers from the home config (``~/.config/project-setup/config.toml``),
        keyed by module id.
    project_committed:
        Answers from ``.project-setup/answers.toml``, keyed by module id.
    user_choices:
        Answers from the CLI interview (highest precedence), keyed by module id.

    Returns
    -------
    (answers, provenance_map, errors):
        ``answers`` — per-module dict of coerced final values.
        ``provenance_map`` — per-module per-key Provenance string.
        ``errors`` — accumulated INPUT_VALUE_INVALID errors (not raised here).
    """
    manifest_defaults = _manifest_defaults(manifests)

    # Build a type-lookup: module_id -> input_key -> input_type_str
    type_map: dict[str, dict[str, str]] = {}
    for m in manifests:
        type_map[m.id] = {inp.key: inp.type.value for inp in m.inputs}

    final_answers: dict[str, dict[str, Any]] = {}
    final_provenance: dict[str, dict[str, str]] = {}
    all_errors: list[SetupError] = []

    for m in manifests:
        mod_id = m.id
        defaults = manifest_defaults.get(mod_id, {})
        home_vals = home.get(mod_id, {})
        project_vals = project_committed.get(mod_id, {})
        user_vals = user_choices.get(mod_id, {})

        # Layer: start with defaults, merge up
        merged: dict[str, Any] = {}
        prov: dict[str, str] = {}

        # 1. Manifest defaults (lowest)
        for k, v in defaults.items():
            merged[k] = v
            prov[k] = Provenance.DEFAULT.value

        # 2. Home config
        for k, v in home_vals.items():
            merged[k] = v
            prov[k] = Provenance.HOME.value

        # 3. Project committed answers
        for k, v in project_vals.items():
            merged[k] = v
            prov[k] = Provenance.PROJECT.value

        # 4. User choices (highest)
        for k, v in user_vals.items():
            merged[k] = v
            prov[k] = Provenance.FLAG.value

        # Coerce each value to its declared type (once)
        coerced: dict[str, Any] = {}
        mod_types = type_map.get(mod_id, {})
        for k, v in merged.items():
            input_type = mod_types.get(k)
            if input_type:
                coerced_val, err = _coerce_value(k, v, input_type, mod_id)
                if err:
                    all_errors.append(err)
                coerced[k] = coerced_val
            else:
                coerced[k] = v

        final_answers[mod_id] = coerced
        final_provenance[mod_id] = prov

    return final_answers, final_provenance, all_errors
