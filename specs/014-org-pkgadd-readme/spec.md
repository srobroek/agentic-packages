# Feature Specification: Org-Convention Overlay, Monorepo Package-Add Resolver, README Draft

**Feature Branch**: `feat/project-setup-modular-redesign` (continues) → likely a
dedicated `feat/org-pkgadd-readme` branch

**Created**: 2026-06-28

**Status**: Draft (2026-06-28)

**Input**: Roadmap rank #12 from `reviews/tier2-agentic-features-roadmap.md` —
"org-convention overlay + monorepo package-add resolver + readme-draft
[low value / medium effort]". Three loosely-coupled extension demonstrations
bundled as one spec because they share the same gate seam and the same module
anatomy: an agent decides overrides/alignment/sections, a python step writes
deterministically, and a gate gives the user visibility before any write.

## Overview

Three sub-features, each a distinct module or module extension:

> **Sub-feature A — Org-convention overlay (`org-policy`)**: A new default-disabled
> module that loads a private org-owned module source from `sources.toml` (pinned
> by git ref/tag — arbitrary code, so must be pinned), runs an agent step that
> maps the org's manifest of mandatory conventions against the user's frozen answers,
> and gates the result: every override the org's policy forces is surfaced
> (user-asked vs mandated) before any write. The policy source is a git repo the
> org controls; the runner fetches it at init via the existing `fetch_source`
> machinery and never re-fetches on plain reproduce (zero network).
>
> **Sub-feature B — Package-add Tier-2 resolver (`package-add` extension)**: The
> existing `package-add` module gains an optional agent step and gate that align the
> new monorepo package's framework choice and version pins with the sibling packages'
> already-frozen pins (read from `answers.toml`). Path-traversal guards
> (`_validate_name` / `sdk.is_safe_relative_path`) are security-pinned and MUST run
> verbatim BEFORE any `mkdir` — agent decisions cannot relax them. A new file-write
> gate covers the new manifest created for the package; a separate, softer gate
> covers the shared root-workspace-manifest edit (adding the new entry).
>
> **Sub-feature C — README draft (`readme-draft`)**: A new default-disabled module
> that runs a single agent step to draft a project README from frozen scaffold facts
> (project name, org, layout, language, framework, resolved stack) and a python step
> that writes `README.md` with `reconcile=false` (write-once, never clobber a
> hand-edited README). The gate fires on first creation only; re-runs are
> unconditionally skipped (the `reconcile=false` guard).

All three follow the 003-established "agent decides → frozen answers → gate →
deterministic python write" seam. Research only happens at init; reproduce replays
frozen agent decisions zero-network. The determinism contract from 003/004 is
inherited intact.

## Current state (verified — citations, do not re-derive)

All file:line references verified against code on `feat/project-setup-modular-redesign`
at HEAD `7779c27`.

