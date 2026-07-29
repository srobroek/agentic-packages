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
DETECT = (
    Path(__file__).resolve().parent.parent
    / ".apm"
    / "skills"
    / "release-please"
    / "scripts"
    / "detect-release-please.sh"
)


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)


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


def test_detect_script_still_parses_under_bin_bash() -> None:
    # detect-release-please.sh stays a shell script -- out of this port's scope --
    # but the guard depends on it, so its own bats parse-check is preserved here.
    result = subprocess.run(["/bin/bash", "-n", str(DETECT)], capture_output=True)
    assert result.returncode == 0


def test_detect_reports_present_on_a_release_please_repo(rp_dir: Path) -> None:
    result = subprocess.run(
        ["/bin/bash", str(DETECT), str(rp_dir)], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "present=true" in result.stdout


def test_detect_reports_absent_on_a_plain_repo(plain_dir: Path) -> None:
    result = subprocess.run(
        ["/bin/bash", str(DETECT), str(plain_dir)], capture_output=True, text=True
    )
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
