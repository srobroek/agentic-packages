"""End-to-end tests for the lang-go module.

Verifies:
  - manifest parses and is valid (id, default_enabled=False, reconcile=True, order,
    write+run-generator+scaffold steps present)
  - happy path: config files written + gitignore/pre-commit appends present with
    correct markers (toolchain stubbed offline — no real go, no network) — all
    under --step write
  - scaffold step: go mod init runs under --step scaffold
  - module_path derived from a stubbed git remote
  - tool-missing → warn+continue (no raise, returncode==0)
  - idempotent re-run does NOT double-append (grep-guard works — run twice,
    assert marker appears exactly once in .gitignore and .pre-commit-config.yaml)
  - --inspect writes nothing

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_lang_go.py
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
_MODULE_REL = "modules/lang-go"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(
    tmp: Path,
    module_path: str = "",
    app_kind: str = "",
) -> Path:
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["lang-go"],
        "modules": {
            "lang-go": {
                "id": "lang-go",
                "version": "1.0.0",
                "reconcile": True,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "module_path": module_path,
                    "app_kind": app_kind,
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


def _stub_go_and_git(tmp: Path, remote_url: str = "") -> Path:
    """Write fake go + git stubs. git remote get-url returns remote_url if set."""
    stub_dir = tmp / "stubs"
    stub_dir.mkdir(exist_ok=True)

    # stub go: succeeds silently
    stub_go = stub_dir / "go"
    stub_go.write_text("#!/bin/sh\nexit 0\n")
    stub_go.chmod(0o755)

    # stub git: 'git remote get-url origin' returns the configured remote
    if remote_url:
        git_script = f"""\
#!/bin/sh
if [ "$1" = "remote" ] && [ "$2" = "get-url" ]; then
    echo '{remote_url}'
    exit 0
fi
exit 0
"""
    else:
        git_script = "#!/bin/sh\nexit 1\n"
    stub_git = stub_dir / "git"
    stub_git.write_text(git_script)
    stub_git.chmod(0o755)

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
    assert mani.id == "lang-go"
    assert mani.default_enabled is False, "language overlays must be opt-in (default_enabled=false)"
    assert mani.reconcile is True
    assert any(s.id == "write" and s.kind == "python" for s in mani.steps)
    assert any(s.id == "run-generator" and s.kind == "gate" for s in mani.steps)
    assert any(s.id == "scaffold" and s.kind == "python" for s in mani.steps)
    assert "gitignore-generate" in mani.order.get("after", [])
    assert "precommit-setup" in mani.order.get("after", [])

    input_keys = {inp.key for inp in mani.inputs}
    assert "module_path" in input_keys
    assert "app_kind" in input_keys


# ── happy path (--step write) ─────────────────────────────────────────────────

def test_happy_path_creates_golangci_yml(tmp_path):
    """Happy path: .golangci.yml is created with expected content (write step)."""
    project = tmp_path / "myservice"
    project.mkdir()
    stub_dir = _stub_go_and_git(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path, module_path="github.com/example/myservice")

    proc = _run(project, plan, stub_dir)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"

    golangci = project / ".golangci.yml"
    assert golangci.exists(), f".golangci.yml not created; files_written={result['files_written']}"
    content = golangci.read_text()
    assert "errcheck" in content
    assert "staticcheck" in content
    assert "timeout: 5m" in content


def test_happy_path_creates_cmd_main_go(tmp_path):
    """Happy path: cmd/main.go is created (write step)."""
    project = tmp_path / "mycli"
    project.mkdir()
    stub_dir = _stub_go_and_git(tmp_path)
    plan = _frozen_plan(tmp_path, module_path="github.com/example/mycli")

    proc = _run(project, plan, stub_dir)
    assert proc.returncode == 0, proc.stderr

    main_go = project / "cmd" / "main.go"
    assert main_go.exists(), "cmd/main.go not created"
    content = main_go.read_text()
    assert "package main" in content
    assert "fmt.Println" in content


def test_happy_path_appends_gitignore_block(tmp_path):
    """Happy path: *.test marker present in .gitignore after write step."""
    project = tmp_path / "myservice"
    project.mkdir()
    stub_dir = _stub_go_and_git(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path, module_path="github.com/example/myservice")

    proc = _run(project, plan, stub_dir)
    assert proc.returncode == 0, proc.stderr

    gi_content = (project / ".gitignore").read_text()
    assert "*.test" in gi_content, "gitignore *.test marker missing"
    assert "*.exe" in gi_content


def test_happy_path_appends_precommit_hooks(tmp_path):
    """Happy path: go pre-commit hooks appended to .pre-commit-config.yaml (write step)."""
    project = tmp_path / "myservice"
    project.mkdir()
    stub_dir = _stub_go_and_git(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    (project / ".pre-commit-config.yaml").write_text("repos:\n")
    plan = _frozen_plan(tmp_path, module_path="github.com/example/myservice")

    proc = _run(project, plan, stub_dir)
    assert proc.returncode == 0, proc.stderr

    pc_content = (project / ".pre-commit-config.yaml").read_text()
    assert "tekwizely/pre-commit-golang" in pc_content
    assert "golangci-lint" in pc_content
    assert "go-fmt" in pc_content


# ── scaffold step (--step scaffold) ──────────────────────────────────────────

def test_scaffold_runs_go_mod_init(tmp_path):
    """scaffold step: go mod init is invoked with the stub on PATH."""
    project = tmp_path / "myservice"
    project.mkdir()
    stub_dir = _stub_go_and_git(tmp_path)
    plan = _frozen_plan(tmp_path, module_path="github.com/example/myservice")

    proc = _run(project, plan, stub_dir, step="scaffold")
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"


# ── module_path derived from git remote ──────────────────────────────────────

def test_module_path_derived_from_git_remote(tmp_path):
    """When module_path is empty, derive from git remote (stubbed) in write step."""
    project = tmp_path / "myrepo"
    project.mkdir()
    # Stub git to return an HTTPS remote
    stub_dir = _stub_go_and_git(tmp_path, remote_url="https://github.com/example/myrepo.git")
    plan = _frozen_plan(tmp_path, module_path="")  # empty → derive

    proc = _run(project, plan, stub_dir)
    assert proc.returncode == 0, proc.stderr
    # go mod init should have been invoked with the derived path; since go is
    # stubbed the go.mod file won't exist, but there should be no error
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    # Warning about example.com fallback must NOT appear (remote was provided)
    assert not any("example.com" in w for w in result["warnings"]), (
        f"Module used fallback despite git remote being available; warnings={result['warnings']}"
    )


def test_module_path_fallback_when_no_git_remote(tmp_path):
    """When module_path is empty and no git remote, fallback to example.com/<name>."""
    project = tmp_path / "myrepo"
    project.mkdir()
    # Stub git to return non-zero (no remote)
    stub_dir = _stub_go_and_git(tmp_path, remote_url="")
    plan = _frozen_plan(tmp_path, module_path="")

    proc = _run(project, plan, stub_dir)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert any("example.com" in w for w in result["warnings"]), (
        f"Expected fallback warning; got: {result['warnings']}"
    )


# ── tool-missing → warn+continue ─────────────────────────────────────────────

def test_tool_missing_warns_and_continues(tmp_path):
    """When go is absent, sdk.run_tool warns and returns False (no raise).

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

    project = tmp_path / "myservice"
    project.mkdir()
    warnings_out: list[str] = []

    import unittest.mock
    with unittest.mock.patch.object(sdk_mod.shutil, "which", return_value=None):
        ok = sdk_mod.run_tool(
            ["go", "mod", "init", "github.com/example/myservice"],
            cwd=project,
            warnings=warnings_out,
            label="go mod init",
        )

    assert ok is False
    assert any("go" in w.lower() for w in warnings_out), (
        f"Expected warning about go missing; got: {warnings_out}"
    )


