#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("worktrunk-writer.py")
HANDSHAKE = Path(__file__).with_name("context-handshake.py")
SPEC = importlib.util.spec_from_file_location("worktrunk_writer", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


STATE_HOME = tempfile.TemporaryDirectory()


def setUpModule() -> None:
    """Point the whole suite at a throwaway XDG state home.

    `context_index_path()` falls back to `Path.home()`, so any test that binds or
    reads the binding index writes the developer's real
    `~/.local/state/worktrunk-writer/contexts.json` when this is unset.
    """
    os.environ["XDG_STATE_HOME"] = STATE_HOME.name


def tearDownModule() -> None:
    STATE_HOME.cleanup()


def cleared_env(**overrides: str):
    """Reduce the environment to `overrides`, keeping the suite's state home.

    Clearing proves the guard works with no writer variables set; XDG_STATE_HOME
    has to survive that so a cleared environment cannot reach the real index.
    """
    return patch.dict(
        os.environ,
        {"XDG_STATE_HOME": os.environ["XDG_STATE_HOME"], **overrides},
        clear=True,
    )


def clear_binding_index() -> None:
    MODULE.context_index_path().unlink(missing_ok=True)


def hook_manifest_root() -> Path:
    """Locate package hook manifests in source and installed skill layouts."""
    candidates = [SCRIPT.parents[3] / "hooks"]
    for root in (Path.cwd(), *Path.cwd().parents):
        modules = root / "apm_modules"
        if not modules.is_dir():
            continue
        candidates.extend(modules.glob("*/hooks"))
        candidates.extend(modules.glob("*/*/hooks"))
        candidates.extend(modules.glob("**/hooks"))
    for candidate in candidates:
        if all((candidate / name).is_file() for name in (
            "worktrunk-writer-claude-hooks.json",
            "worktrunk-writer-codex-hooks.json",
        )):
            return candidate
    raise FileNotFoundError("worktrunk-writer hook manifests are not installed")


class InventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.payload = [
            {
                "branch": "agent/task",
                "path": str(self.root),
                "kind": "worktree",
                "vars": {
                    "actor": "codex-writer-a1",
                    "lease": "lease-a1",
                    "bead": "demo-1",
                },
            }
        ]

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
        self.assertEqual(MODULE.containing_item(self.payload, nested)["branch"], "agent/task")

    def test_containing_item_rejects_a_different_checkout(self) -> None:
        self.assertIsNone(MODULE.containing_item(self.payload, Path("/var/tmp/other")))

    def test_copy_result_distinguishes_noop(self) -> None:
        self.assertEqual(MODULE.copy_result(json.dumps({"copied": 0})), "noop")
        self.assertEqual(MODULE.copy_result(json.dumps({"copied": 3})), "done")

    def test_bound_resource_uses_explicit_resource_not_node_label(self) -> None:
        item = {"vars": {"resource": "demo-1", "node": "t1"}}
        self.assertEqual(MODULE.bound_resource(item), "demo-1")

    def test_runtime_bindings_read_worktrunk_safe_key(self) -> None:
        item = {
            "vars": {
                "runtime-bindings": json.dumps(
                    [{"handle": "routing-handle", "context": "hook-context"}]
                )
            }
        }
        self.assertEqual(
            MODULE.runtime_bindings(item),
            [{"handle": "routing-handle", "context": "hook-context"}],
        )

    def test_set_var_rejects_worktrunk_invalid_key_before_execution(self) -> None:
        with (
            patch.object(MODULE, "run") as command,
            self.assertRaisesRegex(MODULE.ContractError, "letters, digits, and hyphens"),
        ):
            MODULE.set_var(Path("/tmp/repo"), "writer/a", "runtime_bindings", "[]")
        command.assert_not_called()

    def test_set_var_accepts_worktrunk_safe_key(self) -> None:
        with patch.object(MODULE, "run") as command:
            MODULE.set_var(Path("/tmp/repo"), "writer/a", "runtime-bindings", "[]")
        self.assertIn(
            "runtime-bindings=[]",
            command.call_args.args[0],
        )


class ContextHandshakeTests(unittest.TestCase):
    def invoke(self, payload: dict, env: dict[str, str] | None = None) -> dict:
        # PATH="" hides `wt`, so an unset WORKTRUNK_WRITER_ENFORCE reads as "no
        # protocol" regardless of whatever real repository the test runs inside.
        process_env = {"PATH": "", **(env or {})}
        process = subprocess.run(
            [sys.executable, str(HANDSHAKE)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
            env=process_env,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout or "{}")

    def test_engaged_agent_id_is_exposed_without_a_tool_call(self) -> None:
        output = self.invoke(
            {"agent_id": "aresearcher-r1-cb8a2c084ff1c7fa"},
            env={"WORKTRUNK_WRITER_ENFORCE": "1"},
        )
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn(
            "WAIT context=aresearcher-r1-cb8a2c084ff1c7fa",
            context,
        )
        self.assertIn("without invoking any tool", context)
        self.assertIn("completion notification", context)
        self.assertIn("not the spawn handle", context)

    def test_engaged_subagent_id_is_supported(self) -> None:
        output = self.invoke(
            {"subagent_id": "438444453a695885"},
            env={"WORKTRUNK_WRITER_ENFORCE": "1"},
        )
        self.assertIn(
            "WAIT context=438444453a695885",
            output["hookSpecificOutput"]["additionalContext"],
        )

    def test_missing_runtime_context_is_silent(self) -> None:
        self.assertEqual(
            self.invoke({"session_id": "parent"}, env={"WORKTRUNK_WRITER_ENFORCE": "1"}),
            {},
        )

    def test_spawn_outside_the_protocol_gets_no_wait_demand(self) -> None:
        """The reported stall: a plain spawn with no lease got a bare WAIT.

        With no operator opt-in and no reachable `wt` lease, the handshake must
        stay silent so an ordinary delegated child never believes it owes a WAIT
        reply it has no lease to bind to.
        """
        self.assertEqual(self.invoke({"agent_id": "aresearcher-r1-cb8a2c084ff1c7fa"}), {})


class HandshakeEngagementTests(unittest.TestCase):
    """protocol_engaged decides WAIT injection purely from observable evidence."""

    def setUp(self) -> None:
        spec = importlib.util.spec_from_file_location("context_handshake", HANDSHAKE)
        assert spec and spec.loader
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_operator_opt_in_engages_without_a_lease(self) -> None:
        with cleared_env(WORKTRUNK_WRITER_ENFORCE="1"):
            self.assertTrue(self.mod.protocol_engaged({}))

    def test_external_writer_env_engages(self) -> None:
        with cleared_env(WORKTRUNK_WRITER_LEASE="l"):
            self.assertTrue(self.mod.protocol_engaged({}))

    def test_absent_wt_reads_as_no_protocol(self) -> None:
        with (
            cleared_env(),
            patch.object(self.mod.shutil, "which", return_value=None),
        ):
            self.assertFalse(self.mod.protocol_engaged({"cwd": "/tmp"}))

    def test_a_repository_holding_a_lease_engages(self) -> None:
        inventory = [{"branch": "w/a", "path": "/tmp/w-a", "vars": {"actor": "a", "lease": "l"}}]
        with (
            cleared_env(),
            patch.object(self.mod.shutil, "which", return_value="/usr/bin/wt"),
            patch.object(self.mod, "_writer") as loader,
        ):
            loader.return_value.wt_inventory.return_value = inventory
            loader.return_value.repo_has_leases.return_value = True
            self.assertTrue(self.mod.protocol_engaged({"cwd": "/tmp"}))

    def test_a_repository_with_no_lease_does_not_engage(self) -> None:
        with (
            cleared_env(),
            patch.object(self.mod.shutil, "which", return_value="/usr/bin/wt"),
            patch.object(self.mod, "_writer") as loader,
        ):
            loader.return_value.wt_inventory.return_value = [{"branch": "main", "path": "/tmp"}]
            loader.return_value.repo_has_leases.return_value = False
            self.assertFalse(self.mod.protocol_engaged({"cwd": "/tmp"}))

    def test_an_inventory_error_fails_toward_no_protocol(self) -> None:
        with (
            cleared_env(),
            patch.object(self.mod.shutil, "which", return_value="/usr/bin/wt"),
            patch.object(self.mod, "_writer") as loader,
        ):
            loader.return_value.wt_inventory.side_effect = RuntimeError("no wt")
            self.assertFalse(self.mod.protocol_engaged({"cwd": "/tmp"}))


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

    def _conflicts(self, issues: list[dict[str, object]], path: str = "/tmp/wt") -> list[str]:
        original = MODULE.beads_json
        MODULE.beads_json = lambda *_args, **_kwargs: issues
        try:
            return MODULE.active_bead_conflicts(
                Path("/tmp"), "active-1", "agent/task", Path(path)
            )
        finally:
            MODULE.beads_json = original

    def test_tracking_merge_bead_sharing_branch_is_not_a_conflict(self) -> None:
        # A merge bead names the implementer's branch by design and holds no
        # checkout. Treating it as a competing writer denied the implementer its
        # own lease and blocked all work on the PR.
        self.assertEqual(
            self._conflicts(
                [
                    {
                        "id": "merge-1",
                        "status": "open",
                        "metadata": {
                            "branch": "agent/task",
                            "head": "agent/task",
                            "pr": 1623,
                            "tracks_beads": ["active-1"],
                            "closes_beads": ["active-1"],
                        },
                    }
                ]
            ),
            [],
        )

    def test_closes_beads_scalar_also_exempts(self) -> None:
        self.assertEqual(
            self._conflicts(
                [
                    {
                        "id": "merge-1",
                        "status": "open",
                        "metadata": {"branch": "agent/task", "closes_beads": "active-1"},
                    }
                ]
            ),
            [],
        )

    def test_json_encoded_list_also_exempts(self) -> None:
        # `bd --set-metadata tracks_beads='["active-1"]'` stores the value as a
        # string, so the list arrives JSON-encoded rather than as a real list. The
        # sibling cases above pass real lists, which no `bd` invocation produces.
        self.assertEqual(
            self._conflicts(
                [
                    {
                        "id": "merge-1",
                        "status": "open",
                        "metadata": {
                            "branch": "agent/task",
                            "tracks_beads": '["active-1"]',
                            "closes_beads": '["active-1"]',
                        },
                    }
                ]
            ),
            [],
        )

    def test_json_encoded_list_naming_another_bead_still_conflicts(self) -> None:
        self.assertEqual(
            self._conflicts(
                [
                    {
                        "id": "merge-2",
                        "status": "open",
                        "metadata": {"branch": "agent/task", "tracks_beads": '["other-9"]'},
                    }
                ]
            ),
            ["merge-2"],
        )

    def test_unparsable_string_is_not_an_exemption(self) -> None:
        self.assertEqual(
            self._conflicts(
                [
                    {
                        "id": "merge-4",
                        "status": "open",
                        "metadata": {"branch": "agent/task", "tracks_beads": "[not json"},
                    }
                ]
            ),
            ["merge-4"],
        )

    def test_merge_bead_tracking_a_different_bead_still_conflicts(self) -> None:
        # The exemption is per-bead, not a blanket pass for anything with a
        # tracks_beads key: this one claims our branch while tracking someone else.
        self.assertEqual(
            self._conflicts(
                [
                    {
                        "id": "merge-2",
                        "status": "open",
                        "metadata": {"branch": "agent/task", "tracks_beads": ["other-9"]},
                    }
                ]
            ),
            ["merge-2"],
        )

    def test_tracking_bead_sharing_the_checkout_still_conflicts(self) -> None:
        # Two actors in one checkout is a real conflict regardless of tracking.
        self.assertEqual(
            self._conflicts(
                [
                    {
                        "id": "merge-3",
                        "status": "open",
                        "metadata": {
                            "branch": "agent/task",
                            "worktree_path": "/tmp/wt",
                            "tracks_beads": ["active-1"],
                        },
                    }
                ]
            ),
            ["merge-3"],
        )


class RuntimeHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name).resolve()
        self.primary = root / "primary"
        self.claude = root / "claude"
        self.codex = root / "codex"
        self.reviewer = root / "reviewer"
        self.artifacts = root / "run" / "artifacts"
        self.outside = root / "outside"
        self.primary.mkdir()
        self.claude.mkdir()
        self.codex.mkdir()
        self.reviewer.mkdir()
        self.artifacts.mkdir(parents=True)
        self.outside.mkdir()
        self.inventory = [
            {"branch": "main", "path": str(self.primary), "kind": "worktree"},
            {
                "branch": "writer/claude",
                "path": str(self.claude),
                "kind": "worktree",
                "vars": {
                    "actor": "claude-actor",
                    "lease": "claude-lease",
                    "context": "claude-agent-1",
                    "runtime-bindings": json.dumps(
                        [
                            {
                                "handle": "researcher-r1@session-b807e068",
                                "context": "claude-agent-1",
                            }
                        ]
                    ),
                    "resource": "demo-1",
                },
            },
            {
                "branch": "writer/codex",
                "path": str(self.codex),
                "kind": "worktree",
                "vars": {
                    "actor": "codex-actor",
                    "lease": "codex-lease",
                    "context": "codex-agent-2",
                    "runtime-bindings": json.dumps(
                        [
                            {
                                "handle": "codex-agent-2",
                                "context": "codex-agent-2",
                            }
                        ]
                    ),
                    "resource": "demo-2",
                },
            },
            {
                "branch": "review/security-reviewer-3",
                "path": str(self.reviewer),
                "kind": "worktree",
                "vars": {
                    "actor": "reviewer-actor",
                    "lease": "reviewer-lease",
                    "context": "reviewer-agent-3",
                },
            },
        ]
        self.artifact_issue = {
            "id": "demo-1",
            "status": "in_progress",
            "assignee": "claude-actor",
            "metadata": {
                "actor": "claude-actor",
                "branch": "writer/claude",
                "lease_token": "claude-lease",
                "worktree": str(self.claude),
                "execution_kind": "artifact",
                "artifacts_dir": str(self.artifacts),
            },
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

    def test_denial_names_the_target_and_the_leased_path(self) -> None:
        # The old message said only "targets an unleased checkout", which reads as
        # a broken lease. The real cause is a Bash call that never ran
        # `cd -- <leased-path>`, so the message has to name both paths and the fix.
        with self.assertRaises(MODULE.ContractError) as caught:
            MODULE.assert_runtime_lease(
                {"agent_id": "claude-agent-1"}, self.inventory, self.primary
            )
        message = str(caught.exception)
        self.assertIn(str(self.primary), message)
        self.assertIn(str(self.claude), message)
        self.assertIn("cd -- <leased-path>", message)

    def test_unbound_harness_subagent_is_denied_in_primary_checkout(self) -> None:
        with self.assertRaises(MODULE.ContractError):
            MODULE.assert_runtime_lease({"agent_id": "unbound-agent"}, self.inventory, self.primary)

    def test_unbound_readonly_reviewer_bash_is_denied(self) -> None:
        output = self.invoke_engaged_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "agent_id": "unbound-reviewer",
                "cwd": str(self.primary),
                "tool_input": {"workdir": str(self.primary), "command": "git status"},
            }
        )
        self.assertEqual(json.loads(output)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_parent_cannot_spawn_task_bearing_agent_before_lease_handshake(self) -> None:
        output = self.invoke_engaged_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Agent",
                "cwd": str(self.primary),
                "tool_input": {
                    "subagent_type": "researcher",
                    "prompt": "Inspect the repository and report the result.",
                },
            }
        )
        decision = json.loads(output)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("worktrunk-writer", decision["permissionDecisionReason"])
        self.assertIn("parent", decision["permissionDecisionReason"])
        self.assertIn("child cannot establish its own lease", decision["permissionDecisionReason"])

    def test_wrong_cwd_cannot_claim_another_lease(self) -> None:
        """A drifted cwd must not let one lease holder act inside another lease.

        Guards the reported failure where a lead whose cwd was wrong claimed
        the wrong lease.
        """
        for label, tool_input in (
            ("cross-lease write", {"file_path": str(self.codex / "x.py")}),
            ("bare bash with inherited cwd", {"command": "echo hi"}),
            ("leading cd into the wrong lease", {"command": f"cd -- {self.codex} && echo hi"}),
        ):
            with self.subTest(label):
                decision = json.loads(
                    self.invoke_hook(
                        {
                            "hook_event_name": "PreToolUse",
                            "tool_name": "Bash" if "command" in tool_input else "Write",
                            "agent_id": "claude-agent-1",
                            "cwd": str(self.codex),
                            "tool_input": tool_input,
                        }
                    )
                )
                self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_a_lease_holder_still_reaches_its_own_checkout_from_a_wrong_cwd(self) -> None:
        self.assertEqual(
            self.invoke_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Write",
                    "agent_id": "claude-agent-1",
                    "cwd": str(self.codex),
                    "tool_input": {"file_path": str(self.claude / "x.py")},
                }
            ),
            "",
        )

    def test_standalone_wait_spawn_engages_without_orchestration(self) -> None:
        """Worktrunk delegation must work outside orchestrate.

        The WAIT grammar is itself protocol evidence, so a standalone parent
        gets the contract enforced with no orchestration run present.
        """
        wait = (
            f"WAIT checkout={self.claude}\n"
            "Do not invoke tools or start work.\n"
            "The controlling parent will send your task after binding "
            "your Worktrunk lease."
        )
        self.assertEqual(
            self.invoke_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Agent",
                    "cwd": str(self.primary),
                    "tool_input": {"subagent_type": "coder", "prompt": wait},
                }
            ),
            "",
        )
        decision = json.loads(
            self.invoke_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Agent",
                    "cwd": str(self.primary),
                    "tool_input": {
                        "subagent_type": "coder",
                        "prompt": wait.replace(str(self.claude), str(self.outside)),
                    },
                }
            )
        )
        self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_parent_can_spawn_generic_wait_in_a_prepared_checkout(self) -> None:
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Agent",
                "cwd": str(self.primary),
                "tool_input": {
                    "subagent_type": "researcher",
                    "prompt": (
                        f"WAIT checkout={self.claude}\n"
                        "Do not invoke tools or start work.\n"
                        "The controlling parent will send your task after binding "
                        "your Worktrunk lease."
                    ),
                },
            }
        )
        self.assertEqual(output, "")

    def test_parent_cannot_allocate_an_unknown_checkout(self) -> None:
        output = self.invoke_engaged_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Agent",
                "cwd": str(self.primary),
                "tool_input": {
                    "subagent_type": "researcher",
                    "prompt": (
                        f"WAIT checkout={self.outside}\n"
                        "Do not invoke tools or start work.\n"
                        "The controlling parent will send your task after binding "
                        "your Worktrunk lease."
                    ),
                },
            }
        )
        self.assertEqual(
            json.loads(output)["hookSpecificOutput"]["permissionDecision"],
            "deny",
        )

    def test_parent_can_resume_a_bound_handle_with_the_actual_task(self) -> None:
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Agent",
                "cwd": str(self.primary),
                "tool_input": {
                    "resume": "researcher-r1@session-b807e068",
                    "prompt": "Inspect the repository and report the result.",
                },
            }
        )
        self.assertEqual(output, "")

    def test_parent_cannot_resume_an_unbound_handle(self) -> None:
        output = self.invoke_engaged_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Agent",
                "cwd": str(self.primary),
                "tool_input": {
                    "resume": "researcher-unbound@session-b807e068",
                    "prompt": "Inspect the repository and report the result.",
                },
            }
        )
        self.assertEqual(
            json.loads(output)["hookSpecificOutput"]["permissionDecision"],
            "deny",
        )

    def test_codex_followup_task_requires_a_bound_handle(self) -> None:
        output = self.invoke_engaged_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "followup_task",
                "cwd": str(self.primary),
                "tool_input": {
                    "target": "codex-agent-2",
                    "message": "Inspect the repository and report the result.",
                },
            }
        )
        self.assertEqual(output, "")

        output = self.invoke_engaged_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "followup_task",
                "cwd": str(self.primary),
                "tool_input": {
                    "target": "codex-agent-unbound",
                    "message": "Inspect the repository and report the result.",
                },
            }
        )
        self.assertEqual(
            json.loads(output)["hookSpecificOutput"]["permissionDecision"],
            "deny",
        )

    def test_codex_legacy_send_input_requires_a_bound_handle(self) -> None:
        output = self.invoke_engaged_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "send_input",
                "cwd": str(self.primary),
                "tool_input": {
                    "id": "codex-agent-2",
                    "message": "Inspect the repository and report the result.",
                },
            }
        )
        self.assertEqual(output, "")

        output = self.invoke_engaged_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "send_input",
                "cwd": str(self.primary),
                "tool_input": {
                    "id": "codex-agent-unbound",
                    "message": "Inspect the repository and report the result.",
                },
            }
        )
        self.assertEqual(
            json.loads(output)["hookSpecificOutput"]["permissionDecision"],
            "deny",
        )

    def test_codex_v1_namespaced_continuations_require_a_bound_handle(self) -> None:
        cases = (
            ("multi_agent_v1send_input", {"target": "codex-agent-2", "message": "Inspect."}),
            ("multi_agent_v1resume_agent", {"id": "codex-agent-2"}),
        )
        for tool_name, tool_input in cases:
            with self.subTest(tool_name=tool_name):
                output = self.invoke_engaged_hook(
                    {
                        "hook_event_name": "PreToolUse",
                        "tool_name": tool_name,
                        "cwd": str(self.primary),
                        "tool_input": tool_input,
                    }
                )
                self.assertEqual(output, "")

                unbound_input = dict(tool_input)
                key = "target" if "target" in unbound_input else "id"
                unbound_input[key] = "codex-agent-unbound"
                output = self.invoke_engaged_hook(
                    {
                        "hook_event_name": "PreToolUse",
                        "tool_name": tool_name,
                        "cwd": str(self.primary),
                        "tool_input": unbound_input,
                    }
                )
                self.assertEqual(
                    json.loads(output)["hookSpecificOutput"]["permissionDecision"],
                    "deny",
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

    def test_bound_claude_agent_can_enter_its_checkout_with_leading_cd(self) -> None:
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "agent_id": "claude-agent-1",
                "cwd": str(self.primary),
                "tool_input": {"command": f"cd -- {shlex.quote(str(self.claude))}\nbd show demo-1"},
            }
        )
        self.assertEqual(output, "")

    def test_live_claude_leading_cd_shape_uses_the_leased_checkout(self) -> None:
        command = f"cd {shlex.quote(str(self.claude))} && pwd"
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "agent_id": "claude-agent-1",
                "cwd": str(self.primary),
                "tool_input": {"command": command},
            }
        )
        self.assertEqual(output, "")

    def test_bound_claude_agent_cannot_enter_an_unleased_checkout(self) -> None:
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "agent_id": "claude-agent-1",
                "cwd": str(self.primary),
                "tool_input": {"command": f"cd -- {shlex.quote(str(self.primary))} && git status"},
            }
        )
        self.assertEqual(json.loads(output)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_bound_claude_agent_without_checkout_cd_is_denied(self) -> None:
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "agent_id": "claude-agent-1",
                "cwd": str(self.primary),
                "tool_input": {"command": "git status"},
            }
        )
        self.assertEqual(json.loads(output)["hookSpecificOutput"]["permissionDecision"], "deny")

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

    def test_explicitly_bound_child_shares_parent_worktree(self) -> None:
        self.inventory[1]["vars"]["contexts"] = json.dumps(["claude-agent-1", "claude-child-1"])
        item = MODULE.assert_runtime_lease(
            {"agent_id": "claude-child-1"}, self.inventory, self.claude
        )
        self.assertEqual(item["branch"], "writer/claude")

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
        self.inventory[1]["vars"].pop("context")
        self.inventory[1]["vars"].pop("runtime-bindings")
        with self.assertRaises(MODULE.ContractError):
            MODULE.assert_runtime_lease({"agent_id": "claude-agent-1"}, self.inventory, self.claude)

    def invoke_engaged_hook(self, payload: dict, env: dict[str, str] | None = None) -> str:
        """Invoke the hook with the writer protocol explicitly engaged.

        The hook is repository-global and stays inert for ordinary delegation,
        so an enforcement scenario must opt in the way a protocol owner does.
        """
        return self.invoke_hook(payload, {"WORKTRUNK_WRITER_ENFORCE": "1", **(env or {})})

    def invoke_hook(self, payload: dict, env: dict[str, str] | None = None) -> str:
        stdout = io.StringIO()
        completed = subprocess.CompletedProcess([], 0, "", "")
        with (
            patch.object(MODULE, "wt_inventory", return_value=self.inventory),
            patch.object(MODULE, "one_bead", return_value=self.artifact_issue),
            patch.object(MODULE.shutil, "which", return_value="/usr/bin/wt"),
            patch.object(MODULE.subprocess, "run", return_value=completed),
            patch.object(sys, "stdin", io.StringIO(json.dumps(payload))),
            patch.object(sys, "stdout", stdout),
            cleared_env(**(env or {})),
        ):
            self.assertEqual(MODULE.hook(), 0)
        return stdout.getvalue()

    def test_ordinary_subagent_bash_outside_a_lease_is_untouched(self) -> None:
        """An unrelated subagent must not be blocked by a repository's leases."""
        self.assertEqual(
            self.invoke_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                    "agent_id": "unrelated-subagent",
                    "cwd": str(self.primary),
                    "tool_input": {"command": "echo hi"},
                }
            ),
            "",
        )

    def test_ordinary_agent_spawn_is_advised_not_denied(self) -> None:
        """An unleased task-bearing spawn proceeds, carrying guidance.

        Never a deny: a PreToolUse hook sees only free-form `subagent_type`
        and prompt text, so it cannot tell a read-only child from a writing
        one. Guessing is what got the hooks-subagent-worktree deny gate
        reverted in 3bb87228. Steering is only a pointer the parent may not
        follow, so this advisory is the one mechanical cue a parent outside
        the protocol still receives.
        """
        decision = json.loads(
            self.invoke_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Agent",
                    "cwd": str(self.primary),
                    "tool_input": {
                        "subagent_type": "general-purpose",
                        "prompt": "Summarize the release notes.",
                    },
                }
            )
        )["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", decision)
        self.assertIn("worktrunk-writer", decision["additionalContext"])
        self.assertIn("PREPARE", decision["additionalContext"])

    def test_advisory_skips_calls_that_need_no_lease(self) -> None:
        for label, tool, tool_input in (
            ("resume by handle", "Agent", {"resume": "h1", "prompt": "continue"}),
            ("continuation", "SendMessage", {"to": "a", "message": "go"}),
            ("empty prompt", "Agent", {"subagent_type": "coder", "prompt": ""}),
        ):
            with self.subTest(label):
                self.assertEqual(
                    self.invoke_hook(
                        {
                            "hook_event_name": "PreToolUse",
                            "tool_name": tool,
                            "cwd": str(self.primary),
                            "tool_input": tool_input,
                        }
                    ),
                    "",
                )

    def test_ordinary_continuation_outside_the_protocol_is_untouched(self) -> None:
        self.assertEqual(
            self.invoke_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "SendMessage",
                    "cwd": str(self.primary),
                    "tool_input": {"to": "unrelated-agent", "message": "continue"},
                }
            ),
            "",
        )

    def test_ordinary_edit_outside_a_lease_is_untouched(self) -> None:
        self.assertEqual(
            self.invoke_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Edit",
                    "agent_id": "unrelated-subagent",
                    "cwd": str(self.primary),
                    "tool_input": {"file_path": str(self.primary / "README.md")},
                }
            ),
            "",
        )

    def test_bound_notebook_write_outside_the_lease_is_denied(self) -> None:
        """NotebookEdit names its target `notebook_path`, not `file_path`.

        Reading only `file_path` made the target fall back to `cwd`, so a bound
        writer's notebook write to any path at all validated the leased cwd and
        passed.
        """
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "NotebookEdit",
                "agent_id": "claude-agent-1",
                "cwd": str(self.claude),
                "tool_input": {"notebook_path": str(self.outside / "escape.ipynb")},
            }
        )
        self.assertEqual(json.loads(output)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_bound_notebook_write_inside_the_lease_is_allowed(self) -> None:
        self.assertEqual(
            self.invoke_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "NotebookEdit",
                    "agent_id": "claude-agent-1",
                    "cwd": str(self.claude),
                    "tool_input": {"notebook_path": str(self.claude / "analysis.ipynb")},
                }
            ),
            "",
        )

    def test_an_active_orchestration_run_engages_enforcement(self) -> None:
        marker = self.primary / ".orchestration" / ".active-run"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"run_id": "orc-run-1"}), encoding="utf-8")
        decision = json.loads(
            self.invoke_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Agent",
                    "cwd": str(self.primary),
                    "tool_input": {
                        "subagent_type": "researcher",
                        "prompt": "Inspect the repository and report the result.",
                    },
                },
                {"ORCHESTRATE_MARKER_FILE": str(marker)},
            )
        )
        self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_a_caller_inside_a_leased_checkout_engages_enforcement(self) -> None:
        decision = json.loads(
            self.invoke_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                    "agent_id": "unbound-agent",
                    "cwd": str(self.claude),
                    "tool_input": {"command": "echo hi", "workdir": str(self.primary)},
                }
            )
        )
        self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")

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

    def test_bound_artifact_actor_can_write_inside_stamped_artifacts_dir(self) -> None:
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "agent_id": "claude-agent-1",
                "cwd": str(self.primary),
                "tool_input": {"file_path": str(self.artifacts / "result.json")},
            }
        )
        self.assertEqual(output, "")

    def test_bound_artifact_actor_accepts_legacy_bead_resource_alias(self) -> None:
        self.inventory[1]["vars"]["bead"] = self.inventory[1]["vars"].pop("resource")
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "agent_id": "claude-agent-1",
                "cwd": str(self.primary),
                "tool_input": {"file_path": str(self.artifacts / "result.json")},
            }
        )
        self.assertEqual(output, "")

    def test_bound_artifact_actor_cannot_write_outside_stamped_artifacts_dir(self) -> None:
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "agent_id": "claude-agent-1",
                "cwd": str(self.primary),
                "tool_input": {"file_path": str(self.outside / "result.json")},
            }
        )
        self.assertEqual(
            json.loads(output)["hookSpecificOutput"]["permissionDecision"],
            "deny",
        )

    def test_bound_artifact_actor_bash_redirection_can_target_artifacts_dir(self) -> None:
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "agent_id": "claude-agent-1",
                "cwd": str(self.primary),
                "tool_input": {
                    "command": (
                        f"cd -- {shlex.quote(str(self.claude))} && "
                        f"cat > {shlex.quote(str(self.artifacts / 'result.json'))} <<'JSON'\n"
                        "{}\n"
                        "JSON"
                    )
                },
            }
        )
        self.assertEqual(output, "")

    def test_bound_artifact_actor_bash_redirection_cannot_escape_artifacts_dir(self) -> None:
        output = self.invoke_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "agent_id": "claude-agent-1",
                "cwd": str(self.primary),
                "tool_input": {
                    "command": (
                        f"cd -- {shlex.quote(str(self.claude))} && "
                        f"cat > {shlex.quote(str(self.outside / 'result.json'))} <<'JSON'\n"
                        "{}\n"
                        "JSON"
                    )
                },
            }
        )
        self.assertEqual(
            json.loads(output)["hookSpecificOutput"]["permissionDecision"],
            "deny",
        )

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
        self.assertEqual(json.loads(output)["hookSpecificOutput"]["permissionDecision"], "deny")

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
        self.assertEqual(json.loads(output)["hookSpecificOutput"]["permissionDecision"], "deny")

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
        self.assertEqual(json.loads(output)["hookSpecificOutput"]["permissionDecision"], "deny")

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
        self.assertEqual(json.loads(output)["hookSpecificOutput"]["permissionDecision"], "deny")


