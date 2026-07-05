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
        [sys.executable, MSG_LINT], input=body, capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout


class MsgLintTest(unittest.TestCase):
    def test_valid_reported_accepted(self):
        code, out = lint("REPORTED t3\nbranch: coder/t3\ncommits: abc123\nverify: green\n")
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

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

    def test_line1_must_be_exactly_verb_and_node(self):
        code, out = lint("REVIEW t3  verdict: changes  items: 2\n")
        self.assertEqual(code, 1)
        self.assertIn("line 1", out)


if __name__ == "__main__":
    unittest.main()
