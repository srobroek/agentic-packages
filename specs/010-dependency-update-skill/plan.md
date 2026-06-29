# Implementation Plan: Dependency Update / Upgrade Advisory Skill

**Branch**: `feat/project-setup-modular-redesign` (continues) → likely `feat/dep-update-skill`
| **Date**: 2026-06-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature spec `specs/010-dependency-update-skill/spec.md` + the synthesis
sequencing (`specs/roadmap-synthesis.md`) which ships 010 FIRST (zero runner coupling).

## Summary

Build a standalone APM skill package `packages/dep-update/` — a sibling to `dep-audit`
and `whats-new`, NOT a project-setup module. It reads ecosystem lockfiles + (optionally)
`.project-setup/answers.toml`, researches each dependency's latest version + CVEs +
changelog via stdlib registry endpoints, produces a severity-grouped cited upgrade plan,
and applies ONLY patch/minor bumps behind a per-bump `[Y/n]` confirm (majors are
advisory-only; Rust/Go are advisory-only). It never writes `answers.toml`, never imports
the runner SDK, and has no project-setup dependency. Its output is deliberately
time-varying (outside the determinism contract).

The skill follows the established dep-audit/whats-new shape exactly: an `apm.yml`
(`type: skill`), a `.apm/skills/dep-update/SKILL.md` (trigger frontmatter + thick
process doc), helper scripts under `.apm/skills/dep-update/scripts/`, references under
`.apm/skills/dep-update/references/`, and `tests/*.bats`. The deterministic parts
(ecosystem detection, registry queries, the apply loop) live in shell/python scripts;
the agent drives synthesis (changelog prose, the plan narrative, the per-bump decision
framing). This script-does-the-deterministic-part / agent-does-synthesis split is the
dep-audit + whats-new pattern (Settled Decision via OQ-3).

## OQ resolutions (per synthesis leans + spec memory)

- **OQ-1 (share vs copy `detect.sh`)** → **COPY** a skill-local `detect.sh` into
  `packages/dep-update/.apm/skills/dep-update/scripts/`. The portability floor is
  identical to whats-new (bash 3.2.57 + BSD tools), but package coupling (a shared
  script across two APM packages) is worse than ~120 lines of duplication: each skill
  installs standalone. Adapt whats-new's `detect.sh` (it already emits
  `ecosystem<TAB>name<TAB>version`).
- **OQ-2 (apply confirm UX)** → **line-by-line `[Y/n]` in a TTY** (Settled Decision C:
  no global yes-to-all). Each bump is its own prompt with the old→new diff + cite.
- **OQ-3 (script vs agent split)** → **hybrid**: a `research.sh` does the deterministic
  registry queries (PyPI JSON / npm registry via stdlib `urllib` in an embedded python
  one-liner, or `curl` fallback) + semver classification; the agent reads its output,
  fetches changelog prose for MINOR/MAJOR via web-fetch, and drives the apply loop.
- **OQ-4 (changelog fetch depth)** → **registry metadata first, CHANGELOG entry
  fallback**: for MINOR-CHECK fetch the registry's release metadata + the target
  version's CHANGELOG entry; full commit-log spans only on explicit user request
  (latency control for large repos).

## Technical Context

**Language/Version**: bash (portability floor bash 3.2.57 + BSD sed/grep/awk, matching
whats-new) for detection + apply scripts; an embedded `python3` block for registry JSON
parsing (stdlib `json`/`urllib`/`tomllib`) where shell JSON parsing is fragile. No
third-party deps; no runner SDK import (FR-016).

**Primary Dependencies**: none hard. Optional external tools, reported-not-required
(dep-audit posture): `pip-audit`, `npm/pnpm audit`, `osv-scanner` for CVEs; the
ecosystem package managers (`uv`, `npm`, `pnpm`, `bun`) for the apply path. `tomllib`
(py≥3.11) or `tomli` for the `answers.toml` read.

**Storage**: reads only — lockfiles/manifests + `.project-setup/answers.toml`
(opportunistic). The apply path edits ecosystem manifests/lockfiles via the package
manager CLI, never `.project-setup/` (FR-015). No new persisted state.

