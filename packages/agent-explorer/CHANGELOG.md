# Changelog

## [3.0.1](https://github.com/srobroek/agentic-packages/compare/agent-explorer--v3.0.0...agent-explorer--v3.0.1) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/agent-explorer--v2.0.1...agent-explorer--v3.0.0) (2026-07-27)


### ⚠ BREAKING CHANGES

* **agents:** `agent-coder` is now `agent-builder` and `agent-coder-high` is `agent-builder-high`. The agents `parallel-builder`, `worker`, `coder-high`, `domain-specialist-medium` and `domain-specialist-xhigh` no longer exist; use `builder` with an explicit mode, `builder-high`, or `domain-specialist{,-high}`. Spawn calls naming a removed agent must be updated.
* route every Codex agent to a benchmarked model tier ([#766](https://github.com/srobroek/agentic-packages/issues/766))

### Bug Fixes

* **agents:** pin every agent to a model, collapse duplicate tiers ([#771](https://github.com/srobroek/agentic-packages/issues/771)) ([fd8193f](https://github.com/srobroek/agentic-packages/commit/fd8193f6e1f8fb7a4bfcb889e24f4ccd5327a7f7))
* route every Codex agent to a benchmarked model tier ([#766](https://github.com/srobroek/agentic-packages/issues/766)) ([f8fb26a](https://github.com/srobroek/agentic-packages/commit/f8fb26aacaa45cbf7ab9ceaa42855089d34b6673))

## [2.0.1](https://github.com/srobroek/agentic-packages/compare/agent-explorer--v2.0.0...agent-explorer--v2.0.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/agent-explorer--v1.1.0...agent-explorer--v2.0.0) (2026-07-23)


### ⚠ BREAKING CHANGES

* retire generic tier-wrapper agents in favor of semantic roles ([#668](https://github.com/srobroek/agentic-packages/issues/668))

### Features

* retire generic tier-wrapper agents in favor of semantic roles ([#668](https://github.com/srobroek/agentic-packages/issues/668)) ([5ba8f01](https://github.com/srobroek/agentic-packages/commit/5ba8f019572661f184468fd99bf3fbfc9d5240e6))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/agent-explorer--v1.0.0...agent-explorer--v1.1.0) (2026-07-22)


### Features

* make Codex and Claude APM integration target-aware ([#643](https://github.com/srobroek/agentic-packages/issues/643)) ([83fe64b](https://github.com/srobroek/agentic-packages/commit/83fe64b7bf119cb91aaea3f3d7932b2781a45eee))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/agent-explorer--v0.1.0...agent-explorer--v1.0.0) (2026-07-21)


### Features

* **agents:** add independently installable Codex profiles ([6b3f3fa](https://github.com/srobroek/agentic-packages/commit/6b3f3fae27544a4712a070e28811b5ab3c70d6da))
