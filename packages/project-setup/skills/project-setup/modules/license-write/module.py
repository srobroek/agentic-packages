# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""license-write — write a LICENSE file.

Preserves the verbatim Apache 2.0 and MIT license texts from project-setup.sh
Step 9 (lines 646–877). Templates live in templates/apache-2.0.txt and
templates/mit.txt with {YEAR} and {AUTHOR} as Python str.format placeholders.

SC-001 carve-out: year and author lines vary at runtime (current year via
datetime, author from git config user.name or the input). Tests MUST exclude
these lines from byte-identical assertions.

reconcile=false: LICENSE is never overwritten on re-run (the legacy script
behaviour: `if [ ! -f LICENSE ]`).

Invoked by the runner as:
    uv run module.py --plan <frozen_plan.json> --step write [--inspect]
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from datetime import datetime
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


def _git_user_name() -> str:
    """Return git config user.name, or 'AUTHOR' if unavailable."""
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        name = result.stdout.strip()
        return name if name else "AUTHOR"
    except Exception:
        return "AUTHOR"


def _render(license_type: str, year: str, author: str) -> str:
    template_map = {
        "apache-2.0": "apache-2.0.txt",
        "apache": "apache-2.0.txt",
        "mit": "mit.txt",
    }
    fname = template_map.get(license_type.lower())
    if fname is None:
        raise ValueError(f"Unknown license type: {license_type!r}")
    template_file = _TEMPLATES / fname
    body = template_file.read_text(encoding="utf-8")
    return body.replace("{YEAR}", year).replace("{AUTHOR}", author)


def main() -> int:
    ap = argparse.ArgumentParser(description="license-write module")
    ap.add_argument("--plan", required=True, help="path to the frozen plan.json")
    ap.add_argument("--step", required=True, help="step id to run")
    ap.add_argument("--inspect", action="store_true", help="dry pass: preview, no write")
    args = ap.parse_args()

    sdk = _load_sdk()
    inputs = sdk.load_frozen_inputs(args.plan, module_id="license-write")

    license_type = inputs.get_choice("license", default="apache-2.0")
    # SC-001 carve-out: author and year are runtime values, not frozen answers.
    author_input = inputs.get_str("author", default="")
    author = author_input if author_input else _git_user_name()
    year = str(datetime.now().year)

    body = _render(license_type, year, author)

    diff = sdk.idempotent_write(
        "LICENSE",
        body,
        reconcile=False,  # write-if-absent; never overwrite on re-run
        inspect=args.inspect,
    )

    files_written = [diff.path] if diff.kind in ("create", "modify") else []
    result = sdk.ModuleResult(
        module_id="license-write",
        step_id=args.step,
        status="ok",
        files_written=files_written,
        diffs=[diff],
    )
    sdk.emit_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