class SpawnAllocationCrossRepoTests(unittest.TestCase):
    """assert_spawn_allocation must find a lease prepared in a DIFFERENT repo
    than the session cwd (dep-repo-worker / external-repo-worker dispatch),
    while still failing closed for an unprepared checkout inside the caller's
    own repo -- and for a checkout whose OWN repo has no matching lease
    either, which is what a forged or mismatched claim would look like."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name).resolve()
        self.caller_repo = root / "caller-repo"
        self.other_repo = root / "other-repo"
        self.other_lease_path = self.other_repo / "worktree" / "feature"
        self.other_lease_path.mkdir(parents=True)
        self.caller_repo.mkdir()
        self.unrelated_path = root / "unrelated"
        self.unrelated_path.mkdir()
        self.other_repo_inventory = [
            {
                "branch": "writer/dep-1",
                "path": str(self.other_lease_path),
                "kind": "worktree",
                "vars": {"actor": "dep-actor", "lease": "dep-lease"},
            }
        ]

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _wait_prompt(self, checkout: Path) -> str:
        return (
            f"WAIT checkout={checkout}\n"
            "Do not invoke tools or start work.\n"
            "The controlling parent will send your task after binding "
            "your Worktrunk lease."
        )

    def test_cross_repo_prepared_lease_is_dispatchable(self) -> None:
        """A lease prepared in a different repo than the caller's cwd must be
        found by re-deriving the checkout's own git root, not by trusting the
        caller's repo-local inventory alone."""
        tool_input = {"prompt": self._wait_prompt(self.other_lease_path)}
        with (
            patch.object(MODULE, "resolve_checkout_repo", return_value=self.other_repo),
            patch.object(MODULE, "wt_inventory", return_value=self.other_repo_inventory),
        ):
            item = MODULE.assert_spawn_allocation(
                tool_input, inventory=[], repo=self.caller_repo
            )
        self.assertEqual(item["vars"]["lease"], "dep-lease")

    def test_unprepared_same_repo_spawn_is_still_denied(self) -> None:
        """An unleased path INSIDE the caller's own repo must fail closed --
        the fix must not loosen this, only extend the lookup to other repos."""
        tool_input = {"prompt": self._wait_prompt(self.unrelated_path)}
        with patch.object(MODULE, "resolve_checkout_repo", return_value=self.caller_repo):
            with self.assertRaises(MODULE.ContractError):
                MODULE.assert_spawn_allocation(
                    tool_input, inventory=[], repo=self.caller_repo
                )

    def test_checkout_in_a_real_other_repo_with_no_matching_lease_is_denied(self) -> None:
        """A path that DOES resolve to a real, different git repo but was never
        `prepare`-d there is a forged/mismatched claim and must still be
        denied -- resolving the repo grants a lookup, not a lease."""
        tool_input = {"prompt": self._wait_prompt(self.other_lease_path)}
        with (
            patch.object(MODULE, "resolve_checkout_repo", return_value=self.other_repo),
            patch.object(MODULE, "wt_inventory", return_value=[]),
        ):
            with self.assertRaises(MODULE.ContractError):
                MODULE.assert_spawn_allocation(
                    tool_input, inventory=[], repo=self.caller_repo
                )
