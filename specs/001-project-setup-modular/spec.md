# Feature Specification: Modular, Config-Driven project-setup

**Feature Branch**: `feat/project-setup-modular-redesign`

**Created**: 2026-06-27

**Status**: Draft (clarified — design decisions settled via a `grill-me` session)

**Input**: User description: "Modular, config-driven redesign of the project-setup bootstrap skill — make the skill generic, push all specific configuration out into auto-discovered modules + layered config, configurable via a home config file and env var, with install-time enable/disable, user-added modules, config overlay/merge, dynamic module sources, persisted answers, and deterministic repeatable results."

## Overview

`project-setup` is the bootstrap skill that scaffolds a new repository: directory
structure, git/GitHub, pre-commit hooks, license, agent steering files, APM
package install/compile, language overlays, and SpecKit. Today its executor is a
~1106-line shell monolith with eleven hardcoded steps, and every specific
choice — the interview questions, the directory set, the language list, the
tool toggles, the pre-commit hook set, the license texts — is baked into the
script or its reference docs. Adding any capability means editing the monolith,
its references, and its flag parser. The interview is free-form prose, so two
runs of the same setup can diverge.

This feature replaces that with a **runner + modules** architecture:

- **The runner** is the entire skill. It is generic Python (launched via `uv`),
  carrying zero project-specific configuration. It does one job:
  **resolve module sources → fetch/cache them → discover modules → conduct a
  manifest-driven interview → resolve execution order → validate → execute →
  persist answers**.
- **Everything else is a module** — git, GitHub, directories, pre-commit,
  license, .gitignore, AGENTS.md, APM install/compile, the SpecKit bridge, each
  language overlay, monorepo package-add, and even project identity. A module is
  a self-contained directory: a TOML manifest plus a Python entrypoint. The
  "base" scaffold is simply the bundle of modules marked enabled-by-default.

Specifics live in **modules** and **layered configuration**, never in the skill.
A person can drop in a new module (or point at a remote source of modules) and
have it discovered automatically; enable or disable any module; override
defaults through a layered config they own; and reproduce the exact same project
on any machine. The decisions a setup makes are **persisted in the project**
(committed), so re-runs are idempotent and a clone reproduces the project from
its own committed declarations — independent of any one machine's home config.

This is delivered as **one cohesive build** (no phased split). "Data-out-first"
survives only as an internal build order: extract the capabilities into modules,
then wire the generic runner around them.

## Architecture (settled decisions)

These decisions were resolved interactively and are the binding design contract
for planning. Detailed rationale lives in this feature's `memory.md`.

### A. Runner + modules; no capability core

- **A1**: The skill body IS the runner. The runner is generic and contains no
  project-specific payloads (no directory lists, language lists, tool toggles,
  pre-commit sets, license texts, or interview questions).
- **A2**: Every capability is a **module** — including project identity
  (`core-identity`) and monorepo package-add. There is no special-cased "core"
  of capabilities; "base" is the set of `default_enabled` modules, expressed as
  a bundle.
- **A3**: A module is a self-contained directory: a `module.toml` manifest
  co-located with a **Python** entrypoint (and any templates/assets it needs).
  Third-party module authors write Python, not shell.

### B. Language and runtime floor

- **B1**: The runner and all modules are **Python**. Shell (bash/sh) is dropped
  entirely; the prior bash-3.2.57 + BSD-tools portability floor and its
  shellcheck/bats tooling no longer apply to this package.
- **B2**: **`uv` is a hard prerequisite.** If `uv` is absent, the runner fails
  loudly with an install instruction. It never auto-installs `uv`, and there is
  **no standard-library fallback** path.
- **B3**: Dependencies are declared (a `pyproject`-style dependency set) and
  also available via PEP 723 inline script metadata resolved by `uv run`. The
  runner never assumes a parser the interpreter happens to have.
- **B4**: Tests are **pytest**, run via `uv run` (the repo's existing Python
  test convention).

### C. Configuration and manifests

- **C1**: All human-authored configuration is **TOML**: the home config file,
  every `module.toml`, and the project's `.project-setup/` files. The internal
  merged execution plan is **JSON**, emitted canonically (stable key order) for
  determinism.
- **C2**: A module manifest declares at least: `id`, `title`, ordering relations
  (`before` / `requires` / `after`), `default_enabled`, `kind`
  (`scripted` | `agent-steered`), the Python `entrypoint`, `required_answers`,
  `optional_answers`, default answer values, directories it creates, external
  tools it uses, and — for `agent-steered` modules — the embedded instructions
  the agent must follow.
- **C3**: There is **no `priority` field**. Modules declare explicit
  `before`/`requires`/`after` relations by module id; the runner computes a
  **stable topological order**. Independent modules (disjoint outputs) may run
  in either order. Missing `requires` or dependency cycles are a hard,
  located error caught before any execution.

### D. Module sources and discovery

- **D1**: Modules are discovered from a precedence-ordered search path
  (highest wins on id collision): environment override
  (`PROJECT_SETUP_MODULES_DIR`) → project-local `./.project-setup/modules/` →
  home `~/.config/project-setup/modules/` → **fetched dynamic sources** →
  bundled base (shipped inside the skill; always present, lowest precedence).
