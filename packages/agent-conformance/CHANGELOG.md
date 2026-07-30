# Changelog

## [6.0.0](https://github.com/srobroek/agentic-packages/compare/agent-conformance--v5.0.0...agent-conformance--v6.0.0) (2026-07-30)


### ⚠ BREAKING CHANGES

* drop the speckit package, now its own repository ([#829](https://github.com/srobroek/agentic-packages/issues/829))

### Refactors

* drop the speckit package, now its own repository ([#829](https://github.com/srobroek/agentic-packages/issues/829)) ([583c6ab](https://github.com/srobroek/agentic-packages/commit/583c6ab411201cfda3bd3a2c0911652467b27989))

## [5.0.0](https://github.com/srobroek/agentic-packages/compare/agent-conformance--v4.0.0...agent-conformance--v5.0.0) (2026-07-27)


### ⚠ BREAKING CHANGES

* **agents:** `agent-coder` is now `agent-builder` and `agent-coder-high` is `agent-builder-high`. The agents `parallel-builder`, `worker`, `coder-high`, `domain-specialist-medium` and `domain-specialist-xhigh` no longer exist; use `builder` with an explicit mode, `builder-high`, or `domain-specialist{,-high}`. Spawn calls naming a removed agent must be updated.
* route every Codex agent to a benchmarked model tier ([#766](https://github.com/srobroek/agentic-packages/issues/766))

### Bug Fixes

* **agents:** pin every agent to a model, collapse duplicate tiers ([#771](https://github.com/srobroek/agentic-packages/issues/771)) ([fd8193f](https://github.com/srobroek/agentic-packages/commit/fd8193f6e1f8fb7a4bfcb889e24f4ccd5327a7f7))
* route every Codex agent to a benchmarked model tier ([#766](https://github.com/srobroek/agentic-packages/issues/766)) ([f8fb26a](https://github.com/srobroek/agentic-packages/commit/f8fb26aacaa45cbf7ab9ceaa42855089d34b6673))

## [4.0.0](https://github.com/srobroek/agentic-packages/compare/agent-conformance--v3.0.0...agent-conformance--v4.0.0) (2026-07-26)


### ⚠ BREAKING CHANGES

* **orchestrate:** enforce the parent-managed activation contract and cut contradictory steering ([#741](https://github.com/srobroek/agentic-packages/issues/741))

### Features

* **orchestrate:** enforce the parent-managed activation contract and cut contradictory steering ([#741](https://github.com/srobroek/agentic-packages/issues/741)) ([c72959f](https://github.com/srobroek/agentic-packages/commit/c72959f0f0f5300f6b049c04ec878a164d39d5d5))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/agent-conformance--v2.0.0...agent-conformance--v3.0.0) (2026-07-25)


### ⚠ BREAKING CHANGES

* drop xhigh effort pins to high and remove a duplicate agent variant ([#723](https://github.com/srobroek/agentic-packages/issues/723))

### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))
* drop xhigh effort pins to high and remove a duplicate agent variant ([#723](https://github.com/srobroek/agentic-packages/issues/723)) ([7ce15d2](https://github.com/srobroek/agentic-packages/commit/7ce15d2f601c232b1e8f2aff6e09706547d48849))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/agent-conformance--v1.0.2...agent-conformance--v2.0.0) (2026-07-25)


### ⚠ BREAKING CHANGES

* **orchestrate:** subagent_type 'coder' -> 'builder', 'parallel-coder' -> 'parallel-builder'. Update any spawn calls referencing the old names.

### Features

* **orchestrate:** bead-as-brief v2 — claim-bound contracts, delegation-first fleet, cache policy ([#713](https://github.com/srobroek/agentic-packages/issues/713)) ([e8deb15](https://github.com/srobroek/agentic-packages/commit/e8deb151d222e843e9bc80fc6808c9acc141124f))


### Bug Fixes

* **orchestrate:** restore domain-specialist; rename coder-&gt;builder ([#715](https://github.com/srobroek/agentic-packages/issues/715)) ([223e0c9](https://github.com/srobroek/agentic-packages/commit/223e0c95cb8dee08d1f3cd00cd96cb598d78d24e))

## [1.0.2](https://github.com/srobroek/agentic-packages/compare/agent-conformance--v1.0.1...agent-conformance--v1.0.2) (2026-07-24)


### Bug Fixes

* **agent-conformance:** tolerate markdown emphasis and literal L1 token on the verdict line ([#693](https://github.com/srobroek/agentic-packages/issues/693)) ([bbeddb0](https://github.com/srobroek/agentic-packages/commit/bbeddb0dba65dbafc26561b9524a7c13ba655b2d))

## [1.0.1](https://github.com/srobroek/agentic-packages/compare/agent-conformance--v1.0.0...agent-conformance--v1.0.1) (2026-07-24)


### Bug Fixes

* **agent-conformance:** deduplicate attempt records in _record_attempt ([cce60bf](https://github.com/srobroek/agentic-packages/commit/cce60bffd49d438f54e8e8054095473b2bf83137))
* **agents:** verdict line is the literal first line — no preamble, no markdown emphasis ([#688](https://github.com/srobroek/agentic-packages/issues/688)) ([0cef5d6](https://github.com/srobroek/agentic-packages/commit/0cef5d6698a0ee7b5f3337ef993a4bf9fb653e9a))

## 1.0.0 (2026-07-24)


### Features

* agent conformance harness — behavioral contract tests for all shipped agents ([#682](https://github.com/srobroek/agentic-packages/issues/682)) ([1d44052](https://github.com/srobroek/agentic-packages/commit/1d440522d5650c8a4c9ca78f2bcc337a6bd843dd))

## Changelog
