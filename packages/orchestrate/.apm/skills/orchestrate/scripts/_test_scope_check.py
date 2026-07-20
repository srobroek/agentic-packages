#!/usr/bin/env python3
"""Self-tests for scope-check.py (stdlib unittest, no deps).

CI has no beads install, so these tests exercise the bd-facing path against a
stub `bd` executable that replays canned JSON per subcommand. Real-bd behavior
(label filters, claim semantics, metadata merge) is verified manually against
bd 1.1.0 and documented in references/beads-store.md.
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCOPE = os.path.join(HERE, "scope-check.py")


def _bead(bid, scope=None, status="open"):
    return {
        "id": bid, "status": status, "labels": ["orc-node"],
        "metadata": {"scope": scope} if scope is not None else {},
    }


def _make_stub(dirpath, show, listing):
    """Write a fake `bd` that prints canned JSON for show/list. Canned data
    goes through files, not shell quoting."""
    for name, payload in (("show.json", show), ("list.json", listing)):
        with open(os.path.join(dirpath, name), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
    path = os.path.join(dirpath, "bd")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(
            "#!/bin/sh\n"
            f"here='{dirpath}'\n"
            'case "$1" in\n'
            '  show) cat "$here/show.json" ;;\n'
            '  list) cat "$here/list.json" ;;\n'
            "  *) echo \"stub bd: unknown $1\" >&2; exit 2 ;;\n"
            "esac\n"
        )
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    return path


def _run(*args):
    return subprocess.run([sys.executable, SCOPE, *args],
                          capture_output=True, text=True)


class ScopeCheckTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_disjoint_scopes_pass(self):
        bd = _make_stub(
            self.dir,
            show=[_bead("orc-1", ["docs/**"])],
            listing=[_bead("orc-2", ["src/api/**"], status="in_progress")],
        )
        p = _run("--candidate", "orc-1", "--bd", bd)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("disjoint", p.stdout)

    def test_overlapping_scope_conflicts(self):
        bd = _make_stub(
            self.dir,
            show=[_bead("orc-1", ["tests/**"])],
            listing=[_bead("orc-2", ["tests/integration/**"], status="in_progress")],
        )
        p = _run("--candidate", "orc-1", "--bd", bd)
        self.assertEqual(p.returncode, 1)
        self.assertIn("conflict", p.stdout)
        self.assertIn("orc-2", p.stdout)

    def test_bare_doublestar_conflicts_with_everything(self):
        bd = _make_stub(
            self.dir,
            show=[_bead("orc-1", ["**"])],
            listing=[_bead("orc-2", ["docs/**"], status="in_progress")],
        )
        p = _run("--candidate", "orc-1", "--bd", bd)
        self.assertEqual(p.returncode, 1)

    def test_candidate_ignored_in_inflight_sweep(self):
        # the candidate itself may already be listed in_progress (claim retry);
        # it must not conflict with itself
        bd = _make_stub(
            self.dir,
            show=[_bead("orc-1", ["src/a/**"])],
            listing=[_bead("orc-1", ["src/a/**"], status="in_progress")],
        )
        p = _run("--candidate", "orc-1", "--bd", bd)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_no_inflight_passes(self):
        bd = _make_stub(self.dir, show=[_bead("orc-1", ["src/a/**"])], listing=[])
        p = _run("--candidate", "orc-1", "--bd", bd)
        self.assertEqual(p.returncode, 0)

    def test_missing_scope_metadata_dies(self):
        bd = _make_stub(self.dir, show=[_bead("orc-1")], listing=[])
        p = _run("--candidate", "orc-1", "--bd", bd)
        self.assertEqual(p.returncode, 2)
        self.assertIn("scope", p.stderr)

    def test_comma_string_scope_tolerated(self):
        bd = _make_stub(
            self.dir,
            show=[_bead("orc-1", "src/a/**, src/b/**")],
            listing=[_bead("orc-2", ["src/b/core/**"], status="in_progress")],
        )
        p = _run("--candidate", "orc-1", "--bd", bd)
        self.assertEqual(p.returncode, 1)

    def test_envelope_json_tolerated(self):
        # BD_JSON_ENVELOPE=1 wraps output in {"schema_version":1,"data":...}
        bd = _make_stub(
            self.dir,
            show={"schema_version": 1, "data": [_bead("orc-1", ["docs/**"])]},
            listing={"schema_version": 1,
                     "data": [_bead("orc-2", ["src/**"], status="in_progress")]},
        )
        p = _run("--candidate", "orc-1", "--bd", bd)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
