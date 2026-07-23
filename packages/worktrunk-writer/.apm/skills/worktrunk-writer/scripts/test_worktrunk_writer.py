#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("worktrunk-writer.py")
SPEC = importlib.util.spec_from_file_location("worktrunk_writer", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.payload = {
            "schema": 2,
            "items": [
                {
                    "branch": "agent/task",
                    "worktree": {"path": str(self.root)},
                    "vars": {
                        "actor": "codex-writer-a1",
                        "lease": "lease-a1",
                        "bead": "demo-1",
                    },
                }
            ],
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_find_item_joins_branch_and_path(self) -> None:
        item = MODULE.find_item(self.payload, branch="agent/task", path=self.root)
        self.assertEqual(item["vars"]["lease"], "lease-a1")

    def test_find_item_rejects_missing_anchor(self) -> None:
        with self.assertRaises(MODULE.ContractError):
            MODULE.find_item(self.payload, branch="other")

    def test_containing_item_accepts_nested_command_path(self) -> None:
        nested = self.root / "src" / "module"
        self.assertEqual(
            MODULE.containing_item(self.payload, nested)["branch"], "agent/task"
        )

    def test_containing_item_rejects_a_different_checkout(self) -> None:
        self.assertIsNone(MODULE.containing_item(self.payload, Path("/var/tmp/other")))

    def test_copy_result_distinguishes_noop(self) -> None:
        self.assertEqual(MODULE.copy_result(json.dumps({"copied": 0})), "noop")
        self.assertEqual(MODULE.copy_result(json.dumps({"copied": 3})), "done")


class BeadsConflictTests(unittest.TestCase):
    def test_closed_bead_is_not_a_conflict(self) -> None:
        issues = [
            {
                "id": "done-1",
                "status": "closed",
                "metadata": {"branch": "agent/task", "worktree_path": "/tmp/wt"},
            }
        ]
        original = MODULE.beads_json
        MODULE.beads_json = lambda *_args, **_kwargs: issues
        try:
            self.assertEqual(
                MODULE.active_bead_conflicts(
                    Path("/tmp"), "active-1", "agent/task", Path("/tmp/wt")
                ),
                [],
            )
        finally:
            MODULE.beads_json = original

    def test_open_bead_sharing_path_is_a_conflict(self) -> None:
        issues = [
            {
                "id": "other-1",
                "status": "in_progress",
                "metadata": {"branch": "other", "worktree_path": "/tmp/wt"},
            }
        ]
        original = MODULE.beads_json
        MODULE.beads_json = lambda *_args, **_kwargs: issues
        try:
            self.assertEqual(
                MODULE.active_bead_conflicts(
                    Path("/tmp"), "active-1", "agent/task", Path("/tmp/wt")
                ),
                ["other-1"],
            )
        finally:
            MODULE.beads_json = original


class RuntimeHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name).resolve()
        self.primary = root / "primary"
        self.claude = root / "claude"
        self.codex = root / "codex"
        self.reviewer = root / "reviewer"
        self.primary.mkdir()
        self.claude.mkdir()
        self.codex.mkdir()
        self.reviewer.mkdir()
        self.inventory = {
            "schema": 2,
            "items": [
                {"branch": "main", "worktree": {"path": str(self.primary)}},
                {
                    "branch": "writer/claude",
                    "worktree": {"path": str(self.claude)},
                    "vars": {
                        "actor": "claude-actor",
                        "lease": "claude-lease",
                        "context": "claude-agent-1",
                        "bead": "demo-1",
                    },
                },
                {
                    "branch": "writer/codex",
                    "worktree": {"path": str(self.codex)},
                    "vars": {
                        "actor": "codex-actor",
                        "lease": "codex-lease",
                        "context": "codex-agent-2",
                        "bead": "demo-2",
                    },
                },
                {
                    "branch": "review/security-reviewer-3",
                    "worktree": {"path": str(self.reviewer)},
                    "vars": {
                        "actor": "reviewer-actor",
                        "lease": "reviewer-lease",
                        "context": "reviewer-agent-3",
                    },
                },
            ],
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_primary_human_checkout_is_outside_writer_contract(self) -> None:
        self.assertIsNone(MODULE.assert_runtime_lease({}, self.inventory, self.primary))

    def test_claude_writer_is_denied_in_primary_checkout(self) -> None:
        with self.assertRaises(MODULE.ContractError):
            MODULE.assert_runtime_lease(
                {"agent_id": "claude-agent-1"}, self.inventory, self.primary
            )

    def test_unbound_harness_subagent_is_denied_in_primary_checkout(self) -> None:
        with self.assertRaises(MODULE.ContractError):
            MODULE.assert_runtime_lease(
                {"agent_id": "unbound-agent"}, self.inventory, self.primary
            )

    def test_unbound_readonly_reviewer_bash_is_denied(self) -> None:
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "agent_id": "unbound-reviewer",
                "cwd": str(self.primary),
                "tool_input": {"workdir": str(self.primary), "command": "git status"},
            }
        )
        self.assertEqual(
            json.loads(output)["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_bound_readonly_reviewer_can_inspect_own_worktree(self) -> None:
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "agent_id": "reviewer-agent-3",
                "cwd": str(self.primary),
                "tool_input": {"workdir": str(self.reviewer), "command": "git status"},
            }
        )
        self.assertEqual(output, "")

    def test_claude_writer_matches_bound_leased_checkout(self) -> None:
        item = MODULE.assert_runtime_lease(
            {"agent_id": "claude-agent-1"}, self.inventory, self.claude
        )
        self.assertEqual(item["branch"], "writer/claude")

    def test_codex_writer_matches_bound_leased_checkout(self) -> None:
        item = MODULE.assert_runtime_lease(
            {"subagent_id": "codex-agent-2"}, self.inventory, self.codex
        )
        self.assertEqual(item["branch"], "writer/codex")

    def test_external_writer_actor_mismatch_is_denied(self) -> None:
        with self.assertRaises(MODULE.ContractError):
            MODULE.assert_runtime_lease(
                {},
                self.inventory,
                self.claude,
                expected_lease="claude-lease",
                expected_actor="wrong-actor",
            )

    def test_unbound_writer_worktree_is_denied(self) -> None:
        self.inventory["items"][1]["vars"].pop("context")
        with self.assertRaises(MODULE.ContractError):
            MODULE.assert_runtime_lease(
                {"agent_id": "claude-agent-1"}, self.inventory, self.claude
            )

    def invoke_hook(self, payload: dict, env: dict[str, str] | None = None) -> str:
        stdout = io.StringIO()
        completed = subprocess.CompletedProcess([], 0, "", "")
        with (
            patch.object(MODULE, "wt_inventory", return_value=self.inventory),
            patch.object(MODULE.shutil, "which", return_value="/usr/bin/wt"),
            patch.object(MODULE.subprocess, "run", return_value=completed),
            patch.object(sys, "stdin", io.StringIO(json.dumps(payload))),
            patch.object(sys, "stdout", stdout),
            patch.dict(os.environ, env or {}, clear=True),
        ):
            self.assertEqual(MODULE.hook(), 0)
        return stdout.getvalue()

    def test_claude_edit_payload_allows_bound_checkout(self) -> None:
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Edit",
                "agent_id": "claude-agent-1",
                "cwd": str(self.primary),
                "tool_input": {"file_path": str(self.claude / "src.py")},
            }
        )
        self.assertEqual(output, "")

    def test_codex_apply_patch_payload_denies_wrong_checkout(self) -> None:
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "apply_patch",
                "agent_id": "codex-agent-2",
                "cwd": str(self.primary),
                "tool_input": {
                    "command": f"*** Begin Patch\n*** Update File: {self.primary / 'src.rs'}\n"
                },
            }
        )
        self.assertEqual(
            json.loads(output)["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_codex_apply_patch_payload_allows_bound_checkout(self) -> None:
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "apply_patch",
                "agent_id": "codex-agent-2",
                "cwd": str(self.primary),
                "tool_input": {
                    "command": f"*** Begin Patch\n*** Update File: {self.codex / 'src.rs'}\n"
                },
            }
        )
        self.assertEqual(output, "")

    def test_claude_multiedit_denies_any_target_outside_bound_checkout(self) -> None:
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "MultiEdit",
                "agent_id": "claude-agent-1",
                "cwd": str(self.claude),
                "tool_input": {
                    "edits": [
                        {"file_path": str(self.claude / "inside.py")},
                        {"file_path": str(self.primary / "outside.py")},
                    ]
                },
            }
        )
        self.assertEqual(
            json.loads(output)["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_primary_human_apply_patch_payload_is_silent(self) -> None:
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "apply_patch",
                "session_id": "human-session",
                "cwd": str(self.primary),
                "tool_input": {
                    "command": f"*** Begin Patch\n*** Update File: {self.primary / 'src.rs'}\n"
                },
            }
        )
        self.assertEqual(output, "")

    def test_external_bash_payload_denies_actor_mismatch(self) -> None:
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "cwd": str(self.claude),
                "tool_input": {"workdir": str(self.claude), "command": "touch x"},
            },
            {
                "WORKTRUNK_WRITER_LEASE": "claude-lease",
                "WORKTRUNK_WRITER_ACTOR": "wrong-actor",
            },
        )
        self.assertEqual(
            json.loads(output)["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_external_bash_payload_denies_missing_actor(self) -> None:
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "cwd": str(self.claude),
                "tool_input": {"workdir": str(self.claude), "command": "touch x"},
            },
            {"WORKTRUNK_WRITER_LEASE": "claude-lease"},
        )
        self.assertEqual(
            json.loads(output)["hookSpecificOutput"]["permissionDecision"], "deny"
        )


