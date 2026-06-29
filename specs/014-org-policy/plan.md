# Implementation Plan: 014 Org-Convention Overlay (org-policy)

**Spec**: `specs/014-org-policy/spec.md` · **Status**: Draft (2026-06-29)
**Baseline**: full suite 764 passed, 4 deselected (post 015).

Last of the 014 split. The ONLY runner-touching one: a new `ORG_SOURCE_UNPINNED`
validation + a new bundled `org-policy` module. OQ-2 leaned (validate_sources in Stage 1).
The validation is a NEW runner-level refusal → backward-compat is the dominant risk;
gate on the full suite.

## Resolved OQs (leans applied)

- **OQ-2 (validation location)** → `validate_sources(sources)` at the TOP of pipeline
  Stage 1, after `all_sources` assembled, before the fetch loop. Returns list[SetupError];
  hard-abort on any error.
- **Precision** → reject ONLY a git locator whose ref resolves to default `"HEAD"` with NO
  explicit `ref` field and NO `#ref` fragment. `#main`/`#tag`/`#sha`/`ref=` all PASS;
  local sources exempt. (Keeps existing tests green.)

## Phase 1 — Runner: ORG_SOURCE_UNPINNED validation

1. `runner/contracts.py`: add `ORG_SOURCE_UNPINNED = "ORG_SOURCE_UNPINNED"` to the
   `ErrorCode` enum.
2. `runner/pipeline.py`: add `validate_sources(sources: list[dict]) -> list[SetupError]`.
   For each source dict: parse its locator (`sources.locator.parse_locator`); if
   `kind=="git"` AND the source has no explicit `ref` field AND the locator string has no
   `#ref` fragment (i.e. ref resolved to the default "HEAD") → append a SetupError(
   error_code=ORG_SOURCE_UNPINNED, expected="explicit git ref (tag/SHA) for source",
   received=<locator>, how_to_fix="Pin the source: add ref=\"vX.Y.Z\" or locator#vX.Y.Z").
   Detection: a git source is unpinned iff (no "ref" key in the dict) AND ("#" not in the
   locator string) — simplest robust signal; cross-check parse_locator(raw).ref=="HEAD".
   Call it at the top of Stage 1 (after `all_sources` built ~pipeline.py:320s); on errors,
   set result.errors + return the failed PipelineResult (existing hard-error path).

**Tests (Phase 1, runner-level):** extend `tests/test_pipeline.py` or a new
`tests/test_validate_sources.py`: SC-001 — a git source dict `{locator:"acme/policy"}`
(no ref) → one ORG_SOURCE_UNPINNED error; `{locator:"acme/policy", ref:"v1.0.0"}` → none;
`{locator:"acme/policy#v1.0.0"}` → none; `{locator:"/abs/local/path"}` (local) → none.
SC-006 backward-compat: confirm no existing source fixture trips it (the full suite gate
is the real guard). **Gate full suite before Phase 2.**

## Phase 2 — org-policy module

`modules/org-policy/` (module.toml + module.py + steering/resolve.md):
- module.toml: `[meta]`; `[module]` id="org-policy", default_enabled=false, reconcile=false.
  Steps: resolve(agent, steering/resolve.md) → overrides(gate, hardness="hard",
  allow_flag="allow-org-policy", init_only=true, message="Org-policy overrides
  (org-mandated):\n{decision}\nApply these overrides?") → apply(python).
- module.py (stdlib, dependencies=[]): STEP_HANDLERS={"apply": _do_apply} + bootstrap
  shim + __main__. `_do_apply`: read `overrides` (the agent-steered list) from
  FrozenInputs; for each {key, mandated_value}, emit it via answers_to_persist (so the
  mandated value lands in the frozen answers). Apply ONLY listed overrides; touch nothing
  else (FR-008). reconcile=false (applied once). ModuleResult+emit_result. No wall-clock.
- steering/resolve.md: agent reads context["all_answers"] + the org policy manifest (a
  sibling file the fetched org module provides — for the bundled bootstrap, the manifest
  may be absent → emit zero overrides) and emits the `overrides` list {key, user_value,
  mandated_value, reason}. Zero overrides valid. Prohibit filesystem reads beyond the
  provided manifest.

**Tests (Phase 2):** SC-002 (frozen `overrides` with one entry → _do_apply emits the
mandated value via answers_to_persist; a second untouched key is unchanged); zero
overrides → no answer change; SC-004 (manifest shape: default_enabled false, step order,
gate hard+allow-org-policy+init_only). SC-003/SC-005 (gate safe-skip + reproduce replay)
via the pipeline harness / generically by the gate suite. **Gate full suite.**

## Phase 3 — closeout

Final full-suite gate; flip spec Status → Implemented; write memory.md AS-BUILT; commit
(unsigned per session). Then the entire 014/015/016 split is complete and the greenfield
roadmap batch is drained (009 intentionally unbuilt; brownfield 017/008 deferred to stage 2).

## Risk notes

- **Backward-compat (FR-011/SC-006) is the dominant risk:** ORG_SOURCE_UNPINNED is a NEW
  runner refusal. The precision rule (reject only bare git, ref→HEAD, no fragment/field)
  keeps existing explicit-ref/local sources passing. The full-suite gate is the guard —
  if ANY existing test trips it, the rule is too broad; re-narrow.
- Re-verify parse_locator's HEAD-default behavior at implementation (locator.py:123
  `ref = m.group("ref") or "HEAD"`).
- Re-run the full suite in the main thread per phase.
