"""Tests for the mcp-config module.

Verifies:
  - SC-006: mcp_servers=[context7, repomix] + no existing .mcp.json →
    creates .mcp.json with mcpServers.context7 (npx @upstash/context7-mcp) +
    mcpServers.repomix; two invocations byte-identical; NO srobroek in output.
  - empty mcp_servers list → no-op, no file written, status ok (FR-010).
  - unknown name (mcp_servers=["bogus"]) → warn + skipped; if only bogus → no file.
  - merge: pre-existing .mcp.json with a user server → myserver PRESERVED + context7 added.
  - malformed existing .mcp.json → warn, NOT clobbered, status ok.
  - manifest: parses without errors; default_enabled=False; step ids [resolve, mcp-gate, write];
    mcp-gate hardness=hard + allow_flag=allow-mcp-config + init_only; inputs declared.
  - no wall-clock in module.py.
  - no "srobroek" runtime literal in module.py.

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_mcp_config.py
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
_PLUGIN_ROOT = _PKG / "skills" / "project-setup"
_RUNNER = _PLUGIN_ROOT / "runner"
_MODULE_REL = "modules/mcp-config"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(
    tmp: Path,
    mcp_servers: list | None = None,
    marketplace: str = "",
    reconcile: bool = True,
    mcp_versions: str = "",
) -> Path:
    """Build a frozen plan.json for the mcp-config write step."""
    if mcp_servers is None:
        mcp_servers = []
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["mcp-config"],
        "modules": {
            "mcp-config": {
                "id": "mcp-config",
                "version": "1.0.0",
                "reconcile": reconcile,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "mcp_servers": mcp_servers,
                    "marketplace": marketplace,
                    "mcp_versions": mcp_versions,
                },
                "steps": [
                    {"id": "resolve", "kind": "agent", "steering": "steering/resolve.md"},
                    {
                        "id": "mcp-gate",
                        "kind": "gate",
                        "hardness": "hard",
                        "allow_flag": "allow-mcp-config",
                        "init_only": True,
                        "message": (
                            "Configure MCP servers (each runs via npx/uvx; review before approving):\n"
                            "{decision}\nWrite .mcp.json?"
                        ),
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
# Manifest                                                                      #
# --------------------------------------------------------------------------- #

def test_manifest_parses_and_is_valid():
    """Manifest must parse cleanly with correct step shape, gate config, and inputs."""
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, [e.to_dict() for e in mani.errors]

    assert mani.id == "mcp-config"
    assert mani.default_enabled is False, "mcp-config must be default_enabled=false"

    step_ids = [s.id for s in mani.steps]
    assert step_ids == ["resolve", "mcp-gate", "write"], step_ids

    # resolve must be kind=agent
    resolve_step = next(s for s in mani.steps if s.id == "resolve")
    assert resolve_step.kind == "agent"

    # mcp-gate must be hard + init_only + allow_flag=allow-mcp-config
    gate_step = next(s for s in mani.steps if s.id == "mcp-gate")
    assert gate_step.kind == "gate"
    assert gate_step.hardness == "hard"
    assert gate_step.allow_flag == "allow-mcp-config"
    assert gate_step.init_only is True
    assert gate_step.when is None, f"gate must have no 'when' predicate, got: {gate_step.when!r}"

    # write must be kind=python
    write_step = next(s for s in mani.steps if s.id == "write")
    assert write_step.kind == "python"

    # inputs: mcp_servers + marketplace + mcp_versions all declared
    input_keys = [i.key for i in mani.inputs]
    assert "mcp_servers" in input_keys, f"mcp_servers input missing; got {input_keys}"
    assert "marketplace" in input_keys, f"marketplace input missing; got {input_keys}"
    # FR-V2: mcp_versions per-server version override must be declared
    assert "mcp_versions" in input_keys, (
        f"mcp_versions input missing from manifest; got: {input_keys}"
    )
    mv_input = next(i for i in mani.inputs if i.key == "mcp_versions")
    assert mv_input.default == "", (
        f"mcp_versions default should be '' (empty = all latest), got: {mv_input.default!r}"
    )

    # order: after dirs-scaffold
    after = mani.order.get("after", [])
    assert "dirs-scaffold" in after, f"expected dirs-scaffold in after, got {after}"

    # no requires
    assert not mani.order.get("requires")


# --------------------------------------------------------------------------- #
# SC-006: public refs written on confirm (mcp_servers=[context7, repomix])     #
# --------------------------------------------------------------------------- #

def test_sc006_creates_mcp_json_with_public_refs(tmp_path):
    """SC-006: frozen mcp_servers=[context7, repomix] + no existing .mcp.json →
    write creates .mcp.json with correct public upstream entries."""
    project = tmp_path / "proj"
    project.mkdir()

    plan = _frozen_plan(tmp_path, mcp_servers=["context7", "repomix"])
    proc = _run(project, plan)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert ".mcp.json" in result["files_written"]

    doc = json.loads((project / ".mcp.json").read_text())
    servers = doc["mcpServers"]

    # context7 entry
    assert "context7" in servers
    assert servers["context7"]["command"] == "npx"
    assert servers["context7"]["args"] == ["-y", "@upstash/context7-mcp"]

    # repomix entry
    assert "repomix" in servers
    assert servers["repomix"]["command"] == "npx"
    assert servers["repomix"]["args"] == ["-y", "repomix", "--mcp"]

    # Only requested servers present
    assert set(servers.keys()) == {"context7", "repomix"}


def test_sc006_deterministic_two_invocations(tmp_path):
    """SC-006: two invocations with the same plan produce byte-identical .mcp.json."""
    project = tmp_path / "proj"
    project.mkdir()

    plan = _frozen_plan(tmp_path, mcp_servers=["context7", "repomix"])

    # First run — creates .mcp.json
    proc1 = _run(project, plan)
    assert proc1.returncode == 0, proc1.stderr
    content1 = (project / ".mcp.json").read_bytes()

    # Second run — reconcile=true rewrites; must produce same bytes
    proc2 = _run(project, plan)
    assert proc2.returncode == 0, proc2.stderr
    content2 = (project / ".mcp.json").read_bytes()

    assert content1 == content2, "Two invocations must produce byte-identical output"


def test_sc006_no_srobroek_in_output(tmp_path):
    """SC-006: .mcp.json output must contain zero 'srobroek' references."""
    project = tmp_path / "proj"
    project.mkdir()

    plan = _frozen_plan(
        tmp_path,
        mcp_servers=["context7", "repomix", "package-version", "codebase-memory"],
    )
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr

    content = (project / ".mcp.json").read_text()
    assert "srobroek" not in content.lower(), (
        f"srobroek must not appear in .mcp.json output; got:\n{content}"
    )


# --------------------------------------------------------------------------- #
# FR-010: empty list → no-op                                                   #
# --------------------------------------------------------------------------- #

def test_empty_mcp_servers_no_op(tmp_path):
    """FR-010: empty mcp_servers → status ok, no file written."""
    project = tmp_path / "proj"
    project.mkdir()

    plan = _frozen_plan(tmp_path, mcp_servers=[])
    proc = _run(project, plan)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert result["files_written"] == []
    assert not (project / ".mcp.json").exists()


# --------------------------------------------------------------------------- #
# Unknown name → warn + skipped; only unknowns → no file written               #
# --------------------------------------------------------------------------- #

def test_unknown_name_warns_and_skips(tmp_path):
    """mcp_servers=["bogus"] → warn emitted, skipped, no file written."""
    project = tmp_path / "proj"
    project.mkdir()

    plan = _frozen_plan(tmp_path, mcp_servers=["bogus"])
    proc = _run(project, plan)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert result["files_written"] == [], "No file should be written for all-unknown servers"
    assert not (project / ".mcp.json").exists()

    warnings = result.get("warnings", [])
    assert any("bogus" in w for w in warnings), (
        f"Expected a warning mentioning 'bogus', got: {warnings}"
    )


def test_mixed_known_and_unknown_writes_known_warns_unknown(tmp_path):
    """mcp_servers=["context7", "bogus"] → context7 written, bogus warned."""
    project = tmp_path / "proj"
    project.mkdir()

    plan = _frozen_plan(tmp_path, mcp_servers=["context7", "bogus"])
    proc = _run(project, plan)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert ".mcp.json" in result["files_written"]

    doc = json.loads((project / ".mcp.json").read_text())
    servers = doc["mcpServers"]
    assert "context7" in servers
    assert "bogus" not in servers

    warnings = result.get("warnings", [])
    assert any("bogus" in w for w in warnings), (
        f"Expected a warning mentioning 'bogus', got: {warnings}"
    )


# --------------------------------------------------------------------------- #
# Merge: pre-existing .mcp.json → foreign servers preserved                    #
# --------------------------------------------------------------------------- #

def test_merge_preserves_foreign_servers(tmp_path):
    """Pre-existing .mcp.json with myserver → after write, myserver PRESERVED + context7 added."""
    project = tmp_path / "proj"
    project.mkdir()

    # Pre-existing config with a user-defined server
    existing = {
        "mcpServers": {
            "myserver": {"command": "uvx", "args": ["my-mcp-tool"]},
        }
    }
    (project / ".mcp.json").write_text(json.dumps(existing, indent=2))

    plan = _frozen_plan(tmp_path, mcp_servers=["context7"])
    proc = _run(project, plan)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"

    doc = json.loads((project / ".mcp.json").read_text())
    servers = doc["mcpServers"]

    # Foreign server must be preserved
    assert "myserver" in servers, f"myserver should be preserved; got keys: {list(servers)}"
    assert servers["myserver"] == {"command": "uvx", "args": ["my-mcp-tool"]}

    # New server must be added
    assert "context7" in servers
    assert servers["context7"]["command"] == "npx"


# --------------------------------------------------------------------------- #
# Malformed existing .mcp.json → warn, NOT clobbered, status ok                #
# --------------------------------------------------------------------------- #

def test_malformed_existing_mcp_json_not_clobbered(tmp_path):
    """Malformed existing .mcp.json → warn, NOT clobbered, status ok."""
    project = tmp_path / "proj"
    project.mkdir()

    malformed = "{ this is not valid json !!!"
    (project / ".mcp.json").write_text(malformed)

    plan = _frozen_plan(tmp_path, mcp_servers=["context7"])
    proc = _run(project, plan)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert result["files_written"] == [], "Must not write when existing file is malformed"

    # Original malformed content must be unchanged
    assert (project / ".mcp.json").read_text() == malformed

    warnings = result.get("warnings", [])
    assert any("malformed" in w.lower() or "invalid" in w.lower() or "json" in w.lower() for w in warnings), (
        f"Expected a warning about malformed JSON, got: {warnings}"
    )


# --------------------------------------------------------------------------- #
# No wall-clock import/call in module.py                                        #
# --------------------------------------------------------------------------- #

def test_no_wall_clock_in_module_py():
    """module.py must not import datetime/time or call wall-clock functions."""
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    source = module_py.read_text(encoding="utf-8")

    for bad in ("import datetime", "import time", "from datetime", "from time"):
        assert bad not in source, f"module.py must not use {bad!r} (no wall-clock)"

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in ("datetime", "time"), (
                    f"module.py imports wall-clock module: {alias.name!r}"
                )
        if isinstance(node, ast.ImportFrom):
            assert node.module not in ("datetime", "time"), (
                f"module.py imports from wall-clock module: {node.module!r}"
            )


# --------------------------------------------------------------------------- #
# No "srobroek" runtime literal in module.py                                   #
# --------------------------------------------------------------------------- #

def test_no_srobroek_runtime_literal_in_module_py():
    """module.py must not contain 'srobroek' in any runtime constant or logic."""
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    source = module_py.read_text(encoding="utf-8")

    # Walk the AST; check string constants (not comments/docstrings from the module
    # header). We parse and look at Constant nodes that carry string values.
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert "srobroek" not in node.value.lower(), (
                f"module.py contains 'srobroek' in a string constant at line {node.lineno}: "
                f"{node.value!r}"
            )


# --------------------------------------------------------------------------- #
# FR-V2: per-server version overrides via mcp_versions                         #
# --------------------------------------------------------------------------- #

def test_mcp_versions_pins_package_token(tmp_path):
    """mcp_versions='context7=1.0.14' → context7 args contain '@upstash/context7-mcp@1.0.14'."""
    project = tmp_path / "proj"
    project.mkdir()

    plan = _frozen_plan(
        tmp_path,
        mcp_servers=["context7"],
        mcp_versions="context7=1.0.14",
    )
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok", result
    assert ".mcp.json" in result["files_written"]

    doc = json.loads((project / ".mcp.json").read_text())
    servers = doc["mcpServers"]
    assert "context7" in servers
    # The versioned package token must be in args
    args = servers["context7"]["args"]
    assert "@upstash/context7-mcp@1.0.14" in args, (
        f"Expected versioned package token in args, got: {args}"
    )


def test_mcp_versions_no_override_is_unpinned(tmp_path):
    """mcp_versions='' (default) → context7 args contain '@upstash/context7-mcp' (no @version)."""
    project = tmp_path / "proj"
    project.mkdir()

    plan = _frozen_plan(
        tmp_path,
        mcp_servers=["context7"],
        mcp_versions="",
    )
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok", result

    doc = json.loads((project / ".mcp.json").read_text())
    args = doc["mcpServers"]["context7"]["args"]
    # The unpinned token must be present; no @version appended
    assert "@upstash/context7-mcp" in args, f"Expected base package in args, got: {args}"
    for token in args:
        assert not (token.startswith("@upstash/context7-mcp@") and token != "@upstash/context7-mcp"), (
            f"No version suffix expected in unpinned mode, got: {token!r}"
        )


def test_mcp_versions_repomix_pin_preserves_mcp_flag(tmp_path):
    """mcp_versions='repomix=0.2.0' → package token pinned but '--mcp' flag preserved."""
    project = tmp_path / "proj"
    project.mkdir()

    plan = _frozen_plan(
        tmp_path,
        mcp_servers=["repomix"],
        mcp_versions="repomix=0.2.0",
    )
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok", result

    doc = json.loads((project / ".mcp.json").read_text())
    args = doc["mcpServers"]["repomix"]["args"]
    # Package token must be versioned
    assert "repomix@0.2.0" in args, f"Expected pinned repomix token, got: {args}"
    # --mcp flag must be preserved
    assert "--mcp" in args, f"--mcp flag must be preserved after pinning, got: {args}"


def test_mcp_versions_multiple_overrides(tmp_path):
    """mcp_versions='context7=1.0.14 repomix=0.2.0' → both servers pinned."""
    project = tmp_path / "proj"
    project.mkdir()

    plan = _frozen_plan(
        tmp_path,
        mcp_servers=["context7", "repomix"],
        mcp_versions="context7=1.0.14 repomix=0.2.0",
    )
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok", result

    doc = json.loads((project / ".mcp.json").read_text())
    servers = doc["mcpServers"]
    assert "@upstash/context7-mcp@1.0.14" in servers["context7"]["args"]
    assert "repomix@0.2.0" in servers["repomix"]["args"]
    assert "--mcp" in servers["repomix"]["args"]


def test_mcp_versions_partial_override(tmp_path):
    """mcp_versions pins only context7; repomix stays unpinned."""
    project = tmp_path / "proj"
    project.mkdir()

    plan = _frozen_plan(
        tmp_path,
        mcp_servers=["context7", "repomix"],
        mcp_versions="context7=1.0.14",
    )
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr

    doc = json.loads((project / ".mcp.json").read_text())
    servers = doc["mcpServers"]
    # context7 pinned
    assert "@upstash/context7-mcp@1.0.14" in servers["context7"]["args"]
    # repomix unpinned
    repomix_args = servers["repomix"]["args"]
    assert "repomix" in repomix_args, f"Expected bare 'repomix' token, got: {repomix_args}"
    assert not any("repomix@" in t for t in repomix_args), (
        f"repomix should be unpinned (no version suffix), got: {repomix_args}"
    )
