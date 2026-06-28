"""Persistence — write .project-setup/sources.toml and answers.toml.

Writes the two committed project files that encode what was set up and what
answers were chosen.  These are the ONLY committed artifacts the runner
produces; all runtime artifacts (frozen plan, fetched source checkouts) stay
in ``~/.cache/project-setup/``.

Schema (shared-contracts.md §8 / data-model.md):

  .project-setup/sources.toml
  ----------------------------
  [meta]
  skill_version = "0.3.0"   # advisory

  [[source]]
  locator = "github.com/me/mods"
  ref     = "main"
  subdir  = "modules"

  .project-setup/answers.toml
  ---------------------------
  [module.core-identity]
  name = "acme-api"

  [module.core-identity.source]   # parallel per-key provenance
  name = "flag"

Provenance assignment rules:
  - Modules may only emit: default | derived | agent-steered
  - This module assigns: flag | home | project
  - The ``provenance_map`` from ``answers.resolve_final_answers()`` tells us
    which layer each key won at (default/home/project/flag); we copy those
    verbatim since they are already the persistence-assigned values.

Dependencies:
  None. TOML is written by a small stdlib-only emitter (``_write_toml`` below)
  that handles exactly the shapes this module produces and round-trips through
  stdlib ``tomllib``. The runner core stays dependency-free (only ``uv`` itself
  is required), which also keeps it working under the CI invocation
  ``uv run --with pytest pytest`` (which does not provision third-party deps).

Standard library only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Sibling runner modules import by plain name; the runner dir is on sys.path via
# the entry point (cli.py / conftest.py / executor PYTHONPATH — spec 005 OQ-2).
import contracts as _contracts
import paths as _paths_mod

Provenance = _contracts.Provenance
project_setup_dir = _paths_mod.project_setup_dir


# --------------------------------------------------------------------------- #
# Internal TOML writer                                                         #
# --------------------------------------------------------------------------- #
def _toml_str(s: str) -> str:
    """Encode a Python str as a TOML basic string with correct escaping.

    Covers the escapes the TOML spec requires for basic strings; sufficient for
    our values (locators, refs, answer scalars, provenance strings). Control
    chars below 0x20 (other than the named ones) use the \\uXXXX form.
    """
    out = ['"']
    for ch in s:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\b":
            out.append("\\b")
        elif ch == "\f":
            out.append("\\f")
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04X}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _toml_scalar(v: Any) -> str:
    """Render a scalar/list TOML value. Booleans before ints (bool is an int)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return _toml_str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_toml_scalar(item) for item in v) + "]"
    raise TypeError(f"unsupported TOML value type: {type(v).__name__}")


def _bare_or_quoted_key(key: str) -> str:
    """A TOML key: bare if it matches [A-Za-z0-9_-]+, else a quoted key."""
    import re as _re

    if _re.fullmatch(r"[A-Za-z0-9_-]+", key):
        return key
    return _toml_str(key)


def _emit_table(lines: list[str], header: str, table: dict[str, Any]) -> None:
    """Emit one ``[header]`` table with its scalar/list keys, then recurse into
    nested-dict children as ``[header.child]`` sub-tables. Insertion order is
    preserved so callers control determinism by ordering the dict.
    """
    scalars = {k: v for k, v in table.items() if not isinstance(v, dict)}
    children = {k: v for k, v in table.items() if isinstance(v, dict)}
    if header:
        lines.append(f"[{header}]")
    for k, v in scalars.items():
        lines.append(f"{_bare_or_quoted_key(k)} = {_toml_scalar(v)}")
    if header and scalars:
        lines.append("")
    for child_key, child in children.items():
        child_header = f"{header}.{_bare_or_quoted_key(child_key)}" if header else _bare_or_quoted_key(child_key)
        _emit_table(lines, child_header, child)


def _write_toml(path: Path, data: dict[str, Any]) -> None:
    """Write *data* as TOML using a small, deterministic, stdlib-only emitter.

    Supports exactly the shapes this module produces: top-level scalar keys,
    nested ``[table]`` / ``[table.sub]`` dicts, and an array-of-tables under a
    list-of-dicts key (rendered as repeated ``[[key]]``). No third-party dep, so
    the runner core stays dependency-free (only ``uv`` itself is required) and
    works under the CI invocation ``uv run --with pytest pytest`` which does NOT
    provide ``tomli-w``. Round-trips through stdlib ``tomllib`` (read side).
    """
    lines: list[str] = []
    # Top-level scalars first.
    top_scalars = {k: v for k, v in data.items() if not isinstance(v, (dict, list))}
    for k, v in top_scalars.items():
        lines.append(f"{_bare_or_quoted_key(k)} = {_toml_scalar(v)}")
    if top_scalars:
        lines.append("")
    # Then dict tables and array-of-tables, in insertion order.
    for key, val in data.items():
        if isinstance(val, dict):
            _emit_table(lines, _bare_or_quoted_key(key), val)
            lines.append("")
        elif isinstance(val, list) and val and all(isinstance(item, dict) for item in val):
            for item in val:
                lines.append(f"[[{_bare_or_quoted_key(key)}]]")
                _emit_table(lines, "", item)
                lines.append("")
    text = "\n".join(lines).rstrip("\n") + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------- #
