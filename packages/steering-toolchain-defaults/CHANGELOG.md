# Changelog

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
