# Roadmap Synthesis: Specs 006–014 (Batch 2)

**Created**: 2026-06-28  
**Status**: **Human decisions RESOLVED 2026-06-28 (see "Resolved Decisions" at top).**
Specs are ready for plan.md authoring in the recommended sequence.  
**Covers**: roadmap ranks #4–#12, feature specs 006 through 014  
**Foundation**: specs 001–005 shipped and green (616 tests; +Go/Rust G4)

---

## Resolved Decisions (2026-06-28, user)

The five consolidated human questions are answered. All other per-spec OQs are
implementer-resolvable with the leans recorded in each spec's memory.md.

- **Q2 (012, HIGH) → `--refresh` OVERRIDES `reproduce_only`.** An explicit
  `--refresh <module>` fires the agent even on a `reproduce_only` step (consistent
  with 003 FR-010: `--refresh` is the only path to fresh research). Impl: in
  `run_agent_phase`, check `_module_refreshed(module_id)` BEFORE the `reproduce_only`
  guard. This is the project-wide contract for all future `reproduce_only` steps.
- **Q4 (014, HIGH) → SPLIT into 014 / 015 / 016.** The bundled 014 spec becomes the
  shared preamble (settled decisions inherited); produce three thin plan.md files:
  **016-readme-draft** (simplest, no security surface — ship first), **015-pkgadd-resolver**
  (security-sensitive path-traversal work — deeper review), **014-org-policy**
  (runner validation change). Renumber the three sub-features into their own dirs at
  plan time; no spec re-authoring needed.
- **Q1 (009, MED) → `orm_intent` default = `"none"` (string sentinel).** Zero runner
  change; `when = "orm_intent != none"` then correctly suppresses on the default.
  Consistent with 013's `ui_kit_id` default. (Truthy-`when` form NOT added — no
  consumer justifies the runner change.)
- **Q3 (009, MED) → add Litestar to the base `resolve.md` in 009's PR.** Additive
  one table-row change; shipping `web-resolve.md` that lists Litestar while the base
  resolver omits it is an inconsistency. 009 tests must cover the Litestar path.
- **Q5 (012, MED) → LOCAL date** (`datetime.date.today().isoformat()`) for
  `written_at`. Advisory human-readable field; byte-identity already holds via plan
  freeze. Document the policy in a `plan.py` comment.

**Scope note (user clarification on 009):** ORM and Litestar are roadmap-scoped
*options*, not load-bearing needs. The ORM sub-resolver pins + cross-validates the
Python *data tier* (SQLModel/SQLAlchemy + the correct async/sync driver for the DB +
alembic-if-ORM) — the persistence analogue of what 003 did for the framework; it
closes an unpinned-data-layer drift gap, but only matters for Python-web/DB projects.
Litestar is merely one option in the {FastAPI, Litestar, Django} choice set. **009 as
a whole is opt-in** — build it when a Python-web/DB use case is actually present;
it is the most deferrable spec in the batch otherwise.

---

## Executive Summary

This batch delivers the full Tier-2 capability layer on top of the 003/004 runner
foundation. Eight of the nine specs extend the runner's module framework with new
agent steps, gates, and write steps — following the frozen-decision seam established
in 003. The ninth (spec 010) is a standalone skill deliberately outside that seam.

The batch divides cleanly into three families:

- **Depth-resolver specs (006, 007, 009, 013):** Add agent sub-resolvers to the
  existing `agents-md`, `lang-python`, `lang-ts` modules and a new `ci-github-actions`
  module. These share step-ordering concerns because 006, 009, and 013 all add steps
  to modules that other specs may also touch.
- **Cross-cutting infrastructure specs (008, 011, 012):** A pre-interview brownfield
  detector (008), an env-file generator (011), and a stack-decision record writer plus
  staleness advisor (012). These introduce two new runner primitives:
  `run_brownfield_phase` in `pipeline.py` (008) and `reproduce_only: bool` on `StepSpec`
  plus `written_at` on `ExecutionPlan` (012).
