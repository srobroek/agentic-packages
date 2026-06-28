# Feature Specification: TypeScript Depth Resolvers

**Feature Branch**: `feat/project-setup-modular-redesign` (continues) → likely a
dedicated `feat/ts-depth-resolvers` branch

**Created**: 2026-06-28

**Status**: Draft (2026-06-28)

**Input**: Roadmap rank #11 from `reviews/tier2-agentic-features-roadmap.md:95-99` —
"ts-test-tooling-resolver + ts-ui-kit-resolver + ts-runtime-pm-resolver (ts depth)".
Builds directly on the shipped `lang-ts` module (spec 003/004), which already has the
`resolve` → `pins` → `write` → `run-generator` → `scaffold` step sequence and the
three existing agent-steered answers (`framework`, `pinned_deps`, `dev_deps`,
`package_manager_pin`). This spec adds three specialised depth resolvers as **new
agent-steered answers and new steps on the same `lang-ts` module** — not a separate
module.

## Overview

The 003/004 `lang-ts` resolver decides the primary framework stack. Three important
dimensions are deliberately left flat today:

1. **Test runner** — `dev_deps` may include `vitest` or `@playwright/test` but
   nothing decides *which* runner to use, which config template to instantiate, or
   whether Playwright is layered on top of a unit runner.
2. **UI kit** — `ui_kit` is an interview string that shapes `pinned_deps` via the
   existing agent step. Nothing runs `shadcn init` or installs Tailwind v4; the gate
   and the non-idempotent clobber risk of `shadcn init` are unaddressed.
3. **Runtime / package-manager pin** — `package_manager_pin` already exists. The
   runtime choice (Bun vs Node) and the matching `engines` field + `.node-version` or
   `.nvmrc` file are not written; `packageManager` format is not validated.

This spec adds the following to `lang-ts`:

> **Three coherent depth resolvers** — the agent is extended to also decide
> `test_runner + template_id`, `ui_kit_id + ui_kit_init_command`, and
> `runtime + node_line + package_manager_pin` — plus the python step work that
> instantiates config templates, validates the PM field, writes engine/version
> files, and gates the UI-kit init command before running it.

The pattern is the same seam as 003: agent decides (frozen, `agent-steered`);
python writes from frozen answers only; gates protect non-idempotent side-effects.
No new runner machinery is needed — the existing two-phase plan, reproduce-replay,
`init_only` gate, and `sdk.verify_pins` cover everything.

**Ordering constraint**: the runtime resolver result (`package_manager_pin`,
`runtime`) MUST be folded into `resolved_answers` **before the `scaffold` step
runs**, because the scaffolder invocation reads `package_manager` to pick `bunx` vs
`pnpm dlx`. The two-phase plan already ensures all agent steps (Phase A) complete
before any python step (Phase B), so the ordering is guaranteed by the existing
mechanism — not a new runner change. It is documented explicitly here because it is
load-bearing for the scaffolder correctness.

## Current state (verified — citations, do not re-derive)

All file:line references verified against
`packages/project-setup/skills/project-setup/` on `feat/project-setup-modular-redesign`
at HEAD `7779c27`.

- **`lang-ts/module.toml`**: existing inputs are `target`, `package_manager`,
  `framework`, `ui_kit` (lines 19–46). The `ui_kit` input is a free-form string that
  the agent step reads for context, but nothing validates it, gates a `shadcn init`,
  or runs any UI-kit init command. Steps: `resolve` (agent), `pins` (gate, hard,
  `init_only`, `allow-stack-write`), `write` (python), `run-generator` (gate, soft,
  `no-external-generators`), `scaffold` (python) — lines 47–82.
- **`lang-ts/module.py:199-203`**: `_do_write` reads `package_manager`, `framework`,
  `pinned_deps`, `dev_deps`, `package_manager_pin` from `FrozenInputs`. No
  `test_runner`, no `template_id`, no `runtime`, no `node_line`, no `engines`
  field, no `.node-version` write. The `package_manager_pin` value is written
  verbatim to `package.json["packageManager"]` at line 137 in `_patch_package_json`
  with **no format validation**.
- **`lang-ts/module.py:400-479`**: `_do_scaffold` reads `package_manager` and
  `framework` to dispatch to `nuxi@latest`, `create-vite`, or `bun/pnpm init`. The
  `package_manager` value was decided at interview time (a `choice` input), not by
  the resolver — so if the runtime resolver changes the agreed PM, the scaffolder
  already sees the correct value because both read from the same `resolved_answers`
  frozen plan (Phase A folds the agent answer before Phase B runs the scaffolder).
