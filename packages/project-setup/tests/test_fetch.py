"""Tests for sources/fetch.py — fetch_source, fetch_all.

Key guarantees tested:
  * Offline / git-missing → FetchResult(ok=False) — NEVER raises.
  * Cache-key stability: same repo via different locator forms maps to the
    same cache directory.
  * Local paths: existing dir → ok=True; missing dir → ok=False.
  * No network access: git is stubbed via PATH manipulation.

Run via:
    uv run --with pytest pytest -q packages/project-setup/tests/test_fetch.py
"""

from __future__ import annotations

import importlib.util
import os
import sys
import textwrap
from pathlib import Path

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"
_SOURCES = _RUNNER / "sources"


def _load_runner(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_source(name: str):
    qualified = f"sources.{name}"
    if qualified in sys.modules:
        return sys.modules[qualified]
    spec = importlib.util.spec_from_file_location(qualified, _SOURCES / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = mod
    spec.loader.exec_module(mod)
    return mod


# Pre-load runner deps
_load_runner("contracts")
_load_runner("paths")

locator_mod = _load_source("locator")
fetch_mod = _load_source("fetch")

parse_locator = locator_mod.parse_locator
fetch_source = fetch_mod.fetch_source
FetchResult = fetch_mod.FetchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_fake_git(bin_dir: Path, exit_code: int = 1, message: str = "fake git") -> None:
    """Write a fake ``git`` script into *bin_dir* that exits with *exit_code*."""
    fake = bin_dir / "git"
    fake.write_text(
        textwrap.dedent(f"""\
            #!/bin/sh
            echo '{message}' >&2
            exit {exit_code}
        """)
    )
    fake.chmod(0o755)


def _remove_git_from_path(monkeypatch) -> None:
    """Remove all directories containing a real ``git`` binary from PATH."""
    import shutil
    original = os.environ.get("PATH", "")
    parts = [p for p in original.split(os.pathsep)
             if not (Path(p) / "git").exists() and not shutil.which("git", path=p)]
    monkeypatch.setenv("PATH", os.pathsep.join(parts))


# ---------------------------------------------------------------------------
# Local locator tests (no git involved)
# ---------------------------------------------------------------------------

class TestFetchSourceLocal:
    def test_existing_dir_returns_ok(self, tmp_path):
        loc = parse_locator(str(tmp_path))
        result = fetch_source(loc)
        assert result.ok is True
        assert result.root_path == tmp_path
        assert result.skipped_reason == ""

    def test_missing_dir_returns_not_ok(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        loc = parse_locator(str(missing))
        result = fetch_source(loc)
        assert result.ok is False
        assert result.root_path is None
        assert "does not exist" in result.skipped_reason

    def test_does_not_raise_on_missing_dir(self, tmp_path):
        missing = tmp_path / "gone"
        loc = parse_locator(str(missing))
        # Must not raise under any circumstances
        result = fetch_source(loc)
        assert isinstance(result, FetchResult)


# ---------------------------------------------------------------------------
# Git locator tests: git binary absent → graceful skip
# ---------------------------------------------------------------------------

class TestFetchSourceGitAbsent:
    def test_returns_not_ok_when_git_missing(self, tmp_path, monkeypatch):
        # Point PATH to an empty directory so git is not found.
        empty_bin = tmp_path / "empty_bin"
        empty_bin.mkdir()
        monkeypatch.setenv("PATH", str(empty_bin))
        monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))

        loc = parse_locator("some-org/some-repo")
        result = fetch_source(loc)

        assert result.ok is False
        assert result.root_path is None
        assert result.skipped_reason  # non-empty explanation

    def test_does_not_raise_when_git_missing(self, tmp_path, monkeypatch):
        empty_bin = tmp_path / "empty_bin"
        empty_bin.mkdir()
        monkeypatch.setenv("PATH", str(empty_bin))
        monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))

        loc = parse_locator("some-org/some-repo")
        # The critical invariant: this must never raise
        result = fetch_source(loc)
        assert isinstance(result, FetchResult)

    def test_skipped_reason_mentions_git(self, tmp_path, monkeypatch):
        empty_bin = tmp_path / "empty_bin"
        empty_bin.mkdir()
        monkeypatch.setenv("PATH", str(empty_bin))
        monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))

        loc = parse_locator("org/repo")
        result = fetch_source(loc)
        # Should mention git in the reason
        assert "git" in result.skipped_reason.lower()


