"""Tests for the ci-github-actions module (spec 007).

Covers:
  - SC-001: python-only frozen ci_plan (1 job, matrix [python 3.13], action
    refs owner/repo@vN, commands [just test, just lint]) + a justfile stub →
    writes .github/workflows/ci.yml referencing only those; no floating refs.
  - SC-002: py+ts ci_plan with 2 jobs → both jobs present; ts job uses
    package_manager from frozen answers.
  - SC-003: ci_plan_commands includes "just deploy", justfile stub has no deploy
    recipe → deploy dropped, WARN present, YAML written without deploy.
  - SC-004: manifest gate assertions — hardness=="hard", allow_flag=="allow-ci-write",
    init_only True; step order resolve/ci-review/write; default_enabled False.
  - SC-005: action_refs includes "actions/checkout@main" → FIXME placeholder +
    WARN, rest of YAML still written.
  - SC-006: render_ci_yaml called twice with same dict → byte-identical.
  - SC-008: ci_plan whose commands all drop → files_written==[], warning, no file.
  - manifest parses with no errors.

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_ci_github_actions.py
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
_MODULE_REL = "modules/ci-github-actions"
_MODULE_PY = _PLUGIN_ROOT / _MODULE_REL / "module.py"


# --------------------------------------------------------------------------- #
# Module loaders                                                                #
# --------------------------------------------------------------------------- #

def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_module_py():
    """Load ci-github-actions/module.py directly for in-process unit tests."""
    key = "ci_github_actions_module"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, _MODULE_PY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# Helpers: frozen plan builder + subprocess runner                             #
# --------------------------------------------------------------------------- #

def _frozen_plan(
    tmp: Path,
    *,
    mode: str = "init",
    ci_answers: dict | None = None,
    lang_python_answers: dict | None = None,
    lang_ts_answers: dict | None = None,
) -> Path:
    """Build a minimal frozen plan.json for the ci-github-actions write step."""
    ci_ans: dict = {
        "ci_trigger": ["push", "pull_request"],
        "default_branch": "main",
        "use_just": True,
    }
    if ci_answers:
        ci_ans.update(ci_answers)

    modules: dict = {
        "ci-github-actions": {
            "id": "ci-github-actions",
            "version": "1.0.0",
            "reconcile": True,
            "module_rel_root": _MODULE_REL,
            "answers": ci_ans,
            "steps": [{"id": "write", "kind": "python"}],
        }
    }
    order = ["ci-github-actions"]

    if lang_python_answers is not None:
        modules["lang-python"] = {
            "id": "lang-python",
            "version": "1.0.0",
            "reconcile": True,
            "module_rel_root": "modules/lang-python",
            "answers": lang_python_answers,
            "steps": [],
        }
        order = ["lang-python"] + order

    if lang_ts_answers is not None:
        modules["lang-ts"] = {
            "id": "lang-ts",
            "version": "1.0.0",
            "reconcile": True,
            "module_rel_root": "modules/lang-ts",
            "answers": lang_ts_answers,
            "steps": [],
        }
        order = ["lang-ts"] + [o for o in order if o != "lang-ts"]

    plan = {
        "schema_version": 1,
        "mode": mode,
        "order": order,
        "modules": modules,
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _run(
    project: Path,
    plan: Path,
    *,
    inspect: bool = False,
) -> subprocess.CompletedProcess:
    cmd = ["uv", "run", str(_MODULE_PY), "--plan", str(plan), "--step", "write"]
    if inspect:
        cmd.append("--inspect")
    env = {
        **os.environ,
        "PLUGIN_ROOT": str(_PLUGIN_ROOT),
        "PROJECT_DIR": str(project),
    }
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))


def _stub_justfile(project: Path, recipes: list[str] | None = None) -> None:
    """Write a minimal justfile with the given recipes (default: test/lint/build/dev/clean)."""
    if recipes is None:
        recipes = ["default", "test", "lint", "build", "dev", "clean"]
    lines = []
    for recipe in recipes:
        if recipe == "default":
            lines.append("default:\n    @just --list\n")
        else:
            lines.append(f"{recipe}:\n    @echo 'TODO: {recipe}'\n")
    (project / "justfile").write_text("\n".join(lines))


def _stub_package_json(project: Path, scripts: list[str] | None = None) -> None:
    """Write a minimal package.json with the given script names."""
    if scripts is None:
        scripts = ["test", "lint", "build", "dev"]
    data = {"name": "test-pkg", "scripts": {s: f"echo {s}" for s in scripts}}
    (project / "package.json").write_text(json.dumps(data))


# --------------------------------------------------------------------------- #
# SC-004: manifest structure assertions                                        #
# --------------------------------------------------------------------------- #

def test_manifest_parses_with_no_errors():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, mani.errors


def test_manifest_module_flags():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert mani.id == "ci-github-actions"
    assert mani.default_enabled is False, "ci-github-actions must be opt-in (default_enabled=false)"
    assert mani.reconcile is True, "ci-github-actions must reconcile=true"


def test_manifest_step_order():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    step_ids = [s.id for s in mani.steps]
    assert step_ids == ["resolve", "ci-review", "write"], (
        f"Expected step order [resolve, ci-review, write], got {step_ids}"
    )


def test_manifest_gate_flags():
    """SC-004: gate hardness=hard, allow_flag=allow-ci-write, init_only=True."""
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    gate = next(s for s in mani.steps if s.id == "ci-review")
    assert gate.kind == "gate"
    assert gate.hardness == "hard", f"gate hardness must be 'hard', got {gate.hardness!r}"
    assert gate.allow_flag == "allow-ci-write", (
        f"gate allow_flag must be 'allow-ci-write', got {gate.allow_flag!r}"
    )
    assert gate.init_only is True, "gate must be init_only=true"


# --------------------------------------------------------------------------- #
# SC-006: render_ci_yaml determinism                                           #
# --------------------------------------------------------------------------- #

def test_render_ci_yaml_is_deterministic():
    """SC-006: same plan_dict → byte-identical output on two calls."""
    mod = _load_module_py()
    plan_dict = {
        "name": "CI",
        "on": {
            "pull_request": {"branches": ["main"]},
            "push": {"branches": ["main"]},
        },
        "jobs": {
            "test-python": {
                "name": "Test Python",
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {"uses": "astral-sh/setup-uv@v5"},
                    {"name": "Run: just test", "run": "just test"},
                ],
            }
        },
    }
    result_a = mod.render_ci_yaml(plan_dict)
    result_b = mod.render_ci_yaml(plan_dict)
    assert result_a == result_b, "render_ci_yaml must produce byte-identical output"
    assert result_a.endswith("\n"), "YAML output must end with newline"


def test_render_ci_yaml_key_order():
    """render_ci_yaml produces name/on/jobs at top level."""
    mod = _load_module_py()
    plan_dict = {
        "name": "CI",
        "on": {"push": {"branches": ["main"]}},
        "jobs": {},
    }
    yaml = mod.render_ci_yaml(plan_dict)
    lines = yaml.splitlines()
    assert lines[0].startswith("name:"), f"First line must be name:, got {lines[0]!r}"
    assert any(l.startswith("on:") for l in lines), "Must contain 'on:'"
    assert any(l.startswith("jobs:") for l in lines), "Must contain 'jobs:'"


def test_render_ci_yaml_booleans():
    """render_ci_yaml emits 'true'/'false' not 'True'/'False'."""
    mod = _load_module_py()
    plan_dict = {
        "name": "CI",
        "on": {"workflow_dispatch": None},
        "jobs": {
            "lint": {
                "name": "Lint",
                "runs-on": "ubuntu-latest",
                "steps": [],
            }
        },
    }
    yaml = mod.render_ci_yaml(plan_dict)
    assert "True" not in yaml, "YAML must not contain Python 'True'"
    assert "False" not in yaml, "YAML must not contain Python 'False'"


# --------------------------------------------------------------------------- #
# SC-001: Python-only project — 1 job, valid justfile, owner/repo@vN refs      #
# --------------------------------------------------------------------------- #

def test_sc001_python_only_writes_ci_yml(tmp_path):
    """SC-001: python-only frozen ci_plan produces .github/workflows/ci.yml."""
    project = tmp_path / "project"
    project.mkdir()
    _stub_justfile(project)  # has test/lint/etc.

    plan = _frozen_plan(
        tmp_path,
        ci_answers={
            "use_just": True,
            "ci_plan_jobs": ["test-python"],
            "ci_plan_action_refs": [
                "actions/checkout@v4",
                "astral-sh/setup-uv@v5",
                "actions/setup-python@v5",
            ],
            "ci_plan_matrix": '[{"lang": "python", "version": "3.13"}]',
            "ci_plan_commands": ["just test", "just lint"],
        },
        lang_python_answers={"python_version": "3.13", "framework": "none"},
    )
    r = _run(project, plan)
    assert r.returncode == 0, r.stderr

    ci_yml = project / ".github" / "workflows" / "ci.yml"
    assert ci_yml.exists(), ".github/workflows/ci.yml must be written"
    content = ci_yml.read_text()

    # Correct action ref form — setup-uv takes precedence over setup-python
    # when both are in action_refs; at least checkout and setup-uv must appear.
    assert "actions/checkout@v4" in content
    assert "astral-sh/setup-uv@v5" in content
    # All action refs are in owner/repo@vN form — none are floating
    assert "@main" not in content
    assert "@master" not in content
    # Commands present
    assert "just test" in content
    assert "just lint" in content


def test_sc001_python_only_single_job(tmp_path):
    """SC-001: python-only plan produces exactly one job."""
    project = tmp_path / "project"
    project.mkdir()
    _stub_justfile(project)

    plan = _frozen_plan(
        tmp_path,
        ci_answers={
            "use_just": True,
            "ci_plan_jobs": ["test-python"],
            "ci_plan_action_refs": ["actions/checkout@v4", "astral-sh/setup-uv@v5"],
            "ci_plan_matrix": '[{"lang": "python", "version": "3.13"}]',
            "ci_plan_commands": ["just test"],
        },
        lang_python_answers={"python_version": "3.13"},
    )
    r = _run(project, plan)
    assert r.returncode == 0, r.stderr

    content = (project / ".github" / "workflows" / "ci.yml").read_text()
    # Only one job under jobs:
    assert "test-python:" in content
    assert "test-ts:" not in content
    assert "test-go:" not in content


# --------------------------------------------------------------------------- #
# SC-002: Python + TS — 2 jobs, TS uses package_manager from frozen answers   #
# --------------------------------------------------------------------------- #

def test_sc002_python_plus_ts_two_jobs(tmp_path):
    """SC-002: py+ts ci_plan → both jobs present in YAML."""
    project = tmp_path / "project"
    project.mkdir()
    _stub_justfile(project)
    _stub_package_json(project, scripts=["test", "lint"])

    plan = _frozen_plan(
        tmp_path,
        ci_answers={
            "use_just": False,
            "ci_plan_jobs": ["test-python", "test-ts"],
            "ci_plan_action_refs": [
                "actions/checkout@v4",
                "astral-sh/setup-uv@v5",
                "oven-sh/setup-bun@v2",
            ],
            "ci_plan_matrix": (
                '[{"lang": "python", "version": "3.13"}, '
                '{"lang": "ts", "pm": "bun"}]'
            ),
            "ci_plan_commands": ["uv run pytest", "bun test"],
        },
        lang_python_answers={"python_version": "3.13", "framework": "none"},
        lang_ts_answers={"package_manager": "bun", "framework": "none"},
    )
    r = _run(project, plan)
    assert r.returncode == 0, r.stderr

    content = (project / ".github" / "workflows" / "ci.yml").read_text()
    assert "test-python:" in content, "test-python job must be present"
    assert "test-ts:" in content, "test-ts job must be present"
    # TS job should use bun setup action
    assert "oven-sh/setup-bun@v2" in content


# --------------------------------------------------------------------------- #
# SC-003: just deploy missing → dropped + WARN, rest of YAML written          #
# --------------------------------------------------------------------------- #

def test_sc003_missing_just_recipe_dropped(tmp_path):
    """SC-003: just deploy not in justfile → dropped, warning, YAML still written."""
    project = tmp_path / "project"
    project.mkdir()
    # Justfile has test/lint but NOT deploy
    _stub_justfile(project, recipes=["default", "test", "lint"])

    plan = _frozen_plan(
        tmp_path,
        ci_answers={
            "use_just": True,
            "ci_plan_jobs": ["test-python"],
            "ci_plan_action_refs": ["actions/checkout@v4", "astral-sh/setup-uv@v5"],
            "ci_plan_matrix": '[{"lang": "python", "version": "3.13"}]',
            "ci_plan_commands": ["just test", "just deploy", "just lint"],
        },
        lang_python_answers={"python_version": "3.13"},
    )
    r = _run(project, plan)
    assert r.returncode == 0, r.stderr

    # The module result is on stdout; warnings should mention deploy dropped
    output_text = r.stdout
    assert "deploy" in output_text.lower() or "dropped" in output_text.lower(), (
        f"Expected deploy/dropped warning in output. stdout={r.stdout!r} stderr={r.stderr!r}"
    )

    ci_yml = project / ".github" / "workflows" / "ci.yml"
    assert ci_yml.exists(), "YAML must still be written even with dropped commands"
    content = ci_yml.read_text()
    assert "just deploy" not in content, "just deploy must not appear in YAML"
    assert "just test" in content, "just test (valid) must be present"
    assert "just lint" in content, "just lint (valid) must be present"


def test_sc003_warning_in_result(tmp_path):
    """SC-003: result JSON includes warning about missing recipe."""
    mod = _load_module_py()
    project = tmp_path / "project"
    project.mkdir()
    _stub_justfile(project, recipes=["test", "lint"])

    _, warnings = mod._validate_commands(
        ["just test", "just deploy", "just lint"],
        use_just=True,
        justfile_recipes={"test", "lint"},
        pkg_scripts=None,
        project_dir=project,
    )
    assert any("deploy" in w for w in warnings), f"Expected deploy warning, got {warnings}"
    assert any("dropped" in w for w in warnings), f"Expected 'dropped' in warnings, got {warnings}"


# --------------------------------------------------------------------------- #
# SC-005: floating action ref → FIXME placeholder + WARN                      #
# --------------------------------------------------------------------------- #

def test_sc005_floating_ref_fixme(tmp_path):
    """SC-005: actions/checkout@main → FIXME placeholder in YAML + warning."""
    project = tmp_path / "project"
    project.mkdir()
    _stub_justfile(project)

    plan = _frozen_plan(
        tmp_path,
        ci_answers={
            "use_just": True,
            "ci_plan_jobs": ["test-python"],
            "ci_plan_action_refs": [
                "actions/checkout@main",   # floating — should get FIXME
                "astral-sh/setup-uv@v5",    # valid — should pass through
            ],
            "ci_plan_matrix": '[{"lang": "python", "version": "3.13"}]',
            "ci_plan_commands": ["just test"],
        },
        lang_python_answers={"python_version": "3.13"},
    )
    r = _run(project, plan)
    assert r.returncode == 0, r.stderr

    ci_yml = project / ".github" / "workflows" / "ci.yml"
    assert ci_yml.exists(), "YAML must still be written despite floating ref"
    content = ci_yml.read_text()

    # FIXME placeholder must appear
    assert "FIXME" in content, f"Expected FIXME in YAML for floating ref. content:\n{content}"
    # Valid ref still present
    assert "astral-sh/setup-uv@v5" in content
    # Warning in stdout
    assert "FIXME" in r.stdout or "floating" in r.stdout.lower() or "not in owner/repo@vN" in r.stdout


def test_sc005_validate_action_refs_unit():
    """SC-005 unit: _validate_action_refs identifies floating refs."""
    mod = _load_module_py()
    valid, fixmes, warnings = mod._validate_action_refs([
        "actions/checkout@v4",
        "actions/checkout@main",
        "actions/setup-python@v5",
        "some/action",  # no @ at all
    ])
    assert "actions/checkout@v4" in valid
    assert "actions/setup-python@v5" in valid
    assert len(fixmes) == 2, f"Expected 2 FIXME entries, got {fixmes}"
    assert len(warnings) == 2, f"Expected 2 warnings, got {warnings}"
    assert all("FIXME" in f for f in fixmes)


# --------------------------------------------------------------------------- #
# SC-008: all commands drop → files_written=[], warning, no YAML written      #
# --------------------------------------------------------------------------- #

def test_sc008_all_commands_drop_no_yaml(tmp_path):
    """SC-008: when all commands are dropped, no YAML is written."""
    project = tmp_path / "project"
    project.mkdir()
    # Justfile only has 'test', but commands only reference 'deploy' + 'release'
    _stub_justfile(project, recipes=["test"])

    plan = _frozen_plan(
        tmp_path,
        ci_answers={
            "use_just": True,
            "ci_plan_jobs": ["test-python"],
            "ci_plan_action_refs": ["actions/checkout@v4"],
            "ci_plan_matrix": '[{"lang": "python", "version": "3.13"}]',
            "ci_plan_commands": ["just deploy", "just release"],
        },
        lang_python_answers={"python_version": "3.13"},
    )
    r = _run(project, plan)
    assert r.returncode == 0, r.stderr

    ci_yml = project / ".github" / "workflows" / "ci.yml"
    assert not ci_yml.exists(), "No YAML must be written when all commands are dropped"

    # Warning must be present
    assert "dropped" in r.stdout.lower() or "dropped" in r.stderr.lower(), (
        f"Expected 'dropped' warning in output. stdout={r.stdout!r}"
    )


# --------------------------------------------------------------------------- #
# Additional unit tests for the YAML renderer and validators                  #
# --------------------------------------------------------------------------- #

def test_render_ci_yaml_quotes_colon_values():
    """Values containing ':' must be quoted in YAML output."""
    mod = _load_module_py()
    plan_dict = {
        "name": "CI: test",
        "on": {"push": {"branches": ["main"]}},
        "jobs": {},
    }
    yaml = mod.render_ci_yaml(plan_dict)
    # The name value contains ':' and must be quoted
    assert "'CI: test'" in yaml or '"CI: test"' in yaml, (
        f"Value with colon must be quoted. yaml:\n{yaml}"
    )


def test_justfile_recipe_loader(tmp_path):
    """_load_justfile_recipes correctly parses recipe names."""
    mod = _load_module_py()
    justfile = tmp_path / "justfile"
    justfile.write_text(
        "default:\n    @just --list\n\ntest:\n    echo test\n\nlint:\n    echo lint\n"
    )
    recipes = mod._load_justfile_recipes(tmp_path)
    assert recipes is not None
    assert "default" in recipes
    assert "test" in recipes
    assert "lint" in recipes
    assert "deploy" not in recipes


def test_justfile_recipe_loader_missing(tmp_path):
    """_load_justfile_recipes returns None when justfile is absent."""
    mod = _load_module_py()
    result = mod._load_justfile_recipes(tmp_path)
    assert result is None


def test_validate_commands_bare_passthrough(tmp_path):
    """Bare commands (uv run pytest, cargo test) pass through without validation."""
    mod = _load_module_py()
    valid, warnings = mod._validate_commands(
        ["uv run pytest", "cargo test", "go test ./..."],
        use_just=True,
        justfile_recipes={"test"},
        pkg_scripts=None,
        project_dir=tmp_path,
    )
    assert valid == ["uv run pytest", "cargo test", "go test ./..."]
    assert warnings == []


def test_validate_commands_pkg_json_missing_passes_through(tmp_path):
    """When package.json is absent, bun run scripts pass through with warning."""
    mod = _load_module_py()
    valid, warnings = mod._validate_commands(
        ["bun run test"],
        use_just=False,
        justfile_recipes=None,
        pkg_scripts=None,  # None = file absent
        project_dir=tmp_path,
    )
    # Passes through with a warning when file is absent
    assert "bun run test" in valid
    assert any("package.json" in w for w in warnings)


def test_validate_commands_pkg_json_missing_script_dropped(tmp_path):
    """When package.json is present but script missing → dropped."""
    mod = _load_module_py()
    valid, warnings = mod._validate_commands(
        ["bun run deploy"],
        use_just=False,
        justfile_recipes=None,
        pkg_scripts={"test", "lint"},  # deploy not in scripts
        project_dir=tmp_path,
    )
    assert "bun run deploy" not in valid
    assert any("deploy" in w for w in warnings)


def test_use_just_false_drops_just_commands(tmp_path):
    """When use_just=false, all 'just ...' commands are dropped."""
    mod = _load_module_py()
    valid, warnings = mod._validate_commands(
        ["just test", "uv run pytest"],
        use_just=False,
        justfile_recipes={"test"},
        pkg_scripts=None,
        project_dir=tmp_path,
    )
    assert "just test" not in valid
    assert "uv run pytest" in valid
    assert any("use_just=false" in w for w in warnings)
