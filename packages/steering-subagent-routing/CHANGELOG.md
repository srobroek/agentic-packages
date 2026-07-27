# Changelog

## [3.2.5](https://github.com/srobroek/agentic-packages/compare/steering-subagent-routing--v3.2.4...steering-subagent-routing--v3.2.5) (2026-07-27)


### Bug Fixes

* give every APM instruction an explicit applyTo, add drift guard ([#769](https://github.com/srobroek/agentic-packages/issues/769)) ([d983034](https://github.com/srobroek/agentic-packages/commit/d98303486d87b5dfb348a4a04fa435afa5fce692))

## [3.2.4](https://github.com/srobroek/agentic-packages/compare/steering-subagent-routing--v3.2.3...steering-subagent-routing--v3.2.4) (2026-07-25)


### Refactors

* cut duplicated rules from steering, agents and skills ([#728](https://github.com/srobroek/agentic-packages/issues/728)) ([8f892aa](https://github.com/srobroek/agentic-packages/commit/8f892aa01b3b0ffbb5888cca0dc4178d57ee967d))

## [3.2.3](https://github.com/srobroek/agentic-packages/compare/steering-subagent-routing--v3.2.2...steering-subagent-routing--v3.2.3) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [3.2.2](https://github.com/srobroek/agentic-packages/compare/steering-subagent-routing--v3.2.1...steering-subagent-routing--v3.2.2) (2026-07-23)


### Bug Fixes

* steering matches deployed models and sheds per-session token weight ([#664](https://github.com/srobroek/agentic-packages/issues/664)) ([05ac136](https://github.com/srobroek/agentic-packages/commit/05ac136fb5b81c8a3b2497078eb79d88a4aa9f2c))

## [3.2.1](https://github.com/srobroek/agentic-packages/compare/steering-subagent-routing--v3.2.0...steering-subagent-routing--v3.2.1) (2026-07-22)


### Bug Fixes

* route agent code discovery through Serena ([bf9593c](https://github.com/srobroek/agentic-packages/commit/bf9593c14f5d486af11f2d364e8d5dd66d3b0306))

## [3.2.0](https://github.com/srobroek/agentic-packages/compare/steering-subagent-routing--v3.1.0...steering-subagent-routing--v3.2.0) (2026-07-20)


### Features

* **beads:** subagent work-contract reminder and bead-id delegation rule ([88d8062](https://github.com/srobroek/agentic-packages/commit/88d8062a691a93fb0f946c1ab341356a7a847031))
* subagent beads work-contract reminder and bead-id delegation rule ([81d878b](https://github.com/srobroek/agentic-packages/commit/81d878b7f1602af288055437b9e67ee7632bdcfa))

## [3.1.0](https://github.com/srobroek/agentic-packages/compare/steering-subagent-routing--v3.0.0...steering-subagent-routing--v3.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/steering-subagent-routing--v2.0.0...steering-subagent-routing--v3.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* code-economy rule overhaul — OVERRIDE, YAGNI section, hand-roll pricing, haiku routing guard ([#496](https://github.com/srobroek/agentic-packages/issues/496))

### Features

* code-economy rule overhaul — OVERRIDE, YAGNI section, hand-roll pricing, haiku routing guard ([#496](https://github.com/srobroek/agentic-packages/issues/496)) ([954025f](https://github.com/srobroek/agentic-packages/commit/954025fd2514453cf3c5bc1fecd8678be5b75258))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/steering-subagent-routing-v1.0.0...steering-subagent-routing--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* **steering:** Wave 4 steering rewrites — pragmatic, code-economy, dedup, language compression, orchestrate fixes

### Features

* **steering:** Wave 4 steering rewrites — pragmatic, code-economy, dedup, language compression, orchestrate fixes ([1412eaf](https://github.com/srobroek/agentic-packages/commit/1412eafea2ec018655d73d353337feb918dd27f0))


### Refactors

* **steering-subagent-routing:** rewrite agent-routing to table format ([108be05](https://github.com/srobroek/agentic-packages/commit/108be0508da2d4d69f6359afebae650ef064bacf))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/steering-subagent-routing-v0.1.0...steering-subagent-routing-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/steering-subagent-routing-v0.0.1...steering-subagent-routing-v0.1.0) (2026-06-02)


### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **steering:** split baseline into 3 opt-in packages; extract speckit hooks [skip tests] ([9a19504](https://github.com/srobroek/agentic-packages/commit/9a195043c208f8d03d462507a2720d66e7addc2c))
