"""Seeded fuzz harness for the release-please-guard `detect` subcommand.

The shell predecessor emitted INVALID JSON on an empty manifest: `grep -Ec`
printed 0 AND exited 1, which fired a `|| printf '0'` fallback that appended a
SECOND value, so the field carried `00` and the object would not parse. It got
`package_count` wrong the same way, counting LINES holding a key rather than
keys, so a minified three-package manifest reported 1. Three properties:

  P1  every `--json` invocation emits exactly one object that `json.loads`
      accepts, with every documented field present and correctly typed.
  P2  `package_count` counts KEYS, so it is invariant under formatting: minified,
      multi-line and indented spellings of the same manifest agree.
  P3  a per-package block never answers for the repo. The three load-bearing
      config values are read from the TOP LEVEL only, because a `packages` entry
      that shadowed one made the guard report the wrong repo-wide setting.

Adversarial shapes -- empty, malformed, BOM, duplicate keys, deep nesting, a
directory where a file belongs -- are pinned explicitly, since a generator does
not produce them.

Run standalone for a larger corpus: FUZZ_CASES=2000 pytest <this file>
"""

from __future__ import annotations

import importlib.util
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release-please-guard.py"
SEED = 20260729
# Each generated case spawns a subprocess, because the defect being guarded
# against is malformed OUTPUT that an in-process call cannot observe. At roughly
# 70ms per spawn the default keeps this file inside a CI budget; raise it for a
# deeper sweep.
CORPUS_SIZE = int(os.environ.get("FUZZ_CASES", "60"))

CONFIG_NAME = "release-please-config.json"
MANIFEST_NAME = ".release-please-manifest.json"

# Every field the detector documents, with the type each must hold. A missing or
# wrong-typed field breaks the shell callers that read `key=value` lines.
FIELD_TYPES = {
    "present": bool,
    "mode": str,
    "config_file": str,
    "manifest_file": str,
    "workflow_files": str,
    "separate_pull_requests": str,
    "include_component_in_tag": str,
    "tag_separator": str,
    "package_count": int,
}

MODES = frozenset({"manifest", "config-only", "inline-action", "none"})
FLAG_VALUES = frozenset({"true", "false", "unknown"})


def _load():
    spec = importlib.util.spec_from_file_location("rp_detect_fuzz", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load()


def _detect_json(directory) -> dict:
    """Run `detect --json` as a subprocess and parse its stdout.

    Deliberately out-of-process: the defect being guarded against was malformed
    OUTPUT, which an in-process call to `detect()` cannot see.
    """
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "detect", "--json", str(directory)],
        capture_output=True,
        text=True,
    )
    assert "Traceback" not in result.stderr, result.stderr
    assert result.returncode in (0, 1), f"rc={result.returncode} {result.stderr}"
    # P1: the whole point. One object, parseable, no trailing junk.
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    assert set(payload) == set(FIELD_TYPES), sorted(set(payload) ^ set(FIELD_TYPES))
    for key, expected in FIELD_TYPES.items():
        assert type(payload[key]) is expected, f"{key}={payload[key]!r}"
    assert payload["mode"] in MODES
    assert payload["separate_pull_requests"] in FLAG_VALUES
    assert payload["include_component_in_tag"] in FLAG_VALUES
    assert payload["package_count"] >= 0
    return payload


# --- P1: no shape produces malformed output ----------------------------------

MANIFEST_SHAPES = (
    "{}",
    '{"a":"1.0.0"}',
    '{"a":"1.0.0","b":"2.0.0","c":"3.0.0"}',
    '{\n  "a": "1.0.0",\n  "b": "2.0.0",\n  "c": "3.0.0"\n}\n',
    '{"a":"1","a":"2"}',
    '{"packages/x":"1.0.0","packages/y":"2.0.0"}',
    '{".":"1.0.0"}',
    "[]",
    '["a","b"]',
    "null",
    "0",
    '"a string"',
    "{",
    "}",
    "",
    "   ",
    "not json at all",
    "// a comment\n{}",
    "/* block */ {}",
    '{"a":"1",}',
    "{'a':'1'}",
    '{"a":' + "[" * 400 + "]" * 400 + "}",
    '{"' + "k" * 10_000 + '":"1"}',
    '{"a":null}',
    '{"a":1}',
    '{"a":{"nested":"1"}}',
)

