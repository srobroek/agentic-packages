#!/usr/bin/env python3
"""Self-tests for ledger.py (stdlib unittest, no deps)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "ledger.py")


def run(store, *args, expect=0):
    proc = subprocess.run(
        [sys.executable, LEDGER, "--store", store, *args],
        capture_output=True, text=True,
    )
    assert proc.returncode == expect, f"{args} -> {proc.returncode}\n{proc.stderr}"
    return proc.stdout


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def _lines(self):
        with open(os.path.join(self.dir, "ledger.jsonl"), encoding="utf-8") as fh:
            return [json.loads(x) for x in fh if x.strip()]

    def test_add_stamps_ts_seq_runid(self):
        run(self.dir, "add", "--event", "assign", "--node", "t1",
            "--actor", "main", "--run-id", "run-x")
        run(self.dir, "add", "--event", "reported", "--node", "t1", "--actor", "coder-t1")
        rows = self._lines()
        self.assertEqual([r["seq"] for r in rows], [1, 2])
        self.assertTrue(rows[0]["ts"].endswith("Z"))
        self.assertEqual(rows[1]["run_id"], "run-x")  # inherited

    def test_unknown_event_warns_but_still_writes(self):
        # canonical vocabulary is enforced with a warning, not a die -- a
        # mistyped/novel event must never break the append.
        proc = subprocess.run(
            [sys.executable, LEDGER, "--store", self.dir, "add", "--event", "bogus",
             "--actor", "main", "--node", "t9"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("warning", proc.stderr.lower())
        rows = self._lines()
        self.assertEqual(rows[0]["event"], "bogus")

    def test_relative_store_rejected(self):
        proc = subprocess.run(
            [sys.executable, LEDGER, "--store", "relative/store/path", "query"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("absolute", proc.stderr)

    def test_corrupted_trailing_line_does_not_break_reads(self):
        run(self.dir, "add", "--event", "assign", "--node", "t1", "--actor", "main")
        run(self.dir, "add", "--event", "reported", "--node", "t1", "--actor", "coder-t1")
        path = os.path.join(self.dir, "ledger.jsonl")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write('{"seq": 3, "event": "reported", "node": "t1"  garbage not json\n')
        proc = subprocess.run(
            [sys.executable, LEDGER, "--store", self.dir, "summary"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("t1", proc.stdout)
        self.assertIn("warning", proc.stderr.lower())
        self.assertIn("1", proc.stderr)  # one bad line skipped

    def test_worktree_flag_persisted(self):
        run(self.dir, "add", "--event", "assign", "--node", "t1", "--actor", "main",
            "--worktree", "/home/x/.claude/worktrees/t1")
        rec = self._lines()[0]
        self.assertEqual(rec["worktree"], "/home/x/.claude/worktrees/t1")

    def test_long_inline_text_truncated_in_row_but_full_in_artifact(self):
        long_text = "x" * 250
        run(self.dir, "add", "--event", "reported", "--node", "t1", "--actor", "coder-t1",
            "--output", long_text)
        rec = self._lines()[0]
        self.assertEqual(len(rec["output"]), 200)
        self.assertEqual(rec["output_ref"], "artifacts/0001-output.md")
        with open(os.path.join(self.dir, rec["output_ref"]), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), long_text)

    def test_artifacts_written_and_referenced(self):
        run(self.dir, "add", "--event", "reported", "--node", "t1", "--actor", "coder-t1",
            "--input", "the brief text", "--output", "the report text")
        rec = self._lines()[0]
        self.assertEqual(rec["input_ref"], "artifacts/0001-input.md")
        self.assertEqual(rec["output_ref"], "artifacts/0001-output.md")
        with open(os.path.join(self.dir, rec["output_ref"]), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "the report text")

    def test_query_filters(self):
        run(self.dir, "add", "--event", "assign", "--node", "t1", "--actor", "main")
        run(self.dir, "add", "--event", "review", "--node", "t1", "--actor", "reviewer-t1")
        run(self.dir, "add", "--event", "assign", "--node", "t2", "--actor", "main")
        out = run(self.dir, "query", "--node", "t1", "--json")
        rows = json.loads(out)
        self.assertEqual(len(rows), 2)
        out = run(self.dir, "query", "--event", "assign", "--json")
        self.assertEqual(len(json.loads(out)), 2)

    def test_issues_collects_all(self):
        run(self.dir, "add", "--event", "reported", "--node", "t1", "--actor", "coder-t1",
            "--issue", "sig change", "--unexpected", "legacy endpoint")
        out = run(self.dir, "issues", "--json")
        kinds = sorted(x["kind"] for x in json.loads(out))
        self.assertEqual(kinds, ["issues", "unexpected"])

    def test_summary_handles_missing_state(self):
        # a node whose events never set --state must not crash summary/table
        run(self.dir, "add", "--event", "assign", "--node", "t9", "--actor", "main")
        out = run(self.dir, "summary")
        self.assertIn("t9", out)
        run(self.dir, "query", "--node", "t9")  # table path also tolerates None

    def test_replay_and_summary(self):
        run(self.dir, "add", "--event", "assign", "--node", "t1", "--actor", "main",
            "--input", "do the thing")
        run(self.dir, "add", "--event", "reported", "--node", "t1", "--actor", "coder-t1",
            "--result", "green", "--commit", "abc123", "--state", "in_review")
        replay = run(self.dir, "replay", "--node", "t1")
        self.assertIn("do the thing", replay)
        self.assertIn("green", replay)
        self.assertIn("abc123", replay)
        summ = run(self.dir, "summary")
        self.assertIn("t1", summ)


if __name__ == "__main__":
    unittest.main()
