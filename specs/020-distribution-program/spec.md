# Feature Specification: Distribution Program (addon catalog + SHA cache + thin core + standalone repo + authoring)

**Feature Branch**: `feat/project-setup-modular-redesign` (continues) → likely a
dedicated `feat/distribution-program` branch

**Created**: 2026-06-29

**Status**: **Implemented (in-repo groups) (2026-06-29)** — Groups A (SHA cache), B (addon
catalog + agent offer), C (sources schema validation + author docs/scaffold), and the
in-repo prep of D/E (addon catalog.json + publish-workflow template + CLAUDE_PLUGIN_ROOT
token fix) are SHIPPED; full suite 943 passed, 4 deselected. The OUTWARD remainder — actually
creating/pushing the standalone repo, wiring the catalog-publish workflow to a live repo,
and deleting the 18 modules from the bundled payload once they have a fetch home — is a
USER HANDOFF (see AS-BUILT + the program memory). Consolidated at the user's request;
builds on spec 019. See `memory.md` AS-BUILT + `[[project-setup-distribution-program]]`.

**Input**: User: make project-setup a standalone, distributable tool — own repo + native
Claude plugin; thin 6-module core + addon modules fetched from git (internal AND external);
SHA-keyed module cache; CI/CD to publish catalogs; document how to add + develop modules.
"Build everything in one spec."

## The program (6 capability groups, in build order)

> **A — SHA-keyed module cache.** The git source cache keys on normalized origin ONLY
> (`locator.cache_key`), so two projects pinning different refs of one addon repo thrash a
> single dir. Re-key by `(origin, ref)` (or resolved commit SHA) so pinned versions coexist
> and reuse across projects. In-repo, no external dep. SHIP FIRST.
>
> **B — Addon catalog + agent-offered addons.** A runtime-fetched catalog (JSON index of
> `{name, description, locator, category}`) from a CONFIGURABLE URL (precedent:
> speckit-setup's community catalog). The runner fetches it; the agent presents catalog
> addons alongside bundled modules in the interview (per the table/escape RULES); the user
> picks → entries written to `.project-setup/sources.toml` (ref-pinned) → fetched on demand
> → modules become selectable. Catalog URL overridable (your / org / none / multiple).
> Support BOTH internal and external catalogs. The headline capability. In-repo.
>
> **C — sources.toml schema validation + addon-author docs + new-module scaffold.** Fix
> the broken `examples/README.md` addon schema (`[[sources]]`/`id`/`git` + phantom
> `project-setup fetch` → real `[[source]]`/`locator`); ship or strip `shared-contracts.md`;
> document the sdk public API + a standalone module-test recipe; add `sources.toml` schema
> VALIDATION (loud error on mis-keyed records, today silently dropped); add a
> `project-setup new-module <id>` scaffold. In-repo.
>
> **D — Thin core.** Reduce the bundled payload to the 6 base modules
> (core-identity, dirs-scaffold, gitignore-generate, license-write, agents-md, git-init);
> the other 18 become catalog-fetched addons. DEPENDS ON B + a real catalog/fetch home (the
> standalone repo, group E) — so the actual module MOVE is staged behind extraction;
> what ships in-repo now is the catalog ENTRIES for the 18 + the mechanism, not deleting
> them from the payload.
>
> **E — Standalone repo + native Claude plugin + catalog-publish CI/CD.** Move the package
> to its own repo; native-root plugin via APM (`apm pack` → `.claude-plugin/{plugin.json,
> marketplace.json}`); release-please simple mode; CI/CD that PUBLISHES the addon catalog
> (internal + external). OUTWARD ACTION (new repo creation/push) — staged behind a user
> handoff; this spec prepares everything extractable in-repo (single-package apm.yml shape,
> the catalog-publish workflow file, the `CLAUDE_PLUGIN_ROOT` token fix) but does NOT create
> the remote repo.

## Settled decisions (from the program memory — all user-confirmed)

- 6-module bundled core; everything else an addon. Offline-safety is MOOT (Claude Code
  needs network), so the only real costs of fetching are latency (mitigated by SHA cache,
  group A) + fetch-failure (already soft-fail). Determinism holds because addon sources are
  ref-pinned (spec-014 `ORG_SOURCE_UNPINNED` gate enforces).
- Runtime-fetched catalog from a configurable URL; agent both READS declared config sources
  AND proactively OFFERS catalog addons. Internal + external.
- Native Claude plugin via APM is the distribution form ("too complex" refuted for a pure
  skill); NOT a bundled CLI tool (loses the agent model).
- Separate repo for the whole package; self-contained → low-risk, config-only extraction.

## Functional Requirements

### Group A — SHA-keyed module cache

- **FR-A1**: `locator.cache_key` MUST incorporate the resolved ref so different pinned refs
  of the same origin map to DIFFERENT cache dirs (e.g. key = hash of `normalized_origin +
  "@" + ref`). Local-path locators unchanged. The change MUST be backward-compatible: a
  fresh cache is rebuilt; no migration of existing cache dirs required (stale dirs are
  harmless and re-created under the new key).
- **FR-A2**: `fetch.py` MUST continue to clone/checkout into `sources_cache_dir()/<key>`
  with the new key, so the SAME (origin, ref) reuses one dir across projects (the
  cross-project reuse + latency win). Two projects on the same addon@ref share a cache hit;
  two projects on different refs do not collide.
- **FR-A3**: No behavior change to discovery/precedence; only the cache key + dir layout.
  Existing fetch tests MUST stay green (adjust only those that assert the old origin-only
  key shape).

### Group B — Addon catalog + agent-offered addons

- **FR-B1**: A new `sdk` helper `fetch_addon_catalog(url, *, timeout=...)` MUST fetch a
  catalog JSON from a URL (stdlib urllib, like `verify_pins`), returning a list of
  `{name, description, locator, category}` records. Network failure / malformed / empty →
  empty list, NEVER raises (mirror `detect_marketplaces`/`verify_pins` defensiveness).
- **FR-B2**: The catalog URL(s) MUST be CONFIGURABLE and OVERRIDABLE: read from the home
  config (`~/.config/project-setup/config.toml`, a `[catalog] urls = [...]` or
  `catalog_urls`) and/or an env override (`PROJECT_SETUP_CATALOG_URL`); ZERO hardcoded
  srobroek/org default URL (consistent with spec 018 standalone). No catalog configured →
  no remote fetch (the agent offers only bundled + any declared sources).
- **FR-B3**: The catalog supports BOTH internal and external sources — it is just a list of
  records pointing at git locators; an org publishes its own catalog JSON at its own URL.
- **FR-B4**: SKILL.md FR-005 interview MUST gain an addon step: the agent calls
  `fetch_addon_catalog` for each configured URL, presents the catalog addons (per the
  table/`other`-escape/honest-curation RULES) ALONGSIDE bundled modules, and on selection
  writes the chosen addons' locators (ref-PINNED) into `.project-setup/sources.toml`. The
  user may also paste a raw locator (the existing manual path). Then the runner fetches +
  discovers them (existing `[[source]]` mechanism).
- **FR-B5**: A selected addon's source MUST be ref-pinned when written (reuse the spec-014
  `ORG_SOURCE_UNPINNED` rule — an unpinned catalog locator is rejected/escalated, not
  silently floated). Catalog records SHOULD carry a recommended ref; if absent, the agent
  asks or pins to a resolved default.
