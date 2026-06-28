# Feature 014 — Org-Convention Overlay, Package-Add Resolver, README Draft (memory)

Authored 2026-06-28. Three loosely-coupled Tier-2 extension demonstrations from
roadmap rank #12. All verified against code on `feat/project-setup-modular-redesign`
at HEAD `7779c27`. The key code reads were: `package-add/module.py` (full),
`package-add/module.toml`, `runner/persist.py:187-227` (sources write),
`runner/pipeline.py:109-119` (sources read), `runner/sources/locator.py` (full),
`runner/sources/fetch.py` (full), `runner/sources/discover.py` (full),
`runner/sdk.py` (full), `lang-python/module.toml` (full).

## Scope decision (what 014 is)

014 = **three new modules / module extensions** (all share the agent→gate→python
seam):

- **Sub-feature A**: A new `org-policy` bootstrap module + `ORG_SOURCE_UNPINNED`
  validation for git sources without a pinned ref.
- **Sub-feature B**: Extension of the existing `package-add` module with an optional
  Tier-2 resolver agent step + two new gates + a new manifest-write step.
- **Sub-feature C**: A new `readme-draft` module (write-once, `reconcile=false`).

OQ-1 (split vs bundle) is a human decision that may split these into three thin
specs. All other OQs are design details resolved during planning/implementation.

## VERIFIED CODE FACTS (load-bearing — read these first)

### Fact 1 — package-add security guards and their exact positions

- `_validate_name`: defined `module.py:61-75`. Three checks: `/` or `\\` in name,
  dot-only names (`..`/`.`/`""`), embedded `..`. Returns error string or `None`.
- `sdk.is_safe_relative_path(dir_)`: called at `module.py:159-177` on the `dir_`
  interview answer. Both run inside the `main()` function BEFORE `target.mkdir`
  at `module.py:199`. The spec mandates these stay in the `kind=python` `add` step,
  run verbatim, BEFORE any mkdir — agent output cannot bypass them.
- `module.toml:39-41`: ONE step today, `{id="add", kind="python"}`. Adding the
  resolver requires inserting `resolve`/`pins`/`manifest` steps BEFORE `add`.

### Fact 2 — sources.toml format is `[[source]]` with locator + ref + subdir

- `persist.py:217-224`: each source written as `{locator, ref?, subdir?}`. The
  `ref` field is the pinning mechanism; without it, `fetch_source` uses
  `"HEAD"` (a floating ref — the security risk FR-001 closes).
- `pipeline.py:109-119`: reads `data.get("source", [])` — standard list of dicts.
- `locator.py:95-161`: `parse_locator` resolves all git forms to a `Locator`
  dataclass. A shorthand `owner/repo` with no `#ref` gets `ref="HEAD"` by default
  (`:157`). The new FR-001 validation must check: git locator AND `ref=="HEAD"`
  AND no explicit `ref` field → `ORG_SOURCE_UNPINNED`.

### Fact 3 — fetch_source is soft-fail, non-raising

- `fetch.py:141-177`: returns `FetchResult(ok=False, skipped_reason=...)` for any
  failure. The pipeline proceeds without the module. Org fetch failures at init or
  reproduce are soft-warn + skip (consistent with 001 contract).
- Cache keyed on `locator.origin` only (not ref/subdir) via `cache_key`
  (`locator.py:201-212`). Two fetches of the same repo at different refs land in
  the same cache dir; checkout is switched to the ref each time. So a pinned-ref
  reproduce hits the same cache dir and checks out the exact ref.

### Fact 4 — Discovery precedence is ENV→PROJECT→HOME→FETCHED→BUNDLED

- `discover.py:180-226` (`build_discovery_roots`): fetched roots land at level 4.
  No runner change needed. An org policy repo module at the FETCHED level shadows
  BUNDLED but is shadowed by PROJECT/HOME/ENV — exactly the right priority.

### Fact 5 — The agent step + gate + python step pattern from lang-python

