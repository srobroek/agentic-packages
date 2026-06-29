# Feature Specification: Python Web + ORM Stack Overlays

**Feature Branch**: `feat/project-setup-modular-redesign` (continues)

**Created**: 2026-06-28

**Status**: **Draft (2026-06-28)**

**Input**: Roadmap rank #7 `py-web-stack-select + py-data-orm-select` from
`reviews/tier2-agentic-features-roadmap.md` — the deep Python web/persistence
specialization of the rank-#1 resolver. Extends `lang-python` (spec 003
instantiation) with a web-tier and a data-tier sub-resolver, each producing a
fully-pinned, cross-validated decision and scaffolding static structural files.

## Overview

Spec 003 built the generic Tier-2 resolver and instantiated it for `lang-python`:
the agent maps `framework` prose to a pinned dep list; the write step verifies
pins, patches `pyproject.toml`, and writes dev tooling. However, the 003
instantiation treats the web tier shallowly — it knows `fastapi -> uvicorn +
asyncpg` from a table in the steering doc, but it emits no ASGI server pin, no
`pydantic-settings` pin, no ORM decision, no migration scaffolding, and no
structural files (`alembic.ini`, `migrations/env.py`, models stub). A "FastAPI +
Postgres + SQLModel" project that runs 003 gets `pyproject.toml` pins but nothing
else — no project layout the ORM requires, no Alembic wiring, no driver cross-check.

This spec adds two specialization steps to `lang-python` that fire only when the
chosen framework is a known web tier framework or the user mentions an ORM/DB in
prose:

> **Web sub-resolver** (`py-web-resolve`, agent step) — decides ASGI server,
> `pydantic-settings`, and any web-tier companion pins cross-checked against the
> already-frozen base stack (FR-001 … FR-006).
>
> **ORM sub-resolver** (`py-orm-resolve`, agent step) — decides ORM id
> (SQLModel / SQLAlchemy / Django ORM / none), async-vs-sync flavor, DB driver
> matched to the DB named in prose (asyncpg for async-Postgres, psycopg2 for
> sync-Postgres, aiomysql / mysqlclient for MySQL, aiosqlite / sqlite3-bundled
> for SQLite), migration-tool presence (alembic only when a non-Django ORM is
> chosen), and all exact pins — in one coherent research pass (FR-007 … FR-014).

The decisions from both sub-resolvers are gated at a single combined gate
(`py-web-orm-pins`, a hard gate with `init_only`) that shows the complete
augmented pin table plus the new structural-file scaffold list before any write
(FR-015 … FR-017). A `py-web-orm-write` python step then reads ALL frozen answers
(the base `lang-python` answers + the sub-resolver answers), re-validates the
cross-field constraints (driver-vs-DB, async-vs-sync coherence,
`requires_python`-vs-`python_version`), writes the additional pins into
`pyproject.toml`, and scaffolds the static structural files from templates keyed on
the frozen ids (FR-018 … FR-025).

**Module shape decision:** 009 adds NEW STEPS to `lang-python`, NOT a new
independent module. Lean and rationale: the ORM decision is entangled with the
`framework` and `python_version` already frozen by `lang-python`; splitting them
into a separate module would require cross-module answer access (not supported by
the current runner — answers are module-scoped in the frozen plan), an additional
`requires` edge, and namespace plumbing. The 003 `memory.md` OQ-5 resolved to "on
lang-* for 003; extract to a shared module only if package-add needs it." That
precedent holds here: web/ORM specialization is `lang-python`-specific logic, not
a generic resolver the TS or Go overlays need. The new steps are activated by a
`when = "framework != none"` predicate on the web resolver and a `when`-or-input
predicate on the ORM resolver, so a plain Python project with no web framework sees
no new prompts and no new files.

## Current state (verified — citations, do not re-derive)

All file:line references verified against shipped code on
`feat/project-setup-modular-redesign` at HEAD `7779c27`.

- **`lang-python/module.toml` defines three steps** (`resolve`, `pins`, `write`)
  and two interview inputs (`python_version`, `framework`). Lines 1–52. The
  `framework` input has `required = false` and `default = ""`.
- **`lang-python/module.py` `_do_write` reads five keys from the frozen plan**
  (`python_version`, `framework`, `pinned_deps`, `dev_deps`, `ruff_version`) and
  acts on them at `module.py:281-285`. The ORM, ASGI server, DB driver, and
  migration-tool decisions are **not present anywhere** in `module.py` or
  `module.toml`. The cross-field validation at `module.py:496-508` checks only
  `framework in ("django",)` vs `python_version` — a one-row table, no async/sync
  check, no driver check.
- **`lang-python/steering/resolve.md` has a shallow table** mapping framework
  intent to deps (lines 43–49): `fastapi + postgres -> asyncpg + sqlalchemy`.
  There is no ORM id selection, no async-vs-sync branching, no migration-tool
  decision, no ASGI server sub-choice (uvicorn vs hypercorn vs granian), no
  `pydantic-settings` rule.
- **`lang-python/templates/` contains three files** (`ruff-config.toml`,
  `precommit-block.yaml`, `gitignore-block.txt`). There are NO Alembic templates,
  NO models stub templates, and NO `alembic.ini` template in this directory today.
  All structural ORM files would be net-new static templates.