- **D2**: **Dynamic module sources** are first-class: a source may be a git
  repo, a git path/subdir, or a local path, declared with an APM-style locator
  and an optional ref. A floating ref (e.g. `main`) is allowed — updating a
  source to update one's setup is a feature.
- **D3**: The runner resolves and **fetches sources to a cache before
  discovery** (fetch → cache → discover → interview → execute). A fetch failure
  or offline run is non-fatal: the runner proceeds with cached + local +
  bundled modules and reports the skip. Bundled base modules always work
  offline.
- **D4**: Executing module code from a remote source is arbitrary code
  execution; this is accepted as the same trust surface as APM packages and
  Claude plugins. APM-packaged modules (modules shipped as their own APM
  package, installed into `apm_modules/`) are **out of scope**.

### E. Determinism — two tiers, relative to resolved module versions

- **E1**: **Tier 1 (scripted modules):** given the same answers, output is
  **byte-identical**. Each module's entrypoint fail-fasts on its own required
  inputs, and the manifest's `required_answers` are enforced before invocation.
- **E2**: **Tier 2 (agent-steered modules):** explicitly marked, carry embedded
  instructions, and produce **consistent-but-not-byte-identical** output. Their
  decisions are persisted and marked as agent-steered.
- **E3**: The guarantee is **relative to resolved module versions**: "same
  answers → same result" holds only when the modules' instructions/versions did
  not change between runs. The byte-identical promise (Tier 1) applies only to
  scripted modules with unchanged versions.
- **E4**: Before any filesystem write, a **validate-closed gate** verifies that
  all `required_answers` are present and that every enabled module and its
  `requires` closure resolve. The run refuses to proceed (with a located error)
  otherwise.

### F. Persisted answers and reproducibility

- **F1**: The project carries two committed files under `.project-setup/`:
  - **`sources.toml`** — declares this project's module sources (refs), plus a
    `[meta] skill_version` recorded **advisorily** (a clone on a different skill
    version warns about drift but proceeds).
  - **`answers.toml`** — the decisions, in **per-module `[module.<id>]`
    sections** so the store is modular (a module contributes its own section;
    nothing central to edit) and the file can later be split into per-module
    files with no schema change. Each section records the answer values and a
    `source` provenance (`default` | `flag` | `home` | `agent-steered`).
- **F2**: A clone on any machine is reproducible from the **committed project
  files alone**: the runner reads `sources.toml`, fetches the declared sources
  into a cache, and applies `answers.toml` — independent of that machine's home
  config. Fetched module bytes are cached (gitignored), not vendored into the
  repo.
- **F3**: **Default-value layering** (what the interview *proposes*, lowest →
  highest): module-manifest default → home-config default → project
  `answers.toml` (on re-run). The user's chosen answer overrides every default.
  Defaults only seed the proposal; the committed answer is authoritative, so a
  home default can never silently change an existing project.
- **F4**: **Home config is a personal catalog + defaults, never authoritative.**
  It declares which module sources are *available* to the user and personal
  default answers for new projects. It applies nothing on its own; only a
  project's committed `.project-setup/` files decide what a given repo is.

### G. Setup modes, the interview, and idempotent re-run

- **G1**: The runner detects mode by the presence of `.project-setup/sources.toml`:
  - **Absent → init mode**: discover bundled base + home-catalog sources,
    conduct the manifest-driven interview (which modules to enable; a free-form
    "add external sources?" prompt seeded by the home catalog but accepting
    ad-hoc locators), then **write** `sources.toml` + `answers.toml`.
  - **Present → reproduce/update mode**: fetch declared sources, load committed
    answers, and run the diff/confirm loop rather than a blank interview.
- **G2**: The interview is **generated from module manifests**, not authored as
  prose, so the same answers are collected the same way regardless of which
  agent conducts it.
- **G3**: Re-run is idempotent and **always diff-and-confirm**: the runner
  compares proposed answers (and newly discovered modules, and on-disk state)
  against the committed per-module sections and presents drift for **explicit
  per-item confirmation**. It never silently replays.
- **G4**: Modules declare a **reconcile capability**. Default behavior is
  skip-if-exists (idempotent create); a module that supports reconciliation can,
  on confirmation, overwrite an existing artifact to match the answers — so a
  re-run can actually *fix* drift rather than only fill gaps.

### H. Distribution and the skill document

- **H1**: project-setup stays in `agentic-packages` and is dual-distributed via
  the APM package **and** the Claude Code plugin marketplace (both already
  registered here). The plugin-marketplace path is "installable into Claude
  without APM." No separate repository, no standalone deploy script. Because a
  plugin install only copies files (no install/build hook), dependency
  provisioning relies on `uv` at runtime (B2/B3), not on an install step.
