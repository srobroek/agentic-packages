#!/usr/bin/env python3
"""Tests for the ADR renderer.

The renderer's input is a `bd export` JSONL stream, so these stub `export_decisions`
rather than a `bd` binary: the seam is the data, and a fake `bd` would test the
subprocess plumbing instead of the rendering. The plumbing's failure modes -- no
`bd`, no database -- are covered separately through `run_bd`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render_adrs.py"


def load_module():
    spec = importlib.util.spec_from_file_location("render_adrs", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["render_adrs"] = module
    spec.loader.exec_module(module)
    return module


mod = load_module()


def bead(**overrides) -> dict:
    """A minimally valid closed decision bead."""
    base = {
        "id": "adr-1",
        "issue_type": "decision",
        "status": "closed",
        "title": "Adopt X for Y",
        "created_at": "2026-01-01T00:00:00Z",
        "closed_at": "2026-01-02T00:00:00Z",
        "description": (
            "## Decision\nAdopt X.\n\n"
            "## Rationale\nX satisfies the driver.\n\n"
            "## Alternatives Considered\nY, rejected because slow."
        ),
    }
    base.update(overrides)
    return base


# --- slugify -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Adopt X for Y", "adopt-x-for-y"),
        ("Use C++ / Rust?", "use-c-rust"),
        ("  leading and trailing  ", "leading-and-trailing"),
        ("!!!", "untitled"),
        ("", "untitled"),
        ("Multiple   spaces", "multiple-spaces"),
    ],
)
def test_slugify(title, expected):
    assert mod.slugify(title) == expected


def test_slugify_never_yields_a_path_separator():
    # A title with a slash must not escape docs/adr/.
    assert "/" not in mod.slugify("a/../../etc/passwd")


# --- section parsing ---------------------------------------------------------


def test_sections_split_on_headings():
    got = mod.sections_from(bead())
    assert got["Decision"] == "Adopt X."
    assert got["Rationale"] == "X satisfies the driver."
    assert got["Alternatives Considered"] == "Y, rejected because slow."


def test_preamble_before_first_heading_is_kept():
    got = mod.sections_from(bead(description="Some context.\n\n## Decision\nX."))
    assert got["_preamble"] == "Some context."
    assert got["Decision"] == "X."


def test_empty_description_yields_no_sections():
    assert mod.sections_from(bead(description="")) == {}
    assert mod.sections_from(bead(description=None)) == {}


# --- supersession ------------------------------------------------------------


def test_supersedes_edge_is_read_from_dependencies():
    # `bd supersede <old> --with <new>` puts the edge on the OLD bead, pointing at
    # the new one. Verified against bd 1.1.2.
    b = bead(
        dependencies=[
            {"issue_id": "adr-1", "depends_on_id": "adr-9", "type": "supersedes"}
        ]
    )
    _, superseded_by = mod.supersession(b)
    assert superseded_by == ["adr-9"]


def test_non_supersedes_edges_are_ignored():
    b = bead(
        dependencies=[
            {"issue_id": "adr-1", "depends_on_id": "wk-3", "type": "relates-to"}
        ]
    )
    _, superseded_by = mod.supersession(b)
    assert superseded_by == []


def test_superseded_bead_renders_as_superseded():
    b = bead(
        dependencies=[
            {"issue_id": "adr-1", "depends_on_id": "adr-9", "type": "supersedes"}
        ]
    )
    out = mod.render_one(b, 1)
    assert "status: superseded" in out
    assert "superseded-by: adr-9" in out
    assert "Superseded by adr-9" in out


def test_unsuperseded_bead_renders_as_accepted():
    out = mod.render_one(bead(), 1)
    assert "status: accepted" in out
    assert "superseded" not in out


# --- rendering ---------------------------------------------------------------


def test_sections_map_to_madr_headings():
    out = mod.render_one(bead(), 3)
    assert "## Considered Options" in out
    assert "## Decision Outcome" in out
    assert "### Rationale" in out
    assert "number: 3" in out
    assert "bead: adr-1" in out


def test_generated_banner_names_the_bead():
    # Without this an author edits the file and loses the edit on the next commit.
    out = mod.render_one(bead(), 1)
    assert "Edit the bead, not this file" in out
    assert "bd show adr-1" in out


def test_title_is_yaml_safe_when_it_contains_a_colon():
    out = mod.render_one(bead(title="Use X: Y"), 1)
    assert 'title: "Use X: Y"' in out


def test_spec_id_is_emitted_when_set():
    assert "spec: 042-x" in mod.render_one(bead(spec_id="042-x"), 1)


def test_spec_id_is_omitted_when_absent():
    assert "spec:" not in mod.render_one(bead(), 1)


def test_design_and_notes_render_as_more_information():
    out = mod.render_one(bead(design="why it holds", notes="a running note"), 1)
    assert "## More Information" in out
    assert "why it holds" in out
    assert "a running note" in out
    # One heading, not two, when both fields are present.
    assert out.count("## More Information") == 1


def test_absent_sections_are_omitted_not_given_placeholders():
    # A placeholder reads as an answered question.
    out = mod.render_one(bead(description="## Decision\nX."), 1)
    assert "## Considered Options" not in out
    assert "TODO" not in out
    assert "{" not in out


def test_render_ends_with_exactly_one_newline():
    out = mod.render_one(bead(), 1)
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


# --- render_all --------------------------------------------------------------


@pytest.fixture
def stub_export(monkeypatch):
    def install(rows):
        monkeypatch.setattr(mod, "export_decisions", lambda repo: rows)

    return install


def test_only_closed_decisions_render(tmp_path, stub_export):
    stub_export(
        [
            bead(id="adr-1", status="closed", title="Closed one"),
            bead(id="adr-2", status="deferred", title="Proposed one"),
            bead(id="adr-3", status="open", title="Drafting one"),
        ]
    )
    written, skipped = mod.render_all(tmp_path)
    assert skipped is None
    names = sorted(p.name for p in written)
    assert names == ["0001-closed-one.md"]


def test_numbering_follows_creation_order_not_bead_id(tmp_path, stub_export):
    stub_export(
        [
            bead(id="adr-11", created_at="2026-01-01T00:00:00Z", title="First"),
            bead(id="adr-2", created_at="2026-02-01T00:00:00Z", title="Second"),
        ]
    )
    written, _ = mod.render_all(tmp_path)
    assert sorted(p.name for p in written) == ["0001-first.md", "0002-second.md"]


def test_numbering_is_stable_on_a_created_at_tie(tmp_path, stub_export):
    rows = [
        bead(id="adr-b", created_at="2026-01-01T00:00:00Z", title="Bee"),
        bead(id="adr-a", created_at="2026-01-01T00:00:00Z", title="Ay"),
    ]
    stub_export(rows)
    first, _ = mod.render_all(tmp_path)
    stub_export(list(reversed(rows)))
    for path in tmp_path.glob("docs/adr/*.md"):
        path.unlink()
    second, _ = mod.render_all(tmp_path)
    assert sorted(p.name for p in first) == sorted(p.name for p in second)


def test_no_database_is_not_a_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "export_decisions", lambda repo: None)
    written, skipped = mod.render_all(tmp_path)
    assert written == []
    assert skipped == "no beads database reachable"


def test_no_decisions_is_not_a_failure(tmp_path, stub_export):
    stub_export([])
    written, skipped = mod.render_all(tmp_path)
    assert written == []
    assert skipped == "no closed decision beads"


def test_renamed_decision_removes_old_projection(tmp_path, stub_export):
    stub_export([bead(title="Old title")])
    mod.render_all(tmp_path)
    old = tmp_path / "docs/adr/0001-old-title.md"

    stub_export([bead(title="New title")])
    changed, skipped = mod.render_all(tmp_path)

    assert skipped is None
    assert old in changed
    assert not old.exists()
    assert (tmp_path / "docs/adr/0001-new-title.md").exists()


def test_removed_decisions_remove_all_projections(tmp_path, stub_export):
    stub_export([bead()])
    mod.render_all(tmp_path)
    old = tmp_path / "docs/adr/0001-adopt-x-for-y.md"

    stub_export([])
    changed, skipped = mod.render_all(tmp_path)

    assert skipped is None
    assert changed == [old]
    assert not old.exists()


def test_second_run_rewrites_nothing(tmp_path, stub_export):
    stub_export([bead()])
    first, _ = mod.render_all(tmp_path)
    assert len(first) == 1
    second, _ = mod.render_all(tmp_path)
    assert second == []


def test_check_mode_does_not_write(tmp_path, stub_export):
    """The regression that mattered: --check repaired the drift it reported.

    One shared code path meant the gate failed, silently corrected the file, and a
    second run passed -- with the author's edit destroyed and never committed.
    """
    stub_export([bead()])
    mod.render_all(tmp_path, write=True)
    target = tmp_path / "docs/adr/0001-adopt-x-for-y.md"
    target.write_text("hand-edited drift\n", encoding="utf-8")

    stale, _ = mod.render_all(tmp_path, write=False)

    assert stale == [target]
    assert target.read_text(encoding="utf-8") == "hand-edited drift\n"


def test_check_mode_creates_no_directory(tmp_path, stub_export):
    stub_export([bead()])
    mod.render_all(tmp_path, write=False)
    assert not (tmp_path / "docs").exists()


# --- main / exit codes -------------------------------------------------------


def test_main_exits_zero_without_bd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod.shutil, "which", lambda name: None)
    assert mod.main([]) == 0


def test_main_check_exits_one_on_drift(tmp_path, monkeypatch, stub_export):
    monkeypatch.chdir(tmp_path)
    stub_export([bead()])
    mod.render_all(tmp_path, write=True)
    (tmp_path / "docs/adr/0001-adopt-x-for-y.md").write_text("drift\n", encoding="utf-8")
    assert mod.main(["--check"]) == 1


def test_main_check_exits_zero_when_current(tmp_path, monkeypatch, stub_export):
    monkeypatch.chdir(tmp_path)
    stub_export([bead()])
    mod.render_all(tmp_path, write=True)
    assert mod.main(["--check"]) == 0


def test_main_returns_one_when_rendering_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        mod, "render_all", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    assert mod.main([]) == 1


def test_malformed_export_line_does_not_discard_the_rest(tmp_path, monkeypatch):
    """One bad JSONL line must not lose every other decision."""
    payload = '{"id":"adr-1","issue_type":"decision"}\n[]\nNOT JSON\n'

    def fake_run_bd(args, cwd):
        out = Path(args[args.index("--output") + 1])
        out.write_text(payload, encoding="utf-8")

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(mod, "run_bd", fake_run_bd)
    rows = mod.export_decisions(tmp_path)
    assert rows == [{"id": "adr-1", "issue_type": "decision"}]


def test_export_returns_none_when_bd_fails(tmp_path, monkeypatch):
    class Result:
        returncode = 1

    monkeypatch.setattr(mod, "run_bd", lambda args, cwd: Result())
    assert mod.export_decisions(tmp_path) is None


def test_run_bd_returns_none_when_bd_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(mod.shutil, "which", lambda name: None)
    assert mod.run_bd(["export"], tmp_path) is None
