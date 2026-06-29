# Feature 010 — Dependency Update / Upgrade Advisory Skill (memory)

Authored 2026-06-28 against `feat/project-setup-modular-redesign` HEAD `7779c27`.
This file is the durable record of HOW the spec was reasoned and WHAT needs
resolution before implementation. Everything here is verified against shipped
code unless marked otherwise.

## Scope decision (what 010 is)

010 = **a standalone APM skill** (sibling to `dep-audit` and `whats-new`) that
reads an already-scaffolded repo's lockfiles + `answers.toml`, researches whether
bumps are safe, and produces a cited upgrade plan; applies only patch/minor bumps
behind per-bump confirm; advisory-only for majors. It is **NOT** a project-setup
module and does NOT write `answers.toml`. The determinism contract that governs
specs 001–004 (freeze-then-replay) does NOT apply here — this skill's correct
output is explicitly time-varying and should differ next month.

The spec boundary is clean: spec-003 writes `answers.toml` with frozen pins;
spec-004 gates those writes. Spec-010 reads them (one direction). No runner
touchpoints other than that filesystem read.

## VERIFIED CODE FACTS that shape the spec (read these first)

Verified by direct read of the runner, modules, and sibling skill packages.

### Fact 1 — answers.toml section structure and key names

- `runner/persist.py:8-32` schema comment: `[module.lang-python]` tables with
  `[module.lang-python.source]` provenance sub-tables.
- `persist.py:260-283` `write_answers_toml`: builds the nested
  `{module: {id: {values + source: {provenance}}}}` dict; the `source` sub-table
  carries provenance strings per key.
- **lang-python keys**: `modules/lang-python/module.py:281-284` reads
  `framework`, `pinned_deps`, `dev_deps`, `ruff_version`, and (via module.toml)
  `python_version`. These are the TOML keys the skill reads from
  `[module.lang-python]`.
- **lang-ts keys**: `modules/lang-ts/module.py:199-203` reads `package_manager`,
  `framework`, `pinned_deps`, `dev_deps`, `package_manager_pin`. These are the
  TOML keys the skill reads from `[module.lang-ts]`.
- **Provenance**: the `source` sub-table for agent-resolved keys carries
  `"agent-steered"` — confirming these are the agent's researched pins, not
  manual user entries. The skill can use this to flag when a dep drifted from an
  agent-researched baseline.

### Fact 2 — sdk.verify_pins is MCP-free, stdlib-urllib-only, has a test seam

- `runner/sdk.py:315-380` `verify_pins`: accepts `list[str]` pins + ecosystem
  (`"pypi"` or `"npm"`), fetches PyPI JSON (`pypi.org/pypi/{name}/json`) or npm
  registry (`registry.npmjs.org/{name}`) via `_registry_get` (stdlib
  `urllib.request.urlopen`, `sdk.py:296-312`). Statuses: `PIN_VERIFIED /
  PIN_DISCONFIRMED / PIN_UNREACHABLE`.
- **Test seam**: `_opener` param at `sdk.py:341` — a `(url, timeout) -> json|None`
  callable that replaces the real network fetch. The skill should replicate this
  pattern for its own registry queries so tests run without network.
- **Yanked detection**: `sdk.py:383-412` `_version_present` marks all-yanked
  PyPI releases as absent. The skill must replicate this (or the logic will be
  re-derived; the registry endpoint returns the same data structure).
- The skill MUST NOT import or exec `sdk.py` (FR-016); re-derive these ~30 lines.

### Fact 3 — dep-audit and whats-new sibling structure (the shape to match)

- **Package layout**: both packages are `apm.yml` + `.apm/skills/<name>/SKILL.md`
  + `.apm/skills/<name>/scripts/` + (whats-new only) `references/`. Tests are
  bats files in `tests/`.
- **dep-audit posture** (`dep-audit/SKILL.md:11`): "read-only; never upgrades,
  pins, or auto-fixes." This skill inherits that posture as the default and adds
  a gated apply path.
- **whats-new detect.sh** (`whats-new/scripts/detect.sh:1-16`): bash 3.2.57
  portability floor, no `jq` hard dependency, covers npm/pip/cargo/go, outputs
  `ecosystem\tname\tversion` lines. The skill's own detection script should match
  this portability floor exactly.
- **apm.yml shape**: `name, version, description, author, license, type: skill,
  target: all, includes: auto, category, tags`. No `dependencies` block in either
  sibling — the skill is independent.