- **`sdk.verify_pins`** (`runner/sdk.py:315-380`) is the shared PyPI/npm
  verification primitive. It accepts any `list[str]` of `name@version` pins and
  returns a `dict[str, str]` with `PIN_VERIFIED` / `PIN_DISCONFIRMED` /
  `PIN_UNREACHABLE` per pin. It is already used by `lang-python`'s write step at
  `module.py:297`. The spec-009 write step reuses the identical call.
- **The `init_only` gate marker** (`module.toml:43-49`, on the `pins` step) exists
  in the shipped `lang-python` module: a hard gate (`hardness = "hard"`,
  `allow_flag = "allow-stack-write"`, `init_only = true`) on the existing `pins`
  step. The new combined `py-web-orm-pins` gate in spec-009 MUST carry the same
  `hardness`, `allow_flag`, and `init_only` values per spec-004 FR-006a — reusing
  the same gate enrichment machinery, no new runner work required.
- **The `when` predicate** (`manifest.py`, as implemented by spec-004) evaluates
  `key`, `key == value`, `key != value` against the module's frozen answers at
  `build_plan` time (`memory.md` spec-004 OQ-1/2 resolved). The new sub-resolver
  steps can use `when = "framework != none"` and `when = "orm_id != none"` to
  suppress themselves for plain Python projects — no new runner machinery.
- **The `FrozenInputs` accessor** (`sdk.py:65-138`) reads any key from the frozen
  plan via `get_str`, `get_list`, `get_bool`, `get_choice`. The write step can
  consume new keys (`orm_id`, `db_driver`, `asgi_server`, `migration_tool`,
  `orm_pins`, `web_pins`) using the same typed accessors — no SDK changes.

## Settled decisions

These are binding for this spec.

- **A — New steps on `lang-python`, not a new module.** The ORM and web-tier
  decisions are too entangled with the already-frozen `framework` and
  `python_version` to live in a separate module without cross-module answer access.
  A new module would require a `requires = ["lang-python"]` edge + answer-namespace
  bridging, which the runner does not support today. New steps on `lang-python` are
  the correct mechanical expression of "spec 003 resolution extended." If `package-
  add` later needs ORM resolution, a shared helper in the SDK (or a shared steering
  doc) is the extraction point — not a new module in 009.
- **B — Both sub-resolvers (web and ORM) share ONE combined gate and ONE combined
  write step.** Separating them into four steps (web-resolve, web-gate, orm-resolve,
  orm-gate, web-write, orm-write) violates the anti-fatigue rule (spec-004 Settled
  Decision F): a user picking FastAPI + SQLModel + Postgres would see two hard gates
  in the same blast-radius class. The combined gate (`py-web-orm-pins`) surfaces the
  full augmented pin table in one confirm; the combined write step applies all new
  pins and templates in one python step.
- **C — `when` predicate suppresses both agent steps for non-web projects.** The
  web sub-resolver carries `when = "framework != none"` and the ORM sub-resolver
  carries `when = "orm_intent != none"` (where `orm_intent` is a new optional
  interview input). A plain Python project (`framework = ""`) skips BOTH sub-resolvers
  and the combined gate entirely — no new prompts, no new files. The `lang-python`
  module stays a clean single-resolver module for basic Python projects.
- **D — Static templates keyed on frozen ids; the agent never emits raw config.**
  The roadmap principle is binding: "Agents pick among CURATED templates by id; they
  never emit raw config text." The ORM sub-resolver emits `orm_id` (e.g.
  `"sqlmodel"`, `"sqlalchemy-async"`, `"django-orm"`, `"none"`) and the python step
  instantiates the corresponding template from `lang-python/templates/orm/<orm_id>/`.
  The same applies to Alembic (`templates/alembic/`) and the models stub
  (`templates/models_stub/`). The agent MUST NOT emit `alembic.ini` content inline.
- **E — Cross-field validation is python's job, not the agent's final word.**
  Following spec-003 FR-003 and the roadmap "cross-module coherence constraints
  are validated deterministically in python": the python write step re-validates
  the frozen decision against ALL frozen answers (driver-vs-DB, async-vs-sync,
  `requires_python`-vs-`python_version`) and HARD-ERRORS rather than silently
  writing an incoherent stack. The agent is trusted for research quality; python is
  trusted for constraint correctness. The agent's validation reasoning goes in
  `rationale`; the python step enforces the same rules structurally.
- **F — `sdk.verify_pins` is reused without changes.** The existing `verify_pins`
  primitive (spec-003 FR-007, `sdk.py:315-380`) verifies PyPI pins. The 009 write
  step calls it on the combined augmented pin list (base `pinned_deps` + `web_pins`
  + `orm_pins`) once in init mode. No new verification primitive is needed; no SDK
  changes are in scope.
- **G — Alembic is scaffolded only when a non-Django ORM is chosen.** Django ships
  its own migration system; adding Alembic to a Django project would create a
  conflict. The ORM sub-resolver MUST set `migration_tool = "alembic"` only when
  `orm_id` is `"sqlmodel"` or `"sqlalchemy-async"` or `"sqlalchemy-sync"`. Django
  projects get `migration_tool = "django"` (a label only, no scaffolding). Projects
  with `orm_id = "none"` get `migration_tool = "none"`. The python write step
  hard-errors if `migration_tool == "alembic"` AND `orm_id` starts with `"django"`.
