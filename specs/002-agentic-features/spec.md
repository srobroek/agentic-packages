# Feature Specification: Module Enablement Layer

**Feature Branch**: `feat/project-setup-modular-redesign` (continues) → likely a dedicated `feat/enablement` branch

**Created**: 2026-06-27

**Status**: Draft

**Input**: Net-new capability after the 001 migration. "Determine which modules to enable — minimal deterministic core, agent grills the user and suggests modules; selection recorded for reproducibility."

## Overview

The 001 migration built a generic runner + 18 modules and proved parity with the
legacy scaffold. But it shipped **without a module-enablement mechanism**: the
pipeline runs *every discovered module*. `default_enabled` is parsed and carried
on `DiscoveredModule` (and enforced first-party-only at discovery), but the
pipeline never uses it as a run filter, and there is no config or interview that
decides *which* optional capabilities a project wants. Consequently all four
language overlays, speckit-bridge, and package-add would execute on every project
if discovered — which is wrong.

This feature adds the **enablement layer**: a minimal deterministic core that
always runs, plus an agent-led selection of optional modules driven by the user's
intent, with the resulting selection **recorded as committed answers** so clones
and re-runs are reproducible. It is the connective tissue the later Tier-2
features (stack-resolver, spec 003) depend on — "which optional modules" must
exist before "research the chosen framework's versions" makes sense.

This spec is **enablement only**. The Tier-2 agentic features
(`reviews/tier2-agentic-features-roadmap.md`) and the gates feature
(`gates-analysis.md`) are future specs 003/004; their analyses live in this
directory as inputs but are out of scope here.

## Current state (verified)

- `sources/discover.py`: `DiscoveredModule` carries `default_enabled`
  (tri-state `Optional[bool]`); `default_enabled=true` on a non-bundled module is
  already a hard error (FR-035 from 001).
- `pipeline.py` (~line 330): collects **every** discovered module into
  `manifests` with no enablement filter; the interview then asks each module's
  inputs unconditionally.
- No `[modules]` enablement section is read anywhere in the runner.
- The agent/gate execution path is verified working end-to-end (agent steps fold
  `agent-steered` answers into persistence with correct provenance).

## Settled decisions

- **A — Minimal deterministic core.** `default_enabled=true` is reserved for the
  irreducible scaffold only. The base set shrinks to: `core-identity`,
  `dirs-scaffold`, `gitignore-generate`, `license-write`, `agents-md`,
  `git-init`. Everything else (github-repo, apm-install, precommit-setup,
  codex-config, justfile-write, quality-hooks, all lang-*, speckit-bridge,
  package-add) becomes opt-in, **agent-proposed**, not auto-run.
- **B — `default_enabled` becomes a real pipeline filter.** Only modules that are
  (base `default_enabled`) OR (explicitly enabled in the resolved selection) are
  parsed-for-execution and run. Their `requires` closure is auto-pulled in (a
  module you enable drags in its hard deps).
- **C — Agent-led selection, not a rigid interview.** The decision of *which*
  optional modules to enable is made by the agent following SKILL.md guidance:
  it grills the user on intent and **proposes** an enablement set with rationale.
  This is judgment (Tier-2-style), not a static checkbox list.
- **D — Selection recorded as committed answers.** The resolved enablement set is
  persisted (a `[modules]` table in `.project-setup/answers.toml`, or a dedicated
  `enabled = [...]` record) with provenance, so a clone/re-run reproduces the
  exact module set deterministically — the agent does not re-decide on reproduce.
- **E — Reproduce never re-grills.** In reproduce mode the committed enablement
  set is authoritative and replayed; selection only happens in init (or an
  explicit `--reconfigure`).
- **F — Home config proposes, project decides.** Home config MAY carry a personal
  default enablement preference (catalog), but it is never authoritative; the
  committed project selection wins (consistent with 001 F4).

## User Scenarios & Testing

### User Story 1 — Minimal core always runs (Priority: P1)

A project with no optional modules selected still gets the irreducible scaffold
(identity, dirs, gitignore, license, AGENTS.md, git). Optional modules do NOT run
unless enabled.

**Acceptance Scenarios**:

1. **Given** a fresh project and no enablement selection, **When** setup runs,
   **Then** only the base `default_enabled` modules execute, and no language
   overlay / speckit / package-add runs.
2. **Given** a discovered optional module that is not enabled, **When** the
   pipeline runs, **Then** it is excluded from the interview and execution.

