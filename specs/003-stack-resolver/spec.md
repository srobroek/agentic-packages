# Feature Specification: Tier-2 Stack Resolver

**Feature Branch**: `feat/project-setup-modular-redesign` (continues) → likely a
dedicated `feat/stack-resolver` branch

**Created**: 2026-06-27

**Status**: **Implemented (2026-06-28)** — all FRs built and green (full suite below).
Authored independently from the 002 roadmap + gates-analysis + the corrected
research-backend decision; **two verified code findings reshaped scope** (see
"Current state"). The two HIGH open questions were resolved by the user: OQ-1 →
keep the runner-contract fixes inside 003 (option A); OQ-2 → same-run agent→python
visibility via the **two-phase plan** (option B). The AS-BUILT refinements (one
freeze instead of two; `{decision}` gate token; gate-blocking in `apply`) are
recorded in `memory.md` → "AS-BUILT".

**Input**: The headline Tier-2 feature the user named — "which framework + which
current versions + which companion libs", instantiated for Python and TypeScript.
Rank #1 in `reviews/tier2-agentic-features-roadmap.md`. Builds on the 001 runner +
modules architecture and the 002 enablement layer.

## Overview

The 001 migration built the generic runner + modules and proved Tier-1 parity.
The 002 enablement layer added agent-led "which optional modules" selection. The
language overlays it can now enable (`lang-python`, `lang-ts`) still treat the
framework as a **free-form string that nothing acts on** (`lang-python/module.py:109-111`
comment: "framework is accepted but not structurally acted on"), and they install
dependencies **unpinned** (`lang-python/module.py:173`: `uv add --dev ruff pytest`
— resolves "latest" at run time).

This feature adds the **stack resolver**: the first real Tier-2 module. It is a
generic, reusable pattern —

> an **agent** maps the user's prose intent to a structured, fully-pinned
> stack decision `{framework, pinned_deps: [name@exact], companions, rationale}`;
> the decision is **frozen** with `agent-steered` provenance; a **gate** shows
> the full pin table; then a deterministic **python** step mechanically writes
> the manifest (`pyproject.toml` / `package.json`) from the frozen pins.

— instantiated for the Python stack and the TypeScript stack. It is the exact
"agent decides → python writes" seam the roadmap built the whole Tier-2 program
around, and it is the first end-to-end exercise of the built-but-unused
`kind=agent` step.

**This spec discovered, by reading the runner, that the seam does not yet hold.**
The roadmap and the 002 `memory.md` both asserted "research happens once at init,
then freezes; reproduce replays frozen answers, zero network" and "agent decides;
python writes". Direct verification (citations in "Current state") shows **neither
is true today**:

- Reproduce mode **re-invokes** every `kind=agent` step (`reproduce.py:335-356`)
  rather than replaying the committed decision — so a plain clone/reproduce would
  silently re-research and could drift the pins. The roadmap's own Risks section
  named this as a *"verify reproduce-mode replay has zero network calls for agent
  steps before shipping any resolver"* gate. It fails that gate.
- The plan is frozen **once, before execution** (`pipeline.py:481`), from interview
  answers only; a `kind=python` step reads that frozen plan and **cannot see** a
  same-run `kind=agent` step's `answers_to_persist`. The agent's decision only
  reaches `answers.toml` at persist time (stage 8, after execution).

Therefore 003 is **not** just "author a module." It is **the first Tier-2 module
PLUS the minimal runner contract work that makes any correct Tier-2 module
possible**: reproduce-replay of frozen agent decisions, an explicit `--refresh`
as the only re-research path, same-run agent→python visibility, and an MCP-free
registry-verification primitive. These runner changes touch 001's territory (the
runner library) and are called out as such.

## Current state (verified — citations, do not re-derive)

All file:line references verified against the shipped code on
`feat/project-setup-modular-redesign` at the time of authoring.

- **`lang-python` framework is inert.** `modules/lang-python/module.py:108-111`:
  `python_version` is consumed; `framework` is read nowhere and the comment says
  it is "a free-form string placeholder for future use".
- **`lang-python` installs unpinned.** `modules/lang-python/module.py:170-177`
  runs `uv add --dev ruff pytest` with no version pins (latest-at-runtime). The
  roadmap classifies lang-* as deliberately NOT byte-identical (they run real
  installers), so this is a *design choice to upgrade*, not a Tier-1 violation —
  but it is the exact thing the resolver pins.
