"""Seeded fuzz harness for the skill dependency detector.

The detector is a parser for eight manifest formats, so malformed input is its
whole attack surface. Four properties are asserted over every generated case:

  P1  no manifest, however malformed, produces a traceback or a nonzero exit --
      a syntax error in one ecosystem must never hide the others.
  P2  every emitted row is exactly three tab-separated fields, and the name is a
      plausible package name rather than a URL, an option, or a manifest key.
  P3  no NON-dependency key is ever emitted as a package: `requires-python`,
      `name`, `version`, poetry's `python`, composer's `php`/`ext-*`, go's
      `module`/`replace`/`exclude`.
  P4  requirement parsing agrees with an INDEPENDENT reading of PEP 508 --
      written from the specification, not from the implementation.

Adversarial file-level cases a generator will not stumble on -- a directory where
a file belongs, a symlink loop, invalid UTF-8, a BOM, an over-long path -- are
pinned explicitly below the generator.

TWIN: byte-identical to packages/dep-update/tests/test_dep_update_detect_fuzz.py
apart from nothing at all; `.apm/scripts/check-twin-scripts.py` enforces it.

Run standalone for a larger corpus: FUZZ_CASES=5000 pytest <this file>
"""

from __future__ import annotations

import importlib.util
import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / ".apm"
    / "skills"
    / Path(__file__).resolve().parents[1].name
    / "scripts"
    / "detect.py"
)
SEED = 20260729
CORPUS_SIZE = int(os.environ.get("FUZZ_CASES", "600"))


