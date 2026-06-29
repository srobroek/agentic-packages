# Implementation Plan: Tier-2 Stack Resolver

**Branch**: `feat/project-setup-modular-redesign` (continues) → likely `feat/stack-resolver`
| **Date**: 2026-06-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-stack-resolver/spec.md` +
decision rationale in [memory.md](./memory.md).

## Summary

Build the first Tier-2 module — the **stack resolver** — as a reusable pattern
(agent picks framework + companion libs + exact version pins → frozen decision →
pin-table gate → deterministic python manifest write), instantiated for the Python
and TypeScript stacks. Because reading the shipped runner proved that the Tier-2
seam **does not actually work yet** (two verified findings, below), this plan also
ships the minimal runner-contract changes that make any correct Tier-2 module
possible. Per the user's decisions: **OQ-1 → option A** (the contract fixes live in
003, not a separate spec) and **OQ-2 → option B** (same-run agent→python visibility
via a two-phase plan).

This plan is sequenced so the runner contract lands and is proven (Phases 1–3)
before the resolver module is instantiated on top of it (Phases 4–5). The execution
*primitives* (`run_agent_step`, `run_python_step`, `run_gate_step`) are unchanged;
all new control flow is in `run_pipeline` + a `reproduce.py` helper + a net-new SDK
verify primitive.

## The two verified findings this plan repairs (do not re-derive)

Both confirmed line-by-line against the shipped runner on
`feat/project-setup-modular-redesign`; full citations in `memory.md`.

1. **Reproduce RE-RUNS agent steps** (`reproduce.py:335-356` calls `run_agent` and
   re-persists its fresh output; `pipeline.py:526`). It does NOT replay the committed
   `agent-steered` decision. → a plain clone would silently re-research + re-verify
   (network), drifting pins. The roadmap's own Risks section named this as a pre-ship
   gate. Repaired by FR-009 (Phase 3).
2. **The plan is frozen ONCE before execution** (`pipeline.py:471-481`), built from
   interview answers only (`plan.py:96-165` `build_plan(resolved_answers=…)`). A
   `kind=python` step reads the frozen plan (shared-contracts §6: the sole input
   channel), so it cannot see a same-run `kind=agent` step's decision. Repaired by
   FR-011 via the two-phase plan (Phase 3).

## Technical Context

**Language/Version**: Python ≥3.11 via `uv` (stdlib `tomllib`, `urllib`, `json`,
`importlib.util`). No shell. Consistent with 001/002.

**Primary Dependencies**: `uv` (unchanged hard prerequisite). The new
registry-verification primitive is **stdlib `urllib` only** — no `requests`, no
third-party HTTP client, and explicitly **no MCP server dependency** (Settled
Decision C/D; FR-006/FR-008). `mcp-context7` / `mcp-package-version` MUST NOT be
added to `dependencies.apm`.

**Storage**: Unchanged. Committed `.project-setup/{sources,answers}.toml`; the frozen
plan stays in `~/.cache/project-setup/`. The two-phase plan writes the SAME
`plan.json` path twice in one run (v1 then v2); only the final v2 is the
authoritative reproduce artifact.

**Testing**: pytest via `uv run --with pytest pytest -q` (the existing CI contract).
New tests need (a) a **stubbed registry** double for pin-verification (assert
hallucinated/yanked pins are rejected without real network), and (b) a
**network-blocking** test double to prove reproduce makes zero network calls for the
agent step. Both follow the hermetic-stub precedent from `gitignore-generate`'s
offline fetch test.

**Target Platform**: macOS + Linux dev + CI under Claude Code, Codex, `apm install`.
Unchanged.

**Project Type**: CLI tool + agent skill (unchanged).

**Performance Goals**: Not latency-bound. The new cost is N registry HTTPS GETs per
init/refresh (one per proposed pin) — acceptable, and absent entirely on plain
reproduce (zero-network replay is the whole point of FR-009).

**Constraints**: Determinism is two-tier and version-relative (carried from 001).
The new binding rule: **Tier-2 agent decisions are consistent-not-identical AT INIT
but frozen + replayed byte-identically on reproduce** — this is the corrected
behavior, not the current one. Every persisted pin is registry-verified in the same
run; research happens only at init or explicit `--refresh`; plain reproduce is
zero-network.

## Constitution Check

The project constitution (`.specify/memory/constitution.md`) is an unfilled template
— no ratified principles to gate against (same as 001). This plan gates on the spec's
binding decisions (A–J), the 001 shared contracts (`specs/001-.../contracts/shared-contracts.md`,
unchanged here), and the two-tier determinism rules. The one place this plan
*extends* a 001 contract is the execution model (two-phase); that extension is
documented as a new contract in Phase 1 rather than silently changing `executor.py`.

## Phase 1 — Runner contract extensions (BLOCKING; design before code)

These are the 001-runner changes. Land + prove them before the resolver module is
built on top. Each becomes a written contract under `specs/003-stack-resolver/contracts/`.

1. **Two-phase execution contract.** Document the new `run_pipeline` shape: freeze v1
   → Phase A (agent steps) → re-freeze v2 → Phase B (python+gate). Pin the
   invariants: (a) all agent steps precede all python steps (global phasing); (b) a
   `kind=agent` step MUST NOT depend on a Phase-B file write; (c) the v2 freeze is the
   authoritative reproduce artifact; (d) v1 exists only so Phase-A agents read their
   interview inputs. → `contracts/two-phase-execution.md`
2. **Reproduce-replay contract.** In reproduce mode a `kind=agent` step re-emits the
   committed `agent-steered` answer from `answers.toml` with ZERO network calls — no
   agent invocation, no registry lookup. Define exactly how the committed decision is
   read back and shaped into the same `{answers_to_persist, message}` an agent would
   return, so Phase B sees identical inputs to init. → `contracts/reproduce-replay.md`
3. **Agent decision contract.** The frozen decision schema (Settled Decision B):
   `{framework: id, pinned_deps: [name@exact], companions: {slot: name@exact|"none"},
   rationale: text}`. No ranges, no "latest". Persisted as `agent-steered` via the
   existing `merge_module_answers_to_persist` (no new persistence primitive — verified
   `persist.py:376-420`). → `contracts/agent-decision.md`
4. **SDK registry-verify contract.** The net-new `sdk.py` primitive signature +
   semantics: `verify_pins(pins, ecosystem) -> VerifyResult` over stdlib `urllib`
   against PyPI JSON (`https://pypi.org/pypi/<pkg>/json`) / npm
   (`https://registry.npmjs.org/<pkg>`). Define: disconfirmed pin → reject as
   `INPUT_VALUE_INVALID` (fail-closed, FR-005); unreachable registry → distinct
   "unverifiable" status, reported + SAFE-skipped, never silently written (resolves
   **OQ-4** with the split-rule the spec drafts; revisit if a uniform rule is
   preferred). MCP-free correctness (FR-006). → `contracts/registry-verify.md`

