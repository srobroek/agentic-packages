"""End-to-end tests for the agents-md module.

Verifies:
  - manifest parses and is valid
  - single layout: writes AGENTS.md with PROJECT_NAME/ORG substituted,
    contains single-layout marker (Path Mapping section), no Monorepo Structure
  - monorepo layout: writes AGENTS.md with Monorepo Structure section
  - --inspect writes nothing
  - reconcile=true: second run with identical content → skip
  - reconcile=true: second run with different layout → modify

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_agents_md.py
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
_MODULE_REL = "modules/agents-md"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(tmp: Path, layout: str = "single", project_name: str = "my-app", org: str = "acme") -> Path:
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["agents-md"],
        "modules": {
            "agents-md": {
                "id": "agents-md",
                "version": "1.0.0",
                "reconcile": True,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "layout": layout,
                    "project_name": project_name,
                    "org": org,
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
    assert mani.id == "agents-md"
    assert mani.default_enabled is True
    assert mani.reconcile is True
    assert any(s.id == "write" and s.kind == "python" for s in mani.steps)
    assert mani.order["requires"] == ["core-identity"]
    assert "dirs-scaffold" in mani.order["after"]


def test_single_layout_writes_agents_md(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, layout="single", project_name="my-app", org="acme")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert result["files_written"] == ["AGENTS.md"]

    content = (project / "AGENTS.md").read_text()
    assert "# my-app" in content
    assert "acme/my-app" in content
    # Single layout has Path Mapping, not Monorepo Structure
    assert "## Path Mapping" in content
    assert "## Monorepo Structure" not in content


def test_monorepo_layout_writes_agents_md(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, layout="monorepo", project_name="mono-proj", org="bigcorp")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr

    content = (project / "AGENTS.md").read_text()
    assert "# mono-proj" in content
    # Monorepo layout has Monorepo Structure section
    assert "## Monorepo Structure" in content
    assert "## Path Mapping" not in content
    assert "`apps/`" in content
    assert "`services/`" in content


def test_inspect_writes_nothing(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["diffs"][0]["kind"] == "create"
    assert not (project / "AGENTS.md").exists()


def test_idempotent_same_content_skips(tmp_path):
    """reconcile=true, same content → second run emits skip."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    _run(project, plan)
    proc2 = _run(project, plan)
    assert proc2.returncode == 0, proc2.stderr
    result = json.loads(proc2.stdout)
    assert result["diffs"][0]["kind"] == "skip"
    assert result["files_written"] == []


def test_placeholder_substitution_is_exact(tmp_path):
    """PROJECT_NAME and ORG literals must not appear in the output."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, project_name="test-svc", org="myorg")
    _run(project, plan)
    content = (project / "AGENTS.md").read_text()
    assert "PROJECT_NAME" not in content
    assert "ORG/PROJECT_NAME" not in content
    assert "test-svc" in content
    assert "myorg/test-svc" in content


def test_write_step_produces_sentinel_markers(tmp_path):
    """The write step must now emit BEGIN/END sentinel markers (FR-008)."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    content = (project / "AGENTS.md").read_text()
    assert "<!-- BEGIN ps:architecture -->" in content
    assert "<!-- END ps:architecture -->" in content
    # The old placeholder must NOT appear now that templates use sentinels.
    assert "ARCHITECTURE: to be filled by agent" not in content


# --------------------------------------------------------------------------- #
# Helpers for splice-step tests                                                #
# --------------------------------------------------------------------------- #

BEGIN = "<!-- BEGIN ps:architecture -->"
END = "<!-- END ps:architecture -->"


def _frozen_plan_with_arch(
    tmp_path: Path,
    architecture_md: str = "",
    agent_editable_globs: list | None = None,
    layout: str = "single",
    project_name: str = "my-app",
    org: str = "acme",
) -> Path:
    """Build a frozen plan with architecture_md + agent_editable_globs answers."""
    if agent_editable_globs is None:
        agent_editable_globs = ["src/**", "tests/**"]
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["agents-md"],
        "modules": {
            "agents-md": {
                "id": "agents-md",
                "version": "1.0.0",
                "reconcile": True,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "layout": layout,
                    "project_name": project_name,
                    "org": org,
                    "architecture_md": architecture_md,
                    "agent_editable_globs": agent_editable_globs,
                },
                "steps": [
                    {"id": "write", "kind": "python"},
                    {"id": "resolve-arch", "kind": "agent", "steering": "steering/resolve-arch.md"},
                    {"id": "arch-gate", "kind": "gate", "hardness": "hard",
                     "allow_flag": "allow-arch-write", "init_only": True,
                     "message": "Architecture section for AGENTS.md (agent-authored):\n{decision}\nWrite this section to AGENTS.md?"},
                    {"id": "splice", "kind": "python"},
                ],
            }
        },
    }
    p = tmp_path / "plan_arch.json"
    p.write_text(json.dumps(plan))
    return p