COMPLETE_ENVELOPE = {
    "scope": ["src/**"],
    "base_ref": "main",
    "base_sha": "0" * 40,
    "execution_task_kind": "rust",
    "execution_kind": "implementation",
    "execution_dispatch": "subagent",
    "execution_agent": "domain-specialist",
    "complexity_tier": "medium",
}


class BindingTests(unittest.TestCase):
    def setUp(self) -> None:
        # bind indexes its fixture repo, and the temp repo is gone by the next test.
        self.addCleanup(clear_binding_index)

    def test_bind_accepts_exact_context_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            path = repo / "writer"
            path.mkdir()
            inventory = [
                {
                    "branch": "writer/a",
                    "path": str(path),
                    "vars": {
                        "actor": "writer-actor",
                        "lease": "lease-a",
                    },
                }
            ]
            writes: list[tuple[str, str]] = []
            args = SimpleNamespace(
                repo=str(repo),
                path=str(path),
                actor="writer-actor",
                lease="lease-a",
                handle="researcher-r1@session-b807e068",
                context=None,
                ack="WAIT context=aresearcher-r1-cb8a2c084ff1c7fa",
                bead=None,
                resource=None,
            )
            with (
                patch.object(MODULE, "wt_inventory", return_value=inventory),
                patch.object(MODULE, "beads_active", return_value=False),
                patch.object(
                    MODULE,
                    "set_var",
                    side_effect=lambda _repo, _branch, key, value: writes.append((key, value)),
                ),
            ):
                result = MODULE.bind(args)

            self.assertEqual(result["context"], "aresearcher-r1-cb8a2c084ff1c7fa")
            self.assertEqual(result["handle"], "researcher-r1@session-b807e068")
            self.assertIn(("context", "aresearcher-r1-cb8a2c084ff1c7fa"), writes)
            self.assertIn(
                (
                    "runtime-bindings",
                    '[{"context":"aresearcher-r1-cb8a2c084ff1c7fa",'
                    '"handle":"researcher-r1@session-b807e068"}]',
                ),
                writes,
            )

    def test_bind_requires_notification_ack_instead_of_raw_context(self) -> None:
        args = SimpleNamespace(
            repo="/tmp/repo",
            path="/tmp/writer",
            actor="writer-actor",
            lease="lease-a",
            handle="researcher-r1@session-b807e068",
            context="aresearcher-r1-cb8a2c084ff1c7fa",
            ack=None,
            bead=None,
            resource=None,
        )
        with self.assertRaisesRegex(MODULE.ContractError, "completion notification"):
            MODULE.bind(args)

    def test_bind_requires_parent_visible_handle(self) -> None:
        args = SimpleNamespace(
            repo="/tmp/repo",
            path="/tmp/writer",
            actor="writer-actor",
            lease="lease-a",
            handle="",
            context=None,
            ack="WAIT context=aresearcher-r1-cb8a2c084ff1c7fa",
            bead=None,
            resource=None,
        )
        with self.assertRaisesRegex(MODULE.ContractError, "routing handle"):
            MODULE.bind(args)

    def test_bind_rejects_claimed_bead_mode(self) -> None:
        args = SimpleNamespace(
            repo="/tmp/repo",
            path="/tmp/writer",
            actor="writer-actor",
            lease="lease-a",
            handle="researcher-r1@session-b807e068",
            context=None,
            ack="WAIT context=aresearcher-r1-cb8a2c084ff1c7fa",
            bead="demo-1",
            resource=None,
        )
        with self.assertRaisesRegex(MODULE.ContractError, "unclaimed --resource"):
            MODULE.bind(args)

    def test_bind_rejects_malformed_context_acknowledgement(self) -> None:
        args = SimpleNamespace(
            repo="/tmp/repo",
            path="/tmp/writer",
            actor="writer-actor",
            lease="lease-a",
            handle="researcher-r1@session-b807e068",
            context=None,
            ack="WAIT context=agent-1\nextra",
            bead=None,
            resource=None,
        )
        with self.assertRaisesRegex(MODULE.ContractError, "WAIT context"):
            MODULE.bind(args)

    def test_bind_adds_child_context_without_replacing_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            path = repo / "writer"
            path.mkdir()
            inventory = [
                {
                    "branch": "writer/a",
                    "path": str(path),
                    "vars": {
                        "actor": "writer-actor",
                        "lease": "lease-a",
                        "context": "parent-agent",
                    },
                }
            ]
            writes: list[tuple[str, str]] = []

            def capture(_repo, _branch, key, value):
                writes.append((key, value))

            args = SimpleNamespace(
                repo=str(repo),
                path=str(path),
                actor="writer-actor",
                lease="lease-a",
                handle="child-agent",
                context=None,
                ack="WAIT context=child-agent",
                bead=None,
                resource=None,
            )
            with (
                patch.object(MODULE, "wt_inventory", return_value=inventory),
                patch.object(MODULE, "beads_active", return_value=False),
                patch.object(MODULE, "set_var", side_effect=capture),
            ):
                result = MODULE.bind(args)

            self.assertEqual(result["contexts"], ["child-agent", "parent-agent"])
            self.assertNotIn(("context", "child-agent"), writes)
            self.assertIn(("contexts", '["child-agent","parent-agent"]'), writes)

    def test_bind_attaches_unclaimed_activation_resource(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            path = repo / "writer"
            path.mkdir()
            inventory = [
                {
                    "branch": "writer/a",
                    "path": str(path),
                    "vars": {"actor": "writer-actor", "lease": "lease-a"},
                }
            ]
            issue = {
                "id": "demo-1",
                "status": "open",
                "assignee": None,
                "metadata": {
                    "actor": "writer-actor",
                    "branch": "writer/a",
                    "lease_token": "lease-a",
                    "worktree": str(path),
                    **COMPLETE_ENVELOPE,
                },
            }
            writes: list[tuple[str, str]] = []
            commands: list[list[str]] = []
            args = SimpleNamespace(
                repo=str(repo),
                path=str(path),
                actor="writer-actor",
                lease="lease-a",
                handle="researcher-r1@session-b807e068",
                context=None,
                ack="WAIT context=aresearcher-r1-cb8a2c084ff1c7fa",
                bead=None,
                resource="demo-1",
            )

            def capture_run(argv, **_kwargs):
                commands.append(argv)
                return subprocess.CompletedProcess(argv, 0, "", "")

            with (
                patch.object(MODULE, "wt_inventory", return_value=inventory),
                patch.object(MODULE, "beads_active", return_value=True),
                patch.object(MODULE, "one_bead", return_value=issue),
                patch.object(MODULE, "active_bead_conflicts", return_value=[]),
                patch.object(
                    MODULE,
                    "set_var",
                    side_effect=lambda _repo, _branch, key, value: writes.append((key, value)),
                ),
                patch.object(MODULE, "run", side_effect=capture_run),
            ):
                result = MODULE.bind(args)

            self.assertEqual(result["resource"], "demo-1")
            self.assertIn(("resource", "demo-1"), writes)
            metadata_updates = [command for command in commands if command[:1] == ["bd"]]
            self.assertEqual(len(metadata_updates), 1)
            self.assertIn("runtime_handle", metadata_updates[0][-1])
            self.assertIn("runtime_context", metadata_updates[0][-1])


class HookManifestTests(unittest.TestCase):
    def test_runtime_manifests_route_native_tool_names(self) -> None:
        hooks = hook_manifest_root()
        claude = json.loads((hooks / "worktrunk-writer-claude-hooks.json").read_text())
        codex = json.loads((hooks / "worktrunk-writer-codex-hooks.json").read_text())
        claude_matchers = [entry["matcher"] for entry in claude["hooks"]["PreToolUse"]]
        codex_matchers = [entry["matcher"] for entry in codex["hooks"]["PreToolUse"]]
        self.assertIn("Agent|SendMessage", claude_matchers)
        self.assertIn(
            "Agent|send_message|followup_task|send_input|multi_agent_v1send_input|resume_agent|multi_agent_v1resume_agent",
            codex_matchers,
        )
        self.assertFalse(any("spawn_agent" in value for value in codex_matchers))
        claude_tools = next(value for value in claude_matchers if "Bash" in value)
        codex_tools = next(value for value in codex_matchers if "Bash" in value)
        self.assertIn("Edit", claude_tools)
        self.assertNotIn("apply_patch", claude_tools)
        self.assertIn("apply_patch", codex_tools)
        self.assertIn("NotebookEdit", claude_tools)
        self.assertIn("NotebookEdit", codex_tools)

    def test_mutation_manifests_match_every_governed_mutation_tool(self) -> None:
        """A tool in MUTATION_TOOLS the manifests never match is never validated."""
        hooks = hook_manifest_root()
        for name, runtime_tools in (
            (
                "worktrunk-writer-claude-hooks.json",
                {"Bash", "Edit", "Write", "MultiEdit", "NotebookEdit"},
            ),
            (
                "worktrunk-writer-codex-hooks.json",
                {"Bash", "apply_patch", "Edit", "Write", "MultiEdit", "NotebookEdit"},
            ),
        ):
            manifest = json.loads((hooks / name).read_text())
            matched = {
                tool
                for entry in manifest["hooks"]["PreToolUse"]
                for tool in entry["matcher"].split("|")
            }
            self.assertEqual(runtime_tools - matched, set(), name)
            self.assertEqual(runtime_tools - MODULE.MUTATION_TOOLS, set(), name)

    def test_runtime_manifests_anchor_scripts_at_project_root(self) -> None:
        hooks = hook_manifest_root()
        for name in (
            "worktrunk-writer-claude-hooks.json",
            "worktrunk-writer-codex-hooks.json",
        ):
            manifest = json.loads((hooks / name).read_text())
            for entry in manifest["hooks"]["PreToolUse"]:
                command = entry["hooks"][0]["command"]
                self.assertTrue(command.startswith('cd "${CLAUDE_PROJECT_DIR:-.}" && '))
                self.assertIn("${PLUGIN_ROOT}/.apm/skills/worktrunk-writer/", command)

    def test_runtime_manifests_expose_the_subagent_context_handshake(self) -> None:
        hooks = hook_manifest_root()
        for name in (
            "worktrunk-writer-claude-hooks.json",
            "worktrunk-writer-codex-hooks.json",
        ):
            manifest = json.loads((hooks / name).read_text())
            entries = manifest["hooks"]["SubagentStart"]
            self.assertEqual(len(entries), 1)
            command = entries[0]["hooks"][0]["command"]
            self.assertTrue(command.startswith('cd "${CLAUDE_PROJECT_DIR:-.}" && '))
            self.assertIn("context-handshake.py", command)


class BeadsLeaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = Path("/tmp/writer-a")
        self.issue = {
            "id": "demo-1",
            "status": "in_progress",
            "assignee": "writer-actor",
            "metadata": {},
        }
        self.inventory: list[dict[str, object]] = []
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
        self.inventory.append(
            {
                "branch": "writer/other",
                "path": "/tmp/writer-other",
                "kind": "worktree",
                "vars": {"bead": "demo-1", "lease": "other-lease"},
            }
        )
        with self.assertRaises(MODULE.ContractError):
            self.assert_available()

    def validate_parent_stamped_anchors(self) -> dict:
        inventory = [
            {
                "branch": "writer/a",
                "path": str(self.path),
                "vars": {"actor": "writer-actor", "lease": "lease-a"},
            }
        ]
        with patch.object(MODULE, "beads_active", return_value=True):
            return MODULE.validate(
                Path("/tmp"),
                self.path,
                actor="writer-actor",
                lease="lease-a",
                bead="demo-1",
                inventory=inventory,
            )

    def test_post_claim_validation_accepts_canonical_worktree_anchor(self) -> None:
        self.issue["metadata"] = {
            "actor": "writer-actor",
            "branch": "writer/a",
            "lease_token": "lease-a",
            "worktree": str(self.path),
        }
        result = self.validate_parent_stamped_anchors()
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["bead"], "demo-1")

    def test_post_claim_validation_accepts_external_artifacts_directory(self) -> None:
        self.issue["metadata"] = {
            "actor": "writer-actor",
            "branch": "writer/a",
            "lease_token": "lease-a",
            "worktree": str(self.path),
            "execution_kind": "artifact",
            "artifacts_dir": "/tmp/shared-run/artifacts",
        }
        result = self.validate_parent_stamped_anchors()
        self.assertEqual(result["status"], "valid")

    def test_post_claim_validation_rejects_relative_artifacts_directory(self) -> None:
        self.issue["metadata"] = {
            "actor": "writer-actor",
            "branch": "writer/a",
            "lease_token": "lease-a",
            "worktree": str(self.path),
            "execution_kind": "artifact",
            "artifacts_dir": ".orchestration/run-1/artifacts",
        }
        with self.assertRaisesRegex(MODULE.ContractError, "absolute artifacts_dir"):
            self.validate_parent_stamped_anchors()

    def test_post_claim_validation_rejects_worktree_artifacts_directory(self) -> None:
        self.issue["metadata"] = {
            "actor": "writer-actor",
            "branch": "writer/a",
            "lease_token": "lease-a",
            "worktree": str(self.path),
            "execution_kind": "artifact",
            "artifacts_dir": str(self.path / ".orchestration/run-1/artifacts"),
        }
        with self.assertRaisesRegex(MODULE.ContractError, "outside its disposable worktree"):
            self.validate_parent_stamped_anchors()

    def test_post_claim_validation_accepts_legacy_worktree_path_anchor(self) -> None:
        self.issue["metadata"] = {
            "actor": "writer-actor",
            "branch": "writer/a",
            "lease_token": "lease-a",
            "worktree_path": str(self.path),
        }
        result = self.validate_parent_stamped_anchors()
        self.assertEqual(result["status"], "valid")

    def test_post_claim_validation_rejects_conflicting_worktree_alias(self) -> None:
        self.issue["metadata"] = {
            "actor": "writer-actor",
            "branch": "writer/a",
            "lease_token": "lease-a",
            "worktree": str(self.path),
            "worktree_path": "/tmp/other-writer",
        }
        with self.assertRaisesRegex(MODULE.ContractError, "worktree_path"):
            self.validate_parent_stamped_anchors()

    def test_post_claim_validation_rejects_missing_actor_anchor(self) -> None:
        self.issue["metadata"] = {
            "branch": "writer/a",
            "lease_token": "lease-a",
            "worktree": str(self.path),
        }
        with self.assertRaisesRegex(MODULE.ContractError, "metadata actor"):
            self.validate_parent_stamped_anchors()

    def test_post_claim_validation_rejects_missing_lease_anchor(self) -> None:
        self.issue["metadata"] = {
            "actor": "writer-actor",
            "branch": "writer/a",
            "worktree": str(self.path),
        }
        with self.assertRaisesRegex(MODULE.ContractError, "metadata lease_token"):
            self.validate_parent_stamped_anchors()

    def test_post_claim_validation_rejects_unclaimed_bead(self) -> None:
        self.issue["assignee"] = None
        self.issue["metadata"] = {
            "actor": "writer-actor",
            "branch": "writer/a",
            "lease_token": "lease-a",
            "worktree": str(self.path),
            "worktree_path": str(self.path),
        }
        inventory = [
            {
                "branch": "writer/a",
                "path": str(self.path),
                "vars": {"actor": "writer-actor", "lease": "lease-a"},
            }
        ]
        with (
            patch.object(MODULE, "beads_active", return_value=True),
            self.assertRaises(MODULE.ContractError),
        ):
            MODULE.validate(
                Path("/tmp"),
                self.path,
                actor="writer-actor",
                lease="lease-a",
                bead="demo-1",
                inventory=inventory,
            )


