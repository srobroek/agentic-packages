# Feature Specification: SDK Import Ergonomics (kill the `_load_sdk` bootstrap)

**Feature Branch**: TBD (`feat/sdk-import-ergonomics`)

**Created**: 2026-06-28

**Status**: Draft — followup spec spun out of the spec-003 leanness audit. Captures
an **empirically verified** finding; not yet scheduled. Lower priority than the
003 resolver itself.

**Input**: The leanness audit's top deferred theme — the import-by-path SDK
bootstrap (`_load_sdk` in modules, `_load_sibling` in the runner) is duplicated
across ~33 files (~315+ lines). The first panel defended it ("no clean DRY seam");
a targeted experiment found a clean seam after all.

## Overview

Every `module.py` carries a ~15-line `_load_sdk()` block that loads `runner/sdk.py`
by file path via `importlib.util.spec_from_file_location`, and every runner file
carries a near-identical `_load_sibling()`. Counts (verified):

- **21** module/example `module.py` files with `_load_sdk` (~15 lines each).
- **12** runner files with `_load_sibling`.

The bootstrap exists because there is no `pyproject`/editable install and a
`uv run module.py` subprocess does not have the runner dir on `sys.path`. The
shared-contracts §6 doc calls the pattern **mandatory** and documents a footgun:
a file-path-loaded module is absent from `sys.modules`, so a `@dataclass`
subclassing `Exception` (e.g. `SetupError`) raises `AttributeError` unless the
module is registered in `sys.modules` BEFORE `exec_module`.

## The verified finding (empirical — do not re-derive)

Tested directly against `uv 0.11.8` on 2026-06-28 with an isolated 3-directory
layout (sdk in dir A, module in dir B, cwd in dir C):

- **Control (PYTHONPATH unset):** `uv run B/module.py` → `import mysdk` (sibling in
  A) **FAILS** (`No module named 'mysdk'`). Confirms the script's own dir alone is
  not enough.
- **Treatment (`PYTHONPATH=A`):** same command → `import mysdk` **SUCCEEDS**.
  Confirms `uv run` propagates the ambient `PYTHONPATH` into the PEP-723 script's
  `sys.path` (verified with and without `--no-project`).

Therefore: if the executor adds the runner dir to `PYTHONPATH` when it spawns a
module, every `module.py` can replace its 15-line `_load_sdk()` with a plain
`import sdk`. The executor already builds a per-subprocess `run_env` and
`setdefault`s `PLUGIN_ROOT` at `executor.py:322` — the exact one-line injection
point exists.

**Bonus — the footgun disappears.** A real `import sdk` registers the module in
`sys.modules` as part of normal import machinery, BEFORE its body executes — so the
`@dataclass(Exception)` `AttributeError` that the manual pattern must guard against
cannot occur. The mandatory "register before exec_module" dance becomes moot for
the import path.

## Settled / proposed decisions

- **A — Executor injects the runner dir on `PYTHONPATH`.** `run_python_step`
  (`executor.py`) adds `<plugin_root>/runner` (and, for examples, the runner dir
  resolved the same way) to `PYTHONPATH` in `run_env`, merged ahead of any inherited
  value. Modules then `import sdk` directly.
- **B — Keep import-by-path as a documented fallback, OR drop it.** Open question
  (OQ-1): some channels may run a `module.py` outside the executor (a test invoking
  it directly). Decide whether modules do a bare `import sdk` (requires the executor
  or the test to set `PYTHONPATH`) or a tiny `try: import sdk / except: <path
  fallback>` shim (a 3-line guard vs the 15-line block). The shim keeps direct
  invocation working at a fraction of the size.
- **C — Runner-internal `_load_sibling` is a SEPARATE, smaller question.** The 12
  runner files use `_load_sibling` because the runner library itself is imported by
  path (no `pyproject` on the runner). `PYTHONPATH` injection by the executor does
  NOT help here (the runner is imported by `cli.py`/tests, not via `uv run`). A
  shared `_bootstrap.py` that each runner file does `from _bootstrap import load`
  still needs ITS OWN path bootstrap to be found — so the runner-side dedup is a
  thinner win and may not be worth it. Scope C as stretch, not core.
