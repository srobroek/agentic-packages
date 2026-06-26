# Changelog

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
