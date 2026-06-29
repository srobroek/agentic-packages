# Quickstart: project-setup runner + modules

Companion to [plan.md](./plan.md). Two walkthroughs: running a setup, and
authoring a module. Both assume `uv` is installed (hard prerequisite).

## Running a setup (what the agent does)

1. **Ensure `uv`.** The runner's first action is a `uv` preflight; if absent it
   exits with an install instruction and does nothing else (no degraded run).
2. **Invoke the runner.** `uv run skills/project-setup/runner/cli.py` (or the
   skill tells the agent to). The runner detects mode by
   `.project-setup/sources.toml` presence:
   - **Init** (absent): resolve sources (bundled + home catalog), fetch/cache,
     discover modules, conduct the manifest-driven interview, write
     `.project-setup/{sources,answers}.toml`.
   - **Reproduce/update** (present): fetch declared sources, load committed
     answers, run the diff/confirm loop.
3. **Validate-closed gate.** Before any write, the runner checks all
   required answers present + every enabled module and its `requires` closure
   resolve + required tools on PATH — reporting ALL problems at once, refusing to
   proceed otherwise.
4. **Execute** in topological order. For each module step:
   - `python` → `uv run module.py --plan <frozen> --step <id>` (Tier-1).
   - `gate` → the runner renders the message and captures confirmation.
   - `agent` → the runner hands the steering doc to the agent (Tier-2); the
     decision is recorded with `agent-steered` provenance.
5. **Persist.** Answers (with per-key provenance) are written to
   `.project-setup/answers.toml`; the project is now reproducible from committed
   files alone.

**Done means**: validate-closed passed, every enabled module's steps ran (or were
confirmed-skipped), `.project-setup/{sources,answers}.toml` are written, and the
observable scaffold matches the answers. The skill instructs the agent on this
definition, on the secrets guardrail (never accept a secret; if supplied, tell
the user to rotate it — compromised — and never persist it), and on running
module entrypoints safely.

## Authoring a module (the bolt-on path)

Drop a directory into a module root (`~/.config/project-setup/modules/` for
personal, `./.project-setup/modules/` for project-local, or a git source declared
in `sources.toml`). No edit to the runner or skill.

```
modules/devcontainer-write/
├── module.toml          # manifest (see contracts/shared-contracts.md §1)
├── module.py            # fixed name; PEP 723 deps; --plan/--step/--inspect
├── templates/           # optional static assets
├── steering/            # optional Tier-2 agent docs
└── test_devcontainer_write.py   # pytest (uv run)
```

`module.toml`:
```toml
[meta]
repository = "github.com/me/my-modules"
author     = "me"

[module]
id = "devcontainer-write"
name = "Dev Container"
version = "1.0.0"
description = "Write a .devcontainer/devcontainer.json"
reconcile = true

[order]
requires = ["core-identity"]
after    = ["dirs-scaffold"]

[[inputs]]
key = "base_image"
type = "choice"
prompt = "Dev container base image?"
choices = ["mcr.microsoft.com/devcontainers/base:ubuntu", "node:22", "python:3.12"]
default = "mcr.microsoft.com/devcontainers/base:ubuntu"
required = true

[[steps]]
id = "write"
kind = "python"
```

`module.py` (skeleton):
```python
# /// script
# requires-python = ">=3.11"
# dependencies = []     # add yours; uv provisions per-invocation
# ///
import argparse, importlib.util, os
# load the SDK by file path (no package import, no PyPI dep)
sdk_path = os.path.join(os.environ.get("PLUGIN_ROOT", _fallback_root()),
                        "skills/project-setup/runner/sdk.py")
spec = importlib.util.spec_from_file_location("ps_sdk", sdk_path)
sdk = importlib.util.module_from_spec(spec); spec.loader.exec_module(sdk)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--step", required=True)
    ap.add_argument("--inspect", action="store_true")  # dry pass: preview, no write
    a = ap.parse_args()
    inputs = sdk.load_frozen_inputs(a.plan, module_id="devcontainer-write")
    image = inputs.get_choice("base_image")
    body = sdk.render(".devcontainer/devcontainer.json", image=image)
    result = sdk.idempotent_write(".devcontainer/devcontainer.json", body,
                                  reconcile=inputs.reconcile, inspect=a.inspect)
    return sdk.emit_result(result)   # the ONE result-JSON writer

if __name__ == "__main__":
    raise SystemExit(main())
```

The runner discovers it, asks `base_image` in the interview (default pre-filled
from module < home < project layering), topologically orders it after
`dirs-scaffold`, and on confirmation runs `uv run module.py --step write`. On
re-run, the diff/confirm loop shows any drift before overwriting (reconcile).

## Testing a module

`test_devcontainer_write.py` runs `uv run module.py` against a tmp project with a
frozen plan and asserts on-disk parity with the answers (FR-031). Tier-1 modules
also get an SC-001 byte-identical re-run assertion (excluding intrinsically
variable values). Run via `uv run --with pytest pytest -q` (the CI contract).
