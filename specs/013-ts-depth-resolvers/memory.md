# Feature 013 — TypeScript Depth Resolvers (memory)

Authored in one session based on full reads of:
`lang-ts/module.py`, `lang-ts/module.toml`, `lang-ts/steering/resolve.md`,
`lang-ts/templates/`, `runner/sdk.py:1-413`, `specs/003-stack-resolver/spec.md`,
`specs/003-stack-resolver/memory.md`, `specs/004-gates/spec.md`,
`specs/004-gates/memory.md`, `reviews/tier2-agentic-features-roadmap.md:90-125`.

## Scope decision (what 013 is)

013 = **three agent-steered answer groups added to the existing `lang-ts` module**
(no new module, no new runner machinery):

1. **Test runner resolver** — `test_runner` + `template_id` (enum); python writes
   the IN-REPO config template by id.
2. **UI kit resolver** — `ui_kit_id` + `ui_kit_init_command` (literal, allowlist-
   validated); a new hard `init_only` gate guards the non-idempotent `shadcn init`
   command; reproduce safe-skips with a `STACK-NOTES` note.
3. **Runtime / PM resolver** — `runtime` + `node_line` + finalized
   `package_manager_pin`; python validates the PM shape, writes `.node-version` and
   `engines.node` for Node runtime.

The determinism boundary is: agent DECIDES (emits frozen `agent-steered` answers);
python WRITES from frozen answers only; gates protect non-idempotent side-effects.
No new runner changes. The two-phase plan, `init_only`, `when`, `verify_pins`,
and `idempotent_write` from 003/004 cover everything.

## VERIFIED CODE FACTS (read line-by-line; do not re-derive)

### Fact 1 — `lang-ts/module.toml` inputs and steps (as-shipped)

- **Inputs**: `target` (string), `package_manager` (choice: bun|pnpm),
  `framework` (string), `ui_kit` (string). No `test_runner`, `ui_kit_id`, `runtime`,
  `node_line` declared — these are the three new groups this spec adds.
- **Steps**: `resolve` (agent) → `pins` (gate, hard, init_only, allow-stack-write)
  → `write` (python) → `run-generator` (gate, soft, no-external-generators) →
  `scaffold` (python). Source: `modules/lang-ts/module.toml:47-82`.

### Fact 2 — No `packageManager` shape validation in `_patch_package_json`

`lang-ts/module.py:93-146` (`_patch_package_json`): the `package_manager_pin` is
written to `data["packageManager"]` verbatim at line 136-138. No `re.fullmatch`
or any shape guard. A value like `"bun@latest"` or just `"bun"` would be silently
written to `package.json`. FR-013 adds the validation.

### Fact 3 — No `engines` or `.node-version` write anywhere

Neither `_do_write` nor `_do_scaffold` in `lang-ts/module.py` touches
`package.json["engines"]` or writes `.node-version` / `.nvmrc`. The write step
reads `package_manager`, `framework`, `pinned_deps`, `dev_deps`, `package_manager_pin`
from `FrozenInputs` at lines 199-203. The new `runtime` and `node_line` answers
are net-new reads. Source: `modules/lang-ts/module.py:197-397`.

### Fact 4 — No test config templates exist

`lang-ts/templates/` contains: `tsconfig.json`, `gitignore-block.txt`,
`gitignore-nuxt.txt`, `gitignore-sst.txt`, `precommit-biome.yaml`,
`precommit-prettier.yaml`. No `vitest.config.ts`, `playwright.config.ts`, or
any subdirectory. All test config template files are net-new.

### Fact 5 — `verify_pins` in `write` step already covers `all_pins`

`lang-ts/module.py:222-276`: in init mode, `all_pins = pinned_deps + dev_deps +
[package_manager_pin]`. The call `sdk.verify_pins(all_pins, "npm")` verifies the
whole batch. New depth-resolver pins (test runner deps, UI-kit deps, finalized PM
pin) join these same lists → existing verify call covers them. No new verify call.

### Fact 6 — `_patch_package_json` is callable with additive extension