- **H3 — Native-root package layout (Claude plugin best practice).** The package
  MUST follow the native-root structure so it works with Claude `/plugin install`,
  Codex `plugin add`, and `apm install` from one source:
  - `packages/project-setup/.claude-plugin/plugin.json` is **required**
    (`name`, `version`, `description`, `author`, `license`); without it `apm
    install` misses components and native loaders skip the package.
  - The skill lives at **native root** `packages/project-setup/skills/project-setup/SKILL.md`
    (+ `references/`), **not** under `.apm/skills/`. The current `.apm/skills/`
    location MUST be migrated to native root as part of this work.
  - `apm.yml` and `CHANGELOG.md` remain at the package root; scripts are
    referenced as `${CLAUDE_PLUGIN_ROOT}/...`.
  - No symlinks (APM rejects them). Release tags follow `<name>--v<version>`.
  - (Repo-wide tooling that builds the marketplace block / docs / release config
    for native-root packages is being updated separately; this spec only fixes
    the project-setup package's own layout.)
- **H2**: SKILL.md stays **thin on configuration** (no project specifics — A1)
  but is **prescriptive on process and guardrails**. It must instruct the agent
  on: ensuring `uv`; running the runner end-to-end; how module discovery and
  sourcing work; conducting the manifest-driven interview; the answers
  diff/confirm loop; how Tier-1 vs Tier-2 modules are executed; **what "done"
  means**; how to check validity (the validate-closed gate plus functional test
  scripts); how to run module entrypoints safely; and the **secrets guardrail**
  (never accept a secret as an input value — if a user supplies one, tell them it
  is now compromised and must be rotated, and never persist it).

### I. Module structure (settled decisions)

- **I1 — On-disk anatomy.** A module is a directory named by its id, containing:
  a `module.toml` manifest; a fixed-name `module.py` entrypoint; optional
  additional `*.py` helper files (a module may be a small multi-file package);
  an optional `steering/` directory of agent-facing prose (progressive
  disclosure — an entry doc that points at deeper references); an optional
  `templates/` directory of static assets (e.g. license texts, vendored CC0
  gitignore templates); and `test_*.py` pytest files (discovered by convention,
  run via `uv run` — no manifest field).
- **I2 — Invocation (Model B).** Each `python` step is executed as a subprocess:
  `uv run module.py --plan <frozen-plan> --step <step-id>`. The module declares
  its own dependencies via PEP 723 inline metadata, so `uv run` provisions them
  per-module with no shared-venv conflicts. The module reads its frozen inputs
  from disk (never from agent-supplied arguments) and emits a structured JSON
  result (files written, diffs, answers to persist). The agent is a trigger, not
  an input source.
- **I3 — Manifest `[meta]`.** Declares `repository` (source URL) and `author`.
- **I4 — Manifest `[module]`.** Declares `id` (speckit-style `<noun>-<verb>`,
  e.g. `git-init`, `gitignore-generate`, `lang-python`), `name`, `version`,
  `description`, and `reconcile` (whether the module may overwrite-to-match on
  confirmed drift; otherwise skip-if-exists).
- **I5 — `default_enabled` is first-party-only.** Only modules in the
  first-party base bundle may set `default_enabled`. A third-party or
  remote-sourced module is never auto-enabled; the field is ignored/rejected on
  non-bundled modules and the module must be explicitly enabled via config or the
  interview.
- **I6 — Id collisions are a hard error.** If two discovered modules share an
  `id` across roots, the runner fails with a located error naming both paths. Ids
  are never silently shadowed; overriding shipped behavior is done through
  config/answers, not by redefining an id.
- **I7 — `[order]`.** Inter-module ordering is declared with `requires` (hard
  dependency — the named module must be enabled and precede), `after`, and
  `before` (soft ordering hints), all by id; resolved by a stable topological
  sort. No `priority` field (per C3).
- **I8 — `[tools]`.** Declares only `required` external tools; a missing required
  tool fails the validate-closed gate. Graceful "try-then-fallback" behavior
  (e.g. prefer a generator tool, fall back to bundled templates) lives in
  `module.py` code, not in the manifest.
- **I9 — `[[inputs]]`.** Each entry declares one input the module asks for:
  `key`, `type` (`string` | `text` | `int` | `bool` | `choice` | `multichoice` |
  `path` | `list`), `prompt`, `choices` (for choice/multichoice), `default`
  (the module-level default — lowest in the F3 layering chain), and `required`
  (enforced by the validate-closed gate). Declared inputs drive the interview;
  resolved values persist to `.project-setup/answers.toml`. There is no `secret`
  type — secrets must never be accepted (H2 guardrail).
- **I10 — `[[steps]]`.** An explicit, ordered list of intra-module steps the
  runner/agent obeys. Each step has an `id` and a `kind`: `python` (Tier-1
  deterministic; runs `module.py --step <id>`), `agent` (Tier-2; carries a
  `steering` file the agent follows), or `gate` (a diff/confirm checkpoint with a
  `message`). This is how per-part tiers (E1/E2) and confirm checkpoints are
  expressed within one module; default order is the listed order.
- **I11 — No declared outputs.** Modules do NOT declare a `produces`/`creates`
  list. Conflict and drift detection use the module's runtime JSON result
  (`files_written` / `diffs`), which is truthful by construction, rather than a
  hand-maintained declaration that can drift from reality.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The skill is generic; capabilities are modules (Priority: P1)

A maintainer opens the skill and finds a generic runner plus a set of module
directories. No directory list, language list, pre-commit set, or license text
lives in the runner — each is a module with its own manifest and Python
entrypoint. Changing what a scaffold produces means editing or adding a module,
never editing the runner.

**Why this priority**: This is the structural goal (R1/A1–A3) that everything
else builds on. It is independently valuable even before remote sources exist.

**Independent Test**: Inspect the runner for hardcoded payloads (there are none);
change a payload in one module (add a directory, swap a default license) and see
the output change with no runner edit.

**Acceptance Scenarios**:

1. **Given** the runner, **When** a maintainer searches it for project-specific
   payloads, **Then** none are present — all live in module manifests/entrypoints.
2. **Given** the base module set, **When** the runner executes with default
   answers, **Then** it produces the expected baseline scaffold (the same
   observable outputs the legacy tool produced: AGENTS.md, .gitignore,
   .pre-commit-config.yaml, docs/, specs/, and no monorepo target dirs in single
   layout).

---

### User Story 2 - Same inputs reproduce the same project (Priority: P1)

A developer (or agent) sets up a project; the decisions are committed to
`.project-setup/`. Later, on another machine or after a clone, the runner
reproduces the same project from those committed files alone — fetching the
declared module sources and applying the committed answers — without relying on
that machine's home config.

**Why this priority**: Reproducibility/determinism is the core promise (R7) and
the reason answers and sources are committed. Without it, modularity multiplies
the ways results drift.

**Independent Test**: Run setup, commit `.project-setup/`, then reproduce in a
fresh clone on a clean home config; assert the scaffold matches (Tier-1 outputs
byte-identical for unchanged module versions).

**Acceptance Scenarios**:

1. **Given** committed `sources.toml` + `answers.toml`, **When** the runner runs
   in a fresh clone with an empty home config, **Then** it fetches the declared
   sources and reproduces the project's Tier-1 outputs identically (for unchanged
   module versions).
