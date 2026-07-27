# Changelog

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/write-docs--v2.0.0...write-docs--v3.0.0) (2026-07-27)


### ⚠ BREAKING CHANGES

* **agents:** `agent-coder` is now `agent-builder` and `agent-coder-high` is `agent-builder-high`. The agents `parallel-builder`, `worker`, `coder-high`, `domain-specialist-medium` and `domain-specialist-xhigh` no longer exist; use `builder` with an explicit mode, `builder-high`, or `domain-specialist{,-high}`. Spawn calls naming a removed agent must be updated.

### Bug Fixes

* **agents:** pin every agent to a model, collapse duplicate tiers ([#771](https://github.com/srobroek/agentic-packages/issues/771)) ([fd8193f](https://github.com/srobroek/agentic-packages/commit/fd8193f6e1f8fb7a4bfcb889e24f4ccd5327a7f7))
* give every APM instruction an explicit applyTo, add drift guard ([#769](https://github.com/srobroek/agentic-packages/issues/769)) ([d983034](https://github.com/srobroek/agentic-packages/commit/d98303486d87b5dfb348a4a04fa435afa5fce692))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/write-docs--v1.2.2...write-docs--v2.0.0) (2026-07-25)


### ⚠ BREAKING CHANGES

* **write-docs:** requires the vale binary on PATH (mise use -g vale, or brew install vale). Suppression syntax changes from <!-- write-docs:allow E2 --> to Vale's <!-- vale WriteDocs.SlopLexicon = NO --> off/on pairs, which are block-scoped rather than line-scoped.

### Features

* **write-docs:** check documentation prose with Vale instead of a bespoke linter ([#721](https://github.com/srobroek/agentic-packages/issues/721)) ([43fc7f7](https://github.com/srobroek/agentic-packages/commit/43fc7f766c6f4a9c6317a71f18ba33ff3fbf507c))


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [1.2.2](https://github.com/srobroek/agentic-packages/compare/write-docs--v1.2.1...write-docs--v1.2.2) (2026-07-22)


### Bug Fixes

* keep package artifacts stable after tests ([#629](https://github.com/srobroek/agentic-packages/issues/629)) ([f3fec83](https://github.com/srobroek/agentic-packages/commit/f3fec8320f69d1e719fa051473055a2e6e7e43fc))

## [1.2.1](https://github.com/srobroek/agentic-packages/compare/write-docs--v1.2.0...write-docs--v1.2.1) (2026-07-20)


### Documentation

* **write-docs:** add ai-tells reference with progressive-disclosure pointers ([#545](https://github.com/srobroek/agentic-packages/issues/545)) ([64e4a5b](https://github.com/srobroek/agentic-packages/commit/64e4a5bbe019026bd6c51cd2bf37db00d7ded56d))
* **write-docs:** modernize ai-tells for current model generations ([#546](https://github.com/srobroek/agentic-packages/issues/546)) ([ad2f925](https://github.com/srobroek/agentic-packages/commit/ad2f925eac6ff5e8f6ed6f0bc5075e2fc41729fe))

## [1.2.0](https://github.com/srobroek/agentic-packages/compare/write-docs--v1.1.0...write-docs--v1.2.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/write-docs--v1.0.0...write-docs--v1.1.0) (2026-07-12)


### Features

* **write-docs:** trigger on buried doc tasks + SubagentStart discipline hook ([#526](https://github.com/srobroek/agentic-packages/issues/526)) ([965587f](https://github.com/srobroek/agentic-packages/commit/965587f909a73e92c743a95f619a5d237c94c93a))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/write-docs--v0.1.0...write-docs--v1.0.0) (2026-07-11)


### ⚠ BREAKING CHANGES

* docs-specs.project-docs.context.md is removed; installs relying on markdown-wide doc-style steering must add the write-docs package.

### Features

* write-docs skill for slop-free, release-focused documentation ([#522](https://github.com/srobroek/agentic-packages/issues/522)) ([3d874b8](https://github.com/srobroek/agentic-packages/commit/3d874b86d9379322ebaeb4ebea3b9e3f7f4bb30c))

## Changelog