CONFIG_SHAPES = (
    "{}",
    '{"packages":{".":{}}}',
    '{"separate-pull-requests":true}',
    '{"separate-pull-requests":false}',
    '{"separate-pull-requests":"true"}',
    '{"separate-pull-requests":null}',
    '{"include-component-in-tag":true,"tag-separator":"-v"}',
    '{"tag-separator":""}',
    '{"tag-separator":5}',
    '{"packages":{"x":{"separate-pull-requests":true}}}',
    '{"separate-pull-requests":false,"packages":{"x":{"separate-pull-requests":true}}}',
    '{"$schema":"https://x","packages":{}}',
    "[]",
    "null",
    "{",
    "",
    "not json",
    '{"packages":' + "{" * 200 + "}" * 200 + "}",
)


@pytest.mark.parametrize("body", MANIFEST_SHAPES, ids=range(len(MANIFEST_SHAPES)))
def test_every_manifest_shape_emits_parseable_json(tmp_path, body):
    """P1: the shell emitted `00` for package_count on an empty manifest, because
    `grep -Ec` prints 0 and exits 1, firing a `|| printf '0'` fallback that
    appended a second value. The object then would not parse at all."""
    (tmp_path / MANIFEST_NAME).write_text(body)
    (tmp_path / CONFIG_NAME).write_text("{}")
    _detect_json(tmp_path)


@pytest.mark.parametrize("body", CONFIG_SHAPES, ids=range(len(CONFIG_SHAPES)))
def test_every_config_shape_emits_parseable_json(tmp_path, body):
    (tmp_path / CONFIG_NAME).write_text(body)
    (tmp_path / MANIFEST_NAME).write_text('{"a":"1.0.0"}')
    _detect_json(tmp_path)


def test_an_empty_manifest_reports_zero_not_a_doubled_value(tmp_path):
    (tmp_path / MANIFEST_NAME).write_text("{}")
    (tmp_path / CONFIG_NAME).write_text("{}")
    assert _detect_json(tmp_path)["package_count"] == 0


def test_a_repo_with_no_release_please_files_still_emits_parseable_json(tmp_path):
    facts = _detect_json(tmp_path)
    assert facts["present"] is False
    assert facts["mode"] == "none"
    assert facts["package_count"] == 0


def test_a_generated_corpus_of_manifest_config_pairs_always_parses(tmp_path):
    """P1 over the product of the two shape lists, sampled with a fixed seed."""
    rng = random.Random(SEED)
    for index in range(CORPUS_SIZE):
        root = tmp_path / f"case{index}"
        root.mkdir()
        if rng.random() < 0.85:
            (root / MANIFEST_NAME).write_text(rng.choice(MANIFEST_SHAPES))
        if rng.random() < 0.85:
            (root / CONFIG_NAME).write_text(rng.choice(CONFIG_SHAPES))
        if rng.random() < 0.3:
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "release.yml").write_text(
                rng.choice(
                    [
                        "uses: googleapis/release-please-action@v4",
                        "name: nothing relevant\n",
                        "",
                    ]
                )
            )
        _detect_json(root)


# --- P2: package_count counts keys, not lines --------------------------------


@pytest.mark.parametrize(
    "body",
    [
        '{"a":"1","b":"2","c":"3"}',
        '{\n"a":"1",\n"b":"2",\n"c":"3"\n}',
        '{\n  "a": "1",\n  "b": "2",\n  "c": "3"\n}\n',
        '{"a":"1",\n "b":"2", "c":"3"}',
        '{ "a" : "1" , "b" : "2" , "c" : "3" }',
    ],
    ids=["minified", "one-per-line", "indented", "mixed", "spaced"],
)
def test_package_count_is_invariant_under_formatting(tmp_path, body):
    """P2, and the second shell defect: `grep -Ec '"[^"]+"[[:space:]]*:'` counted
    LINES holding at least one key, so this minified three-package manifest
    reported 1 while the multi-line spelling reported 3."""
    (tmp_path / MANIFEST_NAME).write_text(body)
    (tmp_path / CONFIG_NAME).write_text("{}")
    assert _detect_json(tmp_path)["package_count"] == 3


def test_duplicate_keys_count_once(tmp_path):
    """JSON semantics: a repeated key is one member, last value winning."""
    (tmp_path / MANIFEST_NAME).write_text('{"a":"1","a":"2","a":"3"}')
    (tmp_path / CONFIG_NAME).write_text("{}")
    assert _detect_json(tmp_path)["package_count"] == 1


def test_a_nested_value_does_not_inflate_the_count(tmp_path):
    """Only top-level members are packages; a nested object's keys are not."""
    (tmp_path / MANIFEST_NAME).write_text('{"a":{"x":"1","y":"2","z":"3"}}')
    (tmp_path / CONFIG_NAME).write_text("{}")
    assert _detect_json(tmp_path)["package_count"] == 1