2. **Given** identical answers and unchanged module versions, **When** a scripted
   (Tier-1) module runs twice, **Then** its output is byte-identical except for
   intrinsically variable values (e.g. timestamps).
3. **Given** a module source pinned to a moved/updated ref, **When** the runner
   reproduces, **Then** the change is surfaced (advisory skill-version drift /
   updated source) rather than silently applied without the diff/confirm loop.

---

### User Story 3 - Bolt on a module from a local dir or a remote source (Priority: P1)

A user wants a capability the base set doesn't cover. They either drop a module
directory into a local root (`~/.config/project-setup/modules/` or the project's
`./.project-setup/modules/`) or point at a remote source (a git repo/path) in
their home catalog or the project's `sources.toml`. On the next run the runner
discovers it, includes its questions in the interview, and executes it in
dependency order — with no edit to the runner.

**Why this priority**: Extensibility (R2/R5) plus dynamic sources is the central
payoff of the redesign.

**Independent Test**: Add a minimal custom module locally and via a declared git
source; run setup; confirm its questions appear and its entrypoint executes in
order, with the runner files unchanged (verified by diff).

**Acceptance Scenarios**:

1. **Given** a custom module in a local module root, **When** setup runs, **Then**
   it is discovered, interviewed, and executed in dependency order with no runner
   edit.
2. **Given** a declared git source (with a ref), **When** setup runs, **Then** the
   runner fetches it to cache before discovery and includes its modules.
3. **Given** two modules with the same id across roots, **When** discovery runs,
   **Then** the documented precedence picks one deterministically and reports
   which won.
4. **Given** a module that declares `requires`/`before`/`after`, **When** the
   selection violates a `requires` or forms a cycle, **Then** the runner reports
   it before writing anything.
5. **Given** a declared source that is unreachable (offline), **When** setup runs,
   **Then** the runner proceeds with cached + local + bundled modules and reports
   the skipped source.

---

### User Story 4 - Personal defaults and a personal source catalog (Priority: P2)

A user maintains a home config declaring the module sources available to them and
their personal default answers (e.g. preferred license). New projects they start
pre-fill from these, but every value is still asked, and nothing in home config
silently decides an existing project's outcome.

**Why this priority**: Delivers configurable location (R3), install-time
enable/disable (R4), and the defaults-layering (R6) — high value, sits atop the
config model.

**Independent Test**: With a home config setting a default license and listing a
source, start a new project and confirm the interview pre-fills the license and
offers the source; then confirm an existing project's committed answers are
unaffected by changing home config.

**Acceptance Scenarios**:

1. **Given** a home default answer, **When** the init interview asks that
   question, **Then** the home value is the proposed default but is still
   confirmable/overridable.
2. **Given** a home source catalog, **When** the init interview asks about
   external sources, **Then** the catalog entries are offered (and ad-hoc
   locators are still acceptable).
3. **Given** an existing project with committed answers, **When** home config
   changes and the project is re-run, **Then** the committed answers remain
   authoritative (home cannot silently change them).
4. **Given** layered config sources for the same key, **When** merged, **Then**
   scalars take the higher-precedence value, tables merge by union, and lists
   replace by default with explicit append/remove operations.

---

### User Story 5 - Idempotent re-run that fixes drift (Priority: P2)