# ---------------------------------------------------------------------------
# Git locator tests: git binary present but clone fails
# ---------------------------------------------------------------------------

class TestFetchSourceGitFails:
    def test_clone_failure_returns_not_ok(self, tmp_path, monkeypatch):
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        _write_fake_git(fake_bin, exit_code=128, message="repository not found")
        monkeypatch.setenv("PATH", str(fake_bin))
        monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))

        loc = parse_locator("org/nonexistent-repo")
        result = fetch_source(loc)

        assert result.ok is False
        assert result.root_path is None
        assert result.skipped_reason  # must be non-empty

    def test_clone_failure_does_not_raise(self, tmp_path, monkeypatch):
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        _write_fake_git(fake_bin, exit_code=1, message="error")
        monkeypatch.setenv("PATH", str(fake_bin))
        monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))

        loc = parse_locator("org/repo")
        result = fetch_source(loc)
        assert isinstance(result, FetchResult)


# ---------------------------------------------------------------------------
# Cache-key stability: same repo, different URL forms → same cache dir
# ---------------------------------------------------------------------------

class TestCacheKeyStability:
    def test_ssh_https_shorthand_use_same_cache_dir(self, tmp_path, monkeypatch):
        """Different URL forms for the same repo must hash to the same dir."""
        monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))

        from sources.locator import cache_key  # noqa: PLC0415
        ssh = parse_locator("git@github.com:myorg/myrepo.git")
        https = parse_locator("https://github.com/myorg/myrepo")
        shorthand = parse_locator("myorg/myrepo")

        assert cache_key(ssh) == cache_key(https) == cache_key(shorthand)

    def test_different_repos_use_different_dirs(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))

        from sources.locator import cache_key  # noqa: PLC0415
        a = parse_locator("myorg/repo-a")
        b = parse_locator("myorg/repo-b")
        assert cache_key(a) != cache_key(b)


# ---------------------------------------------------------------------------
# SC-A: (origin, ref) cache-key coexistence and reuse
# ---------------------------------------------------------------------------

class TestCacheKeyRefIsolation:
    """SC-A — two projects on different refs collide; same ref reuses one dir."""

    def test_different_refs_map_to_different_dirs(self, tmp_path, monkeypatch):
        """org/addons#v1 and org/addons#v2 must resolve to different cache dirs."""
        monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))

        from sources.locator import cache_key  # noqa: PLC0415
        v1 = parse_locator("org/addons#v1")
        v2 = parse_locator("org/addons#v2")

        assert cache_key(v1) != cache_key(v2), (
            "org/addons#v1 and org/addons#v2 must use separate cache dirs "
            "so they do not thrash each other"
        )

    def test_same_ref_maps_to_same_dir(self, tmp_path, monkeypatch):
        """Two projects pinning org/addons#v1 must share one cache dir (reuse)."""
        monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))

        from sources.locator import cache_key  # noqa: PLC0415
        project_a = parse_locator("org/addons#v1")
        project_b = parse_locator("org/addons#v1")

        assert cache_key(project_a) == cache_key(project_b), (
            "Two projects on org/addons#v1 must share one cache dir"
        )

    def test_local_locator_ref_does_not_affect_key(self, tmp_path):
        """Local locators are keyed on path only; the (empty) ref is irrelevant."""
        from sources.locator import cache_key, Locator  # noqa: PLC0415
        # Local locators always have ref="" — build two identical ones and
        # confirm the key is stable (origin-based, not origin@ref-based).
        loc1 = Locator(kind="local", origin=str(tmp_path), subdir="", ref="")
        loc2 = Locator(kind="local", origin=str(tmp_path), subdir="", ref="")
        assert cache_key(loc1) == cache_key(loc2)

    def test_ssh_https_shorthand_with_same_ref_match(self, tmp_path, monkeypatch):
        """Different URL forms for the same repo+ref still produce the same key."""
        monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))

        from sources.locator import cache_key  # noqa: PLC0415
        ssh = parse_locator("git@github.com:myorg/myrepo.git#v1")
        https = parse_locator("https://github.com/myorg/myrepo#v1")
        shorthand = parse_locator("myorg/myrepo#v1")

        assert cache_key(ssh) == cache_key(https) == cache_key(shorthand)


