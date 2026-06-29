# Feature 009 — Python Web + ORM Stack Overlays (memory)

Authored as a standalone spec session from the roadmap #7 description and the
shipped code on `feat/project-setup-modular-redesign` at HEAD `7779c27`.
This file is the durable record of HOW the spec was reasoned, WHAT facts the
implementation can rely on, and WHAT needs human input. All file:line citations
are verified against shipped code; nothing is extrapolated from subagent summaries.

## Scope decision (what 009 is)

009 = **new steps added to `lang-python`** that specialize the spec-003 resolver for
the Python web tier (ASGI server, pydantic-settings) and the data tier (ORM id,
async/sync flavor, DB driver, migration-tool, structural files). Two new agent
sub-resolver steps (`py-web-resolve`, `py-orm-resolve`), one combined hard gate
(`py-web-orm-pins`), and one new python write step (`py-web-orm-write`) — all
conditional on whether the user names a web framework or an ORM intent.

**Not a new module.** The ORM and web-tier decisions are entangled with the
already-frozen `framework` and `python_version` answers that `lang-python` owns.
A separate module would require cross-module answer access (not supported by the
current runner, which is module-scoped in the frozen plan) plus a `requires` edge.
The 003 `memory.md` OQ-5 settled this: "on lang-* for 003; extract only if
package-add needs it." 009 follows that precedent. Extraction is still an option
later, but NOT the right call for 009.

## VERIFIED CODE FACTS that shape the spec

These were read directly from the shipped code (not from subagent digests).

### Fact 1 — `lang-python/module.toml` has three steps, no ORM (lines 1–52)

- `module.toml` defines: `resolve` (`kind=agent`), `pins` (`kind=gate`,
  `hardness="hard"`, `allow_flag="allow-stack-write"`, `init_only=true`), `write`
  (`kind=python`). Line 32–52.
- Two interview inputs: `python_version` (default `"3.13"`) and `framework`
  (default `""`). Lines 17–30.
- There is NO `orm_intent` input, NO ORM step, NO migration-tool step — all net-new.

### Fact 2 — `module.py` `_do_write` reads five keys; ORM is absent (lines 281–285)

- `python_version`, `framework`, `pinned_deps`, `dev_deps`, `ruff_version`.
- The cross-field validation at `module.py:496-508` checks ONLY
  `framework in ("django",)` vs `python_version` — no async/sync check, no driver
  check, no ORM check. All 009 cross-field logic is net-new.

### Fact 3 — `lang-python/steering/resolve.md` has a shallow ORM table (lines 43–49)

- The base steering doc has a 4-row table: `fastapi + postgres → asyncpg + sqlalchemy`.
  No ORM id selection, no async/sync decision logic, no Alembic decision rule,
  no ASGI server sub-choice, no pydantic-settings rule.
- 009 adds TWO new steering docs (`web-resolve.md`, `orm-resolve.md`); it does NOT
  change `resolve.md` (except possibly adding Litestar if OQ-2 is resolved in scope).

### Fact 4 — `lang-python/templates/` has three files, no ORM templates

- `ruff-config.toml`, `precommit-block.yaml`, `gitignore-block.txt`. No alembic
  templates, no models stubs. All structural file templates are net-new.
  009 adds `templates/alembic/` and `templates/orm/<orm_id>/`.

### Fact 5 — `sdk.verify_pins` is the shared verify primitive (sdk.py:315–380)

- Accepts `list[str]` of `name@version` pins, `"pypi"` ecosystem, returns
  `dict[str, PIN_VERIFIED | PIN_DISCONFIRMED | PIN_UNREACHABLE]`.
- Already called by `lang-python`'s write step at `module.py:297`.
- 009 calls it on `web_pins + orm_pins` in init mode — zero SDK changes.

### Fact 6 — `init_only` and `when` predicate are shipped machinery (spec-004)

- The `init_only` field on gate steps (auto-proceed on reproduce, suppresses
  re-prompt) is implemented per spec-004 FR-006a.
- The `when` predicate (`key`, `key == value`, `key != value`) is evaluated at
  `build_plan` time per spec-004 Settled Decisions D + OQ-1/2.
- The `{decision}` token in gate messages is rendered by `build_plan` from
  `render_answer_block(mod_answers)` per `plan.py:159-168`.
- All three are required by 009 and are already in the shipped runner — no runner
  changes needed.

