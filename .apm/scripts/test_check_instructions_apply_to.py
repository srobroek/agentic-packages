from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).with_name("check-instructions-apply-to.py")
SPEC = importlib.util.spec_from_file_location("check_instructions_apply_to", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_flags_instruction_with_no_apply_to(tmp_path):
    f = _write(
        tmp_path / "packages/pkg/.apm/instructions/pkg.instructions.md",
        "---\ndescription: no applyTo here\n---\n\nBody.\n",
    )
    assert MODULE.missing_apply_to(f) is True


def test_accepts_instruction_with_apply_to(tmp_path):
    f = _write(
        tmp_path / "packages/pkg/.apm/instructions/pkg.instructions.md",
        '---\ndescription: has applyTo\napplyTo: "**/*"\n---\n\nBody.\n',
    )
    assert MODULE.missing_apply_to(f) is False


def test_accepts_scoped_apply_to_glob(tmp_path):
    f = _write(
        tmp_path / "packages/pkg/.apm/instructions/pkg.instructions.md",
        '---\ndescription: scoped\napplyTo: "**/*.rs"\n---\n\nBody.\n',
    )
    assert MODULE.missing_apply_to(f) is False


def test_flags_file_with_no_frontmatter(tmp_path):
    f = _write(
        tmp_path / "packages/pkg/.apm/instructions/pkg.instructions.md",
        "Just a body, no frontmatter at all.\n",
    )
    assert MODULE.missing_apply_to(f) is True


def test_find_instruction_files_skips_apm_modules_vendor_copies(tmp_path):
    _write(
        tmp_path / "packages/beads/.apm/instructions/beads.instructions.md",
        '---\ndescription: real source\napplyTo: "**/*"\n---\n\nBody.\n',
    )
    _write(
        tmp_path
        / "packages/orchestrate/apm_modules/srobroek/agentic-packages/packages/beads/.apm/instructions/beads.instructions.md",
        "---\ndescription: vendored copy, missing applyTo\n---\n\nBody.\n",
    )

    found = MODULE.find_instruction_files(tmp_path / "packages")

    assert len(found) == 1
    assert "apm_modules" not in found[0].parts


def test_main_returns_nonzero_when_any_missing(tmp_path, capsys):
    _write(
        tmp_path / "packages/good/.apm/instructions/good.instructions.md",
        '---\ndescription: ok\napplyTo: "**/*"\n---\n\nBody.\n',
    )
    _write(
        tmp_path / "packages/bad/.apm/instructions/bad.instructions.md",
        "---\ndescription: missing applyTo\n---\n\nBody.\n",
    )

    import sys

    old_argv = sys.argv
    sys.argv = ["check-instructions-apply-to.py", "--packages-dir", str(tmp_path / "packages")]
    try:
        rc = MODULE.main()
    finally:
        sys.argv = old_argv

    out = capsys.readouterr().out
    assert rc == 1
    assert "bad.instructions.md" in out
    assert "good.instructions.md" not in out


def test_main_returns_zero_when_all_declare_apply_to(tmp_path):
    _write(
        tmp_path / "packages/good/.apm/instructions/good.instructions.md",
        '---\ndescription: ok\napplyTo: "**/*"\n---\n\nBody.\n',
    )

    import sys

    old_argv = sys.argv
    sys.argv = ["check-instructions-apply-to.py", "--packages-dir", str(tmp_path / "packages")]
    try:
        rc = MODULE.main()
    finally:
        sys.argv = old_argv

    assert rc == 0
