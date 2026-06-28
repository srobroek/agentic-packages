# Feature Specification: Dependency Update / Upgrade Advisory Skill

**Feature Branch**: `feat/project-setup-modular-redesign` (continues) → likely a
dedicated `feat/dep-update-skill` branch

**Created**: 2026-06-28

**Status**: Draft (2026-06-28)

**Input**: Roadmap rank #8 (`reviews/tier2-agentic-features-roadmap.md:78-81`) —
"dependency-update / upgrade-advisory as a STANDALONE skill". The roadmap is
explicit: this MUST NOT be a pipeline module (its correct output is time-varying)
and MUST NOT write `answers.toml`. The only project-setup touchpoint is that the
scaffold LEAVES durable inputs (pinned versions + recorded framework in
`answers.toml`) for this skill to read.

## Overview

The 003 stack-resolver froze exact dependency pins into
`.project-setup/answers.toml` (keys `pinned_deps`, `dev_deps`,
`package_manager_pin` per module, `framework` per `lang-python`/`lang-ts`,
`python_version`). The 004 gates spec gave the user a hard confirm before those
pins were written. But pins rot: a `fastapi@0.111.0` that was current at init is
stale next quarter; `pydantic@2.7.1` may have a CVE by the time the next team
member clones the repo.

This feature is a **standalone skill** (APM package, sibling to `dep-audit` and
`whats-new`) that:

1. Reads the ecosystem lockfiles **and** the project-setup `answers.toml` (the
   frozen agent-researched pins) from the target repo.
2. Researches each dependency: what is the current latest, are there intervening
   CVEs or deprecations, is a bump safe (semver minor/patch vs major)?
3. Produces a **cited upgrade plan** — grouped by severity, with changelog
   sources, a safe/caution/major classification, and a concrete diff of what
   would change in each manifest.
4. Applies **only** patch and minor bumps interactively, one by one, behind a
   per-bump confirm. Major bumps are **advisory-only** — the skill names them,
   explains the breaking changes, and stops.

This is deliberately **outside the project-setup determinism contract**. The
runner's determinism model (Tier-1 byte-identical replay, Tier-2 frozen agent
decision) is the right model for *bootstrapping* a project. It is the wrong model
for keeping it current. Upgrade advisory has no reproduction contract: the same
skill invoked next month on the same repo should produce a *different* plan
(newer latest versions, new CVEs). Forcing it into a module would pollute the
frozen plan with time-varying data and break the zero-network reproduce guarantee.

The skill reads `answers.toml` in one direction only: to learn which lockfiles to
examine, which ecosystem to use, what framework the project targets, and what pins
are the "baseline before any manual drift". It never writes or amends
`answers.toml` — that file is owned by the runner.

## Current state (verified — citations, do not re-derive)

All file:line references verified against `feat/project-setup-modular-redesign`
at HEAD `7779c27`.

- **`answers.toml` schema is `[module.<id>]` tables with parallel
  `[module.<id>.source]` sub-tables** (`runner/persist.py:8-32` schema comment;
  `persist.py:260-283` `write_answers_toml` builds the `{module: {id: {values...,
  source: {...provenance...}}}}` TOML structure). The `[module.lang-python]` and
  `[module.lang-ts]` sections carry the pinned stack.
- **`lang-python` writes `pinned_deps`, `dev_deps`, `ruff_version`, `framework`,
  `python_version` as frozen answers.** `modules/lang-python/module.py:281-284`
  reads `framework = inputs.get_str("framework")`, `pinned_deps =
  inputs.get_list("pinned_deps")`, `dev_deps = inputs.get_list("dev_deps")`,
  `ruff_version = inputs.get_str("ruff_version")`.
- **`lang-ts` writes `pinned_deps`, `dev_deps`, `package_manager_pin`,
  `framework`, `package_manager` as frozen answers.** `modules/lang-ts/module.py:
  199-203` reads `pkg_manager = inputs.get_choice("package_manager")`, `framework
  = inputs.get_str("framework")`, `pinned_deps = inputs.get_list("pinned_deps")`,
  `dev_deps = inputs.get_list("dev_deps")`, `package_manager_pin =
  inputs.get_str("package_manager_pin")`.