- **D — shared-contracts §6 must be amended.** The "register in `sys.modules` before
  `exec_module` is MANDATORY" text is specific to the manual pattern; if modules move
  to `import sdk`, the doc must say the footgun applies only to any remaining
  path-loaded sites (runner-internal), not to modules.

## Requirements

- **FR-001**: The executor MUST place the runner directory on `PYTHONPATH` in the
  per-subprocess env so a `module.py` can `import sdk` without a path bootstrap.
- **FR-002**: All bundled `module.py` files MUST replace `_load_sdk()` with a plain
  `import sdk` (or the 3-line try/except shim per OQ-1), preserving byte-identical
  module OUTPUT (the SDK API and results are unchanged — only the import mechanism).
- **FR-003**: Per-module functional tests that invoke `module.py` via `uv run` MUST
  set the same `PYTHONPATH` (or rely on a conftest helper) so direct-invocation tests
  keep working.
- **FR-004**: shared-contracts §6 MUST be amended to reflect the new import path and
  scope the `sys.modules`-before-`exec_module` footgun to the remaining path-loaded
  sites only.
- **FR-005**: Determinism unchanged — this is a load-mechanism refactor; Tier-1
  output stays byte-identical. The full suite (552+) MUST stay green.

## Success Criteria

- **SC-001**: ~21 module `_load_sdk` blocks removed (~300+ lines), modules
  `import sdk` directly; all module functional tests green.
- **SC-002**: A `module.py` run via the executor resolves the SDK with zero
  importlib boilerplate; a hand-run `uv run module.py` either works (shim) or has a
  documented one-liner to set `PYTHONPATH`.
- **SC-003**: The `@dataclass(Exception)` footgun no longer applies to modules
  (proven by removing the manual `sys.modules` registration from a module and seeing
  `SetupError` still construct fine).

## Out of Scope

- The runner-internal `_load_sibling` dedup (decision C — separate, thinner, stretch).
- Introducing a `pyproject`/editable install (explicitly rejected by 001; the whole
  point is to stay install-free).
- Any change to the SDK's public API or module result shape.

## Open Questions

- **OQ-1 (design) — RESOLVED 2026-06-28: the 3-line try/except shim, NOT bare import.**
  Evidence settled it: the per-module functional tests invoke `uv run module.py`
  DIRECTLY with their own `env={PLUGIN_ROOT, PROJECT_DIR}` (e.g.
  `tests/test_module_lang_python.py:101-105`), NOT through the executor's `run_env`.
  A bare `import sdk` would break ~10 module test files unless each sets `PYTHONPATH`.
  The shim — `try: import sdk` / `except ModuleNotFoundError:` <path-load fallback> —
  keeps direct invocation working with zero test churn, still cuts ~80% of each
  `_load_sdk` block (15 lines → ~3), and removes the manual `sys.modules`-register
  footgun on the happy path. The executor STILL adds `runner/` to `PYTHONPATH`
  (FR-001) so the `try` arm is taken in production; the `except` arm covers
  direct-invocation tests + any non-executor caller.
- **OQ-2 (scope)**: include the runner-side `_load_sibling` (decision C) or defer it?
  Lean: defer; the win is thinner (the runner is imported by cli/tests, not via
  `uv run`, so PYTHONPATH injection doesn't help) and the mechanism is different.
- **OQ-3 (examples)**: the `examples/` modules live two levels deeper; confirm the
  executor's runner-dir resolution covers the example path layout too.

## Scale (re-counted post-leanness-cut, 2026-06-28)

`_load_sdk` in 21 module/example `module.py` files (~15 lines each → ~3 with the shim
= ~250 lines net). `_load_sibling` in 12 runner files (OQ-2, deferred).

## Assumptions

- `uv run` PYTHONPATH propagation is stable behavior (verified on uv 0.11.8; re-verify
  on the CI uv version before implementing).
- The executor is the ONLY production path that spawns `module.py` (tests are the
  other; both can set the env). No third-party harness runs `module.py` without going
  through the executor — confirm before relying on bare `import sdk` (FR-002/OQ-1).
