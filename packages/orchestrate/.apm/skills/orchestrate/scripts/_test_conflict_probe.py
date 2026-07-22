#!/usr/bin/env python3
"""Adversarial self-tests for conflict-probe.sh."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = HERE / "conflict-probe.sh"


def run(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None):
    return subprocess.run(
        [str(PROBE), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


class ConflictProbeTest(unittest.TestCase):
    def test_unknown_merge_tree_error_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_git = fake_bin / "git"
            fake_git.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ $1 == rev-parse ]]; then printf '%040d\\n' 1; exit 0; fi\n"
                "if [[ $1 == merge-tree ]]; then exit 128; fi\n"
                "exit 99\n",
                encoding="utf-8",
            )
            fake_git.chmod(fake_git.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:{env['PATH']}"

            result = run("conflicts", "main", "topic", env=env)

        self.assertEqual(result.returncode, 2)
        self.assertIn("could not classify", result.stderr)
        self.assertNotIn("clean", result.stdout)

    def test_bad_ref_is_unknown_not_conflict(self):
        result = run("conflicts", "missing-base", "missing-branch", cwd=HERE)

        self.assertEqual(result.returncode, 2)
        self.assertIn("bad base", result.stderr)

    def test_conflict_paths_include_root_level_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_git = fake_bin / "git"
            fake_git.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ $1 == rev-parse ]]; then printf '%040d\\n' 1; exit 0; fi\n"
                "if [[ $1 == merge-tree ]]; then\n"
                "  printf '%040d\\nroot.txt\\n\\nCONFLICT (content)\\n' 2\n"
                "  exit 1\n"
                "fi\n"
                "exit 99\n",
                encoding="utf-8",
            )
            fake_git.chmod(fake_git.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:{env['PATH']}"

            result = run("conflicts", "main", "topic", env=env)

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "root.txt\n")

    def test_land_delegates_exact_arguments_in_external_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = root / "landing-contract.sh"
            contract.write_text(
                "#!/usr/bin/env bash\nprintf '%s\\n' \"$@\"\nexit 17\n",
                encoding="utf-8",
            )
            contract.chmod(contract.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env["ORCHESTRATE_LANDING_CONTRACT"] = str(contract)
            args = (
                "orc-run.1",
                "owner/repo",
                "42",
                "stack-base",
                "main",
                "a" * 40,
                "b" * 40,
                "squash",
            )

            result = run("land", *args, env=env)

        self.assertEqual(result.returncode, 17)
        self.assertEqual(result.stdout.splitlines(), ["land", *args, "external"])

    def test_verify_landed_delegates_without_merge_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = root / "landing-contract.sh"
            contract.write_text(
                "#!/usr/bin/env bash\nprintf '%s\\n' \"$@\"\n",
                encoding="utf-8",
            )
            contract.chmod(contract.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env["ORCHESTRATE_LANDING_CONTRACT"] = str(contract)
            args = ("owner/repo", "42", "main", "a" * 40, "b" * 40, "c" * 40)

            result = run("verify-landed", *args, env=env)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["verify-landed", *args])

    def test_check_run_delegates_exact_head(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = root / "landing-contract.sh"
            contract.write_text(
                "#!/usr/bin/env bash\nprintf '%s\\n' \"$@\"\n",
                encoding="utf-8",
            )
            contract.chmod(contract.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env["ORCHESTRATE_LANDING_CONTRACT"] = str(contract)
            args = ("owner/repo", "12345", "b" * 40)

            result = run("check-run", *args, env=env)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["check-run", *args])


if __name__ == "__main__":
    unittest.main()