- **H — The combined gate is `init_only` and hard.** Identical hardness posture to
  the existing `pins` gate on `lang-python` (`module.toml:43-49`): `hardness =
  "hard"`, `allow_flag = "allow-stack-write"` (reuses the same flag — the web+ORM
  pin write is the same blast-radius class as the base stack write), `init_only =
  true`. On plain reproduce the gate auto-proceeds (FR-006a, spec-004); only
  `--refresh lang-python` re-arms it. The structural files (alembic.ini,
  migrations/env.py, models stub) are written with `reconcile = false` on first
  init and skipped on reproduce if already present — they are intended to be
  hand-edited, not overwritten.
- **I — Structural files are write-once (`reconcile=false`).** `alembic.ini`,
  `migrations/env.py`, `migrations/__init__.py`, and `src/<pkg>/models.py` are
  scaffolded with `sdk.idempotent_write(..., reconcile=False)` — they are created on
  first init and skipped on re-run if they already exist. The intent is that
  developers hand-edit them; the runner must never clobber hand-edits on reproduce.
  If the user wants a fresh scaffold, they delete the files and re-run.
- **J — A new optional interview input `orm_intent` is added to `lang-python`.** The
  ORM sub-resolver needs a user signal ("postgres with SQLModel", "sqlite, no ORM",
  "no database") that is distinct from `framework`. Rather than jamming ORM intent
  into the `framework` string (which the base resolver already reads), a new
  optional `orm_intent` input is added: `type = "string"`, `required = false`,
  `default = ""`, `prompt = "Database / ORM intent? (e.g. 'postgres with
  SQLModel', 'sqlite no ORM', 'mysql sqlalchemy', or leave empty to skip)"`. The
  `when = "orm_intent != none"` on the ORM sub-resolver checks this key.

## User Scenarios & Testing

### User Story 1 — FastAPI + Postgres + SQLModel (Priority: P1)

A user runs `lang-python` enabled with `framework = "fastapi"` and
`orm_intent = "postgres with SQLModel"`. The agent sub-resolvers pick uvicorn,
pydantic-settings, SQLModel, asyncpg (async Postgres driver), and alembic; every
pin is registry-verified; the user confirms the full augmented pin table at one
gate; the write step produces `pyproject.toml` with all pins, `alembic.ini`,
`migrations/env.py`, `migrations/__init__.py`, and `src/<pkg>/models.py`.

**Acceptance Scenarios**:

1. **Given** `framework = "fastapi"` and `orm_intent = "postgres with SQLModel"`,
   **When** the web sub-resolver runs, **Then** it emits `asgi_server = "uvicorn"`,
   `web_pins = ["uvicorn@<exact>", "pydantic-settings@<exact>"]` with
   `source = "agent-steered"`.
2. **Given** the same inputs, **When** the ORM sub-resolver runs, **Then** it emits
   `orm_id = "sqlmodel"`, `async_mode = "async"`, `db_driver = "asyncpg"`,
   `migration_tool = "alembic"`, `orm_pins = ["sqlmodel@<exact>", "sqlalchemy@<exact>",
   "asyncpg@<exact>", "alembic@<exact>"]` with exact versions, all `agent-steered`.
3. **Given** verified pins, **When** the combined gate fires, **Then** it shows
   the full augmented pin table (`web_pins` + `orm_pins` merged with the base
   `pinned_deps`) AND the structural-file scaffold list before any write.
4. **Given** the gate confirmed, **When** the write step runs, **Then**:
   `pyproject.toml` contains all pins (runtime and dev, merged); `alembic.ini`
   is created; `migrations/env.py` and `migrations/__init__.py` are created;
   `src/<pkg>/models.py` is created from the sqlmodel stub template.
5. **Given** all pins, **When** verification runs (init mode), **Then** every pin
   is `PIN_VERIFIED`; an injected hallucinated/yanked pin is rejected with
   `INPUT_VALUE_INVALID` before any write.

### User Story 2 — Async FastAPI + asyncpg, NOT psycopg2 (Priority: P1)

The resolver MUST cross-check async framework + async driver. An async framework
(`fastapi`, `litestar`) MUST get `asyncpg` for Postgres, NOT `psycopg2`.

**Acceptance Scenarios**:

1. **Given** `framework = "fastapi"` and `orm_intent = "postgres"`, **When** the
   ORM sub-resolver emits a decision, **Then** `db_driver = "asyncpg"` (not
   `"psycopg2"`), `async_mode = "async"`.
2. **Given** a frozen decision with `async_mode = "async"` and
   `db_driver = "psycopg2"`, **When** the python write step cross-validates,
   **Then** it HARD-ERRORS with a clear message (`async framework requires async
   driver`) and writes nothing.
3. **Given** `framework = "django"` (sync by default) and `orm_intent = "postgres"`,
   **When** the ORM sub-resolver runs, **Then** `db_driver = "psycopg2"` (or
   `psycopg` v3 sync), `async_mode = "sync"`.