**Resolve before coding Phase 1:** read `cli.py` + `mode.py` in full (OQ-6 — not yet
done) so the `--refresh` mode wiring and the gate-message-composition hook are pinned
against how mode detection actually works.

## Phase 2 — SDK registry-verification primitive (the shared, MCP-free verifier)

All in `packages/project-setup/skills/project-setup/runner/sdk.py` + a unit test.

1. `verify_pins(pins, ecosystem)` — stdlib `urllib` HTTPS GET per pin; parse the
   registry JSON; confirm the exact version exists (and is not yanked, for PyPI
   `"yanked"`); return a per-pin `VerifyResult` (`verified | disconfirmed |
   unreachable`). Network-failure-tolerant per the OQ-4 split-rule. No MCP, no
   third-party deps.
2. The verify primitive is a **pure SDK helper** so `lang-python`, `lang-ts`, and a
   later `package-add` reuse ONE implementation (FR-007).
3. Unit test with a stubbed registry (monkeypatched `urllib.request.urlopen`):
   asserts a real pin verifies, a hallucinated/typosquat pin is `disconfirmed`, a
   yanked PyPI version is `disconfirmed`, and an offline registry yields
   `unreachable` (not a false `verified`). No real network in CI.

## Phase 3 — Two-phase pipeline + reproduce-replay (the runner repair)

The core of the runner work. All in `pipeline.py` + `reproduce.py`; primitives in
`executor.py` are UNCHANGED.

