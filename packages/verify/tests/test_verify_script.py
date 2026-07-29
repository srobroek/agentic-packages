"""Coverage for verify.sh package-script detection.

The regression under test: `has_script` chained `command -v jq && jq ...`, so with
jq absent it answered false for every script name and the whole package.json
branch was skipped -- a repo with a working `verify` script exited 1 reporting
"No supported verification workflow detected".
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / ".apm/skills/verify/scripts/verify.sh"
)

# Executables verify.sh and its fallbacks need, minus the JSON parser under test.
_NEEDED = (
    "bash",
    "sh",
    "npm",
    "node",
    "python3",
    "env",
    "uname",
    "dirname",
    "basename",
    "sed",
    "grep",
    "jq",
)


def _sandbox_path(tmp_path: Path, *, omit: tuple[str, ...]) -> str:
    """A PATH holding only the tools verify.sh needs, with `omit` removed.

    npm and node are added by their real directory rather than symlinked: npm
    resolves its own libraries relative to argv[0], so a symlink breaks it.
    """
    bindir = tmp_path / str(abs(hash(omit)))
    bindir.mkdir(parents=True, exist_ok=True)
    extra: list[str] = []
    for name in _NEEDED:
        if name in omit:
            continue
        found = shutil.which(name)
        if not found:
            continue
        if name in ("npm", "node"):
            # NOT resolve(): npm finds its own libraries relative to argv[0], and on
            # a runner where /usr/local/bin/npm is a symlink into a versioned
            # directory, resolving it yields a parent with no node_modules -- npm
            # then dies with "Cannot find module .../npm-prefix.js". Keep the
            # unresolved directory, which is how a normal PATH presents it.
            extra.append(str(Path(found).parent))
        else:
            link = bindir / name
            if not link.exists():
                link.symlink_to(found)
    dirs = [str(bindir), *dict.fromkeys(extra)]
    for name in omit:
        for candidate in dirs[1:]:
            if (Path(candidate) / name).exists():
                pytest.skip(f"cannot hide {name}: it lives beside npm/node in {candidate}")
    return os.pathsep.join(dirs)


def _run(project: Path, path: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PATH=path)
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "package.json").write_text(
        json.dumps({"name": "x", "version": "1.0.0", "scripts": {"verify": "exit 0"}})
    )
    return root


@pytest.mark.skipif(shutil.which("npm") is None, reason="npm is required")
@pytest.mark.parametrize("omit", [(), ("jq",), ("jq", "node"), ("jq", "python3")])
def test_verify_script_runs_without_jq(project: Path, tmp_path: Path, omit) -> None:
    result = _run(project, _sandbox_path(tmp_path, omit=omit))
    assert "No supported verification workflow detected" not in result.stderr, result.stderr
    assert "ran: 1" in result.stdout, result.stdout
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which("npm") is None, reason="npm is required")
def test_no_json_parser_skips_rather_than_reporting_nothing(
    project: Path, tmp_path: Path
) -> None:
    path = _sandbox_path(tmp_path, omit=("jq", "node", "python3"))
    result = _run(project, path)
    assert "no JSON parser" in result.stdout, result.stdout
    assert "skipped: 1" in result.stdout, result.stdout