- `lang-python/module.toml:31-52`: `resolve` (kind=agent, steering=steering/resolve.md)
  → `pins` (kind=gate, hardness=hard, allow_flag=allow-stack-write, init_only=true,
  message with `{decision}`) → `write` (kind=python). This is the EXACT template
  for sub-features A and B.
- `{decision}` token: `plan.py:159-168` replaces it with `render_answer_block(mod_answers)`
  at freeze. Org-policy override tables and aligned-pins tables render through this.

### Fact 6 — `sdk.FrozenInputs.mode` and `verify_pins` are the Tier-2 primitives

- `sdk.py:86-91`: `.mode` returns `"init"` or `"reproduce"`. Gate network work
  on this: `verify_pins` runs in `"init"` only (003 FR-009 pattern).
- `sdk.py:315-380`: `verify_pins(pins, ecosystem)` returns per-pin status dict.
  Supported ecosystems: `"pypi"` and `"npm"` only. Go/Rust → skip + warn (OQ-4).

### Fact 7 — `idempotent_write` with `reconcile=False` is the write-once guard

- `sdk.py:240-257`: if file exists and `reconcile=False`, returns
  `Diff(kind="skip", preview="(exists, skipping — use reconcile to overwrite)")`.
  No write, no error, no prompt. This is the mechanism that makes `readme-draft`
  and the package-add `manifest` step safe to replay on reproduce.

### Fact 8 — `answers.toml` sibling answer structure

- `pipeline.py:122-138`: per-module answers in `[module.<id>]` TOML tables, read
  as a flat dict `{module_id → {key: value}}`. An agent step can access sibling
  pins by reading the plan JSON's module entries (the plan carries the full frozen
  answer set for all enabled modules). The steering doc for sub-feature B must
  instruct the agent to read its `--plan` argument for the sibling answer blocks.

## OPEN QUESTIONS — human input required or design detail for planning

### OQ-1 — Split into three separate specs or keep as one? (HIGH — human decision before plan.md)

**The question**: The three sub-features are loosely coupled: (A) org-policy is a
runner-validation + new module, (B) package-add extension is an existing module
upgrade, (C) readme-draft is a new small module. Each is independently shippable.
Keeping them in one spec makes the FR numbering longer (24 FRs, 10 SCs) but avoids
three thin specs each under ~10 FRs.

**Why the human must decide**: The project has been shipping one feature per spec
(001–005, one coherent capability each). Bundling three into one risks a large PR
with unrelated changes and makes partial shipping harder (e.g. ship B without A).
Splitting gives cleaner per-spec history, smaller PRs, and easier OQ tracking — but
adds overhead for three thin specs.

**Your lean**: SPLIT into three specs (`014-org-policy`, `015-pkgadd-resolver`,
`016-readme-draft`). The sub-features share no code; they only share the spec
preamble on gate seam / determinism contract. Splitting gives each its own plan.md
and tasks.md, making implementation parallel and reviewable independently. This
spec (014 as drafted) serves as the bundled strawman; after splitting, renumber and
thin each.

---

### OQ-2 — `ORG_SOURCE_UNPINNED` validation: where exactly does it run? (MED)

FR-001 requires rejecting a git source with no `ref` at validate time. Open: the
exact insertion point. Options: (a) in `pipeline.py` Stage 1 (`resolve_sources`),
before the fetch loop; (b) in `persist.py` `write_sources_toml` (too late — the
fetch has already run); (c) in a new `validate_sources` function called by the CLI
before `run_pipeline`. The validation must fire BEFORE `fetch_source` (to avoid
fetching from a floating ref at all).

**Lean**: Option (a) — add a `validate_sources(sources: list[dict])` function
called at the top of Stage 1 in `pipeline.py` (`pipeline.py:292-299`). It iterates
`all_sources`, parses each locator, and rejects any `kind="git"` with `ref=="HEAD"`
AND no explicit `ref` field. Returns a list of `SetupError` (following the existing
error-collection pattern).

---

### OQ-3 — Package-add step ordering and `gate_blocked` scope interaction (MED)

