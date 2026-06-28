# Feature 004 — Gates & Review Checkpoints (memory)

Authored after 003 shipped, folding `specs/002-agentic-features/gates-analysis.md`
into a buildable spec. This file is the durable record of HOW the spec was reasoned
and WHAT needs resolution before/during implementation. Everything here is verified
against shipped code on `feat/project-setup-modular-redesign` at HEAD `7779c27`
unless marked otherwise. (The "don't trust a subagent's reading" discipline held:
the five-reader understand pass surfaced anchors; the load-bearing ones — the gate
primitive, the G2/G3/G8 module sites — were re-read line-by-line by the main thread.)

## Scope decision (what 004 is)

004 = **the gate-primitive enrichment (hardness + per-action flags + a `when`
predicate + a data-driven non-interactive resolver) + all eight gates G1–G8 from
the calibration**, including the three net-new detection subsystems (G5 overwrite,
G7 conflict, G8 secret). The user chose the full eight-gate scope (2026-06-28);
nothing is deferred to a 004-followup. 004 builds entirely **on** the 003 machinery
(two-phase plan, gate-blocking `apply`, `{decision}` composition, init
inspect→confirm→write) — it enriches the *data* gates carry, it does not rewrite the
execution model.

## VERIFIED CODE FACTS that shape the spec (read these first)

Verified by direct read of the runner + modules; the load-bearing ones were re-read
by the main thread (not a subagent).

### Fact 1 — The gate-step shape is bare and the serializer drops unknown fields

- `StepSpec` (`runner/manifest.py:68-73`) = `{id, kind, steering, message}`. No
  hardness, no flags.
- The parser (`manifest.py:447-473`) only validates `kind=gate` ⟹ has `message`
  (and `kind=agent` ⟹ has `steering`). Adding `hardness`/`allow_flag` means adding
  parse + validate here.
- **`build_plan` serializes steps as "keep only id/kind/steering/message"**
  (`plan.py:151-169`). This is the trap: a new field added to `StepSpec` but NOT
  threaded through this serializer is silently dropped from the frozen plan, and the
  executor never sees it. FR-002 calls this out explicitly.

### Fact 2 — The non-interactive resolver is ONE hardcoded rule, not data-driven

- `run_gate_step` (`executor.py:409-450`) renders the message via `io.notify`, then:
  in `non_interactive` mode it **always** `return False` (SAFE-skip,
  `executor.py:443-449`); else it calls `io.confirm(...)`.
- This is correct for a **hard** gate but cannot express **soft** (proceed in CI) or
  **informational** (never prompt). 004's FR-003 makes the resolution read
  `hardness` + the active flag set from the frozen plan. The signature must also gain
  the active-flag context (passed down from `cli.py` — see OQ-7).
- TTY default is `[y/N]` (default No), `io_adapter.TerminalIO.confirm:146-156`. A
  soft `[Y/n]` variant is net-new (FR-004).

### Fact 3 — Gate-blocking apply + `{decision}` token already exist (003)

- `reproduce.apply` (`reproduce.py:262-343`): a declined/skipped gate sets a
  module-scoped `gate_blocked` flag (`:319-324`) that skips the module's later
  `kind=python` writes (`:277-283`). 004 reuses this — a declined hard gate already
  blocks the write it guards. No change needed for the blocking itself.
- **The gate fires UNCONDITIONALLY in `apply`, regardless of mode.** `apply` calls
  `run_gate(step_dict, mod_id, io, non_interactive=…)` for every `kind=gate` step
  with NO init/reproduce check (`reproduce.py:319-321`). So today a plain
  *interactive* reproduce **re-prompts** the pin gate; in CI it SAFE-skips →
  `gate_blocked` → skips the manifest re-write. 003 implemented the *agent-step*
  zero-network replay (FR-009) but **never** suppressed the gate prompt — verified
  by `test_two_phase_resolver.py`: the reproduce tests only assert
  `agent_step == []` and that the committed value is written; none pin the gate's
  reproduce-prompt behavior. ⟹ G6's "init-only" is **net-new 004 work** (the
  `init_only` auto-proceed, FR-006a), not a 003-preserved fact. No 003 test breaks.