- **`lang-ts` framework branches exist but are unpinned + scaffolder-driven.**
  `modules/lang-ts/module.py:146-212`: `nuxi@latest init`, `create-vite`,
  `bun init`, then `bun/pnpm install`. Dependencies come from the external
  scaffolder, not from pinned resolver output; `framework` is a free string
  (`"nuxt"`, `"vite"`, `"plain"`).
- **The agent-step machinery works, but is wired wrong for the Tier-2 contract:**
  - `executor.run_agent_step` (`executor.py:443-475`) hands a `kind=agent` step's
    `steering` doc + a context dict to `io.agent_step(steering_path, ctx)` and
    returns the response. The response must carry
    `answers_to_persist = {key: {value, source: "agent-steered"}}` + `message`
    (`io_adapter.py:60-81`).
  - `merge_module_answers_to_persist` (`persist.py:376-420`) correctly folds those
    into the persisted answer maps with `agent-steered` provenance.
  - **BUT reproduce re-runs the agent:** `reproduce.apply` (`reproduce.py:335-356`)
    calls `run_agent(...)` for every `kind=agent` step and merges its **fresh**
    output. There is no branch that reads the committed `agent-steered` answer from
    `answers.toml` and re-emits it. `pipeline.py:526` then re-persists the
    re-derived value. → **reproduce is not a network-free replay.**
  - **AND the plan freezes before execution:** `pipeline.py:471-481` builds + freezes
    the plan from `final_answers` (interview answers), then `execute` runs. `build_plan`
    (`plan.py:96-165`) only sees `resolved_answers`, never `answers_to_persist`. The
    plan is **never re-frozen** during execution. → a python step in the same run
    cannot read an agent step's decision via the frozen plan (the only legal input
    channel — shared-contracts §6: "agent args are NEVER an input channel").
- **No registry-verification primitive exists.** The only network use in the tree
  is `gitignore-generate/module.py` fetching GitHub gitignore *templates* via
  `urllib` (non-fatal), and `sources/fetch.py` doing git fetches via subprocess.
  **No PyPI/npm registry lookup, no version-existence check, anywhere.** The
  resolver's mandatory pin-verification is **net-new**.
- **The gate primitive is bare but functional.** `run_gate_step`
  (`executor.py:396-437`) renders one `message`, calls `io.confirm` (default No),
  and — since commit f1e7269 — SAFE-skips (returns `False`) in `non_interactive`
  mode without blocking on stdin. A `kind=gate` step is `{id, kind, message}`; it
  carries no hardness/allow-flag yet (that richness is spec 004 / `gates-analysis.md`
  G6). **003 can declare a working `kind=gate` step today**; 004 upgrades it.
- **Init now goes through the inspect→confirm→write path too.** `pipeline.py:494-515`
  runs `build_drift_report` + `apply_reproduce` for both modes (the f1e7269 init-confirm
  fix), so a resolver's `kind=python` write step gets a confirm pass in init as well.

## Settled decisions (carried in + newly settled here)

Carried from the roadmap / 002 `memory.md` (the corrected research-backend
decision) — restated as binding for this spec:

- **A — One generic resolver pattern, instantiated per ecosystem.** Build the
  resolver seam ONCE (agent → frozen pinned decision → gate → python manifest write)
  and instantiate it for Python and TypeScript. It is the reusable template ranks
  #2/#5/#7/#11 of the roadmap all reuse.
- **B — The agent decides; python writes. The agent never writes files and never
  emits ranges or "latest".** The agent emits a frozen structured decision (ids +
  exact `name@version` pins + rationale) as `agent-steered` answers; a python step
  reads it and mechanically renders the manifest via `idempotent_write`, then runs
  the package manager with EXACT pins.
- **C — Recommend MCP, do NOT depend on it** (the "install uv" pattern applied to
  MCP — corrected decision, `specs/002-agentic-features/memory.md:72-93`). The
  resolver's steering doc instructs the agent to (1) check whether the context7 /
  package-version MCP tools are available this session; (2) if present, use them for
  richer current-version research; (3) if absent, RECOMMEND installing
  `mcp-context7` + `mcp-package-version`, restart Claude Code, and resume — OR
  proceed now with agent-knowledge pins. **`mcp-context7` / `mcp-package-version`
  MUST NOT be added to project-setup's `dependencies.apm`.**
