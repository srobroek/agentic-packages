# Implementation Plan: Modular, Config-Driven project-setup

**Branch**: `feat/project-setup-modular-redesign` | **Date**: 2026-06-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-project-setup-modular/spec.md`

## Summary

Replace the ~1106-line `project-setup.sh` monolith with a **runner + modules**
architecture: a generic Python runner (the skill itself, launched via `uv`) that
resolves module sources, fetches/caches them, discovers modules, conducts a
manifest-driven interview, topologically orders modules, runs a validate-closed
gate, executes each module as a `uv run module.py` subprocess reading frozen
inputs from disk, and persists per-module answers. Every capability (git,
github, dirs, pre-commit, license, gitignore, apm, speckit-bridge, language
overlays, package-add, identity) becomes a self-contained module. Delivered as
one cohesive build, in-repo at `packages/project-setup/` on the native-root
Claude-plugin layout.

This plan was produced by fanning out seven subsystem designs and an adversarial
coherence review. The review found the subsystems independently invented
**incompatible shapes for every shared contract** (the frozen-plan JSON, the
module result JSON, the error envelope, the answers schema, the import
mechanism, the cache location). Therefore the plan's first phase is non-optional:
**freeze the shared contracts in writing before any subsystem is coded.** The
contract documents live in [`contracts/`](./contracts/); the data shapes in
[`data-model.md`](./data-model.md); the developer walkthrough in
[`quickstart.md`](./quickstart.md).

## Technical Context

**Language/Version**: Python ≥3.11 (provided by `uv`; `tomllib` is stdlib from
3.11). No shell.

**Primary Dependencies**: `uv` (hard runtime prerequisite — fail loud, never
auto-install, no stdlib fallback). Standard library only for the runner core
(`tomllib`, `json`, `graphlib`, `dataclasses`, `pathlib`, `subprocess`,
`importlib.util`, `re`). TOML *writing* uses `tomli-w` declared via PEP 723 on
the few scripts that write TOML (no stdlib TOML writer exists). Module scripts
declare their own deps via PEP 723 inline metadata resolved per-invocation by
`uv run`.

**Storage**: Files only. Committed `.project-setup/sources.toml` +
`.project-setup/answers.toml`. Runtime artifacts (fetched module cache, frozen
execution plan) live OUTSIDE the committed tree, in `~/.cache/project-setup/`.

**Testing**: pytest via `uv run --with pytest pytest -q` (the existing CI
contract). Tests import the runner library by file path
(`importlib.util.spec_from_file_location` — the verified `speckit-dag-hooks`
precedent), since there is no editable install and no `pyproject` on the test
path. Per-module functional tests assert on-disk state matches recorded answers.

**Target Platform**: macOS + Linux dev machines and CI, under Claude Code, Codex,
and `apm install`. The runner is runtime-agnostic; enforcement is in the
runner/modules, not in any harness hook.

**Project Type**: CLI tool + agent skill (a Claude/Codex/APM plugin package).

**Performance Goals**: Not latency-bound. The only cost of note is per-module
`uv run` startup (~hundreds of ms × ~15 modules); acceptable, mitigated by uv's
resolution cache. CI nested `uv run` must be cache-warmed/offline (see Risks).

**Constraints**: Determinism is two-tier and version-relative — Tier-1 scripted
modules are byte-identical for the same answers + unchanged module versions
(SC-001); Tier-2 agent-steered steps are consistent-not-identical. The runner
contains zero project-specific payloads (SC-002). A clone reproduces from
committed files alone (SC-004).

**Scale/Scope**: ~15–21 base modules migrated from the monolith + 4 language
overlays + package-add; a runner library of ~10 modules; one shared-contracts
module every subsystem imports.

## Constitution Check

The project constitution (`.specify/memory/constitution.md`) is an unfilled
template — no ratified principles to gate against. This plan instead gates on the
spec's binding constraints (sections A–I) and the verified-fact list in
`memory.md`. No constitution violations to track.

## Phase 0 — Freeze shared contracts (BLOCKING; no code until done)

The coherence review proved the subsystems cannot compose until these are
settled. Each becomes a written contract under `contracts/`. **No subsystem
implementation may begin until Phase 0 is merged.**

1. **Resolve the FR-009 vs Section-I `module.toml` contradiction** — Section I
   wins. The binding manifest schema is: `[meta]`(repository, author);
   `[module]`(id `<noun>-<verb>`, name, version, description, reconcile);
   `[order]`(requires/after/before); `[tools]`(required); `[[inputs]]`(key, type,
   prompt, choices, default, required); `[[steps]]`(id, kind=python|agent|gate,
   +steering/+message). FR-009's `title`/`entrypoint`/`required_answers`/
   `optional_answers`/`kind@module` wording is **superseded**; the spec text is
   restated to match Section I (see "Spec amendments" below). A
   `FORBIDDEN_FIELD` located error rejects `priority`, `title`, `entrypoint`,
   `required_answers` so "no priority" (C3) is *enforced*, not merely unread.
   → `contracts/shared-contracts.md` §1
2. **One frozen-plan JSON schema + one canonical serializer.** Serializer is
   exactly `json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"`
   (verified `build_nodes.py:560` precedent). The plan **builder**
   (manifest-validator) and plan **reader** (module SDK) share one dataclass and
   one on-disk key set; the runner and config-answers consume, never redefine.
   The frozen plan lives in the runtime cache (`~/.cache/project-setup/`), **never
   inside the committed `.project-setup/`**. Absolute paths are excluded from any
   field that feeds Tier-1 output (determinism). → `contracts/shared-contracts.md` §2
