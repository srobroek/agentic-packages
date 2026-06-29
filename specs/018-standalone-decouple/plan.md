# Implementation Plan: 018 Standalone / Marketplace-Agnostic project-setup

**Spec**: `specs/018-standalone-decouple/spec.md` · **Status**: Draft (2026-06-29)
**Baseline**: full suite 785 passed, 4 deselected (post 014).

Phase-gated. Decouples the two coupled modules + adds detection + a new mcp-config module
+ genericizes metadata. No runner-core change. Each phase gates on the full suite.

## Resolved decisions
- OQ-3 → NEW `mcp-config` module (apm-install = apm packages only).
- OQ-2 → spec-kit = PINNED `uv tool install specify-cli --from git+…/spec-kit.git@<PIN>`.
- A → no-marketplace = OFFER public upstreams (gated). B → interview lists detected +
  user picks + adds. C → public spec-kit (prefer user marketplace if it has speckit).
  D → genericize meta. E → registry-presence detection. F → freeze choice, no re-detect.

## Phase 1 — sdk.detect_marketplaces (foundation)
`runner/sdk.py`: `detect_marketplaces() -> dict` reading offline (stdlib json/tomllib):
- APM `~/.apm/marketplaces.json` → `[m["name"] for m in data.get("marketplaces",[])]`
- Claude Code `~/.claude/plugins/known_marketplaces.json` → `list(data.keys())`
- Codex `~/.codex/config.toml` → `list(data.get("marketplaces",{}).keys())`
Returns `{"apm":[...], "claude-code":[...], "codex":[...]}`. Missing/malformed/empty →
empty list per system, NEVER raises (wrap each in try/except, mirror scan_top_level_dirs).
Home dir via `Path.home()`; allow a `home: Path|None=None` param for test injection.
**Tests:** `tests/test_detect_marketplaces.py` — each registry shape (tmp home fixture);
missing file → []; malformed → []; empty → []; all-three populated. SC-002. **Gate.**

## Phase 2 — apm-install rewrite (drop srobroek)
- Remove `_BASELINE_MCP` (module.py:36-41). `agentic_packages` default `""`
  (module.toml:22 + module.py:124). Remove the 4 baseline lines from G2 gate msg
  (module.toml:44-53).
- `packages = [agentic_packages] if agentic_packages else []` (+ any user-named list);
  NO baseline append. Empty → clean no-op (status ok, no install call). SC-003.
- Precondition: a SELECTED marketplace (frozen `marketplace` answer) — NOT `_apm_available`.
  Add a `marketplace` input (the selected name, frozen by the interview). Binary-present
  but no marketplace + no packages → install nothing. SC-005-bug fix.
- G2 gate renders the ACTUAL frozen list+marketplace via {decision}; empty → when-dropped.
**Tests:** update test_module_apm_install (srobroek-default asserts → standalone); SC-003/004.
**Gate.**

## Phase 3 — speckit-bridge public spec-kit
- Remove `speckit@srobroek-agentic` (module.py:178,171,187,190,214). full-mode →
  pinned `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@<PIN>`
  then `specify init` (or the existing setup-speckit delegation if a marketplace speckit is
  selected). `_SPECKIT_PIN` = a maintained module constant. Prefer user-selected marketplace
  speckit if present; else public. Graceful degrade (warn+manual) when absent. SC-005/008.
**Tests:** update test_module_speckit_bridge; assert public command, no srobroek. **Gate.**

## Phase 4 — new mcp-config module
`modules/mcp-config/` (module.toml + module.py + steering): default_enabled=false. Writes
MCP server entries into the target tool's MCP config from PUBLIC refs (context7
`npx -y @upstash/context7-mcp`, repomix `npx -y repomix --mcp`, package-version
`npx -y mcp-package-version`, codebase-memory `npx -y codebase-memory-mcp`) OR a selected
marketplace. Hard gate (allow-mcp-config) before write; reconcile semantics for the config
file. Pure-scaffolding-safe (default off; declined = nothing). SC-006.
**Tests:** test_module_mcp_config — public refs written on confirm; nothing on decline;
manifest shape. **Gate.**

## Phase 5 — genericize meta + SKILL.md interview + closeout
- Genericize ~21 `[meta] repository = github.com/srobroek/agentic-packages` → neutral
  placeholder (FR-013). Mechanical; verify no test asserts the srobroek meta string.
- SKILL.md FR-005 interview (FR-011/012): instruct the agent to call detect_marketplaces,
  present detected names, ask which to use + any to add, freeze the choice; with none,
  offer public upstreams or pure scaffolding — never push srobroek.
- `rg -i srobroek` over runner/ + modules/ = ZERO runtime refs (SC-001/014).
- Final full-suite gate; flip spec Status → Implemented; memory AS-BUILT; commit.

## Risk notes
- **Determinism (FR-015):** the interview freezes the marketplace/source choice; modules
  read the FROZEN answer, never re-detect. apm-install/speckit/mcp-config must be pure
  consumers of frozen answers — detection is an INIT-time interview concern only. Verify no
  module calls detect_marketplaces at execute time.
- **Behavior-change tests:** P2/P3 update existing tests that assert srobroek defaults —
  those are intentional changes, not regressions; the FULL suite is the guard against
  collateral breakage.
- Re-run the full suite in the main thread per phase (don't trust subagent -k counts).
