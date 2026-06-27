# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""lang-ts — TypeScript language overlay.

Ports setup-ts.sh (220 lines) to a native-root Python module.

Steps (all under step id "write"):
  1. Framework scaffold:
       - nuxt:  bunx/pnpm-dlx nuxi@latest init . --force  (skip if nuxt.config.ts exists)
       - vite:  bunx/pnpm-dlx create-vite . --template vue-ts  (skip if vite.config.ts exists)
       - plain: bun init -y / pnpm init  (skip if package.json exists)
                write tsconfig.json  (write-if-absent)
  2. pkg install  (external tool — warn+continue on failure)
  3. Append Node .gitignore block  (grep-guarded by 'node_modules')
  4. Framework-specific .gitignore extras:
       - nuxt:   append .nitro block  (grep-guarded by '.nitro')
       - (sst is handled via add_sst input — append .sst block)
  5. Append biome pre-commit hook  (grep-guarded by 'biomejs/pre-commit')
  6. Append prettier pre-commit hook  (grep-guarded by 'rbubley/mirrors-prettier')

Framework branches ported from legacy:
  - nuxt  → nuxi@latest scaffold
  - vite  → create-vite vue-ts scaffold
  - plain → bun init / pnpm init + tsconfig.json

External tool absence/failure is NON-FATAL.

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
            args, cwd=str(cwd), capture_output=True, text=True, timeout=180
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


def _pkg_cmd(pkg_manager: str, *sub: str) -> list[str]:
    """Build a package-manager command list (bun or pnpm)."""
    return [pkg_manager, *sub]


def _pkgx_cmd(pkg_manager: str, *sub: str) -> list[str]:
    """Build a package-manager exec command (bunx or pnpm dlx)."""
    if pkg_manager == "bun":
        return ["bunx", *sub]
    return ["pnpm", "dlx", *sub]