def _load():
    spec = importlib.util.spec_from_file_location("detect_fuzz", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


detect = _load()

# Keys that appear in a dependency manifest but are NOT packages. Emitting any of
# these is the defect the shell predecessor shipped: it matched every quoted
# scalar, so `requires-python` and `name` became dependencies.
NEVER_A_PACKAGE = frozenset(
    {
        "name",
        "version",
        "requires-python",
        "python",
        "php",
        "module",
        "replace",
        "exclude",
        "go",
        "source",
        "description",
        "readme",
        "license",
        "authors",
        "scripts",
        "type",
        "packageManager",
    }
)

# Fragments chosen to break a line- or pattern-oriented parser: comments inside
# arrays, quoted dotted keys, inline tables, workspace inheritance, CRLF, markers.
PYPROJECT_FRAGMENTS = (
    '[project]\nname = "mypkg"\nversion = "1.0"\nrequires-python = ">=3.11"\n',
    '[project]\ndependencies = ["requests>=2.31"]\n',
    '[project]\ndependencies = [\n  "requests>=2.31",  # pinned\n  \'zope.interface>=5\',\n]\n',
    '[project.optional-dependencies]\ndev = ["pytest>=8", "ruff"]\n',
    '[dependency-groups]\nlint = ["ruff", {include-group = "base"}]\n',
    '[tool.poetry.dependencies]\npython = "^3.11"\n"ruamel.yaml" = "^0.18"\n',
    '[tool.poetry.dependencies]\nrequests = {version = "^2.31", extras = ["socks"]}\n',
    '[tool.poetry.group.dev.dependencies]\npytest = "^8"\n',
    '[tool.poetry.dev-dependencies]\nblack = "*"\n',
    "[build-system]\nrequires = [\"hatchling\"]\n",
    '[project]\ndependencies = ["a"]\r\n',
    "[project]\ndependencies = []\n",
)

CARGO_FRAGMENTS = (
    '[package]\nname = "x"\nversion = "0.1.0"\n',
    '[dependencies]\nserde = "1.0"\n',
    '[dependencies]\nserde = { version = "1.0", features = ["derive"] }\n',
    '[dependencies.reqwest]\nversion = "0.12"\nfeatures = ["json"]\n',
    "[dependencies.tokio]\nworkspace = true\n",
    "[dependencies.local]\npath = \"../local\"\n",
    '[target.\'cfg(unix)\'.dependencies]\nnix = "0.29"\n',
    '[dev-dependencies]\ncriterion = "0.5"\n',
    '[build-dependencies]\ncc = { version = "1", optional = true }\n',
    "[dependencies]\n",
)

PACKAGE_JSON_BODIES = (
    "{}",
    '{"name":"x","version":"1.0.0"}',
    '{"dependencies":{"left-pad":"^1.3.0"}}',
    '{"dependencies":{"left-pad":"^1.3.0"},"devDependencies":{"jest":"~29"}}',
    '{"peerDependencies":{"react":">=18"},"optionalDependencies":{"fsevents":"*"}}',
    '{"dependencies":{"@scope/pkg":"1.0.0"}}',
    '{"dependencies":{"a":1,"b":null,"c":{"x":1}}}',
    '{"dependencies":{"a":"1"},"dependencies":{"a":"2"}}',
    '{"dependencies":[]}',
    '{"dependencies":"nope"}',
    "not json at all",
    "{",
    '{"packageManager":"pnpm@9.1.0"}',
)

REQUIREMENTS_BODIES = (
    "requests==2.31.0\n",
    'requests[socks]>=2.31 ; python_version < "3.12"\n',
    "-e .\n-r other.txt\n--index-url https://example.com\n",
    "https://example.com/pkg-1.0-py3-none-any.whl\n",
    "pkg @ git+https://github.com/x/y@main\n",
    "foo==1.0 \\\n    --hash=sha256:deadbeef\n",
    "# a comment\n\n   \n",
    "Django>=4\r\nflask\r\n",
    "ruamel.yaml==0.18.5\nzope.interface>=5\n",
    "pkg==1.0 # trailing comment\n",
    "--hash=sha256:abcd\n",
)

GO_MOD_BODIES = (
    "module example.com/x\n\ngo 1.22\n",
    "module example.com/x\n\nrequire github.com/pkg/errors v0.9.1\n",
    "require (\n\tgithub.com/a/b v1.0.0 // indirect\n\tgolang.org/x/net v0.25.0\n)\n",
    "require (\n\t// only a comment\n)\n",
    "replace github.com/a/b => github.com/c/d v1.0.0\n",
    "exclude github.com/bad/pkg v1.0.0\n",
    "require\n",
)

GEMFILE_BODIES = (
    'source "https://rubygems.org"\ngem "rails", "~> 7.1"\n',
    "gem 'puma'\n",
    "group :dev do\n  gem \"rspec\"\nend\n",
    "# gem \"commented\"\n",
    "gemfile_helper 'not a gem'\n",
    'gem "x", require: false\n',
)

COMPOSER_BODIES = (
    '{"require":{"monolog/monolog":"^3.0"}}',
    '{"require":{"php":">=8.1","ext-json":"*","lib-curl":"*","a/b":"1.0"}}',
    '{"require-dev":{"phpunit/phpunit":"^11"}}',
    '{"require":"nope"}',
    "{}",
)

LOCK_BODIES = (
    '[[package]]\nname = "requests"\nversion = "2.31.0"\n',
    '[[package]]\nname = "local"\n',
    "[[package]]\nversion = \"1.0\"\n",
    "",
)

FILE_MENU = {
    "pyproject.toml": PYPROJECT_FRAGMENTS,
    "Cargo.toml": CARGO_FRAGMENTS,
    "package.json": PACKAGE_JSON_BODIES,
    "requirements.txt": REQUIREMENTS_BODIES,
    "go.mod": GO_MOD_BODIES,
    "Gemfile": GEMFILE_BODIES,
    "composer.json": COMPOSER_BODIES,
    "uv.lock": LOCK_BODIES,
    "poetry.lock": LOCK_BODIES,
}

# A name a registry could plausibly accept. Anything else -- a URL, an option, a
# `--hash` fragment, a shell metacharacter -- means the parser leaked syntax into
# the name field and the research step will query a registry with garbage.
PLAUSIBLE_NAME = re.compile(r"^[A-Za-z0-9@._/+-]+$")


def _project(rng: random.Random, root: Path) -> None:
    """A project holding a random subset of manifests with random bodies."""
    for name, bodies in FILE_MENU.items():
        if rng.random() < 0.35:
            body = rng.choice(bodies)
            if rng.random() < 0.15:
                # Splice two fragments: a real manifest holds several tables, and
                # concatenation is where a stateful parser loses its place.
                body += rng.choice(bodies)
            if rng.random() < 0.05:
                body = "﻿" + body  # BOM
            (root / name).write_text(body, encoding="utf-8")


def _rows(directory: Path) -> list[tuple[str, ...]]:
    detector = detect.Detector(directory)
    for scan in ("node", "python", "rust", "go", "ruby", "php"):
        getattr(detector, f"scan_{scan}")()
    return [tuple(row) for row in detector.rows]


def test_generated_manifests_never_crash_and_never_emit_a_non_package(tmp_path):
    """P1, P2 and P3 over the generated corpus."""
    rng = random.Random(SEED)
    emitted = 0
    for index in range(CORPUS_SIZE):
        root = tmp_path / f"case{index}"
        root.mkdir()
        _project(rng, root)
        try:
            rows = _rows(root)
        except Exception as error:  # noqa: BLE001 -- any raise is the defect
            pytest.fail(f"case {index} raised {error!r}")
        for eco, name, version in rows:
            assert name, f"case {index} emitted an empty name"
            assert name not in NEVER_A_PACKAGE, f"case {index} emitted {name!r}"
            assert PLAUSIBLE_NAME.match(name), f"case {index} emitted name {name!r}"
            assert "\t" not in name and "\t" not in version
            assert "\n" not in name and "\n" not in version
            assert eco in ("npm", "pypi", "cargo", "go", "rubygems", "packagist")
            assert version, f"case {index} emitted an empty version for {name!r}"
        emitted += len(rows)
    # A corpus that emitted nothing would prove nothing.
    assert emitted > 0, "generator produced no dependency rows at all"


# --- P4: requirement parsing against an independent reading of PEP 508 --------


def _independently_parsed(raw: str) -> tuple[str, str]:
    """A second, literal reading of the documented requirement rule.

    Written from PEP 508 and the function's own docstring rather than from its
    body, so it diverges if the implementation drifts.
    """
    body = raw.split("#", 1)[0].strip().rstrip("\\").strip()
    if not body or body[0] in "-./":
        return "", ""
    body = body.split(";", 1)[0].strip()
    match = re.match(r"^([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)", body)
    if not match or match.end() == 0:
        return "", ""
    name = match.group(1)
    rest = body[match.end() :]
    # A legal requirement continues with an extras bracket, a specifier, an `@`
    # direct reference, or nothing. Anything else means the leading run of name
    # characters was part of a URL or another construct, not a name.
    if rest and not re.match(r"^\s*[\[<>=!~@]", rest):
        return "", ""
    version = re.sub(r"\[[^\]]*\]", "", rest).strip()
    return name, version or "?"


REQUIREMENT_CASES = (
    "requests",
    "requests==2.31.0",
    "requests>=2.31,<3",
    "requests[socks]>=2.31",
    'requests[socks]>=2.31 ; python_version < "3.12"',
    "ruamel.yaml==0.18.5",
    "zope.interface >= 5",
    "pkg @ git+https://github.com/x/y",
    "https://example.com/pkg.whl",
    "http://example.com/pkg.whl",
    "git+ssh://git@host/x.git",
    "-e .",
    "-r other.txt",
    "--hash=sha256:abcd",
    "./local",
    "/abs/path",
    "# comment only",
    "",
    "   ",
    "foo==1.0 \\",
    "foo==1.0 # note",
    "Django>=4\r",
    "a==1!2.0",
    "a==1.0.0rc1",
    "a==2.0.0.post1",
    "a==1.0.0.dev3",
    "UPPER_case-Name==1",
    "x",
    "1pkg==1.0",
    "pkg-==1.0",
    "-pkg==1.0",
)


@pytest.mark.parametrize("raw", REQUIREMENT_CASES)
def test_requirement_parsing_matches_an_independent_pep508_reading(raw: str):
    assert detect._parse_requirement(raw) == _independently_parsed(raw), raw


@pytest.mark.parametrize(
    "raw",
    [
        "https://example.com/pkg-1.0-py3-none-any.whl",
        "http://example.com/pkg.whl",
        "--hash=sha256:abcd",
        "--index-url https://example.com/simple",
        "-e git+https://github.com/x/y#egg=y",
    ],
)
def test_a_url_or_option_is_never_a_package_name(raw: str):
    """Reproduction: `https://example.com/pkg.whl` was emitted as a package,
    sending the research step to a registry with a URL for a name."""
    name, _ = detect._parse_requirement(raw)
    assert name == "", f"{raw!r} produced the name {name!r}"


# --- adversarial file-level cases --------------------------------------------


def _run(directory) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(directory)],
        capture_output=True,
        text=True,
    )


