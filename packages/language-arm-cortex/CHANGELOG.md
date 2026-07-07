# Changelog

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/language-arm-cortex--v1.1.0...language-arm-cortex--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* pin all external #main refs to SHAs; internal subpath refs to semver ranges

### Chores

* pin all external #main refs to SHAs; internal subpath refs to semver ranges ([7b32fc1](https://github.com/srobroek/agentic-packages/commit/7b32fc13d3eb75710e7c40beb2d30672d0d9dc02))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/language-arm-cortex-v1.0.0...language-arm-cortex--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/language-arm-cortex-v0.1.0...language-arm-cortex-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))


### Refactors

* tidy catalog metadata, dedup steering, fix dead tool references ([#375](https://github.com/srobroek/agentic-packages/issues/375)) ([2ed492c](https://github.com/srobroek/agentic-packages/commit/2ed492c632cf40a8c6cf269216e85021333d4db5))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/language-arm-cortex-v0.0.1...language-arm-cortex-v0.1.0) (2026-06-02)


### Features

* incorporate msitarzewski/agency-agents as opt-in marketplace entries ([7d6ed5b](https://github.com/srobroek/agentic-packages/commit/7d6ed5b713854d0e4c8e291f23664170c89b78a1))
* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* **packages:** add apm.yml to all skill/agent packages; drop category/tags from apm.yml [skip tests] ([722502e](https://github.com/srobroek/agentic-packages/commit/722502e84d74c7fa89d433294355355add2cd523))
* publish standalone mcp packages ([3145100](https://github.com/srobroek/agentic-packages/commit/31451002a7ae874e59c7f11868dd039ba597730c))


### Bug Fixes

* remove invalid msitarzewski/agency-agents dependencies from 15 packages [skip tests] ([f1c97c5](https://github.com/srobroek/agentic-packages/commit/f1c97c5c3203fc87e54c3a9ca615ad7abb783d34))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **bundles:** convert bundles to dependency-aggregator manifests [skip tests] ([615f549](https://github.com/srobroek/agentic-packages/commit/615f5493b15fb3e97231d0e1776bbef46cc86644))
* promote apm wrappers to packages ([bbe7484](https://github.com/srobroek/agentic-packages/commit/bbe748422b5f7dcc4ffbfe8354d21dc171c52add))