- **`lang-ts/module.py:482-486`**: `STEP_HANDLERS` maps only `"write"` and
  `"scaffold"`; a comment notes `resolve`/`pins`/`run-generator` are agent/gate
  steps handled by the runner.
- **`lang-ts/steering/resolve.md`**: the existing resolve steering doc covers
  `framework`, `pinned_deps`, `dev_deps`, `package_manager_pin`, `rationale`. It has
  a `dev_deps` table that may include `@biomejs/biome` and `typescript` but contains
  no test-runner decision logic, no UI-kit init command, and no runtime/engines
  guidance (verified by full read of the file at `modules/lang-ts/steering/resolve.md`).
- **`sdk.py:315-380`**: `verify_pins(pins, ecosystem)` exists and handles npm
  (`registry.npmjs.org/<pkg>`), returning `PIN_VERIFIED` / `PIN_DISCONFIRMED` /
  `PIN_UNREACHABLE`. It is the reusable verification primitive for all three depth
  resolvers (no new helper needed for npm pins).
- **`lang-ts/module.py:226-276`**: the `write` step already calls
  `sdk.verify_pins(all_pins, "npm")` in `init` mode and hard-errors on
  `PIN_DISCONFIRMED`; safe-skips on `PIN_UNREACHABLE`. The depth resolvers' new pins
  will be included in `all_pins` (the same `pinned_deps`/`dev_deps`/`package_manager_pin`
  lists) — no new verify call needed in the write step, only in steering contract.
- **`lang-ts/module.py:83-146`**: `_patch_package_json` and
  `_patch_pins_into_package_json` write `package.json` deterministically from pin
  lists. The `packageManager` field is set from `package_manager_pin` verbatim
  (line 136-138) with no `name@semver` shape check.
- **`lang-ts/templates/`**: contains `tsconfig.json`, `gitignore-block.txt`,
  `gitignore-nuxt.txt`, `gitignore-sst.txt`, `precommit-biome.yaml`,
  `precommit-prettier.yaml`. No test-runner config templates exist today.
- **No `engines` field, `.node-version`, or `.nvmrc` write** anywhere in
  `lang-ts/module.py`. `package.json["engines"]` is not set.
- **The `run-generator` gate** (`module.toml:70-80`) is a soft gate with
  `skip_flag = "no-external-generators"`. The scaffolder runs AFTER the deterministic
  `write` step (the Subtlety-1 fix from spec 004 memory) and re-merges pins via
  `_patch_pins_into_package_json` at `module.py:463`.

## Settled decisions

Letters restart per spec (A-series):

- **A — Three resolvers extend the existing `lang-ts` agent step; they are NOT new
  modules.** The test-runner, UI-kit, and runtime decisions are additions to the
  existing `resolve` step's `answers_to_persist` — new agent-steered answer keys on
  `lang-ts`. A separate `ts-test-resolver` module would require a new `requires`
  edge + cross-module answer plumbing with no benefit, since all three decisions
  depend on the same `framework`, `package_manager`, `ui_kit` inputs already on
  `lang-ts`. One agent step, three new answer groups.
- **B — The agent decides; python writes. Agent emits frozen structured values;
  python instantiates IN-REPO config templates only.** For the test resolver:
  `template_id` is a curated enum that maps to a config file in `lang-ts/templates/`.
  Python opens the template by id and writes it verbatim (or with minor deterministic
  substitutions from frozen answers). The agent NEVER emits freehand config text.
  Freehand config from an agent is not reproducible and cannot be audited — it
  violates the determinism contract.
- **C — The runtime resolver runs in Phase A, and its output is available to the
  scaffolder in Phase B.** The two-phase plan already enforces this (all agent steps
  before all python steps). The `package_manager_pin` and `runtime` answers are
  frozen into the plan before `scaffold` runs. No new runner change is needed; this
  is documented as a load-bearing ordering invariant, not an assumption.
- **D — `packageManager` field MUST match `name@semver` shape; python validates
  before writing.** The existing `_patch_package_json` writes the value verbatim
  (module.py:136-138, no validation). A value like `bun@latest` or `bun` would be
  silently written. The new `write` step adds a `re.fullmatch` shape guard
  (`^[a-z][a-z0-9_-]*(@[^@]+)?/[^@]+@\d+\.\d+\.\d+.*$` or the simpler
  `name@X.Y.Z`) and emits `INPUT_VALUE_INVALID` on mismatch.
