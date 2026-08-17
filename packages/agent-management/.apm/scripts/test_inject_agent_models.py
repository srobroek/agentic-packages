from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("inject-agent-models.py")
SPEC = importlib.util.spec_from_file_location("inject_agent_models", SCRIPT)
assert SPEC and SPEC.loader
injector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(injector)


def write_mapping(root: Path, *, model: str = "gpt-5", effort: str = "high") -> None:
    mapping = (
        "version: 1\n"
        "agents:\n"
        "  demo:\n"
        "    codex:\n"
        f"      model: {model}\n"
        f"      reasoning_effort: {effort}\n"
    )
    mapping_path = root / ".apm" / "agent-models.yml"
    mapping_path.parent.mkdir(parents=True)
    mapping_path.write_text(mapping, encoding="utf-8")


def write_deployed_agent(root: Path, text: str) -> Path:
    path = root / ".codex" / "agents" / "demo.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_injects_models_and_check_is_idempotent(tmp_path: Path) -> None:
    write_mapping(tmp_path)
    path = write_deployed_agent(
        tmp_path,
        'name = "demo"\ndescription = "Demo"\ndeveloper_instructions = "Do it"\n',
    )

    assert injector.main(["--root", str(tmp_path)]) == 0
    parsed = tomllib.loads(path.read_text(encoding="utf-8"))
    assert parsed["model"] == "gpt-5"
    assert parsed["model_reasoning_effort"] == "high"
    assert injector.main(["--root", str(tmp_path), "--check"]) == 0


def test_ignores_resolution_staging_mappings(tmp_path: Path) -> None:
    write_mapping(tmp_path)
    stale = (
        tmp_path
        / "apm_modules"
        / ".apm-resolution-staging"
        / "stale"
        / ".apm"
        / "agent-models.yml"
    )
    stale.parent.mkdir(parents=True)
    stale.write_text(
        "version: 1\n"
        "agents:\n"
        "  demo:\n"
        "    codex:\n"
        "      model: old-model\n"
        "      reasoning_effort: low\n",
        encoding="utf-8",
    )

    mappings = injector.load_mappings(tmp_path)
    assert mappings == {"demo": {"model": "gpt-5", "reasoning_effort": "high"}}


def test_rejects_non_mapping_yaml(tmp_path: Path) -> None:
    mapping = tmp_path / ".apm" / "agent-models.yml"
    mapping.parent.mkdir(parents=True)
    mapping.write_text("- not a mapping\n", encoding="utf-8")

    with pytest.raises(injector.MappingError, match="document must be a mapping"):
        injector.load_mappings(tmp_path)


def test_rejects_non_integer_version(tmp_path: Path) -> None:
    mapping = tmp_path / ".apm" / "agent-models.yml"
    mapping.parent.mkdir(parents=True)
    mapping.write_text("version: true\nagents: {}\n", encoding="utf-8")

    with pytest.raises(injector.MappingError, match="version must be 1"):
        injector.load_mappings(tmp_path)


def test_inserts_root_fields_before_toml_tables() -> None:
    text = 'name = "demo"\n[permissions]\nread = true\n'
    patched = injector.expected_text(
        text,
        {"model": "gpt-5", "reasoning_effort": "high"},
    )

    parsed = tomllib.loads(patched)
    assert parsed["model"] == "gpt-5"
    assert parsed["model_reasoning_effort"] == "high"
    assert parsed["permissions"]["read"] is True


def test_does_not_partially_write_when_validation_fails(tmp_path: Path) -> None:
    write_mapping(tmp_path)
    path = write_deployed_agent(tmp_path, 'name = "demo"\ndescription = "Demo"\n')
    unknown = tmp_path / ".codex" / "agents" / "unknown.toml"
    unknown.write_text('name = "unknown"\ndescription = "Unknown"\n', encoding="utf-8")

    with pytest.raises(injector.MappingError, match="lacks agent-models.yml"):
        injector.patch_codex(
            tmp_path,
            {"demo": {"model": "gpt-5", "reasoning_effort": "high"}},
            check=False,
        )
    assert path.read_text(encoding="utf-8") == 'name = "demo"\ndescription = "Demo"\n'
