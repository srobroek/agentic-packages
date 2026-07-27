# Changelog

## [3.0.1](https://github.com/srobroek/agentic-packages/compare/steering-toolchain-defaults--v3.0.0...steering-toolchain-defaults--v3.0.1) (2026-07-27)


### Bug Fixes

* give every APM instruction an explicit applyTo, add drift guard ([#769](https://github.com/srobroek/agentic-packages/issues/769)) ([d983034](https://github.com/srobroek/agentic-packages/commit/d98303486d87b5dfb348a4a04fa435afa5fce692))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/steering-toolchain-defaults--v2.1.2...steering-toolchain-defaults--v3.0.0) (2026-07-25)


### ⚠ BREAKING CHANGES

* remove mcp-gitnexus and three redundant language-steering packages ([#727](https://github.com/srobroek/agentic-packages/issues/727))

### Chores

* remove mcp-gitnexus and three redundant language-steering packages ([#727](https://github.com/srobroek/agentic-packages/issues/727)) ([11fc470](https://github.com/srobroek/agentic-packages/commit/11fc470dcb3a3a6a840f19d19b1f31c54c77eeb1))

## [2.1.2](https://github.com/srobroek/agentic-packages/compare/steering-toolchain-defaults--v2.1.1...steering-toolchain-defaults--v2.1.2) (2026-07-25)


### Refactors

* cut duplicated rules from steering, agents and skills ([#728](https://github.com/srobroek/agentic-packages/issues/728)) ([8f892aa](https://github.com/srobroek/agentic-packages/commit/8f892aa01b3b0ffbb5888cca0dc4178d57ee967d))

## [2.1.1](https://github.com/srobroek/agentic-packages/compare/steering-toolchain-defaults--v2.1.0...steering-toolchain-defaults--v2.1.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))


### Refactors

* move guidance into the scripts and contracts that enforce it ([#726](https://github.com/srobroek/agentic-packages/issues/726)) ([40bcfdf](https://github.com/srobroek/agentic-packages/commit/40bcfdf27cd6bbf72db02ce143482eac91d4a4cc))

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/steering-toolchain-defaults--v2.0.0...steering-toolchain-defaults--v2.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/steering-toolchain-defaults-v1.0.0...steering-toolchain-defaults--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* the removed packages are no longer published; installs referencing them must update to core >=7 bundles.

### Features

* retire 13 nudge/duplicate packages in favor of static steering ([a2fc229](https://github.com/srobroek/agentic-packages/commit/a2fc229311e85435af1ba9ff1c172016f611436e))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/steering-toolchain-defaults-v0.1.1...steering-toolchain-defaults-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))

## [0.1.1](https://github.com/srobroek/agentic-packages/compare/steering-toolchain-defaults-v0.1.0...steering-toolchain-defaults-v0.1.1) (2026-06-12)


### Bug Fixes

* **steering-toolchain-defaults:** handoff note to steering-frontend ([#298](https://github.com/srobroek/agentic-packages/issues/298)) ([2264dfa](https://github.com/srobroek/agentic-packages/commit/2264dfa459fc755e6f281326a4e876514b550be2))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/steering-toolchain-defaults-v0.0.1...steering-toolchain-defaults-v0.1.0) (2026-06-02)


### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **steering:** split baseline into 3 opt-in packages; extract speckit hooks [skip tests] ([9a19504](https://github.com/srobroek/agentic-packages/commit/9a195043c208f8d03d462507a2720d66e7addc2c))
