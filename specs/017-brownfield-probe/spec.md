# Feature Specification: Standardized Brownfield Probe (SDK primitive + all-module migration)

**Feature Branch**: `feat/project-setup-modular-redesign` (continues) → likely a
dedicated `feat/brownfield-probe` branch

**Created**: 2026-06-28

**Status**: **Draft (2026-06-28)** — net-new foundation spec, carved out of 008 at the
user's direction. 008 (brownfield-detect) is RESCOPED to consume this; the
`brownfield_skip` per-module input it originally prescribed is DROPPED entirely (see
"Why this spec exists"). Design decisions resolved with the user 2026-06-28 — see the
matching `memory.md` and `[[project-setup-008-brownfield-redesign]]`.

**Input**: While planning 008 (brownfield detect-and-adopt), two user decisions
reshaped the work: (1) the `brownfield_skip` `[[input]]` the spec prescribed for three
base modules is config noise — the no-clobber guarantee it bought already exists
deterministically via `sdk.idempotent_write`; and (2) the "does my artifact already
exist?" check should be **standardized across ALL modules**, not hand-rolled per module
nor limited to the three base modules. A survey confirmed every module already
hand-rolls this ad-hoc (`pyproject.exists()` ×4 in `lang-python`, `package.json` ×3 in
`lang-ts`, `go_mod`/`cargo_toml` in `lang-go`/`lang-rust`, `git_dir.exists()` in
`git-init`, `target.exists()` in `package-add`, …). This spec extracts one primitive,
migrates every module to it, and is the foundation 008's agent phase builds on.

## Overview

Every module that writes a project artifact must answer the same question before it
writes: *does this artifact already exist, and if so, do I create / preserve / merge?*
Today each module answers it differently:

- `git-init` checks `git_dir.exists()` and skips (`module.py:135`).
- `license-write` uses `idempotent_write(reconcile=False)` = write-if-absent
  (`module.py:207`) — existing LICENSE silently preserved.
- `gitignore-generate` uses `idempotent_write(reconcile=True)` (`module.py:217`) —
  existing `.gitignore` **overwritten**, dropping hand-authored lines.
- `lang-python` checks `pyproject.exists()` at four sites + reads an existing
  `.gitignore` + checks `precommit.exists()`.
- `lang-ts` checks `package.json` at three sites + `nuxt.config.ts`/`vite.config.ts` +
  `.gitignore`. `lang-go`/`lang-rust` mirror this with `go.mod`/`Cargo.toml`.

This is the same logic implemented ~15 ways, with inconsistent semantics (skip vs
overwrite vs merge) and no uniform way to *report* what pre-existing state was found.
This spec introduces a single SDK primitive and a declarative `module.toml [brownfield]`
section so a module declares the artifacts it owns and the runner/SDK gives it uniform
detect → classify → (preserve | merge | create) behavior, plus a machine-readable
report the pipeline can surface.

This spec also widens the G8 secret-shape detector (`looks_like_secret`) from 6 to a
larger set of **anchored, low-false-positive** provider patterns, cherry-picked from the
MIT-licensed gitleaks ruleset — a self-contained, dependency-free improvement that 008's
agent channel relies on (008 emits answers that bypass the existing G8 interview guard).

## Why this spec exists (the 008 carve-out)

008 originally prescribed (Settled Decision D, FR-003/011/012/013): a brownfield AGENT
emits a per-base-module `brownfield_skip: true` answer; each base module declares a
`brownfield_skip` `[[input]]` and reads it via `inputs.get_bool("brownfield_skip")`. The
user rejected this:

1. **It is redundant.** The no-clobber outcome it protects is already delivered
   deterministically by `idempotent_write` for `git-init` and `license-write`; only
   `gitignore-generate` actually clobbers. No agent judgement is needed to *preserve an
   existing file* — a filesystem `exists()` check suffices.
2. **It pollutes config.** Three base modules gaining a `brownfield_skip` input each,
   plus the agent emitting cross-module skip answers, is noise for a deterministic fact.
3. **It should be uniform.** The check belongs in one primitive used by every module,
   not ad-hoc per module.

So: this spec owns the deterministic detection + preserve/merge semantics for ALL
modules; 008 is rescoped to own only the genuinely agent-judged parts (which optional
modules to enable, and per-overlay pre-fill answers) plus an advisory gate annotation
sourced from this spec's probe. There is no `brownfield_skip` answer anywhere.

## Out of scope

- The brownfield AGENT, Stage 3c pipeline phase, enablement proposal, and pre-fill
  answers — all owned by **008** (which depends on this spec).
- Merge semantics richer than append-only-dedup for `.gitignore` (e.g. semantic TOML
  merge of `pyproject.toml`). Modules that today read-and-recompose their own config
  (lang-* `pyproject`/`package.json` manipulation) keep their existing recompose logic;
  this spec standardizes the *detect + report* layer and the *whole-file* preserve/merge
  decision, not in-file structured merges.
