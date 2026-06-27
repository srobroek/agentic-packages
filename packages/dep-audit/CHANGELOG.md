# Changelog

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
