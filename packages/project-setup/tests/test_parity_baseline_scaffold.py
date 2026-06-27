"""T04A — baseline-scaffold parity audit (SC-005).

Drives the REAL runner pipeline end-to-end with the bundled default_enabled
module set (ScriptedIO, non-interactive) into a temp project, then asserts the
observable scaffold matches what the legacy monolith produced: AGENTS.md,
.gitignore, .pre-commit-config.yaml, docs/, specs/, .codex/config.toml, and NO
monorepo target dirs in single layout. This is the integration gate that proves
the whole runner + modules system composes.

Tools that the base modules shell out to (git, gh, apm, pre-commit) are stubbed
on PATH as no-op successes so the run is hermetic and offline. The run uses the
REAL bundled modules under skills/project-setup/modules/ via the injected
plugin_root.

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_parity_baseline_scaffold.py
"""

from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
_PLUGIN_ROOT = _PKG / "skills" / "project-setup"
_RUNNER = _PLUGIN_ROOT / "runner"


def _load(name: str):
    # Runner submodules live under runner/; sources is a subpackage.
    rel = name.replace(".", "/")
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{rel}.py")
    assert spec and spec.loader, name
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _stub_tools(bin_dir: Path, names: list[str]) -> None:
    """Create no-op success executables for the given tool names on a tmp PATH."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    for n in names:
        p = bin_dir / n
        # gh `repo view` should "fail" so github-repo tries create then no-ops;
        # everything else exits 0. Keep it dead simple: always exit 0 with no
        # output, EXCEPT we must let `git init`/`git remote` be harmless.
        p.write_text("#!/bin/sh\nexit 0\n")
        p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def test_baseline_scaffold_parity(tmp_path, monkeypatch):
    pipeline = _load("pipeline")
    io_adapter = _load("io_adapter")

    project = tmp_path / "demo"
    project.mkdir()

    # Hermetic tool stubs (git/gh/apm/pre-commit/sudo/xattr/gitnr) on PATH front.
    bin_dir = tmp_path / "bin"
    _stub_tools(bin_dir, ["gh", "apm", "pre-commit", "sudo", "xattr", "gitnr", "specify"])
    # Keep a REAL git (modules call it) but neutralize side effects by running
    # inside the temp project; git init there is harmless.
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    # Cache + frozen plan isolated to tmp.
    monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
    # No external/home/project module roots — bundled only.
    monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)

    # Scripted answers for a single-layout project; non_interactive falls back to
    # declared defaults for anything not provided.
    io = io_adapter.ScriptedIO(
        answers={
            "project_name": "demo",
            "org": "acme",
            "description": "demo project",
            "layout": "single",
            "license": "apache-2.0",
            "public": False,
            "create_repo": False,  # don't attempt gh repo create
            "init_git": True,
        },
        default_confirm=True,
    )

    result = pipeline.run_pipeline(
        project_dir=project,
        io=io,
        plugin_root_path=_PLUGIN_ROOT,
        non_interactive=True,
    )

    # The run completed without a hard gate failure.
    assert result is not None
    # Surface any recorded errors for diagnosis.
    errs = getattr(result, "errors", [])
    assert not errs, [getattr(e, "how_to_fix", str(e)) for e in errs]

    # ── SC-005 observable-output parity ──────────────────────────────────── #
    assert (project / "AGENTS.md").is_file(), "AGENTS.md missing"
    assert (project / ".gitignore").is_file(), ".gitignore missing"
    assert (project / ".pre-commit-config.yaml").is_file(), "pre-commit config missing"
    assert (project / ".codex" / "config.toml").is_file(), ".codex/config.toml missing"
    assert (project / "docs").is_dir(), "docs/ missing"
    assert (project / "specs").is_dir(), "specs/ missing"
    assert (project / "LICENSE").is_file(), "LICENSE missing"

    # Single layout: NO monorepo target dirs (the bats-pinned invariant).
    assert not (project / "apps").exists(), "apps/ should not exist in single layout"
    assert not (project / "services").exists(), "services/ should not exist in single layout"

    # Content spot-checks against the legacy scaffold.
    gi = (project / ".gitignore").read_text()
    assert "repomix.xml" in gi and ".env" in gi
    pc = (project / ".pre-commit-config.yaml").read_text()
    assert "gitleaks" in pc and "cocogitto" in pc
    agents = (project / "AGENTS.md").read_text()
    assert "demo" in agents  # PROJECT_NAME substituted

    # Committed project state was written.
    assert (project / ".project-setup" / "answers.toml").is_file()


def test_baseline_scaffold_is_deterministic(tmp_path, monkeypatch):
    """Two runs with identical answers produce identical Tier-1 scaffold files
    (excluding intrinsically variable values: LICENSE year/author).
    """
    pipeline = _load("pipeline")
    io_adapter = _load("io_adapter")

    bin_dir = tmp_path / "bin"
    _stub_tools(bin_dir, ["gh", "apm", "pre-commit", "sudo", "xattr", "gitnr", "specify"])
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)

    def _answers():
        return {
            "project_name": "demo",
            "org": "acme",
            "layout": "single",
            "license": "apache-2.0",
            "create_repo": False,
            "init_git": False,
        }

    outs = {}
    for i in (1, 2):
        proj = tmp_path / f"p{i}"
        proj.mkdir()
        io = io_adapter.ScriptedIO(answers=_answers(), default_confirm=True)
        pipeline.run_pipeline(
            project_dir=proj, io=io, plugin_root_path=_PLUGIN_ROOT, non_interactive=True
        )
        outs[i] = proj

    for fname in (".gitignore", ".pre-commit-config.yaml", ".codex/config.toml", "AGENTS.md"):
        a = (outs[1] / fname).read_text()
        b = (outs[2] / fname).read_text()
        assert a == b, f"{fname} not byte-identical across runs"