FR-013 requires a soft gate on `workspace-edit` AFTER the `add` step. The current
spec-004 `gate_blocked` flag is module-scoped: a declined gate sets `gate_blocked`
and skips ALL later `kind=python` steps in the module (`reproduce.py:277-283`).
If the `pins` hard gate is declined, `gate_blocked` would skip BOTH `manifest` AND
`add` AND `workspace-edit`. That is correct for `manifest` and `add` (the directory
should not be created without reviewed pins), BUT `workspace-edit` should also be
skipped in that case (nothing to register). So the current module-scoped blocking
is actually correct here: decline `pins` → skip everything after it.

The subtlety is the REVERSE case: a declined `workspace-edit` soft gate should
leave `add` + `manifest` intact (they ran before it). The step order enforces this:
`resolve` → `pins` (hard gate) → `manifest` → `add` → `workspace-edit` (soft gate)
→ `workspace-edit-step`. A declined `workspace-edit` only blocks the `workspace-edit-step`.
A declined `pins` blocks `manifest`, `add`, `workspace-edit-step`. This ordering
produces the correct outcome WITHOUT changing `gate_blocked` semantics.

**Lean**: Use the step order `resolve → pins → manifest → add → workspace-edit-gate
→ workspace-edit-step`. Document this ordering explicitly in plan.md.

**Verify** by reading `reproduce.py:262-343` (the `apply` loop) to confirm
`gate_blocked` scopes correctly to steps AFTER the declined gate — not just python
steps but specifically steps in the same module in topo order. (The spec-004 AS-BUILT
Section 5 and Section 6 describe this behavior; confirm the implementation matches.)

---

### OQ-4 — Pin verification for `lang=go` and `lang=rust` (LOW)

FR-011 says `verify_pins` runs for `pypi`/`npm` only; `lang=go`/`lang=rust` skip
with a warning. Open: is there a `crates.io` or `pkg.go.dev` verification path
worth implementing now, or explicitly defer?

**Lean**: Explicitly defer. `verify_pins` in `sdk.py` only supports `pypi`/`npm`
(lines 315-360); adding Go/Rust would require two new registry clients. The blast
radius of a Go/Rust package add is lower (Go modules are checksum-verified by the
toolchain; Cargo has Cargo.lock). Document as a known gap in the steering doc for
sub-feature B. A future spec adds these ecosystems to `verify_pins`.

---

### OQ-5 — `readme_exists` synthetic flag: can `when` evaluate it at build_plan? (MED)

FR-017 gates the README gate step with `when = "readme_exists == false"`. This
requires a `readme_exists` answer in the module's frozen answers at `build_plan`
time. But `readme_exists` is a filesystem fact (does `README.md` exist in
`project_dir`?), not a user interview answer.

**The problem**: `build_plan` receives only `resolved_answers` (interview answers +
agent-steered answers). Filesystem facts are not in the answer set. So `when =
"readme_exists == false"` would evaluate against a missing key → `false` → gate
DROPPED (per spec 004 OQ-2 resolution). That means the gate never fires. Wrong.

**Options**:
- (a) Add a synthetic `readme_exists` bool to the module's interview inputs
  (computed by an `inspect`-pass Python helper that runs before build_plan) and
  store it in answers. This is the cleanest approach but requires the inspect pass
  to populate answers before the plan freeze — which may need a new Stage before
  Stage 6 (freeze).
- (b) Skip the `when` predicate entirely. Instead, the python `write` step checks
  `diff.kind == "create"` AFTER calling `idempotent_write(inspect=True)` and
  signals the gate from inside the step — but the gate cannot be conditional based
  on step output (gates precede their write step in the plan).
- (c) Use `reconcile=false` + the existing G5 overwrite-gate machinery (spec 004).
  Since the file does not exist at init, it creates (no gate needed for new files
  per G5 — G5 only fires for modified files). Wait... that would mean no gate on
  first write. Unacceptable (README is a user-facing artifact; it should be shown).
