# Changelog

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/speckit-dag-hooks-v0.7.0...speckit-dag-hooks-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))


### Bug Fixes

* **phase-1:** guard bypasses, bash-3.2/BSD portability, crashes, bundle pins + tests ([#360](https://github.com/srobroek/agentic-packages/issues/360)) ([b0c9106](https://github.com/srobroek/agentic-packages/commit/b0c91064313282a4265b9b0b8fb779f00afecd90))


### Refactors

* **speckit-dag:** generate nodes.json from a stdlib dataclass builder ([#365](https://github.com/srobroek/agentic-packages/issues/365)) ([757755f](https://github.com/srobroek/agentic-packages/commit/757755f94968d1dfe2edd8f00493991c8f3b4065))
* **speckit-dag:** generate nodes.json from a stdlib dataclass builder ([#367](https://github.com/srobroek/agentic-packages/issues/367)) ([ae598a9](https://github.com/srobroek/agentic-packages/commit/ae598a949b3d09485bb352686073de524607e595))

## [0.7.0](https://github.com/srobroek/agentic-packages/compare/speckit-dag-hooks-v0.6.0...speckit-dag-hooks-v0.7.0) (2026-06-25)


### Features

* **speckit:** adopt memory-md 1.x across speckit, dag-hooks, and steering ([#355](https://github.com/srobroek/agentic-packages/issues/355)) ([450f1f3](https://github.com/srobroek/agentic-packages/commit/450f1f36ae8c9e42562e9270c414da34dd55dbfb))

## [0.6.0](https://github.com/srobroek/agentic-packages/compare/speckit-dag-hooks-v0.5.0...speckit-dag-hooks-v0.6.0) (2026-06-24)


### Features

* **speckit:** checklist-after-tasks reorder, memory-md default, agent-assign + hook fixes ([56ceefc](https://github.com/srobroek/agentic-packages/commit/56ceefc09ae0c8e2e2f46977478f188daeb4fa7a))

## [0.5.0](https://github.com/srobroek/agentic-packages/compare/speckit-dag-hooks-v0.4.1...speckit-dag-hooks-v0.5.0) (2026-06-24)


### Features

* **speckit-dag-hooks:** resolve .run/sub-namespace commands and add converge node [skip tests] ([7eb3f0d](https://github.com/srobroek/agentic-packages/commit/7eb3f0da8108df9d594f239cb6e747dbbc6fc34f))
* **speckit:** align with spec-kit 0.11.x — setup ownership, DAG node fix, converge ([8b2a51b](https://github.com/srobroek/agentic-packages/commit/8b2a51b3faa914ae86bbb6944ba62e408ca2e040))

## [0.4.1](https://github.com/srobroek/agentic-packages/compare/speckit-dag-hooks-v0.4.0...speckit-dag-hooks-v0.4.1) (2026-06-21)


### Bug Fixes

* **speckit-dag-hooks:** glob preconditions and anchor hook commands at project root ([93ae6b0](https://github.com/srobroek/agentic-packages/commit/93ae6b006e901d87399126c6c8a9b46c764ea49d))
* **speckit-dag-hooks:** glob preconditions and anchor hook commands at project root ([2f60f94](https://github.com/srobroek/agentic-packages/commit/2f60f94e35b3070c4ea5ca9794895bb12a92fa4b))

## [0.4.0](https://github.com/srobroek/agentic-packages/compare/speckit-dag-hooks-v0.3.2...speckit-dag-hooks-v0.4.0) (2026-06-20)


### Features

* adopt apm 0.21 semver ranges, sub-bundle core, add kiro target ([#341](https://github.com/srobroek/agentic-packages/issues/341)) ([d033e88](https://github.com/srobroek/agentic-packages/commit/d033e88fee643b036498c1edccc4ba50af742659))

## [0.3.2](https://github.com/srobroek/agentic-packages/compare/speckit-dag-hooks-v0.3.1...speckit-dag-hooks-v0.3.2) (2026-06-20)


### Bug Fixes

* **speckit-dag-hooks:** resolve feature from invoking agent's working dir ([2b9e423](https://github.com/srobroek/agentic-packages/commit/2b9e42396636545b04fd6a1a2e1d9d1badf06c63))
* **speckit-dag-hooks:** resolve feature from invoking agent's working dir ([742c5d3](https://github.com/srobroek/agentic-packages/commit/742c5d36fecbaefd42eabb98f85d61d1cfdff3e9))

## [0.3.1](https://github.com/srobroek/agentic-packages/compare/speckit-dag-hooks-v0.3.0...speckit-dag-hooks-v0.3.1) (2026-06-12)


### Bug Fixes

* bump bundle member pins to released versions, refresh README counts ([#307](https://github.com/srobroek/agentic-packages/issues/307)) ([a1c099b](https://github.com/srobroek/agentic-packages/commit/a1c099b9f03765459fdcb990e61b262aab967cbb))

## [0.3.0](https://github.com/srobroek/agentic-packages/compare/speckit-dag-hooks-v0.2.0...speckit-dag-hooks-v0.3.0) (2026-06-12)


### Features

* **speckit-dag-hooks:** enforce preconditions, gate checkpoint.commit ([#295](https://github.com/srobroek/agentic-packages/issues/295)) ([3346bb2](https://github.com/srobroek/agentic-packages/commit/3346bb202cd5f908a65eb519b9103b4b72cee24f))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/speckit-dag-hooks-v0.1.0...speckit-dag-hooks-v0.2.0) (2026-06-10)


### Features

* **speckit-dag-hooks,steering-speckit:** add orchestrator review gate + hard memory-synthesis precondition ([327329c](https://github.com/srobroek/agentic-packages/commit/327329c6531006f4d4094beb4d11114619d5575a))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/speckit-dag-hooks-v0.0.1...speckit-dag-hooks-v0.1.0) (2026-06-02)


### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* **speckit-dag-hooks:** self-contained Python dispatcher + JSON nodes [skip tests] ([d46f465](https://github.com/srobroek/agentic-packages/commit/d46f465b7e056ca0d1689362f3d192c8819da1a9))


### Bug Fixes

* use valid repo-locator dependency syntax for bundle members [skip tests] ([855d9d6](https://github.com/srobroek/agentic-packages/commit/855d9d67b2e6c93e9dd1b603fd7cf958e172682a))
* valid repo-locator dependency syntax for bundle members ([c4be60c](https://github.com/srobroek/agentic-packages/commit/c4be60cf8308c21be297b9fcf2381b3e6687ac61))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **steering:** split baseline into 3 opt-in packages; extract speckit hooks [skip tests] ([9a19504](https://github.com/srobroek/agentic-packages/commit/9a195043c208f8d03d462507a2720d66e7addc2c))