`lang-ts/module.py:93-146`: the function signature is
`_patch_package_json(pkg_json_path, pinned_deps, dev_deps, package_manager_pin, warnings)`.
An optional `engines: dict | None = None` parameter can be added without breaking
existing callers (`_patch_pins_into_package_json` at line 149 calls it by position
for the first four args; must use keyword arg for `engines`).

### Fact 7 — `init_only` gate + `when` predicate are available (004 shipped)

`lang-ts/module.toml:52-62`: the `pins` gate already uses `hardness = "hard"`,
`allow_flag = "allow-stack-write"`, and `init_only = true`. The `when` predicate
is available (`module.toml` parser supports it per 004 OQ-1/OQ-2 resolution in
`manifest.py`). The `ui-kit-init` gate can use `when = "ui_kit_id != none"`.
**BUT**: 004 OQ-2 resolution says a `when` key not declared as a module input is a
parse-time `MANIFEST_MALFORMED` error. Therefore FR-021 MUST add `ui_kit_id`,
`test_runner`, and `runtime` as declared inputs before any `when` referencing them.

### Fact 8 — `sdk.append_if_absent` is available

`sdk.py` exports `append_if_absent(path, marker, block, warnings, label)` — reused
for `.gitignore` and `.pre-commit-config.yaml` blocks in the existing `write` step
(`module.py:309-386`). It is directly reusable for `STACK-NOTES.md` entries
(using the manual init command as the idempotency marker).

### Fact 9 — Two-phase plan ordering guarantee

From 003/004 AS-BUILT: Phase A runs ALL `kind=agent` steps before Phase B runs any
`kind=python` step. The runtime resolver answers (`runtime`, `node_line`,
`package_manager_pin`) are folded into `resolved_answers` in Phase A. The `scaffold`
python step runs in Phase B. Therefore the scaffolder reads the correct
`package_manager` from the frozen plan. This is a property of the shipped runner,
not an assumption.

### Fact 10 — `when` predicate coercion rule (004 OQ-1 AS-BUILT)

`when = "ui_kit_id != none"` compares both sides as rendered strings. `ui_kit_id`
would be `"none"` (the string literal default in the declared input), not Python
`None`. The predicate `"ui_kit_id != none"` is true when the agent sets the value
to anything other than the string `"none"`. This is consistent with the 004 OQ-1
resolution: both sides are coerced to string for comparison.

## OPEN QUESTIONS — require human input before implementation

### OQ-1 — Should `vitest-node+playwright` be one `template_id` or two? (MED)

**Question**: Can a user have both a unit test runner (Vitest) AND an E2E runner
(Playwright)? The spec allows `template_id = "vitest-node+playwright"` as a
composite value with two config files in the template dir. This works cleanly
technically (the write step iterates all files in the template dir). But: should
`test_runner` be a single choice or a list? A list is more expressive but makes
the `when` predicate and the steering contract slightly more complex.

**Why it needs human**: determines whether `test_runner` is a `choice` (single) or
`multichoice` (list) input declaration. A `choice` with a composite `template_id`
is simpler; a `multichoice` is more extensible for future combinations.

**Lean**: keep `test_runner` as a single choice with composite enum values
(`"vitest-node+playwright"` is a legitimate atom). The template dir for a composite
contains both config files. This avoids `multichoice` plumbing and keeps the
steering decision atomic. Extend to `multichoice` in a future spec if the
combination space grows.

### OQ-2 — `ui_kit_init_command` allowlist: should `nuxt-ui` use `nuxi module add` or its own installer? (MED)

**Question**: For Nuxt UI (`ui_kit_id = "nuxt-ui"`) the installation path is
`bunx nuxi module add @nuxt/ui` (the Nuxt module system), not a standalone `init`
command. Is this the correct canonical command for Nuxt UI v3? And should
`@nuxt/ui` v3's alpha/RC status affect whether it's in-scope for v1 of this spec?