- **E — UI-kit init is a REQUIRED hard gate before any network/file-generating init
  command. Default-skip in CI. Plain reproduce marks kit-init review/skip (non-
  idempotent clobber risk).** `shadcn init` and equivalent commands clobber files
  non-idempotently (they overwrite `tailwind.config.ts`, `globals.css`, `components/`)
  and reach the network. They are NEVER run on reproduce without an explicit
  `--allow-ui-kit-init` flag. In CI the gate hard-skips the init command; a
  `STACK-NOTES` entry is written instead, recording the manual command. This pattern
  is directly analogous to the spec 004 G4 scaffold-split: `write` (deterministic
  dep pins) → `ui-kit-init` gate (hard) → `ui-kit-scaffold` python step (runs the
  init command). A declined gate writes the STACK-NOTES note.
- **F — Config templates are IN-REPO files under `lang-ts/templates/`; `template_id`
  is a curated enum.** Allowed values for `template_id` in the test-runner resolver:
  `vitest-node`, `vitest-browser`, `bun-test`, `playwright-only`, `vitest-node+playwright`.
  Each maps to a concrete `vitest.config.ts` / `playwright.config.ts` in `templates/`.
  The agent emits a `template_id` string; python opens `templates/<template_id>/`
  and writes the files. An unknown `template_id` is `INPUT_VALUE_INVALID` (never
  freehand-generated). New template files are added as part of this spec's
  implementation.
- **G — UI-kit pins (shadcn dependencies, Tailwind v4) are added to `pinned_deps`
  or `dev_deps` by the existing `resolve` step and verified by the existing `write`
  step's `verify_pins` call.** No new verification logic is needed for UI-kit deps
  — they ride the existing npm pin verify path. Only the `ui_kit_init_command` (the
  `shadcn init` invocation) is separately gated.
- **H — Runtime resolver outputs `runtime` (`"bun"` | `"node"`), `node_line` (e.g.
  `"22"` for a `.node-version` file, empty string for Bun), and the finalized
  `package_manager_pin`.** For Bun: `package_manager_pin = "bun@X.Y.Z"`, no
  `.node-version`. For Node: `package_manager_pin = "pnpm@X.Y.Z"` or
  `"npm@X.Y.Z"`, `node_line = "22"` (LTS major, written to `.node-version`). The
  `engines.node` field in `package.json` is written for Node runtime only (Bun
  manages its own version). `corepack` is a Node-runtime concern: when `runtime =
  "node"`, the write step also appends a `packageManager` entry consistent with the
  pin (corepack-compatible format `name@X.Y.Z`).
- **I — The test resolver's `template_id` folds into the existing dependency-approval
  gate (the `pins` gate, G6). The UI-kit init gate is a new hard gate. No additional
  per-resolver standalone gates are introduced beyond what spec 004 mandated.** The
  three resolvers collectively add answers to `answers_to_persist`; those answers
  flow through the existing `{decision}` render in the `pins` gate message. The
  UI-kit init is the only genuinely new gate step because it guards a non-idempotent
  network command.
- **J — The `ui_kit_init_command` is a frozen literal string decided by the agent,
  validated by python.** The agent emits the exact CLI invocation
  (e.g. `"npx shadcn@latest init"` or `"bunx shadcn@latest init --defaults"`),
  never a free-form shell script. Python validates it matches an allowlist of known
  safe prefixes (`npx shadcn`, `bunx shadcn`, `npx nuxi module add @nuxt/ui`,
  `bunx nuxi module add @nuxt/ui`) before executing it. An unrecognized command is
  rejected as `INPUT_VALUE_INVALID`; the agent is asked to correct it.

## User Scenarios & Testing

### User Story 1 — Test runner matched to build tool (Priority: P1)

A user enables `lang-ts` with `framework = "vite"`. The agent decides
`test_runner = "vitest"`, `template_id = "vitest-browser"` (matched to vite's
browser context), and emits the test runner's pinned packages into `dev_deps`.
The python `write` step instantiates `templates/vitest-browser/vitest.config.ts`
into the project directory.

**Acceptance Scenarios**:

1. **Given** `lang-ts` enabled, `framework = "vite"`, **When** the resolver runs,
   **Then** it emits `test_runner`, `template_id` (e.g. `"vitest-browser"`), and
   test-runner packages in `dev_deps` as `agent-steered` answers (exact `name@version`,
   no ranges).
2. **Given** `template_id = "vitest-browser"`, **When** the `write` step runs,
   **Then** `vitest.config.ts` is written from `templates/vitest-browser/vitest.config.ts`
   (never freehand); an unknown `template_id` emits `INPUT_VALUE_INVALID` and
   writes nothing.
