from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).with_name("patch-runtime-agents.py")
SPEC = importlib.util.spec_from_file_location("patch_runtime_agents", SCRIPT)
assert SPEC and SPEC.loader
patch_runtime_agents = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(patch_runtime_agents)


def test_global_agent_discovery_is_bounded_to_apm_paths(tmp_path: Path) -> None:
    root_agent = tmp_path / "root.agent.md"
    root_agent.write_text("---\nname: root\n---\n", encoding="utf-8")

    global_agents = (
        tmp_path
        / ".apm"
        / "apm_modules"
        / "owner"
        / "repo"
        / "packages"
        / "agent-example"
        / ".apm"
        / "agents"
    )
    global_agents.mkdir(parents=True)
    (global_agents / "example.agent.md").write_text(
        "---\nname: example\n---\n",
        encoding="utf-8",
    )

    unrelated = tmp_path / "unrelated" / "deep"
    unrelated.mkdir(parents=True)
    (unrelated / "ignored.agent.md").write_text(
        "---\nname: ignored\n---\n",
        encoding="utf-8",
    )

    discovered = patch_runtime_agents.first_party_agent_dirs(tmp_path)

    assert tmp_path in discovered
    assert global_agents in discovered
    assert unrelated not in discovered


def test_external_global_agents_are_discovered(tmp_path: Path) -> None:
    agents = (
        tmp_path
        / ".apm"
        / "apm_modules"
        / "owner"
        / "repo"
        / "plugins"
        / "example"
        / "agents"
    )
    agents.mkdir(parents=True)
    agent = agents / "reviewer.md"
    agent.write_text("---\nname: reviewer\nmodel: sonnet\n---\n", encoding="utf-8")

    assert patch_runtime_agents.external_agent_paths(tmp_path) == [agent]


def test_patch_codex_normalizes_legacy_none_approval_policy(
    tmp_path: Path,
) -> None:
    agents_dir = tmp_path / ".codex" / "agents"
    agents_dir.mkdir(parents=True)
    agent = agents_dir / "reviewer.toml"
    agent.write_text(
        'description = "Reviews code \\u2014 safely"\n'
        'approval_policy = "none"\n',
        encoding="utf-8",
    )
    (tmp_path / ".codex" / "config.toml").write_text("", encoding="utf-8")

    patched = patch_runtime_agents.patch_codex(
        tmp_path,
        {
            "reviewer": {
                "codex": {
                    "approval_policy": "none",
                }
            }
        },
    )

    assert patched == 1
    assert 'approval_policy = "never"' in agent.read_text(encoding="utf-8")

    # Replacing an existing registration block must treat JSON Unicode escapes
    # as literal text rather than regular-expression replacement syntax.
    patched = patch_runtime_agents.patch_codex(
        tmp_path,
        {
            "reviewer": {
                "codex": {
                    "approval_policy": "none",
                }
            }
        },
    )

    assert patched == 1
