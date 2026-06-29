# Feature 016 — README Draft Module (memory)

Split from the bundled `014-org-pkgadd-readme` (Q4 RESOLVED: split into 014/015/016).
Sub-feature C, shipped first as the simplest. See `specs/014-org-pkgadd-readme/memory.md`
for the shared verified code facts (idempotent_write reconcile=false skip-on-exists,
{decision} token, FrozenInputs.mode, lang-python agent→gate→python template).

## AS-BUILT (2026-06-29)

Shipped on `feat/project-setup-modular-redesign`. Full suite 737 passed, 4 deselected.
NO runner changes (default-disabled additive module).

- `modules/readme-draft/`: module.toml (id=readme-draft, default_enabled=false,
  reconcile=false, after=[core-identity, lang-*], no requires) + module.py + steering/draft.md.
- Steps: draft(agent, steering/draft.md) → readme-gate(gate, hard, allow_flag=allow-readme,
  init_only=true, {decision} message, **NO `when`**) → write(python).
- **OQ-5 resolved (lean d):** dropped the bundled-014 FR-017 `when="readme_exists==false"`
  predicate — a filesystem fact is NOT in build_plan's resolved_answers, so the `when`
  would always drop the gate. Instead `init_only=true` + `reconcile=false`: gate prompts
  at init; reproduce auto-proceeds (init_only) and the write returns skip (file exists).
  No synthetic flag, no new mechanism.
- module.py _do_write: reads `readme_body` (agent-steered) via load_frozen_inputs;
  `idempotent_write("README.md", readme_body, reconcile=False, inspect)`. Empty body →
  warning + no write. No wall-clock (asserted by an AST check in the test).
- steering/draft.md: agent reads ONLY frozen plan answers (project_name/org/layout/
  language/framework/stack/license), emits one `readme_body` answer; PROHIBITS filesystem
  reads (prompt-injection) + shell-variable-looking tokens.
- Tests: test_module_readme_draft.py (6): SC-001 create / SC-002 preserve-existing /
  SC-003 idempotent / SC-004 manifest shape (no `when` on gate) / empty-body warning /
  no-wall-clock. SC-005 (reproduce zero-network) covered generically by 003's replay
  machinery (test_two_phase_resolver), not re-asserted.

Remaining in the 014 split: 015-pkgadd-resolver (security path-traversal), 014-org-policy
(ORG_SOURCE_UNPINNED validation). Both have leaned OQs in 014's memory; 015 has a
verify-step (OQ-3 gate_blocked scope) + the non-negotiable _validate_name/is_safe_relative_path
preservation; 014 adds a runner validation (validate_sources in pipeline Stage 1, OQ-2).