3. **Given** test-runner packages in `dev_deps`, **When** `verify_pins` runs in init
   mode, **Then** every pin is registry-confirmed; a disconfirmed pin is rejected
   before the gate fires.
4. **Given** a reproduce run, **When** the `write` step runs, **Then** the config
   file is re-written from the same frozen `template_id` byte-identically (Tier-1).

### User Story 2 — UI kit matched to styling (shadcn + Tailwind v4) (Priority: P1)

A user enables `lang-ts` with `ui_kit = "shadcn"`. The agent decides
`ui_kit_id = "shadcn"`, `ui_kit_init_command = "bunx shadcn@latest init --defaults"`,
and adds shadcn + Tailwind v4 pins to `pinned_deps`/`dev_deps`. A hard gate fires
before the `ui-kit-scaffold` step with the exact init command; a declined gate writes
a `STACK-NOTES` entry with the manual command instead.

**Acceptance Scenarios**:

1. **Given** `ui_kit = "shadcn"`, **When** the resolver runs, **Then** it emits
   `ui_kit_id = "shadcn"`, a `ui_kit_init_command` literal, and shadcn + Tailwind v4
   pins (exact `name@version`) as `agent-steered` answers.
2. **Given** the agent's `ui_kit_init_command`, **When** the `ui-kit-init` gate fires
   in a TTY, **Then** the exact command is shown with `[y/N]` (hard gate, default No);
   in `--non-interactive` the command is NOT run and a `STACK-NOTES` note is written.
3. **Given** a confirmed gate, **When** the `ui-kit-scaffold` step runs, **Then** it
   validates the command against the allowlist and executes it; an unrecognized command
   is rejected before execution.
4. **Given** a reproduce run (plain, no `--refresh`), **When** the `ui-kit-init`
   gate would fire, **Then** it does NOT re-prompt (the `init_only` marker); the
   `ui-kit-scaffold` step is SAFE-skipped with a note: "kit-init is non-idempotent;
   re-run with `--refresh lang-ts` to re-execute." The deterministic dep-pin write
   still replays byte-identically.
5. **Given** `ui_kit = ""` (none), **When** the plan is built, **Then** the
   `ui-kit-init` gate step is `when`-dropped from the frozen plan and no gate fires.

### User Story 3 — Bun vs Node runtime + packageManager pin (Priority: P1)

A user enables `lang-ts` with `package_manager = "bun"`. The agent decides
`runtime = "bun"`, `package_manager_pin = "bun@1.1.38"`, `node_line = ""`. The
python write step validates the `packageManager` shape, writes it to `package.json`,
and skips `.node-version` (Bun runtime). For a Node+pnpm project, the write step
also writes `.node-version` = `"22"` and `package.json["engines"]["node"] = ">=22"`.

**Acceptance Scenarios**:

1. **Given** `package_manager = "bun"`, **When** the resolver runs, **Then** it
   emits `runtime = "bun"`, a valid `package_manager_pin = "bun@X.Y.Z"`, and
   `node_line = ""` as `agent-steered` answers.
2. **Given** a `package_manager_pin` value, **When** the `write` step validates it,
   **Then** it is accepted if it matches `name@X.Y.Z` (no ranges, no "latest", no
   bare name); a malformed value emits `INPUT_VALUE_INVALID` and writes nothing.
3. **Given** `runtime = "node"` with `node_line = "22"`, **When** the `write` step
   runs, **Then** `.node-version` is written with content `"22\n"` via
   `sdk.idempotent_write` (create-only, `reconcile=False`);
   `package.json["engines"]["node"]` is set to `">=22"`.
4. **Given** `runtime = "bun"`, **When** the `write` step runs, **Then** no
   `.node-version` is written and no `engines` field is added.
5. **Given** a reproduce run, **When** the `write` step runs, **Then** the frozen
   `runtime`/`node_line`/`package_manager_pin` produce byte-identical output (Tier-1).

### User Story 4 — Runtime resolver runs before the scaffolder (Priority: P1)

A user's runtime resolver changes `package_manager_pin` to a newer Bun version. The
scaffolder (`nuxi@latest init --packageManager bun`) reads the correct PM from the
frozen plan because Phase A (agent steps) completed before Phase B (scaffolder).

**Acceptance Scenarios**:

1. **Given** a runtime resolver agent step and a scaffolder python step in the same
   run, **When** the run executes, **Then** the scaffolder reads the frozen
   `package_manager` from the plan resolved AFTER Phase A — the agent's `runtime`
   and `package_manager_pin` are already in the frozen plan at the time `scaffold` runs.