**Why it needs human**: the `nuxt-ui` init command is a network command that modifies
`nuxt.config.ts` and potentially `package.json`. If Nuxt UI v3 is still in alpha at
implementation time, it may be wiser to scope `ui_kit_id` to `"shadcn"` only for v1
and add `"nuxt-ui"` in a follow-up once v3 is stable.

**Lean**: scope v1 to `ui_kit_id` values `["shadcn", "none"]` only; add `"nuxt-ui"`
as a follow-up when Nuxt UI v3 reaches stable. The allowlist and `ui_kit_id` enum
are designed to extend. This avoids shipping a gate for a command that may change
significantly before stable release.

### OQ-3 — Does `_do_write` gain `runtime`/`node_line` from `FrozenInputs`, or from a new step? (LOW)

**Question**: All three depth-resolver answer groups are added to the existing
`resolve` agent step. But the `write` python step is already doing pin verification,
tsconfig, package.json patches, .gitignore, and pre-commit. Adding `.node-version`
and `engines` to `_do_write` makes it larger. Would splitting `write` into `write`
(current content) + `runtime-write` (node_line + engines) be cleaner? Or is the
additional complexity small enough to keep in `_do_write`?

**Why it needs human**: purely a code organization preference. The spec says to add
to `write`; a split adds a new step but keeps each step focused.

**Lean**: keep in `_do_write` for 013. The `.node-version` write and `engines` merge
are small (2-5 lines each). Split only if the step grows unmanageable during
implementation.

### OQ-4 — What is the canonical `shadcn@latest` command for Bun vs pnpm contexts? (LOW)

**Question**: `bunx shadcn@latest init` is the canonical Bun path. For pnpm it is
`pnpm dlx shadcn@latest init`. Should the agent decide the init command per
`package_manager` (the steering doc instructs this), or should python generate the
correct command from `ui_kit_id + package_manager` (deterministic, no agent freedom)?

**Why it needs human**: if python generates the command from known inputs, the
`ui_kit_init_command` answer key is unnecessary (the command is deterministic given
`ui_kit_id + package_manager`). But the agent-decided literal gives flexibility for
flags (`--defaults`, `--yes`) the user might want. The allowlist validation covers
safety either way.

**Lean**: agent emits the literal command (with flags), python validates the prefix
against the allowlist. The flexibility for `--defaults`/`--yes` flags is worth the
small extra complexity of the allowlist. The allowlist covers both `bunx shadcn` and
`pnpm dlx shadcn` (add `pnpm dlx shadcn` to the allowlist in FR-008).

## ASSUMPTIONS

1. The 004 `when` + `init_only` machinery (manifest.py parser, `run_gate_step`
   auto-proceed, `_module_refreshed` check) is available and works for new gate
   steps on `lang-ts`. Verified: `pins` gate already uses both on `lang-ts`.
2. `sdk.append_if_absent` is sufficient for `STACK-NOTES.md` entry idempotency
   (the full init command string as the marker). If the command string could
   vary across runs (e.g. it includes a timestamp), the marker logic needs
   adjustment — but frozen commands are deterministic.
3. Template files are small enough to commit directly to `lang-ts/templates/<id>/`.
   If a template grows beyond ~100 lines it remains fine; there is no size limit in
   `idempotent_write`.
4. The `when = "ui_kit_id != none"` predicate uses the string `"none"` as the
   sentinel, consistent with the 004 OQ-1 coercion rule (both sides as strings).
   The declared `ui_kit_id` input MUST have `default = "none"` (a string, not
   empty string) to make the predicate unambiguous.
5. `_patch_package_json` can be extended with an `engines` dict parameter
   without breaking existing callers (additive keyword-arg change). Verified by
   reading the call sites at `module.py:173-189` (`_patch_pins_into_package_json`
   calls it by keyword for `package_manager_pin`).

## AS-BUILT (2026-06-29)

Shipped on `feat/project-setup-modular-redesign`. Full suite 707 passed, 4 deselected.
NO runner changes (as designed) — all module-level on `lang-ts`.

