# Implementation Plan: 017 Standardized Brownfield Probe

**Spec**: `specs/017-brownfield-probe/spec.md` · **Status**: Draft (2026-06-28)
**Baseline**: full suite 648 passed, 4 deselected (clean, pre-017).

This plan follows the project's plan-then-delegate convention: the task breakdown is
inline below as dependency-ordered phases. Each phase gates on the full suite
(`uv run --with pytest pytest -q packages/project-setup/tests/ -k 'not SuccessfulGitFetch'`,
~8 min, run in background). Migration proceeds in policy groups (OQ-3 lean) to keep the
blast radius reviewable.

## Resolved open questions (leans applied)

- **OQ-1** → BOTH: `brownfield_probe` is the pure read-only detector (used for the 008
  gate annotation + reporting); `idempotent_write` gains a `merge` policy for the write
  path. Read `sdk.py:220-257` + `contracts.py` (`Diff`/`ModuleResult`) before coding.
- **OQ-2** → module-level `[brownfield]` listing `{path, policy}` entries.
- **OQ-3** → migrate in policy groups, full-suite gate per group.

## Phase 1 — SDK primitive + manifest parsing (foundation; no module changes yet)

1. `runner/sdk.py`: add `brownfield_probe(artifacts, *, project_dir=None)` → list of
   records `{path, exists, empty}` (FR-001). Pure, read-only, never raises; zero-byte /
   whitespace-only ⇒ `empty=True`. Mirror `scan_top_level_dirs`'s defensive style
   (`sdk.py:276`).
2. `runner/sdk.py`: add the append-only **merge** path (FR-004) — either a new
   `policy="merge"` branch inside `idempotent_write` or a sibling helper it delegates to.
   Existing content + only the body lines not already present (membership by exact line
   after rstrip), existing order preserved, new lines in body's canonical order, deduped.
   Idempotent (re-run ⇒ `skip`); identical ⇒ `skip`.
3. `runner/sdk.py`: widen `_SECRET_PATTERNS` (FR-008) with anchored gitleaks-sourced
   shapes (Google `AIza`, Stripe `sk_live_`/`rk_live_`, Twilio `AC`/`SK`, SendGrid
   `SG\.`, npm `npm_`, PyPI `pypi-`, JWT `eyJ`). MIT attribution comment. No deps, no
   generic/entropy rules. Keep anchored-only invariant.
4. `runner/manifest.py`: parse an optional module-level `[brownfield]` section — a list
   of `{path, policy}` where policy ∈ {`preserve`,`merge`,`overwrite`} (FR-003). Unknown
   policy ⇒ `SetupError`. Absent section ⇒ unchanged behavior. Add a `brownfield` field
   to the manifest dataclass.

**Tests (Phase 1):** new `tests/test_brownfield_probe.py` — probe missing-dir/missing/
unreadable ⇒ `exists=False` no raise; zero-byte/whitespace ⇒ `empty=True` (SC-003);
merge idempotency + dedup + order (SC-004); `looks_like_secret` new shapes + UUID/SHA/
semver negatives (SC-006); manifest `[brownfield]` parse + unknown-policy SetupError
(SC-005). **Gate Phase 1 before any module migration.**

## Phase 2 — Migrate write-if-absent / skip modules (lowest risk)

Group A (already preserve-on-exists; migration is declarative + swap inline check for
probe, behavior unchanged): `git-init` (`git_dir.exists()` → `[brownfield]` declare
`.git` policy=preserve), `license-write` (declare `LICENSE` preserve),
`core-identity`, `justfile-write`, `dirs-scaffold`, `codex-config`, `apm-install`,
`github-repo`, `agents-md`, `speckit-bridge`, `quality-hooks`, `env-example`,
`package-add` (`target.exists()`), `precommit-setup` (`abs_dest.exists()`).
For each: add `module.toml [brownfield]`, replace the ad-hoc existence check with the
probe / policy-driven write, keep observable behavior identical (FR-007).
**Gate full suite after this group.**

## Phase 3 — gitignore-generate merge (the one intended behavior change)

`gitignore-generate`: declare `.gitignore` policy=`merge`; switch `idempotent_write`
call from `reconcile=True` to the merge path (FR-005). Greenfield output byte-identical
(SC-002, regression test); brownfield appends-only (SC-001). Add the dedicated merge
test. **Gate full suite.**

## Phase 4 — Migrate lang-* recompose modules (highest risk; keep recompose logic)

`lang-python` (`pyproject.exists()` ×4, gitignore read, `precommit.exists()`),
`lang-ts` (`package.json` ×3, nuxt/vite config, gitignore), `lang-go`/`lang-rust`
(`go.mod`/`Cargo.toml`, gitignore, precommit). These READ existing config to recompose
it — keep that logic (FR-007). Standardize only the detect/report layer + the
whole-file preserve/merge decision (their existing-`.gitignore` reads route through the
merge helper; their `pyproject`/`package.json` recompose stays). **Gate full suite.**

## Phase 5 — Completeness + verification

1. `rg` sweep (SC-008): no ad-hoc project-artifact `Path.exists()`/`is_file()` remains
   in a migrated `module.py` (exclude the `sdk_path.is_file()` bootstrap shim). Anything
   left is either intentionally a recompose-read or a migration miss — resolve.
2. Final full-suite gate. Fill spec.md Status → Implemented + memory.md AS-BUILT
   (including the honest greenfield-byte-identity proof and any deferred items).

## Risk notes

- **Greenfield byte-identity (FR-010/SC-007)** is the dominant risk: migration must not
  perturb any module's greenfield output except `gitignore-generate`. Per-group full
  suite gating + the regression test on gitignore greenfield (SC-002) are the guard.
- The lang-* recompose modules are deliberately the LAST group — they have the most
  existing-state logic and the highest chance of a subtle behavior shift.
- Do not trust a subagent's "N passed" — re-run the full suite in the main thread after
  each group (carried discipline; caught real bugs in prior batches).
