# Feature Specification: Package-Add Tier-2 Resolver

**Feature Branch**: `feat/project-setup-modular-redesign` (continues)

**Created**: 2026-06-29

**Status**: **Implemented (2026-06-29)** — thin spec split out of the bundled
`014-org-pkgadd-readme` preamble (Q4 RESOLVED: split into 014/015/016). Sub-feature B.
package-add extended with the optional Tier-2 resolver; path-traversal guards PRESERVED
verbatim at the top of `main()` before any step dispatch (security-pinned, verified).
Reuses the 007 Phase-0 `all_answers` context view for cross-module sibling-pin reads.
No runner changes (OQ-3 verified). 26 module tests + existing package-add suite green
unchanged; full suite 764 passed, 4 deselected. See `memory.md` → AS-BUILT.

**Input**: Roadmap rank #12 (`reviews/tier2-agentic-features-roadmap.md`), the
monorepo `package-add` resolver third of the bundled entry.

## Overview

Extend the existing `package-add` module (today a single `kind=python` directory-creator
with security-pinned path-traversal guards) with an OPTIONAL Tier-2 resolver: an agent
step aligns the new monorepo package's framework + version pins with already-frozen
sibling pins, a hard gate reviews the pins, a python step writes the per-package
manifest, and a soft gate covers the shared root-workspace-manifest edit. The
path-traversal guards remain verbatim and run before any `mkdir` — **agent output can
never bypass them.**

## Settled decisions (inherited from 014, this-spec relevant)

- **C — Path-traversal guards are SECURITY-PINNED, run BEFORE any agent step or mkdir.**
  `_validate_name` (`module.py:61-75`) + `sdk.is_safe_relative_path(dir_)`
  (`module.py:160`) MUST remain verbatim. They currently run at the TOP of `main()`
  (every `--step` invocation re-runs them) — that property is PRESERVED: every new step
  re-runs the guards before constructing any path. No agent answer relaxes them.
- **D — The resolver ALIGNS, never overrides, frozen sibling pins.** The agent reads the
  frozen plan's sibling answer blocks (`lang-python.pinned_deps`, `lang-ts.pinned_deps`)
  via `context["all_answers"]` (the 007 Phase-0 read-only view — now available) and
  proposes versions COMPATIBLE with what's frozen; it does NOT re-decide sibling pins. No
  siblings → fall back to fresh resolution. Best-effort, declinable.
- **E — Two gates: hard on the new package manifest, soft on the root workspace edit.**
- **OQ-3 RESOLVED (verified `reproduce.py:461-477`):** `gate_blocked` resets per module
  and blocks only python steps that FOLLOW a declined gate (step order). Step order
  `resolve → pins(hard) → manifest → add → workspace-edit-gate(soft) → workspace-edit`
  gives correct blocking BOTH ways: declined `pins` skips manifest+add+workspace-edit
  (no package without reviewed pins); declined `workspace-edit-gate` skips only
  workspace-edit (dir+manifest already written). NO runner change.
- **OQ-4 (Go/Rust verify):** DEFERRED. `verify_pins` supports pypi/npm only; lang=go/rust
  skip verification with a warning. Documented in steering.

## User Scenarios

### US1 — Align a new package with sibling Python pins (Priority P2)

Add `packages/workers` to a monorepo that already froze `fastapi@0.111.0` +
`pydantic@2.7.1` in `packages/api`. The resolver reads those sibling pins (via
`all_answers`) and recommends the SAME frozen versions (not latest). Hard gate shows the
aligned pins (verified at init); on confirm `packages/workers/pyproject.toml` is written;
a soft gate offers the root-manifest workspace-member edit.

**Acceptance:**
1. `resolve_stack=true` + sibling pins present → `aligned_pins` reuses sibling frozen
   versions, flags conflicts with rationale.
2. Pins verified via `verify_pins` (init only); disconfirmed → rejected.
3. Manifest gate is hard (`allow-stack-write`, `init_only`); guards ALREADY ran before it.
4. Workspace-edit soft gate shows the exact line + manual command; CI
   `--no-workspace-manifest-edit` skips; without the flag it proceeds.
5. Existing `packages/workers/` → dir-create skips (reconcile=false); manifest skips if
   it exists.

### US2 — Path-traversal guard blocks an agent-injected escape (Priority P1)

A malformed agent/interview value `name="../../etc"` → `_validate_name` fires before any
mkdir → `PATH_ESCAPE`, no directory created, step exits.

**Acceptance:**
1. `name="../../etc"` → `PATH_ESCAPE`, no filesystem side-effect.
2. Every step (resolve/manifest/add) re-runs `_validate_name` + `is_safe_relative_path`
   unconditionally, regardless of whether the agent step ran or was skipped.

### US3 — Opt-out is unchanged behavior (Priority P1, regression guard)

`resolve_stack=false` (or the `when` false) → IDENTICAL to today's package-add: dir
created, workspace guidance printed, no agent step, no manifest written.

### Edge Cases

- No sibling pins → agent falls back to fresh resolution; gate notes "no sibling pins".
- `lang=go`/`lang=rust` → resolver runs (emits go.mod/Cargo.toml stub decision) but
  `verify_pins` is skipped with a warning (OQ-4).
- Declined `pins` gate → no dir, no manifest (gate_blocked skips all following steps).
- Declined `workspace-edit` soft gate → dir+manifest intact, manual command printed.

## Functional Requirements

### Security-pinned guards (non-negotiable)

