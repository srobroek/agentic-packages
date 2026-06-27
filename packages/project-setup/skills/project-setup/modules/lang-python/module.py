# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""lang-python — Python language overlay.

Ports setup-python.sh (119 lines) to a native-root Python module.

Steps (all under step id "write"):
  1. uv init --python <ver>  (skip if pyproject.toml already exists)
  2. Create src/<project_name>/__init__.py  (write-if-absent)
  3. Append ruff config block to pyproject.toml  (grep-guarded by 'ruff')
  4. uv add --dev ruff pytest  (external tool — warn+continue on failure)
  5. Append Python .gitignore block  (grep-guarded by '__pycache__')
  6. Append ruff pre-commit hooks  (grep-guarded by 'astral-sh/ruff-pre-commit')

External tool absence/failure is NON-FATAL: a warning is emitted and the
module continues.  This mirrors the legacy WARN pattern in setup-python.sh.

Invoked by the runner as:
    uv run module.py --plan <frozen_plan.json> --step write [--inspect]
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

_TEMPLATES = Path(__file__).resolve().parent / "templates"


def _load_sdk():
    """Load the runner SDK by file path (the no-pip module contract)."""
    plugin_root = os.environ.get("PLUGIN_ROOT")
    if plugin_root:
        sdk_path = Path(plugin_root) / "runner" / "sdk.py"
        if not sdk_path.is_file():
            sdk_path = Path(plugin_root) / "skills" / "project-setup" / "runner" / "sdk.py"
    else:
        sdk_path = Path(__file__).resolve().parents[2] / "runner" / "sdk.py"
    spec = importlib.util.spec_from_file_location("ps_sdk", sdk_path)
    assert spec and spec.loader, f"cannot locate runner SDK at {sdk_path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ps_sdk"] = mod
    spec.loader.exec_module(mod)
    return mod


def _run_tool(args: list[str], cwd: Path, warnings: list[str], label: str) -> bool:
    """Run an external tool. Returns True on success, appends a warning and returns
    False if the tool is absent or exits non-zero. Never raises."""
    tool = args[0]
    if not shutil.which(tool):
        warnings.append(
            f"WARN: '{tool}' not found on PATH — {label} skipped. "
            f"Install {tool} and re-run to complete this step."
        )
        return False
    try:
        result = subprocess.run(
            args, cwd=str(cwd), capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            warnings.append(
                f"WARN: '{' '.join(args)}' exited {result.returncode} — {label} skipped. "
                f"stderr: {result.stderr.strip()[:200]}"
            )
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"WARN: '{tool}' failed with exception — {label} skipped: {exc}")
        return False


