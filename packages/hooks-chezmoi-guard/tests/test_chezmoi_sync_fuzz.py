"""Seeded fuzz harness for chezmoi-sync.py.

The hook is advisory: the predecessor auto-committed and auto-pushed, which fought
deliberate branch work and swept unrelated dotfile changes into commits. The
property that matters is therefore negative, and it is asserted over the whole
corpus rather than on a few cases:

  P1  no subprocess it spawns is a write. Every argv is matched against an
      allowlist of read-only forms (`chezmoi source-path`, `git rev-parse`,
      `git status`); anything else fails the test, so adding a write later
      breaks this suite rather than a user's repository.
  P2  it exits 0 and raises nothing on any payload.
  P3  it prints advice only -- the text may name a write command, but the hook
      does not run it.

Corpus: 3000 payloads from seed 20260729, crossing hostile file_path values with
hostile payload shapes, plus explicit cases for the template and re-add branches.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import random
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "chezmoi-sync.py"
SEED = 20260729
CORPUS_SIZE = int(os.environ.get("FUZZ_PAYLOADS", "3000"))


def _load():
    spec = importlib.util.spec_from_file_location("chezmoi_sync_fuzz", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sync = _load()

# Every argv form the hook is permitted to run. A write -- `chezmoi add`,
# `chezmoi apply`, `chezmoi re-add`, `git add`, `git commit`, `git push` -- matches
# nothing here and fails P1.
READ_ONLY_FORMS = (
    ("chezmoi", "source-path"),
    ("git", "-C", "*", "rev-parse", "--git-dir"),
    ("git", "-C", "*", "status", "--short"),
)

WRITE_TOKENS = (
    "add",
    "re-add",
    "readd",
    "apply",
    "commit",
    "push",
    "pull",
    "update",
    "init",
    "destroy",
    "forget",
    "remove",
    "rm",
    "checkout",
    "reset",
    "clean",
    "stash",
)

HOSTILE_PATHS = (
    "",
    "/",
    "~",
    "~/.zshrc",
    "relative/path",
    "/etc/passwd",
    "\n",
    "a\nb",
    "/tmp/x\ny",
    '/tmp/"quoted"',
    "/tmp/back\\slash",
    "/tmp/uniçode/.config",
    "/tmp/" + "x" * 3000,
    "--force",
    "-rf",
    "/tmp/;rm -rf /",
    "/tmp/$(whoami)",
    "/tmp/`id`",
    "/tmp/x;git push",
    "\x00/tmp/x",
    "/dev/null",
    "/proc/self/environ",
)


def _matches_read_only(argv: list[str]) -> bool:
    for form in READ_ONLY_FORMS:
        if len(argv) != len(form):
            continue
        if all(want == "*" or want == got for want, got in zip(form, argv)):
            return True
    return False


class Recorder:
    """Stands in for subprocess.run, recording argv and returning benign output."""

    def __init__(self, source: str, *, status: str = "") -> None:
        self.calls: list[list[str]] = []
        self._source = source
        self._status = status

    def __call__(self, command, **kwargs):
        argv = list(command)
        self.calls.append(argv)

        class Result:
            returncode = 0
            stderr = ""

        if argv[:2] == ["chezmoi", "source-path"]:
            Result.stdout = self._source if len(argv) == 2 else ""
        elif "status" in argv:
            Result.stdout = self._status
        else:
            Result.stdout = ".git"
        return Result()

    def assert_read_only(self) -> None:
        for argv in self.calls:
            assert _matches_read_only(argv), f"non-read-only subprocess: {argv!r}"
            for token in WRITE_TOKENS:
                assert token not in argv, f"write token {token!r} in {argv!r}"


def _payload(rng: random.Random, home: Path) -> str:
    """A payload that is usually shaped like a PostToolUse Edit, sometimes not."""
    roll = rng.random()
    if roll < 0.05:
        return rng.choice(["", "not json", "[]", "null", "42", '"text"', "{"])
    if roll < 0.12:
        return json.dumps({"tool_input": rng.choice([None, "string", 42, [], {}])})
    if rng.random() < 0.5:
        target = rng.choice(HOSTILE_PATHS)
    else:
        parts = [
            rng.choice([".config", ".ssh", ".local", "personal", ".cache", ".gitconfig"]),
            rng.choice(["config", "settings.json", "x.tmpl", ".zshrc", "f.lock", "ünï"]),
        ]
        target = str(home.joinpath(*parts))
    body: dict = {"tool_name": "Edit", "tool_input": {"file_path": target}}
    if rng.random() < 0.1:
        body["tool_input"]["file_path"] = rng.choice([None, 42, [], {}, True])
    return json.dumps(body)


@pytest.fixture()
def source(tmp_path):
    """A real git repo standing in for the chezmoi source, with a pending change."""
    root = Path(os.path.realpath(str(tmp_path))) / "chezmoi-source"
    root.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "-q", "-b", "main", "."], cwd=root, check=True, capture_output=True
    )
    (root / "dot_zshrc").write_text("export X=1\n")
    return root


def test_no_write_command_on_any_payload(monkeypatch, capsys, source, tmp_path):
    """P1, P2 and P3 over the generated corpus."""
    home = Path(os.path.realpath(str(tmp_path))) / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    rng = random.Random(SEED)
    recorder = Recorder(str(source), status=" M dot_zshrc\n")
    monkeypatch.setattr("subprocess.run", recorder)

    for index in range(CORPUS_SIZE):
        payload = _payload(rng, home)
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        assert sync.main() == 0, f"case {index} did not exit 0: {payload!r}"
        capsys.readouterr()
    recorder.assert_read_only()


def test_the_tracked_file_branch_advises_without_acting(monkeypatch, capsys, source, tmp_path):
    """The re-add branch prints `chezmoi re-add` as ADVICE; it must not run it."""
    home = Path(os.path.realpath(str(tmp_path))) / "home"
    (home / ".config").mkdir(parents=True)
    target = home / ".config" / "settings.json"
    target.write_text("{}")
    tracked = source / "dot_config" / "settings.json"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("{}")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    recorder = Recorder(str(source), status=" M dot_zshrc\n")

    def resolve(command, **kwargs):
        argv = list(command)
        if argv[:2] == ["chezmoi", "source-path"] and len(argv) == 3:
            recorder.calls.append(argv)

            class Result:
                returncode = 0
                stdout = str(tracked)
                stderr = ""

            return Result()
        return recorder(command, **kwargs)

    monkeypatch.setattr("subprocess.run", resolve)
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"tool_input": {"file_path": str(target)}}))
    )

    assert sync.main() == 0
    out = capsys.readouterr().out
    assert "chezmoi re-add" in out, "the advisory must still name the action"
    assert "does NOT auto-commit" in out
    for argv in recorder.calls:
        assert argv[:3] != ["chezmoi", "source-path", "--"], argv
        assert "re-add" not in argv and "add" not in argv, argv
    assert target.read_text() == "{}", "the edited file must not be rewritten"


def test_a_source_sibling_directory_is_not_treated_as_the_source(tmp_path):
    """`is_ignored` compared string prefixes, so a directory merely NAMED like the
    source -- `<source>-backup` -- was silently skipped."""
    src = str(Path(os.path.realpath(str(tmp_path))) / "chezmoi")
    sibling = Path(src + "-backup")
    sibling.mkdir(parents=True)
    inside = Path(src)
    inside.mkdir(parents=True)

    assert sync.is_ignored(str(inside / ".zshrc"), Path(".zshrc"), src)
    assert not sync.is_ignored(str(sibling / ".zshrc"), Path(".zshrc"), src)


def test_the_script_contains_no_write_invocation():
    """A static backstop: the corpus cannot prove the absence of a branch it never
    reaches, so the source is also read for write verbs in an argv position."""
    body = SCRIPT.read_text(encoding="utf-8")
    for banned in (
        '"add"',
        "'add'",
        '"re-add"',
        "'re-add'",
        '"commit"',
        "'commit'",
        '"push"',
        "'push'",
        '"apply"',
        "'apply'",
    ):
        assert banned not in body, f"{banned} appears as an argv token"
