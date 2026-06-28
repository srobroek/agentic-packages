# Feature Specification: AGENTS.md Architecture Section

**Feature Branch**: `feat/project-setup-modular-redesign` (continues) → likely a
dedicated `feat/agents-md-architecture` branch

**Created**: 2026-06-28

**Status**: **Implemented (2026-06-28)** — all FRs (FR-001…FR-012) built and green
(commit `8c7e40c`); SDK primitives `scan_top_level_dirs`/`splice_between_sentinels`
(`sdk.py:276`/`:300`) + the agents-md `resolve-arch`→`arch-gate`→`splice` steps on
the proven 003/004 machinery (zero runner change). 28 spec tests pass (13
`test_sdk_splice.py` + 15 `test_module_agents_md.py`); full suite green (648 passed,
4 deselected). SC-001/005/006/008 are runner-level and honestly DEFERRED
(covered-by-construction via `test_two_phase_resolver.py`); see `memory.md` → AS-BUILT.

**Input**: Roadmap rank #4 `agents-md-architecture-section` from
`reviews/tier2-agentic-features-roadmap.md:53-57` — "stack-aware conventions in
AGENTS.md". Builds on the base `agents-md` module (spec 001), the Tier-2 resolver
pattern (spec 003), and the full gate machinery (spec 004).

## Overview

The base `agents-md` module (spec 001) writes a skeleton `AGENTS.md` with static
placeholder comments: `<!-- ARCHITECTURE: to be filled by agent based on project
setup -->` and `<!-- BUILD COMMANDS: to be filled by agent after language setup -->`.
Every agent that subsequently works in the repo encounters these unfilled stubs and
must invent project conventions from scratch — or worse, invent the wrong ones.

This feature adds the **architecture section resolver**: a Tier-2 agent step on the
`agents-md` module that reads the frozen answer set (project layout, languages,
resolved framework + pinned deps from the stack resolver, speckit enablement) plus a
**read-only tree scan** of the project directory, and authors a project-specific
`## Architecture & Conventions` section. A `kind=python` step then splices that
section into `AGENTS.md` between fixed `<!-- BEGIN ps:architecture -->` / `<!-- END
ps:architecture -->` sentinels, replacing only that span.

The determinism contract is:

> Agent decides ONE `architecture_md` text block + a list of
> `agent_editable_globs` (agent-steered answers). Python wraps the block in fixed
> sentinels, splices only the sentinel-bounded span in `AGENTS.md` via
> `idempotent_write(reconcile=true)`, and validates that every top-level directory
> referenced in the block actually exists on disk (warn, never write phantom paths).
> Frozen answer → identical bytes; persisted as project provenance so re-runs replay
> it without the agent. The write is guarded by a hard `kind=gate` showing the
> rendered diff before the splice — AGENTS.md steers every future agent in the repo,
> so the write is confirmed.

This spec introduces **two new SDK primitives**: a sentinel-splice helper
(`splice_between_sentinels`) that replaces a marked span inside an existing file,
and a `scan_top_level_dirs` helper that returns the set of existing top-level
directories without traversing further. Both are pure Python, no network, no MCP.
Neither requires changes to the executor or runner pipeline — the feature is entirely
within the `agents-md` module extension and the SDK.

**Why this matters now.** AGENTS.md is the highest-value file project-setup writes:
it steers every future agent in the repo. The skeleton is fine as a bootstrap, but a
project that chose FastAPI + SQLAlchemy + asyncpg has materially different
architecture conventions than one that chose Nuxt + Prisma. Writing those conventions
once from the frozen decision set and persisting them means every future agent (in
Claude Code, in Codex, in CI-lint agents) gets project-accurate guidance rather than
generic stubs — without any human having to hand-edit the skeleton.

## Current state (verified — citations, do not re-derive)

All file:line references verified against shipped code on
`feat/project-setup-modular-redesign` at HEAD `7779c27`.

- **The base `agents-md` module writes a one-step `kind=python` skeleton.**
  `modules/agents-md/module.toml:39-41` declares a single step `[[steps]] id =
  "write" kind = "python"`. There is no agent step, no gate step, and no sentinel
  machinery on this module today.
