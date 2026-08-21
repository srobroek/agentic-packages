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

    def test_exposes_only_self_contained_verbs(self):
        """orchestrate must not reach into another package's scripts at runtime.

        The landing verbs used to `exec` pr-shepherd's landing-contract.sh through a
        relative-path probe. The two are separate tools, so those verbs are gone and
        must not come back: a reintroduced delegation is a constitution violation
        (Principle I, no runtime reach-in), not a feature.
        """
        for verb in ("land", "verify-landed", "check-run"):
            with self.subTest(verb=verb):
                result = run(verb)
                self.assertEqual(result.returncode, 2)
                self.assertIn("usage: conflicts|pairwise|ci", result.stderr)

    def test_script_names_no_foreign_package_path(self):
        source = PROBE.read_text(encoding="utf-8")
        self.assertNotIn("landing-contract.sh", source)
        self.assertNotIn("ORCHESTRATE_LANDING_CONTRACT", source)


if __name__ == "__main__":
    unittest.main()
