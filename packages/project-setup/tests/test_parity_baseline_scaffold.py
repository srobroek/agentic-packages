"""T04A — minimal-core-scaffold parity audit (SC-001 / SC-005).

Drives the REAL runner pipeline end-to-end with the minimal-core default_enabled
module set (ScriptedIO, non-interactive, no explicit module selection) into a
temp project, then asserts the observable scaffold matches the minimal core:
AGENTS.md, .gitignore, docs/, specs/, LICENSE — and that optional-module outputs
(.pre-commit-config.yaml, .codex/config.toml, Justfile) are NOT present.

This is the SC-001 gate: a fresh run with no selection produces ONLY the
minimal-core scaffold; no optional modules run.

The bundled minimal core (default_enabled=true) is:
  core-identity, dirs-scaffold, gitignore-generate, license-write,
  agents-md, git-init

Optional modules (default_enabled=false) require explicit enablement:
  apm-install, codex-config, github-repo, justfile-write, precommit-setup,
  quality-hooks, lang-*, speckit-bridge, package-add

Tools that the base modules shell out to (git, gh) are stubbed on PATH as
no-op successes so the run is hermetic and offline. The run uses the REAL
bundled modules under skills/project-setup/modules/ via the injected
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
    """SC-001: minimal-core run (no selection) produces ONLY the base scaffold.

    Verifies that the 6 core modules execute and their outputs are present,
    and that optional-module outputs are absent.
    """
    pipeline = _load("pipeline")
    io_adapter = _load("io_adapter")

    project = tmp_path / "demo"
    project.mkdir()

    # Hermetic tool stubs on PATH front. Only git/gh needed for base modules.
    bin_dir = tmp_path / "bin"
    _stub_tools(bin_dir, ["gh", "apm", "pre-commit", "sudo", "xattr", "gitnr", "specify"])
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)

    # Scripted answers for a single-layout project; no "enabled" key → base-only.
    io = io_adapter.ScriptedIO(
        answers={
            "project_name": "demo",
            "org": "acme",
            "description": "demo project",
            "layout": "single",
            "license": "apache-2.0",
            "public": False,
            "create_repo": False,
            "init_git": True,
            # No "enabled" key → base-only (FR-007 safe default)
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
    errs = getattr(result, "errors", [])
    assert not errs, [getattr(e, "how_to_fix", str(e)) for e in errs]

    # ── SC-001: minimal-core outputs PRESENT ─────────────────────────────── #
    assert (project / "AGENTS.md").is_file(), "AGENTS.md missing (agents-md module)"
    assert (project / ".gitignore").is_file(), ".gitignore missing (gitignore-generate module)"
    assert (project / "docs").is_dir(), "docs/ missing (dirs-scaffold module)"
    assert (project / "specs").is_dir(), "specs/ missing (dirs-scaffold module)"
    assert (project / "LICENSE").is_file(), "LICENSE missing (license-write module)"

    # ── SC-001: optional-module outputs ABSENT ────────────────────────────── #
    # Note: dirs-scaffold (core) creates placeholder dirs including .codex/ —
    # that is intentional. What must be absent is .codex/config.toml, which is
    # only written by the opt-in codex-config module.
    assert not (project / ".pre-commit-config.yaml").exists(), \
        ".pre-commit-config.yaml must NOT be present in base run (precommit-setup is opt-in)"
    assert not (project / ".codex" / "config.toml").exists(), \
        ".codex/config.toml must NOT be present in base run (codex-config is opt-in)"
    assert not (project / "Justfile").exists(), \
        "Justfile must NOT be present in base run (justfile-write is opt-in)"
    assert not (project / "apps").exists(), "apps/ must not exist in single layout"
    assert not (project / "services").exists(), "services/ must not exist in single layout"

    # Content spot-checks on core outputs.
    gi = (project / ".gitignore").read_text()
    assert "repomix.xml" in gi and ".env" in gi
    agents = (project / "AGENTS.md").read_text()
    assert "demo" in agents  # PROJECT_NAME substituted

    # Committed project state written, including [modules].enabled.
    assert (project / ".project-setup" / "answers.toml").is_file()

    # Enabled modules should be the 6-core set only.
    enabled = getattr(result, "enabled_modules", [])
    assert set(enabled) == {
        "core-identity", "dirs-scaffold", "gitignore-generate",
        "license-write", "agents-md", "git-init",
    }, f"Expected only 6-core enabled, got: {sorted(enabled)}"


def test_baseline_scaffold_is_deterministic(tmp_path, monkeypatch):
    """Two runs with identical answers produce identical Tier-1 scaffold files
    (excluding intrinsically variable values: LICENSE year/author).

    Checks only minimal-core outputs — optional modules are not enabled.
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
            # No "enabled" key → base-only
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

    # Core outputs are byte-identical across runs.
    for fname in (".gitignore", "AGENTS.md"):
        a = (outs[1] / fname).read_text()
        b = (outs[2] / fname).read_text()
        assert a == b, f"{fname} not byte-identical across runs"
