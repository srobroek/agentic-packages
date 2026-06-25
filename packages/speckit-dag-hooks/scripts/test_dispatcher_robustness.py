#!/usr/bin/env python3
"""Robustness (crash-safety) tests for dispatcher.py.

Phase-1 audit remediation: the dispatcher must never raise on a hostile or
malformed hook payload -- it degrades to a silent no-op (returns "" / produces
no decision) instead of crashing the hook. These tests feed the exact
adversarial payloads named in the fix list:

  - non-string command_name / skill / command_name / prompt
  - non-dict tool_input
  - a nodes.json phase missing its 'title'
  - non-string feature_directory in .specify/feature.json

Imports the dispatcher module directly (no hyphen in its name) and drives the
in-process functions, plus one end-to-end subprocess check via main()/stdin.
"""
import importlib.util
import io
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module(name, filename):
    path = os.path.join(HERE, filename)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


disp = _load_module("speckit_dispatcher", "dispatcher.py")


# ---------------------------------------------------------------------------
# _resolve_command must never raise and must return a str for any input shape.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "event,payload",
    [
        # UserPromptExpansion: command_name as non-string types.
        ("UserPromptExpansion", {"command_name": {"nested": "dict"}}),
        ("UserPromptExpansion", {"command_name": ["a", "list"]}),
        ("UserPromptExpansion", {"command_name": 12345}),
        ("UserPromptExpansion", {"command_name": True}),
        ("UserPromptExpansion", {"command_name": None}),
        ("UserPromptExpansion", {}),
        # PreToolUse: tool_input itself non-dict.
        ("PreToolUse", {"tool_input": "a bare string"}),
        ("PreToolUse", {"tool_input": ["list"]}),
        ("PreToolUse", {"tool_input": 7}),
        ("PreToolUse", {"tool_input": None}),
        # PreToolUse: tool_input.skill / command_name / prompt non-string.
        ("PreToolUse", {"tool_input": {"skill": {"x": 1}}}),
        ("PreToolUse", {"tool_input": {"command_name": ["y"]}}),
        ("PreToolUse", {"tool_input": {"prompt": 99}}),
        ("PostToolUse", {"tool_input": {"skill": 3.14}}),
        ("PostToolUse", {"tool_input": {"prompt": {"k": "v"}}}),
        # UserPromptSubmit: prompt non-string.
        ("UserPromptSubmit", {"prompt": {"not": "a string"}}),
        ("UserPromptSubmit", {"prompt": 0}),
        ("UserPromptSubmit", {"prompt": None}),
    ],
)
def test_resolve_command_never_raises_and_returns_str(event, payload):
    result = disp._resolve_command(event, payload)
    assert isinstance(result, str), "must return str, got %r" % type(result)


def test_resolve_command_string_inputs_still_work():
    assert (
        disp._resolve_command(
            "UserPromptExpansion", {"command_name": "speckit.plan"}
        )
        == "speckit.plan"
    )
    assert (
        disp._resolve_command(
            "PreToolUse", {"tool_input": {"skill": "speckit-plan"}}
        )
        == "speckit-plan"
    )
    assert (
        disp._resolve_command(
            "UserPromptSubmit", {"prompt": "run /speckit.plan please"}
        )
        == "speckit.plan"
    )


def test_as_str_coercion():
    assert disp._as_str("ok") == "ok"
    assert disp._as_str(None) == ""
    assert disp._as_str(123) == ""
    assert disp._as_str({"a": 1}) == ""
    assert disp._as_str(["x"]) == ""
    assert disp._as_str(True) == ""


# ---------------------------------------------------------------------------
# render_body must not KeyError when a node phase is missing 'title'.
# ---------------------------------------------------------------------------
def test_render_body_missing_title_falls_back_to_node_id():
    node = {"came_from": ["somewhere"], "soft": ["(none)"]}
    body = disp.render_body("pre", node, "my-node-id")
    assert body.startswith("# my-node-id"), body[:40]


def test_render_body_missing_title_and_no_node_id():
    # Default node_id="" -> header degrades to "# " with no crash.
    node = {"going_to": ["next"]}
    body = disp.render_body("post", node)
    assert body.startswith("# "), body[:40]


def test_render_body_uses_title_when_present():
    node = {"title": "/speckit.plan", "going_to": ["next"]}
    body = disp.render_body("post", node, "plan")
    assert body.startswith("# /speckit.plan"), body[:40]


# ---------------------------------------------------------------------------
# _resolve_feat must not raise on a non-string feature_directory.
# ---------------------------------------------------------------------------
def test_resolve_feat_non_string_feature_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("SPECIFY_FEATURE_DIRECTORY", raising=False)
    specify = tmp_path / ".specify"
    specify.mkdir()
    # feature_directory as a dict -> previously crashed on .startswith/.rstrip.
    (specify / "feature.json").write_text(
        json.dumps({"feature_directory": {"bogus": "nonstring"}})
    )
    feat = disp._resolve_feat(str(tmp_path))
    assert isinstance(feat, str)
    assert feat == ""  # non-string coerced away -> falls through