- **The `## Architecture` section is a static placeholder comment.**
  `modules/agents-md/templates/single.md:22-24` contains
  `## Architecture\n<!-- ARCHITECTURE: to be filled by agent based on project setup
  -->` verbatim; `templates/monorepo.md:22-24` is identical. No dynamic content is
  written into this section by any module today.
- **`idempotent_write` does full-file replacement; it has no sentinel-splice mode.**
  `runner/sdk.py:182-257` implements `idempotent_write` with `reconcile=True`
  overwriting the entire file to match `body`. There is no existing
  "replace-only-the-span-between-markers" path. The sentinel-splice helper
  (`splice_between_sentinels`) is fully net-new.
- **No `scan_top_level_dirs` primitive exists.** The SDK (`runner/sdk.py:1-657`)
  and contracts (`runner/contracts.py`) contain no directory-scanning utility.
  `os.scandir` / `Path.iterdir` are unused. The helper is net-new.
- **The `agents-md` module already reads `layout`, `project_name`, `org` from the
  frozen plan.** `modules/agents-md/module.py:83-86` loads these three answers via
  `FrozenInputs`. Stack-resolver answers (`framework`, `pinned_deps`, `lang`) live
  on their respective modules (`lang-python`, `lang-ts`) in the frozen plan; reading
  them cross-module is supported by `load_frozen_inputs(plan_path, module_id=<other>)`
  because `FrozenInputs` simply reads that module's answer map from the shared
  plan.json.
- **The agent step is handled by the runner's Tier-2 subsystem; `module.py` only
  handles `kind=python` steps.** `modules/lang-python/module.py:522-526` shows the
  pattern: `STEP_HANDLERS = {"write": _do_write}` — agent and gate steps are handled
  by the executor's `run_agent_step` / `run_gate_step` and never dispatched to
  `module.py`. The architecture module follows the same pattern.
- **The existing `agents-md` write uses `idempotent_write` with `reconcile=True`.**
  `modules/agents-md/module.py:89-94`: `diff = sdk.idempotent_write("AGENTS.md",
  body, reconcile=True, inspect=args.inspect)`. The new `splice` step replaces a
  sub-span; the existing `write` step is left untouched.
- **The Tier-2 gate shape is fully available.** `runner/manifest.py:62-71` shows
  `StepSpec` has `hardness`, `allow_flag`, `skip_flag`, `when`, `init_only` fields
  (spec 004). The new gate uses `hardness="hard"`, `allow_flag="allow-arch-write"`,
  `init_only=True` — the same pattern as the lang-python `pins` gate
  (`modules/lang-python/module.toml:43-49`).
- **`reproduce.run_agent_phase` already handles `kind=agent` steps in the correct
  phase order (Phase A before Phase B).** `runner/reproduce.py` (per spec 003
  AS-BUILT): agent steps run first, fold their decisions into `final_answers`,
  before `build_plan` freezes v2 and Phase B runs the python steps. The new
  `resolve-arch` agent step participates in Phase A with no runner changes.
- **The `{decision}` token composition exists.** `runner/plan.py:159-168` (per spec
  003 AS-BUILT and spec 004 Fact 3): a gate message containing `{decision}` is
  expanded with `render_answer_block(mod_answers)` at freeze time. The new
  `arch-gate` gate uses this to render the proposed section text in the gate message.
- **Cross-module answer reads are possible today.** `sdk.load_frozen_inputs` accepts
  any `module_id`; the `lang-python` write step uses this to read its own answers.
  Reading a sibling module's answers (`lang-python`, `lang-ts`) from within the
  `agents-md` `module.py` is supported by calling `load_frozen_inputs(plan_path,
  module_id="lang-python")` — the frozen plan contains every module's answers.

## Settled decisions

Letters continue a fresh A-series (per-feature restart, per house style).

