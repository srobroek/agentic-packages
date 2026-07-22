#!/usr/bin/env python3
"""Self-tests for msg-lint.py (stdlib unittest, no deps)."""

import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MSG_LINT = os.path.join(HERE, "msg-lint.py")


def lint(body: str):
    proc = subprocess.run(
        [sys.executable, MSG_LINT],
        input=body,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout


def watcher_approve(**overrides: str) -> str:
    fields = {
        "branch": "coder/t3",
        "base": "main @ abc123",
        "source": "release-queue-watch",
        "repo": "owner/repo",
        "pr": "42",
        "head": "a" * 40,
        "dispatch": f"owner/repo#42@{'a' * 40}",
    }
    fields.update(overrides)
    return "APPROVE t3\n" + "".join(
        f"{field}: {value}\n" for field, value in fields.items()
    )


def watcher_lifecycle(**overrides: str) -> str:
    fields = {
        "branch": "coder/t3",
        "base": "main @ abc123",
        "source": "release-queue-watch-lifecycle",
        "repo": "owner/repo",
        "pr": "42",
        "head": "a" * 40,
        "transition": "failed",
        "lifecycle": "owner/repo#42#failed#opaque",
    }
    fields.update(overrides)
    return "APPROVE t3\n" + "".join(
        f"{field}: {value}\n" for field, value in fields.items()
    )


class MsgLintTest(unittest.TestCase):
    def test_valid_reported_accepted(self):
        code, out = lint(
            "REPORTED t3\nbranch: coder/t3\ncommits: abc123\nverify: green\n"
        )
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_reported_accepts_commit_pr_and_non_git_evidence(self):
        messages = (
            "REPORTED t3\nbranch: coder/t3\ncommit: abc123\nverify: green\n",
            "REPORTED t3\nbranch: coder/t3\npr: 42\nverify: green\n",
            "REPORTED t3\noutput_ref: /tmp/report.json\nverify: green\n",
        )
        for body in messages:
            with self.subTest(body=body):
                code, out = lint(body)
                self.assertEqual(code, 0, out)

    def test_reported_requires_complete_evidence_shape(self):
        cases = (
            (
                "REPORTED t3\nbranch: coder/t3\nverify: green\n",
                "requires commit, commits, or pr",
            ),
            (
                "REPORTED t3\ncommit: abc123\nverify: green\n",
                "requires branch",
            ),
            (
                "REPORTED t3\nverify: green\n",
                "requires git evidence or non-git output_ref",
            ),
        )
        for body, expected in cases:
            with self.subTest(body=body):
                code, out = lint(body)
                self.assertEqual(code, 1)
                self.assertIn(expected, out)

    def test_reported_rejects_hybrid_evidence(self):
        code, out = lint(
            "REPORTED t3\nbranch: coder/t3\ncommits: abc123\n"
            "output_ref: /tmp/report.json\nverify: green\n"
        )
        self.assertEqual(code, 1)
        self.assertIn("must not mix git evidence", out)

    def test_no_work_activation_is_explicit(self):
        code, out = lint(
            "NO_WORK queue:generic\nepic: orc-7f3a\n"
            "queue: agent:generic\nreason: no-compatible-work\n"
        )
        self.assertEqual(code, 0, out)

        code, out = lint(
            "NO_WORK queue:generic\nepic: orc-7f3a\n"
            "queue: agent:generic\nreason: empty\n"
        )
        self.assertEqual(code, 1)
        self.assertIn("must be one of", out)

        fields = {
            "epic": "orc-7f3a",
            "queue": "agent:generic",
            "reason": "no-compatible-work",
        }
        for empty_field in fields:
            with self.subTest(empty_field=empty_field):
                empty_fields = {**fields, empty_field: ""}
                body = "NO_WORK queue:generic\n" + "".join(
                    f"{field}: {value}\n" for field, value in empty_fields.items()
                )
                code, out = lint(body)
                self.assertEqual(code, 1)
                self.assertIn(f"empty field: {empty_field}", out)

    def test_missing_field_rejected(self):
        code, out = lint("REPORTED t3\nbranch: coder/t3\ncommits: abc123\n")
        self.assertEqual(code, 1)
        self.assertIn("missing field: verify", out)

    def test_bad_verb_rejected(self):
        code, out = lint("RULE t9\ndecision: pick a\n")
        self.assertEqual(code, 1)
        self.assertIn("unknown verb", out)

    def test_prose_blob_rejected(self):
        body = (
            "ASSIGN t1\n"
            "this is a long prose line with no label at all\n"
            "and another prose line still with no label here\n"
            "and a third prose line to push the run past two\n"
        )
        code, out = lint(body)
        self.assertEqual(code, 1)
        self.assertIn("prose smell", out)

    def test_enum_field_value_checked(self):
        code, out = lint("BLOCKED t3\nkind: something\nneed: help\n")
        self.assertEqual(code, 1)
        self.assertIn("must be one of", out)

    def test_dismiss_has_no_required_fields(self):
        code, out = lint("DISMISS t3\n")
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_watcher_approve_handoff_accepted(self):
        code, out = lint(watcher_approve())
        self.assertEqual(code, 0, out)
        self.assertEqual(out, "")

    def test_regular_approve_keeps_minimal_contract(self):
        code, out = lint("APPROVE t3\nbranch: coder/t3\n")
        self.assertEqual(code, 0, out)

    def test_watcher_approve_requires_every_handoff_field(self):
        for missing in ("repo", "base", "pr", "head", "dispatch"):
            with self.subTest(missing=missing):
                body = "\n".join(
                    line
                    for line in watcher_approve().splitlines()
                    if not line.startswith(f"{missing}:")
                )
                code, out = lint(body)
                self.assertEqual(code, 1)
                self.assertIn(f"missing field: {missing}", out)

    def test_watcher_approve_rejects_malformed_identity(self):
        cases = {
            "repo": (watcher_approve(repo="owner"), "field repo must be OWNER/REPO"),
            "pr": (watcher_approve(pr="0"), "field pr must be a positive integer"),
            "head": (
                watcher_approve(head="not-a-sha"),
                "field head must be a hexadecimal Git object id",
            ),
            "dispatch": (
                watcher_approve(dispatch="owner/repo#42@wrong"),
                "field dispatch must equal repo#pr@head",
            ),
        }
        for name, (body, expected) in cases.items():
            with self.subTest(name=name):
                code, out = lint(body)
                self.assertEqual(code, 1)
                self.assertIn(expected, out)

    def test_watcher_lifecycle_handoff_accepted(self):
        code, out = lint(watcher_lifecycle())
        self.assertEqual(code, 0, out)

    def test_watcher_lifecycle_requires_receipt_fields(self):
        for missing in ("repo", "base", "pr", "head", "transition", "lifecycle"):
            with self.subTest(missing=missing):
                body = "\n".join(
                    line
                    for line in watcher_lifecycle().splitlines()
                    if not line.startswith(f"{missing}:")
                )
                code, out = lint(body)
                self.assertEqual(code, 1)
                self.assertIn(f"missing field: {missing}", out)

    def test_watcher_lifecycle_rejects_unknown_transition(self):
        code, out = lint(watcher_lifecycle(transition="surprised"))
        self.assertEqual(code, 1)
        self.assertIn("field transition", out)

    def test_line1_must_be_exactly_verb_and_node(self):
        code, out = lint("REVIEW t3  verdict: changes  items: 2\n")
        self.assertEqual(code, 1)
        self.assertIn("line 1", out)


if __name__ == "__main__":
    unittest.main()
