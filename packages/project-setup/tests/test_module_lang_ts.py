"""End-to-end tests for the lang-ts module.

Verifies:
  - manifest parses and is valid (id, default_enabled=False, reconcile=True, order)
  - happy path (plain framework): tsconfig.json written, node_modules in .gitignore,
    biome+prettier hooks appended  (toolchain stubbed offline — no real bun/pnpm)
  - nuxt framework: .nitro in .gitignore extras
  - tool-missing → warn+continue (no raise, returncode==0)
  - idempotent re-run does NOT double-append: node_modules appears once,
    biomejs appears once, rbubley/mirrors-prettier appears once
  - --inspect writes nothing

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_lang_ts.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
_PLUGIN_ROOT = _PKG / "skills" / "project-setup"
_RUNNER = _PLUGIN_ROOT / "runner"
_MODULE_REL = "modules/lang-ts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(
    tmp: Path,
    package_manager: str = "bun",
    framework: str = "plain",
    target: str = "",
    ui_kit: str = "",
) -> Path:
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["lang-ts"],
        "modules": {
            "lang-ts": {
                "id": "lang-ts",
                "version": "1.0.0",
                "reconcile": True,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "package_manager": package_manager,
                    "framework": framework,
                    "target": target,
                    "ui_kit": ui_kit,
                },
                "steps": [{"id": "write", "kind": "python"}],
            }
        },
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _stub_pkg_managers(tmp: Path, pkg_manager: str = "bun") -> Path:
    """Write fake bun/bunx/pnpm/nuxi stubs that succeed silently."""
    stub_dir = tmp / "stubs"
    stub_dir.mkdir(exist_ok=True)
    for name in ("bun", "bunx", "pnpm"):
        stub = stub_dir / name
        stub.write_text("#!/bin/sh\nexit 0\n")
        stub.chmod(0o755)
    return stub_dir


def _run(
    project: Path,
    plan: Path,
    stub_dir: Path | None = None,
    *,
    inspect: bool = False,
) -> subprocess.CompletedProcess:
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    cmd = ["uv", "run", str(module_py), "--plan", str(plan), "--step", "write"]
    if inspect:
        cmd.append("--inspect")
    env = {**os.environ, "PLUGIN_ROOT": str(_PLUGIN_ROOT), "PROJECT_DIR": str(project)}
    if stub_dir is not None:
        env["PATH"] = f"{stub_dir}:{env.get('PATH', '')}"
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))


# ── manifest ─────────────────────────────────────────────────────────────────

def test_manifest_parses_and_is_valid():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, mani.errors
    assert mani.id == "lang-ts"
    assert mani.default_enabled is False, "language overlays must be opt-in (default_enabled=false)"
    assert mani.reconcile is True
    assert any(s.id == "write" and s.kind == "python" for s in mani.steps)
    assert "gitignore-generate" in mani.order.get("after", [])
    assert "precommit-setup" in mani.order.get("after", [])

    input_keys = {inp.key for inp in mani.inputs}
    assert "package_manager" in input_keys
    assert "framework" in input_keys
    assert "target" in input_keys
    assert "ui_kit" in input_keys


# ── happy path: plain ─────────────────────────────────────────────────────────

def test_happy_path_plain_creates_tsconfig(tmp_path):
    """Happy path (plain): tsconfig.json is created with correct content."""
    project = tmp_path / "myapp"
    project.mkdir()
    stub_dir = _stub_pkg_managers(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path, framework="plain")

    proc = _run(project, plan, stub_dir)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"

    tsconfig = project / "tsconfig.json"
    assert tsconfig.exists(), f"tsconfig.json not created; files_written={result['files_written']}"
    content = tsconfig.read_text()
    assert '"strict": true' in content
    assert '"target": "ES2022"' in content
    assert '"moduleResolution": "Bundler"' in content


def test_happy_path_plain_appends_node_gitignore(tmp_path):
    """Happy path (plain): node_modules marker in .gitignore."""
    project = tmp_path / "myapp"
    project.mkdir()
    stub_dir = _stub_pkg_managers(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path, framework="plain")

    proc = _run(project, plan, stub_dir)
    assert proc.returncode == 0, proc.stderr

    gi_content = (project / ".gitignore").read_text()
    assert "node_modules" in gi_content, "node_modules marker missing from .gitignore"
    assert "*.tsbuildinfo" in gi_content


def test_happy_path_plain_appends_biome_and_prettier_hooks(tmp_path):
    """Happy path (plain): biome and prettier hooks appended to .pre-commit-config.yaml."""
    project = tmp_path / "myapp"
    project.mkdir()
    stub_dir = _stub_pkg_managers(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    (project / ".pre-commit-config.yaml").write_text("repos:\n")
    plan = _frozen_plan(tmp_path, framework="plain")

    proc = _run(project, plan, stub_dir)
    assert proc.returncode == 0, proc.stderr

    pc_content = (project / ".pre-commit-config.yaml").read_text()
    assert "biomejs/pre-commit" in pc_content
    assert "biome-check" in pc_content
    assert "rbubley/mirrors-prettier" in pc_content
    assert "types_or: [markdown, yaml]" in pc_content


# ── framework: nuxt ───────────────────────────────────────────────────────────

def test_nuxt_framework_appends_nitro_gitignore(tmp_path):
    """Nuxt framework: .nitro marker appended to .gitignore."""
    project = tmp_path / "mynuxtapp"
    project.mkdir()
    stub_dir = _stub_pkg_managers(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    # Simulate Nuxt already scaffolded so nuxi is not called
    (project / "nuxt.config.ts").write_text("export default defineNuxtConfig({})\n")
    plan = _frozen_plan(tmp_path, framework="nuxt")

    proc = _run(project, plan, stub_dir)
    assert proc.returncode == 0, proc.stderr

    gi_content = (project / ".gitignore").read_text()
    assert ".nitro" in gi_content, ".nitro marker missing from .gitignore for nuxt framework"
    assert ".data" in gi_content


# ── tool-missing → warn+continue ─────────────────────────────────────────────

def test_tool_missing_warns_and_continues(tmp_path):
    """When bun is absent, _run_tool warns and returns False (no raise).

    Tested in-process via monkeypatching shutil.which so that 'bun' is not
    found, without needing to shadow it in PATH (which would also hide uv).
    """
    runner_dir = _PLUGIN_ROOT / "runner"
    sdk_path = runner_dir / "sdk.py"
    sdk_spec = importlib.util.spec_from_file_location("ps_sdk", sdk_path)
    assert sdk_spec and sdk_spec.loader
    sdk_mod = importlib.util.module_from_spec(sdk_spec)
    sys.modules["ps_sdk"] = sdk_mod
    sdk_spec.loader.exec_module(sdk_mod)
    for dep in ("contracts", "plan"):
        if dep not in sys.modules:
            dspec = importlib.util.spec_from_file_location(dep, runner_dir / f"{dep}.py")
            assert dspec and dspec.loader
            dmod = importlib.util.module_from_spec(dspec)
            sys.modules[dep] = dmod
            dspec.loader.exec_module(dmod)

    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    mspec = importlib.util.spec_from_file_location("lang_ts_mod", module_py)
    assert mspec and mspec.loader
    mmod = importlib.util.module_from_spec(mspec)
    sys.modules["lang_ts_mod"] = mmod
    mspec.loader.exec_module(mmod)

    project = tmp_path / "myapp"
    project.mkdir()
    warnings_out: list[str] = []

    import unittest.mock
    with unittest.mock.patch.object(mmod.shutil, "which", return_value=None):
        ok = mmod._run_tool(
            ["bun", "init", "-y"],
            cwd=project,
            warnings=warnings_out,
            label="bun init",
        )

    assert ok is False
    assert any("bun" in w.lower() for w in warnings_out), (
        f"Expected warning about bun missing; got: {warnings_out}"
    )


# ── idempotence ───────────────────────────────────────────────────────────────

def test_idempotent_no_double_append_gitignore(tmp_path):
    """node_modules marker must appear exactly once after two runs."""
    project = tmp_path / "myapp"
    project.mkdir()
    stub_dir = _stub_pkg_managers(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path, framework="plain")

    _run(project, plan, stub_dir)
    _run(project, plan, stub_dir)

    gi_content = (project / ".gitignore").read_text()
    count = gi_content.count("node_modules")
    assert count == 1, f"node_modules appeared {count} times (expected 1) — double-append bug"


def test_idempotent_no_double_append_biome_hook(tmp_path):
    """biomejs/pre-commit marker must appear exactly once after two runs."""
    project = tmp_path / "myapp"
    project.mkdir()
    stub_dir = _stub_pkg_managers(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    (project / ".pre-commit-config.yaml").write_text("repos:\n")
    plan = _frozen_plan(tmp_path, framework="plain")

    _run(project, plan, stub_dir)
    _run(project, plan, stub_dir)

    pc_content = (project / ".pre-commit-config.yaml").read_text()
    count = pc_content.count("biomejs/pre-commit")
    assert count == 1, f"biomejs/pre-commit appeared {count} times (expected 1) — double-append bug"


def test_idempotent_no_double_append_prettier_hook(tmp_path):
    """rbubley/mirrors-prettier marker must appear exactly once after two runs."""
    project = tmp_path / "myapp"
    project.mkdir()
    stub_dir = _stub_pkg_managers(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    (project / ".pre-commit-config.yaml").write_text("repos:\n")
    plan = _frozen_plan(tmp_path, framework="plain")

    _run(project, plan, stub_dir)
    _run(project, plan, stub_dir)

    pc_content = (project / ".pre-commit-config.yaml").read_text()
    count = pc_content.count("rbubley/mirrors-prettier")
    assert count == 1, f"rbubley/mirrors-prettier appeared {count} times (expected 1) — double-append bug"


# ── inspect ───────────────────────────────────────────────────────────────────

def test_inspect_writes_nothing(tmp_path):
    """--inspect produces diffs but writes nothing to disk."""
    project = tmp_path / "myapp"
    project.mkdir()
    stub_dir = _stub_pkg_managers(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path, framework="plain")

    proc = _run(project, plan, stub_dir, inspect=True)
    assert proc.returncode == 0, proc.stderr

    # tsconfig.json must not be written in inspect mode
    assert not (project / "tsconfig.json").exists()