- **FR-001**: `_validate_name` (`module.py:61-75`) MUST remain verbatim and run BEFORE
  any `mkdir`/path construction in EVERY step invocation, regardless of agent step
  outcome. (Preserved by keeping the guards at the top of `main()`.)
- **FR-002**: `sdk.is_safe_relative_path(dir_)` MUST similarly remain verbatim and run
  before any path construction in every step.

### Resolver agent step

- **FR-003**: `package-add/module.toml` MUST gain an OPTIONAL `kind=agent` step
  (`id="resolve"`) BEFORE the `add` step, gated by `when = "resolve_stack == true"`
  (a new declared bool input, default false — so existing behavior is unchanged when not
  opted in). It emits an `aligned_pins` decision (`framework`, `pinned_deps:[name@exact]`,
  `package_manifest_type`, `rationale`) as agent-steered answers.
- **FR-004**: The steering doc MUST instruct the agent to read the frozen sibling answer
  blocks (`lang-python.pinned_deps`, `lang-ts.pinned_deps`) via `context["all_answers"]`
  (007 Phase-0) and align the new package's pins to those frozen versions where the same
  package appears — it MUST NOT re-research already-frozen sibling pins. No siblings →
  fresh resolution.
- **FR-005**: Every pin in `aligned_pins.pinned_deps` MUST be verified via
  `sdk.verify_pins` in `"init"` mode only (003 FR-009). Disconfirmed → INPUT_VALUE_INVALID;
  unreachable → warn + safe-skip the write. lang=go/rust → skip verify + warn (OQ-4).

### Gates + manifest

- **FR-006**: A `kind=gate` step (`id="pins"`, `hardness="hard"`,
  `allow_flag="allow-stack-write"`, `init_only=true`, `when="resolve_stack == true"`)
  MUST fire after `resolve` and before `manifest`. Message shows the aligned pin table
  via `{decision}`. Declined → gate_blocked skips manifest+add+workspace-edit.
- **FR-007**: A `kind=python` step (`id="manifest"`, when="resolve_stack == true") MUST
  write the per-package manifest (`pyproject.toml`/`package.json`/`go.mod`/`Cargo.toml`)
  inside the new package dir via `sdk.idempotent_write(reconcile=False)` (write-once).
  It MUST re-run `_validate_name` + `is_safe_relative_path` before constructing the path.
- **FR-008**: The existing `add` step (dir creation) is PRESERVED unchanged (guards +
  `reconcile=false` skip-on-exists). Step order: resolve → pins → manifest → add →
  workspace-edit-gate → workspace-edit.
- **FR-009**: A `kind=gate` step (`id="workspace-edit-gate"`, `hardness="soft"`,
  `skip_flag="no-workspace-manifest-edit"`) MUST fire after `add` and before a new
  `kind=python` `workspace-edit` step. Message shows the exact root-manifest line + the
  manual command. Declined → skips only `workspace-edit`.
- **FR-010**: The `workspace-edit` python step MUST use `sdk.append_if_absent` with a
  per-package marker (`# project-setup: {name}`) so re-runs don't double-append. It edits
  the root workspace manifest for the lang (uv `[tool.uv.workspace]` members, root
  package.json `workspaces`, `go.work` use, `Cargo.toml` `[workspace]` members). It MUST
  re-run the guards before constructing paths.

### Determinism & compatibility

- **FR-011**: Reproduce is zero-network (agent replays frozen `aligned_pins`; verify only
  at init). `--refresh package-add` re-invokes the resolver.
- **FR-012**: When `resolve_stack=false` (default), behavior is IDENTICAL to today's
  package-add (the `when` drops resolve/pins/manifest/workspace-edit; only `add` runs).
  The existing package-add test suite MUST stay green unchanged.
- **FR-013**: The full pre-015 suite MUST stay green.

## Success Criteria

- **SC-001**: `resolve_stack=true` + sibling `lang-python.pinned_deps` present →
  `aligned_pins` reuses the sibling frozen versions (not latest); each pin verified at
  init; gate shows verify status (test with stubbed registry + `all_answers` fixture).
- **SC-002**: `name="../../etc"` → `PATH_ESCAPE`, no directory created — asserted in BOTH
  the `add` and `manifest` steps (re-run guards).
- **SC-003**: `resolve_stack=false` → identical to current package-add: dir created, no
  agent step, no manifest, workspace guidance printed (existing suite green unchanged).
- **SC-004**: Declined `pins` gate → no dir, no manifest on disk (gate_blocked).
- **SC-005**: Declined `workspace-edit` soft gate → dir+manifest intact, manual command
  printed; CI without `--no-workspace-manifest-edit` appends the workspace entry.
- **SC-006**: `workspace-edit` is idempotent — re-run does not double-append (marker).
- **SC-007**: Manifest assertions: step order resolve/pins/manifest/add/workspace-edit-gate/
  workspace-edit; pins gate hard+allow-stack-write+init_only+when; workspace-edit-gate
  soft+skip_flag; resolve_stack declared bool default false.
- **SC-008**: Reproduce with committed `aligned_pins` → zero network (replay).

## Out of Scope

- Go/Rust registry verification (OQ-4 deferred; warn + skip).
- Multi-package batch add. One package per run.
- Re-deciding sibling pins (alignment only, Decision D).

## Dependencies

Builds on 003 (two-phase plan, verify_pins, reproduce), 004 (hard/soft/init_only gates,
when, gate_blocked), 007 (the `all_answers` Phase-A context view — REQUIRED for FR-004
cross-module sibling-pin reads). No runner changes. Independent of 014/016.
