"""End-to-end tests for the lang-rust module.

Verifies:
  - manifest parses and is valid (id, default_enabled=False, reconcile=True, order,
    write+run-generator+scaffold steps present)
  - happy path: config files written + gitignore/pre-commit appends with correct markers
    (toolchain stubbed offline — no real cargo, no network) — all under --step write
  - scaffold step: cargo init runs under --step scaffold (workspace=false)
  - workspace=true writes Cargo.toml workspace template in write step (no cargo binary needed)
  - workspace=true scaffold is a no-op (no error, status ok)
  - tool-missing → warn+continue (no raise, returncode==0)
  - idempotent re-run does NOT double-append (grep-guard works — run twice,
    assert /target appears exactly once in .gitignore, doublify once in .pre-commit-config.yaml)
  - --inspect writes nothing

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_lang_rust.py
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
_MODULE_REL = "modules/lang-rust"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(
    tmp: Path,
    workspace: bool = False,
    crate_kind: str = "",
) -> Path:
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["lang-rust"],
        "modules": {
            "lang-rust": {
                "id": "lang-rust",
                "version": "1.0.0",
                "reconcile": True,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "workspace": workspace,
                    "crate_kind": crate_kind,
                },
                "steps": [
                    {"id": "write", "kind": "python"},
                    {"id": "run-generator", "kind": "gate", "hardness": "soft", "skip_flag": "no-external-generators"},
                    {"id": "scaffold", "kind": "python"},
                ],
            }
        },
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _stub_cargo(tmp: Path) -> Path:
    """Write a fake cargo stub that succeeds silently."""
    stub_dir = tmp / "stubs"
    stub_dir.mkdir(exist_ok=True)
    stub = stub_dir / "cargo"
    stub.write_text("#!/bin/sh\nexit 0\n")
    stub.chmod(0o755)
    return stub_dir


def _run(
    project: Path,
    plan: Path,
    stub_dir: Path | None = None,
    *,
    step: str = "write",
    inspect: bool = False,
) -> subprocess.CompletedProcess:
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    cmd = ["uv", "run", str(module_py), "--plan", str(plan), "--step", step]
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
    assert mani.id == "lang-rust"
    assert mani.default_enabled is False, "language overlays must be opt-in (default_enabled=false)"
    assert mani.reconcile is True
    assert any(s.id == "write" and s.kind == "python" for s in mani.steps)
    assert any(s.id == "run-generator" and s.kind == "gate" for s in mani.steps)
    assert any(s.id == "scaffold" and s.kind == "python" for s in mani.steps)
    assert "gitignore-generate" in mani.order.get("after", [])
    assert "precommit-setup" in mani.order.get("after", [])

    input_keys = {inp.key for inp in mani.inputs}
    assert "workspace" in input_keys
    assert "crate_kind" in input_keys


# ── happy path (--step write) ─────────────────────────────────────────────────

def test_happy_path_creates_rustfmt_toml(tmp_path):
    """Happy path: rustfmt.toml is created with correct content (write step)."""
    project = tmp_path / "mycrate"
    project.mkdir()
    stub_dir = _stub_cargo(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path)

    proc = _run(project, plan, stub_dir)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"

    rustfmt = project / "rustfmt.toml"
    assert rustfmt.exists(), f"rustfmt.toml not created; files_written={result['files_written']}"
    content = rustfmt.read_text()
    assert 'edition = "2021"' in content
    assert "max_width = 100" in content


def test_happy_path_creates_clippy_toml(tmp_path):
    """Happy path: clippy.toml is created with correct content (write step)."""
    project = tmp_path / "mycrate"
    project.mkdir()
    stub_dir = _stub_cargo(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path)

    proc = _run(project, plan, stub_dir)
    assert proc.returncode == 0, proc.stderr

    clippy = project / "clippy.toml"
    assert clippy.exists(), "clippy.toml not created"
    content = clippy.read_text()
    assert "too-many-arguments-threshold" in content
    assert "type-complexity-threshold" in content


def test_happy_path_creates_rust_toolchain_toml(tmp_path):
    """Happy path: rust-toolchain.toml with stable channel (write step)."""
    project = tmp_path / "mycrate"
    project.mkdir()
    stub_dir = _stub_cargo(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path)

    proc = _run(project, plan, stub_dir)
    assert proc.returncode == 0, proc.stderr

    toolchain = project / "rust-toolchain.toml"
    assert toolchain.exists(), "rust-toolchain.toml not created"
    content = toolchain.read_text()
    assert 'channel = "stable"' in content
    assert "rustfmt" in content
    assert "clippy" in content


def test_happy_path_appends_gitignore_block(tmp_path):
    """Happy path: /target marker present in .gitignore after write step."""
    project = tmp_path / "mycrate"
    project.mkdir()
    stub_dir = _stub_cargo(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path)

    proc = _run(project, plan, stub_dir)
    assert proc.returncode == 0, proc.stderr

    gi_content = (project / ".gitignore").read_text()
    assert "/target" in gi_content, "gitignore /target marker missing"
    assert "**/*.rs.bk" in gi_content


def test_happy_path_appends_precommit_hooks(tmp_path):
    """Happy path: Rust pre-commit hooks appended (write step)."""
    project = tmp_path / "mycrate"
    project.mkdir()
    stub_dir = _stub_cargo(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    (project / ".pre-commit-config.yaml").write_text("repos:\n")
    plan = _frozen_plan(tmp_path)

    proc = _run(project, plan, stub_dir)
    assert proc.returncode == 0, proc.stderr

    pc_content = (project / ".pre-commit-config.yaml").read_text()
    assert "doublify/pre-commit-rust" in pc_content
    assert "id: fmt" in pc_content
    assert "id: clippy" in pc_content


# ── scaffold step (--step scaffold, workspace=false) ─────────────────────────

def test_scaffold_runs_cargo_init(tmp_path):
    """scaffold step: cargo init is invoked with the stub on PATH."""
    project = tmp_path / "mycrate"
    project.mkdir()
    stub_dir = _stub_cargo(tmp_path)
    plan = _frozen_plan(tmp_path, workspace=False)

    proc = _run(project, plan, stub_dir, step="scaffold")
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"


# ── workspace mode ────────────────────────────────────────────────────────────

def test_workspace_writes_cargo_toml_without_cargo_init(tmp_path):
    """workspace=true: Cargo.toml written from template in write step (no cargo binary needed)."""
    project = tmp_path / "myworkspace"
    project.mkdir()
    # No cargo stub — it should not be needed for workspace mode write step
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path, workspace=True)

    # Use empty bin to ensure cargo is absent
    empty_bin = tmp_path / "empty_bin"
    empty_bin.mkdir()
    proc = _run(project, plan, stub_dir=empty_bin)
    assert proc.returncode == 0, proc.stderr

    cargo_toml = project / "Cargo.toml"
    assert cargo_toml.exists(), "Cargo.toml not written for workspace mode"
    content = cargo_toml.read_text()
    assert "[workspace]" in content
    assert 'resolver = "2"' in content
    assert "members = []" in content


def test_workspace_scaffold_is_noop(tmp_path):
    """workspace=true: scaffold step is a no-op (no generator, status ok)."""
    project = tmp_path / "myworkspace"
    project.mkdir()
    plan = _frozen_plan(tmp_path, workspace=True)

    empty_bin = tmp_path / "empty_bin"
    empty_bin.mkdir()
    proc = _run(project, plan, stub_dir=empty_bin, step="scaffold")
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"


# ── tool-missing → warn+continue ─────────────────────────────────────────────

def test_tool_missing_warns_and_continues(tmp_path):
    """When cargo is absent, sdk.run_tool warns and returns False (no raise).

    After the _run_tool dedup (Part B), the implementation lives in sdk.py.
    Patch sdk_mod.shutil.which and call sdk_mod.run_tool directly.
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

    project = tmp_path / "mycrate"
    project.mkdir()
    warnings_out: list[str] = []

    import unittest.mock
    with unittest.mock.patch.object(sdk_mod.shutil, "which", return_value=None):
        ok = sdk_mod.run_tool(
            ["cargo", "init", "."],
            cwd=project,
            warnings=warnings_out,
            label="cargo init",
        )

    assert ok is False
    assert any("cargo" in w.lower() for w in warnings_out), (
        f"Expected warning about cargo missing; got: {warnings_out}"
    )


