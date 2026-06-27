# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""agents-md — write a skeleton AGENTS.md.

Preserves BOTH verbatim heredocs from project-setup.sh Step 6 (lines 478–585):
  - monorepo layout: templates/monorepo.md  (lines 478–536)
  - single layout:   templates/single.md    (lines 538–585)

PROJECT_NAME and ORG placeholders are substituted from core-identity answers.
The template text is stored in templates/ alongside this module so it travels
with the module and is easy to diff/audit.

reconcile=true: re-running overwrites AGENTS.md to match the template (with
current substitutions) if it has drifted.

Invoked by the runner as:
    uv run module.py --plan <frozen_plan.json> --step write [--inspect]
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

_TEMPLATES = Path(__file__).resolve().parent / "templates"


def _load_sdk():
    plugin_root = os.environ.get("PLUGIN_ROOT")
    if plugin_root:
        sdk_path = Path(plugin_root) / "runner" / "sdk.py"
        if not sdk_path.is_file():
            sdk_path = Path(plugin_root) / "skills" / "project-setup" / "runner" / "sdk.py"
    else:
        sdk_path = Path(__file__).resolve().parents[2] / "runner" / "sdk.py"
    spec = importlib.util.spec_from_file_location("ps_sdk", sdk_path)
    assert spec and spec.loader, f"cannot locate runner SDK at {sdk_path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ps_sdk"] = mod
    spec.loader.exec_module(mod)
    return mod


def _render(layout: str, project_name: str, org: str) -> str:
    """Load the appropriate template and substitute placeholders.

    Single-pass substitution via one regex alternation so a user value that
    happens to contain another placeholder token (e.g. a project literally named
    "myORG-api") cannot be double-substituted. PROJECT_NAME precedes ORG in the
    alternation so the longer token wins on the literal ``ORG/PROJECT_NAME`` line.
    """
    import re

    template_file = _TEMPLATES / ("monorepo.md" if layout == "monorepo" else "single.md")
    body = template_file.read_text(encoding="utf-8")
    mapping = {"PROJECT_NAME": project_name, "ORG": org}
    pattern = re.compile("|".join(re.escape(k) for k in mapping))
    return pattern.sub(lambda m: mapping[m.group(0)], body)


def main() -> int:
    ap = argparse.ArgumentParser(description="agents-md module")
    ap.add_argument("--plan", required=True, help="path to the frozen plan.json")
    ap.add_argument("--step", required=True, help="step id to run")
    ap.add_argument("--inspect", action="store_true", help="dry pass: preview, no write")
    args = ap.parse_args()

    sdk = _load_sdk()
    inputs = sdk.load_frozen_inputs(args.plan, module_id="agents-md")

    layout = inputs.get_choice("layout", default="single")
    project_name = inputs.get_str("project_name", default="PROJECT_NAME")
    org = inputs.get_str("org", default="ORG")

    body = _render(layout, project_name, org)

    diff = sdk.idempotent_write(
        "AGENTS.md",
        body,
        reconcile=True,
        inspect=args.inspect,
    )

    files_written = [diff.path] if diff.kind in ("create", "modify") else []
    result = sdk.ModuleResult(
        module_id="agents-md",
        step_id=args.step,
        status="ok",
        files_written=files_written,
        diffs=[diff],
    )
    sdk.emit_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
