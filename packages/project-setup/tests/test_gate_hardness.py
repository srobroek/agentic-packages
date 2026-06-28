"""Spec 004 Phase 1 — gate-primitive foundation: hardness, flags, when, init_only.

Covers:
- SC-001: StepSpec round-trips hardness/allow_flag/skip_flag/when/init_only through
  the manifest parser + the frozen-plan serializer; an unknown hardness is rejected
  as MANIFEST_MALFORMED; a typo'd `when` key is rejected.
- SC-002: run_gate_step resolves the three hardnesses correctly in --non-interactive
  (hard SAFE-skips / performs with allow_flag; soft proceeds / SAFE-skips with
  skip_flag; informational prints + proceeds) — NONE call io.confirm.
- when predicate drops a gate at build time (deterministic across init/reproduce).
- init_only auto-proceeds on plain reproduce (no prompt, not a skip) and re-arms
  under --refresh.

Run via:
  uv run --with pytest pytest -q packages/project-setup/tests/test_gate_hardness.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


contracts = _load("contracts")
manifest = _load("manifest")
plan_mod = _load("plan")
executor = _load("executor")

run_gate_step = executor.run_gate_step
StepSpec = manifest.StepSpec
parse_manifest = manifest.parse_manifest
ErrorCode = contracts.ErrorCode


# --------------------------------------------------------------------------- #
# IO doubles                                                                   #
# --------------------------------------------------------------------------- #
class _ConfirmRaisesIO:
    """Proves io.confirm() is NEVER called (the CI-deadlock guarantee)."""

    def __init__(self):
        self.log: list[str] = []

    def confirm(self, item):
        raise AssertionError(f"confirm() must NOT be called, got item={item!r}")

    def notify(self, msg: str):
        self.log.append(msg)


class _RecordingIO:
    """Records confirm() calls and returns a scripted result."""

    def __init__(self, result: bool = True):
        self.result = result
        self.confirms: list[dict] = []
        self.log: list[str] = []

    def confirm(self, item):
        self.confirms.append(item)
        return self.result

    def notify(self, msg: str):
        self.log.append(msg)


# --------------------------------------------------------------------------- #
# SC-002 — non-interactive resolution by hardness (no input(), no confirm())   #
# --------------------------------------------------------------------------- #
def test_hard_gate_non_interactive_safe_skips():
    io = _ConfirmRaisesIO()
    step = {"id": "g", "kind": "gate", "message": "m", "hardness": "hard",
            "allow_flag": "allow-install"}
    # no flags active → SAFE-skip (False)
    assert run_gate_step(step, "mod", io, non_interactive=True) is False


def test_hard_gate_non_interactive_proceeds_with_allow_flag():
    io = _ConfirmRaisesIO()
    step = {"id": "g", "kind": "gate", "message": "m", "hardness": "hard",
            "allow_flag": "allow-install"}
    assert run_gate_step(
        step, "mod", io, non_interactive=True,
        active_flags=frozenset({"allow-install"}),
    ) is True


def test_soft_gate_non_interactive_proceeds():
    io = _ConfirmRaisesIO()
    step = {"id": "g", "kind": "gate", "message": "m", "hardness": "soft",
            "skip_flag": "no-external-generators"}
    assert run_gate_step(step, "mod", io, non_interactive=True) is True


def test_soft_gate_non_interactive_skips_with_skip_flag():
    io = _ConfirmRaisesIO()
    step = {"id": "g", "kind": "gate", "message": "m", "hardness": "soft",
            "skip_flag": "no-external-generators"}
    assert run_gate_step(
        step, "mod", io, non_interactive=True,
        active_flags=frozenset({"no-external-generators"}),
    ) is False


def test_informational_gate_proceeds_without_prompt():
    # informational never prompts, in CI or TTY.
    io = _ConfirmRaisesIO()
    step = {"id": "g", "kind": "gate", "message": "m", "hardness": "informational"}
    assert run_gate_step(step, "mod", io, non_interactive=True) is True
    assert run_gate_step(step, "mod", io, non_interactive=False) is True


def test_default_hardness_is_hard_safe_skip():
    # A pre-004 gate dict (no hardness key) behaves exactly as the old SAFE-skip.
    io = _ConfirmRaisesIO()
    step = {"id": "g", "kind": "gate", "message": "m"}
    assert run_gate_step(step, "mod", io, non_interactive=True) is False


# --------------------------------------------------------------------------- #
# TTY resolution: hard [y/N], soft [Y/n], flag pre-resolution                  #
# --------------------------------------------------------------------------- #
def test_hard_gate_tty_delegates_to_confirm_default_no():
    io = _RecordingIO(result=False)
    step = {"id": "g", "kind": "gate", "message": "m", "hardness": "hard"}
    assert run_gate_step(step, "mod", io, non_interactive=False) is False
    assert io.confirms and io.confirms[0]["default_yes"] is False


def test_soft_gate_tty_delegates_to_confirm_default_yes():
    io = _RecordingIO(result=True)
    step = {"id": "g", "kind": "gate", "message": "m", "hardness": "soft"}
    assert run_gate_step(step, "mod", io, non_interactive=False) is True
    assert io.confirms and io.confirms[0]["default_yes"] is True


def test_allow_flag_preresolves_tty_without_prompt():
    # A standing --allow-* flag in a TTY pre-resolves a hard gate (no confirm call).
    io = _ConfirmRaisesIO()
    step = {"id": "g", "kind": "gate", "message": "m", "hardness": "hard",
            "allow_flag": "allow-public-repo"}
    assert run_gate_step(
        step, "mod", io, non_interactive=False,
        active_flags=frozenset({"allow-public-repo"}),
    ) is True


# --------------------------------------------------------------------------- #
# init_only — auto-proceed on plain reproduce (not a skip)                     #
# --------------------------------------------------------------------------- #
def test_init_only_bypass_auto_proceeds_not_skip():
    # init_only_bypass=True → proceed (True) WITHOUT prompting; this is distinct
    # from a hard gate's SAFE-skip (False). The frozen decision replays.
    io = _ConfirmRaisesIO()
    step = {"id": "pins", "kind": "gate", "message": "m", "hardness": "hard",
            "init_only": True}
    assert run_gate_step(
        step, "mod", io, non_interactive=False, init_only_bypass=True,
    ) is True


# --------------------------------------------------------------------------- #
# SC-001 — parse + validate + serialize round-trip                            #
# --------------------------------------------------------------------------- #
_MANIFEST_TMPL = """\
[meta]
repository = "github.com/test/test"
author = "Test"

