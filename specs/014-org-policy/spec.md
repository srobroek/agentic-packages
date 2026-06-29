# Feature Specification: Org-Convention Overlay (org-policy)

**Feature Branch**: `feat/project-setup-modular-redesign` (continues)

**Created**: 2026-06-29

**Status**: **Implemented (2026-06-29)** — thin spec split out of the bundled
`014-org-pkgadd-readme` preamble (Q4 RESOLVED: split into 014/015/016). Sub-feature A,
shipped last. New `ORG_SOURCE_UNPINNED` runner validation (`validate_sources` at the top
of pipeline Stage 1, before fetch — OQ-2 lean) + a new default-disabled `org-policy`
bootstrap module. The precision rule rejects ONLY a bare git source (ref→HEAD, no
fragment/field); existing explicit-ref/local sources pass (full suite 785 green, zero
regressions). NOTE: lives at `specs/014-org-policy/`; the bundled strawman remains at
`specs/014-org-pkgadd-readme/` as the shared preamble. See `memory.md` → AS-BUILT. This
completes the 014/015/016 split and the greenfield roadmap batch.

**Input**: Roadmap rank #12, the org-convention-overlay third of the bundled entry.

## Overview

A new default-disabled `org-policy` bootstrap module that lets an org enforce mandatory
conventions: it loads a private org-owned module source (pinned by git ref/tag in
`sources.toml` — arbitrary code, so MUST be pinned), runs an agent step mapping the org's
policy manifest against the user's frozen answers, and gates the result so every
org-mandated override is surfaced (user-asked vs mandated) before any write. Plus a new
runner-level validation: **a git `[[source]]` with no explicit ref is rejected at
validate time** (`ORG_SOURCE_UNPINNED`) — an unpinned org source is a supply-chain risk
(any push silently changes behavior).

## Settled decisions (inherited, this-spec relevant)

- **B — Org-policy source MUST be pinned by explicit git ref/tag.** Floating HEAD/branch
  = any push silently changes behavior. The new `ORG_SOURCE_UNPINNED` validation enforces
  this BEFORE fetch. Local-path sources are exempt (already on-disk).
- **G — Org-policy overlay modules are in the FETCHED root tier** (ENV→PROJECT→HOME→
  FETCHED→BUNDLED): org overrides beat bundled defaults but are shadowed by project/home/
  env. No discovery-engine change.
- **H — `org-policy` is a standard module.toml + module.py**, NOT a runner change (except
  the `ORG_SOURCE_UNPINNED` validation, which IS runner-level). The bundled `org-policy`
  is a thin bootstrap that declares the source + applies the org's pinned policy modules.
- **OQ-2 RESOLVED → lean (a):** add a `validate_sources(sources)` function called at the
  TOP of pipeline Stage 1 (`pipeline.py`, after `all_sources` is assembled, BEFORE the
  fetch loop). It parses each locator and rejects any `kind="git"` whose ref resolves to
  the default `"HEAD"` AND has no explicit `ref` field / `#ref` fragment →
  `ORG_SOURCE_UNPINNED`. Returns a list of `SetupError` (existing collection pattern).
- **OQ (precision, this spec):** the check is NARROW — `#main`, `#v1.2.0`, `#<sha>`, and a
  `ref =` field all PASS (they're explicit). Only a bare `owner/repo` (ref→HEAD, no
  fragment, no ref field) is rejected. Local sources exempt. This keeps existing tests
  (which use explicit refs or local paths) green.

## User Scenarios

### US1 — Org policy forces a naming override (Priority P2)

Org mandates `com.acme.*` namespaces. `org-policy` enabled, org source pinned to
`v1.3.0` in `sources.toml`. The agent reads frozen answers, finds `project_name="api"`,
and emits an override `{key:"project_name", user_value:"api",
mandated_value:"com.acme.api", reason:"org namespace policy"}`. A gate shows it
(`api → com.acme.api (org-mandated)`); on confirm the python step applies ONLY the
mandated overrides.

**Acceptance:**
1. Agent emits a structured `overrides` list (`agent-steered`); zero-length is valid.
2. Gate shows each override `{key}: {user} → {mandated} (org-mandated: {reason})`. Zero
   overrides → informational gate (no prompt); ≥1 → hard gate.
3. Python applies ONLY mandated overrides (never touches untouched answers).
4. `--non-interactive` without `--allow-org-policy` → SAFE-skip (no overrides applied).

### US2 — Unpinned org source rejected; pinned accepted (Priority P2)

A git `[[source]]` with `locator="acme/policy"` and no ref → `ORG_SOURCE_UNPINNED` at
validate time (before fetch). Adding `ref="v1.0.0"` (or `#v1.0.0` in the locator) → passes.

**Acceptance:**
1. Git locator, ref→HEAD, no explicit ref field/fragment → `ORG_SOURCE_UNPINNED`, refuse.
2. Explicit `ref` field OR `#ref` fragment → passes.
3. Local-path source → exempt (passes).
4. Reproduce with a pinned source → fetch checks out the committed ref exactly.

### Edge Cases

- Org source fetch fails (network) → `fetch_source` soft-fails (FetchResult ok=False),
  module absent from discovery, run proceeds + warns (001 contract). No hard error.