- Any network or git-history scanning. The probe is a pure, offline, read-only
  filesystem stat.

## User Scenarios

### US1 — A module writes into a brownfield repo without clobbering (Priority P0)

A repo already has a `LICENSE`, a `.git/`, and a hand-maintained `.gitignore`. Running
the setup must preserve all three: LICENSE untouched, git not re-init'd, and the
`.gitignore` augmented (existing lines kept, missing stack ignores appended) — never
overwritten.

**Acceptance**: with the artifacts present, `license-write` and `git-init` emit `skip`
Diffs (write nothing); `gitignore-generate` emits a `modify` Diff whose result is the
existing content followed by only the not-already-present template/custom lines, in
canonical order, deduped; no existing user line is dropped.

### US2 — Modules report pre-existing artifacts uniformly (Priority P1)

After the probe, the pipeline can list every pre-existing artifact each enabled module
detected, in one consistent shape, so it can surface them (008 renders these in the
gate as `~ preserve (existing): …`).

**Acceptance**: each enabled module's `ModuleResult` (or the probe call) yields a
machine-readable record of `{artifact_path, state: present|absent, action:
create|preserve|merge}`; the pipeline can aggregate these deterministically without
re-statting the filesystem.

### US3 — A widened secret-shape guard catches more credential formats (Priority P1)

A value shaped like a Google API key (`AIza…`), a Stripe live key (`sk_live_…`), or a
JWT (`eyJ…`) is recognized by `looks_like_secret` and refused at the persist boundary,
not just the original six shapes.

**Acceptance**: `looks_like_secret` returns a non-None label for each newly added
anchored shape, and still returns `None` for a UUID, a git SHA, and a semver string
(no entropy-based false positives).

## Functional Requirements

- **FR-001**: `runner/sdk.py` MUST gain a `brownfield_probe(artifacts, *, project_dir=None)`
  function that takes one or more project-relative artifact paths and returns, per
  artifact, a record of `{path, exists: bool, empty: bool}`. It MUST be pure,
  read-only, offline, and never raise (a missing project dir or unreadable path yields
  `exists=False`). It MUST treat a zero-byte or whitespace-only file as `empty=True` so
  a module can distinguish a real pre-existing artifact from a stub.

- **FR-002**: The probe MUST classify, for a given artifact and a module's declared
  policy, the intended `action`: `create` (absent), `preserve` (present, write-if-absent
  policy), or `merge` (present, append-only policy). The classification MUST be a pure
  function of `(exists, empty, policy)` — no network, no agent input.

- **FR-003**: `manifest.py` MUST parse an optional `[brownfield]` section (or
  per-`[[steps]]` field) in `module.toml` declaring the artifact path(s) a module owns
  and the per-artifact policy (`preserve` | `merge` | `overwrite`). Absent declaration
  MUST be backward-compatible: a module that declares nothing behaves exactly as today.
  Parsing MUST validate the policy enum and surface a `SetupError` on an unknown policy.

- **FR-004**: `sdk.idempotent_write` MUST gain (or be complemented by) an append-only
  **merge** path: given an existing file and a composed body, produce the existing
  content followed by only the lines of the body not already present (membership by
  exact line after stripping trailing whitespace), preserving existing order and
  appending new lines in the body's canonical order. The merge MUST be idempotent
  (re-running yields a `skip`). Identical-content MUST still yield `skip`.

- **FR-005**: `gitignore-generate` MUST switch from `reconcile=True` (overwrite) to the
  append-only merge path when a non-empty `.gitignore` pre-exists, declaring `.gitignore`
  with `policy = "merge"` in its `module.toml [brownfield]`. On a greenfield repo
  (absent `.gitignore`) behavior MUST be byte-identical to today (a `create`).

- **FR-006**: Every module that writes a project artifact MUST be migrated to declare
  its owned artifact(s) in `module.toml [brownfield]` and to obtain pre-existing state
  via `brownfield_probe` (or the policy-driven `idempotent_write`) rather than an ad-hoc
  inline `Path.exists()` check. This is EXHAUSTIVE across modules:
  `git-init`, `license-write`, `gitignore-generate`, `lang-python`, `lang-ts`,
  `lang-go`, `lang-rust`, `package-add`, `precommit-setup`, `dirs-scaffold`,
  `codex-config`, `apm-install`, `agents-md`, `core-identity`, `justfile-write`,
  `github-repo`, `quality-hooks`, `speckit-bridge`, `env-example`. The SDK-bootstrap
  `sdk_path.is_file()` shim (present in every `module.py` for import bootstrapping) is
  NOT a project-artifact check and MUST be left untouched.

