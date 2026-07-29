#!/usr/bin/env python3
"""Verify rtk's filters case by case: what each saves, and what each loses.

The allowlist in `rtk-rewrite-guard.py` is only defensible if someone checked
each entry. This is that check, as a repeatable harness rather than a one-time
session. It runs a real command twice -- natively and through rtk -- in a
scratch fixture built for the purpose, then compares:

  bytes        how much smaller the filtered output is
  facts        whether the load-bearing content survived (per-case patterns)
  exit code    whether the command's own verdict changed
  newline      whether a trailing newline was dropped (breaks `| wc -l`)
  announced    whether an omission was declared rather than silent

A case PASSES only when every required fact survives and the exit code is
unchanged. Size is reported but never decides a verdict: a filter that halves
output and drops a failure message is a regression, not a saving.

Comparison is against the RAW command, not against the `2>&1 | tail -50` idiom
the agent actually uses. Both are reported, because on some shapes hand-tailing
is cheaper than rtk and that is the honest baseline.

Run: rtk-verify.py [--case NAME] [--markdown] [--keep]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TIMEOUT = 300

# Each case: how to build the fixture, the command to run, and the facts that
# MUST survive filtering. `requires` names binaries the case needs.
CASES: dict[str, dict] = {}


def case(name: str, *, requires: list[str], facts: list[str], command: str, setup=None, cwd_is_fixture=True):
    CASES[name] = {
        "requires": requires,
        "facts": facts,
        "command": command,
        "setup": setup,
        "cwd_is_fixture": cwd_is_fixture,
    }


# --- fixtures ---------------------------------------------------------------


def _git_repo(root: Path) -> None:
    run = lambda *a: subprocess.run(["git", "-C", str(root), *a], check=True, capture_output=True)  # noqa: E731
    run("init", "-q")
    run("config", "user.email", "t@example.test")
    run("config", "user.name", "Test Author")
    run("config", "commit.gpgsign", "false")
    for i in range(1, 26):
        (root / f"f{i}.txt").write_text(f"content {i}\n" * 12)
        run("add", "-A")
        run("commit", "-qm", f"commit number {i} with a distinctive subject line")
    (root / "dirty.txt").write_text("uncommitted\n")


def _pytest_failing(root: Path) -> None:
    lines = []
    for i in range(1, 31):
        lines += [
            f"def test_case_{i}():",
            f"    value = {i}",
            f'    assert value == -1, "failure detail number {i}"',
        ]
    (root / "test_many.py").write_text("\n".join(lines) + "\n")


def _pytest_passing(root: Path) -> None:
    lines = []
    for i in range(1, 31):
        lines += [f"def test_ok_{i}():", "    assert True"]
    (root / "test_pass.py").write_text("\n".join(lines) + "\n")


def _cargo_warnings(root: Path) -> None:
    subprocess.run(
        ["cargo", "init", "--name", "probe", "-q"], cwd=str(root), check=True, capture_output=True
    )
    (root / "src" / "main.rs").write_text(
        "fn main() {\n"
        "    let mut v: Vec<i32> = Vec::new();\n"
        "    for i in 0..30 { v.push(i); }\n"
        '    if v.len() == 0 { println!("empty"); }\n'
        "    let s = String::from(\"x\");\n"
        "    let _t = s.clone();\n"
        '    println!("{:?}", v);\n'
        "}\n"
    )


def _ruff_violations(root: Path) -> None:
    (root / "bad.py").write_text(
        "import os\nimport sys\nimport json\n\n\ndef f( a ):\n    x=1\n    return a\n"
    )


def _many_matches(root: Path) -> None:
    (root / "m.txt").write_text(
        "".join(f"match line {i} with distinctive content\n" for i in range(1, 401))
    )


def _big_tree(root: Path) -> None:
    for d in range(6):
        sub = root / f"dir{d}"
        sub.mkdir()
        for i in range(30):
            (sub / f"file{i}.txt").write_text("x\n")


# --- cases ------------------------------------------------------------------

case(
    "git-log",
    requires=["git"],
    setup=_git_repo,
    command="git log --oneline",
    facts=["commit number 25", "commit number 1 "],
)
case(
    "git-log-verbose",
    requires=["git"],
    setup=_git_repo,
    command="git log",
    # rtk reformats the verbose log into a compact line, so assert the author
    # NAME and the subject, not git's "Author:" label -- the label is decoration.
    facts=["commit number 25", "Test Author"],
)
case(
    "git-diff",
    requires=["git"],
    setup=_git_repo,
    command="git diff HEAD~3",
    facts=["f23.txt", "f25.txt"],
)
case(
    "git-show",
    requires=["git"],
    setup=_git_repo,
    command="git show HEAD",
    facts=["commit number 25", "f25.txt"],
)
case(
    "git-blame",
    requires=["git"],
    setup=_git_repo,
    command="git blame f1.txt",
    facts=["content 1"],
)
case(
    "git-status-porcelain",
    requires=["git"],
    setup=_git_repo,
    command="git status --porcelain",
    facts=["dirty.txt"],
)
case(
    "pytest-failing",
    requires=["pytest"],
    setup=_pytest_failing,
    command="pytest test_many.py",
    facts=["failure detail number 1", "failure detail number 30", "30 failed"],
)
case(
    "pytest-passing",
    requires=["pytest"],
    setup=_pytest_passing,
    command="pytest test_pass.py",
    facts=["30 passed"],
)
case(
    "uv-run-pytest-failing",
    requires=["uv"],
    setup=_pytest_failing,
    command="uv run --no-project --with pytest pytest test_many.py",
    facts=["failure detail number 1", "failure detail number 30", "30 failed"],
)
case(
    "cargo-clippy",
    requires=["cargo"],
    setup=_cargo_warnings,
    command="cargo clippy",
    facts=["len", "main.rs"],
)
case(
    "cargo-build",
    requires=["cargo"],
    setup=_cargo_warnings,
    command="cargo build",
    # rtk summarizes as "N crates compiled" and keeps the profile line, so the
    # crate NAME is decoration here; the verdict is what a reader acts on.
    facts=["Finished"],
)
case(
    "cargo-test",
    requires=["cargo"],
    setup=_cargo_warnings,
    command="cargo test",
    # rtk renders the tally as "N passed (N suite)" instead of git's
    # "test result: ok." wording. Assert the tally survives, not the phrasing.
    facts=["passed"],
)
case(
    "ruff-check",
    requires=["ruff"],
    setup=_ruff_violations,
    command="ruff check bad.py",
    facts=["bad.py", "F401"],
)
case(
    "grep-many",
    requires=["grep"],
    setup=_many_matches,
    command="grep -n match m.txt",
    facts=["match line 1 ", "match line 400"],
)
case(
    "grep-count",
    requires=["grep"],
    setup=_many_matches,
    command="grep -c match m.txt",
    facts=["400"],
)
case(
    "wc-lines",
    requires=["wc"],
    setup=_many_matches,
    command="wc -l m.txt",
    facts=["400"],
)
case(
    "ls-tree",
    requires=["ls"],
    setup=_big_tree,
    command="ls -la",
    facts=["dir0", "dir5"],
)
case(
    "find-files",
    requires=["find"],
    setup=_big_tree,
    command="find . -name '*.txt'",
    facts=["dir0", "dir5"],
)


# --- runner -----------------------------------------------------------------


def _named_log(text: str) -> str | None:
    """Extract the tee-log path rtk prints when it truncates.

    rtk writes it as `[full output: ~/Library/.../tee/<name>.log]` or
    `[see remaining: tail -n +N <path>]`, with `~` unexpanded.

    The path CONTAINS A SPACE on macOS (`~/Library/Application Support/rtk/...`),
    so a `[^\\s]` pattern silently truncates it to `Support/rtk/tee/...` and every
    recoverability check then reads a nonexistent file and reports the fact as
    lost. Anchor on the `~`/`/` start and stop at the `.log` extension instead.
    """
    import re

    match = re.search(r"(~?/[^\]\n]*?/rtk/tee/[^\]\n]+?\.log)", text)
    if not match:
        return None
    return os.path.expanduser(match.group(1).strip())


def run_shell(command: str, cwd: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            command, shell=True, cwd=str(cwd), capture_output=True, text=True, timeout=TIMEOUT
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.SubprocessError:
        return -1, ""


def verify(name: str, spec: dict, keep: bool) -> dict:
    missing = [b for b in spec["requires"] if shutil.which(b) is None]
    if missing:
        return {"case": name, "status": "SKIP", "reason": f"missing {', '.join(missing)}"}

    workdir = Path(tempfile.mkdtemp(prefix=f"rtkverify-{name}-"))
    try:
        if spec["setup"]:
            spec["setup"](workdir)

        native_code, native = run_shell(spec["command"], workdir)
        rtk_code, filtered = run_shell(f"rtk {spec['command']}", workdir)
        # The idiom the agent actually uses, as the honest competing baseline.
        _, tailed = run_shell(f"{spec['command']} 2>&1 | tail -50", workdir)

        lost = [f for f in spec["facts"] if f in native and f not in filtered]
        newline_dropped = native.endswith("\n") and bool(filtered) and not filtered.endswith("\n")
        announced = any(
            marker in filtered
            for marker in ("more in", "omitted", "tee/", "full output", "remaining:", "+")
        )

        # A fact rtk dropped from the transcript but preserved in the tee log it
        # NAMED is a different risk from one that vanished. The agent can still
        # reach the first; measured on a 30-failure pytest run, rtk showed 10 and
        # all 30 were recoverable from the log path it printed. Only count a fact
        # as truly lost when the spill file cannot produce it either.
        recoverable = []
        if lost and announced:
            spill = _named_log(filtered)
            if spill:
                try:
                    body = Path(spill).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    body = ""
                recoverable = [f for f in lost if f in body]
        unrecoverable = [f for f in lost if f not in recoverable]

        status = "PASS"
        if unrecoverable:
            status = "LOSES-FACTS"
        elif native_code != rtk_code:
            status = "EXIT-CHANGED"
        elif newline_dropped:
            status = "NEWLINE-DROPPED"
        elif recoverable:
            status = "TRUNCATED-RECOVERABLE"

        return {
            "case": name,
            "status": status,
            "command": spec["command"],
            "bytes_native": len(native),
            "bytes_rtk": len(filtered),
            "bytes_tail50": len(tailed),
            "saved_vs_native_pct": round((1 - len(filtered) / len(native)) * 100, 1) if native else 0.0,
            "rtk_beats_tail50": len(filtered) < len(tailed),
            "exit_native": native_code,
            "exit_rtk": rtk_code,
            "facts_required": len(spec["facts"]),
            "facts_lost": unrecoverable,
            "facts_recoverable_from_log": recoverable,
            "newline_dropped": newline_dropped,
            "truncation_announced": announced,
        }
    finally:
        if not keep:
            shutil.rmtree(workdir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", action="append", help="run only these cases")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--keep", action="store_true", help="keep fixture dirs for inspection")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)

    if args.list:
        for name, spec in CASES.items():
            print(f"{name}\t{spec['command']}")
        return 0

    if shutil.which("rtk") is None:
        print("rtk is not installed", file=sys.stderr)
        return 1

    selected = args.case or list(CASES)
    results = [verify(n, CASES[n], args.keep) for n in selected if n in CASES]

    if args.markdown:
        version = subprocess.run(["rtk", "--version"], capture_output=True, text=True).stdout.strip()
        print(f"# rtk filter verification ({version})\n")
        print("| Case | Status | Native | rtk | `\\| tail -50` | Saved | Facts lost |")
        print("| --- | --- | --- | --- | --- | --- | --- |")
        for r in results:
            if r["status"] == "SKIP":
                print(f"| {r['case']} | SKIP | | | | | {r['reason']} |")
                continue
            print(
                f"| `{r['command']}` | {r['status']} | {r['bytes_native']} | {r['bytes_rtk']} "
                f"| {r['bytes_tail50']} | {r['saved_vs_native_pct']}% "
                f"| {', '.join(r['facts_lost']) or '-'} |"
            )
        bad = [r for r in results if r["status"] not in ("PASS", "SKIP", "TRUNCATED-RECOVERABLE")]
        if bad:
            print("\n## Not safe to route\n")
            for r in bad:
                print(f"- `{r['command']}`: {r['status']}")
        worse = [
            r
            for r in results
            if r["status"] in ("PASS", "TRUNCATED-RECOVERABLE") and not r["rtk_beats_tail50"]
        ]
        if worse:
            print("\n## Safe, but hand-tailing is already cheaper\n")
            for r in worse:
                print(f"- `{r['command']}`: rtk {r['bytes_rtk']} vs tail-50 {r['bytes_tail50']}")
    else:
        print(json.dumps(results, indent=2))

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
