---
name: dep-update
description: >-
  Research each dependency's current latest version, classify bumps by semver
  safety, surface CVEs, and produce a cited upgrade plan grouped by severity.
  Apply only patch and minor bumps interactively — one at a time behind a
  per-bump confirm. Major bumps are advisory-only and never applied. Use when
  the user asks to upgrade dependencies, bump versions, check what's outdated,
  check for stale packages, apply safe bumps, update the lockfile, run dep
  update, or renovate dependencies.
---

# Dependency Update / Upgrade Advisory

On-demand (model-invoked) skill. Detect the project's ecosystem(s) from
lockfiles and manifests, read the installed dependency versions, query their
public registries for the current latest, classify each potential bump by
semver safety class, surface CVEs via native scanners, and produce a
severity-grouped cited upgrade plan. Patch and minor bumps may be applied
interactively — one at a time, each behind a `[Y/n]` confirm. Major bumps are
**advisory-only**: the skill names them, cites the breaking-change summary,
and stops. The skill never writes `.project-setup/answers.toml`.

## When to use

Triggers: "upgrade dependencies", "bump versions", "what's outdated", "check
for stale packages", "apply safe bumps", "update lockfile", "dep update",
"renovate", "check for outdated packages", "update my dependencies".

Not a CI bot. The output is time-varying by design — the same invocation on
the same repo next month should produce a different plan. Do not use to
reproduce a frozen bootstrap; use the project-setup `--refresh` path for that.

## Preferred flow

1. Run `scripts/detect.sh [dir]` from the project root. It enumerates
   dependencies and their lockfile-pinned versions as
   `ecosystem<TAB>name<TAB>version` lines and writes a summary to stderr.
2. Optionally read `.project-setup/answers.toml` (if present) to extract the
   agent-researched baseline pins from `[module.lang-python]` /
   `[module.lang-ts]`. Use stdlib `tomllib` (Python ≥ 3.11) or `tomli`
   (backport). Absent file or section → continue silently with lockfile only.
3. Run `scripts/research.sh [dir]` (or pass the detect output). For each
   dependency it queries PyPI / npm registries, classifies the bump, and
   emits one JSON-lines record per dep. Pass `DEP_UPDATE_REGISTRY_OPENER=path`
   to stub the registry in tests.
4. Run CVE scanners if available (see Ecosystem → Scanner table below). A
   missing scanner is reported as "scanner not available" — never omit it
   silently or imply the ecosystem is clean.
5. Synthesize the upgrade plan in four groups (in priority order):
   **CVE-FLAGGED** → **PATCH-SAFE** → **MINOR-CHECK** → **MAJOR-ADVISORY**.
   Within each group sort by dependency name. Each row: dep name, current
   version (lockfile), latest version, safety class, changelog citation (if
   fetched), and a "drifted from project-setup baseline" note if the
   `answers.toml` pin diverges from the lockfile version.
6. For MINOR-CHECK and MAJOR-ADVISORY bumps, fetch changelog / release-note
   prose: try registry metadata (`info.project_urls` for PyPI; `repository`
   for npm), then a blobless bare git clone at the tag span, then a targeted
   web-fetch of the migration page as a last resort. Cite every source by URL
   or git tag in the plan.
7. Present the plan to the user. State coverage honestly: which ecosystems
   were detected, which lockfiles were read, which CVE scanners ran and which
   were absent.
8. Run the **apply loop** for PATCH-SAFE and MINOR-CHECK deps only (see Apply
   loop section below).
9. Print a session summary: N applied, M skipped, K advisory-only major(s),
   J CVE(s) requiring manual action.

## Four-group plan format

```
CVE-FLAGGED  (if any)
  <name>  <current> → <latest>  [CVE-XXXX-XXXX] <scanner> <advisory-url>

PATCH-SAFE
  <name>  <current> → <latest>  [cite]  [drifted from answers.toml: <baseline>]

MINOR-CHECK
  <name>  <current> → <latest>  [cite]

MAJOR-ADVISORY  (advisory only — never applied)
  <name>  <current> → <latest>  breaking: <summary>  [cite]
```

A dep with `installed == latest` is NOT included in the plan.

Pre-release versions (`rc`, `alpha`, `beta`, `a`, `b`, `.dev`) are excluded
from upgrade offers unless the current installed version is also pre-release.

## Apply loop (patch/minor only)

- Present each PATCH-SAFE and MINOR-CHECK dep in order, one at a time:
  ```
  name: old → new (PATCH|MINOR)  [cite]
  Apply? [Y/n]
  ```
- Default is Yes for both PATCH and MINOR. Show changelog cite for MINOR.
- On `Y`: run `scripts/apply.sh <ecosystem> <name> <new_version> [project-dir]`.
  After the script returns, re-read the manifest to confirm the new version is
  reflected. Warn if there is a post-apply version mismatch.
- On `n`: record as skipped, proceed to the next dep.
- **No global yes-to-all.** Every bump requires its own confirm.
- Rust and Go deps appear in the plan (advisory) but **never** enter the apply
  loop (FR-014).

### ruff pre-commit integration (FR-021)

If `ruff` is bumped in a Python project AND `.pre-commit-config.yaml` exists
AND a `rev:` under `astral-sh/ruff-pre-commit` is parseable, bundle the
pre-commit `rev` update with the ruff bump confirm:

```
ruff: 0.4.5 → 0.6.0 (MINOR)  [cite]
Also update .pre-commit-config.yaml astral-sh/ruff-pre-commit rev:? [Y/n]
```

If the pre-commit config is not parseable as YAML, print the manual change and
skip the bundled offer.

## Ecosystem → registry + package manager table

