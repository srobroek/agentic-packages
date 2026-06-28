"""Spec 006 Phase 1 — unit tests for the two new SDK primitives.

- splice_between_sentinels: span-replace inside a file (create/modify/skip,
  malformed begin-without-end, missing-markers append fallback, idempotence,
  inspect-no-write, outside-span byte-preservation).
- scan_top_level_dirs: shallow dir scan (dirs only, hidden included, missing→empty).

Run via:
  uv run --with pytest pytest -q packages/project-setup/tests/test_sdk_splice.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    # the runner dir must be importable for sdk's plain sibling imports (spec 005 OQ-2)
    for p in (str(_RUNNER), str(_RUNNER / "sources")):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sdk = _load("sdk")

BEGIN = "<!-- BEGIN ps:architecture -->"
END = "<!-- END ps:architecture -->"


# --------------------------------------------------------------------------- #
# scan_top_level_dirs                                                          #
# --------------------------------------------------------------------------- #
def test_scan_dirs_only_no_files(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "README.md").write_text("x")
    got = sdk.scan_top_level_dirs(tmp_path)
    assert got == frozenset({"src", "tests"})


def test_scan_includes_hidden_dirs(tmp_path):
    (tmp_path / ".github").mkdir()
    (tmp_path / "src").mkdir()
    assert sdk.scan_top_level_dirs(tmp_path) == frozenset({".github", "src"})


def test_scan_no_recursion(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "nested").mkdir()
    assert sdk.scan_top_level_dirs(tmp_path) == frozenset({"src"})


def test_scan_missing_dir_returns_empty(tmp_path):
    assert sdk.scan_top_level_dirs(tmp_path / "does-not-exist") == frozenset()


def test_scan_empty_dir_returns_empty(tmp_path):
    assert sdk.scan_top_level_dirs(tmp_path) == frozenset()


# --------------------------------------------------------------------------- #
# splice_between_sentinels                                                     #
# --------------------------------------------------------------------------- #
def _agents_md(tmp_path, body: str) -> Path:
    p = tmp_path / "AGENTS.md"
    p.write_text(body, encoding="utf-8")
    return p


def test_splice_create_when_file_absent(tmp_path):
    diff = sdk.splice_between_sentinels(
        "AGENTS.md", BEGIN, END, "hello", project_dir=tmp_path, missing="append",
    )
    assert diff.kind == "create"
    content = (tmp_path / "AGENTS.md").read_text()
    assert BEGIN in content and END in content and "hello" in content


def test_splice_replaces_only_the_span(tmp_path):
    _agents_md(tmp_path, f"# Title\n\n## Architecture\n{BEGIN}\nOLD\n{END}\n\n## Build\nkeep me\n")
    diff = sdk.splice_between_sentinels(
        "AGENTS.md", BEGIN, END, "NEW BODY", project_dir=tmp_path,
    )
    assert diff.kind == "modify"
    content = (tmp_path / "AGENTS.md").read_text()
    assert "NEW BODY" in content and "OLD" not in content
    # everything outside the span is preserved byte-for-byte
    assert content.startswith("# Title\n\n## Architecture\n")
    assert content.endswith("## Build\nkeep me\n")


def test_splice_idempotent_skip_on_identical(tmp_path):
    _agents_md(tmp_path, f"head\n{BEGIN}\nSAME\n{END}\ntail\n")
    diff = sdk.splice_between_sentinels("AGENTS.md", BEGIN, END, "SAME", project_dir=tmp_path)
    assert diff.kind == "skip"


def test_splice_inspect_writes_nothing(tmp_path):
    p = _agents_md(tmp_path, f"{BEGIN}\nOLD\n{END}\n")
    before = p.read_text()
    diff = sdk.splice_between_sentinels(
        "AGENTS.md", BEGIN, END, "NEW", project_dir=tmp_path, inspect=True,
    )
    assert diff.kind == "modify"  # would modify
    assert p.read_text() == before  # but did not write


def test_splice_malformed_begin_without_end_skips(tmp_path):
    _agents_md(tmp_path, f"head\n{BEGIN}\ndangling, no end marker\n")
    warns: list[str] = []
    diff = sdk.splice_between_sentinels(
        "AGENTS.md", BEGIN, END, "NEW", project_dir=tmp_path, warnings=warns,
    )
    assert diff.kind == "skip"
    assert any("malformed" in w.lower() for w in warns)


def test_splice_missing_markers_appends_after_heading(tmp_path):
    _agents_md(tmp_path, "# Title\n\n## Architecture\n\n## Build\nx\n")
    warns: list[str] = []
    diff = sdk.splice_between_sentinels(
        "AGENTS.md", BEGIN, END, "BODY", project_dir=tmp_path, missing="append", warnings=warns,
    )
    assert diff.kind == "modify"
    content = (tmp_path / "AGENTS.md").read_text()
    # appended right after the "## Architecture" heading, before "## Build"
    arch_idx = content.index("## Architecture")
    build_idx = content.index("## Build")
    begin_idx = content.index(BEGIN)
    assert arch_idx < begin_idx < build_idx
    assert any("markers absent" in w.lower() for w in warns)


def test_splice_missing_markers_error_mode_skips(tmp_path):
    _agents_md(tmp_path, "# Title\nno markers here\n")
    warns: list[str] = []
    diff = sdk.splice_between_sentinels(
        "AGENTS.md", BEGIN, END, "BODY", project_dir=tmp_path, missing="error", warnings=warns,
    )
    assert diff.kind == "skip"
    assert "no markers here" in (tmp_path / "AGENTS.md").read_text()


def test_splice_then_reproduce_replaces_cleanly(tmp_path):
    # first run: missing markers → append; second run: markers present → replace span
    _agents_md(tmp_path, "## Architecture\n")
    sdk.splice_between_sentinels("AGENTS.md", BEGIN, END, "V1", project_dir=tmp_path)
    diff2 = sdk.splice_between_sentinels("AGENTS.md", BEGIN, END, "V2", project_dir=tmp_path)
    assert diff2.kind == "modify"
    content = (tmp_path / "AGENTS.md").read_text()
    assert "V2" in content and "V1" not in content
    assert content.count(BEGIN) == 1  # no duplicate markers
