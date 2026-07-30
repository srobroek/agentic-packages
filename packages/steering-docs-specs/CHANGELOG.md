# Changelog

## [4.0.1](https://github.com/srobroek/agentic-packages/compare/steering-docs-specs--v4.0.0...steering-docs-specs--v4.0.1) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [4.0.0](https://github.com/srobroek/agentic-packages/compare/steering-docs-specs--v3.1.1...steering-docs-specs--v4.0.0) (2026-07-27)


### ⚠ BREAKING CHANGES

* move write-docs to its own repo, srobroek/slopvac ([#780](https://github.com/srobroek/agentic-packages/issues/780))

### Refactors

* move write-docs to its own repo, srobroek/slopvac ([#780](https://github.com/srobroek/agentic-packages/issues/780)) ([3a8fd27](https://github.com/srobroek/agentic-packages/commit/3a8fd27dab5a5692ee0e669ca7942584355ec939))

## [3.1.1](https://github.com/srobroek/agentic-packages/compare/steering-docs-specs--v3.1.0...steering-docs-specs--v3.1.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [3.1.0](https://github.com/srobroek/agentic-packages/compare/steering-docs-specs--v3.0.0...steering-docs-specs--v3.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/steering-docs-specs--v2.0.0...steering-docs-specs--v3.0.0) (2026-07-11)


### ⚠ BREAKING CHANGES

* docs-specs.project-docs.context.md is removed; installs relying on markdown-wide doc-style steering must add the write-docs package.

### Features

* **steering:** write for the released, steady-state artifact ([#520](https://github.com/srobroek/agentic-packages/issues/520)) ([1ff9046](https://github.com/srobroek/agentic-packages/commit/1ff904647e620b8084a3219b4824df1d82ec3ff6))
* write-docs skill for slop-free, release-focused documentation ([#522](https://github.com/srobroek/agentic-packages/issues/522)) ([3d874b8](https://github.com/srobroek/agentic-packages/commit/3d874b86d9379322ebaeb4ebea3b9e3f7f4bb30c))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/steering-docs-specs--v1.1.0...steering-docs-specs--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* **steering:** Wave 4 steering rewrites — pragmatic, code-economy, dedup, language compression, orchestrate fixes

### Features

* **steering:** Wave 4 steering rewrites — pragmatic, code-economy, dedup, language compression, orchestrate fixes ([1412eaf](https://github.com/srobroek/agentic-packages/commit/1412eafea2ec018655d73d353337feb918dd27f0))


### Refactors

* **steering:** dedup steering pairs and convert to delegate/table form ([8cebd5b](https://github.com/srobroek/agentic-packages/commit/8cebd5b4667ff0a9dfb2cf75e3c34a5d5c88120e))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/steering-docs-specs-v1.0.0...steering-docs-specs--v1.1.0) (2026-07-02)


### Features

* **steering-docs-specs:** shipped docs describe current behavior only ([#454](https://github.com/srobroek/agentic-packages/issues/454)) ([887b5b5](https://github.com/srobroek/agentic-packages/commit/887b5b5cb2d59982e170115278e1e058030ee898))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/steering-docs-specs-v0.1.1...steering-docs-specs-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))

## [0.1.1](https://github.com/srobroek/agentic-packages/compare/steering-docs-specs-v0.1.0...steering-docs-specs-v0.1.1) (2026-06-12)


### Bug Fixes

* **steering-docs-specs:** state SpecKit is opt-in per project ([#296](https://github.com/srobroek/agentic-packages/issues/296)) ([70ac232](https://github.com/srobroek/agentic-packages/commit/70ac2327bb2b9fcc097a3ddc24013a8aaff3096b))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/steering-docs-specs-v0.0.1...steering-docs-specs-v0.1.0) (2026-06-02)


### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* **packages:** add apm.yml to all skill/agent packages; drop category/tags from apm.yml [skip tests] ([722502e](https://github.com/srobroek/agentic-packages/commit/722502e84d74c7fa89d433294355355add2cd523))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **steering:** split domain steering into 6 opt-in packages [skip tests] ([6e610f8](https://github.com/srobroek/agentic-packages/commit/6e610f8fd2acae6dec5ff15757d02fa0d26c06e8))
