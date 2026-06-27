# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""lang-go — Go language overlay.

Ports setup-go.sh (145 lines) to a native-root Python module.

Steps (all under step id "write"):
  1. Derive module path from git remote if not provided (same normalization as legacy)
  2. go mod init <module_path>  (skip if go.mod already exists)
  3. Create cmd/ internal/ pkg/ directories + cmd/main.go  (write-if-absent)
  4. Write .golangci.yml  (write-if-absent, template verbatim)
  5. Append Go .gitignore block  (grep-guarded by '*.test')
  6. Append pre-commit-golang hooks  (grep-guarded by 'tekwizely/pre-commit-golang')

External tool absence/failure is NON-FATAL: a warning is emitted and the
module continues.  This mirrors the legacy WARN pattern in setup-go.sh.

Invoked by the runner as:
    uv run module.py --plan <frozen_plan.json> --step write [--inspect]
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
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
    """Run an external tool. Returns True on success, warns+returns False otherwise."""
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


def _derive_module_path(project_dir: Path, warnings: list[str]) -> str:
    """Derive a Go module path from git remote, mirroring legacy setup-go.sh lines 30-38."""
    git = shutil.which("git")
    if git:
        try:
            result = subprocess.run(
                [git, "remote", "get-url", "origin"],
                cwd=str(project_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )
            remote = result.stdout.strip()
            if remote:
                # Normalize https://, ssh://git@, git@host:path  →  host/path
                module = remote
                module = re.sub(r"^https://", "", module)
                module = re.sub(r"^ssh://git@", "", module)
                module = re.sub(r"^git@([^:]+):", r"\1/", module)
                module = re.sub(r"\.git$", "", module)
                return module
        except Exception:  # noqa: BLE001
            pass
    fallback = f"example.com/{project_dir.name}"
    warnings.append(f"WARN: No git remote found — using module path '{fallback}'")
    return fallback


def _append_if_absent(path: Path, marker: str, block: str, warnings: list[str], label: str) -> bool:
    """Append *block* to *path* if *marker* is not already present. Returns True if appended."""
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
    ap = argparse.ArgumentParser(description="lang-go module")
    ap.add_argument("--plan", required=True, help="path to the frozen plan.json")
    ap.add_argument("--step", required=True, help="step id to run")
    ap.add_argument("--inspect", action="store_true", help="dry pass: preview, no write")
    args = ap.parse_args()

    sdk = _load_sdk()
    inputs = sdk.load_frozen_inputs(args.plan, module_id="lang-go")

    module_path: str = inputs.get_str("module_path", default="")
    # app_kind accepted but no structural branches in legacy — free-form placeholder

    project_dir_env = os.environ.get("PROJECT_DIR")
    project_dir = Path(project_dir_env).resolve() if project_dir_env else Path.cwd().resolve()

    warnings: list[str] = []
    diffs = []
    files_written: list[str] = []

    # ── 1. Derive module path ───────────────────────────────────────────────── #
    if not module_path:
        module_path = _derive_module_path(project_dir, warnings)

    # ── 2. go mod init ─────────────────────────────────────────────────────── #
    go_mod = project_dir / "go.mod"
    if not go_mod.exists():
        if not args.inspect:
            _run_tool(
                ["go", "mod", "init", module_path],
                cwd=project_dir,
                warnings=warnings,
                label="go mod init",
            )
        else:
            warnings.append(f"inspect: would run go mod init {module_path}")

    # ── 3. Standard Go layout ──────────────────────────────────────────────── #
    project_name = project_dir.name
    main_go_rel = "cmd/main.go"
    main_go_body = f'package main\n\nimport "fmt"\n\nfunc main() {{\n\tfmt.Println("{project_name}")\n}}\n'
    if not args.inspect:
        for d in ("cmd", "internal", "pkg"):
            (project_dir / d).mkdir(exist_ok=True)
    diff = sdk.idempotent_write(
        main_go_rel,
        main_go_body,
        project_dir=project_dir,
        reconcile=False,
        inspect=args.inspect,
    )
    diffs.append(diff)
    if diff.kind in ("create", "modify"):
        files_written.append(diff.path)

    # ── 4. .golangci.yml ───────────────────────────────────────────────────── #
    golangci_body = (_TEMPLATES / "golangci.yml").read_text(encoding="utf-8")
    diff = sdk.idempotent_write(
        ".golangci.yml",
        golangci_body,
        project_dir=project_dir,
        reconcile=False,
        inspect=args.inspect,
    )
    diffs.append(diff)
    if diff.kind in ("create", "modify"):
        files_written.append(diff.path)

    # ── 5. Append Go .gitignore block ──────────────────────────────────────── #
    gitignore = project_dir / ".gitignore"
    gi_block = (_TEMPLATES / "gitignore-block.txt").read_text(encoding="utf-8")
    if not args.inspect:
        appended = _append_if_absent(
            gitignore, "*.test", gi_block, warnings, "Go .gitignore"
        )
        if appended:
            files_written.append(".gitignore")
            diffs.append(sdk.Diff(path=".gitignore", kind="modify", preview="(Go gitignore block appended)"))
        else:
            diffs.append(sdk.Diff(path=".gitignore", kind="skip", preview="(*.test already present)"))
    else:
        existing_gi = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
        if "*.test" not in existing_gi:
            diffs.append(sdk.Diff(path=".gitignore", kind="modify", preview="(would append Go gitignore block)"))
        else:
            diffs.append(sdk.Diff(path=".gitignore", kind="skip", preview="(*.test already present)"))

    # ── 6. Append Go pre-commit hooks ──────────────────────────────────────── #
    precommit = project_dir / ".pre-commit-config.yaml"
    pc_block = (_TEMPLATES / "precommit-block.yaml").read_text(encoding="utf-8")
    if precommit.exists():
        if not args.inspect:
            appended = _append_if_absent(
                precommit, "tekwizely/pre-commit-golang", pc_block, warnings, "Go pre-commit hooks"
            )
            if appended:
                files_written.append(".pre-commit-config.yaml")
                diffs.append(sdk.Diff(path=".pre-commit-config.yaml", kind="modify", preview="(Go hooks appended)"))
            else:
                diffs.append(sdk.Diff(path=".pre-commit-config.yaml", kind="skip", preview="(Go hooks already present)"))
        else:
            existing_pc = precommit.read_text(encoding="utf-8")
            if "tekwizely/pre-commit-golang" not in existing_pc:
                diffs.append(sdk.Diff(path=".pre-commit-config.yaml", kind="modify", preview="(would append Go hooks)"))
            else:
                diffs.append(sdk.Diff(path=".pre-commit-config.yaml", kind="skip", preview="(Go hooks already present)"))
    else:
        diffs.append(sdk.Diff(
            path=".pre-commit-config.yaml",
            kind="skip",
            preview="(.pre-commit-config.yaml absent — run precommit-setup first)",
        ))

    result = sdk.ModuleResult(
        module_id="lang-go",
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