- **A — The feature EXTENDS the existing `agents-md` module; no new module is
  created.** The three new steps (`resolve-arch`, `arch-gate`, `splice`) are appended
  to `modules/agents-md/module.toml` and handled in `modules/agents-md/module.py`.
  A new steering doc `modules/agents-md/steering/resolve-arch.md` is added. The
  base `write` step is untouched — it still writes the full AGENTS.md skeleton on
  first run. The `splice` step then fills in the sentinel-bounded architecture span.
  Step order: `write` → `resolve-arch` → `arch-gate` → `splice` (write first so the
  file exists before the splice; the sentinel markers are written by the base
  template in `write`).
- **B — The sentinel markers are fixed HTML comments in the base template.**
  `<!-- BEGIN ps:architecture -->` and `<!-- END ps:architecture -->` are injected
  into `modules/agents-md/templates/single.md` and `templates/monorepo.md`, replacing
  the existing `<!-- ARCHITECTURE: to be filled by agent based on project setup -->`
  placeholder. If the markers are absent from an existing `AGENTS.md` (the file
  predates this feature or was hand-edited), the `splice` step appends the section
  after the `## Architecture` heading (warn + append, never silently skip).
- **C — The agent decides exactly two answers: `architecture_md` (a text block) and
  `agent_editable_globs` (a list of path glob patterns).** Both are persisted with
  `source="agent-steered"`. `architecture_md` is the raw markdown text of the
  section body (no sentinel markers — python adds those). `agent_editable_globs` is
  the list of file patterns the architecture section declares as agent-editable
  (e.g. `["src/**", "tests/**"]`); it is persisted for provenance and future use by
  tooling. The agent NEVER emits the sentinel markers, headings, or the surrounding
  AGENTS.md structure — those are python's concern.
- **D — The `splice` step uses a new SDK primitive `splice_between_sentinels`.** The
  primitive takes a file path, a begin-marker string, an end-marker string, and a
  replacement body, and returns a `Diff` (kind="create" if the file was newly
  written, "modify" if the span was replaced, "skip" if the on-disk span is already
  identical). It does NOT use `idempotent_write` for the splice because
  `idempotent_write` replaces the whole file; `splice_between_sentinels` replaces
  only the bounded span. Both are in `sdk.py` and share the same idempotent,
  reconcile-aware contract. The fallback behavior when markers are absent is
  configurable: `missing="append"` (default for this use) appends the section after
  the `## Architecture` heading, emitting a warning; `missing="skip"` skips and warns.
- **E — The `splice` step validates referenced top-level directories before writing.**
  After composing the section body, `module.py` calls `scan_top_level_dirs()` (a new
  SDK helper returning the set of existing top-level dir names in `$PROJECT_DIR`)
  and strips any `path/…` table row from the `architecture_md` that references a
  top-level directory not in that set. Stripped rows are reported as warnings. A
  phantom-path write is NEVER emitted — the agent's output is structurally filtered,
  not trusted blindly. A correctly-specced project (all dirs created by `dirs-scaffold`
  before `agents-md` runs) produces zero warnings.
- **F — Reproduce replays zero-network; `--refresh` is the only re-research path.**
  The `resolve-arch` step is `kind=agent`. In reproduce mode the executor
  (`reproduce.run_agent_phase`) already replays committed `agent-steered` answers
  zero-network (spec 003 FR-009). On reproduce the `arch-gate` gate carries
  `init_only=True` — it auto-proceeds (does not prompt, does not block) so the
  deterministic splice replays byte-identically. Only `--refresh agents-md` re-arms
  the agent step and re-triggers the gate. This is identical to the lang-python
  pattern (`modules/lang-python/module.toml:43-49`).
- **G — The gate is hard, `init_only`, and uses `allow_flag="allow-arch-write"`.** In
  CI (`--non-interactive`) without `--allow-arch-write`, the gate SAFE-skips the
  splice. The skeleton AGENTS.md (written by the base `write` step) is always written
  — only the architecture-section splice is gated. This is consistent with the
  blast-radius principle: the skeleton is deterministic and low-stakes; the
  architecture section is an agent judgment that steers every future agent in the
  repo.
- **H — The agent reads cross-module frozen answers but NEVER reads `$PROJECT_DIR`
  files beyond the top-level directory list.** The tree scan is read-only and
  shallow: one `os.scandir($PROJECT_DIR)` call yielding top-level entries (no
  recursion, no file content reads). The agent is given the directory names as a
  structured input, not raw file contents — preventing prompt injection from stray
  files in the project tree. The agent MUST NOT be given file contents.
