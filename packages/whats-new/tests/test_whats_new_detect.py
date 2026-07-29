#!/usr/bin/env python3
"""Tests for the skill dependency detector.

Ported from tests/detect.bats, which was the parity oracle for the shell-to-
Python port; every case that suite asserted is preserved here, plus the defects
the port fixed.

This module is imported by BOTH twin packages: whats-new and dep-update ship
byte-identical detectors, and the suite locates the one beside it.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = next(PKG_ROOT.glob(".apm/skills/*/scripts/detect.py"))


def _load():
    spec = importlib.util.spec_from_file_location("detect_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


detect = _load()


def rows(tmp_path: Path) -> list[tuple[str, str, str]]:
    """Detector rows for a project directory, via the module API."""
    detector = detect.Detector(tmp_path)
    detector.scan_node()
    detector.scan_python()
    detector.scan_rust()
    detector.scan_go()
    detector.scan_ruby()
    detector.scan_php()
    return detector.rows


def run_cli(target: Path | str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(target)],
        capture_output=True,
        text=True,
    )


# --- shipped contract -------------------------------------------------------


def test_script_is_committed_executable():
    mode = SCRIPT.stat().st_mode
    assert mode & 0o111, f"{SCRIPT} must be mode 755 (authoring rule 2)"


def test_shebang_is_python3():
    assert SCRIPT.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3\n")


def test_no_shell_helper_subprocess():
    """The port exists to remove jq/awk/sed tokenizing; keep it removed."""
    body = SCRIPT.read_text(encoding="utf-8")
    for tool in ("jq", "awk", "sed"):
        assert f'"{tool}"' not in body and f"'{tool}'" not in body


# --- empty / bad input ------------------------------------------------------


def test_empty_project_reports_zero_and_exits_zero(tmp_path):
    result = run_cli(tmp_path)
    assert result.returncode == 0
    assert result.stdout == ""
    assert "0 dependency declaration(s) found" in result.stderr
    assert "No supported manifest" in result.stderr


def test_missing_target_directory_exits_two(tmp_path):
    result = run_cli(tmp_path / "nope")
    assert result.returncode == 2


def test_output_is_tab_separated_triples(tmp_path):
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n")
    result = run_cli(tmp_path)
    assert result.returncode == 0
    assert result.stdout == "pypi\trequests\t==2.31.0\n"


# --- node -------------------------------------------------------------------


def test_package_json_deps_and_dev_deps(tmp_path):
    (tmp_path / "package.json").write_text(
        """
        {
          "name": "demo",
          "dependencies": { "react": "^18.2.0", "left-pad": "1.3.0" },
          "devDependencies": { "typescript": "~5.4.0" }
        }
        """
    )
    assert set(rows(tmp_path)) == {
        ("npm", "react", "^18.2.0"),
        ("npm", "left-pad", "1.3.0"),
        ("npm", "typescript", "~5.4.0"),
    }


def test_package_json_peer_and_optional_deps(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"peerDependencies":{"vue":"^3"},"optionalDependencies":{"fsevents":"2.3"}}'
    )
    assert set(rows(tmp_path)) == {
        ("npm", "vue", "^3"),
        ("npm", "fsevents", "2.3"),
    }


def test_malformed_package_json_fails_open(tmp_path):
    """An unparseable manifest yields no rows and still exits 0."""
    (tmp_path / "package.json").write_text("{not json")
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n")
    result = run_cli(tmp_path)
    assert result.returncode == 0
    assert "pypi\trequests\t==2.31.0\n" in result.stdout


def test_package_json_non_object_dependency_block_is_ignored(tmp_path):
    (tmp_path / "package.json").write_text('{"dependencies": "not-a-table"}')
    assert rows(tmp_path) == []


# --- python -----------------------------------------------------------------


def test_requirements_pins_ranges_bare_names_comments(tmp_path):
    (tmp_path / "requirements.txt").write_text(
        "requests==2.31.0\nflask>=3.0\n# a comment line\nnumpy\n-r other.txt\n"
    )
    result = rows(tmp_path)
    assert ("pypi", "requests", "==2.31.0") in result
    assert ("pypi", "flask", ">=3.0") in result
    assert ("pypi", "numpy", "?") in result
    assert not any("other.txt" in name for _, name, _ in result)


def test_requirements_extras_and_markers_do_not_leak_into_version(tmp_path):
    """DEFECT (shell): extras and markers leaked into the version field.

    `requests[socks]>=2.31.0; python_version < "3.12"` produced a version of
    `[socks]>=2.31.0; python_version < "3.12"`.
    """
    (tmp_path / "requirements.txt").write_text(
        'requests[socks]>=2.31.0; python_version < "3.12"\n'
        "uvicorn[standard]==0.30.0\n"
    )
    assert set(rows(tmp_path)) == {
        ("pypi", "requests", ">=2.31.0"),
        ("pypi", "uvicorn", "==0.30.0"),
    }


def test_pep621_project_dependencies_are_emitted(tmp_path):
    """DEFECT (shell): PEP 621 dependency ARRAYS were missed entirely, while
    `requires-python`, `name`, and a tool's `target-version` were emitted AS
    PACKAGES -- any quoted TOML scalar matched.
    """
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "demo"
requires-python = ">=3.11"
dependencies = [
  "requests>=2.31.0",
  "click==8.1.7",
]

[tool.ruff]
target-version = "py311"
"""
    )
    assert set(rows(tmp_path)) == {
        ("pypi", "requests", ">=2.31.0"),
        ("pypi", "click", "==8.1.7"),
    }


