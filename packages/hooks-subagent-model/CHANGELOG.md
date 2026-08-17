# Changelog

## [3.1.0](https://github.com/srobroek/agentic-packages/compare/hooks-subagent-model--v3.0.2...hooks-subagent-model--v3.1.0) (2026-08-17)


### Features

* **codex:** validate packages and standardize language tooling ([#856](https://github.com/srobroek/agentic-packages/issues/856)) ([42edbfb](https://github.com/srobroek/agentic-packages/commit/42edbfb3948c0103f3ce3ef5ba6819a08ae73566))

## [3.0.2](https://github.com/srobroek/agentic-packages/compare/hooks-subagent-model--v3.0.1...hooks-subagent-model--v3.0.2) (2026-08-17)


### Bug Fixes

* one undecodable byte no longer silences eleven more guards ([#852](https://github.com/srobroek/agentic-packages/issues/852)) ([3fb5835](https://github.com/srobroek/agentic-packages/commit/3fb58352d2f37ba67adc14ba3c03d204c1507a9e))

## [3.0.1](https://github.com/srobroek/agentic-packages/compare/hooks-subagent-model--v3.0.0...hooks-subagent-model--v3.0.1) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-subagent-model--v2.0.0...hooks-subagent-model--v3.0.0) (2026-07-28)


### ⚠ BREAKING CHANGES

* the hook script is now subagent-model-guard.py and requires python3 on PATH.

### Refactors

* port every remaining shell hook to Python ([#797](https://github.com/srobroek/agentic-packages/issues/797)) ([d01fd9a](https://github.com/srobroek/agentic-packages/commit/d01fd9a79bdc07b01d4477196c5277939fa935a3))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-subagent-model--v1.0.2...hooks-subagent-model--v2.0.0) (2026-07-28)


### ⚠ BREAKING CHANGES

* agentic-source-guard no longer runs; edits to agentic source files are no longer hook-gated.

### Bug Fixes

* drop the repo-local source guard and stop routing agent work to haiku ([#791](https://github.com/srobroek/agentic-packages/issues/791)) ([b1b8b4e](https://github.com/srobroek/agentic-packages/commit/b1b8b4e78d6f18deb387d351cfb7365452e005d9))

## [1.0.2](https://github.com/srobroek/agentic-packages/compare/hooks-subagent-model--v1.0.1...hooks-subagent-model--v1.0.2) (2026-07-27)


### Bug Fixes

* give every APM instruction an explicit applyTo, add drift guard ([#769](https://github.com/srobroek/agentic-packages/issues/769)) ([d983034](https://github.com/srobroek/agentic-packages/commit/d98303486d87b5dfb348a4a04fa435afa5fce692))

## [1.0.1](https://github.com/srobroek/agentic-packages/compare/hooks-subagent-model--v1.0.0...hooks-subagent-model--v1.0.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-subagent-model--v0.3.0...hooks-subagent-model--v1.0.0) (2026-07-23)


### ⚠ BREAKING CHANGES

* retire generic tier-wrapper agents in favor of semantic roles ([#668](https://github.com/srobroek/agentic-packages/issues/668))

### Features

* retire generic tier-wrapper agents in favor of semantic roles ([#668](https://github.com/srobroek/agentic-packages/issues/668)) ([5ba8f01](https://github.com/srobroek/agentic-packages/commit/5ba8f019572661f184468fd99bf3fbfc9d5240e6))


### Bug Fixes

* **hooks-subagent-model:** recommend installed agent profiles instead of hardcoded names ([#670](https://github.com/srobroek/agentic-packages/issues/670)) ([2c508ab](https://github.com/srobroek/agentic-packages/commit/2c508ab6b599d456f0c49c4f3daea8c672300925))
* steering matches deployed models and sheds per-session token weight ([#664](https://github.com/srobroek/agentic-packages/issues/664)) ([05ac136](https://github.com/srobroek/agentic-packages/commit/05ac136fb5b81c8a3b2497078eb79d88a4aa9f2c))

## [0.3.0](https://github.com/srobroek/agentic-packages/compare/hooks-subagent-model--v0.2.1...hooks-subagent-model--v0.3.0) (2026-07-22)


### Features

* make Codex and Claude APM integration target-aware ([#643](https://github.com/srobroek/agentic-packages/issues/643)) ([83fe64b](https://github.com/srobroek/agentic-packages/commit/83fe64b7bf119cb91aaea3f3d7932b2781a45eee))


### Bug Fixes

* prevent duplicate and invalid release notes ([#645](https://github.com/srobroek/agentic-packages/issues/645)) ([01d3689](https://github.com/srobroek/agentic-packages/commit/01d3689d03245a46adb511b04cb3d12ce1c7b603))

## [0.2.1](https://github.com/srobroek/agentic-packages/compare/hooks-subagent-model--v0.2.0...hooks-subagent-model--v0.2.1) (2026-07-22)


### Bug Fixes

* prevent subagents from inheriting unintended models ([44f3d50](https://github.com/srobroek/agentic-packages/commit/44f3d501dfeb3ce2b645e53b5ddc77a63938fdb6))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/hooks-subagent-model--v0.1.0...hooks-subagent-model--v0.2.0) (2026-07-20)


### Features

* **hooks-subagent-model:** deny model-less spawns of inherit-type subagents with routing guidance ([#542](https://github.com/srobroek/agentic-packages/issues/542)) ([26cd426](https://github.com/srobroek/agentic-packages/commit/26cd426e4dff3b0ae0e0d2ccfb8b4e43d11907c3))

## 0.1.0 (2026-07-17)

### Features

* PreToolUse:Agent deny gate that blocks model-less spawns of inherit-type subagents (`general-purpose`, `Explore`, `Plan`, `claude`, `fork`, or `subagent_type` omitted) and returns a tier routing table (cheap/mid/top) so the caller's retry succeeds. Deny reason also notes that reasoning effort is not enforceable per-call and points to pinning `effort:` in reusable agent definitions instead. Inherit-type list overridable via `SUBAGENT_MODEL_GUARD_INHERIT_TYPES`. Fails open on malformed input. Claude-only.