1. **Split `run_pipeline` stage 6/7 into Phase A / Phase B** (option B). Today:
   build+freeze plan (`pipeline.py:471-486`) → `build_drift_report` + `apply`
   (`494-515`). New flow:
   - **Freeze v1** from interview answers (unchanged build).
   - **Phase A** — a new helper (in `reproduce.py`) walks topo order and runs every
     `kind=agent` step: init → `run_agent_step` (invoke agent); reproduce → replay the
     committed decision (Phase 1 contract #2, zero network); `--refresh <key>` →
     re-invoke + old-vs-new diff gate (FR-010). Fold every decision into
     `resolved_answers` (reuse `merge_module_answers_to_persist`'s value/provenance
     logic).
   - **Re-freeze v2** — rebuild the plan from the folded answers AND compose each
     `kind=gate` step's `message` from the resolved decision (SUBTLETY 1 — the gate
     must render the pin table; the bare gate only shows a static string today,
     `executor.py:427`). v2 overwrites `plan.json` and is the authoritative artifact.
   - **Phase B** — `build_drift_report` + `apply` over `kind=python` and `kind=gate`
     steps ONLY (agent steps already ran in Phase A), reading v2. The pin-table gate
     fires before its python write; non-interactive SAFE-skips per f1e7269.
2. **Reproduce-replay** (`reproduce.py`) — implement the contract #2 read-back: in
   reproduce mode the Phase-A helper reads the committed `agent-steered` answer and
   re-emits it as the agent's decision WITHOUT calling `io.agent_step` or the registry.
   This is the FR-009 fix; it removes the `reproduce.py:335-356` re-run for the
   reproduce path. (Init/refresh still invoke the agent.)
3. **`--refresh` wiring** — a flag layered on reproduce (resolves **OQ-3** to the
   simplest grammar: `--refresh <module>` or `--refresh <module>.<key>`; whole-module
   refresh re-researches all agent keys). Plain reproduce NEVER researches; `--refresh`
   is the only re-research path, gated per-key by an old-vs-new diff confirm. Verify
   against `cli.py`/`mode.py` mode detection (OQ-6).
4. **Tests**: (a) end-to-end init via ScriptedIO `agent_responses` proving the python
   step reads the agent's pins from v2 and writes them (SC-004); (b) reproduce with a
   network-blocking double proving zero network for the agent step + byte-identical
   manifest (SC-002); (c) `--refresh` re-researches only named keys + a declined
   refresh leaves pins unchanged (SC-003); (d) the global-phasing invariant (an agent
   step ordered after a python step still runs in Phase A).

## Phase 4 — The resolver pattern + Python instantiation

Resolver steps live ON the language modules (resolves **OQ-5** to "on lang-* for 003";
extract a shared `stack-resolve` module later only if `package-add` needs it — the
"build once" mandate is met by the shared SDK verify helper + a shared steering-doc
template, not a shared module). Model the agent step on
`packages/project-setup/skills/project-setup/examples/agent-steered/`.

1. **Shared steering-doc template** — the agent brief that encodes: prose-intent →
   framework + companion suppression (Settled Decision E: default every slot to
   `none`); the recommend-MCP-don't-depend flow (Decision C — check this session's MCP
   tools; if absent, recommend install + restart + resume, OR proceed with
   agent-knowledge pins); emit the exact decision schema; never write files; never
   emit ranges/"latest".
2. **`lang-python` upgrade** (FR-014) — add `[[steps]]`: `resolve` (agent) → `pins`
   (gate) → `write` (python, upgraded). The python step writes a pinned
   `pyproject.toml` (framework + companions), REPLACING the unpinned
   `uv add --dev ruff pytest` at `module.py:173` with a researched+pinned dev-tool
   block, and derives the `astral-sh/ruff-pre-commit` `rev` from the SAME frozen ruff
   pin (so local + CI agree). The currently-inert `framework` input (`module.py:108-111`)
   becomes the agent's structured decision. Cross-field re-validation: `requires_python`
   vs frozen `python_version`, async-framework vs driver (FR-003) — hard-error on
   contradiction.
3. **Tests**: pins all registry-verified (stubbed); an injected hallucinated/yanked
   pin is rejected and never written (SC-001); no unpinned `uv add` remains; ruff-hook
   `rev` equals the frozen ruff pin (SC-005).

## Phase 5 — TypeScript instantiation

1. **`lang-ts` upgrade** (FR-015) — same step shape: agent resolves framework
   (Nuxt/Vite/plain) + `name@version` deps + a pinned `packageManager` field, each
   verified against the npm registry. The python step writes a pinned `package.json`
   deterministically REGARDLESS of whether an external scaffolder runs. External
   scaffolder runs (`nuxi init`, `create-vite`) stay recorded-command + gated (the
   spec-004 G4 generator gate; 003 uses the bare gate) and are skipped in CI.
2. **Tests**: pinned `package.json` + `packageManager`; CI (`--non-interactive`) skips
   the scaffolder + the pin-table write, exits green, deterministic (SC-006); no MCP in
   `dependencies.apm`; bad pins rejected with zero MCP tools present (SC-007).

## Phase 6 — Verification + docs