def test_resolve_feat_list_feature_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("SPECIFY_FEATURE_DIRECTORY", raising=False)
    specify = tmp_path / ".specify"
    specify.mkdir()
    (specify / "feature.json").write_text(
        json.dumps({"feature_directory": ["specs/001-demo"]})
    )
    feat = disp._resolve_feat(str(tmp_path))
    assert isinstance(feat, str)
    assert feat == ""


def test_resolve_feat_string_feature_directory_still_works(tmp_path, monkeypatch):
    monkeypatch.delenv("SPECIFY_FEATURE_DIRECTORY", raising=False)
    specify = tmp_path / ".specify"
    specify.mkdir()
    (specify / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-demo/"})
    )
    feat = disp._resolve_feat(str(tmp_path))
    assert feat == "001-demo"


# ---------------------------------------------------------------------------
# End-to-end: main() over stdin with an adversarial payload must exit 0 and not
# raise. Drives the full path (parse argv-less -> resolve_command -> normalize).
# ---------------------------------------------------------------------------
def _run_main(monkeypatch, payload, argv_tail):
    monkeypatch.setattr(sys, "argv", ["dispatcher.py"] + argv_tail)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    rc = disp.main()
    return rc, out.getvalue()


def test_main_nonstring_command_name_is_silent_noop(monkeypatch, tmp_path):
    nodes = tmp_path / "nodes.json"
    nodes.write_text(json.dumps({"plan": {"pre": {"title": "/speckit.plan"}}}))
    rc, output = _run_main(
        monkeypatch,
        {"hook_event_name": "UserPromptExpansion", "command_name": {"x": 1}},
        [str(nodes), "pre"],
    )
    assert rc == 0
    assert output == ""  # unresolved command -> no decision emitted


def test_main_nondict_tool_input_is_silent_noop(monkeypatch, tmp_path):
    nodes = tmp_path / "nodes.json"
    nodes.write_text(json.dumps({"plan": {"pre": {"title": "/speckit.plan"}}}))
    rc, output = _run_main(
        monkeypatch,
        {"hook_event_name": "PreToolUse", "tool_input": "bare-string"},
        [str(nodes), "pre"],
    )
    assert rc == 0
    assert output == ""


def test_main_node_missing_title_does_not_crash(monkeypatch, tmp_path):
    # A real resolvable command whose node phase lacks 'title': must render
    # using node_id and emit a valid decision rather than KeyError.
    nodes = tmp_path / "nodes.json"
    nodes.write_text(json.dumps({"plan": {"post": {"going_to": ["next"]}}}))
    rc, output = _run_main(
        monkeypatch,
        {
            "hook_event_name": "PostToolUse",
            "tool_input": {"skill": "speckit-plan"},
        },
        [str(nodes), "post"],
    )
    assert rc == 0
    decision = json.loads(output)
    ctx = decision["hookSpecificOutput"]["additionalContext"]
    assert ctx.startswith("# plan"), ctx[:40]


def test_main_malformed_stdin_is_silent_noop(monkeypatch, tmp_path):
    nodes = tmp_path / "nodes.json"
    nodes.write_text(json.dumps({"plan": {"pre": {"title": "/speckit.plan"}}}))
    monkeypatch.setattr(sys, "argv", ["dispatcher.py", str(nodes), "pre"])
    monkeypatch.setattr(sys, "stdin", io.StringIO("{not valid json"))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    rc = disp.main()
    assert rc == 0
    assert out.getvalue() == ""


def test_main_nonstring_feature_directory_does_not_crash(monkeypatch, tmp_path):
    # spec.md-less feature with a malformed feature.json: _resolve_feat must
    # coerce the non-string and the dispatcher must still emit a decision.
    monkeypatch.delenv("SPECIFY_FEATURE_DIRECTORY", raising=False)
    specify = tmp_path / ".specify"
    specify.mkdir()
    (specify / "feature.json").write_text(
        json.dumps({"feature_directory": {"bogus": 1}})
    )
    nodes = tmp_path / "nodes.json"
    nodes.write_text(json.dumps({"plan": {"post": {"title": "/speckit.plan"}}}))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    rc, output = _run_main(
        monkeypatch,
        {
            "hook_event_name": "PostToolUse",
            "tool_input": {"skill": "speckit-plan"},
            "cwd": str(tmp_path),
        },
        [str(nodes), "post"],
    )
    assert rc == 0
    decision = json.loads(output)
    assert decision["hookSpecificOutput"]["additionalContext"].startswith(
        "# /speckit.plan"
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
