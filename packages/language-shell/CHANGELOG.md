# Changelog

## [3.1.0](https://github.com/srobroek/agentic-packages/compare/language-shell--v3.0.4...language-shell--v3.1.0) (2026-08-17)


### Features

* **codex:** validate packages and standardize language tooling ([#856](https://github.com/srobroek/agentic-packages/issues/856)) ([42edbfb](https://github.com/srobroek/agentic-packages/commit/42edbfb3948c0103f3ce3ef5ba6819a08ae73566))

## [3.0.4](https://github.com/srobroek/agentic-packages/compare/language-shell--v3.0.3...language-shell--v3.0.4) (2026-08-17)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([2e89d20](https://github.com/srobroek/agentic-packages/commit/2e89d2093e420a321d4c5b97016ea464ae4c61ba))

## [3.0.3](https://github.com/srobroek/agentic-packages/compare/language-shell--v3.0.2...language-shell--v3.0.3) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [3.0.2](https://github.com/srobroek/agentic-packages/compare/language-shell--v3.0.1...language-shell--v3.0.2) (2026-07-25)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([6c55c29](https://github.com/srobroek/agentic-packages/commit/6c55c291106d03bdb7f5a2912a6a1aba76025c18))

## [3.0.1](https://github.com/srobroek/agentic-packages/compare/language-shell--v3.0.0...language-shell--v3.0.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/language-shell--v2.3.0...language-shell--v3.0.0) (2026-07-23)


### ⚠ BREAKING CHANGES

* the eleven bundle packages are removed. Anyone installing them must drop the dependency; no replacement is needed as the bundles provided no content beyond wshobson plugin passthroughs.

### Features

* drop bundled wshobson plugins and retire eleven empty bundles ([#671](https://github.com/srobroek/agentic-packages/issues/671)) ([6a3c4f9](https://github.com/srobroek/agentic-packages/commit/6a3c4f91a0ce805b0eb436cfd457d69670de4c42))

## [2.3.0](https://github.com/srobroek/agentic-packages/compare/language-shell--v2.2.1...language-shell--v2.3.0) (2026-07-23)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([#646](https://github.com/srobroek/agentic-packages/issues/646)) ([29f3dd0](https://github.com/srobroek/agentic-packages/commit/29f3dd0e10f84f9c740db515743cc057d83bbb4f))

## [2.2.1](https://github.com/srobroek/agentic-packages/compare/language-shell--v2.2.0...language-shell--v2.2.1) (2026-07-22)


### Bug Fixes

* prevent subagents from inheriting unintended models ([44f3d50](https://github.com/srobroek/agentic-packages/commit/44f3d501dfeb3ce2b645e53b5ddc77a63938fdb6))

## [2.2.0](https://github.com/srobroek/agentic-packages/compare/language-shell--v2.1.0...language-shell--v2.2.0) (2026-07-20)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([cec3d7c](https://github.com/srobroek/agentic-packages/commit/cec3d7c1026fb6cf532dea73ac02dcea62b01e1c))

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/language-shell--v2.0.1...language-shell--v2.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [2.0.1](https://github.com/srobroek/agentic-packages/compare/language-shell--v2.0.0...language-shell--v2.0.1) (2026-07-07)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([ea6b11c](https://github.com/srobroek/agentic-packages/commit/ea6b11c796f28c33dffe8700b1b675e5f02a5905))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/language-shell--v1.2.0...language-shell--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* pin all external #main refs to SHAs; internal subpath refs to semver ranges

### Chores

* pin all external #main refs to SHAs; internal subpath refs to semver ranges ([7b32fc1](https://github.com/srobroek/agentic-packages/commit/7b32fc13d3eb75710e7c40beb2d30672d0d9dc02))

## [1.2.0](https://github.com/srobroek/agentic-packages/compare/language-shell--v1.1.0...language-shell--v1.2.0) (2026-07-02)


### Features

* parallel-coder agent + per-language LSP packages ([#449](https://github.com/srobroek/agentic-packages/issues/449)) ([112c80d](https://github.com/srobroek/agentic-packages/commit/112c80d900549c81b72c065ac0c5556f74263f3f))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/language-shell-v1.0.0...language-shell--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/language-shell-v0.1.0...language-shell-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))


### Refactors

* tidy catalog metadata, dedup steering, fix dead tool references ([#375](https://github.com/srobroek/agentic-packages/issues/375)) ([2ed492c](https://github.com/srobroek/agentic-packages/commit/2ed492c632cf40a8c6cf269216e85021333d4db5))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/language-shell-v0.0.1...language-shell-v0.1.0) (2026-06-02)


### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* **packages:** add apm.yml to all skill/agent packages; drop category/tags from apm.yml [skip tests] ([722502e](https://github.com/srobroek/agentic-packages/commit/722502e84d74c7fa89d433294355355add2cd523))
* publish standalone mcp packages ([3145100](https://github.com/srobroek/agentic-packages/commit/31451002a7ae874e59c7f11868dd039ba597730c))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **bundles:** convert bundles to dependency-aggregator manifests [skip tests] ([615f549](https://github.com/srobroek/agentic-packages/commit/615f5493b15fb3e97231d0e1776bbef46cc86644))
* promote apm wrappers to packages ([bbe7484](https://github.com/srobroek/agentic-packages/commit/bbe748422b5f7dcc4ffbfe8354d21dc171c52add))
