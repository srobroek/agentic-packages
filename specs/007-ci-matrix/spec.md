# Feature Specification: CI Matrix Sized to Stack

**Feature Branch**: `feat/project-setup-modular-redesign` (continues) → likely a
dedicated `feat/ci-matrix` branch

**Created**: 2026-06-28

**Status**: **Implemented (2026-06-29)** — new `ci-github-actions` module shipped + a
small additive runner change. Full suite 731 passed, 4 deselected. A premise check before
build found the CI agent could NOT see other modules' frozen answers (the runner gave an
agent only its OWN answers), which 007's "size the matrix to the actual stack" depends on;
RESOLVED (user) with a backward-compatible runner change: the Phase-A agent context now
carries a read-only `all_answers` snapshot (Settled Decision C/I/Assumption-4 now
supported). OQ leans applied: no live GitHub API probe (OQ-1), flat `ci_plan_*` keys
(OQ-2), single-version matrix (OQ-3). See `memory.md` → AS-BUILT and
`reviews/autonomous-drive-decision-log.md`.

**Input**: Roadmap rank #5 `ci-matrix-sized-to-stack` in
`reviews/tier2-agentic-features-roadmap.md:59-63`.

## Overview

The 001 runner, 003 stack-resolver, and 004 gates established the full Tier-2
machinery: agent decides a frozen structured decision, gate shows it, python writes
deterministically from the frozen answers via `idempotent_write`. The justfile-write
module (modules/justfile-write) writes a `justfile` with named recipes; the lang-*
overlays resolve and pin the project's tech stack. **Nothing writes a CI workflow.**

This feature adds `ci-github-actions` — a new, dedicated module — that synthesizes a
`.github/workflows/ci.yml` sized to the project's actual stack:

> The **agent** reads the frozen answers (languages, frameworks, pinned runtime
> versions, package manager) from prior modules and synthesizes a **`ci_plan`**: a
> structured decision containing the job graph (job ids, runner, per-job steps),
> the OS/runtime matrix (only the runtimes the stack actually needs), GitHub
> Actions action refs pinned to their **current major** (e.g. `actions/checkout@v4`,
> `astral-sh/setup-uv@v5`), and the commands to run in each job (validated against
> real justfile recipes and manifest scripts). The agent decides the CI architecture.
>
> A **gate** shows the rendered workflow YAML before any write — CI that runs on
> every push is consequential (deprecated node-runtimes, over-broad matrix burning
> minutes). User confirms.
>
> A **python** step reads the frozen `ci_plan`, drops any commands not found in the
> scaffolded justfile or manifest scripts (with a warning per dropped command),
> renders canonical YAML, and writes `.github/workflows/ci.yml` via
> `sdk.idempotent_write`.

**The determinism contract:** the agent decides once at init (research: current
action majors, supported runtime versions for the language). The python step is fully
mechanical: same `ci_plan` → identical YAML bytes. Action majors are persisted in
`answers.toml`, so "the current v4 became v5" is a deliberate `--refresh`, not a
silent drift. Reproduce replays zero-network.

**Why a new module (not a step on lang-*)?** CI YAML is a cross-cutting, independent
artifact that concerns every language overlay equally, that a project may want even
without a lang-* overlay (just a justfile + precommit), and whose correctness depends
on the FULL set of resolved answers — not just Python or TS in isolation. A standalone
module reading the frozen answer set is the right boundary.

## Current state (verified — citations, do not re-derive)

All file:line references verified against shipped code on
`feat/project-setup-modular-redesign` at HEAD `7779c27`.

- **No CI workflow module exists.** The modules directory
  (`packages/project-setup/skills/project-setup/modules/`) contains: agents-md,
  apm-install, codex-config, core-identity, dirs-scaffold, git-init, github-repo,
  gitignore-generate, justfile-write, lang-go, lang-python, lang-rust, lang-ts,
  license-write, package-add, precommit-setup, quality-hooks, speckit-bridge. No
  `ci-github-actions` module exists. The `ci-github-actions` module is fully net-new.
