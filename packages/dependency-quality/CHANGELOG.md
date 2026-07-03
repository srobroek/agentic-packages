# Changelog

## [1.1.2](https://github.com/srobroek/agentic-packages/compare/dependency-quality--v1.1.1...dependency-quality--v1.1.2) (2026-07-03)


### Bug Fixes

* **deps:** sync internal package pins to released versions ([#466](https://github.com/srobroek/agentic-packages/issues/466)) ([d252bf8](https://github.com/srobroek/agentic-packages/commit/d252bf8604c34e6887ca95426d35026f18fca05f))

## [1.1.1](https://github.com/srobroek/agentic-packages/compare/dependency-quality--v1.1.0...dependency-quality--v1.1.1) (2026-06-29)


### Bug Fixes

* **build-native-plugins:** emit parseable {git,path} bundle deps ([#417](https://github.com/srobroek/agentic-packages/issues/417)) ([8bd39d4](https://github.com/srobroek/agentic-packages/commit/8bd39d47a8f03a7f162849099844ae332f858105))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/dependency-quality-v1.0.0...dependency-quality--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/dependency-quality-v0.1.0...dependency-quality-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* mcp-package-version no longer ships the package-file-warn or pkg-version-warn hooks. Installers that relied on those hooks should install hooks-package-file-guard / hooks-pkg-version-warn (or the dependency-quality bundle) instead.

### Features

* split dependency tooling into independent packages + dependency-quality bundle ([#370](https://github.com/srobroek/agentic-packages/issues/370)) ([03d50a5](https://github.com/srobroek/agentic-packages/commit/03d50a5db3a1572fbe36a4ac1bc1e6877cd96ade))

## 0.1.0

### Features

* Initial `dependency-quality` bundle aggregating the independently-installable
  dependency-hygiene components: `hooks-package-file-guard` (warn on direct
  manifest edits), `hooks-package-investigate` (investigate a dependency before
  adding), `hooks-pkg-version-warn` (install latest compatible version),
  `dep-audit` (CVE scanning), and `mcp-package-version` (version-discovery MCP
  server). Install the bundle for the full surface, or any component on its own.