**Testing**: `tests/*.bats` mirroring `dep-audit/tests/audit.bats` +
`whats-new/tests/detect.bats`. Stubbed registries (a fake `curl`/python opener) for the
research path; a fixture repo with a `uv.lock` + `answers.toml` for the plan path; a
stub package manager for the apply path. NO real network in tests. The bats suite runs
under the repo's existing bats harness (the project-setup pytest suite is unaffected —
this package has no python runner code).

**Target Platform**: macOS + Linux dev + CI. Standalone skill, installed via APM into
claude/codex/agent-skills targets (matching dep-audit `target: all`).

**Constraints**: time-varying output is a FEATURE (FR-017); no reproducibility/caching.
No `answers.toml` write under any path (FR-015, SC-009). No major-bump apply ever
(FR-013). No global yes-to-all (FR-011).

## Constitution Check

No ratified constitution (template). This skill gates on: the spec's Settled Decisions
A–H, the dep-audit read-only-by-default posture (extended with a gated patch/minor apply
path), and the whats-new programmatic-first research posture. It introduces NO
project-setup runner change — the project-setup pytest suite (616) is untouched; the
gate for this work is the new bats suite + a manual smoke against a fixture repo.

## Phase 1 — Package skeleton + manifest

1. `packages/dep-update/apm.yml` — `type: skill`, `target: all`,
   `category: code-intelligence` (matching dep-audit's neighbourhood; spec FR-003 says
   `code-intelligence`), tags `[skill, dependencies, upgrade, advisory, cve]`. NO
   `dependencies:` entry (FR-001/FR-016/SC-010). `includes: auto`.
2. `.apm/skills/dep-update/SKILL.md` — frontmatter `name` + `description` covering the
   trigger phrases (FR-002: "upgrade dependencies", "bump versions", "what's outdated",
   "check for stale packages", "apply safe bumps", "update lockfile", "dep update").
   Body: the thick process doc (when-to-use, preferred flow, the 4-group plan format,
   the apply-loop steering, the majors-advisory-only + Rust/Go-advisory-only rules, the
   ruff-rev note, honest-coverage steering). Mirror dep-audit's SKILL.md structure.
3. `CHANGELOG.md` stub (matching sibling packages).

## Phase 2 — Detection + research scripts

1. `scripts/detect.sh` — adapt whats-new's `detect.sh` (copy + trim to the ecosystems
   in scope: npm/pnpm/yarn, pip/uv/poetry, cargo, go). Emits
   `ecosystem<TAB>name<TAB>version`. Portability floor bash 3.2.57.
2. `scripts/research.sh` — for each `(ecosystem, name)` from detect, query the registry
   latest via stdlib (PyPI JSON `pypi.org/pypi/<name>/json`; npm
   `registry.npmjs.org/<name>`) through an embedded `python3` block (stdlib
   `urllib`+`json`); classify the bump PATCH-SAFE / MINOR-CHECK / MAJOR-ADVISORY by
   semver; mark UNRESOLVABLE on 404/auth/offline (never abort — FR-007). Replicate the
   yanked-version → DISCONFIRMED check (spec Edge Case; mirror `sdk.verify_pins`
   yanked logic without importing it — FR-016). A `--opener`/env test seam so bats can
   stub the registry.
3. `scripts/read_answers.py` (or an embedded block) — stdlib `tomllib`/`tomli` read of
   `.project-setup/answers.toml`: extract `[module.lang-python]` / `[module.lang-ts]`
   `pinned_deps`/`dev_deps`/`framework`/`python_version`/`package_manager`(_pin).
   Opportunistic: absent file/section → empty, never error (FR-005).

## Phase 3 — Plan synthesis + CVE pass

1. The agent (SKILL.md flow) merges detect + research + answers into the 4-group plan
   (CVE-FLAGGED, PATCH-SAFE, MINOR-CHECK, MAJOR-ADVISORY; sorted by name within group;
   "drifted from project-setup baseline" note where lockfile ≠ answers pin — FR-006/
   FR-018).
2. CVE pass: run `pip-audit` / `npm|pnpm audit` / `osv-scanner` if present (guarded by
   `command -v`); a missing scanner is "scanner not available", never "no CVEs"
   (FR-010/FR-019). The skill never installs scanners.
