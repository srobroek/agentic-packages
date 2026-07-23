# Changelog

## [2.1.1](https://github.com/srobroek/agentic-packages/compare/dep-update--v2.1.0...dep-update--v2.1.1) (2026-07-23)


### Bug Fixes

* script dependencies self-declare and agent contracts match reality ([#667](https://github.com/srobroek/agentic-packages/issues/667)) ([6e0f967](https://github.com/srobroek/agentic-packages/commit/6e0f96709f0f88b76461a750e9b46aa5045cede6))

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/dep-update--v2.0.0...dep-update--v2.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/dep-update--v1.0.0...dep-update--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering

### Features

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering ([9cb202d](https://github.com/srobroek/agentic-packages/commit/9cb202d2b76a649dda0489baaeefd61a2e0829e1))


### Bug Fixes

* **skills:** de-hedge and trim descriptions across 17 skill files ([49b5ffa](https://github.com/srobroek/agentic-packages/commit/49b5ffa1555f7f0c8fad6aa4ea6a53dbfaa6873f))

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