- **Extension demonstrations (010, 014):** A standalone skill outside the runner (010)
  and a three-headed spec covering org-policy, package-add resolver, and README draft
  (014). These are lowest-dependency and can ship or be deferred independently.

Five cross-spec conflicts demand resolution before any plan.md is authored (see
section below). Seven human decisions collapse to four distinct question families.
The recommended build sequence ships specs in dependency order while batching
quick wins early.

---

## Cross-Spec Conflicts and Shared Decisions

### C1 — Multiple specs add steps to `lang-python`

Specs **009** (web + ORM sub-resolvers) and **007** (CI matrix, `after = ["lang-python",
...]`) both touch `lang-python`-related plumbing. Additionally, **008** (brownfield-detect)
emits `python_version` and `framework` as per-module pre-fills for `lang-python`, and
**011** (env-example) reads `lang-python.framework` from the frozen plan.

None of these conflict in step ordering because 007 is a separate module (reads
`lang-python` answers, does not add steps), 008 feeds `lang-python` answers via the
interview pre-fill layer (does not add steps), and 011 is a separate module. Only 009
adds steps directly to `lang-python/module.toml`.

**Resolution required:** If any other in-flight work adds steps to `lang-python`
concurrently with 009, the implementers must coordinate on the step array in
`module.toml`. The safe rule: 009 appends AFTER the base `resolve → pins → write`
triplet and any other spec's steps come after 009's `py-web-orm-write`. State this
explicitly in 009's plan.md step-order section.

### C2 — Multiple specs add steps to `lang-ts`

Spec **013** adds three new answer groups (test runner, UI kit, runtime/PM) to the
existing `lang-ts` `resolve` agent step and two new gate/python steps. Spec **007**
reads `lang-ts` answers (separate module, no step additions). Spec **011** reads
`lang-ts.framework` (separate module).

If 013 ships before 007, the CI module's steering doc must reference the new frozen
answers (`test_runner`, `runtime`) for correctly-sized CI jobs. If 007 ships before
013, the CI steering doc should note "013 not yet shipped" and instruct the agent to
fall back to `package_manager` for runtime inference.

**Resolution required:** Decide the ship order of 007 vs 013 (recommended below).
Whichever ships second must update the other's steering doc in the same PR.

### C3 — `lang-python/steering/resolve.md` ownership across 009

Spec **009** OQ-2 asks whether to add Litestar to the base `resolve.md` (a 003-era
file) in the same PR. If yes, 009 touches a spec-003 file. This is safe (additive,
one-row table entry) but must be flagged in the 009 PR description so reviewers do
not treat it as scope creep.

**Resolution required:** The human must answer OQ-2 for spec 009 (see consolidated
question Q3 below).

### C4 — `reproduce_only` runner primitive in 012 is load-bearing for its own spec

Spec **012** adds `reproduce_only: bool = False` to `StepSpec` (manifest.py) and
`written_at: str` to `ExecutionPlan` (plan.py). These are additive and
backward-compatible but touch runner-level files. The `written_at` field has a
subtle correctness trap: if `freeze()` is called at reproduce time (pipeline Stage 6
re-freezes), it would overwrite `written_at` with today's date, breaking
byte-identity. Memory.md Assumption 4 proposes the fix: emit `written_at` as a
`"derived"` answer in the write step's `answers_to_persist` at init, then read it
from `FrozenInputs` on reproduce. This is confirmed feasible by Fact 6 in 012's
memory (MODULE_EMITTABLE_PROVENANCE includes `"derived"`).

**Action before 012 plan.md:** Confirm the `written_at` propagation route (plan-level
field vs module-answer) per OQ-2. The module-answer route avoids mutating the plan
at reproduce time and is the safer choice.

### C5 — Spec 008 (brownfield) adds a pre-interview pipeline stage touching 002's enablement channel

Spec **008** adds `run_brownfield_phase` as a new Stage 3c in `pipeline.py`,
re-invoking `resolve_enabled_modules` with brownfield's proposal. This is the only
spec in this batch that modifies `pipeline.py` structurally (012 touches only
`manifest.py`, `plan.py`, and `reproduce.py`). The change is additive
(FR-020: the hook is a no-op if `brownfield-detect` is not discovered), but it must
be forward-compatible with any future spec that also wants an early-phase hook.