3. Changelog: registry metadata first, then a bare git clone at the tag range, then
   web-fetch prose fallback; each source cited (FR-009, OQ-4 depth rule).

## Phase 4 — Apply path (patch/minor only)

1. `scripts/apply.sh` — given a confirmed `(ecosystem, name, new_version)`, run the
   package manager: `uv add "name==new"` (py); `npm install`/`pnpm update`/`bun add`
   (node, PM chosen from answers `package_manager` else lockfile detection — FR-012).
   PM absent → print the manual command, skip (FR-012). Post-apply manifest re-read to
   confirm the version landed (FR-012a).
2. The agent drives the per-bump `[Y/n]` loop (FR-011); majors NEVER offered (FR-013);
   Rust/Go advisory-only (FR-014). Session summary at the end (FR-020).
3. The ruff-rev note (FR-021): if ruff is bumped + `.pre-commit-config.yaml` parseable,
   offer to update the `astral-sh/ruff-pre-commit` `rev:` bundled with the ruff confirm.

## Phase 5 — Tests + verification

1. `tests/dep-update.bats`:
   - detect: a fixture with `uv.lock` + `pyproject.toml` emits the python deps; a
     `pnpm-lock.yaml` repo emits node deps.
   - research (stubbed registry): a pinned dep == latest is NOT offered; patch/minor/
     major classified correctly; a 404 dep → UNRESOLVABLE; all-offline → graceful
     "no registry access", zero writes (SC-001/SC-006/SC-008).
   - answers read: a fixture `answers.toml` whose `pinned_deps` differ from the lockfile
     flags "drifted" (SC-007); absent `answers.toml` → lockfile-only, no error (SC-006).
   - apply (stub PM): a confirmed patch runs the stub + re-reads (SC-004); a skip is
     summarized (SC-005); a major never reaches the apply loop (SC-003).
   - invariant: NO write to `.project-setup/` under any path (SC-009) — pre/post diff.
   - manifest: `apm.yml` is `type: skill`, no project-setup dependency, trigger
     frontmatter present (SC-010).
2. Run `bats packages/dep-update/tests/` green. (The project-setup pytest suite is
   unaffected — confirm with a quick targeted run, not the full 7-min suite, since no
   runner file changed.)
3. Update the repo marketplace/docs inventory if required (`render-docs.py all` +
   `apm pack` are the build-artifacts step — run if the new package must appear in the
   marketplace block; otherwise note it for the release step).

## Project Structure

```text
packages/dep-update/
├── apm.yml                                  # type: skill, no project-setup dep
├── CHANGELOG.md
├── .apm/skills/dep-update/
│   ├── SKILL.md                             # trigger frontmatter + process doc
│   ├── scripts/
│   │   ├── detect.sh                        # ecosystem+dep enumeration (copied/trimmed from whats-new)
│   │   ├── research.sh                      # registry latest + semver class + yanked/CVE (stdlib urllib)
│   │   └── apply.sh                         # per-bump package-manager apply (patch/minor)
│   └── references/
│       └── recipes.md                       # registry endpoints + PM apply commands per ecosystem
└── tests/
    └── dep-update.bats
```

**Structure Decision**: standalone APM package, NOT under `packages/project-setup/`,
NO runner dependency (Settled Decision F). The only cross-spec touchpoint is reading
the `answers.toml` schema spec-003 writes — read-only, stdlib, opportunistic.

## Complexity Tracking

| Decision | Why needed | Simpler alternative rejected because |
|----------|------------|--------------------------------------|
| Standalone skill, not a module | Output is time-varying (different latest/CVEs next month); a module freezes for reproduction (roadmap:25) | A module would pollute the frozen plan with time-varying data + break zero-network reproduce |
| Copy `detect.sh` not share | Each skill installs standalone via APM | A shared script couples two packages' install graphs for ~120 lines saved |
| Apply via package-manager CLI, not `sdk.idempotent_write` | The skill is a sibling, not a runner consumer; PM updates manifest+lockfile atomically | Importing the runner SDK (FR-016) couples the skill to project-setup internals |
| Majors advisory-only, never applied | Major = breaking by semver contract; auto-applying is unsafe even behind confirm | A confirm-gated major-apply collapses safe/risky into one gesture (spec-004 anti-pattern 5) |
