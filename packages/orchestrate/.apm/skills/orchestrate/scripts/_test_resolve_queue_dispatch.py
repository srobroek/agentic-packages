#!/usr/bin/env python3
"""Self-tests for resolve-queue-dispatch.py (stdlib unittest, no deps)."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RESOLVER = os.path.join(HERE, "resolve-queue-dispatch.py")
SPEC = importlib.util.spec_from_file_location("queue_dispatch", RESOLVER)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def dispatch(**overrides):
    pull_request = {
        "repository": "owner/repo",
        "number": 42,
        "title": "Ready change",
        "headSha": "a" * 40,
        "baseRef": "main",
        "labels": ["priority:high"],
        "priority": 1,
        "draft": False,
        "mergeable": True,
        "checks": "pass",
        "createdAt": "2026-07-21T00:00:00Z",
        "updatedAt": "2026-07-21T01:00:00Z",
        "state": "active",
        "activeSince": "2026-07-21T01:00:01Z",
    }
    pull_request.update(overrides)
    return {"type": "dispatch", "pullRequest": pull_request}


def node(identifier="orc-run.1", **metadata):
    values = {
        "repo": "owner/repo",
        "pr": 42,
        "head_sha": "a" * 40,
        "branch": "coder/t1",
        "base_sha": "b" * 40,
    }
    values.update(metadata)
    return {
        "id": identifier,
        "status": "in_progress",
        "labels": ["orc-node", "state:approved"],
        "metadata": values,
    }


class ResolveQueueDispatchTest(unittest.TestCase):
    def test_resolves_exact_approved_node(self):
        result = MODULE.resolve(dispatch(), [node()])
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["node"], "orc-run.1")
        self.assertEqual(result["dispatchKey"], f"owner/repo#42@{'a' * 40}")
        self.assertEqual(
            result["requiredMetadata"],
            {
                "queue_dispatch": f"owner/repo#42@{'a' * 40}",
                "queue_dispatch_pending": f"owner/repo#42@{'a' * 40}",
            },
        )

    def test_marks_acknowledged_dispatch_as_duplicate(self):
        key = f"owner/repo#42@{'a' * 40}"
        result = MODULE.resolve(
            dispatch(), [node(queue_dispatch=key, queue_dispatch_ack=key)]
        )
        self.assertEqual(result["status"], "duplicate")

    def test_replays_unacknowledged_dispatch_after_crash(self):
        key = f"owner/repo#42@{'a' * 40}"
        initial = MODULE.resolve(dispatch(), [node()])
        pending_after_pre_send_crash = MODULE.resolve(
            dispatch(), [node(queue_dispatch=key, queue_dispatch_pending=key)]
        )
        sent_before_ack_crash = MODULE.resolve(
            dispatch(),
            [
                node(
                    queue_dispatch=key,
                    queue_dispatch_pending=key,
                    queue_dispatch_sent=key,
                )
            ],
        )
        acknowledged = MODULE.resolve(
            dispatch(),
            [
                node(
                    queue_dispatch=key,
                    queue_dispatch_pending=key,
                    queue_dispatch_sent=key,
                    queue_dispatch_ack=key,
                )
            ],
        )

        self.assertEqual(initial["status"], "resolved")
        self.assertEqual(pending_after_pre_send_crash["status"], "replay")
        self.assertEqual(pending_after_pre_send_crash["deliveryState"], "pending")
        self.assertEqual(pending_after_pre_send_crash["requiredMetadata"], {})
        self.assertEqual(sent_before_ack_crash["status"], "replay")
        self.assertEqual(sent_before_ack_crash["deliveryState"], "sent")
        self.assertEqual(acknowledged["status"], "duplicate")

    def test_untracked_migration_is_normalized_before_gatekeeper_handoff(self):
        key = f"owner/repo#42@{'a' * 40}"
        migration_node = node(queue_dispatch=key)

        reconstructed = MODULE.replay_unacknowledged([migration_node])[0]
        migration_node["metadata"].update(reconstructed["requiredMetadata"])
        normalized = MODULE.resolve(dispatch(), [migration_node])

        self.assertEqual(reconstructed["deliveryState"], "untracked")
        self.assertEqual(
            reconstructed["requiredMetadata"], {"queue_dispatch_pending": key}
        )
        self.assertEqual(normalized["status"], "replay")
        self.assertEqual(normalized["deliveryState"], "pending")
        self.assertEqual(normalized["requiredMetadata"], {})
        self.assertEqual(
            migration_node["metadata"]["queue_dispatch_pending"],
            normalized["dispatchKey"],
        )

    def test_resume_scan_reconstructs_only_unacknowledged_handoffs(self):
        key = f"owner/repo#42@{'a' * 40}"
        pending = node("orc-run.2", queue_dispatch=key, queue_dispatch_pending=key)
        sent = node(
            "orc-run.1",
            queue_dispatch=key,
            queue_dispatch_pending=key,
            queue_dispatch_sent=key,
        )
        acknowledged = node(
            "orc-run.3",
            queue_dispatch=key,
            queue_dispatch_pending=key,
            queue_dispatch_sent=key,
            queue_dispatch_ack=key,
        )

        result = MODULE.replay_unacknowledged([pending, acknowledged, sent, node()])

        self.assertEqual([item["node"] for item in result], ["orc-run.1", "orc-run.2"])
        self.assertEqual(
            [item["deliveryState"] for item in result], ["sent", "pending"]
        )

    def test_rejects_stale_head(self):
        with self.assertRaisesRegex(MODULE.ResolutionError, "found 0"):
            MODULE.resolve(dispatch(headSha="c" * 40), [node()])

    def test_rejects_non_ready_dispatch(self):
        with self.assertRaisesRegex(MODULE.ContractError, "checks must be pass"):
            MODULE.resolve(dispatch(checks="fail"), [node()])

    def test_rejects_ambiguous_approved_nodes(self):
        with self.assertRaisesRegex(MODULE.ResolutionError, "found 2"):
            MODULE.resolve(dispatch(), [node(), node("orc-run.2")])

    def test_rejects_node_without_git_anchors(self):
        with self.assertRaisesRegex(MODULE.ResolutionError, "metadata.branch"):
            MODULE.resolve(dispatch(), [node(branch=None)])

    def test_ignores_watcher_control_record(self):
        result = MODULE.resolve({"type": "watcher-active"}, [node()])
        self.assertEqual(result, {"status": "ignored", "recordType": "watcher-active"})

    def test_cli_accepts_bd_envelope(self):
        with tempfile.TemporaryDirectory() as directory:
            nodes_path = os.path.join(directory, "nodes.json")
            with open(nodes_path, "w", encoding="utf-8") as handle:
                json.dump({"schema_version": 1, "data": [node()]}, handle)
            process = subprocess.run(
                [sys.executable, RESOLVER, "--nodes-file", nodes_path],
                input=json.dumps(dispatch()),
                capture_output=True,
                text=True,
            )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["status"], "resolved")

    def test_cli_replays_without_watcher_input(self):
        key = f"owner/repo#42@{'a' * 40}"
        with tempfile.TemporaryDirectory() as directory:
            nodes_path = os.path.join(directory, "nodes.json")
            with open(nodes_path, "w", encoding="utf-8") as handle:
                json.dump(
                    [node(queue_dispatch=key, queue_dispatch_pending=key)], handle
                )
            process = subprocess.run(
                [
                    sys.executable,
                    RESOLVER,
                    "--nodes-file",
                    nodes_path,
                    "--replay-unacknowledged",
                ],
                capture_output=True,
                text=True,
            )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(
            json.loads(process.stdout)["dispatches"][0]["status"], "replay"
        )


if __name__ == "__main__":
    unittest.main()