### User Story 3 — Django ORM (no Alembic) (Priority: P1)

A user picks Django. Django ships its own migration system. No Alembic is scaffolded.

**Acceptance Scenarios**:

1. **Given** `framework = "django"`, **When** the ORM sub-resolver runs, **Then**
   `orm_id = "django-orm"`, `migration_tool = "django"`, no Alembic pin in
   `orm_pins`, no `alembic.ini` written.
2. **Given** a frozen decision with `migration_tool == "alembic"` and
   `orm_id` starting with `"django"`, **When** the python write step validates,
   **Then** it HARD-ERRORS (`alembic conflicts with Django ORM migration system`).

### User Story 4 — No ORM, plain FastAPI (Priority: P2)

A user sets `orm_intent = ""` (empty). The ORM sub-resolver is `when`-dropped.
No ORM pins, no migration files, no models stub.

**Acceptance Scenarios**:

1. **Given** `framework = "fastapi"` and `orm_intent = ""`, **When** the plan
   is built, **Then** the ORM sub-resolver step is dropped (the `when` predicate
   is false), no `orm_pins` key exists in the frozen plan.
2. **Given** no ORM sub-resolver, **When** the write step runs, **Then** only the
   web-tier augmentation is applied (ASGI server + pydantic-settings pins); no
   Alembic files are written.

### User Story 5 — Plain Python project (no web framework, no ORM) (Priority: P1)

A user sets `framework = ""`. Both sub-resolvers are `when`-dropped. The
`lang-python` module behaves exactly as it did in spec-003 — no regressions.

**Acceptance Scenarios**:

1. **Given** `framework = ""` and `orm_intent = ""`, **When** the plan is built,
   **Then** BOTH the web sub-resolver step and the ORM sub-resolver step are
   dropped from the frozen plan.
2. **Given** no sub-resolvers, **When** the run completes, **Then** the output
   is byte-identical to a spec-003 run with the same inputs — zero regression.

### User Story 6 — Reproduce is zero-network (Priority: P1)

A teammate clones and reproduces. All `agent-steered` decisions replay from
`answers.toml`; the new structural files either already exist (skip) or are created
from frozen ids via static templates — zero network, byte-identical.

**Acceptance Scenarios**:

1. **Given** committed `agent-steered` answers, **When** the runner reproduces,
   **Then** BOTH agent sub-resolver steps replay with zero network calls.
2. **Given** structural files that already exist (hand-edited), **When** the write
   step runs in reproduce mode, **Then** they are SKIPPED (`reconcile=False`).
3. **Given** structural files that do NOT exist (fresh clone), **When** the write
   step runs in reproduce mode, **Then** they are created from the static templates
   keyed on the frozen `orm_id` — byte-identical to the first init output.

### User Story 7 — `requires_python` constraint hard-error (Priority: P1)

A frozen `python_version = "3.9"` is inconsistent with SQLModel which requires
Python >= 3.10. The python write step MUST hard-error, not silently write.

**Acceptance Scenarios**:

1. **Given** `python_version = "3.9"` and `orm_id = "sqlmodel"`, **When** the write
   step cross-validates, **Then** it HARD-ERRORS with
   `ERROR: SQLModel requires Python >=3.10; frozen python_version=3.9`.
2. **Given** `python_version = "3.9"` and `orm_id = "none"`, **When** the write
   step runs, **Then** no `requires_python` error fires — the check is
   ORM-id-specific.

### Edge Cases

- **Agent proposes `psycopg2` for async FastAPI**: python write step catches the
  async/sync mismatch and hard-errors; no file is written.
- **Agent proposes `alembic` for Django**: python write step catches the migration
  conflict and hard-errors.
- **`orm_intent` names a DB the agent cannot match a driver for**: agent sets
  `db_driver = "unknown"` and includes a rationale note; the python step emits a
  warning (not a hard error) and skips the driver pin; the gate message shows the
  unresolved slot.
- **Hallucinated ORM version (e.g. sqlmodel@99.0.0)**: `verify_pins` returns
  `PIN_DISCONFIRMED`; the write step hard-errors and writes nothing.
- **Registry unreachable at init for one ORM pin**: the write step safe-skips the
  entire write (consistent with spec-003 FR-012), warns about the unreachable pin,
  and emits a `Diff(kind="skip")` for all new files.
- **Structural files already exist at init** (user ran `alembic init migrations`
  manually): `idempotent_write(reconcile=False)` skips them; a `Diff(kind="skip")`
  is emitted per file; no overwrite.
- **`--non-interactive` at init**: the combined gate (`init_only`, `hardness=hard`,
  `allow_flag=allow-stack-write`) SAFE-skips the write without `--allow-stack-write`;
  `--allow-stack-write` performs it. Same behavior as the base `pins` gate.
- **SQLModel `<->` SQLAlchemy version mismatch**: SQLModel has a strict
  SQLAlchemy version range; the agent must research the exact compatible pair in
  one pass (`orm_pins` must satisfy it). The python write step does NOT try to
  re-resolve the version relationship — it validates that both `sqlalchemy` and
  `sqlmodel` appear in `orm_pins` and that their versions satisfy the publicly
  documented compatibility range. A mismatch surfaces as a warning, not a
  hard-error (the agent is responsible for resolving the pair correctly; the python
  step checks it was provided).

