"""Phase 1 tests for spec 017 — brownfield_probe SDK primitive.

Covers:
  SC-003: brownfield_probe existence / emptiness edge cases.
  SC-004: merge_append_lines / idempotent_write(merge=True) idempotency,
          dedup, and order.
  SC-005: manifest [brownfield] parse — valid, unknown policy, absent.
  SC-006: looks_like_secret new shapes + UUID/SHA/semver negatives.

Run via:
  uv run --with pytest pytest -q packages/project-setup/tests/test_brownfield_probe.py
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sdk = _load("sdk")
manifest_mod = _load("manifest")

parse_manifest = manifest_mod.parse_manifest
# Derive ErrorCode from manifest_mod to avoid a separate contracts load that
# could create a duplicate class identity in sys.modules and break other
# tests that also import contracts (test isolation — matches test_manifest.py style).
ErrorCode = manifest_mod.ErrorCode


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def write_toml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "module.toml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


MINIMAL_VALID = """\
    [meta]
    repository = "github.com/test/repo"
    author = "test"

    [module]
    id = "test-module"
    name = "Test"
    version = "1.0.0"
    description = "A test module"
    reconcile = false
"""


# --------------------------------------------------------------------------- #
# SC-003 — brownfield_probe edge cases                                         #
# --------------------------------------------------------------------------- #
class TestBrownfieldProbe:
    def test_missing_project_dir_returns_not_exists(self, tmp_path):
        """A project dir that does not exist → exists=False, no raise."""
        nonexistent = tmp_path / "no_such_dir"
        results = sdk.brownfield_probe([".gitignore"], project_dir=nonexistent)
        assert len(results) == 1
        r = results[0]
        assert r.path == ".gitignore"
        assert r.exists is False
        assert r.empty is False

    def test_missing_artifact_returns_not_exists(self, tmp_path):
        """Artifact that does not exist inside a valid project dir → exists=False."""
        results = sdk.brownfield_probe([".gitignore"], project_dir=tmp_path)
        assert len(results) == 1
        r = results[0]
        assert r.exists is False
        assert r.empty is False

    def test_zero_byte_file_is_empty(self, tmp_path):
        """A zero-byte file → exists=True, empty=True."""
        (tmp_path / ".gitignore").write_bytes(b"")
        results = sdk.brownfield_probe([".gitignore"], project_dir=tmp_path)
        assert results[0].exists is True
        assert results[0].empty is True

    def test_whitespace_only_file_is_empty(self, tmp_path):
        """A file containing only whitespace → exists=True, empty=True."""
        (tmp_path / ".gitignore").write_text("   \n\t\n  ", encoding="utf-8")
        results = sdk.brownfield_probe([".gitignore"], project_dir=tmp_path)
        assert results[0].exists is True
        assert results[0].empty is True

    def test_non_empty_file_is_not_empty(self, tmp_path):
        """A file with real content → exists=True, empty=False."""
        (tmp_path / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
        results = sdk.brownfield_probe([".gitignore"], project_dir=tmp_path)
        assert results[0].exists is True
        assert results[0].empty is False

    def test_existing_directory_is_not_empty(self, tmp_path):
        """An existing directory → exists=True, empty=False (dirs are never empty)."""
        (tmp_path / ".git").mkdir()
        results = sdk.brownfield_probe([".git"], project_dir=tmp_path)
        assert results[0].exists is True
        assert results[0].empty is False

    def test_single_str_artifact_accepted(self, tmp_path):
        """A single str (not a list) is accepted per FR-001."""
        results = sdk.brownfield_probe(".gitignore", project_dir=tmp_path)
        assert len(results) == 1
        assert results[0].path == ".gitignore"
        assert results[0].exists is False

    def test_multiple_artifacts_returned_in_order(self, tmp_path):
        """Multiple artifacts returned in the same order given."""
        (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
        results = sdk.brownfield_probe(["a.txt", "missing.txt"], project_dir=tmp_path)
        assert len(results) == 2
        assert results[0].path == "a.txt"
        assert results[0].exists is True
        assert results[1].path == "missing.txt"
        assert results[1].exists is False

    def test_never_raises_on_unreadable_path(self, tmp_path):
        """An unreadable file path → exists=False, no exception raised."""
        # Simulate an unreadable path by pointing to a subpath under a file
        (tmp_path / "afile").write_text("x")
        # Trying to stat a path inside a file (e.g. afile/child) triggers OSError
        results = sdk.brownfield_probe(["afile/child"], project_dir=tmp_path)
        assert len(results) == 1
        assert results[0].exists is False
        assert results[0].empty is False


# --------------------------------------------------------------------------- #
# SC-004 — merge_append_lines / idempotent_write(merge=True)                  #
# --------------------------------------------------------------------------- #
class TestMergeAppendLines:
    def test_append_new_lines(self):
        """New lines from body are appended after existing content."""
        existing = "*.pyc\n__pycache__/\n"
        body = "*.pyc\n.env\n.DS_Store\n"
        result = sdk.merge_append_lines(existing, body)
        lines = result.splitlines()
        # Existing lines preserved first
        assert lines[0] == "*.pyc"
        assert lines[1] == "__pycache__/"
        # New lines appended
        assert ".env" in lines
        assert ".DS_Store" in lines
        # No duplicates
        assert lines.count("*.pyc") == 1

    def test_idempotent_second_call_returns_unchanged(self):
        """merge_append_lines called twice with same body → no change on 2nd call."""
        existing = "*.pyc\n"
        body = "*.pyc\n.env\n"
        merged_once = sdk.merge_append_lines(existing, body)
        merged_twice = sdk.merge_append_lines(merged_once, body)
        assert merged_once == merged_twice

    def test_dedup_body_line_already_in_existing(self):
        """A body line already in existing is NOT re-added."""
        existing = "*.pyc\n.env\n"
        body = "*.pyc\n.env\n.DS_Store\n"
        result = sdk.merge_append_lines(existing, body)
        assert result.count(".env") == 1
        assert result.count("*.pyc") == 1
        assert ".DS_Store" in result

    def test_dedup_body_line_appearing_twice_in_body(self):
        """A body line appearing twice is appended only once."""
        existing = "a\n"
        body = "b\nb\nc\n"
        result = sdk.merge_append_lines(existing, body)
        assert result.count("b") == 1
        assert "c" in result

    def test_nothing_new_returns_existing_unchanged(self):
        """When no new lines, existing_text is returned byte-identical."""
        existing = "*.pyc\n.env\n"
        body = "*.pyc\n.env\n"
        result = sdk.merge_append_lines(existing, body)
        assert result == existing

    def test_existing_order_preserved_new_lines_appended(self):
        """Existing lines stay in their original order; new lines come after."""
        existing = "b\na\n"
        body = "c\nb\na\n"
        result = sdk.merge_append_lines(existing, body)
        lines = result.splitlines()
        assert lines[:2] == ["b", "a"]
        assert lines[2] == "c"

    def test_trailing_whitespace_insensitive_membership(self):
        """A body line matching existing after rstrip is treated as already present."""
        existing = "*.pyc\n"
        body = "*.pyc   \n"   # trailing spaces — same content after rstrip
        result = sdk.merge_append_lines(existing, body)
        # No new line should have been added
        assert result == existing


class TestIdempotentWriteMerge:
    def test_merge_creates_when_file_absent(self, tmp_path):
        """merge=True on a missing file behaves like a normal create."""
        diff = sdk.idempotent_write(
            ".gitignore", "*.pyc\n", project_dir=tmp_path, merge=True
        )
        assert diff.kind == "create"
        assert (tmp_path / ".gitignore").read_text() == "*.pyc\n"

    def test_merge_appends_new_lines(self, tmp_path):
        """merge=True with existing non-empty file appends only new lines."""
        (tmp_path / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
        diff = sdk.idempotent_write(
            ".gitignore", "*.pyc\n.env\n", project_dir=tmp_path, merge=True
        )
        assert diff.kind == "modify"
        content = (tmp_path / ".gitignore").read_text()
        assert "*.pyc" in content
        assert ".env" in content
        assert content.count("*.pyc") == 1

    def test_merge_idempotent_second_run_is_skip(self, tmp_path):
        """merge=True called twice with same body → second call is skip."""
        (tmp_path / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
        body = "*.pyc\n.env\n"
        first = sdk.idempotent_write(
            ".gitignore", body, project_dir=tmp_path, merge=True
        )
        assert first.kind == "modify"
        second = sdk.idempotent_write(
            ".gitignore", body, project_dir=tmp_path, merge=True
        )
        assert second.kind == "skip"

    def test_merge_takes_precedence_over_reconcile(self, tmp_path):
        """When merge=True and reconcile=True, merge path wins (no full overwrite)."""
        (tmp_path / ".gitignore").write_text("existing_line\n", encoding="utf-8")
        diff = sdk.idempotent_write(
            ".gitignore", "existing_line\nnew_line\n",
            project_dir=tmp_path, merge=True, reconcile=True
        )
        assert diff.kind == "modify"
        content = (tmp_path / ".gitignore").read_text()
        assert "existing_line" in content
        assert "new_line" in content
        assert content.count("existing_line") == 1

    def test_merge_inspect_does_not_write(self, tmp_path):
        """merge=True with inspect=True does not write to disk."""
        (tmp_path / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
        diff = sdk.idempotent_write(
            ".gitignore", "*.pyc\n.env\n",
            project_dir=tmp_path, merge=True, inspect=True
        )
        assert diff.kind == "modify"
        # File on disk must be unchanged
        assert (tmp_path / ".gitignore").read_text() == "*.pyc\n"

    def test_merge_skip_when_nothing_new(self, tmp_path):
        """merge=True with body fully contained in existing → skip."""
        (tmp_path / ".gitignore").write_text("*.pyc\n.env\n", encoding="utf-8")
        diff = sdk.idempotent_write(
            ".gitignore", "*.pyc\n", project_dir=tmp_path, merge=True
        )
        assert diff.kind == "skip"


# --------------------------------------------------------------------------- #
# SC-006 — looks_like_secret new shapes + negatives                           #
# --------------------------------------------------------------------------- #
class TestLooksLikeSecret:
    # ── New shapes must be detected ─────────────────────────────────────────
    def test_google_api_key(self):
        """AIza + 35 chars."""
        val = "AIza" + "A" * 35
        assert sdk.looks_like_secret(val) is not None

    def test_stripe_sk_live(self):
        """sk_live_ prefix."""
        val = "sk_live_" + "A" * 24
        assert sdk.looks_like_secret(val) is not None

    def test_stripe_rk_live(self):
        """rk_live_ prefix."""
        val = "rk_live_" + "A" * 24
        assert sdk.looks_like_secret(val) is not None

    def test_twilio_api_key(self):
        """SK + 32 hex chars."""
        val = "SK" + "a" * 32
        assert sdk.looks_like_secret(val) is not None

    def test_sendgrid_key(self):
        """SG. + 22 chars + . + 43 chars."""
        val = "SG." + "A" * 22 + "." + "B" * 43
        assert sdk.looks_like_secret(val) is not None

    def test_npm_token(self):
        """npm_ + 36 alphanum chars."""
        val = "npm_" + "A" * 36
        assert sdk.looks_like_secret(val) is not None

    def test_pypi_token(self):
        """pypi- prefix."""
        val = "pypi-" + "A" * 20
        assert sdk.looks_like_secret(val) is not None

    def test_jwt(self):
        """eyJ header + two more dotted segments."""
        val = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        assert sdk.looks_like_secret(val) is not None

    # ── Original patterns still detected ────────────────────────────────────
    def test_github_token_still_detected(self):
        """Original ghp_ shape is still detected after widening."""
        val = "ghp_" + "A" * 20
        assert sdk.looks_like_secret(val) is not None

    # ── Negatives: must NOT match ────────────────────────────────────────────
    def test_uuid_v4_not_secret(self):
        """A UUIDv4 must not match any pattern."""
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        assert sdk.looks_like_secret(uuid) is None

    def test_40_char_git_sha_not_secret(self):
        """A 40-char hex git SHA must not match."""
        sha = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
        assert sdk.looks_like_secret(sha) is None

    def test_semver_not_secret(self):
        """A semver like 1.2.3-rc.1 must not match."""
        assert sdk.looks_like_secret("1.2.3-rc.1") is None


# --------------------------------------------------------------------------- #
# SC-005 — manifest [brownfield] parsing                                      #
# --------------------------------------------------------------------------- #
class TestManifestBrownfield:
    def test_valid_brownfield_section_parsed(self, tmp_path):
        """[brownfield] with valid entries populates manifest.brownfield."""
        toml = write_toml(tmp_path, MINIMAL_VALID + textwrap.dedent("""
            [[brownfield]]
            path = ".gitignore"
            policy = "merge"

            [[brownfield]]
            path = "LICENSE"
            policy = "preserve"
        """))
        m = parse_manifest(toml)
        assert len(m.errors) == 0
        assert len(m.brownfield) == 2
        assert m.brownfield[0].path == ".gitignore"
        assert m.brownfield[0].policy == "merge"
        assert m.brownfield[1].path == "LICENSE"
        assert m.brownfield[1].policy == "preserve"

    def test_overwrite_policy_valid(self, tmp_path):
        """'overwrite' is a valid policy."""
        toml = write_toml(tmp_path, MINIMAL_VALID + textwrap.dedent("""
            [[brownfield]]
            path = ".gitignore"
            policy = "overwrite"
        """))
        m = parse_manifest(toml)
        assert len(m.errors) == 0
        assert m.brownfield[0].policy == "overwrite"

    def test_unknown_policy_produces_setup_error(self, tmp_path):
        """An unknown policy value → SetupError in manifest.errors (no raise)."""
        toml = write_toml(tmp_path, MINIMAL_VALID + textwrap.dedent("""
            [[brownfield]]
            path = ".gitignore"
            policy = "clobber"
        """))
        m = parse_manifest(toml)
        assert any(
            e.error_code == ErrorCode.MANIFEST_MALFORMED for e in m.errors
        ), f"Expected MANIFEST_MALFORMED in errors, got: {m.errors}"
        # The bad entry is skipped — brownfield list is empty
        assert len(m.brownfield) == 0

    def test_no_brownfield_section_backward_compatible(self, tmp_path):
        """A module with no [brownfield] section has empty brownfield list."""
        toml = write_toml(tmp_path, MINIMAL_VALID)
        m = parse_manifest(toml)
        assert len(m.errors) == 0
        assert m.brownfield == []

    def test_inline_table_style_also_accepted(self, tmp_path):
        """Top-level brownfield as an array of inline tables also works.

        Note: in TOML, a bare `brownfield = [...]` key must appear BEFORE any
        [table] headers (or at top-level scope) to be parsed as a top-level key.
        We place it first in the TOML to avoid falling inside [module].
        """
        content = textwrap.dedent("""\
            brownfield = [
              {path = ".env.example", policy = "preserve"},
            ]

            [meta]
            repository = "github.com/test/repo"
            author = "test"

            [module]
            id = "test-module"
            name = "Test"
            version = "1.0.0"
            description = "A test module"
            reconcile = false
        """)
        toml = write_toml(tmp_path, content)
        m = parse_manifest(toml)
        assert len(m.errors) == 0
        assert len(m.brownfield) == 1
        assert m.brownfield[0].path == ".env.example"
        assert m.brownfield[0].policy == "preserve"
