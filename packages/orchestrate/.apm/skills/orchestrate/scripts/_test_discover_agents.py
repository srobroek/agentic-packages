#!/usr/bin/env python3
"""Self-tests for deterministic, validated agent discovery."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("discover-agents.py")
SPEC = importlib.util.spec_from_file_location("discover_agents", SCRIPT)
assert SPEC and SPEC.loader
discover_agents = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(discover_agents)


def definition(
    name: str,
    *,
    description: str = "Handles code implementation.",
    model: str = "sonnet",
    tools: str = "Read, Edit, Bash",
    extra: str = "",
) -> str:
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"model: {model}\n"
        f"tools: {tools}\n"
        f"{extra}"
        "---\n\nBody.\n"
    )


class DiscoverAgentsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.first = self.root / "first"
        self.second = self.root / "second"
        self.first.mkdir()
        self.second.mkdir()
        self.scope_patch = mock.patch.object(
            discover_agents, "_default_scopes", return_value=[]
        )
        self.scope_patch.start()

    def tearDown(self) -> None:
        self.scope_patch.stop()
        self.temporary.cleanup()

    def write(self, directory: Path, filename: str, text: str) -> None:
        (directory / filename).write_text(text, encoding="utf-8")

    def collect(self, *directories: Path) -> list[dict[str, object]]:
        return discover_agents.collect(
            [os.fspath(path) for path in directories], None, False
        )

    def test_catalog_is_sorted_and_exposes_routing_metadata(self) -> None:
        self.write(
            self.first,
            "zeta.agent.md",
            definition(
                "zeta",
                extra="task-kinds: [docs, code]\ncapabilities: [python, git]\n",
            ),
        )
        self.write(self.first, "alpha.md", definition("alpha"))

        agents = self.collect(self.first)

        self.assertEqual([agent["name"] for agent in agents], ["alpha", "zeta"])
        self.assertEqual(agents[1]["task_kinds"], ["code", "docs"])
        self.assertEqual(agents[1]["capabilities"], ["git", "python"])

    def test_higher_precedence_duplicate_wins(self) -> None:
        self.write(
            self.first,
            "preferred.md",
            definition("duplicate", description="Preferred implementation agent."),
        )
        self.write(
            self.second,
            "fallback.md",
            definition("duplicate", description="Fallback implementation agent."),
        )

        agents = self.collect(self.first, self.second)

        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0]["description"], "Preferred implementation agent.")

    def test_role_filter_cannot_bypass_higher_precedence_duplicate(self) -> None:
        self.write(
            self.first,
            "preferred.md",
            definition("duplicate", description="Reviews pull requests."),
        )
        self.write(
            self.second,
            "fallback.md",
            definition("duplicate", description="Codes implementation."),
        )

        agents = discover_agents.collect(
            [os.fspath(self.first), os.fspath(self.second)], "coder", False
        )

        self.assertEqual(agents, [])

    def test_malformed_duplicate_does_not_hide_valid_lower_precedence_agent(
        self,
    ) -> None:
        self.write(
            self.first, "broken.md", "---\nname: duplicate\nname: duplicate\n---\n"
        )
        self.write(self.second, "valid.md", definition("duplicate"))

        agents = self.collect(self.first, self.second)

        self.assertEqual([agent["name"] for agent in agents], ["duplicate"])

    def test_missing_or_malformed_metadata_is_rejected(self) -> None:
        self.write(self.first, "no-frontmatter.md", "Body only.\n")
        self.write(self.first, "missing-description.md", "---\nname: absent\n---\n")
        self.write(self.first, "bad-name.md", definition("Not A Slug"))
        self.write(
            self.first,
            "bad-capability.md",
            definition("bad-capability", extra="capabilities: [valid, Not Valid]\n"),
        )

        self.assertEqual(self.collect(self.first), [])

    def test_missing_optional_model_and_tools_use_runtime_defaults(self) -> None:
        self.write(
            self.first,
            "defaults.md",
            "---\nname: defaults\ndescription: Uses runtime defaults.\n---\n",
        )

        agent = self.collect(self.first)[0]

        self.assertEqual(agent["model"], "inherit")
        self.assertEqual(agent["tools"], "(all)")

    def test_role_filter_uses_whole_words(self) -> None:
        self.write(self.first, "coder.md", definition("coder"))
        self.write(
            self.first, "encoder.md", definition("encoder", description="Encodes data.")
        )

        agents = discover_agents.collect([os.fspath(self.first)], "coder", False)

        self.assertEqual([agent["name"] for agent in agents], ["coder"])

    def test_real_package_agents_preserve_model_and_tools(self) -> None:
        package_agents = SCRIPT.parents[3] / "agents"

        agents = {agent["name"]: agent for agent in self.collect(package_agents)}

        self.assertEqual(agents["workflow-pull-worker"]["model"], "sonnet")
        self.assertEqual(
            agents["workflow-pull-worker"]["tools"],
            "Read, Edit, Write, Bash, Grep, Glob",
        )
        self.assertEqual(agents["workflow-researcher"]["model"], "sonnet")
        self.assertIn("WebSearch", str(agents["workflow-researcher"]["tools"]))
        self.assertEqual(agents["workflow-worker"]["model"], "sonnet")

    def test_json_is_byte_deterministic(self) -> None:
        self.write(self.first, "beta.md", definition("beta"))
        self.write(self.first, "alpha.md", definition("alpha"))

        first = json.dumps(self.collect(self.first), indent=2)
        second = json.dumps(self.collect(self.first), indent=2)

        self.assertEqual(first.encode(), second.encode())


if __name__ == "__main__":
    unittest.main()
