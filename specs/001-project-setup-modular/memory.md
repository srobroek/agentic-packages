# Feature Memory: project-setup modular redesign

Feature-local working notes. Durable project memory lives in `docs/memory/`
(currently greenfield — none exists). This file is transient feature context.

## Memory state at spec time

- Greenfield: no `docs/memory/`, no durable memory, `mcp-speckit-memory` MCP not
  connected this session. `.specify/memory/constitution.md` is an unfilled
  template (no governing principles to honor).
- First feature in `specs/` (sequential numbering → `001-project-setup-modular`).

## Constraints carried in from investigation (verified facts)

- **Portability floor (hard, for shell):** macOS system bash 3.2.57 +
  `set -euo pipefail` + BSD sed/grep/awk. No associative arrays, no `mapfile`,
  no GNU-only flags. Proven-safe patterns already in `apm-discover.sh`:
  `while IFS= read -r` into arrays, `${arr[@]+"${arr[@]}"}` empty-array guard,
  `case "$SEEN" in *"|$id|"*)` substring registry.
- **Dependency floor (for structured parsing):** the scripts resolve `python3`
  from PATH. Only python3 **stdlib (JSON)** is guaranteed for arbitrary
  installers. VERIFIED: `/usr/bin/python3` = 3.9.6 (no `tomllib`, no `tomli`,
  no TOML writer). mise python 3.14 has `tomllib` + PyYAML, but PyYAML is only
  guaranteed inside apm-cli's OWN env, NOT the PATH python the scripts call.
  ⇒ A bare skill calling PATH python3 can safely assume only JSON.
- **Existing precedent to generalize:** `apm-discover.sh` resolves the
  preferences index via `APM_PACKAGE_PREFERENCES_FILE` env > `./indexes/`
  project-local > `$SCRIPT_DIR/../indexes/` bundled. The index was co-located
  INSIDE the skill in #393 ("co-locate skill scripts so they resolve after
  install"). This is the model for "config outside the skill body."
- **bats contract (must stay green in Phase 1):** `packages/project-setup/tests/setup.bats`
  pins the flag interface (`--name/--org/--no-repo/--no-git/--no-apm-install/
  --layout/--target/--lang`...), scaffold outputs (AGENTS.md, .gitignore,
  .pre-commit-config.yaml, docs/, specs/, no apps/ in single layout),
  empty-array safety under set -u, BSD-safe `--help`, and the gitnr-fails
  fallback.
- **project-setup.sh** is ~1106 lines, hardcoded numbered Steps 1–11.
  Language overlays (`setup-{ts,python,go,rust}.sh`) are already module-shaped.
  SpecKit is already delegated to its own `speckit` package. Serena is doc-only.

## Decisions locked with the user

- Keep project-setup IN `agentic-packages` (no separate repo).
- Dual-distribute: APM package + Claude Code plugin marketplace (both already
  exist here; project-setup is registered in both marketplace.json files).
  "Installable into Claude without APM" = the plugin marketplace path. No
  standalone deploy script.
- Scope: INCREMENTAL, data-out-first. Phase 1 = extract hardcoded payloads to
  overlay-able config + manifest registry + manifest-generated interview, keep
  flag surface + setup-*.sh, keep bats green. Phase 2 (spec-only, not built) =
  full module engine (multi-root discovery, deep-merge overlay, topo plan,
  user + apm-package module roots, generated reference docs).
- Config format: TOML/YAML for human-authored surfaces, JSON for the internal
  merged execution plan (byte-stable determinism).
- Tooling-distribution is the load-bearing OPEN decision for the spec to
  resolve: ship-scripts-with-skill (PATH python3, stdlib-only) vs build-as-tool
  (pyproject declared deps) vs binary-via-APM vs uv inline deps (PEP 723).

## Resolved decisions (grill-me session, 2026-06-27)

The open questions below were resolved by a relentless `grill-me` interview.
Each ruling and its rationale:

1. **uv prerequisite, no fallback.** Plugin install only copies files (verified:
   Claude plugin entry schema = name/description/version/tags/source — no
   install/build hook), so declared pyproject deps never run on the plugin
   channel. Therefore `uv` is the single hard runtime prerequisite: fail loud
   with an install message, never auto-install, NO stdlib fallback ("messy").
   Deps via pyproject + PEP 723 inline, provided by `uv run`.
2. **All Python; drop shell.** This dissolves the bash-3.2/BSD floor entirely
   (shellcheck/bats gone). Tests = pytest via `uv run`. The 4 lang overlays are
   PORTED to Python, not lifted. Honest cost: more work than "reuse" implied.
3. **TOML everywhere human-authored, JSON internal plan.** TOML on the critical
   path is fine because uv guarantees the parser.
4. **Runner + modules; no capability core.** Even identity (`core-identity`) and
   package-add are modules. The runner is the one irreducible engine = the skill.
   "Base" = the `default_enabled` bundle (mirrors how frontend/security bundles
   compose).
5. **Ordering via before/requires/after + topo sort; no priority.** Independent
   modules touch disjoint outputs so either order is fine; topo emission is
   stable (sort by id within a level).
6. **Two-tier determinism, version-relative.** Tier-1 scripted byte-identical;
   Tier-2 agent-steered marked + instructed + persisted. SC-001 → Tier-1 only.
   Functional test scripts validate on-disk vs answers per module.
7. **Answers persisted in-project, per-module sections.** `.project-setup/
   answers.toml` committed, `[module.<id>]` sections (splittable), `source`
   provenance. Re-run = always diff-and-confirm, never silent replay. Modules
   declare reconcile capability so re-run fixes drift.
8. **Reproducibility via committed sources, APM-style.** `.project-setup/
   sources.toml` committed (sources+refs + advisory skill_version). Clone reads
   it → fetches to cache → applies answers. Independent of home config. Fetched
   bytes gitignored, not vendored (mirrors apm.yml committed / apm_modules
   gitignored, verified).
9. **Dynamic sources first-class, in this build** (git repo/path/local, floating
   main allowed). Fetch→cache before discovery; proceed-on-failure. APM-packaged
   modules OUT of scope (install-timing mess). Arbitrary code execution accepted
   (same trust as APM/plugins).
10. **Home = personal catalog + defaults, never authoritative.** Defaults layer:
    module default < home default < project answer < user choice. Home can't
    silently change an existing project.
11. **Modes by sources.toml presence:** absent → init interview + write;
    present → reproduce/update + diff/confirm. Interview generated from
    manifests. First-time init asks which modules + "add external sources?"
    seeded by the home catalog (ad-hoc locators allowed).
12. **gitignore:** no PyPI generator exists (only matchers, verified). Vendor
    github/gitignore CC0 templates + on-demand fetch from github/gitignore. No
    live toptal API.
13. **Phasing dropped.** One cohesive build; data-out-first = internal build
    order only.
14. **SKILL.md:** thin on config, thick on process/guardrails (ensure uv, run
    end-to-end, sourcing, interview, diff/confirm loop, tier execution, "done"
    definition, validity checks, safe execution).

## Conflicts with durable memory

None — greenfield. NOTE: this design SUPERSEDES the original spec's FR-016
(keep bats green verbatim), FR-013 (frozen-plan executor), the Phase 1/Phase 2
split, and the bash portability floor — all intentionally retired above.
