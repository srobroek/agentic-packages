---
name: speckit-setup
description: Bootstrap a SpecKit project end-to-end -- scaffold .specify/, register the community extension catalog, install and enable all required extensions and workflow definitions. Use when setting up SpecKit in a repo, when /speckit.* commands are missing, or when the user asks to initialize/enable SpecKit.
---

# SpecKit Setup

Automates the one-time SpecKit project bootstrap that otherwise has to be done by hand.
Runs `scripts/setup-speckit.sh`, which is idempotent (safe to re-run).

## When to use

- A repo needs SpecKit but `.specify/` doesn't exist yet.
- `/speckit.*` slash commands are missing or extensions are not installed.
- The user asks to "set up / initialize / enable SpecKit".

## What it does

`scripts/setup-speckit.sh` performs six steps:

1. **`specify init --here`** -- scaffolds `.specify/`. Defaults to `--integration codex --script sh`; override with `--integration` / `--script`.
2. **Register the community catalog** -- `specify extension catalog add --name community --install-allowed <catalog.community.json>`.
3. **Install + enable 28 required extensions** -- `agent-assign`, `archive`, `brownfield`, `bugfix`, `checkpoint`, `cleanup`, `conduct`, `critique`, `diagram`, `doctor`, `fix-findings`, `fleet`, `github-issues`, `iterate`, `onboard`, `optimize`, `qa`, `reconcile`, `refine`, `retro`, `review`, `roadmap`, `security-review`, `status-report`, `tinyspec`, `verify`, `verify-tasks`, `worktree`. `agent-assign` is mandatory; the DAG hard-blocks `/speckit.implement`. Custom-source installs via `name=<archive-url>` or `name=latest-release:<owner>/<repo>` are best-effort: an unreachable source warns and is skipped rather than aborting setup.
4. **Register extension commands** -- forces a (re-)registration for the requested integration via `integration switch` bounce to ensure commands are rendered correctly.
5. **Install workflow definitions** -- `speckit`, `speckit-quality`, `speckit-full` via `specify workflow add` from this package's local `workflows/<id>/` dirs.
6. **Ignore status-report artefact** -- appends `specs/**/spec-status.md` to `.gitignore`.

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

Workflow ordering is enforced by speckit-dag-hooks and described in the speckit steering; run `/speckit.status-report.show` to see current position.

## Rules

- This skill only bootstraps the upstream spec-kit side. The orchestration that enforces the DAG (agents, hooks, node store) comes from the APM `speckit` bundle -- install it too.
- Do not hand-edit `.specify/` scaffolding or invent extension ids; the set above is what the DAG nodes expect. Keep the extension list in sync with the script's `EXTENSIONS` array.
- The script is idempotent; prefer re-running it over partial manual fixes.