A user re-runs setup on an existing project to fix an issue, adopt a newly added
module, or update answers. The runner shows what changed — proposed answers vs.
committed, newly discovered modules, and on-disk drift — and asks for explicit
confirmation per item before writing. Modules that support reconciliation can
overwrite to match; others only fill gaps.

**Why this priority**: Idempotent, drift-fixing re-runs are an explicit goal of
persisting answers in the project.

**Independent Test**: Hand-edit a scaffolded file to diverge from `answers.toml`,
re-run, and confirm the runner reports the drift and (for a reconcile-capable
module, on confirmation) restores it — without clobbering anything unconfirmed.

**Acceptance Scenarios**:

1. **Given** on-disk state that diverges from committed answers, **When** the
   runner re-runs, **Then** it reports the drift and requests explicit
   confirmation before any write.
2. **Given** a reconcile-capable module and a confirmed drift, **When** the runner
   proceeds, **Then** it overwrites the artifact to match the answers.
3. **Given** a non-reconcile module with an existing artifact, **When** the runner
   re-runs, **Then** it skips (idempotent create) and does not clobber.
4. **Given** a newly added module since last run, **When** the runner re-runs,
   **Then** it surfaces the new module and its questions rather than silently
   enabling or skipping it.

---

### Edge Cases

- **`uv` is missing**: the runner fails immediately with a clear install
  instruction; it does not attempt a degraded run.
- **A module's external tool is missing** (e.g. a generator): the module reports
  a warning and uses a defined fallback (e.g. the bundled-templates path for
  .gitignore) rather than aborting the run.
- **A declared source is unreachable / offline**: the run proceeds with cached +
  local + bundled modules and reports the skip; never hard-fails the whole run
  for one source.
- **A `module.toml` is malformed, or a `requires` is unmet, or the dependency
  graph has a cycle**: the validate-closed gate fails with a located error
  before any filesystem write.
- **Two modules share an id across roots**: the documented precedence resolves it
  deterministically and reports the winner.
- **A clone runs on a different skill version than recorded in `sources.toml`**:
  the runner warns about advisory skill-version drift and proceeds.
- **Re-run on an already-scaffolded directory**: idempotent; existing artifacts
  are preserved unless a reconcile-capable module is confirmed to overwrite.
- **A floating-ref source updated since last run**: surfaced through the
  diff/confirm loop, not silently applied.

## Requirements *(mandatory)*

### Functional Requirements

**Generic runner & modules (A)**

- **FR-001**: The runner MUST contain no project-specific configuration payloads;
  all such payloads live in module manifests and entrypoints.
- **FR-002**: Every capability MUST be a self-contained module: a `module.toml`
  manifest co-located with a Python entrypoint and any assets it needs.
- **FR-003**: Project identity and monorepo package-add MUST be modules, not
  special-cased runner logic. The base scaffold MUST be the set of
  `default_enabled` modules, expressed as a bundle.

**Runtime (B)**

- **FR-004**: The runner and all modules MUST be Python; no shell components.
- **FR-005**: The runner MUST require `uv`; if absent it MUST fail with a clear
  install instruction, MUST NOT auto-install it, and MUST NOT provide a
  standard-library fallback.
- **FR-006**: Dependencies MUST be explicitly declared (packaged dependency set)
  and resolvable via `uv run` (PEP 723 inline metadata) so required parsers are
  always provided.
- **FR-007**: Tests MUST be pytest, runnable via `uv run`.

**Config & manifests (C)**

- **FR-008**: Human-authored config (home config, `module.toml`,
  `.project-setup/` files) MUST be TOML; the internal merged execution plan MUST
  be JSON emitted with the single canonical serializer
  `json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"`, and
  the frozen plan MUST live in the runtime cache (`~/.cache/project-setup/`),
  never inside the committed `.project-setup/`.
- **FR-009**: *(Amended — Section I is authoritative; this restates the earlier
  draft to match.)* A `module.toml` MUST declare the Section I schema:
  `[meta]`(repository, author); `[module]`(`id` `<noun>-<verb>`, `name`,
  `version`, `description`, `reconcile`, optional first-party-only
  `default_enabled`); `[order]`(`requires`/`after`/`before`); `[tools]`(`required`);
  `[[inputs]]`(`key`, `type`, `prompt`, `choices`, `default`, `required`);
  `[[steps]]`(`id`, `kind`=`python`|`agent`|`gate`). Determinism tier is
  **step-scoped** (derived from step `kind`); there is no module-level `kind`.
  The forbidden fields `priority`, `title`, `entrypoint`, `required_answers`,
  `optional_answers`, and any `produces`/created-directories list MUST be
  rejected with a located `FORBIDDEN_FIELD` error (so "no priority", C3, is
  enforced, not merely unread). The fixed entrypoint is `module.py` (no
  `entrypoint` field). *(Earlier draft fields — `title`, module-level `kind`,
  Python `entrypoint`, `required_answers`, `optional_answers`, created
  directories — are superseded.)* For reference, the superseded draft read: a
  `module.toml` MUST declare at least: `id`, `title`,
  `before`/`requires`/`after`, `default_enabled`, `kind`
  (`scripted`|`agent-steered`), Python `entrypoint`, `required_answers`,
  `optional_answers`, default answer values, created directories, used external
  tools, and (for `agent-steered`) embedded agent instructions.
