# Feature 003 — Tier-2 Stack Resolver (memory)

Authored independently in one session (per user goal: "work fully independent;
note down any questions, blockers, assumptions or ambiguities so we can address
later"). This file is the durable record of HOW the spec was reasoned and WHAT
needs the user's input before implementation. Everything here is verified against
shipped code on `feat/project-setup-modular-redesign` unless marked otherwise.

## Scope decision (what 003 is)

003 = **the generic Tier-2 resolver pattern (agent → freeze → gate → python write)
+ its py/ts instantiation + the minimal runner contract fixes that make ANY correct
Tier-2 module possible.** It is roadmap rank #1, and it absorbs the parts of ranks #2
(py-toolchain pin) and #3 (refresh gate) that are inseparable from making #1 correct.
Ranks #4–#12 explicitly deferred (reuse the pattern later).

## TWO VERIFIED CODE FINDINGS that reshaped the spec (read these first)

These contradict claims in `specs/002-agentic-features/memory.md` and
`reviews/tier2-agentic-features-roadmap.md`. I verified each by reading the runner
directly (the handover explicitly warned not to trust a subagent's reading; one
finding was first surfaced by an Explore subagent and I confirmed it line-by-line).

### Finding 1 — Reproduce RE-RUNS agent steps; it does NOT replay frozen answers

- **Claimed** (002 memory line 30; roadmap Executive Summary + principle 3):
  "Research happens exactly once at init, then freezes. Reproduce replays the frozen
  answer verbatim (no network)."
- **Reality**: `reproduce.py:335-356` — `apply()` calls `run_agent(step_dict, mod_id, io)`
  for EVERY `kind=agent` step and folds its **fresh** `answers_to_persist` into the
  outcome. `pipeline.py:526` then re-persists the re-derived value. There is **no
  code path** that reads the committed `agent-steered` answer from `answers.toml` and
  re-emits it. So a plain clone/reproduce re-invokes the agent (and, for the resolver,
  would re-research + re-verify, with network).
- **The roadmap itself flagged this as a pre-ship gate** (Risks section: "Verify
  reproduce-mode replay has zero network calls for agent steps before shipping any
  resolver"). It fails that gate today. → became spec FR-009 + Settled Decision F.

### Finding 2 — The plan is frozen ONCE, before execution; agent→python can't flow in one run

- **Claimed** (roadmap principle 2): "The agent decides; python writes" — implying a
  single run where the agent's decision reaches the python step.
- **Reality**: `pipeline.py:471-481` builds + freezes the plan from `final_answers`
  (interview answers only), THEN executes (`pipeline.py:494-515`). `build_plan`
  (`plan.py:96-165`) only receives `resolved_answers`, never `answers_to_persist`. The
  plan is **never re-frozen** during execution. A `kind=python` step reads the frozen
  plan (shared-contracts §6: "agent args are NEVER an input channel"), so it **cannot
  see** a same-run `kind=agent` step's decision. The agent's value only lands in
  `answers.toml` at persist (stage 8, AFTER execution).
- → became spec FR-011 + Settled Decision H (fold + re-freeze before dependent python
  step). This is the trickiest runner change; see OQ-2 for the design tension.

## Verified facts the spec relies on (so implementation doesn't re-derive)

- `lang-python/module.py:108-111` — `framework` input is read NOWHERE (inert string).
- `lang-python/module.py:170-177` — `uv add --dev ruff pytest` is UNPINNED.
- `lang-ts/module.py:146-212` — framework branches run external scaffolders
  (`nuxi@latest init`, `create-vite`, `bun init`) + `bun/pnpm install`; deps are
  scaffolder-driven, not pinned-resolver-driven.
- `executor.run_agent_step` (`executor.py:443-475`) + `io_adapter.agent_step`
  (`io_adapter.py:60-81`): agent gets steering path + context dict; must return
  `{answers_to_persist: {k:{value,source:"agent-steered"}}, message}`. WORKS.
- `merge_module_answers_to_persist` (`persist.py:376-420`): folds agent answers into
  persisted maps with provenance. WORKS — reuse it, no new primitive.
- `run_gate_step` (`executor.py:396-437`): bare `{id,kind,message}` gate; `io.confirm`
  defaults No; non_interactive SAFE-skips (returns False) since f1e7269. WORKS for 003.
- **No registry-verify primitive exists anywhere** in `runner/` or `modules/`. Only
  network use: `gitignore-generate` urllib template fetch + `sources/fetch.py` git
  subprocess. → the verify helper (FR-005/007) is fully net-new.
- Init now also uses inspect→confirm→write (`pipeline.py:494-515`, f1e7269), so the
  resolver's python write gets a confirm pass in init too.

## OPEN QUESTIONS — require user input before implementation

Each is written so it can be answered without re-reading the spec. Numbered for
reference from the handover.

### OQ-1 — Split the runner contract fixes into their own spec? (HIGH) — RESOLVED 2026-06-28: option A

**User chose A: keep FR-009/010/011 inside 003.** One spec ships the runner contract +
its first consumer together. Confirmed rationale: the contract is untestable without a
real Tier-2 module to drive it. NOT extracted into a separate "003a" spec. spec.md
Status + Dependencies section + plan.md reflect this.

### OQ-2 — How should same-run agent→python visibility be implemented? (HIGH) — RESOLVED 2026-06-28: option B

**User chose B: the two-phase plan.** Run ALL `kind=agent` steps first (Phase A), fold
their decisions into resolved answers, re-freeze the plan (v2, authoritative), then run
`kind=python`/`kind=gate` steps (Phase B) reading v2. Rejected: (a) re-freeze
mid-execution — temporal hazard (the inspect/confirm pass at `pipeline.py:498` already
ran over the old plan); (c) sidecar file — bypasses the frozen-plan input channel
(shared-contracts §6). Full design in `plan.md` Phase 3 + the two subtleties below.

### Phase design + TWO SUBTLETIES discovered while designing B (durable — drives plan.md/impl)

The two-phase restructure lives in `run_pipeline` (`pipeline.py`) + a helper in
`reproduce.py`. The execute PRIMITIVES (`run_agent_step`, `run_python_step`,
`run_gate_step`) do NOT change. Current single pass: `build_drift_report(plan)`
[inspects python steps only, `reproduce.py:143`] → `apply(plan)` [dispatches all kinds].
B becomes: freeze v1 → **Phase A** (agent steps; fold answers) → **re-freeze v2** →
**Phase B** (`build_drift_report` + `apply` over python+gate only).

- **SUBTLETY 1 — the re-freeze MUST compose gate messages.** The bare gate renders a
  static `message` string (`executor.py:427`). For the pin-table gate to DISPLAY the
  resolved pins, the v2 re-freeze must template each `kind=gate` step's `message` from
  the agent decision (pins are known by then). So re-freeze does TWO things: fold
  answers AND compose gate messages. Spec-004's richer gate would carry structured data
  instead of a baked string; 003 bakes the string at re-freeze. (Design point, not a
  blocker.)
- **SUBTLETY 2 — phasing is GLOBAL, not per-module.** Today `apply` interleaves per
  module (module A's python could precede module B's agent). Global Phase A → Phase B
  means ALL agent steps run before ANY python step. Fine for the resolver (an agent
  step needs only interview answers + its own research, never another module's writes),
  but it becomes an INVARIANT: a `kind=agent` step MUST NOT depend on a Phase-B file
  write. Encode as an invariant (consistent with the Tier-2 principle), not a bug.

### AS-BUILT (2026-06-28) — how it was actually implemented (refinements vs. the sketch above)

Implemented and green (552-baseline + new tests). Three refinements emerged when
reading the runner, all SIMPLER than the plan sketch:

1. **ONE freeze, not "v1 → re-freeze v2".** The agent step receives the module's
   resolved answers as an in-process `context` dict (via `io.agent_step`), NOT the
   frozen plan — only `module.py` subprocesses read the plan. And in reproduce mode
   the committed `agent-steered` answers are ALREADY in `final_answers` (001 loads
   answers.toml as the project layer). So `run_agent_phase` runs the agent steps
   in-memory, folds decisions into `final_answers`, and THEN the existing single
   `build_plan`/`freeze` bakes them in. No v1 freeze, no double-write of plan.json.
   Faithful to option B ("agents → freeze → deterministic writes"); just no redundant
   freeze. Wired at `pipeline.py` Stage 5b (run_agent_phase) before Stage 6 (freeze),
   gated on `not dry_run`. New fn: `reproduce.run_agent_phase`.
2. **SUBTLETY 1 realized as a `{decision}` token.** A gate step's `message` may contain
   the literal `{decision}`; `plan.build_plan` replaces it with
   `contracts.render_answer_block(module_answers)` at freeze time (the answers carry
   the agent's pins by then). Shared renderer in `contracts.py` (one source, also used
   by the --refresh diff). No re-freeze needed (see #1).
3. **NEW: gate-blocking added to `reproduce.apply`** (was a real gap — a declined gate
   recorded an outcome but did NOT block the following write). Now a non-confirmed
   `kind=gate` sets a module-scoped `gate_blocked` flag that skips subsequent
   `kind=python` writes IN THAT MODULE. This is what makes the pin-table gate actually
   gate the manifest write (FR-012). `apply`'s old `kind=agent` branch now `continue`s
   (agent steps ran in Phase A) — the `run_agent` binding there is now dead (flagged in
   the leanness re-review as `dead-run-agent-binding-apply`, cut in the leanness pass).

Verify policy (in each lang module's python write step, NOT the runner — keeps the
runner generic): `verify_pins` runs ONLY when `inputs.mode == "init"`; DISCONFIRMED →
status=error, write nothing; UNREACHABLE → warning + safe-skip the write; reproduce →
no verify call (zero network). New SDK: `FrozenInputs.mode` property + `verify_pins`.

### OQ-3 — `--refresh` granularity and CLI surface (MED)

FR-010 says `--refresh <module|key>`. Open: exact CLI grammar. `--refresh lang-python`
(whole module) vs `--refresh lang-python.pinned_deps` (one key) vs `--refresh` (all
agent steps). Also: does `--refresh` imply a mode (like init/reproduce) in
`mode.py`/`cli.py`, or a flag layered on reproduce? I assumed a flag on reproduce.
Needs confirmation against the existing `cli.py` mode detection (didn't fully spec the
CLI grammar — see OQ-6 on `cli.py` not yet read in depth).

### OQ-4 — Offline-at-init verify policy: fail-closed vs defer (MED)

FR-012 says a pin that FAILED verification is fail-closed (never written), but a pin
that couldn't be REACHED (offline) is reported + SAFE-skipped. Is SAFE-skip (write
nothing, leave manifest unpinned) the right call, or should offline-init be a hard
error ("you must be online to resolve a stack the first time")? The roadmap leans
hard-verify; the 001 source-fetch path leans soft-skip-offline. I split the
difference (fail-closed on disconfirmed, skip on unreachable). User may want one
uniform rule.

### OQ-5 — Where does the resolver agent step live: on lang-* or a new shared module? (MED)

I specced the resolver as steps ADDED to `lang-python`/`lang-ts` (FR-014/015). The
roadmap says "build the resolver ONCE as a generic pattern, then instantiate." That
could instead mean a separate `stack-resolve` module that lang-* `requires`. Tension:
- **On lang-***: simplest; the framework decision lives with the overlay that uses it.
- **Separate `stack-resolve` module**: more reuse (package-add could require it too),
  but adds a module + a `requires` edge + answer-namespace plumbing across modules.
- **My lean**: steps on lang-* for 003 (concrete, testable), extract a shared module
  later if package-add needs it. The "build once" mandate is satisfied by the shared
  SDK verify helper + a shared steering doc template, not necessarily a shared module.
  User may prefer the shared module up front.

### OQ-6 — `cli.py` / `mode.py` were NOT read in depth this session (LOW — verify before impl)

I read `pipeline.py`, `reproduce.py`, `executor.py`, `io_adapter.py`, `persist.py`,
`plan.py` (build_plan signature), `sdk.py` (via Explore digest), the agent-steered
example, lang-python (full), lang-ts (via digest). I did NOT fully read `cli.py` or
`mode.py`. The `--refresh` mode wiring (OQ-3) and the "restart+resume can't reproduce
an incomplete init" edge case (spec Edge Cases / the MCP-restart flow) depend on how
mode detection + resume actually work. **Verify `cli.py`/`mode.py` before implementing
FR-010 and the MCP-recommend-restart-resume UX.** The MCP-restart flow in the
corrected decision (002 memory) assumes "resume reproduces because state is committed"
— but init writes `.project-setup/` only at persist (stage 8), so an interrupted init
has nothing to resume from. The spec's Edge Case notes this; the safe default I
specced is "proceed now with agent-knowledge pins, `--refresh` later."

## ASSUMPTIONS made (flagged so they can be corrected)

1. The bare `kind=gate` + f1e7269 non-interactive SAFE-skip is enough for 003; the
   rich G6 gate (hardness/allow-flag/inline verify status) is 004. If the user wants
   the rich gate as part of 003, scope grows (and 003 then depends on 004).
2. PyPI JSON (`pypi.org/pypi/<pkg>/json`) and npm registry (`registry.npmjs.org/<pkg>`)
   are the canonical verify endpoints, reachable via plain HTTPS GET, no auth. Not
   re-verified against current API shapes this session.
3. Reusing `merge_module_answers_to_persist` unchanged is sufficient for resolver
   answers (it is, for the persist side; the GAP is reproduce-replay + re-freeze,
   which are net-new — FR-009/011).
4. The resolver decision schema `{framework, pinned_deps, companions, rationale}` is a
   reasonable shape; the exact key names/structure are a design detail for plan.md.
5. Go/Rust are out of scope for 003 (pattern extends later). If the user wants all
   four languages in 003, scope ~doubles.

## NEXT ARTIFACTS (speckit flow)

Produced so far: `spec.md`, this `memory.md`, **`plan.md`** (phased build order with
the two-phase execution design as Phase 3). Still to author (when implementation
starts): `data-model.md` (decision schema + verify-result shape), `contracts/` (the
agent decision contract + the SDK verify-helper signature + the reproduce-replay
contract + the two-phase execution contract), `tasks.md`, `research.md` (registry
endpoint shapes + the gate-message-composition detail), `quickstart.md`,
`checklists/requirements.md`. These were intentionally deferred from the planning
session: they're produced by `/speckit.tasks` + implementation, and OQ-3/4/5 (CLI
grammar, offline policy, resolver placement) are resolved as they're written.

## Determinism rules carried from 001/002 (must hold)

- Tier-1 (kind=python) byte-identical for same answers + module version.
- Tier-2 (kind=agent) consistent-not-identical AT INIT; **frozen + replayed
  byte-identically on reproduce** (this is the fix, not the current behavior).
- Every persisted pin registry-verified in the same run; reject hallucinated/yanked.
- Research only at init or explicit `--refresh`; plain reproduce is zero-network.
