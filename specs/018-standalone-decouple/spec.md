# Feature Specification: Standalone / Marketplace-Agnostic project-setup

**Feature Branch**: `feat/project-setup-modular-redesign` (continues) → likely a
dedicated `feat/standalone-decouple` branch

**Created**: 2026-06-29

**Status**: **Draft (2026-06-29)** — decouple project-setup from the
srobroek/agentic-packages marketplace so the skill is a fully standalone scaffolding
tool. Decisions resolved with the user 2026-06-29; see the matching `memory.md` and
`[[project-setup-standalone-decouple]]`.

**Input**: User directive — "we should only be using apm if the user has an apm
marketplace, claude code marketplace discovery if the user has a global claude code
marketplace, codex marketplace if the user has a global codex marketplace. Any kind of
apm packages should only come from the user's preference if they have it enabled or are
using it by default, otherwise we should just be doing project setup and scaffolding."
Plus: drop our baseline MCP + speckit defaults; use public upstreams; the tool must be
standalone from our repo.

## Overview

A marketplace audit confirmed the **runner core + discovery are already
marketplace-agnostic** (zero-config = bundled-modules-only, no network, no srobroek
refs; the 6 `default_enabled=true` modules are pure scaffolding). The coupling lives in
exactly **two opt-in modules** — `apm-install` and `speckit-bridge` — which hardcode
`@srobroek-agentic` package locators, plus ~21 inert `[meta] repository` strings.

This spec makes the skill standalone:

1. **Drop ALL srobroek defaults.** Remove the `_BASELINE_MCP` constant, the
   `core@srobroek-agentic` input default, and the `speckit@srobroek-agentic` literal.
2. **Detect, don't assume.** Package installs are gated on a DETECTED marketplace (read
   from the user's APM / Claude Code / Codex registry files) OR a user-named source —
   never our marketplace. Detection runs once at init and is FROZEN into `answers.toml`.
3. **Public upstreams by default.** When no marketplace is detected and the user names
   no source, the skill OFFERS the canonical PUBLIC upstreams (spec-kit via `uvx`, MCP
   servers via `npx`) at a gate — never srobroek, and only on confirm.
4. **User picks + adds.** The FR-005 interview lists detected marketplaces by name and
   lets the user pick which to use AND name additional marketplaces.
5. **Pure scaffolding always works.** With no marketplace and a declined offer, the skill
   still does all non-package scaffolding (git, dirs, gitignore, license, AGENTS.md,
   language overlays, CI, README) with zero package installs.

## Settled decisions (user, 2026-06-29)

- **A — No-marketplace default = OFFER PUBLIC upstreams (gated), not "install nothing".**
  A bare user can still get working spec-kit + MCP from PUBLIC refs (npx/uvx), behind a
  hard gate, never srobroek. Declining leaves pure scaffolding intact.
- **B — Marketplace selection = user PICKS from detected + can ADD others.** The interview
  lists detected marketplace names (from the 3 registries) and asks which to use, and asks
  for any additional marketplaces. The choice is frozen into `answers.toml`.
- **C — speckit full-mode = public spec-kit via `uvx`** by default; prefer the user's
  detected marketplace if it provides a speckit package. Never srobroek.
- **D — Genericize the ~21 `[meta] repository` strings** to a neutral placeholder. No
  srobroek string anywhere, even in inert metadata.
- **E — Detection is registry-presence, not binary-presence.** Having `apm` on PATH ≠
  having a marketplace. Detection reads the registry FILES (below). This fixes the
  current `apm-install/module.py:165` bug (it treats `apm --version` success as
  install-go).
- **F — Determinism: detect once at init, FREEZE the choice.** Reproduce/clone replays
  the frozen marketplace/source/offer decision from `answers.toml`; it NEVER re-detects
  (re-detecting would make a clone behave differently on a machine with vs without a
  marketplace — breaking the SKILL.md "clone reproduces independent of home config"
  contract).

## Detection mechanism (verified live; offline, stdlib only)