## Requirements

### Web sub-resolver (agent step)

- **FR-001**: `lang-python/module.toml` MUST add a `py-web-resolve` step with
  `kind = "agent"`, `steering = "steering/web-resolve.md"`, and
  `when = "framework != none"`. The step MUST be ordered AFTER the base `resolve`
  step (which provides the frozen `framework` answer) and BEFORE the combined gate.
- **FR-002**: The `py-web-resolve` agent step MUST emit at minimum:
  `asgi_server` (e.g. `"uvicorn"`, `"hypercorn"`, `"granian"`, `"none"`) and
  `web_pins` (list of `name@exact-version` pins for the ASGI server and
  `pydantic-settings`) as `agent-steered` answers. It MUST NOT write any files.
  It MUST NOT re-decide `framework` or `pinned_deps` (those belong to `resolve`).
- **FR-003**: The web steering doc (`steering/web-resolve.md`) MUST specify the
  decision table for ASGI server by framework: FastAPI/Litestar → uvicorn (default),
  with an override path to hypercorn or granian; Django → daphne (for ASGI) or none
  (for WSGI). It MUST also specify when `pydantic-settings` is added (FastAPI/Litestar
  only; Django has its own settings system). The doc MUST apply the MCP-check pattern
  from the base `resolve.md` (check context7 / package-version first; proceed without
  if absent).
- **FR-004**: The `py-web-resolve` step MUST carry `init_only = true` to suppress
  re-prompting on plain reproduce (consistent with the base `resolve` step's behavior
  and spec-004 FR-006a / Settled Decision H here).
- **FR-005**: In reproduce mode the `py-web-resolve` step MUST replay the committed
  `agent-steered` answers from `answers.toml` with zero network calls (spec-003
  FR-009 applies to all `kind=agent` steps, including these).
- **FR-006**: On `--refresh lang-python`, the `py-web-resolve` step MUST re-invoke
  the agent, verify new pins, present an old-vs-new diff gate, and only on confirm
  update the frozen answers (spec-003 FR-010 applies).

### ORM sub-resolver (agent step)

- **FR-007**: `lang-python/module.toml` MUST add a new optional interview input
  `orm_intent` (`type = "string"`, `required = false`, `default = ""`). Its prompt
  MUST clearly state that leaving it empty skips all ORM/migration scaffolding.
- **FR-008**: `lang-python/module.toml` MUST add a `py-orm-resolve` step with
  `kind = "agent"`, `steering = "steering/orm-resolve.md"`, and
  `when = "orm_intent != none"`. It MUST be ordered AFTER `py-web-resolve` and
  BEFORE the combined gate.
- **FR-009**: The `py-orm-resolve` agent step MUST emit as `agent-steered` answers:
  - `orm_id`: one of `"sqlmodel"`, `"sqlalchemy-async"`, `"sqlalchemy-sync"`,
    `"django-orm"`, `"none"`.
  - `async_mode`: `"async"` or `"sync"`.
  - `db_driver`: the exact PyPI package name for the chosen DB driver (e.g.
    `"asyncpg"`, `"psycopg2-binary"`, `"psycopg"`, `"aiomysql"`, `"mysqlclient"`,
    `"aiosqlite"`, `"none"`).
  - `migration_tool`: `"alembic"`, `"django"`, or `"none"`.
  - `orm_pins`: list of `name@exact-version` pins for ALL ORM-tier packages
    (ORM lib, SQLAlchemy if applicable, DB driver, Alembic if applicable).
  - `orm_rationale`: a 2–4 sentence explanation of the choices.
  It MUST NOT write any files.
- **FR-010**: The ORM steering doc (`steering/orm-resolve.md`) MUST specify the
  full decision matrix:
  - async framework (FastAPI, Litestar) → `async_mode = "async"` → asyncpg for
    Postgres, aiosqlite for SQLite, aiomysql for MySQL, aioodbc for MSSQL.
  - sync framework (Django, Flask) or `async_mode = "sync"` → psycopg2-binary /
    psycopg (v3 sync) for Postgres, mysqlclient for MySQL, sqlite3 (bundled) for
    SQLite.
  - Django → `orm_id = "django-orm"`, `migration_tool = "django"`, no Alembic.
  - SQLModel → always emit BOTH `sqlmodel` AND the compatible `sqlalchemy` version
    in `orm_pins` (SQLModel's version range constraint on SQLAlchemy MUST be
    satisfied in the same research pass).
  - No ORM → `orm_id = "none"`, `orm_pins = []`, `migration_tool = "none"`.
- **FR-011**: The ORM steering doc MUST instruct the agent that `async_mode` MUST
  be consistent with the already-frozen `framework` answer (available in the agent's
  context dict at step invocation time). The async/sync relationship is a research
  constraint, not a free choice.
- **FR-012**: The `py-orm-resolve` step MUST carry `init_only = true` (same
  rationale as FR-004).