**Action:** The 008 implementation must document the Stage 3c contract so future
specs that need pre-interview agent hooks (there are no others in this batch) can
reuse the pattern. Note this in 008's plan.md.

---

## Consolidated Human Decisions

These are the questions that must be resolved before the relevant spec proceeds to
`plan.md`. Grouped by family. Specs list which OQ they close.

---

### Q1 — `when = "orm_intent != none"` predicate semantics (MED)

**Affects:** 009 OQ-1 (primary); pattern also used by 013 (`ui_kit_id != none`,
`test_runner != none`)

**Context:** The `when` grammar coerces both sides to strings. `orm_intent` defaults
to `""` (empty string). The predicate `orm_intent != none` evaluates `"" != "none"`
which is TRUE — meaning a user who leaves `orm_intent` blank would NOT suppress the
ORM sub-resolver. The same coercion issue applies to 013's `ui_kit_id != none`
predicate.

**Three options:**

- **(a) Sentinel default:** Set `orm_intent` default to `"none"` (the string literal).
  `when = "orm_intent != none"` then correctly suppresses on the default. Simple; no
  runner change. Same fix applies to `ui_kit_id` (default `"none"` already in 013's
  Fact 10).
- **(b) Truthy `when` form:** Add `when = "orm_intent"` (non-empty-string truthy
  check) to `eval_when` in `manifest.py`. Expressive; small runner change that
  benefits all future modules.
- **(c) Empty-string comparison:** `when = "orm_intent != \"\""`. Works with existing
  grammar; fragile parsing.

**Lean:** Option (a) for 009 (set default to `"none"`); option (b) is worth doing in
012 or as a micro-runner cleanup PR if the human wants it. Option (a) requires zero
runner changes and is consistent with 013's already-chosen `"none"` default for
`ui_kit_id`. **Recommend (a): set `orm_intent` default to `"none"` in 009.**

---

### Q2 — `reproduce_only` + `--refresh` precedence rule (HIGH)

**Affects:** 012 OQ-1 (primary); sets a project-wide runner contract for all future
`reproduce_only` steps

**Context:** 012 introduces `reproduce_only=True` on the staleness agent step (skips
at init; runs at reproduce). If a user runs `--refresh stack-adr`, should `--refresh`
override the `reproduce_only` flag and fire the agent at init?

**Two options:**

- **(a) `--refresh` overrides `reproduce_only`:** Consistent with the rule that
  `--refresh` is the only path to fresh research (003 FR-010). A user who runs
  `--refresh stack-adr` wants fresh staleness intelligence; skipping the agent would
  be surprising. The staleness agent then fires at init if explicitly requested.
- **(b) `reproduce_only` always wins:** Simpler; the staleness check is fundamentally
  a reproduce-context advisory (pins were just verified at init; redundant check). A
  user who wants a staleness check at init should use `dep-update` (spec 010) instead.

**Lean:** Option (a). The `--refresh` contract (003 FR-010: "the only mode that
re-researches") should dominate; silently ignoring an explicit `--refresh` would be
confusing. Implementation: in `run_agent_phase`, check `_module_refreshed(module_id)`
before the `reproduce_only` guard — if refreshed, run the agent regardless of mode.

**This is a load-bearing runner contract. Human must confirm before 012 plan.md.**

---

### Q3 — Litestar scope in spec 009: update base `resolve.md`? (MED)

**Affects:** 009 OQ-2 (primary)

**Context:** 009 adds a `web-resolve.md` steering doc that lists Litestar as an async
web framework. But the base `resolve.md` (003-era) does not include `litestar` in its
framework table. A user who sets `framework = "litestar"` gets ASGI server pins from
`web-resolve.md` but no `litestar` base pin from `resolve.md`.

**Two options:**

- **(a) Update `resolve.md` in 009's PR:** One coherent PR. Additive (one row in the
  framework table). The change is a forward-spec touching a prior-spec file, which is
  acceptable for additive changes. 009's tests must cover the Litestar path.
