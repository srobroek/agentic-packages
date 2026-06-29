"""Module executor — Model-B subprocess driver + result gate.

Runs each step of an ``ExecutionPlan`` module as a ``uv run module.py``
subprocess and validates the result.

Key contracts (see shared-contracts.md §6):
- Invocation: ``uv run <plugin_root>/<module_rel_root>/module.py
               --plan <frozen_plan_path> --step <step_id>``
  (+ ``--inspect`` for the dry-pass preview).
- The module reads frozen inputs from disk; agent args are NEVER a channel.
- Result: exactly ONE JSON object on stdout, validated against
  ``RESULT_REQUIRED_KEYS``.
- ``files_written ⊆ project_dir`` guard (PATH_ESCAPE).
- Per-module failure isolation: a subprocess error records the failure and
  continues (SC-008).  BUT: if ``uv`` vanishes mid-run the executor
  hard-fails with ``UV_MISSING`` (a distinct re-check, not a soft skip).

Standard library only.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

# Sibling runner modules import by plain name; the runner dir is on sys.path via
# the entry point (cli.py / conftest.py / executor PYTHONPATH — spec 005 OQ-2).
import contracts as _contracts
import paths as _paths_mod

SetupError = _contracts.SetupError
ErrorCode = _contracts.ErrorCode
GateFailure = _contracts.GateFailure
ModuleResult = _contracts.ModuleResult
RESULT_REQUIRED_KEYS = _contracts.RESULT_REQUIRED_KEYS
SCHEMA_VERSION = _contracts.SCHEMA_VERSION
plugin_root = _paths_mod.plugin_root


# --------------------------------------------------------------------------- #
# Typed result of a single step execution                                      #
# --------------------------------------------------------------------------- #
class StepOutcome:
    """Result of executing one module step.

    Attributes
    ----------
    ok : bool
        ``True`` when the step completed without executor-level or module-level
        error.
    module_id : str
    step_id : str
    result : dict | None
        The parsed JSON dict from the module's stdout (when ``ok`` is True or
        for module-level errors that still emitted a valid envelope).
    error : SetupError | None
        An executor-level ``SetupError`` when ``ok`` is False.
    raw_stdout : str
        Whatever the subprocess printed to stdout (for diagnostics).
    raw_stderr : str
        Whatever the subprocess printed to stderr.
    inspect : bool
        Whether this outcome came from a dry-pass (``--inspect``) invocation.
    """

    __slots__ = (
        "ok", "module_id", "step_id", "result",
        "error", "raw_stdout", "raw_stderr", "inspect",
    )

    def __init__(
        self,
        *,
        ok: bool,
        module_id: str,
        step_id: str,
        result: dict[str, Any] | None = None,
        error: SetupError | None = None,
        raw_stdout: str = "",
        raw_stderr: str = "",
        inspect: bool = False,
    ) -> None:
        self.ok = ok
        self.module_id = module_id
        self.step_id = step_id
        self.result = result
        self.error = error
        self.raw_stdout = raw_stdout
        self.raw_stderr = raw_stderr
        self.inspect = inspect

    def files_written(self) -> list[str]:
        """Return the list of files reported by the module (or [])."""
        if self.result is None:
            return []
        return list(self.result.get("files_written", []))

    def diffs(self) -> list[dict[str, Any]]:
        """Return the diffs list reported by the module (or [])."""
        if self.result is None:
            return []
        return list(self.result.get("diffs", []))


# --------------------------------------------------------------------------- #
# UV_MISSING re-check helper                                                   #
# --------------------------------------------------------------------------- #
def _assert_uv_present() -> None:
    """Hard-fail immediately if ``uv`` is no longer on PATH.

    This is the mid-run re-check (distinct from the CLI preflight).  If ``uv``
    vanishes between module invocations the executor raises ``GateFailure``
    with ``UV_MISSING`` rather than silently skipping the remaining steps.
    """
    import shutil
    if shutil.which("uv") is None:
        raise GateFailure([SetupError(
            error_code=ErrorCode.UV_MISSING,
            expected="'uv' on PATH",
            received="not found (vanished mid-run)",
            how_to_fix=(
                "Install uv: https://docs.astral.sh/uv/getting-started/installation/ "
                "and ensure it is on your PATH before re-running project-setup."
            ),
        )])


# --------------------------------------------------------------------------- #
# Result-gate validation                                                       #
# --------------------------------------------------------------------------- #
def _parse_and_validate_result(
    raw_stdout: str,
    module_id: str,
    step_id: str,
    project_dir: Path,
) -> tuple[dict[str, Any] | None, SetupError | None]:
    """Parse stdout as JSON and validate it against the result contract.

    Returns ``(result_dict, None)`` on success or ``(None, error)`` on failure.
    Checks:
    1. Exactly one JSON object parseable from stdout.
    2. All ``RESULT_REQUIRED_KEYS`` present.
    3. ``schema_version`` matches ``SCHEMA_VERSION``.
    4. ``files_written ⊆ project_dir`` (PATH_ESCAPE guard — runner-side).
    """
    # 1. Parse JSON
    try:
        data = json.loads(raw_stdout)
    except json.JSONDecodeError as exc:
        return None, SetupError(
            error_code=ErrorCode.RESULT_SHAPE,
            module_id=module_id,
            expected="exactly one JSON object on stdout",
            received=f"JSONDecodeError: {exc}  stdout={raw_stdout[:200]!r}",
            how_to_fix=(
                f"Module '{module_id}' step '{step_id}' must print exactly one "
                "JSON object to stdout via sdk.emit_result()."
            ),
        )

    if not isinstance(data, dict):
        return None, SetupError(
            error_code=ErrorCode.RESULT_SHAPE,
            module_id=module_id,
            expected="JSON object (dict) on stdout",
            received=f"got {type(data).__name__}",
            how_to_fix=(
                f"Module '{module_id}' step '{step_id}' must print a JSON object "
                "(not a list or scalar) to stdout."
            ),
        )

    # 2. Required keys
    missing = RESULT_REQUIRED_KEYS - set(data.keys())
    if missing:
        return None, SetupError(
            error_code=ErrorCode.RESULT_SHAPE,
            module_id=module_id,
            expected=f"result keys {sorted(RESULT_REQUIRED_KEYS)}",
            received=f"missing keys {sorted(missing)}",
            how_to_fix=(
                f"Module '{module_id}' step '{step_id}' result is missing "
                f"required keys: {sorted(missing)}.  Use sdk.emit_result()."
            ),
        )

    # 3. schema_version
    got_version = data.get("schema_version")
    if got_version != SCHEMA_VERSION:
        return None, SetupError(
            error_code=ErrorCode.RESULT_SHAPE,
            module_id=module_id,
            expected=f"schema_version={SCHEMA_VERSION}",
            received=f"schema_version={got_version!r}",
            how_to_fix=(
                f"Module '{module_id}' was built against schema version "
                f"{got_version}; the runner expects {SCHEMA_VERSION}. "
                "Rebuild or update the module."
            ),
        )

    # 4. PATH_ESCAPE: files_written must all resolve within project_dir
    project_resolved = project_dir.resolve()
    for rel in data.get("files_written", []):
        # We only have relative paths here (the module used idempotent_write).
        # Reconstruct the absolute path and verify containment.
        try:
            candidate = (project_resolved / rel).resolve()
        except Exception:
            return None, SetupError(
                error_code=ErrorCode.PATH_ESCAPE,
                module_id=module_id,
                expected=f"files_written paths within {project_dir}",
                received=f"could not resolve path {rel!r}",
                how_to_fix=(
                    f"Module '{module_id}' reported a path it cannot write: {rel!r}. "
                    "Use sdk.idempotent_write() with a safe relative path."
                ),
            )
        if not str(candidate).startswith(str(project_resolved)):
            return None, SetupError(
                error_code=ErrorCode.PATH_ESCAPE,
                module_id=module_id,
                expected=f"files_written path within {project_dir}",
                received=f"{rel!r} resolves to {candidate}",
                how_to_fix=(
                    f"Module '{module_id}' tried to write a file outside the project "
                    f"directory: {rel!r}.  Only paths within the project dir are allowed."
                ),
            )

    return data, None


# --------------------------------------------------------------------------- #
# Core subprocess invocation                                                   #
# --------------------------------------------------------------------------- #
def run_python_step(
    plugin_root_path: Path,
    module_rel_root: str,
    step_id: str,
    frozen_plan_path: Path,
    project_dir: Path,
    *,
    inspect: bool = False,
    env: dict[str, str] | None = None,
) -> StepOutcome:
    """Invoke a ``kind=python`` step via ``uv run module.py``.

    This is the Model-B invocation contract (shared-contracts.md §6):
    ``uv run <plugin_root>/<module_rel_root>/module.py --plan <frozen> --step <step_id>``
    (plus ``--inspect`` for the dry pass).

    Parameters
    ----------
    plugin_root_path:
        Absolute path to the plugin root (the ``skills/project-setup/`` dir).
    module_rel_root:
        The path of the module dir relative to *plugin_root_path* (from the
        frozen plan's ``module_rel_root`` field).
    step_id:
        The step id within the module to execute.
    frozen_plan_path:
        The path to the frozen ``plan.json`` on disk.
    project_dir:
        The project root directory used for the PATH_ESCAPE guard.
    inspect:
        If True, pass ``--inspect`` — dry pass, no writes.
    env:
        Optional environment variable overrides (merged with os.environ).

    Returns
    -------
    StepOutcome
        Always returns (never raises on subprocess failure — per-module failure
        isolation).  Hard-fails only on UV_MISSING (checked before invoking).
    """
    import os

    # Mid-run uv re-check — hard-fail if uv vanished.
    _assert_uv_present()

    module_dir = plugin_root_path / module_rel_root
    module_py = module_dir / "module.py"

    # Extract module_id from module_rel_root (last path component)
    module_id = Path(module_rel_root).name

    cmd: list[str] = [
        "uv", "run",
        str(module_py),
        "--plan", str(frozen_plan_path),
        "--step", step_id,
    ]
    if inspect:
        cmd.append("--inspect")

    # Build env: inherit os.environ, apply overrides, set PROJECT_DIR
    run_env = {**os.environ}
    if env:
        run_env.update(env)
    # Ensure the module knows where the project is
    run_env.setdefault("PROJECT_DIR", str(project_dir))
    # Ensure PLUGIN_ROOT is set so modules can load the SDK
    run_env.setdefault("PLUGIN_ROOT", str(plugin_root_path))
    # Also set CLAUDE_PLUGIN_ROOT so native-plugin installs (which export this token) work (spec 020 FR-E1/E3).
    run_env.setdefault("CLAUDE_PLUGIN_ROOT", str(plugin_root_path))
    # Put the runner dir on PYTHONPATH so module.py can `import sdk` directly
    # (spec 005). `uv run` propagates PYTHONPATH into the PEP-723 script's
    # sys.path (verified, uv 0.11.8). Modules keep a path-load fallback for
    # direct invocation outside the executor (e.g. functional tests), so this
    # is the fast path, not a hard requirement. Handle both layouts the module
    # fallback knows about: <root>/runner and <root>/skills/project-setup/runner.
    _runner_dir = plugin_root_path / "runner"
    if not (_runner_dir / "sdk.py").is_file():
        _runner_dir = plugin_root_path / "skills" / "project-setup" / "runner"
    _existing_pp = run_env.get("PYTHONPATH", "")
    run_env["PYTHONPATH"] = (
        f"{_runner_dir}{os.pathsep}{_existing_pp}" if _existing_pp else str(_runner_dir)
    )

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=run_env,
            cwd=str(project_dir),
        )
    except FileNotFoundError:
        # uv binary not found — hard UV_MISSING failure
        raise GateFailure([SetupError(
            error_code=ErrorCode.UV_MISSING,
            expected="'uv' on PATH",
            received="FileNotFoundError when invoking uv",
            how_to_fix=(
                "Install uv: https://docs.astral.sh/uv/getting-started/installation/"
            ),
        )])

    raw_stdout = proc.stdout or ""
    raw_stderr = proc.stderr or ""

    if proc.returncode != 0:
        # Per-module failure isolation (SC-008): record and continue.
        return StepOutcome(
            ok=False,
            module_id=module_id,
            step_id=step_id,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            inspect=inspect,
            error=SetupError(
                error_code=ErrorCode.RESULT_SHAPE,
                module_id=module_id,
                expected="exit code 0",
                received=f"exit code {proc.returncode}",
                how_to_fix=(
                    f"Module '{module_id}' step '{step_id}' exited with code "
                    f"{proc.returncode}.  Check stderr: {raw_stderr[:300]!r}"
                ),
            ),
        )

    # Parse and gate the result
    result, err = _parse_and_validate_result(
        raw_stdout, module_id, step_id, project_dir
    )
    if err is not None:
        return StepOutcome(
            ok=False,
            module_id=module_id,
            step_id=step_id,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            inspect=inspect,
            error=err,
        )

    return StepOutcome(
        ok=True,
        module_id=module_id,
        step_id=step_id,
        result=result,
        raw_stdout=raw_stdout,
        raw_stderr=raw_stderr,
        inspect=inspect,
    )


# --------------------------------------------------------------------------- #
# Gate step                                                                    #
# --------------------------------------------------------------------------- #
def run_gate_step(
    step: dict[str, Any],
    module_id: str,
    io: Any,
    *,
    non_interactive: bool = False,
    active_flags: frozenset[str] | None = None,
    init_only_bypass: bool = False,
) -> bool:
    """Render a ``kind=gate`` step message and resolve confirmation by hardness.

    The resolution is **data-driven** (spec 004 FR-003/004): it reads the step's
    ``hardness`` (``hard`` | ``soft`` | ``informational``, default ``hard``) and the
    active per-action flag set, instead of the pre-004 "always SAFE-skip in CI" rule.

    Parameters
    ----------
    step:
        The step dict from the frozen plan (keys: ``id``, ``kind``, ``message``,
        and the spec-004 enrichment ``hardness``/``allow_flag``/``skip_flag``).
    module_id:
        The owning module id (for logging).
    io:
        An ``InterviewIO`` implementation.
    non_interactive:
        When True (CI / --non-interactive), DO NOT call ``io.confirm`` (which would
        block on ``input()`` and deadlock CI). The outcome is resolved from hardness
        + flags (see below) WITHOUT prompting.
    active_flags:
        The set of opt-in/opt-out flag names active this run (e.g.
        ``{"allow-public-repo"}`` from ``--allow-public-repo``). Drives the
        non-interactive resolution; a standing flag also pre-resolves a TTY gate.
    init_only_bypass:
        True when this gate is ``init_only`` AND the run is a plain reproduce (mode
        ``reproduce``, module not named by ``--refresh``). The gate then AUTO-PROCEEDS
        (returns ``True``) without prompting — the frozen decision is already
        consented, so its byte-identical write must replay, NOT be skipped (spec 004
        FR-006a). This is distinct from a hard gate's CI SAFE-skip.

    Returns
    -------
    bool
        ``True`` = confirmed/proceed; ``False`` = skipped (the SAFE action).

    The resolution table (spec 004 §3 CI policy):

    ======================  =====================  =============================
    hardness                TTY                    non-interactive / CI
    ======================  =====================  =============================
    hard                    prompt ``[y/N]``       SAFE-skip, unless ``allow_flag``
                            (default No)           is active → proceed
    soft                    prompt ``[Y/n]``       proceed, unless ``skip_flag``
                            (default Yes)          is active → SAFE-skip
    informational           print, no prompt       print, proceed
    ======================  =====================  =============================
    """
    flags = active_flags or frozenset()
    message = step.get("message", "(no message)")
    step_id = step.get("id", "gate")
    hardness = step.get("hardness", "hard")
    allow_flag = step.get("allow_flag")
    skip_flag = step.get("skip_flag")
    tag = f"{module_id}/{step_id}"

    io.notify(f"\n[GATE] {tag}: {message}")

    # init_only on plain reproduce: auto-proceed (consented frozen decision replays).
    if init_only_bypass:
        io.notify(
            f"[GATE] {tag}: init-only — frozen decision already consented; "
            f"auto-proceeding on reproduce (pass --refresh to re-review)."
        )
        return True

    # informational: never prompts, always proceeds (TTY and CI alike).
    if hardness == "informational":
        return True

    # A standing flag pre-resolves the gate regardless of interactivity:
    #   hard + allow_flag active  → proceed
    #   soft + skip_flag active    → SAFE-skip
    if hardness == "hard" and allow_flag and allow_flag in flags:
        io.notify(f"[GATE] {tag}: --{allow_flag} active — proceeding with the gated action.")
        return True
    if hardness == "soft" and skip_flag and skip_flag in flags:
        io.notify(f"[GATE] {tag}: --{skip_flag} active — SAFE-skipping the gated action.")
        return False

    if non_interactive:
        if hardness == "soft":
            io.notify(f"[GATE] {tag}: non-interactive soft gate — proceeding (pass --{skip_flag} to skip).")
            return True
        # hard (default): SAFE-skip, never auto-approve.
        opt_in = f" Pass --{allow_flag} to perform it." if allow_flag else ""
        io.notify(
            f"[GATE] {tag}: non-interactive — SAFE-skipping the gated step "
            f"(not auto-approved).{opt_in}"
        )
        return False

    # Interactive TTY: hard → [y/N] default No; soft → [Y/n] default Yes.
    default_yes = hardness == "soft"
    return io.confirm({
        "path": tag,
        "kind": "gate",
        "preview": message,
        "default_yes": default_yes,
    })


# --------------------------------------------------------------------------- #
# Agent step                                                                   #
# --------------------------------------------------------------------------- #
def run_agent_step(
    step: dict[str, Any],
    module_id: str,
    io: Any,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Hand a ``kind=agent`` step to ``io.agent_step`` and fold back the result.

    Parameters
    ----------
    step:
        The step dict from the frozen plan (keys: ``id``, ``kind``, ``steering``).
    module_id:
        The owning module id.
    io:
        An ``InterviewIO`` implementation.
    context:
        Additional context passed to the agent (plan fragment, ids, …).

    Returns
    -------
    dict
        The agent's response as returned by ``io.agent_step``.  Must contain
        at least ``"answers_to_persist"`` (with ``"agent-steered"`` source on
        each entry) and ``"message"``.  The caller is responsible for folding
        these back into the persisted answer set.
    """
    steering_path = step.get("steering", "")
    step_id = step.get("id", "agent")
    ctx = dict(context or {})
    ctx.update({"module_id": module_id, "step_id": step_id})
    io.notify(f"\n[AGENT] {module_id}/{step_id}: delegating to agent (steering: {steering_path})")
    return io.agent_step(steering_path, ctx)
