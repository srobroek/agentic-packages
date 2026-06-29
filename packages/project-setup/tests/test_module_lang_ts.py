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
    """When bun is absent, sdk.run_tool warns and returns False (no raise).

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

    project = tmp_path / "myapp"
    project.mkdir()
    warnings_out: list[str] = []

    import unittest.mock
    with unittest.mock.patch.object(sdk_mod.shutil, "which", return_value=None):
        ok = sdk_mod.run_tool(
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


# ── SC-001 / SC-006: pin verification behaviour ───────────────────────────────

def _frozen_plan_with_pins(
    tmp: Path,
    *,
    mode: str = "init",
    framework: str = "plain",
    package_manager: str = "bun",
    pinned_deps: list[str] | None = None,
    dev_deps: list[str] | None = None,
    package_manager_pin: str = "bun@1.1.38",
) -> Path:
    """Build a frozen plan.json that carries resolved agent pins.

    Spec-013 fields (template_id, runtime, node_line, ui_kit_id,
    ui_kit_init_command) are omitted intentionally; the module defaults them
    to "none"/"bun"/"" via get_str defaults so these tests are unaffected.
    """
    plan = {
        "schema_version": 1,
        "mode": mode,
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
                    "target": "",
                    "ui_kit": "",
                    "pinned_deps": pinned_deps if pinned_deps is not None else ["vue@3.5.13"],
                    "dev_deps": dev_deps if dev_deps is not None else ["typescript@5.7.2", "@biomejs/biome@1.9.4"],
                    "package_manager_pin": package_manager_pin,
                    # Spec-013 defaults: template_id=none avoids template writes in
                    # pre-013 tests; runtime=bun avoids .node-version writes.
                    "template_id": "none",
                    "runtime": "bun",
                    "node_line": "",
                    "ui_kit_id": "none",
                    "ui_kit_init_command": "",
                    "test_runner": "",
                },
                "steps": [{"id": "write", "kind": "python"}],
            }
        },
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _load_module_inprocess():
    """Load module.py in-process with SDK pre-wired.

    Returns the loaded module object.  Idempotent: re-uses cached modules.
    """
    runner_dir = _PLUGIN_ROOT / "runner"
    # Pre-load SDK dependencies
    for dep in ("contracts", "plan", "sdk"):
        mod_key = dep if dep != "sdk" else "ps_sdk"
        if mod_key not in sys.modules:
            dspec = importlib.util.spec_from_file_location(
                mod_key, runner_dir / f"{dep}.py"
            )
            assert dspec and dspec.loader
            dmod = importlib.util.module_from_spec(dspec)
            sys.modules[mod_key] = dmod
            dspec.loader.exec_module(dmod)

    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    if "lang_ts_mod" in sys.modules:
        return sys.modules["lang_ts_mod"]
    mspec = importlib.util.spec_from_file_location("lang_ts_mod", module_py)
    assert mspec and mspec.loader
    mmod = importlib.util.module_from_spec(mspec)
    sys.modules["lang_ts_mod"] = mmod
    mspec.loader.exec_module(mmod)
    return mmod


def test_sc001_reproduce_mode_skips_verification(tmp_path):
    """SC-001 (reproduce path): mode='reproduce' → no verify_pins call, files written.

    In reproduce mode the module must write the manifest without calling the
    network at all — the pins were already verified at init.  We prove this by
    making the module's sdk.verify_pins raise if called (any call = test failure),
    then asserting the write still succeeds.
    """
    mmod = _load_module_inprocess()
    sdk = sys.modules["ps_sdk"]

    project = tmp_path / "myapp"
    project.mkdir()
    (project / ".gitignore").write_text("# base\n")

    plan_path = _frozen_plan_with_pins(
        tmp_path,
        mode="reproduce",
        framework="plain",
        pinned_deps=["vue@3.5.13"],
        dev_deps=["typescript@5.7.2"],
        package_manager_pin="bun@1.1.38",
    )

    import unittest.mock
    import types

    def _verify_should_not_be_called(*args, **kwargs):
        raise AssertionError("verify_pins must NOT be called in reproduce mode")

    args_ns = types.SimpleNamespace(step="write", inspect=False, plan=str(plan_path))

    with unittest.mock.patch.dict(os.environ, {"PROJECT_DIR": str(project), "PLUGIN_ROOT": str(_PLUGIN_ROOT)}):
        with unittest.mock.patch.object(sdk, "verify_pins", side_effect=_verify_should_not_be_called):
            inputs = sdk.load_frozen_inputs(str(plan_path), module_id="lang-ts")
            import io, contextlib
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                ret = mmod._do_write(sdk, inputs, args_ns)

    assert ret == 0, f"write step failed in reproduce mode: {captured.getvalue()}"
    result = json.loads(captured.getvalue())
    assert result["status"] == "ok", result


def test_sc001_disconfirmed_pin_rejected_and_nothing_written(tmp_path):
    """SC-001 (bad pin rejection): a disconfirmed pin → status=error, no files written.

    Uses monkeypatching to simulate a registry that returns disconfirmed for a
    hallucinated pin.  The module must return status=error and write nothing.
    """
    mmod = _load_module_inprocess()
    sdk = sys.modules["ps_sdk"]

    project = tmp_path / "myapp"
    project.mkdir()
    (project / ".gitignore").write_text("# base\n")

    # Plan with a hallucinated pin (vvue is a typosquat)
    plan_path = _frozen_plan_with_pins(
        tmp_path,
        mode="init",
        framework="plain",
        pinned_deps=["vvue@3.5.13"],   # hallucinated — disconfirmed
        dev_deps=["typescript@5.7.2"],
        package_manager_pin="bun@1.1.38",
    )

    import unittest.mock, types

    args_ns = types.SimpleNamespace(step="write", inspect=False, plan=str(plan_path))

    def _stub_verify(pins, ecosystem, **kwargs):
        result = {}
        for pin in pins:
            if "vvue" in pin:
                result[pin] = sdk.PIN_DISCONFIRMED
            else:
                result[pin] = sdk.PIN_VERIFIED
        return result

    with unittest.mock.patch.dict(os.environ, {"PROJECT_DIR": str(project), "PLUGIN_ROOT": str(_PLUGIN_ROOT)}):
        with unittest.mock.patch.object(sdk, "verify_pins", side_effect=_stub_verify):
            inputs = sdk.load_frozen_inputs(str(plan_path), module_id="lang-ts")
            import io, contextlib
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                ret = mmod._do_write(sdk, inputs, args_ns)

    assert ret == 1, "Expected non-zero exit for disconfirmed pin"
    result = json.loads(captured.getvalue())
    assert result["status"] == "error", result
    assert result["error"] is not None
    assert "vvue@3.5.13" in result["error"].get("received", ""), result["error"]

    # Critical: package.json must not have been written
    assert not (project / "package.json").exists(), \
        "Module wrote package.json despite a disconfirmed pin — violates FR-005"


def test_sc001_unreachable_registry_safe_skips(tmp_path):
    """SC-001 (offline safe-skip): unreachable registry → status=ok, manifest write skipped."""
    mmod = _load_module_inprocess()
    sdk = sys.modules["ps_sdk"]

    project = tmp_path / "myapp"
    project.mkdir()
    (project / ".gitignore").write_text("# base\n")

    plan_path = _frozen_plan_with_pins(
        tmp_path,
        mode="init",
        framework="plain",
        pinned_deps=["vue@3.5.13"],
        dev_deps=["typescript@5.7.2"],
        package_manager_pin="bun@1.1.38",
    )

    import unittest.mock, types, io, contextlib

    args_ns = types.SimpleNamespace(step="write", inspect=False, plan=str(plan_path))

    def _all_unreachable(pins, ecosystem, **kwargs):
        return {pin: sdk.PIN_UNREACHABLE for pin in pins}

    with unittest.mock.patch.dict(os.environ, {"PROJECT_DIR": str(project), "PLUGIN_ROOT": str(_PLUGIN_ROOT)}):
        with unittest.mock.patch.object(sdk, "verify_pins", side_effect=_all_unreachable):
            inputs = sdk.load_frozen_inputs(str(plan_path), module_id="lang-ts")
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                ret = mmod._do_write(sdk, inputs, args_ns)

    assert ret == 0, "Unreachable registry should be a safe-skip (ok), not an error"
    result = json.loads(captured.getvalue())
    assert result["status"] == "ok", result
    assert any("unreachable" in w.lower() or "registry" in w.lower() for w in result["warnings"]), \
        f"Expected registry-unreachable warning; got: {result['warnings']}"
    # Manifest write must be skipped — package.json should not exist
    assert not (project / "package.json").exists(), \
        "Module wrote package.json despite unreachable registry — violates FR-012"


def test_sc001_verified_pins_written_in_package_json(tmp_path):
    """SC-001 (happy path): all pins verified → package.json contains exact deps + devDeps + packageManager.

    Uses reproduce mode so no network is needed — pins are treated as pre-verified.
    """
    project = tmp_path / "myapp"
    project.mkdir()
    stub_dir = _stub_pkg_managers(tmp_path)
    (project / ".gitignore").write_text("# base\n")

    plan_path = _frozen_plan_with_pins(
        tmp_path,
        mode="reproduce",
        framework="plain",
        pinned_deps=["vue@3.5.13", "nuxt@3.14.0"],
        dev_deps=["typescript@5.7.2", "@biomejs/biome@1.9.4"],
        package_manager_pin="bun@1.1.38",
    )

    proc = _run(project, plan_path, stub_dir)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok", result

    pkg_json = project / "package.json"
    assert pkg_json.exists(), "package.json not written"
    data = json.loads(pkg_json.read_text())

    assert data.get("dependencies", {}).get("vue") == "3.5.13", \
        f"Expected vue=3.5.13 in dependencies; got: {data.get('dependencies')}"
    assert data.get("dependencies", {}).get("nuxt") == "3.14.0", \
        f"Expected nuxt=3.14.0 in dependencies; got: {data.get('dependencies')}"
    assert data.get("devDependencies", {}).get("typescript") == "5.7.2", \
        f"Expected typescript=5.7.2 in devDependencies; got: {data.get('devDependencies')}"
    assert data.get("devDependencies", {}).get("@biomejs/biome") == "1.9.4", \
        f"Expected @biomejs/biome=1.9.4 in devDependencies; got: {data.get('devDependencies')}"
    assert data.get("packageManager") == "bun@1.1.38", \
        f"Expected packageManager=bun@1.1.38; got: {data.get('packageManager')}"


# ── SC-006: deterministic package.json write (no scaffolder dependency) ──────

def test_sc006_pinned_package_json_is_deterministic(tmp_path):
    """SC-006: two runs with the same answers produce byte-identical package.json."""
    project = tmp_path / "myapp"
    project.mkdir()
    stub_dir = _stub_pkg_managers(tmp_path)
    (project / ".gitignore").write_text("# base\n")

    plan_path = _frozen_plan_with_pins(
        tmp_path,
        mode="reproduce",
        framework="plain",
        package_manager="pnpm",  # consistent with package_manager_pin=pnpm@9.14.2
        pinned_deps=["vue@3.5.13"],
        dev_deps=["typescript@5.7.2", "@biomejs/biome@1.9.4"],
        package_manager_pin="pnpm@9.14.2",
    )

    # First run
    proc1 = _run(project, plan_path, stub_dir)
    assert proc1.returncode == 0, proc1.stderr
    content1 = (project / "package.json").read_bytes()

    # Remove package.json to force a fresh write on the second run
    (project / "package.json").unlink()

    # Second run
    proc2 = _run(project, plan_path, stub_dir)
    assert proc2.returncode == 0, proc2.stderr
    content2 = (project / "package.json").read_bytes()

    assert content1 == content2, (
        "package.json is not byte-identical across two runs — Tier-1 determinism violated.\n"
        f"Run 1:\n{content1.decode()}\nRun 2:\n{content2.decode()}"
    )


# ── spec 013 Phase 1: manifest-level assertions ───────────────────────────────

def test_013_manifest_no_errors():
    """spec 013 Phase 1: manifest parses with no errors (when predicate on declared ui_kit_id)."""
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, (
        "lang-ts manifest has errors after spec-013 Phase 1 changes: "
        + str(mani.errors)
    )


def test_013_six_new_inputs_declared():
    """spec 013 Phase 1: all six new agent-decided inputs are declared."""
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    input_keys = {inp.key for inp in mani.inputs}
    for key in ("test_runner", "template_id", "ui_kit_id", "ui_kit_init_command", "runtime", "node_line"):
        assert key in input_keys, f"Expected declared input '{key}' in lang-ts manifest"


def test_013_step_order():
    """spec 013 Phase 1: step IDs are in the exact order mandated by FR-019."""
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert [s.id for s in mani.steps] == [
        "resolve",
        "pins",
        "write",
        "run-generator",
        "scaffold",
        "ui-kit-init",
        "ui-kit-scaffold",
    ], f"Unexpected step order: {[s.id for s in mani.steps]}"


def test_013_ui_kit_init_step_fields():
    """spec 013 Phase 1: ui-kit-init gate step has correct kind, hardness, init_only, allow_flag, when."""
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    step = next((s for s in mani.steps if s.id == "ui-kit-init"), None)
    assert step is not None, "ui-kit-init step not found in manifest"
    assert step.kind == "gate", f"Expected kind=gate, got: {step.kind!r}"
    assert step.hardness == "hard", f"Expected hardness=hard, got: {step.hardness!r}"
    assert step.init_only is True, "Expected init_only=True"
    assert step.allow_flag == "allow-ui-kit-init", (
        f"Expected allow_flag='allow-ui-kit-init', got: {step.allow_flag!r}"
    )
    assert step.when == "ui_kit_id != none", (
        f"Expected when='ui_kit_id != none', got: {step.when!r}"
    )


def test_013_ui_kit_scaffold_step_is_python():
    """spec 013 Phase 1: ui-kit-scaffold step is kind=python."""
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    step = next((s for s in mani.steps if s.id == "ui-kit-scaffold"), None)
    assert step is not None, "ui-kit-scaffold step not found in manifest"
    assert step.kind == "python", f"Expected kind=python, got: {step.kind!r}"


def test_sc006_scaffolder_absence_does_not_block_pinned_write(tmp_path):
    """SC-006: when scaffolder (bun/pnpm) is absent, package.json is still written with pins.

    The pinned package.json write is deterministic and independent of whether
    the scaffolder ran.  Scaffolder absence is warn+continue; the pin write proceeds.
    """
    project = tmp_path / "myapp"
    project.mkdir()
    # Empty PATH: no bun, no pnpm — scaffolders will warn+skip
    empty_stub = tmp_path / "empty_stubs"
    empty_stub.mkdir()

    plan_path = _frozen_plan_with_pins(
        tmp_path,
        mode="reproduce",
        framework="plain",
        pinned_deps=["vue@3.5.13"],
        dev_deps=["typescript@5.7.2"],
        package_manager_pin="bun@1.1.38",
    )
    (project / ".gitignore").write_text("# base\n")

    proc = _run(project, plan_path, empty_stub)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok", result

    # Warnings about scaffolder being absent are expected (warn+continue)
    # but the package.json with pinned deps must exist
    pkg_json = project / "package.json"
    assert pkg_json.exists(), (
        "package.json not written despite valid pins — scaffolder absence blocked the write.\n"
        f"warnings: {result.get('warnings')}"
    )
    data = json.loads(pkg_json.read_text())
    assert data.get("dependencies", {}).get("vue") == "3.5.13"
    assert data.get("packageManager") == "bun@1.1.38"


# ── spec 013 Phase 2 & 3: helper + new tests ─────────────────────────────────

def _frozen_plan_013(
    tmp: Path,
    *,
    mode: str = "reproduce",
    framework: str = "vite",
    package_manager: str = "bun",
    pinned_deps: list[str] | None = None,
    dev_deps: list[str] | None = None,
    package_manager_pin: str = "bun@1.1.38",
    template_id: str = "none",
    runtime: str = "bun",
    node_line: str = "",
    ui_kit_id: str = "none",
    ui_kit_init_command: str = "",
    step_id: str = "write",
) -> Path:
    """Build a frozen plan for spec-013 Phase 2/3 tests (write or ui-kit-scaffold step)."""
    plan = {
        "schema_version": 1,
        "mode": mode,
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
                    "target": "",
                    "ui_kit": "",
                    "pinned_deps": pinned_deps if pinned_deps is not None else [],
                    "dev_deps": dev_deps if dev_deps is not None else [],
                    "package_manager_pin": package_manager_pin,
                    "template_id": template_id,
                    "runtime": runtime,
                    "node_line": node_line,
                    "ui_kit_id": ui_kit_id,
                    "ui_kit_init_command": ui_kit_init_command,
                    "test_runner": "",
                },
                "steps": [{"id": step_id, "kind": "python"}],
            }
        },
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _run_step(
    project: Path,
    plan: Path,
    stub_dir: Path | None = None,
    *,
    step: str = "write",
    inspect: bool = False,
) -> "subprocess.CompletedProcess":
    """Run an arbitrary step (write or ui-kit-scaffold) via uv run."""
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    cmd = ["uv", "run", str(module_py), "--plan", str(plan), "--step", step]
    if inspect:
        cmd.append("--inspect")
    env = {**os.environ, "PLUGIN_ROOT": str(_PLUGIN_ROOT), "PROJECT_DIR": str(project)}
    if stub_dir is not None:
        env["PATH"] = f"{stub_dir}:{env.get('PATH', '')}"
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))


# ── SC-001 (spec 013): vite + vitest-browser template + bun → writes vitest.config.ts ─

def test_013_sc001_vitest_browser_template_written(tmp_path):
    """SC-001: framework=vite, template_id=vitest-browser, package_manager=bun,
    package_manager_pin=bun@1.1.38 → writes package.json (packageManager=bun@1.1.38),
    vitest.config.ts from templates/vitest-browser/, NO .node-version."""
    project = tmp_path / "myapp"
    project.mkdir()
    stub_dir = _stub_pkg_managers(tmp_path)
    (project / ".gitignore").write_text("# base\n")

    plan_path = _frozen_plan_013(
        tmp_path,
        mode="reproduce",
        framework="vite",
        package_manager="bun",
        package_manager_pin="bun@1.1.38",
        template_id="vitest-browser",
        runtime="bun",
        node_line="",
    )

    proc = _run_step(project, plan_path, stub_dir, step="write")
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok", result

    # vitest.config.ts written from template
    vitest_config = project / "vitest.config.ts"
    assert vitest_config.exists(), "vitest.config.ts not written"
    content = vitest_config.read_text()
    assert "jsdom" in content, "expected jsdom environment in vitest-browser template"
    assert "defineConfig" in content

    # package.json with packageManager
    pkg_json = project / "package.json"
    assert pkg_json.exists(), "package.json not written"
    data = json.loads(pkg_json.read_text())
    assert data.get("packageManager") == "bun@1.1.38"

    # No .node-version for bun runtime
    assert not (project / ".node-version").exists(), ".node-version must NOT be written for bun runtime"


# ── SC-002 (spec 013): two _do_write invocations → byte-identical output ─────

def test_013_sc002_write_is_byte_identical(tmp_path):
    """SC-002: two runs with the same frozen plan produce byte-identical files."""
    project = tmp_path / "myapp"
    project.mkdir()
    stub_dir = _stub_pkg_managers(tmp_path)
    (project / ".gitignore").write_text("# base\n")

    plan_path = _frozen_plan_013(
        tmp_path,
        mode="reproduce",
        framework="vite",
        package_manager="bun",
        package_manager_pin="bun@1.1.38",
        template_id="vitest-browser",
        runtime="bun",
        node_line="",
    )

    proc1 = _run_step(project, plan_path, stub_dir, step="write")
    assert proc1.returncode == 0, proc1.stderr
    content_vitest1 = (project / "vitest.config.ts").read_bytes()
    content_pkg1 = (project / "package.json").read_bytes()

    # Delete files so second run writes fresh
    (project / "vitest.config.ts").unlink()
    (project / "package.json").unlink()

    proc2 = _run_step(project, plan_path, stub_dir, step="write")
    assert proc2.returncode == 0, proc2.stderr
    content_vitest2 = (project / "vitest.config.ts").read_bytes()
    content_pkg2 = (project / "package.json").read_bytes()

    assert content_vitest1 == content_vitest2, (
        "vitest.config.ts is not byte-identical across two runs — Tier-1 determinism violated"
    )
    assert content_pkg1 == content_pkg2, (
        "package.json is not byte-identical across two runs — Tier-1 determinism violated"
    )


# ── SC-006 (spec 013): runtime=node → .node-version + engines + packageManager ─

def test_013_sc006_node_runtime_writes_node_version_and_engines(tmp_path):
    """SC-006: runtime=node, node_line=22, pnpm@9.14.2 → .node-version=22, engines.node=>=22."""
    project = tmp_path / "myapp"
    project.mkdir()
    stub_dir = _stub_pkg_managers(tmp_path)
    (project / ".gitignore").write_text("# base\n")

    plan_path = _frozen_plan_013(
        tmp_path,
        mode="reproduce",
        framework="plain",
        package_manager="pnpm",
        package_manager_pin="pnpm@9.14.2",
        template_id="none",
        runtime="node",
        node_line="22",
    )

    proc = _run_step(project, plan_path, stub_dir, step="write")
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok", result

    # .node-version written
    nv = project / ".node-version"
    assert nv.exists(), ".node-version not written for runtime=node"
    assert nv.read_text() == "22\n", f"Expected '22\\n', got {nv.read_text()!r}"

    # package.json: engines + packageManager
    pkg_json = project / "package.json"
    assert pkg_json.exists()
    data = json.loads(pkg_json.read_text())
    assert data.get("engines", {}).get("node") == ">=22", (
        f"Expected engines.node=>=22; got: {data.get('engines')}"
    )
    assert data.get("packageManager") == "pnpm@9.14.2", (
        f"Expected packageManager=pnpm@9.14.2; got: {data.get('packageManager')}"
    )


# ── SC-007 (spec 013): bun@latest → INPUT_VALUE_INVALID ──────────────────────

def test_013_sc007_pm_pin_latest_rejected(tmp_path):
    """SC-007: package_manager_pin='bun@latest' → INPUT_VALUE_INVALID, nothing written."""
    mmod = _load_module_inprocess()
    sdk = sys.modules["ps_sdk"]

    project = tmp_path / "myapp"
    project.mkdir()
    (project / ".gitignore").write_text("# base\n")

    plan_path = _frozen_plan_013(
        tmp_path,
        mode="init",
        framework="plain",
        package_manager="bun",
        package_manager_pin="bun@latest",
        template_id="none",
        runtime="bun",
        node_line="",
    )

    import unittest.mock, types, io as _io, contextlib

    args_ns = types.SimpleNamespace(step="write", inspect=False, plan=str(plan_path))

    def _stub_verify(pins, ecosystem, **kwargs):
        return {p: sdk.PIN_VERIFIED for p in pins}

    with unittest.mock.patch.dict(os.environ, {"PROJECT_DIR": str(project), "PLUGIN_ROOT": str(_PLUGIN_ROOT)}):
        with unittest.mock.patch.object(sdk, "verify_pins", side_effect=_stub_verify):
            inputs = sdk.load_frozen_inputs(str(plan_path), module_id="lang-ts")
            captured = _io.StringIO()
            with contextlib.redirect_stdout(captured):
                ret = mmod._do_write(sdk, inputs, args_ns)

    assert ret == 1, "Expected non-zero exit for bun@latest pin"
    result = json.loads(captured.getvalue())
    assert result["status"] == "error", result
    assert result["error"] is not None
    error_text = str(result["error"])
    assert "bun@latest" in error_text or "INPUT_VALUE_INVALID" in error_text or "invalid" in error_text.lower(), (
        f"Expected INPUT_VALUE_INVALID about bun@latest; got: {result['error']}"
    )
    # Nothing written
    assert not (project / "package.json").exists(), "package.json must not be written for invalid pin"


# ── SC-008 (spec 013): PM/pin mismatch → INPUT_VALUE_INVALID ──────────────────

def test_013_sc008_pm_pin_mismatch_rejected(tmp_path):
    """SC-008: package_manager=bun, package_manager_pin=pnpm@9.14.2 → INPUT_VALUE_INVALID."""
    mmod = _load_module_inprocess()
    sdk = sys.modules["ps_sdk"]

    project = tmp_path / "myapp"
    project.mkdir()
    (project / ".gitignore").write_text("# base\n")

    plan_path = _frozen_plan_013(
        tmp_path,
        mode="init",
        framework="plain",
        package_manager="bun",
        package_manager_pin="pnpm@9.14.2",  # mismatch: PM=bun but pin=pnpm
        template_id="none",
        runtime="bun",
        node_line="",
    )

    import unittest.mock, types, io as _io, contextlib

    args_ns = types.SimpleNamespace(step="write", inspect=False, plan=str(plan_path))

    def _stub_verify(pins, ecosystem, **kwargs):
        return {p: sdk.PIN_VERIFIED for p in pins}

    with unittest.mock.patch.dict(os.environ, {"PROJECT_DIR": str(project), "PLUGIN_ROOT": str(_PLUGIN_ROOT)}):
        with unittest.mock.patch.object(sdk, "verify_pins", side_effect=_stub_verify):
            inputs = sdk.load_frozen_inputs(str(plan_path), module_id="lang-ts")
            captured = _io.StringIO()
            with contextlib.redirect_stdout(captured):
                ret = mmod._do_write(sdk, inputs, args_ns)

    assert ret == 1, "Expected non-zero exit for PM/pin mismatch"
    result = json.loads(captured.getvalue())
    assert result["status"] == "error", result
    assert result["error"] is not None
    assert not (project / "package.json").exists(), "package.json must not be written for PM/pin mismatch"


# ── SC-009 (spec 013): unknown template_id → INPUT_VALUE_INVALID ──────────────

def test_013_sc009_unknown_template_id_rejected(tmp_path):
    """SC-009: template_id='bogus' → INPUT_VALUE_INVALID, no config file written."""
    mmod = _load_module_inprocess()
    sdk = sys.modules["ps_sdk"]

    project = tmp_path / "myapp"
    project.mkdir()
    (project / ".gitignore").write_text("# base\n")

    plan_path = _frozen_plan_013(
        tmp_path,
        mode="init",
        framework="plain",
        package_manager="bun",
        package_manager_pin="bun@1.1.38",
        template_id="bogus",  # not in _ALLOWED_TEMPLATE_IDS
        runtime="bun",
        node_line="",
    )

    import unittest.mock, types, io as _io, contextlib

    args_ns = types.SimpleNamespace(step="write", inspect=False, plan=str(plan_path))

    def _stub_verify(pins, ecosystem, **kwargs):
        return {p: sdk.PIN_VERIFIED for p in pins}

    with unittest.mock.patch.dict(os.environ, {"PROJECT_DIR": str(project), "PLUGIN_ROOT": str(_PLUGIN_ROOT)}):
        with unittest.mock.patch.object(sdk, "verify_pins", side_effect=_stub_verify):
            inputs = sdk.load_frozen_inputs(str(plan_path), module_id="lang-ts")
            captured = _io.StringIO()
            with contextlib.redirect_stdout(captured):
                ret = mmod._do_write(sdk, inputs, args_ns)

    assert ret == 1, "Expected non-zero exit for bogus template_id"
    result = json.loads(captured.getvalue())
    assert result["status"] == "error", result
    # No config file should exist
    assert not (project / "vitest.config.ts").exists(), "vitest.config.ts must not be written for invalid template_id"
    assert not (project / "playwright.config.ts").exists(), "playwright.config.ts must not be written for invalid template_id"


# ── SC-010 (spec 013): bad ui_kit_init_command → INPUT_VALUE_INVALID ──────────

def test_013_sc010_bad_ui_kit_init_command_rejected(tmp_path):
    """SC-010: ui_kit_id=shadcn, ui_kit_init_command='rm -rf /' → INPUT_VALUE_INVALID."""
    mmod = _load_module_inprocess()
    sdk = sys.modules["ps_sdk"]

    project = tmp_path / "myapp"
    project.mkdir()

    plan_path = _frozen_plan_013(
        tmp_path,
        mode="init",
        package_manager="bun",
        package_manager_pin="bun@1.1.38",
        ui_kit_id="shadcn",
        ui_kit_init_command="rm -rf /",  # not in allowlist
        step_id="ui-kit-scaffold",
    )

    import unittest.mock, types, io as _io, contextlib

    args_ns = types.SimpleNamespace(step="ui-kit-scaffold", inspect=False, plan=str(plan_path))

    with unittest.mock.patch.dict(os.environ, {"PROJECT_DIR": str(project), "PLUGIN_ROOT": str(_PLUGIN_ROOT)}):
        inputs = sdk.load_frozen_inputs(str(plan_path), module_id="lang-ts")
        captured = _io.StringIO()
        with contextlib.redirect_stdout(captured):
            ret = mmod._do_ui_kit_scaffold(sdk, inputs, args_ns)

    assert ret == 1, "Expected non-zero exit for disallowed ui_kit_init_command"
    result = json.loads(captured.getvalue())
    assert result["status"] == "error", result
    assert result["error"] is not None


# ── SC-012 (spec 013): ui_kit_id=none → _do_ui_kit_scaffold no-op ────────────

def test_013_sc012_ui_kit_id_none_is_noop(tmp_path):
    """SC-012: ui_kit_id=none → _do_ui_kit_scaffold returns 0, nothing executed."""
    mmod = _load_module_inprocess()
    sdk = sys.modules["ps_sdk"]

    project = tmp_path / "myapp"
    project.mkdir()

    plan_path = _frozen_plan_013(
        tmp_path,
        mode="init",
        package_manager="bun",
        package_manager_pin="bun@1.1.38",
        ui_kit_id="none",
        ui_kit_init_command="",
        step_id="ui-kit-scaffold",
    )

    import unittest.mock, types, io as _io, contextlib

    args_ns = types.SimpleNamespace(step="ui-kit-scaffold", inspect=False, plan=str(plan_path))

    run_tool_called = []

    def _should_not_run(*args, **kwargs):
        run_tool_called.append(args)
        return False

    with unittest.mock.patch.dict(os.environ, {"PROJECT_DIR": str(project), "PLUGIN_ROOT": str(_PLUGIN_ROOT)}):
        with unittest.mock.patch.object(sdk, "run_tool", side_effect=_should_not_run):
            inputs = sdk.load_frozen_inputs(str(plan_path), module_id="lang-ts")
            captured = _io.StringIO()
            with contextlib.redirect_stdout(captured):
                ret = mmod._do_ui_kit_scaffold(sdk, inputs, args_ns)

    assert ret == 0, "Expected 0 for ui_kit_id=none"
    result = json.loads(captured.getvalue())
    assert result["status"] == "ok", result
    assert not run_tool_called, "run_tool must NOT be called when ui_kit_id=none"


# ── reproduce safe-skip (spec 013 FR-010, SC-005): ui-kit-scaffold writes note ─

def test_013_ui_kit_scaffold_reproduce_safe_skips(tmp_path):
    """Reproduce path: ui_kit_id=shadcn + valid command + mode=reproduce →
    STACK-NOTES.md written with command, run_tool NOT called."""
    mmod = _load_module_inprocess()
    sdk = sys.modules["ps_sdk"]

    project = tmp_path / "myapp"
    project.mkdir()

    plan_path = _frozen_plan_013(
        tmp_path,
        mode="reproduce",  # not init → safe-skip
        package_manager="bun",
        package_manager_pin="bun@1.1.38",
        ui_kit_id="shadcn",
        ui_kit_init_command="bunx shadcn@latest init --defaults",
        step_id="ui-kit-scaffold",
    )

    import unittest.mock, types, io as _io, contextlib

    args_ns = types.SimpleNamespace(step="ui-kit-scaffold", inspect=False, plan=str(plan_path))

    run_tool_called = []

    def _should_not_run(*args, **kwargs):
        run_tool_called.append(args)
        return False

    with unittest.mock.patch.dict(os.environ, {"PROJECT_DIR": str(project), "PLUGIN_ROOT": str(_PLUGIN_ROOT)}):
        with unittest.mock.patch.object(sdk, "run_tool", side_effect=_should_not_run):
            inputs = sdk.load_frozen_inputs(str(plan_path), module_id="lang-ts")
            captured = _io.StringIO()
            with contextlib.redirect_stdout(captured):
                ret = mmod._do_ui_kit_scaffold(sdk, inputs, args_ns)

    assert ret == 0, f"Expected 0 for safe-skip; got {ret}; stdout={captured.getvalue()}"
    result = json.loads(captured.getvalue())
    assert result["status"] == "ok", result
    assert not run_tool_called, "run_tool must NOT be called on reproduce"

    # STACK-NOTES.md must contain the init command
    stack_notes = project / "STACK-NOTES.md"
    assert stack_notes.exists(), "STACK-NOTES.md not written on reproduce safe-skip"
    notes_content = stack_notes.read_text()
    assert "bunx shadcn@latest init --defaults" in notes_content, (
        f"Expected init command in STACK-NOTES.md; got:\n{notes_content}"
    )