### User Story 2 — Agent proposes modules from intent (Priority: P1)

A user describes their project ("a TypeScript web API with Postgres"); the agent
proposes enabling `lang-ts` (+ later, via 003, the framework resolver) and
records the selection.

**Acceptance Scenarios**:

1. **Given** a user intent, **When** the agent conducts selection per SKILL.md,
   **Then** it proposes an enablement set with rationale and the user
   confirms/edits it.
2. **Given** a confirmed selection, **When** setup completes, **Then** the
   enabled set is recorded in `.project-setup/answers.toml` with provenance.

### User Story 3 — Reproducible enablement (Priority: P1)

A clone reproduces the exact same module set from committed files, without
re-grilling.

**Acceptance Scenarios**:

1. **Given** a committed enablement selection, **When** the runner runs in
   reproduce mode, **Then** it enables exactly that set (no agent re-decision)
   and the resulting scaffold matches.
2. **Given** an enabled module with a `requires` dependency, **When** enablement
   resolves, **Then** the required module is auto-included even if not explicitly
   listed.

### Edge Cases

- An enabled module whose `requires` target is disabled → the requires-closure
  auto-enables it (a module can't be enabled without its hard deps).
- A `[modules].enabled` entry naming an unknown/undiscovered id → reported error
  (don't silently ignore a typo'd module id).
- `--non-interactive` with no committed selection and no config → run base only
  (safe default), report which optional modules were available but skipped.
- Home config proposes module X, project committed answers omit it → project
  wins; X does not run.

## Requirements

- **FR-001**: `default_enabled` MUST be reduced to the minimal core set (core-identity,
  dirs-scaffold, gitignore-generate, license-write, agents-md, git-init); all
  other modules MUST become opt-in.
- **FR-002**: The pipeline MUST filter discovered modules to (base default_enabled
  ∪ explicitly-enabled ∪ their `requires` closure); only those are interviewed
  and executed.
- **FR-003**: An enablement-resolution step MUST run between discovery and the
  interview, computing the enabled set from: base defaults, committed selection
  (reproduce), home-config proposal (init, non-authoritative), and the agent's
  proposed selection (init).
- **FR-004**: The resolved enablement set MUST be persisted to
  `.project-setup/answers.toml` (a `[modules] enabled = [...]` record) with
  provenance, and replayed authoritatively on reproduce (no agent re-decision).
- **FR-005**: SKILL.md MUST instruct the agent to conduct module selection:
  grill the user on intent, propose an enablement set with rationale, confirm,
  and record it. This is agent-led, not a static per-module yes/no interview.
- **FR-006**: Enabling a module MUST auto-include its `requires` closure; a
  `requires`/`enabled` entry naming an undiscovered id MUST be a located error.
- **FR-007**: `--non-interactive` with no selection MUST run the base set only
  (safe default) and report skipped-available optional modules; it MUST NOT
  auto-enable optional modules.
- **FR-008**: Home config MAY propose a default enablement set but MUST NOT be
  authoritative; committed project selection wins.
- **FR-009**: The existing 001 determinism guarantees MUST hold — the enablement
  set is data (recorded answers), so reproduce is deterministic; the agent's
  init-time selection is the only non-deterministic moment and it is frozen.

## Success Criteria

- **SC-001**: A fresh run with no selection produces ONLY the minimal-core
  scaffold; no optional module runs (verified end-to-end).
- **SC-002**: An agent-proposed selection is recorded and a clone reproduces the
  identical module set with no re-grilling.
- **SC-003**: Enabling a module auto-pulls its `requires`; an unknown enabled id
  errors clearly.
- **SC-004**: `--non-interactive`/CI runs base-only safely (no deadlock, no
  surprise optional modules).
- **SC-005**: Home-config enablement preference never overrides a committed
  project selection.

## Out of Scope

- Tier-2 stack-resolver / framework + version research (spec 003).
- Gates / review checkpoints + the two verified gate-blocking code fixes (spec
  004): init-mode confirm pass, `run_gate_step` non-interactive handler.
- Changing the manifest schema or the discovery/collision rules from 001.

## Assumptions

- `DiscoveredModule.default_enabled` (tri-state) already exists and is the data
  the filter consumes.
- The answers/persistence machinery from 001 (`merge_module_answers_to_persist`,
  per-key provenance) extends naturally to a `[modules]` enablement record.
- The agent-led selection rides the existing agent-step / SKILL.md mechanism;
  no new runtime primitive is required (selection is recorded as answers).
