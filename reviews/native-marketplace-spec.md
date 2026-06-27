# Native Claude/Codex marketplace — implementation spec

Status: in progress on `feat/native-marketplace`. All findings VERIFIED against
`apm` 0.21.0, `claude` 2.1.195, `codex` 0.137.0, and `microsoft/apm` tag
`v0.21.0`. Full research record is in the original branch's
`reviews/marketplace-functional-cut-spec.md`; this file is the implementation
spec for the worktree.

## Problem

`apm pack` generates schema-valid marketplace catalogs, but every entry's
`source: ./packages/<name>` points at APM-native `.apm/` layout with no native
plugin layout. So Claude `/plugin install` and `codex plugin add` both fail
(`missing plugin.json`); only `apm install` (which understands `.apm/`) works.

## Decided architecture: two marketplaces

1. **In-repo APM catalog** — `apm pack` emits
   `.claude-plugin/marketplace.json` + `.agents/plugins/marketplace.json` listing
   ALL packages incl. steering. Consumed via `apm marketplace add` + `apm
   install`. Unchanged.
2. **Separate native marketplace repo** — generated FROM the APM inventory,
   filtered to natively-loadable plugins, entries pinned to `{name}--v{version}`
   `git-subdir` sources on agentic-packages. Consumed via Claude `/plugin
   marketplace add` + `codex plugin marketplace add`. Steering + steering-only
   packages are omitted, so the native silent-no-op trap never arises.

Plus: each package gets a committed native plugin layout (generated) so its
`source` is loadable by all three consumers.

## What's built so far

- **Tag migration to `{name}--v{version}`** (double dash): APM's remote version
  resolver matches that pattern only. `tag-separator: "--"` in the render-docs
  release-please generator + `apm.yml` `tagPattern`. 434 existing single-dash
  tags backfilled with double-dash twins (same commits) and pushed; future
  releases tag only `--`.
- **Hook unification** (7 packages): agent-coder, hooks-git-workflow,
  hooks-quality, mcp-repomix, hooks-worktree, hooks-subagent-worktree,
  code-intelligence — claude/codex variants made byte-identical (superset
  matcher `apply_patch|Edit|Write|MultiEdit`, kept async/timeout, carried
  Claude-only events Codex tolerates). Identical variants dedup on apm install
  (no leak) and let the generator emit one native `hooks/hooks.json`. Only
  speckit, speckit-dag-hooks, unstuck stay split (genuine per-harness logic).
- **`build-native-plugins.py`** generator: per-package
  `.claude-plugin/plugin.json` + native `skills/`, `agents/*.md`, `.mcp.json`,
  `hooks/hooks.json` (only when claude==codex), `dependencies` for bundles.
  Driven by `build_inventory.build_context()`, idempotent, `--check`. Skills +
  agents materialized whenever a package ships them (so multi-primitive bundles
  like speckit surface both). Wired into `build-artifacts` + `apm.yml` scripts.

## Native-catalog filter rule (verified by content scan)

EXCLUDE a package from the native marketplace when it has NO native component
(no skills/agents/hooks/mcp) — its only content is steering. Broader than
`classification==steering`:

- 16 steering packages — excluded (pure steering).
- `codex-hook-contract` (bundle, 0 deps, instructions-only) — excluded.
- `language-rust`, `language-typescript` (bundles, own content = 5 context files
  each; 3 apm deps) — excluded as standalone native entries; their first-party
  member deps are listed individually.

KEEP (native component works) but steering is APM-install-only — note in
description:
- `hooks-subagent-worktree` — hook native; "declare worktree isolation"
  instruction is apm-install-only.
- `mcp-tauri` — MCP native; Tauri instruction+context apm-install-only.

Filter = "ships at least one of skills/agents/hooks/mcp, OR is a bundle with
first-party native member deps".

## Known pre-existing issue (out of scope here)

`apm pack` exits 1 on `Unknown target 'kiro'` (root `apm.yml` declares
`targets: [claude, codex, kiro]`; this APM build rejects kiro for pack). It does
NOT block marketplace.json generation (written before the target check). Flagged
for a separate fix.

## Remaining work

- Native-catalog filter in the separate-repo generator.
- Separate native marketplace repo: generator + its own CI to regenerate +
  publish on release, pinned to `--v` tags.
- CI native-loadability gate: assert every listed native entry has plugin.json.