2. **Given** a test that instruments Phase A completion and Phase B start, **Then**
   `runtime` and `package_manager_pin` are present in `resolved_answers` before any
   python step executes.

### Edge Cases

- **Agent emits an unknown `template_id`**: rejected as `INPUT_VALUE_INVALID`; the
  write step writes nothing and instructs the user to re-run with `--refresh lang-ts`.
- **Agent emits a `ui_kit_init_command` not in the allowlist**: rejected as
  `INPUT_VALUE_INVALID` before execution; the gate is still shown but the execute
  step hard-errors.
- **Agent emits `package_manager_pin = "bun@latest"`**: rejected by shape validation
  (`INPUT_VALUE_INVALID`); plain reproduce would silently write this if unvalidated.
- **`ui_kit` set but framework doesn't support shadcn** (e.g. plain/SST + shadcn):
  the agent should note the incompatibility in `rationale` and set
  `ui_kit_id = "none"` with a warning; the `ui-kit-init` gate is `when`-dropped.
- **Reproduce with a stale `template_id`**: the template file at that id either still
  exists (byte-identical replay) or was removed from the repo (module upgrade broke
  the invariant) — hard-error with a clear message instructing `--refresh`.
- **CI (`--non-interactive`) with `ui_kit = "shadcn"`**: the `ui-kit-init` gate is
  hard; it SAFE-skips the `ui-kit-scaffold` step and writes a `STACK-NOTES` note.
  The pinned deps are still written to `package.json`. The project is incomplete
  (shadcn component styles not initialized) but deterministic and buildable — the
  STACK-NOTES entry records the manual completion step.
- **Bun runtime + Node scaffolder flag conflict**: if `framework = "nuxt"` but
  `runtime = "node"`, the scaffolder receives `--packageManager pnpm` (or whichever
  PM the runtime resolver chose). The frozen `package_manager` input and the resolver
  output must agree — if the agent picks a PM inconsistent with the interview
  `package_manager` choice, the `write` step validates consistency and emits
  `INPUT_VALUE_INVALID`.

## Requirements

### Test runner resolver (agent-steered answers + template instantiation)

- **FR-001**: The `resolve` agent step MUST emit two new `agent-steered` answer keys:
  `test_runner` (a curated string: `"vitest"`, `"bun:test"`, `"playwright"`, or
  `"none"`) and `template_id` (a curated string matching a template dir under
  `lang-ts/templates/`). The agent MUST NOT emit a freehand config or a range;
  unknown values are treated as `"none"`.
- **FR-002**: The allowed `template_id` values are: `"vitest-node"`, `"vitest-browser"`,
  `"bun-test"`, `"playwright-only"`, `"vitest-node+playwright"`, `"none"`. These
  MUST correspond 1-to-1 to subdirectories under `lang-ts/templates/`. Each subdir
  MUST contain at minimum one config file (e.g. `vitest.config.ts`,
  `playwright.config.ts`).
- **FR-003**: The `write` step MUST instantiate the chosen template: for each file
  in `templates/<template_id>/`, call `sdk.idempotent_write(filename, content,
  reconcile=True, inspect=…)`. If `template_id = "none"` no config files are
  written. If `template_id` is not in the allowed set, the step MUST emit
  `INPUT_VALUE_INVALID` and write nothing.
- **FR-004**: Test-runner pinned packages MUST be added to `dev_deps` by the agent
  and verified by the existing `verify_pins` call in the `write` step (no new
  verify call). The `template_id` is NOT a package and is NOT passed to `verify_pins`.
- **FR-005**: On a reproduce run the config file(s) written from `template_id` MUST
  be byte-identical to the init run (Tier-1 guarantee). The template source files
  are versioned in the repo — a module upgrade that changes a template is a deliberate
  API change and MUST bump the module version.

### UI-kit resolver (agent-steered answers + gated init command)

- **FR-006**: The `resolve` agent step MUST emit two new `agent-steered` answer keys:
  `ui_kit_id` (a curated string: `"shadcn"`, `"nuxt-ui"`, `"none"`) and
  `ui_kit_init_command` (the exact CLI invocation literal, or empty string when
  `ui_kit_id = "none"`). The agent MUST NOT emit a freehand shell script.
- **FR-007**: The `module.toml` MUST declare a new `kind=gate` step `ui-kit-init`
  with `hardness = "hard"`, `allow_flag = "allow-ui-kit-init"`, `init_only = true`,
  and `when = "ui_kit_id != none"`. It MUST be ordered AFTER `write` and BEFORE
  `ui-kit-scaffold`. It MUST carry `init_only = true` (the 004 FR-006a mechanism):
  on plain reproduce the gate auto-proceeds but the `ui-kit-scaffold` step is
  SAFE-skipped (the non-idempotent clobber risk). Only `--refresh lang-ts`
  re-triggers the init prompt.