- **FR-013**: In reproduce mode the `py-orm-resolve` step MUST replay committed
  `agent-steered` answers with zero network (spec-003 FR-009).
- **FR-014**: On `--refresh lang-python`, the `py-orm-resolve` step MUST re-invoke,
  verify, and diff-gate the same as FR-006 (spec-003 FR-010).

### Combined gate

- **FR-015**: `lang-python/module.toml` MUST add a `py-web-orm-pins` step with
  `kind = "gate"`, `hardness = "hard"`, `allow_flag = "allow-stack-write"`,
  `init_only = true`, and a `when` predicate that fires ONLY when at least one
  sub-resolver produced pins (i.e. `when = "framework != none"` is sufficient —
  if both sub-resolvers were dropped, no pins were produced). The gate MUST be
  ordered AFTER both sub-resolver steps and BEFORE `py-web-orm-write`.
- **FR-016**: The gate message MUST use the `{decision}` token (rendered by
  `build_plan` from the module's frozen answers at freeze time, per spec-003
  SUBTLETY 1 + spec-004 Fact 3 / `plan.py:159-168`). The rendered block MUST
  show: the augmented pin table (all `web_pins` + `orm_pins` merged with base
  `pinned_deps`, one pin per line with `✓`/`✗` verify status), the async/sync
  flavor, the migration tool decision, and the list of structural files that will
  be created (`alembic.ini`, `migrations/env.py`, etc.) or `(none)`.
- **FR-017**: In `--non-interactive` the gate MUST SAFE-skip the write without
  `--allow-stack-write` (hard gate CI policy, spec-004 FR-003). With
  `--allow-stack-write` the write proceeds. On plain reproduce (init_only) the gate
  MUST auto-proceed without prompting (spec-004 FR-006a).

### Write step (`py-web-orm-write`)

- **FR-018**: `lang-python/module.toml` MUST add a `py-web-orm-write` step with
  `kind = "python"` ordered AFTER `py-web-orm-pins`. It MUST be the last step in
  the module.
- **FR-019**: `module.py` MUST add a `_do_web_orm_write` handler. It MUST read the
  following frozen keys via `FrozenInputs` accessors (no raw plan dict access):
  `python_version`, `framework`, `pinned_deps`, `web_pins`, `orm_id`, `async_mode`,
  `db_driver`, `migration_tool`, `orm_pins`. Missing optional keys (empty list for
  `web_pins`/`orm_pins`, `"none"` for `orm_id`/`migration_tool`) MUST default
  gracefully rather than hard-error.
- **FR-020**: In `init` mode the write step MUST call `sdk.verify_pins` on the
  combined augmented pin list (`web_pins + orm_pins`) before any write. A
  `PIN_DISCONFIRMED` result MUST hard-error (status `"error"`,
  `INPUT_VALUE_INVALID`, writes nothing). A `PIN_UNREACHABLE` result MUST
  safe-skip all writes with a warning (status `"ok"`, `Diff(kind="skip")` per
  file). In `reproduce` mode the step MUST NOT call `verify_pins` (zero network,
  spec-003 FR-009).
- **FR-021**: The write step MUST re-validate the following cross-field constraints
  and HARD-ERROR on any violation (not a warning):
  - `async_mode == "async"` AND `db_driver` is a known sync-only driver
    (`"psycopg2-binary"`, `"psycopg2"`, `"mysqlclient"`, `"sqlite3"`) →
    ERROR: `async framework requires async DB driver`.
  - `migration_tool == "alembic"` AND `orm_id` starts with `"django"` →
    ERROR: `alembic conflicts with Django ORM; use Django migrations`.
  - `orm_id == "sqlmodel"` AND `"sqlalchemy"` not in any `orm_pins` entry →
    ERROR: `SQLModel requires SQLAlchemy pin; add sqlalchemy@<version> to orm_pins`.
  - `orm_id in ("sqlmodel",)` AND `python_version < "3.10"` →
    ERROR: `SQLModel requires Python >=3.10; frozen python_version=<x>`.
- **FR-022**: The write step MUST merge `web_pins + orm_pins` into `pyproject.toml`
  using the existing `_patch_pyproject_deps` helper (`module.py:117-160`).
  `web_pins` and `orm_pins` are runtime deps (not dev). After patching, the step
  MUST run `uv add` with the exact augmented pin list (same pattern as the base
  write step's `uv add --dev` at `module.py:427-434`, but for runtime pins with
  `uv add` not `uv add --dev`).
- **FR-023**: The write step MUST scaffold structural files using
  `sdk.idempotent_write(..., reconcile=False)` for each applicable file:
  - `migration_tool == "alembic"`: create `alembic.ini` (from
    `templates/alembic/alembic.ini.tmpl`), `migrations/__init__.py` (empty),
    `migrations/env.py` (from `templates/alembic/env.py.tmpl`, with
    `target_metadata` placeholder referencing the models module).
  - `orm_id != "none"` AND `orm_id != "django-orm"`: create
    `src/<project_name>/models.py` (from `templates/orm/<orm_id>/models.py.tmpl`).
  - `orm_id == "django-orm"`: no extra files (Django's own `startapp` owns the
    models layout).
  - All writes use `reconcile=False` — if the file already exists it is skipped
    with `Diff(kind="skip")`.
