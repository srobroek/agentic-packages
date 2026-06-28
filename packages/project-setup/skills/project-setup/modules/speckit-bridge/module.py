# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""speckit-bridge — install and initialise speckit.

Migrated from the legacy monolith project-setup.sh Step 10 (lines 946-996):
  - none → skip.
  - lightweight → ensure specs/ exists (line 948-950).
  - full → apm install speckit@srobroek-agentic (line 964-968);
    locate setup-speckit.sh under apm_modules (lines 970-974);
    run with --script sh --render-for codex,claude (lines 987-995).

The speckit package owns all spec-kit setup logic; project-setup only delegates
(FR-029). apm/specify missing → emit error result (not raise).

Invoked by the runner as:
    uv run module.py --plan <frozen_plan.json> --step setup [--inspect]
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _load_sdk():
    """Load the runner SDK. Fast path: `import sdk` (the executor puts the runner
    dir on PYTHONPATH — spec 005). Fallback: load by file path for direct
    invocation outside the executor (e.g. functional tests)."""
    try:
        import sdk  # noqa: PLC0415
        return sdk
    except ModuleNotFoundError:
        pass
    # Fallback: locate sdk.py by path (PLUGIN_ROOT, or __file__-relative).
    plugin_root = os.environ.get("PLUGIN_ROOT")
    if plugin_root:
        sdk_path = Path(plugin_root) / "runner" / "sdk.py"
        if not sdk_path.is_file():
            sdk_path = Path(plugin_root) / "skills" / "project-setup" / "runner" / "sdk.py"
    else:
        sdk_path = Path(__file__).resolve().parents[2] / "runner" / "sdk.py"
    spec = importlib.util.spec_from_file_location("sdk", sdk_path)
    assert spec and spec.loader, f"cannot locate runner SDK at {sdk_path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sdk"] = mod          # register BEFORE exec_module (the @dataclass(Exception) footgun)
    spec.loader.exec_module(mod)
    return mod
def _run_apm(args: list[str], env: dict, cwd: str) -> tuple[int, str, str]:
    """Try apm via three resolution paths (mirrors apm-install module)."""
    if shutil.which("apm"):
        proc = subprocess.run(
            ["apm"] + args, capture_output=True, text=True, env=env, cwd=cwd
        )
        return proc.returncode, proc.stdout, proc.stderr

    if shutil.which("mise"):
        check = subprocess.run(
            ["mise", "which", "apm"], capture_output=True, text=True, env=env, cwd=cwd
        )
        if check.returncode == 0:
            proc = subprocess.run(
                ["mise", "exec", "--", "apm"] + args,
                capture_output=True,
                text=True,
                env=env,
                cwd=cwd,
            )
            return proc.returncode, proc.stdout, proc.stderr

    if shutil.which("uv"):
        proc = subprocess.run(
            ["uv", "tool", "run", "--from", "apm-cli", "apm"] + args,
            capture_output=True,
            text=True,
            env=env,
            cwd=cwd,
        )
        return proc.returncode, proc.stdout, proc.stderr

    return 127, "", "apm not found"


