# Changelog

## [1.2.1](https://github.com/srobroek/agentic-packages/compare/mcp-package-version--v1.2.0...mcp-package-version--v1.2.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [1.2.0](https://github.com/srobroek/agentic-packages/compare/mcp-package-version--v1.1.0...mcp-package-version--v1.2.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/mcp-package-version-v1.0.0...mcp-package-version--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/mcp-package-version-v0.2.0...mcp-package-version-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* mcp-package-version no longer ships the package-file-warn or pkg-version-warn hooks. Installers that relied on those hooks should install hooks-package-file-guard / hooks-pkg-version-warn (or the dependency-quality bundle) instead.
* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* **packages:** add apm.yml to all skill/agent packages; drop category/tags from apm.yml [skip tests] ([722502e](https://github.com/srobroek/agentic-packages/commit/722502e84d74c7fa89d433294355355add2cd523))
* publish standalone mcp packages ([3145100](https://github.com/srobroek/agentic-packages/commit/31451002a7ae874e59c7f11868dd039ba597730c))
* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))
* split dependency tooling into independent packages + dependency-quality bundle ([#370](https://github.com/srobroek/agentic-packages/issues/370)) ([03d50a5](https://github.com/srobroek/agentic-packages/commit/03d50a5db3a1572fbe36a4ac1bc1e6877cd96ade))


### Bug Fixes

* **mcp-package-version:** emit JSON hook output the model can see ([#285](https://github.com/srobroek/agentic-packages/issues/285)) ([be2eda0](https://github.com/srobroek/agentic-packages/commit/be2eda059639e64df972f1c4a5be6706b1de0455))
* **phase-1:** guard bypasses, bash-3.2/BSD portability, crashes, bundle pins + tests ([#360](https://github.com/srobroek/agentic-packages/issues/360)) ([b0c9106](https://github.com/srobroek/agentic-packages/commit/b0c91064313282a4265b9b0b8fb779f00afecd90))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **bundles:** convert bundles to dependency-aggregator manifests [skip tests] ([615f549](https://github.com/srobroek/agentic-packages/commit/615f5493b15fb3e97231d0e1776bbef46cc86644))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/mcp-package-version-v0.1.1...mcp-package-version-v0.2.0) (2026-06-25)


### ⚠ BREAKING CHANGES

* **mcp-package-version:** split advisory hooks out into standalone hook packages. This package now ships only the package-version MCP server registration. The `package-file-warn.sh` and `pkg-version-warn.sh` PreToolUse hooks (and the `.apm/hooks` JSON wiring) have been removed and are now provided by their own independent hook packages. Installations relying on this package for the file/version advisory hooks must add the new hook packages.

## [0.1.1](https://github.com/srobroek/agentic-packages/compare/mcp-package-version-v0.1.0...mcp-package-version-v0.1.1) (2026-06-12)


### Bug Fixes

* **mcp-package-version:** emit JSON hook output the model can see ([#285](https://github.com/srobroek/agentic-packages/issues/285)) ([be2eda0](https://github.com/srobroek/agentic-packages/commit/be2eda059639e64df972f1c4a5be6706b1de0455))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/mcp-package-version-v0.0.1...mcp-package-version-v0.1.0) (2026-06-02)


### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* **packages:** add apm.yml to all skill/agent packages; drop category/tags from apm.yml [skip tests] ([722502e](https://github.com/srobroek/agentic-packages/commit/722502e84d74c7fa89d433294355355add2cd523))
* publish standalone mcp packages ([3145100](https://github.com/srobroek/agentic-packages/commit/31451002a7ae874e59c7f11868dd039ba597730c))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **bundles:** convert bundles to dependency-aggregator manifests [skip tests] ([615f549](https://github.com/srobroek/agentic-packages/commit/615f5493b15fb3e97231d0e1776bbef46cc86644))