- **I — The agent-editable-globs answer is provenance only in 006; it is not yet
  enforced.** `agent_editable_globs` is persisted so future tooling (e.g. a Codex
  config module or an AGENTS.md linter) can read it from `answers.toml`. This spec
  does not build any enforcement — only the persist + splice of the declared globs
  as a section in AGENTS.md.

## User Scenarios & Testing

**Story → gate → FR → SC traceability**:

| Story | Gate | FRs | SC | Priority |
|---|---|---|---|---|
| US1 | G-arch (whole section confirm) | FR-001…FR-008 | SC-001…SC-004 | P1 |
| US2 | none (reproduce replay) | FR-009, FR-010 | SC-005 | P1 |
| US3 | refresh path | FR-010, FR-011 | SC-006 | P2 |
| US4 | phantom-path guard | FR-007 | SC-007 | P1 |
| US5 | missing-markers fallback | FR-005 | SC-008 | P2 |
| US6 | CI / non-interactive | FR-008 | SC-009 | P1 |

### User Story 1 — Fresh init writes a stack-aware architecture section (Priority: P1)

A user scaffolds a FastAPI + asyncpg project with `lang-python` enabled. After the
stack resolver commits the pinned decision, the `agents-md` module's `write` step
lays down the skeleton AGENTS.md (with sentinel markers). The `resolve-arch` agent
step reads the frozen framework (`fastapi`), language (`python@3.13`), pinned deps
(`fastapi@0.115.5`, `asyncpg@0.29.0`, …), and the top-level directory list
(`src/`, `tests/`, `.github/`, etc.), then authors a concrete Architecture &
Conventions section: path table, framework conventions, dev-tool guidance, agent
glob list. The `arch-gate` shows the rendered diff. On confirm, `splice` writes
exactly the sentinel-bounded span.

**Acceptance Scenarios**:

1. **Given** a frozen plan with `lang-python` answers (framework=fastapi, pinned
   deps populated), **When** `resolve-arch` runs, **Then** it emits `architecture_md`
   (non-empty text referencing the framework by name) + `agent_editable_globs` as
   `agent-steered` answers — no files written.
2. **Given** the frozen `architecture_md`, **When** the `arch-gate` fires, **Then**
   the gate message shows the full rendered section text as the diff body, with the
   sentinel markers visible, before any write.
3. **Given** the user confirms the gate, **When** `splice` runs, **Then**
   `AGENTS.md` contains the text exactly between `<!-- BEGIN ps:architecture -->` and
   `<!-- END ps:architecture -->`, and the rest of the file is byte-identical to the
   base skeleton.
4. **Given** a referenced top-level dir in `architecture_md` that does NOT exist on
   disk, **When** `splice` runs, **Then** that path table row is stripped, a warning
   is emitted, and the write still proceeds with the remaining rows.

### User Story 2 — Reproduce replays zero-network (Priority: P1)

A teammate clones the repo and runs reproduce. The committed `agent-steered`
`architecture_md` answer replays into the splice write with zero network calls — no
agent re-invocation, no tree re-scan (the top-level dirs are not an input to the
python step; only the frozen text block is).

**Acceptance Scenarios**:

1. **Given** committed `agent-steered` `architecture_md` in `answers.toml`, **When**
   reproduce mode runs, **Then** `resolve-arch` replays the committed answer with
   zero network calls (verified by a network-blocking test double).
2. **Given** the replayed answer, **When** `splice` runs, **Then** `AGENTS.md`'s
   architecture span is byte-identical to the init output (Tier-1 for the same frozen
   answer).
3. **Given** plain reproduce (no `--refresh`), **When** `arch-gate` would fire,
   **Then** it auto-proceeds (`init_only=True`) — no prompt, no `gate_blocked`.

### User Story 3 — `--refresh agents-md` re-researches the architecture section (Priority: P2)

A maintainer has reorganized the repo (new packages added, framework upgraded). They
run `--refresh agents-md` to update the architecture section. The agent re-reads the
frozen plan (now updated by a prior stack-resolver refresh) + the current top-level
dirs, authors an updated section, the gate shows the old-vs-new diff, and on confirm
the new text is spliced in.