- **(b) Defer Litestar to a follow-up:** 009 ships FastAPI and Django only. A 009a or
  009-litestar followup adds the row later.

**Lean:** Option (a). The change is trivial (one table row in `resolve.md`), and
shipping a `web-resolve.md` that lists Litestar while the base resolver silently ignores
it is an inconsistency that will surface immediately in testing. Do it in the same PR.

---

### Q4 — Spec 014: split into three specs or keep bundled? (HIGH)

**Affects:** 014 OQ-1 (primary); determines whether 014 produces one or three plan.md
files

**Context:** Spec 014 bundles: (A) org-policy module + ORG_SOURCE_UNPINNED validation,
(B) package-add Tier-2 resolver extension, (C) readme-draft new module. They share
no code beyond the gate seam. Each is independently shippable. Combined the spec has
24 FRs and 10 SCs.

**Two options:**

- **(a) Keep bundled:** One PR, one plan.md, one tasks.md. Fewer process artifacts.
  All three ship together.
- **(b) Split into 014-org-policy, 015-pkgadd-resolver, 016-readme-draft:** Cleaner
  per-feature history, smaller PRs, parallel implementation possible, easier to defer
  one sub-feature. Each spec gets its own plan/tasks. The existing spec 014 becomes
  the strawman; three thin specs inherit its settled decisions.

**Lean:** Split (option b). Sub-features A (runner validation change) and B (security-
sensitive module extension) have meaningfully different risk profiles from C (a simple
new write-once module). Bundling means a security review of the path-traversal guard
work (sub-feature B) is entangled with a low-risk README draft (sub-feature C). Splitting
lets sub-feature C ship fast while A and B get appropriate review depth. **The
existing spec 014 serves as the shared preamble; no re-authoring needed — just produce
three thin plan.md files after this decision.**

---

### Q5 — `written_at` timezone policy: local date vs UTC date (MED)

**Affects:** 012 OQ-2 (primary); sets a project-wide policy for future plan timestamp
fields

**Context:** `freeze()` in `plan.py` will populate `written_at`. `datetime.date.today()`
gives local date; `datetime.datetime.utcnow().date()` gives UTC date. Two contributors
in different timezones initiating on the same UTC day can produce different `written_at`
values. However, the `written_at` field is frozen in the plan and replayed unchanged on
reproduce — byte-identity is preserved regardless of timezone choice.

**Two options:**

- **(a) Local date (`datetime.date.today().isoformat()`):** More intuitive for the
  developer. Acceptable ambiguity for a human-readable ADR "decided on" field.
- **(b) UTC date/datetime:** More consistent across contributor machines; avoids
  timezone-crossing mismatches in multi-timezone teams.

**Lean:** Option (a), local date. The `written_at` field is advisory (a human-readable
"decided on" date), not a cryptographic timestamp. Byte-identity is already guaranteed
because the value is frozen in the plan. The timezone gap is an acceptable ambiguity
for this use case. Document the policy in a comment in `plan.py`.

---

## Recommended Build Sequence

Dependency rationale: 003/004/005 are the foundation (already shipped). Within this
batch, 008 is the only spec that adds a new pipeline stage — build it early to establish
the Stage 3c seam. 012 adds two runner primitives — build it before any spec that might
need `reproduce_only` (none in this batch do, but building it early keeps the runner
complete). Depth resolvers (006, 009, 013) are module-only and can ship in any order
after their foundations; CI (007) is cross-cutting and reads those resolvers' answers,
so it benefits from shipping after at least one resolver is expanded.

