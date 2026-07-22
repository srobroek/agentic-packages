#!/usr/bin/env python3
"""Integration tests for thread-message.py against a temporary Beads database."""

from __future__ import annotations

import importlib.util
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
import unittest

HERE = Path(__file__).resolve().parent
THREAD_MESSAGE = HERE / "thread-message.py"


def load_module():
    spec = importlib.util.spec_from_file_location("thread_message", THREAD_MESSAGE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ThreadMessageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tempdir = tempfile.TemporaryDirectory(prefix="thread-message-")
        cls.repo = Path(cls.tempdir.name)
        subprocess.run(
            [
                "bd",
                "init",
                "--prefix",
                "tm",
                "--skip-hooks",
                "--skip-agents",
                "--non-interactive",
                "--role",
                "maintainer",
            ],
            cwd=cls.repo,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        cls.ids = itertools.count(1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tempdir.cleanup()

    def bd(self, *args: str, actor: str = "test-orchestrator"):
        env = os.environ.copy()
        env.update(
            {
                "BEADS_ACTOR": actor,
                "BD_JSON_ENVELOPE": "1",
                "BD_NO_PAGER": "1",
                "BD_NON_INTERACTIVE": "1",
            }
        )
        process = subprocess.run(
            ["bd", *args, "--json"],
            cwd=self.repo,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(process.returncode, 0, process.stderr or process.stdout)
        return json.loads(process.stdout)["data"]

    def helper(self, *args: str, bd: str = "bd"):
        process = subprocess.run(
            [sys.executable, str(THREAD_MESSAGE), "--bd", bd, *args],
            cwd=self.repo,
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
        payload = json.loads(process.stdout)
        self.assertNotIn("Traceback", process.stderr)
        self.assertEqual(payload["ok"], process.returncode == 0, process.stderr)
        return process.returncode, payload

    def bd_stub(self, name: str, data) -> str:
        envelope = json.dumps({"data": data, "schema_version": 1})
        stub = self.repo / name
        stub.write_text(
            f"#!/usr/bin/env python3\nprint({envelope!r})\n", encoding="utf-8"
        )
        stub.chmod(0o755)
        return str(stub)

    def run_and_work(self):
        number = next(self.ids)
        run = f"tm-run-{number}"
        self.bd("create", "--id", run, "--title", "Run", "--type", "epic")
        work = self.bd(
            "create",
            "--title",
            "Work",
            "--type",
            "task",
            "--parent",
            run,
        )["id"]
        return run, work

    def send(self, run: str, work: str, *, assignee: str = "recipient") -> str:
        code, payload = self.helper(
            "send",
            "--actor",
            "sender",
            "--assignee",
            assignee,
            "--run",
            run,
            "--bead",
            work,
            "--subject",
            "Root",
            "--body",
            "Root body",
        )
        self.assertEqual(code, 0, payload)
        return payload["data"]["message"]["id"]

    def reply(self, run: str, work: str, parent: str, subject: str = "Reply"):
        return self.helper(
            "reply",
            "--actor",
            "recipient",
            "--assignee",
            "sender",
            "--run",
            run,
            "--bead",
            work,
            "--parent",
            parent,
            "--subject",
            subject,
            "--body",
            f"{subject} body",
        )

    def error_code(self, result) -> str:
        code, payload = result
        self.assertEqual(code, 1, payload)
        return payload["error"]["code"]

    def test_root_reply_inbox_thread_and_acknowledge(self):
        run, work = self.run_and_work()
        root = self.send(run, work)
        code, reply_payload = self.reply(run, work, root)
        self.assertEqual(code, 0, reply_payload)
        reply_id = reply_payload["data"]["message"]["id"]

        code, inbox_payload = self.helper(
            "inbox", "--actor", "recipient", "--run", run, "--bead", work
        )
        self.assertEqual(code, 0, inbox_payload)
        self.assertEqual(
            [message["id"] for message in inbox_payload["data"]["messages"]], [root]
        )

        code, thread_payload = self.helper("show", "--message", reply_id, "--thread")
        self.assertEqual(code, 0, thread_payload)
        thread = thread_payload["data"]["thread"]
        self.assertEqual([message["id"] for message in thread], [root, reply_id])
        self.assertEqual(thread[0]["actor"], "sender")
        self.assertEqual(thread[1]["parent"], root)

        wrong_actor = self.helper(
            "acknowledge",
            "--actor",
            "intruder",
            "--run",
            run,
            "--bead",
            work,
            "--message",
            root,
        )
        self.assertEqual(self.error_code(wrong_actor), "recipient_mismatch")
        non_message = self.helper(
            "acknowledge",
            "--actor",
            "recipient",
            "--run",
            run,
            "--bead",
            work,
            "--message",
            work,
        )
        self.assertEqual(self.error_code(non_message), "parent_not_message")

        code, ack_payload = self.helper(
            "acknowledge",
            "--actor",
            "recipient",
            "--run",
            run,
            "--bead",
            work,
            "--message",
            root,
        )
        self.assertEqual(code, 0, ack_payload)
        self.assertFalse(ack_payload["data"]["already_closed"])
        self.assertEqual(ack_payload["data"]["work_bead"]["status"], "open")
        self.assertEqual(self.error_code(self.reply(run, work, root)), "message_closed")

        self.bd("close", work, "--reason", "work complete")

        code, duplicate = self.helper(
            "ack",
            "--actor",
            "recipient",
            "--run",
            run,
            "--bead",
            work,
            "--message",
            root,
        )
        self.assertEqual(code, 0, duplicate)
        self.assertTrue(duplicate["data"]["already_closed"])
        self.assertEqual(duplicate["data"]["work_bead"]["status"], "closed")

        code, thread_payload = self.helper("thread", "--message", reply_id)
        self.assertEqual(code, 0, thread_payload)
        self.assertEqual(
            [message["id"] for message in thread_payload["data"]["thread"]],
            [root, reply_id],
        )

        code, inbox_payload = self.helper(
            "inbox", "--actor", "sender", "--run", run, "--bead", work
        )
        self.assertEqual(code, 0, inbox_payload)
        self.assertEqual(
            [message["id"] for message in inbox_payload["data"]["messages"]],
            [reply_id],
        )

        send_after_close = self.helper(
            "send",
            "--actor",
            "sender",
            "--assignee",
            "recipient",
            "--run",
            run,
            "--bead",
            work,
            "--subject",
            "Late root",
            "--body",
            "Late root body",
        )
        self.assertEqual(self.error_code(send_after_close), "work_bead_closed")
        self.assertEqual(
            self.error_code(self.reply(run, work, reply_id, "Late reply")),
            "work_bead_closed",
        )

        code, reply_ack = self.helper(
            "acknowledge",
            "--actor",
            "sender",
            "--run",
            run,
            "--bead",
            work,
            "--message",
            reply_id,
        )
        self.assertEqual(code, 0, reply_ack)
        self.assertFalse(reply_ack["data"]["already_closed"])
        self.assertEqual(reply_ack["data"]["work_bead"]["status"], "closed")
        self.assertEqual(self.bd("show", f"--id={work}")[0]["status"], "closed")

    def test_concurrent_replies_form_deterministic_branches(self):
        run, work = self.run_and_work()
        root = self.send(run, work)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self.reply, run, work, root, f"Branch {number}")
                for number in (1, 2)
            ]
        replies = [future.result() for future in futures]
        self.assertTrue(all(code == 0 for code, _ in replies), replies)

        code, payload = self.helper("thread", "--message", root)
        self.assertEqual(code, 0, payload)
        thread = payload["data"]["thread"]
        self.assertEqual(len(thread), 3)
        self.assertEqual({message["parent"] for message in thread[1:]}, {root})

    def test_parent_and_thread_identity_failures(self):
        run, work = self.run_and_work()
        root = self.send(run, work)
        self.assertEqual(
            self.error_code(self.reply(run, work, "tm-missing-parent")),
            "parent_not_found",
        )
        self.assertEqual(
            self.error_code(self.reply(run, work, work)), "parent_not_message"
        )

        other_run, other_work = self.run_and_work()
        self.assertEqual(
            self.error_code(self.reply(other_run, other_work, root)), "run_mismatch"
        )
        sibling = self.bd(
            "create",
            "--title",
            "Sibling",
            "--type",
            "task",
            "--parent",
            run,
        )["id"]
        self.assertEqual(
            self.error_code(self.reply(run, sibling, root)), "bead_mismatch"
        )

        deleted = self.send(run, work)
        self.bd("delete", deleted, "--force")
        self.assertEqual(
            self.error_code(self.reply(run, work, deleted)), "parent_not_found"
        )

    def test_cycle_and_self_reference_are_rejected(self):
        run, work = self.run_and_work()
        root = self.send(run, work)
        _, first_payload = self.reply(run, work, root, "First")
        first = first_payload["data"]["message"]["id"]
        _, second_payload = self.reply(run, work, first, "Second")
        second = second_payload["data"]["message"]["id"]
        self.bd("dep", "remove", root, work)
        self.bd("dep", "add", root, second, "--type", "replies-to")
        self.assertEqual(
            self.error_code(self.helper("show", "--message", root, "--thread")),
            "thread_cycle",
        )

        module = load_module()
        with self.assertRaises(module.MessageError) as raised:
            module._replies_to(
                {
                    "id": "tm-wisp-self",
                    "dependencies": [
                        {
                            "id": "tm-wisp-self",
                            "dependency_type": "replies-to",
                        }
                    ],
                }
            )
        self.assertEqual(raised.exception.code, "self_reference")

    def test_unavailable_beads_and_malformed_json_are_safe(self):
        code, payload = self.helper(
            "inbox", "--actor", "recipient", bd="/missing/thread-message-bd"
        )
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"]["code"], "bd_unavailable")

        malformed = self.repo / "malformed-bd"
        malformed.write_text("#!/bin/sh\nprintf '{not-json\\n'\n", encoding="utf-8")
        malformed.chmod(0o755)
        code, payload = self.helper("inbox", "--actor", "recipient", bd=str(malformed))
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"]["code"], "invalid_bd_json")

    def test_parseable_malformed_bd_shapes_are_safe(self):
        list_stub = self.bd_stub("list-shape-bd", [[]])
        code, payload = self.helper("inbox", "--actor", "recipient", bd=list_stub)
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"]["code"], "invalid_bd_json")

        valid_metadata = {
            "actor": "sender",
            "assignee": "recipient",
            "bead": "tm-work-shape",
            "protocol": "replies-to",
            "run": "tm-run-shape",
        }
        base_message = {
            "assignee": "recipient",
            "created_by": "sender",
            "description": "Body",
            "id": "tm-wisp-shape",
            "issue_type": "message",
            "metadata": valid_metadata,
            "status": "open",
            "title": "Subject",
        }
        malformed_shapes = (
            {"metadata": []},
            {"metadata": {**valid_metadata, "protocol": []}},
            {"dependencies": {}},
            {"dependencies": [[]]},
            {"dependencies": [{"dependency_type": [], "id": "tm-work-shape"}]},
            {"dependencies": [{"dependency_type": "replies-to", "id": []}]},
        )
        for number, malformed_fields in enumerate(malformed_shapes):
            with self.subTest(malformed_fields=malformed_fields):
                issue = {**base_message, **malformed_fields}
                stub = self.bd_stub(f"show-shape-{number}-bd", [issue])
                code, payload = self.helper(
                    "show", "--message", "tm-wisp-shape", bd=stub
                )
                self.assertEqual(code, 1)
                self.assertEqual(payload["error"]["code"], "invalid_bd_json")

    def test_inbox_quarantines_invalid_message_metadata(self):
        self.bd(
            "create",
            "--title",
            "Legacy message",
            "--type",
            "message",
            "--assignee",
            "recipient",
            "--metadata",
            '{"protocol":"replies-to"}',
            "--ephemeral",
        )
        code, payload = self.helper("inbox", "--actor", "recipient")
        self.assertEqual(code, 0, payload)
        self.assertTrue(
            any(
                invalid["code"] == "invalid_message_metadata"
                for invalid in payload["data"]["invalid"]
            )
        )


if __name__ == "__main__":
    unittest.main()
