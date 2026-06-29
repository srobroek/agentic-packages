# Autonomous Drive — Decision Log

Running log of decisions, ambiguities, and deviations made while driving the
project-setup spec queue autonomously (started 2026-06-28). **For human review when
back.** Newest entries appended at the bottom of each section. Nothing here is a
blocker that stopped the drive; items tagged ⚠️ REVIEW want a second look.

## Standing decisions (confirmed with user before the drive)

- **008 pivot**: drop `brownfield_skip` inputs entirely; standardize a brownfield
  probe across ALL modules in a NEW spec **017**, which 008 then consumes. (User chose
  "split into new SDK spec" + "migrate every module exhaustively".)
- **gitignore-generate**: existing `.gitignore` → **append-only merge** (preserve user
  lines, append missing stack lines, dedup). Not skip-entirely.
- **Brownfield gate**: advisory `~ preserve (existing): …` annotation, informational
  (not declinable — files preserved deterministically regardless).
- **reproduce.py reuse (008 OQ-1)**: extract shared `_run_one_agent_step` helper; both
  Stage 5b and Stage 3c call it. Add `skip_ids` so brownfield isn't double-run.
- **G8 secret detection**: keep curated anchored-regex `looks_like_secret`; cherry-pick
  additional **anchored** provider shapes from gitleaks (MIT). NO library dep
  (detect-secrets pulls requests+pyyaml; trufflehog is a Go/AGPL subprocess). NO
  generic/entropy rules (their precision is keyword+entropy+allowlist, not the regex).
- **Specs 006/010/011**: flipped Draft→Implemented (adversarially verified built+green).
- **No tasks.md / 005 no plan.md**: NOT gaps — intentional plan-then-delegate
  convention; 005 was a direct-from-spec refactor. (Optional hygiene: document the
  convention so a future reviewer doesn't flag the absent tasks.md / the lone 001
  tasks.md as drift. Deferred — low priority.)

## Autonomous decisions during implementation

### 017 Phase 1 (SDK foundation)

- **Probe API (OQ-1)** → resolved BOTH ways per the lean: `brownfield_probe` is the
  pure read-only detector; `idempotent_write` gained a `merge=True` policy for the write
  path. No human input needed (implementer-resolvable, leaned in plan).
- **`[brownfield]` granularity (OQ-2)** → module-level table with `artifacts =
  [{path, policy}]`; parser also accepts `[[brownfield]]` array-of-tables for
  consistency with the existing toml style. Implementer-resolvable.
- **merge on non-UTF-8 existing file** → falls back to reconcile/skip (never raises).
  Acceptable per FR-009 "never raises". ⚠️ REVIEW (minor): no module writes binary
  today, so untested in practice. Note if a binary-writing module ever appears.

#### coder edits OUTSIDE the Phase-1 brief — VERIFIED SOUND (no action needed)

1. **`manifest.py`: added `_empty_manifest(errors)`** — ✅ VERIFIED a real latent bug.
   In HEAD the function was *called* (manifest.py:151, on malformed-TOML) but had **0
   definitions** → a `NameError` would fire on any malformed module.toml. No test
   exercised the malformed-TOML path, so it stayed hidden. The fix is correct. Optional
   follow-up: add a malformed-TOML test to lock it (low priority; trivial factory fn).
2. **`tests/test_contracts.py`: added `if name in sys.modules: return` cache guard** —
   ✅ VERIFIED sound, NOT regression-masking. Confirmed **all ~30 other test loaders
   already have this exact guard**; test_contracts.py was the lone outlier. The new
   test file (alphabetically before test_contracts) loads `sdk` at collection, and
   test_contracts's unconditional re-exec then created a SECOND `contracts` module with
   distinct `SetupError`/`GateFailure` classes, breaking `pytest.raises` identity in
   test_sdk.py. The guard makes it consistent with every sibling. Legitimate isolation fix.

17 P1 GATE: full suite **687 passed, 4 deselected** (648→687, +39, zero regressions).
Committed `5868661`.

### 017 Phase 2 (migrate write-if-absent modules) — scope decisions

The survey showed Phase 2 is lower-risk than first framed: most Group-A modules ALREADY
use `idempotent_write` (brownfield-safe); only git-init + package-add have genuine ad-hoc
existence checks for a project artifact.