Each tool keeps a home-dir registry of the marketplaces the user added. Detection = read
the file, check for ≥1 entry. No network, no subprocess.

- **APM**: `~/.apm/marketplaces.json` → `{"marketplaces": [{name, url, path, ...}]}`;
  ≥1 entry = user has APM marketplaces. Marketplace names = each `.name`.
- **Claude Code**: `~/.claude/plugins/known_marketplaces.json` → a flat object whose KEYS
  are marketplace names (e.g. `claude-plugins-official`, `repomix`); enabled plugins in
  `~/.claude/settings.json` `enabledPlugins` (`<plugin>@<marketplace>`).
- **Codex**: `~/.codex/config.toml` → `[marketplaces.<name>]` tables (Codex 0.137.0+);
  the `marketplaces` table's keys are names (e.g. `openai-bundled`).

## Public upstream references (canonical, verified)

- **spec-kit**: `uvx --from git+https://github.com/github/spec-kit.git specify init <P>`
  (one-off) or `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@vX.Y.Z`
  (pinned). Community catalog: `raw.githubusercontent.com/github/spec-kit/main/extensions/catalog.community.json`.
- **context7**: `npx -y @upstash/context7-mcp` (optional `CONTEXT7_API_KEY`).
- **repomix**: `npx -y repomix --mcp`.
- **package-version**: `npx -y mcp-package-version`.
- **codebase-memory**: `npx -y codebase-memory-mcp` (DeusData; npm+PyPI) or its static-
  binary install. (OQ-1: npx vs static-binary default.)

## Current state (verified — file:line)

- `apm-install/module.py:36-41` — `_BASELINE_MCP` = 4 `@srobroek-agentic` locators
  (baked constant). `:149` `packages = [agentic_packages] + _BASELINE_MCP` (always
  appended). `:124` + `module.toml:22` — `agentic_packages` default `core@srobroek-agentic`.
  `:165` `_apm_available` (binary presence) is the SOLE install precondition (the bug).
  `module.toml:44-53` — G2 gate message hardcodes the 4 MCP names.
- `speckit-bridge/module.py:178` (+ `:171,:187,:190,:214`) — literal
  `speckit@srobroek-agentic`, gated only by `spec_mode=="full"`. `module.toml:18-24` —
  only input is `spec_mode` (none|lightweight|full); no source input.
- `runner/sources/*` + `pipeline.py` Stage 1 — already marketplace-agnostic; NO change.
- ~21 `module.toml [meta] repository = "github.com/srobroek/agentic-packages"` — inert
  metadata; genericize (Decision D).

## Functional Requirements

### Marketplace detection (new shared SDK capability)

- **FR-001**: A new `sdk` helper (e.g. `detect_marketplaces() -> dict`) MUST read the
  three registry files offline and return the detected marketplaces per system:
  `{"apm": [names...], "claude-code": [names...], "codex": [names...]}`. Missing file,
  malformed JSON/TOML, or empty registry MUST yield an empty list for that system — NEVER
  raise. No network, no subprocess, stdlib only (`json`, `tomllib`).
- **FR-002**: Detection MUST be invoked at INIT only and its RESULT (the user's
  marketplace/source CHOICE, not the raw detection) MUST be frozen into `answers.toml`.
  On reproduce the frozen choice is replayed; detection MUST NOT re-run (Decision F).

### apm-install rewrite (drop srobroek; consume frozen choice)

- **FR-003**: `_BASELINE_MCP` MUST be removed. The `agentic_packages` input default MUST
  change from `core@srobroek-agentic` to `""` (empty). No srobroek literal may remain in
  `apm-install/module.{py,toml}`.
- **FR-004**: `apm-install` MUST install ONLY packages the user supplied (the
  `agentic_packages` frozen answer, plus any user-named packages) from a marketplace the
  user SELECTED (the frozen `marketplace` answer). With an empty package list it MUST
  be a clean no-op (status ok, nothing installed) — NOT install a baseline set.
- **FR-005**: The install precondition MUST be a DETECTED/SELECTED marketplace (frozen
  answer), NOT `_apm_available` binary presence. If `apm` is on PATH but the user has no
  marketplace and named no packages, `apm-install` installs nothing.