**Acceptance Scenarios**:

1. **Given** a prior committed `architecture_md`, **When** `--refresh agents-md`
   runs, **Then** `resolve-arch` re-invokes the agent with the current frozen answers
   + top-level dirs.
2. **Given** a new proposed `architecture_md`, **When** `arch-gate` fires, **Then**
   the gate shows the proposed new text (old text is the on-disk sentinel span; diff
   is visible).
3. **Given** a declined gate, **Then** the committed `architecture_md` and the on-disk
   `AGENTS.md` architecture span are unchanged.

### User Story 4 — Phantom-path guard strips non-existent dirs (Priority: P1)

The agent proposes a path table row for `services/` which does not exist in the
project (a single-package app, not a monorepo). The `splice` step validates against
the on-disk top-level dirs and strips the `services/` row, emitting a warning.

**Acceptance Scenarios**:

1. **Given** `architecture_md` containing a `| \`services/\`` table row, **When**
   `$PROJECT_DIR/services/` does not exist, **Then** the row is stripped, a
   `WARN: phantom path 'services/' referenced in architecture_md — row removed`
   warning is emitted, and the splice writes the filtered text.
2. **Given** all referenced paths exist on disk, **Then** no stripping occurs and
   no phantom-path warning is emitted.

### User Story 5 — Missing sentinel markers fallback (Priority: P2)

An existing `AGENTS.md` (written before this feature, or hand-edited to remove the
markers) has no sentinel markers. The `splice` step falls back to appending the
marked section after the `## Architecture` heading, emitting a warning.

**Acceptance Scenarios**:

1. **Given** an `AGENTS.md` without `<!-- BEGIN ps:architecture -->`, **When**
   `splice` runs, **Then** the section is appended after the `## Architecture`
   heading (or at end-of-file if the heading is absent), a
   `WARN: sentinel markers absent — appending architecture section` warning is
   emitted, and the file is not otherwise modified.
2. **Given** subsequent reproduce runs with the now-marker-present `AGENTS.md`,
   **Then** the sentinel-splice path is taken (markers now present, no warning).

### User Story 6 — CI / non-interactive safe-skip (Priority: P1)

In a CI environment (`--non-interactive`) without `--allow-arch-write`, the base
skeleton `AGENTS.md` is written (deterministic, no gate) but the architecture splice
is SAFE-skipped. The build does not deadlock.

**Acceptance Scenarios**:

1. **Given** `--non-interactive` with no `--allow-arch-write`, **When** `arch-gate`
   fires, **Then** it SAFE-skips, the splice does not run, and the run exits green
   with the skeleton AGENTS.md present.
2. **Given** `--non-interactive --allow-arch-write`, **When** `arch-gate` fires,
   **Then** it auto-approves and the splice runs.
3. **Given** the base `write` step (no gate), **Then** the skeleton is always written
   in CI regardless of `--allow-arch-write` (the gate guards only the splice step).

### Edge Cases

- **`lang-python` or `lang-ts` not enabled**: the agent receives empty framework/pins
  inputs. It still authors a section (generic for the layout), but without
  language-specific conventions. No error — missing cross-module answers fall back to
  their defaults via `FrozenInputs.get_str(default="")`.
- **Both `lang-python` and `lang-ts` enabled** (full-stack project): the agent
  receives both sets of frozen answers and authors a poly-language section. Both are
  inputs to `resolve-arch`; the steering doc describes how to handle them.
- **`architecture_md` is empty or whitespace-only**: the agent step failed to produce
  useful content. The `splice` step MUST still write the sentinel-bounded empty span
  (so subsequent reproduce is deterministic) but emits a warning. It does NOT write
  a phantom-filled block.
- **`agents-md` module disabled**: the base module is `default_enabled=true`
  (`module.toml:12`). If a user disables it, the splice step never runs. No cascade
  error.
- **AGENTS.md deleted between init and reproduce**: the `splice` step creates the
  file anew (the sentinel block becomes the whole file content). It warns that no
  base skeleton was found but proceeds, keeping the architecture content.