def _run_splice(project: Path, plan: Path, *, inspect: bool = False) -> subprocess.CompletedProcess:
    """Run the splice step of module.py."""
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    cmd = ["uv", "run", str(module_py), "--plan", str(plan), "--step", "splice"]
    if inspect:
        cmd.append("--inspect")
    env = {**os.environ, "PLUGIN_ROOT": str(_PLUGIN_ROOT), "PROJECT_DIR": str(project)}
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))


# --------------------------------------------------------------------------- #
# SC-003: splice writes sentinel span; surrounding bytes unchanged             #
# --------------------------------------------------------------------------- #

def test_splice_writes_sentinel_span_rest_unchanged(tmp_path):
    """SC-003: splice fills the sentinel span; everything else byte-identical."""
    project = tmp_path / "proj"
    project.mkdir()

    # Step 1: write the skeleton (produces markers).
    write_plan = _frozen_plan(tmp_path)
    proc = _run(project, write_plan)
    assert proc.returncode == 0, proc.stderr
    skeleton = (project / "AGENTS.md").read_text()
    assert BEGIN in skeleton and END in skeleton

    # Step 2: splice a known architecture_md into the sentinel span.
    arch_text = "A fast FastAPI service.\n\n| Path | Purpose |\n|------|---------|"
    splice_plan = _frozen_plan_with_arch(tmp_path, architecture_md=arch_text)
    proc2 = _run_splice(project, splice_plan)
    assert proc2.returncode == 0, proc2.stderr
    result = json.loads(proc2.stdout)
    assert result["status"] == "ok"
    assert result["files_written"] == ["AGENTS.md"]

    after = (project / "AGENTS.md").read_text()

    # The arch_text must be between the sentinels.
    bi = after.index(BEGIN)
    ei = after.index(END)
    inner = after[bi + len(BEGIN):ei]
    assert arch_text in inner

    # Everything before BEGIN and after END must be byte-identical to the skeleton.
    assert after[:bi] == skeleton[:skeleton.index(BEGIN)]
    skel_ei = skeleton.index(END) + len(END)
    assert after[ei + len(END):] == skeleton[skel_ei:]


# --------------------------------------------------------------------------- #
# SC-004: phantom-path row stripped + warned                                   #
# --------------------------------------------------------------------------- #