def main() -> int:
    ap = argparse.ArgumentParser(description="speckit-bridge module")
    ap.add_argument("--plan", required=True, help="path to the frozen plan.json")
    ap.add_argument("--step", required=True, help="step id to run")
    ap.add_argument("--inspect", action="store_true", help="dry pass: preview, no write")
    args = ap.parse_args()

    sdk = _load_sdk()
    inputs = sdk.load_frozen_inputs(args.plan, module_id="speckit-bridge")

    spec_mode = inputs.get_choice("spec_mode", default="none")

    project_dir_env = os.environ.get("PROJECT_DIR")
    project_dir = Path(project_dir_env).resolve() if project_dir_env else Path.cwd().resolve()
    cwd = str(project_dir)

    env = dict(os.environ)
    warnings: list[str] = []

    if spec_mode == "none":
        result = sdk.ModuleResult(
            module_id="speckit-bridge",
            step_id=args.step,
            status="ok",
            message="spec_mode=none; skipped",
        )
        sdk.emit_result(result)
        return 0

    if spec_mode == "lightweight":
        specs_dir = project_dir / "specs"
        if args.inspect:
            result = sdk.ModuleResult(
                module_id="speckit-bridge",
                step_id=args.step,
                status="ok",
                message="would create specs/ directory",
            )
            sdk.emit_result(result)
            return 0

        specs_dir.mkdir(parents=True, exist_ok=True)
        result = sdk.ModuleResult(
            module_id="speckit-bridge",
            step_id=args.step,
            status="ok",
            message="spec_mode=lightweight; specs/ ensured",
        )
        sdk.emit_result(result)
        return 0

    # spec_mode == "full"
    # Check apm is available
    rc_ver, _, _ = _run_apm(["--version"], env, cwd)
    if rc_ver != 0:
        err_dict = {
            "error_code": "MISSING_REQUIRED_TOOL",
            "module_id": "speckit-bridge",
            "module_ids": [],
            "expected": "apm CLI available",
            "received": "apm not found on PATH",
            "how_to_fix": (
                "Install apm, then rerun with spec_mode=full. "
                "Alternatively, set spec_mode=lightweight or spec_mode=none."
            ),
        }
        result = sdk.ModuleResult(
            module_id="speckit-bridge",
            step_id=args.step,
            status="error",
            message="spec_mode=full requires apm; apm not found",
            error=err_dict,
        )
        sdk.emit_result(result)
        return 0

    if args.inspect:
        result = sdk.ModuleResult(
            module_id="speckit-bridge",
            step_id=args.step,
            status="ok",
            message="would install speckit@srobroek-agentic and run setup-speckit.sh",
        )
        sdk.emit_result(result)
        return 0

    # Install speckit package (monolith line 964-968)
    rc_install, _, stderr_install = _run_apm(
        ["install", "--target", "claude,codex,agent-skills", "speckit@srobroek-agentic"],
        env,
        cwd,
    )
    if rc_install != 0:
        err_dict = {
            "error_code": "FETCH_FAILED",
            "module_id": "speckit-bridge",
            "module_ids": [],
            "expected": "successful apm install of speckit@srobroek-agentic",
            "received": f"exit {rc_install}: {stderr_install.strip()}",
            "how_to_fix": (
                "Run 'apm install --target claude,codex,agent-skills speckit@srobroek-agentic' "
                "manually, then rerun speckit-bridge."
            ),
        }
        result = sdk.ModuleResult(
            module_id="speckit-bridge",
            step_id=args.step,
            status="error",
            message=f"apm install speckit failed: {stderr_install.strip()}",
            error=err_dict,
        )
        sdk.emit_result(result)
        return 0

    # Locate setup-speckit.sh under apm_modules (monolith lines 970-974)
    setup_scripts = list(project_dir.glob("apm_modules/**/speckit-setup/scripts/setup-speckit.sh"))
    if not setup_scripts:
        err_dict = {
            "error_code": "FETCH_FAILED",
            "module_id": "speckit-bridge",
            "module_ids": [],
            "expected": "setup-speckit.sh under apm_modules/*/speckit-setup/scripts/",
            "received": "not found after successful apm install",
            "how_to_fix": (
                "Run 'apm install --target claude,codex,agent-skills speckit@srobroek-agentic' "
                "and verify setup-speckit.sh exists under apm_modules."
            ),
        }
        result = sdk.ModuleResult(
            module_id="speckit-bridge",
            step_id=args.step,
            status="error",
            message="setup-speckit.sh not found after apm install",
            error=err_dict,
        )
        sdk.emit_result(result)
        return 0

    setup_script = setup_scripts[0]

    # Run setup-speckit.sh (monolith lines 987-995)
    run_proc = subprocess.run(
        ["bash", str(setup_script), "--script", "sh", "--render-for", "codex,claude"],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )
    if run_proc.returncode != 0:
        warnings.append(
            f"setup-speckit.sh failed (exit {run_proc.returncode}): "
            f"{run_proc.stderr.strip()}. "
            "Run 'bash setup-speckit.sh --script sh --render-for codex,claude' manually."
        )

    result = sdk.ModuleResult(
        module_id="speckit-bridge",
        step_id=args.step,
        status="ok",
        warnings=warnings,
        message="speckit setup completed" if not warnings else "speckit setup completed with warnings",
    )
    sdk.emit_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
