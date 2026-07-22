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


def lifecycle(transition="updated", **overrides):
    pull_request = dispatch(**overrides)["pullRequest"]
    return {
        "type": "pr-lifecycle",
        "transition": transition,
        "source": "webhook",
        "lifecycleKey": f"owner/repo#42#{transition}#opaque",
        "pullRequest": pull_request,
        "deliveryId": "delivery-1",
        "webhookAction": "synchronize",
    }


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
        sent_key = f"owner/repo#43@{'a' * 40}"
        pending = node("orc-run.2", queue_dispatch=key, queue_dispatch_pending=key)
        sent = node(
            "orc-run.1",
            pr=43,
            queue_dispatch=sent_key,
            queue_dispatch_pending=sent_key,
            queue_dispatch_sent=sent_key,
        )
        acknowledged = node(
            "orc-run.3",
            pr=44,
            queue_dispatch=f"owner/repo#44@{'a' * 40}",
            queue_dispatch_pending=f"owner/repo#44@{'a' * 40}",
            queue_dispatch_sent=f"owner/repo#44@{'a' * 40}",
            queue_dispatch_ack=f"owner/repo#44@{'a' * 40}",
        )

        result = MODULE.replay_unacknowledged(
            [pending, acknowledged, sent, node(pr=45)]
        )

        self.assertEqual([item["node"] for item in result], ["orc-run.1", "orc-run.2"])
        self.assertEqual(
            [item["deliveryState"] for item in result], ["sent", "pending"]
        )

    def test_rejects_stale_head(self):
        with self.assertRaisesRegex(MODULE.UnmatchedError, "no approved node"):
            MODULE.resolve(dispatch(headSha="c" * 40), [node()])

    def test_rejects_non_ready_dispatch(self):
        with self.assertRaisesRegex(MODULE.ContractError, "checks must be pass"):
            MODULE.resolve(dispatch(checks="fail"), [node()])

    def test_rejects_ambiguous_approved_nodes(self):
        with self.assertRaisesRegex(MODULE.ResolutionError, "found 2"):
            MODULE.resolve(dispatch(), [node(), node("orc-run.2")])

    def test_boolean_metadata_pr_never_matches_integer_pr(self):
        with self.assertRaisesRegex(MODULE.UnmatchedError, "no approved node"):
            MODULE.resolve(dispatch(number=1), [node(pr=True)])

    def test_rejects_node_without_git_anchors(self):
        with self.assertRaisesRegex(MODULE.ResolutionError, "metadata.branch"):
            MODULE.resolve(dispatch(), [node(branch=None)])

    def test_rejects_mismatched_dispatch_receipt(self):
        key = f"owner/repo#42@{'a' * 40}"
        with self.assertRaisesRegex(MODULE.ResolutionError, "receipt mismatch"):
            MODULE.resolve(
                dispatch(),
                [
                    node(
                        queue_dispatch=key,
                        queue_dispatch_pending=f"owner/repo#42@{'c' * 40}",
                    )
                ],
            )

    def test_rejects_new_dispatch_while_previous_receipt_is_unacknowledged(self):
        old_key = f"owner/repo#42@{'c' * 40}"
        with self.assertRaisesRegex(MODULE.ResolutionError, "cannot replace"):
            MODULE.resolve(
                dispatch(),
                [
                    node(
                        queue_dispatch=old_key,
                        queue_dispatch_pending=old_key,
                    )
                ],
            )

    def test_new_dispatch_replays_after_completed_prior_lineage(self):
        old_key = f"owner/repo#42@{'a' * 40}"
        new_key = f"owner/repo#42@{'c' * 40}"
        tracked = node(
            head_sha="c" * 40,
            queue_dispatch=old_key,
            queue_dispatch_pending=old_key,
            queue_dispatch_sent=old_key,
            queue_dispatch_ack=old_key,
        )

        admitted = MODULE.resolve(dispatch(headSha="c" * 40), [tracked])
        tracked["metadata"].update(admitted["requiredMetadata"])
        pending = MODULE.resolve(dispatch(headSha="c" * 40), [tracked])
        replayed = MODULE.replay_unacknowledged([tracked])
        tracked["metadata"]["queue_dispatch_sent"] = new_key
        sent = MODULE.resolve(dispatch(headSha="c" * 40), [tracked])

        self.assertEqual(admitted["status"], "resolved")
        self.assertEqual(pending["deliveryState"], "pending")
        self.assertEqual(replayed[0]["dispatchKey"], new_key)
        self.assertEqual(replayed[0]["deliveryState"], "pending")
        self.assertEqual(sent["deliveryState"], "sent")

    def test_resolves_lifecycle_for_exact_orchestrate_node(self):
        result = MODULE.resolve(lifecycle("failed", checks="fail"), [node()])

        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["eventType"], "pr-lifecycle")
        self.assertEqual(result["node"], "orc-run.1")
        self.assertEqual(result["transition"], "failed")
        self.assertTrue(result["wakeGatekeeper"])
        self.assertEqual(
            result["requiredMetadata"],
            {
                "queue_lifecycle": "owner/repo#42#failed#opaque",
                "queue_lifecycle_head": "a" * 40,
                "queue_lifecycle_pending": "owner/repo#42#failed#opaque",
                "queue_lifecycle_transition": "failed",
            },
        )

    def test_records_nonterminal_lifecycle_without_waking_unapproved_node(self):
        unapproved = node()
        unapproved["labels"] = ["orc-node", "state:reported"]

        result = MODULE.resolve(lifecycle("updated"), [unapproved])

        self.assertEqual(result["status"], "resolved")
        self.assertFalse(result["wakeGatekeeper"])
        self.assertEqual(
            result["requiredMetadata"]["queue_lifecycle_ack"],
            "owner/repo#42#updated#opaque",
        )

    def test_marks_acknowledged_lifecycle_as_duplicate(self):
        key = "owner/repo#42#updated#opaque"
        result = MODULE.resolve(
            lifecycle(),
            [node(queue_lifecycle=key, queue_lifecycle_ack=key)],
        )

        self.assertEqual(result["status"], "duplicate")
        self.assertEqual(result["eventType"], "pr-lifecycle")
        self.assertEqual(result["deliveryState"], "ack")

    def test_lifecycle_receipts_survive_each_crash_boundary(self):
        event = lifecycle("failed", checks="fail")
        tracked = node()

        initial = MODULE.resolve(event, [tracked])
        tracked["metadata"].update(initial["requiredMetadata"])
        pending = MODULE.resolve(event, [tracked])
        tracked["metadata"]["queue_lifecycle_sent"] = initial["lifecycleKey"]
        sent = MODULE.resolve(event, [tracked])
        tracked["metadata"]["queue_lifecycle_ack"] = initial["lifecycleKey"]
        acknowledged = MODULE.resolve(event, [tracked])

        self.assertEqual(initial["status"], "resolved")
        self.assertEqual(pending["deliveryState"], "pending")
        self.assertEqual(sent["deliveryState"], "sent")
        self.assertEqual(acknowledged["status"], "duplicate")

    def test_replays_unacknowledged_lifecycle_after_crash(self):
        key = "owner/repo#42#failed#opaque"
        pending = node(
            queue_lifecycle=key,
            queue_lifecycle_head="a" * 40,
            queue_lifecycle_pending=key,
            queue_lifecycle_transition="failed",
        )

        result = MODULE.replay_unacknowledged_lifecycles([pending])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "replay")
        self.assertEqual(result[0]["deliveryState"], "pending")
        self.assertTrue(result[0]["wakeGatekeeper"])

    def test_normalizes_unapproved_nonterminal_lifecycle_to_ack(self):
        key = "owner/repo#42#updated#opaque"
        unapproved = node(
            queue_lifecycle=key,
            queue_lifecycle_head="a" * 40,
            queue_lifecycle_transition="updated",
        )
        unapproved["labels"] = ["orc-node", "state:reported"]

        result = MODULE.replay_unacknowledged_lifecycles([unapproved])[0]

        self.assertFalse(result["wakeGatekeeper"])
        self.assertEqual(result["requiredMetadata"], {"queue_lifecycle_ack": key})

    def test_lifecycle_head_change_is_observed_not_trusted(self):
        result = MODULE.resolve(lifecycle(headSha="c" * 40), [node()])

        self.assertTrue(result["headChanged"])
        self.assertEqual(result["headSha"], "c" * 40)
        self.assertNotIn("dispatchKey", result)

    def test_rejects_mismatched_lifecycle_receipt(self):
        key = "owner/repo#42#failed#opaque"
        with self.assertRaisesRegex(MODULE.ResolutionError, "receipt mismatch"):
            MODULE.resolve(
                lifecycle("failed", checks="fail"),
                [
                    node(
                        queue_lifecycle=key,
                        queue_lifecycle_pending="owner/repo#42#other#opaque",
                    )
                ],
            )

    def test_rejects_new_lifecycle_while_previous_receipt_is_unacknowledged(self):
        old_key = "owner/repo#42#updated#old"
        with self.assertRaisesRegex(MODULE.ResolutionError, "cannot replace"):
            MODULE.resolve(
                lifecycle("failed", checks="fail"),
                [
                    node(
                        queue_lifecycle=old_key,
                        queue_lifecycle_head="a" * 40,
                        queue_lifecycle_pending=old_key,
                        queue_lifecycle_transition="updated",
                    )
                ],
            )

    def test_new_lifecycle_replays_after_completed_prior_lineage(self):
        old_key = "owner/repo#42#updated#old"
        new_key = "owner/repo#42#failed#opaque"
        tracked = node(
            queue_lifecycle=old_key,
            queue_lifecycle_head="a" * 40,
            queue_lifecycle_pending=old_key,
            queue_lifecycle_sent=old_key,
            queue_lifecycle_ack=old_key,
            queue_lifecycle_transition="updated",
        )
        event = lifecycle("failed", checks="fail")

        admitted = MODULE.resolve(event, [tracked])
        tracked["metadata"].update(admitted["requiredMetadata"])
        pending = MODULE.resolve(event, [tracked])
        replayed = MODULE.replay_unacknowledged_lifecycles([tracked])
        tracked["metadata"]["queue_lifecycle_sent"] = new_key
        sent = MODULE.resolve(event, [tracked])

        self.assertEqual(admitted["status"], "resolved")
        self.assertEqual(pending["deliveryState"], "pending")
        self.assertEqual(replayed[0]["lifecycleKey"], new_key)
        self.assertEqual(replayed[0]["deliveryState"], "pending")
        self.assertEqual(sent["deliveryState"], "sent")

    def test_accepts_reconciled_external_merge_for_proof_only(self):
        event = lifecycle("merged", state="closed")
        event["source"] = "reconciliation"

        result = MODULE.resolve(event, [node()])

        self.assertEqual(result["transition"], "merged")
        self.assertTrue(result["wakeGatekeeper"])
        self.assertNotIn("dispatchKey", result)

    def test_rejects_malformed_lifecycle(self):
        with self.assertRaisesRegex(MODULE.ContractError, "transition"):
            MODULE.resolve(lifecycle("unknown"), [node()])

    def test_rejects_impossible_lifecycle_combination(self):
        with self.assertRaisesRegex(
            MODULE.ContractError, "failed lifecycle checks must be fail"
        ):
            MODULE.resolve(lifecycle("failed", checks="pass"), [node()])

    def test_surfaces_watcher_error_as_explicit_fallback(self):
        result = MODULE.resolve(
            {"type": "webhook-error", "message": "bad signature"}, [node()]
        )

        self.assertEqual(result["status"], "fallback")
        self.assertEqual(result["action"], "gate-check-and-pass")

    def test_dispatch_replay_rejects_duplicate_pr_ownership(self):
        key = f"owner/repo#42@{'a' * 40}"
        with self.assertRaisesRegex(MODULE.ResolutionError, "duplicate"):
            MODULE.replay_unacknowledged(
                [
                    node(
                        "orc-run.1",
                        queue_dispatch=key,
                        queue_dispatch_ack=key,
                    ),
                    node("orc-run.2", queue_dispatch=key),
                ]
            )

    def test_lifecycle_replay_rejects_duplicate_pr_ownership(self):
        key = "owner/repo#42#failed#opaque"
        metadata = {
            "queue_lifecycle": key,
            "queue_lifecycle_head": "a" * 40,
            "queue_lifecycle_pending": key,
            "queue_lifecycle_transition": "failed",
        }
        with self.assertRaisesRegex(MODULE.ResolutionError, "duplicate"):
            MODULE.replay_unacknowledged_lifecycles(
                [node("orc-run.1", **metadata), node("orc-run.2", **metadata)]
            )

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

    def test_cli_distinguishes_unmatched_from_ambiguous_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            nodes_path = os.path.join(directory, "nodes.json")
            with open(nodes_path, "w", encoding="utf-8") as handle:
                json.dump([], handle)
            unmatched = subprocess.run(
                [sys.executable, RESOLVER, "--nodes-file", nodes_path],
                input=json.dumps(dispatch()),
                capture_output=True,
                text=True,
            )
            with open(nodes_path, "w", encoding="utf-8") as handle:
                json.dump([node(), node("orc-run.2")], handle)
            ambiguous = subprocess.run(
                [sys.executable, RESOLVER, "--nodes-file", nodes_path],
                input=json.dumps(dispatch()),
                capture_output=True,
                text=True,
            )

        self.assertEqual(unmatched.returncode, 2)
        self.assertIn("unmatched watcher record", unmatched.stderr)
        self.assertEqual(ambiguous.returncode, 3)
        self.assertIn("unresolved watcher record", ambiguous.stderr)

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

    def test_cli_replays_dispatches_and_lifecycles(self):
        dispatch_key = f"owner/repo#42@{'a' * 40}"
        lifecycle_key = "owner/repo#43#failed#opaque"
        lifecycle_node = node(
            "orc-run.2",
            pr=43,
            queue_lifecycle=lifecycle_key,
            queue_lifecycle_head="c" * 40,
            queue_lifecycle_pending=lifecycle_key,
            queue_lifecycle_transition="failed",
        )
        with tempfile.TemporaryDirectory() as directory:
            nodes_path = os.path.join(directory, "nodes.json")
            with open(nodes_path, "w", encoding="utf-8") as handle:
                json.dump(
                    [
                        node(
                            queue_dispatch=dispatch_key,
                            queue_dispatch_pending=dispatch_key,
                        ),
                        lifecycle_node,
                    ],
                    handle,
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
        output = json.loads(process.stdout)
        self.assertEqual(len(output["dispatches"]), 1)
        self.assertEqual(len(output["lifecycles"]), 1)


if __name__ == "__main__":
    unittest.main()
