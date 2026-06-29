# Implementation Plan: 007 CI Matrix Sized to Stack

**Spec**: `specs/007-ci-matrix/spec.md` · **Status**: Draft (2026-06-29)
**Baseline**: full suite 707 passed, 4 deselected (post 013).

Plan-then-delegate. 007 needed a verified premise check FIRST (synthesis OQ-3): the CI
agent must read OTHER modules' frozen answers to size the matrix, but the runner only
gave an agent its OWN answers. RESOLVED (user): add a read-only `all_answers` view to the
Phase-A agent context — a small additive runner change (Phase 0 below). Then the module
ships as the spec intends.

## Resolved open questions / decisions

- **Cross-module visibility (the blocking gap)** → RUNNER CHANGE: broaden the Phase-A
  agent `context` dict with `all_answers` (read-only snapshot of all resolved answers so
  far). Additive, backward-compatible (existing agents ignore the new key). Phase 0.
- **OQ-1** → NO live GitHub API probe in the python step (rate limits, zero-network-on-
  reproduce). Agent + steering + context7 carry action-major research; `--refresh` handles
  drift.
- **OQ-2** → FLAT scalar agent-steered keys (`ci_plan_jobs`, `ci_plan_action_refs`,
  `ci_plan_matrix`, `ci_plan_commands`) — inspectable, lang-* precedent, per-key refresh.
- **OQ-3** → NO `ci_matrix_versions` input in v1 (single-version matrix; over-broad
  matrices are the anti-goal). TODO comment for a future spec.

## Phase 0 — Runner: read-only `all_answers` in the Phase-A agent context

`runner/reproduce.py` `run_agent_phase`, the context build (currently ~647-651):
```
context = {
    "module_id": mod_id,
    "step_id": step_id,
    "answers": dict(answers.get(mod_id, {})),
    "all_answers": {m: dict(a) for m, a in answers.items()},  # NEW: read-only view
}
```
`answers` at this point is the accumulator folded in topo order, so a module ordered
`after` lang-* sees their already-emitted answers. Pass a COPY (read-only intent — the
agent's response only persists via `answers_to_persist`, never by mutating context).
Backward-compatible: every existing agent ignores the new key.

**Tests (Phase 0, runner-level):** extend `tests/test_two_phase_resolver.py` (or
`test_reproduce_only.py`) — a synthetic two-module plan where module B is ordered after A;
assert B's agent context carries `all_answers` containing A's emitted answer. Assert
existing single-module agents still work (backward-compat). **Gate full suite.**

## Phase 1 — ci-github-actions module scaffold (module.toml + steering)

`modules/ci-github-actions/` (FR-001/002/003/004/005/006/007):
- module.toml: `id="ci-github-actions"`, `default_enabled=false`, `reconcile=true`,
  `[order] after=["justfile-write","lang-python","lang-ts","lang-go","lang-rust"]`.
  Inputs: `ci_trigger` (multichoice push/pull_request/workflow_dispatch, default
  [push,pull_request]), `default_branch` (string, default "main"). Steps:
  `resolve`(agent, steering/resolve.md) → `ci-review`(gate, hard, allow_flag=allow-ci-write,
  init_only=true, message="{decision}") → `write`(python).
- steering/resolve.md: instruct the agent to read `all_answers` (Phase 0) for active
  lang-* overlays (python_version, package_manager, use_just); emit FLAT agent-steered
  keys (ci_plan_jobs, ci_plan_action_refs, ci_plan_matrix, ci_plan_commands); size matrix
  to ACTUAL stack only (one entry per frozen lang version); action refs `owner/repo@vN`
  current-major (context7/whats-new if available, agent knowledge fallback); NEVER floating
  refs/ranges/latest.

**Test (Phase 1):** manifest parses; steps/inputs/gate flags correct. **(gate folded with P2.)**

## Phase 2 — write step (validate + canonical YAML render)

`module.py` `_do_write` (FR-010..018), stdlib-only (`dependencies=[]`):
- Read flat ci_plan_* answers via FrozenInputs; read cross-module answers via
  `sdk.load_plan(args.plan).modules[...].answers` (the python step CAN read the full plan)
  for matrix trimming (FR-015) against the frozen `python_version` etc.
- Command validation (FR-012): `just <recipe>` → must exist in on-disk justfile (line-prefix
  scan); `{bun,pnpm,npm} run <script>` → must exist in package.json scripts; bare tool
  commands pass through; floating action ref (no `@v`) → FIXME placeholder + warning.
  Dropped commands → WARN, not hard error.
- Canonical YAML renderer (FR-013): pure-stdlib dict→YAML, 2-space indent, deterministic
  key order, real `true`/`false`, quote special-char values. Standalone function. Same
  ci_plan → identical bytes (FR-017, SC-006).
- Matrix trimming (FR-015): trim to frozen lang version, warn on excess.
- Zero jobs after validation (FR-014) → status ok, files_written=[], warning, NO empty YAML.
- Write `.github/workflows/ci.yml` via idempotent_write(reconcile=True). Zero-network on
  reproduce (FR-016).

**Tests (Phase 2):** SC-001 (python-only → 1 job, just test/lint verified, owner/repo@vN);
SC-002 (py+ts → 2 jobs, ts uses frozen package_manager); SC-003 (just deploy missing →
dropped+warn, YAML still written); SC-005 (floating ref → FIXME+warn); SC-006 (render twice
→ byte-identical); SC-008 (zero valid jobs → files_written=[]+warn); SC-004 (gate hard +
allow-ci-write + init_only: --non-interactive safe-skips, flag proceeds, reproduce auto-
proceeds — ScriptedIO); SC-007 (reproduce zero-network). **Gate full suite.**

## Phase 3 — closeout

Final full-suite gate; flip spec Status → Implemented; fill memory AS-BUILT (record the
Phase-0 all_answers runner addition + that python-step cross-module reads use load_plan).
Commit (unsigned if 1Password still failing).

## Risk notes

- Phase 0 touches the SHARED Phase-A context for EVERY agent module — must be additive +
  backward-compatible (a copy, read-only). Full-suite gate is the guard; assert existing
  agents unaffected. This is a deliberate, user-approved runner change (not scope creep).
- YAML renderer determinism is the core Tier-1 contract — no wall-clock, sorted/explicit
  key order, byte-identical (SC-006).
- Re-verify line numbers at implementation (spec cites HEAD 7779c27; many commits since).
- Re-run the full suite in the main thread per phase — do not trust subagent -k counts.
