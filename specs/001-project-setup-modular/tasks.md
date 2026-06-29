# Tasks: Modular, Config-Driven project-setup

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Contracts**: [contracts/shared-contracts.md](./contracts/shared-contracts.md)

> **Status (2026-06-27): functionally complete, NOT fully closed.** 35/38 tasks
> done across 13 signed commits (runner + 18 modules + parity audit + Phase-5
> additive; 524 tests green). The new runner+modules tree at
> `skills/project-setup/` COEXISTS with the legacy `.apm/skills/project-setup/`
> monolith. The 3 remaining tasks are the **native-root cutover** (T050 delete
> legacy tree + write plugin.json, T051 repo-wide inventory/tag tooling, T054
> packaging/install verification) — all ⏸️ **DEFERRED**, atomically coupled and
> blocked on the parallel native-root tooling effort. Deleting the legacy tree
> before T051 lands would red the repo's check-artifacts gate. Resume the cutover
> when that tooling lands; verify together.

## Format: `[ID] [P?] [Phase] Description`

- **[P]** = parallelizable (different files, no dependency on an unfinished task in the same batch).
- All paths are under `packages/project-setup/`. Runner library = `skills/project-setup/runner/`, modules = `skills/project-setup/modules/`.
- Tests run via `uv run --with pytest pytest -q`; import the runner by file path (`importlib.util.spec_from_file_location`), not a package install.
- Determinism: Tier-1 (`kind=python`) byte-identical for same answers + unchanged module version; Tier-2 (`kind=agent`) consistent-not-identical.

## Path Conventions

```
packages/project-setup/
  .claude-plugin/plugin.json
  apm.yml  CHANGELOG.md
  skills/project-setup/{SKILL.md, runner/, modules/}
  tests/
```

---

## Phase 0 — Freeze shared contracts (BLOCKING — no implementation until merged)

- [x] T001 [Ph0] Apply the spec amendments (FR-008/009/017/018/036) — **DONE** in this branch; verify `spec.md` matches `contracts/shared-contracts.md` (FR-009 = Section I, step-scoped tier, forbidden fields; provenance enum 6 values; collision boundary; canonical serializer + cache-not-committed plan).
- [x] T002 [Ph0] Ratify `contracts/shared-contracts.md` as the single source for: module.toml schema (§1), frozen-plan JSON (§2), error envelope + codes (§3), result JSON (§4), provenance enum (§5), invocation/import (§6), discovery/collision (§7), project files (§8). Get sign-off; no §changes after this without re-review.
- [x] T003 [Ph0] Confirm the build-order coupling with the **parallel native-root migration** the user flagged (build_inventory.py + release-tag separator). Agree who lands the inventory/docgen fix so Phase 5.2 doesn't double-edit. Record the decision in `research.md` open-items.

---

## Phase 1 — Runner library (the spine)

All under `skills/project-setup/runner/`.