- `build_plan` replaces a `{decision}` literal in a gate message with
  `render_answer_block(mod_answers)` (`plan.py:159-168`). G6 enriches this *message*
  (verify-status, rationale, sources) — the gate *shape* change is only hardness/
  flags.

### Fact 4 — Init already runs the inspect pass G1/G7 need

- `run_pipeline` Stage 7 (`pipeline.py:517-539`) runs `build_drift_report` +
  `apply_reproduce` for both init and reproduce (f1e7269); Stage 5b
  `run_agent_phase` + Stage 6 freeze precede it (`pipeline.py:488-515`). So the
  inspect outcomes (the `would …` previews, the `files_written` sets) are ALREADY
  computed in init. G1 must **aggregate + show them before the writes**; G7 must
  **cross-reference `files_written` across modules**. Neither needs a new module-side
  preview API IF the inspect outcome carries enough (Assumption / OQ-3 — verify in
  plan Phase 1).

### Fact 5 — The G2/G3/G4/G8 module sites (re-read by main thread)

- **G3 (github-repo):** `module.py:178` `visibility = "--public" if public else
  "--private"`; create runs `gh repo create … --source .`; `public` is an interview
  input. Inspect emits `would create GitHub repo <full>` (`:155-156`); skip prints
  the manual `gh` command (`:125`). → a `when="public == true"` hard gate (FR-012).
- **G2 (apm-install):** `_BASELINE_MCP` hardcoded (`module.py:36`); package list =
  `[agentic_packages] + _BASELINE_MCP` (`:148-149`); runs `apm install --target
  claude,codex,agent-skills <packages>` (`:151-181`); inspect emits `would run:
  <install_cmd_str>` (`:155-160`); skip prints the manual command. `agentic_packages`
  is prepended **unvalidated**. → a hard batched gate listing every package
  (FR-010/011).
- **G4 (lang-ts):** runs `nuxi@latest init`, `create-vite`, `bun init`, then
  `bun/pnpm install` (lang-ts `module.py` ~147-212, per 003 spec) — inside the write
  step, not a separate step. → must split the scaffolder run into its own soft-gated
  step so a decline skips it while deterministic writes proceed (FR-013).
- **G8 (secrets):** `SKILL.md:125-130` "Secrets guardrail (non-negotiable)" is
  **prose to the agent**, not enforced. `io_adapter` `ask`/`ask_non_interactive`
  (`:136`) and the persist path do not match secret shapes. → a code-level matcher at
  the interview/persist boundary (FR-018/019).

## The eight gates → hardness + mechanism (the build map)

From gates-analysis §1–§3, mapped to where each attaches. "Rides machinery" = a
`kind=gate` step that just gains hardness/flags/`when`; "NEW subsystem" = detection
beyond the gate-step shape.

| Gate | Action guarded | Hardness | Mechanism |
|---|---|---|---|
| G1 | whole init plan, pre-write | soft/informational | **NEW**: aggregate the inspect pass before writes (`pipeline.py`) |
| G2 | apm-install install | hard (`allow-install`) | rides: gate step on apm-install; batched message |
| G3 | public repo create | hard (`allow-public-repo`), `when=public==true` | rides: gate step on github-repo |
| G4 | lang-* scaffolder run | soft (`no-external-generators`) | rides + **split**: scaffolder becomes its own gated step |
| G5 | destructive overwrite on re-run | hard (overwrite), soft (clean), none (create/append) | **NEW**: divergence check in reproduce drift/apply |
| G6 | Tier-2 pin write (003 gate) | hard (`allow-stack-write`), init-only prompt¹ | rides: upgrade the 003 gate message + hardness + `init_only` marker |
| G7 | shared-file write collision | informational | **NEW**: collision detector over `files_written` |
| G8 | secret persisted | hard (refuse) | **NEW**: matcher at interview/persist boundary |

