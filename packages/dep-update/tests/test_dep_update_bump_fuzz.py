"""Seeded fuzz harness for research.py classification and apply.py confirmation.

Version comparison is where the shell predecessor got it wrong twice, so both
halves are hammered here:

  research.py `classify` ordered versions by a leading numeric triple.
  apply.py `check_*_version` confirmed a bump with `ver in v`, a SUBSTRING test,
  so bumping to `1.2` "confirmed" against an unchanged `^1.20.0`, and it ran
  `grep -qiE "\"${name}==${ver}\""` with both interpolations unescaped, so every
  `.` was a regex wildcard and `ruamel.yaml` confirmed against `ruamelXyaml`.

Four properties:

  P1  a bump is confirmed ONLY when the manifest genuinely holds the new version.
      Asserted over the cartesian product of declared spec x claimed version, so
      every (spec, version) pair where the spec does not mean that version must
      be rejected -- the substring class is proven absent rather than spot-checked.
  P2  a name containing regex metacharacters is matched literally.
  P3  `classify` never raises and never reports an unorderable version as a safe
      patch, over a seeded corpus of PEP 440, semver, and non-semver strings.
  P4  no registry payload, however malformed, raises: every failure is a status.

Run standalone for a larger corpus: FUZZ_CASES=20000 pytest <this file>
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import os
import random
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / ".apm" / "skills" / "dep-update" / "scripts"
SEED = 20260729
CORPUS_SIZE = int(os.environ.get("FUZZ_CASES", "4000"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_fuzz", SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


research = _load("research")
apply_mod = _load("apply")

# Version strings spanning semver, PEP 440, npm ranges, and the non-semver forms
# real registries serve. Ordering some of these is impossible; the property is
# that an unorderable pair is never called a safe patch.
VERSIONS = (
    "1.0.0",
    "1.0.1",
    "1.1.0",
    "2.0.0",
    "0.9.0",
    "10.0.0",
    "1.2",
    "1.20.0",
    "1.2.3",
    "1.0.0rc1",
    "1.0.0a1",
    "1.0.0b2",
    "1.0.0-rc.1",
    "1.0.0-alpha",
    "1.0.0.dev3",
    "2.0.0.post1",
    "1!2.0",
    "1.0.0+build.1",
    "1.0.0+build.2",
    "2023.10.1",
    "2023.11.1",
    "v1.2.3",
    "v1.2.4",
    "1.2.3-1ubuntu2",
    "",
    "latest",
    "*",
    "1.x",
    "^1.20.0",
    "~1.2",
    ">=1 <2",
    "nan",
    "-1",
    "1.",
    "x" * 200,
)

# npm range spellings that do NOT pin the claimed version, plus the three that do.
# `^1.20.0` against `1.2` is the exact shell defect.
NPM_ACCEPTED = ("{v}", "^{v}", "~{v}", "={v}")
NPM_REJECTED = (
    "^1.20.0",
    "~1.20.0",
    ">=1 <2",
    "1.x",
    "*",
    "latest",
    "next",
    ">={v}",
    "<{v}",
    ">{v}",
    "{v}-0",
    "{v}.0",
    "0{v}",
    "^^{v}",
    " {v}",
    "{v} ",
    "workspace:*",
    "file:../local",
    "npm:other@{v}",
    "github:o/r#{v}",
)

# Names whose characters are regex metacharacters. `ruamel.yaml` and
# `zope.interface` are real PyPI projects; `c++filt` and `a+b` are the general case.
META_NAMES = (
    "ruamel.yaml",
    "zope.interface",
    "c++filt",
    "a+b",
    "a.b.c",
    "x|y",
    "a(b)",
    "a*b",
    "a$b",
    "a^b",
    "a?b",
    "a\\b",
)

# An extras bracket is stripped from a requirement by design, so `a[b]` is not a
# name a python manifest can carry -- it is `a` with the extra `b`.
PYTHON_META_NAMES = tuple(name for name in META_NAMES if "[" not in name)


# --- P1: node confirmation ---------------------------------------------------


def _node_manifest(tmp_path: Path, spec: str, name: str = "pkg") -> Path:
    """A project directory declaring exactly one dependency.

    One directory per test, rewritten per case: a name-derived directory collided
    whenever two cases shared a spec, and PEP 440 spellings collide often.
    """
    root = tmp_path / "node"
    root.mkdir(exist_ok=True)
    (root / "package.json").write_text(json.dumps({"dependencies": {name: spec}}))
    return root


@pytest.mark.parametrize("version", ["1.2", "1.20.0", "2.0.0", "1.0.0", "0.1.0"])
def test_a_node_range_only_confirms_the_version_it_actually_pins(tmp_path, version):
    """P1: every accepted form confirms, every other form must not."""
    for template in NPM_ACCEPTED:
        root = _node_manifest(tmp_path, template.format(v=version))
        assert apply_mod.check_node_version(root, "pkg", version), template

    for template in NPM_REJECTED:
        spec = template.format(v=version)
        if spec in {form.format(v=version) for form in NPM_ACCEPTED}:
            continue  # a rejected template that coincides with an accepted form
        root = _node_manifest(tmp_path, spec)
        assert not apply_mod.check_node_version(root, "pkg", version), (
            f"{spec!r} must not confirm {version!r}"
        )


def test_the_substring_confirmation_class_is_gone_for_node(tmp_path):
    """Reproduction: the shell ran `ver in v`, so a manifest still holding
    `^1.20.0` confirmed a bump to `1.2` and the skill reported a landed upgrade
    that never happened."""
    root = _node_manifest(tmp_path, "^1.20.0")
    assert not apply_mod.check_node_version(root, "pkg", "1.2")
    assert not apply_mod.check_node_version(root, "pkg", "1.20")
    assert not apply_mod.check_node_version(root, "pkg", "0.0")
    assert apply_mod.check_node_version(root, "pkg", "1.20.0")


def test_every_spec_version_pair_confirms_only_on_a_genuine_pin(tmp_path):
    """P1 exhaustively: 35 versions x 35 declared specs = 1,225 pairs. A pair
    confirms only when the declared spec is one of the four accepted spellings of
    the claimed version -- no substring, prefix, or suffix relation counts."""
    checked = 0
    for declared, claimed in itertools.product(VERSIONS, VERSIONS):
        if not declared:
            continue
        root = _node_manifest(tmp_path, declared)
        expected = declared in {form.format(v=claimed) for form in NPM_ACCEPTED}
        assert apply_mod.check_node_version(root, "pkg", claimed) == expected, (
            f"declared={declared!r} claimed={claimed!r}"
        )
        checked += 1
    assert checked > 1000, checked


@pytest.mark.parametrize("name", META_NAMES)
def test_a_node_name_with_regex_metacharacters_matches_literally(tmp_path, name):
    """P2: the name is a dict KEY here, so metacharacters cannot be interpreted --
    pinned so a port back to pattern matching breaks a test."""
    root = _node_manifest(tmp_path, "1.0.0", name)
    assert apply_mod.check_node_version(root, name, "1.0.0")
    # Names that a LIVE regex built from `name` would also match: `.` as any
    # character, and the name as a prefix of a longer key. Node lookup is exact,
    # so every one of these must miss.
    for impostor in (name.replace(".", "X"), name + "-extra", "prefix-" + name):
        if impostor == name:
            continue
        assert not apply_mod.check_node_version(root, impostor, "1.0.0"), impostor


@pytest.mark.parametrize(
    "body",
    [
        "{}",
        "not json",
        "{",
        "[]",
        "null",
        '{"dependencies": "nope"}',
        '{"dependencies": []}',
        '{"dependencies": {"pkg": 1}}',
        '{"dependencies": {"pkg": null}}',
        '{"dependencies": {"pkg": ["1.0.0"]}}',
        '{"dependencies": {"pkg": {"version": "1.0.0"}}}',
        '{"dependencies": {"other": "1.0.0"}}',
    ],
    ids=range(12),
)
def test_a_malformed_package_json_never_confirms_and_never_raises(tmp_path, body):
    root = tmp_path / f"m{abs(hash(body))}"
    root.mkdir()
    (root / "package.json").write_text(body)
    assert apply_mod.check_node_version(root, "pkg", "1.0.0") is False


def test_a_numeric_version_value_does_not_confirm_a_string_bump(tmp_path):
    """Reproduction: `str(block.get(name))` stringified a numeric `"pkg": 1` to
    "1" and confirmed a bump to version "1" -- a manifest npm would reject read as
    a landed upgrade."""
    root = tmp_path / "numeric"
    root.mkdir()
    (root / "package.json").write_text('{"dependencies": {"pkg": 1}}')
    assert apply_mod.check_node_version(root, "pkg", "1") is False


def test_a_missing_package_json_never_confirms(tmp_path):
    assert apply_mod.check_node_version(tmp_path, "pkg", "1.0.0") is False


# --- P1/P2: python confirmation ----------------------------------------------


def _py_project(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "py"
    if root.exists():
        for stale in root.iterdir():
            stale.unlink()
    root.mkdir(exist_ok=True)
    for name, body in files.items():
        (root / name).write_text(body)
    return root


@pytest.mark.parametrize("name", PYTHON_META_NAMES)
def test_a_python_name_with_regex_metacharacters_matches_literally(tmp_path, name):
    """Reproduction: `grep -qiE "\"${name}==${ver}\""` interpolated the name into
    a regex, so every `.` was a wildcard and `ruamel.yaml` confirmed against a
    manifest declaring `ruamelXyaml`."""
    root = _py_project(tmp_path, {"requirements.txt": f"{name}==1.0.0\n"})
    assert apply_mod.check_python_version(root, name, "1.0.0")

    wildcarded = name.replace(".", "X").replace("+", "X")
    if wildcarded != name:
        other = _py_project(tmp_path, {"requirements.txt": f"{wildcarded}==1.0.0\n"})
        assert not apply_mod.check_python_version(other, name, "1.0.0"), (
            f"{name!r} confirmed against {wildcarded!r}: the name is live regex"
        )


def test_the_substring_confirmation_class_is_gone_for_python(tmp_path):
    root = _py_project(tmp_path, {"requirements.txt": "pkg==1.20.0\n"})
    assert not apply_mod.check_python_version(root, "pkg", "1.2")
    assert not apply_mod.check_python_version(root, "pkg", "1.20")
    assert apply_mod.check_python_version(root, "pkg", "1.20.0")


@pytest.mark.parametrize(
    "version", ["1.0.0", "1.0.0rc1", "1!2.0", "2.0.0.post1", "1.0.0.dev3", "2023.10.1"]
)
def test_a_pep440_version_confirms_exactly(tmp_path, version):
    root = _py_project(tmp_path, {"requirements.txt": f"pkg=={version}\n"})
    assert apply_mod.check_python_version(root, "pkg", version)
    assert not apply_mod.check_python_version(root, "pkg", version + "0")


@pytest.mark.parametrize(
    "line",
    [
        "pkg>=1.0.0",
        "pkg~=1.0.0",
        "pkg<1.0.0",
        "pkg!=1.0.0",
        "pkg",
        "# pkg==1.0.0",
        "other==1.0.0",
        "",
    ],
)
def test_only_an_exact_pin_confirms_a_python_bump(tmp_path, line):
    """A range is not a landed pin: `uv add` writes `==` when it pins, and
    accepting `>=1.0.0` would confirm a bump that did not change the manifest."""
    root = _py_project(tmp_path, {"requirements.txt": line + "\n"})
    assert apply_mod.check_python_version(root, "pkg", "1.0.0") is False


@pytest.mark.parametrize(
    "spelling", ["ruamel.yaml", "ruamel-yaml", "ruamel_yaml", "Ruamel.YAML", "RUAMEL-yaml"]
)
def test_pep503_normalization_accepts_every_equivalent_spelling(tmp_path, spelling):
    """`.`, `-`, `_` and case all fold on PyPI, so a manifest spelling that
    differs from the requested name is the same project, not a mismatch."""
    root = _py_project(tmp_path, {"requirements.txt": f"{spelling}==0.18.5\n"})
    assert apply_mod.check_python_version(root, "ruamel.yaml", "0.18.5")


def test_an_extras_bracket_does_not_defeat_the_pin_check(tmp_path):
    root = _py_project(tmp_path, {"requirements.txt": "pkg[socks]==1.0.0\n"})
    assert apply_mod.check_python_version(root, "pkg", "1.0.0")


def test_an_environment_marker_does_not_defeat_the_pin_check(tmp_path):
    root = _py_project(
        tmp_path, {"requirements.txt": 'pkg==1.0.0 ; python_version < "3.12"\n'}
    )
    assert apply_mod.check_python_version(root, "pkg", "1.0.0")


def test_a_project_with_no_python_manifest_is_unconfirmed(tmp_path):
    """Conservative by design: no manifest read means the bump is not proven."""
    assert apply_mod.check_python_version(tmp_path, "pkg", "1.0.0") is False


@pytest.mark.parametrize(
    ("name", "body"),
    [
        ("pyproject.toml", "not toml ["),
        ("pyproject.toml", ""),
        ("pyproject.toml", '[project]\ndependencies = "nope"\n'),
        ("pyproject.toml", "[project]\ndependencies = [1, 2]\n"),
        ("uv.lock", "not toml ["),
        ("uv.lock", '[[package]]\nname = "pkg"\n'),
        ("uv.lock", '[[package]]\nname = "pkg"\nversion = 1\n'),
        ("requirements.txt", "\x00\xff"),
    ],
)
def test_a_malformed_python_manifest_never_confirms_and_never_raises(
    tmp_path, name, body
):
    root = _py_project(tmp_path, {name: body})
    assert apply_mod.check_python_version(root, "pkg", "1.0.0") is False


def test_a_uv_lock_pin_confirms_and_a_wrong_version_does_not(tmp_path):
    root = _py_project(
        tmp_path, {"uv.lock": '[[package]]\nname = "pkg"\nversion = "1.0.0"\n'}
    )
    assert apply_mod.check_python_version(root, "pkg", "1.0.0")
    assert not apply_mod.check_python_version(root, "pkg", "1.0")


# --- P3: classification ------------------------------------------------------


def _independently_classified(installed: str, latest: str) -> str:
    """A second, literal reading of the documented classification rule.

    Written from research.py's docstring -- PATCH-SAFE, MINOR-CHECK,
    MAJOR-ADVISORY or CURRENT, with an unorderable version falling back to
    MINOR-CHECK because it is never reported as a safe patch.
    """
    import re

    head = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?")

    def triple(raw: str):
        match = head.match(raw.lstrip("v"))
        if not match:
            return None
        return tuple(int(group or 0) for group in match.groups())

    cur, lat = triple(installed), triple(latest)
    if cur is None or lat is None:
        return "MINOR-CHECK"
    if cur == lat:
        return "CURRENT"
    if lat[0] > cur[0]:
        return "MAJOR-ADVISORY"
    if lat[0] == cur[0] and lat[1] > cur[1]:
        return "MINOR-CHECK"
    if lat[:2] == cur[:2] and lat[2] > cur[2]:
        return "PATCH-SAFE"
    return "CURRENT"


def test_classification_matches_an_independent_reading_of_the_documented_rule():
    """P3 exhaustively over every version pair: 35 x 35 = 1,225 comparisons."""
    for installed, latest in itertools.product(VERSIONS, VERSIONS):
        verdict = research.classify(installed, latest)
        assert verdict in ("PATCH-SAFE", "MINOR-CHECK", "MAJOR-ADVISORY", "CURRENT")
        assert verdict == _independently_classified(installed, latest), (
            f"{installed!r} -> {latest!r}"
        )


def test_an_unorderable_version_is_never_reported_as_a_safe_patch():
    """PATCH-SAFE is the only class the skill applies without asking, so a version
    this parser cannot order must never earn it."""
    unorderable = ("", "latest", "*", "^1.20.0", ">=1 <2", "nan", "x" * 200, "-1")
    for value in unorderable:
        for other in VERSIONS:
            assert research.classify(value, other) != "PATCH-SAFE", (value, other)
            assert research.classify(other, value) != "PATCH-SAFE", (other, value)


def test_a_seeded_corpus_of_random_version_strings_never_raises():
    """P3 over generated input: the pieces are drawn from real version grammars,
    so the generator stays near the boundary rather than producing pure noise."""
    rng = random.Random(SEED)
    pieces = ("0", "1", "9", "10", "999", "", "x", "rc1", "a1", "dev0", "post1", "-1")
    separators = (".", "-", "+", "!", "", "~", "^")
    for _ in range(CORPUS_SIZE):
        def spin() -> str:
            count = rng.randint(1, 5)
            out = "".join(
                rng.choice(pieces) + rng.choice(separators) for _ in range(count)
            )
            return rng.choice(("", "v", "^", "~", ">=")) + out

        installed, latest = spin(), spin()
        verdict = research.classify(installed, latest)
        assert verdict == _independently_classified(installed, latest), (
            f"{installed!r} -> {latest!r} gave {verdict}"
        )
        assert isinstance(research.is_prerelease(installed), bool)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.0.0rc1", True),
        ("1.0.0a1", True),
        ("1.0.0b2", True),
        ("1.0.0-rc.1", True),
        ("1.0.0.dev3", True),
        ("2.0.0.post1", True),
        ("1.0.0", False),
        ("2023.10.1", False),
        ("v1.2.3", False),
        ("1.2.3-1ubuntu2", False),
        ("1.0.0+build.1", False),
        ("", False),
    ],
)
def test_prerelease_detection(raw: str, expected: bool):
    assert research.is_prerelease(raw) is expected


def test_pick_stable_never_returns_an_unorderable_candidate():
    """Reproduction: sorting by `normalize_version(v) or (0,0,0)` made every
    unorderable candidate compare EQUAL, so a registry serving junk keys returned
    "" as the latest version -- an empty version then flowed into the bump."""
    assert research.pick_stable("1.0.0rc1", "0.9", ["", "x", "nan"]) == "1.0.0rc1"
    assert research.pick_stable("1.0.0rc1", "0.9", []) == "1.0.0rc1"
    assert research.pick_stable("1.0.0rc1", "0.9", ["0.8", "0.9"]) == "0.9"
    # An installed pre-release keeps the caller on the pre-release track.
    assert research.pick_stable("1.0.0rc1", "1.0.0rc0", ["0.9"]) == "1.0.0rc1"
    # A stable latest is returned untouched.
    assert research.pick_stable("2.0.0", "1.0.0", ["1.0.0"]) == "2.0.0"


# --- P4: registry payloads ---------------------------------------------------

REGISTRY_PAYLOADS = (
    "{}",
    "null",
    "[]",
    '{"info": null}',
    '{"info": {}}',
    '{"info": {"version": null}}',
    '{"info": {"version": "1.0.0"}}',
    '{"info": {"version": "1.0.0"}, "releases": null}',
    '{"info": {"version": "1.0.0"}, "releases": {"1.0.0": []}}',
    '{"info": {"version": "1.0.0"}, "releases": {"1.0.0": [{"yanked": true}]}}',
    '{"info": {"version": "1.0.0"}, "releases": {"1.0.0": [{"yanked": "yes"}]}}',
    '{"dist-tags": null}',
    '{"dist-tags": {}}',
    '{"dist-tags": {"latest": ""}}',
    '{"dist-tags": {"latest": "1.0.0"}, "versions": null}',
    '{"dist-tags": {"latest": "1.0.0"}, "versions": {"1.0.0": {}}}',
)


@pytest.mark.parametrize("ecosystem", ["pypi", "npm"])
@pytest.mark.parametrize("payload", REGISTRY_PAYLOADS, ids=range(len(REGISTRY_PAYLOADS)))
def test_no_registry_payload_raises_every_failure_is_a_status(
    tmp_path, monkeypatch, ecosystem, payload
):
    """P4: query_registry documents "Never raises: every failure is a status"."""
    fixtures = tmp_path / f"fx-{ecosystem}-{abs(hash(payload))}"
    fixtures.mkdir()
    (fixtures / f"{ecosystem}_pkg.json").write_text(payload)
    monkeypatch.setenv("DEP_UPDATE_FIXTURE_DIR", str(fixtures))

    record = research.query_registry(ecosystem, "pkg", "1.0.0")
    assert isinstance(record, dict)
    assert record["ecosystem"] == ecosystem
    assert record["name"] == "pkg"
    assert record.get("status") in ("OK", "CURRENT", "UNRESOLVABLE", "DISCONFIRMED")
    if record["status"] in ("OK", "CURRENT"):
        assert record["latest"], "a resolved record must carry a non-empty version"
        assert record["class"] in (
            "PATCH-SAFE",
            "MINOR-CHECK",
            "MAJOR-ADVISORY",
            "CURRENT",
        )
    else:
        assert record.get("reason"), "an unresolved record must say why"
    # The record is the tool's output contract, so it has to serialize.
    json.loads(json.dumps(record))


def test_an_unimplemented_ecosystem_is_unresolvable_not_a_crash(tmp_path, monkeypatch):
    monkeypatch.setenv("DEP_UPDATE_FIXTURE_DIR", str(tmp_path))
    for ecosystem in ("cargo", "go", "rubygems", "packagist", "", "../etc"):
        record = research.query_registry(ecosystem, "pkg", "1.0.0")
        assert record["status"] == "UNRESOLVABLE"
        assert record["reason"]


def test_an_absent_fixture_simulates_being_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("DEP_UPDATE_FIXTURE_DIR", str(tmp_path))
    record = research.query_registry("pypi", "never-published", "1.0.0")
    assert record["status"] == "UNRESOLVABLE"
    assert "network error" in record["reason"]


def test_a_fully_yanked_latest_is_disconfirmed(tmp_path, monkeypatch):
    fixtures = tmp_path / "yanked"
    fixtures.mkdir()
    (fixtures / "pypi_pkg.json").write_text(
        json.dumps(
            {
                "info": {"version": "2.0.0"},
                "releases": {"2.0.0": [{"yanked": True}, {"yanked": True}]},
            }
        )
    )
    monkeypatch.setenv("DEP_UPDATE_FIXTURE_DIR", str(fixtures))
    record = research.query_registry("pypi", "pkg", "1.0.0")
    assert record["status"] == "DISCONFIRMED"
    assert record["class"] == "DISCONFIRMED"


# --- apply.py argument handling ----------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        ".project-setup",
        ".project-setup/answers.toml",
        "answers.toml",
        "sources.toml",
        "x/answers.toml",
    ],
)
def test_apply_refuses_a_project_setup_path_as_a_package_name(tmp_path, name):
    assert apply_mod.main(["apply.py", "pypi", name, "1.0.0", str(tmp_path)]) == 2


@pytest.mark.parametrize(
    "argv",
    [
        ["apply.py"],
        ["apply.py", "pypi"],
        ["apply.py", "pypi", "pkg"],
    ],
)
def test_apply_rejects_missing_arguments(argv):
    assert apply_mod.main(argv) == 2


def test_apply_rejects_a_target_that_is_not_a_directory(tmp_path):
    missing = tmp_path / "nope"
    assert apply_mod.main(["apply.py", "pypi", "pkg", "1.0.0", str(missing)]) == 2
    assert apply_mod.main(["apply.py", "pypi", "pkg", "1.0.0", "/tmp/" + "x" * 400]) == 2


@pytest.mark.parametrize("ecosystem", ["cargo", "rust", "go"])
def test_an_advisory_only_ecosystem_prints_a_command_and_exits_zero(
    tmp_path, capsys, ecosystem
):
    assert apply_mod.main(["apply.py", ecosystem, "pkg", "1.0.0", str(tmp_path)]) == 0
    assert "ADVISORY-ONLY" in capsys.readouterr().out


def test_an_unknown_ecosystem_warns_but_exits_zero(tmp_path, capsys):
    assert apply_mod.main(["apply.py", "elixir", "pkg", "1.0.0", str(tmp_path)]) == 0
    assert "unknown ecosystem" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("files", "env", "expected"),
    [
        ({}, {}, "npm"),
        ({"pnpm-lock.yaml": ""}, {}, "pnpm"),
        ({"bun.lock": ""}, {}, "bun"),
        ({"bun.lockb": ""}, {}, "bun"),
        ({"yarn.lock": ""}, {}, "yarn"),
        ({"pnpm-lock.yaml": "", "yarn.lock": ""}, {}, "pnpm"),
        ({"yarn.lock": ""}, {"DEP_UPDATE_PKG_MANAGER": "bun"}, "bun"),
        (
            {".project-setup/answers.toml": '[module.lang-ts]\npackage_manager = "pnpm@9.1.0"\n'},
            {},
            "pnpm",
        ),
        ({".project-setup/answers.toml": "not toml ["}, {}, "npm"),
        ({".project-setup/answers.toml": "[module]\nlang-ts = 5\n"}, {}, "npm"),
    ],
)
def test_node_package_manager_detection_follows_the_documented_precedence(
    tmp_path, monkeypatch, files, env, expected
):
    root = tmp_path / f"pm{abs(hash((tuple(sorted(files)), tuple(sorted(env)))))}"
    root.mkdir()
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    monkeypatch.delenv("DEP_UPDATE_PKG_MANAGER", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert apply_mod.detect_node_pm(root) == expected


def test_the_scripts_are_committed_executable_with_a_python_shebang():
    for name in ("research.py", "apply.py"):
        path = SCRIPTS / name
        assert path.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3")
        assert os.access(path, os.X_OK), f"{name} must ship mode 755"
