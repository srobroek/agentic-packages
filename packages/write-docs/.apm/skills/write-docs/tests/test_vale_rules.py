"""Behavioural tests for the WriteDocs Vale style and the slop-lint entrypoint.

Replaces test_slop_lint.py. Vale has no rule-test framework, so these drive the
real binary over fixtures and assert on rule names and the exit contract.

Skipped when `vale` is absent so a checkout without it still collects.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
ENTRY = SKILL / "scripts" / "slop-lint.sh"
CONFIG = SKILL / "vale" / ".vale.ini"
FIXTURES = Path(__file__).parent / "fixtures"

pytestmark = pytest.mark.skipif(
    shutil.which("vale") is None or not (SKILL / "vale" / "styles" / "ai-tells").is_dir(),
    reason="vale not installed, or packaged styles not synced (`vale sync`)",
)


def rules(*paths: Path) -> dict[str, int]:
    """Rule name -> hit count for the given fixtures."""
    proc = subprocess.run(
        ["vale", f"--config={CONFIG}", "--output=JSON", "--no-exit", *map(str, paths)],
        capture_output=True,
        text=True,
        check=False,
    )
    counts: dict[str, int] = {}
    for alerts in json.loads(proc.stdout or "{}").values():
        for alert in alerts:
            counts[alert["Check"]] = counts.get(alert["Check"], 0) + 1
    return counts


def run_entry(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(ENTRY), *args], capture_output=True, text=True, check=False
    )


# --- E1 status language ------------------------------------------------------


def test_status_language_fires_and_respects_the_lookahead():
    # "currently running" is runtime state, not doc status: the negative
    # lookahead ported from slop-lint.py:32 must still exclude it.
    found = rules(FIXTURES / "e1-status.md")
    assert found.get("WriteDocs.StatusLanguage") == 3


# --- E5 chat-session leakage -------------------------------------------------


def test_chat_leakage_catches_disclaimers_and_artifacts():
    found = rules(FIXTURES / "e5-leakage.md")
    assert found.get("WriteDocs.ChatLeakage", 0) >= 3


# --- W1 prose block ----------------------------------------------------------


def test_long_prose_block_warns():
    assert rules(FIXTURES / "w1-long.md").get("WriteDocs.ProseBlock") == 1


def test_prose_block_ignores_lists_and_tables():
    """The old line-prefix heuristic counted wrapped list continuations and
    table rows as prose. Vale's paragraph scope does not."""
    assert "WriteDocs.ProseBlock" not in rules(FIXTURES / "w1-prose.md")


# --- Code and structure exclusions ------------------------------------------


def test_inline_code_and_fences_are_not_scanned(tmp_path):
    doc = tmp_path / "code.md"
    doc.write_text(
        "Run `apm compile --no-constitution` to skip it.\n\n"
        "```\nA powerful robust WIP tool.\n```\n",
        encoding="utf-8",
    )
    found = rules(doc)
    assert "WriteDocs.SlopLexicon" not in found
    assert "WriteDocs.StatusLanguage" not in found
    assert "WriteDocs.InternalRefs" not in found


def test_unicode_dash_is_banned_but_double_hyphen_is_not(tmp_path):
    doc = tmp_path / "dash.md"
    doc.write_text("An em dash — here.\n\nDouble hyphens -- are fine.\n", encoding="utf-8")
    assert rules(doc).get("WriteDocs.NoUnicodeDash") == 1


# --- Genre routing -----------------------------------------------------------


def test_internal_refs_off_under_specs(tmp_path, monkeypatch):
    specs = tmp_path / "specs" / "001"
    specs.mkdir(parents=True)
    doc = specs / "spec.md"
    doc.write_text("Per the spec, see ADR-7 for the constitution.\n", encoding="utf-8")
    # Section globs match the path Vale is given, so run from tmp_path.
    monkeypatch.chdir(tmp_path)
    proc = subprocess.run(
        ["vale", f"--config={CONFIG}", "--output=JSON", "--no-exit", "specs/001/spec.md"],
        capture_output=True,
        text=True,
        check=False,
    )
    checks = {
        a["Check"] for alerts in json.loads(proc.stdout or "{}").values() for a in alerts
    }
    assert "WriteDocs.InternalRefs" not in checks


# --- Entrypoint exit contract ------------------------------------------------


def test_exit_zero_when_clean():
    assert run_entry(str(FIXTURES / "clean.md")).returncode == 0


def test_exit_one_on_error():
    assert run_entry(str(FIXTURES / "e1-status.md")).returncode == 1


def test_warnings_alone_still_exit_zero(tmp_path):
    doc = tmp_path / "warn.md"
    doc.write_text("It simply works.\n", encoding="utf-8")
    proc = run_entry(str(doc))
    assert "WARNING" in proc.stdout
    assert proc.returncode == 0


def test_usage_errors_exit_two():
    assert run_entry().returncode == 2
    assert run_entry("--genre", "bogus", str(FIXTURES / "clean.md")).returncode == 2
