from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).with_name("compile-global-contexts.py")
SPEC = importlib.util.spec_from_file_location("compile_global_contexts", SCRIPT)
assert SPEC and SPEC.loader
compiler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compiler)


def write_instruction(root: Path, *, link: str = "../context/rules.md") -> Path:
    package = root / ".apm" / "apm_modules" / "owner" / "package" / ".apm"
    instruction = package / "instructions" / "00-rules.instructions.md"
    instruction.parent.mkdir(parents=True)
    instruction.write_text(
        "---\ndescription: Rules.\n---\n\nRead [rules](" + link + ").\n",
        encoding="utf-8",
    )
    context = package / "context" / "rules.md"
    context.parent.mkdir()
    context.write_text("# Rules\n", encoding="utf-8")
    return context


def test_compiles_both_roots_and_rewrites_links(tmp_path: Path) -> None:
    context = write_instruction(tmp_path)
    assert compiler.main(["--root", str(tmp_path)]) == 0
    for relative in (".claude/CLAUDE.md", ".codex/AGENTS.md"):
        output = tmp_path / relative
        text = output.read_text(encoding="utf-8")
        expected = Path("..") / context.relative_to(tmp_path)
        assert text.startswith(compiler.MARKER)
        assert f"]({expected})" in text
    assert compiler.main(["--root", str(tmp_path), "--check"]) == 0


def test_refuses_hand_authored_root(tmp_path: Path) -> None:
    write_instruction(tmp_path)
    destination = tmp_path / ".codex" / "AGENTS.md"
    destination.parent.mkdir()
    destination.write_text("# Hand authored\n", encoding="utf-8")
    assert compiler.main(["--root", str(tmp_path)]) == 1
    assert destination.read_text(encoding="utf-8") == "# Hand authored\n"


def test_broken_instruction_link_fails_loudly(tmp_path: Path) -> None:
    write_instruction(tmp_path, link="../context/missing.md")
    with pytest.raises(compiler.CompileError, match="broken instruction link"):
        compiler.expected_content(
            tmp_path / ".apm" / "apm_modules", tmp_path / ".codex" / "AGENTS.md"
        )