**Phase 1 (module.toml):** 6 declared inputs added (test_runner, template_id, ui_kit_id
[default "none"], ui_kit_init_command, runtime [default "bun"], node_line) so the
`when="ui_kit_id != none"` predicate parses (004 OQ-2). Two new steps appended:
`ui-kit-init` (gate, hard, allow_flag=allow-ui-kit-init, init_only, when) →
`ui-kit-scaffold` (python). Final order: resolve→pins→write→run-generator→scaffold→
ui-kit-init→ui-kit-scaffold (FR-019).

**Phase 2 (write step):** _ALLOWED_TEMPLATE_IDS frozenset; template instantiation iterates
`templates/<template_id>/` and idempotent_write(reconcile=True) each file (FR-003); unknown
id → INPUT_VALUE_INVALID (SC-009). _PM_PIN_RE shape guard rejects latest/range/bare-name
(FR-013, SC-007). PM/runtime consistency check (FR-017, SC-008). `.node-version` write-if-
absent + `engines.node` merge for runtime=node (FR-014, SC-006); none for bun (FR-015).
`_patch_package_json` + `_patch_pins_into_package_json` gained an ADDITIVE keyword
`engines: dict|None=None` (existing positional callers unaffected). 6 template files created:
vitest-node/, vitest-browser/, bun-test/, playwright-only/, vitest-node+playwright/ (2 files).

**Phase 3 (_do_ui_kit_scaffold):** _UI_KIT_ALLOWLIST = (npx shadcn, bunx shadcn, pnpm dlx
shadcn). ui_kit_id=none → no-op (SC-012); command not in allowlist → INPUT_VALUE_INVALID
(SC-010). Execute-vs-safeskip: keys off inputs.mode — mode=="init" (gate confirmed this run)
executes via sdk.run_tool; else (reproduce) SAFE-skips + writes STACK-NOTES.md via
append_if_absent (SC-005). The runner's gate_blocked latch (reproduce.py:465-477) skips the
step entirely when the hard gate is declined — so the step is only reached when allowed.

**FR-009 AMENDED (user, 2026-06-29):** original required a STACK-NOTES write in the CI
(--non-interactive) gate-blocked path. That is unachievable (runner skips the gate-blocked
python step entirely) AND unnecessary (CI workspace is ephemeral; the runner's `[SKIP]` log
line is the record; pins still land). STACK-NOTES remains on the interactive/reproduce
safe-skip path (FR-010, SC-005, tested). Gate stays HARD (Decision E preserved).

**Test coverage:** 30 lang-ts module tests. SC-001/002/006/007/008/009/010/012 + reproduce
safe-skip directly tested. SC-003 (CI STACK-NOTES) → amended away. SC-004 (confirmed gate
executes run_tool) structurally present, inspect-path tested, no live-subprocess integration
(acceptable — run_tool is the shared, separately-tested primitive). SC-011 (phase ordering)
covered by 003's proven two-phase plan (test_two_phase_resolver), not re-asserted.

**Two pre-existing test edits (verified legitimate, not weakening):** test_gate_g4_generator
step-order list updated for the 2 new Phase-1 steps; SC-006 fixture's package_manager
corrected bun→pnpm to match its own pnpm pin (the new FR-017 check exposed the fixture's
internal inconsistency).

## DETERMINISM RULES CARRIED FROM 001/002/003 (must hold)

- Tier-1: all `kind=python` writes byte-identical for same frozen answers +
  same module version. Template instantiation is byte-identical by construction
  (file content is the template content; no wall-clock or random values).
- Tier-2: agent decisions are consistent-not-identical at init; FROZEN and
  replayed byte-identically on reproduce (003 FR-009 — zero network for agent step).
- `ui-kit-scaffold` is EXPLICITLY non-idempotent (the roadmap calls this out at
  line 109: "shadcn init is NOT byte-stable even at a pinned CLI version"). It is
  NEVER replayed on reproduce; reproduce SAFE-skips it with a note. This is not
  a Tier-1 violation — the `write` step's dep-pin write IS byte-identical; only
  the `ui-kit-scaffold` step is excluded from the Tier-1 guarantee (documented
  at the gate message and in STACK-NOTES).
- Verify only at init; reproduce is zero-network.