- **The lang-* resolver step is `kind=agent` with `source: "agent-steered"`
  provenance** (`lang-python/module.toml:32-36`; `lang-ts/module.toml:47-50`).
  Both steps use the steering doc at `steering/resolve.md` and emit agent-steered
  answers folded into `answers.toml` at persist (runner stage 8).
- **`answers.toml` key names are exact**: the TOML section is
  `[module.lang-python]` / `[module.lang-ts]`; list values (`pinned_deps`,
  `dev_deps`) are TOML arrays of `"name@exact-version"` strings. The `source`
  sub-table records `"agent-steered"` provenance for agent-resolved keys.
- **`sdk.verify_pins` exists and is MCP-free** (`runner/sdk.py:315-380`). It
  accepts a list of `name@version` strings and an `ecosystem` (`"pypi"` or
  `"npm"`), fetches PyPI JSON (`pypi.org/pypi/{name}/json`) or npm registry
  (`registry.npmjs.org/{name}`) via stdlib `urllib`, and returns
  `PIN_VERIFIED / PIN_DISCONFIRMED / PIN_UNREACHABLE` per pin. Its `_opener` test
  seam (`sdk.py:341`) allows stub-based testing without network.
- **The `dep-audit` skill (sibling) is read-only by posture** (`packages/dep-audit/
  .apm/skills/dep-audit/SKILL.md:11`: "This skill is read-only: it reports, it
  never upgrades, pins, or auto-fixes anything."). The new skill inherits this
  posture as the default but adds an opt-in apply path for patch/minor bumps.
- **The `whats-new` skill (sibling) detects ecosystem lockfiles offline via
  `scripts/detect.sh`** (`packages/whats-new/.apm/skills/whats-new/scripts/
  detect.sh:1-16`). That script covers npm/pnpm/yarn, pip/poetry/uv, cargo, go —
  the same ecosystems this skill needs to enumerate.
- **No existing skill applies dependency bumps** to manifests or lockfiles. Both
  `dep-audit` and `whats-new` are report-only. The new skill is the first in the
  family to have a gated write path.
- **`sdk.looks_like_secret` exists** (`runner/sdk.py:432-444`) and is used at the
  interview/persist boundary. It is not relevant to this skill's write path (the
  skill writes dependency versions, not secrets) but documents the SDK posture
  this skill inherits.
- **The runner's `--refresh` mechanism** (`003` FR-010; `runner/cli.py`) is the
  project-setup path to re-research frozen agent decisions. This skill is NOT that
  path: it is an entirely separate, time-varying advisory loop that operates on
  the living repo's lockfiles, not just the frozen plan.

## Settled decisions

- **A — This is a skill, not a module.** The roadmap rule is binding
  (`roadmap:25`): "If the correct output SHOULD change next month, it is a
  standalone SKILL, not a pipeline module." Upgrade advisory satisfies that rule:
  the skill invoked on the same repo next month should report different latest
  versions and possibly new CVEs. A pipeline module's output freezes for
  reproduction; a skill's output is time-varying by design. No `module.toml`,
  no `kind=agent`/`kind=python` steps, no `plan.json` involvement.
- **B — The skill READS `answers.toml`; it NEVER writes it.** `answers.toml` is
  owned by the project-setup runner. The skill reads it as a source of structured
  baseline information (ecosystem, frozen pins, framework). Writing to it would
  violate the runner's determinism contract: a plain `reproduce` after the skill's
  bump write would re-derive the Tier-1 manifest from the answers — and the
  answers would no longer match the live lockfile. The manifest write path (if the
  user approves a bump) targets the ecosystem lockfile/manifest directly, not
  `answers.toml`.
- **C — Majors are advisory-only; patch/minor require per-bump confirm.** Semver
  major bumps are breaking changes by contract. The skill names them, cites the
  changelog, and produces a "what you would need to change" summary — but NEVER
  applies them, not even behind a confirm. Patch and minor bumps are offered for
  application one at a time, each behind a `[Y/n]` confirm. A global "yes-to-all"
  for bumps is a **binding non-goal** (mirrors spec-004's anti-pattern 5 — a
  batch-approve collapses safe/risky bumps together).