- **FR-010**: Module ordering MUST be expressed only via `before`/`requires`/
  `after` by id and resolved by a stable topological sort; there MUST be no
  `priority` field. Missing `requires` or cycles MUST be a hard, located error
  before execution.

**Sources & discovery (D)**

- **FR-011**: The runner MUST discover modules from a precedence-ordered search
  path: env `PROJECT_SETUP_MODULES_DIR` > project `./.project-setup/modules/` >
  home `~/.config/project-setup/modules/` > fetched dynamic sources > bundled
  base; id collisions resolve by this precedence and the winner MUST be reported.
- **FR-012**: The runner MUST support dynamic module sources (git repo, git
  path/subdir, local path) declared via an APM-style locator with an optional
  ref; floating refs MUST be permitted.
- **FR-013**: The runner MUST fetch declared sources to a cache BEFORE discovery;
  a fetch failure or offline condition MUST NOT abort the run — it MUST proceed
  with cached + local + bundled modules and report the skip.
- **FR-014**: Bundled base modules MUST ship inside the skill package and resolve
  without any fetch or install, so a baseline run works offline.

**Determinism (E)**

- **FR-015**: Scripted (Tier-1) modules MUST produce byte-identical output for
  the same answers and unchanged module versions (excluding intrinsically
  variable values). Each MUST fail-fast on its own required inputs, and the
  manifest's `required_answers` MUST be enforced before invocation.
- **FR-016**: Agent-steered (Tier-2) modules MUST be explicitly marked, carry
  embedded instructions, and have their decisions persisted and marked as
  agent-steered; their output is consistent-but-not-byte-identical and is exempt
  from the byte-identical guarantee.
- **FR-017**: Before any filesystem write, the runner MUST run a single
  validate-closed gate that accumulates and reports **all problems at once**:
  every required input present, all enabled modules and their `requires` closure
  resolve, no dependency cycle, and every `[tools].required` tool present on
  PATH. Topological ordering MUST be pure/non-raising (it returns accumulated
  errors, never raises mid-order); the validate-closed gate is the only place
  that raises `GateFailure`. The located error envelope MUST carry a
  `module_ids: list` field so multi-id errors (collision = two paths, cycle = a
  path of ids) are machine-readable.

**Persistence & reproducibility (F)**

- **FR-018**: The project MUST carry committed `.project-setup/sources.toml`
  (structured `[[source]]` records with locator/ref/subdir + advisory
  `[meta] skill_version`) and `.project-setup/answers.toml` (per-module
  `[module.<id>]` value tables with **per-key** provenance under a parallel
  `[module.<id>.source]` table). The provenance enum is
  `{default, flag, home, project, derived, agent-steered}` — `project` covers a
  value reproduced from committed answers on re-run and `derived` a value a
  module computes at runtime. Modules MAY emit only `default`/`derived`/
  `agent-steered`; persistence assigns `flag`/`home`/`project`.
- **FR-019**: A clone MUST be reproducible from the committed project files
  alone: read `sources.toml`, fetch declared sources to a (gitignored) cache,
  apply `answers.toml` — independent of the machine's home config. Fetched
  module bytes MUST NOT be vendored into the repo.
- **FR-020**: Interview defaults MUST layer module-manifest default <
  home-config default < project committed answer, with the user's chosen answer
  overriding all defaults; a home default MUST NOT silently change an existing
  project.
- **FR-021**: Home config MUST act only as a personal source catalog + personal
  default answers; it MUST NOT be authoritative for any project's outcome.

**Modes, interview, re-run (G)**

- **FR-022**: The runner MUST detect mode by the presence of
  `.project-setup/sources.toml`: absent → init (interview, then write
  sources+answers); present → reproduce/update (fetch, load answers, diff/confirm).
- **FR-023**: The interview MUST be generated from module manifests, not authored
  prose.
- **FR-024**: Re-run MUST be idempotent and always diff-and-confirm: drift in
  answers, newly discovered modules, and on-disk state MUST be presented for
  explicit per-item confirmation; the runner MUST NOT silently replay.
- **FR-025**: Modules MUST be able to declare a reconcile capability; default is
  skip-if-exists, and a reconcile-capable module MAY overwrite to match answers
  on confirmation, so re-run can fix drift.

**Config overlay (R6)**

- **FR-026**: Layered configuration MUST deep-merge by documented rules: tables
  merge by union (recurse on collision), scalars are replaced by the
  higher-precedence layer, and lists replace by default with explicit opt-in
  append/remove operations; the merged result MUST be canonical (stable order).

**Distribution & skill doc (H)**

- **FR-027**: project-setup MUST remain in `agentic-packages` and be installable
  both via APM and via the Claude Code plugin marketplace; no separate repo, no
  standalone deploy script.
- **FR-027a**: The package MUST adopt the native-root Claude-plugin layout: a
  required `.claude-plugin/plugin.json`, the skill at
  `skills/project-setup/SKILL.md` (migrated off `.apm/skills/`), scripts
  referenced via `${CLAUDE_PLUGIN_ROOT}/...`, no symlinks, and `<name>--v<version>`
  release tags.