- **The justfile-write module writes a skeleton justfile with six recipes.** The
  verbatim body is defined in
  `modules/justfile-write/module.py:27-49` as `_JUSTFILE`, containing recipes:
  `default`, `test`, `lint`, `build`, `dev`, `clean`. The test/lint/build/dev/clean
  bodies are all `TODO` stubs. The `lint` recipe invokes `pre-commit run --all-files`
  (line 34). No other recipe is wired to a real command by the skeleton alone.
- **`use_just` is the justfile-write input key.** `modules/justfile-write/module.toml:19`
  declares `key = "use_just"`, `type = "bool"`, `default = true`. A CI module can
  read this answer from the frozen plan to know whether to validate commands against
  the justfile.
- **The lang-python module pins exact versions into pyproject.toml.** Its `write`
  step reads `pinned_deps`, `dev_deps`, `python_version`, `ruff_version` from the
  frozen plan (`modules/lang-python/module.py:281-286`). A CI module can read
  `python_version` to size the matrix.
- **The lang-ts module pins exact versions + a package manager into package.json.**
  Its `module.toml:19-38` declares inputs `target`, `package_manager` (choice:
  `bun`/`pnpm`, default `bun`), `framework`, `ui_kit`. A CI module reads
  `package_manager` to pick the correct install step.
- **`FrozenInputs` has a `.mode` property.** `runner/sdk.py:87-91` — `mode` returns
  `"init"` or `"reproduce"` from the frozen plan. The CI module uses this to gate
  registry lookups for action major verification (init only, zero-network on
  reproduce), matching the lang-* pattern.
- **`sdk.verify_pins` is the shared MCP-free registry helper.** `runner/sdk.py:315-380`
  — takes `pins: list[str]` and `ecosystem: "pypi" | "npm"`. No equivalent helper
  exists for GitHub Actions version probing, so action-major pinning uses agent
  knowledge + steering guidance (see Settled Decision D).
- **The gate step shape supports `hardness`, `allow_flag`, `init_only`, and
  `when`.** `runner/manifest.py:60-71` — fully available since spec 004. The CI gate
  uses `hardness="hard"`, `allow_flag="allow-ci-write"`, `init_only=true` (same
  rationale as the lang-* pin gate: the frozen decision is consented once at init;
  reproduce replays byte-identically without re-prompting).
- **`sdk.idempotent_write` supports `reconcile=True`.** `runner/sdk.py:182-257` —
  writes the file if absent (`create`) or overwrites if content differs (`modify`)
  when `reconcile=True`. CI YAML should reconcile on re-run so it always matches the
  frozen plan.
- **The two-phase plan is in place (spec 003 FR-011).** All `kind=agent` steps run in
  Phase A before any `kind=python` step runs in Phase B. The CI module's agent step
  therefore has access to all prior-module frozen answers (lang-python pins,
  lang-ts package manager, justfile presence) when the plan is re-frozen after
  Phase A.
- **The `{decision}` gate token is in place.** `runner/plan.py:159-168` replaces
  `{decision}` in a gate message with `render_answer_block(mod_answers)` at freeze
  time. The CI gate uses this to embed the rendered `ci_plan` (jobs + matrix + action
  refs + commands) in the gate message so the user can review the full YAML plan
  before confirming.
- **`append_if_absent` exists but is not needed here.** `runner/sdk.py:498-532` —
  CI YAML is a single authoritative file, not an append target. `idempotent_write`
  with `reconcile=True` is the correct primitive.
- **`run_tool` is the shared external-command helper.** `runner/sdk.py:450-495` —
  used by lang-python to invoke `uv add`; the CI module does NOT need `run_tool`
  (it writes YAML, it does not run CI tools). Pure `idempotent_write` write.
- **Module ordering uses `after` and `requires` in `[order]`.** lang-python
  `module.toml:16` declares `after = ["gitignore-generate", "precommit-setup"]`.
  The CI module must declare `after = ["justfile-write", "lang-python", "lang-ts",
  "lang-go", "lang-rust"]` (it is a consumer of their answers; the `after`
  constraint lets the resolver read all resolved lang answers at Phase-A agent time).
- **No GitHub Actions version-probe utility exists in the runner or any module.**
  No `urllib` call to the GitHub API or `api.github.com/repos/{owner}/{repo}/releases`
  exists anywhere in the codebase. Action major pinning is therefore agent-knowledge
  at init, not a live API probe (see OQ-1 for whether a live probe should be added).