### Fact 4 — lang-python/module.toml step shape (the agent step that produces the pins)

- `modules/lang-python/module.toml:32-36`: `kind=agent`, id `"resolve"`, steering
  at `steering/resolve.md`. The step emits `pinned_deps`, `dev_deps`, `ruff_version`
  as `agent-steered` answers persisted to `answers.toml`.
- `modules/lang-ts/module.toml:47-50`: same pattern.
- **This confirms the answers.toml keys are agent-steered, not user-typed** — the
  skill can rely on them being `name@exact-version` format (no ranges, no "latest"
  — the resolver contract forbids them per 003 FR-002).

### Fact 5 — ruff_version / pre-commit coupling (lang-python specific)

- `modules/lang-python/module.py:284` reads `ruff_version = inputs.get_str(...)`.
  The ruff pre-commit hook `rev` is derived from this frozen pin so local run and
  CI hook agree (003 FR-014 / 003 SC-005). If this skill bumps ruff, the
  `.pre-commit-config.yaml` `rev` under `astral-sh/ruff-pre-commit` needs updating
  too. FR-021 captures this coupling.

## The determinism boundary for this spec (driving principle)

The runner's determinism contract (`000`–`004`) governs module steps:
- Tier-1 (`kind=python`): byte-identical for same frozen answers.
- Tier-2 (`kind=agent`): frozen at init, replayed zero-network on reproduce.

This skill is **explicitly outside that contract**. The roadmap rule
(`roadmap:25`): "If the correct output SHOULD change next month, it is a
standalone SKILL, not a pipeline module." The skill's output is correct precisely
when it differs next month (new latest versions, new CVEs). There is no
reproducibility requirement; there is no `plan.json`; there is no `--refresh`
path within the skill (the runner's `--refresh` is for re-researching the initial
agent stack decision, which is a different act).

**Concretely: the skill reads answers.toml (runner output), reads lockfiles (repo
state), queries registries (live external state), and produces an upgrade plan.
None of these steps belong in the runner's determinism envelope.**

## OPEN QUESTIONS — resolve during planning/implementation

Each is written so it can be answered without re-reading the spec. None block
authoring spec.md; they are design details to resolve before or during
implementation.

### OQ-1 — Detection script: copy from whats-new or share? (MED)

The `whats-new/scripts/detect.sh` lockfile scan covers the same ecosystems this
skill needs. Options:
- **(a) Copy** into `dep-update/scripts/detect.sh` (verbatim or with minor
  adaptations). Simple; no inter-package coupling.
- **(b) Reference** whats-new's detect.sh directly from the skill prose (tell the
  agent to use it if available on `PATH`). Fragile — installs may not place it
  on `PATH`.
- **(c) A shared `lockfile-detect` APM package** that both whats-new and dep-update
  `depend on`. Cleanest long-term but adds a third package to maintain.

**Lean: (a)** — copy into this package. The two packages have the same portability
requirement; the script is small (~200 lines); coupling via a shared package for a
detection helper is over-engineering at this stage. If a third skill needs the
same script, extract then.

### OQ-2 — Apply confirm UX: line-by-line TTY vs batch-select? (MED)

FR-011 specifies per-bump `[Y/n]` prompts. Two UX patterns:
- **(a) Line-by-line interactive**: each bump is presented in turn;
  the user types `y`/`n` or Enter. Natural TTY flow; blocking in a non-TTY context.
- **(b) Print plan + "which indices to apply?" prompt**: show the full plan, then
  ask for a comma-separated list of indices (or "all" / "patches-only"). One
  shot; scriptable; but loses the per-bump changelog cite visibility at confirm time.

**Lean: (a)** — line-by-line, matching the 003 gate UX pattern. The skill is
driven by an agent session, not a CI script, so TTY blocking is expected. The
changelog cite is surfaced at each confirm (most useful at the moment of decision).
Non-TTY callers can pipe `"y\ny\nn\n"` etc.; the script should detect `--yes` or
`--no-apply` flags for non-interactive use.

### OQ-3 — Script vs agent for registry queries and apply loop (MED)

`dep-audit` uses a shell script for detection/scanning and the agent for synthesis.
`whats-new` uses a shell script for offline enumeration and the agent for network
research + summarization. Options for 010:
- **(a) Shell/Python script for registry queries + apply**; agent reads the script
  output, synthesizes the plan, drives the per-bump confirms interactively.
