# Changelog

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/agent-quality-guards--v1.0.1...agent-quality-guards--v2.0.0) (2026-07-27)


### ⚠ BREAKING CHANGES

* **agents:** `agent-coder` is now `agent-builder` and `agent-coder-high` is `agent-builder-high`. The agents `parallel-builder`, `worker`, `coder-high`, `domain-specialist-medium` and `domain-specialist-xhigh` no longer exist; use `builder` with an explicit mode, `builder-high`, or `domain-specialist{,-high}`. Spawn calls naming a removed agent must be updated.
* route every Codex agent to a benchmarked model tier ([#766](https://github.com/srobroek/agentic-packages/issues/766))

### Bug Fixes

* **agents:** pin every agent to a model, collapse duplicate tiers ([#771](https://github.com/srobroek/agentic-packages/issues/771)) ([fd8193f](https://github.com/srobroek/agentic-packages/commit/fd8193f6e1f8fb7a4bfcb889e24f4ccd5327a7f7))
* route every Codex agent to a benchmarked model tier ([#766](https://github.com/srobroek/agentic-packages/issues/766)) ([f8fb26a](https://github.com/srobroek/agentic-packages/commit/f8fb26aacaa45cbf7ab9ceaa42855089d34b6673))

## [1.0.1](https://github.com/srobroek/agentic-packages/compare/agent-quality-guards--v1.0.0...agent-quality-guards--v1.0.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))
* close three guard bypasses and eight broken agent references ([#722](https://github.com/srobroek/agentic-packages/issues/722)) ([cbc6875](https://github.com/srobroek/agentic-packages/commit/cbc6875f53b3b048f4fe882bad69305a04e47bc3))

## 1.0.0 (2026-07-23)


### Features

* standalone quality-guard agents for docs, lint, metrics, maintenance, and diff triage ([#656](https://github.com/srobroek/agentic-packages/issues/656)) ([1263c67](https://github.com/srobroek/agentic-packages/commit/1263c670ce5f7ab7de5b6cc5b55803e1dadaf8c0))
