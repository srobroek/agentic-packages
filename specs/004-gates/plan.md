# Implementation Plan: Gates & Review Checkpoints

**Branch**: `feat/project-setup-modular-redesign` (continues) → likely `feat/gates`
| **Date**: 2026-06-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-gates/spec.md` + the calibration in
`specs/002-agentic-features/gates-analysis.md` + decision rationale in
[memory.md](./memory.md).

## Summary

Implement the eight-gate calibration (G1–G8) on top of the 003 runner. The work is
**enrichment + three new detection subsystems**, never a rewrite: the gate primitive,
the two-phase plan, the gate-blocking `apply`, the `{decision}` token, and the init
inspect→confirm→write path are all shipped and green. 004 gives gate steps a
`hardness` field (`hard` | `soft` | `informational`, default `hard`), per-action
opt-in/opt-out flags, and a `when` predicate; makes `run_gate_step`'s non-interactive
resolution **data-driven** by hardness + the active flag set instead of the one
hardcoded SAFE-skip; and then lands the eight gates — five that **ride** the enriched
gate-step machinery (G2/G3/G4/G6 + the G1 preview reusing the inspect pass) and three
**new subsystems** (G5 overwrite-detection, G7 conflict-detection, G8 secret-matcher).

This plan is sequenced so the **foundation lands and is proven first** (Phases 1–2),
then the gates that ride it (Phases 3–5), then the new subsystems (Phases 6–8), then
verification (Phase 9). The compatibility hinge — `hardness` defaults to `"hard"` —
means the full 003 suite must stay green after Phase 1 with **zero** behavior change
(the first gate of correctness).

## The verified facts this plan builds on (do not re-derive)

All confirmed line-by-line against shipped code on
`feat/project-setup-modular-redesign` (HEAD `7779c27`); full citations in `memory.md`.

1. **The gate-step shape is bare and the serializer drops unknown fields.**
   `StepSpec` (`manifest.py:68-73`) = `{id, kind, steering, message}`; `build_plan`
   serializes "keep only id/kind/steering/message" (`plan.py:151-169`). New fields
   must thread through BOTH the parser (`manifest.py:447-473`) AND this serializer.
2. **The non-interactive resolver is one hardcoded SAFE-skip** (`run_gate_step`,
   `executor.py:443-449`) — no per-gate data consulted. FR-003 makes it data-driven.
3. **Gate-blocking apply + `{decision}` token already work** (`reproduce.py:262-343`;
   `plan.py:159-168`) — 004 reuses both; a declined hard gate already blocks its write.
4. **Init already runs the inspect pass** G1/G7 need (`pipeline.py:517-539` Stage 7,
   f1e7269; Stage 5b/6 precede at `:488-515`) — G1 aggregates it before writes; G7
   cross-references `files_written`.
6. **The gate fires unconditionally in `apply`, every mode** (`reproduce.py:319-321`,
   no init/reproduce check) — so a plain reproduce currently re-prompts the pin gate.
   G6's "init-only" is net-new (the `init_only` auto-proceed), not preserved 003
   behavior; no 003 test pins it (verified in `test_two_phase_resolver.py`).
5. **The module sites:** github-repo public create (`module.py:178`), apm-install
   batch (`module.py:36,148-181`), lang-ts scaffolder (~`module.py:147-212`),
   SKILL.md prose-only secrets guardrail (`SKILL.md:125-130`).

## Technical Context

**Language/Version**: Python ≥3.11 via `uv` (stdlib `tomllib`, `re`, `json`). No
shell. Consistent with 001/002/003.

**Primary Dependencies**: `uv` (unchanged). No new third-party deps. The G8 secret
matcher is stdlib `re` against a documented prefix/shape set (no entropy library).
No MCP, no network primitive added (G8 is local; G1/G7 reuse the existing inspect).

**Storage**: Unchanged. The frozen `plan.json` gains additive gate fields
(`hardness`, `allow_flag`, `skip_flag`, and `when` is resolved away at build so it
never appears in the frozen plan). Committed `.project-setup/{sources,answers}.toml`
unchanged. G8 ensures secrets never reach `answers.toml`.

**Testing**: pytest via `uv run --with pytest pytest -q` (the existing CI contract).
New doubles needed: (a) a **stdin-blocking IO** to prove no non-interactive gate
calls `input()` (extends the `test_gate_non_interactive` precedent); (b) ScriptedIO
flag-set injection to exercise hard/soft/informational × allow/skip flag combinations;
(c) a fixture that writes a divergent on-disk file for G5; (d) two-module collision
fixtures for G7; (e) secret-shaped input values for G8.

**Target Platform**: macOS + Linux dev + CI under Claude Code, Codex, `apm install`.
Unchanged.

**Project Type**: CLI tool + agent skill (unchanged).

**Performance Goals**: Not latency-bound. G1 adds one render of already-computed
inspect data; G7 adds an O(modules × files) collision scan over the same data; G8
adds N regex matches per interview. All negligible.

**Constraints**: The blast-radius→hardness mapping and the anti-fatigue ceiling are
binding (Settled Decision F). At most one hard gate per blast-radius class per run,
batched where shared; the common path surfaces G1 + at most G4. No non-interactive
path may call `input()`. No global yes-to-all flag (FR-005). The 003 contract
(two-phase, reproduce-replay, gate-blocking) is preserved unchanged (FR-021).

## Constitution Check

The project constitution (`.specify/memory/constitution.md`) is an unfilled template
— no ratified principles to gate against (same as 001/003). This plan gates on the
spec's binding decisions (A–H), the gates-analysis calibration (§2 hardness rule, §3
CI policy, §4 anti-patterns as binding non-goals), and the 001 shared contracts
(unchanged — 004 is additive to the gate-step shape). The one place 004 *extends* a
001 contract is the `StepSpec`/frozen-plan gate shape; that extension is additive and
backward-compatible (default `hardness="hard"`), documented here rather than silently
changing `manifest.py`.

## Phase 1 — Gate-primitive foundation (BLOCKING; the compatibility hinge)

The enrichment every gate rides. Land it and prove the 003 suite stays green BEFORE
any gate is added. All in `manifest.py` + `plan.py` + `executor.py` + `cli.py`.

1. **`StepSpec` + parser (FR-001, FR-002, FR-006, FR-006a)** (`manifest.py`): per
   Settled Decision A, add `hardness: str = "hard"` (FR-001), `allow_flag: str | None`
   + `skip_flag: str | None` (FR-002), `when: str | None` (FR-006), and
   `init_only: bool = False` (FR-006a). Parse from `[[steps]]`; validate
   `hardness ∈ {hard, soft, informational}` (else `MANIFEST_MALFORMED`, mirroring the
   `kind` validation at `manifest.py:438-444`). Validate the `when` key is a declared
   input of the module (catch typos — OQ-2).
2. **Frozen-plan serializer (FR-002, FR-006)** (`plan.py:151-169`): thread
   `hardness`/`allow_flag`/`skip_flag`/`init_only` into the step dict (the "keep only
   id/kind/steering/message" site — Fact 1; FR-002 names this as the silent-drop
   trap). **Resolve `when` HERE** (Settled Decision D) against `mod_answers`: false ⟹
   drop the gate step from the frozen plan entirely (FR-006, Subtlety 3 — build-time
   drop, not runtime skip). A tiny hand-rolled predicate splitter
   (`key` / `key == v` / `key != v`), no expression-language dep (OQ-1).
3. **Data-driven resolver (FR-003, FR-004, FR-006a)** (`executor.run_gate_step`):
   replace the hardcoded `non_interactive → return False` (`executor.py:443-449`) with
   the §3 table (FR-003) — resolve from `step["hardness"]` + an `active_flags` set:
   hard → skip unless `allow_flag ∈ active_flags`; soft → proceed unless
   `skip_flag ∈ active_flags`; informational → notify + proceed. Add the
   `init_only` mode-aware bypass (FR-006a): mode `reproduce` + module not in
   `--refresh` ⟹ auto-PROCEED (not skip), so the consented frozen decision replays
   without prompting or blocking. Add the TTY `[Y/n]` soft variant (FR-004); hard
   stays `io.confirm` `[y/N]`. A standing `allow_flag`/`skip_flag` in a TTY
   pre-resolves (no prompt).
4. **Flag threading (FR-005)** (`cli.py` → `pipeline.py` → `apply` →
   `run_gate_step`): parse the per-action flags (`--allow-install`,
   `--allow-public-repo`, `--allow-stack-write`, `--no-external-generators`); pass an
   `active_flags: frozenset[str]` (or a small `GatePolicy`) down the same path
   `non_interactive` already travels (OQ-7). **No global `--yes`** (Settled Decision
   C / FR-005).
5. **Tests**: round-trip a soft+`skip_flag` step through parser+serializer (SC-001);
   reject an unknown hardness; resolver returns the three correct outcomes ×
   flag-on/off in non-interactive with a stdin-blocking IO (SC-002); a
   `when="public == true"` gate is dropped when `public=false` (SC-005 half); the
   OQ-2 lean — a `when` on a declared-but-unset optional input ⟹ false (gate dropped),
   a `when` with a typo'd key ⟹ `MANIFEST_MALFORMED` at parse; an `init_only` gate on
   plain reproduce auto-proceeds (no prompt, write replays) but prompts under
   `--refresh` (FR-006a).

**Resolve before coding Phase 1:** read `cli.py` + `mode.py` in full (003 memory
OQ-6 flagged them under-read) so the flag-parse surface and the `apply`/
`run_gate_step` call path are pinned (OQ-7). **Gate Phase 1 on: the full 003 suite
green, unchanged** — the default `hardness="hard"` MUST make every pre-004 gate
behave identically (FR-021 / SC-011). If any 003 test changes, the default is wrong.

## Phase 2 — G1 whole-plan preview (the cheapest high-value gate)

Reuses the inspect pass already run in init (Fact 4). All in `pipeline.py` +
a render helper (`contracts.py` or a small `preview.py`).

1. **Aggregate the inspect outcomes (FR-007)** from `build_drift_report` (already
   computed, `pipeline.py:517-539` Stage 7) into an ordered, per-module checklist
   BEFORE the writes in init mode. Reuse each step's `would …` preview string — never
   a parallel literal (Settled Decision E; the G1 failure mode).
2. **Side-effect classification** (FR-008): per line, derive `[writes file]` /
   `[network]` / `[creates remote]` / `[installs N pkgs]` / `[runs external
   generator]`. **Resolve OQ-3 first** — read `build_drift_report` + the module
   result contract (`contracts.py`) to see what the inspect outcome exposes; if thin,
   classify from `(step.kind, step.hardness, allow_flag)` (data-driven, no per-module
   table — e.g. an `allow-install` gate ⟹ `[installs N pkgs]`).
3. **The G1 gate** (FR-009): soft/informational. TTY → one confirm to proceed
   (decline = abort, nothing written); MAY offer "proceed but skip module X". CI →
   print the plan and proceed (never blocks). G1 does NOT auto-confirm the hard
   sub-gates (Subtlety 2 — they still fire at their steps).
4. **Tests**: init renders the preview from the inspect pass with a class per line
   before any write; declining writes nothing; CI prints + proceeds (SC-003); G1
   confirm does not suppress a downstream hard gate.

## Phase 3 — G3 public-repo gate + G2 batched install gate (the hard rides)

Declarative gate steps on the modules; both ride Phase 1's machinery.

1. **G3 (github-repo)**: add a `kind=gate` step before the create step —
   `hardness="hard"`, `allow_flag="allow-public-repo"`, `when="public == true"`,
   message `Create PUBLIC GitHub repo {org}/{name}? World-visible, name claimed
   immediately.` (`{org}`/`{name}` via the existing message-composition or a
   `{decision}`-style token). Private (`public=false`) ⟹ `when` drops the gate
   (FR-012). Decline ⟹ existing `gate_blocked` skips the create; the manual `gh`
   command already prints (`module.py:125`). (SC-005.)
2. **G2 (apm-install)**: add a `kind=gate` step before the install —
   `hardness="hard"`, `allow_flag="allow-install"`, message = the full package list,
   one `name@marketplace` per line, grouped "baseline (always)" (`_BASELINE_MCP`,
   `module.py:36`) vs "you/agent selected" (`agentic_packages`), **never truncated**
   (FR-010). Compose the list at build (it is known from frozen answers + the
   hardcoded baseline). Decline ⟹ skip install, print the manual command
   (`module.py` skip path). CI without `--allow-install` SAFE-skips (FR-011). (SC-004.)
3. **Tests**: G3 present+safe-skipped in CI for public / dropped for private; G2
   lists every package untruncated, CI safe-skips without the flag and installs with
   it.

## Phase 4 — G6 upgrade the 003 pin gate (hard, init-only prompt)

Enrich the EXISTING lang-* pin gate + add the `init_only` reproduce bypass. Relies
on the Phase-1 foundation (`hardness`, `allow_flag`, `init_only`); no new module step.

1. **Hardness + flag (FR-014)**: set the lang-python / lang-ts `pins` gate to
   `hardness="hard"`, `allow_flag="allow-stack-write"`, `init_only=true`. Default-hard
   already made it SAFE-skip in CI (003 behavior) — this names the opt-in flag so CI
   *can* perform it.
2. **Richer message (FR-014)**: extend the `{decision}` render
   (`contracts.render_answer_block`, `plan.py:159-168`) so the pin table shows per-pin
   `name@version` + verify-status + downgrade reason + the agent's rationale + sources
   (the agent already emits rationale; thread verify-status from the 003 `verify_pins`
   result into the rendered block).
3. **`init_only` reproduce bypass (FR-006a)** — the corrected mechanism: today the
   gate fires UNCONDITIONALLY in `apply` (`reproduce.py:319-321`, no mode check), so a
   plain *interactive* reproduce re-prompts the pin gate (verified — no 003 test pins
   this). `init_only=true` makes `run_gate_step` **auto-PROCEED** (not skip) when mode
   is `reproduce` and the module is not in `--refresh`: no prompt, `gate_blocked` not
   set, the byte-identical write replays (003 FR-009 agent-replay preserved). Only
   `--refresh` re-triggers the prompt (003 FR-010). This is NEW 004 behavior, not a
   003-preserved fact — do NOT implement it by dropping the gate from the reproduce
   plan (that breaks gate-blocking; see memory.md footnote ¹).
4. **Tests**: pin gate shows verify-status + rationale + sources; CI safe-skips the
   write without `--allow-stack-write`, writes with it; plain reproduce auto-proceeds
   (no prompt, write replays byte-identical) and `--refresh` re-prompts (SC-007). The
   003 reproduce suite (`test_two_phase_resolver.py`) stays green.

## Phase 5 — G4 external-generator gate (soft, requires a step-split)

The one gate needing a module reshape (Subtlety 1 / OQ-6).

1. **Split the lang-ts write** (FR-013): separate the external scaffolder run
   (`nuxi init` / `create-vite` / `bun init`) from the deterministic manifest write.
   Per **Subtlety 1 (memory.md)**: **order deterministic `write` BEFORE the soft-gated
   `scaffold`** (option a) so a declined scaffold gate skips ONLY the scaffolder while
   the manifest is already written — reusing the existing module-scoped `gate_blocked`
   semantics unchanged (rather than rescoping `gate_blocked`, which would change 003
   blocking for every module).
2. **The G4 gate**: `kind=gate`, `hardness="soft"`, `skip_flag="no-external-
   generators"`, message names the exact command + the `--force`/overwrite hazard.
   TTY `[Y/n]` (default Yes); CI proceeds unless `--no-external-generators` (FR-013).