- **FR-007**: Migration MUST preserve each module's existing observable behavior except
  where this spec deliberately changes it (only `gitignore-generate`: overwrite →
  merge). Modules whose internal logic *reads* an existing config to recompose it
  (lang-* `pyproject`/`package.json`) MAY keep that recompose logic; FR-006 standardizes
  the *detect/report* of pre-existence and the whole-file preserve/merge action, not the
  in-file structured merge.

- **FR-008**: `runner/sdk.py` MUST widen `looks_like_secret`'s `_SECRET_PATTERNS` with
  additional **anchored** provider shapes cherry-picked from the MIT-licensed gitleaks
  ruleset (e.g. Google `AIza[0-9A-Za-z_-]{35}`, Stripe `sk_live_`/`rk_live_`, Twilio
  `AC`/`SK`, SendGrid `SG\.`, npm `npm_`, PyPI `pypi-`, JWT `eyJ` header). It MUST NOT
  add a third-party dependency, MUST NOT vendor gitleaks' generic/high-entropy rules
  (whose precision depends on keyword+entropy+allowlist prefilters that are not plain
  regex), and MUST retain the "anchored shapes only, no generic entropy heuristic"
  invariant. Borrowed patterns MUST carry an MIT attribution comment.

- **FR-009**: The probe and the migration MUST NOT introduce any new network call,
  subprocess, or third-party import. The runner stays hermetic and stdlib-only; the
  reproduce path stays fully offline and deterministic.

- **FR-010**: The full suite (648 at this spec's start) MUST stay green. Greenfield
  behavior across all migrated modules MUST be byte-identical to pre-migration except
  the single intended `gitignore-generate` merge change, which MUST have its own test.

## Success Criteria

- **SC-001**: On a repo with pre-existing `LICENSE`, `.git/`, and a non-empty
  `.gitignore`, a full run preserves LICENSE byte-for-byte, does not re-init git, and
  produces a `.gitignore` that contains every original line plus the missing stack lines
  (no original line dropped, no duplicate added).
- **SC-002**: `gitignore-generate` on a greenfield repo produces a byte-identical
  `.gitignore` to the pre-migration implementation (regression-locked).
- **SC-003**: `brownfield_probe` returns `exists=False` (never raises) for a missing
  project dir, a missing artifact, and an unreadable path; returns `empty=True` for a
  zero-byte and a whitespace-only file.
- **SC-004**: The append-only merge is idempotent — running it twice yields a `skip` on
  the second run.
- **SC-005**: A `module.toml` declaring `[brownfield]` with an unknown policy yields a
  parse `SetupError`; a module declaring no `[brownfield]` behaves exactly as before.
- **SC-006**: `looks_like_secret` returns a label for each newly added anchored shape
  and `None` for a UUIDv4, a 40-hex git SHA, and `1.2.3-rc.1` (no false positive).
- **SC-007**: The full pre-existing suite passes unchanged; no module's greenfield output
  differs except `gitignore-generate`'s documented merge behavior.
- **SC-008**: `rg` finds no remaining ad-hoc project-artifact `Path.exists()` /
  `is_file()` existence check in any migrated `module.py` that should have moved to the
  probe (the SDK-bootstrap `sdk_path.is_file()` shim excluded), demonstrating the
  standardization is complete.

## Dependencies

- Builds on the 001 runner + modules, 003 stack-resolver, 004 gates, 005 SDK imports
  (all Implemented). Touches `runner/sdk.py`, `runner/manifest.py`, and every module's
  `module.py` / `module.toml`.
- **008 (brownfield-detect) depends on THIS spec** and must ship after it.

## Open Questions

- **OQ-1 (probe API shape)**: should `brownfield_probe` return a list of dataclass
  records, or should the policy-driven behavior live entirely inside `idempotent_write`
  (with `brownfield_probe` only the read-only detector)? Lean: BOTH — `brownfield_probe`
  is the pure read-only detector (for reporting / the 008 gate annotation), and
  `idempotent_write` gains the `merge` policy for the write path. Implementer-resolvable
  after reading `sdk.py:220-257` + `contracts.py` (the `Diff`/`ModuleResult` shapes).
- **OQ-2 (`[brownfield]` granularity)**: declare owned artifacts at the `[brownfield]`
  module level or per `[[steps]]`? Lean: module-level `[brownfield]` listing
  `{path, policy}` entries — most modules own one artifact; lang-* own a few. Confirm
  against `manifest.py` parsing ergonomics during plan authoring.
- **OQ-3 (migration risk budget)**: exhaustive migration touches ~19 modules. Lean:
  migrate in policy groups (write-if-absent modules first — lowest risk; then the
  merge/recompose modules), gating each group on the full suite, to keep the blast
  radius reviewable. Implementer-resolvable.
