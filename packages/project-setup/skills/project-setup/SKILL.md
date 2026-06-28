---
name: project-setup
description: Bootstrap or update a repo with a modular, config-driven runner. The skill is generic; every capability (git, GitHub, dirs, pre-commit, license, gitignore, APM, SpecKit, language overlays, identity) is a discoverable module. Use when creating a project, adding a monorepo package, choosing modules/sources, or re-running setup to fix drift.
---

# Project Setup (runner + modules)

This skill is a **generic runner**: it carries no project-specific configuration.
Every capability is a self-contained **module** the runner discovers, orders,
and executes. You drive the runner; the runner is the source of truth for
orchestration. Read this whole file before running it.

`uv` is a **hard prerequisite**. The runner is Python launched via `uv run`. If
`uv` is missing, the runner exits with an install instruction — do not try to
work around it, install `uv` (https://docs.astral.sh/uv/).

## How to run it end-to-end

The entry point is the runner CLI:

```
uv run <plugin-root>/skills/project-setup/runner/cli.py --project-dir <dir>
```

`<plugin-root>` is this skill's directory (resolved at runtime via `${PLUGIN_ROOT}`).
The runner executes a fixed pipeline:

1. **Resolve sources** — read module sources (bundled + any declared in config).
2. **Fetch/cache** — clone declared git sources into `~/.cache/project-setup/`
   (offline/failed fetch is non-fatal; bundled modules always work).
3. **Discover modules** — scan the module roots (precedence: env
   `PROJECT_SETUP_MODULES_DIR` > project `./.project-setup/modules/` > home
   `~/.config/project-setup/modules/` > fetched sources > bundled).
4. **Interview** — ask each enabled module's declared inputs (generated from
   manifests, not free-form).
5. **Validate-closed gate** — refuse to write unless every required input is
   present, every `requires` resolves, there is no dependency cycle, and every
   required tool is on PATH. It reports **all** problems at once.
6. **Freeze plan** — write the canonical execution plan to the cache (never into
   the committed project).
7. **Execute** — run each module's steps in topological order (see Tiers below).
8. **Persist** — write committed `.project-setup/sources.toml` +
   `.project-setup/answers.toml`.

## Modes (the runner detects this; you do not choose it)

- **Init** (no `.project-setup/sources.toml`): conduct the interview, then write
  `sources.toml` + `answers.toml`. This is a fresh project.
- **Reproduce/update** (`sources.toml` present): fetch declared sources, load the
  committed answers, and run the **diff/confirm loop** — every change is shown
  and confirmed before any write. Used on a clone, or to fix drift / update.

A clone reproduces a project from its committed `.project-setup/` files alone —
independent of any machine's home config.

## Tiers — what is deterministic vs. agent-steered

Each module step has a `kind`:

- **`python`** (Tier 1): deterministic. Same answers + same module version →
  byte-identical output. Runs as `uv run module.py`.
- **`agent`** (Tier 2): the step carries a `steering/` doc; you (the agent) follow
  it and record a decision. Consistent, not byte-identical. Its decisions are
  persisted with `agent-steered` provenance.
- **`gate`**: a confirm checkpoint — show the message, capture yes/no. Each gate
  carries a `hardness` (default `hard`) that drives its non-interactive behavior
  (see "Gates & hardness" below).

Your judgment belongs in `agent` steps and in choosing answers. Never hand-write
what a `python` step produces; never pass answers as arguments to a module — the
module reads frozen inputs from disk.

## Gates & hardness (the review checkpoints)

A `gate` step is calibrated by `hardness` so non-interactive/CI runs never deadlock
and never silently take a consequential action:

| hardness | TTY | `--non-interactive` / CI |
|---|---|---|
| `hard` (default) | prompt `[y/N]`, default No | **SAFE-skip** the gated step, unless its `allow_flag` is passed → perform |
| `soft` | prompt `[Y/n]`, default Yes | proceed, unless its `skip_flag` is passed → SAFE-skip |
| `informational` | print, no prompt | print, proceed |

A declined/safe-skipped gate **blocks the consequential step it guards** (the
later `python` writes in that module). CI opts into a specific hard action with a
**per-action flag** — there is deliberately **no** global "yes-to-all":

- `--allow-public-repo` — create a PUBLIC GitHub repo (G3; private is ungated).
- `--allow-install` — run the batched `apm install` (G2 supply-chain gate).
- `--allow-stack-write` — write agent-researched dependency pins (G6).
- `--no-external-generators` — skip external scaffolders like `nuxi init` (G4 soft).