class PrepareRollbackTests(unittest.TestCase):
    def test_copy_failure_removes_the_new_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            path = Path(temp) / "writer"
            repo.mkdir()
            path.mkdir()
            resolved_path = path.resolve()
            item = {"branch": "writer/a", "path": str(path), "is_main": False}
            commands: list[list[str]] = []

            def fake_run(argv, **_kwargs):
                commands.append(argv)
                if "switch" in argv:
                    return subprocess.CompletedProcess(
                        argv,
                        0,
                        json.dumps({"branch": "writer/a", "path": str(path)}),
                        "",
                    )
                if argv[:3] == ["git", "-C", str(resolved_path)] and "branch" in argv:
                    return subprocess.CompletedProcess(argv, 0, "writer/a\n", "")
                if argv[:3] == ["git", "-C", str(resolved_path)] and "rev-parse" in argv:
                    return subprocess.CompletedProcess(argv, 0, "abc123\n", "")
                if "copy-ignored" in argv:
                    raise MODULE.ContractError("copy failed")
                if "remove" in argv:
                    return subprocess.CompletedProcess(argv, 0, "", "")
                raise AssertionError(argv)

            args = SimpleNamespace(
                repo=str(repo),
                branch="writer/a",
                base="origin/main",
                source="main",
                actor="writer-actor",
                lease="lease-a",
                runtime="codex",
                agent="builder",
                bead=None,
                run=None,
                node=None,
                model=None,
                effort=None,
                worktree_path=None,
            )
            with (
                patch.object(MODULE.shutil, "which", return_value="/usr/bin/wt"),
                patch.object(MODULE, "beads_active", return_value=False),
                patch.object(MODULE, "wt_inventory", side_effect=[[], [item]]),
                patch.object(MODULE, "run", side_effect=fake_run),
                self.assertRaisesRegex(MODULE.ContractError, "copy failed"),
            ):
                MODULE.prepare(args)

            removals = [command for command in commands if "remove" in command]
            self.assertEqual(len(removals), 1)
            self.assertIn("--foreground", removals[0])
            self.assertIn("--force-delete", removals[0])
            self.assertEqual(removals[0][-1], str(resolved_path))

    def test_prepare_rejects_claimed_bead_mode_before_worktree_creation(self) -> None:
        args = SimpleNamespace(
            repo="/tmp/repo",
            branch="writer/a",
            base="origin/main",
            source="main",
            actor="writer-actor",
            lease="lease-a",
            runtime="codex",
            agent="builder",
            bead="demo-1",
            run=None,
            node=None,
            model=None,
            effort=None,
            worktree_path=None,
        )
        with (
            patch.object(MODULE, "wt_inventory") as inventory,
            self.assertRaisesRegex(MODULE.ContractError, "parent-managed"),
        ):
            MODULE.prepare(args)
        inventory.assert_not_called()


