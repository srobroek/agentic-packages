#!/usr/bin/env python3
"""Self-tests for consistency-check.py (stdlib unittest, no deps)."""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GRAPH = os.path.join(HERE, "graph.py")
LEDGER = os.path.join(HERE, "ledger.py")
CHECK = os.path.join(HERE, "consistency-check.py")


def _run(script, store, *args, expect=0):
    proc = subprocess.run(
        [sys.executable, script, "--store", store, *args],
        capture_output=True, text=True,
    )
    assert proc.returncode == expect, f"{args} -> {proc.returncode}\n{proc.stderr}"
    return proc.stdout


def _check(store, expect):
    proc = subprocess.run(
        [sys.executable, CHECK, "--store", store], capture_output=True, text=True,
    )
    assert proc.returncode == expect, f"consistency-check -> {proc.returncode}\n{proc.stdout}{proc.stderr}"
    return proc.stdout


class ConsistencyCheckTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        _run(GRAPH, self.dir, "init", "--run-id", "run-cc")

    def test_consistent_store_passes(self):
        _run(GRAPH, self.dir, "add-node", "t1", "--scope", "src/a/**")
        _run(GRAPH, self.dir, "set-state", "t1", "working")
        _run(LEDGER, self.dir, "add", "--event", "assign", "--actor", "main", "--node", "t1")
        out = _check(self.dir, 0)
        self.assertIn("consistent", out)

    def test_merged_node_without_event_fails(self):
        _run(GRAPH, self.dir, "add-node", "t1", "--scope", "src/a/**")
        _run(GRAPH, self.dir, "set-state", "t1", "merged")
        out = _check(self.dir, 1)
        self.assertIn("orphan-graph", out)
        self.assertIn("t1", out)

    def test_ledger_event_for_unknown_node_flagged(self):
        _run(LEDGER, self.dir, "add", "--event", "assign", "--actor", "main", "--node", "ghost")
        out = _check(self.dir, 1)
        self.assertIn("orphan-ledger", out)
        self.assertIn("ghost", out)


if __name__ == "__main__":
    unittest.main()