## Settled decisions

Letters restart at A for this spec.

- **A — New standalone module `ci-github-actions`, not a step on lang-*.** CI YAML
  is cross-cutting (it covers all active overlays, plus a justfile-only project with
  no lang-* overlay), and its correctness depends on the FULL resolved answer set
  from prior modules. A dedicated module reading the frozen plan is the right scope
  boundary. It is `default_enabled = false` (opt-in): projects that want to manage
  their own CI should not get a generated workflow.
- **B — Agent decides the full `ci_plan`; python validates and writes.** Following
  the exact Tier-2 pattern (003 Settled Decision B): the agent emits a frozen
  structured decision as `agent-steered` answers — `{jobs, matrix, action_refs,
  commands_by_job, rationale}`; the python step reads it from the frozen plan,
  validates commands, renders YAML, and writes via `idempotent_write`. The agent
  NEVER writes files and NEVER emits action ref ranges like `actions/checkout@v*`.
- **C — The agent's job graph is sized to ACTUAL stack only.** The agent reads the
  frozen answers for active language overlays (python_version, package_manager,
  etc.) and emits ONLY the jobs the stack needs. A Python-only project gets one CI
  job; a Python+TS project gets two. No matrix entry is added for a language not in
  the frozen answer set. Over-broad matrices burn minutes — this is explicitly called
  out in the roadmap gate rationale (roadmap:62).
- **D — Action majors are pinned to current majors at agent-research time (init),
  NOT probed live.** No new HTTP client is added to the runner for GitHub API probing
  (the SDK already has `verify_pins` for pypi/npm; a GH Actions API surface would
  be a disproportionate addition). The agent's steering doc instructs it to use
  context7 / whats-new tools if available to confirm current majors, then emit exact
  `owner/action@vN` refs. These are persisted in `answers.toml` so drift from "v4
  became v5" is intentional (`--refresh ci-github-actions`), never silent. The agent
  MUST NOT emit floating refs like `@main` or `@master` — only `@vN` major pins.