def test_pep621_optional_dependencies(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\n'
        '[project.optional-dependencies]\ndev = ["pytest>=8.0"]\n'
    )
    assert rows(tmp_path) == [("pypi", "pytest", ">=8.0")]


def test_pep735_dependency_groups(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[dependency-groups]\n"
        'test = ["pytest>=8.0", {include-group = "lint"}]\n'
        'lint = ["ruff==0.6.0"]\n'
    )
    assert set(rows(tmp_path)) == {
        ("pypi", "pytest", ">=8.0"),
        ("pypi", "ruff", "==0.6.0"),
    }


def test_pyproject_poetry_style_skips_python_itself(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poetry.dependencies]\npython = "^3.11"\nrequests = "^2.28"\n'
    )
    assert rows(tmp_path) == [("pypi", "requests", "^2.28")]


def test_poetry_quoted_dotted_key_dependency(tmp_path):
    """DEFECT (shell): a quoted dotted key was dropped -- its name regex
    stopped at the dot, so `"ruamel.yaml" = "^0.18"` emitted nothing.
    """
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poetry.dependencies]\n"ruamel.yaml" = "^0.18"\n'
    )
    assert rows(tmp_path) == [("pypi", "ruamel.yaml", "^0.18")]


def test_poetry_table_form_and_group_dependencies(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.poetry.dependencies]\n"
        'requests = { version = "^2.28", extras = ["socks"] }\n'
        'local = { path = "../local" }\n'
        "[tool.poetry.group.dev.dependencies]\n"
        'pytest = "^8.0"\n'
    )
    assert set(rows(tmp_path)) == {
        ("pypi", "requests", "^2.28"),
        ("pypi", "local", "?"),
        ("pypi", "pytest", "^8.0"),
    }