### Fact 7 — `FrozenInputs` accessors handle missing keys gracefully (sdk.py:96–138)

- `get_str(key, default="")` returns `default` if `key` is absent.
- `get_list(key, default=[])` returns `[]` if `key` is absent.
- The 009 write step reads `web_pins`, `orm_pins`, `orm_id`, etc. from the frozen
  plan; these keys may be absent for non-ORM runs. Defensive defaults work correctly.

### Fact 8 — `_patch_pyproject_deps` is the dep-merge helper (module.py:117–160)

- Accepts `runtime_pins: list[str]` and `dev_pins: list[str]`, merges with
  existing `pyproject.toml`. 009 calls it with `web_pins + orm_pins` as runtime
  pins in `_do_web_orm_write`.

### Fact 9 — Template rendering in module.py uses `str.replace` (module.py:467–470)

- The existing pattern for parameterizing a template block: read file, call
  `str.replace("rev: v...", f"rev: v{ruff_version}")`. 009 uses the same pattern
  (`str.replace("{project_name}", project_name)`) — no Jinja2 or other engine.

## OPEN QUESTIONS — require human input or implementation decision

### OQ-1 — `when = "orm_intent != none"` — predicate semantics vs empty string (MED)

**The issue:** The `when` grammar (spec-004) coerces both sides to string.
`orm_intent` defaults to `""` (empty string). `"" != "none"` is TRUE — a user who
leaves `orm_intent` empty would NOT suppress the ORM sub-resolver under this predicate.

**Options:**
- (a) Change `orm_intent` default to `"none"` (the string literal), so
  `when = "orm_intent != none"` suppresses on the default. Simple; consistent
  with how the existing `framework` default `""` is treated.
- (b) Add a truthy `when = "orm_intent"` form to `eval_when` (`manifest.py`) — fires
  when the string is non-empty. Expressive; a small `manifest.py` change.
- (c) Use `when = "orm_intent != \"\""` — works with existing grammar if the
  splitter handles quoted empty strings; parsing complexity risk.

**Lean:** option (a) — set `orm_intent` default to `"none"`. No runner change,
consistent with future inputs that want a "clearly-unset" sentinel vs a truly
absent key. The prompt should say `(leave empty or type 'none' to skip)`.

**Why this needs human input:** any change to the `when` grammar (option b) touches
`manifest.py` and affects all future module authors. Human should decide whether to
extend the grammar or use the sentinel-default convention.

**Priority:** MED — blocks authoring `module.toml` for the ORM sub-resolver step.

### OQ-2 — Litestar scope: update the base `resolve.md` in 009? (MED)

**The issue:** The web steering doc (`web-resolve.md`) lists Litestar as an async
web framework with identical ASGI server and async-mode semantics to FastAPI. But
the base `resolve.md` does NOT list Litestar in its framework table. A user who
types `framework = "litestar"` gets the base resolver run but no Litestar-specific
base deps (starlette, litestar itself).

**Options:**
- (a) 009 also updates `resolve.md` to add Litestar to the base framework table.
  One PR, complete coverage. Touches a 003-era file.
- (b) 009 ships Litestar only in `web-resolve.md` (ASGI server choice) and leaves
  the base `resolve.md` unchanged. A `framework = "litestar"` run would get ASGI
  server pins from `web-resolve.md` but no `litestar` base pin from `resolve.md`.
  Inconsistent — the base resolver would not emit `litestar@<version>` in
  `pinned_deps`.
- (c) Defer Litestar entirely — FastAPI and Django only in 009.

**Lean:** option (a) — update `resolve.md` to add Litestar in the same PR. The
change is additive (one row in the framework table); it is consistent with the
spec's goal of covering the "major Python web frameworks." Touching a 003-era file
in a forward-spec is fine as long as the change is additive.

**Why this needs human input:** Expanding the scope of 009 to touch a spec-003 file
(`resolve.md`) is a deliberate cross-spec change. Human should confirm the scope.

**Priority:** MED — determines whether `resolve.md` is in the 009 diff.

### OQ-3 — Alembic `env.py`: one template or two (async/sync variants)? (LOW)

**The issue:** Alembic's `env.py` has meaningfully different content for async
engines (uses `run_sync`, `AsyncEngine`, `async_sessionmaker`) vs sync engines
(uses `connection.execute`, `Engine`). A single template would need both paths
inline (confusing for new users reading the scaffold).

