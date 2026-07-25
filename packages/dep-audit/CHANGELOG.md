# Changelog

## [2.1.1](https://github.com/srobroek/agentic-packages/compare/dep-audit--v2.1.0...dep-audit--v2.1.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))


### Refactors

* move guidance into the scripts and contracts that enforce it ([#726](https://github.com/srobroek/agentic-packages/issues/726)) ([40bcfdf](https://github.com/srobroek/agentic-packages/commit/40bcfdf27cd6bbf72db02ce143482eac91d4a4cc))

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/dep-audit--v2.0.0...dep-audit--v2.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/dep-audit--v1.1.0...dep-audit--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering

### Features

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering ([9cb202d](https://github.com/srobroek/agentic-packages/commit/9cb202d2b76a649dda0489baaeefd61a2e0829e1))


### Bug Fixes

* **skills:** de-hedge and trim descriptions across 17 skill files ([49b5ffa](https://github.com/srobroek/agentic-packages/commit/49b5ffa1555f7f0c8fad6aa4ea6a53dbfaa6873f))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/dep-audit-v1.0.0...dep-audit--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/dep-audit-v0.1.0...dep-audit-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* mcp-package-version no longer ships the package-file-warn or pkg-version-warn hooks. Installers that relied on those hooks should install hooks-package-file-guard / hooks-pkg-version-warn (or the dependency-quality bundle) instead.

### Features

* split dependency tooling into independent packages + dependency-quality bundle ([#370](https://github.com/srobroek/agentic-packages/issues/370)) ([03d50a5](https://github.com/srobroek/agentic-packages/commit/03d50a5db3a1572fbe36a4ac1bc1e6877cd96ade))


### Bug Fixes

* co-locate skill scripts so they resolve after install ([#376](https://github.com/srobroek/agentic-packages/issues/376)) ([1bb71cc](https://github.com/srobroek/agentic-packages/commit/1bb71ccac2ac14992506bddf11f0ae0ff5db5d0d))

## 0.1.0

### Features

* Initial release: on-demand dependency CVE scanner skill. Detects the
  ecosystem(s) present from lockfiles/manifests and dispatches to the native
  scanner for each (npm/pnpm audit, pip-audit, cargo audit, govulncheck,
  osv-scanner), guarding every scanner with `command -v`. Reports which
  scanners ran versus were unavailable (with install hints) and never
  auto-fixes. `scripts/audit.sh` exits non-zero when any HIGH/CRITICAL
  vulnerability is found so it can gate CI.
