# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""package-add — add a package directory to a monorepo.

Ports the path-traversal guards VERBATIM from legacy package-add.sh (lines ~50-69).
These guards are SECURITY-PINNED by the old bats suite and MUST NOT be relaxed.

Guards (in order, each fails fast before any mkdir):
  1. name contains '/' or '\\' → reject "must not contain a path separator"
  2. name is '..', '.', or '' → reject "must be a plain package name"
  3. name contains '..' as substring → reject "must not contain '..'"
  4. lang not in {ts, python, go, rust} → reject "must be one of"

After guards pass: create dir/name under project_dir. Lang-overlay invocation
is a follow-up (lang modules separate); this module only creates the dir and
emits workspace registration guidance.

reconcile=false: re-run skips existing dir.
default_enabled=false: monorepo add-package tool, not base scaffold.

Invoked by the runner as:
    uv run module.py --plan <frozen_plan.json> --step add [--inspect]
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

_VALID_LANGS = frozenset({"ts", "python", "go", "rust"})


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
def _validate_name(name: str) -> str | None:
    """Return an error message if *name* fails the path-traversal guards.

    Ports package-add.sh lines ~50-69 VERBATIM. Returns None if name is safe.
    """
    # Guard 1: path separators (monolith case */*|*\\*)
    if "/" in name or "\\" in name:
        return f"--name must not contain a path separator: {name}"
    # Guard 2: dot-only names (monolith case ..|.|"")
    if name in ("..", ".", ""):
        return f"--name must be a plain package name: {name}"
    # Guard 3: embedded '..' (monolith case *..*) — catches 'foo..bar'
    if ".." in name:
        return f"--name must not contain '..': {name}"
    return None


def _workspace_guidance(lang: str, dir_: str, name: str) -> str:
    """Return workspace registration guidance (mirrors package-add.sh lines 160-182)."""
    rel = f"{dir_}/{name}"
    if lang == "ts":
        return (
            f"Add to root package.json workspaces: "
            f'  "workspaces": ["{rel}"]'
        )
    elif lang == "rust":
        return (
            f"Add to root Cargo.toml: "
            f"  [workspace]\\n  members = [\"{rel}\"]"
        )
    elif lang == "python":
        return (
            f"Add to root pyproject.toml: "
            f"  [tool.uv.workspace]\\n  members = [\"{rel}\"]"
        )
    elif lang == "go":
        return f"Add to go.work: use ./{rel}"
    return f"Register {rel} in your workspace manifest."


def main() -> int:
    ap = argparse.ArgumentParser(description="package-add module")
    ap.add_argument("--plan", required=True, help="path to the frozen plan.json")
    ap.add_argument("--step", required=True, help="step id to run")
    ap.add_argument("--inspect", action="store_true", help="dry pass: preview, no write")
    args = ap.parse_args()

    sdk = _load_sdk()
    inputs = sdk.load_frozen_inputs(args.plan, module_id="package-add")

    name = inputs.get_str("name", default="")
    lang = inputs.get_choice("lang", default="ts")
    dir_ = inputs.get_str("dir", default="packages")

    # --- Path-traversal guards (security-pinned, MUST run before any mkdir) ---
    name_err = _validate_name(name)
    if name_err:
        err_dict = {
            "error_code": "PATH_ESCAPE",
            "module_id": "package-add",
            "module_ids": [],
            "expected": "plain package name without path separators or '..'",
            "received": repr(name),
            "how_to_fix": name_err,
        }
        result = sdk.ModuleResult(
            module_id="package-add",
            step_id=args.step,
            status="error",
            message=name_err,
            error=err_dict,
        )
        sdk.emit_result(result)
        return 0

    # Validate lang
    if lang not in _VALID_LANGS:
        err_dict = {
            "error_code": "INPUT_VALUE_INVALID",
            "module_id": "package-add",
            "module_ids": [],
            "expected": f"lang in {sorted(_VALID_LANGS)}",
            "received": repr(lang),
            "how_to_fix": f"Set lang to one of: ts, python, go, rust (got: {lang!r})",
        }
        result = sdk.ModuleResult(
            module_id="package-add",
            step_id=args.step,
            status="error",
            message=f"invalid lang: {lang!r}",
            error=err_dict,
        )
        sdk.emit_result(result)
        return 0

    project_dir_env = os.environ.get("PROJECT_DIR")
    project_dir = Path(project_dir_env).resolve() if project_dir_env else Path.cwd().resolve()

    # Validate dir_ itself is a safe relative path (no traversal in the dir arg either)
    if not sdk.is_safe_relative_path(dir_):
        err_dict = {
            "error_code": "PATH_ESCAPE",
            "module_id": "package-add",
            "module_ids": [],
            "expected": "safe relative dir path",
            "received": repr(dir_),
            "how_to_fix": f"dir must be a safe relative path within the project: {dir_!r}",
        }
        result = sdk.ModuleResult(
            module_id="package-add",
            step_id=args.step,
            status="error",
            message=f"unsafe dir path: {dir_!r}",
            error=err_dict,
        )
        sdk.emit_result(result)
        return 0

    target = project_dir / dir_ / name
    target_rel = f"{dir_}/{name}"

    guidance = _workspace_guidance(lang, dir_, name)

    if args.inspect:
        result = sdk.ModuleResult(
            module_id="package-add",
            step_id=args.step,
            status="ok",
            message=f"would create {target_rel}/; {guidance}",
        )
        sdk.emit_result(result)
        return 0

    files_written: list[str] = []

    if target.exists():
        message = f"directory {target_rel}/ already exists; skipped"
    else:
        target.mkdir(parents=True, exist_ok=True)
        files_written.append(f"{target_rel}/")
        message = (
            f"Created {target_rel}/. "
            f"Lang-overlay invocation is a follow-up (lang modules separate). "
            f"{guidance}"
        )

    result = sdk.ModuleResult(
        module_id="package-add",
        step_id=args.step,
        status="ok",
        files_written=files_written,
        message=message,
    )
    sdk.emit_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
