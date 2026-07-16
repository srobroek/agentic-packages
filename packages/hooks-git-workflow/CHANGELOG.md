# Changelog

## [2.2.0](https://github.com/srobroek/agentic-packages/compare/hooks-git-workflow--v2.1.0...hooks-git-workflow--v2.2.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/hooks-git-workflow--v2.0.0...hooks-git-workflow--v2.1.0) (2026-07-07)


### Features

* **hooks:** stable rule IDs for git-workflow, bash-safety, and git-safety guards ([#494](https://github.com/srobroek/agentic-packages/issues/494)) ([d46a50a](https://github.com/srobroek/agentic-packages/commit/d46a50ab266a706728455e127c906b87d73bba55))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-git-workflow--v1.3.0...hooks-git-workflow--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* **hooks:** tier-gate the coder nudge; drop push test-gate and discovery steer

### Features

* **hooks:** tier-gate the coder nudge; drop push test-gate and discovery steer ([786988a](https://github.com/srobroek/agentic-packages/commit/786988af6a80f3afe31e8763e1077e4a30e61920))

## [1.3.0](https://github.com/srobroek/agentic-packages/compare/hooks-git-workflow--v1.2.0...hooks-git-workflow--v1.3.0) (2026-07-05)


### Features

* continuous commit/push delivery cadence (steering-delivery package + agent/hook updates) ([#476](https://github.com/srobroek/agentic-packages/issues/476)) ([1f0534f](https://github.com/srobroek/agentic-packages/commit/1f0534f15b7b86952153feaacbbf3e2b9c8887c7))

## [1.2.0](https://github.com/srobroek/agentic-packages/compare/hooks-git-workflow--v1.1.0...hooks-git-workflow--v1.2.0) (2026-07-02)


### Features

* block git push on stale or failing unit tests ([#451](https://github.com/srobroek/agentic-packages/issues/451)) ([34041b8](https://github.com/srobroek/agentic-packages/commit/34041b8468c6d307ae8a5b074f9dc4942bf7d848))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/hooks-git-workflow-v1.0.1...hooks-git-workflow--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.1](https://github.com/srobroek/agentic-packages/compare/hooks-git-workflow-v1.0.0...hooks-git-workflow-v1.0.1) (2026-06-26)


### Bug Fixes

* use installable package types so hooks + speckit resolve globally ([#387](https://github.com/srobroek/agentic-packages/issues/387)) ([ff2b7a2](https://github.com/srobroek/agentic-packages/commit/ff2b7a2200fc88bcf39abafe9f73ed6f5d31e942))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-git-workflow-v0.2.1...hooks-git-workflow-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* mcp-package-version no longer ships the package-file-warn or pkg-version-warn hooks. Installers that relied on those hooks should install hooks-package-file-guard / hooks-pkg-version-warn (or the dependency-quality bundle) instead.
* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))
* **speckit:** checklist-after-tasks reorder, memory-md default, agent-assign + hook fixes ([56ceefc](https://github.com/srobroek/agentic-packages/commit/56ceefc09ae0c8e2e2f46977478f188daeb4fa7a))
* split dependency tooling into independent packages + dependency-quality bundle ([#370](https://github.com/srobroek/agentic-packages/issues/370)) ([03d50a5](https://github.com/srobroek/agentic-packages/commit/03d50a5db3a1572fbe36a4ac1bc1e6877cd96ade))


### Bug Fixes

* **hooks-git-workflow:** make pre-commit test gate a soft warning [skip tests] ([9290b42](https://github.com/srobroek/agentic-packages/commit/9290b428e3fb6fe092c984494d57537f44c2206f))
* **hooks-git-workflow:** revive the pre-commit test gate ([#275](https://github.com/srobroek/agentic-packages/issues/275)) ([671afed](https://github.com/srobroek/agentic-packages/commit/671afedf40b54801221484413fd3d6acb87942ec))
* **hooks-git-workflow:** sync apm.yml description with soft-warn gate [skip tests] ([3f5758f](https://github.com/srobroek/agentic-packages/commit/3f5758f50df15056c5caf1f5830ed946432ce414))
* **hooks:** repair silently-dead hook filters (if-alternation bug) ([#372](https://github.com/srobroek/agentic-packages/issues/372)) ([659d5fe](https://github.com/srobroek/agentic-packages/commit/659d5fe6bb24a27b1876f46c6a750379eb66ec87))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/hooks-git-workflow-v0.1.1...hooks-git-workflow-v0.2.0) (2026-06-24)


### Features

* **speckit:** checklist-after-tasks reorder, memory-md default, agent-assign + hook fixes ([56ceefc](https://github.com/srobroek/agentic-packages/commit/56ceefc09ae0c8e2e2f46977478f188daeb4fa7a))


### Bug Fixes

* **hooks-git-workflow:** make pre-commit test gate a soft warning [skip tests] ([9290b42](https://github.com/srobroek/agentic-packages/commit/9290b428e3fb6fe092c984494d57537f44c2206f))
* **hooks-git-workflow:** sync apm.yml description with soft-warn gate [skip tests] ([3f5758f](https://github.com/srobroek/agentic-packages/commit/3f5758f50df15056c5caf1f5830ed946432ce414))

## [0.1.1](https://github.com/srobroek/agentic-packages/compare/hooks-git-workflow-v0.1.0...hooks-git-workflow-v0.1.1) (2026-06-12)


### Bug Fixes

* **hooks-git-workflow:** revive the pre-commit test gate ([#275](https://github.com/srobroek/agentic-packages/issues/275)) ([671afed](https://github.com/srobroek/agentic-packages/commit/671afedf40b54801221484413fd3d6acb87942ec))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/hooks-git-workflow-v0.0.1...hooks-git-workflow-v0.1.0) (2026-06-02)


### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
