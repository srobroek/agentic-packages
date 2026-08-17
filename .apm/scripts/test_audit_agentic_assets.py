from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).with_name("audit-agentic-assets.py")
SPEC = importlib.util.spec_from_file_location("audit_agentic_assets", SCRIPT)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def write_agent(package: Path, package_name: str, *, tools: bool = False) -> None:
    agents = package / ".apm" / "agents"
    agents.mkdir(parents=True)
    (package / "apm.yml").write_text(
        f"name: {package_name}\ntarget: all\n",
        encoding="utf-8",
    )
    tools_block = "tools:\n  - Read\n" if tools else ""
    (agents / "reviewer.agent.md").write_text(
        "---\n"
        "name: reviewer\n"
        "model: sonnet\n"
        "effort: high\n"
        "permissionMode: plan\n"
        f"{tools_block}"
        "---\n",
        encoding="utf-8",
    )


def test_metadata_prefers_direct_local_package_over_remote_cache(tmp_path: Path) -> None:
    local = tmp_path / "apm_modules" / "_local" / "quality"
    remote = tmp_path / "apm_modules" / "owner" / "repo" / "packages" / "quality"
    write_agent(local, "quality")
    write_agent(remote, "quality", tools=True)

    metadata = audit.source_agent_metadata(tmp_path)

    assert len(metadata) == 1
    source_path, actual = next(iter(metadata.items()))
    assert source_path.startswith("apm_modules/_local/quality/")
    assert actual["tools"] == ""


def test_metadata_keeps_same_role_from_distinct_packages(tmp_path: Path) -> None:
    write_agent(tmp_path / "packages" / "quality-one", "quality-one")
    write_agent(tmp_path / "packages" / "quality-two", "quality-two")

    metadata = audit.source_agent_metadata(tmp_path)

    assert len(metadata) == 2
