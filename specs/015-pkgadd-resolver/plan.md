# Implementation Plan: 015 Package-Add Tier-2 Resolver

**Spec**: `specs/015-pkgadd-resolver/spec.md` · **Status**: Draft (2026-06-29)
**Baseline**: full suite 737 passed, 4 deselected (post 016).

Security-sensitive: extends package-add while preserving the path-traversal guards
verbatim. No runner changes (OQ-3 verified: gate_blocked is per-module, blocks python
steps after a declined gate — step ordering gives correct behavior). FR-004's
cross-module sibling-pin read uses the `all_answers` context view shipped in 007 Phase-0.

## Resolved OQs (leans applied)

- **OQ-3 (gate_blocked scope)** → VERIFIED at reproduce.py:461-477; step order
  resolve→pins→manifest→add→workspace-edit-gate→workspace-edit is correct. No runner change.
- **OQ-4 (Go/Rust verify)** → DEFERRED; lang=go/rust skip verify_pins + warn.

## Phase 1 — module.toml (inputs + steps) + guard-preservation refactor

1. `package-add/module.toml`: add declared input `resolve_stack` (bool, default false,
   required false). Add steps so order is: `resolve`(agent, steering/resolve.md,
   when="resolve_stack == true") → `pins`(gate, hard, allow_flag=allow-stack-write,
   init_only=true, when="resolve_stack == true", message="{decision}") →
   `manifest`(python, when="resolve_stack == true") → `add`(python, EXISTING) →
   `workspace-edit-gate`(gate, soft, skip_flag=no-workspace-manifest-edit) →
   `workspace-edit`(python). NOTE: declare any `when` key (resolve_stack) as an input
   (004 OQ-2) — done.
2. `package-add/module.py`: it currently uses `def main()` dispatched on `--step` with the
   guards at the TOP (every step re-runs them). PRESERVE that: keep `_validate_name` +
   `is_safe_relative_path` + lang validation at the top of main(), unconditionally, BEFORE
   any step-specific path construction (FR-001/002/016/SC-002). Then dispatch on args.step:
   "add" → existing dir-create logic (unchanged); "manifest" → _do_manifest; "resolve" is
   kind=agent (runner-dispatched, no python handler); "workspace-edit" → _do_workspace_edit.
   The agent/gate steps have NO python handler. Guard the dispatch so an unknown step is a
   clean error.

**Tests (Phase 1):** manifest parses; step order + flags correct; resolve_stack declared.
SC-003 regression: a `resolve_stack=false` plan runs ONLY `add` (the when drops the rest) —
the existing package-add test suite (test_module_package_add.py) MUST stay green unchanged.
**Gate full suite.**

## Phase 2 — manifest write + workspace edit (python handlers)

`_do_manifest(sdk, inputs, args)` (FR-007):
- Re-run guards (they're at top of main, so already done before dispatch) — confirm the
  path is constructed only after the guards.
- Read `aligned_pins` (package_manifest_type, pinned_deps) from FrozenInputs. Verify pins
  via verify_pins in init mode (FR-005): pypi/npm only; go/rust skip+warn; disconfirmed →
  INPUT_VALUE_INVALID. Render the per-package manifest (pyproject.toml/package.json/go.mod/
  Cargo.toml) into `{dir}/{name}/` via idempotent_write(reconcile=False). Deterministic
  (sorted keys, no wall-clock).
`_do_workspace_edit(sdk, inputs, args)` (FR-010):
- Re-run guards. Append the new member to the root workspace manifest via append_if_absent
  with marker `# project-setup: {name}` (idempotent). Per-lang target: uv
  `[tool.uv.workspace]` members / root package.json workspaces / go.work use / Cargo.toml
  [workspace] members. (Keep the append minimal + format-correct; reuse _workspace_guidance's
  knowledge of the per-lang location.)

**Tests (Phase 2):** SC-001 (resolve_stack=true + sibling pins via all_answers fixture →
aligned_pins reuses frozen versions; manifest written with them); SC-002 (name=../../etc →
PATH_ESCAPE in manifest step too, no write); SC-004 (declined pins gate → no dir/manifest);
SC-005 (declined workspace-edit → dir+manifest intact, command printed); SC-006 (workspace-edit
idempotent — re-run no double-append); SC-007 (manifest shape). Use the pipeline harness for
the gate/decline behaviors (test_two_phase_resolver-style); unit-test _do_manifest/_do_workspace_edit
directly for the write logic. **Gate full suite.**

## Phase 3 — steering + closeout

1. `package-add/steering/resolve.md` (FR-004): agent reads context["all_answers"] for
   lang-python.pinned_deps / lang-ts.pinned_deps; aligns the new package's pins to those
   frozen versions; no siblings → fresh resolution; emit aligned_pins (framework,
   pinned_deps name@exact, package_manifest_type, rationale); exact pins, no ranges/latest;
   note go/rust skip verification (OQ-4).
2. Final full-suite gate; flip spec Status → Implemented; write memory.md AS-BUILT
   (honest note on which SCs are pipeline-tested vs unit-tested). Commit (unsigned per session).

## Risk notes

- **SECURITY (highest priority):** the path-traversal guards must run before EVERY path
  construction in every step. Keeping them at the top of main() (current design) preserves
  this — do NOT move path construction above the guards. SC-002 asserts PATH_ESCAPE in both
  add and manifest. Do not let the agent step's output feed a path without re-validation.
- gate_blocked: verified per-module + after-declined-gate; step order is load-bearing — do
  not reorder pins/manifest/add or the blocking semantics change.
- SC-003 regression guard (resolve_stack=false = unchanged behavior) is the backward-compat
  anchor — the existing package-add suite must stay byte-green.
- Re-run the full suite in the main thread per phase (don't trust subagent -k counts).
