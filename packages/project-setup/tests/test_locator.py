"""Tests for sources/locator.py — parse_locator, normalize_origin, cache_key.

Imports the runner library by file path (the verified import-by-path pattern
from test_contracts.py::_load — registers in sys.modules before exec_module).

Run via:
    uv run --with pytest pytest -q packages/project-setup/tests/test_locator.py
"""

from __future__ import annotations

import importlib.util
import sys
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


# Pre-load runner deps so sibling auto-loads work.
_load_runner("contracts")
_load_runner("paths")

locator_mod = _load_source("locator")
parse_locator = locator_mod.parse_locator
normalize_origin = locator_mod.normalize_origin
cache_key = locator_mod.cache_key
Locator = locator_mod.Locator


# ---------------------------------------------------------------------------
# parse_locator: shorthand forms
# ---------------------------------------------------------------------------

class TestParseShorthand:
    def test_owner_repo_only(self):
        loc = parse_locator("myorg/my-repo")
        assert loc.kind == "git"
        assert loc.subdir == ""
        assert loc.ref == "HEAD"
        # normalized origin should be github.com/myorg/my-repo
        assert "myorg/my-repo" in loc.origin

    def test_owner_repo_with_subdir(self):
        loc = parse_locator("myorg/my-repo/modules")
        assert loc.kind == "git"
        assert loc.subdir == "modules"
        assert loc.ref == "HEAD"

    def test_owner_repo_with_deep_subdir(self):
        loc = parse_locator("myorg/my-repo/a/b/c")
        assert loc.subdir == "a/b/c"

    def test_owner_repo_with_ref(self):
        loc = parse_locator("myorg/my-repo#main")
        assert loc.ref == "main"
        assert loc.subdir == ""

    def test_owner_repo_subdir_and_ref(self):
        loc = parse_locator("myorg/my-repo/src#v1.2.3")
        assert loc.subdir == "src"
        assert loc.ref == "v1.2.3"

    def test_sha_ref(self):
        loc = parse_locator("myorg/my-repo#abc1234")
        assert loc.ref == "abc1234"


# ---------------------------------------------------------------------------
# parse_locator: HTTPS URLs
# ---------------------------------------------------------------------------

class TestParseHttpsUrl:
    def test_plain_https(self):
        loc = parse_locator("https://github.com/owner/repo")
        assert loc.kind == "git"
        assert loc.origin == "github.com/owner/repo"
        assert loc.subdir == ""
        assert loc.ref == "HEAD"

    def test_https_with_dot_git(self):
        loc = parse_locator("https://github.com/owner/repo.git")
        assert loc.origin == "github.com/owner/repo"

    def test_https_with_subdir(self):
        loc = parse_locator("https://github.com/owner/repo/packages/foo")
        assert loc.subdir == "packages/foo"

    def test_https_with_ref(self):
        loc = parse_locator("https://github.com/owner/repo#develop")
        assert loc.ref == "develop"

    def test_https_with_subdir_and_ref(self):
        loc = parse_locator("https://github.com/owner/repo/pkg#v2")
        assert loc.subdir == "pkg"
        assert loc.ref == "v2"


# ---------------------------------------------------------------------------
# parse_locator: SSH URLs
# ---------------------------------------------------------------------------

class TestParseSshUrl:
    def test_plain_ssh(self):
        loc = parse_locator("git@github.com:owner/repo")
        assert loc.kind == "git"
        assert "owner/repo" in loc.origin
        assert loc.subdir == ""
        assert loc.ref == "HEAD"

    def test_ssh_with_dot_git(self):
        loc = parse_locator("git@github.com:owner/repo.git")
        assert loc.origin == "github.com/owner/repo"

    def test_ssh_with_ref(self):
        loc = parse_locator("git@github.com:owner/repo.git#feature-x")
        assert loc.ref == "feature-x"


# ---------------------------------------------------------------------------
# parse_locator: local paths
# ---------------------------------------------------------------------------