def worktrunk_available() -> bool:
    return shutil.which("wt") is not None and shutil.which("git") is not None


@unittest.skipUnless(worktrunk_available(), "requires the real wt and git binaries")
class RealWorktrunkVarTests(unittest.TestCase):
    """Exercise the real Worktrunk CLI.

    Mocked ``set_var`` cannot catch a key Worktrunk itself rejects, which is
    exactly how the ``runtime_bindings`` underscore defect reached runtime.
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name).resolve() / "repo"
        self.repo.mkdir(parents=True)
        self.branch = "writer/real-var-probe"
        self.worktree: Path | None = None
        for argv in (
            ["git", "-C", str(self.repo), "init", "-q"],
            ["git", "-C", str(self.repo), "config", "user.email", "test@example.com"],
            ["git", "-C", str(self.repo), "config", "user.name", "Test"],
            # A global commit.gpgsign otherwise fails the fixture commit with
            # "1Password: Could not connect to socket" whenever that agent is
            # not running. Nothing here is worth signing.
            ["git", "-C", str(self.repo), "config", "commit.gpgsign", "false"],
            ["git", "-C", str(self.repo), "config", "tag.gpgsign", "false"],
            ["git", "-C", str(self.repo), "commit", "-q", "--allow-empty", "-m", "init"],
        ):
            subprocess.run(argv, check=True, capture_output=True, text=True)
        created = subprocess.run(
            [
                "wt",
                "-C",
                str(self.repo),
                "switch",
                "--create",
                self.branch,
                "--base",
                "HEAD",
                "--no-cd",
                "--format=json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if created.returncode:
            self.skipTest(f"wt switch --create failed: {created.stderr.strip()}")
        self.worktree = Path(json.loads(created.stdout)["path"]).resolve()

    def tearDown(self) -> None:
        if self.worktree:
            subprocess.run(
                [
                    "wt",
                    "-C",
                    str(self.repo),
                    "remove",
                    "--foreground",
                    "--force-delete",
                    str(self.worktree),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        self.temp.cleanup()

    def test_hyphenated_runtime_bindings_persists_in_the_inventory(self) -> None:
        value = json.dumps(
            [{"handle": "researcher-r1@session-b807e068", "context": "claude-agent-1"}],
            separators=(",", ":"),
        )
        MODULE.set_var(self.repo, self.branch, MODULE.RUNTIME_BINDINGS_KEY, value)
        item = MODULE.find_item(MODULE.wt_inventory(self.repo), branch=self.branch)
        self.assertEqual(
            MODULE.runtime_bindings(item),
            [{"handle": "researcher-r1@session-b807e068", "context": "claude-agent-1"}],
        )

    def test_worktrunk_rejects_the_legacy_underscore_key(self) -> None:
        """Worktrunk itself must reject the legacy spelling."""
        rejected = subprocess.run(
            [
                "wt",
                "-C",
                str(self.repo),
                "config",
                "state",
                "vars",
                "set",
                f"{MODULE.LEGACY_RUNTIME_BINDINGS_KEY}=[]",
                f"--branch={self.branch}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("nvalid key", rejected.stderr + rejected.stdout)

    def test_inventory_parses_the_real_cli_output(self) -> None:
        branches = {item.get("branch") for item in MODULE.wt_inventory(self.repo)}
        self.assertIn(self.branch, branches)

    def test_inventory_resolves_the_real_checkout_path(self) -> None:
        """Schema 2 nests the path under worktree; item_path must still find it."""
        item = MODULE.find_item(MODULE.wt_inventory(self.repo), branch=self.branch)
        self.assertEqual(MODULE.item_path(item), self.worktree)

    def test_inventory_requests_a_pinned_schema(self) -> None:
        self.assertIn("list.json-schema=2", MODULE.wt_inventory.__code__.co_consts)


class InventorySchemaTests(unittest.TestCase):
    def test_schema_two_envelope_is_flattened(self) -> None:
        payload = {
            "schema": 2,
            "items": [
                {
                    "branch": "writer/a",
                    "worktree": {"path": "/tmp/wt-a", "main": False},
                    "vars": {"lease": "L1"},
                },
                {"branch": "main", "worktree": {"path": "/tmp/repo", "main": True}},
            ],
        }
        items = MODULE.normalize_inventory(payload)
        self.assertEqual([item["path"] for item in items], ["/tmp/wt-a", "/tmp/repo"])
        self.assertEqual([item["is_main"] for item in items], [False, True])
        self.assertEqual(items[0]["vars"], {"lease": "L1"})

    def test_schema_one_array_is_passed_through(self) -> None:
        payload = [{"branch": "writer/a", "path": "/tmp/wt-a", "is_main": False}]
        self.assertEqual(MODULE.normalize_inventory(payload), payload)

    def test_branch_only_rows_have_no_path(self) -> None:
        items = MODULE.normalize_inventory({"schema": 2, "items": [{"branch": "remote-only"}]})
        self.assertIsNone(MODULE.item_path(items[0]))

    def test_envelope_without_items_is_rejected(self) -> None:
        with self.assertRaises(MODULE.ContractError):
            MODULE.normalize_inventory({"schema": 2})


class ChildSpawnTests(unittest.TestCase):
    """A claim-holder delegates inside its own lease, and cannot leave it.

    Both SKILL.md files promised this; the code had no branch for it, so every
    delegation-first specialist did its own bulk work. One burned 295k tokens and
    280 tool calls on work it was designed to hand off.
    """

    def setUp(self) -> None:
        self.parent_path = Path("/tmp/leased-parent")
        self.other_path = Path("/tmp/leased-other")
        self.inventory = [
            {
                "branch": "writer/parent",
                "path": str(self.parent_path),
                "vars": {
                    "actor": "parent-actor",
                    "lease": "parent-lease",
                    "contexts": json.dumps(["parent-ctx"]),
                    "runtime-bindings": json.dumps(
                        [{"context": "parent-ctx", "handle": "parent-ctx"}]
                    ),
                },
            },
            {
                "branch": "writer/other",
                "path": str(self.other_path),
                "vars": {
                    "actor": "other-actor",
                    "lease": "other-lease",
                    "contexts": json.dumps(["other-ctx"]),
                    "runtime-bindings": json.dumps(
                        [{"context": "other-ctx", "handle": "other-ctx"}]
                    ),
                },
            },
        ]

    def spawn(self, tool_input, context=None):
        payload = {"agent_id": context} if context else {}
        return MODULE.assert_spawn_allocation(tool_input, self.inventory, payload)

    def wait_for(self, path):
        return (
            f"WAIT checkout={path}\n"
            "Do not invoke tools or start work.\n"
            "The controlling parent will send your task after binding your Worktrunk lease."
        )

    def test_child_may_name_the_parents_own_checkout(self) -> None:
        item = self.spawn({"prompt": self.wait_for(self.parent_path)}, "parent-ctx")
        self.assertEqual(item["branch"], "writer/parent")

    def test_a_task_bearing_child_is_told_to_be_wait_only(self) -> None:
        """Admitting it would spawn a child that cannot act.

        An unbound context is refused by assert_runtime_lease on its first Bash or
        Edit, so the useful failure is here, naming the wait-only sequence.
        """
        with self.assertRaisesRegex(MODULE.ContractError, "must be wait-only"):
            self.spawn(
                {"subagent_type": "general-purpose", "prompt": "Grep callers"}, "parent-ctx"
            )

    def test_child_may_not_escape_to_another_lease(self) -> None:
        with self.assertRaisesRegex(MODULE.ContractError, "stay in its parent's leased checkout"):
            self.spawn({"prompt": self.wait_for(self.other_path)}, "parent-ctx")

    def test_unbound_spawner_is_still_denied(self) -> None:
        with self.assertRaisesRegex(MODULE.ContractError, "not parent-prepared"):
            self.spawn({"subagent_type": "general-purpose", "prompt": "Do work"}, "stranger")

    def test_spawn_without_a_context_is_still_denied(self) -> None:
        with self.assertRaisesRegex(MODULE.ContractError, "not parent-prepared"):
            self.spawn({"subagent_type": "general-purpose", "prompt": "Do work"})

    def test_exemption_ignores_agent_type_and_reads_only_the_binding(self) -> None:
        """Classifying by subagent_type is what got the 1.x deny gate reverted."""
        for kind in ("general-purpose", "domain-specialist", "reviewer", ""):
            item = self.spawn(
                {"subagent_type": kind, "prompt": self.wait_for(self.parent_path)},
                "parent-ctx",
            )
            self.assertEqual(item["branch"], "writer/parent")

    def test_a_context_bound_twice_grants_no_exemption(self) -> None:
        for item in self.inventory:
            item["vars"]["contexts"] = json.dumps(["dupe-ctx"])
            item["vars"]["runtime-bindings"] = json.dumps(
                [{"context": "dupe-ctx", "handle": "dupe-ctx"}]
            )
        with self.assertRaisesRegex(MODULE.ContractError, "not parent-prepared"):
            self.spawn({"subagent_type": "general-purpose", "prompt": "work"}, "dupe-ctx")


class MarkerLivenessTests(unittest.TestCase):
    """A run marker engages the protocol only while its run is going.

    Every uncertainty resolves toward live: this narrows a guard, so an
    unreadable marker or an absent task system must not switch it off.
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.temp.name)
        self.marker = self.cwd / ".active-run"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def live(self, text, issue=None, beads=True):
        self.marker.write_text(text)
        with patch.object(MODULE, "beads_active", return_value=beads):
            with patch.object(MODULE, "beads_json", return_value=[issue] if issue else []):
                return MODULE.marker_run_live(self.cwd, self.marker)

    def test_open_run_is_live(self) -> None:
        self.assertTrue(self.live('{"run_id": "run-1"}', {"id": "run-1", "status": "open"}))

    def test_closed_run_is_not_live(self) -> None:
        self.assertFalse(self.live('{"run_id": "run-1"}', {"id": "run-1", "status": "closed"}))

    def test_pending_marker_is_live(self) -> None:
        self.assertTrue(self.live('{"run_id": "pending"}'))

    def test_unparsable_marker_is_live(self) -> None:
        self.assertTrue(self.live("not json at all"))

    def test_absent_task_system_is_live(self) -> None:
        self.assertTrue(self.live('{"run_id": "run-1"}', {"status": "closed"}, beads=False))

    def test_unreadable_resource_is_live(self) -> None:
        self.marker.write_text('{"run_id": "run-1"}')
        with patch.object(MODULE, "beads_active", return_value=True):
            with patch.object(MODULE, "beads_json", side_effect=MODULE.ContractError("no bd")):
                self.assertTrue(MODULE.marker_run_live(self.cwd, self.marker))


