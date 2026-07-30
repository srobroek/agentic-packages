# Changelog

## [1.1.2](https://github.com/srobroek/agentic-packages/compare/session-review--v1.1.1...session-review--v1.1.2) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [1.1.1](https://github.com/srobroek/agentic-packages/compare/session-review--v1.1.0...session-review--v1.1.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/session-review--v1.0.0...session-review--v1.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/session-review--v0.2.0...session-review--v1.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering
* **write-agentic:** package renamed write-a-skill -> write-agentic; referencing bundles updated.

### Features

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering ([9cb202d](https://github.com/srobroek/agentic-packages/commit/9cb202d2b76a649dda0489baaeefd61a2e0829e1))
* **write-agentic:** generalize write-a-skill to all agentic assets, add lint ([ff5df7a](https://github.com/srobroek/agentic-packages/commit/ff5df7a6614906c669eac40f8bc05c0ee55257cd))


### Refactors

* **agentic:** replace sigil grammar with MUST/DEFAULT/ASK/NOT keywords throughout ([52a8958](https://github.com/srobroek/agentic-packages/commit/52a895874110733cc0f5f11197366659d3fe6074))
* **audit-steering:** absorb project-hygiene + optimize-steering; delete both packages ([2d4426e](https://github.com/srobroek/agentic-packages/commit/2d4426ecd3316c450d09f93eae7f958bf25bf1e2))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/session-review-v0.1.1...session-review--v0.2.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [0.1.1](https://github.com/srobroek/agentic-packages/compare/session-review-v0.1.0...session-review-v0.1.1) (2026-06-26)


### Refactors

* split core-global into independently installable packages ([#380](https://github.com/srobroek/agentic-packages/issues/380)) ([36f9470](https://github.com/srobroek/agentic-packages/commit/36f9470fc50a7ff5af2c7dd943a817a1d9808247))

## 0.1.0

### Features

* Initial `session-review` skill package, extracted from the `core-global`
  bundle so it can be installed independently.
