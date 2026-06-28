"""G8 secret-shape detection tests for spec 004 FR-018/019 (widened in spec 017).

Covers:
  SC-006: looks_like_secret new shapes + UUID/SHA/semver negatives.

Run via:
  uv run --with pytest pytest -q packages/project-setup/tests/test_g8_secret_shapes.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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
