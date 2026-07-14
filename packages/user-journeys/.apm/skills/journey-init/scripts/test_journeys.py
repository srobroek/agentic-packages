"""Tests for journeys.py (pytest, stdlib only)."""

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("journeys", HERE / "journeys.py")
assert spec is not None and spec.loader is not None
journeys = importlib.util.module_from_spec(spec)
sys.modules["journeys"] = journeys
spec.loader.exec_module(journeys)

GOOD_JOURNEY = """---
id: J01
title: Buy a widget
version: 2
status: active
last_reviewed: 2026-07-10
actors: [shopper]
surfaces: [checkout, cart]
interfaces: [web-ui]
trace: []
---

## Goal
Buy the thing.

## Preconditions
- P1: A seeded catalog.

## Steps
### S1 — Open the cart {#S1}
- **Do:** open the cart.
- **Expect:** the cart lists one widget.

### S2a — Pay {#S2a}
- **Do:** pay.
- **Expect:** confirmation is shown.

## Success criteria
- SC1: order exists (S1, S2a).

## Known gaps

## Delta log
- **Δ2** 2026-07-14 · S2a · behavior-change
  Payment moved to a dialog.
  Evidence: PR #12 · by: journey-scribe (intent-gated)
"""

GOOD_RUN = """---
journey: J01
journey_version: 2
commit: abc1234
date: 2026-07-14T09:31Z
mode: full
interface: web-ui (playwright)
result: fail
steps: {S1: pass, S2a: fail}
findings: [JV-0001]
---
## S2a — FAIL
Expected confirmation; observed spinner.
"""


def make_journey(root, body=GOOD_JOURNEY, name="J01-buy-widget", runs=()):
    jdir = root / name
    jdir.mkdir(parents=True)
    (jdir / "journey.md").write_text(body, encoding="utf-8")
    if runs:
        (jdir / "runs").mkdir()
        for i, run in enumerate(runs):
            (jdir / "runs" / f"2026-07-14T09-3{i}Z.md").write_text(run, encoding="utf-8")
    return jdir


def test_frontmatter_parses_scalars_lists_and_dicts():
    fm = journeys.parse_frontmatter(GOOD_RUN)
    assert fm["journey"] == "J01"
    assert fm["steps"] == {"S1": "pass", "S2a": "fail"}
    assert fm["findings"] == ["JV-0001"]


def test_frontmatter_missing_returns_empty():
    assert journeys.parse_frontmatter("# no frontmatter\n") == {}
    assert journeys.parse_frontmatter("---\nid: J01\n") == {}  # unterminated


def test_lint_clean_journey_passes(tmp_path):
    make_journey(tmp_path, runs=[GOOD_RUN])
    assert journeys.cmd_lint(tmp_path) == 0


def test_lint_catches_structural_errors(tmp_path):
    bad = GOOD_JOURNEY.replace("### S1 — Open the cart {#S1}", "### S1 — Open the cart")
    bad = bad.replace("status: active", "status: golden")
    make_journey(tmp_path, body=bad)
    errors = []
    journeys.lint_journey(tmp_path / "J01-buy-widget", errors, {})
    text = "\n".join(errors)
    assert "missing `{#S<id>}` anchor" in text
    assert "status `golden`" in text


def test_lint_catches_duplicate_ids_and_bad_delta_refs(tmp_path):
    make_journey(tmp_path)
    dup = GOOD_JOURNEY.replace(
        "- **Δ2** 2026-07-14 · S2a · behavior-change",
        "- **Δ2** 2026-07-14 · S9 · behavior-change",
    )
    make_journey(tmp_path, body=dup, name="J01-duplicate")
    errors = []
    seen = {}
    for jdir in journeys.journey_dirs(tmp_path):
        journeys.lint_journey(jdir, errors, seen)
    text = "\n".join(errors)
    assert "duplicate id `J01`" in text
    assert "references unknown step S9" in text
    assert "does not start with `J01-`" not in text  # both dirs J01-*


def test_lint_checks_run_against_journey(tmp_path):
    bad_run = GOOD_RUN.replace("journey: J01", "journey: J02").replace(
        "steps: {S1: pass, S2a: fail}", "steps: {S1: pass, S3: fail}"
    )
    make_journey(tmp_path, runs=[bad_run])
    errors = []
    journeys.lint_journey(tmp_path / "J01-buy-widget", errors, {})
    text = "\n".join(errors)
    assert "journey `J02` != `J01`" in text
    assert "unknown step id S3" in text


def test_index_lists_latest_run(tmp_path):
    make_journey(tmp_path, runs=[GOOD_RUN])
    assert journeys.cmd_index(tmp_path) == 0
    index = (tmp_path / "INDEX.md").read_text(encoding="utf-8")
    assert "| [J01](J01-buy-widget/journey.md) | Buy a widget | active | v2 |" in index
    assert "2026-07-14T09:31Z fail (full)" in index


def test_index_counts_open_findings_and_shows_mode(tmp_path):
    make_journey(tmp_path, runs=[GOOD_RUN.replace("mode: full", "mode: changed-only(S1)")])
    (tmp_path / "TRACKER.md").write_text(
        "# Journey findings\n\n## JV-0001 — x\n\n<!-- journey-finding\n"
        "journey: J01\nstep: S2a\ntriage: suspected-regression\nseverity: P2\n-->\n"
        "status: open\n\n## JV-0002 — y\n\n<!-- journey-finding\n"
        "journey: J01\nstep: S1\n-->\nstatus: fixed\n",
        encoding="utf-8",
    )
    journeys.cmd_index(tmp_path)
    index = (tmp_path / "INDEX.md").read_text(encoding="utf-8")
    assert "fail (changed-only) | 1 |" in index


def test_prune_dry_run_then_delete(tmp_path):
    make_journey(tmp_path, runs=[GOOD_RUN, GOOD_RUN, GOOD_RUN])
    jdir = tmp_path / "J01-buy-widget"
    journeys.cmd_prune(tmp_path, keep=1, yes=False)
    assert len(list((jdir / "runs").glob("*.md"))) == 3
    journeys.cmd_prune(tmp_path, keep=1, yes=True)
    remaining = list((jdir / "runs").glob("*.md"))
    assert [p.name for p in remaining] == ["2026-07-14T09-32Z.md"]