class ProtocolEngagementTests(unittest.TestCase):
    """A marker alone is not enough; a lease must be reachable.

    Escalating on the marker alone turned the documented advise-not-deny default
    into a deny for every spawn from the primary checkout during a run, including
    read-only work aimed at a different repository.
    """

    def engaged(self, inventory, cwd="/tmp/elsewhere"):
        payload = {"tool_input": {"subagent_type": "general-purpose", "prompt": "work"}}
        with patch.object(MODULE, "orchestration_active", return_value=True):
            return MODULE.protocol_engaged(payload, inventory, Path(cwd))

    def test_a_repo_with_no_leases_does_not_engage(self) -> None:
        self.assertFalse(self.engaged([{"branch": "main", "path": "/tmp/primary"}]))

    def test_a_repo_holding_a_lease_still_engages(self) -> None:
        inventory = [
            {"branch": "main", "path": "/tmp/primary"},
            {"branch": "w/a", "path": "/tmp/w-a", "vars": {"actor": "a", "lease": "l"}},
        ]
        self.assertTrue(self.engaged(inventory))


class EnvelopeCompletenessTests(unittest.TestCase):
    def test_missing_fields_are_named(self) -> None:
        metadata = dict(COMPLETE_ENVELOPE)
        del metadata["scope"]
        del metadata["complexity_tier"]
        with self.assertRaises(MODULE.ContractError) as caught:
            MODULE.assert_envelope_complete("demo-1", metadata)
        message = str(caught.exception)
        self.assertIn("scope", message)
        self.assertIn("complexity_tier", message)
        self.assertNotIn("base_ref", message)

    def test_a_complete_envelope_passes(self) -> None:
        MODULE.assert_envelope_complete("demo-1", dict(COMPLETE_ENVELOPE))

    def test_an_empty_value_counts_as_missing(self) -> None:
        metadata = dict(COMPLETE_ENVELOPE, base_sha="")
        with self.assertRaisesRegex(MODULE.ContractError, "base_sha"):
            MODULE.assert_envelope_complete("demo-1", metadata)


class MergeBeadOwnerTests(unittest.TestCase):
    """An unowned merge bead can be drained mid-run by the global shepherd."""

    def check(self, issues, metadata={"run_id": "run-1"}):
        with patch.object(MODULE, "beads_active", return_value=True):
            with patch.object(MODULE, "beads_json", return_value=issues):
                MODULE.assert_merge_beads_owned(Path("/tmp/repo"), "demo-1", metadata)

    def merge_bead(self, **over):
        issue = {
            "id": "merge-1",
            "status": "open",
            "labels": ["agent:integrator"],
            "metadata": {"run_id": "run-1", "integration_owner": "orchestrate"},
        }
        issue.update(over)
        return issue

    def test_owned_merge_beads_pass(self) -> None:
        self.check([self.merge_bead()])

    def test_unowned_merge_bead_in_this_run_is_reported(self) -> None:
        bead = self.merge_bead(metadata={"run_id": "run-1"})
        with self.assertRaisesRegex(MODULE.ContractError, "merge-1"):
            self.check([bead])

    def test_another_runs_merge_bead_is_not_our_business(self) -> None:
        self.check([self.merge_bead(metadata={"run_id": "run-2"})])

    def test_closed_merge_bead_is_ignored(self) -> None:
        self.check([self.merge_bead(status="closed", metadata={"run_id": "run-1"})])

    def test_non_merge_beads_are_ignored(self) -> None:
        self.check([self.merge_bead(labels=["orc-node"], metadata={"run_id": "run-1"})])

    def test_a_run_without_an_id_is_skipped(self) -> None:
        self.check([self.merge_bead(metadata={"run_id": "run-1"})], metadata={})