@pytest.mark.parametrize("body", ["[]", '["a","b"]', "null", "5", '"str"', "{", ""])
def test_a_non_object_manifest_counts_zero(tmp_path, body):
    """A manifest that is not an object declares no packages; guessing a count
    from a list would report packages that release-please will not release."""
    (tmp_path / MANIFEST_NAME).write_text(body)
    (tmp_path / CONFIG_NAME).write_text("{}")
    assert _detect_json(tmp_path)["package_count"] == 0


def test_a_utf8_bom_does_not_zero_the_package_count(tmp_path):
    """Reproduction: `json` rejects a BOM outright, so a manifest written by a
    Windows editor parsed as nothing and a three-package repo reported 0."""
    (tmp_path / MANIFEST_NAME).write_bytes(
        b'\xef\xbb\xbf{"a":"1","b":"2","c":"3"}'
    )
    (tmp_path / CONFIG_NAME).write_bytes(b'\xef\xbb\xbf{"separate-pull-requests":true}')
    facts = _detect_json(tmp_path)
    assert facts["package_count"] == 3
    assert facts["separate_pull_requests"] == "true"


def test_a_large_manifest_counts_every_key(tmp_path):
    count = 5_000
    (tmp_path / MANIFEST_NAME).write_text(
        json.dumps({f"packages/p{index}": "1.0.0" for index in range(count)})
    )
    (tmp_path / CONFIG_NAME).write_text("{}")
    assert _detect_json(tmp_path)["package_count"] == count


# --- P3: a per-package block never answers for the repo ----------------------


@pytest.mark.parametrize(
    ("key", "field"),
    [
        ("separate-pull-requests", "separate_pull_requests"),
        ("include-component-in-tag", "include_component_in_tag"),
    ],
)
@pytest.mark.parametrize("top", [True, False])
def test_a_per_package_override_never_shadows_the_top_level_flag(
    tmp_path, key, field, top
):
    """Reproduction: the shell pattern matched ANYWHERE in the file, so a package
    entry setting `separate-pull-requests: true` made the guard report the repo as
    separate-PR when the top level said otherwise."""
    root = tmp_path / f"{field}-{top}"
    root.mkdir()
    (root / CONFIG_NAME).write_text(
        json.dumps({key: top, "packages": {"x": {key: not top}}})
    )
    (root / MANIFEST_NAME).write_text('{"x":"1.0.0"}')
    assert _detect_json(root)[field] == ("true" if top else "false")


@pytest.mark.parametrize(
    "key", ["separate-pull-requests", "include-component-in-tag"]
)
def test_a_flag_set_only_per_package_reports_unknown_at_the_top_level(tmp_path, key):
    root = tmp_path / f"only-{key}"
    root.mkdir()
    (root / CONFIG_NAME).write_text(json.dumps({"packages": {"x": {key: True}}}))
    (root / MANIFEST_NAME).write_text('{"x":"1.0.0"}')
    field = key.replace("-", "_")
    assert _detect_json(root)[field] == "unknown"


@pytest.mark.parametrize(
    "value", [True, False, None, "true", "false", 1, 0, [], {}, "yes"]
)
def test_only_a_real_boolean_reports_true_or_false(tmp_path, value):
    """A string "true" is not a boolean to release-please, so reporting it as one
    would tell the caller the repo is configured a way it is not."""
    root = tmp_path / f"flag-{value!r}".replace("/", "_")
    root.mkdir()
    (root / CONFIG_NAME).write_text(json.dumps({"separate-pull-requests": value}))
    (root / MANIFEST_NAME).write_text("{}")
    expected = {True: "true", False: "false"}.get(
        value if isinstance(value, bool) else object(), "unknown"
    )
    assert _detect_json(root)["separate_pull_requests"] == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [("-v", "-v"), ("", "unknown"), (None, "unknown"), (5, "unknown"), ([], "unknown")],
)
def test_the_tag_separator_is_reported_only_when_it_is_a_non_empty_string(
    tmp_path, value, expected
):
    root = tmp_path / f"sep-{value!r}".replace("/", "_")
    root.mkdir()
    (root / CONFIG_NAME).write_text(json.dumps({"tag-separator": value}))
    (root / MANIFEST_NAME).write_text("{}")
    assert _detect_json(root)["tag_separator"] == expected


# --- mode and exit status ----------------------------------------------------


