"""Tests for the non-guard repo-local hooks.

These hooks had no tests before the port. Each suite pins the behaviour that
made the hook worth keeping plus the fail-open contract, and several cases record a
defect the shell version carried.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(stem: str):
    """Import a hyphenated hook script as a module."""
    path = SCRIPTS / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    assert spec and spec.loader, path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def drive(module, payload, monkeypatch):
    """Run a hook's main() against a payload string."""
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    return module.main()


ALL_STEMS = [
    "failure-logger",
    "apm-outdated-check",
    "notify",
]


# --- contract: every hook -------------------------------------------------


@pytest.mark.parametrize("stem", ALL_STEMS)
def test_every_hook_has_a_shebang(stem):
    first = (SCRIPTS / f"{stem}.py").read_text(encoding="utf-8").splitlines()[0]
    assert first == "#!/usr/bin/env python3"


@pytest.mark.parametrize("stem", ALL_STEMS)
def test_every_hook_is_executable(stem):
    assert os.access(SCRIPTS / f"{stem}.py", os.X_OK), f"{stem}.py must be chmod +x"


@pytest.mark.parametrize("stem", ALL_STEMS)
def test_every_hook_compiles(stem):
    path = SCRIPTS / f"{stem}.py"
    subprocess.run(["python3", "-m", "py_compile", str(path)], check=True)


@pytest.mark.parametrize("stem", ALL_STEMS)
@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("", id="empty"),
        pytest.param("not json", id="unparseable"),
        pytest.param("[]", id="not-an-object"),
        pytest.param("{}", id="empty-object"),
        pytest.param('{"tool_input": null}', id="null-tool-input"),
    ],
)
def test_no_hook_raises_on_a_malformed_payload(stem, payload, monkeypatch, capsys):
    """Fail open: a hook must never turn a bad payload into a crash."""
    module = load(stem)
    code = drive(module, payload, monkeypatch)
    capsys.readouterr()
    assert code in (0, 2)


@pytest.mark.parametrize("stem", ALL_STEMS)
def test_no_hook_shells_out_to_jq_or_awk(stem):
    """The point of the port: no hook parses JSON or tokenizes with a subprocess."""
    body = (SCRIPTS / f"{stem}.py").read_text(encoding="utf-8")
    for banned in ('"jq"', "'jq'", '"awk"', "'awk'", '"sed"', "'sed'"):
        assert banned not in body, f"{stem}.py still spawns {banned}"


# --- failure-logger ------------------------------------------------------


def test_failure_logger_writes_one_line(tmp_path, monkeypatch, capsys):
    module = load("failure-logger")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    payload = json.dumps({"tool_name": "Bash", "error": "boom", "cwd": "/x"})
    assert drive(module, payload, monkeypatch) == 0
    capsys.readouterr()
    content = (tmp_path / ".claude" / "debug" / "tool-failures.log").read_text()
    assert content.count("\n") == 1
    assert "Bash" in content and "boom" in content


def test_failure_logger_collapses_newlines(tmp_path, monkeypatch, capsys):
    """A multi-line error must not break the one-record-per-line format."""
    module = load("failure-logger")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    payload = json.dumps({"tool_name": "Bash", "error": "line1\nline2\nline3"})
    drive(module, payload, monkeypatch)
    capsys.readouterr()
    content = (tmp_path / ".claude" / "debug" / "tool-failures.log").read_text()
    assert content.count("\n") == 1
    assert "line1 line2 line3" in content


def test_failure_logger_truncates(tmp_path, monkeypatch, capsys):
    module = load("failure-logger")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    drive(module, json.dumps({"error": "x" * 5000}), monkeypatch)
    capsys.readouterr()
    content = (tmp_path / ".claude" / "debug" / "tool-failures.log").read_text()
    assert len(content) < 400


def test_failure_logger_rotates(tmp_path, monkeypatch, capsys):
    module = load("failure-logger")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    log = tmp_path / ".claude" / "debug" / "tool-failures.log"
    log.parent.mkdir(parents=True)
    log.write_text("x" * (module.ROTATE_BYTES + 1))
    drive(module, json.dumps({"tool_name": "T", "error": "e"}), monkeypatch)
    capsys.readouterr()
    assert (tmp_path / ".claude" / "debug" / "tool-failures.log.old").is_file()
    # The record that triggered rotation must survive in the rotated file.
    assert "T" in (tmp_path / ".claude" / "debug" / "tool-failures.log.old").read_text()




# --- apm-outdated-check -------------------------------------------------


def test_outdated_skips_subagents(monkeypatch):
    module = load("apm-outdated-check")
    assert drive(module, json.dumps({"agent_id": "sub"}), monkeypatch) == 0


def test_outdated_state_filename_is_platform_stable():
    """The shell version derived it from `md5 || md5sum | cut`, which produced a
    different filename on macOS than on Linux for the same repository."""
    import hashlib

    a = hashlib.md5(b"/repo/x", usedforsecurity=False).hexdigest()
    b = hashlib.md5(b"/repo/x", usedforsecurity=False).hexdigest()
    assert a == b and len(a) == 32


def test_outdated_exit_two_is_documented():
    """asyncRewake delivers stderr to the agent only on exit 2."""
    body = (SCRIPTS / "apm-outdated-check.py").read_text(encoding="utf-8")
    assert "return 2" in body


def test_outdated_advice_uses_the_undeprecated_command():
    """APM reports `apm deps update` as DEPRECATED in favour of `apm update`."""
    module = load("apm-outdated-check")
    assert "apm update" in module.ADVICE
    assert "apm deps update" not in module.ADVICE


def test_outdated_advice_never_names_a_single_global_package():
    """`apm update --global <pkg>` plans "1 updated, N removed" and prunes every
    other global package; the bare `--global --yes` form removes nothing."""
    module = load("apm-outdated-check")
    assert "apm update --global --yes" in module.ADVICE
    assert "prunes" in module.ADVICE



# --- notify -------------------------------------------------------------


def test_notify_is_a_noop_off_darwin(monkeypatch):
    module = load("notify")
    monkeypatch.setattr("platform.system", lambda: "Linux")
    assert drive(module, json.dumps({"message": "hi"}), monkeypatch) == 0


def test_notify_suppresses_when_own_app_is_frontmost(monkeypatch):
    module = load("notify")
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setenv("__CFBundleIdentifier", "com.github.wez.wezterm")
    monkeypatch.setattr(module, "frontmost", lambda: "com.github.wez.wezterm")
    calls = []
    monkeypatch.setattr("subprocess.run", lambda *a, **k: calls.append(a))
    assert drive(module, json.dumps({"message": "hi"}), monkeypatch) == 0
    assert calls == []


def test_notify_maps_term_program_to_bundle_id():
    module = load("notify")
    assert module.BUNDLE_IDS["ghostty"] == "com.mitchellh.ghostty"