3. **One shared-contracts module** (`contracts.py` in the runner library) owning:
   the structured-error envelope `{error_code, module_id, module_ids: list,
   expected, received, how_to_fix}` (note the added `module_ids` for
   collision/cycle multi-id errors); ALL `error_code` constants; the module
   result-JSON shape (settle the `files_written` key name — **`files_written`**,
   not `files`); the provenance enum **extended** to `{default, flag, home,
   project, derived, agent-steered}` (adds `project` for committed re-run values
   and `derived` for module-computed values); and the `schema_version` governance
   (who bumps, what the runner does on mismatch). All gates and the SDK import
   from it. → `contracts/shared-contracts.md` §3–5
4. **Import mechanism** — `importlib.util.spec_from_file_location` (the verified
   no-pyproject precedent) for both the runner's own tests AND `module.py`'s
   access to the SDK. The SDK is vendored as a single file the runner exposes at
   a known path under the plugin root; `module.py` loads it by path, not by
   package name (no `sys.path` assumption, no PyPI dep). The `PLUGIN_ROOT` token
   resolution is pinned (see fix #6). → `contracts/shared-contracts.md` §6
5. **Answers/sources file schemas** — `.project-setup/answers.toml` uses
   per-module `[module.<id>]` value tables with **per-key** provenance under a
   parallel `[module.<id>.source]` table; `.project-setup/sources.toml` carries
   `[meta] skill_version` (advisory) + structured `[[source]]` records (locator,
   ref, subdir parsed by sources-discovery only). Modules may emit only
   `default|derived|agent-steered` provenance; persistence assigns
   `flag|home|project`. → `contracts/shared-contracts.md` §8
6. **PLUGIN_ROOT + file-tree + package name unification.** Pin: the runner
   library lives at `packages/project-setup/skills/project-setup/runner/`
   (importable by file path), the SDK at `.../runner/sdk.py`, base modules at
   `.../skills/project-setup/modules/<id>/`. Scripts/manifests reference assets
   via the repo's real APM token `${PLUGIN_ROOT}` (NOT `${CLAUDE_PLUGIN_ROOT}`);
   the runner resolves a `plugin_root()` that prefers the env token and falls
   back to a `__file__`-relative path that works on the APM channel where the
   token is unset at runtime. One package name across all runner-touching
   subsystems. → `contracts/shared-contracts.md` §6
7. **Collision rule (FR-011 vs FR-036)** — same-root-kind id collision = HARD
   located error (`ID_COLLISION` with `module_ids`); across precedence levels =
   reported shadow (higher precedence wins, winner logged). `default_enabled` is
   tri-state `Optional[bool]` so FR-035 can reject a third-party module that set
   it. → `contracts/shared-contracts.md` §7

**Spec amendments produced by Phase 0** (applied to `spec.md` as part of this
phase): restate FR-009 to Section I; widen the provenance enum (FR-018); add the
`module_ids` error field (FR-017); name the canonical serializer and frozen-plan
location (FR-008/FR-019); name the collision boundary (FR-011/FR-036). These are
reconciliations of internal spec tension, not scope changes.

## Phase 1 — Runner library + shared contracts (the spine)

Build order strictly after Phase 0. All under
`packages/project-setup/skills/project-setup/runner/`.

1. `contracts.py` — the Phase-0 shared contracts as code (error envelope + codes,
   result shape, provenance enum, schema_version). Everything imports this.
2. `paths.py` — `plugin_root()`, `bundled_modules_dir()`, `cache_dir()` (owns the
   single fetch-cache + frozen-plan-location constants), `project_setup_dir()`,
   `home_config_path()`. Sole owner of all path constants.
3. `manifest.py` — `module.toml` parser (`tomllib`) → `ModuleManifest`;
   `FORBIDDEN_FIELD`/unknown-field rejection; input-type validation for all 8
   types.
4. `order.py` — **pure, non-raising** topo check returning accumulated errors +
   the stable order (`graphlib.TopologicalSorter`, predecessor-insertion order,
   tie-break by id; cycle/missing-requires *collected*, not raised). Mirrors
   `build_nodes.py` cycle extraction (`exc.args[1]`).
5. `validate.py` — the single validate-closed gate: accumulates cycle +
   missing-requires + missing-answer + missing-required-tool (incl. the
   which-on-PATH check I8/FR-038 mandates) and reports **all at once**, then
   orders. The only place that raises `GateFailure`.
6. `answers.py` — config layering + deep-merge (tables union, scalars replace,
   lists replace + explicit `append`/`remove`; magic-key collision guarded), the
   defaults chain (module < home < project < user-choice), and the single
   `resolve_final_answers()` that materializes the authoritative coerced answer
   map both validate and plan-freeze consume. Canonical TOML/JSON round-trip.
7. `plan.py` — builds the `ExecutionPlan` dataclass, coerces answers ONCE,
   embeds the stable order, freezes to the cache via the one canonical
   serializer.
8. `sdk.py` — the module-author API loaded by `module.py` via importlib:
   `load_frozen_inputs()`, typed accessors for **all 8** input types
   (incl. `get_multichoice`/`get_text`), `idempotent_write()`, `tool_or_fallback()`,
   `emit_result()` (the one result-JSON writer), `is_safe_relative_path()` (one
   correct path-traversal primitive, allows subdirs, blocks `..`/abs/symlink
   escape).
9. `errors` integration test + `order`/`validate`/`answers`/`plan` unit tests
   (import-by-path; CI-shaped).

## Phase 2 — Sources, discovery, cache

1. `sources/locator.py` — sole owner of locator parsing (`owner/repo/subdir#ref`,
   git path, local); structured `Locator`.
2. `sources/fetch.py` — git fetch → `~/.cache/project-setup/` (own constant from
   `paths.py`), proceed-on-failure offline, `SourceReport`.
3. `sources/discover.py` — search-path precedence (env `PROJECT_SETUP_MODULES_DIR`
   > project `./.project-setup/modules/` > home > fetched > bundled at
   `${PLUGIN_ROOT}/.../modules`), id-collision rule from contract #7,
   tri-state `default_enabled` enforcement (FR-035). Fetch happens BEFORE
   discovery.

## Phase 3 — Pipeline, executor, modes, persistence

1. `pipeline.py` — the 8-stage spine + mode detection (`sources.toml` presence).
2. `executor.py` — Model-B subprocess (`uv run module.py --plan <frozen> --step
   <id>`), result-gate validation, per-module failure isolation **with** a
   distinct `UV_MISSING` re-check (a vanished `uv` mid-run hard-fails, not
   skip), and the runner-side `files_written ⊆ project_dir` guard.
   Renders `kind=gate` messages and captures confirmation; hands `kind=agent`
   steering to the agent and folds the returned decision back as
   `agent-steered` provenance.
3. `reproduce.py` — the **pre-write** diff/confirm engine. Resolves the
   circular-ordering bug: Tier-1 python steps run a **`--inspect` dry pass** that
   emits proposed `files_written`+`diffs` WITHOUT writing; the confirm list is
   built from that; on confirmation the same step runs for-real, with a
   guarantee that inspect-preview == write for Tier-1. Reconcile overwrites only
   confirmed files.
4. `persist.py` — writes `.project-setup/{sources,answers}.toml` (per-key
   provenance), advisory `skill_version` drift warning, package `.gitignore`
   entries for pytest artifacts (cache is home-global, needs none).

## Phase 4 — Module migration (the capabilities)

Each becomes `modules/<id>/{module.toml, module.py, [helpers], [steering/],
[templates/], test_*.py}`. Mapping (Tier per step; reconcile y/n) is in
[`data-model.md`](./data-model.md). Notable rulings from the review:

- **core-identity** collects only identity (name/org/description/license-choice);
  cross-module values (init_git, create_repo, layout) are interview answers
  layered to consumers, NOT pushed module-to-module.
- **gitignore-generate**: vendored CC0 github/gitignore templates (base set) +
  on-demand github/gitignore fetch. SC-005 parity targets each legacy overlay's
  **static-fallback heredoc** (the `gh:`=toptal output is out of scope), not the
  legacy gitnr output.
- **speckit-bridge** delegates to the installed `speckit` package's
  `setup-speckit.sh` via subprocess (allowed by FR-029; it's a delegated tool,
  not runner shell).
- **lang-{ts,python,go,rust}** steps that run `uv add`/`cargo init`/etc. are
  `kind=python` but **not byte-identical** (they invoke external installers);
  they preserve the legacy gitignore idempotence grep-markers
  (`__pycache__`/`*.test`/`/target`/`node_modules`).
- **git-init** carries the macOS provenance-xattr clear and the Codex
  read-only-protected-paths preflight (`fail_if_codex_protected_paths_are_readonly`).
- **package-add** ports the path-traversal guards (reject `..`/abs/separators)
  verbatim — a load-bearing security behavior the old bats suite pinned.
- Golden fixtures: the monolith's literal `DIRS[]` (21), monorepo `TARGETS` (15),
  both AGENTS.md heredocs, and the default apm/MCP package lists
  (`core@srobroek-agentic` + 4 baseline MCP).

## Phase 5 — Packaging, native-root migration, tests

1. Native-root layout: write `.claude-plugin/plugin.json`; `git mv` SKILL.md to
   `skills/project-setup/SKILL.md` and **delete** the old `.apm/skills/` tree;
   `${PLUGIN_ROOT}` script refs; no symlinks.
2. **Atomically** land the repo-wide tooling fix (this is owned here, NOT
   "parallel separate work"): teach `build_inventory.py` to discover skills via
   `skills/*/SKILL.md` + read `.claude-plugin/plugin.json`, and add a
   per-package `tag-separator: "--"` override in `release-please-config.json` for
   `<name>--v<version>`. Without this the whole-repo check-artifacts gate goes red.
   *(Coordinate with the parallel native-root effort the user flagged; verify together.)*
3. pytest suite: runner unit tests (import-by-path), per-module functional tests,
   `test_baseline_scaffold.py` (the SC-005 integration gate — green only after
   Phase 4), a `uv`-missing hard-fail test (SC-010), a home-not-authoritative
   test (SC-006), an input-types/secrets-guardrail test (FR-043), and an
   offline network stub for gitignore-generate's fetch (hermetic CI).
4. SKILL.md content: thin-config/thick-process (ensure uv, run end-to-end,
   sourcing, interview, diff/confirm, tiers, "done", validity, safe execution,
   secrets guardrail).

## Project Structure

### Documentation (this feature)

```text
specs/001-project-setup-modular/
├── plan.md              # this file
├── spec.md              # the spec (amended by Phase 0)
├── memory.md            # decision rationale + verified facts
├── memory-synthesis.md  # compact planning summary
├── research.md          # Phase 0 findings + verified-fact ledger
├── data-model.md        # module migration map + dataclass shapes
├── quickstart.md        # "author a module" + "run the runner" walkthrough
├── contracts/           # the 7 frozen shared-contract docs (Phase 0)
└── tasks.md             # produced by /speckit.tasks (NOT this command)
```

### Source Code (repository root)

```text
packages/project-setup/
├── .claude-plugin/
│   └── plugin.json                 # required native-root manifest
├── apm.yml                         # package metadata
├── CHANGELOG.md
├── skills/
│   └── project-setup/
│       ├── SKILL.md                # thin-config / thick-process (migrated off .apm/skills)
│       ├── runner/                 # the runner library (import-by-path)
│       │   ├── contracts.py        # shared error/result/provenance contracts
│       │   ├── paths.py            # all path + cache constants (sole owner)
│       │   ├── manifest.py         # module.toml parse + validate
│       │   ├── order.py            # pure non-raising topo
│       │   ├── validate.py         # the one validate-closed gate
│       │   ├── answers.py          # layering/merge + resolve_final_answers
│       │   ├── plan.py             # ExecutionPlan build + canonical freeze
│       │   ├── sdk.py              # module-author API (loaded by module.py)
│       │   ├── pipeline.py         # 8-stage spine + mode detection
│       │   ├── executor.py         # Model-B subprocess + gates + guards
│       │   ├── reproduce.py        # pre-write inspect/diff/confirm + reconcile
│       │   ├── persist.py          # .project-setup/* writers
│       │   ├── cli.py              # entry; uv preflight
│       │   └── sources/            # locator, fetch, discover
│       └── modules/                # base modules (default_enabled bundle)
│           ├── core-identity/      # {module.toml, module.py, test_*.py}
│           ├── git-init/
│           ├── github-repo/
│           ├── dirs-scaffold/
│           ├── precommit-setup/
│           ├── agents-md/
│           ├── codex-config/
│           ├── justfile-create/
│           ├── license-write/
│           ├── gitignore-generate/
│           ├── apm-install/
│           ├── speckit-bridge/
│           ├── quality-hooks/
│           ├── package-add/
│           └── lang-{ts,python,go,rust}/
└── tests/                          # runner-level pytest (import-by-path)
```

**Structure Decision**: Native-root Claude-plugin layout (H3/FR-027a). The
runner library lives under the skill dir (resolved via `${PLUGIN_ROOT}`),
imported by file path (no pyproject/editable install — the verified
`speckit-dag-hooks` precedent). Modules are sibling directories discovered at
runtime; base modules ship bundled, others arrive via sources or local roots.

## Complexity Tracking

| Decision | Why needed | Simpler alternative rejected because |
|----------|------------|--------------------------------------|
| One shared `contracts.py` every subsystem imports | Coherence review found 4 independent definitions of the error envelope, 3 of the plan model, 2 canonical serializers | Letting each subsystem own its types produced incompatible shapes that cannot read/write the same files |
| Pre-write `--inspect` dry pass for diff/confirm | FR-024/SC-007 require confirm-BEFORE-write, but drift is only knowable from a module's runtime output | Reading post-execution diffs to gate the write is circular; a prior-files hash alone can't preview new content |
| Import-by-file-path (not packaged install) | Zero pyproject precedent; `uv run` subprocess has no sibling dir on `sys.path`; APM copies files without installing | A packaged SDK on PyPI/editable install has no working precedent on any of the three channels |
| Phase 0 blocking contract-freeze | Independent subsystem designs disagreed on every shared contract | Starting code first guarantees rework when the seams don't meet |
