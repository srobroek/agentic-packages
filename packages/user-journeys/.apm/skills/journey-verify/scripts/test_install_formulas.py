"""Tests for journey formula installation and workflow structure."""

import importlib.util
import sys
import tomllib
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "install_formulas", HERE / "install_formulas.py"
)
assert spec is not None and spec.loader is not None
install_formulas = importlib.util.module_from_spec(spec)
sys.modules["install_formulas"] = install_formulas
spec.loader.exec_module(install_formulas)


def load_formula(name: str) -> dict:
    path = install_formulas.FORMULAS_DIR / f"{name}.formula.toml"
    with path.open("rb") as formula_file:
        return tomllib.load(formula_file)


def steps_by_id(formula: dict) -> dict[str, dict]:
    return {step["id"]: step for step in formula["steps"]}


def test_installs_both_formulas_and_is_idempotent(tmp_path):
    (tmp_path / ".beads").mkdir()

    assert install_formulas.install_formulas(tmp_path) == (2, 0)
    assert install_formulas.install_formulas(tmp_path) == (0, 2)
    installed = sorted(
        path.name for path in (tmp_path / ".beads" / "formulas").iterdir()
    )
    assert installed == [
        "journey-step-agentic-verification.formula.toml",
        "journey-step-human-verification.formula.toml",
    ]


def test_refuses_non_beads_workspace(tmp_path):
    with pytest.raises(RuntimeError, match="not a Beads workspace"):
        install_formulas.install_formulas(tmp_path)


def test_refuses_divergent_copy_without_partial_install(tmp_path):
    destination = tmp_path / ".beads" / "formulas"
    destination.mkdir(parents=True)
    conflict = destination / "journey-step-human-verification.formula.toml"
    conflict.write_text("local formula\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        install_formulas.install_formulas(tmp_path)

    assert conflict.read_text(encoding="utf-8") == "local formula\n"
    assert not (destination / "journey-step-agentic-verification.formula.toml").exists()


def test_force_replaces_divergent_copy(tmp_path):
    destination = tmp_path / ".beads" / "formulas"
    destination.mkdir(parents=True)
    conflict = destination / "journey-step-human-verification.formula.toml"
    conflict.write_text("local formula\n", encoding="utf-8")

    assert install_formulas.install_formulas(tmp_path, force=True) == (2, 0)
    assert (
        conflict.read_bytes()
        == (install_formulas.FORMULAS_DIR / conflict.name).read_bytes()
    )


def test_force_refuses_symlink_destination(tmp_path):
    destination = tmp_path / ".beads" / "formulas"
    destination.mkdir(parents=True)
    outside = tmp_path / "outside.toml"
    outside.write_text("outside\n", encoding="utf-8")
    (destination / "journey-step-human-verification.formula.toml").symlink_to(outside)

    with pytest.raises(RuntimeError, match="unsafe formula destinations"):
        install_formulas.install_formulas(tmp_path, force=True)

    assert outside.read_text(encoding="utf-8") == "outside\n"


def test_agentic_formula_fans_in_without_a_human_gate():
    formula = load_formula("journey-step-agentic-verification")
    steps = steps_by_id(formula)

    assert formula["vars"]["profile"]["default"] == "default"
    assert steps["triage"]["needs"] == [
        "drive-step",
        "inspect-definition",
        "inspect-acceptance",
    ]
    assert steps["record"]["needs"] == ["triage"]
    assert all("gate" not in step for step in formula["steps"])


def test_human_formula_gates_after_fan_in_and_before_record():
    formula = load_formula("journey-step-human-verification")
    steps = steps_by_id(formula)

    assert steps["triage"]["needs"] == [
        "drive-step",
        "inspect-definition",
        "inspect-acceptance",
    ]
    assert steps["human-review"]["needs"] == ["triage"]
    assert steps["human-review"]["gate"] == {"type": "human"}
    assert steps["record"]["needs"] == ["human-review"]


def test_formulas_are_service_agnostic():
    for name in (
        "journey-step-agentic-verification",
        "journey-step-human-verification",
    ):
        formula = load_formula(name)
        text = str(formula).lower()
        assert "tauri" not in text
        assert "windows" not in text
        assert "desktop" not in text
