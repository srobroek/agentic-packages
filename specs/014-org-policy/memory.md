# Feature 014 — Org-Convention Overlay (org-policy) (memory)

Split from the bundled `014-org-pkgadd-readme` (Q4 RESOLVED: split into 014/015/016).
Sub-feature A, shipped last (the only runner-touching one). See
`specs/014-org-pkgadd-readme/memory.md` for the shared verified code facts (sources.toml
format, fetch soft-fail, discovery precedence, locator HEAD-default).

## AS-BUILT (2026-06-29)

Shipped on `feat/project-setup-modular-redesign`. Full suite 785 passed, 4 deselected.

**Runner-level validation (the one runner change):**
- `runner/contracts.py`: added `ORG_SOURCE_UNPINNED` to the ErrorCode enum.
- `runner/pipeline.py`: `validate_sources(sources) -> list[SetupError]` (def at :90),
  called at Stage 1 (:395) AFTER all_sources assembled, BEFORE the fetch loop (:420),
  with hard-abort (:397-401) mirroring the Stage-3 discovery-error pattern.
- **PRECISION RULE (backward-compat critical, verified):** reject a source ONLY when ALL
  of: parse_locator(locator).kind=="git" AND no "ref" field AND no "#" fragment in the
  locator (i.e. ref→default "HEAD", unpinned). PASS: explicit `ref=` field; `#main`/
  `#vX.Y.Z`/`#sha` fragment; local-path sources. Defensive (parse_locator wrapped in
  try/except; missing "locator" key skipped). The full suite (785) confirms NO existing
  source fixture trips it — every existing source uses an explicit ref or a local path.

**org-policy module:** modules/org-policy/ (module.toml + module.py + steering/resolve.md).
default_enabled=false, reconcile=false. Steps: resolve(agent) → overrides(gate, hard,
allow_flag=allow-org-policy, init_only=true, {decision}) → apply(python). _do_apply reads
`overrides` (a list of {key,user_value,mandated_value,reason}) via inputs.get_list and
emits answers_to_persist with ONLY the mandated values (source="agent-steered"); touches
nothing else (FR-008). Zero overrides → ok no-op. No wall-clock. steering/resolve.md:
agent reads context["all_answers"] (007 Phase-0) + an optional org policy manifest (the
fetched org module provides it; bundled bootstrap with no manifest → zero overrides).

**FR-007 simplification:** v1 ships a single `hardness="hard"` overrides gate (the common
≥1-override case); the dynamic hard/informational-by-count switch is deferred (Out of
Scope). A zero-override run shows the empty decision + confirms once — acceptable for v1.

**Tests:** test_validate_sources.py (bare-git reject / explicit-ref pass / fragment pass /
local exempt / empty / mixed / missing-locator-skip / HTTPS forms) + test_module_org_policy.py
(SC-002 one-override apply + unrelated-key-untouched, zero-overrides no-op, multiple, manifest
shape, no wall-clock). SC-003/SC-005 (gate safe-skip + reproduce replay) covered generically
by the gate/reproduce suites.

## Batch status (this completes the greenfield roadmap)

014/015/016 split COMPLETE. Greenfield roadmap batch (006/010/011/012/013/007/014/015/016)
all DONE. 009 (py-web-orm) INTENTIONALLY unbuilt (user: opt-in). Brownfield (017-brownfield-probe
+ 008-brownfield-detect) DEFERRED to stage 2 — see [[project-setup-008-brownfield-redesign]].