- **FR-008**: The `module.toml` MUST declare a new `kind=python` step `ui-kit-scaffold`
  ordered after `ui-kit-init`. This step MUST validate `ui_kit_init_command` against a
  hardcoded allowlist of safe prefixes before executing it. An unrecognized command
  MUST emit `INPUT_VALUE_INVALID` and write nothing. The allowlist: `["npx shadcn",
  "bunx shadcn", "npx nuxi module add @nuxt/ui", "bunx nuxi module add @nuxt/ui"]`.
- **FR-009**: In `--non-interactive` (without `--allow-ui-kit-init`), the `ui-kit-init`
  gate MUST SAFE-skip the `ui-kit-scaffold` step and MUST write a `STACK-NOTES.md`
  entry recording the manual `ui_kit_init_command`. This file is written via
  `sdk.append_if_absent` (idempotent; the manual command is the marker).
- **FR-010**: On plain reproduce (no `--refresh lang-ts`), the `ui-kit-scaffold` step
  MUST be SAFE-skipped and MUST append a note to `STACK-NOTES.md` explaining the
  non-idempotent clobber risk and the `--refresh lang-ts` path to re-execute. The
  pinned-dep write (`write` step) MUST still replay byte-identically.
- **FR-011**: When `ui_kit_id = "none"` (or `ui_kit` interview input is blank), the
  `ui-kit-init` gate step MUST be dropped from the frozen plan via the `when =
  "ui_kit_id != none"` predicate. No gate prompt fires. The `ui-kit-scaffold`
  python step MUST still execute but exit cleanly (no-op when `ui_kit_id = "none"`).

### Runtime / package-manager resolver (agent-steered answers + deterministic writes)

- **FR-012**: The `resolve` agent step MUST emit three new `agent-steered` answer
  keys: `runtime` (`"bun"` | `"node"`), `node_line` (a node major version string
  e.g. `"22"`, or empty string `""` when `runtime = "bun"`), and a finalized
  `package_manager_pin`. The existing `package_manager_pin` key is reused; the agent
  overrides it with a registry-verified exact version (same `answers_to_persist` key).
- **FR-013**: The `write` step MUST validate `package_manager_pin` matches the shape
  `<name>@<major>.<minor>.<patch>[<prerelease>]` using a `re.fullmatch` guard
  BEFORE writing `package.json["packageManager"]`. A malformed value MUST emit
  `INPUT_VALUE_INVALID` and write nothing. The regex MUST reject "latest", ranges,
  and bare package names.
- **FR-014**: When `runtime = "node"` and `node_line` is non-empty, the `write` step
  MUST write `.node-version` with content `f"{node_line}\n"` via
  `sdk.idempotent_write(reconcile=False)` (write-if-absent; an existing `.node-version`
  is not overwritten). It MUST also merge `{"node": f">={node_line}"}` into
  `package.json["engines"]` via `_patch_package_json`.
- **FR-015**: When `runtime = "bun"`, the `write` step MUST NOT write `.node-version`
  and MUST NOT set `package.json["engines"]`. The `package_manager_pin` starting with
  `"bun@"` is sufficient.
- **FR-016**: The finalized `package_manager_pin` MUST be verified via the existing
  `sdk.verify_pins([package_manager_pin], "npm")` call in init mode. A disconfirmed
  pin (e.g. `bun@latest`, a non-existent version) is rejected before the gate fires.
  The package manager pin is already included in `all_pins` at
  `lang-ts/module.py:223-225`; no new verify call is needed — the existing path covers
  the finalized value.
- **FR-017**: The `write` step MUST validate that `package_manager_pin` name prefix
  is consistent with `package_manager` (the interview choice). If `package_manager =
  "bun"` but `package_manager_pin = "pnpm@9.14.2"`, emit `INPUT_VALUE_INVALID`.

### Ordering + phasing

- **FR-018**: The runtime resolver's `runtime`, `node_line`, and finalized
  `package_manager_pin` answers MUST be available in the frozen plan before the
  `scaffold` python step runs. This is guaranteed by the two-phase plan (003
  FR-011): Phase A runs ALL `kind=agent` steps before Phase B runs any `kind=python`
  step. No new runner change is needed; this FR documents the invariant as a
  testable requirement.

### Step ordering in `module.toml`