- **DECISION (autonomous): `[brownfield]` policy mirrors each module's CURRENT
  `reconcile` setting** — `reconcile=False` ⇒ `policy="preserve"`, `reconcile=True` ⇒
  `policy="overwrite"`. This obeys 017 FR-007 (preserve existing observable behavior;
  only gitignore-generate changes). The declaration's value: it gives 008's Stage 3c the
  manifest-level data to enumerate "which artifacts each enabled module touches + whether
  they exist" for the advisory gate annotation, computed from manifests + probe BEFORE
  any module runs.

- **⚠️ REVIEW — deferred broader question (NOT acted on; would exceed approved 017
  scope):** three modules write with `reconcile=True` and therefore OVERWRITE an existing
  user file in a brownfield repo, same clobber-class as gitignore:
    - `precommit-setup` → `.pre-commit-config.yaml` (a user may hand-customize this — the
      strongest candidate to switch to preserve/merge).
    - `quality-hooks` → `.agents/hooks/quality-languages` (a tool-MANAGED generated
      sorted-list; overwrite is arguably correct — it's ours, not user content).
    - `dirs-scaffold` → `.gitkeep` (empty files; overwrite harmless/idempotent).
    - `env-example` → `.env.example` (`reconcile=inputs.reconcile`, default true).
  My lean: leave all as-is for 017 (spec only mandated gitignore). If you want brownfield
  to also stop clobbering `.pre-commit-config.yaml`, that's a small follow-up (declare it
  `merge` or `preserve`) — flagging because it's a judgement call about user-owned vs
  tool-managed files, not a mechanical migration.

- **DECISION (autonomous): core-identity, apm-install, github-repo get NO `[brownfield]`
  declaration** — they write no local project artifact (record answers / run apm+gh
  subprocesses). 017 FR-006 scopes migration to "every module that WRITES a project
  artifact", so this is in-spec, not a gap in "exhaustive". Noted for transparency.

## ⛳ PIVOT: brownfield DEFERRED to stage 2 (user, 2026-06-28) — greenfield prioritized

Mid-Phase-2 the user asked "do we even need `[brownfield]`?" then "maybe brownfield is
best for a stage 2 — defer and focus greenfield". Both confirmed. Decisions:

- **`[brownfield]` manifest section is REDUNDANT (verified)** and would be dropped even
  if we continued: collision behavior already lives at the call site
  (`idempotent_write(reconcile=...)`); 008's gate annotation can read pre-existing
  artifacts from the inspect-pass Diffs the pipeline ALREADY emits
  (`reproduce.build_drift_report` :79; skip-because-exists Diff :173). A static field just
  duplicates `reconcile` and can drift — same smell that killed `brownfield_skip`.
- **DEFER all brownfield** (017 + 008) to a future stage 2. Resume greenfield roadmap:
  012 stack-adr → 013 ts-depth → 007 ci-matrix → 014/015/016. Design fully preserved in
  `[[project-setup-008-brownfield-redesign]]`.
- **P1 (commit 5868661) disposition — KEEP G8, REVERT brownfield bits:**
  - KEEP: widened G8 regexes (6→13 anchored shapes) + the `_empty_manifest` NameError fix
    + the test_contracts loader cache-guard (all greenfield-independent, real value/bugfix).
  - REVERT: `brownfield_probe`, `merge_append_lines`, `idempotent_write(merge=)`, the
    `[brownfield]` manifest parser, and the brownfield-specific tests (probe+merge). Unused
    once deferred — avoid dead SDK code. Re-add in stage 2.
- **⚠️ STAGE-2 carryover (user):** protect ALL blunt clobberers with append/preserve, not
  just gitignore — `.pre-commit-config.yaml`, the quality-hooks generated list, and
  `.env.example` (all `reconcile=True` today). Judgement call: user-owned vs tool-managed.

## Secrets / inline-scanner question (user asked twice) — ANSWERED

Did anything work INLINE? Yes — but adopting a *tool* always meant an unacceptable dep:
- **detect-secrets** (Yelp): genuinely inline (`core.scan.scan_line(str)`, offline) — but
  pulls mandatory `requests`+`pyyaml`, breaking the stdlib-only hermetic runner. (Apache-2.0)
