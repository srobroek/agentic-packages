#!/usr/bin/env python3
"""Self-tests for graph.py (stdlib unittest, no deps)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GRAPH = os.path.join(HERE, "graph.py")


def run(store, *args, expect=0):
    proc = subprocess.run(
        [sys.executable, GRAPH, "--store", store, *args],
        capture_output=True, text=True,
    )
    assert proc.returncode == expect, f"{args} -> {proc.returncode}\n{proc.stderr}"
    return proc.stdout


class GraphTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        run(self.dir, "init", "--run-id", "run-test")

    def test_ready_respects_deps_and_scope(self):
        run(self.dir, "add-node", "t1", "--scope", "src/a/**")
        run(self.dir, "add-node", "t2", "--scope", "src/b/**")
        run(self.dir, "add-node", "t3", "--scope", "src/c/**", "--dep", "t1")
        # t3 blocked on t1; t1 and t2 ready (disjoint scope)
        ready = run(self.dir, "ready").split()
        self.assertIn("t1", ready)
        self.assertIn("t2", ready)
        self.assertNotIn("t3", ready)
        # put t1 in flight -> still no t3, t2 stays ready (disjoint)
        run(self.dir, "set-state", "t1", "working")
        ready = run(self.dir, "ready").split()
        self.assertNotIn("t3", ready)
        # finish t1 -> t3 becomes ready
        run(self.dir, "set-state", "t1", "merged")
        ready = run(self.dir, "ready").split()
        self.assertIn("t3", ready)

    def test_scope_collision_blocks_ready(self):
        run(self.dir, "add-node", "a", "--scope", "src/auth/**")
        run(self.dir, "add-node", "b", "--scope", "src/auth/token/**")  # overlaps a
        run(self.dir, "set-state", "a", "working")
        ready = run(self.dir, "ready").split()
        self.assertNotIn("b", ready)  # b's scope overlaps in-flight a

    def test_validate_detects_cycle(self):
        run(self.dir, "add-node", "x", "--scope", "x/**")
        run(self.dir, "add-node", "y", "--scope", "y/**", "--dep", "x")
        run(self.dir, "add-edge", "y", "x")  # x now depends on y too -> cycle
        run(self.dir, "validate", expect=2)

    def test_validate_detects_scope_overlap_concurrent(self):
        run(self.dir, "add-node", "p", "--scope", "src/shared/**")
        run(self.dir, "add-node", "q", "--scope", "src/shared/util/**")  # concurrent + overlap
        run(self.dir, "validate", expect=2)

    def test_validate_ok_when_ordered_overlap(self):
        # overlapping scope is fine if one depends on the other (not concurrent)
        run(self.dir, "add-node", "p", "--scope", "src/shared/**")
        run(self.dir, "add-node", "q", "--scope", "src/shared/util/**", "--dep", "p")
        out = run(self.dir, "validate")
        self.assertIn("ok", out)

    def test_set_state_rejects_bad_state(self):
        run(self.dir, "add-node", "n", "--scope", "n/**")
        run(self.dir, "set-state", "n", "bogus", expect=2)

    def test_show_json_roundtrip(self):
        run(self.dir, "add-node", "n", "--scope", "n/**", "--desc", "hello")
        node = json.loads(run(self.dir, "show", "n"))
        self.assertEqual(node["desc"], "hello")
        self.assertEqual(node["state"], "pending")


if __name__ == "__main__":
    unittest.main()
