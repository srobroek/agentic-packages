# Changelog

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/dep-update--v0.1.0...dep-update--v1.0.0) (2026-06-29)


### ⚠ BREAKING CHANGES

* standalone, agent-driven project scaffolding with git-distributed add-on modules ([#418](https://github.com/srobroek/agentic-packages/issues/418))

### Features

* standalone, agent-driven project scaffolding with git-distributed add-on modules ([#418](https://github.com/srobroek/agentic-packages/issues/418)) ([318dc97](https://github.com/srobroek/agentic-packages/commit/318dc975d485dd04cf1903262b1227242204d482))

## 0.1.0

### Features

* Initial release: interactive dependency upgrade advisory skill. Detects
  ecosystems from lockfiles/manifests, queries PyPI and npm registries for
  current latest versions, classifies bumps as PATCH-SAFE / MINOR-CHECK /
  MAJOR-ADVISORY, surfaces CVEs via native scanners (pip-audit, npm/pnpm
  audit, osv-scanner), and applies patch and minor bumps one at a time behind
  a per-bump confirm. Major bumps are advisory-only and never applied. Reads
  `.project-setup/answers.toml` opportunistically; never writes it.