# ── idempotence ───────────────────────────────────────────────────────────────

def test_idempotent_no_double_append_gitignore(tmp_path):
    """/target marker must appear exactly once after two write-step runs."""
    project = tmp_path / "mycrate"
    project.mkdir()
    stub_dir = _stub_cargo(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path)

    _run(project, plan, stub_dir)
    _run(project, plan, stub_dir)

    gi_content = (project / ".gitignore").read_text()
    count = gi_content.count("/target")
    assert count == 1, f"/target appeared {count} times (expected 1) — double-append bug"


def test_idempotent_no_double_append_precommit(tmp_path):
    """doublify/pre-commit-rust marker must appear exactly once after two write-step runs."""
    project = tmp_path / "mycrate"
    project.mkdir()
    stub_dir = _stub_cargo(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    (project / ".pre-commit-config.yaml").write_text("repos:\n")
    plan = _frozen_plan(tmp_path)

    _run(project, plan, stub_dir)
    _run(project, plan, stub_dir)

    pc_content = (project / ".pre-commit-config.yaml").read_text()
    count = pc_content.count("doublify/pre-commit-rust")
    assert count == 1, f"doublify/pre-commit-rust appeared {count} times (expected 1) — double-append bug"


# ── inspect ───────────────────────────────────────────────────────────────────

def test_inspect_writes_nothing(tmp_path):
    """--inspect produces diffs but writes nothing to disk."""
    project = tmp_path / "mycrate"
    project.mkdir()
    stub_dir = _stub_cargo(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path)

    proc = _run(project, plan, stub_dir, inspect=True)
    assert proc.returncode == 0, proc.stderr

    assert not (project / "rustfmt.toml").exists()
    assert not (project / "clippy.toml").exists()
    assert not (project / "rust-toolchain.toml").exists()
