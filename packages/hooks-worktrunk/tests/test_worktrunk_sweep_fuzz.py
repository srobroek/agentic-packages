"""Seeded fuzz harness for worktrunk-sweep.py.

This hook deletes directories, so the invariants below are absolute rather than
statistical, and the corpus is generated from a fixed seed so a failure is
reproducible. Three properties are asserted over every generated record:

  P1  is_stale never raises, whatever the record contains.
  P2  a record is only stale when EVERY signal is present, well-typed, and
      benign -- an absent or wrong-typed field can never produce a sweep.
  P3  reclaim never deletes anything outside the directory it was given, and
      never removes a directory git does not ignore.

Adversarial cases that are not random -- symlink escapes, `..` traversal, a path
symlinked to the home directory -- are pinned as explicit cases below the
generator, since a generator will not stumble on them.

Run standalone for a larger corpus: FUZZ_RECORDS=20000 pytest <this file>
"""

from __future__ import annotations

import importlib.util
import os
import random
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "worktrunk-sweep.py"
SEED = 20260729
CORPUS_SIZE = int(os.environ.get("FUZZ_RECORDS", "4000"))

WORKING_KEYS = ("staged", "modified", "untracked", "renamed", "deleted")


def _load():
    spec = importlib.util.spec_from_file_location("worktrunk_sweep_fuzz", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sweep = _load()

# Values chosen to break a naive truthiness or isinstance check: bool is an int
# subclass, 0/-1 are falsy-or-nonsense counts, and the strings include newline,
# quote, backslash, and non-ASCII bytes.
HOSTILE_SCALARS = (
    None,
    True,
    False,
    0,
    -1,
    1,
    1.0,
    1.5,
    "",
    "0",
    "false",
    "true",
    "\n",
    'a"b',
    "a\\b",
    "brânch/ünicode",
    "a\nb",
    "-x",
    "--force",
    "x" * 4096,
    [],
    {},
    [1, 2],
    {"k": "v"},
)


def _hostile(rng: random.Random):
    return rng.choice(HOSTILE_SCALARS)


def _record(rng: random.Random, path: str) -> dict:
    """A record that is USUALLY well-formed, with fields randomly corrupted.

    Starting from a valid stale record and spoiling it keeps the generator near
    the decision boundary, where an over-permissive check actually shows up.
    """
    old = int(time.time() - 60 * 86400)
    record: dict = {
        "branch": "feat/x",
        "path": path,
        "is_main": False,
        "is_current": False,
        "working_tree": {key: False for key in WORKING_KEYS},
        "remote": {"name": "origin", "ahead": 0, "behind": 0},
        "commit": {"sha": "abc", "timestamp": old},
    }
    for field in ("branch", "path", "is_main", "is_current"):
        if rng.random() < 0.15:
            record[field] = _hostile(rng)
    if rng.random() < 0.2:
        record["working_tree"] = _hostile(rng)
    elif rng.random() < 0.4:
        working = dict(record["working_tree"])
        if rng.random() < 0.5:
            del working[rng.choice(WORKING_KEYS)]
        else:
            working[rng.choice(WORKING_KEYS)] = _hostile(rng)
        record["working_tree"] = working
    if rng.random() < 0.2:
        record["remote"] = _hostile(rng)
    elif rng.random() < 0.4:
        record["remote"] = {"name": "origin", "ahead": _hostile(rng)}
    if rng.random() < 0.2:
        record["commit"] = _hostile(rng)
    elif rng.random() < 0.4:
        record["commit"] = {"sha": "abc", "timestamp": _hostile(rng)}
    if rng.random() < 0.1:
        record.pop(rng.choice(list(record)), None)
    return record


def _independently_stale(record: dict, now: float, threshold: int) -> bool:
    """A second, deliberately literal reading of the documented staleness rule.

    Written from the docstring rather than from the implementation, so it fails
    the parity check if the implementation drifts toward permissiveness.
    """
    if not isinstance(record, dict):
        return False
    if type(record.get("is_main")) is not bool or type(record.get("is_current")) is not bool:
        return False
    if record["is_main"] or record["is_current"]:
        return False
    path = record.get("path")
    if not isinstance(path, str) or not path or not os.path.isdir(path):
        return False
    if path != os.path.realpath(path):
        return False
    branch = record.get("branch")
    if not isinstance(branch, str) or not branch:
        return False
    working = record.get("working_tree")
    if not isinstance(working, dict):
        return False
    for key in WORKING_KEYS:
        if key not in working or type(working[key]) is not bool or working[key]:
            return False
    remote = record.get("remote")
    if not isinstance(remote, dict):
        return False
    ahead = remote.get("ahead")
    if type(ahead) is not int or ahead < 0 or ahead > 0:
        return False
    commit = record.get("commit")
    if not isinstance(commit, dict):
        return False
    stamp = commit.get("timestamp")
    if type(stamp) is not int or stamp <= 0:
        return False
    return (now - stamp) >= threshold


@pytest.fixture(scope="module")
def canonical_dir(tmp_path_factory):
    # realpath matters on macOS, where /tmp is a symlink to /private/tmp and an
    # unresolved path would trip the canonical-path gate for every case.
    return os.path.realpath(str(tmp_path_factory.mktemp("wt")))


def test_is_stale_never_raises_and_matches_the_documented_rule(canonical_dir):
    """P1 and P2 over the generated corpus."""
    rng = random.Random(SEED)
    now = time.time()
    swept = 0
    for index in range(CORPUS_SIZE):
        record = _record(rng, canonical_dir)
        ok, reason = sweep.is_stale(record, now)
        assert isinstance(ok, bool) and isinstance(reason, str)
        expected = _independently_stale(record, now, sweep.STALE_AFTER_SECONDS)
        assert ok == expected, f"case {index} diverged: {record!r} -> {ok} ({reason})"
        swept += ok
    # A corpus that never reaches the stale branch would prove nothing.
    assert swept > 0, "generator never produced a stale record"


def test_corrupting_any_single_signal_blocks_the_sweep(canonical_dir):
    """P2, exhaustively rather than randomly: spoil one field at a time."""
    now = time.time()
    valid = {
        "branch": "feat/x",
        "path": canonical_dir,
        "is_main": False,
        "is_current": False,
        "working_tree": {key: False for key in WORKING_KEYS},
        "remote": {"name": "origin", "ahead": 0},
        "commit": {"sha": "abc", "timestamp": int(now - 60 * 86400)},
    }
    assert sweep.is_stale(valid, now)[0], "baseline record must be stale"

    for field in valid:
        for value in HOSTILE_SCALARS:
            if field in ("is_main", "is_current") and not value:
                continue  # a falsy flag is the valid case, not a corruption
            candidate = dict(valid)
            candidate[field] = value
            ok, _ = sweep.is_stale(candidate, now)
            assert ok == _independently_stale(candidate, now, sweep.STALE_AFTER_SECONDS), (
                f"{field}={value!r}"
            )
    for key in WORKING_KEYS:
        missing = {k: v for k, v in valid["working_tree"].items() if k != key}
        assert not sweep.is_stale(dict(valid, working_tree=missing), now)[0], (
            f"absent working_tree.{key} must not read as clean"
        )


def _repo_with_ignored_artifacts(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q", "-b", "main", "."], cwd=root, check=True, capture_output=True
    )
    (root / ".gitignore").write_text("node_modules/\ntarget/\n")
    for name in ("node_modules", "target"):
        (root / name).mkdir()
        (root / name / "artifact").write_text("build output")


@pytest.mark.parametrize("escape", ["symlink", "traversal", "symlink-to-home"])
def test_reclaim_cannot_delete_outside_the_directory_it_was_given(tmp_path, escape):
    """P3, for the three escapes a generator will not find on its own.

    Reproduction before the fix: reclaim("<symlink to another repo>") returned
    ['node_modules'] and deleted that repo's node_modules; the `..` form did the
    same through a path nominally under the managed root.
    """
    outside = tmp_path / "outside"
    _repo_with_ignored_artifacts(outside)
    victim = outside / "node_modules" / "artifact"

    if escape == "traversal":
        managed = tmp_path / "managed" / "repo" / "branch"
        managed.mkdir(parents=True)
        target = str(managed / ".." / ".." / ".." / "outside")
    else:
        link = tmp_path / "wt-link"
        link.symlink_to(outside, target_is_directory=True)
        target = str(link)

    assert os.path.isdir(target), "the escape path must resolve, or the test is vacuous"
    assert sweep.reclaim(target) == []
    assert victim.read_text() == "build output"


def test_reclaim_removes_only_git_ignored_directories(tmp_path):
    """P3, positive half: the real `git check-ignore` gates each removal."""
    root = Path(os.path.realpath(str(tmp_path))) / "repo"
    _repo_with_ignored_artifacts(root)
    (root / "dist").mkdir()
    (root / "dist" / "tracked").write_text("keep")
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("code")

    removed = sweep.reclaim(str(root))

    assert sorted(removed) == ["node_modules", "target"]
    assert (root / "dist" / "tracked").read_text() == "keep"
    assert (root / "src" / "main.py").read_text() == "code"
    assert (root / ".git").is_dir()


def test_a_symlinked_artifact_dir_is_never_followed(tmp_path):
    root = Path(os.path.realpath(str(tmp_path))) / "repo"
    _repo_with_ignored_artifacts(root)
    outside = Path(os.path.realpath(str(tmp_path))) / "precious"
    outside.mkdir()
    (outside / "keep").write_text("keep")
    (root / "node_modules" / "artifact").unlink()
    (root / "node_modules").rmdir()
    (root / "node_modules").symlink_to(outside, target_is_directory=True)

    assert "node_modules" not in sweep.reclaim(str(root))
    assert (outside / "keep").read_text() == "keep"


@pytest.mark.parametrize(
    "value", ["", "abc", "-1", "0", "1e6", "nan", " ", "x" * 100, "9" * 400]
)
def test_a_hostile_age_threshold_falls_back_rather_than_crashing(value):
    """The override is read at import; a bad value used to raise before the hook
    read stdin, exiting 1 -- a guard crashing closed."""
    result = subprocess.run(
        ["python3", str(SCRIPT)],
        input="{}",
        capture_output=True,
        text=True,
        env=dict(os.environ, WORKTRUNK_SWEEP_STALE_AFTER=value),
    )
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr


def test_a_huge_record_set_is_reported_not_dumped(monkeypatch, capsys, canonical_dir):
    """A machine with thousands of stale worktrees gets a capped nudge."""
    import io
    import json

    old = int(time.time() - 60 * 86400)
    many = [
        {
            "branch": f"feat/b{index}",
            "path": canonical_dir,
            "is_main": False,
            "is_current": False,
            "working_tree": {key: False for key in WORKING_KEYS},
            "remote": {"ahead": 0},
            "commit": {"timestamp": old},
        }
        for index in range(5000)
    ]
    monkeypatch.setattr(sweep, "worktrees", lambda: many)
    monkeypatch.setattr(sweep, "reclaim", lambda path: [])
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/wt")
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))

    assert sweep.main() == 0
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert "5000 abandoned" in context
    assert f"and {5000 - sweep.REPORT_LIMIT} more" in context
    for index in range(sweep.REPORT_LIMIT):
        assert f"feat/b{index} " in context
    assert "feat/b4999" not in context, "the report must be capped, not dumped"


@pytest.mark.parametrize(
    "stdout",
    [
        '[{"path": 1}]',
        "[" * 200,
        '[{"working_tree": {"staged": "no"}}]',
        '{"schema": 2, "worktrees": []}',
        "\x00[]",
        '[{"branch": "a\\nb", "path": "/"}]',
        "▲ banner\n" * 100 + "[]",
    ],
    ids=["wrong-type", "unbalanced", "string-flag", "schema2", "nul", "newline", "banners"],
)
def test_wt_output_junk_never_raises(stdout, monkeypatch):
    class Result:
        returncode = 0

    Result.stdout = stdout
    monkeypatch.setattr(sweep, "run", lambda *a, **k: Result())
    assert isinstance(sweep.worktrees(), list)