1. Full suite green (the ~6-min real-`uv-run` suite; run in background):
   `uv run --with pytest pytest -q packages/project-setup/tests/ -k 'not SuccessfulGitFetch'`.
2. SKILL.md additions: how the agent conducts stack resolution (the steering-doc
   reference), the recommend-MCP-don't-depend flow, the pin-table gate, and what
   "done" means for a Tier-2 resolve. Thin-config / thick-process (unchanged H2 rule).
3. Confirm the determinism rules hold end-to-end: reproduce is byte-identical +
   zero-network; `--refresh` is the only re-research path.

## Project Structure

### Documentation (this feature)

```text
specs/003-stack-resolver/
├── plan.md              # this file
├── spec.md              # the spec (OQ-1/OQ-2 resolved)
├── memory.md            # findings, resolved OQs, phase design + 2 subtleties
├── contracts/           # Phase-1 contracts (to author at impl start):
│                        #   two-phase-execution.md, reproduce-replay.md,
│                        #   agent-decision.md, registry-verify.md
├── data-model.md        # decision schema + VerifyResult shape (to author)
├── research.md          # registry endpoint shapes + gate-message composition (to author)
├── quickstart.md        # "author a Tier-2 resolver step" walkthrough (to author)
├── checklists/requirements.md   # (to author)
└── tasks.md             # produced by /speckit.tasks (NOT this command)
```

### Source code touched (repository root)

```text
packages/project-setup/skills/project-setup/
├── runner/
│   ├── sdk.py           # + verify_pins() registry primitive (Phase 2, net-new)
│   ├── pipeline.py      # two-phase split: freeze v1 → Phase A → re-freeze v2 → Phase B (Phase 3)
│   ├── reproduce.py     # Phase-A helper + reproduce-replay (zero-network agent) (Phase 3)
│   ├── plan.py          # re-freeze entry + gate-message composition at v2 (Phase 3)
│   ├── cli.py           # --refresh flag wiring (Phase 3; read in full first — OQ-6)
│   └── mode.py          # --refresh mode interaction (verify — OQ-6)
└── modules/
    ├── lang-python/     # resolve(agent)→pins(gate)→write(python); kill unpinned uv add (Phase 4)
    │   └── steering/    # + shared resolver steering-doc template (Phase 4)
    └── lang-ts/         # resolve(agent)→pins(gate)→write(python); pinned package.json (Phase 5)
        └── steering/
```

**Structure Decision**: Resolver steps live on the existing `lang-*` modules (OQ-5),
reusing the unchanged native-root layout + import-by-path SDK contract from 001. The
only net-new runner file surface is `sdk.verify_pins`; everything else is edits to
existing runner files (the two-phase control flow) and the two language modules. No
new module directory, no schema change, no new persistence primitive.

## Complexity Tracking

| Decision | Why needed | Simpler alternative rejected because |
|----------|------------|--------------------------------------|
| Two-phase plan (Phase A agents → re-freeze v2 → Phase B python/gate) | A python step reads ONLY the frozen plan (contracts §6); a same-run agent decision must be in the plan before the python step runs | (a) re-freeze mid-execution: the inspect/confirm pass at `pipeline.py:498` already ran over the stale plan — temporal hazard; (c) sidecar file: bypasses the frozen-plan input channel, punching a second input source into the determinism model |
| Runner contract fixes inside 003 (not a separate 003a) | The contract (reproduce-replay, two-phase, refresh) is untestable without a real Tier-2 module to drive it | Extracting 003a would land runner machinery with no in-tree consumer, needing a synthetic example module as a stand-in — make-work, and the contract could drift from what the real resolver needs (user-confirmed, OQ-1=A) |
| Gate-message composition at re-freeze (v2) | The bare `kind=gate` renders a static `message` string; the pin table isn't known until the agent decides | Carrying structured gate data is spec-004's richer gate; baking the string at v2 lets 003 ship on the existing bare gate without depending on 004 |
| Net-new `sdk.verify_pins` over stdlib urllib | No registry-verification primitive exists anywhere in the tree; hallucinated/yanked pins are the dominant supply-chain abuse mode | Depending on `mcp-package-version` for verification would make correctness require an MCP server (CI/headless can't connect) — the exact over-coupling the corrected decision forbids |
| Global phasing (all agents before all python) | One simple, deterministic phase boundary; the resolver agent needs only interview answers + research | Per-module interleaving (today's `apply`) would require a partial topological re-freeze after each agent step — more complex, and no resolver use-case needs an agent to read another module's Phase-B writes |