| Lockfile / manifest                                          | Ecosystem | Registry query (scripts/research.sh) | Apply command (scripts/apply.sh) |
|--------------------------------------------------------------|-----------|--------------------------------------|----------------------------------|
| `uv.lock` / `pyproject.toml` / `requirements.txt` / `poetry.lock` / `Pipfile.lock` | python | PyPI JSON: `pypi.org/pypi/<name>/json` | `uv add "name==ver"` |
| `pnpm-lock.yaml`                                            | node (pnpm) | npm registry: `registry.npmjs.org/<name>` | `pnpm update <name> --version <ver>` |
| `bun.lock` / `bun.lockb`                                    | node (bun)  | npm registry | `bun add "<name>@<ver>"` |
| `package-lock.json` / `npm-shrinkwrap.json`                 | node (npm)  | npm registry | `npm install "<name>@<ver>"` |
| `yarn.lock`                                                 | node (yarn) | npm registry | `yarn add "<name>@<ver>"` |
| `Cargo.lock` / `Cargo.toml`                                 | rust        | advisory only — no apply            | (advisory only) |
| `go.sum` / `go.mod`                                         | go          | advisory only — no apply            | (advisory only) |

Node package manager precedence (lockfile detection): `pnpm-lock.yaml` →
`bun.lock`/`bun.lockb` → `yarn.lock` → `package-lock.json`. If
`.project-setup/answers.toml` has a `package_manager` key in
`[module.lang-ts]`, that takes precedence over lockfile detection.

If the package manager binary is absent, `scripts/apply.sh` prints the manual
command and exits 0 (skip, not abort).

## CVE scanner dispatch

| Ecosystem | CVE scanner                         | Install hint                                    |
|-----------|-------------------------------------|-------------------------------------------------|
| python    | `pip-audit` / `uvx pip-audit`       | `pip install pip-audit`                         |
| node      | `pnpm audit` / `npm audit` / `yarn npm audit` | install via Node.js / Corepack          |
| rust      | `cargo audit`                       | `cargo install cargo-audit`                     |
| go        | `govulncheck`                       | `go install golang.org/x/vuln/cmd/govulncheck@latest` |
| any       | `osv-scanner` (supplemental)        | https://google.github.io/osv-scanner/            |

Each scanner is guarded with `command -v`. Missing → report as "scanner not
available: `<name>`" + install hint. Never install scanners; never imply clean.

## Binding rules

- **Majors are advisory-only, always.** MAJOR-ADVISORY deps are named,
  cited, and stopped. They never enter the apply loop, not even behind a
  confirm. The user must apply them manually.
- **Rust and Go are advisory-only.** `cargo update` and `go get` are deferred.
  They appear in the plan; they never enter the apply loop.
- **No global yes-to-all.** A batch-approve collapses safe and risky bumps.
  Every bump requires its own `[Y/n]`.
- **Never write `.project-setup/answers.toml` or `.project-setup/sources.toml`.**
  Those files are owned by the project-setup runner. This skill is a read-only
  consumer of the runner's outputs.
- **Never import the runner SDK (`sdk.py`).** Registry queries, semver
  classification, and TOML reads use stdlib only (`urllib`, `json`,
  `tomllib`/`tomli`). This keeps the skill's dependency surface identical to
  `dep-audit` and `whats-new`.
- **Honest coverage.** State which ecosystems were detected, which lockfiles
  were read, which CVE scanners ran, and which were absent. Do not imply clean
  when a scanner did not run.
- **Yanked PyPI versions are DISCONFIRMED.** If all published files for a
  candidate version are yanked on PyPI, `scripts/research.sh` marks it
  DISCONFIRMED and it is not offered as an upgrade target.
- **UNRESOLVABLE is not a failure.** A dep returning 404 / auth error / timeout
  is listed as UNRESOLVABLE with the reason and the skill continues. All-offline
  → "no registry access" report, zero writes, graceful exit.

## Semver classification rule

Given installed version `A.B.C` and candidate latest `X.Y.Z` (both normalized
to three-part numeric):

| Condition           | Class            |
|---------------------|------------------|
| `A==X, B==Y, C<Z`  | PATCH-SAFE        |
| `A==X, B<Y`        | MINOR-CHECK       |
| `A<X`              | MAJOR-ADVISORY    |
| `A==X, B==Y, C==Z` | (already current; omit) |

`research.sh` normalizes non-numeric pre-release suffixes and drops pre-release
candidates from the upgrade offer unless the installed version is also
pre-release.

## Install hints (for missing optional tools)

- `pip-audit`: `pip install pip-audit` (or run ad hoc with `uvx pip-audit`)
- `cargo audit`: `cargo install cargo-audit`
- `govulncheck`: `go install golang.org/x/vuln/cmd/govulncheck@latest`
- `osv-scanner`: https://google.github.io/osv-scanner/
- `npm` / `pnpm` / `yarn` / `bun`: install via Node.js / Corepack
- `uv`: https://docs.astral.sh/uv/getting-started/installation/
- `tomli` (Python < 3.11): `pip install tomli`

## Scripts

| Script            | Purpose                                                                                                       |
|-------------------|---------------------------------------------------------------------------------------------------------------|
| `scripts/detect.sh`   | Enumerate dependencies and lockfile-pinned versions by ecosystem, without network. Emits `ecosystem<TAB>name<TAB>version`. |
| `scripts/research.sh` | For each dep from detect, query PyPI / npm registry, classify the bump, emit JSON-lines records. Set `DEP_UPDATE_REGISTRY_OPENER=path` to stub the registry. |
| `scripts/apply.sh`    | Given `<ecosystem> <name> <new_version> [project-dir]`, run the appropriate package manager to apply the bump. Re-reads the manifest to verify. |

See `references/recipes.md` for the registry endpoints, per-ecosystem apply
commands, and the semver classification rule.
