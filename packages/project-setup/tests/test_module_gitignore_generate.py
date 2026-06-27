"""End-to-end tests for the gitignore-generate module.

Verifies:
  - manifest parses and is valid (id, default_enabled, reconcile, inputs, after order)
  - .gitignore is created containing selected base templates + verbatim custom block
  - deterministic byte-identical output across two runs (vendored, dynamic_fetch=false)
  - --inspect writes nothing
  - reconcile=true: second run with identical content → all-skip diffs
  - dynamic_fetch=true with OFFLINE monkeypatch: warns + continues with vendored only
    (no real network in tests — uses unittest.mock to stub _fetch_template)

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_gitignore_generate.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import textwrap
import unittest.mock
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
_PLUGIN_ROOT = _PKG / "skills" / "project-setup"
_RUNNER = _PLUGIN_ROOT / "runner"
_MODULE_REL = "modules/gitignore-generate"
_TEMPLATES_DIR = _PLUGIN_ROOT / _MODULE_REL / "templates" / "gitignore"

# The exact custom block that must always appear in .gitignore (from monolith lines 915-930).
_CUSTOM_BLOCK_MARKERS = [
    "# Environment",
    ".env",
    ".env.*",
    "!.env.example",
    "# Fastembed",
    ".fastembed_cache",
    "# Repomix local snapshots",
    "repomix.xml",
    "repomix.md",
    "repomix.json",
    "repomix.txt",
]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(
    tmp: Path,
    templates: list[str] | None = None,
    dynamic_fetch: bool = False,
) -> Path:
    if templates is None:
        templates = ["macos", "linux", "windows", "jetbrains", "vscode", "vim", "backup", "patch", "gpg"]
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["gitignore-generate"],
        "modules": {
            "gitignore-generate": {
                "id": "gitignore-generate",
                "version": "1.0.0",
                "reconcile": True,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "templates": templates,
                    "dynamic_fetch": dynamic_fetch,
                },
                "steps": [{"id": "write", "kind": "python"}],
            }
        },
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _run(project: Path, plan: Path, *, inspect: bool = False) -> subprocess.CompletedProcess:
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    cmd = ["uv", "run", str(module_py), "--plan", str(plan), "--step", "write"]
    if inspect:
        cmd.append("--inspect")
    env = {**os.environ, "PLUGIN_ROOT": str(_PLUGIN_ROOT), "PROJECT_DIR": str(project)}
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))


def test_manifest_parses_and_is_valid():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, mani.errors
    assert mani.id == "gitignore-generate"
    assert mani.default_enabled is True
    assert mani.reconcile is True
    assert any(s.id == "write" and s.kind == "python" for s in mani.steps)
    assert mani.order.get("after") == ["dirs-scaffold"]

    # Check inputs are declared
    input_keys = {inp.key for inp in mani.inputs}
    assert "templates" in input_keys
    assert "dynamic_fetch" in input_keys


def test_creates_gitignore_with_base_templates(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, templates=["macos", "linux", "windows"])
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert ".gitignore" in result["files_written"]

    content = (project / ".gitignore").read_text()
    # macOS template content
    assert ".DS_Store" in content
    # Linux template content
    assert ".fuse_hidden*" in content
    # Windows template content
    assert "Thumbs.db" in content


def test_gitignore_contains_custom_block(tmp_path):
    """The verbatim custom block (lines 915-930 of monolith) must always appear."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    _run(project, plan)

    content = (project / ".gitignore").read_text()
    for marker in _CUSTOM_BLOCK_MARKERS:
        assert marker in content, f"Custom block marker missing: {marker!r}"


def test_deterministic_byte_identical_two_runs(tmp_path):
    """Tier-1 guarantee: vendored, dynamic_fetch=false → byte-identical across runs."""
    project_a = tmp_path / "proj_a"
    project_a.mkdir()
    project_b = tmp_path / "proj_b"
    project_b.mkdir()

    plan_a_dir = tmp_path / "plan_a"
    plan_a_dir.mkdir()
    plan_b_dir = tmp_path / "plan_b"
    plan_b_dir.mkdir()
    plan_a = _frozen_plan(plan_a_dir, templates=["macos", "linux", "gpg"])
    plan_b = _frozen_plan(plan_b_dir, templates=["macos", "linux", "gpg"])

    proc_a = _run(project_a, plan_a)
    proc_b = _run(project_b, plan_b)
    assert proc_a.returncode == 0, proc_a.stderr
    assert proc_b.returncode == 0, proc_b.stderr

    bytes_a = (project_a / ".gitignore").read_bytes()
    bytes_b = (project_b / ".gitignore").read_bytes()
    assert bytes_a == bytes_b, "Output is not byte-identical across two independent runs"