- **D — Research is programmatic-first, web-fetch only for prose gaps.** Version
  discovery uses machine endpoints (PyPI JSON, npm registry JSON) via the same
  stdlib `urllib` path the runner SDK uses — no scraping, no rendered pages. Web
  fetch is the fallback for changelog prose (migration guides, breaking-change
  explanations) that has no machine endpoint. This mirrors `whats-new`'s posture
  (`whats-new/SKILL.md:14-18`).
- **E — The skill reads both lockfiles AND `answers.toml`.** Lockfiles give the
  live resolved versions (what is actually installed). `answers.toml` gives the
  agent-researched baseline (what was the *intended* pinned set, including the
  framework context). The combination lets the skill flag: (a) lockfile drifted
  from `answers.toml` pins (manual edits or partial updates), (b) current latest
  > lockfile pin, (c) CVE in the installed version. The `answers.toml` read is
  opportunistic: the skill works on a repo that has no `answers.toml` (just reads
  the lockfile).
- **F — The skill is a standalone APM package** with the same shape as `dep-audit`
  and `whats-new`: `apm.yml` + `.apm/skills/dep-update/SKILL.md` +
  `.apm/skills/dep-update/scripts/` + `.apm/skills/dep-update/references/`. It
  does NOT live under `packages/project-setup/` and does NOT `require` or depend
  on the project-setup package. The `answers.toml` read is filesystem-only
  (stdlib `tomllib`/`tomli`); no runner SDK import.
- **G — The apply path targets ecosystem manifests + runs the package manager;
  it does NOT use `sdk.idempotent_write`.** The runner SDK is a project-setup
  internal; this skill is a sibling, not a consumer of runner internals. Bump
  application uses direct file edits (stdlib) + the ecosystem's own package
  manager CLI (`uv add`, `npm install`, `pnpm update`, `bun update`,
  `cargo update`) to update both the manifest and the lockfile atomically. If the
  package manager is absent, the skill reports the manual command.
- **H — No answers.toml write, even to record applied bumps.** Applied bumps are
  recorded in the lockfile by the package manager. The frozen pins in
  `answers.toml` may become stale after the skill applies bumps — that is
  expected and acceptable. The runner's `--refresh` is the path to re-freeze new
  agent decisions; this skill is not that path.

## User Scenarios & Testing

### User Story 1 — Produce a cited upgrade plan for a Python project (Priority: P1)

A maintainer runs the skill against a FastAPI project that was scaffolded six
months ago. The skill reads `answers.toml` (lang-python pins: `fastapi@0.111.0`,
`pydantic@2.7.1`, `python@3.13`, `ruff@0.4.5` …), reads `uv.lock`, queries PyPI,
fetches changelogs, and returns a plan grouped by safety class.

**Acceptance Scenarios**:

1. **Given** a project with a `uv.lock` and a `[module.lang-python]` block in
   `answers.toml`, **When** the skill runs, **Then** it reads the pinned versions
   from both sources, queries PyPI for the current latest of each, and produces a
   grouped plan: PATCH-SAFE, MINOR-CHECK, MAJOR-ADVISORY, CVE-FLAGGED.
2. **Given** a dep with a CVE in the installed version, **When** the plan is
   produced, **Then** the CVE is flagged in a dedicated CVE-FLAGGED group,
   ordered before safety classes, with the advisory id and a cite.
3. **Given** a dep with a major version increment available, **When** the plan is
   produced, **Then** it appears in MAJOR-ADVISORY with the breaking-change summary
   and a changelog cite; the skill MUST NOT offer to apply it.

### User Story 2 — Apply patch/minor bumps behind per-bump confirm (Priority: P1)

After reviewing the plan from US1, the user decides to apply the safe bumps. Each
patch/minor bump is presented one at a time with the old→new diff and changelog
cite; the user confirms or skips each.

**Acceptance Scenarios**:

1. **Given** the upgrade plan, **When** the user runs the apply flow, **Then** the
   skill presents each patch/minor bump in turn: `name: old → new (PATCH|MINOR)
   [cite]`, `[Y/n]`.
2. **Given** a confirmed bump, **Then** the skill runs the appropriate package
   manager command (`uv add name==new`, `npm install name@new`, etc.) and
   verifies the manifest/lockfile reflects the new version before proceeding to
   the next bump. If the package manager is absent, it prints the manual command.
