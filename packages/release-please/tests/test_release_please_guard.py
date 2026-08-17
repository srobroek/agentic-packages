"""Coverage for release-please-guard.py -- a non-blocking PreToolUse hook that
warns when, on a release-please-managed repo, the agent tries to cut a release
or tag manually, push tags, or hand-merge a release branch to a protected
branch. Tests assert the warn/allow decision (presence/absence of
additionalContext), and that it stays silent off release-please repos.

Ported from release-please-guard.bats; every bats case has a matching test here.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parent.parent / "scripts" / "release-please-guard.py"


def run_detect(*args: str) -> subprocess.CompletedProcess:
    """The folded `detect` subcommand, invoked as the skill's step-0 gate does."""
    return subprocess.run(
        [sys.executable, str(GUARD), "detect", *args],
        capture_output=True,
        text=True,
    )


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    # Repo-local, so every later commit in the fixture picks it up. A global
    # commit.gpgsign otherwise fails all of these with "1Password: Could not
    # connect to socket" whenever that agent is not running, and a throwaway
    # fixture commit has nothing to sign for.
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)
    subprocess.run(["git", "config", "tag.gpgsign", "false"], cwd=path, check=True)


@pytest.fixture
def rp_dir(tmp_path: Path) -> Path:
    """A throwaway repo that LOOKS release-please-managed (config + manifest)."""
    repo = tmp_path / "rp"
    repo.mkdir()
    (repo / "release-please-config.json").write_text('{"packages":{".":{}}}\n')
    (repo / ".release-please-manifest.json").write_text('{".":"1.0.0"}\n')
    _init_repo(repo)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, check=True)
    return repo


@pytest.fixture
def plain_dir(tmp_path: Path) -> Path:
    """A throwaway repo with NO release-please config."""
    repo = tmp_path / "plain"
    repo.mkdir()
    _init_repo(repo)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo, check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, check=True)
    return repo


def run_guard(command: str | None, cwd: Path | None, *, as_string: bool = False) -> tuple[int, str]:
    if command is None:
        payload = ""
    else:
        tool_input = command if as_string else {"command": command}
        payload = json.dumps({"tool_input": tool_input, "cwd": str(cwd) if cwd else None})
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode, result.stdout.strip()


def context(output: str) -> str:
    if not output:
        return ""
    return json.loads(output).get("hookSpecificOutput", {}).get("additionalContext", "")


def test_parses() -> None:
    subprocess.run([sys.executable, "-c", f"compile(open({str(GUARD)!r}).read(), 'g', 'exec')"], check=True)


def test_detect_reports_present_on_a_release_please_repo(rp_dir: Path) -> None:
    result = run_detect(str(rp_dir))
    assert result.returncode == 0
    assert "present=true" in result.stdout


def test_detect_reports_absent_on_a_plain_repo(plain_dir: Path) -> None:
    result = run_detect(str(plain_dir))
    assert result.returncode == 1
    assert "present=false" in result.stdout


def test_gh_release_create_on_rp_repo_warns(rp_dir: Path) -> None:
    code, output = run_guard("gh release create v9.9.9", rp_dir)
    assert code == 0
    ctx = context(output)
    assert ctx
    assert "release-please" in ctx


def test_git_tag_vxyz_on_rp_repo_warns(rp_dir: Path) -> None:
    code, output = run_guard("git tag -a v1.2.3 -m release", rp_dir)
    assert code == 0
    assert context(output)


def test_git_tag_from_a_nested_directory_still_warns(rp_dir: Path) -> None:
    nested = rp_dir / "packages" / "component"
    nested.mkdir(parents=True)
    code, output = run_guard("git tag v1.2.3", nested)
    assert code == 0
    assert context(output)


def test_git_push_tags_on_rp_repo_warns(rp_dir: Path) -> None:
    code, output = run_guard("git push origin --tags", rp_dir)
    assert code == 0
    assert context(output)


def test_git_push_follow_tags_on_rp_repo_warns(rp_dir: Path) -> None:
    code, output = run_guard("git push --follow-tags", rp_dir)
    assert code == 0
    assert context(output)


