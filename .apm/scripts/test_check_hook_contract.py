"""Coverage for check-hook-contract.py.

The check this replaced, check-hook-wiring.py, was deleted for passing silently: it
required a file that exists only in a chezmoi checkout and printed success when
handed nothing, so it read as coverage for months while enforcing nothing.

These tests exist to stop that recurring. Each one builds a deliberately broken
package tree and asserts the check REJECTS it, and the negative cases assert it does
not fire on the shapes that are legitimately fine. A validator nobody has watched
fail is indistinguishable from a validator that cannot.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

CHECK = Path(__file__).resolve().parent / "check-hook-contract.py"

SPEC = importlib.util.spec_from_file_location("check_hook_contract", CHECK)
assert SPEC is not None and SPEC.loader is not None
contract = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = contract
SPEC.loader.exec_module(contract)


def build_package(
    root: Path,
    name: str,
    *,
    matcher: str = "Bash",
    script: str = "#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n",
    script_name: str = "guard.py",
    target: str = "all",
    with_tests: bool = True,
    event: str = "PreToolUse",
) -> Path:
    package = root / "packages" / name
    (package / "scripts").mkdir(parents=True)
    (package / "hooks").mkdir(parents=True)

    (package / "scripts" / script_name).write_text(script)
    entry: dict = {
        "hooks": {
            event: [
                {
                    "hooks": [
                        {"type": "command", "command": f"${{PLUGIN_ROOT}}/scripts/{script_name}"}
                    ]
                }
            ]
        }
    }
    if matcher is not None:
        entry["hooks"][event][0]["matcher"] = matcher
    (package / "hooks" / "hooks.json").write_text(json.dumps(entry, indent=2))
    (package / "apm.yml").write_text(f"name: {name}\nversion: 1.0.0\ntarget: {target}\n")

    if with_tests:
        (package / "tests").mkdir()
        (package / "tests" / "test_guard.py").write_text("def test_placeholder():\n    pass\n")
    return package


def run_check(root: Path) -> tuple[int, str]:
    """Run the check against a synthetic repository root."""
    body = CHECK.read_text().replace(
        'ROOT = Path(__file__).resolve().parents[2]', f'ROOT = Path({str(root)!r})'
    )
    stand_in = root / "check.py"
    stand_in.write_text(body)
    result = subprocess.run(
        [sys.executable, str(stand_in)], capture_output=True, text=True, timeout=60
    )
    return result.returncode, result.stdout + result.stderr


# --- rule 1: a matcher must route every tool the script branches on ------------


@pytest.mark.parametrize(
    "script",
    [
        pytest.param(
            'import sys\nif tool_name == "apply_patch":\n    sys.exit(0)\n',
            id="python-equality",
        ),
        pytest.param(
            'import sys\nif tool_name in ("apply_patch", "Write"):\n    sys.exit(0)\n',
            id="python-tuple-membership",
        ),
        pytest.param(
            'case "$tool_name" in\n  apply_patch|functions.apply_patch)\n    :;;\nesac\n',
            id="shell-case",
        ),
    ],
)
def test_an_unrouted_branch_is_rejected(tmp_path: Path, script: str) -> None:
    build_package(tmp_path, "hooks-example", matcher="Edit|Write", script=script)

    code, output = run_check(tmp_path)

    assert code == 1, "a branch no matcher routes must fail the check"
    assert "matcher-coverage" in output
    assert "apply_patch" in output


def test_a_routed_branch_passes(tmp_path: Path) -> None:
    build_package(
        tmp_path,
        "hooks-example",
        matcher="apply_patch|Edit|Write",
        script='import sys\nif tool_name == "apply_patch":\n    sys.exit(0)\n',
    )

    code, output = run_check(tmp_path)

    assert code == 0, output


def test_an_empty_matcher_routes_everything(tmp_path: Path) -> None:
    """An empty matcher binds every tool, so no branch can be unreachable."""
    build_package(
        tmp_path,
        "hooks-example",
        matcher="",
        script='import sys\nif tool_name == "apply_patch":\n    sys.exit(0)\n',
    )

    code, output = run_check(tmp_path)

    assert code == 0, output


def test_prose_mentioning_a_tool_is_not_a_branch(tmp_path: Path) -> None:
    """Every guard here discusses tool names in its header comment.

    A substring check would flag all of them and be muted within a week, so only a
    comparison or a case arm counts.
    """
    build_package(
        tmp_path,
        "hooks-example",
        matcher="Bash",
        script=(
            "# This guard does not handle apply_patch, Edit, or Write; see the\n"
            "# contract for why apply_patch is Codex's alias for those.\n"
            "import sys\nsys.exit(0)\n"
        ),
    )

    code, output = run_check(tmp_path)

    assert code == 0, output


def test_one_manifest_cannot_mask_a_gap_in_another(tmp_path: Path) -> None:
    """Native and APM manifests are separate deploy targets and drift apart.

    Judging the union of their matchers let `.apm/hooks/hooks.json` hide the removal
    of `apply_patch` from `hooks/hooks.json`.
    """
    package = build_package(
        tmp_path,
        "hooks-example",
        matcher="Edit|Write",
        script='import sys\nif tool_name == "apply_patch":\n    sys.exit(0)\n',
    )
    # A second manifest that DOES bind the tool must not excuse the first.
    apm = package / ".apm" / "hooks"
    apm.mkdir(parents=True)
    (apm / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "apply_patch|Edit|Write",
                            "hooks": [
                                {"type": "command", "command": "${PLUGIN_ROOT}/scripts/guard.py"}
                            ],
                        }
                    ]
                }
            }
        )
    )

    code, output = run_check(tmp_path)

    assert code == 1, "the manifest missing the binding must still be reported"
    assert "hooks/hooks.json" in output


def test_a_codex_only_tool_is_not_required_in_a_claude_manifest(tmp_path: Path) -> None:
    """`apply_patch` is Codex's tool, so a claude-hooks.json is right to omit it.

    `speckit-beads` splits this way deliberately, and an earlier revision of this
    check reported it as a defect.
    """
    package = build_package(
        tmp_path,
        "hooks-example",
        script=(
            'import sys\nif tool_name in ("apply_patch", "Edit"):\n    sys.exit(0)\n'
        ),
        with_tests=True,
    )
    (package / "hooks" / "hooks.json").unlink()
    for audience, matcher in (
        ("claude", "Edit|Write|MultiEdit"),
        ("codex", "apply_patch|Edit|Write|MultiEdit"),
    ):
        (package / "hooks" / f"{audience}-hooks.json").write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": matcher,
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "${PLUGIN_ROOT}/scripts/guard.py",
                                    }
                                ],
                            }
                        ]
                    }
                }
            )
        )

    code, output = run_check(tmp_path)

    assert code == 0, output


# --- rule 2: output fields must suit the declared target ----------------------


def test_a_claude_only_field_under_target_all_is_rejected(tmp_path: Path) -> None:
    build_package(
        tmp_path,
        "hooks-example",
        target="all",
        script='import json\nprint(json.dumps({"systemMessage": "hi"}))\n',
    )

    code, output = run_check(tmp_path)

    assert code == 1, "systemMessage under target: all is a silent no-op on Codex"
    assert "cross-tool-output" in output


def test_a_claude_only_field_under_target_claude_passes(tmp_path: Path) -> None:
    build_package(
        tmp_path,
        "hooks-example",
        target="claude",
        script='import json\nprint(json.dumps({"systemMessage": "hi"}))\n',
    )

    code, output = run_check(tmp_path)

    assert code == 0, output


@pytest.mark.parametrize(
    "script",
    [
        pytest.param(
            'import json\nprint(json.dumps({"permissionDecision": "ask"}))\n',
            id="python-dict",
        ),
        pytest.param(
            'jq -cn \'{hookSpecificOutput:{permissionDecision:"ask"}}\'\n',
            id="shell-jq-literal",
        ),
    ],
)
def test_emitting_ask_is_rejected(tmp_path: Path, script: str) -> None:
    """Constitution III forbids `ask`, and nothing enforced it before this check."""
    build_package(tmp_path, "hooks-example", script=script)

    code, output = run_check(tmp_path)

    assert code == 1
    assert "no-ask" in output


def test_documenting_the_ask_ban_is_not_emitting_it(tmp_path: Path) -> None:
    """Several guards explain the ban in a comment; none may be flagged for it."""
    build_package(
        tmp_path,
        "hooks-example",
        script=(
            '# Never emits permissionDecision "ask": per constitution III it waits\n'
            "# for a human and stalls an autonomous run.\n"
            "import sys\nsys.exit(0)\n"
        ),
    )

    code, output = run_check(tmp_path)

    assert code == 0, output


# --- rule 3: a hook script needs a suite --------------------------------------


def test_a_hook_script_without_tests_is_rejected(tmp_path: Path) -> None:
    build_package(tmp_path, "hooks-example", with_tests=False)

    code, output = run_check(tmp_path)

    assert code == 1
    assert "test-coverage" in output


def test_a_suite_outside_the_tests_directory_counts(tmp_path: Path) -> None:
    """`orchestrate` keeps `scripts/rules-eval-test.py` beside the code it covers."""
    package = build_package(tmp_path, "hooks-example", with_tests=False)
    (package / "scripts" / "guard-test.py").write_text("assert True\n")

    code, output = run_check(tmp_path)

    assert code == 0, output


def test_a_stale_allowlist_entry_is_rejected(tmp_path: Path) -> None:
    """An entry that no longer describes a gap silently exempts a real package."""
    build_package(tmp_path, "beads", with_tests=True)

    code, output = run_check(tmp_path)

    assert code == 1, "beads is allowlisted but now has a suite"
    assert "stale-allowlist" in output


# --- the failure mode that killed the predecessor -----------------------------


def test_inspecting_nothing_is_a_failure(tmp_path: Path) -> None:
    """Reporting success while inspecting nothing is what made the old check useless."""
    (tmp_path / "packages").mkdir()

    code, output = run_check(tmp_path)

    assert code == 1
    assert "inspected no hook packages" in output


def test_a_package_without_hooks_is_ignored(tmp_path: Path) -> None:
    """Only hook-bearing packages are in scope; a skill-only package is not."""
    build_package(tmp_path, "hooks-example")
    plain = tmp_path / "packages" / "some-skill"
    plain.mkdir(parents=True)
    (plain / "apm.yml").write_text("name: some-skill\nversion: 1.0.0\ntarget: all\n")

    code, output = run_check(tmp_path)

    assert code == 0, output
    assert "1 hook package(s)" in output