class TestParseLocalPath:
    def test_absolute_path(self, tmp_path):
        loc = parse_locator(str(tmp_path))
        assert loc.kind == "local"
        assert loc.origin == str(tmp_path)

    def test_dotslash_relative(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sub = tmp_path / "modules"
        sub.mkdir()
        loc = parse_locator("./modules")
        assert loc.kind == "local"

    def test_dotdot_relative(self, tmp_path):
        loc = parse_locator("../something")
        assert loc.kind == "local"


# ---------------------------------------------------------------------------
# normalize_origin: all forms collapse to the same canonical string
# ---------------------------------------------------------------------------

class TestNormalizeOrigin:
    def test_ssh_https_shorthand_all_equal(self):
        ssh = normalize_origin("git@github.com:acme/widgets.git")
        https = normalize_origin("https://github.com/acme/widgets.git")
        shorthand = normalize_origin("github.com/acme/widgets")
        assert ssh == https == shorthand

    def test_drops_git_suffix(self):
        with_git = normalize_origin("https://github.com/o/r.git")
        without_git = normalize_origin("https://github.com/o/r")
        assert with_git == without_git

    def test_lowercase_host(self):
        upper = normalize_origin("https://GITHUB.COM/Owner/Repo")
        lower = normalize_origin("https://github.com/Owner/Repo")
        assert upper == lower

    def test_no_trailing_slash(self):
        result = normalize_origin("https://github.com/o/r/")
        assert not result.endswith("/")

    def test_ssh_no_dot_git(self):
        result = normalize_origin("git@github.com:o/r")
        assert not result.endswith(".git")

    def test_result_has_no_scheme(self):
        result = normalize_origin("https://github.com/o/r")
        assert not result.startswith("http")


# ---------------------------------------------------------------------------
# cache_key: stability + equivalence across locator forms
# ---------------------------------------------------------------------------

class TestCacheKey:
    def test_same_repo_different_forms_give_same_key(self):
        ssh = parse_locator("git@github.com:myorg/myrepo.git")
        https = parse_locator("https://github.com/myorg/myrepo")
        shorthand = parse_locator("myorg/myrepo")
        assert cache_key(ssh) == cache_key(https) == cache_key(shorthand)

    def test_different_repos_give_different_keys(self):
        a = parse_locator("myorg/repo-a")
        b = parse_locator("myorg/repo-b")
        assert cache_key(a) != cache_key(b)

    def test_different_refs_same_repo_give_different_keys(self):
        # FR-A1: different pinned refs must map to DIFFERENT cache dirs so they
        # do not thrash each other.
        main = parse_locator("myorg/myrepo#main")
        dev = parse_locator("myorg/myrepo#develop")
        assert cache_key(main) != cache_key(dev)

    def test_same_ref_same_repo_give_same_key(self):
        # FR-A2: two projects on the same (origin, ref) share one cache dir.
        a = parse_locator("myorg/myrepo#v1.0.0")
        b = parse_locator("myorg/myrepo#v1.0.0")
        assert cache_key(a) == cache_key(b)

    def test_different_subdirs_same_repo_and_ref_give_same_key(self):
        # Subdir slicing happens inside the cache entry; it does not affect key.
        a = parse_locator("myorg/myrepo/pkg-a")
        b = parse_locator("myorg/myrepo/pkg-b")
        # Both have ref="HEAD" so they share a cache dir (same origin+ref).
        assert cache_key(a) == cache_key(b)

    def test_key_is_hex_string(self):
        loc = parse_locator("myorg/myrepo")
        key = cache_key(loc)
        int(key, 16)  # should not raise
        assert len(key) == 16  # short hash

    def test_key_is_stable_across_calls(self):
        loc = parse_locator("myorg/myrepo")
        assert cache_key(loc) == cache_key(loc)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestParseErrors:
    def test_empty_string_raises(self):
        import pytest
        with pytest.raises(ValueError, match="empty"):
            parse_locator("")

    def test_whitespace_only_raises(self):
        import pytest
        with pytest.raises(ValueError):
            parse_locator("   ")
