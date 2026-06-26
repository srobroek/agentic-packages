---
name: dep-audit
description: Scan the project's dependencies for known CVEs using each ecosystem's native vulnerability scanner and report findings by severity. Use when the user asks to audit dependencies, check for vulnerable packages, run a CVE scan, or do a supply-chain / dependency security check. Read-only; never auto-fixes.
---

# Dependency CVE Audit

On-demand (model-invoked) skill. Detect which package ecosystem(s) the project
uses from its lockfiles/manifests, run the matching native vulnerability
scanner for each, and report known CVEs grouped by severity. This skill is
read-only: it reports, it never upgrades, pins, or auto-fixes anything.

## When to use

Triggers: "audit dependencies", "check for vulnerable packages", "CVE scan",
"supply chain check", "are any of our deps vulnerable", "dependency security
review".

## Preferred flow

1. Prefer the project's own audit task if one obviously exists (`just audit`,
   a `package.json` `audit` script, a documented security target).
2. Otherwise run `scripts/audit.sh` from the project root. It detects the
   ecosystem(s), dispatches to each available scanner, prints each scanner's
   output, and ends with a summary.
3. Read the summary: it lists ecosystems detected, scanners that ran, scanners
   that were unavailable (with install hints), and the HIGH/CRITICAL count.
4. Report findings to the user grouped by severity. Lead with CRITICAL/HIGH,
   then MEDIUM/LOW. Name the package, the advisory/CVE id, the affected and
   fixed version ranges where the scanner provides them.
5. Be explicit about coverage: state which ecosystems were scanned, and which
   were detected but skipped because the scanner was not installed. Do not
   imply an ecosystem is clean when its scanner never ran.

## Ecosystem -> scanner mapping

| Lockfile / manifest                         | Scanner                          |
|---------------------------------------------|----------------------------------|
| `pnpm-lock.yaml`                            | `pnpm audit`                     |
| `package-lock.json` / `npm-shrinkwrap.json` | `npm audit`                      |
| `yarn.lock`                                 | `yarn npm audit` (or `npm audit`)|
| `poetry.lock` / `uv.lock` / `Pipfile.lock` / `requirements.txt` / `pyproject.toml` | `pip-audit` (or `uvx pip-audit`) |
| `Cargo.lock` / `Cargo.toml`                 | `cargo audit`                    |
| `go.mod`                                    | `govulncheck ./...`              |
| any of the above (cross-ecosystem)          | `osv-scanner` (supplemental)     |

Each scanner is guarded with `command -v`. A missing scanner is reported with
an install hint, not treated as a failure.

## Install hints (only if a scanner is missing)

- `pip-audit`: `pip install pip-audit` (or run ad hoc with `uvx pip-audit`)
- `cargo audit`: `cargo install cargo-audit`
- `govulncheck`: `go install golang.org/x/vuln/cmd/govulncheck@latest`
- `osv-scanner`: https://google.github.io/osv-scanner/
- `npm` / `pnpm` / `yarn`: install via Node.js / Corepack

## Steering

- Never auto-fix, upgrade, or pin. Report and let the human decide.
- Never claim an ecosystem is vulnerability-free if its scanner did not run.
- A bare `package.json` with no lockfile cannot be audited by `npm audit`;
  say so and suggest installing dependencies first.
- `govulncheck` has no severity tiers and only reports vulnerabilities that
  are actually reachable from the code; treat any finding as gating.
- `scripts/audit.sh` exits non-zero only when a HIGH/CRITICAL match is found,
  so it can gate CI. A clean run, an empty project, or "scanners unavailable"
  all exit 0 -- read the summary to distinguish them.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/audit.sh` | Detect ecosystem(s) by lockfile and run each available scanner; summarize and gate on HIGH/CRITICAL. Optional arg: project dir (default `.`). |
