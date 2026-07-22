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
6. **Provision the beads workflow** -- runs `bd init --skip-hooks` (unless a workspace exists) and installs the `speckit-feature` formula from the speckit-beads package into `.beads/formulas/`; the poured molecule is the phase DAG with human gates. Guard: skipped with a clear message when `bd` is absent. (Replaces the retired speckit-gate PyPI tool.)
7. **Ignore status-report artefact** -- appends `specs/**/spec-status.md` to `.gitignore`.

## How to run

```bash
bash scripts/setup-speckit.sh                         # defaults: codex integration, sh scripts
bash scripts/setup-speckit.sh --integration claude --script sh
bash scripts/setup-speckit.sh --force                 # re-scaffold even if .specify/ exists
```

Then install the orchestration bundle and compile:

```bash
apm install speckit@<marketplace> --target claude,codex,agent-skills
apm compile --target codex,claude --no-constitution
```

Start the workflow with `/speckit.specify`.

## Workflow ordering and current position

Workflow ordering is enforced by the beads molecule (dependency edges + gate beads; see the speckit-beads steering) and described in the speckit steering; run `bd mol current <root>` or `/speckit.status-report.show` to see current position.

## Rules

- This skill only bootstraps the upstream spec-kit side. The orchestration that enforces the DAG (agents, hooks, node store) comes from the APM `speckit` bundle -- install it too.
- Do not hand-edit `.specify/` scaffolding or invent extension ids; the set above is what the DAG nodes expect. Keep the extension list in sync with the script's `EXTENSIONS` array.
- The script is idempotent; prefer re-running it over partial manual fixes.
- Workflow gates are beads (`bd gate resolve` for human sign-off); speckit-gate and `speckit-dag-hooks` are retired -- do not add either on new installs.
