# Changelog

## [1.0.2](https://github.com/srobroek/agentic-packages/compare/user-journeys--v1.0.1...user-journeys--v1.0.2) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [1.0.1](https://github.com/srobroek/agentic-packages/compare/user-journeys--v1.0.0...user-journeys--v1.0.1) (2026-07-30)


### Bug Fixes

* quote frontmatter values holding a colon, so six primitives deploy at all ([#826](https://github.com/srobroek/agentic-packages/issues/826)) ([b3b6325](https://github.com/srobroek/agentic-packages/commit/b3b6325f0bf881160f6977c5257bc76d3c8ccae1))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/user-journeys--v0.7.2...user-journeys--v1.0.0) (2026-07-27)


### ⚠ BREAKING CHANGES

* **agents:** `agent-coder` is now `agent-builder` and `agent-coder-high` is `agent-builder-high`. The agents `parallel-builder`, `worker`, `coder-high`, `domain-specialist-medium` and `domain-specialist-xhigh` no longer exist; use `builder` with an explicit mode, `builder-high`, or `domain-specialist{,-high}`. Spawn calls naming a removed agent must be updated.
* route every Codex agent to a benchmarked model tier ([#766](https://github.com/srobroek/agentic-packages/issues/766))

### Bug Fixes

* **agents:** pin every agent to a model, collapse duplicate tiers ([#771](https://github.com/srobroek/agentic-packages/issues/771)) ([fd8193f](https://github.com/srobroek/agentic-packages/commit/fd8193f6e1f8fb7a4bfcb889e24f4ccd5327a7f7))
* route every Codex agent to a benchmarked model tier ([#766](https://github.com/srobroek/agentic-packages/issues/766)) ([f8fb26a](https://github.com/srobroek/agentic-packages/commit/f8fb26aacaa45cbf7ab9ceaa42855089d34b6673))

## [0.7.2](https://github.com/srobroek/agentic-packages/compare/user-journeys--v0.7.1...user-journeys--v0.7.2) (2026-07-25)


### Refactors

* cut duplicated rules from steering, agents and skills ([#728](https://github.com/srobroek/agentic-packages/issues/728)) ([8f892aa](https://github.com/srobroek/agentic-packages/commit/8f892aa01b3b0ffbb5888cca0dc4178d57ee967d))

## [0.7.1](https://github.com/srobroek/agentic-packages/compare/user-journeys--v0.7.0...user-journeys--v0.7.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [0.7.0](https://github.com/srobroek/agentic-packages/compare/user-journeys--v0.6.0...user-journeys--v0.7.0) (2026-07-25)


### Features

* **orchestrate:** bead-as-brief v2 — claim-bound contracts, delegation-first fleet, cache policy ([#713](https://github.com/srobroek/agentic-packages/issues/713)) ([e8deb15](https://github.com/srobroek/agentic-packages/commit/e8deb151d222e843e9bc80fc6808c9acc141124f))

## [0.6.0](https://github.com/srobroek/agentic-packages/compare/user-journeys--v0.5.0...user-journeys--v0.6.0) (2026-07-23)


### Features

* agent linter catches empty descriptions, over-constraint, missing triggers, and bloat ([#672](https://github.com/srobroek/agentic-packages/issues/672)) ([47feb78](https://github.com/srobroek/agentic-packages/commit/47feb78421542944aa0f1ee7947e1b3ebab0f08d))

## [0.5.0](https://github.com/srobroek/agentic-packages/compare/user-journeys--v0.4.0...user-journeys--v0.5.0) (2026-07-23)


### Features

* **user-journeys:** add Beads verification formulas ([#606](https://github.com/srobroek/agentic-packages/issues/606)) ([1ae5c5c](https://github.com/srobroek/agentic-packages/commit/1ae5c5c29fe185c62d2445bdea8bb6e04ef3006d))

## [0.4.0](https://github.com/srobroek/agentic-packages/compare/user-journeys--v0.3.1...user-journeys--v0.4.0) (2026-07-21)


### Features

* **agents:** preserve model routing in workflow packages ([df86afc](https://github.com/srobroek/agentic-packages/commit/df86afc45f5c6da979e939aba1ed7f5fe2fcbc6a))

## [0.3.1](https://github.com/srobroek/agentic-packages/compare/user-journeys--v0.3.0...user-journeys--v0.3.1) (2026-07-20)


### Bug Fixes

* **user-journeys:** let journey-validator follow a canonical driving-mechanics doc ([#544](https://github.com/srobroek/agentic-packages/issues/544)) ([bb7a378](https://github.com/srobroek/agentic-packages/commit/bb7a3781e7c628f69adc04e0fc0dcc765fc90a4b))

## [0.3.0](https://github.com/srobroek/agentic-packages/compare/user-journeys--v0.2.0...user-journeys--v0.3.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))
* **user-journeys:** issue-driven mode for journey-campaign ([#534](https://github.com/srobroek/agentic-packages/issues/534)) ([72b2a24](https://github.com/srobroek/agentic-packages/commit/72b2a244049737acdfedf85ba1dcd623124bfb4f))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/user-journeys--v0.1.0...user-journeys--v0.2.0) (2026-07-14)


### Features

* **user-journeys:** service-agnostic user-journey lifecycle package ([#532](https://github.com/srobroek/agentic-packages/issues/532)) ([5799976](https://github.com/srobroek/agentic-packages/commit/57999765c239a322883d662545ab1b2739f19792))
