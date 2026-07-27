# Changelog

## [2.2.2](https://github.com/srobroek/agentic-packages/compare/hooks-git-safety--v2.2.1...hooks-git-safety--v2.2.2) (2026-07-27)


### Bug Fixes

* give every APM instruction an explicit applyTo, add drift guard ([#769](https://github.com/srobroek/agentic-packages/issues/769)) ([d983034](https://github.com/srobroek/agentic-packages/commit/d98303486d87b5dfb348a4a04fa435afa5fce692))

## [2.2.1](https://github.com/srobroek/agentic-packages/compare/hooks-git-safety--v2.2.0...hooks-git-safety--v2.2.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))


### Refactors

* move guidance into the scripts and contracts that enforce it ([#726](https://github.com/srobroek/agentic-packages/issues/726)) ([40bcfdf](https://github.com/srobroek/agentic-packages/commit/40bcfdf27cd6bbf72db02ce143482eac91d4a4cc))

## [2.2.0](https://github.com/srobroek/agentic-packages/compare/hooks-git-safety--v2.1.0...hooks-git-safety--v2.2.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/hooks-git-safety--v2.0.1...hooks-git-safety--v2.1.0) (2026-07-07)


### Features

* **hooks:** stable rule IDs for git-workflow, bash-safety, and git-safety guards ([#494](https://github.com/srobroek/agentic-packages/issues/494)) ([d46a50a](https://github.com/srobroek/agentic-packages/commit/d46a50ab266a706728455e127c906b87d73bba55))

## [2.0.1](https://github.com/srobroek/agentic-packages/compare/hooks-git-safety--v2.0.0...hooks-git-safety--v2.0.1) (2026-07-02)


### Performance

* **hooks:** cut PreToolUse:Bash hot-path cost with pre-jq bail + single-parse ([#450](https://github.com/srobroek/agentic-packages/issues/450)) ([58c1ce1](https://github.com/srobroek/agentic-packages/commit/58c1ce168e99ef1ac63427903c9180bf1ae916fe))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-git-safety--v1.3.0...hooks-git-safety--v2.0.0) (2026-06-30)


### ⚠ BREAKING CHANGES

* mcp-package-version no longer ships the package-file-warn or pkg-version-warn hooks. Installers that relied on those hooks should install hooks-package-file-guard / hooks-pkg-version-warn (or the dependency-quality bundle) instead.
* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* **hooks-git-safety:** soften destructive-op guards ([#337](https://github.com/srobroek/agentic-packages/issues/337)) ([f0f494a](https://github.com/srobroek/agentic-packages/commit/f0f494a7402d3ed6c86f8243261d533514302ccb))
* **hooks,steering:** add granular global guard hooks + pragmatic steering [skip tests] ([#248](https://github.com/srobroek/agentic-packages/issues/248)) ([11d60ed](https://github.com/srobroek/agentic-packages/commit/11d60ed5e9c4b342742e421995beebde7a157fa0))
* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))
* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))
* **speckit:** checklist-after-tasks reorder, memory-md default, agent-assign + hook fixes ([56ceefc](https://github.com/srobroek/agentic-packages/commit/56ceefc09ae0c8e2e2f46977478f188daeb4fa7a))
* split dependency tooling into independent packages + dependency-quality bundle ([#370](https://github.com/srobroek/agentic-packages/issues/370)) ([03d50a5](https://github.com/srobroek/agentic-packages/commit/03d50a5db3a1572fbe36a4ac1bc1e6877cd96ade))
* tighten autonomous-agent hook guards; add precommit-gate and close-keywords packages ([#391](https://github.com/srobroek/agentic-packages/issues/391)) ([34f155a](https://github.com/srobroek/agentic-packages/commit/34f155aab3ae1586b2ce16e2418a30a9d47b5137))


### Bug Fixes

* **hooks-git-safety:** drop obsolete gh-rate-guard hook [skip tests] ([7f36f18](https://github.com/srobroek/agentic-packages/commit/7f36f182ffd23b28c97a54e769cf7dafe580e653))
* **hooks-git-safety:** match git global options, fix false positives ([#274](https://github.com/srobroek/agentic-packages/issues/274)) ([abd5330](https://github.com/srobroek/agentic-packages/commit/abd5330324542d1ce58e78e6d01e86805a8f1a3e))
* **hooks:** rework PreToolUse guards to never stall auto mode ([#432](https://github.com/srobroek/agentic-packages/issues/432)) ([e00ebb7](https://github.com/srobroek/agentic-packages/commit/e00ebb723fd8e00031fdf28c02ca6b846053d652))
* **phase-1:** guard bypasses, bash-3.2/BSD portability, crashes, bundle pins + tests ([#360](https://github.com/srobroek/agentic-packages/issues/360)) ([b0c9106](https://github.com/srobroek/agentic-packages/commit/b0c91064313282a4265b9b0b8fb779f00afecd90))
* use installable package types so hooks + speckit resolve globally ([#387](https://github.com/srobroek/agentic-packages/issues/387)) ([ff2b7a2](https://github.com/srobroek/agentic-packages/commit/ff2b7a2200fc88bcf39abafe9f73ed6f5d31e942))

## [1.2.0](https://github.com/srobroek/agentic-packages/compare/hooks-git-safety-v1.1.0...hooks-git-safety--v1.2.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/hooks-git-safety-v1.0.1...hooks-git-safety-v1.1.0) (2026-06-26)


### Features

* tighten autonomous-agent hook guards; add precommit-gate and close-keywords packages ([#391](https://github.com/srobroek/agentic-packages/issues/391)) ([34f155a](https://github.com/srobroek/agentic-packages/commit/34f155aab3ae1586b2ce16e2418a30a9d47b5137))

## [1.0.1](https://github.com/srobroek/agentic-packages/compare/hooks-git-safety-v1.0.0...hooks-git-safety-v1.0.1) (2026-06-26)


### Bug Fixes

* use installable package types so hooks + speckit resolve globally ([#387](https://github.com/srobroek/agentic-packages/issues/387)) ([ff2b7a2](https://github.com/srobroek/agentic-packages/commit/ff2b7a2200fc88bcf39abafe9f73ed6f5d31e942))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-git-safety-v0.4.0...hooks-git-safety-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* mcp-package-version no longer ships the package-file-warn or pkg-version-warn hooks. Installers that relied on those hooks should install hooks-package-file-guard / hooks-pkg-version-warn (or the dependency-quality bundle) instead.
* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))
* split dependency tooling into independent packages + dependency-quality bundle ([#370](https://github.com/srobroek/agentic-packages/issues/370)) ([03d50a5](https://github.com/srobroek/agentic-packages/commit/03d50a5db3a1572fbe36a4ac1bc1e6877cd96ade))


### Bug Fixes

* **phase-1:** guard bypasses, bash-3.2/BSD portability, crashes, bundle pins + tests ([#360](https://github.com/srobroek/agentic-packages/issues/360)) ([b0c9106](https://github.com/srobroek/agentic-packages/commit/b0c91064313282a4265b9b0b8fb779f00afecd90))

## [0.4.0](https://github.com/srobroek/agentic-packages/compare/hooks-git-safety-v0.3.0...hooks-git-safety-v0.4.0) (2026-06-24)


### Features

* **speckit:** checklist-after-tasks reorder, memory-md default, agent-assign + hook fixes ([56ceefc](https://github.com/srobroek/agentic-packages/commit/56ceefc09ae0c8e2e2f46977478f188daeb4fa7a))


### Bug Fixes

* **hooks-git-safety:** drop obsolete gh-rate-guard hook [skip tests] ([7f36f18](https://github.com/srobroek/agentic-packages/commit/7f36f182ffd23b28c97a54e769cf7dafe580e653))

## [0.3.0](https://github.com/srobroek/agentic-packages/compare/hooks-git-safety-v0.2.1...hooks-git-safety-v0.3.0) (2026-06-20)


### Features

* **hooks-git-safety:** soften destructive-op guards ([#337](https://github.com/srobroek/agentic-packages/issues/337)) ([f0f494a](https://github.com/srobroek/agentic-packages/commit/f0f494a7402d3ed6c86f8243261d533514302ccb))

## [0.2.1](https://github.com/srobroek/agentic-packages/compare/hooks-git-safety-v0.2.0...hooks-git-safety-v0.2.1) (2026-06-12)


### Bug Fixes

* **hooks-git-safety:** match git global options, fix false positives ([#274](https://github.com/srobroek/agentic-packages/issues/274)) ([abd5330](https://github.com/srobroek/agentic-packages/commit/abd5330324542d1ce58e78e6d01e86805a8f1a3e))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/hooks-git-safety-v0.1.0...hooks-git-safety-v0.2.0) (2026-06-04)


### Features

* **hooks,steering:** add granular global guard hooks + pragmatic steering [skip tests] ([#248](https://github.com/srobroek/agentic-packages/issues/248)) ([11d60ed](https://github.com/srobroek/agentic-packages/commit/11d60ed5e9c4b342742e421995beebde7a157fa0))
