"""End-to-end tests for the env-example module.

Verifies:
  - manifest parses and is valid (step ids, gate hardness, init_only)
  - SC-001: FastAPI env_keys → status ok, all keys present, no secret placeholders
  - SC-002: placeholder matching looks_like_secret → status=error, nothing written
  - SC-003: sorted output + preamble present + byte-identical on two runs
  - SC-004: empty env_keys → preamble-only file, status ok
  - SC-007: invalid name skipped with warning; valid entries still written
  - SC-008: secret_bool=true + empty placeholder → status=error, nothing written

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_env_example.py
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
_MODULE_REL = "modules/env-example"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(tmp: Path, env_keys: list | None = None) -> Path:
    """Build a frozen plan.json with canned env_keys for the write step."""
    if env_keys is None:
        env_keys = []
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["env-example"],
        "modules": {
            "env-example": {
                "id": "env-example",
                "version": "1.0.0",
                "reconcile": True,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "framework_python": "",
                    "framework_ts": "",
                    "extra_env_hints": "",
                    "env_keys": env_keys,
                },
                "steps": [
                    {"id": "resolve", "kind": "agent", "steering": "steering/resolve.md"},
                    {
                        "id": "preview",
                        "kind": "gate",
                        "hardness": "soft",
                        "init_only": True,
                        "message": "Env vars for .env.example (agent-derived):\n{decision}\nWrite .env.example with these placeholder keys?",
                    },
                    {"id": "write", "kind": "python"},
                ],
            }
        },
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _run(
    project: Path,
    plan: Path,
    step: str = "write",
    inspect: bool = False,
) -> subprocess.CompletedProcess:
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    cmd = ["uv", "run", str(module_py), "--plan", str(plan), "--step", step]
    if inspect:
        cmd.append("--inspect")
    env = {**os.environ, "PLUGIN_ROOT": str(_PLUGIN_ROOT), "PROJECT_DIR": str(project)}
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))


# --------------------------------------------------------------------------- #
# Manifest                                                                     #
# --------------------------------------------------------------------------- #

def test_manifest_parses_and_is_valid():
    """Manifest must parse cleanly with the correct step shape."""
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, [e.to_dict() for e in mani.errors]
    assert mani.id == "env-example"
    assert mani.default_enabled is False
    assert mani.reconcile is True

    step_ids = [s.id for s in mani.steps]
    assert step_ids == ["resolve", "preview", "write"], step_ids

    # resolve must be kind=agent
    resolve_step = next(s for s in mani.steps if s.id == "resolve")
    assert resolve_step.kind == "agent"

    # preview must be a soft, init_only gate
    preview_step = next(s for s in mani.steps if s.id == "preview")
    assert preview_step.kind == "gate"
    assert preview_step.hardness == "soft"
    assert preview_step.init_only is True

    # write must be kind=python
    write_step = next(s for s in mani.steps if s.id == "write")
    assert write_step.kind == "python"

    # order: after lists lang-python and lang-ts (no requires)
    assert "lang-python" in mani.order.get("after", [])
    assert "lang-ts" in mani.order.get("after", [])
    assert not mani.order.get("requires")


# --------------------------------------------------------------------------- #
# SC-001: FastAPI stack → ok, all keys present, safe placeholders              #
# --------------------------------------------------------------------------- #

def test_sc001_fastapi_keys_written(tmp_path):
    """SC-001: FastAPI-ish env_keys produce status ok, all keys present."""
    project = tmp_path / "proj"
    project.mkdir()

    env_keys = [
        {"name": "DATABASE_URL", "placeholder": "postgres://user:pass@localhost/db",
         "comment": "Database connection string", "secret_bool": False},
        {"name": "SECRET_KEY", "placeholder": "your-secret-key-here",
         "comment": "Rotate before committing to production", "secret_bool": True},
        {"name": "DEBUG", "placeholder": "true",
         "comment": "Enable debug mode", "secret_bool": False},
    ]
    plan = _frozen_plan(tmp_path, env_keys=env_keys)
    proc = _run(project, plan)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert ".env.example" in result["files_written"]

    content = (project / ".env.example").read_text()
    assert "DATABASE_URL=postgres://user:pass@localhost/db" in content
    assert "SECRET_KEY=your-secret-key-here" in content
    assert "DEBUG=true" in content


# --------------------------------------------------------------------------- #
# SC-002: secret-shaped placeholder → hard error, nothing written              #
# --------------------------------------------------------------------------- #

def test_sc002_secret_placeholder_hard_error(tmp_path):
    """SC-002: a placeholder matching looks_like_secret → status=error, no file."""
    project = tmp_path / "proj"
    project.mkdir()

    env_keys = [
        {
            "name": "GITHUB_TOKEN",
            "placeholder": "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "comment": "",
            "secret_bool": True,
        }
    ]
    plan = _frozen_plan(tmp_path, env_keys=env_keys)
    proc = _run(project, plan)

    assert proc.returncode == 1
    result = json.loads(proc.stdout)
    assert result["status"] == "error"
    assert not (project / ".env.example").exists()
    # Error message should name the offending key
    error = result.get("error", {})
    assert "GITHUB_TOKEN" in str(error)


# --------------------------------------------------------------------------- #
# SC-003: sorted output + preamble + byte-identical on two runs                #
# --------------------------------------------------------------------------- #

def test_sc003_sorted_preamble_deterministic(tmp_path):
    """SC-003: entries sorted alphabetically, preamble present, byte-identical on re-run."""
    project = tmp_path / "proj"
    project.mkdir()

    # Deliberately unsorted input: Z before A
    env_keys = [
        {"name": "ZEBRA_URL", "placeholder": "http://localhost/zebra", "comment": "", "secret_bool": False},
        {"name": "ALPHA_KEY", "placeholder": "your-alpha-key-here", "comment": "Alpha key", "secret_bool": True},
        {"name": "MIDDLE_VAR", "placeholder": "some-value", "comment": "", "secret_bool": False},
    ]
    plan = _frozen_plan(tmp_path, env_keys=env_keys)

    # First run
    proc1 = _run(project, plan)
    assert proc1.returncode == 0, proc1.stderr
    content1 = (project / ".env.example").read_bytes()

    # Preamble must be present
    text1 = content1.decode("utf-8")
    assert "# .env.example — generated by project-setup" in text1
    assert "# DO NOT commit real values to version control." in text1

    # Must be sorted alphabetically
    lines = [ln for ln in text1.splitlines() if ln and not ln.startswith("#")]
    names = [ln.split("=")[0] for ln in lines]
    assert names == sorted(names), f"Lines not sorted: {names}"

    # Second run — must produce identical bytes (idempotent)
    # Remove the file to force a re-create from same plan
    (project / ".env.example").unlink()
    proc2 = _run(project, plan)
    assert proc2.returncode == 0, proc2.stderr
    content2 = (project / ".env.example").read_bytes()
    assert content1 == content2, "File content differs between runs — not deterministic"


# --------------------------------------------------------------------------- #
# SC-004: empty env_keys → preamble-only file, no error                       #
# --------------------------------------------------------------------------- #

def test_sc004_empty_env_keys_writes_preamble_only(tmp_path):
    """SC-004: empty env_keys list → .env.example with only preamble, status ok."""
    project = tmp_path / "proj"
    project.mkdir()

    plan = _frozen_plan(tmp_path, env_keys=[])
    proc = _run(project, plan)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert ".env.example" in result["files_written"]

    content = (project / ".env.example").read_text()
    assert "# .env.example — generated by project-setup" in content
    assert "# DO NOT commit real values to version control." in content
    # No KEY=value lines should be present
    non_comment_lines = [ln for ln in content.splitlines() if ln and not ln.startswith("#")]
    assert non_comment_lines == [], f"Unexpected non-comment lines: {non_comment_lines}"


# --------------------------------------------------------------------------- #
# SC-007: invalid name skipped with warning, valid entries still written       #
# --------------------------------------------------------------------------- #

def test_sc007_invalid_name_skipped_valid_written(tmp_path):
    """SC-007: entry with bad name (lowercase + space) is skipped; valid entry written."""
    project = tmp_path / "proj"
    project.mkdir()

    env_keys = [
        {"name": "bad name", "placeholder": "some-value", "comment": "", "secret_bool": False},
        {"name": "VALID_KEY", "placeholder": "your-valid-key-here", "comment": "A valid key", "secret_bool": False},
    ]
    plan = _frozen_plan(tmp_path, env_keys=env_keys)
    proc = _run(project, plan)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"

    content = (project / ".env.example").read_text()
    # Valid entry must be present
    assert "VALID_KEY=your-valid-key-here" in content
    # Bad entry must NOT be present
    assert "bad name" not in content

    # A warning must be emitted about the bad name
    warnings = result.get("warnings", [])
    assert any("bad name" in w or "invalid name" in w.lower() for w in warnings), warnings


# --------------------------------------------------------------------------- #
# SC-008: secret_bool=true + empty placeholder → hard error, nothing written   #
# --------------------------------------------------------------------------- #

def test_sc008_secret_bool_empty_placeholder_hard_error(tmp_path):
    """SC-008: secret_bool=true with empty placeholder → status=error, no file."""
    project = tmp_path / "proj"
    project.mkdir()

    env_keys = [
        {"name": "API_SECRET", "placeholder": "", "comment": "", "secret_bool": True},
    ]
    plan = _frozen_plan(tmp_path, env_keys=env_keys)
    proc = _run(project, plan)

    assert proc.returncode == 1
    result = json.loads(proc.stdout)
    assert result["status"] == "error"
    assert not (project / ".env.example").exists()
    # Error should mention the key name
    error = result.get("error", {})
    assert "API_SECRET" in str(error)


# --------------------------------------------------------------------------- #
# Additional: idempotent second run produces skip                              #
# --------------------------------------------------------------------------- #

def test_idempotent_second_run_skips(tmp_path):
    """Second run with identical frozen plan → diff kind=skip, files_written=[]."""
    project = tmp_path / "proj"
    project.mkdir()

    env_keys = [
        {"name": "FOO", "placeholder": "foo-value", "comment": "Foo var", "secret_bool": False},
    ]
    plan = _frozen_plan(tmp_path, env_keys=env_keys)

    # First run writes the file
    proc1 = _run(project, plan)
    assert proc1.returncode == 0, proc1.stderr

    # Second run with same content should skip
    proc2 = _run(project, plan)
    assert proc2.returncode == 0, proc2.stderr
    result2 = json.loads(proc2.stdout)
    assert result2["diffs"][0]["kind"] == "skip"
    assert result2["files_written"] == []


# --------------------------------------------------------------------------- #
# Additional: inspect mode writes nothing                                      #
# --------------------------------------------------------------------------- #

def test_inspect_writes_nothing(tmp_path):
    """--inspect must report a create diff but not touch the filesystem."""
    project = tmp_path / "proj"
    project.mkdir()

    env_keys = [
        {"name": "MY_VAR", "placeholder": "my-value", "comment": "", "secret_bool": False},
    ]
    plan = _frozen_plan(tmp_path, env_keys=env_keys)
    proc = _run(project, plan, inspect=True)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["diffs"][0]["kind"] == "create"
    assert not (project / ".env.example").exists()


# --------------------------------------------------------------------------- #
# Additional: comment suffix appears inline                                    #
# --------------------------------------------------------------------------- #

def test_comment_suffix_inline(tmp_path):
    """Entries with non-empty comment get an inline '  # comment' suffix."""
    project = tmp_path / "proj"
    project.mkdir()

    env_keys = [
        {"name": "DB_HOST", "placeholder": "localhost", "comment": "Database host", "secret_bool": False},
        {"name": "PORT", "placeholder": "5432", "comment": "", "secret_bool": False},
    ]
    plan = _frozen_plan(tmp_path, env_keys=env_keys)
    proc = _run(project, plan)

    assert proc.returncode == 0, proc.stderr
    content = (project / ".env.example").read_text()
    assert "DB_HOST=localhost  # Database host" in content
    # No trailing comment for PORT (empty comment)
    port_line = next(ln for ln in content.splitlines() if ln.startswith("PORT="))
    assert "#" not in port_line