- **FR-024**: The templates in `lang-python/templates/` MUST be extended:
  - `templates/alembic/alembic.ini.tmpl` — a minimal `alembic.ini` with a
    `script_location = migrations` line and `%(here)s` database URL placeholder.
  - `templates/alembic/env.py.tmpl` — a standard async-capable `migrations/env.py`
    with `target_metadata` referencing `src.<pkg>.models.Base`.
  - `templates/orm/sqlmodel/models.py.tmpl` — a stub SQLModel file with a sample
    `SQLModel` table class and `create_engine`/`async_engine` import stubs.
  - `templates/orm/sqlalchemy-async/models.py.tmpl` — a stub SQLAlchemy async file
    with `DeclarativeBase`, `async_sessionmaker`, and `create_async_engine` imports.
  - `templates/orm/sqlalchemy-sync/models.py.tmpl` — a stub SQLAlchemy sync file
    with `DeclarativeBase` and `create_engine` imports.
  All template files MUST be static text (no Python-side template rendering engine
  — use a single `{project_name}` substitution via `str.replace()` in the write
  step, consistent with the existing `pc_block.replace("rev: ...", ...)` pattern at
  `module.py:467`).
- **FR-025**: The write step MUST emit a `ModuleResult` with `files_written` listing
  every file it touched (created or modified), `diffs` with a `Diff` per file, and
  `warnings` for any non-fatal issues (unknown `db_driver`, skipped structural files,
  `uv add` failure).

### Non-regression / compatibility

- **FR-026**: A `lang-python` run with `framework = ""` and `orm_intent = ""`
  MUST produce output byte-identical to a spec-003 run with the same inputs. The
  new steps are `when`-dropped; the existing `resolve` → `pins` → `write` sequence
  is unchanged.
- **FR-027**: All existing `lang-python` tests (`test_lang_python*.py`) MUST stay
  green without modification. The new steps are conditional; a test that does not
  set `framework` or `orm_intent` must not see the new steps in the frozen plan.

## Success Criteria

- **SC-001**: An agent-resolved `fastapi + postgres + sqlmodel` run writes
  `pyproject.toml` with `sqlmodel`, `sqlalchemy`, `asyncpg`, `uvicorn`,
  `pydantic-settings`, and `alembic` pins ALL `PIN_VERIFIED`; an injected
  hallucinated pin is rejected before any write (tested with a stubbed registry).
- **SC-002**: The python write step HARD-ERRORS when `async_mode = "async"` and
  `db_driver = "psycopg2"` (async/sync mismatch), writes nothing (unit test with
  a crafted frozen plan).
- **SC-003**: The python write step HARD-ERRORS when `migration_tool = "alembic"`
  and `orm_id = "django-orm"` (Alembic+Django conflict), writes nothing.
- **SC-004**: A reproduce run of a committed `sqlmodel + asyncpg + alembic` stack
  replays BOTH agent sub-resolver steps with zero network calls and produces
  byte-identical `pyproject.toml` + structural files (the structural files are
  skipped as `reconcile=False` if they exist, or created identically if absent).
- **SC-005**: A `lang-python` run with `framework = ""` and `orm_intent = ""` is
  byte-identical to a spec-003 run (zero regressions; the new steps are absent from
  the frozen plan; all pre-009 tests stay green).
- **SC-006**: `--non-interactive` at init safe-skips the combined write without
  `--allow-stack-write`; `--non-interactive --allow-stack-write` performs the full
  write including structural files.
- **SC-007**: The SQLModel + Python 3.9 constraint check hard-errors at the write
  step with a clear `requires Python >=3.10` message.
- **SC-008**: `alembic.ini`, `migrations/env.py`, and `src/<pkg>/models.py` are
  created on first init and SKIPPED (not overwritten) on reproduce when already
  present.
- **SC-009**: A Django run emits NO `alembic` pin and creates NO `alembic.ini` /
  `migrations/env.py`; `migration_tool = "django"` is the only migration annotation
  (test with a crafted frozen plan).
- **SC-010**: All `lang-python` pre-009 tests pass without modification (the
  full suite that shipped with spec-003/004 stays green).

## Out of Scope

- TypeScript ORM resolution (Prisma, Drizzle, TypeORM) — spec roadmap #11 covers
  TS depth resolvers. 009 is Python only.
- Flask ORM integration — Flask is a minimal framework that leaves ORM fully to the
  developer. If `framework = "flask"` and `orm_intent` is set, the ORM sub-resolver
  runs and produces standalone SQLAlchemy/SQLModel pins + Alembic, but there is no
  Flask-specific scaffolding beyond the base. No Flask-specific templates.
- `extra-index-url` or custom PyPI index resolution (the roadmap ML/CUDA case) —
  that supply-chain concern is a separate feature requiring an allowlist gate. 009
  uses only the official PyPI index.
- A Tier-2 DB-host provisioning or connection-string decision — the `alembic.ini`
  and `env.py` use a `%(here)s` placeholder URL. Actual DB credentials are out of
  scope (G8 in spec-004 guards against persisting them).
- Changing the base `lang-python` `resolve` → `pins` → `write` sequence or the
  existing write step logic — 009 adds AFTER the existing write step without
  touching it.