| # | Spec | Title | Rationale |
|---|---|---|---|
| 1 | **010** | Dependency Update / Upgrade Advisory Skill | No runner dependencies; standalone APM skill. Ships independently without touching the runner, establishing the `dep-update` skill while the runner specs are being planned. Zero risk of conflicting with other specs. |
| 2 | **006** | AGENTS.md Architecture Section | Extends `agents-md` (a module no other batch-2 spec touches). Adds two net-new SDK primitives (`splice_between_sentinels`, `scan_top_level_dirs`) that 007's CI module might reuse for injecting a CI-matrix section into AGENTS.md in a future spec. No OQs requiring human input (all LOW, implementer-resolvable). Quick win. |
| 3 | **011** | env-example-from-stack | New standalone module. Only dependency is 003/004 (shipped). OQ-1 (framework_python answer propagation) is the one verification to do before coding, but it is implementer-resolvable. Low complexity; delivers user-visible value fast. Must ship before 012 so STACK.md can reference env-example as a related module. |
| 4 | **008** | Brownfield Detect and Adopt | Adds Stage 3c `run_brownfield_phase` to `pipeline.py` — the only structural pipeline change in this batch. Build it early so the Stage 3c seam is established; later specs benefit from knowing brownfield's pre-fill layer is in place. OQ-1 (Option B: reuse `run_agent_phase` with filter) and OQ-2 (Option A: declare in module.toml) are both decided above (leaned). Human must confirm before implementation. |
| 5 | **012** | Stack Decision Record + Staleness Check | Adds `reproduce_only` to `StepSpec` and `written_at` to `ExecutionPlan` — runner primitives that are additive and backward-compatible. Build after 008 because 008's Stage 3c establishes the runner extension pattern. Q2 (`--refresh` + `reproduce_only` precedence) and Q5 (`written_at` timezone) must be resolved before plan.md. |
| 6 | **009** | Python Web + ORM Stack Overlays | Extends `lang-python`. Q1 (`orm_intent` sentinel) and Q3 (Litestar in `resolve.md`) must be resolved. No concurrent `lang-python` edits at this point if 006/011 shipped first (neither touches `lang-python`). |
| 7 | **013** | TypeScript Depth Resolvers | Extends `lang-ts`. Same pattern as 009 but for TS. Ships after 009 so the Python depth pattern is established and the TS implementation can cross-reference it. OQ-2 (`nuxt-ui` scope) and OQ-1 (`vitest+playwright` composite) are LOW/MED; lean is to scope v1 to `shadcn` only for UI kit and keep `test_runner` as a single choice. No human-blocking decisions; all are implementer-resolvable given leaning above. |
| 8 | **007** | CI Matrix Sized to Stack | New `ci-github-actions` module. Must ship after 009 and 013 so its steering doc can reference the full frozen answer set (Python framework/version, TS runtime/package-manager). OQ-1 (no GH API probe), OQ-2 (flat keys), OQ-3 (Phase A ordering) are all self-resolved by the spec's own settled decisions. No human-blocking decisions. |
| 9 | **014** | Org-Policy / Package-Add Resolver / README Draft | Lowest-dependency (no other spec in this batch depends on it). Q4 (split vs bundle) must be resolved. If split, implement as three separate thin plan/tasks pairs: (a) readme-draft first (simplest, no security surface), (b) pkgadd-resolver (security-sensitive), (c) org-policy (runner validation change). |

---

## Per-Spec Open Questions: Resolved vs Pending Human Input

