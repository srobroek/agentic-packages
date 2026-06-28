# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""lang-ts — TypeScript language overlay (Tier-2 stack resolver).

Ports setup-ts.sh (220 lines) to a native-root Python module, upgraded with
a Tier-2 agent resolver step that decides the fully-pinned stack.

Steps:
  resolve  (agent)  — Tier-2 agent maps prose intent → framework + pinned deps
  pins     (gate)   — shows the frozen pin table; user confirms before any write
  write    (python) — reads frozen pins from plan, verifies against npm,
                      writes package.json + dev tooling, appends .gitignore +
                      pre-commit hooks

Pin verification (init mode only, FR-005/FR-012):
  - PIN_DISCONFIRMED → hard error, write nothing
  - PIN_UNREACHABLE  → safe-skip the manifest write, emit warning (not error)
  - PIN_VERIFIED     → proceed

Reproduce mode: zero network — verification is skipped entirely (FR-009); the
pins were verified at init and the decision is replayed from answers.toml.

External tool absence/failure is NON-FATAL: a warning is emitted and the
module continues.  This mirrors the legacy WARN pattern in setup-ts.sh.

Invoked by the runner as:
    uv run module.py --plan <frozen_plan.json> --step write [--inspect]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
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


def _pkg_cmd(pkg_manager: str, *sub: str) -> list[str]:
    """Build a package-manager command list (bun or pnpm)."""
    return [pkg_manager, *sub]


def _pkgx_cmd(pkg_manager: str, *sub: str) -> list[str]:
    """Build a package-manager exec command (bunx or pnpm dlx)."""
    if pkg_manager == "bun":
        return ["bunx", *sub]
    return ["pnpm", "dlx", *sub]


# --------------------------------------------------------------------------- #
# package.json dep-merging helpers (stdlib json only)                          #
# --------------------------------------------------------------------------- #

def _split_npm_pin(pin: str) -> tuple[str, str]:
    """Split ``name@version`` → (name, version). Handles scoped ``@scope/pkg@X.Y.Z``
    by splitting on the LAST ``@``. Returns (pin, "") if there is no version."""
    s = str(pin).strip()
    at = s.rfind("@")
    if at <= 0:
        return s, ""
    return s[:at], s[at + 1:]


def _patch_package_json(
    pkg_json_path: Path,
    pinned_deps: list[str],
    dev_deps: list[str],
    package_manager_pin: str,
    warnings: list[str],
) -> bool:
    """Write merged runtime + dev deps into package.json.

    Strategy: read existing (if any), merge ``dependencies`` from pinned_deps
    and ``devDependencies`` from dev_deps (name→version, sorted keys), set the
    top-level ``packageManager`` field from package_manager_pin.  Writes with
    ``json.dumps(..., indent=2, sort_keys=True) + "\\n"`` for byte-stable
    determinism (Tier-1 guarantee: same answers → byte-identical output).

    Returns True if the file was written.  Never raises.
    """
    try:
        if pkg_json_path.exists():
            data = json.loads(pkg_json_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        else:
            data = {}

        # Merge runtime deps into data["dependencies"]
        existing_deps: dict[str, str] = dict(data.get("dependencies") or {})
        for pin in pinned_deps:
            name, version = _split_npm_pin(pin)
            if name and version:
                existing_deps[name] = version
        # Sort for determinism
        data["dependencies"] = dict(sorted(existing_deps.items()))

        # Merge dev deps into data["devDependencies"]
        existing_dev: dict[str, str] = dict(data.get("devDependencies") or {})
        for pin in dev_deps:
            name, version = _split_npm_pin(pin)
            if name and version:
                existing_dev[name] = version
        data["devDependencies"] = dict(sorted(existing_dev.items()))

        # Set packageManager field
        if package_manager_pin:
            data["packageManager"] = package_manager_pin

        pkg_json_path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return True
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"WARN: could not patch package.json: {exc}")
        return False


# --------------------------------------------------------------------------- #
# Step handlers                                                                #
# --------------------------------------------------------------------------- #