- **FR-006**: The G2 `confirm-install` gate message MUST render the ACTUAL frozen package
  list + selected marketplace (via `{decision}`), not a hardcoded baseline. An empty list
  → the gate is a no-op / `when`-dropped.

### speckit-bridge rewrite (public spec-kit)

- **FR-007**: The `speckit@srobroek-agentic` literal MUST be removed. `spec_mode=="full"`
  MUST default to the PUBLIC spec-kit path:
  `uvx --from git+https://github.com/github/spec-kit.git specify init` (or the pinned
  `uv tool install` form — OQ-2). If the user's SELECTED marketplace provides a speckit
  package, prefer that; else public. Never srobroek.
- **FR-008**: speckit-bridge MUST gracefully degrade when neither `specify`/`uvx`/`uv`
  nor a marketplace speckit is available (warn + manual command, non-fatal — current
  contract preserved).

### Public-MCP offer (no-marketplace default)

- **FR-009**: When NO marketplace is detected/selected AND the user opts into agentic
  tooling, the skill MUST OFFER the canonical PUBLIC MCP servers (context7/repomix/
  package-version/codebase-memory via `npx`/`uvx`) at a HARD gate. On confirm, write the
  MCP server config into the target tool's MCP config (NOT an apm install — these are MCP
  server entries). On decline / `--non-interactive` without the allow-flag, write nothing.
  *(OQ-3: where the public-MCP write lives — apm-install vs a distinct concern.)*
- **FR-010**: The public-MCP offer MUST be entirely optional and srobroek-free. Pure
  scaffolding (all non-package modules) MUST run regardless of the offer outcome.

### Interview (FR-005 flow) — marketplace selection

- **FR-011**: The SKILL.md FR-005 interview MUST be extended: the agent reads the detected
  marketplaces (FR-001), PRESENTS them to the user by name, asks which to use for package
  installs, AND asks for any additional marketplaces the user wants to add. The selection
  (chosen marketplace + any added + package list) is recorded as frozen answers (Decision B).
- **FR-012**: With no marketplace and no user selection, the interview MUST NOT push our
  marketplace; it offers public upstreams (Decision A) or pure scaffolding only.

### Scope boundary (the skill SCAFFOLDS — it does not build the product)

- **FR-S1**: SKILL.md MUST declare an explicit scope boundary: project-setup SCAFFOLDS a
  project (structure, config files, pinned manifest + toolchain, frozen stack decisions,
  CI workflow, README draft, .env.example) and STOPS. It MUST NOT author application
  source code, business logic, ORM models, endpoint handlers, hand-written migrations, or
  a test suite — those are the user's product work. (Observed failure 2026-06-29: with no
  boundary, the agent spent ~24min building a full FastAPI app + tests + migrations.)
- **FR-S2**: SKILL.md MUST instruct the agent that "done" = the runner's modules have run
  + answers frozen + committed; at that point it STOPS and prints a concise next-steps
  HANDOFF (what was scaffolded, what the user does next) rather than continuing to build.
  The agent MUST NOT invent a post-scaffold "I own the rest / fill in the app" phase.
- **FR-S3**: The in-scope artifact set is exactly what bundled MODULES produce (dirs,
  gitignore, license, AGENTS.md, pre-commit config, justfile, CI yml, .env.example,
  STACK.md, pinned manifest + toolchain, README draft). Anything not produced by a module
  step is out of scope.

### Metadata + standalone hygiene

- **FR-013**: The ~21 `[meta] repository = "github.com/srobroek/agentic-packages"` strings
  across `modules/*/module.toml` MUST be genericized to a neutral placeholder. (Inert;
  cosmetic; but no srobroek string ships, even in metadata.) (Decision D)
- **FR-014**: A repo-wide scan of the shipped skill MUST find ZERO `srobroek` references
  in any runtime path (module.py constants, module.toml inputs/defaults, steering docs).
  Authorship metadata genericized per FR-013.