- **FR-019**: The final `module.toml` step order MUST be:
  `resolve` (agent) → `pins` (gate, hard, init_only) → `write` (python) →
  `run-generator` (gate, soft) → `scaffold` (python) → `ui-kit-init` (gate, hard,
  init_only, when) → `ui-kit-scaffold` (python).
  The `pins` gate covers the complete decision including test runner, UI kit, and
  runtime answers (all appear in the `{decision}` render). The `run-generator` gate
  guards the external framework scaffolder. The `ui-kit-init` gate guards only the
  UI-kit init command.
- **FR-020**: The `pins` gate message MUST render the new answers (`test_runner`,
  `template_id`, `ui_kit_id`, `ui_kit_init_command`, `runtime`, `node_line`,
  `package_manager_pin`) via the existing `{decision}` substitution at freeze time.
  No change to the gate machinery is needed — `render_answer_block` already renders
  all `mod_answers`.

### Inputs + steering

- **FR-021**: The `lang-ts` `module.toml` MUST declare three new inputs (or validate
  that existing inputs are sufficient): `test_runner` (string, default `""`),
  `ui_kit_id` (string, default `"none"`), `runtime` (string, default `"bun"`). These
  are NOT interview inputs (the agent decides them) but MUST be declared so the
  `when = "ui_kit_id != none"` predicate is parsed without a `MANIFEST_MALFORMED`
  error (004 OQ-2 resolution: a `when` key not declared as a module input is a
  parse-time error).
- **FR-022**: The `lang-ts/steering/resolve.md` MUST be extended to cover the three
  new decision groups: (a) test runner + template_id selection logic (framework →
  recommended runner table); (b) UI kit + init command decision (ui_kit input →
  `ui_kit_id` + literal command + companion pins); (c) runtime selection
  (package_manager → `runtime` + `node_line` + finalized `package_manager_pin`).
  All new `answers_to_persist` keys MUST be documented with their constraints (exact
  pins, enum values, no "latest").

### Verify and determinism

- **FR-023**: All new npm pins emitted by the three depth resolvers MUST be
  registry-verified via the existing `verify_pins` call in the `write` step. No new
  verify call is added; the new pins join the existing `all_pins` list.
- **FR-024**: Plain reproduce MUST be zero-network for all three depth resolvers:
  the agent answers are replayed from `answers.toml` (003 FR-009); `verify_pins`
  is skipped in reproduce mode (existing `inputs.mode == "init"` guard at
  `lang-ts/module.py:227`); the `ui-kit-scaffold` step is SAFE-skipped per FR-010.
- **FR-025**: On `--refresh lang-ts`, ALL three depth resolver answers MUST be
  re-researched (they are part of the same `resolve` agent step). `--refresh` on
  a single key within the step is out of scope for this spec (003 OQ-3: per-key
  `--refresh` granularity is deferred).

## Success Criteria

- **SC-001**: A `lang-ts` init run with `framework = "vite"` and `ui_kit = "none"`
  produces: a pinned `package.json` (with `packageManager = "bun@X.Y.Z"`), a
  `tsconfig.json`, a `vitest.config.ts` from the correct template, no `.node-version`
  — all registry-verified and written deterministically.
- **SC-002**: Reproduce of SC-001 is byte-identical: same `package.json`, same
  `tsconfig.json`, same `vitest.config.ts` from the same `template_id`; zero network
  calls for the agent step or `verify_pins`.
- **SC-003**: A `lang-ts` init with `ui_kit = "shadcn"` and `--non-interactive` (no
  `--allow-ui-kit-init`): `package.json` contains shadcn + Tailwind v4 pins;
  `ui-kit-scaffold` is SAFE-skipped; `STACK-NOTES.md` contains the manual init
  command.
- **SC-004**: A `lang-ts` init with `ui_kit = "shadcn"` and `--allow-ui-kit-init`
  in a TTY that confirms the gate: `ui-kit-scaffold` runs the validated `shadcn init`
  command; the command is checked against the allowlist before execution.
- **SC-005**: A plain reproduce of a project with `ui_kit_id = "shadcn"` (already
  initialized): the `ui-kit-init` gate does NOT prompt (init_only auto-proceed);
  `ui-kit-scaffold` is SAFE-skipped with a note in `STACK-NOTES.md`.
- **SC-006**: A `lang-ts` init with `runtime = "node"`, `node_line = "22"`,
  `package_manager_pin = "pnpm@9.14.2"`: `.node-version` = `"22\n"`,
  `package.json["engines"]["node"] = ">=22"`, `package.json["packageManager"] =
  "pnpm@9.14.2"`.
