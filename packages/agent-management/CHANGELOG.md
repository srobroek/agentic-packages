# Changelog

## [1.2.5](https://github.com/srobroek/agentic-packages/compare/agent-management--v1.2.4...agent-management--v1.2.5) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [1.2.4](https://github.com/srobroek/agentic-packages/compare/agent-management--v1.2.3...agent-management--v1.2.4) (2026-07-27)


### Bug Fixes

* **agent-management:** run the global scripts through uv, not a shadowed python3 ([#786](https://github.com/srobroek/agentic-packages/issues/786)) ([a264e1f](https://github.com/srobroek/agentic-packages/commit/a264e1f2341f2cdb0e092f6b430782b1c1ceece5))

## [1.2.3](https://github.com/srobroek/agentic-packages/compare/agent-management--v1.2.2...agent-management--v1.2.3) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))


### Refactors

* move guidance into the scripts and contracts that enforce it ([#726](https://github.com/srobroek/agentic-packages/issues/726)) ([40bcfdf](https://github.com/srobroek/agentic-packages/commit/40bcfdf27cd6bbf72db02ce143482eac91d4a4cc))

## [1.2.2](https://github.com/srobroek/agentic-packages/compare/agent-management--v1.2.1...agent-management--v1.2.2) (2026-07-23)


### Bug Fixes

* **inject-agent-models:** tolerate identical duplicate mappings across packages ([#669](https://github.com/srobroek/agentic-packages/issues/669)) ([c2eda86](https://github.com/srobroek/agentic-packages/commit/c2eda860c2caf85c5645b323779f5c669a8adaf2))
* script dependencies self-declare and agent contracts match reality ([#667](https://github.com/srobroek/agentic-packages/issues/667)) ([6e0f967](https://github.com/srobroek/agentic-packages/commit/6e0f96709f0f88b76461a750e9b46aa5045cede6))

## [1.2.1](https://github.com/srobroek/agentic-packages/compare/agent-management--v1.2.0...agent-management--v1.2.1) (2026-07-22)


### Bug Fixes

* prevent subagents from inheriting unintended models ([44f3d50](https://github.com/srobroek/agentic-packages/commit/44f3d501dfeb3ce2b645e53b5ddc77a63938fdb6))

## [1.2.0](https://github.com/srobroek/agentic-packages/compare/agent-management--v1.1.1...agent-management--v1.2.0) (2026-07-21)


### Features

* **agent-management:** compile global root contexts safely ([659b663](https://github.com/srobroek/agentic-packages/commit/659b663f6b5d3f0676348a2dba7e0872b07eb85a))

## [1.1.1](https://github.com/srobroek/agentic-packages/compare/agent-management--v1.1.0...agent-management--v1.1.1) (2026-07-21)


### Bug Fixes

* **agent-management:** distribute agent model injector ([#582](https://github.com/srobroek/agentic-packages/issues/582)) ([cd63272](https://github.com/srobroek/agentic-packages/commit/cd6327260d47012962795206f0be3a1bcd4b3475))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/agent-management--v1.0.0...agent-management--v1.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/agent-management--v0.2.0...agent-management--v1.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering

### Features

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering ([9cb202d](https://github.com/srobroek/agentic-packages/commit/9cb202d2b76a649dda0489baaeefd61a2e0829e1))


### Refactors

* **audit-steering:** absorb project-hygiene + optimize-steering; delete both packages ([2d4426e](https://github.com/srobroek/agentic-packages/commit/2d4426ecd3316c450d09f93eae7f958bf25bf1e2))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/agent-management-v0.1.1...agent-management--v0.2.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [0.1.1](https://github.com/srobroek/agentic-packages/compare/agent-management-v0.1.0...agent-management-v0.1.1) (2026-06-26)


### Refactors

* split core-global into independently installable packages ([#380](https://github.com/srobroek/agentic-packages/issues/380)) ([36f9470](https://github.com/srobroek/agentic-packages/commit/36f9470fc50a7ff5af2c7dd943a817a1d9808247))

## 0.1.0

### Features

* Initial `agent-management` skill package, extracted from the `core-global`
  bundle so it can be installed independently.
