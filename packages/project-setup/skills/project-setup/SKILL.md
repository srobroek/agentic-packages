---
name: project-setup
description: Set up, scaffold, bootstrap, spin up, stand up, or initialize a NEW project or repository — for any language or framework (Python, FastAPI, TypeScript, Go, Rust, etc.). Use whenever the user wants to start/create/spin up/stand up/build/make/"get going" a new project, service, API, app, or repo — e.g. "set up a project", "start a new project", "spin up a FastAPI service", "create a new <language/framework> app", "scaffold a repo", "initialize a repo", "make a new project" — or adds a monorepo package, or re-runs setup to fix drift. A generic, config-driven runner that SCAFFOLDS (it does not deploy or release): every capability (git, GitHub, dirs, pre-commit, license, gitignore, CI, README, env, APM/MCP, SpecKit, language overlays) is a discoverable module.
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

**There is ONE entrypoint — invoke it; do NOT inspect the internals.** The runner is
the source of truth for orchestration. Do **not** read `runner/*.py`, `module.py`,
`executor.py`, or any module source to "understand how it works" or to plan execution —
that wastes time and is unnecessary. You only ever run this one command:

```
uv run <plugin-root>/skills/project-setup/runner/cli.py --project-dir <dir> [flags]
```

`<plugin-root>` is this skill's directory (resolved at runtime via `${PLUGIN_ROOT}`).
There are **no per-script parameters and no legacy `.sh` scripts** — the project's
answers are NOT passed as CLI arguments; the runner collects them in the interview and
freezes them to `.project-setup/answers.toml`. The complete flag set is:

| flag | meaning |
|---|---|
| `--project-dir <dir>` | the project directory to set up (default `.`) |
| `--non-interactive` | no prompts; use defaults + committed answers only (CI) |
| `--dry-run` | run the interview + build the plan but write nothing |
| `--skill-version <v>` | advisory version string recorded in `sources.toml` |
| `--refresh <module[.key]>` | reproduce only: re-research the named agent decision(s); repeatable |
| `--allow-public-repo` | CI opt-in: create a PUBLIC GitHub repo (G3 hard gate) |
| `--allow-install` | CI opt-in: run the batched `apm install` (G2 supply-chain gate) |
| `--allow-stack-write` | CI opt-in: write agent-researched dependency pins (G6) |
| `--no-external-generators` | CI opt-out: skip external scaffolders like `nuxi init` (G4 soft) |

If a step fails, read its structured error (each carries `how_to_fix`) — do not read the
runner source to diagnose it. The runner executes a fixed pipeline:

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

## Scope: this skill SCAFFOLDS — it does NOT build the product

**Hard boundary. Read this before running anything.** project-setup creates a
project's *scaffold* and then STOPS. It is done when the runner's modules have run,
the answers are frozen, and `.project-setup/` is committed — at that point you
**hand off to the user**, you do not keep building.

**In scope** (only what bundled MODULES produce): directory structure, `.gitignore`,
`LICENSE`, `AGENTS.md`, pre-commit config, `justfile`, the CI workflow YAML,
`.env.example`, `STACK.md`, a pinned dependency manifest + toolchain (e.g.
`pyproject.toml` + `uv`), a README *draft*, and any agent-steered *decisions* frozen
to `answers.toml`.

**Out of scope — do NOT author any of this:** application source code, business
logic, ORM models, endpoint/route handlers, database schemas, hand-written
migrations, or a test suite. Those are the user's product work, not setup. A pinned
`pyproject.toml` is in scope; the FastAPI app that uses it is not. A CI workflow that
runs `pytest` is in scope; writing the tests it runs is not.

