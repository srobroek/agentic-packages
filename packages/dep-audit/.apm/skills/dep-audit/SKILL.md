---
name: dep-audit
description: Scan dependencies for CVEs using each ecosystem's native scanner and report findings by severity. Use when asked to audit dependencies or check for vulnerable packages.
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
3. Report findings grouped by severity. Name the package, the advisory/CVE id,
   and the affected and fixed version ranges where the scanner provides them.

## Ecosystem -> scanner mapping

Run `scripts/audit.sh --help` for the full lockfile-to-scanner mapping and
install hints. Each scanner is guarded with `command -v`; a missing scanner is
reported with an install hint, not treated as a failure.

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