- Go, Rust, or TypeScript ORM overlays.
- Non-relational DB drivers (MongoDB `motor`, Redis `aioredis`, Cassandra) — the
  driver matrix in FR-010 covers relational DBs only; non-relational is a scope
  extension for a later spec.
- `--refresh lang-python.orm_id` key-level refresh granularity — 009 inherits the
  module-level `--refresh lang-python` from spec-003. Per-key refresh is a later
  runner enhancement.
- Upgrading the `lang-python` interview prompts or the base resolver steering doc
  — 009 adds new inputs and new steps but does NOT change the existing `framework`
  prompt or `resolve.md`.

## Assumptions

- Spec-003 and spec-004 are implemented and green (the `init_only` gate marker,
  the `when` predicate, `sdk.verify_pins`, and the two-phase plan are all shipped).
  009 is a pure extension of 003 on top of 004 — it introduces zero new runner
  machinery.
- `FrozenInputs.get_list` and `FrozenInputs.get_str` correctly handle missing
  optional keys by returning the `default` argument (verified: `sdk.py:114-121`
  and `96-101`).
- The `{decision}` token in a gate `message` is rendered from `render_answer_block`
  which includes all module answers. The augmented answers (`web_pins`, `orm_pins`,
  `orm_id`, `migration_tool`) are in the module's frozen answer map by freeze time
  (Phase A complete before freeze), so they appear in the rendered block.
- Static template rendering using `str.replace()` is sufficient for the one
  variable slot (`project_name`) in all structural file templates — no Jinja2 or
  other template engine is needed.
- PyPI package names for the covered driver/ORM ecosystem are stable and verifiable
  at `pypi.org/pypi/<pkg>/json` (asyncpg, psycopg2-binary, psycopg, aiomysql,
  mysqlclient, aiosqlite, sqlmodel, sqlalchemy, alembic, pydantic-settings, uvicorn,
  hypercorn, granian, daphne).

## Dependencies & Open Questions

**Hard dependencies, resolved:**
- Spec-003 (two-phase plan, reproduce-replay, `sdk.verify_pins`, `FrozenInputs.mode`).
- Spec-004 (`init_only` gate marker, `when` predicate, `hardness`/`allow_flag`
  fields in gate steps).
- Both must be implemented and green before 009 is built. 009 adds zero new runner
  machinery.

**Soft dependency:** Spec-007 (`py-toolchain-pin-resolve`) and spec-008 are
intermediate roadmap items that 009 does not depend on, but since 009 extends
`lang-python`, any concurrent changes to that module must coordinate on merge order.

**Remaining open questions** (OQ-1 … OQ-3, all MED/LOW) are tracked in `memory.md`.
None block authoring a plan when 009's OQs are resolved.

### OQ-1 — Should `when = "orm_intent != none"` be the exact predicate for the ORM sub-resolver? (MED)

The `when` predicate grammar supports `key != value`; the resolved `orm_intent`
default is `""` (empty string). The shipped grammar (`memory.md` spec-004 OQ-1/2)
coerces both sides to string. So `when = "orm_intent != none"` evaluates
`"" != "none"` which is TRUE — a user who leaves `orm_intent` empty would NOT
suppress the ORM sub-resolver. The correct predicate is either
`when = "orm_intent != \"\""` (compare to empty string) or a non-empty input
validator. This needs confirmation against the exact coercion in `eval_when`.
**Lean:** add a fourth `when` form `when = "orm_intent"` (truthy check: non-empty
string = true, empty = false) — simpler and maps naturally to "user gave any
intent". Alternatively keep the default as `"none"` (the string literal) so
`when = "orm_intent != none"` works exactly. Either requires a small `eval_when`
clarification or a default-value convention. Needs human sign-off since it affects
`manifest.py`.

### OQ-2 — Litestar as a supported framework id (MED)

The roadmap mention and steering doc draft include Litestar as an async web
framework alongside FastAPI. However, the existing `lang-python` base resolver
steering (`resolve.md`) does not list Litestar. If 009 adds Litestar support in
the web steering doc, the base resolver also needs updating (so that
`framework = "litestar"` produces correct base `pinned_deps`). Scope question:
does 009 also update the base `resolve.md` to add Litestar? **Lean:** yes, update
both in one PR — the ASGI server and async-mode decisions for Litestar are
identical to FastAPI and it is a first-class async Python web framework. However,
this touches a 003-era steering doc and the user should confirm the scope.

### OQ-3 — Alembic `env.py` template: sync vs async variant? (LOW)

Alembic's `env.py` has meaningfully different content for async vs sync engines.
The spec FR-024 specifies one `env.py.tmpl` template. Should it be a single template
with both code paths (commented-out sync section), or two separate templates keyed
on `async_mode`? **Lean:** two templates (`templates/alembic/env_async.py.tmpl` and
`templates/alembic/env_sync.py.tmpl`), selected by the frozen `async_mode` value —
this keeps each template clean and matches the "curated static templates keyed on
frozen ids" principle (Settled Decision D). Update FR-024 to reflect this split.
This is a design detail resolvable during implementation without blocking the plan.