- **E — Python validates commands against justfile recipes and manifest scripts
  before writing.** Every command string in `ci_plan.commands_by_job` is checked:
  (a) if it starts with `just `, the recipe name must exist in the on-disk `justfile`
  (parsed by line-prefix scan, not exec); (b) if it references a `package.json`
  script, the script key must exist in `package.json`; (c) if it is a bare shell
  command (`uv run`, `cargo test`, `bun test`), it is passed through without
  validation (no attempt to exec it). Unknown `just <recipe>` commands are DROPPED
  with a warning (not a hard error), so CI never references a recipe that does not
  exist. This is the key correctness guarantee the roadmap calls out
  (roadmap:61-62: "validates every command against real justfile recipes/manifest
  scripts").
- **F — The gate is hard + init-only.** Same rationale as the lang-* pin gate
  (004 G6): the agent researched + decided the CI matrix and action refs (non-
  deterministic judgment), so a human consents before the deterministic write turns
  it into a reproducible, push-triggering artifact. On plain reproduce the frozen
  decision is already consented; the gate auto-proceeds without re-prompting
  (`init_only=true`, 004 FR-006a). Only `--refresh ci-github-actions` re-arms the
  gate. CI must pass `--allow-ci-write` to perform the write at init.
- **G — YAML is rendered by a pure-python canonical renderer, not a template.** CI
  YAML has a well-defined structure (a dict with `on:`, `jobs:` sections); the python
  step renders it deterministically from the frozen `ci_plan` using stdlib only
  (no PyYAML dependency — the module has `dependencies = []` per the `# ///` header
  convention). The renderer produces a canonical output: keys in deterministic order,
  two-space indent, explicit `true`/`false`. Same frozen `ci_plan` → identical bytes.
- **H — `reconcile = true` for the module.** The CI workflow is always overwritten
  to match the frozen plan on re-run. Unlike justfile (which is `reconcile=false` —
  write-once to preserve hand edits), a generated CI workflow should stay in sync
  with the frozen stack decisions; hand-editing a generated workflow is the anti-
  pattern the gate prevents.
- **I — The module declares `[order] after` the lang-* modules and justfile-write.**
  The agent step runs in Phase A and reads the frozen answers from all prior modules
  via its context dict (the two-phase plan, 003 Settled Decision H). The `after`
  constraint ensures the answer set is complete when the agent runs. No `requires`
  constraint on lang-* — the module works on a project with no lang-* overlays
  (just a justfile-only skeleton), generating a minimal `lint` + `test` job.

## User Scenarios & Testing

### User Story 1 — Python-only project gets a single, correctly-sized CI job (Priority: P1)

A user enables `ci-github-actions` on a project where `lang-python` is also enabled.
The agent reads `python_version = "3.13"` and `use_just = true`. It emits a
`ci_plan` with one `test` job, a `3.13` matrix entry, `actions/checkout@v4`,
`astral-sh/setup-uv@v5`, and a `just test` command. The python step confirms `test`
is a real justfile recipe, renders the YAML, and writes `.github/workflows/ci.yml`.

**Acceptance Scenarios**:

1. **Given** `lang-python` enabled with `python_version = "3.13"` and `use_just =
   true`, **When** the agent step runs, **Then** it emits a `ci_plan` with exactly
   one job (no TS job, no matrix entries for unlisted Python versions), and all
   `action_refs` are in `owner/repo@vN` form (no floating refs).
2. **Given** the frozen `ci_plan`, **When** the python `write` step runs, **Then**
   it validates `just test` against the justfile (recipe exists → kept), renders
   canonical YAML, and writes `.github/workflows/ci.yml` via `idempotent_write`.
3. **Given** `use_just = false` (no justfile), **When** the python step runs, **Then**
   it skips the justfile-recipe validation and emits the commands the agent chose
   (bare tool commands like `uv run pytest`), without a `just` prefix.

### User Story 2 — Python+TS project gets two jobs without over-broadening (Priority: P1)

A user enables both `lang-python` and `lang-ts` (with `package_manager = "bun"`).
The agent emits two jobs: `test-python` (Python matrix, uv-based) and `test-ts`
(bun-based). The matrix has one Python version entry and one bun entry — no
gratuitous multi-version matrix unless the agent judged the project needs it.

**Acceptance Scenarios**:

1. **Given** `lang-python` + `lang-ts` enabled, **When** the agent emits the
   `ci_plan`, **Then** it contains exactly two jobs; the TS job uses `package_manager`
   = `"bun"` from the frozen answers (not a hardcoded fallback).
2. **Given** the rendered YAML, **When** a teammate reproduces, **Then** the YAML is
   byte-identical to the init output (zero network, frozen plan replay).

### User Story 3 — Unknown justfile recipe is dropped with a warning, not a hard error (Priority: P1)

The agent emitted a `just deploy` command in the CI plan, but `justfile` only has
`default/test/lint/build/dev/clean`. The python step drops `just deploy` from the
rendered YAML, appends a warning to the module result, and still writes the file with
the remaining valid commands.

**Acceptance Scenarios**:

1. **Given** a `ci_plan` whose commands include `just deploy` and a `justfile` that
   has no `deploy` recipe, **When** the python write step runs, **Then** `just deploy`
   is dropped, a `WARN: recipe 'deploy' not found in justfile — command dropped`
   warning is emitted, and the YAML is written with the remaining commands.
2. **Given** all commands are valid (all `just <recipe>` names exist), **Then** no
   warnings are emitted and the YAML contains all planned commands.

### User Story 4 — Gate shows the full rendered YAML before write; CI safe-skips without flag (Priority: P1)

At init the gate fires, showing the complete rendered `.github/workflows/ci.yml` YAML
in the gate message. The user reviews and confirms. In `--non-interactive` (CI) the
gate SAFE-skips the write unless `--allow-ci-write` is passed.

**Acceptance Scenarios**:

1. **Given** a frozen `ci_plan`, **When** the gate fires at init, **Then** the gate
   message contains the full rendered YAML (rendered from frozen answers, not a
   summary) and confirms once.
2. **Given** `--non-interactive` at init, **When** the gate step executes, **Then**
   the write is SAFE-skipped (no YAML file written) and the manual command is printed;
   **Given** `--non-interactive --allow-ci-write`, **Then** the write proceeds.
3. **Given** a plain reproduce (no `--refresh`), **When** the gate step executes,
   **Then** the gate auto-proceeds without prompting (`init_only=true` bypass, 004
   FR-006a) and the YAML is written byte-identically.

### User Story 5 — `--refresh ci-github-actions` re-researches action majors + re-gates (Priority: P2)

Six months later, `actions/checkout` shipped v5. The user runs
`--refresh ci-github-actions`. The agent re-researches current action majors, emits
an updated `ci_plan`, the gate shows a diff (old `@v4` → new `@v5`), and on confirm
the YAML is updated.

**Acceptance Scenarios**:

1. **Given** a committed `ci_plan` with `actions/checkout@v4`, **When**
   `--refresh ci-github-actions` runs, **Then** the agent re-researches action
   majors; if a newer major exists the gate shows an old→new diff and prompts.
2. **Given** the user declines the refresh diff, **Then** the committed `ci_plan`
   is preserved unchanged and the YAML is not modified.

### User Story 6 — No lang-* overlays: justfile-only project gets a minimal lint job (Priority: P2)

A user enables `ci-github-actions` with `use_just = true` but no lang-* overlays.
The agent emits a single `lint` job using `actions/checkout@vN` + `just lint`.
No language-specific setup actions appear.

**Acceptance Scenarios**:

1. **Given** no lang-* overlays enabled and `use_just = true`, **When** the agent
   emits the `ci_plan`, **Then** it contains exactly one job (`lint`) with no
   language matrix and no language-setup action.
2. **Given** neither `use_just` nor any lang-* overlay, **When** the agent emits the
   `ci_plan`, **Then** it emits an empty-or-minimal plan and the python step writes
   a minimal YAML with only `on:` triggers and an empty `jobs:` section, with a
   warning that no executable jobs were synthesized.

### Edge Cases

- **A `ci_plan` with zero valid commands after validation**: the python step writes
  a YAML with the job present but no `steps:` commands, appends a warning, and still
  emits `status="ok"` (the file is a valid, if minimal, workflow). A YAML with NO
  jobs at all is not written — the step emits `status="ok"` with `files_written=[]`
  and a warning.
- **`reconcile=True` on re-run over a hand-edited `.github/workflows/ci.yml`**: the
  004 G5 overwrite gate fires (on-disk content diverges from the deterministic re-
  render of frozen answers); in CI it SAFE-skips, preserving local edits. The CI
  module does not need to implement this — it is enforced by the runner's existing
  G5 machinery.
- **A `ci_plan` where `action_refs` contains a floating ref** (`@main`, `@master`,
  no `@v`): the python step REJECTS the ref as invalid (`INPUT_VALUE_INVALID` on
  that specific ref), substitutes a `FIXME` placeholder comment in the YAML, and
  appends a warning. It does not hard-error the whole write (the remaining jobs are
  still useful).
- **Agent emits a matrix with more runtime versions than the frozen stack answer**
  (e.g. Python `[3.11, 3.12, 3.13]` when `python_version = "3.13"`): the python step
  trims the matrix to the frozen `python_version` only and warns. The determinism
  boundary is binding: the frozen answer is the source of truth for the matrix, not
  the agent's broader proposal.
- **`use_just = false` but agent emits `just` commands**: the python step detects
  the mismatch (justfile does not exist), drops ALL `just *` commands, and warns.
  The job is written with whatever non-`just` commands remain.
- **`lang-ts` enabled but no `package.json` exists at write time** (e.g. the TS
  scaffolder was skipped via G4): the package.json-script validation step silently
  skips script-existence checks (file absent → treat all non-just commands as
  unvalidatable pass-throughs) and warns.

## Requirements

### Module structure

- **FR-001**: A new module directory `modules/ci-github-actions/` MUST be created
  with `module.toml`, `module.py`, and a `steering/` subdirectory containing the
  agent steering document. No `templates/` directory is needed (YAML is rendered
  programmatically, not from templates — Settled Decision G).
- **FR-002**: `module.toml` MUST declare `id = "ci-github-actions"`,
  `default_enabled = false`, `reconcile = true`. The `[order]` section MUST declare
  `after = ["justfile-write", "lang-python", "lang-ts", "lang-go", "lang-rust"]`
  so the frozen answers for all lang-* overlays are available in the agent's context
  dict at Phase-A time (003 Settled Decision H / two-phase plan).
- **FR-003**: `module.toml` MUST declare the following inputs (in addition to any
  impl-detail ones needed for the `ci_plan` storage):
  - `ci_trigger` (type `multichoice`, choices `["push", "pull_request",
    "workflow_dispatch"]`, default `["push", "pull_request"]`, required `false`) —
    which GitHub event triggers the workflow.
  - `default_branch` (type `string`, default `"main"`, required `false`) — the
    branch the push trigger targets.
  - Agent-steered answers (`ci_plan_jobs`, `ci_plan_action_refs`, `ci_plan_matrix`,
    `ci_plan_commands`) are stored as `agent-steered` provenance and accessed via
    `inputs.get_list` / `inputs.get_str` in the python step — they are NOT declared
    as `[[inputs]]` in the toml (they are emitted by the agent and folded via
    `merge_module_answers_to_persist`).

### Agent step (resolve)

- **FR-004**: The `[[steps]]` array MUST include a `kind=agent` step with
  `id = "resolve"` and `steering = "steering/resolve.md"` as its FIRST step.
- **FR-005**: The steering document MUST instruct the agent to:
  (a) read the frozen answers for all active language overlays from its context dict
  (`python_version`, `package_manager`, `use_just`, active lang-* module ids, etc.);
  (b) emit a `ci_plan` as `agent-steered` answers covering: job ids + per-job
  runner (`ubuntu-latest`), the OS/runtime matrix (sized to ACTUAL active
  stack only), action refs pinned to `owner/repo@vN` current-major form (no
  floating refs), and the list of commands per job;
  (c) instruct the agent to use context7 / whats-new tools if available to verify
  current action major versions, then use agent knowledge if tools are absent;
  (d) MUST NOT emit floating action refs (`@main`, `@master`, unversioned), version
  ranges, or `latest`-style refs.
- **FR-006**: The agent MUST leave the matrix minimal: one entry per frozen language
  version. It MUST NOT generate a multi-version matrix unless the user explicitly
  requested it via `ci_trigger` or a future `ci_matrix_versions` input. Over-broad
  matrices that burn minutes are a binding anti-goal (roadmap:62).

### Gate step (ci-review)

- **FR-007**: The `[[steps]]` array MUST include a `kind=gate` step with
  `id = "ci-review"`, `hardness = "hard"`, `allow_flag = "allow-ci-write"`,
  `init_only = true`, placed AFTER the `resolve` agent step and BEFORE the `write`
  python step.
- **FR-008**: The gate `message` MUST contain the `{decision}` token so the full
  rendered `ci_plan` (jobs, matrix entries, action refs, commands) appears in the
  gate before the write. The gate message MUST NOT be a static summary — it must be
  dynamically composed from the frozen answers at plan re-freeze time (the existing
  `{decision}` / `render_answer_block` mechanism, 003 AS-BUILT point 2).
- **FR-009**: In `--non-interactive` at init the gate MUST SAFE-skip the write
  unless `--allow-ci-write` is in the active flags (hard gate, 004 FR-003). On
  plain reproduce the gate MUST auto-proceed without prompting (`init_only = true`,
  004 FR-006a). Only `--refresh ci-github-actions` re-arms the gate prompt.

### Python write step

- **FR-010**: The `[[steps]]` array MUST include a `kind=python` step with
  `id = "write"` placed AFTER the gate step.
- **FR-011**: The `write` step MUST read the frozen `ci_plan` answers from the
  frozen plan via `sdk.load_frozen_inputs`, validate commands (FR-012), render
  canonical YAML (FR-013), and write `.github/workflows/ci.yml` via
  `sdk.idempotent_write(reconcile=True)`. It MUST use stdlib only (no `pyyaml`
  or third-party dependencies — the `# /// script` header MUST have
  `dependencies = []`).
- **FR-012 — Command validation**: For every command string in `ci_plan.commands`:
  (a) if the command begins with `just `, the recipe name (the token after `just`)
  MUST be confirmed to exist in the on-disk `justfile` (parse by scanning for lines
  matching `^<recipe>:`, case-sensitive); a command referencing a missing recipe
  MUST be DROPPED from the rendered YAML with a `WARN: recipe '<name>' not found in
  justfile — command dropped` warning appended to the module result;
  (b) if the command references a `package.json` script (begins with
  `bun run <script>`, `pnpm run <script>`, `npm run <script>`), the script name
  MUST be confirmed to exist in `package.json` `scripts` (parsed via `json.loads`);
  a missing script MUST be DROPPED with a warning;
  (c) bare tool commands (`uv run`, `cargo test`, `go test`, `bun test`) are
  PASSED THROUGH without validation;
  (d) an action ref in `ci_plan.action_refs` containing no `@v` (floating ref)
  MUST be replaced with a `FIXME: <ref>` comment placeholder and a warning (not
  a hard error).
- **FR-013 — Canonical YAML renderer**: The python step MUST render the workflow
  YAML using a pure-stdlib dict-to-YAML serializer with: two-space indentation;
  deterministic key order (`name`, `on`, `env`, `jobs` at top level; within each
  job: `name`, `runs-on`, `strategy`, `steps`); YAML boolean `true`/`false` (not
  Python-style `True`/`False`); quoted strings for values that contain special YAML
  characters (`:`). The renderer MUST be a standalone function in `module.py`
  (no external library). Same frozen `ci_plan` + same module version → identical
  output bytes.
- **FR-014**: If the validated `ci_plan` produces zero jobs (all jobs' commands were
  entirely dropped, or the plan was empty), the python step MUST emit `status="ok"`,
  `files_written=[]`, and a warning message — it MUST NOT write an empty or invalid
  workflow YAML.
- **FR-015 — Matrix trimming**: If `ci_plan.matrix` for a Python job contains
  runtime versions other than the frozen `python_version` answer, the python step
  MUST trim the matrix to the single frozen version and append a warning. The frozen
  answer is the source of truth; the agent may only expand the matrix if a future
  `ci_matrix_versions` input explicitly authorises multiple versions. Same rule
  applies to other language runtimes.
- **FR-016 — Reproduce is zero-network**: In `inputs.mode == "reproduce"` the python
  step MUST NOT probe any registry, API, or network resource. All validation is
  performed against on-disk files only (justfile, package.json). This mirrors the
  lang-* pattern (`runner/sdk.py:87-91`; `modules/lang-python/module.py:296`).

### Determinism contract

- **FR-017**: The same frozen `ci_plan` answers MUST produce byte-identical
  `.github/workflows/ci.yml` on every run (same module version). This is the core
  Tier-1/Tier-2 contract: the agent decides once; python writes deterministically.
- **FR-018**: Action majors persisted in `answers.toml` MUST NOT be silently updated
  on plain reproduce. Re-derivation MUST require `--refresh ci-github-actions`
  (003 FR-010 / Settled Decision D). A plain reproduce that finds committed
  `ci_plan_action_refs` MUST replay them byte-identically.

## Success Criteria

- **SC-001**: A frozen `ci_plan` for a Python-only project (single `python_version`,
  `use_just = true`) produces a `.github/workflows/ci.yml` that references only the
  Python matrix entry, only `just test` and `just lint` (both verified to exist in
  the justfile skeleton), and action refs of the form `owner/repo@vN` — verified
  by a unit test with a scripted `ci_plan` and a stubbed justfile.
- **SC-002**: A frozen `ci_plan` for a Python+TS project produces two jobs; the TS
  job uses the `package_manager` value from the frozen answers (not a hardcoded
  default); verified end-to-end with a scripted `ci_plan` carrying both jobs.
- **SC-003**: A `ci_plan` containing `just deploy` where the on-disk justfile has
  no `deploy` recipe: `deploy` is dropped, a `WARN: recipe 'deploy' not found`
  warning is in the result, and the YAML does not reference `just deploy`; verified
  by a unit test with a minimal justfile stub.
- **SC-004**: The gate step is present in the frozen plan, is hard (`hardness="hard"`),
  carries `allow_flag="allow-ci-write"` and `init_only=true`; in `--non-interactive`
  without the flag the write is SAFE-skipped; with the flag the write proceeds;
  on plain reproduce the gate auto-proceeds without prompting — all verified by a
  test with a `ScriptedIO` double.
- **SC-005**: A floating action ref (`actions/checkout@main`) in the frozen
  `ci_plan.action_refs` is replaced with a `FIXME:` placeholder comment and a
  warning; the rest of the YAML is still written (not aborted) — verified by unit
  test.
- **SC-006**: Same frozen `ci_plan` rendered twice produces byte-identical YAML
  (determinism test — call the renderer function twice with the same input and
  assert `==`).
- **SC-007**: A reproduce run performs zero network calls (verified by a
  network-blocking test double, mirroring the lang-* reproduce test pattern).
- **SC-008**: A `ci_plan` that produces zero valid jobs (all commands dropped by
  validation) results in `files_written=[]` and a warning — no YAML file written.
- **SC-009**: The full existing test suite (613+ tests at 004 ship) remains green
  after the new module is added — no runner regressions.

## Out of Scope

- A multi-version CI matrix (testing Python 3.11/3.12/3.13 in parallel). 007 pins
  a single-version matrix from the frozen `python_version` answer. A
  `ci_matrix_versions` input or a matrix-expansion mode is deferred.
- CI platforms other than GitHub Actions (CircleCI, GitLab CI, Bitbucket Pipelines).
  The module id `ci-github-actions` is deliberate: it scopes to the one platform.
- Deployment, release, or publish jobs. 007 covers test + lint only. Release
  automation is a separate concern (not part of the project-setup scaffold).
- A live GitHub API probe for action version discovery. Action majors are pinned by
  agent research at init; drift is corrected via `--refresh`. A live probe would
  require a new authenticated API client and is disproportionate to the value here.
- The 004 G5 overwrite-gate interaction. G5 is handled by the existing runner
  machinery; the CI module does not need to implement divergence detection.
- Caching steps in the CI YAML (e.g. `actions/cache` for uv). This can be added
  by the user or a future iteration; 007 emits a functional but minimal workflow.
- Self-hosted runner support. The module always emits `runs-on: ubuntu-latest`.
- YAML syntax validation (running `yamllint` or similar). The renderer produces
  structurally valid YAML by construction; external lint is out of scope.

## Assumptions

- The 003 two-phase plan and the 004 gate machinery are in place and green (613+
  tests at 004 ship). The CI module is purely additive — it adds a new module that
  the existing runner dispatches using the same `kind=agent` / `kind=gate` /
  `kind=python` step machinery.
- The justfile-write skeleton's recipe names (`test`, `lint`, `build`, `dev`,
  `clean`, `default`) are stable across runs. If a user customises their justfile,
  the validation catches any new recipe names the CI module adds.