def test_a_directory_where_a_manifest_belongs_is_skipped(tmp_path):
    (tmp_path / "package.json").mkdir()
    (tmp_path / "pyproject.toml").mkdir()
    result = _run(tmp_path)
    assert result.returncode == 0
    assert "Traceback" not in result.stderr


def test_a_symlink_loop_is_skipped(tmp_path):
    (tmp_path / "package.json").symlink_to(tmp_path / "package.json")
    result = _run(tmp_path)
    assert result.returncode == 0
    assert "Traceback" not in result.stderr


def test_an_unreadable_manifest_is_skipped(tmp_path):
    manifest = tmp_path / "package.json"
    manifest.write_text('{"dependencies":{"a":"1"}}')
    os.chmod(manifest, 0)
    try:
        result = _run(tmp_path)
    finally:
        os.chmod(manifest, 0o644)
    assert result.returncode == 0
    assert "Traceback" not in result.stderr


def test_invalid_utf8_in_a_toml_manifest_does_not_crash_the_detector(tmp_path):
    """Reproduction: tomllib.load reads BYTES and raises UnicodeDecodeError, not
    TOMLDecodeError, so one bad byte escaped the handler and exited 1 with a
    traceback -- taking every other ecosystem's rows with it."""
    (tmp_path / "pyproject.toml").write_bytes(
        b'[project]\ndependencies = ["requests>=1", "a\xff\xfeb"]\n'
    )
    (tmp_path / "package.json").write_text('{"dependencies":{"left-pad":"1.0.0"}}')
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr, result.stderr
    assert "npm\tleft-pad\t1.0.0" in result.stdout


