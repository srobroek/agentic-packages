#!/usr/bin/env python3
"""Self-tests for pull-worker.py (stdlib unittest, no dependencies)."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "pull-worker.py")
AGENT = os.path.join(HERE, "../../../agents/workflow-pull-worker.agent.md")
SPEC = importlib.util.spec_from_file_location("pull_worker", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def contract(**overrides):
    values = {
        "epic": "orc-run",
        "queue": "python",
        "task_kind": "code",
        "evidence": "git",
        "actor": "pull-python-1",
        "capabilities": ("python",),
    }
    values.update(overrides)
    return MODULE.QueueContract(**values)


def issue(**overrides):
    value = {
        "id": "orc-run.2",
        "title": "Implement worker",
        "status": "in_progress",
        "priority": 2,
        "issue_type": "task",
        "assignee": "pull-python-1",
        "parent": "orc-run",
        "labels": ["agent:python", "cap:python", "orc-node"],
        "metadata": {
            "scope": ["src/**"],
            "execution_kind": "code",
            "execution_capabilities": ["python"],
            "execution_evidence": "git",
        },
    }
    value.update(overrides)
    return value


def completed(stdout="[]", stderr="", returncode=0):
    return subprocess.CompletedProcess(["bd"], returncode, stdout=stdout, stderr=stderr)


class PullWorkerUnitTest(unittest.TestCase):
    def test_builds_one_filtered_atomic_beads_1_1_claim(self):
        command = MODULE.build_claim_command("bd", contract())

        self.assertEqual(command[:4], ["bd", "--actor", "pull-python-1", "ready"])
        self.assertIn("--unassigned", command)
        self.assertIn("--claim", command)
        self.assertIn("--json", command)
        self.assertNotIn("list", command)
        self.assertEqual(
            [
                command[index + 1]
                for index, item in enumerate(command)
                if item == "--label"
            ],
            ["orc-node", "agent:python"],
        )
        self.assertEqual(
            [
                command[index + 1]
                for index, item in enumerate(command)
                if item == "--metadata-field"
            ],
            ["execution_kind=code", "execution_evidence=git"],
        )
        self.assertEqual(command[command.index("--sort") + 1], "priority")

    def test_empty_queue_or_lost_race_is_successful_no_work(self):
        result = MODULE.run_claim(
            contract(), runner=lambda *_args, **_kwargs: completed()
        )

        self.assertEqual(result["status"], "NO_WORK")
        self.assertEqual(result["queue"], "agent:python")

    def test_claimed_git_work_requires_commit(self):
        result = MODULE.run_claim(
            contract(),
            runner=lambda *_args, **_kwargs: completed(json.dumps([issue()])),
        )

        self.assertEqual(result["status"], "CLAIMED")
        self.assertEqual(result["bead"], "orc-run.2")
        self.assertEqual(
            result["completion"],
            {"commit_required": True, "output_ref_required": False},
        )

    def test_non_git_work_requires_output_ref_without_commit(self):
        non_git = contract(
            queue="research",
            task_kind="research",
            evidence="artifact",
            actor="pull-research-1",
            capabilities=("research",),
        )
        claimed = issue(
            assignee="pull-research-1",
            labels=["agent:research", "cap:research", "orc-node"],
            metadata={
                "scope": ["artifact:/tmp/run/findings.json"],
                "execution_kind": "research",
                "execution_capabilities": ["research"],
                "execution_evidence": "artifact",
            },
        )

        result = MODULE.run_claim(
            non_git,
            runner=lambda *_args, **_kwargs: completed(json.dumps([claimed])),
        )

        self.assertEqual(
            result["completion"],
            {"commit_required": False, "output_ref_required": True},
        )

    def test_malformed_or_missing_json_requires_reconciliation(self):
        for stdout in ("", "not json", "{}"):
            with self.subTest(stdout=stdout):
                with self.assertRaises(MODULE.PullWorkerError) as caught:
                    MODULE.run_claim(
                        contract(),
                        runner=lambda *_args, **_kwargs: completed(stdout),
                    )
                self.assertEqual(caught.exception.kind, "beads_json")
                self.assertTrue(caught.exception.reconcile_required)

    def test_missing_routing_metadata_is_refused(self):
        with self.assertRaises(MODULE.PullWorkerError) as caught:
            MODULE.run_claim(
                contract(),
                runner=lambda *_args, **_kwargs: completed(
                    json.dumps([issue(metadata={})])
                ),
            )

        self.assertEqual(caught.exception.kind, "routing_envelope")
        self.assertTrue(caught.exception.reconcile_required)

    def test_beads_failure_is_reported_without_retry(self):
        with self.assertRaises(MODULE.PullWorkerError) as caught:
            MODULE.run_claim(
                contract(),
                runner=lambda *_args, **_kwargs: completed(
                    stderr="database unavailable", returncode=1
                ),
            )

        self.assertEqual(caught.exception.kind, "beads_command")
        self.assertEqual(caught.exception.exit_code, 3)
        self.assertTrue(caught.exception.reconcile_required)

    def test_timeout_and_interrupt_stop_without_a_retry(self):
        def timeout(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(["bd"], 1)

        with self.assertRaises(MODULE.PullWorkerError) as timed_out:
            MODULE.run_claim(contract(), runner=timeout, timeout=1)
        self.assertEqual(timed_out.exception.kind, "beads_timeout")
        self.assertTrue(timed_out.exception.reconcile_required)

        def interrupt(*_args, **_kwargs):
            raise KeyboardInterrupt

        with self.assertRaises(MODULE.StopRequested):
            MODULE.run_claim(contract(), runner=interrupt)

    def test_cli_interrupt_is_deterministic_stopped_output(self):
        argv = [
            "--epic",
            "orc-run",
            "--queue",
            "python",
            "--task-kind",
            "code",
            "--evidence",
            "git",
            "--actor",
            "pull-python-1",
        ]
        stderr = io.StringIO()

        with mock.patch.object(MODULE, "run_claim", side_effect=MODULE.StopRequested):
            with redirect_stderr(stderr):
                exit_code = MODULE.main(argv)

        self.assertEqual(exit_code, 130)
        self.assertEqual(json.loads(stderr.getvalue())["status"], "STOPPED")

    def test_lost_claim_never_overwrites_another_actor(self):
        claimed = issue(assignee="specialist-1")

        with self.assertRaises(MODULE.PullWorkerError) as caught:
            MODULE.run_claim(
                contract(),
                runner=lambda *_args, **_kwargs: completed(json.dumps([claimed])),
            )

        self.assertEqual(caught.exception.kind, "claim_lost")
        self.assertIn("specialist-1", str(caught.exception))

    def test_specialised_route_is_refused(self):
        metadata = issue()["metadata"] | {
            "execution_dispatch": "specialist",
            "execution_agent": "python-pro",
        }

        with self.assertRaises(MODULE.PullWorkerError) as caught:
            MODULE.run_claim(
                contract(),
                runner=lambda *_args, **_kwargs: completed(
                    json.dumps([issue(metadata=metadata)])
                ),
            )

        self.assertEqual(caught.exception.kind, "routing_envelope")
        self.assertIn("specialised", str(caught.exception))

    def test_capability_mismatch_is_refused(self):
        with self.assertRaises(MODULE.PullWorkerError) as caught:
            MODULE.run_claim(
                contract(capabilities=()),
                runner=lambda *_args, **_kwargs: completed(json.dumps([issue()])),
            )

        self.assertIn("python", str(caught.exception))

    def test_subprocess_receives_arguments_without_a_shell(self):
        seen = {}

        def runner(command, **kwargs):
            seen["command"] = command
            seen["kwargs"] = kwargs
            return completed()

        MODULE.run_claim(contract(), runner=runner)

        self.assertIsInstance(seen["command"], list)
        self.assertNotIn("shell", seen["kwargs"])
        self.assertEqual(seen["kwargs"]["timeout"], 15.0)
        self.assertEqual(seen["kwargs"]["env"]["BEADS_ACTOR"], "pull-python-1")

    def test_agent_contract_requires_holder_death_evidence(self):
        with open(AGENT, encoding="utf-8") as handle:
            agent = handle.read()

        self.assertIn("Only the coordinator may clear and requeue a dead claim", agent)
        self.assertIn("after recording holder-death evidence", agent)

    def test_agent_contract_reports_every_error_and_stop(self):
        with open(AGENT, encoding="utf-8") as handle:
            agent = handle.read()

        self.assertIn("Always send a", agent)
        self.assertIn("status=<ERROR|STOPPED>", agent)
        self.assertIn("claim=<none|bead|unknown>", agent)


STUB = r"""
#!/usr/bin/env python3
import json
import os
import sys