- Action ref format `owner/repo@vN` (where `N` is a decimal integer major version)
  is the canonical pinning form accepted by GitHub Actions. Patch/minor-pinned refs
  (`@v4.1.0`) are also valid and passed through without modification.
- `ubuntu-latest` is an acceptable runner for all generated jobs. Projects requiring
  macOS or Windows runners are out of scope for this spec.
- The `steering/resolve.md` document instructs the agent to prefer context7 /
  whats-new tools for action-major research, with agent knowledge as fallback (003
  Settled Decision C pattern: recommend MCP, do not depend on it).
- The existing `$PROJECT_DIR` env and `PYTHONPATH` wiring (005) are in place for the
  module subprocess invocation.

## Dependencies & Open Questions

**Hard dependency on 003 (stack resolver):** The CI module reads `python_version`,
`pinned_deps`, `package_manager`, and `framework` from the frozen answer set — these
are only populated when the lang-* overlays are active AND have completed their Phase-A
agent steps. The module works without lang-* overlays (generating a minimal workflow),
but its full value is realized when 003 has resolved the stack.

**Hard dependency on 004 (gates):** The `kind=gate` step uses `hardness`,
`allow_flag`, and `init_only` — all of which require the 004 gate-primitive
enrichment.

**Hard dependency on justfile-write module** (for command validation): The python
step validates `just <recipe>` commands against the on-disk justfile. If
justfile-write has not run (or `use_just=false`), the validation skips gracefully.

**Remaining open questions** (OQ-1…OQ-3) are in `memory.md`. None block authoring
the spec; they are design-detail decisions for planning/implementation.