- **FR-028**: SKILL.md MUST carry no project-specific configuration but MUST be
  prescriptive on process and guardrails: ensuring `uv`; running the runner
  end-to-end; module discovery/sourcing; the manifest-driven interview; the
  answers diff/confirm loop; Tier-1 vs Tier-2 execution; the definition of
  "done"; validity checks (validate-closed gate + functional test scripts); and
  safe module-entrypoint execution.

**Migration & validation**

- **FR-029**: Each current capability MUST be migrated to a module without losing
  current observable behavior: git, GitHub, directory scaffold, pre-commit
  (+ close-keywords vendoring), AGENTS.md, .codex config, justfile, license,
  .gitignore, APM install/compile/patch/audit, the SpecKit bridge (delegating to
  the existing `speckit` package), each language overlay (ts/python/go/rust),
  quality-hooks, and monorepo package-add.
- **FR-030**: The .gitignore module MUST generate deterministically with no live
  external API: it ships vendored github/gitignore (CC0) templates AND offers a
  dynamic option that fetches matching templates from github/gitignore on demand
  (so not every stack needs a bundled template).
- **FR-031**: Functional test scripts MUST be providable per module to validate
  that produced on-disk state matches the recorded answers, covering both Tier-1
  and Tier-2 modules where applicable. Tests are plain pytest (`test_*.py` in the
  module directory), discovered by convention and run via `uv run`.

**Module structure (I)**

- **FR-032**: A module MUST be a directory containing a `module.toml` manifest
  and a fixed-name `module.py` entrypoint; it MAY also contain additional `*.py`
  helper files, a `steering/` directory (progressive-disclosure agent docs), a
  `templates/` directory (static assets), and `test_*.py` files.
- **FR-033**: Each `python` step MUST be invoked as a subprocess
  (`uv run module.py --plan <frozen-plan> --step <step-id>`); the module MUST
  declare its dependencies via PEP 723 inline metadata, MUST read its inputs from
  the frozen plan on disk (never from agent-supplied arguments), and MUST emit a
  structured JSON result.
- **FR-034**: `module.toml` MUST provide `[meta]` (`repository`, `author`) and
  `[module]` (`id` in `<noun>-<verb>` form, `name`, `version`, `description`,
  `reconcile`).
- **FR-035**: `default_enabled` MUST be honored only for first-party base-bundle
  modules; it MUST be ignored or rejected on third-party/remote modules, which
  MUST require explicit enablement.
- **FR-036**: Module `id` collision is resolved by a precedence boundary:
  two modules with the same `id` **within the same root kind** MUST be a hard,
  located `ID_COLLISION` error (naming both paths via `module_ids`); the same
  `id` **across precedence levels** is a reported shadow (higher precedence wins
  and the shadow is logged). This cross-level shadow is the only "override by id"
  path; otherwise overriding is via config/answers. `default_enabled` MUST be
  tri-state (`Optional[bool]`) so a non-bundled module that sets it is rejected
  (FR-035).
- **FR-037**: `[order]` MUST express `requires`/`after`/`before` by id only,
  resolved by stable topological sort, with no `priority` field.
- **FR-038**: `[tools]` MUST declare only `required` tools (missing → gate
  fails); graceful fallback behavior MUST live in module code, not the manifest.
- **FR-039**: `[[inputs]]` MUST declare each input with `key`, `type`
  (`string`|`text`|`int`|`bool`|`choice`|`multichoice`|`path`|`list`), `prompt`,
  optional `choices`, `default`, and `required`; there MUST be no `secret` type.
- **FR-040**: Inputs of every supported type MUST have defined handling that the
  skill instructs the agent on (how to elicit, validate, and record each type).
- **FR-041**: `[[steps]]` MUST declare an ordered list of steps, each with `id`
  and `kind` (`python` | `agent` (+`steering`) | `gate` (+`message`)); listed
  order is execution order, and this is how per-part tiers and confirm
  checkpoints are expressed within a module.
- **FR-042**: Modules MUST NOT declare an outputs/`produces` list; conflict and
  drift detection MUST use the runtime JSON result instead.
- **FR-043**: Secrets MUST never be accepted as input values; if a user supplies
  one, the skill MUST instruct them that it is compromised and must be rotated,
  and MUST NOT persist it.

### Key Entities

- **Runner**: The generic engine and the skill itself. Resolves sources,
  discovers modules, interviews, validates, executes, persists answers. Carries
  no project specifics.
- **Module**: A self-contained capability directory — `module.toml` + fixed
  `module.py` entrypoint (+ optional helper `*.py`, `steering/`, `templates/`,
  `test_*.py`). Discovered from a root; declares meta, ordering, tools, inputs,
  ordered steps, and reconcile capability. Invoked per `python` step as
  `uv run module.py --plan <frozen> --step <id>` with PEP 723 deps.
- **Module manifest (`module.toml`)**: The TOML declaration the runner reads to
  discover, interview, validate, order, and execute a module. Sections: `[meta]`
  (repository, author), `[module]` (id `<noun>-<verb>`, name, version,
  description, reconcile), `[order]` (requires/after/before), `[tools]`
  (required), `[[inputs]]` (declared questions → persisted answers), `[[steps]]`
  (ordered python/agent/gate steps).
