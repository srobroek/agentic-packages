# Changelog

## [5.0.1](https://github.com/srobroek/agentic-packages/compare/hooks-bash-safety--v5.0.0...hooks-bash-safety--v5.0.1) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [5.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-bash-safety--v4.0.0...hooks-bash-safety--v5.0.0) (2026-07-30)


### ⚠ BREAKING CHANGES

* the hooks-worktree and mcp-1mcp packages are removed. Worktree lifecycle and cleanup are owned by hooks-worktrunk, which requires the wt binary; 1mcp has no replacement because nothing used it.

### Bug Fixes

* close two guard bypasses found by fuzzing the Python hooks ([#806](https://github.com/srobroek/agentic-packages/issues/806)) ([7505cc7](https://github.com/srobroek/agentic-packages/commit/7505cc76fccad74c1ba0c5d2d017320b721475ff))

## [4.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-bash-safety--v3.0.0...hooks-bash-safety--v4.0.0) (2026-07-28)


### ⚠ BREAKING CHANGES

* commands that previously passed silently are now judged. A destructive verb inside an inline shell string, or behind timeout, flock, or nice with an option value, is denied where it was allowed, and a download piped to any interpreter now warns.
* **steering-git-workflow:** the hook script is now attribution-guard.py and requires python3 on PATH.

### Bug Fixes

* **steering-git-workflow:** stop blocking pull requests when the policy check cannot verify them ([#794](https://github.com/srobroek/agentic-packages/issues/794)) ([023c0f0](https://github.com/srobroek/agentic-packages/commit/023c0f087717a57386d18d06f2575fca0435b7b1))
* stop the hook guards blocking correct work, and close the wrapper bypasses ([#796](https://github.com/srobroek/agentic-packages/issues/796)) ([217a455](https://github.com/srobroek/agentic-packages/commit/217a4559fe3d0be9fb2751ffbefd41dfe8903f0d))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-bash-safety--v2.2.2...hooks-bash-safety--v3.0.0) (2026-07-28)


### ⚠ BREAKING CHANGES

* **hooks-bash-safety:** agentic-source-guard no longer runs; edits to agentic source files are no longer hook-gated.

### Bug Fixes

* **hooks-bash-safety:** block rm -rf that a leading cd redirects to a system path ([#788](https://github.com/srobroek/agentic-packages/issues/788)) ([34bfd74](https://github.com/srobroek/agentic-packages/commit/34bfd74cf22648d223e2c76f1d073ff7987787a8))

## [2.2.2](https://github.com/srobroek/agentic-packages/compare/hooks-bash-safety--v2.2.1...hooks-bash-safety--v2.2.2) (2026-07-27)


### Bug Fixes

* give every APM instruction an explicit applyTo, add drift guard ([#769](https://github.com/srobroek/agentic-packages/issues/769)) ([d983034](https://github.com/srobroek/agentic-packages/commit/d98303486d87b5dfb348a4a04fa435afa5fce692))

## [2.2.1](https://github.com/srobroek/agentic-packages/compare/hooks-bash-safety--v2.2.0...hooks-bash-safety--v2.2.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))
* close three guard bypasses and eight broken agent references ([#722](https://github.com/srobroek/agentic-packages/issues/722)) ([cbc6875](https://github.com/srobroek/agentic-packages/commit/cbc6875f53b3b048f4fe882bad69305a04e47bc3))


### Refactors

* move guidance into the scripts and contracts that enforce it ([#726](https://github.com/srobroek/agentic-packages/issues/726)) ([40bcfdf](https://github.com/srobroek/agentic-packages/commit/40bcfdf27cd6bbf72db02ce143482eac91d4a4cc))

## [2.2.0](https://github.com/srobroek/agentic-packages/compare/hooks-bash-safety--v2.1.0...hooks-bash-safety--v2.2.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/hooks-bash-safety--v2.0.1...hooks-bash-safety--v2.1.0) (2026-07-07)


### Features

* **hooks:** stable rule IDs for git-workflow, bash-safety, and git-safety guards ([#494](https://github.com/srobroek/agentic-packages/issues/494)) ([d46a50a](https://github.com/srobroek/agentic-packages/commit/d46a50ab266a706728455e127c906b87d73bba55))

## [2.0.1](https://github.com/srobroek/agentic-packages/compare/hooks-bash-safety--v2.0.0...hooks-bash-safety--v2.0.1) (2026-07-02)


### Performance

* **hooks:** cut PreToolUse:Bash hot-path cost with pre-jq bail + single-parse ([#450](https://github.com/srobroek/agentic-packages/issues/450)) ([58c1ce1](https://github.com/srobroek/agentic-packages/commit/58c1ce168e99ef1ac63427903c9180bf1ae916fe))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-bash-safety--v1.3.0...hooks-bash-safety--v2.0.0) (2026-06-30)


### ⚠ BREAKING CHANGES

* mcp-package-version no longer ships the package-file-warn or pkg-version-warn hooks. Installers that relied on those hooks should install hooks-package-file-guard / hooks-pkg-version-warn (or the dependency-quality bundle) instead.
* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* **hooks,steering:** add granular global guard hooks + pragmatic steering [skip tests] ([#248](https://github.com/srobroek/agentic-packages/issues/248)) ([11d60ed](https://github.com/srobroek/agentic-packages/commit/11d60ed5e9c4b342742e421995beebde7a157fa0))
* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))
* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))
* split dependency tooling into independent packages + dependency-quality bundle ([#370](https://github.com/srobroek/agentic-packages/issues/370)) ([03d50a5](https://github.com/srobroek/agentic-packages/commit/03d50a5db3a1572fbe36a4ac1bc1e6877cd96ade))
* tighten autonomous-agent hook guards; add precommit-gate and close-keywords packages ([#391](https://github.com/srobroek/agentic-packages/issues/391)) ([34f155a](https://github.com/srobroek/agentic-packages/commit/34f155aab3ae1586b2ce16e2418a30a9d47b5137))


### Bug Fixes

* **hooks-bash-safety:** catch combined rm flags and check all targets ([#272](https://github.com/srobroek/agentic-packages/issues/272)) ([8096d34](https://github.com/srobroek/agentic-packages/commit/8096d3429317e287b2c3b9388bbeabe260a86ef9))
* **hooks:** rework PreToolUse guards to never stall auto mode ([#432](https://github.com/srobroek/agentic-packages/issues/432)) ([e00ebb7](https://github.com/srobroek/agentic-packages/commit/e00ebb723fd8e00031fdf28c02ca6b846053d652))
* **phase-1:** guard bypasses, bash-3.2/BSD portability, crashes, bundle pins + tests ([#360](https://github.com/srobroek/agentic-packages/issues/360)) ([b0c9106](https://github.com/srobroek/agentic-packages/commit/b0c91064313282a4265b9b0b8fb779f00afecd90))
* use installable package types so hooks + speckit resolve globally ([#387](https://github.com/srobroek/agentic-packages/issues/387)) ([ff2b7a2](https://github.com/srobroek/agentic-packages/commit/ff2b7a2200fc88bcf39abafe9f73ed6f5d31e942))

## [1.2.0](https://github.com/srobroek/agentic-packages/compare/hooks-bash-safety-v1.1.0...hooks-bash-safety--v1.2.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/hooks-bash-safety-v1.0.1...hooks-bash-safety-v1.1.0) (2026-06-26)


### Features

* tighten autonomous-agent hook guards; add precommit-gate and close-keywords packages ([#391](https://github.com/srobroek/agentic-packages/issues/391)) ([34f155a](https://github.com/srobroek/agentic-packages/commit/34f155aab3ae1586b2ce16e2418a30a9d47b5137))

## [1.0.1](https://github.com/srobroek/agentic-packages/compare/hooks-bash-safety-v1.0.0...hooks-bash-safety-v1.0.1) (2026-06-26)


### Bug Fixes

* use installable package types so hooks + speckit resolve globally ([#387](https://github.com/srobroek/agentic-packages/issues/387)) ([ff2b7a2](https://github.com/srobroek/agentic-packages/commit/ff2b7a2200fc88bcf39abafe9f73ed6f5d31e942))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-bash-safety-v0.2.1...hooks-bash-safety-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* mcp-package-version no longer ships the package-file-warn or pkg-version-warn hooks. Installers that relied on those hooks should install hooks-package-file-guard / hooks-pkg-version-warn (or the dependency-quality bundle) instead.
* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))
* split dependency tooling into independent packages + dependency-quality bundle ([#370](https://github.com/srobroek/agentic-packages/issues/370)) ([03d50a5](https://github.com/srobroek/agentic-packages/commit/03d50a5db3a1572fbe36a4ac1bc1e6877cd96ade))


### Bug Fixes

* **phase-1:** guard bypasses, bash-3.2/BSD portability, crashes, bundle pins + tests ([#360](https://github.com/srobroek/agentic-packages/issues/360)) ([b0c9106](https://github.com/srobroek/agentic-packages/commit/b0c91064313282a4265b9b0b8fb779f00afecd90))

## [0.2.1](https://github.com/srobroek/agentic-packages/compare/hooks-bash-safety-v0.2.0...hooks-bash-safety-v0.2.1) (2026-06-12)


### Bug Fixes

* **hooks-bash-safety:** catch combined rm flags and check all targets ([#272](https://github.com/srobroek/agentic-packages/issues/272)) ([8096d34](https://github.com/srobroek/agentic-packages/commit/8096d3429317e287b2c3b9388bbeabe260a86ef9))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/hooks-bash-safety-v0.1.0...hooks-bash-safety-v0.2.0) (2026-06-04)


### Features

* **hooks,steering:** add granular global guard hooks + pragmatic steering [skip tests] ([#248](https://github.com/srobroek/agentic-packages/issues/248)) ([11d60ed](https://github.com/srobroek/agentic-packages/commit/11d60ed5e9c4b342742e421995beebde7a157fa0))