def test_inspect_writes_nothing(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)

    assert result["diffs"][0]["kind"] == "create"
    assert not (project / ".gitignore").exists()


def test_idempotent_second_run_all_skip(tmp_path):
    """reconcile=true: second run with identical .gitignore → diff is skip."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    _run(project, plan)
    proc2 = _run(project, plan)
    assert proc2.returncode == 0, proc2.stderr
    result = json.loads(proc2.stdout)
    assert result["files_written"] == []
    assert result["diffs"][0]["kind"] == "skip"


def test_subset_templates_only_includes_selected(tmp_path):
    """When only 'gpg' is selected, .gitignore must not contain macOS content."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, templates=["gpg"])
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr

    content = (project / ".gitignore").read_text()
    assert "secring.*" in content  # gpg template content
    assert ".DS_Store" not in content  # macOS must not appear


def test_dynamic_fetch_offline_warns_and_continues(tmp_path):
    """dynamic_fetch=true with a name not in vendored set: warns + continues, no crash.

    This test monkeypatches _fetch_template to simulate an offline environment.
    The vendored templates (e.g. 'macos') still render from disk.
    An unknown name that would require a fetch gets a warning, not an exception.

    We inject the monkeypatch via a side-car script that patches the module at
    import time, because module.py is run as a subprocess via uv run. Instead,
    we test the module logic directly by importing it in-process with a patched
    fetch function.
    """
    # Load the module in-process so we can monkeypatch _fetch_template.
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"

    # We need the SDK loaded first (the module's _load_sdk() will be called
    # indirectly via imports). Load it into sys.modules.
    sdk_path = _PLUGIN_ROOT / "runner" / "sdk.py"
    sdk_spec = importlib.util.spec_from_file_location("ps_sdk", sdk_path)
    assert sdk_spec and sdk_spec.loader
    sdk_mod = importlib.util.module_from_spec(sdk_spec)
    sys.modules["ps_sdk"] = sdk_mod
    sdk_spec.loader.exec_module(sdk_mod)

    # Load contracts and plan modules (SDK deps).
    runner_dir = _PLUGIN_ROOT / "runner"
    for dep in ("contracts", "plan"):
        if dep not in sys.modules:
            dspec = importlib.util.spec_from_file_location(dep, runner_dir / f"{dep}.py")
            assert dspec and dspec.loader
            dmod = importlib.util.module_from_spec(dspec)
            sys.modules[dep] = dmod
            dspec.loader.exec_module(dmod)

    gi_spec = importlib.util.spec_from_file_location("gitignore_generate_mod", module_py)
    assert gi_spec and gi_spec.loader
    gi_mod = importlib.util.module_from_spec(gi_spec)
    sys.modules["gitignore_generate_mod"] = gi_mod
    gi_spec.loader.exec_module(gi_mod)

    warnings_out: list[str] = []

    # Monkeypatch _fetch_template to always fail (offline simulation).
    with unittest.mock.patch.object(gi_mod, "_fetch_template", return_value=None):
        body = gi_mod._compose_gitignore(
            templates=["macos", "unknown-framework"],
            dynamic_fetch=True,
            warnings=warnings_out,
        )

    # 'macos' is vendored → present in output
    assert ".DS_Store" in body
    # 'unknown-framework' had a fetch failure → warning emitted, not an exception
    assert any("unknown-framework" in w for w in warnings_out), (
        f"Expected warning about 'unknown-framework' fetch failure; got: {warnings_out}"
    )
    # Custom block is always present
    assert ".fastembed_cache" in body


def test_SuccessfulGitFetch_is_skipped_in_offline_suite():
    """Marker test: tests that actually hit the network are excluded by -k 'not SuccessfulGitFetch'."""
    # This test itself is a no-op — it exists so the marker name appears in the
    # codebase for documentation. The real network tests would be named
    # test_SuccessfulGitFetch_* and are excluded from the CI suite.
    pass