- **Module source**: A declared origin of modules (bundled, local root, or
  dynamic git/path source with a ref), resolved into the search path.
- **Home config (`~/.config/project-setup/config.toml`)**: Personal source
  catalog + personal default answers. Never authoritative for a project.
- **Project config (`.project-setup/`)**: Committed `sources.toml` (sources +
  refs + advisory skill_version) and `answers.toml` (per-module sections with
  provenance). Authoritative and portable.
- **Answer set**: Per-module recorded decisions with provenance
  (`default`/`flag`/`home`/`agent-steered`); the variable input to execution.
- **Execution plan**: The deterministic, topologically ordered, JSON-serialized
  list of modules-with-answers the runner executes after the validate gate.

## Success Criteria *(mandatory)*

- **SC-001**: For scripted (Tier-1) modules with unchanged versions, running
  setup twice with identical answers produces byte-identical output (excluding
  intrinsically variable values). *(Applies to Tier-1 only; Tier-2 is
  consistent-not-identical.)*
- **SC-002**: The runner contains zero hardcoded project-specific payloads;
  100% of directory sets, language lists, tool toggles, pre-commit sets, license
  texts, and interview questions live in modules (verified by inspection).
- **SC-003**: A new capability can be added by authoring one module (local or via
  a declared source) with zero lines changed in the runner (verified by diff).
- **SC-004**: A clone on a clean home config reproduces a project's Tier-1
  scaffold from the committed `.project-setup/` files alone.
- **SC-005**: The migrated base module set produces the same observable scaffold
  outputs the legacy tool produced (AGENTS.md, .gitignore,
  .pre-commit-config.yaml, docs/, specs/, no monorepo target dirs in single
  layout), verified by the new pytest suite.
- **SC-006**: A user can set a personal default answer and a personal source
  catalog in home config; new projects pre-fill from them, and an existing
  project's committed answers are unaffected by home-config changes.
- **SC-007**: A re-run never writes without explicit confirmation of any drift,
  and a reconcile-capable module restores a drifted artifact to match answers on
  confirmation.
- **SC-008**: A single unreachable source or failed module never aborts the whole
  run; the run reports the skip and a later run reaches the intended end state.
- **SC-009**: The .gitignore module produces output offline from vendored CC0
  templates and can additionally fetch matching templates from github/gitignore
  on demand.
- **SC-010**: project-setup is installable both via APM and via the Claude plugin
  marketplace from this repository, with `uv` as the only runtime prerequisite.

## Assumptions

- **Greenfield governance**: No project constitution or durable memory currently
  constrains this work; the spec stands on the verified investigation facts in
  this feature's `memory.md`.
- **`uv` available**: The single runtime prerequisite. Absence is a hard, loud
  failure by design — not a degraded mode.
- **Plugin install copies arbitrary files (VERIFIED).** A Claude plugin install
  copies the package source directory as-is, not just recognized component
  types. Empirically confirmed against installed plugins under
  `~/.claude/plugins/cache/`: multi-file Python packages (e.g. hookify's
  `core/config_loader.py`, `matchers/__init__.py`), arbitrary config/data
  (`rust-toolchain.toml`, `.typos.toml`), and whole source subtrees all survive.
  Therefore `module.py`, helper `*.py`, `templates/`, and `steering/` arrive on
  the plugin channel. The runner MUST resolve module/template paths via
  `${CLAUDE_PLUGIN_ROOT}` (relative to the install cache), and the Model-B
  `uv run module.py` subprocess invocation does not depend on the cache being on
  `sys.path`.
- **Modern Python via `uv`**: Parsers (TOML via tomllib, etc.) are guaranteed
  through declared/inline deps, not assumed on the system interpreter.
- **Determinism is version-relative**: "Same answers → same result" holds only
  for unchanged module versions; floating refs intentionally allow updates.
- **The legacy bats suite and flag CLI are retired**: replaced by pytest and the
  interview→answers model. The behavioral guarantee (observable scaffold outputs)
  is preserved under the new suite, not the old entrypoint.
- **APM-packaged modules and live external gitignore APIs are out of scope**;
  dynamic gitignore fetches the CC0 github/gitignore templates only.
- **The SpecKit setup flow is owned by the `speckit` package**; the SpecKit
  module is a thin bridge that delegates to it.
- **Native-root layout is a new repo standard**: no existing package uses it yet,
  so project-setup is the first reference implementation. Repo-wide tooling
  (marketplace-block builder, docgen/inventory, release-tag convention) is being
  migrated to support native-root packages **in parallel by separate work**; this
  spec assumes that tooling will accept the layout and does not itself change it.

## Out of Scope

- Modules shipped as their own APM packages (install-timing complexity).
- A standalone deploy script or moving project-setup to a separate repository.
- Re-implementing the SpecKit setup flow (owned by the `speckit` package).
- Changing how the APM marketplace itself resolves or installs packages.
- A live external gitignore API (e.g. toptal/gitignore.io); only vendored +
  github/gitignore fetch are in scope.