Other built-in checkpoints: the **whole-plan preview** (init shows the full plan +
one aggregate confirm before any write — decline = abort, nothing written; CI
prints + proceeds); a **destructive-overwrite** gate on re-run (a write that would
clobber locally-edited files is hard-gated; CI safe-skips and preserves them); and
an **informational cross-module conflict** warning when two modules write the same
shared file. An `init_only` gate (the pin-review) does not re-prompt on plain
reproduce — the frozen decision is already consented and replays byte-identically;
`--refresh` re-arms it.

## Module sources and bolting on modules

Base modules ship bundled (always present). Users add more by dropping a module
directory into a module root, or by declaring a git/path **source** in
`~/.config/project-setup/config.toml` or the project's `.project-setup/sources.toml`.
Home config is a personal **catalog + default answers only** — it is never
authoritative for a project; the committed project files are. A module from a
remote source runs arbitrary code (same trust surface as any plugin) — only add
sources you trust.

To author a module, see `runner/` (the SDK) and any bundled module as a template:
a directory with `module.toml` + a fixed `module.py` (+ optional `templates/`,
`steering/`, `test_*.py`). The manifest declares `[meta]`, `[module]` (id, name,
version, description, reconcile), `[order]` (requires/after/before — no priority),
`[tools]` (required only), `[[inputs]]`, and `[[steps]]`.

## The bundled module set

- **Base (always enabled):** core-identity, dirs-scaffold, gitignore-generate,
  license-write, agents-md, git-init.  These run on every project; they cannot
  be deselected.
- **Optional (opt in):** apm-install, codex-config, github-repo, justfile-write,
  precommit-setup, quality-hooks, lang-ts, lang-python, lang-go, lang-rust,
  speckit-bridge, package-add.

## Module selection (FR-005)

Before running the pipeline for a new project, you MUST conduct module selection:

1. **Grill the user on intent** — ask what the project does, its language/stack,
   whether it needs CI tooling, APM/SpecKit, GitHub repo creation, etc.  Do not
   accept vague answers; ask follow-up questions until you have enough signal to
   propose a concrete set.

2. **Propose an enablement set with rationale** — list the optional modules you
   recommend enabling, each with a one-line reason (e.g. "lang-python: Python
   project; precommit-setup: you mentioned wanting linting; github-repo: you
   want the repo auto-created").  Start from the base set and add only what
   fits the intent.

3. **Confirm with the user** — show the final proposed set (base + optional) and
   ask for explicit approval.  The user may add or remove modules.

4. **Pass the selection to the runner** — supply the confirmed list as the
   ``enabled`` answer in the ScriptedIO / CLI invocation so the pipeline records
   it.  The runner persists it as ``[modules].enabled`` in
   `.project-setup/answers.toml` so clones reproduce the exact set.

**In reproduce mode** the committed enablement set is authoritative — do not
re-propose modules; replay exactly what is recorded.

**In non-interactive/CI mode** with no committed selection, the runner runs the
base set only (safe default — no optional modules auto-run).

## Secrets guardrail (non-negotiable, enforced)

NEVER accept a secret (API key, token, password, private key) as an input value.
This is **enforced in code** (G8): an answer matching a known credential shape
(`ghp_`, `sk-`, `AKIA`/`ASIA`, `glpat-`, `xox[baprs]-`, PEM private keys) is
refused at the interview boundary — dropped, never written to
`.project-setup/answers.toml`, and a required input then fails as
`MISSING_ANSWER`. If a user supplies a secret, tell them it is now **compromised
and must be rotated**; secrets belong in the runtime environment or a secret
manager. The matcher is shape-scoped (no entropy heuristic) to avoid false
positives; an input may declare `allow_secret = true` to opt out for a
legitimately secret-shaped non-secret value.

## Safe execution & failure handling

- A single module or source failure is reported and the run continues; it does
  not abort the whole setup. A re-run reaches the intended end state.
- The validate-closed gate is the only hard stop before writes — if it fails,
  read its structured errors (each has `how_to_fix`) and fix the answers/sources,
  then re-run. Do not try to bypass the gate.
- If a step's error names a missing tool, install the tool or disable the module;
  do not hand-fake the output.

## What "done" means

- The validate-closed gate passed (no `MISSING_ANSWER` / `MISSING_REQUIRES` /
  cycle / `MISSING_REQUIRED_TOOL`).
- Every enabled module's steps ran (or were confirmed-skipped); failures were
  reported, not hidden.
- `.project-setup/sources.toml` and `.project-setup/answers.toml` are written and
  committed.
- The observable scaffold matches the answers (the per-module functional tests
  encode this; run `uv run --with pytest pytest -q .../tests/` to verify).

## Checking validity

- Per-module functional tests (`test_*.py`) assert that on-disk state matches the
  recorded answers — run them after building or changing a module.
- The baseline parity test proves the base bundle reproduces the expected
  scaffold and is byte-identical across runs.
