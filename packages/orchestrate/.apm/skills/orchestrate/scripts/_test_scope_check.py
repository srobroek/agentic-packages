#!/usr/bin/env python3
"""Self-tests for scope-check.py (stdlib unittest, no deps).

CI has no beads install, so the bd-facing tests run against a stub `bd`
executable that replays canned JSON per subcommand. Real-bd behavior (label
filters, claim semantics, metadata merge) is verified manually against bd and
documented in references/beads-store.md. The overlap rule itself is tested
in-process, stub-free.
"""

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCOPE = os.path.join(HERE, "scope-check.py")


def _load_scope_check():
    """The script's filename is not an importable identifier."""
    spec = importlib.util.spec_from_file_location("scope_check", SCOPE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


scope_check = _load_scope_check()


def _bead(bid, scope=None, status="open"):
    return {
        "id": bid,
        "status": status,
        "labels": ["orc-node"],
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
            '  *) echo "stub bd: unknown $1" >&2; exit 2 ;;\n'
            "esac\n"
        )
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    return path


def _run(*args):
    return subprocess.run(
        [sys.executable, SCOPE, *args], capture_output=True, text=True
    )


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
            listing={
                "schema_version": 1,
                "data": [_bead("orc-2", ["src/**"], status="in_progress")],
            },
        )
        p = _run("--candidate", "orc-1", "--bd", bd)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


class ScopesOverlapTest(unittest.TestCase):
    def assertOverlap(self, a, b):
        self.assertTrue(scope_check._scopes_overlap(a, b), f"{a} vs {b}")
        self.assertTrue(scope_check._scopes_overlap(b, a), f"{b} vs {a} (reversed)")

    def assertDisjoint(self, a, b):
        self.assertFalse(scope_check._scopes_overlap(a, b), f"{a} vs {b}")
        self.assertFalse(scope_check._scopes_overlap(b, a), f"{b} vs {a} (reversed)")

    def test_extension_splits_of_one_dir_are_disjoint(self):
        self.assertDisjoint(["src/api/*.py"], ["src/api/*.ts"])

    def test_star_subsumes_extension_glob(self):
        self.assertOverlap(["src/api/*"], ["src/api/*.py"])

    def test_identical_globs_overlap(self):
        self.assertOverlap(["src/api/*.py"], ["src/api/*.py"])

    def test_per_file_splits_of_one_dir_are_disjoint(self):
        self.assertDisjoint(["src/api/users.py"], ["src/api/orders.py"])

    def test_literal_file_under_glob_overlaps(self):
        self.assertOverlap(["src/api/*.py"], ["src/api/users.py"])

    def test_literal_dir_owns_globs_beneath_it(self):
        self.assertOverlap(["src/api"], ["src/api/*.py"])

    def test_nested_dir_overlaps_parent_glob(self):
        self.assertOverlap(["tests/**"], ["tests/integration/**"])

    def test_sibling_dirs_are_disjoint(self):
        self.assertDisjoint(["docs/**"], ["src/api/**"])

    def test_bare_doublestar_owns_everything(self):
        self.assertOverlap(["**"], ["docs/**"])

    def test_trailing_slash_dir_form_matches_bare_form(self):
        self.assertOverlap(["src/api/"], ["src/api/*.py"])
        self.assertDisjoint(["src/api/"], ["src/web/*.py"])

    def test_recursive_glob_conservatively_overlaps_single_level(self):
        # fnmatch gives '**' no separator-spanning meaning, so 'src/**/*.py' is
        # reported as overlapping any same-rooted glob rather than guessed at
        self.assertOverlap(["src/**/*.py"], ["src/api/*.py"])
        self.assertOverlap(["src/**/*.py"], ["src/api/*.ts"])

    def test_mid_segment_wildcards_conservatively_overlap(self):
        # both can name src/ab/f.py, which neither direction of fnmatch shows
        self.assertOverlap(["src/a*/f.py"], ["src/*b/f.py"])

    def test_wildcard_dir_conservatively_overlaps_deeper_literal(self):
        self.assertOverlap(["src/*/f.py"], ["src/api/f.py"])

    def test_any_overlapping_pair_in_a_set_conflicts(self):
        self.assertOverlap(["docs/**", "src/api/*.py"], ["src/api/*"])

    def test_disjoint_multi_glob_sets(self):
        self.assertDisjoint(["docs/**", "src/api/*.py"], ["tests/**", "src/api/*.ts"])


if __name__ == "__main__":
    unittest.main()
