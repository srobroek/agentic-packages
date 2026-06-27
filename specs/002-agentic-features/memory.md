# Feature 002 — Module enablement layer (memory)

**SCOPE DECISION: 002 = enablement layer ONLY** (smallest coherent piece + the
connective tissue the others need). Tier-2 stack-resolver → future spec 003;
gates → future spec 004. The Tier-2 roadmap + gates-analysis below are INPUTS
for 003/004, retained here for continuity, not 002 scope.

Net-new capability phase, AFTER the 0–5 migration (spec 001) ships.

## 002 scope (enablement layer)

1. **Module enablement layer** (Task #7). Confirmed gap: `default_enabled` is
   validated but NEVER used as a run filter — the pipeline runs every discovered
   module; no "which capabilities?" selection step exists. User-steered design:
   - Minimal deterministic floor: shrink `default_enabled=true` to the irreducible
     scaffold only (identity, dirs, gitignore, license, agents-md, git-init).
   - `default_enabled` becomes a REAL pipeline filter (only base + explicitly
     enabled modules run).
   - Agent-LED selection via SKILL.md grilling instructions (agent suggests which
     optional modules to enable from user intent) — NOT a rigid python interview.
   - Selection recorded as answers (`[modules].enabled`) for reproducibility.

2. **Tier-2 agentic features** (roadmap: reviews/tier2-agentic-features-roadmap.md).
   Top ranked: #1 stack-resolver (framework + companion-libs + version pinning via
   live research, instantiated for py + ts — the feature the user named); #2
   py-toolchain-pin-resolve; #3 --refresh/re-research gate. Core pattern (every
   Tier-2 op): agent researches + picks among options → freezes a structured
   decision → gate shows it → a deterministic python step writes the pinned
   manifest. Research (context7 / package-version MCP / whats-new) happens ONCE at
   init, then freezes; reproduce replays frozen answers, zero network.

3. **Gates** (gates-and-review survey re-running — task wddbxhqia). Feeds the gate
   calibration: which blast radii (dependency-manifest write, external generator,
   public-repo create, N-package install, shared-file mutation) earn a hard gate
   vs soft/auto-approvable vs none, without gate fatigue / CI deadlock.

## VERIFIED foundations (so the spec doesn't re-litigate)

- The agent/gate execution path WORKS end-to-end: `executor.run_agent_step`
  delegates to `io.agent_step`; `reproduce.py:331` dispatches `kind=agent`;
  `persist.merge_module_answers_to_persist` folds an outcome's
  `answers_to_persist` into the persisted answers with correct value + provenance.
  Direct test confirmed: `{readme_intro: {value, source:"agent-steered"}}` →
  persisted with `agent-steered` provenance. (An earlier full-pipeline test
  LOOKED broken but was test-author error — the scripted agent_responses didn't
  match the example module's actual step keys; the merge itself is correct.)
- The Tier-2 demonstrators exist: examples/agent-steered (kind=agent + steering/)
  and examples/multi-step-python (STEP_HANDLERS dispatch on --step). Both are
  siblings of modules/, never discovered as real modules.
- `default_enabled` is already a tri-state Optional[bool] in the manifest +
  enforced first-party-only in discovery — so the enablement filter has the data
  it needs; it's the PIPELINE that doesn't consume it yet.

## Determinism rules carried from 001 (must hold)

- Tier-1 (kind=python) byte-identical for same answers + module version.
- Tier-2 (kind=agent) consistent-not-identical; decision frozen + replayed.
- New rule from the roadmap: every persisted pin must be registry-verified in the
  same run (reject hallucinated/yanked/typosquat versions); index-url allowlist;
  research only at init, never on plain reproduce (only `--refresh` re-researches).

## Open inputs before authoring the spec

- Gates survey (wddbxhqia) — the gate calibration table + non-interactive policy.
- Decision: sequence enablement-layer vs stack-resolver first (enablement is the
  connective tissue; stack-resolver is the headline value — likely enablement
  first since stack-resolver needs the "which optional modules" selection to exist).

## Gates analysis (DONE — specs/002-agentic-features/gates-analysis.md)

First workflow run crashed (API error); second returned STUB "test" values
(unusable); a third direct agent run produced the real analysis: 8 calibrated
gate opportunities (whole-plan preview, consolidated supply-chain install
approval, public-repo confirm, external-generator confirm, destructive-overwrite
confirm, Tier-2 agent-decision review, cross-module conflict review, secret-
detected abort), a blast-radius→hardness calibration rule (3 axes: reversibility
/ reach / determinism; only irreversible-or-supply-chain-or-destructive earn
hard gates; clean local run = ≤1-2 prompts), and a CI policy (hard gate in CI →
SAFE-skip the consequential step, never auto-approve, never deadlock).

### TWO VERIFIED CODE FINDINGS (required fixes for the gates feature; confirmed against shipped code)

1. **Init mode has NO confirm pass.** `pipeline.py` init branch (~line 426,
   comment: "run all steps directly (no pre-write confirm pass)") runs gh repo
   create / apm install / external generators with ZERO confirmation. Only
   REPRODUCE mode has the per-file --inspect+confirm loop. The gates feature must
   add a confirm pass to init mode (or unify init through the reproduce path).
2. **`run_gate_step` has no non-interactive handler.** It delegates to
   `io.confirm` → `TerminalIO.confirm` calls `input()`, so a gate in CI BLOCKS on
   stdin (deadlock). The earlier `ask_non_interactive` fix covered the interview,
   NOT gates. The gates feature must add a non-interactive gate resolution
   (SAFE-skip per the CI policy).

Neither is a migration correctness bug (parity tests pass); both are gaps that
block the gates feature. Fold into the 002 spec as required fixes.