- **A `<!-- BEGIN ps:architecture -->` marker exists but the `<!-- END
  ps:architecture -->` marker is missing** (truncated or hand-edited): the splice
  step emits an error (`ARCH_SENTINEL_MALFORMED`) and SAFE-skips, never partially
  writing the file.

## Requirements

### Sentinel-splice SDK primitive

- **FR-001**: `runner/sdk.py` MUST gain a `splice_between_sentinels(path, begin,
  end, body, *, project_dir, inspect, missing)` function that replaces the content
  between `begin` and `end` markers in a file with `body` (the replacement text,
  WITHOUT the marker lines themselves). It MUST return a `Diff` (`kind="create"` /
  `"modify"` / `"skip"`). The `inspect=True` path MUST produce the identical diff
  kind and preview as the real write (Tier-1 guarantee). The function MUST be
  pure Python, stdlib-only, no network.
- **FR-002**: `splice_between_sentinels` MUST handle the `missing` parameter:
  `missing="append"` (default) appends `begin + "\n" + body + "\n" + end + "\n"`
  after the first occurrence of `## Architecture` (case-insensitive) or at
  end-of-file if the heading is absent, and returns `kind="modify"` (or `"create"`
  for a new file); `missing="error"` returns `kind="skip"` and appends a
  `WARN: sentinel markers absent` message to the caller-supplied warnings list (no
  exception raised). A detected `begin` with no matching `end` MUST always use
  `missing="error"` behavior, regardless of the `missing` parameter, and MUST
  append a `WARN: malformed sentinel span (begin without end)` message.
- **FR-003**: `splice_between_sentinels` MUST be idempotent: if the on-disk content
  between the markers is ALREADY identical to `body`, it returns `kind="skip"` with
  no write. The full-file content outside the markers MUST be preserved byte-for-byte.

### Directory-scan SDK primitive

- **FR-004**: `runner/sdk.py` MUST gain a `scan_top_level_dirs(project_dir)` function
  that returns a `frozenset[str]` of top-level DIRECTORY names (not files) directly
  under `project_dir`, using `os.scandir` with no recursion. Hidden directories
  (names starting with `.`) MUST be included. The function MUST be pure Python,
  stdlib-only, no network, and MUST NOT raise on an empty or missing project dir (it
  returns an empty frozenset).

### `agents-md` module extension

- **FR-005**: `modules/agents-md/module.toml` MUST gain three new `[[steps]]` entries
  appended AFTER the existing `write` step (so the skeleton always lands first):
  - `id="resolve-arch"`, `kind="agent"`, `steering="steering/resolve-arch.md"`
  - `id="arch-gate"`, `kind="gate"`, `hardness="hard"`,
    `allow_flag="allow-arch-write"`, `init_only=true`,
    `message="Architecture section for AGENTS.md (agent-authored):\n{decision}\nWrite this section to AGENTS.md?"` 
  - `id="splice"`, `kind="python"`