- **(b) Agent-only**: the agent calls web-fetch / runs shell commands inline;
  no dedicated helper script beyond detection.
- **(c) Hybrid**: a helper script `scripts/research.sh` handles PyPI/npm JSON
  fetches (deterministic, output-parseable), apply loop is a `scripts/apply.sh`
  the agent drives; agent synthesizes the plan and wording.

**Lean: (c)** — mirrors the dep-audit/whats-new split. The registry fetch and
apply loop are mechanical and testable as scripts; the plan synthesis and
changelog prose summarization are agent work. This also keeps the apply loop
testable (bats tests can stub the package manager) without needing an LLM in the
test loop.

### OQ-4 — Changelog fetch depth for MINOR-CHECK bumps (LOW)

FR-009 says "attempt to fetch changelog data programmatically" for minor bumps.
Options:
- **(a) CHANGELOG entry for the target version only**: fast, small download.
- **(b) Commit log for the full span** (`current..latest`): complete but large
  for projects with many intermediate versions.
- **(c) Latest N releases' notes** from the registry's metadata (PyPI
  `project_urls.Changelog` / npm `repository`): hits the right level of detail
  without cloning.

**Lean: (c) first, (a) as fallback, (b) only if neither is available.** The
`whats-new/references/recipes.md` pattern already documents this ordering for
versioned-software research; adopt it here.

## ASSUMPTIONS made (flagged so they can be corrected)

1. `tomllib` (Python ≥ 3.11) or `tomli` (backport) is available wherever the
   skill runs. If neither is available, the skill degrades gracefully (skips
   `answers.toml` read, lockfile-only mode). This is the same assumption the
   runner makes about `uv`.
2. PyPI JSON and npm registry endpoints are reachable over plain HTTPS GET, no
   auth, same as `sdk.py:282-283`. Private registries (Artifactory, etc.) are
   out of scope for this spec; the skill reports `UNRESOLVABLE` for any 401/403.
3. Semver version strings from the registry are parseable as `MAJOR.MINOR.PATCH`
   (with optional pre-release suffix). Non-semver version schemes (Calendar
   Versioning, date-stamped) are classified as `UNRESOLVABLE` for semver safety
   class (advisory note, no apply offered).
4. The skill runs in a TTY (interactive) context by default; the apply confirm
   loop is `[Y/n]` line-by-line. `--no-apply` flag suppresses the apply path
   entirely (plan-only mode).
5. The skill does not need to handle private git sources declared in
   `sources.toml` — it reads only the public lockfile/manifest + answers.toml;
   private source modules' deps are not in the public registry anyway.

## AS-BUILT (TBD)

_Fill in after implementation: refinements vs the plan, test counts, OQ
resolutions, any edge-case surprises._

## Cross-spec interactions

| Spec | Relationship |
|---|---|
| 003 stack-resolver | Writes the `answers.toml` keys this skill reads. No dependency — spec-010 works on repos with no answers.toml. |
| 004 gates | The `init_only` gate + `--allow-stack-write` gate in 003/004 governs WRITING pins. This skill has no gate interaction with the runner. |
| dep-audit | Sibling skill; inherits read-only-by-default posture; shares CVE scanner list. The two skills are complementary: dep-audit finds CVEs NOW; dep-update researches upgrade paths. |
| whats-new | Sibling skill; detection script logic is copied (OQ-1). The two skills are complementary: whats-new researches a named target's changelog; dep-update iterates the repo's full dep set. |

## Calibration rules for the apply gate

Since this skill is outside the runner's gate machinery, the per-bump confirm
must enforce the same anti-fatigue discipline independently:

- **Hard cap**: majors are NEVER offered — not a gate, a hard code refusal.
- **Per-bump, not per-session**: each bump is a separate confirm, not a batch
  "apply all patches" (that would be the yes-to-all anti-pattern in a different
  form — a dozen patches accepted in one confirm, one of which is a yanked or
  conflicting version).
- **Fail-closed on package manager error**: if `uv add` exits non-zero, the bump
  is recorded as FAILED and the skill continues to the next one. No retry, no
  silent partial application.
- **The `answers.toml` pins are NOT updated even if the skill applies bumps.**
  The runner's `--refresh` is the path to re-freeze new agent decisions; the
  skill's job ends at updating the lockfile/manifest.