- **FR-B6**: This is additive — with no catalog configured and no sources declared, behavior
  is exactly today's bundled-only flow.

### Group C — Validation + authoring docs + scaffold

- **FR-C1**: `validate_sources` (pipeline.py, from spec 014) MUST be extended to a full
  `sources.toml` SCHEMA validation: a record using the WRONG keys (`[[sources]]` plural,
  `id`, `git`) or missing `locator` MUST produce a loud `SetupError`
  (`SOURCES_SCHEMA_INVALID` or reuse an existing code) — NOT be silently dropped. The
  correct shape is `[[source]]` with `locator` (+ optional `ref`, `subdir`).
- **FR-C2**: `examples/README.md` MUST be corrected: the addon-source schema example fixed
  to `[[source]]`/`locator`/`ref`/`subdir`, and the non-existent `project-setup fetch`
  instruction removed (fetch is automatic in the pipeline).
- **FR-C3**: `shared-contracts.md` (referenced 10+ times in examples/README.md + persist.py
  but NOT shipped) MUST be either shipped under the skill dir OR all references stripped and
  the contract inlined into examples/README.md. (Decide at build: ship if the content
  exists in history; else inline a concise contract section.)
- **FR-C4**: The sdk PUBLIC API for module authors MUST be documented (in examples/README.md
  or a sibling AUTHORING.md): `load_frozen_inputs`/`FrozenInputs` accessors, `emit_result`/
  `ModuleResult`, `idempotent_write`, `merge_append_lines`, `run_tool`, `append_if_absent`,
  `verify_pins`, `looks_like_secret`, `scan_top_level_dirs`, `detect_marketplaces`,
  `fetch_addon_catalog`, `is_safe_relative_path` — name, signature, one-line purpose. Plus a
  standalone module-test recipe (`uv run module.py --plan <frozen> --step <id> [--inspect]`).
- **FR-C5**: A `project-setup new-module <id>` scaffold MUST be added (a CLI subcommand or a
  small script) that writes a starter module dir (module.toml + module.py from a template +
  a test stub) so external authors don't hand-copy a bundled module. `default_enabled` MUST
  be omitted/false (it is FORBIDDEN on non-bundled modules).

### Group D — Thin core (staged)

