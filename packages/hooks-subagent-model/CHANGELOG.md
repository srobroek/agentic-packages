# Changelog

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