- (d) Make the gate `hardness="soft"` with no `when` predicate. It fires on every
  run; on reproduce the gate auto-proceeds (`init_only=true`) and the write step
  returns `Diff(kind="skip")` because the file exists. The gate only prompts at
  init (first time); on re-runs it is init_only auto-proceed + skip write. This
  is the simplest option and matches the existing `init_only` semantics exactly.

**Lean**: Option (d) — use `hardness="hard"`, `allow_flag="allow-readme"`,
`init_only=true`, no `when` predicate. The `init_only` flag means the gate only
prompts at init; on reproduce it auto-proceeds without prompting. The write step
then calls `idempotent_write(reconcile=False)` which returns `skip` if the file
exists. The net effect: gate fires + prompts at first init; on reproduce, gate
auto-proceeds + write skips. No `readme_exists` synthetic flag needed. FR-017 in
the spec should be updated to remove the `when` predicate and use this simpler
approach.

**Update needed in spec before plan.md**: FR-017 currently says
`when = "readme_exists == false"`; this should be removed in favour of the simpler
`init_only=true` + `reconcile=false` combination described above.

## ASSUMPTIONS (flagged for correction)

1. Spec 003 (two-phase plan, `verify_pins`, `FrozenInputs.mode`) and spec 004
   (gate enrichment: `hardness`, `allow_flag`, `skip_flag`, `init_only`, `when`,
   `gate_blocked` per-module scope) are in place and green.
2. The `{decision}` token composition renders the full `answers_to_persist` block
   from the agent step via `render_answer_block`. For override tables (sub-feature A)
   and pin tables (sub-feature B), the render is a flat KV dump — acceptable for a
   gate message. If the rendered output is unreadable for complex tables, the gate
   message may need a custom renderer (a data detail, not a spec change).
3. `sdk.append_if_absent` is sufficient for all four workspace manifest formats
   (pyproject.toml `[tool.uv.workspace]` members list, root `package.json`
   `workspaces` array, `go.work` `use` directive, `Cargo.toml` `[workspace]`
   members array). The exact per-format append strings are plan.md data details.
4. The `gate_blocked` per-module-scoped blocking (OQ-3 lean) means the step order
   `resolve → pins-gate → manifest → add → workspace-edit-gate → workspace-edit-step`
   gives correct blocking for both declined-pins (skip everything after) and
   declined-workspace-edit (skip only workspace-edit-step).
5. Splitting or keeping bundled (OQ-1) does not affect the settled decisions or
   the FR/SC numbering within each sub-feature — those restart per-spec regardless.

## NEXT ARTIFACTS (speckit flow)

Produced so far: `spec.md`, this `memory.md`. NOT yet produced (defer until OQ-1
resolved + human confirms scope):
- `plan.md` — phased build order. Deferred; the split decision (OQ-1) determines
  whether this is one plan or three.
- `tasks.md` — implementation tasks.
- `data-model.md` — the `overrides` decision schema + `aligned_pins` schema +
  `ORG_SOURCE_UNPINNED` error code.
- `contracts/` — the org-source validation contract + the security-guard invariant.
- `research.md` — the `when`-predicate + `gate_blocked` interaction (OQ-3 verify
  step before implementing FR-013).

## DETERMINISM RULES carried from 003/004 (must hold)

- Research only at init; reproduce replays frozen `agent-steered` answers, zero
  network (spec 003 FR-009). `verify_pins` runs in `"init"` mode only.
- `--refresh <module>` is the ONLY path that re-invokes agent research (spec 003
  FR-010). Plain reproduce never researches.
- Every persisted pin is registry-verified at init; unverified pins are never
  written (spec 003 FR-005/012).
- `reconcile=false` modules (package-add manifest, readme-draft) skip if the file
  exists — write-once, never overwrite a hand-edited file without an explicit
  `reconcile=true` opt-in by the module author.
- `init_only=true` gate steps auto-proceed on reproduce without prompting (spec 004
  FR-006a). They do NOT set `gate_blocked`; the write replays byte-identically.

## AS-BUILT (TBD)