def test_uv_lock_wins_over_pyproject(tmp_path):
    """Lockfile precedence is part of the output contract."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\ndependencies = ["requests>=2.0"]\n'
    )
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname = "requests"\nversion = "2.31.0"\n'
    )
    assert rows(tmp_path) == [("pypi", "requests", "2.31.0")]


def test_poetry_lock_packages(tmp_path):
    (tmp_path / "poetry.lock").write_text(
        '[[package]]\nname = "requests"\nversion = "2.31.0"\n'
        '[[package]]\nname = "flask"\nversion = "3.0.0"\n'
    )
    assert set(rows(tmp_path)) == {
        ("pypi", "requests", "2.31.0"),
        ("pypi", "flask", "3.0.0"),
    }


def test_lock_package_missing_version_is_skipped(tmp_path):
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname = "workspace-member"\n'
        '[[package]]\nname = "requests"\nversion = "2.31.0"\n'
    )
    assert rows(tmp_path) == [("pypi", "requests", "2.31.0")]


# --- rust -------------------------------------------------------------------


def test_cargo_plain_and_inline_table_versions(tmp_path):
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "demo"\n\n[dependencies]\n'
        'serde = "1.0"\n'
        'tokio = { version = "1.36", features = ["full"] }\n'
    )
    result = rows(tmp_path)
    assert ("cargo", "serde", "1.0") in result
    assert ("cargo", "tokio", "1.36") in result
    # `[package] name`/`version` are manifest metadata, not dependencies.
    assert not any(name == "demo" for _, name, _ in result)


def test_cargo_dependency_subtable_form(tmp_path):
    """DEFECT (shell): `[dependencies.reqwest]` was dropped, because any line
    starting `[` reset the in-dependencies flag.
    """
    (tmp_path / "Cargo.toml").write_text(
        '[dependencies]\nserde = "1.0"\n\n'
        '[dependencies.reqwest]\nversion = "0.12"\nfeatures = ["json"]\n'
    )
    assert set(rows(tmp_path)) == {
        ("cargo", "serde", "1.0"),
        ("cargo", "reqwest", "0.12"),
    }


def test_cargo_dev_and_build_dependencies(tmp_path):
    (tmp_path / "Cargo.toml").write_text(
        '[dev-dependencies]\ncriterion = "0.5"\n'
        '[build-dependencies]\ncc = "1.0"\n'
    )
    assert set(rows(tmp_path)) == {
        ("cargo", "criterion", "0.5"),
        ("cargo", "cc", "1.0"),
    }


def test_cargo_git_dependency_has_no_version(tmp_path):
    (tmp_path / "Cargo.toml").write_text(
        '[dependencies]\nfoo = { git = "https://example.invalid/foo" }\n'
    )
    assert rows(tmp_path) == [("cargo", "foo", "?")]


# --- go ---------------------------------------------------------------------


def test_go_mod_require_block_and_single_line(tmp_path):
    (tmp_path / "go.mod").write_text(
        "module example.com/m\n\ngo 1.22\n\n"
        "require (\n"
        "\tgithub.com/spf13/cobra v1.8.0\n"
        "\tgolang.org/x/text v0.14.0 // indirect\n"
        ")\n\n"
        "require github.com/stretchr/testify v1.9.0\n"
    )
    assert set(rows(tmp_path)) == {
        ("go", "github.com/spf13/cobra", "v1.8.0"),
        ("go", "golang.org/x/text", "v0.14.0"),
        ("go", "github.com/stretchr/testify", "v1.9.0"),
    }


def test_go_mod_comment_line_in_block_is_not_a_module(tmp_path):
    (tmp_path / "go.mod").write_text(
        "require (\n\t// a note\n\tgithub.com/a/b v1.0.0\n)\n"
    )
    assert rows(tmp_path) == [("go", "github.com/a/b", "v1.0.0")]


# --- ruby / php -------------------------------------------------------------


def test_gemfile_with_and_without_version(tmp_path):
    (tmp_path / "Gemfile").write_text(
        'source "https://rubygems.org"\ngem "rails", "~> 7.1"\ngem "puma"\n'
    )
    result = rows(tmp_path)
    assert ("rubygems", "rails", "~> 7.1") in result
    assert ("rubygems", "puma", "?") in result


def test_gemfile_single_quotes_and_group_indent(tmp_path):
    (tmp_path / "Gemfile").write_text(
        "group :test do\n  gem 'rspec', '~> 3.13'\nend\n"
    )
    assert rows(tmp_path) == [("rubygems", "rspec", "~> 3.13")]


def test_gemfile_gem_word_in_prose_is_not_a_dependency(tmp_path):
    """Only a line whose first token is `gem` declares one."""
    (tmp_path / "Gemfile").write_text('# use the gem "rails" from source\n')
    assert rows(tmp_path) == []


def test_composer_require_skips_platform_requirements(tmp_path):
    (tmp_path / "composer.json").write_text(
        """
        {
          "require": {
            "php": ">=8.1",
            "ext-json": "*",
            "lib-curl": "*",
            "monolog/monolog": "^3.0"
          }
        }
        """
    )
    assert rows(tmp_path) == [("packagist", "monolog/monolog", "^3.0")]


def test_composer_require_dev(tmp_path):
    (tmp_path / "composer.json").write_text(
        '{"require-dev": {"phpunit/phpunit": "^11.0"}}'
    )
    assert rows(tmp_path) == [("packagist", "phpunit/phpunit", "^11.0")]


# --- cross-ecosystem --------------------------------------------------------


def test_polyglot_repo_counts_every_ecosystem(tmp_path):
    (tmp_path / "package.json").write_text('{ "dependencies": { "a": "1.0.0" } }')
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n")
    result = run_cli(tmp_path)
    assert result.returncode == 0
    assert "npm\ta\t1.0.0\n" in result.stdout
    assert "pypi\trequests\t==2.31.0\n" in result.stdout
    assert "2 dependency declaration(s) found" in result.stderr


def test_duplicate_declaration_across_blocks_yields_one_row(tmp_path):
    """`jq '[...] | add'` merged the blocks last-wins; preserve that."""
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"react": "^18.0.0"}, "devDependencies": {"react": "^19.0.0"}}'
    )
    assert rows(tmp_path) == [("npm", "react", "^19.0.0")]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("requests", ("requests", "?")),
        ("requests==2.31.0", ("requests", "==2.31.0")),
        ("requests >= 2.0", ("requests", ">= 2.0")),
        ("requests[socks]", ("requests", "?")),
        ('requests; python_version < "3.12"', ("requests", "?")),
        ("requests~=2.31", ("requests", "~=2.31")),
        ("requests!=2.30.0", ("requests", "!=2.30.0")),
        ("  # comment", ("", "")),
        ("-e .", ("", "")),
        ("./local-pkg", ("", "")),
        ("/abs/path", ("", "")),
        ("", ("", "")),
    ],
)
def test_parse_requirement(raw, expected):
    assert detect._parse_requirement(raw) == expected