[module]
id = "m"
name = "M"
version = "1.0.0"
description = "d"
reconcile = false

[[inputs]]
key = "public"
type = "bool"
prompt = "Public?"

{steps}
"""


def _write_manifest(tmp_path: Path, steps_toml: str) -> Path:
    p = tmp_path / "module.toml"
    p.write_text(_MANIFEST_TMPL.format(steps=steps_toml), encoding="utf-8")
    return p


def test_parse_gate_enrichment_fields(tmp_path):
    steps = (
        '[[steps]]\n'
        'id = "pins"\n'
        'kind = "gate"\n'
        'message = "review"\n'
        'hardness = "hard"\n'
        'allow_flag = "allow-stack-write"\n'
        'init_only = true\n'
    )
    m = parse_manifest(_write_manifest(tmp_path, steps))
    assert not m.errors, [e.to_dict() for e in m.errors]
    step = m.steps[0]
    assert step.hardness == "hard"
    assert step.allow_flag == "allow-stack-write"
    assert step.init_only is True


def test_unknown_hardness_rejected(tmp_path):
    steps = (
        '[[steps]]\n'
        'id = "g"\n'
        'kind = "gate"\n'
        'message = "m"\n'
        'hardness = "kinda-hard"\n'
    )
    m = parse_manifest(_write_manifest(tmp_path, steps))
    assert any(e.error_code == ErrorCode.MANIFEST_MALFORMED for e in m.errors)


def test_when_typo_key_rejected(tmp_path):
    # `publik` is not a declared input → authoring error (OQ-2).
    steps = (
        '[[steps]]\n'
        'id = "g"\n'
        'kind = "gate"\n'
        'message = "m"\n'
        'when = "publik == true"\n'
    )
    m = parse_manifest(_write_manifest(tmp_path, steps))
    assert any(e.error_code == ErrorCode.MANIFEST_MALFORMED for e in m.errors)


def test_when_valid_key_accepted(tmp_path):
    steps = (
        '[[steps]]\n'
        'id = "g"\n'
        'kind = "gate"\n'
        'message = "m"\n'
        'when = "public == true"\n'
    )
    m = parse_manifest(_write_manifest(tmp_path, steps))
    assert not m.errors, [e.to_dict() for e in m.errors]
    assert m.steps[0].when == "public == true"


# --------------------------------------------------------------------------- #
# when drops the gate at build time (deterministic across modes)              #
# --------------------------------------------------------------------------- #
def _build(manifest_obj, answers, mode):
    return plan_mod.build_plan(
        [manifest_obj],
        resolved_answers={"m": answers},
        ordered_ids=["m"],
        mode=mode,
        plugin_root_path=Path("/tmp"),
    )


def _gate_ids(plan, mod="m"):
    return [s["id"] for s in plan.modules[mod].steps if s.get("kind") == "gate"]


def test_when_true_keeps_gate(tmp_path):
    steps = (
        '[[steps]]\n'
        'id = "g"\n'
        'kind = "gate"\n'
        'message = "m"\n'
        'when = "public == true"\n'
    )
    m = parse_manifest(_write_manifest(tmp_path, steps))
    m._toml_path = tmp_path / "module.toml"
    plan = _build(m, {"public": True}, "init")
    assert _gate_ids(plan) == ["g"]


def test_when_false_drops_gate_both_modes(tmp_path):
    steps = (
        '[[steps]]\n'
        'id = "g"\n'
        'kind = "gate"\n'
        'message = "m"\n'
        'when = "public == true"\n'
    )
    m = parse_manifest(_write_manifest(tmp_path, steps))
    m._toml_path = tmp_path / "module.toml"
    for mode in ("init", "reproduce"):
        plan = _build(m, {"public": False}, mode)
        assert _gate_ids(plan) == [], f"gate should be dropped in {mode}"


def test_enrichment_serialized_into_frozen_plan(tmp_path):
    steps = (
        '[[steps]]\n'
        'id = "pins"\n'
        'kind = "gate"\n'
        'message = "review"\n'
        'hardness = "soft"\n'
        'skip_flag = "no-external-generators"\n'
        'init_only = true\n'
    )
    m = parse_manifest(_write_manifest(tmp_path, steps))
    m._toml_path = tmp_path / "module.toml"
    plan = _build(m, {}, "init")
    step = plan.modules["m"].steps[0]
    assert step["hardness"] == "soft"
    assert step["skip_flag"] == "no-external-generators"
    assert step["init_only"] is True