- **SC-007**: A `package_manager_pin = "bun@latest"` emitted by the agent is
  rejected as `INPUT_VALUE_INVALID` before the gate fires; nothing is written.
- **SC-008**: A `package_manager_pin` name inconsistent with `package_manager`
  interview choice (e.g. PM=bun, pin=pnpm@9) is rejected as `INPUT_VALUE_INVALID`.
- **SC-009**: An unknown `template_id` emitted by the agent is rejected as
  `INPUT_VALUE_INVALID`; no config file is written and the run exits non-zero.
- **SC-010**: A `ui_kit_init_command` not matching the allowlist is rejected as
  `INPUT_VALUE_INVALID` before execution; the gate fires but the `ui-kit-scaffold`
  step hard-errors without running the command.
- **SC-011**: Phase ordering: an instrumented test asserts that `runtime`,
  `node_line`, and `package_manager_pin` are present in `resolved_answers` before
  the `scaffold` python step executes (Phase B).
- **SC-012**: `when = "ui_kit_id != none"` drops the `ui-kit-init` gate from the
  frozen plan when `ui_kit_id = "none"`; the `ui-kit-scaffold` step runs as a no-op.

## Out of Scope

- A separate `ts-test-resolver`, `ts-ui-resolver`, or `ts-runtime-resolver` module.
  All three are new answer groups on the existing `lang-ts` module.
- Per-key `--refresh` granularity (e.g. `--refresh lang-ts.test_runner`). The
  roadmap's 003 OQ-3 defers this; `--refresh lang-ts` re-researches all three depth
  groups together.
- Go / Rust / Python depth resolvers. The pattern is identical but instantiated here
  only for TypeScript.
- Tailwind v4 configuration beyond dependency pins — the `write` step writes the
  pinned `@tailwindcss/vite` or equivalent dep; the `shadcn init` command sets up
  the config. Manual Tailwind config authoring is out of scope.
- A TUI / interactive template picker at the gate. The agent decides `template_id`;
  the gate shows it; the user confirms or declines the whole decision (consistent with
  spec 004's "no inline editing at the gate" out-of-scope ruling).
- `nuxt/ui` or other UI kits beyond `shadcn` and `nuxt-ui` as `ui_kit_id` values in
  v1. The enum is explicitly extendable; additional kits are added by amending the
  steering doc + adding an allowlist entry + a template (if applicable).
- Staleness/CVE advisory (roadmap rank #10). That is a separate reproduce-mode agent
  step with a distinct gate; it does not mutate pins.

## Assumptions

- The 003/004 runner is in place and green (613 tests at 004 ship). The two-phase
  plan (FR-018), `init_only` gate (FR-007), `when` predicate (FR-007/FR-011),
  `verify_pins` (FR-016/FR-023), and `sdk.idempotent_write` (FR-014) are all
  available with no new runner changes.
- `when = "ui_kit_id != none"` requires `ui_kit_id` to be declared as a module input
  (per 004 OQ-2 resolution). FR-021 adds the declaration. The `when` predicate
  evaluates `"none"` as the string `"none"` (not Python `None`) — consistent with
  the 004 OQ-1 coercion rule (both sides rendered as strings).
- `sdk.append_if_absent` is usable for `STACK-NOTES.md` entries (the manual init
  command serves as the idempotency marker). This is a reuse of the existing API
  (verified: `sdk.py` exports `append_if_absent`).
- Template files under `lang-ts/templates/<template_id>/` are committed to the repo
  and version-stable for a given module version. A template change bumps the module
  version (SemVer patch for non-breaking changes to template content).
- The UI-kit init command allowlist is intentionally narrow at launch. The risk of
  an overly permissive allowlist is a supply-chain injection; broadening the allowlist
  is a deliberate policy change requiring a PR, not a steering-doc update.
- `_patch_package_json` (lang-ts/module.py:93-146) can be extended to accept an
  `engines` dict argument without breaking its existing callers. The extension is
  additive (new optional parameter).

## Dependencies & Open Questions

**Hard dependency**: specs 003 + 004 (shipped). This spec adds no new runner
machinery; it extends the `lang-ts` module using only the shipped two-phase plan,
`init_only` gate, `when` predicate, `sdk.verify_pins`, and `sdk.idempotent_write`.

**Soft dependency on spec 012** (org-overlay + package-add): none. 013 touches only
`lang-ts`; package-add is independent.

**Open questions** (OQ-1 … OQ-4) requiring human decisions are tracked in
`memory.md`. None block spec authoring; they are resolved before or during
implementation.