def test_invalid_utf8_in_a_json_manifest_does_not_crash_the_detector(tmp_path):
    (tmp_path / "package.json").write_bytes(b'{"dependencies":{"a\xffb":"1"}}')
    result = _run(tmp_path)
    assert result.returncode == 0
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    ("name", "body", "expected"),
    [
        ("package.json", b'\xef\xbb\xbf{"dependencies":{"a":"1"}}', "npm\ta\t1"),
        (
            "pyproject.toml",
            b'\xef\xbb\xbf[project]\ndependencies = ["requests>=1"]\n',
            "pypi\trequests\t>=1",
        ),
        ("requirements.txt", b"\xef\xbb\xbfrequests==1.0\n", "pypi\trequests\t==1.0"),
    ],
)
def test_a_utf8_bom_does_not_discard_the_manifest(tmp_path, name, body, expected):
    """Reproduction: both `json` and `tomllib` reject a BOM outright, so a
    manifest written by a Windows editor parsed as nothing at all."""
    (tmp_path / name).write_bytes(body)
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert expected in result.stdout, result.stdout


def test_a_zero_byte_manifest_of_every_kind_is_harmless(tmp_path):
    for name in FILE_MENU:
        (tmp_path / name).write_bytes(b"")
    result = _run(tmp_path)
    assert result.returncode == 0
    assert "Traceback" not in result.stderr


def test_an_over_long_target_path_is_rejected_not_raised():
    """Which OSErrors pathlib swallows is platform and version dependent, so the
    detector guards rather than assumes; a raise here would exit nonzero."""
    result = _run("/tmp/" + "x" * 400)
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_a_deeply_nested_json_manifest_is_skipped(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"dependencies":' + "[" * 2000 + "]" * 2000 + "}"
    )
    result = _run(tmp_path)
    assert result.returncode == 0
    assert "Traceback" not in result.stderr


def test_a_large_manifest_is_parsed_without_crashing(tmp_path):
    """50k requirements: the parser is line-oriented, so the only failure mode is
    a crash or a hang, not a wrong answer."""
    (tmp_path / "requirements.txt").write_text(
        "".join(f"pkg{index}==1.0.{index}\n" for index in range(50_000))
    )
    result = _run(tmp_path)
    assert result.returncode == 0
    assert result.stdout.count("\n") == 50_000


def test_output_is_always_three_tab_separated_fields(tmp_path):
    """P2 end-to-end: the contract downstream research.py splits on."""
    (tmp_path / "package.json").write_text('{"dependencies":{"a":"1","b":"2"}}')
    (tmp_path / "requirements.txt").write_text("requests==1\nruamel.yaml==2\n")
    (tmp_path / "Cargo.toml").write_text('[dependencies]\nserde = "1.0"\n')
    result = _run(tmp_path)
    lines = result.stdout.splitlines()
    assert lines
    for line in lines:
        assert len(line.split("\t")) == 3, line


# --- the twin invariant ------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
TWIN_CHECK = REPO_ROOT / ".apm" / "scripts" / "check-twin-scripts.py"
TWINS = (
    "packages/whats-new/.apm/skills/whats-new/scripts/detect.py",
    "packages/dep-update/.apm/skills/dep-update/scripts/detect.py",
)


def test_the_twin_detectors_hold_identical_bytes():
    bodies = {rel: (REPO_ROOT / rel).read_bytes() for rel in TWINS}
    assert len(set(bodies.values())) == 1, "the twin detectors have drifted"


def test_the_twin_checker_catches_a_deliberate_divergence(tmp_path):
    """The enforcement itself is under test: a comment saying "keep both
    identical" enforces nothing, and neither does an unexercised checker."""
    assert subprocess.run(
        [sys.executable, str(TWIN_CHECK)], cwd=REPO_ROOT, capture_output=True
    ).returncode == 0, "the committed twins must agree before this test means anything"

    victim = REPO_ROOT / TWINS[1]
    original = victim.read_bytes()
    try:
        victim.write_bytes(original + b"\n# deliberate divergence\n")
        result = subprocess.run(
            [sys.executable, str(TWIN_CHECK)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, "the twin checker missed a real divergence"
        assert "differs from" in result.stdout + result.stderr
    finally:
        victim.write_bytes(original)


def test_the_hook_payload_shape_is_irrelevant_here():
    """The detector is a skill script, not a hook: it takes argv, not stdin JSON.
    Pinned so a future port does not quietly grow a stdin contract."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "."],
        input=json.dumps({"tool_input": {"command": "x"}}),
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0