class HookManifestTests(unittest.TestCase):
    def test_runtime_manifests_route_native_tool_names(self) -> None:
        hooks = SCRIPT.parents[3] / "hooks"
        claude = json.loads((hooks / "worktrunk-writer-claude-hooks.json").read_text())
        codex = json.loads((hooks / "worktrunk-writer-codex-hooks.json").read_text())
        claude_matcher = claude["hooks"]["PreToolUse"][0]["matcher"]
        codex_matcher = codex["hooks"]["PreToolUse"][0]["matcher"]
        self.assertIn("Edit", claude_matcher)
        self.assertNotIn("apply_patch", claude_matcher)
        self.assertIn("apply_patch", codex_matcher)


class BeadsLeaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = Path("/tmp/writer-a")
        self.issue = {
            "id": "demo-1",
            "status": "in_progress",
            "assignee": "writer-actor",
            "metadata": {},
        }
        self.inventory = {"schema": 2, "items": []}
        self.original_one = MODULE.one_bead
        self.original_conflicts = MODULE.active_bead_conflicts
        MODULE.one_bead = lambda *_args, **_kwargs: self.issue
        MODULE.active_bead_conflicts = lambda *_args, **_kwargs: []

    def tearDown(self) -> None:
        MODULE.one_bead = self.original_one
        MODULE.active_bead_conflicts = self.original_conflicts

    def assert_available(self) -> None:
        MODULE.assert_bead_lease_available(
            Path("/tmp"),
            "demo-1",
            "writer-actor",
            "writer/a",
            "lease-a",
            self.inventory,
            self.path,
        )

    def test_active_claimed_bead_is_available(self) -> None:
        self.assert_available()

    def test_closed_bead_is_rejected(self) -> None:
        self.issue["status"] = "closed"
        with self.assertRaises(MODULE.ContractError):
            self.assert_available()

    def test_actor_claim_mismatch_is_rejected(self) -> None:
        self.issue["assignee"] = "other-actor"
        with self.assertRaises(MODULE.ContractError):
            self.assert_available()

    def test_same_bead_on_another_worktree_is_rejected(self) -> None:
        self.inventory["items"].append(
            {
                "branch": "writer/other",
                "worktree": {"path": "/tmp/writer-other"},
                "vars": {"bead": "demo-1", "lease": "other-lease"},
            }
        )
        with self.assertRaises(MODULE.ContractError):
            self.assert_available()


if __name__ == "__main__":
    unittest.main()