- **gitleaks**: not a lib, but its ~179 rules are plain RE2 regexes (Python-`re`-safe,
  verified), MIT, vendorable as data with zero dep. CAVEAT: ~60-70% rely on
  keyword+entropy+allowlist prefilters that aren't the regex → only the ANCHORED provider
  rules are safe to lift (generic/entropy ones reintroduce UUID/hash false positives).
- **trufflehog**: not inline at all (Go binary, subprocess, AGPL).
RESOLUTION: adopt the gitleaks ANCHORED PATTERNS (not the tool) into `looks_like_secret`
— inline, hermetic, no dep. This is the KEPT part of P1 (6→13 shapes). Research was
adversarially verified; see `inline-secret-scanner-research` workflow output.

## Revert executed + greenfield resumed

- Brownfield revert committed `45f490e`. Independently verified: zero brownfield refs in
  runner; `idempotent_write` byte-identical to pre-P1; G8 widening intact (13 shapes +
  attribution) relocated to `tests/test_g8_secret_shapes.py`; `_empty_manifest` +
  test_contracts cache-guard kept. **Full suite 660 passed, 4 deselected** (648 pre-P1
  baseline + 12 kept G8 tests = 660; the 27 brownfield tests removed with their code).
- `specs/017-brownfield-probe/` kept on disk, Status → Deferred (stage-2 design of record).
  `008` stays Draft/deferred (depends on 017).
- **Now driving the GREENFIELD queue autonomously:** 012 → 013 → 007 → 014/015/016, per
  `specs/roadmap-synthesis.md` sequence. Each: author plan (leans from synthesis/memory)
  → coder builds working tree → I re-verify + full-suite gate → commit signed → memory
  AS-BUILT. 009 stays unbuilt (user opt-in). Will only surface for genuinely blocking
  decisions.

### 012 (stack-adr) — Phase 1 committed `6b1be3b` (671 green). P2+P3 built; FOUND A REGRESSION.

