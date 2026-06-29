"""End-to-end tests for the stack-adr module (spec 012).

Covers:
  - manifest parse: module.toml parses with no errors; staleness step has
    reproduce_only=True; staleness-gate has hardness=informational + init_only=True.
  - SC-001: frozen plan w/ lang-python answers (framework, pinned_deps, rationale) +
    fixed written_at → docs/decisions/STACK.md contains framework, a pins table,
    rationale, the fixed date; assert byte-identical across two write invocations;
    assert NO wall-clock (the date equals the fixed written_at).
  - SC-002: two write invocations of the same frozen plan → identical bytes.
  - SC-003: format="adr", tmp docs/adr/ with an existing 001-*.md → writes
    002-stack-decision.md AND emits adr_path derived; a second (reproduce)
    invocation with adr_path frozen writes the SAME 002 path without rescanning
    (even if a 003- file was added).
  - edge: no resolver modules enabled → minimal stub STACK.md, no error.
  - Phase 3 / manifest: assert staleness step flags (reproduce_only, init_only on
    gate) via manifest parse — the runner-level SC-004/SC-005 are covered by
    test_reproduce_only.py (Phase 1) for the dispatch logic, and the manifest flags
    are the binding spec constraint here.

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_stack_adr.py
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
_MODULE_REL = "modules/stack-adr"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(
    tmp: Path,
    *,
    mode: str = "init",
    format: str = "simple",
    adr_path: str = "",
    written_at: str = "",
    resolver_answers: dict | None = None,
    written_at_plan_field: str = "",
) -> Path:
    """Build a frozen plan.json for the stack-adr write step.

    resolver_answers: if provided, injected as a 'lang-python' module in the plan
    so that _collect_resolver_modules picks it up.
    written_at_plan_field: value for the top-level plan.written_at field.
    """
    stack_answers: dict = {"format": format}
    if adr_path:
        stack_answers["adr_path"] = adr_path
    if written_at:
        stack_answers["written_at"] = written_at

    modules: dict = {
        "stack-adr": {
            "id": "stack-adr",
            "version": "1.0.0",
            "reconcile": True,
            "module_rel_root": _MODULE_REL,
            "answers": stack_answers,
            "steps": [
                {"id": "write", "kind": "python"},
                {"id": "staleness", "kind": "agent",
                 "steering": "steering/staleness.md", "reproduce_only": True},
                {"id": "staleness-gate", "kind": "gate",
                 "hardness": "informational", "init_only": True,
                 "message": "Stack staleness advisory (see above). Proceeding."},
            ],
        }
    }
    order = ["stack-adr"]

    if resolver_answers is not None:
        modules["lang-python"] = {
            "id": "lang-python",
            "version": "1.0.0",
            "reconcile": True,
            "module_rel_root": "modules/lang-python",
            "answers": resolver_answers,
            "steps": [],
        }
        order = ["lang-python", "stack-adr"]

    plan = {
        "schema_version": 1,
        "mode": mode,
        "order": order,
        "modules": modules,
    }
    if written_at_plan_field:
        plan["written_at"] = written_at_plan_field

    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _run(
    project: Path,
    plan: Path,
    *,
    inspect: bool = False,
) -> subprocess.CompletedProcess:
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    cmd = ["uv", "run", str(module_py), "--plan", str(plan), "--step", "write"]
    if inspect:
        cmd.append("--inspect")
    env = {**os.environ, "PLUGIN_ROOT": str(_PLUGIN_ROOT), "PROJECT_DIR": str(project)}
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))


# --------------------------------------------------------------------------- #
# Manifest tests                                                               #
# --------------------------------------------------------------------------- #

def test_manifest_parses_no_errors():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, mani.errors
    assert mani.id == "stack-adr"
    # opt-in (spec 012 Decision J amended): keeps the 6-core minimal default footprint.
    assert mani.default_enabled is False
    assert mani.reconcile is True


def test_manifest_write_step_is_python():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    write_steps = [s for s in mani.steps if s.id == "write"]
    assert len(write_steps) == 1
    assert write_steps[0].kind == "python"


def test_manifest_staleness_step_reproduce_only():
    """staleness step must carry reproduce_only=True (spec 012 FR-009)."""
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    staleness = next((s for s in mani.steps if s.id == "staleness"), None)
    assert staleness is not None, "staleness step missing from manifest"
    assert staleness.kind == "agent"
    assert staleness.reproduce_only is True


def test_manifest_staleness_gate_informational_init_only():
    """staleness-gate must have hardness=informational AND init_only=True (FR-011)."""
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    gate = next((s for s in mani.steps if s.id == "staleness-gate"), None)
    assert gate is not None, "staleness-gate step missing from manifest"
    assert gate.kind == "gate"
    assert gate.hardness == "informational"
    assert gate.init_only is True


def test_manifest_order_after():
    """[order] after must include both lang-python and lang-ts."""
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert "lang-python" in mani.order["after"]
    assert "lang-ts" in mani.order["after"]
    # NO requires — order only, not a hard dependency.
    assert mani.order["requires"] == []


def test_manifest_inputs_declared():
    """format and adr_path inputs must be declared."""
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    keys = {i.key for i in mani.inputs}
    assert "format" in keys
    assert "adr_path" in keys
    assert "written_at" in keys


# --------------------------------------------------------------------------- #
# SC-001: write produces correct STACK.md with fixed date, no wall-clock       #
# --------------------------------------------------------------------------- #

def test_sc001_write_produces_stack_md_with_correct_content(tmp_path):
    """SC-001: frozen plan with lang-python answers + fixed written_at → STACK.md
    contains framework, pins table, rationale, and the fixed date (not wall-clock)."""
    project = tmp_path / "proj"
    project.mkdir()

    fixed_date = "2026-01-15"
    resolver_answers = {
        "framework": "fastapi",
        "ecosystem": "pypi",
        "pinned_deps": ["fastapi@0.115.5", "uvicorn@0.34.0", "pydantic@2.11.0"],
        "rationale": "FastAPI chosen for async support and automatic OpenAPI generation.",
    }
    plan = _frozen_plan(
        tmp_path,
        written_at=fixed_date,
        resolver_answers=resolver_answers,
    )
    proc = _run(project, plan)
    assert proc.returncode == 0, f"stderr: {proc.stderr}\nstdout: {proc.stdout}"
    result = json.loads(proc.stdout)
    assert result["status"] == "ok", result

    stack_md = project / "docs" / "decisions" / "STACK.md"
    assert stack_md.exists(), "docs/decisions/STACK.md was not created"

    content = stack_md.read_text()

    # Date must be the fixed frozen date, not today's wall-clock.
    assert fixed_date in content, f"Fixed date {fixed_date!r} not found in STACK.md"
    # Should NOT contain any other plausible date pattern for "today" if different.
    # (We can't rule out coincidence, but we can verify the placeholder was filled.)
    assert "WRITTEN_AT" not in content, "WRITTEN_AT placeholder was not substituted"

    # Framework present
    assert "fastapi" in content.lower()

    # Pins table present — at minimum the package names should appear
    assert "fastapi" in content
    assert "uvicorn" in content
    assert "pydantic" in content
    assert "0.115.5" in content

    # Rationale present
    assert "FastAPI chosen for async support" in content

    # Status section
    assert "Accepted" in content


def test_sc001_no_wall_clock_in_output(tmp_path):
    """The date in STACK.md must equal the frozen written_at, not today."""
    import datetime
    project = tmp_path / "proj"
    project.mkdir()

    # Use a date clearly in the past so it cannot match today.
    fixed_date = "2020-06-15"
    resolver_answers = {
        "framework": "django",
        "pinned_deps": ["django@4.2.0"],
        "rationale": "Django for batteries-included web development.",
    }
    plan = _frozen_plan(
        tmp_path,
        written_at=fixed_date,
        resolver_answers=resolver_answers,
    )
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr

    content = (project / "docs" / "decisions" / "STACK.md").read_text()
    assert fixed_date in content

    today = datetime.date.today().isoformat()
    # Today's date must NOT appear in the content (this is the no-wall-clock check).
    assert today not in content, (
        f"Wall-clock date {today!r} appeared in STACK.md; expected frozen date {fixed_date!r}"
    )


# --------------------------------------------------------------------------- #
# SC-002: byte-identical across two write invocations                          #
# --------------------------------------------------------------------------- #

def test_sc002_byte_identical_two_invocations(tmp_path):
    """SC-002: two invocations of the same frozen plan produce byte-identical output."""
    project = tmp_path / "proj"
    project.mkdir()

    resolver_answers = {
        "framework": "fastapi",
        "pinned_deps": ["fastapi@0.115.5"],
        "rationale": "Async support.",
    }
    plan = _frozen_plan(
        tmp_path,
        written_at="2026-03-01",
        resolver_answers=resolver_answers,
    )

    proc1 = _run(project, plan)
    assert proc1.returncode == 0, proc1.stderr
    content1 = (project / "docs" / "decisions" / "STACK.md").read_text()

    proc2 = _run(project, plan)
    assert proc2.returncode == 0, proc2.stderr
    content2 = (project / "docs" / "decisions" / "STACK.md").read_text()

    assert content1 == content2, "Two write invocations produced different STACK.md bytes"


def test_sc002_second_run_emits_skip(tmp_path):
    """Second run with same frozen plan should emit diff kind=skip (reconcile + same content)."""
    project = tmp_path / "proj"
    project.mkdir()

    resolver_answers = {"framework": "flask", "pinned_deps": ["flask@3.1.0"], "rationale": "Minimal."}
    plan = _frozen_plan(tmp_path, written_at="2026-01-01", resolver_answers=resolver_answers)

    _run(project, plan)  # first run creates the file
    proc2 = _run(project, plan)
    assert proc2.returncode == 0, proc2.stderr
    result = json.loads(proc2.stdout)
    assert result["diffs"][0]["kind"] == "skip"
    assert result["files_written"] == []


# --------------------------------------------------------------------------- #
# SC-003: ADR format — number scanning, adr_path persistence, reproduce path  #
# --------------------------------------------------------------------------- #

def test_sc003_adr_format_assigns_next_number(tmp_path):
    """SC-003: format=adr with one existing 001-*.md → writes 002-stack-decision.md."""
    project = tmp_path / "proj"
    project.mkdir()
    adr_dir = project / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    # Pre-existing ADR
    (adr_dir / "001-initial-architecture.md").write_text("# Initial ADR\n")

    resolver_answers = {
        "framework": "fastapi",
        "pinned_deps": ["fastapi@0.115.5"],
        "rationale": "Chosen for performance.",
    }
    plan = _frozen_plan(
        tmp_path,
        format="adr",
        written_at="2026-02-10",
        resolver_answers=resolver_answers,
    )
    proc = _run(project, plan)
    assert proc.returncode == 0, f"stderr: {proc.stderr}\nstdout: {proc.stdout}"

    result = json.loads(proc.stdout)
    assert result["status"] == "ok"

    adr_file = project / "docs" / "adr" / "002-stack-decision.md"
    assert adr_file.exists(), f"002-stack-decision.md not created; files_written={result['files_written']}"

    content = adr_file.read_text()
    assert "002" in content, "ADR number 002 not in ADR content"
    assert "2026-02-10" in content, "written_at date not in ADR content"

    # adr_path must be persisted as derived answer
    atp = result.get("answers_to_persist", {})
    assert "adr_path" in atp, f"adr_path not in answers_to_persist: {atp}"
    assert atp["adr_path"]["source"] == "derived"
    assert "002-stack-decision.md" in atp["adr_path"]["value"]


def test_sc003_reproduce_uses_frozen_adr_path_no_rescan(tmp_path):
    """SC-003 reproduce: frozen adr_path → writes to same 002- path even if 003- added."""
    project = tmp_path / "proj"
    project.mkdir()
    adr_dir = project / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "001-initial-architecture.md").write_text("# Initial ADR\n")

    resolver_answers = {
        "framework": "fastapi",
        "pinned_deps": ["fastapi@0.115.5"],
        "rationale": "Performance.",
    }
    # First run: init, no frozen adr_path.
    plan_init = _frozen_plan(
        tmp_path,
        format="adr",
        written_at="2026-02-10",
        resolver_answers=resolver_answers,
    )
    proc_init = _run(project, plan_init)
    assert proc_init.returncode == 0, proc_init.stderr
    init_result = json.loads(proc_init.stdout)
    frozen_path = init_result["answers_to_persist"]["adr_path"]["value"]
    assert "002-stack-decision.md" in frozen_path

    # A human adds 003- between runs.
    (adr_dir / "003-another-decision.md").write_text("# Another ADR\n")

    # Second run: reproduce with adr_path frozen — must write to 002-, NOT re-scan to 004-.
    repro_tmp = tmp_path / "repro"
    repro_tmp.mkdir(exist_ok=True)
    plan_repro = _frozen_plan(
        repro_tmp,
        format="adr",
        adr_path=frozen_path,
        written_at="2026-02-10",
        resolver_answers=resolver_answers,
    )

    proc_repro = _run(project, plan_repro)
    assert proc_repro.returncode == 0, proc_repro.stderr

    # 002- must exist and be the written file
    assert (adr_dir / "002-stack-decision.md").exists()
    # 004- must NOT exist (no re-scan)
    assert not (adr_dir / "004-stack-decision.md").exists()


def test_sc003_adr_number_zero_files(tmp_path):
    """format=adr with NO existing files in docs/adr/ → assigns 001."""
    project = tmp_path / "proj"
    project.mkdir()
    # docs/adr/ does NOT exist yet

    resolver_answers = {
        "framework": "fastapi",
        "pinned_deps": ["fastapi@0.115.5"],
        "rationale": "Async.",
    }
    plan = _frozen_plan(
        tmp_path,
        format="adr",
        written_at="2026-03-01",
        resolver_answers=resolver_answers,
    )
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    atp = result.get("answers_to_persist", {})
    assert "001-stack-decision.md" in atp["adr_path"]["value"]
    assert (project / "docs" / "adr" / "001-stack-decision.md").exists()


# --------------------------------------------------------------------------- #
# Edge case: no resolver modules enabled                                       #
# --------------------------------------------------------------------------- #

def test_edge_no_resolver_modules_writes_stub(tmp_path):
    """No lang-* modules in plan → minimal stub STACK.md, no error."""
    project = tmp_path / "proj"
    project.mkdir()

    # Plan has only stack-adr, no resolver modules.
    plan = _frozen_plan(tmp_path, written_at="2026-01-01")
    proc = _run(project, plan)
    assert proc.returncode == 0, f"stderr: {proc.stderr}\nstdout: {proc.stdout}"

    result = json.loads(proc.stdout)
    assert result["status"] == "ok"

    stack_md = project / "docs" / "decisions" / "STACK.md"
    assert stack_md.exists()

    content = stack_md.read_text()
    # Must contain "no resolver decisions" stub language.
    assert "no resolver" in content.lower() or "no pinned" in content.lower() or "not recorded" in content.lower()
    # Must still have date and Status.
    assert "2026-01-01" in content
    assert "Accepted" in content


# --------------------------------------------------------------------------- #
# written_at persistence: answers_to_persist carries derived written_at        #
# --------------------------------------------------------------------------- #

def test_written_at_persisted_as_derived(tmp_path):
    """The write step must emit written_at in answers_to_persist with source=derived."""
    project = tmp_path / "proj"
    project.mkdir()

    resolver_answers = {"framework": "fastapi", "pinned_deps": ["fastapi@0.115.5"], "rationale": "Perf."}
    plan = _frozen_plan(tmp_path, written_at="2026-04-01", resolver_answers=resolver_answers)
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    atp = result.get("answers_to_persist", {})
    assert "written_at" in atp, f"written_at missing from answers_to_persist: {atp}"
    assert atp["written_at"]["source"] == "derived"
    assert atp["written_at"]["value"] == "2026-04-01"


def test_written_at_seeds_from_plan_field_when_absent(tmp_path):
    """When written_at answer is absent, seeds from plan.written_at field and persists it."""
    project = tmp_path / "proj"
    project.mkdir()

    # No written_at in stack-adr answers, but plan has written_at at top level.
    resolver_answers = {"framework": "flask", "pinned_deps": ["flask@3.0.0"], "rationale": "Simple."}
    plan = _frozen_plan(
        tmp_path,
        written_at="",         # no frozen answer
        written_at_plan_field="2026-05-20",   # plan-level field
        resolver_answers=resolver_answers,
    )
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    atp = result.get("answers_to_persist", {})
    # Should have persisted the plan-level date.
    assert "written_at" in atp
    assert atp["written_at"]["value"] == "2026-05-20"

    content = (project / "docs" / "decisions" / "STACK.md").read_text()
    assert "2026-05-20" in content


def test_written_at_unknown_fallback(tmp_path):
    """When both written_at answer and plan.written_at are absent, renders 'unknown'."""
    project = tmp_path / "proj"
    project.mkdir()

    # Pre-012 plan: no written_at anywhere.
    resolver_answers = {"framework": "flask", "pinned_deps": ["flask@3.0.0"], "rationale": "Minimal."}
    plan = _frozen_plan(
        tmp_path,
        written_at="",
        written_at_plan_field="",
        resolver_answers=resolver_answers,
    )
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    content = (project / "docs" / "decisions" / "STACK.md").read_text()
    assert "unknown" in content


# --------------------------------------------------------------------------- #
# inspect mode                                                                 #
# --------------------------------------------------------------------------- #

def test_inspect_writes_nothing(tmp_path):
    """--inspect: diff kind=create or similar, but no file written to disk."""
    project = tmp_path / "proj"
    project.mkdir()

    resolver_answers = {"framework": "fastapi", "pinned_deps": ["fastapi@0.115.5"], "rationale": "Perf."}
    plan = _frozen_plan(tmp_path, written_at="2026-01-01", resolver_answers=resolver_answers)
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["diffs"][0]["kind"] == "create"
    assert not (project / "docs" / "decisions" / "STACK.md").exists()


# --------------------------------------------------------------------------- #
# Multi-ecosystem: both lang-python and lang-ts resolver modules               #
# --------------------------------------------------------------------------- #

def test_multiple_resolver_modules_both_in_output(tmp_path):
    """Both Python and TypeScript resolver modules are rendered in STACK.md."""
    project = tmp_path / "proj"
    project.mkdir()

    modules: dict = {
        "stack-adr": {
            "id": "stack-adr",
            "version": "1.0.0",
            "reconcile": True,
            "module_rel_root": _MODULE_REL,
            "answers": {"format": "simple", "written_at": "2026-06-01"},
            "steps": [{"id": "write", "kind": "python"}],
        },
        "lang-python": {
            "id": "lang-python",
            "version": "1.0.0",
            "reconcile": True,
            "module_rel_root": "modules/lang-python",
            "answers": {
                "framework": "fastapi",
                "ecosystem": "pypi",
                "pinned_deps": ["fastapi@0.115.5"],
                "rationale": "FastAPI for Python APIs.",
            },
            "steps": [],
        },
        "lang-ts": {
            "id": "lang-ts",
            "version": "1.0.0",
            "reconcile": True,
            "module_rel_root": "modules/lang-ts",
            "answers": {
                "framework": "nextjs",
                "ecosystem": "npm",
                "pinned_deps": ["next@14.2.0", "react@18.3.0"],
                "rationale": "Next.js for the frontend.",
            },
            "steps": [],
        },
    }
    plan_data = {
        "schema_version": 1,
        "mode": "init",
        "order": ["lang-python", "lang-ts", "stack-adr"],
        "modules": modules,
    }
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan_data))

    proc = _run(project, plan_file)
    assert proc.returncode == 0, f"stderr: {proc.stderr}"

    content = (project / "docs" / "decisions" / "STACK.md").read_text()
    # Both ecosystems present
    assert "fastapi" in content.lower()
    assert "next" in content.lower() or "nextjs" in content.lower()
    assert "FastAPI for Python APIs" in content
    assert "Next.js for the frontend" in content
    # Both lang module sections
    assert "lang-python" in content
    assert "lang-ts" in content


# --------------------------------------------------------------------------- #
# Phase 3 manifest assertions (SC-004/SC-005 are runner-level,                 #
# covered by test_reproduce_only.py Phase 1 dispatch tests)                    #
# --------------------------------------------------------------------------- #

def test_sc004_sc005_manifest_flags_are_binding():
    """The binding spec constraints for SC-004/SC-005 are the manifest flags:
    reproduce_only=True on staleness (runner skips at init) and
    init_only=True on staleness-gate (gate auto-proceeds at init).
    The full runner-level dispatch is covered by test_reproduce_only.py.
    """
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")

    staleness = next(s for s in mani.steps if s.id == "staleness")
    assert staleness.reproduce_only is True, "staleness step must be reproduce_only=True (SC-004)"

    gate = next(s for s in mani.steps if s.id == "staleness-gate")
    assert gate.init_only is True, "staleness-gate must be init_only=True (SC-004/SC-005)"
    assert gate.hardness == "informational", "staleness-gate must be informational (SC-005/SC-006)"


def test_sc012_gate_message_is_static():
    """FR-012: staleness-gate message must be static, NOT {decision}, so the
    gate cannot compose an advisory from answers_to_persist (which is forbidden)."""
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    gate = next(s for s in mani.steps if s.id == "staleness-gate")
    assert "{decision}" not in (gate.message or ""), (
        "staleness-gate message must not use {decision} — FR-012 forbids "
        "answers_to_persist from staleness step, so {decision} composition is illegal"
    )