def main() -> int:
    ap = argparse.ArgumentParser(description="lang-ts module")
    ap.add_argument("--plan", required=True, help="path to the frozen plan.json")
    ap.add_argument("--step", required=True, help="step id to run")
    ap.add_argument("--inspect", action="store_true", help="dry pass: preview, no write")
    args = ap.parse_args()

    sdk = _load_sdk()
    inputs = sdk.load_frozen_inputs(args.plan, module_id="lang-ts")

    pkg_manager: str = inputs.get_choice("package_manager", default="bun")
    framework: str = inputs.get_str("framework", default="plain") or "plain"
    # target and ui_kit are accepted context inputs, not structurally acted on
    # (they are free-form strings for future framework-branch expansion)

    # Normalize framework to known values; treat unknowns as "plain"
    if framework not in ("nuxt", "vite", "plain"):
        warnings_pre: list[str] = [
            f"WARN: unknown framework '{framework}' — treating as 'plain'"
        ]
        framework = "plain"
    else:
        warnings_pre = []

    project_dir_env = os.environ.get("PROJECT_DIR")
    project_dir = Path(project_dir_env).resolve() if project_dir_env else Path.cwd().resolve()

    warnings: list[str] = list(warnings_pre)
    diffs = []
    files_written: list[str] = []

    # ── 1. Framework scaffold ───────────────────────────────────────────────── #
    if framework == "nuxt":
        if not (project_dir / "nuxt.config.ts").exists():
            if not args.inspect:
                _run_tool(
                    _pkgx_cmd(pkg_manager, "nuxi@latest", "init", ".", "--force",
                              "--packageManager", pkg_manager),
                    cwd=project_dir,
                    warnings=warnings,
                    label="nuxi init",
                )
            else:
                warnings.append(f"inspect: would run nuxi@latest init . --force --packageManager {pkg_manager}")
        else:
            diffs.append(sdk.Diff(path="nuxt.config.ts", kind="skip", preview="(Nuxt already scaffolded)"))

    elif framework == "vite":
        if not (project_dir / "vite.config.ts").exists():
            if not args.inspect:
                _run_tool(
                    _pkgx_cmd(pkg_manager, "create-vite", ".", "--template", "vue-ts"),
                    cwd=project_dir,
                    warnings=warnings,
                    label="create-vite vue-ts",
                )
            else:
                warnings.append("inspect: would run create-vite . --template vue-ts")
        else:
            diffs.append(sdk.Diff(path="vite.config.ts", kind="skip", preview="(Vite already scaffolded)"))

    else:  # plain
        package_json = project_dir / "package.json"
        if not package_json.exists():
            if not args.inspect:
                if pkg_manager == "bun":
                    _run_tool(["bun", "init", "-y"], cwd=project_dir, warnings=warnings, label="bun init")
                else:
                    _run_tool(["pnpm", "init"], cwd=project_dir, warnings=warnings, label="pnpm init")
            else:
                warnings.append(f"inspect: would run {pkg_manager} init")
        else:
            diffs.append(sdk.Diff(path="package.json", kind="skip", preview="(package.json already exists)"))

        # tsconfig.json (write-if-absent)
        tsconfig_body = (_TEMPLATES / "tsconfig.json").read_text(encoding="utf-8")
        diff = sdk.idempotent_write(
            "tsconfig.json",
            tsconfig_body,
            project_dir=project_dir,
            reconcile=False,
            inspect=args.inspect,
        )
        diffs.append(diff)
        if diff.kind in ("create", "modify"):
            files_written.append(diff.path)
            # ensure src/ directory exists
            if not args.inspect:
                (project_dir / "src").mkdir(exist_ok=True)

    # ── 2. pkg install ─────────────────────────────────────────────────────── #
    if not args.inspect:
        _run_tool(
            _pkg_cmd(pkg_manager, "install"),
            cwd=project_dir,
            warnings=warnings,
            label=f"{pkg_manager} install",
        )

    # ── 3. Append Node .gitignore block ────────────────────────────────────── #
    gitignore = project_dir / ".gitignore"
    gi_block = (_TEMPLATES / "gitignore-block.txt").read_text(encoding="utf-8")
    if not args.inspect:
        appended = _append_if_absent(
            gitignore, "node_modules", gi_block, warnings, "Node .gitignore"
        )
        if appended:
            files_written.append(".gitignore")
            diffs.append(sdk.Diff(path=".gitignore", kind="modify", preview="(Node gitignore block appended)"))
        else:
            diffs.append(sdk.Diff(path=".gitignore", kind="skip", preview="(node_modules already present)"))
    else:
        existing_gi = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
        if "node_modules" not in existing_gi:
            diffs.append(sdk.Diff(path=".gitignore", kind="modify", preview="(would append Node gitignore block)"))
        else:
            diffs.append(sdk.Diff(path=".gitignore", kind="skip", preview="(node_modules already present)"))

    # ── 4. Framework-specific .gitignore extras ─────────────────────────────── #
    if framework == "nuxt":
        nuxt_gi_block = (_TEMPLATES / "gitignore-nuxt.txt").read_text(encoding="utf-8")
        if not args.inspect:
            appended = _append_if_absent(
                gitignore, ".nitro", nuxt_gi_block, warnings, "Nuxt .gitignore extras"
            )
            if appended:
                if ".gitignore" not in files_written:
                    files_written.append(".gitignore")
                diffs.append(sdk.Diff(path=".gitignore", kind="modify", preview="(Nuxt extras appended)"))
            else:
                diffs.append(sdk.Diff(path=".gitignore", kind="skip", preview="(.nitro already present)"))
        else:
            existing_gi2 = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
            if ".nitro" not in existing_gi2:
                diffs.append(sdk.Diff(path=".gitignore", kind="modify", preview="(would append Nuxt gitignore extras)"))
            else:
                diffs.append(sdk.Diff(path=".gitignore", kind="skip", preview="(.nitro already present)"))

    # ── 5. Append biome pre-commit hook ────────────────────────────────────── #
    precommit = project_dir / ".pre-commit-config.yaml"
    biome_block = (_TEMPLATES / "precommit-biome.yaml").read_text(encoding="utf-8")
    prettier_block = (_TEMPLATES / "precommit-prettier.yaml").read_text(encoding="utf-8")
    if precommit.exists():
        if not args.inspect:
            appended = _append_if_absent(
                precommit, "biomejs/pre-commit", biome_block, warnings, "biome pre-commit hook"
            )
            if appended:
                files_written.append(".pre-commit-config.yaml")
                diffs.append(sdk.Diff(path=".pre-commit-config.yaml", kind="modify", preview="(biome hook appended)"))
            else:
                diffs.append(sdk.Diff(path=".pre-commit-config.yaml", kind="skip", preview="(biome hook already present)"))

            # ── 6. Append prettier pre-commit hook ─────────────────────────── #
            appended2 = _append_if_absent(
                precommit, "rbubley/mirrors-prettier", prettier_block, warnings, "prettier pre-commit hook"
            )
            if appended2:
                if ".pre-commit-config.yaml" not in files_written:
                    files_written.append(".pre-commit-config.yaml")
                diffs.append(sdk.Diff(path=".pre-commit-config.yaml", kind="modify", preview="(prettier hook appended)"))
            else:
                diffs.append(sdk.Diff(path=".pre-commit-config.yaml", kind="skip", preview="(prettier hook already present)"))
        else:
            existing_pc = precommit.read_text(encoding="utf-8")
            if "biomejs/pre-commit" not in existing_pc:
                diffs.append(sdk.Diff(path=".pre-commit-config.yaml", kind="modify", preview="(would append biome hook)"))
            else:
                diffs.append(sdk.Diff(path=".pre-commit-config.yaml", kind="skip", preview="(biome hook already present)"))
            if "rbubley/mirrors-prettier" not in existing_pc:
                diffs.append(sdk.Diff(path=".pre-commit-config.yaml", kind="modify", preview="(would append prettier hook)"))
            else:
                diffs.append(sdk.Diff(path=".pre-commit-config.yaml", kind="skip", preview="(prettier hook already present)"))
    else:
        diffs.append(sdk.Diff(
            path=".pre-commit-config.yaml",
            kind="skip",
            preview="(.pre-commit-config.yaml absent — run precommit-setup first)",
        ))

    result = sdk.ModuleResult(
        module_id="lang-ts",
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