- [x] T010 [Ph1] Create `contracts.py`: `SetupError` dataclass (with `module_ids: list`), `ERROR_CODES` (14 constants), `Provenance` enum (6 values), `ModuleResult` shape, `schema_version` governance. Everything imports this. (FR-017 envelope, §3–5)
- [x] T011 [P] [Ph1] Create `paths.py`: sole owner of `plugin_root()` (env `${PLUGIN_ROOT}` → `__file__`-relative fallback), `bundled_modules_dir()`, `cache_dir()` (the one fetch-cache + frozen-plan-location constant under `~/.cache/project-setup/`), `project_setup_dir()`, `home_config_path()`. (§6, cache-ownership fix)
- [x] T012 [Ph1] `manifest.py`: parse `module.toml` (`tomllib`) → `ModuleManifest`; reject `FORBIDDEN_FIELD` (priority/title/entrypoint/required_answers/produces/module-kind) + `UNKNOWN_FIELD`; validate all 8 input types + choice/multichoice `default ∈ choices`. (FR-009, FR-039, §1) — depends T010.
- [x] T013 [Ph1] `order.py`: **pure, non-raising** topo over requires/after/before via `graphlib.TopologicalSorter` (predecessor-insertion order, tie-break by id; cycle via `.prepare()`/`exc.args[1]` per build_nodes.py). Returns `(ordered_ids, accumulated_errors)`. (FR-010/FR-037) — depends T010.
- [x] T014 [Ph1] `validate.py`: the ONE validate-closed gate — accumulates missing-input + cycle + missing-requires + missing-required-tool (incl. which-on-PATH) and reports all at once, then orders; only place that raises `GateFailure`. (FR-017, FR-038) — depends T012, T013.
- [x] T015 [Ph1] `answers.py`: deep-merge (tables union / scalars replace / lists replace + explicit append/remove, magic-key-collision guarded), defaults chain (module<home<project<choice), and the single `resolve_final_answers()` coercion point both validate + plan-freeze consume. Canonical TOML round-trip. (FR-020, FR-026) — depends T010.
- [x] T016 [Ph1] `plan.py`: build `ExecutionPlan` (shared model, §2), coerce answers once (via T015), embed stable order, freeze to `cache_dir()/plan.json` with the canonical serializer. NO absolute paths in Tier-1-read fields. (FR-008) — depends T013, T015.
- [x] T017 [Ph1] `sdk.py`: module-author API loaded by `module.py` via importlib — `load_frozen_inputs()`, typed accessors for ALL 8 types (incl. `get_multichoice`/`get_text`), `idempotent_write(..., inspect=)`, `tool_or_fallback()`, `emit_result()` (the one result writer), `is_safe_relative_path()` (allows subdirs, blocks `..`/abs/symlink-escape). (FR-033, FR-039, §4/§6) — depends T010.
- [x] T018 [P] [Ph1] Unit tests (import-by-path, CI-shaped): `test_contracts.py`, `test_manifest.py` (forbidden/unknown fields), `test_order.py` (stable order + cycle/missing-requires accumulation), `test_validate.py` (all-at-once), `test_answers.py` (merge + defaults chain), `test_plan.py` (byte-identical canonical freeze cross-process). — depends T010–T017.

---

## Phase 2 — Sources, discovery, cache

- [x] T020 [Ph2] `sources/locator.py`: sole owner of locator parsing (`owner/repo/subdir#ref`, git path, local) → structured `Locator`; stable cache-key normalization (same repo via different locator forms → same key). (FR-012) — depends T010.
- [x] T021 [Ph2] `sources/fetch.py`: git fetch → `cache_dir()` (from paths.py), floating-ref allowed, proceed-on-failure offline, `SourceReport` (fetched/cached/skipped + reasons). (FR-013, SC-008) — depends T011, T020.
- [x] T022 [Ph2] `sources/discover.py`: search-path precedence (env > project > home > fetched > bundled), collision boundary (same-root = hard `ID_COLLISION`; cross-level = reported shadow), tri-state `default_enabled` first-party enforcement, fetch-before-discovery. (FR-011, FR-014, FR-035, FR-036, §7) — depends T012, T021.
- [x] T023 [P] [Ph2] Tests: `test_locator.py`, `test_fetch.py` (offline stub), `test_discover.py` (precedence, collision hard-error vs shadow, default_enabled rejection). — depends T020–T022.

---

## Phase 3 — Pipeline, executor, modes, persistence