def test_phantom_path_row_stripped_with_warning(tmp_path):
    """SC-004: a path-table row for a non-existent dir is stripped + warned."""
    project = tmp_path / "proj"
    project.mkdir()
    # Only 'src' and 'tests' exist on disk.
    (project / "src").mkdir()
    (project / "tests").mkdir()

    # Write skeleton first so AGENTS.md has the sentinel markers.
    write_plan = _frozen_plan(tmp_path)
    _run(project, write_plan)

    # architecture_md references 'services/' which does NOT exist.
    arch_text = (
        "A project.\n\n"
        "| Path | Purpose |\n"
        "|------|---------|  \n"
        "| `src/` | Source code |\n"
        "| `services/` | Backend services |\n"
        "| `tests/` | Tests |\n"
    )
    splice_plan = _frozen_plan_with_arch(tmp_path, architecture_md=arch_text)
    proc = _run_splice(project, splice_plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"

    # The phantom row must be stripped.
    after = (project / "AGENTS.md").read_text()
    assert "`services/`" not in after
    # Valid rows must be present.
    assert "`src/`" in after
    assert "`tests/`" in after

    # A warning about the phantom path must be present.
    warnings = result.get("warnings", [])
    assert any("services" in w and "phantom" in w.lower() for w in warnings), warnings


def test_no_phantom_warning_when_all_dirs_exist(tmp_path):
    """SC-004 (negative): no warning if all referenced dirs exist."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "src").mkdir()
    (project / "tests").mkdir()

    write_plan = _frozen_plan(tmp_path)
    _run(project, write_plan)

    arch_text = "| `src/` | Source |\n| `tests/` | Tests |\n"
    splice_plan = _frozen_plan_with_arch(tmp_path, architecture_md=arch_text)
    proc = _run_splice(project, splice_plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    phantom_warns = [w for w in result.get("warnings", []) if "phantom" in w.lower()]
    assert phantom_warns == [], phantom_warns


# --------------------------------------------------------------------------- #
# SC-007: missing sentinel markers → append fallback                          #
# --------------------------------------------------------------------------- #

def test_missing_markers_append_fallback(tmp_path):
    """SC-007 part 1: AGENTS.md without markers gets section appended after ## Architecture."""
    project = tmp_path / "proj"
    project.mkdir()

    # Write an AGENTS.md WITHOUT sentinel markers (pre-feature file).
    legacy_content = (
        "# my-app\n\n"
        "## Architecture\n\n"
        "Some old content.\n\n"
        "## Build & Run\n\n"
        "make build\n"
    )
    (project / "AGENTS.md").write_text(legacy_content)

    arch_text = "A modern service."
    splice_plan = _frozen_plan_with_arch(tmp_path, architecture_md=arch_text)
    proc = _run_splice(project, splice_plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"

    after = (project / "AGENTS.md").read_text()

    # Sentinel markers must now be present.
    assert BEGIN in after
    assert END in after
    assert arch_text in after

    # Sentinels must appear after ## Architecture and before ## Build & Run.
    arch_idx = after.index("## Architecture")
    build_idx = after.index("## Build & Run")
    begin_idx = after.index(BEGIN)
    assert arch_idx < begin_idx < build_idx, (
        f"sentinel not between headings: arch={arch_idx} begin={begin_idx} build={build_idx}"
    )

    # A warning about missing markers must be emitted.
    warnings = result.get("warnings", [])
    assert any("markers absent" in w.lower() or "sentinel" in w.lower() for w in warnings), warnings


def test_missing_markers_second_run_uses_splice_path(tmp_path):
    """SC-007 part 2: after the append, a second run takes the normal splice path (no extra markers)."""
    project = tmp_path / "proj"
    project.mkdir()

    legacy_content = "# my-app\n\n## Architecture\n\nOld.\n"
    (project / "AGENTS.md").write_text(legacy_content)

    arch_text = "First version."
    splice_plan = _frozen_plan_with_arch(tmp_path, architecture_md=arch_text)
    _run_splice(project, splice_plan)

    # Second run with different text — should splice-replace.
    arch_text2 = "Second version."
    splice_plan2 = _frozen_plan_with_arch(tmp_path, architecture_md=arch_text2)
    proc2 = _run_splice(project, splice_plan2)
    assert proc2.returncode == 0, proc2.stderr
    result2 = json.loads(proc2.stdout)
    assert result2["status"] == "ok"
    assert result2["files_written"] == ["AGENTS.md"]

    after = (project / "AGENTS.md").read_text()
    # Only one copy of each sentinel marker.
    assert after.count(BEGIN) == 1
    assert after.count(END) == 1
    # New text present, old text gone.
    assert arch_text2 in after
    assert arch_text not in after


# --------------------------------------------------------------------------- #
# splice step: inspect mode writes nothing                                     #
# --------------------------------------------------------------------------- #

def test_splice_inspect_writes_nothing(tmp_path):
    """splice --inspect must report what would happen but not touch the file."""
    project = tmp_path / "proj"
    project.mkdir()

    write_plan = _frozen_plan(tmp_path)
    _run(project, write_plan)
    before = (project / "AGENTS.md").read_text()

    arch_text = "Some new architecture content."
    splice_plan = _frozen_plan_with_arch(tmp_path, architecture_md=arch_text)
    proc = _run_splice(project, splice_plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    # diff kind should indicate modify (there is content to write)
    assert result["diffs"][0]["kind"] in ("modify", "create")
    # The file must be unchanged.
    assert (project / "AGENTS.md").read_text() == before


# --------------------------------------------------------------------------- #
# splice step: idempotent — same content produces skip                         #
# --------------------------------------------------------------------------- #

def test_splice_idempotent_skip(tmp_path):
    """splice with identical content on second run produces 'skip'."""
    project = tmp_path / "proj"
    project.mkdir()

    write_plan = _frozen_plan(tmp_path)
    _run(project, write_plan)

    arch_text = "Stable architecture text."
    splice_plan = _frozen_plan_with_arch(tmp_path, architecture_md=arch_text)
    # First run.
    proc1 = _run_splice(project, splice_plan)
    assert proc1.returncode == 0, proc1.stderr
    r1 = json.loads(proc1.stdout)
    assert r1["files_written"] == ["AGENTS.md"]

    # Second run — same plan, same content.
    proc2 = _run_splice(project, splice_plan)
    assert proc2.returncode == 0, proc2.stderr
    r2 = json.loads(proc2.stdout)
    assert r2["diffs"][0]["kind"] == "skip"
    assert r2["files_written"] == []


# --------------------------------------------------------------------------- #
# Manifest: new steps appear                                                   #
# --------------------------------------------------------------------------- #

def test_manifest_has_all_four_steps():
    """The manifest must declare write/resolve-arch/arch-gate/splice in that order."""
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, mani.errors
    step_ids = [s.id for s in mani.steps]
    assert step_ids == ["write", "resolve-arch", "arch-gate", "splice"], step_ids
    # Gate must have the correct fields.
    gate = next(s for s in mani.steps if s.id == "arch-gate")
    assert gate.kind == "gate"
    assert gate.hardness == "hard"
    assert gate.allow_flag == "allow-arch-write"
    assert gate.init_only is True
    # New inputs present.
    input_keys = [i.key for i in mani.inputs]
    assert "architecture_md" in input_keys
    assert "agent_editable_globs" in input_keys
