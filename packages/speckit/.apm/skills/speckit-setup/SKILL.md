---
name: speckit-setup
description: Bootstrap SpecKit end-to-end -- scaffold, extensions, workflows, gates. Use when setting up SpecKit, when /speckit.* commands are missing, or to initialize/enable SpecKit.
---

# SpecKit Setup

Automates the one-time SpecKit project bootstrap that otherwise has to be done by hand.
Runs `scripts/setup-speckit.sh`, which is idempotent (safe to re-run).

Requires `specify-cli` >= 0.12.0 (install/upgrade with `uv tool install specify-cli`).

## When to use

- A repo needs SpecKit but `.specify/` doesn't exist yet.
- `/speckit.*` slash commands are missing or extensions are not installed.
- The user asks to "set up / initialize / enable SpecKit".

## What it does

`scripts/setup-speckit.sh` performs seven steps:

1. **`specify init --here --force`** -- scaffolds `.specify/`. Defaults to `--integration codex --script sh`; override with `--integration` / `--script`. `--force` is always passed so init is non-interactive even on a fresh git repo (where `.git/` makes the dir non-empty and the default y/N prompt aborts).
2. **Register the community catalog** -- `specify extension catalog add --name community --install-allowed <catalog.community.json>`.
3. **Install + enable 12 required extensions** -- `agent-assign`, `cleanup`, `critique`, `fix-findings`, `iterate`, `qa`, `retro`, `review`, `roadmap`, `security-review`, `status-report`, `tinyspec`. `agent-assign` is mandatory; the DAG hard-blocks `/speckit.implement`. Custom-source installs via `name=<archive-url>` or `name=latest-release:<owner>/<repo>` are best-effort: an unreachable source warns and is skipped rather than aborting setup.
4. **Register extension commands** -- forces a (re-)registration for the requested integration via `integration switch` bounce to ensure commands are rendered correctly.
5. **Install workflow definitions** -- `speckit`, `speckit-quality`, `speckit-full` via `specify workflow add` from this package's local `workflows/<id>/` dirs (spec-kit 0.11+ workflows are a first-class primitive, not extensions).
6. **Provision the beads workflow** -- `apm install speckit` ships the formulas with this skill. Setup runs `bd init --skip-hooks` unless a workspace exists, then atomically installs `speckit-feature`, `mol-speckit-fix-findings`, and `mol-speckit-iterate` into `.beads/formulas/`. It parses every formula and dry-runs the feature graph. User-global formulas are never a setup source.
7. **Ignore status-report artefact** -- appends `specs/**/spec-status.md` to `.gitignore`.

## How to run

```bash
bash scripts/setup-speckit.sh                         # defaults: codex integration, sh scripts
bash scripts/setup-speckit.sh --integration claude --render-for claude,codex --script sh
bash scripts/setup-speckit.sh --force                 # re-scaffold even if .specify/ exists
```

Then install the orchestration bundle and compile:

```bash
apm install speckit@<marketplace> --target claude,codex,agent-skills
apm compile --target codex,claude --no-constitution
```

Start the workflow with `/speckit.specify`.

## Workflow ordering and current position

Workflow ordering is enforced by the persistent beads molecule. Run `bd swarm validate <root>` before parallel execution and `bd swarm status <root> --json` for its computed state. Do not create an extra swarm marker unless coordinator discovery must survive handoff.

## Rules

- This skill bootstraps the upstream spec-kit assets and project-local formulas. The APM `speckit` package is the formula source of truth.
- Do not hand-edit `.specify/` scaffolding or invent extension ids; the set above is what the DAG nodes expect. Keep the extension list in sync with the script's `EXTENSIONS` array.
- The script is idempotent; prefer re-running it over partial manual fixes.
- Workflow gates are beads (`bd gate resolve` for human sign-off); speckit-gate and `speckit-dag-hooks` are retired -- do not add either on new installs.