def test_string_form_tool_input_still_warns(rp_dir: Path) -> None:
    code, output = run_guard("gh release create v2.0.0", rp_dir, as_string=True)
    assert code == 0
    assert context(output)


def test_benign_command_on_rp_repo_is_silent(rp_dir: Path) -> None:
    code, output = run_guard("npm run build", rp_dir)
    assert code == 0
    assert not context(output)


def test_gh_release_create_on_non_rp_repo_is_silent(plain_dir: Path) -> None:
    code, output = run_guard("gh release create v1.0.0", plain_dir)
    assert code == 0
    assert not context(output)


def test_gh_release_view_read_only_is_silent(rp_dir: Path) -> None:
    code, output = run_guard("gh release view v1.0.0", rp_dir)
    assert code == 0
    assert not context(output)


def test_git_tag_list_no_version_is_silent(rp_dir: Path) -> None:
    code, output = run_guard("git tag -l", rp_dir)
    assert code == 0
    assert not context(output)


def test_empty_payload_is_silent(rp_dir: Path) -> None:
    code, output = run_guard(None, rp_dir)
    assert code == 0
    assert not output


def test_git_merge_while_on_main_of_rp_repo_warns(rp_dir: Path) -> None:
    subprocess.run(["git", "checkout", "-qb", "feat"], cwd=rp_dir, check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "x"], cwd=rp_dir, check=True)
    subprocess.run(["git", "checkout", "-qq", "main"], cwd=rp_dir, check=True)

    code, output = run_guard("git merge feat", rp_dir)
    assert code == 0
    ctx = context(output)
    assert ctx
    assert "release PR" in ctx


def test_git_merge_abort_is_silent(rp_dir: Path) -> None:
    code, output = run_guard("git merge --abort", rp_dir)
    assert code == 0
    assert not context(output)


# --- detect: config facts ---------------------------------------------------
#
# The detector was a separate shell script parsing its own JSON with `grep -E`.
# These cases pin the three defects that parsing carried.


def test_detect_json_is_valid_json(rp_dir: Path) -> None:
    """DEFECT: `grep -Ec` printed its own `0` AND the `|| printf '0'` fallback
    fired, so an empty manifest emitted `"package_count":0\\n0` -- unparsable.
    """
    (rp_dir / ".release-please-manifest.json").write_text("{}")
    result = run_detect("--json", str(rp_dir))
    assert json.loads(result.stdout)["package_count"] == 0


def test_detect_counts_keys_not_lines_in_a_minified_manifest(rp_dir: Path) -> None:
    """DEFECT: `grep -Ec '"[^"]+"[[:space:]]*:'` counted LINES holding a key, so
    a minified three-package manifest reported 1.
    """
    (rp_dir / ".release-please-manifest.json").write_text(
        '{"a":"1.0.0","b":"2.0.0","c":"3.0.0"}'
    )
    result = run_detect("--json", str(rp_dir))
    assert json.loads(result.stdout)["package_count"] == 3


def test_detect_counts_a_pretty_printed_manifest(rp_dir: Path) -> None:
    (rp_dir / ".release-please-manifest.json").write_text(
        json.dumps({"a": "1.0.0", "b": "2.0.0"}, indent=2)
    )
    result = run_detect("--json", str(rp_dir))
    assert json.loads(result.stdout)["package_count"] == 2


def test_detect_ignores_a_per_package_flag_override(rp_dir: Path) -> None:
    """DEFECT: the flag pattern matched ANYWHERE in the file, so a per-package
    `separate-pull-requests` reported itself as the top-level value.
    """
    (rp_dir / "release-please-config.json").write_text(
        json.dumps(
            {
                "separate-pull-requests": False,
                "packages": {"pkg-a": {"separate-pull-requests": True}},
            }
        )
    )
    result = run_detect("--json", str(rp_dir))
    assert json.loads(result.stdout)["separate_pull_requests"] == "false"


def test_detect_reports_unknown_for_an_unset_flag(rp_dir: Path) -> None:
    result = run_detect("--json", str(rp_dir))
    facts = json.loads(result.stdout)
    assert facts["separate_pull_requests"] == "unknown"
    assert facts["include_component_in_tag"] == "unknown"
    assert facts["tag_separator"] == "unknown"