# ── idempotence ───────────────────────────────────────────────────────────────

def test_idempotent_no_double_append_gitignore(tmp_path):
    """*.test marker must appear exactly once after two write-step runs."""
    project = tmp_path / "myservice"
    project.mkdir()
    stub_dir = _stub_go_and_git(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path, module_path="github.com/example/myservice")

    _run(project, plan, stub_dir)
    _run(project, plan, stub_dir)

    gi_content = (project / ".gitignore").read_text()
    count = gi_content.count("*.test")
    assert count == 1, f"*.test appeared {count} times (expected 1) — double-append bug"


def test_idempotent_no_double_append_precommit(tmp_path):
    """tekwizely/pre-commit-golang marker must appear exactly once after two write-step runs."""
    project = tmp_path / "myservice"
    project.mkdir()
    stub_dir = _stub_go_and_git(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    (project / ".pre-commit-config.yaml").write_text("repos:\n")
    plan = _frozen_plan(tmp_path, module_path="github.com/example/myservice")

    _run(project, plan, stub_dir)
    _run(project, plan, stub_dir)

    pc_content = (project / ".pre-commit-config.yaml").read_text()
    count = pc_content.count("tekwizely/pre-commit-golang")
    assert count == 1, f"tekwizely/pre-commit-golang appeared {count} times (expected 1) — double-append bug"


# ── inspect ───────────────────────────────────────────────────────────────────

def test_inspect_writes_nothing(tmp_path):
    """--inspect produces diffs but writes nothing to disk."""
    project = tmp_path / "myservice"
    project.mkdir()
    stub_dir = _stub_go_and_git(tmp_path)
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path, module_path="github.com/example/myservice")

    proc = _run(project, plan, stub_dir, inspect=True)
    assert proc.returncode == 0, proc.stderr

    # .golangci.yml must not exist (write-if-absent, inspect=True)
    assert not (project / ".golangci.yml").exists()
    assert not (project / "cmd").exists()
