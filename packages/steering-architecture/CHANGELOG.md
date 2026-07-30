# Changelog

## [2.1.4](https://github.com/srobroek/agentic-packages/compare/steering-architecture--v2.1.3...steering-architecture--v2.1.4) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [2.1.3](https://github.com/srobroek/agentic-packages/compare/steering-architecture--v2.1.2...steering-architecture--v2.1.3) (2026-07-27)


### Bug Fixes

* give every APM instruction an explicit applyTo, add drift guard ([#769](https://github.com/srobroek/agentic-packages/issues/769)) ([d983034](https://github.com/srobroek/agentic-packages/commit/d98303486d87b5dfb348a4a04fa435afa5fce692))

## [2.1.2](https://github.com/srobroek/agentic-packages/compare/steering-architecture--v2.1.1...steering-architecture--v2.1.2) (2026-07-25)


### Refactors

* cut duplicated rules from steering, agents and skills ([#728](https://github.com/srobroek/agentic-packages/issues/728)) ([8f892aa](https://github.com/srobroek/agentic-packages/commit/8f892aa01b3b0ffbb5888cca0dc4178d57ee967d))

## [2.1.1](https://github.com/srobroek/agentic-packages/compare/steering-architecture--v2.1.0...steering-architecture--v2.1.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/steering-architecture--v2.0.0...steering-architecture--v2.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/steering-architecture--v1.1.0...steering-architecture--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* **steering:** Wave 4 steering rewrites — pragmatic, code-economy, dedup, language compression, orchestrate fixes

### Features

* **steering:** Wave 4 steering rewrites — pragmatic, code-economy, dedup, language compression, orchestrate fixes ([1412eaf](https://github.com/srobroek/agentic-packages/commit/1412eafea2ec018655d73d353337feb918dd27f0))


### Refactors

* **steering:** dedup steering pairs and convert to delegate/table form ([8cebd5b](https://github.com/srobroek/agentic-packages/commit/8cebd5b4667ff0a9dfb2cf75e3c34a5d5c88120e))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/steering-architecture--v1.0.0...steering-architecture--v1.1.0) (2026-07-03)


### Features

* add steering-architecture package (compose over fork) ([#460](https://github.com/srobroek/agentic-packages/issues/460)) ([7b3a91f](https://github.com/srobroek/agentic-packages/commit/7b3a91fce332182ec0efa3111edb511216bd3a7e))

## 1.0.0

### Features

- **steering-architecture:** New opt-in steering package: compose-don't-fork
  as a cross-cutting, language-agnostic design principle. Extend existing
  subsystems through their seams instead of copying, branching, or
  re-implementing them into a variant; keep dispatch/registry/core layers
  case-agnostic; state structural invariants as a verifiable (near-empty)
  diff to the shared surface. Also documents when forking is the honest
  choice.
