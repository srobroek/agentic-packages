---
description: Security scanning tool routing and CLI patterns
applyTo: "**/*"
---

## Security Scanning Priority

1. **semgrep** (CLI) — AST-based vulnerability detection with 5000+ rules.
   `semgrep scan --config auto .` for full scan.
   `semgrep scan --config auto path/to/file.ts` for targeted scan.
   Use for: injection flaws, auth issues, crypto misuse, secrets, OWASP top 10.

2. **trivy** (CLI) — comprehensive vulnerability scanner.
   `trivy fs .` for local filesystem (deps + IaC).
   `trivy image <name>` for container images.
   Use for: dependency vulnerabilities, Dockerfile issues, Terraform/CloudFormation misconfig.

3. **Language-specific audits** (CLI):
   - `npm audit` / `yarn audit` — Node.js dependencies
   - `pip-audit` — Python dependencies
   - `cargo audit` — Rust dependencies
   - `bundler-audit` — Ruby dependencies

## When to Run

- Before committing security-sensitive changes: run semgrep on affected files
- Before merging: run trivy for dependency and IaC checks
- On new dependencies: run language-specific audit
