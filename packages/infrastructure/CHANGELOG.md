# Changelog

## [4.1.0](https://github.com/srobroek/agentic-packages/compare/infrastructure--v4.0.4...infrastructure--v4.1.0) (2026-08-17)


### Features

* **codex:** validate packages and standardize language tooling ([#856](https://github.com/srobroek/agentic-packages/issues/856)) ([42edbfb](https://github.com/srobroek/agentic-packages/commit/42edbfb3948c0103f3ce3ef5ba6819a08ae73566))

## [4.0.4](https://github.com/srobroek/agentic-packages/compare/infrastructure--v4.0.3...infrastructure--v4.0.4) (2026-08-17)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([2e89d20](https://github.com/srobroek/agentic-packages/commit/2e89d2093e420a321d4c5b97016ea464ae4c61ba))

## [4.0.3](https://github.com/srobroek/agentic-packages/compare/infrastructure--v4.0.2...infrastructure--v4.0.3) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [4.0.2](https://github.com/srobroek/agentic-packages/compare/infrastructure--v4.0.1...infrastructure--v4.0.2) (2026-07-25)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([6c55c29](https://github.com/srobroek/agentic-packages/commit/6c55c291106d03bdb7f5a2912a6a1aba76025c18))

## [4.0.1](https://github.com/srobroek/agentic-packages/compare/infrastructure--v4.0.0...infrastructure--v4.0.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [4.0.0](https://github.com/srobroek/agentic-packages/compare/infrastructure--v3.2.0...infrastructure--v4.0.0) (2026-07-23)


### ⚠ BREAKING CHANGES

* the eleven bundle packages are removed. Anyone installing them must drop the dependency; no replacement is needed as the bundles provided no content beyond wshobson plugin passthroughs.

### Features

* drop bundled wshobson plugins and retire eleven empty bundles ([#671](https://github.com/srobroek/agentic-packages/issues/671)) ([6a3c4f9](https://github.com/srobroek/agentic-packages/commit/6a3c4f91a0ce805b0eb436cfd457d69670de4c42))

## [3.2.0](https://github.com/srobroek/agentic-packages/compare/infrastructure--v3.1.0...infrastructure--v3.2.0) (2026-07-20)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([cec3d7c](https://github.com/srobroek/agentic-packages/commit/cec3d7c1026fb6cf532dea73ac02dcea62b01e1c))

## [3.1.0](https://github.com/srobroek/agentic-packages/compare/infrastructure--v3.0.0...infrastructure--v3.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/infrastructure--v2.0.0...infrastructure--v3.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* **deps:** sync internal package pins (major-level dep releases)

### Features

* **deps:** sync internal package pins (major-level dep releases) ([0bdb7ce](https://github.com/srobroek/agentic-packages/commit/0bdb7ceae8bbd763f64baa26b9d7647863e1c3fc))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/infrastructure--v1.1.2...infrastructure--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* pin all external #main refs to SHAs; internal subpath refs to semver ranges

### Chores

* pin all external #main refs to SHAs; internal subpath refs to semver ranges ([7b32fc1](https://github.com/srobroek/agentic-packages/commit/7b32fc13d3eb75710e7c40beb2d30672d0d9dc02))

## [1.1.2](https://github.com/srobroek/agentic-packages/compare/infrastructure--v1.1.1...infrastructure--v1.1.2) (2026-07-03)


### Bug Fixes

* **deps:** sync internal package pins to released versions ([#466](https://github.com/srobroek/agentic-packages/issues/466)) ([d252bf8](https://github.com/srobroek/agentic-packages/commit/d252bf8604c34e6887ca95426d35026f18fca05f))

## [1.1.1](https://github.com/srobroek/agentic-packages/compare/infrastructure--v1.1.0...infrastructure--v1.1.1) (2026-06-29)


### Bug Fixes

* **build-native-plugins:** emit parseable {git,path} bundle deps ([#417](https://github.com/srobroek/agentic-packages/issues/417)) ([8bd39d4](https://github.com/srobroek/agentic-packages/commit/8bd39d47a8f03a7f162849099844ae332f858105))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/infrastructure-v1.0.0...infrastructure--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/infrastructure-v0.2.0...infrastructure-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/infrastructure-v0.1.0...infrastructure-v0.2.0) (2026-06-20)


### Features

* adopt apm 0.21 semver ranges, sub-bundle core, add kiro target ([#341](https://github.com/srobroek/agentic-packages/issues/341)) ([d033e88](https://github.com/srobroek/agentic-packages/commit/d033e88fee643b036498c1edccc4ba50af742659))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/infrastructure-v0.0.1...infrastructure-v0.1.0) (2026-06-02)


### Features

* incorporate msitarzewski/agency-agents as opt-in marketplace entries ([7d6ed5b](https://github.com/srobroek/agentic-packages/commit/7d6ed5b713854d0e4c8e291f23664170c89b78a1))
* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* **packages:** add apm.yml to all skill/agent packages; drop category/tags from apm.yml [skip tests] ([722502e](https://github.com/srobroek/agentic-packages/commit/722502e84d74c7fa89d433294355355add2cd523))
* publish standalone mcp packages ([3145100](https://github.com/srobroek/agentic-packages/commit/31451002a7ae874e59c7f11868dd039ba597730c))


### Bug Fixes

* remove invalid msitarzewski/agency-agents dependencies from 15 packages [skip tests] ([f1c97c5](https://github.com/srobroek/agentic-packages/commit/f1c97c5c3203fc87e54c3a9ca615ad7abb783d34))
* use valid repo-locator dependency syntax for bundle members [skip tests] ([855d9d6](https://github.com/srobroek/agentic-packages/commit/855d9d67b2e6c93e9dd1b603fd7cf958e172682a))
* valid repo-locator dependency syntax for bundle members ([c4be60c](https://github.com/srobroek/agentic-packages/commit/c4be60cf8308c21be297b9fcf2381b3e6687ac61))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **bundles:** convert bundles to dependency-aggregator manifests [skip tests] ([615f549](https://github.com/srobroek/agentic-packages/commit/615f5493b15fb3e97231d0e1776bbef46cc86644))
* promote apm wrappers to packages ([bbe7484](https://github.com/srobroek/agentic-packages/commit/bbe748422b5f7dcc4ffbfe8354d21dc171c52add))
