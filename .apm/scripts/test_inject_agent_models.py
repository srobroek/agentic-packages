from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT_COPY = Path(__file__).with_name("inject-agent-models.py")
SCRIPT = (
    Path(__file__).parents[2]
    / "packages"
    / "agent-management"
    / ".apm"
    / "scripts"
    / "inject-agent-models.py"
)
SPEC = importlib.util.spec_from_file_location("inject_agent_models", SCRIPT)
assert SPEC and SPEC.loader
injector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(injector)


def test_root_copy_matches_distributed_package_copy() -> None:
    assert ROOT_COPY.read_bytes() == SCRIPT.read_bytes()


def write_mapping(path: Path, model: str = "gpt-5.6-luna") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "version: 1\nagents:\n  coder:\n    codex:\n"
        f"      model: {model}\n      reasoning_effort: xhigh\n",
        encoding="utf-8",
    )


def test_discovers_package_owned_mapping_and_patches_codex(tmp_path: Path) -> None:
    write_mapping(tmp_path / "apm_modules" / "owner" / "pkg" / ".apm" / "agent-models.yml")
    agent = tmp_path / ".codex" / "agents" / "coder.toml"
    agent.parent.mkdir(parents=True)
    agent.write_text(
        'name = "coder"\ndescription = "Codes"\ndeveloper_instructions = "Work"\n',
        encoding="utf-8",
    )

    mappings = injector.load_mappings(tmp_path)
    assert injector.patch_codex(tmp_path, mappings, check=False) == 1
    assert injector.patch_codex(tmp_path, mappings, check=True) == 0
    text = agent.read_text(encoding="utf-8")
    assert 'model = "gpt-5.6-luna"' in text
    assert 'model_reasoning_effort = "xhigh"' in text


def test_rejects_conflicting_package_mappings(tmp_path: Path) -> None:
    write_mapping(tmp_path / "packages" / "one" / ".apm" / "agent-models.yml")
    write_mapping(
        tmp_path / "packages" / "two" / ".apm" / "agent-models.yml",
        model="gpt-5.6-sol",
    )

    with pytest.raises(injector.MappingError, match="conflicting mapping for coder"):
        injector.load_mappings(tmp_path)


def test_missing_deployed_agent_fails(tmp_path: Path) -> None:
    write_mapping(tmp_path / ".apm" / "agent-models.yml")

    with pytest.raises(injector.MappingError, match="missing deployed Codex agent"):
        injector.patch_codex(tmp_path, injector.load_mappings(tmp_path), check=False)


def test_deployed_agent_without_mapping_fails(tmp_path: Path) -> None:
    write_mapping(tmp_path / ".apm" / "agent-models.yml")
    agents = tmp_path / ".codex" / "agents"
    agents.mkdir(parents=True)
    (agents / "coder.toml").write_text(
        'name = "coder"\ndescription = "Codes"\ndeveloper_instructions = "Work"\n',
        encoding="utf-8",
    )
    stale = agents / "stale-agent.toml"
    stale.write_text(
        'name = "stale-agent"\ndescription = "Stale"\n'
        'developer_instructions = "Work"\n',
        encoding="utf-8",
    )

    with pytest.raises(
        injector.MappingError,
        match=r"lacks agent-models\.yml entry: .*stale-agent\.toml \(stale-agent\)",
    ):
        injector.patch_codex(tmp_path, injector.load_mappings(tmp_path), check=True)


def test_agent_source_without_mapping_fails(tmp_path: Path) -> None:
    write_mapping(tmp_path / "packages" / "mapped" / ".apm" / "agent-models.yml")
    source = tmp_path / "packages" / "unmapped" / "agents" / "reviewer.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        '---\nname: reviewer\ndescription: Reviews\n---\n\nReview the change.\n',
        encoding="utf-8",
    )

    with pytest.raises(
        injector.MappingError,
        match=r"agent source lacks agent-models\.yml entry: .*reviewer\.md \(reviewer\)",
    ):
        injector.validate_source_coverage(tmp_path, injector.load_mappings(tmp_path))


def test_all_repository_agent_sources_have_model_mappings() -> None:
    root = Path(__file__).parents[2]
    mappings = injector.load_mappings(root)
    injector.validate_source_coverage(root, mappings)