@pytest.mark.parametrize(
    ("files", "mode", "present"),
    [
        ({CONFIG_NAME: "{}", MANIFEST_NAME: "{}"}, "manifest", True),
        ({CONFIG_NAME: "{}"}, "config-only", True),
        ({MANIFEST_NAME: "{}"}, "none", False),
        ({}, "none", False),
    ],
)
def test_the_mode_follows_which_files_are_present(tmp_path, files, mode, present):
    """A manifest alone is NOT release-please: the config is what wires it up."""
    root = tmp_path / f"{mode}-{present}"
    root.mkdir()
    for name, body in files.items():
        (root / name).write_text(body)
    facts = _detect_json(root)
    assert facts["mode"] == mode
    assert facts["present"] is present


def test_a_workflow_alone_is_inline_action_mode(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "release.yml").write_text("uses: googleapis/release-please-action@v4")
    facts = _detect_json(tmp_path)
    assert facts["mode"] == "inline-action"
    assert facts["present"] is True
    assert ".github/workflows/release.yml" in facts["workflow_files"]


def test_the_exit_status_reports_whether_the_repo_is_managed(tmp_path):
    """0 when managed, 1 when not: the gate's callers branch on this."""
    managed = tmp_path / "managed"
    managed.mkdir()
    (managed / CONFIG_NAME).write_text("{}")
    (managed / MANIFEST_NAME).write_text("{}")
    unmanaged = tmp_path / "unmanaged"
    unmanaged.mkdir()

    for directory, expected in ((managed, 0), (unmanaged, 1)):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "detect", "--json", str(directory)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == expected
        json.loads(result.stdout)


# --- the text output mode ----------------------------------------------------


def test_text_mode_emits_one_key_equals_value_line_per_field(tmp_path):
    (tmp_path / CONFIG_NAME).write_text('{"separate-pull-requests":false}')
    (tmp_path / MANIFEST_NAME).write_text('{"a":"1","b":"2"}')
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "detect", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = result.stdout.splitlines()
    assert len(lines) == len(FIELD_TYPES)
    keys = [line.split("=", 1)[0] for line in lines]
    assert keys == list(guard.FIELD_ORDER)
    assert "package_count=2" in lines
    assert "present=true" in lines, "a bool renders as true/false, not True/False"


def test_a_workflow_filename_holding_an_equals_sign_does_not_break_the_text_format(
    tmp_path,
):
    """The text format is `key=value`, so a value containing `=` must still leave
    the KEY unambiguous -- callers split on the FIRST `=`."""
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "a=b.yml").write_text("uses: googleapis/release-please-action@v4")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "detect", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        assert line.split("=", 1)[0] in FIELD_TYPES


# --- argument and filesystem handling ----------------------------------------


@pytest.mark.parametrize(
    ("argv", "status"),
    [
        (["detect", "--nope"], 2),
        (["detect", "-x"], 2),
        (["detect", "a", "b"], 2),
        (["detect", "/nonexistent/path/xyz"], 2),
        (["detect", "/tmp/" + "x" * 400], 2),
        (["nonsense"], 2),
    ],
)
def test_a_usage_error_exits_two_without_a_traceback(argv, status):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *argv], capture_output=True, text=True
    )
    assert result.returncode == status, result.stderr
    assert "Traceback" not in result.stderr


def test_detect_help_exits_zero():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "detect", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip()


def test_a_directory_where_a_config_file_belongs_is_not_a_config(tmp_path):
    (tmp_path / CONFIG_NAME).mkdir()
    (tmp_path / MANIFEST_NAME).mkdir()
    facts = _detect_json(tmp_path)
    assert facts["config_file"] == ""
    assert facts["manifest_file"] == ""
    assert facts["mode"] == "none"


def test_an_unreadable_config_falls_back_to_unknown_rather_than_crashing(tmp_path):
    config = tmp_path / CONFIG_NAME
    config.write_text('{"separate-pull-requests":true}')
    (tmp_path / MANIFEST_NAME).write_text("{}")
    os.chmod(config, 0)
    try:
        facts = _detect_json(tmp_path)
    finally:
        os.chmod(config, 0o644)
    # The file EXISTS, so the mode still reports manifest; only its values are
    # unknown. Fail open: an unreadable config loses a fact, not the run.
    assert facts["mode"] == "manifest"
    assert facts["separate_pull_requests"] == "unknown"


def test_the_guard_still_reads_a_hook_payload_on_stdin():
    """`detect` is an argv subcommand bolted onto a PreToolUse hook. With no argv
    the script must still behave as a hook: fail open on junk, never `ask`."""
    for payload in ("", "not json", "{}", '{"tool_input": 5}', '{"tool_input": {}}'):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)], input=payload, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
        assert "Traceback" not in result.stderr
        assert '"ask"' not in result.stdout