class SubagentExitTests(unittest.TestCase):
    """SubagentStop is a trigger, not an actor.

    A stop is not an ending: `domain-specialist` is resumable and its review/fix
    loop depends on being woken for the same node, so clearing the binding on every
    stop would strand a live actor between review rounds.
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name).resolve()
        self.leased = self.repo / "leased"
        self.leased.mkdir()
        self.item = {
            "branch": "writer/leased",
            "path": str(self.leased),
            "vars": {
                "actor": "a",
                "lease": "l",
                "context": "ctx-1",
                "runtime-bindings": json.dumps([{"context": "ctx-1", "handle": "ctx-1"}]),
                "resource": "demo-1",
            },
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def invoke(self, payload, *, stale):
        stamped, cleared = [], []
        with patch.object(MODULE, "run") as command:
            command.return_value = SimpleNamespace(stdout=str(self.repo), stderr="")
            with patch.object(MODULE, "wt_inventory", return_value=[self.item]):
                with patch.object(MODULE, "stale_binding", return_value=stale):
                    with patch.object(MODULE, "set_var", side_effect=lambda r, b, k, v: stamped.append(k)):
                        with patch.object(MODULE, "clear_var", side_effect=lambda r, b, k: cleared.append(k)):
                            with patch("sys.stdin", io.StringIO(json.dumps(payload))):
                                code = MODULE.subagent_exit()
        return code, stamped, cleared

    def test_a_resumable_actor_keeps_its_binding(self) -> None:
        code, stamped, cleared = self.invoke(
            {"agent_type": "domain-specialist", "agent_id": "ctx-1", "cwd": str(self.leased)},
            stale=False,
        )
        self.assertEqual(code, 0)
        self.assertEqual(stamped, ["exited"])
        self.assertEqual(cleared, [])

    def test_a_resolved_resource_releases_the_binding(self) -> None:
        code, stamped, cleared = self.invoke(
            {"agent_type": "domain-specialist", "agent_id": "ctx-1", "cwd": str(self.leased)},
            stale=True,
        )
        self.assertEqual(code, 0)
        self.assertIn("exited", stamped)
        self.assertEqual(sorted(cleared), ["context", "contexts", "runtime-bindings"])

    def test_an_unknown_context_is_a_noop(self) -> None:
        code, stamped, cleared = self.invoke(
            {"agent_type": "domain-specialist", "agent_id": "stranger", "cwd": str(self.leased)},
            stale=True,
        )
        self.assertEqual((code, stamped, cleared), (0, [], []))

    def test_a_payload_without_a_context_is_a_noop(self) -> None:
        code, stamped, cleared = self.invoke({"cwd": str(self.leased)}, stale=True)
        self.assertEqual((code, stamped, cleared), (0, [], []))

    def test_an_error_never_traps_the_subagent(self) -> None:
        with patch.object(MODULE, "run", side_effect=MODULE.ContractError("no git")):
            with patch("sys.stdin", io.StringIO(json.dumps({"agent_id": "ctx-1"}))):
                self.assertEqual(MODULE.subagent_exit(), 0)

    def test_unparsable_stdin_exits_clean(self) -> None:
        with patch("sys.stdin", io.StringIO("not json")):
            self.assertEqual(MODULE.subagent_exit(), 0)


class LifecycleHookTests(unittest.TestCase):
    """The wt hook entry point. A leased checkout is guarded; nothing else is.

    Regression cover for a live lockout: a specialist ran `git switch -c` inside
    its leased checkout, which moved it off the stamped branch and left it unable
    to run any tool, including the `bd` call that would have reported the failure.
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name).resolve()
        self.primary = root / "primary"
        self.leased = root / "leased"
        self.plain = root / "plain"
        for path in (self.primary, self.leased, self.plain):
            path.mkdir()
        self.inventory = [
            {"branch": "main", "path": str(self.primary), "kind": "worktree"},
            {"branch": "plain/branch", "path": str(self.plain), "kind": "worktree"},
            {
                "branch": "writer/leased",
                "path": str(self.leased),
                "kind": "worktree",
                "vars": {
                    "actor": "leased-actor",
                    "lease": "leased-token",
                    "context": "agent-1",
                    "contexts": json.dumps(["agent-1"]),
                    "runtime-bindings": json.dumps([{"context": "agent-1", "handle": "agent-1"}]),
                    "resource": "demo-1",
                },
            },
        ]

    def tearDown(self) -> None:
        self.temp.cleanup()

    def invoke(self, **kwargs):
        fields = {"repo": str(self.primary), "path": None, "target": None, "event": "pre-start"}
        fields.update(kwargs)
        args = SimpleNamespace(**fields)
        with patch.object(MODULE, "wt_inventory", return_value=self.inventory):
            with patch.object(MODULE, "clear_var") as cleared:
                code = MODULE.lifecycle(args)
        return code, [call.args[2] for call in cleared.call_args_list]

    def test_unleased_checkout_is_a_silent_noop_on_every_event(self) -> None:
        for event in ("pre-start", "pre-switch", "pre-remove"):
            code, cleared = self.invoke(event=event, path=str(self.plain), target="elsewhere")
            self.assertEqual((event, code, cleared), (event, 0, []))

    def test_pre_switch_refuses_to_leave_the_stamped_branch(self) -> None:
        code, cleared = self.invoke(event="pre-switch", path=str(self.leased), target="main")
        self.assertEqual(code, 1)
        self.assertEqual(cleared, [])

    def test_pre_switch_allows_a_switch_to_the_stamped_branch(self) -> None:
        code, _ = self.invoke(
            event="pre-switch", path=str(self.leased), target="writer/leased"
        )
        self.assertEqual(code, 0)

    def test_pre_remove_always_clears_the_binding(self) -> None:
        code, cleared = self.invoke(event="pre-remove", path=str(self.leased))
        self.assertEqual(code, 0)
        self.assertEqual(sorted(cleared), ["context", "contexts", "runtime-bindings"])

    def test_pre_start_keeps_a_binding_whose_resource_is_still_working(self) -> None:
        with patch.object(MODULE, "stale_binding", return_value=False):
            code, cleared = self.invoke(event="pre-start", path=str(self.leased))
        self.assertEqual((code, cleared), (0, []))

    def test_pre_start_releases_a_binding_the_resource_proves_finished(self) -> None:
        with patch.object(MODULE, "stale_binding", return_value=True):
            code, cleared = self.invoke(event="pre-start", path=str(self.leased))
        self.assertEqual(code, 0)
        self.assertEqual(sorted(cleared), ["context", "contexts", "runtime-bindings"])

    def test_an_internal_error_fails_open(self) -> None:
        args = SimpleNamespace(
            repo=str(self.primary), path=str(self.leased), target=None, event="pre-remove"
        )
        with patch.object(MODULE, "wt_inventory", side_effect=MODULE.ContractError("no wt")):
            self.assertEqual(MODULE.lifecycle(args), 0)


class StaleBindingTests(unittest.TestCase):
    """Liveness is never guessed: only the task system can prove an actor is done."""

    def setUp(self) -> None:
        self.repo = Path("/tmp/repo")
        self.item = {"branch": "writer/leased", "vars": {"resource": "demo-1"}}

    def stale(self, issue, *, beads=True):
        with patch.object(MODULE, "beads_active", return_value=beads):
            with patch.object(MODULE, "beads_json", return_value=[issue]):
                return MODULE.stale_binding(self.repo, self.item)

    def test_closed_resource_is_stale(self) -> None:
        self.assertTrue(self.stale({"status": "closed", "assignee": "someone"}))

    def test_unassigned_and_not_in_progress_is_stale(self) -> None:
        self.assertTrue(self.stale({"status": "open", "assignee": None}))

    def test_claimed_in_progress_resource_is_live(self) -> None:
        self.assertFalse(self.stale({"status": "in_progress", "assignee": "orc-a"}))

    def test_unassigned_but_in_progress_is_left_alone(self) -> None:
        self.assertFalse(self.stale({"status": "in_progress", "assignee": None}))

    def test_blocked_resource_is_left_alone(self) -> None:
        self.assertFalse(self.stale({"status": "blocked", "assignee": None}))

    def test_no_resource_var_is_never_stale(self) -> None:
        self.assertFalse(MODULE.stale_binding(self.repo, {"vars": {}}))

    def test_absent_beads_workspace_is_never_stale(self) -> None:
        self.assertFalse(self.stale({"status": "closed"}, beads=False))

    def test_unreadable_resource_is_never_stale(self) -> None:
        with patch.object(MODULE, "beads_active", return_value=True):
            with patch.object(
                MODULE, "beads_json", side_effect=MODULE.ContractError("bd missing")
            ):
                self.assertFalse(MODULE.stale_binding(self.repo, self.item))


class ReleaseTests(unittest.TestCase):
    def test_release_clears_only_binding_vars(self) -> None:
        item = {
            "branch": "writer/leased",
            "path": "/tmp/leased",
            "vars": {
                "actor": "a",
                "lease": "l",
                "context": "agent-1",
                "contexts": json.dumps(["agent-1"]),
                "runtime-bindings": json.dumps([{"context": "agent-1", "handle": "agent-1"}]),
            },
        }
        args = SimpleNamespace(repo="/tmp/repo", path="/tmp/leased", actor="a", lease="l")
        with patch.object(MODULE, "wt_inventory", return_value=[item]):
            with patch.object(MODULE, "validate", return_value={"status": "valid"}):
                with patch.object(MODULE, "find_item", return_value=item):
                    with patch.object(MODULE, "clear_var") as cleared:
                        result = MODULE.release(args)
        self.assertEqual(result["status"], "released")
        self.assertEqual(result["released_contexts"], ["agent-1"])
        self.assertEqual(
            sorted(call.args[2] for call in cleared.call_args_list),
            ["context", "contexts", "runtime-bindings"],
        )

    def test_release_rejects_a_mismatched_lease(self) -> None:
        args = SimpleNamespace(repo="/tmp/repo", path="/tmp/leased", actor="a", lease="wrong")
        with patch.object(MODULE, "wt_inventory", return_value=[]):
            with patch.object(
                MODULE, "validate", side_effect=MODULE.ContractError("lease mismatch")
            ):
                with self.assertRaises(MODULE.ContractError):
                    MODULE.release(args)