def _do_write(sdk, inputs, args) -> int:
    """write step: verify pins (init only), then write package.json + tooling."""
    pkg_manager: str = inputs.get_choice("package_manager", default="bun")
    framework: str = inputs.get_str("framework", default="plain") or "plain"
    pinned_deps: list[str] = inputs.get_list("pinned_deps", default=[])
    dev_deps: list[str] = inputs.get_list("dev_deps", default=[])
    package_manager_pin: str = inputs.get_str("package_manager_pin", default="")

    # Normalize framework to known values; treat unknowns as "plain"
    if framework not in ("nuxt", "vite", "plain", "sst"):
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

    # ── Pin verification (init mode only, FR-005/FR-012) ───────────────────── #
    # Include package_manager_pin in the verify batch (it is also a name@version)
    all_pins = list(pinned_deps) + list(dev_deps)
    if package_manager_pin:
        all_pins = all_pins + [package_manager_pin]

    if all_pins and inputs.mode == "init":
        verify_result = sdk.verify_pins(all_pins, "npm")

        bad_pins = [p for p, s in verify_result.items() if s == sdk.PIN_DISCONFIRMED]
        if bad_pins:
            error = sdk.SetupError(
                error_code=sdk.ErrorCode.INPUT_VALUE_INVALID,
                module_id="lang-ts",
                expected="all pins to exist on npm",
                received=f"disconfirmed pins: {bad_pins}",
                how_to_fix=(
                    "The agent proposed pins that do not exist on npm: "
                    + ", ".join(bad_pins)
                    + ". Re-run with --refresh lang-ts to let the agent correct them."
                ),
            )
            result = sdk.ModuleResult(
                module_id="lang-ts",
                step_id=args.step,
                status="error",
                files_written=[],
                diffs=[],
                warnings=warnings,
                error=error.to_dict(),
            )
            sdk.emit_result(result)
            return 1

        unreachable_pins = [p for p, s in verify_result.items() if s == sdk.PIN_UNREACHABLE]
        if unreachable_pins:
            warnings.append(
                "WARN: registry unreachable for pins: "
                + ", ".join(unreachable_pins)
                + " — manifest write SKIPPED (safe-skip, FR-012). "
                "Restore network connectivity and re-run to write the manifest."
            )
            result = sdk.ModuleResult(
                module_id="lang-ts",
                step_id=args.step,
                status="ok",
                files_written=[],
                diffs=[sdk.Diff(
                    path="package.json",
                    kind="skip",
                    preview="(safe-skip: registry unreachable for some pins)",
                )],
                warnings=warnings,
            )
            sdk.emit_result(result)
            return 0

    # ── 1. Framework scaffold (scaffolder runs are non-fatal; pinned write is separate) #
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

    else:  # plain / sst / unknown-treated-as-plain
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

        # tsconfig.json (write-if-absent) — deterministic write regardless of scaffolder
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

    # ── 2. Write pinned deps into package.json (deterministic, FR-005/FR-012) ─ #
    # This runs regardless of whether the scaffolder succeeded — the pinned
    # package.json write is a deterministic first-class action, not a scaffolder
    # side-effect.
    any_pins = bool(pinned_deps or dev_deps or package_manager_pin)
    if any_pins and not args.inspect:
        patched = _patch_package_json(
            project_dir / "package.json",
            pinned_deps=list(pinned_deps),
            dev_deps=list(dev_deps),
            package_manager_pin=package_manager_pin,
            warnings=warnings,
        )
        if patched:
            if "package.json" not in files_written:
                files_written.append("package.json")
            diffs.append(sdk.Diff(
                path="package.json",
                kind="modify",
                preview=(
                    f"(pinned deps written: {len(pinned_deps)} runtime, "
                    f"{len(dev_deps)} dev, packageManager={package_manager_pin!r})"
                ),
            ))
    elif any_pins and args.inspect:
        diffs.append(sdk.Diff(
            path="package.json",
            kind="modify",
            preview=(
                f"(would write {len(pinned_deps)} runtime pins + {len(dev_deps)} dev pins"
                + (f", packageManager={package_manager_pin!r}" if package_manager_pin else "")
                + ")"
            ),
        ))

    # ── 3. pkg install (non-fatal, skipped under inspect) ─────────────────── #
    if not args.inspect:
        _run_tool(
            _pkg_cmd(pkg_manager, "install"),
            cwd=project_dir,
            warnings=warnings,
            label=f"{pkg_manager} install",
        )

    # ── 4. Append Node .gitignore block ────────────────────────────────────── #
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

    # ── 5. Framework-specific .gitignore extras ─────────────────────────────── #
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

    # ── 6. Append biome pre-commit hook ────────────────────────────────────── #
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

            # ── 7. Append prettier pre-commit hook ──────────────────────────── #
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


STEP_HANDLERS = {
    "write": _do_write,
    # "resolve" is kind=agent — handled by the runner's Tier-2 agent subsystem.
    # "pins" is kind=gate — handled by the runner's gate subsystem.
}


def main() -> int:
    ap = argparse.ArgumentParser(description="lang-ts module")
    ap.add_argument("--plan", required=True, help="path to the frozen plan.json")
    ap.add_argument("--step", required=True, help="step id to run")
    ap.add_argument("--inspect", action="store_true", help="dry pass: preview, no write")
    args = ap.parse_args()

    handler = STEP_HANDLERS.get(args.step)
    if handler is None:
        print(
            f"Unknown step: {args.step!r}. "
            f"Python-handled steps: {list(STEP_HANDLERS)}. "
            f"Agent/gate steps are dispatched by the runner, not by module.py.",
            file=sys.stderr,
        )
        return 1

    sdk = _load_sdk()
    inputs = sdk.load_frozen_inputs(args.plan, module_id="lang-ts")
    return handler(sdk, inputs, args)


if __name__ == "__main__":
    raise SystemExit(main())