- **D — Pin verification is MANDATORY and MCP-free.** Every proposed pin is
  hard-verified against the live registry (PyPI JSON `https://pypi.org/pypi/<pkg>/json`;
  npm `https://registry.npmjs.org/<pkg>`) via **stdlib `urllib`** before persist.
  A pin the registry cannot confirm (hallucinated / yanked / typosquat) is rejected
  as `INPUT_VALUE_INVALID`. Correctness NEVER depends on an MCP server being present.
  Canonical package names come from the framework's current docs (context7 when
  available), not free recall.
- **E — Companion-lib suppression by default.** Every capability slot
  (router/state/data-fetching/ORM/test-runner) defaults to `none` and is filled
  ONLY if the chosen meta-framework demonstrably does not already provide it. The
  agent's value is suppression of redundant/conflicting libs, not a checkbox pile.

Newly settled here (forced by the two verified findings — these are the in-scope
runner contract changes):

- **F — Reproduce REPLAYS frozen agent decisions; it does not re-run the agent.**
  In reproduce mode, a `kind=agent` step MUST re-emit the committed `agent-steered`
  answers from `answers.toml` with **zero network calls** — not re-invoke the
  research. This is the determinism fix the roadmap's Risks section demanded. (Fixes
  the `reproduce.py:335-356` re-run.)
