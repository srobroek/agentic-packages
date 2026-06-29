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
import json
import shutil
import sys
import tomllib
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
# Runner library bootstrap (sys.path seam — spec 005 OQ-2)                     #
# --------------------------------------------------------------------------- #
# Put the runner dir (and its sources/ sub-package dir) on sys.path so every
# runner module resolves its siblings with a plain ``import <name>`` instead of
# the old per-file ``_load_sibling`` importlib bootstrap. This is the one place
# the path is established for the CLI entry; pytest does the same via conftest.py,
# and the ``uv run module.py`` subprocess path is covered by the executor's
# PYTHONPATH injection (spec 005 FR-001). A real import also registers the module
# in ``sys.modules`` before its body runs, so the ``@dataclass(Exception)`` footgun
# the old pattern guarded against cannot occur.
_RUNNER = Path(__file__).resolve().parent
for _p in (str(_RUNNER), str(_RUNNER / "sources")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pipeline  # noqa: E402
import io_adapter  # noqa: E402

run_pipeline = pipeline.run_pipeline
TerminalIO = io_adapter.TerminalIO
FileAnswersIO = io_adapter.FileAnswersIO


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
    p.add_argument(
        "--answers",
        default=None,
        metavar="FILE",
        help=(
            "Path to a JSON or TOML file of pre-collected answers "
            "(format: {\"module_id.key\": value, ..., \"enabled\": [\"module-id\", ...]}). "
            "Drives the runner non-interactively; the agent collects answers up front "
            "(interview + agent-steered decisions) and passes them here. "
            "Example: {\"core-identity.project_name\": \"my-app\", "
            "\"core-identity.license\": \"mit\", "
            "\"enabled\": [\"lang-python\"]}. "
            "On parse error the runner exits 1 — it does NOT fall back to stdin."
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

    # ── New-module scaffold (FR-C5) ──────────────────────────────────────────── #
    p.add_argument(
        "--new-module",
        default=None,
        metavar="ID",
        help=(
            "Scaffold a new addon module directory with starter module.toml, "
            "module.py, and test stub. Writes to "
            ".project-setup/modules/<id>/ in --project-dir (or --new-module-dest). "
            "Exits immediately after scaffolding without running the pipeline."
        ),
    )
    p.add_argument(
        "--new-module-dest",
        default=None,
        metavar="DIR",
        help=(
            "Destination directory for --new-module (overrides the default "
            ".project-setup/modules/<id>/ placement). The <id> subdirectory "
            "is created inside this dir."
        ),
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
# New-module scaffold (FR-C5)                                                  #
# --------------------------------------------------------------------------- #

_MODULE_TOML_TEMPLATE = """\
schema_version = "1.0"

[meta]
repository = "github.com/owner/repo"   # replace with your repo URL
author     = "Your Name"

[module]
id          = "{id}"
name        = "{name}"
version     = "0.1.0"
description = "TODO: describe what this module does."
reconcile   = false
# default_enabled is FORBIDDEN on non-bundled (addon) modules — do not add it.

[order]
requires = []
after    = []

# Input declarations drive the interview and are frozen into the plan.
# Remove or customise this example input.
[[inputs]]
key      = "greeting"
type     = "string"
prompt   = "What greeting should {name} write?"
default  = "Hello, world!"
required = false

# Steps are listed in execution order.
[[steps]]
id   = "write"
kind = "python"
"""

_MODULE_PY_TEMPLATE = '''\
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Starter module for {id}.

Run standalone:
    uv run module.py --plan /path/to/plan.json --step write [--inspect]
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path


def _load_sdk():
    # Fast path: executor puts runner dir on PYTHONPATH (spec 005).
    try:
        import sdk
        return sdk
    except ModuleNotFoundError:
        pass
    # Fallback: file-path load for direct invocation outside the executor.
    plugin_root = os.environ.get("PLUGIN_ROOT") or os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        sdk_path = Path(plugin_root) / "runner" / "sdk.py"
    else:
        sdk_path = Path(__file__).resolve().parents[2] / "runner" / "sdk.py"
    spec = importlib.util.spec_from_file_location("sdk", sdk_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sdk"] = mod   # register BEFORE exec_module (sys.modules footgun)
    spec.loader.exec_module(mod)
    return mod


def _do_write(sdk, inputs, args):
    """Step: write — write a placeholder file."""
    greeting = inputs.get_str("greeting", "Hello, world!")
    body = f"{{greeting}}\\n"

    diff = sdk.idempotent_write(
        "{id}/greeting.txt",
        body,
        reconcile=inputs.reconcile,
        inspect=args.inspect,
    )

    sdk.emit_result(sdk.ModuleResult(
        module_id="{id}",
        step_id=args.step,
        status="ok",
        files_written=[] if args.inspect else [diff.path],
        diffs=[diff],
    ))
    return 0


STEP_HANDLERS = {{
    "write": _do_write,
}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--step", required=True)
    ap.add_argument("--inspect", action="store_true")
    args = ap.parse_args()

    sdk = _load_sdk()
    inputs = sdk.load_frozen_inputs(args.plan, module_id="{id}")

    handler = STEP_HANDLERS.get(args.step)
    if handler is None:
        print(f"Unknown step: {{args.step!r}}", file=sys.stderr)
        return 1
    return handler(sdk, inputs, args)


if __name__ == "__main__":
    raise SystemExit(main())
'''

_TEST_TEMPLATE = '''\
"""Stub tests for the {id} module.

Run:
    uv run --with pytest pytest -q test_{id_safe}.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MODULE_DIR = Path(__file__).resolve().parent


def _load_parse_manifest():
    """Load parse_manifest from the runner (two levels up from modules/<id>/)."""
    runner = _MODULE_DIR.parents[2] / "runner"
    for dep in (
        "contracts", "paths", "manifest",
    ):
        for cand in (runner / f"{{dep}}.py", runner / "sources" / f"{{dep}}.py"):
            if cand.is_file() and dep not in sys.modules:
                spec = importlib.util.spec_from_file_location(dep, cand)
                assert spec and spec.loader
                mod = importlib.util.module_from_spec(spec)
                sys.modules[dep] = mod
                spec.loader.exec_module(mod)
                break
    manifest_path = runner / "manifest.py"
    if "manifest" not in sys.modules:
        spec = importlib.util.spec_from_file_location("manifest", manifest_path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules["manifest"] = mod
        spec.loader.exec_module(mod)
    return sys.modules["manifest"].parse_manifest


def test_manifest_parses_without_errors():
    """module.toml must be accepted by parse_manifest with no errors."""
    parse_manifest = _load_parse_manifest()
    manifest = parse_manifest(_MODULE_DIR / "module.toml")
    assert manifest.errors == [], (
        f"module.toml has parse errors: {{[e.how_to_fix for e in manifest.errors]}}"
    )
    assert manifest.id == "{id}"


def test_module_py_compiles():
    """module.py must be importable (syntax-valid Python)."""
    import py_compile
    py_compile.compile(str(_MODULE_DIR / "module.py"), doraise=True)
'''


def _scaffold_new_module(module_id: str, dest_dir: Path) -> int:
    """Write the starter module directory for *module_id* under *dest_dir*.

    Creates *dest_dir*/<module_id>/ containing:
    - module.toml  — valid manifest skeleton
    - module.py    — minimal working Tier-1 handler
    - test_<id>.py — stub test that calls parse_manifest

    Returns 0 on success, 1 on error (with message already printed to stderr).
    """
    import re

    # Validate id: must be non-empty, lowercase, kebab-case
    if not module_id or not re.match(r"^[a-z][a-z0-9-]*$", module_id):
        print(
            f"Error: --new-module id must be lowercase kebab-case (e.g. 'my-module'), "
            f"got: {module_id!r}",
            file=sys.stderr,
        )
        return 1

    module_dir = dest_dir / module_id
    if module_dir.exists():
        print(
            f"Error: destination already exists: {module_dir}\n"
            "Remove it first or choose a different id.",
            file=sys.stderr,
        )
        return 1

    # Derive a human name from the id (kebab → Title Case)
    name = " ".join(part.title() for part in module_id.split("-"))
    # Safe Python identifier for the test file name
    id_safe = module_id.replace("-", "_")

    try:
        module_dir.mkdir(parents=True, exist_ok=False)

        (module_dir / "module.toml").write_text(
            _MODULE_TOML_TEMPLATE.format(id=module_id, name=name),
            encoding="utf-8",
        )
        (module_dir / "module.py").write_text(
            _MODULE_PY_TEMPLATE.format(id=module_id),
            encoding="utf-8",
        )
        (module_dir / f"test_{id_safe}.py").write_text(
            _TEST_TEMPLATE.format(id=module_id, id_safe=id_safe),
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"Error: could not scaffold module: {exc}", file=sys.stderr)
        return 1

    print(
        f"Scaffolded module '{module_id}' at {module_dir}\n"
        f"  module.toml   — edit metadata, inputs, steps\n"
        f"  module.py     — implement step handlers\n"
        f"  test_{id_safe}.py — add tests\n"
        f"\n"
        f"To use locally, add .project-setup/modules/{module_id}/ to your project\n"
        f"(or declare it as a [[source]] in .project-setup/sources.toml for git dist).",
    )
    return 0


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    """Parse arguments, construct IO + Pipeline, return POSIX exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    # ── --new-module: scaffold and exit (no pipeline run) ───────────────────── #
    if args.new_module:
        project_dir = Path(args.project_dir).expanduser().resolve()
        if args.new_module_dest:
            dest_dir = Path(args.new_module_dest).expanduser().resolve()
        else:
            dest_dir = project_dir / ".project-setup" / "modules"
        return _scaffold_new_module(args.new_module, dest_dir)

    project_dir = Path(args.project_dir).expanduser().resolve()
    if not project_dir.exists():
        print(
            f"Error: project directory does not exist: {project_dir}",
            file=sys.stderr,
        )
        return 1

    # ── IO construction (FR-001/002/006) ─────────────────────────────────────── #
    # Priority: --answers (agent path) > --non-interactive > TerminalIO (human).
    non_interactive = args.non_interactive
    if args.answers:
        answers_path = Path(args.answers).expanduser().resolve()
        try:
            if answers_path.suffix.lower() == ".toml":
                with answers_path.open("rb") as _f:
                    raw_answers: dict = tomllib.load(_f)
            else:
                with answers_path.open("r", encoding="utf-8") as _f:
                    raw_answers = json.load(_f)
        except Exception as exc:
            print(
                f"Error: could not read --answers {args.answers}: {exc}",
                file=sys.stderr,
            )
            return 1
        # Pull the optional top-level "enabled" list out of the dict; the rest
        # are answer entries keyed as "module_id.key" (or bare "key").
        enabled: list[str] | None = raw_answers.pop("enabled", None)
        if enabled is not None and not isinstance(enabled, list):
            print(
                f"Error: 'enabled' in --answers file must be a list of module ids, got {type(enabled).__name__}",
                file=sys.stderr,
            )
            return 1
        io = FileAnswersIO(
            answers=raw_answers,
            enabled=enabled,
            active_flags=_active_flags(args),
        )
        non_interactive = True  # answer-driven implies non-interactive semantics
    elif args.non_interactive:
        io = TerminalIO()
    else:
        io = TerminalIO()

    try:
        result = run_pipeline(
            project_dir=project_dir,
            io=io,
            skill_version=args.skill_version,
            non_interactive=non_interactive,
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
