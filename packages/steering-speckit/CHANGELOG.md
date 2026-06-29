# Changelog

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/steering-speckit-v1.0.0...steering-speckit--v2.0.0) (2026-06-29)


### ⚠ BREAKING CHANGES

* **speckit:** the /speckit.memory-md.* commands and the mcp-speckit-memory MCP server are no longer installed by speckit setup.

### Features

* **speckit:** drop memory-md extension and mcp-speckit-memory package ([#415](https://github.com/srobroek/agentic-packages/issues/415)) ([855bd7d](https://github.com/srobroek/agentic-packages/commit/855bd7d86bf8cadadbdc94179bc80c35eb06119d))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/steering-speckit-v0.5.0...steering-speckit-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))


### Bug Fixes

* **speckit:** roadmap.write after iterate + regenerate stale bundles table ([#363](https://github.com/srobroek/agentic-packages/issues/363)) ([be1aa2c](https://github.com/srobroek/agentic-packages/commit/be1aa2c8ec14d36b7fb8dccbb3ad62396442193c))

## [0.5.0](https://github.com/srobroek/agentic-packages/compare/steering-speckit-v0.4.0...steering-speckit-v0.5.0) (2026-06-25)


### Features

* **speckit:** adopt memory-md 1.x across speckit, dag-hooks, and steering ([#355](https://github.com/srobroek/agentic-packages/issues/355)) ([450f1f3](https://github.com/srobroek/agentic-packages/commit/450f1f36ae8c9e42562e9270c414da34dd55dbfb))

## [0.4.0](https://github.com/srobroek/agentic-packages/compare/steering-speckit-v0.3.0...steering-speckit-v0.4.0) (2026-06-24)


### Features

* **speckit:** checklist-after-tasks reorder, memory-md default, agent-assign + hook fixes ([56ceefc](https://github.com/srobroek/agentic-packages/commit/56ceefc09ae0c8e2e2f46977478f188daeb4fa7a))

## [0.3.0](https://github.com/srobroek/agentic-packages/compare/steering-speckit-v0.2.1...steering-speckit-v0.3.0) (2026-06-24)


### Features

* **speckit:** align with spec-kit 0.11.x — setup ownership, DAG node fix, converge ([8b2a51b](https://github.com/srobroek/agentic-packages/commit/8b2a51b3faa914ae86bbb6944ba62e408ca2e040))
* **steering-speckit:** document converge path and fix dead command names [skip tests] ([8bdef3a](https://github.com/srobroek/agentic-packages/commit/8bdef3abe73d2630b62db9bd358ff4649602adf6))

## [0.2.1](https://github.com/srobroek/agentic-packages/compare/steering-speckit-v0.2.0...steering-speckit-v0.2.1) (2026-06-12)


### Bug Fixes

* **steering-speckit:** token-efficiency pass, true Phase 3 chain ([#297](https://github.com/srobroek/agentic-packages/issues/297)) ([60e42a9](https://github.com/srobroek/agentic-packages/commit/60e42a9dcae26c62e725743eb75983bf803dc740))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/steering-speckit-v0.1.0...steering-speckit-v0.2.0) (2026-06-10)


### Features

* **speckit-dag-hooks,steering-speckit:** add orchestrator review gate + hard memory-synthesis precondition ([327329c](https://github.com/srobroek/agentic-packages/commit/327329c6531006f4d4094beb4d11114619d5575a))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/steering-speckit-v0.0.1...steering-speckit-v0.1.0) (2026-06-02)


### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **speckit:** remove root duplicates; extract workflow to steering-speckit [skip tests] ([7ff5284](https://github.com/srobroek/agentic-packages/commit/7ff52846cdc17386f83ceb5e6de187196bb0f3de))
