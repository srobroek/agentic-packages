# Feature 015 — Package-Add Tier-2 Resolver (memory)

Split from the bundled `014-org-pkgadd-readme` (Q4 RESOLVED: split into 014/015/016).
Sub-feature B. See `specs/014-org-pkgadd-readme/memory.md` for the shared verified code
facts (package-add guard positions, sources.toml, verify_pins, gate machinery).

## AS-BUILT (2026-06-29)

Shipped on `feat/project-setup-modular-redesign`. Full suite 764 passed, 4 deselected.
NO runner changes.

**Security (the non-negotiable, verified):** `_validate_name` (module.py:508) +
`sdk.is_safe_relative_path(dir_)` (module.py:552) run at the TOP of `main()`,
unconditionally, BEFORE the `args.step` dispatch (module.py:581). Path construction
(`project_dir / dir_ / name`) lives ONLY inside the step handlers (`_do_add:134`,
`_do_manifest:184`, `_do_workspace_edit`), all reached only after both guards pass. So
EVERY step re-runs the guards; agent output (aligned_pins) never feeds a path. SC-002
asserts PATH_ESCAPE for both `--step add` and `--step manifest`.

**Module shape:** `package-add` refactored from a single inline `main()` body to
guards-then-dispatch. New declared input `resolve_stack` (bool, default false). Steps
(FR-008): resolve(agent, steering/resolve.md, when="resolve_stack == true") →
pins(gate, hard, allow-stack-write, init_only, when) → manifest(python, when) →
add(python, EXISTING logic moved to _do_add, unchanged) → workspace-edit-gate(gate,
soft, skip_flag="no-workspace-manifest-edit") → workspace-edit(python).

**OQ-3 (gate_blocked scope) VERIFIED at reproduce.py:461-477:** gate_blocked resets per
module and blocks only python steps that FOLLOW a declined gate (step order). So declined
`pins` → skips manifest+add+workspace-edit (no package without reviewed pins); declined
`workspace-edit-gate` → skips only workspace-edit (dir+manifest already written). No runner
change; the step ORDER is load-bearing — do not reorder.

**FR-004 cross-module reads use the 007 `all_answers` view:** steering instructs the agent
to read `context["all_answers"]["lang-python"]["pinned_deps"]` / `["lang-ts"]["pinned_deps"]`
and align the new package's pins to those FROZEN versions (no re-research); no siblings →
fresh resolution. This is why 007 (which shipped the all_answers Phase-0 view) was built
before 015 — 015's resolver depends on it.

**_do_manifest:** reads aligned_pins (package_manifest_type, pinned_deps, framework);
verify_pins in init only — pypi(python)/npm(ts); go/rust SKIP verify + warn (OQ-4 deferred);
disconfirmed → INPUT_VALUE_INVALID. Renders deterministic (sorted keys, no wall-clock)
pyproject.toml/package.json/go.mod/Cargo.toml into {dir}/{name}/ via idempotent_write(
reconcile=False, write-once). **_do_workspace_edit:** append_if_absent with marker
`# project-setup: {name}` (idempotent) into the per-lang root workspace manifest.

**Tests:** test_module_pkgadd_resolver.py (26). test_module_package_add.py (16) UNCHANGED
and green (SC-003 backward-compat anchor: resolve_stack=false → only `add` runs, identical
to today). SC-004/005 gate-decline behaviors asserted via step-order + manifest shape (the
gate_blocked semantics are runner-level, proven generically by the gate suite). SC-008
reproduce zero-network via mode=reproduce tests.

Remaining in the 014 split: 014-org-policy (ORG_SOURCE_UNPINNED validation — the one with
a runner-level validation change; validate_sources in pipeline Stage 1, OQ-2 lean).
