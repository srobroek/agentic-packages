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

import importlib.util
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── import-by-path bootstrap ──────────────────────────────────────────────── #
_RUNNER = Path(__file__).resolve().parent


def _load_sibling(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_sources(name: str):
    """Load a module from the sources/ sub-package."""
    if name in sys.modules:
        return sys.modules[name]
    path = _RUNNER / "sources" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_contracts = _load_sibling("contracts")
_paths_mod = _load_sibling("paths")
_manifest_mod = _load_sibling("manifest")
_answers_mod = _load_sibling("answers")
_validate_mod = _load_sibling("validate")
_plan_mod = _load_sibling("plan")
_mode_mod = _load_sibling("mode")
_executor_mod = _load_sibling("executor")
_reproduce_mod = _load_sibling("reproduce")
_persist_mod = _load_sibling("persist")
_enablement_mod = _load_sibling("enablement")
_discover_mod = _load_sources("discover")
_fetch_mod = _load_sources("fetch")
_locator_mod = _load_sources("locator")

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
run_python_step = _executor_mod.run_python_step
build_drift_report = _reproduce_mod.build_drift_report
apply_reproduce = _reproduce_mod.apply

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
    """Parse .project-setup/sources.toml and return the [[source]] records."""
    src_toml = project_setup_dir(project_dir) / "sources.toml"
    if not src_toml.is_file():
        return []
    try:
        with open(src_toml, "rb") as fh:
            data = tomllib.load(fh)
    except Exception:
        return []
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
    # Structure: {module: {mod_id: {key: value}, "mod_id.source": {...}}}
    module_section = data.get("module", {})
    answers: dict[str, dict[str, Any]] = {}
    for key, val in module_section.items():
        if isinstance(val, dict) and "." not in key:
            answers[key] = val
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
        committed_sources = _read_committed_sources(project_dir)

    all_sources = list(committed_sources)
    if extra_sources:
        all_sources.extend(extra_sources)

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

    # ── Stage 6: build + freeze plan ────────────────────────────────────────── #
    plan = build_plan(
        manifests,
        resolved_answers=final_answers,
        ordered_ids=ordered_ids,
        mode=mode,
        plugin_root_path=plugin_root_path,
    )

    if not dry_run:
        freeze(plan, path=plan_path)
        result.plan_path = plan_path
    else:
        # Dry run: freeze to the path but record it
        freeze(plan, path=plan_path)
        result.plan_path = plan_path

    # ── Dry run stops here ────────────────────────────────────────────────── #
    if dry_run:
        result.success = True
        io.notify("[DRY RUN] Plan frozen. No files written to project.")
        return result

    # ── Stage 7: execute ────────────────────────────────────────────────────── #
    if mode == "reproduce":
        # Pre-write diff/confirm pass, then apply
        confirmations = build_drift_report(
            plan=plan,
            plugin_root_path=plugin_root_path,
            project_dir=project_dir,
            io=io,
            frozen_plan_path=plan_path,
            env=env,
        )
        step_outcomes = apply_reproduce(
            plan=plan,
            confirmations=confirmations,
            plugin_root_path=plugin_root_path,
            project_dir=project_dir,
            io=io,
            frozen_plan_path=plan_path,
            env=env,
        )
    else:
        # Init mode: run all steps directly (no pre-write confirm pass)
        step_outcomes = []
        for mod_id in plan.order:
            mod_entry = plan.modules.get(mod_id)
            if mod_entry is None:
                continue
            for step in mod_entry.steps:
                kind = step.get("kind") if isinstance(step, dict) else getattr(step, "kind", None)
                step_id = step.get("id") if isinstance(step, dict) else getattr(step, "id", None)

                if kind == "python":
                    outcome = run_python_step(
                        plugin_root_path=plugin_root_path,
                        module_rel_root=mod_entry.module_rel_root,
                        step_id=step_id,
                        frozen_plan_path=plan_path,
                        project_dir=project_dir,
                        inspect=False,
                        env=env,
                    )
                    step_outcomes.append(outcome)
                    if not outcome.ok:
                        io.notify(
                            f"[ERROR] {mod_id}/{step_id}: "
                            f"{outcome.error and outcome.error.how_to_fix}"
                        )
                    else:
                        result.files_written.extend(outcome.files_written())
                        result.modules_executed.append(mod_id)

                elif kind == "gate":
                    step_dict = step if isinstance(step, dict) else {"id": step_id, "kind": kind, "message": getattr(step, "message", "")}
                    _executor_mod.run_gate_step(step_dict, mod_id, io)

                elif kind == "agent":
                    step_dict = step if isinstance(step, dict) else {"id": step_id, "kind": kind, "steering": getattr(step, "steering", "")}
                    _executor_mod.run_agent_step(step_dict, mod_id, io)

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
    answers_path = write_answers_toml(
        project_dir,
        answers=final_answers,
        provenance_map=provenance_map,
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