# skill_version drift warning                                                  #
# --------------------------------------------------------------------------- #
def _check_skill_version_drift(
    committed_version: str | None,
    current_version: str | None,
) -> str | None:
    """Return a warning message if the committed skill_version differs from
    the currently installed skill version.  Returns ``None`` if no drift.
    """
    if committed_version and current_version and committed_version != current_version:
        return (
            f"Advisory: committed sources.toml was created with skill "
            f"version {committed_version!r}; current version is "
            f"{current_version!r}.  Review changes before proceeding."
        )
    return None


# --------------------------------------------------------------------------- #
# write_sources_toml                                                           #
# --------------------------------------------------------------------------- #
def write_sources_toml(
    project_dir: Path,
    sources: list[dict[str, Any]],
    skill_version: str = "",
) -> Path:
    """Write ``.project-setup/sources.toml``.

    Parameters
    ----------
    project_dir:
        The project root directory.
    sources:
        List of source records, each with at least ``locator`` and optional
        ``ref`` and ``subdir`` keys.
    skill_version:
        Advisory version string embedded in ``[meta]`` (not enforced on
        re-run; used only for drift warning).

    Returns
    -------
    Path
        The path written.
    """
    psd = project_setup_dir(project_dir)
    dest = psd / "sources.toml"

    data: dict[str, Any] = {}
    if skill_version:
        data["meta"] = {"skill_version": skill_version}
    if sources:
        data["source"] = []
        for src in sources:
            record: dict[str, Any] = {"locator": src.get("locator", "")}
            if src.get("ref"):
                record["ref"] = src["ref"]
            if src.get("subdir"):
                record["subdir"] = src["subdir"]
            data["source"].append(record)

    _write_toml(dest, data)
    return dest


# --------------------------------------------------------------------------- #
# write_answers_toml                                                           #
# --------------------------------------------------------------------------- #
def write_answers_toml(
    project_dir: Path,
    answers: dict[str, dict[str, Any]],
    provenance_map: dict[str, dict[str, str]],
) -> Path:
    """Write ``.project-setup/answers.toml``.

    Parameters
    ----------
    project_dir:
        The project root directory.
    answers:
        Per-module answer dicts.  Keys: module id → {answer_key: value}.
    provenance_map:
        Per-module per-key provenance strings.  Same structure as *answers*
        but values are provenance strings (from ``Provenance`` enum values).
        These are written to the parallel ``[module.<id>.source]`` sub-table.

    Returns
    -------
    Path
        The path written.
    """
    psd = project_setup_dir(project_dir)
    dest = psd / "answers.toml"

    # TOML structure: flat dict to be serialized
    # We build a nested dict: {"module": {"core-identity": {...values...},
    #                                      "core-identity.source": {...}}}
    # The stdlib _write_toml emitter renders nested dicts as [module.<id>]
    # tables with [module.<id>.source] sub-tables for provenance.
    # Build a properly NESTED dict so the emitter renders [module.<id>] and a
    # parallel [module.<id>.source] sub-table. The provenance goes UNDER the
    # module's own table as a nested "source" dict (not a flat "<id>.source"
    # key, which would mis-render — and would break if an id ever contained a
    # dot). The emitter writes a table's scalar keys before recursing into its
    # nested-dict children, so values land in [module.<id>] and provenance in
    # [module.<id>.source].
    module_data: dict[str, Any] = {}
    for mod_id, mod_answers in answers.items():
        entry: dict[str, Any] = dict(mod_answers)
        mod_prov = provenance_map.get(mod_id, {})
        if mod_prov:
            entry["source"] = dict(mod_prov)
        module_data[mod_id] = entry

    data: dict[str, Any] = {}
    if module_data:
        data["module"] = module_data

    _write_toml(dest, data)
    return dest