- **`package-add` path-traversal guards exist and are security-pinned.**
  `modules/package-add/module.py:61-75` defines `_validate_name`, which checks
  three guards verbatim from the legacy `package-add.sh`: (1) no `/` or `\`,
  (2) not `..`, `.`, or `""`, (3) no embedded `..`. A fourth guard at
  `module.py:137-154` validates `lang` against `_VALID_LANGS`. A fifth guard at
  `module.py:159-177` calls `sdk.is_safe_relative_path(dir_)` on the parent-dir
  argument. Guards run at `module.py:115-134` BEFORE the `target.mkdir` at
  `module.py:199`. These are load-bearing security behaviors that MUST NOT be
  moved, weakened, or bypassed by any agent step in sub-feature B.

- **`package-add` is a single `kind=python` step today.**
  `modules/package-add/module.toml:39-41` declares one step `{id="add",
  kind="python"}`. The module creates the directory and emits workspace registration
  guidance as a message; it does NOT currently write a package manifest (no
  `pyproject.toml`/`package.json`) or edit any root workspace file. Adding a
  Tier-2 resolver step requires adding `kind=agent` + `kind=gate` steps before
  the existing `add` step — following the `lang-python` pattern.

- **`package-add` module is `reconcile=false` and `default_enabled=false`.**
  `modules/package-add/module.toml:12-13`. The `reconcile=false` means re-running
  with an existing target directory skips (the `if target.exists()` branch at
  `module.py:196-199`). This is correct for a directory-creation module; the new
  manifest write step must honour the same `reconcile=false` semantics (no
  clobbering an already-written package manifest).

- **The `sources.toml` format is `[[source]]` records with `locator`, optional
  `ref`, optional `subdir`.** `runner/persist.py:218-224` writes each source as
  `{locator, ref?, subdir?}`. `runner/pipeline.py:109-119` reads
  `.project-setup/sources.toml` as `data.get("source", [])`. The locator forms
  supported are: GitHub shorthand `owner/repo[/subdir][#ref]`, HTTPS URL, SSH URL,
  local path (`runner/sources/locator.py:95-161`). A `ref` field in the source
  record overrides the `#ref` fragment in the locator string.

- **`fetch_source` is non-fatal on failure.** `runner/sources/fetch.py:141-177`
  returns `FetchResult(ok=False, skipped_reason=...)` for any failure (git absent,
  network, bad ref, missing subdir) and NEVER raises. The pipeline proceeds with
  whatever other roots are available (FR-013 / SC-008 of the 001 spec). An org
  source that cannot be fetched (stale network) must follow the same soft-skip
  contract — its modules are simply absent from discovery, not a hard error.

- **The fetched-root discovery path exists.** `runner/sources/discover.py:180-226`
  (`build_discovery_roots`) places fetched source roots at precedence level 4
  (between HOME and BUNDLED). An org policy source checked out via `fetch_source`
  lands in the fetched root tier and its modules are discovered normally.

- **The agent step + gate + python step pattern is established for `lang-python`.**
  `modules/lang-python/module.toml:31-52`: three steps `{resolve/agent, pins/gate
  (hard, allow-stack-write, init_only), write/python}`. The steering doc lives at
  `modules/lang-python/steering/resolve.md`. This is the exact pattern sub-features
  A and B replicate.

- **The `{decision}` token in gate messages is supported.**
  `runner/plan.py:159-168` (referenced in spec 003 / 004 memory): `build_plan`
  replaces `{decision}` in a gate step's `message` with
  `render_answer_block(mod_answers)` at freeze time. All three new gate messages
  may use this token to surface the agent's frozen decision at the gate.

- **`sdk.FrozenInputs.mode` distinguishes init from reproduce.**
  `runner/sdk.py:86-91`: the `.mode` property returns `"init"` or `"reproduce"`.
  Sub-feature B's verify step (registry-check for aligned pins) uses this to
  gate network: verify only at init, skip on reproduce (same as `lang-python`'s
  `verify_pins` call pattern, 003 FR-009).

- **`sdk.verify_pins` is the shared MCP-free registry verification primitive.**
  `runner/sdk.py:315-380`: accepts a list of `name@version` pins and an ecosystem
  (`"pypi"` or `"npm"`), returns a dict of `pin → verified|disconfirmed|unreachable`.
  Available to sub-feature B's `module.py` via `import sdk`.

- **`sdk.idempotent_write` with `reconcile=False` is write-once.**
  `runner/sdk.py:240-257`: when `reconcile=False` and the file already exists,
  returns `Diff(kind="skip", ...)` without writing. This is the guard that makes
  `reconcile=false` modules (like `agents-md` with `reconcile=True`, or
  `package-add` with `reconcile=False`) idempotent on re-run. Sub-feature C
  (`readme-draft`) relies on this: `README.md` is written at init, skipped on
  every reproduce.

- **No org-policy module, no readme-draft module, no package-add resolver exist
  today.** `eza modules/` output lists 18 modules; none is `org-policy`,
  `readme-draft`, or an extended `package-add` with an agent step. All three are
  fully net-new.

- **`answers.toml` per-module structure is `[module.<id>]` tables.**
  `runner/pipeline.py:122-138` reads per-module answers as `module_section` keyed
  by module id. An agent step reading sibling answers (sub-feature B: reading
  `lang-python.pinned_deps` to align the new package) can access them via
  `FrozenInputs._answers` — but ONLY if those answers are in the frozen plan for
  the package-add module, which requires the steering doc to instruct the agent to
  read the plan's sibling module answer blocks. The plan carries per-module frozen
  answers for all enabled modules (verifiable in `plan.py`'s frozen plan shape);
  the steering doc can instruct the agent to read the plan JSON passed as `--plan`.

## Settled decisions

Letters restart fresh A-series.

- **A — Three sub-features in one spec; no plan.md authored until OQ-1 is
  resolved.** The sub-features are loosely coupled (same gate seam, same module
  anatomy, no ordering dependencies between them), so bundling them avoids
  three thin specs. If the human chooses to split (OQ-1), each becomes its own
  thin spec inheriting these settled decisions. No plan.md is authored until OQ-1
  is answered because the phasing (ship all three together vs one-at-a-time) drives
  the plan's phase structure.

- **B — Org-policy source MUST be pinned by explicit git ref/tag in sources.toml.**
  An org policy repo executes arbitrary code (its module.py runs in a `uv run`
  subprocess). A floating `HEAD` / branch fetch means any push to the org repo
  silently changes behavior on the next `fetch_source`. Pinning by tag or SHA is
  the only mechanism that gives a reproducible audit trail. The ref is written to
  the committed `.project-setup/sources.toml` so reproduce uses the SAME ref. The
  SKILL.md author-facing docs MUST call this out as a non-negotiable authoring
  rule. Adding a new org source without an explicit `ref` MUST be rejected at
  validate time (new `ORG_SOURCE_UNPINNED` validation error, not a soft warning).

- **C — Path-traversal guards in `package-add/module.py` are SECURITY-PINNED and
  run BEFORE any agent step or mkdir.** `_validate_name` (lines 61-75) and the
  `sdk.is_safe_relative_path(dir_)` call (lines 159-177) MUST remain verbatim in
  the same positions in the execution order. The agent step is inserted as a
  PRECEDING step in `module.toml` (before the `add` step); the python `add` step
  re-runs the guards unconditionally before its `mkdir`. No agent answer can bypass,
  relax, or skip these guards. This is non-negotiable (roadmap verbatim: "MUST keep
  its existing path-traversal guards verbatim and run them before any mkdir").

- **D — Package-add resolver aligns, never overrides, frozen sibling pins.**
  The agent step reads the frozen plan's sibling module answers (e.g.
  `lang-python.pinned_deps`, `lang-ts.pinned_deps`) and proposes framework/version
  choices for the new package that are COMPATIBLE with what is already frozen — it
  DOES NOT re-decide the sibling pins. If no sibling pins exist, the agent falls
  back to the same resolver logic as `lang-python`/`lang-ts`. The alignment is a
  best-effort recommendation surfaced at the gate; the user can decline and run
  without the manifest (the directory is still created).

- **E — Two gates for package-add: one hard gate on the new package manifest, one
  soft gate on the root workspace manifest edit.** The new package manifest
  (`pyproject.toml` or `package.json` inside the new package dir) is a hard gate
  because it installs pins and is supply-chain surface. The root workspace manifest
  edit (`tool.uv.workspace.members`, `workspaces` in root `package.json`, `go.work`
  `use`, or `workspace.members` in root `Cargo.toml`) is a SOFT gate — it touches
  a shared file the user may have hand-edited. A declined root-manifest gate leaves
  the package dir + manifest intact but prints the manual registration command
  (already emitted as `guidance` by the existing `_workspace_guidance` function at
  `module.py:78-98`). CI must not auto-edit the root workspace manifest without
  the soft gate's explicit `skip_flag` (`no-workspace-manifest-edit`) opt-out.

- **F — README draft is write-once (`reconcile=false`); the gate fires on first
  draft only.** `sdk.idempotent_write` with `reconcile=False` skips if the file
  already exists (`Diff(kind="skip")`). On reproduce, the `README.md` skip is
  unconditional (no gate). The gate fires only when `diff.kind == "create"` in
  the inspect pass — i.e., only when no `README.md` exists yet. This makes the
  gate pattern: inspect → if create → hard gate on first draft → write; on re-run
  inspect → skip → no gate. This is consistent with the G5 destructive-overwrite
  rule from spec 004 (never silently overwrite a hand-edited file) and the
  `reconcile=false` write-once semantics already established for `agents-md`'s
  complementary module shape.

- **G — Org-policy overlay modules are in the FETCHED root tier; they shadow
  BUNDLED modules but are shadowed by PROJECT/HOME/ENV.** The standard precedence
  (`build_discovery_roots`: ENV → PROJECT → HOME → FETCHED → BUNDLED,
  `discover.py:180-226`) already gives fetched-root modules the correct priority:
  org overrides beat bundled defaults, but a user's project-local module beats
  both. No change to the discovery engine is needed.

- **H — Org-policy module is a standard module.toml + module.py; it is NOT a
  runner change.** An org writes a directory (one `module.toml` + `module.py`)
  following the standard module contract. The `org-policy` module in the bundled
  set is only a THIN BOOTSTRAP module that declares the source entry and installs
  the fetched-root org policy modules from the org's pinned repo. Org authors
  follow the same module.toml schema as any other module author.

- **I — README agent step reads ONLY the frozen plan's answers; it does not scan
  the filesystem.** The agent receives the frozen plan JSON (via the `--plan` arg)
  and drafts the README from structured facts (project_name, org, layout, language,
  framework, resolved stack). It MUST NOT read arbitrary files from the project
  directory (prompt injection risk). The steering doc explicitly limits context to
  the plan's answer block only.

- **J — All three sub-features honour the 003/004 determinism contract.**
  Research only at init; reproduce replays frozen agent answers zero-network. The
  `sdk.FrozenInputs.mode` property gates any network work. `verify_pins` runs only
  in `"init"` mode. The `init_only` gate marker (spec 004 FR-006a) applies to the
  package-add pin gate: at plain reproduce, the frozen decision is already consented
  and the write replays byte-identically without re-prompting.

## User Scenarios & Testing

### User Story 1 — Org policy forces a naming convention override (Priority: P2)

A developer at an org that mandates all Python packages use a `com.acme.*` namespace
runs project-setup with the `org-policy` module enabled. The org's policy repo is
pinned to tag `v1.3.0` in `sources.toml`. The org policy agent reads the frozen
answers and finds the user picked `project_name = "api"` — which the org policy
mandates must be `com.acme.api`. Before any file write, a gate shows the exact
set of policy-forced overrides: `project_name: api → com.acme.api (org-mandated)`.
The developer confirms and the override is applied in the frozen answers.

**Acceptance Scenarios**:

1. **Given** `org-policy` enabled and a pinned org source in `sources.toml`,
   **When** the agent step runs, **Then** it emits a structured `overrides` decision
   listing each policy-forced change as `{key, user_value, mandated_value, reason}`.
2. **Given** the overrides decision, **When** the gate fires, **Then** it shows
   every override with `(user-asked: X → org-mandated: Y)` labelling, before any
   write. A gate with zero overrides MAY be `informational` (no changes needed).
3. **Given** the gate confirmed, **When** the python step runs, **Then** it applies
   only the `mandated` overrides, never modifying answers the org policy did not
   touch.
4. **Given** `--non-interactive`, **When** the gate fires, **Then** it SAFE-skips
   (CI never silently applies org-policy overwrites without `--allow-org-policy`).

### User Story 2 — Org source pinned by ref; unpinned source rejected (Priority: P2)

An org admin adds a new org source to `sources.toml`. They try `locator =
"acme-corp/policy-modules"` without a `ref`. The runner rejects this at validate
time with `ORG_SOURCE_UNPINNED`. They add `ref = "v1.0.0"` and it is accepted.

**Acceptance Scenarios**:

1. **Given** a `[[source]]` record from a git locator with no `ref` field AND no
   `#ref` fragment in the locator, **When** validation runs, **Then** the runner
   emits `ORG_SOURCE_UNPINNED` and refuses to proceed.
2. **Given** a `[[source]]` record with an explicit `ref` field, **When** validation
   runs, **Then** it proceeds normally.
3. **Given** reproduce with a pinned source, **When** `fetch_source` runs, **Then**
   it checks out EXACTLY the committed ref (no `fetch --prune` to pick up new tags
   without `--refresh`).

### User Story 3 — Package-add aligns a new package with sibling Python pins (Priority: P2)

A developer adds a `packages/workers` package to a monorepo that already has a
`packages/api` package with frozen `fastapi@0.111.0` + `pydantic@2.7.1` pins. The
package-add resolver agent reads those sibling pins and recommends `pydantic@2.7.1`
for the new package (not the current latest). The gate shows the aligned pins; the
developer confirms; the new `packages/workers/pyproject.toml` is written with the
frozen pins. The root `pyproject.toml` workspace manifest is offered for update at
a soft gate.

**Acceptance Scenarios**:

1. **Given** `package-add` enabled with `lang=python` and existing sibling pins in
   `answers.toml`, **When** the resolver agent runs, **Then** it emits an
   `aligned_pins` decision that includes sibling-pinned deps at their frozen
   versions (not current-latest) and flags any version conflicts with rationale.
2. **Given** the `aligned_pins` decision, **When** pin verification runs (init
   mode only), **Then** each pin is checked against PyPI/npm before the gate fires;
   disconfirmed pins fail closed.
3. **Given** verified pins, **When** the manifest gate fires, **Then** it is a
   hard gate (`allow_flag=allow-stack-write`, `init_only=true`) showing the full
   pin table; the path-traversal guards have ALREADY run before this gate.
4. **Given** the manifest gate confirmed, **When** the workspace-manifest soft gate
   fires, **Then** it shows the exact line to add to the root manifest and the
   manual command to add it manually; CI with `--no-workspace-manifest-edit` skips
   it; CI without the flag proceeds.
5. **Given** an existing `packages/workers/` directory, **When** `package-add`
   runs, **Then** it skips directory creation (reconcile=false); the manifest step
   also skips if `pyproject.toml` already exists (reconcile=false).

### User Story 4 — Path-traversal guard blocks an agent-injected escape attempt (Priority: P1)

An agent (or a malformed steering response) returns `name = "../../etc"`. The
runner's path-traversal guard fires before any mkdir — the directory is NOT created,
the agent decision is rejected, and the error `PATH_ESCAPE` is emitted.

**Acceptance Scenarios**:

1. **Given** `name = "../../etc"`, **When** `_validate_name` runs (BEFORE any
   agent step output is used to create a path), **Then** `PATH_ESCAPE` is emitted
   and the step exits immediately.
2. **Given** any name an agent returned via `aligned_pins`, **When** the python
   `add` step runs, **Then** it re-runs `_validate_name` and `sdk.is_safe_relative_path`
   unconditionally, regardless of whether the agent step ran or was skipped.

### User Story 5 — README is drafted once; re-runs skip it (Priority: P3)

On first init with `readme-draft` enabled, the agent drafts a `README.md` from the
frozen scaffold facts (project name, org, language, framework, resolved stack). A
gate shows the draft. The developer confirms; `README.md` is written. On the next
reproduce run, the README step detects the file already exists and skips silently —
no gate, no overwrite prompt, no diff.

**Acceptance Scenarios**:

1. **Given** no `README.md` exists, **When** the inspect pass runs, **Then** the
   diff is `create`; **When** the gate fires, **Then** it shows the full draft
   before writing.
2. **Given** `--non-interactive` at init, **When** the gate fires, **Then** it
   SAFE-skips the write (CI never auto-writes a README without `--allow-readme`);
   the developer gets the manual path to write it.
3. **Given** a `README.md` already exists (any content), **When** the inspect pass
   runs, **Then** the diff is `skip`; **When** the python step runs, **Then** it
   does NOT write, does NOT prompt, does NOT gate. The existing file is preserved.
4. **Given** reproduce mode, **Then** the agent step replays the frozen draft
   zero-network and the write step is skipped (file already exists from init).

### Edge Cases

- **Org source fetch fails at init** (network unavailable): `fetch_source` returns
  `FetchResult(ok=False)`; the org policy module is absent from discovery; the run
  proceeds without org enforcement. This is intentional soft-fail semantics
  (consistent with the 001 source-fetch policy). An informational warning is emitted.
- **Org source fetch fails at reproduce**: the committed `sources.toml` ref is
  exact; the same repo/commit should be available. A failure here is treated the
  same as init (soft warn + skip module). Reproduce never re-fetches if the cache
  hit exists (the existing `_clone_or_update` cache logic in `fetch.py:83-133`).
- **No sibling pins found for package-add align** (first package in a monorepo):
  the agent falls back to the standard stack-resolver path (`lang-python`/`lang-ts`
  pattern), treating it as a fresh resolution. The gate message notes "no sibling
  pins found; resolved from current registry".
- **Package-add with `lang=go` or `lang=rust`**: the resolver agent step still runs
  (emits a `go.mod` / `Cargo.toml` stub decision), but `verify_pins` is only called
  for `pypi`/`npm` — Go modules and Rust crates do not use the same verification
  path. The gate fires; pin verification is skipped with a warning for these
  ecosystems (OQ-4).
- **README agent returns prose containing `PLUGIN_ROOT` or other env-looking
  tokens**: the python step writes the content as-is (it is Markdown prose, not
  executed). No interpolation of env variables occurs. The steering doc MUST
  instruct the agent not to emit placeholders that look like shell variables.
- **`org-policy` module id collides with a bundled module**: Discovery applies the
  standard precedence rules — FETCHED root wins over BUNDLED, PROJECT/HOME/ENV
  override both. No special handling needed.

## Requirements

### Sub-feature A — Org-convention overlay

#### Org source pinning

- **FR-001**: The runner MUST validate that every `[[source]]` record whose locator
  resolves to a `kind="git"` locator has an explicit `ref` field (or a `#ref`
  fragment in the locator string). A git source with no ref MUST be rejected at
  validate time with a new `ORG_SOURCE_UNPINNED` error code, before any fetch.
  Local-path sources are exempt (they are already on-disk, no network surface).
- **FR-002**: The committed `.project-setup/sources.toml` MUST record the exact
  `ref` as written by the user/agent. `persist.write_sources_toml` already writes
  the `ref` field (verified at `persist.py:221-222`); no change to the persist path
  is needed. Reproduce reads the committed ref and passes it to `fetch_source` —
  the checkout is pinned to that exact ref.

#### Org-policy module shape

- **FR-003**: A new bundled bootstrap module `org-policy` (default_enabled=false)
  MUST declare one `kind=agent` step and one `kind=gate` step (hard,
  `allow_flag=allow-org-policy`, `init_only=true`) followed by one `kind=python`
  step. The agent step reads the frozen plan answers and an org-specific policy
  manifest (provided by the fetched org module as a sibling file) and emits an
  `overrides` decision: `{key, user_value, mandated_value, reason}` list as
  `agent-steered` answers. A zero-length overrides list is valid.
- **FR-004**: The gate message MUST show every override as
  `{key}: {user_value} → {mandated_value} (org-mandated: {reason})`. A gate with
  zero overrides SHOULD use `hardness="informational"` (never prompts); a gate with
  one or more overrides MUST use `hardness="hard"`. The `{decision}` token is used
  to render this from the frozen decision (reusing the existing `build_plan`
  composition at `plan.py:159-168`).
- **FR-005**: The python step MUST apply ONLY the mandated overrides to the frozen
  answers, using `sdk.idempotent_write` to emit a delta-answers file or via the
  standard `answers_to_persist` path. It MUST NOT modify any answer the org policy
  did not list as `mandated`. The write is `reconcile=false` (applied once at init;
  re-runs skip if the delta file exists).
- **FR-006**: In `--non-interactive`, the org-policy gate MUST SAFE-skip (apply no
  overrides) unless `--allow-org-policy` is active. The run MUST NOT silently apply
  org-mandated overrides in CI without explicit opt-in.

### Sub-feature B — Package-add Tier-2 resolver

#### Security-pinned guards (non-negotiable)

- **FR-007**: `_validate_name` (`module.py:61-75`) MUST remain verbatim in the
  `module.py` file and MUST be called in the `kind=python` `add` step BEFORE any
  `mkdir`, regardless of whether the agent step ran or was skipped. The guards are
  security-pinned behaviors that cannot be bypassed by agent output or gate outcome.
- **FR-008**: `sdk.is_safe_relative_path(dir_)` (`module.py:159-177`) MUST
  similarly remain verbatim and run before any `mkdir` in the `add` step. The `dir_`
  value comes from frozen interview inputs, not agent output — but the guard runs
  regardless.

#### Resolver agent step

- **FR-009**: The `package-add` module MUST gain an optional `kind=agent` step
  (`id="resolve"`) BEFORE the existing `kind=python` `add` step. The agent step
  emits an `aligned_pins` decision: `{framework, pinned_deps: [name@exact],
  package_manifest_type: "pyproject.toml"|"package.json"|"go.mod"|"Cargo.toml",
  rationale}` as `agent-steered` answers. The step is skipped (via a
  `when = "resolve_stack == true"` predicate) when the user has not asked for stack
  alignment — keeping the existing plain directory-creation behavior unchanged for
  users who do not opt in.
- **FR-010**: The agent step steering MUST instruct the agent to read the frozen
  plan's sibling module answer blocks for `lang-python.pinned_deps` and/or
  `lang-ts.pinned_deps` and align the new package's pins to match those frozen
  versions where the same package appears. The agent MUST NOT re-research pins
  already frozen in a sibling module; it proposes the sibling's exact version.
- **FR-011**: Every pin in `aligned_pins.pinned_deps` MUST be verified against its
  registry using `sdk.verify_pins` in `"init"` mode only (spec 003 FR-009 pattern).
  Disconfirmed pins are rejected as `INPUT_VALUE_INVALID`; unreachable pins are
  reported + safe-skipped (the write does not proceed for unverified pins).

#### Gates

- **FR-012**: A `kind=gate` step (`id="pins"`, `hardness="hard"`,
  `allow_flag="allow-stack-write"`, `init_only=true`) MUST fire after the resolve
  step and before the `add` step. Its message shows the aligned pin table
  (name@version, verify status, sibling-match notes). When declined or CI-skipped,
  the manifest write and the `mkdir` are both skipped (gate-blocking `apply`,
  spec 003/004 — `reproduce.py:277-283`).
- **FR-013**: An additional `kind=gate` step (`id="workspace-edit"`,
  `hardness="soft"`, `skip_flag="no-workspace-manifest-edit"`) MUST fire after the
  `add` step and before a new `kind=python` `workspace-edit` step that appends to
  the root workspace manifest. Its message shows the exact line to append and the
  manual command. A declined gate skips only the workspace edit; the package dir and
  its manifest are already written (gate-blocking is per-step, not module-wide in
  this case — see OQ-3 for the ordering interaction with `gate_blocked`).
- **FR-014**: The `kind=python` `workspace-edit` step MUST use `sdk.append_if_absent`
  with a per-package marker (e.g. `# project-setup: {name}`) so re-runs are
  idempotent (the same line is not appended twice if the workspace manifest already
  contains it).

#### Manifest write

- **FR-015**: A new `kind=python` step (`id="manifest"`) MUST be inserted between
  the `pins` gate and the `add` step. It writes the per-package manifest
  (`pyproject.toml`/`package.json`/`go.mod`/`Cargo.toml`) inside the new package
  directory using `sdk.idempotent_write` with `reconcile=False` (write-once). If
  the manifest already exists, it is skipped.
- **FR-016**: The manifest step MUST RE-RUN `_validate_name` and
  `sdk.is_safe_relative_path` unconditionally before constructing any paths, as
  required by FR-007/FR-008. This double-check is the second layer of defence.

### Sub-feature C — README draft

- **FR-017**: A new default-disabled bundled module `readme-draft` MUST declare
  one `kind=agent` step (`id="draft"`) followed by one `kind=gate` step and one
  `kind=python` step (`id="write"`). The gate MUST be conditional:
  `when = "readme_exists == false"` evaluated by the inspect pass (the python step
  sets this synthetic flag after calling `sdk.idempotent_write` with `inspect=True`
  to check whether the file exists).
- **FR-018**: The agent step MUST read ONLY the frozen plan answers (project_name,
  org, layout, language, framework, resolved stack, license) to draft the README.
  It MUST NOT read from the filesystem. The steering doc MUST explicitly prohibit
  filesystem reads and shell-variable-looking tokens in the draft.
- **FR-019**: The gate message MUST show the full README draft (or a meaningful
  preview if long) before the write. It MUST be a hard gate (`allow_flag=
  "allow-readme"`) with `init_only=true` — plain reproduce does NOT re-prompt (the
  file already exists; the `reconcile=False` guard makes the write a skip anyway).
- **FR-020**: The python `write` step MUST call `sdk.idempotent_write("README.md",
  body, reconcile=False)`. If the file exists (any content, any origin), it MUST
  return `Diff(kind="skip")` without writing or prompting. The gate in FR-017 fires
  ONLY when the inspect pass returns `Diff(kind="create")` — on an existing
  `README.md` the gate is `when`-dropped (never fires).
- **FR-021**: In `--non-interactive`, the README gate MUST SAFE-skip (no write)
  unless `--allow-readme` is active. A README is a curated human artifact; CI must
  not auto-create it.

### Cross-cutting: determinism & compatibility

- **FR-022**: All three sub-features MUST honour the 003 reproduce contract:
  `kind=agent` steps replay frozen `agent-steered` answers zero-network on plain
  reproduce; only `--refresh` re-invokes the agent. `sdk.FrozenInputs.mode` is
  used to gate any network or verification work to `"init"` mode only.
- **FR-023**: All new gate steps MUST reuse the spec-004 gate machinery
  (`hardness`, `allow_flag`, `skip_flag`, `init_only`, `when`) as implemented.
  No new gate primitives are introduced.
- **FR-024**: The `{decision}` gate-message token MUST be used for every gate step
  that surfaces an agent decision (org-policy overrides, aligned pins, README
  draft). Static gate messages without `{decision}` are only acceptable for the
  workspace-manifest soft gate (its content is deterministic from frozen inputs,
  not from an agent step).

## Success Criteria

- **SC-001**: A git `[[source]]` record with no `ref` is rejected at validate time
  with `ORG_SOURCE_UNPINNED` before any fetch; a record with an explicit `ref` field
  passes validation (unit test: validate code path).
- **SC-002**: An org-policy agent step emitting one override produces a hard gate
  message naming the key + user_value → mandated_value with `(org-mandated)` label;
  an agent step emitting zero overrides produces an informational (non-prompting)
  gate. In `--non-interactive`, both SAFE-skip without `--allow-org-policy`.
- **SC-003**: `_validate_name` is called BEFORE any `mkdir` in both the existing
  `add` step and the new `manifest` step; injecting `name="../../etc"` produces
  `PATH_ESCAPE` with no directory created (test: inject the malformed name, verify
  no filesystem side-effects).
- **SC-004**: A `package-add` run with `resolve_stack=true` and sibling
  `lang-python.pinned_deps` present produces an `aligned_pins` decision that re-uses
  the sibling's pinned versions for matching packages (not current-latest); each pin
  is registry-verified at init and the gate shows verify-status (test with stubbed
  registry).
- **SC-005**: A `package-add` run with `resolve_stack=false` (or the `when`
  predicate false) produces IDENTICAL behavior to the current module — directory
  created, workspace guidance printed, no manifest written, no agent step run
  (regression guard: the existing package-add test suite stays green unchanged).
- **SC-006**: A declined `pins` gate in package-add leaves no directory and no
  manifest on disk (gate-blocking; the `add` step skips).
- **SC-007**: A declined `workspace-edit` soft gate leaves the package directory
  and manifest intact, prints the manual command, and continues; a CI run without
  `--no-workspace-manifest-edit` appends the workspace entry.
- **SC-008**: On first init with `readme-draft` enabled and no `README.md` present,
  the hard gate fires and CI SAFE-skips (no write) without `--allow-readme`; with
  `--allow-readme`, `README.md` is written. On a reproduce run with `README.md`
  already present, no gate fires and no write occurs.
- **SC-009**: All three new agent steps, when run in reproduce mode, perform zero
  network calls and emit the committed frozen decision (verified with a
  network-blocking IO double that asserts `agent_step == []`).
- **SC-010**: The full pre-014 test suite stays green unchanged (no regressions to
  existing package-add, lang-python, lang-ts, or gate machinery).

## Out of Scope

- A general org-policy enforcement framework beyond the single `kind=agent`
  decision step. Structural enforcement (e.g. lint the project against org rules
  on every run, CI-break on non-conformance) is out of scope; the overlay is a
  ONCE-at-init alignment tool, not a continuous compliance checker.
- Go and Rust pin verification via their native registries (`pkg.go.dev` / `crates.io`).
  Sub-feature B reports a warning and skips verification for `lang=go`/`lang=rust`
  packages; a full Cargo/Go registry verifier is deferred (OQ-4).
- Multi-repo or multi-source org overlays (more than one org source per project).
  The spec supports exactly one org policy source; merging two org policies is out
  of scope.
- Interactive README editing inside the gate (an edit UI at gate time). The gate
  surfaces the draft and the user can decline + edit the steering doc; inline editing
  is not supported (same out-of-scope pattern as the spec-004 G6 inline pin-editing).
- Changing the `sources.toml` schema beyond the existing `locator`/`ref`/`subdir`
  fields. The `ORG_SOURCE_UNPINNED` validation is a new CHECK over the existing
  schema, not a schema change.
- Automatic org-policy source discovery (e.g. inferring the org repo from the GitHub
  org the project lives in). The user or admin must explicitly add the source.
- README sections beyond a standard scaffold fact summary (e.g. a generated API
  reference, a changelog section). The agent drafts a starting README only; deeper
  content is out of scope.

## Assumptions

1. Spec 003 (two-phase plan, reproduce-replay, `verify_pins`, `sdk.FrozenInputs.mode`)
   and spec 004 (gate enrichment: `hardness`, `allow_flag`, `skip_flag`, `init_only`,
   `when`, `{decision}` composition) are in place and green (613 tests at 004 ship).
2. The spec-004 `gate_blocked` per-module-scoped blocking behavior
   (`reproduce.py:277-283`) is the mechanism for sub-feature B's pins gate to block
   the `manifest` and `add` steps. OQ-3 tracks whether the ordering of
   `workspace-edit` (which must NOT be blocked by a declined pins gate) requires
   careful step ordering or a finer-grained gate_blocked scope.
3. The `{decision}` gate message token (spec 003 SUBTLETY 1 / spec 004 AS-BUILT #2)
   composes from the agent step's full `answers_to_persist` block; structured
   override/pin tables will render acceptably as the `render_answer_block` output.
   If the rendered block is too verbose, the gate message may cap it (a display
   detail, not a contract change).
4. The `when` predicate evaluation at `build_plan` (spec 004 Decision D,
   `manifest.py` `eval_when`) supports the `key == value` form needed for
   `when = "resolve_stack == true"` and `when = "readme_exists == false"`.
   `readme_exists` is a synthetic boolean populated by the inspect pass before
   plan freeze — this requires the inspect pass to run before the `when` evaluation,
   which is the existing init flow (Stage 5: inspect + freeze, `pipeline.py:488-515`).
   Verify this interaction before implementing FR-017 (OQ-5).
5. `sdk.append_if_absent` is sufficient for the workspace manifest edit (sub-feature
   B FR-014). The existing four workspace manifest formats (root `pyproject.toml`
   `[tool.uv.workspace]`, root `package.json` `workspaces`, `go.work`, `Cargo.toml`
   `[workspace]`) all support appending a new member entry idempotently. The exact
   append format per lang is a data detail for plan.md (not blocking authoring this
   spec).

## Dependencies & Open Questions

**Hard dependency on 003 + 004:** All three sub-features require the two-phase plan
(FR-009/FR-011 from spec 003), the `init_only` gate marker (FR-006a from spec 004),
the `when` predicate (FR-006 from spec 004), and the hardness-driven resolver
(FR-003 from spec 004). 014 builds on top; it does not touch the runner machinery
introduced in 003/004 except to declare gate steps with the 004-shaped fields.

**Remaining open questions** (OQ-1 … OQ-5) are tracked in `memory.md` with
priority and lean. OQ-1 (split vs bundle) is the only HIGH-priority question
that requires human input before authoring `plan.md`. The others are design
details resolved during planning/implementation.
