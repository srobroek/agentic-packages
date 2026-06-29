# Feature 020 — Distribution Program (memory)

Consolidated single spec covering the whole distribution program (user: "build everything
in one spec"). Builds on spec 019 (answer-driven CLI). Full decision record in
`[[project-setup-distribution-program]]`.

## AS-BUILT (2026-06-29) — in-repo groups SHIPPED, full suite 943 passed, 4 deselected

- **Group A — SHA cache** (`1b3e0b4`): `locator.cache_key` keys git locators by
  `(origin, ref)` (sha256 of `origin@ref`) not origin-only, so different pinned refs of one
  addon repo coexist + the same (origin,ref) reuses one cache dir cross-project. Local
  locators unchanged. fetch.py needed no change (logic correct under the new key).
- **Group C — validation + authoring** (`1b3e0b4`): `validate_sources` extended with full
  schema validation — new `SOURCES_SCHEMA_INVALID` ErrorCode; mis-keyed records
  (`[[sources]]` plural / `id` / `git` / missing `locator`) now fail LOUD (was silent drop).
  Correct schema = `[[source]]`/`locator`/`ref`/`subdir`. Fixed examples/README.md (wrong
  schema + phantom `project-setup fetch` removed); shipped examples/shared-contracts.md
  (restored from specs/001 history); new examples/AUTHORING.md (sdk public API + standalone
  `uv run module.py --plan --step` test recipe); `cli.py --new-module <id> [--new-module-dest]`
  scaffolds a parseable starter module (no default_enabled). NOTE: AUTHORING.md honestly
  marks `merge_append_lines` as "not yet available" (it was in the reverted brownfield P1).
- **Group B — addon catalog** (`0126c2c`): `sdk.fetch_addon_catalog(url, *, timeout, _opener)`
  fetches a catalog JSON (list of {name,description,locator,category}, or object with
  modules/addons key) via stdlib urllib; never raises (→ []). `sdk.addon_catalog_urls(home)`
  resolves URLs from `PROJECT_SETUP_CATALOG_URL` env + home config `[catalog].urls` /
  `catalog_urls`; NO hardcoded URL (empty config → []). SKILL.md FR-005 step 2b: agent
  fetches configured catalogs, offers catalog addons alongside bundled (numbered tables +
  escape), writes the chosen addon's REF-PINNED `[[source]]` to sources.toml (ORG_SOURCE_UNPINNED
  enforces pinning). No catalog configured → unchanged bundled-only behavior.
- **Group D/E in-repo prep** (this commit): `addons/catalog.json` — first-party catalog of
  the 18 non-base modules ({name,description,locator,category,ref}, schema
  "project-setup-addon-catalog/v1", placeholder locators noted pending extraction; categories:
  language/quality/tooling/docs/agentic/integration/monorepo). `addons/publish-catalog.yml`
  — a TEMPLATE GH Actions workflow (parameterized org/repo) an addon repo copies to build +
  publish its catalog.json from modules/*/module.toml. **CLAUDE_PLUGIN_ROOT fix**: every
  `os.environ.get("PLUGIN_ROOT")` SDK-load fallback now `... or os.environ.get("CLAUDE_PLUGIN_ROOT")`
  — across all 24 modules + cli.py + executor (also sets both env vars) + the 2 examples/
  templates + the README snippet (so the live native-plugin env var works; the orchestrator
  caught cli.py + examples that the coder's first pass missed). paths.plugin_root() already
  handled both.

## ⚠️ USER HANDOFF — the OUTWARD remainder (not buildable here)
1. Create + push the standalone project-setup repo (outward action). The package is
   self-contained (spec 018/019 + the research) so extraction is config-only: single-package
   apm.yml at root, release-please simple mode, `apm pack` → single-plugin marketplace.
2. Once the standalone repo exists: update `addons/catalog.json` locators from placeholders
   (`<your-org>/project-setup/modules/<name>`) to the real ref-pinned repo paths, then
   (Group D thin-core) DELETE the 18 non-base modules from the bundled payload — they're
   fetched from the catalog instead. Do NOT delete before the fetch home exists.
3. Wire `addons/publish-catalog.yml` into the addon repo's `.github/workflows/`.
4. Verify the CLAUDE_PLUGIN_ROOT inline-substitution doc fact on a real /plugin install.
5. Decide monorepo disposition: exclude vs remove project-setup.

## Tests added: test_locator/test_fetch (SHA cache), test_validate_sources (+schema),
test_new_module_scaffold, test_addon_catalog (fetch/urls), test_addon_catalog_file (catalog.json +
CLAUDE_PLUGIN_ROOT fallback). Full suite 648 (session start) → 943.
