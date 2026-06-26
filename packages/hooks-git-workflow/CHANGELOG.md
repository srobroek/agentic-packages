# Changelog

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
