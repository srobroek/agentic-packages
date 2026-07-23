#!/usr/bin/env python3
"""Self-tests for resolve-queue-event.py (stdlib unittest, no deps)."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RESOLVER = os.path.join(HERE, "resolve-queue-event.py")
SPEC = importlib.util.spec_from_file_location("queue_event", RESOLVER)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def pull_request(**overrides):
    value = {
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
    value.update(overrides)
    return value


def dispatch(**overrides):
    return {"type": "dispatch", "pullRequest": pull_request(**overrides)}


def lifecycle(transition="updated", **overrides):
    return {
        "type": "pr-lifecycle",
        "transition": transition,
        "source": "webhook",
        "lifecycleKey": f"owner/repo#42#{transition}#opaque",
        "pullRequest": pull_request(**overrides),
        "deliveryId": "delivery-1",
        "webhookAction": "synchronize",
    }


def merge_bead(identifier="merge-42", **metadata):
    values = {
        "repo": "owner/repo",
        "pr": 42,
        "branch": "feature/ready-change",
        "base_sha": "b" * 40,
    }
    values.update(metadata)
    return {
        "id": identifier,
        "status": "open",
        "labels": ["agent:integrator"],
        "metadata": values,
    }


class ResolveQueueEventTest(unittest.TestCase):
    def test_resolves_lifecycle_to_exact_merge_bead(self):
        result = MODULE.resolve(lifecycle("failed", checks="fail"), [merge_bead()])

        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["bead"], "merge-42")
        self.assertEqual(result["eventType"], "pr-lifecycle")
        self.assertEqual(result["transition"], "failed")
        self.assertEqual(result["eventKey"], "lifecycle:owner/repo#42#failed#opaque")
        self.assertEqual(
            result["requiredMetadata"],
            {
                "shepherd_event": "lifecycle:owner/repo#42#failed#opaque",
                "shepherd_event_head": "a" * 40,
                "shepherd_event_pending": "lifecycle:owner/repo#42#failed#opaque",
                "shepherd_event_transition": "failed",
                "shepherd_event_type": "pr-lifecycle",
            },
        )

    def test_resolves_ready_dispatch(self):
        result = MODULE.resolve(dispatch(), [merge_bead(head_sha="a" * 40)])

        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["eventType"], "dispatch")
        self.assertEqual(result["transition"], "ready")
        self.assertEqual(result["priority"], 1)

    def test_rejects_non_ready_dispatch(self):
        with self.assertRaisesRegex(MODULE.ContractError, "checks must be pass"):
            MODULE.resolve(dispatch(checks="fail"), [merge_bead()])

    def test_marks_acknowledged_event_as_duplicate(self):
        key = "lifecycle:owner/repo#42#updated#opaque"
        result = MODULE.resolve(
            lifecycle(),
            [merge_bead(shepherd_event=key, shepherd_event_ack=key)],
        )

        self.assertEqual(result["status"], "duplicate")
        self.assertEqual(result["deliveryState"], "ack")
        self.assertEqual(result["requiredMetadata"], {})

    def test_receipt_sequence_survives_crashes_at_each_boundary(self):
        event = lifecycle()
        bead = merge_bead()

        initial = MODULE.resolve(event, [bead])
        bead["metadata"].update(initial["requiredMetadata"])
        pending = MODULE.resolve(event, [bead])
        bead["metadata"]["shepherd_event_sent"] = initial["eventKey"]
        sent = MODULE.resolve(event, [bead])
        bead["metadata"]["shepherd_event_ack"] = initial["eventKey"]
        acknowledged = MODULE.resolve(event, [bead])

        self.assertEqual(initial["status"], "resolved")
        self.assertEqual(pending["deliveryState"], "pending")
        self.assertEqual(sent["deliveryState"], "sent")
        self.assertEqual(acknowledged["status"], "duplicate")

    def test_replays_sent_event_after_crash(self):
        key = "lifecycle:owner/repo#42#updated#opaque"
        bead = merge_bead(
            shepherd_event=key,
            shepherd_event_type="pr-lifecycle",
            shepherd_event_transition="updated",
            shepherd_event_head="a" * 40,
            shepherd_event_pending=key,
            shepherd_event_sent=key,
        )

        replay = MODULE.replay_unacknowledged([bead])

        self.assertEqual(len(replay), 1)
        self.assertEqual(replay[0]["status"], "replay")
        self.assertEqual(replay[0]["deliveryState"], "sent")
        self.assertEqual(replay[0]["requiredMetadata"], {})

    def test_normalizes_legacy_event_before_replay(self):
        key = f"dispatch:owner/repo#42@{'a' * 40}"
        bead = merge_bead(
            shepherd_event=key,
            shepherd_event_type="dispatch",
            shepherd_event_transition="ready",
            shepherd_event_head="a" * 40,
        )

        replay = MODULE.replay_unacknowledged([bead])[0]

        self.assertEqual(replay["deliveryState"], "untracked")
        self.assertEqual(replay["requiredMetadata"], {"shepherd_event_pending": key})

    def test_ignores_orchestrator_owned_bead(self):
        result = MODULE.resolve(
            lifecycle(), [merge_bead(integration_owner="orchestrate")]
        )

        self.assertEqual(result["status"], "ignored")
        self.assertEqual(result["reason"], "orchestrate-owned")

    def test_orchestrator_ownership_wins_over_duplicate_generic_bead(self):
        result = MODULE.resolve(
            lifecycle(),
            [
                merge_bead("orchestrate-merge", integration_owner="orchestrate"),
                merge_bead("generic-merge"),
            ],
        )

        self.assertEqual(result["status"], "ignored")
        self.assertEqual(result["reason"], "orchestrate-owned")

    def test_rejects_ambiguous_merge_beads(self):
        with self.assertRaisesRegex(MODULE.ResolutionError, "found 2"):
            MODULE.resolve(lifecycle(), [merge_bead(), merge_bead("merge-43")])

    def test_boolean_metadata_pr_never_matches_integer_pr(self):
        with self.assertRaisesRegex(MODULE.ResolutionError, "found 0"):
            MODULE.resolve(lifecycle(number=1), [merge_bead(pr=True)])

    def test_rejects_stale_dispatch_head_when_bead_has_anchor(self):
        with self.assertRaisesRegex(MODULE.ResolutionError, "head does not match"):
            MODULE.resolve(dispatch(), [merge_bead(head_sha="c" * 40)])

    def test_replay_rejects_corrupt_dispatch_identity(self):
        bead = merge_bead(
            shepherd_event="dispatch:owner/repo#99@deadbeef",
            shepherd_event_type="dispatch",
            shepherd_event_transition="ready",
            shepherd_event_head="a" * 40,
        )

        with self.assertRaisesRegex(MODULE.ResolutionError, "identity"):
            MODULE.replay_unacknowledged([bead])

    def test_replay_rejects_duplicate_merge_bead_ownership(self):
        key = "lifecycle:owner/repo#42#updated#opaque"
        metadata = {
            "shepherd_event": key,
            "shepherd_event_type": "pr-lifecycle",
            "shepherd_event_transition": "updated",
            "shepherd_event_head": "a" * 40,
            "shepherd_event_pending": key,
        }

        acknowledged = dict(metadata)
        acknowledged["shepherd_event_ack"] = key
        with self.assertRaisesRegex(MODULE.ResolutionError, "duplicate"):
            MODULE.replay_unacknowledged(
                [
                    merge_bead("merge-1", **acknowledged),
                    merge_bead("merge-2", **metadata),
                ]
            )

    def test_closed_reconciliation_lifecycle_is_valid(self):
        event = lifecycle(
            "closed",
            activeSince=None,
            checks="pending",
            mergeable=None,
            state="closed",
        )
        event["source"] = "reconciliation"

        result = MODULE.resolve(event, [merge_bead()])

        self.assertEqual(result["transition"], "closed")

    def test_rejects_impossible_lifecycle_combinations(self):
        failed_green = lifecycle("failed", checks="pass")
        merged_from_polling = lifecycle(
            "merged", activeSince=None, state="closed", checks="pending"
        )
        merged_from_polling["source"] = "reconciliation"
        unsigned_webhook = lifecycle()
        del unsigned_webhook["deliveryId"]

        cases = [
            (failed_green, "failed lifecycle checks must be fail"),
            (merged_from_polling, "merged lifecycle must come from webhook"),
            (unsigned_webhook, "deliveryId"),
        ]
        for event, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(MODULE.ContractError, expected):
                    MODULE.resolve(event, [merge_bead()])

    def test_ignores_control_record(self):
        result = MODULE.resolve({"type": "watcher-active"}, [merge_bead()])
        self.assertEqual(result, {"status": "ignored", "recordType": "watcher-active"})

    def test_surfaces_watcher_error_as_explicit_fallback(self):
        result = MODULE.resolve(
            {
                "type": "reconcile-error",
                "repository": "owner/repo",
                "message": "rate limited",
            },
            [merge_bead()],
        )

        self.assertEqual(result["status"], "fallback")
        self.assertEqual(result["action"], "gate-check-and-pass")

    def test_resolves_target_at_end_of_large_snapshot(self):
        unrelated = [
            merge_bead(f"merge-{number}", repo="owner/other", pr=number + 100)
            for number in range(2000)
        ]

        result = MODULE.resolve(lifecycle(), unrelated + [merge_bead()])

        self.assertEqual(result["bead"], "merge-42")

    def test_cli_accepts_bd_envelope(self):
        with tempfile.TemporaryDirectory() as directory:
            beads_path = os.path.join(directory, "beads.json")
            with open(beads_path, "w", encoding="utf-8") as handle:
                json.dump({"schema_version": 1, "data": [merge_bead()]}, handle)
            process = subprocess.run(
                [sys.executable, RESOLVER, "--beads-file", beads_path],
                input=json.dumps(lifecycle()),
                capture_output=True,
                text=True,
            )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["status"], "resolved")


if __name__ == "__main__":
    unittest.main()