**Options:**
- (a) Two templates: `templates/alembic/env_async.py.tmpl` and
  `templates/alembic/env_sync.py.tmpl`. Selected by frozen `async_mode` in the
  write step.
- (b) One template with inline `# async version` / `# sync version` comments,
  both code paths present.

**Lean:** option (a) — two clean templates. Matches Settled Decision D ("static
templates keyed on frozen ids") and avoids confusing new developers with both code
paths in the same file.

**Why this needs human input:** This is a design detail resolvable during
implementation but changes FR-024 (which currently specifies one `env.py.tmpl`).
Human should confirm the preferred approach before the implementer writes the
templates.

**Priority:** LOW — does not block the plan; the implementer can decide if the
human is unavailable.

## ASSUMPTIONS made (flagged so they can be corrected)

1. Spec-003 and spec-004 are fully implemented and green before 009 starts. 009
   introduces zero new runner machinery; it is purely a module extension.
2. The `when` predicate (spec-004 OQ-1/2) coerces both sides to string. The sentinel
   default `"none"` for `orm_intent` will correctly suppress the ORM sub-resolver
   step when the user leaves the input empty (pending OQ-1 resolution).
3. The combined `py-web-orm-pins` gate reuses the same `allow_flag = "allow-stack-
   write"` as the base `pins` gate. CI that already passes `--allow-stack-write` will
   also allow the augmented write. No new CLI flag is needed.
4. Static template rendering via `str.replace("{project_name}", project_name)` is
   sufficient. No Jinja2 or other engine is introduced (consistent with the existing
   module.py pattern at `module.py:467-470`).
5. The SQLModel–SQLAlchemy version compatibility range is documentable in the agent
   steering doc and resolvable in one research pass. The python write step does NOT
   re-resolve the pair — it only validates that both keys are present in `orm_pins`.
6. The gate message `{decision}` block (rendered from `render_answer_block`) includes
   all module answers including `orm_id`, `web_pins`, `orm_pins` since these are in
   the module's frozen answer map after Phase A. The existing `{decision}` rendering
   pipeline does not need changes for this to work.
7. The `uv add` call for runtime pins uses the same `name==version` form as the
   existing `uv add --dev` call (the `@` → `==` replacement at `module.py:431`).
   `uv add` (without `--dev`) is the correct form for runtime deps.

## DETERMINISM CONTRACT for 009

These invariants MUST hold (restated from 003, specialized for 009):

- **Agent steps (`py-web-resolve`, `py-orm-resolve`)**: DECIDE only. Emit frozen
  `agent-steered` answers with exact `name@version` pins. Never write files.
  Never emit ranges or `"latest"`.
- **Python write step (`py-web-orm-write`)**: WRITES only. Reads frozen answers via
  `FrozenInputs`. Calls `sdk.verify_pins` in init mode only. Renders structural
  files from static templates keyed on frozen `orm_id` and `async_mode`. Zero
  agent invocation, zero registry research in reproduce mode.
- **Structural files (`alembic.ini`, `migrations/env.py`, `models.py`)**: written
  with `reconcile=False` — created once, never overwritten by the runner. Reproduce
  mode creates them from static templates if absent, skips them if present.
- **Registry verification policy (init mode)**:
  - `PIN_DISCONFIRMED` → hard-error, write nothing.
  - `PIN_UNREACHABLE` → safe-skip all writes, warn, `Diff(kind="skip")`.
  - `PIN_VERIFIED` → proceed.
- **Reproduce mode**: zero network calls for both agent steps (replay from
  `answers.toml`) and zero network calls in the write step (no `verify_pins`).

## CROSS-SPEC INTERACTIONS

- **009 extends 003** (`lang-python` module steps). The 003 `resolve` → `pins` →
  `write` sequence is untouched. 009 adds AFTER `write`: `py-web-resolve` →
  `py-orm-resolve` → `py-web-orm-pins` → `py-web-orm-write`.
- **009 uses 004 machinery** (`init_only` gate, `when` predicate, `hardness`,
  `allow_flag`). No 004 runner changes — only 004 features on new step declarations.
- **007 + 008** (intermediate roadmap items, not yet specced) also extend
  `lang-python`. If they ship before 009, the 009 implementer must coordinate on
  step ordering and `module.toml` merge. The general rule: 009 steps come last
  in the module's step sequence (after the base 003 steps).

## AS-BUILT (TBD)

_Populated when implementation completes._
