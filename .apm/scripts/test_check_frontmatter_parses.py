from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("check-frontmatter-parses.py")
SPEC = importlib.util.spec_from_file_location("check_frontmatter_parses", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _agent(root: Path, frontmatter: str) -> Path:
    path = root / "packages/pkg/.apm/agents/role.agent.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: role\n{frontmatter}---\n\nBody.\n", encoding="utf-8")
    return path


@pytest.mark.parametrize("mode", sorted(MODULE.PERMISSION_MODES))
def test_accepts_every_legal_permission_mode(tmp_path, mode):
    _agent(tmp_path, f"permissionMode: {mode}\n")

    assert MODULE.findings(tmp_path) == []


@pytest.mark.parametrize("mode", ["acceptEdit", "AcceptEdits", "accept-edits", "bogusValue"])
def test_rejects_realistic_permission_mode_typos(tmp_path, mode):
    path = _agent(tmp_path, f"permissionMode: {mode}\n")

    bad = MODULE.findings(tmp_path)

    assert [p for p, _ in bad] == [path]
    reason = bad[0][1]
    assert mode in reason
    assert "acceptEdits" in reason


def test_absent_permission_mode_is_legal(tmp_path):
    _agent(tmp_path, "")

    assert MODULE.findings(tmp_path) == []


def test_unparsable_frontmatter_is_reported_once(tmp_path):
    """An unparsable block cannot also be mode-checked -- one finding, not two."""
    path = _agent(tmp_path, "description: Rules for X: code economy\n")

    bad = MODULE.findings(tmp_path)

    assert len(bad) == 1
    assert bad[0][0] == path


def test_repo_tree_has_no_findings():
    assert MODULE.findings(MODULE.ROOT) == []