**When the modules have run, STOP and print a concise handoff**: what was scaffolded,
and the next steps the user takes (e.g. "write your app under `src/`, add tests under
`tests/`, run `just test`"). Do NOT invent a post-scaffold "I'll fill in the app now"
phase — there isn't one. If you find yourself writing `.py`/`.ts` source modules,
models, routers, migrations, or test files, you have exceeded scope: stop.

## How to ask the user (one question at a time, always an escape hatch)

This governs EVERY choice you surface — modules, marketplace packages, MCP servers,
leaf/sub-packages, language overlays, versions, anything. Three rules:

**RULE 1 — ONE question at a time.** Ask a single question, wait for the answer, then ask
the next. Do NOT batch several decisions into one multi-question prompt, and do NOT fire a
stack of choice-prompts at once. Each decision is its own turn — this keeps the interview
legible and lets earlier answers shape later questions.

**RULE 2 — A menu/choice prompt is fine** (for any number of options, including small
ones). Use it to present the choices clearly. Recommend a sensible default and label it.

**RULE 3 — ALWAYS include an "another option" / "other" escape** so the user is never
limited to only the shown choices — they can always type their own answer or ask to see
more. This matters most when there are MORE options than the menu can show (a menu caps at
~4 visible choices): then the menu MUST carry an explicit "Other / more options" choice,
AND you list the remaining options in your message text so the user can see the full menu
and name any of them via the escape. Never let the widget's size silently drop options the
user should know about.

**RULE 4 — present option sets as NUMBERED TABLES, grouped by category, selectable by
number.** For modules, packages, plugins, MCP servers, overlays — any set of options —
do NOT use loose bullet lists. Render markdown tables grouped into these categories (omit
a group if empty):

- **Mandatory** (always run, cannot be deselected) — show for transparency, not selectable.
- **Recommended** (your proposed defaults for this project).
- **Optional** (available, not recommended — the rest of the menu).
- **Not applicable** (excluded for this project, with the reason — e.g. other languages).

Number the rows in a single continuous sequence across the selectable groups so the user
can answer by number. Each table: `#`, name, and a one-line reason/what-it-does. Then ask
ONE question: which to enable — accept the recommended set, or give the numbers to
add/remove — and always allow a free-text "other" answer. Example shape:

```
Mandatory (always run)
| name | what it does |
| core-identity, dirs-scaffold, gitignore-generate, license-write, agents-md, git-init | base scaffold |

Recommended for a FastAPI service
| # | module | why |
| 1 | lang-python      | Python overlay: pins 3.13, uv + pyproject.toml |
| 2 | precommit-setup  | ruff lint/format enforced on commit |
| 3 | justfile-write   | run/test/lint task shortcuts |

Optional (available)
| #  | module | what it does |
| 4  | quality-hooks    | extra agent quality hooks |
| 5  | github-repo      | create + push a GitHub repo |
| 6  | apm-install      | install agentic (APM) packages |
| 7  | codex-config     | write .codex/ config |
| 8  | speckit-bridge   | SpecKit spec-driven workflow |
| 9  | mcp-config       | configure MCP servers |
| 10 | env-example      | .env.example from the stack |
| 11 | stack-adr        | STACK.md decision record |
| 12 | ci-github-actions| CI workflow sized to the stack |

Not applicable here
| module | reason |
| lang-ts / lang-go / lang-rust | project is Python |

→ Enable the recommended set (1–3)? Or reply with numbers to add/remove (e.g. "1,2,3,5"),
or describe anything else you want.
```

For a long marketplace package list, same idea: number every package in tables; the user
picks by number; an "other / type a package not listed" answer is always available.

## Module selection (FR-005)

Before running the pipeline for a new project, you MUST conduct module selection:

1. **Grill the user on intent** — ask what the project does, its language/stack,
   whether it needs CI tooling, APM/SpecKit, GitHub repo creation, etc.  Do not
   accept vague answers; ask follow-up questions until you have enough signal to
   propose a concrete set.

2. **Detect marketplaces and offer sources (do NOT assume one).** This skill is
   marketplace-agnostic and ships with NO default marketplace. If the project will
   use agentic packages (APM packages, MCP servers, speckit), call
   `sdk.detect_marketplaces()` (reads `~/.apm/marketplaces.json`,
   `~/.claude/plugins/known_marketplaces.json`, `~/.codex/config.toml` offline) and:
   - **Present the detected marketplaces by name** and ask which to use for package
     installs, AND ask whether the user wants to add any other marketplace.
   - **If none is detected and the user names none**, offer the canonical PUBLIC
     upstreams (spec-kit via `uvx`/`uv tool`, MCP servers via `npx` — `mcp-config`)
     at the relevant gate, or skip package installs entirely (pure scaffolding).
   - **Never push a specific org's marketplace.** The chosen marketplace + package
     list are recorded as frozen answers (e.g. `apm-install.marketplace` /
     `agentic_packages`, `mcp-config.mcp_servers`, `speckit-bridge.speckit_source`).
   Detection runs ONCE at init and the *choice* is frozen; reproduce replays the
   frozen choice and never re-detects.

   **Version choices (FR-V1–FR-V4).** After the user picks their packages and
   sources, default ALL installable packages to `latest` — never carry a
   hardcoded pin. Then offer a per-package version override: "Pin any package to
   a specific version? Leave blank to use latest for all." For packages left at
   `latest`, ask whether the user wants **latest-always** (freeze the literal
   `"latest"` — clones re-resolve to the newest release at clone time; this is
   the default, matching one-time scaffolders like `nuxi@latest`) or
   **latest-today** (resolve the current version NOW and freeze that concrete
   number — clones get the identical build). Record the answers as frozen inputs:
   `speckit_version` (for speckit-bridge), `mcp_versions` as `"name=version
   name2=version2"` (for mcp-config), and version-bearing locators for
   apm-install. A concrete version → identical install on reproduce;
   `"latest"` → latest-at-clone-time (documented, intentional exception to
   byte-identity for one-time external installs).

3. **Propose an enablement set as NUMBERED TABLES** (see "How to ask the user" RULE 4):
   present Mandatory / Recommended / Optional / Not-applicable tables, rows numbered in
   one continuous sequence, each with a one-line reason. Then ask ONE question — accept
   the recommended set or give numbers to add/remove, with a free-text "other" always
   available. Start from the base set and add only what fits the intent. The SAME table
   format applies when the chosen marketplace exposes many packages/leaf packages: number
   every package in tables, select by number, "type one not listed" always available —
   one question at a time, never several prompts at once.

4. **Confirm with the user** — show the final proposed set (base + optional) and
   ask for explicit approval.  The user may add or remove modules.

5. **Pass the selection to the runner** — supply the confirmed list as the
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

**If a step or the runner fails, STOP — do not work around it.** Report to the user
exactly what failed (the step/module + its structured error and `how_to_fix`) and ask
for follow-up instructions. Do **not** get creative: do not hand-install packages the
runner couldn't, do not hand-edit generated files (`apm.yml`, manifests, etc.) to route
around a failure, do not inspect the runner/module source to invent a fix, and do not
substitute your own implementation for what a step was supposed to produce. A failed
step is a signal to pause and consult the user, not a problem for you to solve
autonomously. The user decides whether to retry, skip the module, fix the environment,
or abort.

- A single module or source failure is reported by the runner and the run continues
  past it where the runner is designed to (non-fatal steps); it does not silently
  abort the whole setup. Still: surface every failure to the user — never bury it.
- The validate-closed gate is the only hard stop before writes — if it fails, report
  its structured errors (each has `how_to_fix`) to the user and ask how to proceed. Do
  not silently change answers/sources to force it closed, and do not bypass the gate.
- If a step's error names a missing tool, report it and ask the user whether to install
  the tool or disable the module — do not hand-fake the output and do not install
  arbitrary tooling on your own initiative.

## What "done" means

- The validate-closed gate passed (no `MISSING_ANSWER` / `MISSING_REQUIRES` /
  cycle / `MISSING_REQUIRED_TOOL`).
- Every enabled module's steps ran (or were confirmed-skipped); failures were
  reported, not hidden.
- `.project-setup/sources.toml` and `.project-setup/answers.toml` are written and
  committed.
- The observable scaffold matches the answers (the per-module functional tests
  encode this; run `uv run --with pytest pytest -q .../tests/` to verify).
- **You STOP here and hand off.** Print what was scaffolded + the user's next steps;
  do not continue into authoring application code, tests, or migrations (see "Scope").

## Checking validity

- Per-module functional tests (`test_*.py`) assert that on-disk state matches the
  recorded answers — run them after building or changing a module.
- The baseline parity test proves the base bundle reproduces the expected
  scaffold and is byte-identical across runs.