| Spec | OQ | Status | Resolution |
|---|---|---|---|
| 006 | OQ-1 (ctx dict cross-module) | Implementer-resolvable | Read `executor.py:443-475` before coding; use `[[inputs]]` mirror entries if needed |
| 006 | OQ-2 (phantom-path regex) | Implementer-resolvable | Match `\| \`<name>/` pattern; heuristic is sufficient |
| 006 | OQ-3 (splice in sdk.py vs local) | Implementer-resolvable | Lean: sdk.py (reusable) |
| 007 | OQ-1 (GH API probe) | Resolved by settled decision D | No live probe; agent knowledge + context7 |
| 007 | OQ-2 (flat keys vs JSON blob) | Resolved by memory lean | Flat keys (`ci_plan_jobs`, etc.) |
| 007 | OQ-3 (Phase A ordering) | Resolved by two-phase plan | `after` in `[order]` + Phase A guarantee |
| 008 | OQ-1 (Stage 3c invocation) | Lean decided; human confirm | Option B: reuse `run_agent_phase` with filter |
| 008 | OQ-2 (`brownfield_skip` declaration) | Lean decided; human confirm | Option A: declare in module.toml |
| 008 | OQ-3 (all-or-nothing gate) | Resolved by settled decision I | All-or-nothing; multi-select deferred |
| 008 | OQ-4 (`--no-brownfield` flag) | Deferred | Follow-up spec if needed in practice |
| 009 | OQ-1 (`orm_intent` predicate) | **Needs human input (Q1)** | Lean: sentinel default `"none"` |
| 009 | OQ-2 (Litestar in `resolve.md`) | **Needs human input (Q3)** | Lean: update in same PR |
| 009 | OQ-3 (Alembic env.py templates) | Implementer-resolvable | Lean: two templates (async/sync) |
| 010 | OQ-1 (detection script copy vs share) | Resolved by memory lean | Copy into package |
| 010 | OQ-2 (apply confirm UX) | Resolved by memory lean | Line-by-line [Y/n] |
| 010 | OQ-3 (script vs agent for registry) | Resolved by memory lean | Hybrid: helper script + agent |
| 010 | OQ-4 (changelog fetch depth) | Resolved by memory lean | Registry metadata first, CHANGELOG entry fallback |
| 011 | OQ-1 (framework_python propagation) | Implementer-resolvable (verify) | Check `pipeline._interview_module` before coding |
| 011 | OQ-2 (env_keys JSON shape) | Resolved by memory lean | Structured objects |
| 011 | OQ-3 (comment format) | Resolved by memory lean | Inline `# comment` suffix |
| 012 | OQ-1 (`--refresh` + `reproduce_only`) | **Needs human input (Q2)** | Lean: `--refresh` overrides |
| 012 | OQ-2 (`written_at` timezone) | **Needs human input (Q5)** | Lean: local date |
| 012 | OQ-3 (`adr_path` bootstrap) | Tentatively self-resolved | Two-run bootstrap is acceptable; confirm with human |
| 013 | OQ-1 (composite `template_id`) | Implementer-resolvable | Lean: single-choice with composite enum atom |
| 013 | OQ-2 (`nuxt-ui` scope) | Implementer-resolvable | Lean: defer to follow-up; v1 = `shadcn` only |
| 013 | OQ-3 (write step split) | Implementer-resolvable | Lean: keep in `_do_write` |
| 013 | OQ-4 (shadcn command per PM) | Implementer-resolvable | Lean: agent decides literal; python validates prefix |
| 014 | OQ-1 (split vs bundle) | **Needs human input (Q4)** | Lean: split into 014/015/016 |
| 014 | OQ-2 (`ORG_SOURCE_UNPINNED` location) | Implementer-resolvable | Stage 1 `validate_sources` |
| 014 | OQ-3 (`gate_blocked` scope) | Resolved by memory lean | Step order ensures correct scoping |
| 014 | OQ-4 (Go/Rust pin verify) | Explicitly deferred | Report warning + skip; add registry clients in future spec |
| 014 | OQ-5 (`readme_exists` synthetic flag) | Resolved by memory lean | Drop `when` predicate; use `init_only=true` + `reconcile=false` |

---

## Answer Namespace Conflicts

The following answer keys appear in multiple specs or have shared-namespace risk:

| Key | Module(s) | Risk |
|---|---|---|
| `framework` | `lang-python`, `lang-ts`, `env-example` (as `framework_python`/`framework_ts`), `stack-adr` (reads both) | No collision — each module reads its own namespace. `env-example` uses distinct key names. `stack-adr` reads cross-module via discovery (no namespace write). |
| `pinned_deps` | `lang-python`, `lang-ts`, `stack-adr` (reads), `dep-update` (reads), `package-add` (aligns) | Read-only consumers. No collision. |
| `allow-stack-write` flag | `lang-python` (`pins` gate), `lang-ts` (`pins` gate), `009` (`py-web-orm-pins` gate) | All three share the same `--allow-stack-write` flag. This is intentional (same blast-radius class). CI must pass one flag to unlock all three. No conflict — desired shared behavior. |
| `brownfield_skip` | `brownfield-detect` (emitter), `git-init` / `license-write` / `gitignore-generate` (readers) | Module.toml additions on three base modules. Additive (default `false`). No conflict but requires touching three existing modules. |
| `written_at` | `stack-adr` (emits as `"derived"` answer), `ExecutionPlan` (new top-level field) | The memory.md proposes two routes. Choose ONE: either use only the plan-level field (cleaner, used at write time) OR the module-answer route (safer for reproduce — avoids re-freeze mutation). Recommendation: module-answer route (`answers_to_persist` at init, `FrozenInputs` at reproduce). |
| `adr_path` | `stack-adr` (emits as `"derived"` answer on first init) | No collision. Two-run bootstrap pattern confirmed feasible (Fact 6 in 012 memory). |