- [x] T030 [Ph3] `pipeline.py`: the 8-stage spine (resolve→fetch→discover→interview→order→validate→execute→persist) + mode detection by `.project-setup/sources.toml` presence. (FR-022) — depends T014, T016, T022.
- [x] T031 [Ph3] `executor.py`: Model-B subprocess (`uv run module.py --plan <frozen> --step <id>`), result-gate validation (§4), per-module failure isolation, distinct `UV_MISSING` mid-run re-check (vanished uv hard-fails, not skip), runner-side `files_written ⊆ project_dir` guard, render `kind=gate` messages + capture confirmation, hand `kind=agent` steering to agent and fold decision back as `agent-steered`. (FR-016, FR-033, FR-041, unowned-resp fixes) — depends T017, T030.
- [x] T032 [Ph3] `reproduce.py`: PRE-write diff/confirm — Tier-1 python steps run `--inspect` dry pass emitting proposed files_written+diffs WITHOUT writing; confirm list built from that; real write on confirmation; **guarantee inspect==write for Tier-1**; reconcile overwrites only confirmed files. (FR-024, FR-025, SC-007, the circular-ordering fix) — depends T031.
- [x] T033 [Ph3] `persist.py`: write `.project-setup/{sources,answers}.toml` (per-key provenance, §8), advisory skill_version drift warning, package `.gitignore` for pytest artifacts. (FR-018, FR-019) — depends T015.
- [x] T034 [Ph3] `cli.py`: entry point, `uv` preflight (fail loud, no auto-install, no stdlib fallback), wire pipeline. (FR-005) — depends T030.
- [x] T035 [P] [Ph3] Tests: `test_pipeline.py` (modes, stage order, offline proceed), `test_executor.py` (invocation shape, result-gate, failure isolation, uv-missing mid-run, path-traversal guard), `test_reproduce.py` (inspect==write, confirm-before-write, reconcile), `test_persist.py` (provenance round-trip, drift warning). — depends T030–T034.

---

## Phase 4 — Module migration (build the capabilities)

Each = `modules/<id>/{module.toml, module.py, [helpers], [templates/], [steering/], test_*.py}`. Capture golden fixtures from the monolith (DIRS[21], TARGETS[15], both AGENTS.md heredocs, default apm/MCP lists, pre-commit config). Per-module test asserts on-disk==answers; Tier-1 also gets an SC-001 byte-identical re-run test.

- [x] T040 [Ph4] Build `codex-config` FIRST as the reference module + the module-authoring template (module.toml skeleton, module.py skeleton w/ --plan/--step/--inspect, PEP 723 header, SDK-by-path load). Proves the whole contract end-to-end. — depends T017, T031.
- [x] T041 [Ph4] `core-identity` (answers-only; upstream of most): inputs name/org/description/layout/license/public/create_repo/init_git. — depends T040.
- [x] T042 [P] [Ph4] Simple Tier-1 template modules: `dirs-scaffold` (golden DIRS+TARGETS), `agents-md` (both heredocs), `justfile-write`, `license-write` (year/author = SC-001 carve-out). — depends T041.
- [x] T043 [P] [Ph4] `gitignore-generate`: vendor CC0 github/gitignore templates + on-demand fetch; **parity target = legacy static-fallback heredoc** (not gitnr/toptal). Offline network stub for the fetch. (FR-030, SC-009) — depends T040.
- [x] T044 [Ph4] `precommit-setup`: vendor exact legacy hook set + vendored close-keywords copy; `pre-commit install`. (FR-029) — depends T042.
- [x] T045 [P] [Ph4] `git-init` (init + macOS provenance-xattr clear + **Codex read-only preflight**) and `github-repo` (gh-api.py→gh, ensure origin, failures→warn). — depends T041.
- [x] T046 [Ph4] `apm-install`: port run_apm resolution chain + GITHUB_APM_PAT-from-gh; marketplace register; install/compile/patch/audit; unions every module's apm deps; ordered after all capability modules. — depends T041.
- [x] T047 [Ph4] `speckit-bridge`: spec_mode none/lightweight/full; full delegates to installed speckit pkg `setup-speckit.sh` (subprocess); hard-fail when apm/specify unavailable. — depends T046.
- [x] T048 [P] [Ph4] Language overlays `lang-{ts,python,go,rust}`: ordered after gitignore-generate + precommit-setup; port config heredocs to templates/; preserve gitignore grep-markers (`__pycache__`/`*.test`/`/target`/`node_modules`); NOT byte-identical (run installers). — depends T043, T044.
- [x] T049 [P] [Ph4] `quality-hooks` (reads quality_languages via interview layering, writes sorted-unique marker; after lang-*) and `package-add` (non-default; port path-traversal guards + workspace-root detection verbatim). — depends T048.
- [x] T04A [Ph4] Final parity audit: diff produced base scaffold vs a legacy `project-setup.sh` run with equivalent flags; reconcile any drift (dirs, AGENTS.md text, pre-commit YAML, .gitignore). — depends T041–T049.