- **FR-D1**: The 6 base modules (core-identity, dirs-scaffold, gitignore-generate,
  license-write, agents-md, git-init) remain bundled. The other 18 are designated ADDONS.
- **FR-D2**: A canonical first-party addon CATALOG file MUST be authored in-repo (the JSON
  index B consumes) listing the 18 non-base modules with their locator (pointing at the
  standalone repo's module path once extracted) + category + recommended ref. Until
  extraction (group E), the locator points at the current monorepo path / is marked
  pending-extraction; the 18 modules are NOT yet deleted from the payload (deleting them
  before they have a fetch home would break every run). The MOVE is the extraction step.
- **FR-D3**: When the modules DO move (post-extraction), removing them from the bundled
  payload MUST NOT change behavior for a user who selects them — they are fetched from the
  catalog locator and discovered identically (the discovery FETCHED tier already supports
  this). A greenfield run selecting lang-python fetches it from the catalog.

### Group E — Standalone repo + native plugin + catalog CI/CD (staged behind handoff)

- **FR-E1**: A single-package `apm.yml` shape + native-plugin manifest plan MUST be prepared
  in-repo (documented + the `CLAUDE_PLUGIN_ROOT` token fix applied to SKILL.md where
  `PLUGIN_ROOT` is still referenced). The actual repo creation/push is a USER action (outward).
- **FR-E2**: A catalog-publish CI/CD WORKFLOW (GitHub Actions YAML) MUST be authored that
  builds + publishes the addon catalog JSON from a repo of modules (so internal AND external
  authors can run the same workflow to publish their own catalog). The workflow file is
  prepared in-repo; wiring it to a live repo is part of the user handoff.
- **FR-E3**: Verify the `CLAUDE_PLUGIN_ROOT` inline-substitution doc fact before relying on
  the native-plugin run path; the only code change is the token rename in SKILL.md.

### Cross-cutting

- **FR-X1**: ZERO hardcoded srobroek/org references anywhere new (catalog URLs, locators) —
  consistent with spec 018. Defaults are empty/none; the user/org supplies their catalog.
- **FR-X2**: The full suite MUST stay green at every group's gate. Each group is additive.
- **FR-X3**: Determinism preserved: catalog fetch + addon fetch happen at INIT; the chosen
  locators (ref-pinned) are frozen to sources.toml; reproduce replays them (existing
  machinery). The catalog itself is NOT frozen (it is a discovery aid, like a marketplace
  browse), only the chosen source locators are.

## Success Criteria

- **SC-A**: Two projects pinning `org/addons#v1` and `org/addons#v2` resolve to DIFFERENT
  cache dirs and both succeed; two projects on `org/addons#v1` share one cache dir (reuse).
  Fetch tests green.
- **SC-B**: `fetch_addon_catalog(url)` returns parsed records for a valid catalog; network
  failure / malformed / empty → `[]` no raise. With a configured catalog URL the agent can
  present its addons; with none configured, no remote fetch occurs. Selecting an addon
  writes a ref-pinned `[[source]]` to sources.toml; the addon's modules then discover.
- **SC-C**: A `sources.toml` with the WRONG schema (`[[sources]]`/`id`/`git`) produces a
  loud `SOURCES_SCHEMA_INVALID` error (not silent drop). examples/README.md documents the
  correct schema + no `project-setup fetch`. `project-setup new-module foo` writes a valid,
  parseable starter module. sdk API documented.
- **SC-D**: The first-party addon catalog JSON lists the 18 non-base modules with locator +
  category + ref and parses via `fetch_addon_catalog`. (Module deletion from payload is
  deferred to extraction; not tested here.)
- **SC-E**: The catalog-publish workflow YAML is present + lints; SKILL.md uses
  `CLAUDE_PLUGIN_ROOT`. (Repo extraction itself is the user handoff, not gated here.)
- **SC-X**: `rg -i srobroek` over the shipped skill stays ZERO; full suite green.

## Out of Scope

- The actual remote-repo creation/push + wiring the catalog-publish workflow to a live repo
  (USER handoff — outward action).
- Deleting the 18 modules from the bundled payload before extraction gives them a fetch home
  (would break every run).
- A signed/curated catalog trust framework beyond ref-pinning (future).
- Brownfield (017/008, deferred).

## Dependencies

Builds on 019 (answer-driven CLI), 018 (standalone/detection), 014 (ORG_SOURCE_UNPINNED),
003/004 (sources/fetch/discover, gates). Touches `runner/sources/locator.py` (cache key),
`runner/sources/fetch.py`, `runner/sdk.py` (fetch_addon_catalog), `runner/pipeline.py`
(validate_sources schema), `runner/cli.py` (new-module), SKILL.md (interview + token), a
new in-repo addon catalog JSON, `examples/README.md`/AUTHORING docs, and a catalog-publish
workflow YAML. No change to the pipeline stage model.