# --------------------------------------------------------------------------- #
# write_modules_enabled                                                        #
# --------------------------------------------------------------------------- #
def write_modules_enabled(
    project_dir: Path,
    enabled_ids: list[str],
    provenance: str = "default",
) -> Path:
    """Append / overwrite the ``[modules]`` table in ``.project-setup/answers.toml``.

    The ``[modules] enabled = [...]`` record is the canonical persistence of the
    resolved enablement set (FR-004).  It is written as a top-level ``[modules]``
    table alongside ``[module.*]`` answer tables.  The provenance string is stored
    under ``[modules.source] enabled = <provenance>`` so reproduce can see how the
    set was determined.

    This helper reads the existing answers.toml (if any), injects/replaces the
    ``[modules]`` section, and rewrites the file — preserving all ``[module.*]``
    content unchanged.

    Parameters
    ----------
    project_dir:
        The project root directory.
    enabled_ids:
        Sorted list of enabled module ids to persist.
    provenance:
        How the enabled set was determined: ``"default"`` (base only) or
        ``"agent-steered"`` (agent proposed + user confirmed).

    Returns
    -------
    Path
        The path written.
    """
    import tomllib as _tomllib

    psd = project_setup_dir(project_dir)
    dest = psd / "answers.toml"

    # Read existing answers.toml (if any) to preserve module answers
    existing_module_data: dict[str, Any] = {}
    if dest.is_file():
        try:
            with open(dest, "rb") as fh:
                existing = _tomllib.load(fh)
            existing_module_data = existing.get("module", {})
        except Exception:
            pass  # If unreadable, write fresh

    # Build output: modules section first (enablement metadata), then module answers
    data: dict[str, Any] = {}

    # [modules] table with enablement record
    modules_section: dict[str, Any] = {
        "enabled": sorted(enabled_ids),
        "source": {"enabled": provenance},
    }
    data["modules"] = modules_section

    # Preserve existing [module.*] answer tables
    if existing_module_data:
        data["module"] = existing_module_data

    _write_toml(dest, data)
    return dest


# --------------------------------------------------------------------------- #
# merge_module_answers_to_persist                                              #
# --------------------------------------------------------------------------- #
def merge_module_answers_to_persist(
    answers: dict[str, dict[str, Any]],
    provenance_map: dict[str, dict[str, str]],
    step_outcomes: list[Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]]]:
    """Fold ``answers_to_persist`` from step outcomes into the resolved maps.

    Modules may emit additional derived/agent-steered answers in their
    result.  These override the interview answers for the same key (runtime
    values win over pre-flight answers for persistence purposes).

    Parameters
    ----------
    answers:
        The resolved answer map from the interview phase.
    provenance_map:
        The resolved provenance map from the interview phase.
    step_outcomes:
        ``StepOutcome`` instances collected during execution.

    Returns
    -------
    (updated_answers, updated_provenance_map)
    """
    merged_answers = {k: dict(v) for k, v in answers.items()}
    merged_prov = {k: dict(v) for k, v in provenance_map.items()}

    for outcome in step_outcomes:
        if not outcome.ok or outcome.result is None:
            continue
        mod_id = outcome.module_id
        atp = outcome.result.get("answers_to_persist", {})
        if not atp:
            continue
        if mod_id not in merged_answers:
            merged_answers[mod_id] = {}
        if mod_id not in merged_prov:
            merged_prov[mod_id] = {}
        for key, entry in atp.items():
            merged_answers[mod_id][key] = entry.get("value")
            source = entry.get("source")
            if source:
                merged_prov[mod_id][key] = str(source)

    return merged_answers, merged_prov


# --------------------------------------------------------------------------- #
# ensure_gitignore_pytest_entry                                                #
# --------------------------------------------------------------------------- #
def ensure_gitignore_pytest_entry(project_dir: Path) -> bool:
    """Add pytest artifact entries to ``.gitignore`` if absent.

    Only writes entries for ``.pytest_cache/`` and ``__pycache__/``; does not
    touch any other gitignore content.  Idempotent.

    Returns ``True`` if the file was modified, ``False`` if already present or
    no gitignore exists (we do NOT create a fresh one here).
    """
    gitignore = project_dir / ".gitignore"
    if not gitignore.exists():
        return False

    content = gitignore.read_text(encoding="utf-8")
    to_add = []
    for entry in (".pytest_cache/", "__pycache__/"):
        if entry not in content:
            to_add.append(entry)

    if not to_add:
        return False

    addition = "\n# pytest artifacts (project-setup runner)\n"
    for e in to_add:
        addition += e + "\n"

    gitignore.write_text(content.rstrip("\n") + "\n" + addition, encoding="utf-8")
    return True


# --------------------------------------------------------------------------- #
# check_sources_drift                                                          #
# --------------------------------------------------------------------------- #
def check_sources_drift(
    project_dir: Path,
    current_skill_version: str | None = None,
) -> str | None:
    """Read the committed sources.toml and check for skill_version drift.

    Returns a warning string if drift is detected, else ``None``.
    """
    import tomllib

    sources_toml = project_setup_dir(project_dir) / "sources.toml"
    if not sources_toml.is_file():
        return None
    try:
        with open(sources_toml, "rb") as fh:
            data = tomllib.load(fh)
    except Exception:
        return None

    committed_version = data.get("meta", {}).get("skill_version")
    return _check_skill_version_drift(committed_version, current_skill_version)
