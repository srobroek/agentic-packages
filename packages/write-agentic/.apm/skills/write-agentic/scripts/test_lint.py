#!/usr/bin/env python3
"""Tests for lint.py — x-lint override mechanism and core rules.

Run: pytest packages/write-agentic/.apm/skills/write-agentic/scripts/test_lint.py
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    path = os.path.join(HERE, "lint.py")
    spec = importlib.util.spec_from_file_location("lint", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lint_mod = _load()


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# parse_xlint
# ---------------------------------------------------------------------------

class TestParseXlint:
    def test_no_xlint(self):
        text = "---\nname: foo\ndescription: bar\n---\nbody"
        codes, reason = lint_mod.parse_xlint(text)
        assert codes == set()
        assert reason == ""

    def test_inline_list(self):
        text = "---\nx-lint:\n  allow: [E1, E3]\n  reason: \"test reason\"\n---\nbody"
        codes, reason = lint_mod.parse_xlint(text)
        assert codes == {"E1", "E3"}
        assert reason == "test reason"

    def test_block_list(self):
        text = "---\nx-lint:\n  allow:\n    - E1\n    - W9\n  reason: block reason\n---\nbody"
        codes, reason = lint_mod.parse_xlint(text)
        assert codes == {"E1", "W9"}
        assert reason == "block reason"

    def test_no_frontmatter(self):
        codes, reason = lint_mod.parse_xlint("no frontmatter here")
        assert codes == set()
        assert reason == ""

    def test_missing_reason_returns_empty_reason(self):
        text = "---\nx-lint:\n  allow: [E1]\n---\nbody"
        codes, reason = lint_mod.parse_xlint(text)
        assert "E1" in codes
        assert reason == ""

    def test_w_code_allowed(self):
        text = "---\nx-lint:\n  allow: [W9]\n  reason: \"acceptable duplication\"\n---\nbody"
        codes, reason = lint_mod.parse_xlint(text)
        assert "W9" in codes
        assert reason == "acceptable duplication"


# ---------------------------------------------------------------------------
# Override behavior in lint()
# ---------------------------------------------------------------------------

SKILL_TEMPLATE_LONG = """\
---
name: test-skill
description: {desc}
x-lint:
  allow: [{codes}]
  reason: "{reason}"
---

# Test Skill

MUST do something.
"""

SKILL_TEMPLATE_NO_OVERRIDE = """\
---
name: test-skill
description: {desc}
---

# Test Skill

MUST do something.
"""


class TestOverrideMechanism:
    def test_suppressed_e1_prints_overridden(self, tmp_path):
        # 30-word description on a skill (cap is 25)
        desc = "word " * 30
        content = SKILL_TEMPLATE_LONG.format(
            desc=desc.strip(), codes="E1", reason="routing depends on full description"
        )
        p = _write(tmp_path, "SKILL.md", content)
        findings = lint_mod.lint(p)
        codes = {code for _, code, _ in findings}
        sevs = {sev for sev, _, _ in findings}
        assert "E1" not in codes or all(
            sev == "OVERRIDDEN" for sev, code, _ in findings if code == "E1"
        ), "E1 should be OVERRIDDEN, not ERROR"
        assert "OVERRIDDEN" in sevs
        assert "ERROR" not in sevs

    def test_overridden_message_contains_reason(self, tmp_path):
        desc = "word " * 30
        content = SKILL_TEMPLATE_LONG.format(
            desc=desc.strip(), codes="E1", reason="routing depends on full description"
        )
        p = _write(tmp_path, "SKILL.md", content)
        findings = lint_mod.lint(p)
        overridden = [(sev, code, msg) for sev, code, msg in findings if sev == "OVERRIDDEN"]
        assert overridden, "expected at least one OVERRIDDEN finding"
        assert "routing depends on full description" in overridden[0][2]

    def test_missing_reason_is_e9(self, tmp_path):
        desc = "word " * 30
        content = """\
---
name: test-skill
description: {desc}
x-lint:
  allow: [E1]
---

# Test Skill

MUST do something.
""".format(desc=desc.strip())
        p = _write(tmp_path, "SKILL.md", content)
        findings = lint_mod.lint(p)
        error_codes = [code for sev, code, _ in findings if sev == "ERROR"]
        assert "E9" in error_codes, f"expected E9, got {error_codes}"

    def test_non_overridden_error_still_errors(self, tmp_path):
        # Override E1 but not E3 — model name in prose should still error
        desc = "word " * 30
        content = """\
---
name: test-skill
description: {desc}
x-lint:
  allow: [E1]
  reason: "routing needs it"
---

# Test Skill

MUST do something.
MUST prefer haiku for cheap tasks.
""".format(desc=desc.strip())
        p = _write(tmp_path, "SKILL.md", content)
        findings = lint_mod.lint(p)
        error_codes = [code for sev, code, _ in findings if sev == "ERROR"]
        assert "E3" in error_codes

    def test_no_override_e1_is_error(self, tmp_path):
        desc = "word " * 30
        content = SKILL_TEMPLATE_NO_OVERRIDE.format(desc=desc.strip())
        p = _write(tmp_path, "SKILL.md", content)
        findings = lint_mod.lint(p)
        error_codes = [code for sev, code, _ in findings if sev == "ERROR"]
        assert "E1" in error_codes

    def test_allow_w_code(self, tmp_path):
        # Two identical MUST lines (W9) with override
        content = """\
---
name: test-skill
description: short skill description here nice
x-lint:
  allow: [W9]
  reason: "duplicate rules needed for emphasis in this reference doc"
---

# Test

- MUST always check the file path before editing any document in scope
- MUST always check the file path before editing any document in scope
"""
        p = _write(tmp_path, "SKILL.md", content)
        findings = lint_mod.lint(p)
        # W9 should be OVERRIDDEN, not WARN
        for sev, code, msg in findings:
            if code == "W9":
                assert sev == "OVERRIDDEN", f"W9 should be OVERRIDDEN, got {sev}"

    def test_clean_file_returns_empty(self, tmp_path):
        content = """\
---
name: test-skill
description: Short clean skill description here.
---

# Test Skill

MUST do something specific and verifiable.
"""
        p = _write(tmp_path, "SKILL.md", content)
        findings = lint_mod.lint(p)
        errors = [f for f in findings if f[0] == "ERROR"]
        assert errors == []


# ---------------------------------------------------------------------------
# main() exit code with overrides
# ---------------------------------------------------------------------------

class TestMainExitCode:
    def test_overridden_only_exits_0(self, tmp_path, capsys):
        desc = "word " * 30
        content = SKILL_TEMPLATE_LONG.format(
            desc=desc.strip(), codes="E1", reason="routing depends on full description"
        )
        p = _write(tmp_path, "SKILL.md", content)
        rc = lint_mod.main([str(p)])
        assert rc == 0, "overridden-only file should exit 0"

    def test_real_error_exits_1(self, tmp_path):
        desc = "word " * 30
        content = SKILL_TEMPLATE_NO_OVERRIDE.format(desc=desc.strip())
        p = _write(tmp_path, "SKILL.md", content)
        rc = lint_mod.main([str(p)])
        assert rc == 1

    def test_e9_exits_1(self, tmp_path):
        desc = "word " * 30
        content = """\
---
name: test-skill
description: {desc}
x-lint:
  allow: [E1]
---

# Test Skill

MUST do something.
""".format(desc=desc.strip())
        p = _write(tmp_path, "SKILL.md", content)
        rc = lint_mod.main([str(p)])
        assert rc == 1, "missing reason should be E9 → exit 1"