---

## Phase 5 — Packaging, native-root migration, tests

- [ ] T050 ⏸️ DEFERRED (blocked on parallel native-root tooling) [Ph5] Native-root layout: write `.claude-plugin/plugin.json` (name/version/description/author/license); `git mv` SKILL.md → `skills/project-setup/SKILL.md`; **delete** old `.apm/skills/` tree; `${PLUGIN_ROOT}` script refs; assert no symlinks. (FR-027a) — depends T034.
- [ ] T051 ⏸️ DEFERRED (blocked on parallel native-root tooling) [Ph5] **Atomically** with T050: land the repo-wide tooling fix (build_inventory.py discovers `skills/*/SKILL.md` + reads `.claude-plugin/plugin.json`) + per-package `tag-separator: "--"` in release-please-config.json. **Coordinate with the parallel native-root effort** (T003). Without this the repo check-artifacts gate goes red. — depends T050.
- [x] T052 [Ph5] SKILL.md content: thin-config / thick-process (ensure uv, run end-to-end, sourcing, interview, diff/confirm, tiers, "done" definition, validity checks, safe execution, **secrets guardrail**). (FR-028, FR-043) — depends T034.
- [x] T053 [Ph5] Integration + guardrail tests: `test_baseline_scaffold.py` (SC-005, green only after Phase 4), `test_uv_missing.py` (SC-010 hard-fail), `test_home_not_authoritative.py` (SC-006), `test_input_types.py` (8 types, no secret, FR-043), offline stubs. — depends T04A, T050.
- [ ] T054 ⏸️ DEFERRED (blocked on parallel native-root tooling) [Ph5] `apm.yml` + `CHANGELOG.md` for the package; bump version; verify `apm install <path> --target claude` + `claude --plugin-dir packages/project-setup plugin details project-setup` + codex plugin add all resolve. (FR-007, FR-027) — depends T050, T051.

---

## Dependencies & parallelization

- **Phase 0 blocks everything.** No Phase 1+ task starts until T002 is ratified.
- Phase 1 is the spine; T010 (`contracts.py`) blocks nearly all of it. T011 is parallel to T010.
- Phase 2 depends on Phase 1 (T011, T012). Phase 3 depends on Phases 1+2.
- Phase 4 depends on the runner+SDK contract (T017, T031) being stable; T040 is the gate (reference module proves the contract) before fanning out T042/T043/T045/T048/T049 in parallel.
- Phase 5 T050+T051 are atomically coupled and coordinate with parallel native-root work (T003).
- **Build order**: T001–T003 → T010–T018 → T020–T023 → T030–T035 → T040 → (T041 → parallel T042–T049) → T04A → T050–T054.

## FR coverage note

31 of 44 FRs are cited inline above. The remaining 13 are **structural/cross-cutting**
and satisfied by the architecture as a whole rather than one task: FR-001/002/003
(generic runner + everything-is-a-module) is the premise of the entire layout
(Phase 1 + Phase 4); FR-004 (all-Python) is enforced by T050's no-`.sh` assertion;
FR-006 (declared+PEP723 deps) by T017/T040 skeletons + T054; FR-015 (Tier-1
byte-identical) by T018 + per-module SC-001 tests in Phase 4; FR-021
(home-not-authoritative) by T015 + T053; FR-023 (manifest-driven interview) by
T012 + T030; FR-031/032/034/040/042 (module structure, functional tests, no
declared outputs) by T012, T017, T035, T053. No FR is unowned.

## Suggested checkpoints (commit boundaries)

1. After T018 — runner spine + contracts, unit-tested.
2. After T035 — full runner pipeline runs an empty/no-module project end-to-end.
3. After T040 — one reference module proves the Model-B contract end-to-end.
4. After T04A — base bundle reproduces the legacy scaffold (SC-005).
5. After T054 — native-root package installs via all three channels.