- **G — `--refresh <module|key>` is the ONLY mode that re-researches.** Re-derivation
  is always explicit, per-key, and gated behind an old-vs-new diff confirm
  (roadmap #3). Plain reproduce never researches. This is what makes F safe by
  construction rather than convention.
- **H — Same-run agent→python visibility via a two-phase plan (option B, chosen).**
  The runner splits execution into **Phase A (research/decide)** and **Phase B
  (deterministic writes)**, with a single authoritative freeze between them:
  1. Build + freeze the plan v1 from interview answers (as today).
  2. **Phase A:** run ALL `kind=agent` steps (topo order). In init they invoke the
     agent; in reproduce they REPLAY the committed `agent-steered` answer with zero
     network (FR-009); under `--refresh` they re-invoke + diff-gate (FR-010). Fold
     every agent decision into `resolved_answers`.
  3. **Re-freeze the plan v2** — now carrying the agent pins — as the single
     authoritative plan (FR-011). For `kind=gate` steps, re-freeze ALSO composes the
     gate `message` from the resolved decision (so the bare gate can render the pin
     table; see "Two design subtleties" in `plan.md`).
  4. **Phase B:** run `build_drift_report` + `apply` over `kind=python` and
     `kind=gate` steps, reading plan v2. The pin-table gate fires before its python
     write. This preserves shared-contracts §6 ("the frozen plan is the only input
     channel" — agent args are never a channel).

  This makes phasing **global**: every agent step runs before any python step. That
  is an invariant, not a limitation — a `kind=agent` step MUST NOT depend on a
  Phase-B file write (consistent with the Tier-2 principle that an agent decides
  from prose + research, never from another module's writes). Plan v1 exists only so
  the Phase-A agent can read its interview inputs; plan v2 is the authoritative
  freeze every Tier-1 write reproduces from.
- **I — Registry verification is a shared SDK helper.** The MCP-free verify
  primitive (D) lives in the runner SDK (`sdk.py`) so `lang-python`, `lang-ts`, and
  later `package-add` reuse one implementation. It is stdlib-`urllib`-only,
  network-failure-tolerant in a defined way (see FR-012), and never a hard runner
  dependency beyond `uv`.
- **J — The pin-table gate is mandatory and rides the EXISTING bare gate.** The
  resolver declares a `kind=gate` step showing the full pin table + each pin's
  registry-verification status + downgrade-from-latest reasons, before the manifest
  write. It works with today's `run_gate_step`; spec 004 later enriches it with
  hardness/allow-flags (G6). In `--non-interactive`/CI the gate SAFE-skips the
  manifest write (per f1e7269), so CI never writes unverified pins and never
  deadlocks.

## User Scenarios & Testing

### User Story 1 — Resolve a Python web stack from prose (Priority: P1)

A user enables `lang-python` and says "a FastAPI service with Postgres". The agent
researches current versions, proposes a fully-pinned stack (framework + ASGI server
+ async driver + dev tools), every pin is registry-verified, the user sees the pin
table at a gate and confirms, and the python step writes `pyproject.toml` with the
exact pins.

**Acceptance Scenarios**:

1. **Given** `lang-python` enabled and a prose intent, **When** the resolver's agent
   step runs, **Then** it emits an `agent-steered` decision with a framework id and
   a list of `name@exact-version` pins (no ranges, no "latest") + rationale.
2. **Given** the agent's proposed pins, **When** verification runs, **Then** each pin
   is confirmed to exist on PyPI; a non-resolving pin is rejected with
   `INPUT_VALUE_INVALID` and the agent is asked to correct it (never written).
3. **Given** verified pins, **When** the gate fires, **Then** the user sees the full
   pin table (name@version, verified ✓/✗, downgrade reasons) and confirms; **Then**
   the python step writes `pyproject.toml` with exactly those pins.

### User Story 2 — Reproduce is a zero-network replay (Priority: P1)

A teammate clones the repo and reproduces. The committed `agent-steered` pins replay
byte-for-byte into the manifest with **no** research and **no** network for the
agent step.

**Acceptance Scenarios**:

1. **Given** committed `agent-steered` pins in `answers.toml`, **When** the runner
   runs in reproduce mode, **Then** the `kind=agent` step re-emits the committed
   decision with zero network calls (no agent re-invocation, no registry lookup).
2. **Given** the replayed decision, **When** the python write step runs, **Then** it
   writes the identical manifest (Tier-1 byte-identical for the same pins).

### User Story 3 — Explicit re-research via `--refresh` (Priority: P2)

A maintainer wants newer versions. They run `--refresh lang-python` (or
`--refresh lang-python.pinned_deps`); the agent re-researches ONLY the named keys,
the runner shows old-vs-new pins at a diff gate, and only on confirm are the new
pins verified, frozen, and written.

**Acceptance Scenarios**:

1. **Given** a committed stack, **When** the user runs plain reproduce, **Then** no
   re-research happens (Story 2).
2. **Given** `--refresh lang-python`, **When** the runner runs, **Then** the agent
   re-researches the named keys, a diff gate shows old→new per pin, and a declined
   refresh leaves the committed pins unchanged.

### User Story 4 — TypeScript stack instantiation (Priority: P2)

The same pattern resolves a TS stack: framework (Nuxt/Vite/plain) + package manager
+ pinned companion set, written to `package.json` with the `packageManager` field
pinned; external scaffolder runs (if any) stay behind the existing generator gate
(G4, spec 004) and are skipped in CI.

**Acceptance Scenarios**:

1. **Given** `lang-ts` enabled + prose intent, **When** the resolver runs, **Then**
   it emits a pinned TS decision (framework id + `name@version` deps + `packageManager`
   pin), each verified against the npm registry.
2. **Given** an external scaffolder is part of the chosen framework, **When** the
   manifest write runs, **Then** the pinned deps are written deterministically and
   the scaffolder invocation is recorded-command + gated (not silently run in CI).

### Edge Cases

- **Offline / registry unreachable at init**: verification cannot confirm a pin →
  the resolver MUST NOT silently write an unverified pin. It reports the unverifiable
  pins at the gate and (non-interactive) SAFE-skips the write. (See FR-012 for the
  exact policy — fail-closed on verify, distinct from the soft-skip the offline
  *source-fetch* path uses.)
- **Agent proposes a range or "latest"**: rejected as `INPUT_VALUE_INVALID` (the
  decision must be exact pins).
- **A chosen meta-framework already provides a slot** (e.g. Nuxt provides routing):
  the agent leaves that companion slot `none`; filling it anyway is a flagged
  redundancy.
- **`--refresh` on a key that has no committed value**: treated as first research
  (init-like), gated normally.
- **Cross-field contradiction** (e.g. async framework + sync driver; framework
  `requires_python` > frozen `python_version`): the python step re-validates the
  frozen decision against the other frozen answers and hard-errors rather than
  trusting the agent blindly.
- **MCP recommended mid-init, user restarts before init completes**: there is no
  committed `.project-setup/` yet to resume from (it is written at persist, stage 8)
  — so "restart + resume" cannot reproduce an incomplete init. See Open Question
  OQ-6; the safe default is "proceed now with agent-knowledge pins, then `--refresh`
  later once MCP is installed."

## Requirements

### Resolver pattern (agent → freeze → gate → write)

- **FR-001**: The resolver MUST be expressed as an ordered `[[steps]]` sequence on
  the language module: a `kind=agent` research/decision step, a `kind=gate` pin-table
  review step, then a `kind=python` manifest-write step — in that order.
- **FR-002**: The `kind=agent` step MUST emit a structured decision as
  `agent-steered` answers: at minimum `{framework: id, pinned_deps: [name@exact],
  companions: {slot: name@exact|none}, rationale: text}`. It MUST NOT emit version
  ranges or "latest", and MUST NOT write any file.
- **FR-003**: The `kind=python` step MUST read the frozen decision from the frozen
  plan (never from agent args), render the manifest via `sdk.idempotent_write`, and
  invoke the package manager with EXACT pins only. It MUST re-validate the frozen
  decision against the other frozen answers (e.g. `requires_python` vs
  `python_version`, async-framework vs driver) and hard-error on contradiction.
- **FR-004**: The decision MUST be persisted to `answers.toml` with `agent-steered`
  provenance via the existing `merge_module_answers_to_persist` path (no new
  persistence primitive).

### Pin verification (MCP-free, mandatory)

- **FR-005**: Every persisted pin MUST be verified to exist on its registry (PyPI
  JSON / npm registry) via stdlib `urllib` in the same run, BEFORE the gate and
  before any write. A pin the registry does not confirm MUST be rejected as
  `INPUT_VALUE_INVALID` and never written.
- **FR-006**: Verification MUST NOT depend on any MCP server. Correctness (rejecting
  bad pins) MUST hold with zero MCP tools available.
- **FR-007**: The verification helper MUST live in the runner SDK (`sdk.py`) as a
  shared primitive reusable by `lang-python`, `lang-ts`, and later `package-add`.
- **FR-008**: The resolver MUST NOT add `mcp-context7` / `mcp-package-version` (or any
  MCP server) to project-setup's `dependencies.apm`.

### Reproduce, refresh, determinism (the runner contract fixes)

- **FR-009**: In reproduce mode a `kind=agent` step MUST replay the committed
  `agent-steered` answer from `answers.toml` and re-emit it with **zero network
  calls** — it MUST NOT re-invoke the agent or re-verify against the registry. *(Fixes
  the verified `reproduce.py:335-356` re-run.)*
- **FR-010**: A `--refresh <module|key>` mode MUST be the only path that re-invokes
  agent research and re-verifies pins; it MUST present an old-vs-new diff gate per
  refreshed key and MUST NOT re-persist or re-write without confirmation. Plain
  reproduce MUST NEVER research.
- **FR-011**: Execution MUST be split into two phases with one authoritative freeze
  between them (the two-phase plan, Settled Decision H): **Phase A** runs all
  `kind=agent` steps and folds their decisions into the resolved answers; the runner
  then **re-freezes the plan (v2)**; **Phase B** runs `kind=python` (+ `kind=gate`)
  steps reading plan v2, so a python step reads the agent's decision via the frozen
  plan. Phasing is global (all agent steps precede all python steps); a `kind=agent`
  step MUST NOT depend on a Phase-B file write. *(Fixes the verified
  freeze-once-before-execute gap, `pipeline.py:481`.)*

### Gate + non-interactive

- **FR-012**: The pin-table gate MUST show, per pin: `name@version`, registry-verify
  status, and any downgrade-from-latest reason. In `--non-interactive`/CI the gate
  MUST SAFE-skip the manifest write (no unverified write, no deadlock) per the
  f1e7269 policy. On init, a pin that **failed verification** is fail-closed (never
  written) regardless of interactivity; a pin that could not be *reached* (offline)
  is reported and SAFE-skipped, never silently written.
- **FR-013**: The resolver MUST work with the existing bare `kind=gate` primitive;
  it MUST NOT require the spec-004 hardness/allow-flag enrichment to function (004
  upgrades the gate; 003 does not block on it).

### Instantiation

- **FR-014**: `lang-python` MUST be upgraded so `framework` is acted on: the resolver
  writes a pinned `pyproject.toml` (framework + companions + the dev-tool block that
  replaces the unpinned `uv add --dev ruff pytest` at `module.py:173`). The
  ruff-pre-commit hook `rev` MUST be derived from the SAME frozen ruff pin so local
  and CI agree.
- **FR-015**: `lang-ts` MUST be upgraded to resolve a pinned TS stack (framework +
  `name@version` deps + a pinned `packageManager` field). External scaffolder runs
  (`nuxi init`, `create-vite`) MUST stay recorded-command + gated and skipped in CI;
  the pinned deps MUST be written deterministically regardless of whether the
  scaffolder runs.

## Success Criteria

- **SC-001**: An agent-resolved Python stack writes a `pyproject.toml` whose pins are
  ALL registry-verified; an injected hallucinated/yanked pin is rejected and never
  written (verified by test with a stubbed registry).
- **SC-002**: A reproduce run of a committed stack performs ZERO network calls for
  the agent step and writes a byte-identical manifest (verified by a network-blocking
  test double + byte comparison).
- **SC-003**: `--refresh` re-researches only the named keys, shows an old→new diff,
  and a declined refresh leaves committed pins unchanged.
- **SC-004**: A same-run init resolves → freezes → the python step reads the agent's
  pins from the re-frozen plan and writes them (verified end-to-end with ScriptedIO
  agent_responses).
- **SC-005**: `lang-python` no longer runs an unpinned `uv add`; dev tools are pinned
  and the ruff-pre-commit `rev` equals the frozen ruff pin.
- **SC-006**: `lang-ts` writes a pinned `package.json` + `packageManager`; CI
  (`--non-interactive`) skips the external scaffolder and the pin-table write, exits
  green, and is deterministic.
- **SC-007**: No MCP server appears in project-setup's `dependencies.apm`; the resolver
  rejects bad pins with zero MCP tools present.

## Out of Scope

- The richer spec-004 gate machinery (hardness field, `allow_flag`, whole-plan
  preview G1, batched install gate G2). 003 uses the bare gate; 004 enriches it.
- Roadmap ranks #4–#12 (agents-md architecture section, CI-matrix module, brownfield
  detect, dependency-update skill, env-example, stack ADR, deep py-web/orm overlays,
  ts depth resolvers, org-overlay). 003 builds ONLY the generic pattern + py/ts
  instantiation; later specs reuse the pattern.
- Go / Rust stack resolution (the pattern will extend later; not in 003).
- Changing the 001 manifest schema or discovery/collision rules.

## Assumptions

- The 001 runner + 002 enablement layer are in place and green (533 tests at
  authoring).
- `merge_module_answers_to_persist` (`persist.py:376-420`) is the persistence path
  for `agent-steered` answers; no new persistence primitive is needed (verified).
- The bare `kind=gate` primitive + the f1e7269 non-interactive SAFE-skip are
  sufficient for 003's gate; 004 enriches later.
- `${PLUGIN_ROOT}` / `PROJECT_DIR` env wiring and the import-by-path SDK contract
  (shared-contracts §6) are unchanged.
- Registry endpoints (`pypi.org/pypi/<pkg>/json`, `registry.npmjs.org/<pkg>`) are the
  canonical verify sources and are reachable over plain HTTPS GET with no auth.

## Dependencies & Open Questions

**Hard dependency, resolved (OQ-1 → option A):** 003's correctness requires the
runner contract fixes (FR-009, FR-010, FR-011). These touch the 001 runner library
(`reproduce.py`, `pipeline.py`, `plan.py`, `cli.py`, `sdk.py`), not just a new
module directory. **The user chose to keep them inside 003** — a Tier-2 module is
the only thing that exercises the contract, so the contract and its first consumer
ship together. (Not extracted into a separate "003a" spec.)

**Same-run agent→python design, resolved (OQ-2 → option B):** the two-phase plan
(Settled Decision H + `plan.md` Phase 3). Not the mid-execution re-freeze (option A,
rejected — temporal hazard) nor the sidecar file (option C, rejected — bypasses the
frozen-plan input channel).

**Soft dependency on 004**: the rich G6 pin-review gate (hardness, allow-flags,
inline verify status) is 004. 003 ships the bare gate; 004 upgrades it. No ordering
deadlock — 003 works standalone, 004 makes the gate nicer.

**Remaining open questions** (OQ-3 … OQ-6, all MED/LOW) are tracked in `memory.md`
so they can be addressed without re-reading this spec. None block authoring `plan.md`;
they are resolved during planning/implementation (CLI grammar, offline-verify policy,
resolver-on-lang-* vs shared module, `cli.py`/`mode.py` verification).