¹ **"init-only prompt" ≠ "absent from the frozen plan on reproduce".** The gate step
is STILL in the frozen plan on reproduce (it must remain so the gate-blocking
machinery is intact). `init_only` (FR-006a) only changes the *runtime resolution*:
on plain reproduce `run_gate_step` **auto-proceeds** (returns confirmed, does NOT
prompt, does NOT set `gate_blocked`) so the byte-identical write replays. Do NOT
implement this by dropping the gate from the reproduce plan — that would break
gate-blocking for any gate that legitimately should block on reproduce.

**The compatibility hinge:** `StepSpec.hardness` defaults to `"hard"`. Every gate
003 already declared (the pin gate) keeps SAFE-skip-in-CI behavior unchanged until
its message/hardness is deliberately upgraded by G6. So the full 003 suite stays
green by construction (FR-021 / SC-011). The one deliberate behavior change G6 makes
— the `init_only` reproduce auto-proceed — is not covered by any 003 test (verified
above), so it too keeps the suite green.

## OPEN QUESTIONS — resolve during planning/implementation

Each is written so it can be answered without re-reading the spec. None block
authoring `plan.md`; they are design details settled as the relevant phase is built.

### OQ-1 — `when` predicate grammar (MED)

FR-006 specs `when` as one of `key`, `key == value`, `key != value` over the
module's frozen answers. Open: exact string syntax in `module.toml` (e.g.
`when = "public == true"` vs a `[steps.when]` table), type coercion (the `public`
answer is a bool/str — compare as string?), and whether `==`/`!=` is enough or a
`key in [a, b]` form is wanted for, e.g., a framework-specific gate. **Lean:** the
three minimal string forms; a TOML string `when = "public == true"` parsed by a tiny
hand-rolled splitter (no expression-language dependency — out of scope). Coerce both
sides to the answers' rendered string for comparison.

### OQ-2 — `when` over a missing answer: false, or error? (MED)

Edge Case says a `when` referencing a missing answer ⟹ false (gate dropped — never
fire on an unknown condition). Open: is silently-dropping right, or should a `when`
that names a non-existent key be a `MANIFEST_MALFORMED` authoring error (the key is
a typo)? **Lean:** validate at parse that the `when` key is a declared input of the
module (catch typos as authoring errors); at runtime a *declared-but-unset* optional
input ⟹ false (gate dropped). Distinguishes "typo" from "legitimately unset".

### OQ-3 — G1 side-effect classification + G7 collision set: does the inspect outcome carry enough? (MED — verify in plan Phase 1)

FR-008 wants `[writes file]/[network]/[creates remote]/[installs N pkgs]/[runs
external generator]` per line, and G7 wants the `files_written` set per module,
both **from the existing inspect pass** (Assumption / Fact 4). Open: does
`build_drift_report` / the module result schema already expose (a) `files_written`
paths and (b) a side-effect hint, or must the classification be derived from
step-kind + gate-hardness + parsing the `would …` string? **Verify by reading
`reproduce.build_drift_report` + the module result contract (`contracts.py`) before
coding G1/G7.** If the data is thin, the fallback is: classify from `(step.kind,
step.hardness, gate.allow_flag)` — e.g. a step gated `allow-install` ⟹
`[installs N pkgs]`, a `allow-public-repo` gate ⟹ `[creates remote]` — which keeps
the classification data-driven (no per-module literal table, the G1 failure mode).

### OQ-4 — G5 divergence detection: re-render vs recorded prior output (MED)

FR-015 gates when on-disk ≠ "the deterministic re-render of the frozen answers".
Open: is the comparison baseline (a) re-run the module's `--inspect` to get what it
*would* write now and diff against on-disk, or (b) a recorded hash of what the last
run actually wrote (a new sidecar), or (c) the drift report's existing diff? **Lean:
(a/c)** — reproduce's drift report already inspects the would-write content
(`build_drift_report`); G5 = "the drift exists AND on-disk also differs from the
*previous* frozen plan's output". Avoid a new sidecar hash file if the drift report
already distinguishes "I would change this" from "this changed under me". **Verify
what `build_drift_report` actually captures before designing G5** — this is the
subtlest of the three new subsystems (the over-gate/under-gate trap, gates-analysis
G5 failure mode).

### OQ-5 — G8 secret-shape set + override-answer plumbing (MED-LOW)