---

## Risk Register

| Risk | Specs | Severity | Mitigation |
|---|---|---|---|
| Stage 3c (`run_brownfield_phase`) breaks existing greenfield tests | 008 | HIGH | FR-019/FR-020: no-op path for empty repo + additive hook that's absent-safe. Add a full greenfield regression test (SC-010). |
| `written_at` in `freeze()` mutates on reproduce, breaking byte-identity | 012 | HIGH | Use module-answer route (emit at init via `answers_to_persist`, replay at reproduce via `FrozenInputs`). See C4 above. |
| `lang-python/module.toml` step array edited by 009 concurrently with other work | 009 | MED | Serialize 009 as a single PR; no concurrent `lang-python` edits in this batch once 009 starts. |
| 013's `ui-kit-scaffold` step executes `shadcn init` — supply-chain surface | 013 | MED | Hard gate + explicit allowlist (FR-008). Allowlist is narrow by design; broadening requires a deliberate PR, not a steering-doc update. |
| 006's `agents-md` base `write` step (reconcile=True) overwrites arch sentinel span on reproduce | 006 | MED | Settle Step order: `write → resolve-arch → arch-gate → splice`. Sentinel markers in base templates ensure `splice` always has markers to target. Documented in memory.md Assumption 3. |
| brownfield agent reads malicious content from scanned files (prompt injection) | 008 | MED | Corroboration rule (>=2 signals), steering prohibition on env files, G8 guardrail. Three independent layers. |
| `package-add` path-traversal guards bypassed by agent-decided name | 014B | MED | FR-007/FR-008: guards are security-pinned, run verbatim BEFORE any mkdir, unconditionally. No agent path can bypass them. |
| 012's staleness advisory floods developers with noise | 012 | LOW | Steering threshold: HIGH/CRITICAL CVEs + hard deprecations only. LOW/MEDIUM CVEs and minor bumps explicitly suppressed. |

---

## Spec-by-Spec Digest (reference)

| Spec | Type | Runner changes | Key new primitives | Blocks |
|---|---|---|---|---|
| 006 | extends `agents-md` | None | `splice_between_sentinels`, `scan_top_level_dirs` in sdk.py | — |
| 007 | new module `ci-github-actions` | None | Pure-stdlib YAML renderer in module.py | After 003/004; ideally after 009+013 |
| 008 | new module `brownfield-detect` | `run_brownfield_phase` in pipeline.py (Stage 3c) | — | After 003/004 |
| 009 | extends `lang-python` | None | ORM + web steering docs + Alembic/ORM templates | After 003/004; Q1+Q3 resolved |
| 010 | standalone skill `dep-update` | None | `detect.sh` copy, `research.sh`, `apply.sh` | None (standalone) |
| 011 | new module `env-example` | None | — | After 003/004 |
| 012 | new module `stack-adr` | `reproduce_only: bool` on StepSpec; `written_at: str` on ExecutionPlan | ADR template | After 003/004; Q2+Q5 resolved |
| 013 | extends `lang-ts` | None | Test-runner config templates | After 003/004 |
| 014 | 3 new modules/extensions | `validate_sources` in pipeline.py Stage 1 (sub-feature A) | `ORG_SOURCE_UNPINNED` error code | After 003/004; Q4 resolved |
