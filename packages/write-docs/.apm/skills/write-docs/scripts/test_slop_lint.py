"""Tests for slop-lint.py. Run with pytest."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent / "slop-lint.py"
spec = importlib.util.spec_from_file_location("slop_lint", SCRIPT)
assert spec is not None and spec.loader is not None
slop_lint = importlib.util.module_from_spec(spec)
sys.modules["slop_lint"] = slop_lint
spec.loader.exec_module(slop_lint)


def run(tmp_path, content, genre="consumer", name="README.md"):
    f = tmp_path / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")
    return slop_lint.lint(f, genre)


def codes(findings):
    return {c for _, c, _, _ in findings}


# --- E1 status language ---------------------------------------------------


def test_status_language_errors(tmp_path):
    doc = "# Tool\n\nThis feature is under construction.\nSupport is coming soon.\n"
    found = run(tmp_path, doc)
    assert codes(found) == {"E1"}
    assert len([f for f in found if f[1] == "E1"]) == 2


def test_currently_is_status_language(tmp_path):
    found = run(tmp_path, "Currently, only JSON output is supported.\n")
    assert "E1" in codes(found)


def test_currently_running_is_runtime_state_not_status(tmp_path):
    found = run(tmp_path, "Lists currently running jobs.\n")
    assert "E1" not in codes(found)


def test_wip_and_tbd(tmp_path):
    found = run(tmp_path, "WIP: docs.\nSchema: TBD.\n")
    assert len([f for f in found if f[1] == "E1"]) == 2


# --- E2 slop lexicon --------------------------------------------------------


def test_slop_lexicon_errors(tmp_path):
    doc = (
        "A powerful, comprehensive toolkit that seamlessly integrates and "
        "leverages robust primitives.\n"
    )
    found = [f for f in run(tmp_path, doc) if f[1] == "E2"]
    assert found  # at least one E2 on the line


def test_blazingly_fast(tmp_path):
    assert "E2" in codes(run(tmp_path, "Blazingly fast parsing.\n"))


def test_plain_factual_line_passes(tmp_path):
    doc = (
        "# csv2json\n\n"
        "Converts CSV files to JSON.\n\n"
        "## Install\n\n"
        "Run the install command from the release page.\n"
    )
    assert run(tmp_path, doc) == []


def test_inline_code_identifier_is_not_slop_prose(tmp_path):
    found = run(
        tmp_path,
        "Install the `comprehensive-review` package with `apm install`.\n",
    )
    assert "E2" not in codes(found)


def test_inline_code_does_not_hide_adjacent_slop_prose(tmp_path):
    found = run(
        tmp_path,
        "The comprehensive `comprehensive-review` package is powerful.\n",
    )
    assert "E2" in codes(found)


def test_double_backtick_code_span_is_not_slop_prose(tmp_path):
    found = run(tmp_path, "The identifier is ``comprehensive-review``.\n")
    assert "E2" not in codes(found)


def test_escaped_backticks_do_not_hide_slop_prose(tmp_path):
    found = run(tmp_path, r"The \`comprehensive-review\` package." + "\n")
    e2 = [finding for finding in found if finding[1] == "E2"]
    assert e2 == [("ERROR", "E2", 1, "slop lexicon: 'comprehensive'")]


def test_inline_masking_preserves_later_error_line_and_text(tmp_path):
    found = run(
        tmp_path,
        "Use `comprehensive-review`.\nThe comprehensive mode is enabled.\n",
    )
    e2 = [finding for finding in found if finding[1] == "E2"]
    assert e2 == [("ERROR", "E2", 2, "slop lexicon: 'comprehensive'")]


def test_inline_masking_preserves_source_offsets():
    line = "Use `comprehensive-review`, then reject comprehensive prose."
    masked = slop_lint._strip_inline_code(line)
    assert len(masked) == len(line)
    assert masked.index("comprehensive") == line.rindex("comprehensive")


# --- E3 internal references (consumer only) --------------------------------


def test_internal_refs_error_in_consumer(tmp_path):
    doc = "See specs/001-parser/spec.md and ADR-12 for details.\n"
    found = run(tmp_path, doc, genre="consumer")
    assert "E3" in codes(found)


def test_internal_refs_allowed_in_internal(tmp_path):
    doc = "See specs/001-parser/spec.md and ADR-12 for details.\n"
    found = run(tmp_path, doc, genre="internal")
    assert "E3" not in codes(found)


def test_extraction_lineage_is_internal_ref(tmp_path):
    found = run(tmp_path, "This module was extracted from the core package.\n")
    assert "E3" in codes(found)


def test_product_name_speckit_is_not_internal_ref(tmp_path):
    found = run(tmp_path, "Install the SpecKit workflow with `apm install speckit`.\n")
    assert "E3" not in codes(found)


# --- E4 history narration ---------------------------------------------------


def test_history_narration_consumer(tmp_path):
    found = run(tmp_path, "Previously the parser used regex; we switched to a PEG grammar.\n")
    assert "E4" in codes(found)


def test_history_allowed_in_change_genre(tmp_path):
    found = run(tmp_path, "Previously the parser used regex; we switched to a PEG grammar.\n", genre="change")
    assert "E4" not in codes(found)


# --- E5 chat-session leakage -------------------------------------------------


def test_chat_leakage_self_identification(tmp_path):
    found = run(tmp_path, "As an AI, I cannot verify that claim.\n")
    assert "E5" in codes(found)


def test_chat_leakage_cutoff_disclaimer(tmp_path):
    found = run(tmp_path, "As of my last update, the endpoint was stable.\n")
    assert "E5" in codes(found)


def test_chat_leakage_placeholder_text(tmp_path):
    assert "E5" in codes(run(tmp_path, "This section would describe the schema.\n"))
    assert "E5" in codes(run(tmp_path, "Insert your API token here.\n"))


def test_chat_leakage_tool_artifacts(tmp_path):
    for artifact in ("oaicite", "contentReference", "[cite: 4]", "【4†source】"):
        found = run(tmp_path, f"See the reference {artifact} for details.\n")
        assert "E5" in codes(found), artifact


def test_chat_leakage_fires_in_every_genre(tmp_path):
    # Unlike the lexicon rules, leaked assistant output is never house style.
    for genre in ("consumer", "internal", "change"):
        found = run(tmp_path, "As an AI, I cannot browse.\n", genre=genre)
        assert "E5" in codes(found), genre


def test_chat_leakage_ignores_legitimate_prose(tmp_path):
    doc = (
        "The agent cannot write outside its scope.\n\n"
        "Update the manifest as of each release.\n\n"
        "This section describes the schema.\n"
    )
    assert "E5" not in codes(run(tmp_path, doc))


# --- W1 / W2 / W3 warnings ---------------------------------------------------


def test_long_prose_block_warns(tmp_path):
    doc = " ".join(["word"] * 90) + "\n"
    found = run(tmp_path, doc)
    assert ("WARN", "W1") in {(s, c) for s, c, _, _ in found}


def test_emoji_heading_warns(tmp_path):
    found = run(tmp_path, "# 🚀 Getting started\n")
    assert "W2" in codes(found)


def test_borderline_hype_warns_not_errors(tmp_path):
    found = run(tmp_path, "It just works out of the box.\n")
    w3 = [f for f in found if f[1] == "W3"]
    assert w3 and all(s == "WARN" for s, _, _, _ in w3)


# --- code fences and suppression ---------------------------------------------


def test_code_fences_are_skipped(tmp_path):
    doc = "```\n# WIP powerful seamlessly specs/x.md\n```\n"
    assert run(tmp_path, doc) == []


def test_inline_suppression(tmp_path):
    doc = "The robust mode retries twice. <!-- write-docs:allow E2 -->\n"
    assert "E2" not in codes(run(tmp_path, doc))


def test_suppression_on_previous_line(tmp_path):
    doc = "<!-- write-docs:allow E1 -->\nCurrently limited to 10 MB inputs.\n"
    assert "E1" not in codes(run(tmp_path, doc))


def test_suppression_is_code_specific(tmp_path):
    doc = "A robust tool. <!-- write-docs:allow E1 -->\n"
    assert "E2" in codes(run(tmp_path, doc))


# --- genre detection ----------------------------------------------------------


def test_genre_detection_readme_is_consumer():
    assert slop_lint.detect_genre(Path("README.md")) == "consumer"


def test_genre_detection_specs_is_internal():
    assert slop_lint.detect_genre(Path("specs/001/spec.md")) == "internal"
    assert slop_lint.detect_genre(Path("docs/adr/0001-choice.md")) == "internal"
    assert slop_lint.detect_genre(Path("CONTRIBUTING.md")) == "internal"
    assert slop_lint.detect_genre(Path(".specify/memory/constitution.md")) == "internal"


# --- CLI contract ---------------------------------------------------------------


def test_main_exit_codes(tmp_path):
    clean = tmp_path / "clean.md"
    clean.write_text("Converts CSV to JSON.\n", encoding="utf-8")
    dirty = tmp_path / "dirty.md"
    dirty.write_text("A powerful WIP tool.\n", encoding="utf-8")
    assert slop_lint.main([str(clean)]) == 0
    assert slop_lint.main([str(dirty)]) == 1
    assert slop_lint.main([]) == 2
    assert slop_lint.main(["--genre", "bogus", str(clean)]) == 2
