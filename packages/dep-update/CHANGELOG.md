# Changelog

## 0.1.0

### Features

* Initial release: interactive dependency upgrade advisory skill. Detects
  ecosystems from lockfiles/manifests, queries PyPI and npm registries for
  current latest versions, classifies bumps as PATCH-SAFE / MINOR-CHECK /
  MAJOR-ADVISORY, surfaces CVEs via native scanners (pip-audit, npm/pnpm
  audit, osv-scanner), and applies patch and minor bumps one at a time behind
  a per-bump confirm. Major bumps are advisory-only and never applied. Reads
  `.project-setup/answers.toml` opportunistically; never writes it.
