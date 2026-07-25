# Changelog

## [4.0.1](https://github.com/srobroek/agentic-packages/compare/dependency-quality--v4.0.0...dependency-quality--v4.0.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [4.0.0](https://github.com/srobroek/agentic-packages/compare/dependency-quality--v3.2.0...dependency-quality--v4.0.0) (2026-07-21)


### ⚠ BREAKING CHANGES

* share MCP backends through 1MCP

### Features

* share MCP backends through 1MCP ([4896601](https://github.com/srobroek/agentic-packages/commit/4896601ca0326762493f340526a97a341b98e24a))

## [3.2.0](https://github.com/srobroek/agentic-packages/compare/dependency-quality--v3.1.0...dependency-quality--v3.2.0) (2026-07-20)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([cec3d7c](https://github.com/srobroek/agentic-packages/commit/cec3d7c1026fb6cf532dea73ac02dcea62b01e1c))

## [3.1.0](https://github.com/srobroek/agentic-packages/compare/dependency-quality--v3.0.0...dependency-quality--v3.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/dependency-quality--v2.0.0...dependency-quality--v3.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* **deps:** sync internal package pins (major-level dep releases)

### Features

* **deps:** sync internal package pins (major-level dep releases) ([0bdb7ce](https://github.com/srobroek/agentic-packages/commit/0bdb7ceae8bbd763f64baa26b9d7647863e1c3fc))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/dependency-quality--v1.1.2...dependency-quality--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* the removed packages are no longer published; installs referencing them must update to core >=7 bundles.

### Features

* retire 13 nudge/duplicate packages in favor of static steering ([a2fc229](https://github.com/srobroek/agentic-packages/commit/a2fc229311e85435af1ba9ff1c172016f611436e))

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