def test_detect_reports_top_level_flags_and_separator(rp_dir: Path) -> None:
    (rp_dir / "release-please-config.json").write_text(
        json.dumps(
            {
                "separate-pull-requests": True,
                "include-component-in-tag": False,
                "tag-separator": "--",
                "packages": {".": {}},
            }
        )
    )
    facts = json.loads(run_detect("--json", str(rp_dir)).stdout)
    assert facts["separate_pull_requests"] == "true"
    assert facts["include_component_in_tag"] == "false"
    assert facts["tag_separator"] == "--"


def test_detect_on_malformed_config_reports_unknown_rather_than_crashing(
    rp_dir: Path,
) -> None:
    (rp_dir / "release-please-config.json").write_text("{not json")
    result = run_detect("--json", str(rp_dir))
    assert result.returncode == 0
    facts = json.loads(result.stdout)
    # The file EXISTS, so the repo is still managed; only its values are unknown.
    assert facts["present"] is True
    assert facts["separate_pull_requests"] == "unknown"


# --- detect: mode classification --------------------------------------------


def test_detect_mode_manifest(rp_dir: Path) -> None:
    assert json.loads(run_detect("--json", str(rp_dir)).stdout)["mode"] == "manifest"


def test_detect_mode_config_only(rp_dir: Path) -> None:
    (rp_dir / ".release-please-manifest.json").unlink()
    facts = json.loads(run_detect("--json", str(rp_dir)).stdout)
    assert facts["mode"] == "config-only"
    assert facts["package_count"] == 0


def test_detect_mode_inline_action_from_a_workflow(plain_dir: Path) -> None:
    workflows = plain_dir / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "release.yml").write_text(
        "jobs:\n  r:\n    steps:\n      - uses: googleapis/release-please-action@v4\n"
    )
    facts = json.loads(run_detect("--json", str(plain_dir)).stdout)
    assert facts["mode"] == "inline-action"
    assert facts["present"] is True
    assert facts["workflow_files"] == ".github/workflows/release.yml"


def test_detect_mode_none_on_a_plain_repo(plain_dir: Path) -> None:
    facts = json.loads(run_detect("--json", str(plain_dir)).stdout)
    assert facts["mode"] == "none"
    assert facts["present"] is False


def test_detect_ignores_a_workflow_without_the_action(plain_dir: Path) -> None:
    workflows = plain_dir / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("jobs:\n  b:\n    steps:\n      - run: true\n")
    facts = json.loads(run_detect("--json", str(plain_dir)).stdout)
    assert facts["workflow_files"] == ""
    assert facts["present"] is False


def test_detect_accepts_the_legacy_config_name(plain_dir: Path) -> None:
    (plain_dir / ".release-please-config.json").write_text('{"packages":{".":{}}}')
    facts = json.loads(run_detect("--json", str(plain_dir)).stdout)
    assert facts["present"] is True
    assert facts["config_file"].endswith(".release-please-config.json")


# --- detect: CLI contract ---------------------------------------------------


def test_detect_default_output_is_key_value_lines(rp_dir: Path) -> None:
    result = run_detect(str(rp_dir))
    keys = [line.split("=", 1)[0] for line in result.stdout.splitlines()]
    assert keys == [
        "present",
        "mode",
        "config_file",
        "manifest_file",
        "workflow_files",
        "separate_pull_requests",
        "include_component_in_tag",
        "tag_separator",
        "package_count",
    ]


def test_detect_rejects_an_unknown_option(rp_dir: Path) -> None:
    assert run_detect("--bogus", str(rp_dir)).returncode == 2


def test_detect_rejects_a_second_directory(rp_dir: Path) -> None:
    assert run_detect(str(rp_dir), str(rp_dir)).returncode == 2


def test_detect_rejects_a_missing_directory(tmp_path: Path) -> None:
    assert run_detect(str(tmp_path / "nope")).returncode == 2


def test_unknown_subcommand_exits_two() -> None:
    result = subprocess.run(
        [sys.executable, str(GUARD), "bogus"], capture_output=True, text=True
    )
    assert result.returncode == 2