- **FR-006**: `modules/agents-md/module.toml` MUST gain two new `[[inputs]]` entries
  (consumed by `module.py`'s `splice` handler, NOT by the agent step directly):
  - `key="architecture_md"`, `type="string"`, `required=false`, `default=""`
    (populated by the agent step)
  - `key="agent_editable_globs"`, `type="list"`, `required=false`, `default=[]`
    (populated by the agent step)
- **FR-007**: `modules/agents-md/module.py` MUST implement a `_do_splice` handler for
  the `splice` step that:
  1. Reads `architecture_md` and `agent_editable_globs` from `FrozenInputs`.
  2. Calls `scan_top_level_dirs($PROJECT_DIR)` and filters any path table row in
     `architecture_md` that references a top-level directory not in the returned set
     (warn for each removed row; continue with the filtered text).
  3. Calls `splice_between_sentinels("AGENTS.md", BEGIN_SENTINEL, END_SENTINEL,
     filtered_body, inspect=args.inspect, missing="append")`, collecting any warnings.
  4. Emits a `ModuleResult` with `status="ok"`, `files_written` populated from the
     diff, and all warnings.
  The handler MUST NOT make network calls. It MUST work in both `init` and
  `reproduce` modes (in reproduce the frozen `architecture_md` is the committed text,
  replayed byte-identically).
- **FR-008**: The sentinel markers `<!-- BEGIN ps:architecture -->` and
  `<!-- END ps:architecture -->` MUST be inserted into both base templates
  (`templates/single.md` and `templates/monorepo.md`), replacing the existing
  `<!-- ARCHITECTURE: to be filled by agent based on project setup -->` placeholder,
  so that a fresh `write` step produces a file with the markers already in place for
  the `splice` step.

### Steering document

- **FR-009**: `modules/agents-md/steering/resolve-arch.md` MUST be created as the
  agent step steering document. It MUST instruct the agent to:
  1. Read the provided frozen inputs: `layout`, `project_name`, `org`, `framework`
     (from `lang-python` / `lang-ts` answers if populated), `pinned_deps`, top-level
     directory names.
  2. Check for available MCP tools (context7) for richer framework doc lookup, but
     proceed without them if absent — never stall on MCP absence.
  3. Author `architecture_md`: a section body starting with a brief project
     description, then a path table for existing top-level directories (using only
     names from the provided directory list — never invent paths), then framework
     conventions, then a note on agent-editable areas.
  4. Emit `agent_editable_globs`: a list of glob patterns covering source code and
     tests (`["src/**", "tests/**"]` for single layout; `["apps/**", "packages/**",
     "libs/**", "tests/**"]` for monorepo layout, adjusted for actual dirs present).
  5. NEVER write files. NEVER invent directory paths not in the provided list. NEVER
     include the sentinel markers in `architecture_md` (python adds those). Emit EXACT
     `agent-steered` answers for both keys.

### Determinism and compatibility

- **FR-010**: In reproduce mode the `resolve-arch` step MUST replay the committed
  `agent-steered` `architecture_md` answer from `answers.toml` with zero network
  calls — identical behavior to spec 003 FR-009 for the stack resolver. The `splice`
  step MUST produce byte-identical output from the same frozen `architecture_md`.
- **FR-011**: `--refresh agents-md` (spec 003 FR-010) MUST re-invoke the `resolve-arch`
  agent step, re-produce `architecture_md`, present the updated text at `arch-gate`,
  and on confirm splice the new text in. A declined refresh MUST leave the committed
  `architecture_md` and the on-disk AGENTS.md architecture span unchanged.
- **FR-012**: The full suite (613 at 004 ship) MUST stay green. The existing `write`
  step behavior is unchanged; this spec adds steps only. The base `agents-md`
  functional tests (`test_module_agents_md.py`) MUST continue to pass unchanged;
  new tests are additive.

## Success Criteria

- **SC-001**: The `resolve-arch` agent step emits `architecture_md` (non-empty string)
  + `agent_editable_globs` (non-empty list) as `agent-steered` answers when given a
  non-empty frozen framework; a ScriptedIO test with a canned agent response verifies
  the answers flow through the agent phase and into the frozen plan before `splice`
  runs.
- **SC-002**: `splice_between_sentinels` is idempotent: a second call with the same
  body returns `kind="skip"` and does not modify the file; a different body returns
  `kind="modify"` and replaces only the sentinel span, leaving surrounding content
  byte-identical (unit test).
- **SC-003**: The `splice` step writes the correct sentinel-bounded span into
  `AGENTS.md`; the rest of the file (before `BEGIN` and after `END`) is unchanged
  byte-for-byte (end-to-end test against a real temp dir).
- **SC-004**: A phantom-path row (`| \`nonexistent/\` |`) in a canned `architecture_md`
  is stripped with a warning; the splice writes the filtered text (unit test with a
  stubbed `scan_top_level_dirs` returning a known set).
- **SC-005**: A reproduce run with committed `agent-steered` answers produces zero
  network calls for the `resolve-arch` step and writes a byte-identical architecture
  span (network-blocking test double + byte comparison).
- **SC-006**: `--refresh agents-md` with a ScriptedIO new agent response updates
  `architecture_md`; a declined gate leaves the committed answer and AGENTS.md span
  unchanged.
- **SC-007**: An `AGENTS.md` without sentinel markers receives the appended section
  after `## Architecture` with a warning; a subsequent reproduce splice-replaces
  correctly (two-run integration test).
- **SC-008**: `--non-interactive` without `--allow-arch-write` writes the skeleton
  AGENTS.md (base `write` step) but SAFE-skips the splice; with `--allow-arch-write`
  the splice runs (non-interactive integration test).
- **SC-009**: `scan_top_level_dirs` returns the correct set for a test temp dir with
  known directories + files; hidden dirs are included; the function returns an empty
  frozenset for a missing project dir without raising (unit test).

## Out of Scope

- **Enforcement of `agent_editable_globs`**: the persisted glob list is provenance
  only in 006. A future module (e.g. a Codex config writer or an AGENTS.md linter)
  may read and enforce it; that is not built here.
- **Filling the `## Build & Run` section** or any other placeholder comment beyond
  the `## Architecture` sentinel span. Those remain agent-fillable stubs; they are
  not addressed by this spec.
- **Reading project file contents** in the agent context: the tree scan is
  intentionally shallow (top-level directory names only) to prevent prompt injection.
  Deep file inspection is out of scope.
- **Multiple sentinel spans in one file**: `splice_between_sentinels` handles exactly
  one BEGIN/END pair per call. Multiple architectural sub-sections would require
  multiple calls or a richer sentinel grammar; that generalization is deferred.
- **Cross-module answer unification / a shared resolver context object**: the
  `resolve-arch` agent reads sibling module answers via separate `load_frozen_inputs`
  calls. A unified "project context" object across modules is a runner-level design
  question deferred to a later spec.
- **Applying `agent_editable_globs` to Codex `.codex/config.toml`**: a natural
  follow-on (generate the Codex `file_rules` from these globs), but a separate
  module concern outside `agents-md`.
- **Changing the 001/003/004 runner contract**: no changes to the executor, pipeline,
  reproduce, manifest parser, or gate machinery are needed. All new behavior is
  within the module extension and the SDK.

## Assumptions

- The 003 + 004 runner (two-phase plan, reproduce-replay, gate-blocking `apply`,
  `init_only` gate bypass, `{decision}` composition, full suite 613 green) is in
  place.
- `dirs-scaffold` runs before `agents-md` in topo order (per spec 001 ordering) so
  the top-level directories are already present on disk when `splice` runs at init.
  The `scan_top_level_dirs` call therefore reflects the true project structure.
- The `lang-python` / `lang-ts` modules' frozen answers are present in the plan when
  `resolve-arch` runs (Phase A runs all agent steps after all interview answers are
  collected; the stack resolver's `resolve` step runs in Phase A of the SAME run, so
  its answers are in `final_answers` before `build_plan` freezes v2, and thus
  available to any Phase-A agent step of any other module).
- HTML-comment sentinel markers (`<!-- BEGIN/END ps:architecture -->`) are safe to
  include in Markdown AGENTS.md files — they are invisible to most Markdown renderers
  and do not interfere with agent readability.
- The `agents-md` base template modification (adding sentinel markers) is
  backward-compatible: existing AGENTS.md files without markers trigger the
  `missing="append"` fallback, which is correct behavior for brownfield projects.

## Dependencies & Open Questions

**Dependency on 003 (resolved, ship-order):** The two-phase plan and the reproduce-
replay contract (spec 003 FR-009/011) are prerequisites. 006 does not work correctly
without them — the reproduce zero-network guarantee requires the committed
`architecture_md` to be replayed from `answers.toml`, not re-derived. 003 is
implemented and green.

**Dependency on 004 (resolved, ship-order):** The `init_only` gate bypass and the
`allow_flag` mechanism are prerequisites for the `arch-gate` design (FR-008 of spec
004, `init_only=True` on the gate). 004 is implemented and green.

**Dependency on 005 (resolved):** The 3-line `import sdk` shim for modules is the
current pattern (spec 005 OQ-1). 006 follows it.

**Remaining open questions** (OQ-1 … OQ-3, all design-detail / LOW) are tracked in
`memory.md` and do not block implementation. None require human input before
planning; they are resolvable by the implementer.