3. **Given** a skipped bump (user types `n`), **Then** the dep is recorded as
   "skipped" in the session summary and the skill moves to the next bump.
4. **Given** all bumps processed, **Then** the skill prints a summary: applied N,
   skipped M, advisory-only K major(s), advisory-only J CVE(s) (if any were
   advisory-only majors or un-applied CVEs remain).

### User Story 3 — Works on a repo with no answers.toml (Priority: P2)

A repo was not scaffolded with project-setup (or `answers.toml` is absent). The
skill still works by reading the lockfile directly; the `answers.toml` column in
the plan is simply absent.

**Acceptance Scenarios**:

1. **Given** a repo with `package.json` + `pnpm-lock.yaml` but no
   `.project-setup/answers.toml`, **When** the skill runs, **Then** it reads
   pinned versions from the lockfile only, queries npm, and produces the plan
   without the "baseline from project-setup" column.
2. **Given** a repo with `answers.toml` whose `pinned_deps` diverges from the
   lockfile (manual bump outside the runner), **Then** the plan flags the
   divergence as a note in the per-dep row.

### User Story 4 — No version found for a dependency (Priority: P2)

A dep in the lockfile does not appear on the public registry (private, removed,
or name-squatted). The skill reports it as "unresolvable" and skips it without
erroring out.

**Acceptance Scenarios**:

1. **Given** a lockfile with a private/scoped dep that returns 404 or requires
   auth, **When** the skill queries the registry, **Then** the dep is listed as
   `UNRESOLVABLE` with the reason (404 / auth-required hint), and the skill
   continues with the remaining deps.
2. **Given** all registry calls failing (offline), **When** the skill runs, **Then**
   it reports "no registry access" and exits gracefully — no plan, no writes,
   no crash.

### Edge Cases

- **Major bump with no published changelog / migration guide**: the skill says so
  explicitly ("no changelog found") and advises the user to check the upstream
  repo manually before upgrading.
- **Patch bump that is actually a yanked version on PyPI**: `sdk.verify_pins`
  logic (`sdk.py:383-412`) treats all-yanked files as `PIN_DISCONFIRMED` — the
  skill must replicate this check (or delegate to the same helper) before offering
  a bump to a yanked version.
- **`answers.toml` present but no `[module.lang-python]` / `[module.lang-ts]`
  section** (project-setup ran without lang overlays): skip the answers.toml
  column for those ecosystems; read lockfiles only.
- **User approves a bump but the package manager exits non-zero** (network error,
  dependency conflict): the skill reports the failure, leaves the manifest at its
  pre-bump state, and continues with the remaining bumps rather than aborting the
  session.
- **Monorepo with multiple lockfiles**: the skill processes each lockfile
  independently; the plan is grouped by lockfile path.
- **`ruff_version` in answers.toml** (lang-python specific): the ruff pre-commit
  hook `rev` is derived from the frozen ruff pin (`module.py:284`). If the skill
  bumps ruff, it notes that the `.pre-commit-config.yaml` `rev` also needs
  updating and either applies it (if the pre-commit config is parseable) or prints
  the manual change.

## Requirements

### Skill artifact (package shape)

- **FR-001**: The skill MUST be a standalone APM package at
  `packages/dep-update/`, structured as: `apm.yml` (type: skill), `.apm/skills/
  dep-update/SKILL.md` (trigger frontmatter + workflow doc), `.apm/skills/
  dep-update/scripts/` (helper scripts), `.apm/skills/dep-update/references/`
  (recipe references for machine endpoints). It MUST NOT live under
  `packages/project-setup/` and MUST NOT declare a dependency on project-setup in
  its `apm.yml`.
- **FR-002**: `SKILL.md` MUST declare a frontmatter trigger description covering:
  "upgrade dependencies", "bump versions", "what's outdated", "check for stale
  packages", "apply safe bumps", "update lockfile". Optionally triggered by "dep
  update" or "renovate" phrasing.