3. **Tests**: TTY confirms the named command; CI runs the scaffolder by default and
   skips it under `--no-external-generators` while the deterministic manifest still
   writes (SC-006).

## Phase 6 — G8 secret-detected abort (hard, new matcher)

The near-zero-cost assurance gate; enforces the prose SKILL.md guardrail.

1. **`sdk.looks_like_secret(value) -> match | None`** — a pure SDK helper matching a
   documented prefix/shape set (`ghp_`, `sk-`, `-----BEGIN`, `AKIA`, … — OQ-5), no
   entropy heuristics (false-positive risk). Reused by TerminalIO + ScriptedIO + the
   non-interactive path.
2. **Enforce at the interview/persist boundary** (FR-018/019): when an input value
   matches, refuse to persist (drop the value, never write to `answers.toml`), fail
   the input (MISSING_ANSWER if required), tell the user to rotate it. CI never
   silently persists a suspected secret. The override escape-hatch = a CLI flag
   naming the specific input key (OQ-5; consistent with FR-005's per-action principle).
3. **Tests**: each shape is refused + not written + prompts rotation; an overridden
   value passes (SC-010). Replaces the SKILL.md prose with a real checkpoint.

## Phase 7 — G7 cross-module conflict review (informational, new detector)

A collision scan over the inspect data; warns, never blocks.

1. **Collision detector** (FR-017): over the inspect pass's per-module `files_written`
   (OQ-3 — confirm the data is exposed), find paths written by ≥2 modules
   **non-idempotently**. Marker-guarded append-if-absent collisions are benign — do
   NOT flag them (no false-positive fatigue). A destructive collision escalates via
   G5, not G7.
2. **Surface informationally**: warn, name the contended path + the resolved topo
   order, proceed (deterministic). No prompt, no block (gates-analysis G7 hardness).
3. **Tests**: two non-idempotent writers of one path ⟹ one warning naming path+order;
   two marker-guarded appends ⟹ none (SC-009).

## Phase 8 — G5 destructive-overwrite gate (hard, new divergence check)

The subtlest subsystem (the over-gate/under-gate trap) — built last, after the
foundation and the simpler gates are proven.

1. **Divergence detection** (FR-015): **resolve OQ-4 first** — read
   `build_drift_report` to see what it captures, then gate when on-disk content
   diverges from the deterministic re-render AND the new write differs (local edits
   present + a real change). Avoid a new sidecar-hash artifact if the drift report
   already distinguishes "I would change this" from "this changed under me".
2. **The escalated gate**: `hardness="hard"`, message `OVERWRITE — <path> has local
   changes that will be lost`; offer confirm/skip/diff in TTY. create-new,
   append-if-absent, and clean modifies stay soft/none (FR-015).
3. **CI policy** (FR-016): a true destructive overwrite SAFE-skips the file
   (preserve local edits), records a skipped diff, continues — CI never silently
   destroys local work.
4. **Tests**: a divergent on-disk file ⟹ overwrite gate; CI safe-skips + preserves
   edits; append/create unaffected (SC-008).

## Phase 9 — Verification + docs

1. Full suite green (the ~7-min real-`uv-run` suite; run in background):
   `uv run --with pytest pytest -q packages/project-setup/tests/ -k 'not SuccessfulGitFetch'`.
   The 003 subset MUST be unchanged-green (FR-021 / SC-011 — the compatibility hinge).
2. SKILL.md additions: the hardness model + the per-action flags, the G1 preview,
   what each gate guards, and the CI policy (hard → safe-skip + opt-in flag; soft →
   proceed + opt-out flag; informational → print). Move the secrets guardrail from
   prose to "enforced by G8". Thin-config / thick-process (unchanged H2 rule).
3. Confirm the anti-fatigue ceiling end-to-end (FR-020, Settled Decision F): a
   private-repo + deterministic-scaffold + opt-in-overlay run surfaces only G1 + at
   most G4 (no per-file confirm, no gating of deterministic local writes — the binding
   non-goals). Confirm all eight gates honor the blast-radius→hardness mapping.
4. Confirm the 003 determinism rules still hold: reproduce zero-network + byte-
   identical; `--refresh` the only re-research path; `when`-dropped gates drop
   deterministically (Subtlety 3).

## Project Structure

### Documentation (this feature)

```text
specs/004-gates/
├── plan.md              # this file
├── spec.md              # the spec (all 8 gates, foundation + G1–G8)
├── memory.md            # verified facts, the gate→hardness build map, OQs, subtleties
├── contracts/           # (optional, author at impl start, as 003 did):
│                        #   gate-resolution.md, g5-divergence.md, g8-matcher.md
├── data-model.md        # (optional) enriched StepSpec + GatePolicy + secret-shape table
├── research.md          # (optional) inspect-outcome capabilities (OQ-3) + drift-report (OQ-4)
├── quickstart.md        # (optional) "author a gated step" walkthrough
├── checklists/requirements.md   # (optional)
└── tasks.md             # produced by /speckit.tasks (NOT this command)
```

### Source code touched (repository root)

```text
packages/project-setup/skills/project-setup/
├── runner/
│   ├── manifest.py     # StepSpec + parser: hardness/allow_flag/skip_flag/when (Phase 1)
│   ├── plan.py         # serializer threads new fields; resolve `when` at build (Phase 1)
│   ├── executor.py     # run_gate_step: data-driven resolver + [Y/n] soft variant (Phase 1)
│   ├── cli.py          # per-action flags; thread active_flags down (Phase 1; read in full — OQ-7)
│   ├── pipeline.py     # G1 aggregate preview before writes (Phase 2); G7 collision scan (Phase 7)
│   ├── reproduce.py    # G5 divergence detection in drift/apply (Phase 8)
│   ├── io_adapter.py   # [Y/n] soft confirm variant (Phase 1); G8 enforcement (Phase 6)
│   ├── contracts.py    # G6 richer pin-table render; G1 preview render helper (Phase 2/4)
│   └── sdk.py          # sdk.looks_like_secret() matcher (Phase 6)
└── modules/
    ├── github-repo/    # G3 public-repo gate step (when=public==true) (Phase 3)
    ├── apm-install/    # G2 batched install gate step (Phase 3)
    ├── lang-python/    # G6 pin gate → hard + allow-stack-write (Phase 4)
    └── lang-ts/        # G6 pin gate → hard; G4 split scaffold/write + soft gate (Phase 4/5)
```

**Structure Decision**: 004 is additive to the gate-step shape (four new optional
fields) + a data-driven resolver + three new detection passes. No new module
directory, no schema-breaking change, no new persistence primitive. The five "rides"
gates (G1/G2/G3/G4/G6) are declarative gate steps + the Phase-1 foundation; the three
"new subsystem" gates (G5/G7/G8) attach to existing passes (drift report, inspect
collision, interview/persist) rather than new top-level machinery.

## Complexity Tracking

| Decision | Why needed | Simpler alternative rejected because |
|----------|------------|--------------------------------------|
| `hardness` field defaulting to `"hard"` on every gate step | The non-interactive resolver must be data-driven (soft proceeds in CI, hard safe-skips) without hardcoding per-gate behavior in the executor; default-hard keeps the 003 suite green | A separate `soft_gate` step kind: doubles the kind enum, splits the gate code path, and a 003 gate would need migrating; the additive field with a safe default is backward-compatible by construction |
| `when` resolved at build (gate dropped from frozen plan), not at runtime | G3 must be "hard for public, none for private" deterministically; answers are frozen, so build-time eval is identical on init and reproduce (no drift) | A runtime skip leaves the gate in the frozen plan and risks init/reproduce divergence; a fourth `"none"` hardness value conflates "no gate" with "conditional gate" and still needs the predicate |
| G4 splits lang-ts into deterministic `write` (first) then soft-gated `scaffold` | The scaffolder must be skippable in CI while the deterministic manifest still writes; ordering writes first reuses the existing module-scoped `gate_blocked` unchanged | Making `gate_blocked` scope to "until the next non-gated step" changes the 003 blocking semantics for every module — riskier than reordering one module's steps |
| Per-action opt-in flags, no global `--yes` | A blanket yes-to-all auto-approves the public repo + the install + the pin write together — exactly the actions that must stay individually consented (anti-pattern 5) | A global `--confirm-all` is convenient but collapses the hardness distinction; per-action flags keep each hard action's CI opt-in explicit and auditable |
| G1 reuses the existing inspect pass, never a hand-written preview literal | The inspect data is already computed in init (f1e7269); a parallel literal drifts from what the code actually does (the named G1 failure mode) | Hand-maintained per-module preview strings: drift silently, and the whole point of G1 is a *faithful* whole-picture checkpoint |
| G5 built last, after OQ-4 verifies the drift-report capabilities | Destructive-overwrite detection is the over-gate/under-gate trap; building it on a verified understanding of what the drift report captures avoids a fragile divergence heuristic | Building G5 first (before the foundation is proven) risks a wrong divergence baseline (e.g. a new sidecar-hash artifact) that the simpler gates would have informed |
