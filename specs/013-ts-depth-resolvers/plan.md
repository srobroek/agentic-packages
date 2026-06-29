# Implementation Plan: 013 TypeScript Depth Resolvers

**Spec**: `specs/013-ts-depth-resolvers/spec.md` · **Status**: Draft (2026-06-29)
**Baseline**: full suite 693 passed, 4 deselected (post 012).

Plan-then-delegate convention: inline phases below. 013 adds NO runner machinery — it
extends the `lang-ts` module only (inputs, steps, steering, templates, module.py). Each
phase gates on the full suite.

## Resolved open questions (leans applied — no human-blocking items)

- **OQ-1** → `test_runner` is a single `choice` with composite enum values
  (`"vitest-node+playwright"` is a legitimate atom); the composite template dir holds
  both config files. No `multichoice` plumbing. Extend later if needed.
- **OQ-2 / scope** → **v1 = `shadcn` + `none` ONLY**. `nuxt-ui` deferred to a follow-up
  (Nuxt UI v3 alpha/RC churn). `ui_kit_id` enum + allowlist designed to extend. (Matches
  the synthesis lean.)
- **OQ-3** → keep `.node-version`/`engines` writes inside `_do_write` (small; ~2-5 lines
  each). Split only if it grows unmanageable.
- **OQ-4** → agent emits the literal `ui_kit_init_command` (with flags), python validates
  the prefix against an allowlist. Allowlist v1: `["npx shadcn", "bunx shadcn",
  "pnpm dlx shadcn"]`. (nuxi entries deferred with nuxt-ui.)

## Phase 1 — module.toml inputs + steps + step ordering

1. `lang-ts/module.toml`: add three declared inputs (NOT interview — agent-decided, but
   declared so `when` parses without MANIFEST_MALFORMED, FR-021/Fact 7):
   `test_runner` (string, default `""`), `ui_kit_id` (string, default `"none"`),
   `runtime` (string, default `"bun"`). (Also `node_line`, `template_id`,
   `ui_kit_init_command` if any `when`/gate references them — declare any key used in a
   predicate; agent-emitted-only keys that are never in a `when` need not be declared but
   declaring them is harmless and documents the contract — declare all six new keys.)
2. Add two new steps in the FR-019 order: after `scaffold` →
   `ui-kit-init` (kind=gate, hardness=hard, allow_flag="allow-ui-kit-init",
   init_only=true, when="ui_kit_id != none", message="{decision}"-style showing the
   init command) → `ui-kit-scaffold` (kind=python).
   Final order: resolve → pins → write → run-generator → scaffold → ui-kit-init → ui-kit-scaffold.

**Test (Phase 1):** extend `tests/test_module_lang_ts.py` (or a manifest test): the
module.toml parses with no errors; the new inputs are declared; `ui-kit-init` gate has
hardness=hard + init_only + when="ui_kit_id != none" + allow_flag; step order matches
FR-019; `when` references only declared inputs (no MANIFEST_MALFORMED). **Gate full suite.**

## Phase 2 — write-step extensions (test-runner templates + PM validation + runtime files)

`lang-ts/module.py` `_do_write` + helpers:
1. **Test-runner templates (FR-001/002/003/005):** read `template_id` from FrozenInputs;
   if in the allowed enum (`vitest-node`, `vitest-browser`, `bun-test`, `playwright-only`,
   `vitest-node+playwright`, `none`) and != none, iterate `templates/<template_id>/` and
   `idempotent_write(reconcile=True)` each file. Unknown id → INPUT_VALUE_INVALID, write
   nothing (SC-009). `none` → no config files.
2. **PM shape validation (FR-013, Decision D):** before writing `packageManager`, guard
   `package_manager_pin` with `re.fullmatch` for `name@X.Y.Z[prerelease]` (reject
   `latest`, ranges, bare name). Mismatch → INPUT_VALUE_INVALID, write nothing (SC-007).
3. **PM/runtime consistency (FR-017):** if `package_manager` (interview) prefix disagrees
   with `package_manager_pin` name (e.g. PM=bun, pin=pnpm@…) → INPUT_VALUE_INVALID (SC-008).
4. **Runtime files (FR-014/015):** `runtime="node"` + non-empty `node_line` →
   `idempotent_write(".node-version", f"{node_line}\n", reconcile=False)` (write-if-absent)
   AND merge `{"node": f">={node_line}"}` into `package.json["engines"]` via the additively-
   extended `_patch_package_json(..., engines=...)` (Fact 6). `runtime="bun"` → no
   `.node-version`, no engines (FR-015, SC-006).

**New template files (FR-002):** create `templates/<id>/` for each enum atom with at least
the named config (`vitest.config.ts`, `playwright.config.ts`, `bunfig.toml`/`bun test`
config as appropriate). Composite `vitest-node+playwright/` holds both configs. Content is
minimal, valid, version-stable.