- **FR-003**: The skill MUST declare `type: skill` and `category: code-intelligence`
  (matching `dep-audit`'s category) in `apm.yml`. Tags MUST include
  `dependencies`, `upgrade`, `advisory`, `skill`.

### Inputs and ecosystem detection

- **FR-004**: The skill MUST detect ecosystem(s) by scanning for lockfiles and
  manifests in the project directory (reusing or mirroring the detection logic
  from `whats-new`'s `scripts/detect.sh`): `uv.lock` / `poetry.lock` /
  `Pipfile.lock` / `requirements.txt` / `pyproject.toml` → Python; `pnpm-lock.yaml`
  / `package-lock.json` / `yarn.lock` → Node; `Cargo.lock` → Rust (advisory only,
  no apply); `go.sum` → Go (advisory only, no apply). The apply path (FR-011) is
  enabled only for Python and Node where the CLI tooling is stable and
  well-defined; Rust and Go are advisory-only (FR-014).
- **FR-005**: If `.project-setup/answers.toml` is present, the skill MUST read it
  with stdlib `tomllib` / `tomli` and extract, for each detected ecosystem: the
  `pinned_deps` list, `dev_deps` list, `framework`, `python_version` / `package_manager`
  / `package_manager_pin` from the appropriate `[module.lang-*]` section. The
  `answers.toml` read is opportunistic — absent file or absent module section
  MUST NOT cause an error.
- **FR-006**: The skill MUST cross-reference lockfile versions against
  `answers.toml` pins. A dep present in both whose versions differ MUST be noted
  as "drifted from project-setup baseline" in the plan.

### Research (version, safety, changelog)

- **FR-007**: For each detected dependency, the skill MUST query its registry for
  the current latest version using machine endpoints: PyPI JSON API
  (`https://pypi.org/pypi/{name}/json`) for Python; npm registry JSON
  (`https://registry.npmjs.org/{name}`) for Node. Registry queries MUST use
  stdlib `urllib` only (no third-party HTTP client dependency). Network errors
  MUST NOT abort the skill: a per-dep `UNRESOLVABLE` status is emitted and the
  skill continues.
- **FR-008**: The skill MUST classify each potential bump by safety class:
  - `PATCH-SAFE` — semver patch increment (`x.y.Z → x.y.Z+n`); apply offered
    by default.
  - `MINOR-CHECK` — semver minor increment (`x.Y.z → x.Y+n.0`); apply offered
    with a changelog cite.
  - `MAJOR-ADVISORY` — semver major increment (`X.y.z → X+n.0.0`); report-only,
    NEVER offered for application (FR-013).
  - `CVE-FLAGGED` — current version has a known CVE (sourced from `pip-audit` /
    `npm audit` / `osv-scanner` output if available); surfaced first in the plan
    regardless of semver class.
- **FR-009**: For MINOR-CHECK and MAJOR-ADVISORY bumps the skill MUST attempt to
  fetch changelog or release-note data programmatically: first from the registry's
  metadata (PyPI `info.project_urls`, npm `repository`), then from a bare git
  clone at the appropriate tag range, then as a fallback from a rendered page via
  web fetch. Each changelog source MUST be cited (URL or git tag) in the plan.
- **FR-010**: The skill MUST check for CVEs by running `pip-audit` (Python) or
  `npm audit` / `pnpm audit` (Node) if the tool is available. A missing scanner
  MUST be noted as "scanner not available" (never claimed as "no CVEs"). The skill
  MUST NOT install scanners itself; it reports with install hints (matching
  `dep-audit`'s posture — `dep-audit/SKILL.md:46-52`).

### Apply path (patch/minor only)

- **FR-011**: For each `PATCH-SAFE` and `MINOR-CHECK` dep, the skill MUST offer
  a per-bump `[Y/n]` confirm (default Yes for patch; default Yes for minor with
  changelog shown). A global "yes-to-all" MUST NOT exist (Settled Decision C).
- **FR-012**: A confirmed bump MUST be applied by running the ecosystem package
  manager: `uv add "name==new_version"` (Python); `npm install "name@new_version"` /
  `pnpm update name --version new_version` / `bun add "name@new_version"` (Node).
  The package manager choice for Node MUST be read from `answers.toml`
  `package_manager` if available, else detected from the lockfile (`pnpm-lock.yaml`
  → pnpm; `bun.lock` → bun; `package-lock.json` → npm). If the package manager
  is absent, the skill MUST print the manual command and skip the apply.
- **FR-012a**: After applying a bump, the skill MUST verify the manifest reflects
  the new version (re-read the manifest file) before proceeding to the next bump.
  A post-apply mismatch (package manager reported success but version did not
  change) MUST be reported as a warning.
- **FR-013**: The skill MUST NOT apply major bumps under any circumstances — not
  even if the user explicitly asks. Major bumps MUST be advisory-only: the skill
  names the dep, summarizes breaking changes, cites sources, and stops. The user
  must perform a major bump manually. (Settled Decision C.)
- **FR-014**: Rust and Go deps are advisory-only in this spec: the skill reports
  available updates and CVEs but MUST NOT apply bumps. `cargo update` and
  `go get` are intentionally deferred (see Out of Scope).

### Determinism boundary (explicitly outside the contract)

- **FR-015**: The skill MUST NOT write or amend `.project-setup/answers.toml` or
  `.project-setup/sources.toml`. Those files are owned by the project-setup
  runner; the skill is a read-only consumer of the runner's outputs.
- **FR-016**: The skill MUST NOT invoke the project-setup runner (`cli.py`) or
  import the runner SDK (`sdk.py`) directly. Any SDK logic the skill needs
  (ecosystem detection, registry queries) MUST be re-implemented with stdlib only,
  or delegated to the skill's own helper scripts. This keeps the skill's
  dependency surface identical to `dep-audit` and `whats-new` (no dependency on
  project-setup).
- **FR-017**: The skill's output is explicitly time-varying. The same invocation
  on the same repo MUST produce different results as registries evolve. This is a
  feature, not a bug. There is no "reproducible" mode, no plan caching, and no
  frozen output. (Settled Decision A.)

### Reporting

- **FR-018**: The plan MUST be organized in four groups (in priority order):
  CVE-FLAGGED (if any), PATCH-SAFE, MINOR-CHECK, MAJOR-ADVISORY. Within each
  group, deps are sorted by name. Each row MUST include: dep name, current
  version (from lockfile), latest version, safety class, changelog citation (if
  fetched), and a "drifted from project-setup baseline" note (if answers.toml
  diverges).
- **FR-019**: The skill MUST state coverage honestly: which ecosystems were
  detected, which lockfiles were read, which CVE scanners ran, and which were
  missing. It MUST NOT imply an ecosystem is clean when its scanner was not
  available (matching `dep-audit/SKILL.md:63`).
- **FR-020**: After the apply session, the skill MUST print a summary: N bumps
  applied, M skipped, K advisory-only major(s) not applied, J CVE(s) requiring
  manual action (if any remain un-applied). Any package manager failures are
  listed by dep name.

### `ruff` pre-commit integration note

- **FR-021**: If `ruff` is bumped in a Python project AND `.pre-commit-config.yaml`
  exists AND a `rev:` under `astral-sh/ruff-pre-commit` is parseable, the skill
  MUST note that the pre-commit `rev` should match the new ruff version (because
  `lang-python`'s `module.py:284` derives it from the frozen ruff pin). If the
  pre-commit config is parseable as YAML, the skill MUST offer to update the
  `rev:` as part of the ruff bump confirm (`[Y/n]` bundled with the ruff version
  bump). If not parseable, the skill prints the manual change.

## Success Criteria

- **SC-001**: A project with a `uv.lock` and `[module.lang-python]` block in
  `answers.toml` produces a grouped upgrade plan with correct semver
  classification and PyPI-sourced latest versions; a pinned dep equal to latest
  is not reported as upgradeable. (Verified by test with a stubbed PyPI registry.)
- **SC-002**: A dep with a simulated CVE from `pip-audit` / `osv-scanner` output
  appears in CVE-FLAGGED ahead of all other groups in the plan output.
- **SC-003**: A major bump candidate is listed in MAJOR-ADVISORY with a changelog
  cite and MUST NOT appear in the per-bump confirm flow; the apply path skips it
  entirely.
- **SC-004**: A confirmed patch bump runs the appropriate package manager command;
  the manifest re-read confirms the new version is reflected; the skill proceeds
  to the next dep.
- **SC-005**: A skipped bump (user selects `n`) is listed as "skipped" in the
  session summary and does not prevent the remaining bumps from being offered.
- **SC-006**: In a repo with no `.project-setup/answers.toml`, the skill runs
  without error against the lockfile only; the "baseline from project-setup"
  column is omitted from the plan.
- **SC-007**: In a repo with `answers.toml` whose `pinned_deps` differ from the
  lockfile, the affected deps are flagged "drifted from project-setup baseline"
  in the plan.
- **SC-008**: When all registry queries fail (offline / stubbed to time out), the
  skill exits gracefully with a "no registry access" report and zero writes.
- **SC-009**: The skill produces no writes to `.project-setup/answers.toml` or
  `.project-setup/sources.toml` under any execution path (verified by a
  filesystem watcher or pre/post diff in the test).
- **SC-010**: The `apm.yml` declares `type: skill` (not `module`), no `dependencies`
  entry pointing at project-setup, and the trigger frontmatter in `SKILL.md`
  covers the expected invocation phrases.

## Out of Scope

- Writing or amending `answers.toml` in any way — this is a hard invariant
  (Settled Decision B / FR-015).
- Applying major bumps, even behind confirmation (Settled Decision C / FR-013).
- `cargo update` / `go get` apply paths for Rust and Go — advisory-only in this
  spec; apply can be added in a followup.
- A "Renovate-style" automated PR workflow (the skill is interactive, not a CI
  bot).
- Resolution of transitive dependency conflicts after a bump (the skill delegates
  to the package manager; if it fails, the skill reports the error and skips).
- Changing `.project-setup/` structure or the project-setup runner's
  `answers.toml` schema — this spec has no runner touchpoints beyond reading the
  file.
- Importing or wrapping the project-setup runner SDK (`sdk.py`) (Settled
  Decision F / FR-016) — the skill is standalone.
- Re-pinning the full stack after bumps (i.e. re-running the Tier-2 resolver) —
  that is the project-setup `--refresh` path, not this skill.
- A TUI or diff-view UI; the per-bump confirm is a plain `[Y/n]` prompt.

## Assumptions

- `tomllib` (Python ≥ 3.11 stdlib) or `tomli` (backport) is available for reading
  `answers.toml`; the skill documents the install hint for older Pythons.
- PyPI JSON (`https://pypi.org/pypi/{name}/json`) and npm registry
  (`https://registry.npmjs.org/{name}`) are the canonical public registry
  endpoints, reachable over plain HTTPS GET with no auth — same assumption as
  `sdk.py:282-283`.
- The `whats-new` `scripts/detect.sh` portability floor (bash 3.2.57 + BSD
  sed/grep/awk) applies to this skill's detection helper as well.
- The semver classification (patch/minor/major) is based on the published version
  strings from the registry; pre-release versions (`rc`, `alpha`, `beta`,
  `a`, `b`) are excluded from upgrade offers unless the current installed version
  is also pre-release.
- `pip-audit`, `npm audit`, `pnpm audit`, `osv-scanner` are optional external
  tools; their absence is reported, never a hard failure.

## Dependencies & Open Questions

**Cross-spec dependency, read-only:** this skill reads the `answers.toml` that
spec-003 writes and spec-004 gates. There is no build-order dependency — the skill
is standalone and works on repos that were not scaffolded with project-setup. The
003/004 work only defines the input format this skill reads.

**Remaining open questions** (OQ-1 … OQ-4) are tracked in `memory.md`. None block
authoring this spec; they are design details to resolve during planning /
implementation.

- **OQ-1** — whether to share the `detect.sh` lockfile-scan logic with `whats-new`
  or copy it into a skill-local script (the portability requirement is identical;
  the question is package coupling vs duplication).
- **OQ-2** — the exact `[Y/n]` confirm UX for the apply flow: line-by-line in a
  TTY vs a printed list followed by "which bumps to apply? (comma-separated
  indices)"; the choice affects the script vs agent driving distinction.
- **OQ-3** — whether the skill is driven entirely by agent (skill prose) or
  partly by a shell/Python script for the registry queries and the apply loop; the
  dep-audit/whats-new pattern uses a shell script for the deterministic part and
  the agent for synthesis — the same split applies here.
- **OQ-4** — changelog fetch depth: for MINOR-CHECK bumps, fetch only the
  CHANGELOG entry for the target version vs the full commit log for the span; the
  tradeoff is completeness vs latency for large repos.