FR-018 lists `ghp_`, `sk-`, `-----BEGIN`, `AKIA`. Open: the full canonical set
(add `xoxb-`/Slack? `glpat-`/GitLab? generic high-entropy?), where the matcher lives
(a pure SDK helper `sdk.looks_like_secret(value) -> match|None`, reused by
TerminalIO + ScriptedIO + non-interactive), and how the override escape-hatch is
expressed (a per-input `allow_secret` flag in `module.toml`? a `--i-know-this-is-a-
secret <key>` CLI flag?). **Lean:** a scoped, documented prefix/shape set in `sdk.py`
(known key shapes only — avoid generic entropy heuristics that false-positive on
UUIDs/hashes); the override is a CLI flag naming the specific input key (consistent
with the per-action-flag principle, FR-005). Keep it near-zero-cost (the gate's
whole value, gates-analysis G8).

### OQ-6 — G4 step-split: where does the scaffolder run become its own step? (MED)

FR-013 requires the scaffolder (`nuxi init` etc.) be an independently-gated step
distinct from the deterministic manifest write, so a decline skips the scaffolder but
keeps the writes. Open: is this (a) two `kind=python` steps on lang-ts (scaffold →
write) with a `kind=gate` between them, or (b) one step with an internal gate-check?
**Lean: (a)** — split lang-ts's write into `scaffold` (soft-gated, runs the external
generator) + `write` (deterministic manifest), with the gate step between. This makes
the gate-blocking apply (003) do the work: decline the scaffold gate ⟹ `gate_blocked`
skips `scaffold` but NOT `write` (need to confirm the per-step granularity — current
`gate_blocked` skips ALL later python in the module; G4 wants it to skip only the
scaffold step, then *unblock* for the deterministic write). **This interaction with
the module-scoped `gate_blocked` flag needs care** — see Subtlety 1 below.

### OQ-7 — CLI flag-passing path from `cli.py` to `run_gate_step` (LOW — verify before impl)

FR-003 makes the resolver data-driven by "the active CLI flag set". Open: the
threading path — `cli.py` parses `--allow-install`/`--no-external-generators`/etc.,
which must reach `run_gate_step` (currently only gets `non_interactive: bool`).
**Verify `cli.py` + `pipeline.py`'s call into `apply`/`run_gate_step` and decide:
pass an `active_flags: frozenset[str]` (or a small `GatePolicy` object) down through
`run_pipeline` → `apply` → `run_gate_step`.** Mirrors how `non_interactive` already
threads. Read `cli.py` in full first (the 003 memory OQ-6 flagged `cli.py`/`mode.py`
were under-read — re-read for the flag surface).

## SUBTLETIES discovered while mapping (durable — drive plan.md/impl)

- **SUBTLETY 1 — G4 vs the module-scoped `gate_blocked` flag.** Today a declined gate
  sets `gate_blocked = True` and skips ALL subsequent python steps in that module
  (`reproduce.py:277-283`). G4 wants the OPPOSITE shape: decline the scaffolder gate
  ⟹ skip ONLY the scaffolder step, then STILL run the deterministic write. Options:
  (a) order the deterministic `write` BEFORE the `scaffold` gate+step (write is
  unconditional, scaffolder is the gated tail) — simplest, no flag change; (b) make
  `gate_blocked` scope to "until the next non-gated step" rather than the whole
  module. **Lean (a):** reorder so deterministic writes precede the gated scaffolder.
  This keeps the existing module-scoped blocking semantics intact (no runner change
  for G4 beyond the soft hardness). Confirm the lang-ts step order can be reshaped
  this way without breaking the manifest-then-install sequence.
- **SUBTLETY 2 — G1's "soft" must not double-confirm the hard sub-gates.** G1 is one
  soft aggregate preview; G2/G3/G6 are hard sub-gates that fire at their own steps.
  Confirming G1 must NOT auto-confirm them (that collapses to yes-to-all, anti-pattern
  5). So G1 is purely additive — a preview+proceed BEFORE the per-step gates, which
  still each fire. In CI, G1 prints (informational) and the hard sub-gates still
  SAFE-skip. The two layers are independent by design.