def _append_if_absent(path: Path, marker: str, block: str, warnings: list[str], label: str) -> bool:
    """Append *block* to *path* if *marker* is not already present.

    Returns True if appended, False if already present (idempotent).
    The file is created if absent.  Never raises.
    """
    try:
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        if marker in existing:
            return False
        with path.open("a", encoding="utf-8") as fh:
            fh.write(block)
        return True
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"WARN: could not append {label} to {path.name}: {exc}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="lang-python module")
    ap.add_argument("--plan", required=True, help="path to the frozen plan.json")
    ap.add_argument("--step", required=True, help="step id to run")
    ap.add_argument("--inspect", action="store_true", help="dry pass: preview, no write")
    args = ap.parse_args()

    sdk = _load_sdk()
    inputs = sdk.load_frozen_inputs(args.plan, module_id="lang-python")

    python_version: str = inputs.get_str("python_version", default="3.13")
    # framework is accepted but not structurally acted on in this port
    # (legacy setup-python.sh has no framework-specific branches — it is a
    # free-form string placeholder for future use)

    project_dir_env = os.environ.get("PROJECT_DIR")
    project_dir = Path(project_dir_env).resolve() if project_dir_env else Path.cwd().resolve()

    warnings: list[str] = []
    diffs = []
    files_written: list[str] = []

    # ── 1. uv init ─────────────────────────────────────────────────────────── #
    pyproject = project_dir / "pyproject.toml"
    if not pyproject.exists():
        if not args.inspect:
            _run_tool(
                ["uv", "init", "--python", python_version],
                cwd=project_dir,
                warnings=warnings,
                label="uv init",
            )
        else:
            # Inspect: report what would happen
            warnings.append(f"inspect: would run uv init --python {python_version}")

    # ── 2. src layout ──────────────────────────────────────────────────────── #
    project_name = project_dir.name.replace("-", "_")
    src_dir = project_dir / "src" / project_name
    init_rel = f"src/{project_name}/__init__.py"
    if not args.inspect:
        src_dir.mkdir(parents=True, exist_ok=True)
    init_body = ""
    diff = sdk.idempotent_write(
        init_rel,
        init_body,
        project_dir=project_dir,
        reconcile=False,
        inspect=args.inspect,
    )
    diffs.append(diff)
    if diff.kind in ("create", "modify"):
        files_written.append(diff.path)

    # ── 3. Ruff config in pyproject.toml ───────────────────────────────────── #
    ruff_block = (_TEMPLATES / "ruff-config.toml").read_text(encoding="utf-8")
    if not args.inspect:
        appended = _append_if_absent(
            pyproject, "ruff", ruff_block, warnings, "ruff config"
        )
        if appended:
            files_written.append("pyproject.toml")
            diffs.append(sdk.Diff(path="pyproject.toml", kind="modify", preview="(ruff config appended)"))
        else:
            diffs.append(sdk.Diff(path="pyproject.toml", kind="skip", preview="(ruff already present)"))
    else:
        existing_toml = pyproject.read_text(encoding="utf-8") if pyproject.exists() else ""
        if "ruff" not in existing_toml:
            diffs.append(sdk.Diff(path="pyproject.toml", kind="modify", preview="(would append ruff config)"))
        else:
            diffs.append(sdk.Diff(path="pyproject.toml", kind="skip", preview="(ruff already present)"))

    # ── 4. uv add dev deps ─────────────────────────────────────────────────── #
    if not args.inspect:
        _run_tool(
            ["uv", "add", "--dev", "ruff", "pytest"],
            cwd=project_dir,
            warnings=warnings,
            label="uv add --dev ruff pytest",
        )

    # ── 5. Append Python .gitignore block ──────────────────────────────────── #
    gitignore = project_dir / ".gitignore"
    gi_block = (_TEMPLATES / "gitignore-block.txt").read_text(encoding="utf-8")
    if not args.inspect:
        appended = _append_if_absent(
            gitignore, "__pycache__", gi_block, warnings, "Python .gitignore"
        )
        if appended:
            files_written.append(".gitignore")
            diffs.append(sdk.Diff(path=".gitignore", kind="modify", preview="(Python gitignore block appended)"))
        else:
            diffs.append(sdk.Diff(path=".gitignore", kind="skip", preview="(__pycache__ already present)"))
    else:
        existing_gi = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
        if "__pycache__" not in existing_gi:
            diffs.append(sdk.Diff(path=".gitignore", kind="modify", preview="(would append Python gitignore block)"))
        else:
            diffs.append(sdk.Diff(path=".gitignore", kind="skip", preview="(__pycache__ already present)"))

    # ── 6. Append ruff pre-commit hooks ────────────────────────────────────── #
    precommit = project_dir / ".pre-commit-config.yaml"
    pc_block = (_TEMPLATES / "precommit-block.yaml").read_text(encoding="utf-8")
    if precommit.exists():
        if not args.inspect:
            appended = _append_if_absent(
                precommit, "astral-sh/ruff-pre-commit", pc_block, warnings, "ruff pre-commit hooks"
            )
            if appended:
                files_written.append(".pre-commit-config.yaml")
                diffs.append(sdk.Diff(path=".pre-commit-config.yaml", kind="modify", preview="(ruff hooks appended)"))
            else:
                diffs.append(sdk.Diff(path=".pre-commit-config.yaml", kind="skip", preview="(ruff hooks already present)"))
        else:
            existing_pc = precommit.read_text(encoding="utf-8")
            if "astral-sh/ruff-pre-commit" not in existing_pc:
                diffs.append(sdk.Diff(path=".pre-commit-config.yaml", kind="modify", preview="(would append ruff hooks)"))
            else:
                diffs.append(sdk.Diff(path=".pre-commit-config.yaml", kind="skip", preview="(ruff hooks already present)"))
    else:
        diffs.append(sdk.Diff(
            path=".pre-commit-config.yaml",
            kind="skip",
            preview="(.pre-commit-config.yaml absent — run precommit-setup first)",
        ))

    result = sdk.ModuleResult(
        module_id="lang-python",
        step_id=args.step,
        status="ok",
        files_written=files_written,
        diffs=diffs,
        warnings=warnings,
    )
    sdk.emit_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
