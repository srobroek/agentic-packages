# Implementation Plan: 012 Stack Decision Record + Reproduce-Time Staleness Check

**Spec**: `specs/012-stack-adr-staleness/spec.md` · **Status**: Draft (2026-06-28)
**Baseline**: full suite 660 passed, 4 deselected (post brownfield-revert).

Plan-then-delegate convention: inline phase breakdown below; each phase gates on the
full suite. 012 has STRUCTURAL runner changes (StepSpec.reproduce_only, ExecutionPlan.
written_at) so it MUST have REAL runner-level tests (mirror `test_two_phase_resolver.py`),
NOT module-only deferrals.

## Resolved open questions (no human-blocking items remain)

- **OQ-1 / Q2 (RESOLVED, user)** → `--refresh` OVERRIDES `reproduce_only`. In
  `run_agent_phase`, a `--refresh stack-adr` (or `.key`) re-invokes the staleness agent
  even at init. Precedence rule: `--refresh` named > `reproduce_only`. Encoded in the
  `do_invoke` logic (see Phase 2).
- **OQ-2 / Q5 (RESOLVED, user)** → `written_at` = LOCAL date
  (`datetime.date.today().isoformat()`), set at `freeze()`. Advisory human "decided-on"
  date, not an audit timestamp. Comment the timezone choice in plan.py.
- **OQ-3 (self-resolved, Fact 6)** → a `kind=python` step CAN emit `answers_to_persist`
  with `"derived"` provenance (`contracts.MODULE_EMITTABLE_PROVENANCE` includes DERIVED).
  Multi-run bootstrap: first init scans + emits `adr_path` (+ `written_at`) as derived
  answers → persisted at stage 8 → reproduce reads them from `FrozenInputs` (no re-scan,
  no date drift). This is the mechanism for FR-006(c) and the written_at-determinism fix.

## The written_at determinism subtlety (memory Assumption 4) — RESOLVED design

`freeze()` is called on EVERY run (init AND reproduce, pipeline Stage 6). If the STACK.md
template read `plan.written_at` directly, a reproduce on a later date would re-freeze a
NEW `written_at` → STACK.md date changes → byte-identity broken (violates FR-016/SC-002).
**Resolution:** the write step reads the date from the module's `written_at` DERIVED
ANSWER (persisted at first init via `answers_to_persist`), NOT from `plan.written_at`
live. At first init that answer is absent → the step seeds it from `plan.written_at` and
emits it as derived. On reproduce the committed `written_at` answer is in the frozen plan
→ read unchanged. `plan.written_at` (the top-level field, FR-014) still exists and is
freshly set each freeze, but the STACK.md date comes from the frozen derived answer. This
keeps the plan-level field honest (it always reflects this run) while the ADR date is
stable.

## Phase 1 — Runner primitives (StepSpec.reproduce_only + ExecutionPlan.written_at)

1. `runner/manifest.py`: add `reproduce_only: bool = False` to `StepSpec` (after
   `init_only`, symmetric, same comment style). Parse it in the step parser exactly like
   `init_only` is parsed. Backward-compatible (default False).
2. `runner/plan.py`:
   - Add `written_at: str = ""` field to `ExecutionPlan`; include in `to_dict()`.
   - `freeze()`: set `plan.written_at = datetime.date.today().isoformat()` at write time
     (add `import datetime` if absent; comment: LOCAL date per Q5). Only set if not
     already populated? NO — set every freeze (the field reflects this run; STACK.md date
     comes from the derived answer, not this field — see subtlety above).
   - `load_plan()`: deserialize `written_at`, default `""` for pre-012 plans (FR-014/SC-010).
   - Step serializer (plan.py:176-177 pattern): serialize `reproduce_only` into the step
     dict when True, mirroring `init_only`.
3. `runner/reproduce.py` `run_agent_phase` (the do_invoke logic at :628-635): extend so
   a `reproduce_only` agent step:
   - at init (`mode != "reproduce"`): SKIP unless `--refresh` named it (module_named or
     key_named) — Q2 override.
   - at reproduce (`mode == "reproduce"`): INVOKE even when not named (plain reproduce
     fires it — the deliberate exception). Read `getattr(step, "reproduce_only", False)`.
   New do_invoke:
     `repro_only = getattr(step, "reproduce_only", False)`
     `if repro_only: do_invoke = module_named or key_named or (mode == "reproduce")`
     `else: do_invoke = (mode != "reproduce") or module_named or key_named`  (unchanged)

