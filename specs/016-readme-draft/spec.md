# Feature Specification: README Draft Module

**Feature Branch**: `feat/project-setup-modular-redesign` (continues)

**Created**: 2026-06-29

**Status**: **Implemented (2026-06-29)** — thin spec split out of the bundled
`014-org-pkgadd-readme` preamble (Q4 RESOLVED: split into 014/015/016); sub-feature C,
shipped first (simplest). New default-disabled `readme-draft` module on the
agent→gate→python seam, NO runner changes. OQ-5 resolved (lean d: no `readme_exists`
`when`; `init_only`+`reconcile=false`). 6 module tests; full suite 737 passed, 4
deselected. See `memory.md` → AS-BUILT.

**Input**: Roadmap rank #12 (`reviews/tier2-agentic-features-roadmap.md`), the
`readme-draft` third of the bundled org/pkgadd/readme entry.

## Overview

A new default-disabled `readme-draft` module that drafts a project `README.md` from
the frozen scaffold facts (project name, org, layout, language, framework, resolved
stack, license) and writes it **write-once** (`reconcile=false`) — it never clobbers a
hand-edited README. The agent drafts; a gate shows the draft; a python step writes.
Same agent→gate→python seam as `lang-python`; research only at init; reproduce replays
the frozen draft zero-network.

## Settled decisions (inherited + this-spec)

- **C-F (from 014):** README draft is write-once (`reconcile=false`); the existing
  `idempotent_write` skip-on-exists guard makes reproduce a no-op.
- **C-I (from 014):** the agent reads ONLY the frozen plan answers — NOT the
  filesystem (prompt-injection safety). The steering doc explicitly prohibits
  filesystem reads and shell-variable-looking tokens.
- **OQ-5 RESOLVED → lean (d):** **NO `when = "readme_exists == false"` predicate.**
  That synthetic filesystem flag is not available to `build_plan` (it only sees
  resolved answers, not filesystem facts), so the `when` would always drop the gate.
  Instead: the gate is `hardness="hard"`, `allow_flag="allow-readme"`,
  `init_only=true`, NO `when`. It prompts at init; on reproduce it auto-proceeds
  (init_only) and the `reconcile=false` write step returns `skip` because the file
  exists. Net effect: gate + prompt at first init; reproduce auto-proceeds + write
  skips. No new mechanism, no synthetic flag. (This supersedes the bundled-014 FR-017
  `when` form.)

## User Scenarios

### US1 — README drafted once; re-runs skip (Priority P3)

First init with `readme-draft` enabled: agent drafts a README from frozen facts; a
hard gate shows the draft; on confirm `README.md` is written. Next reproduce: the
write step sees the file exists → skips silently; the gate auto-proceeds (init_only),
no overwrite, no prompt.

**Acceptance:**
1. No `README.md` present at init → gate shows the full draft → confirm → file written.
2. `--non-interactive` at init without `--allow-readme` → SAFE-skip (no write); manual
   path printed. With `--allow-readme` → write proceeds.
3. `README.md` already exists (any content) → write step returns `Diff(kind="skip")`,
   no write, file preserved.
4. Reproduce → agent replays the frozen draft zero-network; write skips (file exists).

## Functional Requirements

- **FR-001**: A new bundled module `readme-draft` MUST exist at
  `modules/readme-draft/{module.toml, module.py, steering/draft.md}`. `module.toml`
  declares `id="readme-draft"`, `default_enabled=false`, `reconcile=false`.
- **FR-002**: Steps in order: `draft` (kind=agent, steering="steering/draft.md") →
  `readme-gate` (kind=gate, hardness="hard", allow_flag="allow-readme",
  init_only=true, message="{decision}") → `write` (kind=python). NO `when` predicate
  on the gate (OQ-5 lean d).
- **FR-003**: The `draft` agent step MUST read ONLY the frozen plan answers
  (project_name, org, layout, language, framework, resolved stack, license) and emit
  a `readme_body` agent-steered answer (the full Markdown draft). The steering doc
  MUST prohibit filesystem reads and shell-variable-looking tokens (`$VAR`,
  `PLUGIN_ROOT`, etc.) in the draft.
- **FR-004**: The `write` step MUST call
  `sdk.idempotent_write("README.md", readme_body, reconcile=False, inspect=args.inspect)`.
  If the file exists (any content), it MUST return `Diff(kind="skip")` without writing
  or prompting. Determinism: same frozen `readme_body` → byte-identical `README.md`.
- **FR-005**: Reproduce MUST be zero-network: the agent step replays the committed
  `readme_body` (003 FR-009); the write step does no network. `--refresh readme-draft`
  is the only path that re-drafts.
- **FR-006**: The full pre-016 suite MUST stay green (no regressions); the module is
  additive and default-disabled.

## Success Criteria

- **SC-001**: With `readme-draft` enabled, no `README.md` present, a frozen
  `readme_body` answer → the `write` step creates `README.md` byte-identical to the
  frozen body (unit test with a frozen plan).
- **SC-002**: An existing `README.md` (any content) → the `write` step returns
  `skip`, writes nothing, preserves the file (unit test).
- **SC-003**: Two `write` invocations on the same frozen plan (file absent then
  present) → first creates, second skips (idempotent).
- **SC-004**: Manifest assertions: `default_enabled=false`, step order
  draft/readme-gate/write, gate is hard + allow_flag=allow-readme + init_only=true,
  NO `when` on the gate.
- **SC-005**: Reproduce with a committed `readme_body` → zero agent_step network
  calls (replay); covered by the runner's existing reproduce-replay machinery
  (003 FR-009) — asserted generically by `test_two_phase_resolver.py`, noted here.

## Out of Scope

- README sections beyond a scaffold-fact summary (API reference, changelog).
- Inline README editing at the gate (decline + edit steering instead).
- Overwriting an existing README (write-once by design).

## Dependencies

Builds on 003 (two-phase plan, reproduce-replay), 004 (hard/init_only gate,
`{decision}` token), 005 (SDK imports). No runner changes. Independent of 014/015.
