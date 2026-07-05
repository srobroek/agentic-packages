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

    def test_rejects_bad_event(self):
        run(self.dir, "add", "--event", "bogus", expect=2)

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