- The full-suite gate (run in main thread, NOT trusting the subagent's narrow `-k`
  filter — which is precisely why the discipline exists) caught **1 failure**:
  `test_parity_baseline_scaffold.py::test_baseline_scaffold_parity`. NOT a bug — a real
  cross-spec tension: `stack-adr` is `default_enabled=true` (spec 012 Settled Decision J),
  so it now joins the minimal-core set (7 modules), but the parity guardrail asserts
  EXACTLY the 6-core set + that no extra default output appears. Every greenfield project
  would now get a `docs/decisions/STACK.md` stub by default (Decision J + the "no lang-*
  → minimal stub" edge case explicitly intend this).
- **⚠️ DECISION SURFACED TO USER (borderline-blocking):** keep `stack-adr` default-on
  (spec-faithful; update the parity test to the 7-core set) vs make it opt-in
  (`default_enabled=false`; contradicts Decision J but matches the "no default noise"
  instinct shown in the gitignore/clobber discussion). Did NOT auto-resolve — asked.
- The SC-005 FR-012 boundary (answers.toml byte-unchanged after a reproduce with the
  staleness step) is the one genuine test gap from P2+P3 (coder asserted manifest flags
  only); a real end-to-end test is queued for the closeout phase.

### ⚠️⚠️ DISCOVERED BUG (pre-existing) + scope decision needed — stack-adr default flip done

- **stack-adr → opt-in (`default_enabled=false`)** applied: module.toml flipped, spec
  Decision J + FR-001 amended, test_module_stack_adr line 137 assertion flipped. Parity
  guardrail (6-core) stays unchanged.
- **SC-005 test surfaced a REAL PRE-EXISTING BUG** (verified by reverting pipeline.py and
  re-running: the test fails at a *baseline* assertion, not the FR-012 boundary). The bug:
  an UNANSWERED input's bare manifest default (e.g. an empty-string `repro_answer`) is
  stamped `'flag'` (user-choice) provenance and PERSISTED to `answers.toml` — even at init,
  even though the user never chose it and no agent emitted it. This pollutes committed
  state with never-decided values, for EVERY module, on every run. Independent of 012.
- The coder (over its brief — I asked for ONE test) fixed it with THREE `pipeline.py`
  changes: (1) `_read_committed_answers` strips the nested `source` provenance sub-table
  so it can't bleed back as an answer key on reproduce; (2) `_interview_module` suppresses
  "echo-back" values (accepting a committed value or a bare default unchanged ≠ a new
  user choice → not added to user_choices); (3) Stage-8 persist filter drops keys whose
  provenance is bare `"default"` before write_answers_toml. **Full suite: 693 passed, 4
  deselected — zero regressions** across all modules.
- **⚠️ SCOPE DECISION SURFACED TO USER:** these are correct fixes but touch the SHARED
  runner core (pipeline interview + persist), out of spec-012's "stack-adr + reproduce_only"
  scope. Options: (a) keep them in the 012 commit (pragmatic — they're what makes SC-005
  pass cleanly + fix a real bug, full-suite green); (b) split into a separate
  bugfix commit/spec (cleaner provenance, isolates the shared-core change for review);
  (c) revert the pipeline changes + relax the SC-005 test to assert ONLY the FR-012 value-
  stability boundary (narrowest 012 scope; leaves the pre-existing bug for a dedicated
  future fix). Did NOT auto-decide — this is a shared-core behavioral change.
- RESOLVED (user): split into its own bugfix commit `e5e8eb5`; 012 feature in `48b6adf`;
  stack-adr opt-in. 012 CLOSED OUT. Signing failed (1Password op-ssh-sign signal 9) →
  unsigned commits per user authorization.

### 013 CLOSED OUT (`269d88b`, full suite 707). FR-009 amended (CI note → runner [SKIP] log).

### 007 (ci-matrix) — ⚠️ CORE MECHANISM GAP found at plan-authoring (pre-build). NOT yet built.

- Verified before writing any code (synthesis OQ-3 told me to): the CI agent's context
  in `run_agent_phase` is `{module_id, step_id, answers: <THIS module's answers only>}`
  (reproduce.py:647-651 + executor.py:536-539). **The agent CANNOT see other modules'
  answers** (lang-python python_version, lang-ts package_manager). But 007's whole premise
  (FR-005a, Settled Decision C/I, Assumption 4) is "the agent reads the frozen answers for
  all active language overlays from its context dict and sizes the matrix to the actual
  stack." That cross-module visibility does NOT exist in the runner.
- Crucial asymmetry found: the PYTHON write step CAN read cross-module answers via
  `sdk.load_plan(args.plan).modules['lang-python'].answers` (load_plan is exported;
  PlanModule.answers exists; all lang-* answers are frozen by Phase B). So the data is
  reachable in the deterministic step — just not in the agent's decision context.
- **⚠️ DESIGN DECISION SURFACED TO USER (blocks 007 build):** where does stack-sizing
  intelligence live? (a) RUNNER CHANGE — broaden the Phase-A agent context to include a
  read-only view of all already-resolved module answers (small, additive: add an
  `all_answers` key to the context dict at reproduce.py:647; affects every agent module
  but backward-compatible since it's additive); spec stays as written. (b) DESIGN SHIFT —
  keep the agent context single-module, move stack-sizing into the deterministic python
  step (it CAN read the full plan): the agent emits a stack-agnostic ci_plan skeleton +
  action refs (its real research value), python derives the matrix/jobs from the frozen
  lang-* answers it reads via load_plan. Reframes Settled Decision C. (c) interview
  plumbing — declare the needed answers as ci-module inputs pre-filled from prior modules
  (heavier, cross-module answer mirroring). Did NOT auto-decide — this is 007's core
  mechanism and (a) touches the shared runner. Leaning (a): smallest, most spec-faithful,
  genuinely useful for any future cross-cutting agent module; the gcontext broadening is
  additive + read-only.
- RESOLVED (user): option (a) — runner change. Phase-0 `all_answers` added to the Phase-A
  agent context (read-only copy, backward-compatible). 007 CLOSED OUT: full suite 731
  passed, 4 deselected; module + Phase-0 in ONE commit (coherent feature, unlike 012's
  unrelated bugfix split). SC-007 is structural (no network code in the module). The
  `all_answers` view is now reusable infra for future cross-cutting agent modules.

### 014/015/016 split — ALL CLOSED OUT. Greenfield roadmap batch COMPLETE.

- **016 readme-draft** (`7d6ef16`, suite 737): new default-disabled module; OQ-5 resolved
  (no `readme_exists` when; init_only+reconcile=false). Simplest, shipped first.
- **015 pkgadd-resolver** (`6886122`, suite 764): package-add extended with optional
  resolver; SECURITY — path-traversal guards preserved verbatim at top of main() before
  dispatch (verified). Uses 007's all_answers for sibling-pin alignment. OQ-3 gate_blocked
  scope verified. resolve_stack=false = unchanged behavior (existing suite green).
- **014 org-policy** (`4120fe9`, suite 785): new ORG_SOURCE_UNPINNED runner validation
  (validate_sources at Stage 1, narrow precision rule — backward-compat verified, zero
  fixtures tripped) + new default-disabled org-policy module.
- No surprises in this trio (unlike 012's provenance bug + 013's FR-009 gap + 007's
  cross-module-context gap — those were caught earlier and resolved with you).

## SESSION CLOSEOUT SUMMARY (greenfield drive complete)

Specs driven to Implemented this session: **006/010/011** (status flips, pre-built) +
**012, 013, 007, 016, 015, 014** (built + closed out). Commits `d708b04` → `4120fe9`.
Full suite grew 648 → **785 passed, 4 deselected**, green at every gate.
- **Brownfield DEFERRED to stage 2** (017-brownfield-probe + 008-brownfield-detect),
  design preserved in [[project-setup-008-brownfield-redesign]]. Kept the widened G8
  regexes from the reverted 017-P1 (`e5e8eb5`'s sibling `45f490e`).
- **009 (py-web-orm) intentionally unbuilt** (user: opt-in).
- Runner gained two additive primitives this session: `StepSpec.reproduce_only` +
  `ExecutionPlan.written_at` (012), and the Phase-A `all_answers` agent-context view (007).
  Plus one pre-existing provenance/persist bugfix (`e5e8eb5`).
- Signing failed all session (1Password op-ssh-sign signal 9) → all commits UNSIGNED per
  user authorization. **Re-sign on next session if 1Password is back** (optional; history
  is otherwise intact).
- `reviews/marketplace-functional-cut-spec.md` left untouched throughout (parallel session).
- The apm 0.22.0 bundle-dep rejection was apm's own corrupted cache (user), NOT our specs.

### 013 (ts-depth-resolvers) — Phases 1+2+3 built, full suite 707 green. ONE spec gap surfaced.

- Phase 1 (module.toml: 6 declared inputs + ui-kit-init gate + ui-kit-scaffold step),
  Phase 2 (write-step: test-runner template instantiation + PM-shape validation FR-013 +
  PM/runtime consistency FR-017 + .node-version/engines FR-014/015 + 6 template files),
  Phase 3 (_do_ui_kit_scaffold: allowlist validation + safe-skip + STACK-NOTES). v1 scoped
  to shadcn+none (nuxt-ui deferred per OQ-2 lean). 30 lang-ts module tests; full suite 707.
- Two pre-existing test edits VERIFIED legitimate: (a) test_gate_g4_generator step-order
  list was stale (Phase 1 added 2 steps) — appended, not weakened; (b) SC-006 fixture had
  package_manager=bun + pnpm pin (internally inconsistent) — my new FR-017 check correctly
  rejected it, so the fixture's PM was corrected to pnpm. Both sound.
- **⚠️ SPEC GAP SURFACED (SC-003 / FR-009) — needs user decision before 013 closeout:**
  FR-009 says in `--non-interactive` (CI, no --allow-ui-kit-init) the ui-kit-scaffold step
  "SAFE-skips AND writes a STACK-NOTES.md entry recording the manual command." BUT the
  runner's gate-blocking (reproduce.py:465-477): a declined/skipped HARD gate sets
  gate_blocked=True and SKIPS the following python step ENTIRELY (`[SKIP]` notify) — so
  _do_ui_kit_scaffold never runs and CANNOT write the note. This is a real spec-vs-runner
  architecture conflict, NOT a coder error (the coder flagged it honestly). The reproduce
  safe-skip path (SC-005, mode!=init) DOES write the note and is tested; only the CI
  hard-gate-skip path (SC-003) can't, given current runner semantics. Options: (a) accept
  CI gets the runner's [SKIP] notify as its record, amend FR-009 to drop the STACK-NOTES
  requirement in the gate-blocked CI path (no code change; the deterministic pins still
  land); (b) runner change so a gate-blocked step still runs in note-only mode (cross-
  cutting, affects all gated modules); (c) move the STACK-NOTES write into the gate/runner
  layer. Did NOT auto-decide. SC-004 (confirmed gate executes via run_tool) is structurally
  present but only inspect-path tested (no live subprocess integration) — acceptable.
