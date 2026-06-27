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

### OQ-1 — Split the runner contract fixes into their own spec? (HIGH — affects spec count)

FR-009/010/011 are runner-library changes (`reproduce.py`, `pipeline.py`, `plan.py`,
`cli.py`), not module work. I bundled them into 003 because a Tier-2 module is the
only thing that exercises them and they're meaningless alone. **But** they are
arguably a "Tier-2 runner contract" spec that should land BEFORE the resolver module,
matching the roadmap's "build #3 refresh-gate as the structural guarantee" framing.
- **Option A (chosen in draft)**: keep them in 003; one spec ships the contract +
  first user together.
- **Option B**: extract a spec 003a "Tier-2 runner contract" (reproduce-replay +
  --refresh + re-freeze), ship it first, then 003 becomes pure module work.
- **My lean**: A, because the contract is untestable without a real Tier-2 module to
  drive it — but this is the user's call on spec granularity.

### OQ-2 — How should same-run agent→python visibility be implemented? (HIGH — core design)

FR-011 needs the agent's decision to reach a later python step via the frozen plan.
Three implementable shapes, each with a cost:
- **(a) Re-freeze mid-execution**: after each agent step, fold `answers_to_persist`
  into `resolved_answers`, rebuild + re-freeze the plan, continue. Simple mental
  model; but the plan is currently frozen once and `build_drift_report` already ran
  the inspect pass over the OLD plan — ordering gets subtle (the inspect/confirm pass
  in `pipeline.py:498` happens before any agent step runs).
- **(b) Two-phase plan**: run agent steps FIRST (a pre-pass), fold their answers, THEN
  freeze the plan once and run the inspect→confirm→write over python+gate steps. Clean
  separation; changes the execution loop structure in `pipeline.py`.
- **(c) Sidecar decision file**: agent writes its decision to a cache file the python
  step reads (NOT via the plan). Rejected — violates shared-contracts §6 ("agent args
  /channels are never an input channel"; the frozen plan is the sole input).
- **My lean**: (b) — it matches "research happens, freezes, then deterministic writes"
  and keeps one freeze. But it's a real change to the execute loop; needs user/plan
  sign-off. Flagging because it's the highest-risk part of 003.

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

## NEXT ARTIFACTS (speckit flow) — not yet produced

This session produced `spec.md` + this `memory.md` ONLY. Still to author (when the
user confirms scope / answers the HIGH OQs): `plan.md`, `data-model.md` (decision
schema + verify-result shape), `contracts/` (the agent decision contract + the
SDK verify-helper signature + the reproduce-replay contract), `tasks.md`, `research.md`
(registry endpoint shapes + the re-freeze design from OQ-2), `quickstart.md`,
`checklists/requirements.md`. I deliberately stopped at spec+memory because OQ-1/OQ-2
(spec granularity + the core re-freeze design) change everything downstream.

## Determinism rules carried from 001/002 (must hold)

- Tier-1 (kind=python) byte-identical for same answers + module version.
- Tier-2 (kind=agent) consistent-not-identical AT INIT; **frozen + replayed
  byte-identically on reproduce** (this is the fix, not the current behavior).
- Every persisted pin registry-verified in the same run; reject hallucinated/yanked.
- Research only at init or explicit `--refresh`; plain reproduce is zero-network.