class BindingIndexTests(unittest.TestCase):
    """The state repo comes from the binding, not from the agent's cwd.

    A checkout leased in repo A is invisible to an agent whose cwd sits in repo B,
    so every lease lookup keyed on cwd resolved zero holders there: the mutation
    guard fell silent and `subagent-exit` no-opped.
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name).resolve()
        self.state = root / "state"
        self.repo_a = root / "repo-a"
        self.repo_b = root / "repo-b"
        self.leased = self.repo_a / "leased"
        for path in (self.state, self.repo_b, self.leased):
            path.mkdir(parents=True)
        self.item = {
            "branch": "writer/leased",
            "path": str(self.leased),
            "kind": "worktree",
            "vars": {
                "actor": "writer-actor",
                "lease": "lease-a",
                "context": "ctx-1",
                "runtime-bindings": json.dumps([{"context": "ctx-1", "handle": "handle-1"}]),
                "resource": "demo-1",
            },
        }
        self.issue = {
            "id": "demo-1",
            "status": "in_progress",
            "assignee": "writer-actor",
            "metadata": {"repo": str(self.repo_a)},
        }
        self.env = {"XDG_STATE_HOME": str(self.state)}

    def tearDown(self) -> None:
        self.temp.cleanup()

    def index_entry(self, repo: Path | None = None) -> None:
        with patch.dict(os.environ, self.env):
            MODULE.record_binding_repo("ctx-1", "handle-1", repo or self.repo_a, "demo-1")

    def indexed_keys(self) -> list[str]:
        with patch.dict(os.environ, self.env):
            return sorted(MODULE.read_binding_index())

    def inventory_by_repo(self, repo, **kwargs):
        return [self.item] if Path(repo).resolve() == self.repo_a else []

    def invoke_hook(
        self, payload: dict, *, issue: dict | None = None, bead_error: Exception | None = None
    ) -> str:
        stdout = io.StringIO()
        completed = subprocess.CompletedProcess([], 0, "", "")
        bead = (
            {"side_effect": bead_error} if bead_error else {"return_value": issue or self.issue}
        )
        with (
            patch.object(MODULE, "wt_inventory", side_effect=self.inventory_by_repo),
            patch.object(MODULE, "one_bead", **bead),
            patch.object(MODULE.shutil, "which", return_value="/usr/bin/wt"),
            patch.object(MODULE.subprocess, "run", return_value=completed),
            patch.object(sys, "stdin", io.StringIO(json.dumps(payload))),
            patch.object(sys, "stdout", stdout),
            patch.dict(os.environ, self.env, clear=True),
        ):
            self.assertEqual(MODULE.hook(), 0)
        return stdout.getvalue()

    def bash_payload(self, cwd: Path, command: str) -> dict:
        return {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "agent_id": "ctx-1",
            "cwd": str(cwd),
            "tool_input": {"command": command},
        }

    def test_a_lease_in_another_repo_still_governs_this_call(self) -> None:
        self.index_entry()
        decision = json.loads(
            self.invoke_hook(self.bash_payload(self.repo_b, f"cd -- {self.repo_b} && echo hi"))
        )["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn(str(self.leased), decision["permissionDecisionReason"])

    def test_the_holder_reaches_its_own_checkout_from_a_foreign_cwd(self) -> None:
        self.index_entry()
        self.assertEqual(
            self.invoke_hook(self.bash_payload(self.repo_b, f"cd -- {self.leased} && echo hi")),
            "",
        )

    def test_an_entry_the_bead_contradicts_is_denied(self) -> None:
        self.index_entry()
        reason = json.loads(
            self.invoke_hook(
                self.bash_payload(self.repo_b, f"cd -- {self.leased} && echo hi"),
                issue={**self.issue, "metadata": {"repo": str(self.repo_b)}},
            )
        )["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn(str(self.repo_a), reason)
        self.assertIn(str(self.repo_b), reason)

    def test_an_entry_whose_bead_carries_no_repo_is_denied(self) -> None:
        """An unstamped bead is readable and declines to confirm, so it is not stale.

        This branch shares its raise with the mismatch above, so without its own test
        either one reads as covered by the other.
        """
        self.index_entry()
        reason = json.loads(
            self.invoke_hook(
                self.bash_payload(self.repo_b, f"cd -- {self.leased} && echo hi"),
                issue={**self.issue, "metadata": {}},
            )
        )["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("metadata.repo is None", reason)
        self.assertEqual(self.indexed_keys(), ["ctx-1", "handle-1"])

    def test_an_entry_naming_a_deleted_directory_falls_back_and_is_pruned(self) -> None:
        """A vanished checkout is not the redirect attempt the test above denies.

        Denying it blocked every mutation and continuation for the context, in any
        repository, until someone hand-edited the index.
        """
        gone = self.repo_a / "gone"
        gone.mkdir()
        self.index_entry(gone)
        gone.rmdir()
        self.assertEqual(
            self.invoke_hook(self.bash_payload(self.repo_a, f"cd -- {self.leased} && echo hi")),
            "",
        )
        self.assertEqual(self.indexed_keys(), [])

    def test_an_entry_whose_bead_cannot_be_read_falls_back_and_is_pruned(self) -> None:
        """A closed, deleted, or unreachable bead is stale, not a redirect.

        Ephemeral wisps are deleted on close, and `bd` missing from PATH or an
        unopenable database reads the same way, so denying here blocked every
        mutation and continuation for the identifier.
        """
        self.index_entry()
        self.assertEqual(
            self.invoke_hook(
                self.bash_payload(self.repo_a, f"cd -- {self.leased} && echo hi"),
                bead_error=MODULE.ContractError("bd show demo-1 --json: issue not found"),
            ),
            "",
        )
        self.assertEqual(self.indexed_keys(), [])

    def test_a_missing_entry_falls_back_to_the_cwd_repo(self) -> None:
        decision = json.loads(
            self.invoke_hook(self.bash_payload(self.repo_a, f"cd -- {self.repo_a} && echo hi"))
        )["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertEqual(self.indexed_keys(), [])

    def test_a_cleared_environment_cannot_reach_the_developers_index(self) -> None:
        """No test may write the real `~/.local/state/worktrunk-writer/contexts.json`.

        The hook tests clear the environment to prove the guard needs no writer
        variables, which also dropped XDG_STATE_HOME and sent every index read and
        write to the developer's live state.
        """
        real = Path.home() / ".local" / "state" / MODULE.CONTEXT_INDEX_RELATIVE
        with cleared_env():
            self.assertNotEqual(MODULE.context_index_path(), real)
            self.assertEqual(MODULE.context_index_path().parents[1], Path(STATE_HOME.name))

    def test_a_malformed_entry_is_ignored(self) -> None:
        with patch.dict(os.environ, self.env):
            path = MODULE.context_index_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"ctx-1": {"bead": "demo-1"}}))
            self.assertEqual(MODULE.read_binding_index(), {})
            self.assertIsNone(MODULE.indexed_state_repo("ctx-1"))

    def exit_hook(self, cwd: Path, *, stale: bool) -> tuple[list[str], list[str]]:
        stamped: list[str] = []
        cleared: list[str] = []
        payload = {"agent_type": "domain-specialist", "agent_id": "ctx-1", "cwd": str(cwd)}
        with (
            patch.object(MODULE, "run", return_value=SimpleNamespace(stdout=str(cwd), stderr="")),
            patch.object(MODULE, "wt_inventory", side_effect=self.inventory_by_repo),
            patch.object(MODULE, "one_bead", return_value=self.issue),
            patch.object(MODULE, "stale_binding", return_value=stale),
            patch.object(MODULE, "set_var", side_effect=lambda r, b, k, v: stamped.append(k)),
            patch.object(MODULE, "clear_var", side_effect=lambda r, b, k: cleared.append(k)),
            patch("sys.stdin", io.StringIO(json.dumps(payload))),
            patch.dict(os.environ, self.env),
        ):
            self.assertEqual(MODULE.subagent_exit(), 0)
        return stamped, cleared

    def test_exit_clears_a_binding_recorded_in_another_repo(self) -> None:
        self.index_entry()
        stamped, cleared = self.exit_hook(self.repo_b, stale=True)
        self.assertEqual(stamped, ["exited"])
        self.assertEqual(sorted(cleared), ["context", "contexts", "runtime-bindings"])
        self.assertEqual(self.indexed_keys(), [])

    def test_exit_keeps_the_entry_for_a_resumable_actor(self) -> None:
        self.index_entry()
        stamped, cleared = self.exit_hook(self.repo_b, stale=False)
        self.assertEqual((stamped, cleared), (["exited"], []))
        self.assertEqual(self.indexed_keys(), ["ctx-1", "handle-1"])

    def test_release_removes_the_entry(self) -> None:
        self.index_entry()
        args = SimpleNamespace(
            repo=str(self.repo_a), path=str(self.leased), actor="writer-actor", lease="lease-a"
        )
        with (
            patch.object(MODULE, "wt_inventory", return_value=[self.item]),
            patch.object(MODULE, "validate", return_value={"status": "valid"}),
            patch.object(MODULE, "clear_var"),
            patch.dict(os.environ, self.env),
        ):
            self.assertEqual(MODULE.release(args)["status"], "released")
        self.assertEqual(self.indexed_keys(), [])

    def test_release_still_requires_the_matching_actor_and_lease(self) -> None:
        self.index_entry()
        args = SimpleNamespace(
            repo=str(self.repo_a), path=str(self.leased), actor="writer-actor", lease="wrong"
        )
        with (
            patch.object(MODULE, "wt_inventory", return_value=[self.item]),
            patch.object(MODULE, "validate", side_effect=MODULE.ContractError("lease mismatch")),
            patch.dict(os.environ, self.env),
        ):
            with self.assertRaises(MODULE.ContractError):
                MODULE.release(args)
        self.assertEqual(self.indexed_keys(), ["ctx-1", "handle-1"])

    def test_bind_stamps_the_repo_on_the_bead_and_indexes_it(self) -> None:
        args = SimpleNamespace(
            repo=str(self.repo_a),
            path=str(self.leased),
            actor="writer-actor",
            lease="lease-a",
            handle="handle-1",
            context=None,
            ack="WAIT context=ctx-1",
            bead=None,
            resource="demo-1",
        )
        with (
            patch.object(MODULE, "wt_inventory", return_value=[self.item]),
            patch.object(MODULE, "validate", return_value={"status": "valid"}),
            patch.object(MODULE, "beads_active", return_value=True),
            patch.object(MODULE, "assert_activation_resource_available"),
            patch.object(MODULE, "set_var"),
            patch.object(MODULE, "run") as command,
            patch.dict(os.environ, self.env),
        ):
            self.assertEqual(MODULE.bind(args)["status"], "bound")
        argv = command.call_args.args[0]
        self.assertEqual(json.loads(argv[-1])["repo"], str(self.repo_a))
        with patch.dict(os.environ, self.env):
            self.assertEqual(
                MODULE.read_binding_index()["ctx-1"],
                {
                    "repo": str(self.repo_a),
                    "bead": "demo-1",
                    "context": "ctx-1",
                    "handle": "handle-1",
                },
            )


class SubprocessTimeoutTests(unittest.TestCase):
    def test_every_subprocess_run_call_bounds_its_child(self) -> None:
        """A call site with no timeout hangs the verb forever on a wedged child."""
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        unbounded = [
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and getattr(node.func.value, "id", None) == "subprocess"
            and not any(keyword.arg == "timeout" for keyword in node.keywords)
        ]
        self.assertEqual(unbounded, [], f"subprocess.run without timeout at lines {unbounded}")

    def test_a_wedged_child_raises_the_contract_error(self) -> None:
        expired = subprocess.TimeoutExpired(["wt", "list"], MODULE.SUBPROCESS_TIMEOUT_SECONDS)
        with patch.object(MODULE.subprocess, "run", side_effect=expired):
            with self.assertRaises(MODULE.ContractError) as caught:
                MODULE.run(["wt", "list"])
        message = str(caught.exception)
        self.assertIn("wt list", message)
        self.assertIn(str(MODULE.SUBPROCESS_TIMEOUT_SECONDS), message)

    def test_a_wedged_beads_probe_reports_inactive_beads(self) -> None:
        expired = subprocess.TimeoutExpired(["bd", "where"], MODULE.SUBPROCESS_TIMEOUT_SECONDS)
        with (
            patch.object(MODULE.shutil, "which", return_value="/usr/bin/bd"),
            patch.object(MODULE.subprocess, "run", side_effect=expired),
        ):
            with self.assertRaises(MODULE.ContractError):
                MODULE.beads_active(Path("/tmp/repo"))

    def test_a_wedged_git_probe_does_not_crash_the_hook(self) -> None:
        """The hook must answer through its deny channel, never a traceback."""
        expired = subprocess.TimeoutExpired(["git", "rev-parse"], 30)
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "agent_id": "claude-agent-1",
            "cwd": "/tmp",
            "tool_input": {"command": "git status"},
        }
        stdout = io.StringIO()
        with (
            patch.object(MODULE.shutil, "which", return_value="/usr/bin/wt"),
            patch.object(MODULE.subprocess, "run", side_effect=expired),
            patch.object(sys, "stdin", io.StringIO(json.dumps(payload))),
            patch.object(sys, "stdout", stdout),
            cleared_env(),
        ):
            self.assertEqual(MODULE.hook(), 0)
        decision = json.loads(stdout.getvalue())["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("30s", decision["permissionDecisionReason"])

    def test_a_wedged_git_probe_leaves_an_unrelated_caller_alone(self) -> None:
        """Outside the writer protocol the hook stays inert, wedged child or not."""
        expired = subprocess.TimeoutExpired(["git", "rev-parse"], 30)
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "cwd": "/tmp",
            "tool_input": {"command": "git status"},
        }
        stdout = io.StringIO()
        with (
            patch.object(MODULE.shutil, "which", return_value="/usr/bin/wt"),
            patch.object(MODULE.subprocess, "run", side_effect=expired),
            patch.object(sys, "stdin", io.StringIO(json.dumps(payload))),
            patch.object(sys, "stdout", stdout),
            cleared_env(),
        ):
            self.assertEqual(MODULE.hook(), 0)
        self.assertEqual(stdout.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