- `org-policy` id collides with a bundled module → standard precedence (FETCHED wins over
  BUNDLED). No special handling.
- Zero overrides → informational gate, no prompt, no answer changes.

## Functional Requirements

### Runner-level source-pin validation

- **FR-001**: The runner MUST validate that every `[[source]]` whose locator is
  `kind="git"` has an explicit ref (a `ref=` field OR a `#ref` fragment). A git source
  with no ref (locator ref defaulting to `"HEAD"`) MUST be rejected at validate time with
  a new `ORG_SOURCE_UNPINNED` error code, BEFORE any fetch. Local-path sources are exempt.
- **FR-002**: The validation MUST run at the top of pipeline Stage 1 (after `all_sources`
  is assembled, before the fetch loop) via a `validate_sources(sources) -> list[SetupError]`
  function. On any `ORG_SOURCE_UNPINNED` error the pipeline MUST abort with the collected
  errors (the existing hard-error path), never fetching the unpinned source.
- **FR-003**: `ORG_SOURCE_UNPINNED` MUST be added to the `ErrorCode` enum
  (`runner/contracts.py`). The error message MUST name the offending locator and instruct
  the user to add an explicit `ref` (tag/SHA).
- **FR-004**: The committed `.project-setup/sources.toml` already records the exact `ref`
  (`persist.write_sources_toml`, verified) — no persist change. Reproduce reads the
  committed ref and fetches that exact ref.

### org-policy module

- **FR-005**: A new bundled module `org-policy` (default_enabled=false) MUST declare a
  `kind=agent` step (`id="resolve"`) → `kind=gate` step (`id="overrides"`) → `kind=python`
  step (`id="apply"`). module.toml `[meta]` + `[module]` per the standard schema.
- **FR-006**: The agent step reads the frozen plan answers (via `context["all_answers"]`,
  007 Phase-0) and the org policy manifest (a sibling file provided by the fetched org
  module) and emits an `overrides` decision: a list of `{key, user_value, mandated_value,
  reason}` as `agent-steered` answers. A zero-length list is valid.
- **FR-007**: The gate (`id="overrides"`) MUST use `allow_flag="allow-org-policy"`,
  `init_only=true`, and `message="{decision}"` so the override table renders. Per
  Decision-A4: zero overrides → `hardness="informational"` (no prompt); the spec ships a
  single gate step declared `hardness="hard"` (the common ≥1-override case); a zero-override
  run still shows the (empty) decision and the user confirms once — acceptable for v1.
  *(A dynamic hard/informational switch by override-count is deferred — see Out of Scope.)*
- **FR-008**: The python `apply` step MUST apply ONLY the mandated overrides to the frozen
  answers (via `answers_to_persist` with the overridden values), `reconcile=false` (applied
  once at init). It MUST NOT modify any answer the org policy did not list as mandated.
- **FR-009**: In `--non-interactive` without `--allow-org-policy`, the gate MUST SAFE-skip
  (apply no overrides). CI never silently applies org overrides without explicit opt-in.

### Determinism & compatibility

- **FR-010**: Reproduce is zero-network for the agent step (replays frozen `overrides`);
  fetch uses the committed pinned ref. `--refresh org-policy` re-invokes the agent.
- **FR-011**: The `ORG_SOURCE_UNPINNED` validation MUST NOT break any existing flow:
  existing sources use explicit refs or local paths. The full pre-014 suite MUST stay green.

## Success Criteria

- **SC-001**: A git `[[source]]` with no ref → `ORG_SOURCE_UNPINNED` at validate time,
  before any fetch (unit test on `validate_sources`); an explicit `ref` field OR `#ref`
  fragment → passes; a local-path source → passes (exempt).
- **SC-002**: An org-policy agent emitting one override → a gate message naming
  `key: user → mandated (org-mandated: reason)`; the apply step applies only that override
  (other answers untouched). Zero overrides → no answer change.
- **SC-003**: `--non-interactive` without `--allow-org-policy` → SAFE-skip (no overrides
  applied); with the flag → applied.
- **SC-004**: Manifest assertions: `org-policy` default_enabled=false; step order
  resolve/overrides/apply; overrides gate hard + allow-org-policy + init_only.
- **SC-005**: Reproduce with committed `overrides` → zero network (replay); fetch uses the
  committed pinned ref.
- **SC-006**: The full pre-014 suite stays green (the new validation rejects only
  unpinned git sources; existing explicit-ref/local sources pass).

## Out of Scope

- A dynamic hard/informational gate switch by override count (v1 ships a single hard gate;
  the informational-when-empty refinement is deferred).
- A general continuous org-compliance checker (this is a once-at-init alignment tool).
- Multi-source org overlays (exactly one org policy source).
- Go/Rust pin verification (shared with 015 OQ-4).

## Dependencies

Builds on 001 (sources/fetch/discover), 003 (two-phase plan, reproduce), 004 (hard/
informational/init_only gate), 007 (the `all_answers` context view for FR-006). Touches
`runner/contracts.py` (new ErrorCode) + `runner/pipeline.py` (validate_sources in Stage 1)
+ a new bundled `org-policy` module. Independent of 015/016.