- **SUBTLETY 3 — `when`-dropped gates must drop deterministically on reproduce.**
  G3's `when="public == true"` is evaluated at `build_plan` against frozen answers.
  Because answers are frozen, init and reproduce evaluate identically ⟹ the same gate
  set is dropped/kept ⟹ no drift. This is why `when` is a build-time drop (the gate
  step is absent from the frozen plan), not a runtime skip — a runtime skip would
  leave the gate in the plan and risk divergent behavior.

## AS-BUILT (TBD) — how it was actually implemented

*(To be filled in during/after implementation, mirroring the 003 memory AS-BUILT
section: the refinements vs. this plan sketch, the resolved OQs, and any subtleties
that emerged when reading the runner. Empty until Phase 1 starts.)*

## ASSUMPTIONS made (flagged so they can be corrected)

1. The default `hardness="hard"` is the right compatibility hinge — every pre-004
   gate keeps SAFE-skip-in-CI behavior unchanged, so the 003 suite stays green. If a
   pre-004 gate should actually be soft, that's a deliberate per-gate upgrade, not a
   default change.
2. The inspect pass's outcomes carry enough to derive G1's side-effect classes and
   G7's collision set without a new module-side preview API (OQ-3 — verify Phase 1).
   Fallback is data-driven classification from `(step.kind, hardness, allow_flag)`.
3. The three minimal `when` forms (`key`, `key == value`, `key != value`) cover the
   004 gates (only G3 needs one: `public == true`). A richer predicate is out of scope.
4. The G8 secret-shape set (known key prefixes) is sufficient for near-zero-cost
   assurance; generic entropy heuristics are NOT added (false-positive risk on
   UUIDs/hashes/legit high-entropy config).
5. G7 is informational-only in 004 (warn + proceed in topo order); interactive
   reorder/disable is deferred (gates-analysis G7 "reorder" is out of scope).
6. The G5 divergence baseline is derivable from the existing drift report
   (OQ-4 — verify Phase 1); no new sidecar-hash artifact is introduced if avoidable.
7. Reusing the existing module-scoped `gate_blocked` semantics is sufficient for
   G2/G3/G6 (decline ⟹ skip the guarded write); G4 reshapes step ORDER rather than
   the blocking semantics (Subtlety 1).

## NEXT ARTIFACTS (speckit flow)

Produced so far: `spec.md`, this `memory.md`, **`plan.md`** (phased build order).
Still to author when implementation starts (optional, as 003 made them — 003 shipped
without contracts/data-model/research/quickstart/checklists/tasks): `data-model.md`
(the enriched `StepSpec` shape + the `GatePolicy`/active-flags shape + the secret-
shape table), `contracts/` (the gate-resolution contract + the G5 divergence
contract + the G8 matcher contract), `research.md` (the inspect-outcome capabilities
for OQ-3, the drift-report capabilities for OQ-4), `quickstart.md` ("author a gated
step" walkthrough), `checklists/requirements.md`, `tasks.md`. Defer these unless the
full speckit artifact set is wanted on 004; implementation made them optional on 003.

## Calibration rules carried from gates-analysis (must hold)

- Hardness = the worst attribute of the action on three axes (reversibility / reach /
  determinism). HARD ⟺ irreversible OR supply-chain/code-install OR destroys local
  work. SOFT ⟺ non-deterministic or network but reversible AND user opted in. NONE ⟺
  reversible AND local AND deterministic (no gate step).
- Anti-fatigue ceiling: ≤1 hard gate per blast-radius class per run, batched where
  shared. Common path surfaces G1 + at most G4.
- Hard gates fail to the SAFE action in CI (skip the consequential step), never
  auto-approve, never deadlock. Per-action opt-in flags, never a global yes-to-all.
- Frozen-replay bypasses init-only gates (G6) via the NEW `init_only` auto-proceed
  (FR-006a) — NOT a 003-preserved fact: today the gate fires unconditionally in
  `apply` (`reproduce.py:319-321`). Only `--refresh` re-triggers the gate prompt; the
  003 agent-step zero-network replay + byte-identical write (FR-009/010) are
  preserved.