path = os.environ["PULL_WORKER_STUB_STATE"]
with open(path, encoding="utf-8") as handle:
    state = json.load(handle)
args = sys.argv[1:]

def values(flag):
    return [args[index + 1] for index, item in enumerate(args) if item == flag]

required_labels = set(values("--label"))
metadata_filters = dict(value.split("=", 1) for value in values("--metadata-field"))
actor = args[args.index("--actor") + 1]
parent = args[args.index("--parent") + 1]
matches = []
for candidate in state:
    ancestors = candidate.get("ancestors", [])
    if candidate.get("parent") != parent and parent not in ancestors:
        continue
    if not required_labels.issubset(set(candidate.get("labels", []))):
        continue
    if "--unassigned" in args and candidate.get("assignee"):
        continue
    if candidate.get("status") != "open":
        continue
    metadata = candidate.get("metadata", {})
    if any(metadata.get(key) != value for key, value in metadata_filters.items()):
        continue
    matches.append(candidate)

matches.sort(key=lambda item: (item["priority"], item["id"]))
if matches:
    matches[0]["assignee"] = actor
    matches[0]["status"] = "in_progress"
with open(path, "w", encoding="utf-8") as handle:
    json.dump(state, handle, sort_keys=True)
print(json.dumps(matches[:1], sort_keys=True))
"""


class PullWorkerCliTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.stub = os.path.join(self.directory.name, "bd-stub")
        with open(self.stub, "w", encoding="utf-8") as handle:
            handle.write(textwrap.dedent(STUB).lstrip())
        os.chmod(self.stub, os.stat(self.stub).st_mode | stat.S_IXUSR)
        self.state = os.path.join(self.directory.name, "state.json")

    def run_cli(self, state, *extra):
        with open(self.state, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        command = [
            sys.executable,
            SCRIPT,
            "--bd",
            self.stub,
            "--epic",
            "orc-run",
            "--queue",
            "python",
            "--task-kind",
            "code",
            "--evidence",
            "git",
            "--actor",
            "pull-python-1",
            "--capability",
            "python",
            *extra,
        ]
        with mock.patch.dict(os.environ, {"PULL_WORKER_STUB_STATE": self.state}):
            process = subprocess.run(command, capture_output=True, text=True)
        with open(self.state, encoding="utf-8") as handle:
            final_state = json.load(handle)
        return process, final_state

    def candidate(self, identifier, priority, **overrides):
        value = issue(
            id=identifier,
            priority=priority,
            status="open",
            assignee=None,
        )
        value.update(overrides)
        return value

    def test_incompatible_higher_priority_work_stays_unclaimed(self):
        assigned = self.candidate("orc-run.1", 0, assignee="exact-actor")
        specialist = self.candidate(
            "orc-run.2",
            0,
            labels=["agent:specialist", "cap:python", "orc-node"],
        )
        wrong_kind = self.candidate(
            "orc-run.3",
            0,
            metadata=issue()["metadata"] | {"execution_kind": "research"},
        )
        compatible = self.candidate("orc-run.4", 2)

        process, state = self.run_cli([assigned, specialist, wrong_kind, compatible])

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["bead"], "orc-run.4")
        self.assertEqual(
            [(item["id"], item["status"], item.get("assignee")) for item in state],
            [
                ("orc-run.1", "open", "exact-actor"),
                ("orc-run.2", "open", None),
                ("orc-run.3", "open", None),
                ("orc-run.4", "in_progress", "pull-python-1"),
            ],
        )

    def test_nested_compatible_descendant_is_claimed_and_accepted(self):
        nested = self.candidate(
            "orc-run.1.1",
            1,
            parent="orc-run.1",
            ancestors=["orc-run"],
        )

        process, state = self.run_cli([nested])

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["bead"], "orc-run.1.1")
        self.assertEqual(state[0]["status"], "in_progress")
        self.assertEqual(state[0]["assignee"], "pull-python-1")

    def test_ambiguous_live_claim_preserves_persisted_owner_state_and_anchors(self):
        metadata = issue()["metadata"] | {
            "branch": "worker/live",
            "worktree": "/tmp/live-worktree",
            "base_sha": "a" * 40,
        }
        live_claim = self.candidate(
            "orc-run.1",
            0,
            status="in_progress",
            assignee="worker-live",
            metadata=metadata,
        )

        process, state = self.run_cli([live_claim])

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["status"], "NO_WORK")
        self.assertEqual(state[0]["status"], "in_progress")
        self.assertEqual(state[0]["assignee"], "worker-live")
        self.assertEqual(state[0]["metadata"]["branch"], "worker/live")
        self.assertEqual(state[0]["metadata"]["worktree"], "/tmp/live-worktree")
        self.assertEqual(state[0]["metadata"]["base_sha"], "a" * 40)

    def test_requeued_recovery_claim_preserves_persisted_git_anchors(self):
        metadata = issue()["metadata"] | {
            "branch": "worker/recovery",
            "worktree": "/tmp/recovery-worktree",
            "base_sha": "b" * 40,
        }
        recovery = self.candidate("orc-run.1", 1, metadata=metadata)

        process, state = self.run_cli([recovery])

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["status"], "CLAIMED")
        self.assertEqual(state[0]["status"], "in_progress")
        self.assertEqual(state[0]["assignee"], "pull-python-1")
        self.assertEqual(state[0]["metadata"]["branch"], "worker/recovery")
        self.assertEqual(state[0]["metadata"]["worktree"], "/tmp/recovery-worktree")
        self.assertEqual(state[0]["metadata"]["base_sha"], "b" * 40)

    def test_cli_no_work_json_is_deterministic_and_successful(self):
        first, _ = self.run_cli([])
        second, _ = self.run_cli([])

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(json.loads(first.stdout)["status"], "NO_WORK")

    def test_equal_priority_tie_is_left_to_beads_ready_order(self):
        first = self.candidate("orc-run.2", 1)
        second = self.candidate("orc-run.3", 1)

        process, state = self.run_cli([second, first])

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["bead"], "orc-run.2")
        self.assertEqual(
            [item["id"] for item in state if item["status"] == "in_progress"],
            ["orc-run.2"],
        )

    def test_invalid_slug_cannot_inject_a_command(self):
        marker = os.path.join(self.directory.name, "injected")

        process, state = self.run_cli([], "--queue", f"python;touch-{marker}")

        self.assertEqual(process.returncode, 2)
        self.assertEqual(state, [])
        self.assertFalse(os.path.exists(marker))
        self.assertEqual(json.loads(process.stderr)["kind"], "arguments")


if __name__ == "__main__":
    unittest.main()
