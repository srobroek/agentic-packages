#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""CLI entry point for the project-setup runner.

Usage::

    uv run cli.py [--project-dir <path>] [--non-interactive] [--dry-run]

The runner core is dependency-free (stdlib only); TOML is read with stdlib
``tomllib`` and written with a small stdlib emitter in ``persist.py``. The only
hard requirement is ``uv`` itself (checked in preflight). Individual capability
modules declare their own deps via their own PEP 723 headers and run under
``uv run module.py``.

Preflight: the FIRST thing done (before any import from the runner) is a
``shutil.which("uv")`` check.  If ``uv`` is absent the process exits non-zero
with a clear installation instruction.  This is a hard requirement — there is
no stdlib fallback path (see shared-contracts.md, plan.md §Technical Context).
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# uv preflight — MUST be the first check (before any runner imports)          #
# --------------------------------------------------------------------------- #
def _check_uv() -> None:
    """Exit immediately with a helpful message if ``uv`` is not on PATH."""
    if shutil.which("uv") is None:
        print(
            "Error: 'uv' is required but was not found on PATH.\n"
            "\n"
            "Install uv:\n"
            "  curl -LsSf https://astral.sh/uv/install.sh | sh\n"
            "  # or: brew install uv  (macOS)\n"
            "  # or: pip install uv   (fallback)\n"
            "\n"
            "See https://docs.astral.sh/uv/getting-started/installation/\n"
            "\n"
            "project-setup requires uv to provision per-module Python deps.\n"
            "There is no stdlib fallback path.",
            file=sys.stderr,
        )
        sys.exit(1)


_check_uv()  # Hard-fail before any other code runs

# --------------------------------------------------------------------------- #
# Runner library bootstrap (import-by-path)                                   #
# --------------------------------------------------------------------------- #
_RUNNER = Path(__file__).resolve().parent


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_pipeline_mod = _load("pipeline")
_io_mod = _load("io_adapter")

run_pipeline = _pipeline_mod.run_pipeline
TerminalIO = _io_mod.TerminalIO


# --------------------------------------------------------------------------- #
# Argument parser                                                              #
# --------------------------------------------------------------------------- #
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="project-setup",
        description=(
            "Modular, config-driven project bootstrapper.  "
            "Runs a manifest-driven interview, validates constraints, "
            "then executes each enabled module to scaffold the project."
        ),
    )
    p.add_argument(
        "--project-dir",
        default=".",
        metavar="DIR",
        help="Project directory to set up (default: current working directory).",
    )
    p.add_argument(
        "--non-interactive",
        action="store_true",
        default=False,
        help="Skip all prompts and use defaults + committed answers only.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=(
            "Run the interview and build the frozen plan but do NOT execute "
            "modules or write .project-setup/ files."
        ),
    )
    p.add_argument(
        "--skill-version",
        default="",
        metavar="VERSION",
        help="Advisory version string written to sources.toml [meta] section.",
    )
    p.add_argument(
        "--refresh",
        action="append",
        default=None,
        metavar="MODULE[.KEY]",
        help=(
            "Reproduce mode only: re-research the named Tier-2 agent decision(s). "
            "Pass a module id (e.g. 'lang-python') or a module.key. Repeatable. "
            "Each refreshed decision is shown as an old-vs-new diff and applied "
            "only on confirm; all other agent steps replay their committed "
            "decision with zero network. Ignored in init mode."
        ),
    )

    # ── Per-action gate flags (spec 004 §3) ─────────────────────────────────── #
    # Hard gates SAFE-skip in --non-interactive unless opted in by a SPECIFIC flag;
    # soft gates proceed unless opted out. There is deliberately NO global
    # "--yes"/"--confirm-all" (spec 004 FR-005 / anti-pattern 5): a blanket toggle
    # would auto-approve the public repo, the install, and the stack write together.
    gate = p.add_argument_group(
        "gate opt-in/opt-out flags",
        "Per-action consent for hard gates in --non-interactive runs (no global yes-to-all).",
    )
    gate.add_argument(
        "--allow-public-repo", action="store_true", default=False,
        help="CI opt-in: create a PUBLIC GitHub repo (G3 hard gate). Off = safe-skip.",
    )
    gate.add_argument(
        "--allow-install", action="store_true", default=False,
        help="CI opt-in: run the batched 'apm install' (G2 supply-chain gate). Off = safe-skip.",
    )
    gate.add_argument(
        "--allow-stack-write", action="store_true", default=False,
        help="CI opt-in: write agent-researched dependency pins (G6 gate). Off = safe-skip.",
    )
    gate.add_argument(
        "--no-external-generators", action="store_true", default=False,
        help="CI opt-out: skip external scaffolders like 'nuxi init' (G4 soft gate).",
    )
    return p


# Map argparse dest → the gate flag name carried in active_flags. The flag NAME
# (kebab) is what gate steps reference via [[steps]].allow_flag / .skip_flag.
_GATE_FLAGS = {
    "allow_public_repo": "allow-public-repo",
    "allow_install": "allow-install",
    "allow_stack_write": "allow-stack-write",
    "no_external_generators": "no-external-generators",
}


def _active_flags(args: argparse.Namespace) -> frozenset[str]:
    """Collect the gate flag names the user activated into the set the resolver reads."""
    return frozenset(
        flag for dest, flag in _GATE_FLAGS.items() if getattr(args, dest, False)
    )


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    """Parse arguments, construct IO + Pipeline, return POSIX exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    project_dir = Path(args.project_dir).expanduser().resolve()
    if not project_dir.exists():
        print(
            f"Error: project directory does not exist: {project_dir}",
            file=sys.stderr,
        )
        return 1

    io = TerminalIO()

    try:
        result = run_pipeline(
            project_dir=project_dir,
            io=io,
            skill_version=args.skill_version,
            non_interactive=args.non_interactive,
            dry_run=args.dry_run,
            refresh=args.refresh,
            active_flags=_active_flags(args),
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not result.success:
        for err in result.errors:
            print(f"[ERROR] {err.how_to_fix}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
