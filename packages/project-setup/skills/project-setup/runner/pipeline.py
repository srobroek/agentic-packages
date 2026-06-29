"""8-stage pipeline spine for the project-setup runner.

Stages (in order):
  1. resolve_sources  — read .project-setup/sources.toml (reproduce) or
                        accept caller-supplied sources (init)
  2. fetch            — git-fetch each source into the cache
  3. discover         — walk all roots in precedence order, apply collision rules
  4. interview        — manifest-driven interview via io_adapter
  5. validate_closed  — the ONE gate (order + missing answers + missing tools)
  6. build_freeze     — assemble ExecutionPlan, freeze to cache
  7. execute          — run each step via executor / reproduce
  8. persist          — write .project-setup/{sources,answers}.toml

Mode detection: if ``.project-setup/sources.toml`` exists in *project_dir*
the pipeline runs in ``"reproduce"`` mode (committed answers are loaded as
the project layer); otherwise ``"init"``.

This module is pure orchestration — it wires everything together but does
not implement any domain logic itself.

Standard library only (the entire runner core is dependency-free; only ``uv``
itself is required at runtime).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Sibling runner modules import by plain name; the runner dir is on sys.path via
# the entry point (cli.py / conftest.py / executor PYTHONPATH — spec 005 OQ-2).
# The sources/ dir is also on sys.path, so sources sub-modules import by bare name.
import contracts as _contracts
import paths as _paths_mod
import manifest as _manifest_mod
import answers as _answers_mod
import validate as _validate_mod
import plan as _plan_mod
import mode as _mode_mod
import executor as _executor_mod
import reproduce as _reproduce_mod
import persist as _persist_mod
import enablement as _enablement_mod
import sdk as _sdk_mod
import discover as _discover_mod
import fetch as _fetch_mod
import locator as _locator_mod

GateFailure = _contracts.GateFailure
SetupError = _contracts.SetupError
ErrorCode = _contracts.ErrorCode
plugin_root = _paths_mod.plugin_root
frozen_plan_path = _paths_mod.frozen_plan_path
project_setup_dir = _paths_mod.project_setup_dir

parse_manifest = _manifest_mod.parse_manifest
resolve_final_answers = _answers_mod.resolve_final_answers
validate_closed = _validate_mod.validate_closed
build_plan = _plan_mod.build_plan
freeze = _plan_mod.freeze
detect_mode = _mode_mod.detect_mode
looks_like_secret = _sdk_mod.looks_like_secret  # G8 secret-shape detection (spec 004)
build_drift_report = _reproduce_mod.build_drift_report
apply_reproduce = _reproduce_mod.apply
run_agent_phase = _reproduce_mod.run_agent_phase
whole_plan_gate = _reproduce_mod.whole_plan_gate  # G1 whole-plan preview (spec 004)
warn_conflicts = _reproduce_mod.warn_conflicts    # G7 cross-module conflict review (spec 004)

write_sources_toml = _persist_mod.write_sources_toml
write_answers_toml = _persist_mod.write_answers_toml
write_modules_enabled = _persist_mod.write_modules_enabled
merge_module_answers_to_persist = _persist_mod.merge_module_answers_to_persist
ensure_gitignore_pytest_entry = _persist_mod.ensure_gitignore_pytest_entry
check_sources_drift = _persist_mod.check_sources_drift

resolve_enabled_modules = _enablement_mod.resolve_enabled_modules

build_discovery_roots = _discover_mod.build_discovery_roots
discover_modules = _discover_mod.discover_modules
fetch_source = _fetch_mod.fetch_source
parse_locator = _locator_mod.parse_locator


# --------------------------------------------------------------------------- #
# Source-pin validation (FR-001, FR-002, FR-003 — spec 014)                   #
# --------------------------------------------------------------------------- #

def validate_sources_schema(sources: list[dict]) -> list[SetupError]:
    """Validate the SHAPE of each source record (FR-C1).

    Detects mis-keyed records BEFORE pin validation so authors get a clear,
    actionable error instead of a silent skip.

    Checks (in order per record):
    1. If the dict has an ``id`` or ``git`` key (but no ``locator``) → the
       author used the legacy/wrong schema.  Emit ``SOURCES_SCHEMA_INVALID``.
    2. If the dict is missing ``locator`` entirely (and not the above case) →
       ``SOURCES_SCHEMA_INVALID`` for missing required key.
    3. Otherwise the shape is acceptable (``locator`` present); pin validation
       runs next.

    Parameters
    ----------
    sources:
        Raw source records as parsed from the TOML (before any pin check).

    Returns
    -------
    list[SetupError]
        One ``SOURCES_SCHEMA_INVALID`` error per bad record; empty when all
        records carry a ``locator`` key.
    """
    errors: list[SetupError] = []
    for i, src in enumerate(sources):
        if not isinstance(src, dict):
            errors.append(SetupError(
                error_code=ErrorCode.SOURCES_SCHEMA_INVALID,
                expected="[[source]] record as a TOML table (dict)",
                received=repr(src),
                how_to_fix=(
                    "Each source must be a [[source]] table with a `locator` key "
                    "(+ optional ref, subdir). Example:\n"
                    "  [[source]]\n"
                    "  locator = \"github.com/org/repo\"\n"
                    "  ref     = \"v1.0.0\""
                ),
            ))
            continue
        has_locator = "locator" in src
        has_id = "id" in src
        has_git = "git" in src
        if not has_locator and (has_id or has_git):
            # Legacy / wrong schema: user wrote [[sources]] with id/git keys.
            received_keys = ", ".join(sorted(src.keys()))
            errors.append(SetupError(
                error_code=ErrorCode.SOURCES_SCHEMA_INVALID,
                expected="[[source]] record with a `locator` key (+ optional ref, subdir)",
                received=f"source record #{i} uses unknown keys: {{{received_keys}}}",
                how_to_fix=(
                    "source record uses an unknown schema (id/git); use [[source]] "
                    "with a `locator` key (+ optional ref, subdir). Example:\n"
                    "  [[source]]\n"
                    "  locator = \"github.com/org/repo\"\n"
                    "  ref     = \"v1.0.0\""
                ),
            ))
        elif not has_locator:
            received_keys = ", ".join(sorted(src.keys())) if src else "(empty)"
            errors.append(SetupError(
                error_code=ErrorCode.SOURCES_SCHEMA_INVALID,
                expected="[[source]] record with a `locator` key",
                received=f"source record #{i} missing required `locator`; keys present: {{{received_keys}}}",
                how_to_fix=(
                    "source record missing required `locator`. Add the locator field:\n"
                    "  [[source]]\n"
                    "  locator = \"github.com/org/repo\"\n"
                    "  ref     = \"v1.0.0\""
                ),
            ))
    return errors


def validate_sources(sources: list[dict]) -> list[SetupError]:
    """Validate sources.toml records: schema first, then ref-pin check.

    Combines schema validation (``validate_sources_schema``) with the existing
    ref-pin check so callers see ALL problems in one pass.

    Schema errors (``SOURCES_SCHEMA_INVALID``) are returned first; if any exist
    the pin check is skipped for that record (it has no ``locator`` to check).
    Records that pass schema validation are then checked for ref pinning
    (``ORG_SOURCE_UNPINNED``).

    A git source is considered unpinned — and rejected with
    ``ORG_SOURCE_UNPINNED`` — when ALL of the following hold:

    1. Its locator resolves to ``kind="git"`` (remote git repository).
    2. The source dict has no ``"ref"`` key (or the value is empty/falsy).
    3. The locator string contains no ``"#"`` fragment (no inline ref pin).

    Any source that has an explicit ``ref`` field, a ``#ref`` fragment in the
    locator, or is a local-path source (``kind="local"``) passes unconditionally.

    Parameters
    ----------
    sources:
        The assembled ``all_sources`` list (committed + extra_sources).

    Returns
    -------
    list[SetupError]
        Schema errors first, then one ``ORG_SOURCE_UNPINNED`` per unpinned git
        source; empty list when all records are valid and properly pinned.
    """
    errors: list[SetupError] = []

    # Phase 1: schema validation — detect mis-keyed records loudly.
    schema_errors = validate_sources_schema(sources)
    errors.extend(schema_errors)

    # Collect the indices of records that failed schema validation so we skip
    # pin-checking them (they have no usable locator).
    bad_indices = set()
    if schema_errors:
        # Rebuild the set: any record without a 'locator' key failed schema.
        for i, src in enumerate(sources):
            if not isinstance(src, dict) or "locator" not in src:
                bad_indices.add(i)

    # Phase 2: ref-pin check for records that passed schema validation.
    for i, src in enumerate(sources):
        if i in bad_indices:
            continue
        locator_str = src.get("locator", "")
        if not locator_str:
            continue
        # Fast reject: if the dict already has an explicit ref field, it's pinned.
        if src.get("ref"):
            continue
        # Fast reject: if the locator string has a '#' fragment, it's pinned.
        if "#" in locator_str:
            continue
        # Parse the locator to distinguish git from local sources.
        try:
            loc = parse_locator(locator_str)
        except Exception:
            # Unparseable locators are skipped here; fetch will handle them.
            continue
        if loc.kind != "git":
            # Local-path sources are exempt (FR-001).
            continue
        # At this point: git source, no ref field, no fragment — unpinned.
        errors.append(SetupError(
            error_code=ErrorCode.ORG_SOURCE_UNPINNED,
            expected="explicit git ref (tag or SHA) for source",
            received=locator_str,
            how_to_fix=(
                f"Pin the org source to an immutable ref: add ref=\"vX.Y.Z\" "
                f"to the [[source]] record or use {locator_str}#vX.Y.Z. "
                f"Unpinned git sources are a supply-chain risk."
            ),
        ))
    return errors


# --------------------------------------------------------------------------- #
# Pipeline result                                                              #
# --------------------------------------------------------------------------- #
@dataclass
class PipelineResult:
    """Summary of a completed pipeline run."""

    mode: str
    success: bool
    errors: list[SetupError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    modules_executed: list[str] = field(default_factory=list)
    enabled_modules: list[str] = field(default_factory=list)
    files_written: list[str] = field(default_factory=list)
    plan_path: Path | None = None
    sources_toml_path: Path | None = None
    answers_toml_path: Path | None = None
    dry_run: bool = False


# --------------------------------------------------------------------------- #
# Helper: read committed sources.toml                                          #
# --------------------------------------------------------------------------- #
def _read_committed_sources(project_dir: Path) -> list[dict[str, Any]]:
    """Parse .project-setup/sources.toml and return the [[source]] records.

    Raises ``SetupError(SOURCES_SCHEMA_INVALID)`` if the file uses the WRONG
    top-level key ``[[sources]]`` (plural) instead of the correct ``[[source]]``
    (singular).  This is a loud, un-ignorable error — a silent empty-return
    would hide a misconfigured sources file and leave the user confused about
    why their addon modules never appear.
    """
    src_toml = project_setup_dir(project_dir) / "sources.toml"
    if not src_toml.is_file():
        return []
    try:
        with open(src_toml, "rb") as fh:
            data = tomllib.load(fh)
    except Exception:
        return []
    # FR-C1: detect [[sources]] (plural) — the most common authoring mistake.
    if "sources" in data and "source" not in data:
        raise SetupError(
            error_code=ErrorCode.SOURCES_SCHEMA_INVALID,
            expected="top-level [[source]] table (singular)",
            received="top-level [[sources]] table (plural) in sources.toml",
            how_to_fix=(
                "found [[sources]] — the correct table is [[source]] (singular). "
                "Rename every [[sources]] entry to [[source]] in "
                ".project-setup/sources.toml."
            ),
        )
    # Also warn if both keys exist (partial migration) — treat as schema error.
    if "sources" in data and "source" in data:
        raise SetupError(
            error_code=ErrorCode.SOURCES_SCHEMA_INVALID,
            expected="only [[source]] table (singular) — no [[sources]] (plural)",
            received="both [[source]] and [[sources]] keys found in sources.toml",
            how_to_fix=(
                "sources.toml contains both [[source]] and [[sources]] tables. "
                "Remove all [[sources]] (plural) entries; the correct key is "
                "[[source]] (singular)."
            ),
        )
    return list(data.get("source", []))


def _read_committed_answers(project_dir: Path) -> dict[str, dict[str, Any]]:
    """Parse .project-setup/answers.toml and return per-module answer dicts."""
    ans_toml = project_setup_dir(project_dir) / "answers.toml"
    if not ans_toml.is_file():
        return {}
    try:
        with open(ans_toml, "rb") as fh:
            data = tomllib.load(fh)
    except Exception:
        return {}
    # Structure: {module: {mod_id: {key: value, source: {provenance}}, ...}}
    # The nested "source" sub-table is the per-key provenance record — it is NOT
    # an answer value and must be stripped before the dict is used as answers.
    module_section = data.get("module", {})
    answers: dict[str, dict[str, Any]] = {}
    for key, val in module_section.items():
        if isinstance(val, dict) and "." not in key:
            # Strip the reserved "source" provenance sub-table; it must not be
            # treated as an answer value and must not bleed into final_answers.
            answers[key] = {k: v for k, v in val.items() if k != "source"}
    return answers


def _read_committed_enabled(project_dir: Path) -> list[str] | None:
    """Read [modules].enabled from .project-setup/answers.toml.

    Returns the list of explicitly-enabled module ids, or None if the key is
    absent (meaning: rely on defaults only).
    """
    ans_toml = project_setup_dir(project_dir) / "answers.toml"
    if not ans_toml.is_file():
        return None
    try:
        with open(ans_toml, "rb") as fh:
            data = tomllib.load(fh)
    except Exception:
        return None
    modules_section = data.get("modules", {})
    enabled = modules_section.get("enabled")
    if isinstance(enabled, list):
        return [str(x) for x in enabled]
    return None


# --------------------------------------------------------------------------- #
# Helper: interview one module                                                 #
# --------------------------------------------------------------------------- #
def _interview_module(
    manifest: Any,
    current_answers: dict[str, Any],
    io: Any,
    non_interactive: bool,
) -> dict[str, Any]:
    """Prompt for all declared inputs of a module, respecting current_answers."""
    collected: dict[str, Any] = {}
    for inp in manifest.inputs:
        key = inp.key
        default = current_answers.get(key, inp.default)

        # Map InputSpec to a dict for io.ask
        input_spec = {
            "key": key,
            # FR-003: disambiguate shared keys across modules. getattr-guarded so a
            # minimal manifest stub (e.g. the G8 interview unit tests) without `.id`
            # still works — production ModuleManifest always provides the `.id` property.
            "module_id": getattr(manifest, "id", ""),
            "type": getattr(inp.type, "value", str(inp.type)),
            "prompt": inp.prompt,
            "choices": inp.choices,
            "required": inp.required,
        }

        if non_interactive:
            # Non-interactive still consults the IO so PROVIDED answers (e.g. a
            # ScriptedIO map, or flags) are honored — it just must not BLOCK on
            # stdin. ScriptedIO returns scripted answers (falling back to the
            # supplied default); a non-interactive TerminalIO returns the
            # default without prompting. Only fall back to a bare default when
            # the IO does not implement a non-blocking ask.
            ask_ni = getattr(io, "ask_non_interactive", None)
            if callable(ask_ni):
                value = ask_ni(input_spec, default)
            else:
                value = io.ask(input_spec, default)
        else:
            value = io.ask(input_spec, default)

        # FR-012: do NOT promote a value to "flag" (user-choice) provenance when
        # the user has only echoed back the existing committed/home value or the
        # bare manifest default — neither case represents an active user decision:
        #
        #   (a) key in current_answers and value == current_answers[key]:
        #       The user accepted the committed/home value unchanged (e.g. hit
        #       enter).  The answer is already covered by the "project"/"home"
        #       layer in resolve_final_answers; adding it to user_choices would
        #       re-stamp it as "flag" and mask the true provenance on re-runs.
        #
        #   (b) key not in current_answers and value == inp.default:
        #       The answer was never committed.  The interview echoed the manifest
        #       default unchanged; that is not a committed decision, just the
        #       fallback.  resolve_final_answers already applies manifest defaults
        #       via the layering model, so persisting this would be both redundant
        #       and harmful (FR-012: spuriously adds a never-committed key).
        #
        # In both cases the value is already captured by a lower-precedence layer
        # and does not need to be in user_choices.  If the user actively types a
        # different value, value != the baseline and it IS a real choice, kept.
        if key in current_answers:
            if value == current_answers[key]:
                continue  # user accepted committed value unchanged; not a new choice
        else:
            if value == inp.default:
                continue  # user accepted manifest default; not a committed decision

        # G8 — secret-detected abort (spec 004 FR-018/019). A value matching a known
        # credential shape is REFUSED: it is dropped (never added to `collected`, so
        # it never reaches answers.toml), and the user is told to rotate it. A
        # required input then surfaces as MISSING_ANSWER at the validate-closed gate
        # — the correct, actionable failure. An input declaring allow_secret=true
        # opts out (the rare legitimately-secret-shaped non-secret).
        if value is not None and not getattr(inp, "allow_secret", False):
            label = looks_like_secret(value)
            if label is not None:
                io.notify(
                    f"[SECRET] input '{key}' looks like a secret ({label}). It will "
                    f"NOT be persisted — treat it as compromised and rotate it. "
                    f"Secrets belong in the environment or a secret manager, never "
                    f"in .project-setup/answers.toml."
                )
                continue  # drop the value entirely

        if value is not None:
            collected[key] = value

    return collected


# --------------------------------------------------------------------------- #
# Main pipeline                                                                #
# --------------------------------------------------------------------------- #
def run_pipeline(
    project_dir: Path,
    io: Any,
    *,
    extra_sources: list[dict[str, Any]] | None = None,
    skill_version: str = "",
    non_interactive: bool = False,
    dry_run: bool = False,
    plugin_root_path: Path | None = None,
    plan_path: Path | None = None,
    env: dict[str, str] | None = None,
    refresh: list[str] | None = None,
    active_flags: frozenset[str] | None = None,
) -> PipelineResult:
    """Run the 8-stage project-setup pipeline.

    Parameters
    ----------
    project_dir:
        The project root to set up.
    io:
        An ``InterviewIO`` implementation (terminal or scripted for tests).
    extra_sources:
        Additional source records to include (caller-supplied for init mode).
    skill_version:
        The currently installed skill version (advisory; written to sources.toml).
    non_interactive:
        If True, skip all prompts and use defaults.
    dry_run:
        If True, run stages 1–5 (through plan freeze) but skip execute+persist.
    plugin_root_path:
        Override plugin root (tests inject a tmp path).
    plan_path:
        Override frozen plan path (tests inject a tmp path).
    env:
        Optional environment overrides for subprocess calls.
    refresh:
        Optional list of ``<module>`` or ``<module>.<key>`` tokens. In reproduce
        mode these are the ONLY agent steps re-invoked (re-researched); every
        other agent step replays its committed decision with zero network. Each
        refreshed module is gated by an old-vs-new diff confirm. Ignored in init
        mode (init always invokes agents). See spec 003 FR-010.

    Returns
    -------
    PipelineResult
    """
    project_dir = Path(project_dir).resolve()
    if plugin_root_path is None:
        plugin_root_path = plugin_root()
    if plan_path is None:
        plan_path = frozen_plan_path()

    result = PipelineResult(mode="init", success=False, dry_run=dry_run)

    # ── Stage 0: detect mode ────────────────────────────────────────────────── #
    mode = detect_mode(project_dir)
    result.mode = mode

    # Advisory skill_version drift warning in reproduce mode
    drift_warning = check_sources_drift(project_dir, skill_version)
    if drift_warning:
        result.warnings.append(drift_warning)
        io.notify(f"[WARN] {drift_warning}")

    # ── Stage 1: resolve sources ─────────────────────────────────────────────── #
    committed_sources: list[dict[str, Any]] = []
    if mode == "reproduce":
        try:
            committed_sources = _read_committed_sources(project_dir)
        except SetupError as exc:
            result.errors.append(exc)
            result.success = False
            io.notify(f"[ERROR] {exc.how_to_fix}")
            return result

    all_sources = list(committed_sources)
    if extra_sources:
        all_sources.extend(extra_sources)

    # Source-pin validation: reject unpinned git sources before any fetch (FR-002).
    source_errors = validate_sources(all_sources)
    if source_errors:
        result.errors.extend(source_errors)
        result.success = False
        for err in source_errors:
            io.notify(f"[ERROR] {err.how_to_fix}")
        return result

    # ── Stage 2: fetch sources into cache ──────────────────────────────────── #
    fetched_roots: list[Path] = []
    for src in all_sources:
        locator_str = src.get("locator", "")
        if not locator_str:
            continue
        try:
            import dataclasses as _dc
            locator = parse_locator(locator_str)
            # Inject ref/subdir overrides from the source record if present
            override: dict[str, str] = {}
            if src.get("ref"):
                override["ref"] = src["ref"]
            if src.get("subdir"):
                override["subdir"] = src["subdir"]
            if override:
                locator = _dc.replace(locator, **override)
            fetch_result = fetch_source(locator)
            if fetch_result.ok and fetch_result.root_path is not None:
                fetched_roots.append(fetch_result.root_path)
            elif not fetch_result.ok:
                msg = fetch_result.skipped_reason or "unknown fetch error"
                result.warnings.append(f"fetch warning: {msg}")
                io.notify(f"[WARN] fetch {locator_str}: {msg} (proceeding offline)")
        except Exception as exc:
            result.warnings.append(f"fetch error for {locator_str}: {exc}")
            io.notify(f"[WARN] fetch {locator_str} failed: {exc} (proceeding offline)")

    # ── Stage 3: discover modules ─────────────────────────────────────────── #
    # Derive the bundled modules root from the INJECTED plugin_root_path (not the
    # global __file__ resolver) so an explicitly-passed plugin root is honored
    # for discovery, not just execution.
    bundled = plugin_root_path / "modules"
    roots = build_discovery_roots(
        fetched_roots, project_dir=project_dir, bundled_dir=bundled
    )
    discovered, disc_report = discover_modules(roots, bundled_root=bundled)

    if disc_report.hard_errors:
        result.errors.extend(disc_report.hard_errors)
        result.success = False
        for err in disc_report.hard_errors:
            io.notify(f"[ERROR] {err.how_to_fix}")
        return result

    for shadow in disc_report.shadows:
        msg = (
            f"Shadow: module '{shadow['id']}' in {shadow['shadow_kind']} root "
            f"shadowed by {shadow['winner_kind']} root"
        )
        result.warnings.append(msg)
        io.notify(f"[WARN] {msg}")

    # Parse manifests for discovered modules. parse_manifest returns a single
    # ModuleManifest and accumulates problems in manifest.errors (it never
    # raises and never returns a tuple).
    manifests: list[Any] = []
    for mod_id, disc_mod in discovered.items():
        manifest = parse_manifest(disc_mod.manifest_path)
        if manifest.errors:
            for e in manifest.errors:
                io.notify(f"[WARN] manifest parse error for {mod_id}: {e.how_to_fix}")
            continue
        manifest._toml_path = str(disc_mod.manifest_path)
        manifests.append(manifest)

    # ── Stage 3b: enablement resolution ─────────────────────────────────────── #
    # Determine which modules are enabled (base defaults ∪ selection ∪ requires
    # closure). The selection source depends on mode:
    #   - reproduce: committed [modules].enabled from answers.toml (authoritative)
    #   - init: proposed_enabled from io answers under key "enabled" in a virtual
    #           "modules" answer namespace (agent-proposed; None = base-only)
    committed_enabled: list[str] | None = None
    if mode == "reproduce":
        committed_enabled = _read_committed_enabled(project_dir)

    # In init mode, accept a proposed list via ScriptedIO / agent answers.
    # The io may carry a "modules" answer dict with key "enabled" (a list of ids).
    # This is a lightweight channel: ScriptedIO callers supply it as
    #   answers={"enabled": ["lang-python", ...]}  under module id "modules".
    proposed_enabled: list[str] | None = None
    if mode == "init":
        # Ask for optional module selection via io — key is "enabled", type list.
        # Non-interactive callers that don't supply it get base-only (FR-007).
        _mod_sel_spec = {
            "key": "enabled",
            "module_id": "modules",  # FR-003: sentinel so FileAnswersIO can resolve the enabled list
            "type": "list",
            "prompt": "Optional modules to enable (space/comma-separated ids, or leave blank for base only):",
            "choices": None,
            "required": False,
        }
        _default_enabled: list[str] = []
        _ask_ni = getattr(io, "ask_non_interactive", None)
        if non_interactive and callable(_ask_ni):
            _raw = _ask_ni(_mod_sel_spec, _default_enabled)
        else:
            _raw = io.ask(_mod_sel_spec, _default_enabled)
        if isinstance(_raw, list) and _raw:
            proposed_enabled = [str(x) for x in _raw]
        elif isinstance(_raw, str) and _raw.strip():
            # Tolerate a comma/space-separated string from ScriptedIO
            import re as _re
            proposed_enabled = [x.strip() for x in _re.split(r"[,\s]+", _raw.strip()) if x.strip()]

    enabled_ids, en_errors = resolve_enabled_modules(
        manifests,
        committed_enabled=committed_enabled,
        proposed_enabled=proposed_enabled,
        mode=mode,
    )
    if en_errors:
        result.errors.extend(en_errors)
        result.success = False
        for err in en_errors:
            io.notify(f"[ERROR] {err.how_to_fix}")
        return result

    # Filter manifests to enabled set only — the remainder of the pipeline
    # (interview, validate, plan, execute) sees ONLY the enabled modules.
    manifests = [m for m in manifests if m.id in enabled_ids]
    result.enabled_modules = sorted(enabled_ids)

    # Determine enablement provenance for persistence
    if mode == "reproduce":
        _en_provenance = "project"
    elif proposed_enabled:
        _en_provenance = "agent-steered"
    else:
        _en_provenance = "default"

    # ── Stage 4: interview ───────────────────────────────────────────────────── #
    committed_answers = _read_committed_answers(project_dir) if mode == "reproduce" else {}

    # Home config answers
    home_answers: dict[str, dict[str, Any]] = {}
    home_cfg = _paths_mod.home_config_path()
    if home_cfg.is_file():
        try:
            with open(home_cfg, "rb") as fh:
                home_data = tomllib.load(fh)
            home_answers = home_data.get("module", {})
        except Exception:
            pass

    # Conduct the interview: gather user_choices from io
    user_choices: dict[str, dict[str, Any]] = {}
    for manifest in manifests:
        # Combine home + project answers as the current defaults
        current = dict(home_answers.get(manifest.id, {}))
        current.update(committed_answers.get(manifest.id, {}))
        chosen = _interview_module(manifest, current, io, non_interactive)
        if chosen:
            user_choices[manifest.id] = chosen

    # ── Stage 5: resolve + validate-closed ─────────────────────────────────── #
    final_answers, provenance_map, coerce_errors = resolve_final_answers(
        manifests,
        home=home_answers,
        project_committed=committed_answers,
        user_choices=user_choices,
    )
    if coerce_errors:
        result.warnings.extend(e.how_to_fix for e in coerce_errors)

    try:
        ordered_ids = validate_closed(manifests, final_answers)
    except GateFailure as gf:
        result.errors.extend(gf.errors)
        result.success = False
        for err in gf.errors:
            io.notify(f"[GATE ERROR] {err.how_to_fix}")
        return result

    # ── Stage 5b: Phase A — agent research/decision pass (two-phase plan) ────── #
    # Spec 003 Settled Decision H (option B): run every kind=agent step BEFORE the
    # plan is frozen, fold each agent-steered decision into the resolved answers,
    # then freeze ONCE so a Tier-1 python step reads the agent's pins through the
    # frozen plan. In plain reproduce this is a no-op for agent steps (committed
    # agent-steered answers are already in final_answers — zero-network replay,
    # FR-009); --refresh re-invokes only the named keys behind a diff gate (FR-010).
    # When NO module has an agent step, run_agent_phase returns the maps unchanged,
    # so non-Tier-2 runs are byte-identical to the prior single-freeze behavior.
    if not dry_run:
        final_answers, provenance_map = run_agent_phase(
            manifests,
            ordered_ids=ordered_ids,
            resolved_answers=final_answers,
            provenance_map=provenance_map,
            io=io,
            mode=mode,
            refresh=refresh,
        )

    # ── Stage 6: build + freeze plan (the single authoritative freeze) ───────── #
    plan = build_plan(
        manifests,
        resolved_answers=final_answers,
        ordered_ids=ordered_ids,
        mode=mode,
        plugin_root_path=plugin_root_path,
    )

    freeze(plan, path=plan_path)
    result.plan_path = plan_path

    # ── Dry run stops here ────────────────────────────────────────────────── #
    if dry_run:
        result.success = True
        io.notify("[DRY RUN] Plan frozen. No files written to project.")
        return result

    # ── Stage 7: execute ────────────────────────────────────────────────────── #
    # Both init and reproduce use the inspect→confirm→write flow so that
    # consequential steps are never executed without a confirm pass, and gate
    # steps carry non_interactive so CI safe-skips instead of deadlocking.
    #
    # Init vs reproduce differ in the WRITE-confirm shape (spec 004 G1, FR-009):
    #   - init: ONE whole-plan preview + aggregate confirm (G1); per-file prompts
    #     here would be the gates-analysis anti-pattern #1. The inspect pass runs
    #     non-interactively (interactive_per_diff=False) to gather the preview data,
    #     then G1 captures the single decision. Decline ⟹ abort, nothing written.
    #   - reproduce: the per-file write-confirm loop (the 001 behavior; G5 enriches
    #     the destructive-overwrite case in Phase 8).
    is_init = mode == "init"
    confirmations = build_drift_report(
        plan=plan,
        plugin_root_path=plugin_root_path,
        project_dir=project_dir,
        io=io,
        frozen_plan_path=plan_path,
        env=env,
        interactive_per_diff=not is_init,
        non_interactive=non_interactive,
    )
    # G7 — surface cross-module shared-file collisions (informational; never blocks,
    # both modes). Runs over the inspect data just gathered, before the G1 preview so
    # a user sees the collision in the same review.
    warn_conflicts(plan, confirmations, io)
    if is_init:
        proceed = whole_plan_gate(
            plan, confirmations, io, non_interactive=non_interactive
        )
        if not proceed:
            io.notify("[PLAN] declined at the whole-plan preview — nothing written.")
            result.success = True
            result.mode = mode
            return result
    step_outcomes = apply_reproduce(
        plan=plan,
        confirmations=confirmations,
        plugin_root_path=plugin_root_path,
        project_dir=project_dir,
        io=io,
        frozen_plan_path=plan_path,
        env=env,
        non_interactive=non_interactive,
        active_flags=active_flags,
        refresh=refresh,
    )

    # Collect file writes from outcomes
    for out in step_outcomes:
        if out.ok:
            result.files_written.extend(out.files_written())
            if out.module_id not in result.modules_executed:
                result.modules_executed.append(out.module_id)

    # ── Stage 8: persist ────────────────────────────────────────────────────── #
    # Merge runtime answers_to_persist back into the resolved maps
    final_answers, provenance_map = merge_module_answers_to_persist(
        final_answers, provenance_map, step_outcomes
    )

    sources_path = write_sources_toml(
        project_dir,
        sources=all_sources,
        skill_version=skill_version,
    )
    # FR-012: strip keys whose only provenance is the bare manifest default
    # ("default") before writing answers.toml.  Manifest defaults are always
    # recomputed from the manifest on every run (the layering model applies them
    # unconditionally) — persisting them is redundant and harmful: it causes
    # answers.toml to grow with never-committed default values, which violates
    # the FR-012 boundary when a reproduce_only advisory agent returns an empty
    # answers_to_persist.  Keys with provenance above "default" (home, project,
    # agent-steered, flag) represent real committed decisions and are kept.
    _DEFAULT_PROV = _contracts.Provenance.DEFAULT.value
    persist_answers: dict[str, dict[str, Any]] = {}
    persist_prov: dict[str, dict[str, str]] = {}
    for _mod_id, _mod_answers in final_answers.items():
        _mod_prov = provenance_map.get(_mod_id, {})
        _filtered = {
            k: v for k, v in _mod_answers.items()
            if _mod_prov.get(k, _DEFAULT_PROV) != _DEFAULT_PROV
        }
        _filtered_prov = {k: v for k, v in _mod_prov.items() if k in _filtered}
        if _filtered:
            persist_answers[_mod_id] = _filtered
            persist_prov[_mod_id] = _filtered_prov
    answers_path = write_answers_toml(
        project_dir,
        answers=persist_answers,
        provenance_map=persist_prov,
    )
    # Persist the resolved enabled set (FR-004): write [modules].enabled so
    # reproduce can replay the exact module set without re-grilling.
    write_modules_enabled(
        project_dir,
        enabled_ids=sorted(enabled_ids),
        provenance=_en_provenance,
    )
    ensure_gitignore_pytest_entry(project_dir)

    result.sources_toml_path = sources_path
    result.answers_toml_path = answers_path
    result.success = True

    io.notify(
        f"\n[DONE] project-setup complete ({mode} mode). "
        f"{len(result.modules_executed)} module(s) executed."
    )
    return result