class TestSuccessfulGitFetchLocalBareRepo:
    """Exercise the REAL clone+checkout path with a local bare repo (no network).

    Closes the gap where only the offline-skip branch was covered. Builds a real
    git repo, bare-clones it as the 'remote', and points a git-kind Locator at
    that bare repo path.
    """

    def _make_bare_remote(self, tmp_path):
        import shutil
        import subprocess

        if shutil.which("git") is None:
            return None  # caller skips
        work = tmp_path / "work"
        work.mkdir()
        # Hermetic git: isolate from the developer's global/system config so a
        # commit-signing hook (e.g. 1Password gpg.program) can't fail the
        # non-interactive `git commit` with exit 128 ("failed to fill whole
        # buffer"). GIT_CONFIG_GLOBAL/SYSTEM=/dev/null drops global config;
        # commit.gpgsign=false belts-and-braces in case a repo default signs.
        env = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }

        def git(*args, cwd=work):
            subprocess.run(["git", "-c", "commit.gpgsign=false", *args],
                           cwd=str(cwd), check=True, capture_output=True,
                           text=True, env=env)

        git("init", "-q")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "Test")
        (work / "MARKER.txt").write_text("hello from remote\n")
        git("add", "MARKER.txt")
        git("commit", "-q", "-m", "initial")
        bare = tmp_path / "remote.git"
        subprocess.run(["git", "clone", "-q", "--bare", str(work), str(bare)],
                       check=True, capture_output=True, text=True, env=env)
        return bare

    def test_successful_clone_and_checkout(self, tmp_path, monkeypatch):
        import pytest
        bare = self._make_bare_remote(tmp_path)
        if bare is None:
            pytest.skip("git not available")
        monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
        Locator = locator_mod.Locator
        loc = Locator(kind="git", origin=str(bare), subdir="", ref="HEAD")
        result = fetch_source(loc)
        assert result.ok, result.skipped_reason
        assert result.root_path is not None
        assert (result.root_path / "MARKER.txt").read_text() == "hello from remote\n"

    def test_second_fetch_uses_cache(self, tmp_path, monkeypatch):
        import pytest
        bare = self._make_bare_remote(tmp_path)
        if bare is None:
            pytest.skip("git not available")
        monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
        Locator = locator_mod.Locator
        loc = Locator(kind="git", origin=str(bare), subdir="", ref="HEAD")
        first = fetch_source(loc)
        assert first.ok, first.skipped_reason
        second = fetch_source(loc)
        assert second.ok, second.skipped_reason
        assert (second.root_path / "MARKER.txt").exists()

    def test_subdir_resolution(self, tmp_path, monkeypatch):
        import pytest
        import shutil
        import subprocess
        if shutil.which("git") is None:
            pytest.skip("git not available")
        work = tmp_path / "work"
        (work / "pkg").mkdir(parents=True)
        # Hermetic git (see _make_bare_remote): isolate from global/system
        # config so commit signing can't fail the non-interactive commit.
        env = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }

        def git(*args):
            subprocess.run(["git", "-c", "commit.gpgsign=false", *args],
                           cwd=str(work), check=True, capture_output=True,
                           text=True, env=env)

        git("init", "-q")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "Test")
        (work / "pkg" / "M.txt").write_text("sub\n")
        git("add", "-A")
        git("commit", "-q", "-m", "init")
        bare = tmp_path / "remote.git"
        subprocess.run(["git", "clone", "-q", "--bare", str(work), str(bare)],
                       check=True, capture_output=True, text=True, env=env)
        monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
        Locator = locator_mod.Locator
        loc = Locator(kind="git", origin=str(bare), subdir="pkg", ref="HEAD")
        result = fetch_source(loc)
        assert result.ok, result.skipped_reason
        assert (result.root_path / "M.txt").read_text() == "sub\n"