**Tests (Phase 2):** extend `tests/test_module_lang_ts.py` — SC-001 (vite+none → pinned
package.json w/ packageManager=bun@X.Y.Z + tsconfig + vitest config from template + no
.node-version); SC-002 (reproduce byte-identical); SC-006 (node+node_line=22 → .node-version
"22\n" + engines.node ">=22" + packageManager pnpm@…); SC-007 (bun@latest → INPUT_VALUE_INVALID,
nothing written); SC-008 (PM/pin mismatch → INPUT_VALUE_INVALID); SC-009 (unknown template_id
→ INPUT_VALUE_INVALID). **Gate full suite.**

## Phase 3 — UI-kit init gate + scaffold step (the G4-pattern reuse)

`lang-ts/module.py` add `_do_ui_kit_scaffold` handler + register in STEP_HANDLERS:
1. **ui-kit-scaffold (FR-008/011):** read `ui_kit_id` + `ui_kit_init_command`. If
   `ui_kit_id=="none"` → clean no-op exit (SC-012). Else validate `ui_kit_init_command`
   against the hardcoded allowlist prefixes (`npx shadcn`, `bunx shadcn`, `pnpm dlx shadcn`);
   unrecognized → INPUT_VALUE_INVALID, write nothing (SC-010). On a confirmed gate in init,
   execute via `sdk.run_tool` (SC-004).
2. **Non-interactive / reproduce safe-skip (FR-009/010):** when the gate hard-skips
   (--non-interactive without --allow-ui-kit-init) OR on plain reproduce (the init_only
   gate auto-proceeds but the scaffold is non-idempotent), the scaffold step SAFE-skips and
   writes a `STACK-NOTES.md` entry via `sdk.append_if_absent` recording the manual
   `ui_kit_init_command` (SC-003/SC-005). The deterministic dep-pin write (Phase 2) still
   replays byte-identically.
   NOTE: how the scaffold step learns the gate outcome — reuse the EXACT mechanism the
   existing `run-generator`→`scaffold` pair uses (read module.py:400-479; the soft gate's
   decline → scaffold skip). For ui-kit-init (HARD gate) mirror the G4 scaffold-split: a
   declined/skipped hard gate blocks the following python step's action; verify how
   reproduce.apply's gate-blocking (004) signals this to the step.

**Tests (Phase 3):** SC-003 (shadcn + --non-interactive → pins written, scaffold safe-skip,
STACK-NOTES has the command); SC-004 (shadcn + --allow-ui-kit-init + confirm → validated
command executed via run_tool stub); SC-005 (plain reproduce of shadcn project → gate no
prompt, scaffold safe-skip + STACK-NOTES note); SC-010 (bad command → INPUT_VALUE_INVALID);
SC-012 (ui_kit_id=none → ui-kit-init when-dropped, scaffold no-op). Prefer the pipeline
harness (test_two_phase_resolver-style) for the gate/reproduce behaviors. **Gate full suite.**

## Phase 4 — steering + closeout

1. `lang-ts/steering/resolve.md` (FR-022): extend with the three decision groups —
   (a) framework→test_runner+template_id table; (b) ui_kit→ui_kit_id+literal command+
   companion pins (shadcn + Tailwind v4); (c) package_manager→runtime+node_line+finalized
   package_manager_pin. Document all new answer keys' constraints (exact pins, enum values,
   no "latest"). Scope ui_kit_id to shadcn|none for v1 (note nuxt-ui as future).
2. SC-011 phase-ordering test (runtime answers present in resolved_answers before scaffold):
   covered structurally by the two-phase plan — assert via the pipeline harness or note it
   relies on 003's proven Phase-A-before-B (test_two_phase_resolver already proves the
   ordering generically; add a targeted assert if cheap).
3. Final full-suite gate; flip spec Status → Implemented; fill memory AS-BUILT (honest note
   on which agent-runtime SCs are steering-covered vs unit-tested). Commit (signed if
   1Password works this session, else --no-gpg-sign per user authorization).

## Risk notes

- Largest module change in the batch (3 resolver groups). Phase the build; gate each.
- `_patch_package_json` engines extension MUST be keyword-arg additive (Fact 6) — existing
  positional callers unaffected.
- ui-kit-scaffold non-idempotency is BY DESIGN (not a Tier-1 violation) — only the dep-pin
  write is byte-identical; the scaffold is excluded + safe-skipped on reproduce.
- Re-verify lang-ts line numbers at implementation (spec cites HEAD 7779c27; several
  intervening commits since — trust symbols, re-grep lines).
- Do not trust subagent test counts — re-run the full suite in the main thread per phase
  (this session already caught a parity regression a narrow -k run missed).