**Tests (Phase 1, runner-level — REQUIRED, mirror test_two_phase_resolver.py):**
new `tests/test_reproduce_only.py` — a synthetic module with a reproduce_only agent step
+ a non-reproduce_only step: assert init SKIPS the reproduce_only agent (zero agent_step
calls for it) but runs the normal one; assert plain reproduce INVOKES the reproduce_only
agent; assert `--refresh <mod>` at init INVOKES it (Q2); assert backward-compat (a normal
agent step unaffected — SC-009). Extend `tests/test_plan.py`: `written_at` present in
to_dict + round-trips through freeze/load; pre-012 plan (no written_at) loads → `""`
(SC-010). **Gate full suite before Phase 2.**

## Phase 2 — The stack-adr module (Part 1: deterministic STACK.md/ADR write)

`modules/stack-adr/` — `module.toml` + `module.py` + `templates/` + `steering/`.
- module.toml (FR-001/002): `id="stack-adr"`, `default_enabled=true`, `reconcile=true`,
  `[order] after=["lang-python","lang-ts"]` (soft, NO requires). Inputs: `format`
  (choice simple|adr, default simple), `adr_path` (string, derived). Steps:
  `write` (kind=python) → `staleness` (kind=agent, reproduce_only=true) → `staleness-gate`
  (kind=gate, hardness=informational, init_only=true, message="{decision}" or static —
  see Part 2 / memory Assumption 2).
- module.py `_do_write` (FR-003/004/005/007/008): read frozen answers via
  `load_frozen_inputs`; iterate ALL plan modules, collect any with `pinned_deps` /
  `framework` / `rationale` (NO hard-coded lang ids — FR-004); render from a verbatim
  `templates/stack.md` (+ `templates/adr.md`) with placeholder substitution; date from
  the `written_at` derived answer (fallback `plan.written_at`, then `"unknown"`); ADR
  number = deterministic max+1 `sorted(glob)` scan when `adr_path` absent (first init),
  else read `adr_path` from frozen plan (reproduce, no re-scan); write via
  `idempotent_write(reconcile=True, inspect=args.inspect)`; emit `adr_path` + `written_at`
  as `"derived"` answers_to_persist (FR-006c, Fact 6).

**Tests (Phase 2):** `tests/test_module_stack_adr.py` — SC-001 (frozen plan w/ fixed
written_at → STACK.md with framework/pins-table/rationale/date, byte-identical across two
write invocations); SC-002 (two invocations same plan → identical bytes); SC-003 (adr
format: tmp dir w/ existing 001- → writes 002-, emits adr_path derived); edge: no lang-*
enabled → minimal stub. **Gate full suite.**

## Phase 3 — Part 2 (reproduce-only staleness advisory)

- `steering/staleness.md` (FR-010): instruct the agent to probe PyPI/npm freshness +
  CVEs via `sdk.verify_pins` (FR-013); report ONLY high/critical (CVSS≥7) or hard
  deprecations (FR-010b); emit advisory as `message`, NO answers_to_persist (FR-012);
  graceful degrade "network unreachable, staleness check skipped" (FR-010d); NEVER
  suggest mutating files — direct to `--refresh` (FR-010e).
- The advisory text surfaces via the agent step's `message`/`io.notify` BEFORE the gate
  (memory Assumption 2 resolution — the gate carries a static "Review advisory above"
  message, NOT `{decision}`, because FR-012 forbids the answers_to_persist that
  `{decision}` composition needs). The informational gate prints + auto-proceeds.

**Tests (Phase 3, runner-level):** extend `tests/test_module_stack_adr.py` — SC-004 (init:
staleness agent NOT invoked, gate auto-proceeds, zero network — network-blocking IO
double); SC-005 (reproduce: agent invoked, informational gate prints+proceeds,
`answers.toml` UNCHANGED after run — assert byte-identical answers.toml, FR-012); SC-006
(--non-interactive reproduce: prints+proceeds, no deadlock); SC-007 (network-blocked →
"unreachable" message, gate still proceeds); SC-008 (simulated HIGH CVE → advisory names
pkg+severity; all-patch → "no high/critical findings"). **Gate full suite.**

## Phase 4 — Closeout

Final full-suite gate; flip spec Status → Implemented; fill memory AS-BUILT (real
runner-level coverage, NOT deferred — 012 changes the runner). Commit signed.

## Risk notes

- **Backward-compat (FR-017/SC-009)** is the dominant risk: `reproduce_only` default
  False must leave every existing agent step's dispatch byte-identical; `written_at`
  additive must not break pre-012 plan loads. Per-phase full-suite gate + a dedicated
  SC-009 backward-compat assertion guard this.
- Re-verify the exact sdk.py line numbers at implementation (the spec cites verify_pins at
  315-380; this session confirmed looks_like_secret drifted to 558 — line numbers in the
  spec predate intervening commits; trust the symbol, re-grep the line).
- Do not trust subagent test counts — re-run the full suite in the main thread per phase.