### Determinism & compatibility

- **FR-015**: Reproduce/clone MUST replay the frozen marketplace/source/offer decisions
  byte-identically with zero re-detection and zero network beyond the chosen install
  command (Decision F).
- **FR-016**: The full pre-018 suite MUST stay green. Existing apm-install/speckit-bridge
  tests that assert srobroek defaults MUST be updated to the standalone behavior (these
  are deliberate behavior changes, not regressions).

## Success Criteria

- **SC-001**: `rg -i srobroek` over the shipped skill (`runner/` + `modules/`) finds ZERO
  runtime references; `[meta] repository` is the neutral placeholder (FR-013/014).
- **SC-002**: `detect_marketplaces()` returns the correct per-system name lists for the
  three registry shapes; missing/malformed/empty files → empty lists, never raises
  (unit test with tmp fixtures for each shape).
- **SC-003**: `apm-install` with an empty `agentic_packages` answer and no marketplace
  selection installs NOTHING (clean no-op, status ok) — verified the install subprocess
  is never invoked (test double).
- **SC-004**: `apm-install` with a user-selected marketplace + named packages installs
  ONLY those from THAT marketplace; the G2 gate shows the actual list (no baseline MCP).
- **SC-005**: `speckit-bridge` full-mode invokes the PUBLIC spec-kit command (uvx/uv), not
  `apm install speckit@srobroek-agentic`; degrades gracefully when absent.
- **SC-006**: With no marketplace detected, the public-MCP offer presents canonical public
  refs; confirm → MCP config written from public refs; decline → nothing written; pure
  scaffolding unaffected (SC).
- **SC-007**: Reproduce of an init that selected marketplace X replays X from the frozen
  answer WITHOUT re-reading the home registries (test: init on a machine with a registry,
  reproduce with the registry absent → same frozen behavior).
- **SC-008**: A zero-config / no-marketplace / declined-offer run produces a full
  scaffold (git, dirs, gitignore, license, AGENTS.md, …) and installs zero packages.
- **SC-009**: Full pre-018 suite green (with updated apm-install/speckit-bridge tests).

## Out of Scope

- Changing the runner core / discovery (already marketplace-agnostic).
- Implementing per-marketplace package RESOLUTION (querying a marketplace's catalog) —
  the skill records the user's chosen marketplace + package names; resolving/installing is
  the underlying tool's job (apm/claude/codex).
- A network probe to validate a marketplace is reachable at init (detection is file-based).
- Brownfield (017/008 — deferred to stage 2).

## Open Questions

- **OQ-1**: codebase-memory default — `npx -y codebase-memory-mcp` (self-contained,
  cold-start) vs static-binary install (faster, separate step). Lean: npx (unifies the
  install story with the other three).
- **OQ-2**: spec-kit default — public `uvx` one-off (always-latest) vs pinned
  `uv tool install …@vX.Y.Z` (reproducible). Lean: pinned for reproducibility, matching
  the determinism contract; the pin is a maintained constant in the module.
- **OQ-3 RESOLVED (user)**: a NEW `mcp-config` module owns the MCP-server-entry write
  (public refs or marketplace-provided); `apm-install` shrinks to a pure apm-package
  consumer. Clean per-concern boundary.
- **OQ-2 RESOLVED (user)**: spec-kit default = PINNED `uv tool install specify-cli --from
  git+https://github.com/github/spec-kit.git@vX.Y.Z` (reproducible; pin is a maintained
  module constant).
- **OQ-4**: CONTEXT7_API_KEY — prompt for it (higher rate limit) or keyless default. Lean:
  keyless default + a steering note that a key can be added.

## Dependencies

Builds on the shipped runner (001-005), gates (004), and the 007 `all_answers` context
view (the interview agent reads detection results + presents options). Touches `sdk.py`
(detect_marketplaces), `modules/apm-install/`, `modules/speckit-bridge/`, possibly a new
`modules/mcp-config/`, `SKILL.md` (FR-005 interview), and ~21 `module.toml [meta]` lines.
No runner-core change. Independent of brownfield.
