# Changelog

## [5.0.0](https://github.com/srobroek/agentic-packages/compare/steering-pragmatic--v4.4.0...steering-pragmatic--v5.0.0) (2026-07-28)


### ⚠ BREAKING CHANGES

* the hook script is now subagent-model-guard.py and requires python3 on PATH.

### Refactors

* port every remaining shell hook to Python ([#797](https://github.com/srobroek/agentic-packages/issues/797)) ([d01fd9a](https://github.com/srobroek/agentic-packages/commit/d01fd9a79bdc07b01d4477196c5277939fa935a3))

## [4.4.0](https://github.com/srobroek/agentic-packages/compare/steering-pragmatic--v4.3.3...steering-pragmatic--v4.4.0) (2026-07-27)


### Features

* multi-agent coexistence steering package ([#782](https://github.com/srobroek/agentic-packages/issues/782)) ([f3278f3](https://github.com/srobroek/agentic-packages/commit/f3278f3ee81f8ae0ee874086df903ab9432f0b7b))

## [4.3.3](https://github.com/srobroek/agentic-packages/compare/steering-pragmatic--v4.3.2...steering-pragmatic--v4.3.3) (2026-07-27)


### Bug Fixes

* give every APM instruction an explicit applyTo, add drift guard ([#769](https://github.com/srobroek/agentic-packages/issues/769)) ([d983034](https://github.com/srobroek/agentic-packages/commit/d98303486d87b5dfb348a4a04fa435afa5fce692))

## [4.3.2](https://github.com/srobroek/agentic-packages/compare/steering-pragmatic--v4.3.1...steering-pragmatic--v4.3.2) (2026-07-25)


### Refactors

* cut duplicated rules from steering, agents and skills ([#728](https://github.com/srobroek/agentic-packages/issues/728)) ([8f892aa](https://github.com/srobroek/agentic-packages/commit/8f892aa01b3b0ffbb5888cca0dc4178d57ee967d))

## [4.3.1](https://github.com/srobroek/agentic-packages/compare/steering-pragmatic--v4.3.0...steering-pragmatic--v4.3.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [4.3.0](https://github.com/srobroek/agentic-packages/compare/steering-pragmatic--v4.2.0...steering-pragmatic--v4.3.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [4.2.0](https://github.com/srobroek/agentic-packages/compare/steering-pragmatic--v4.1.0...steering-pragmatic--v4.2.0) (2026-07-11)


### Features

* **steering:** write for the released, steady-state artifact ([#520](https://github.com/srobroek/agentic-packages/issues/520)) ([1ff9046](https://github.com/srobroek/agentic-packages/commit/1ff904647e620b8084a3219b4824df1d82ec3ff6))

## [4.1.0](https://github.com/srobroek/agentic-packages/compare/steering-pragmatic--v4.0.0...steering-pragmatic--v4.1.0) (2026-07-09)


### Features

* **steering-pragmatic:** long turns are narrated, not batched — phase-completion notes are mandatory ([bd3a355](https://github.com/srobroek/agentic-packages/commit/bd3a3558034a6e8572b189e16eb7a2b8dfd71ff2))
* **steering-pragmatic:** subagent digest gains the terse-is-not-silent narration MUST ([b4a1d4e](https://github.com/srobroek/agentic-packages/commit/b4a1d4eae8f4fedc7eb339191f2f75ae4864efca))

## [4.0.0](https://github.com/srobroek/agentic-packages/compare/steering-pragmatic--v3.0.0...steering-pragmatic--v4.0.0) (2026-07-08)


### ⚠ BREAKING CHANGES

* **steering-pragmatic:** steering-code-economy is removed; its content now ships in steering-pragmatic 4.0.0. steering-pragmatic is now type: hybrid and registers a SubagentStart hook.

### Features

* **steering-pragmatic:** absorb code-economy + inject working style into subagents ([#501](https://github.com/srobroek/agentic-packages/issues/501)) ([7f0e243](https://github.com/srobroek/agentic-packages/commit/7f0e2438feb9a7e464deb3ec620df73f4c93a9d5))


### Bug Fixes

* let release-please own version bumps for pragmatic and code-intelligence ([#502](https://github.com/srobroek/agentic-packages/issues/502)) ([01a2bb7](https://github.com/srobroek/agentic-packages/commit/01a2bb7d01126fe845429232e4d3ee40544288fc))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/steering-pragmatic--v2.0.0...steering-pragmatic--v3.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* code-economy rule overhaul — OVERRIDE, YAGNI section, hand-roll pricing, haiku routing guard ([#496](https://github.com/srobroek/agentic-packages/issues/496))

### Features

* code-economy rule overhaul — OVERRIDE, YAGNI section, hand-roll pricing, haiku routing guard ([#496](https://github.com/srobroek/agentic-packages/issues/496)) ([954025f](https://github.com/srobroek/agentic-packages/commit/954025fd2514453cf3c5bc1fecd8678be5b75258))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/steering-pragmatic--v1.1.0...steering-pragmatic--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* **steering:** Wave 4 steering rewrites — pragmatic, code-economy, dedup, language compression, orchestrate fixes

### Features

* **steering:** Wave 4 steering rewrites — pragmatic, code-economy, dedup, language compression, orchestrate fixes ([1412eaf](https://github.com/srobroek/agentic-packages/commit/1412eafea2ec018655d73d353337feb918dd27f0))


### Refactors

* **steering-pragmatic:** compress pragmatic-index to decision-table format ([136682e](https://github.com/srobroek/agentic-packages/commit/136682ef2a9aed4cc5a55a7f5755db8b6a4b512f))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/steering-pragmatic-v1.0.0...steering-pragmatic--v1.1.0) (2026-07-05)


### Features

* orchestrate comms protocol v2 with verified injection, concurrency-safe run scripts, and message linting ([#484](https://github.com/srobroek/agentic-packages/issues/484)) ([8c9cce2](https://github.com/srobroek/agentic-packages/commit/8c9cce2fbecd0f31aa2b254a7bd4d03392ce2166))
* orchestrator-only-coordinates rule, terse agent reasoning/output, pragmatic terseness + comment guidance ([#483](https://github.com/srobroek/agentic-packages/issues/483)) ([446b624](https://github.com/srobroek/agentic-packages/commit/446b62498a0e96e5b6663a3977dbd931b64c8d41))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/steering-pragmatic-v0.2.0...steering-pragmatic-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* direct/no-flattery steering + drop redundant global-apm.yml template ([#381](https://github.com/srobroek/agentic-packages/issues/381)) ([0a2a67a](https://github.com/srobroek/agentic-packages/commit/0a2a67ae8c960305d4a7f43d61d283a86801ad05))
* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/steering-pragmatic-v0.1.0...steering-pragmatic-v0.2.0) (2026-06-04)


### Features

* **hooks,steering:** add granular global guard hooks + pragmatic steering [skip tests] ([#248](https://github.com/srobroek/agentic-packages/issues/248)) ([11d60ed](https://github.com/srobroek/agentic-packages/commit/11d60ed5e9c4b342742e421995beebde7a157fa0))
