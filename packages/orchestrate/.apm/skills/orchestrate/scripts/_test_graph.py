#!/usr/bin/env python3
"""Self-tests for graph.py (stdlib unittest, no deps)."""
import concurrent.futures
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

    def test_blocked_is_not_a_valid_state(self):
        # 'blocked' was removed from STATES/INFLIGHT_STATES: unreachable, a
        # blocked coder stays 'working'.
        run(self.dir, "add-node", "n", "--scope", "n/**")
        run(self.dir, "set-state", "n", "blocked", expect=2)

    def test_relative_store_rejected(self):
        proc = subprocess.run(
            [sys.executable, GRAPH, "--store", "relative/store/path", "init"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("absolute", proc.stderr)

    def test_set_meta_roundtrip(self):
        run(self.dir, "add-node", "n", "--scope", "n/**")
        run(self.dir, "set-meta", "n", "--assignee", "coder-n", "--branch", "coder/n",
            "--commit", "abc123")
        run(self.dir, "set-meta", "n", "--commit", "def456")
        node = json.loads(run(self.dir, "show", "n"))
        self.assertEqual(node["assignee"], "coder-n")
        self.assertEqual(node["branch"], "coder/n")
        self.assertEqual(node["commits"], ["abc123", "def456"])

    def test_impact_lists_transitive_dependents(self):
        run(self.dir, "add-node", "a", "--scope", "a/**")
        run(self.dir, "add-node", "b", "--scope", "b/**", "--dep", "a")
        run(self.dir, "add-node", "c", "--scope", "c/**", "--dep", "b")
        run(self.dir, "add-node", "d", "--scope", "d/**")  # unrelated
        out = run(self.dir, "impact", "a")
        ids = [line.split("\t")[0] for line in out.splitlines() if line.strip()]
        self.assertEqual(sorted(ids), ["b", "c"])

    def test_list_multi_state_filter(self):
        run(self.dir, "add-node", "p", "--scope", "p/**")
        run(self.dir, "add-node", "q", "--scope", "q/**")
        run(self.dir, "add-node", "r", "--scope", "r/**")
        run(self.dir, "set-state", "p", "working")
        run(self.dir, "set-state", "q", "reported")
        out = run(self.dir, "list", "--state", "working,reported")
        ids = {line.split("\t")[0] for line in out.splitlines() if line.strip()}
        self.assertEqual(ids, {"p", "q"})


class GraphRaceTest(unittest.TestCase):
    """Concurrent-process races: every mutating command must hold one
    exclusive flock across its whole load->mutate->save cycle, or concurrent
    CLI invocations lose updates (reproduced pre-fix: 20 concurrent add-node
    calls lost 10 nodes; concurrent set-state clobbered)."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        run(self.dir, "init", "--run-id", "run-race")

    def test_concurrent_add_node_loses_nothing(self):
        n = 20
        with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
            list(ex.map(
                lambda i: run(self.dir, "add-node", f"n{i}", "--scope", f"src/n{i}/**"),
                range(n),
            ))
        out = run(self.dir, "list")
        lines = [line for line in out.splitlines() if line.strip()]
        self.assertEqual(len(lines), n, "concurrent add-node lost an update")

    def test_concurrent_set_state_loses_nothing(self):
        n = 10
        for i in range(n):
            run(self.dir, "add-node", f"m{i}", "--scope", f"src/m{i}/**")
        with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
            list(ex.map(
                lambda i: run(self.dir, "set-state", f"m{i}", "working"),
                range(n),
            ))
        out = run(self.dir, "list", "--state", "working")
        lines = [line for line in out.splitlines() if line.strip()]
        self.assertEqual(len(lines), n, "concurrent set-state clobbered an update")


if __name__ == "__main__":
    unittest.main()
