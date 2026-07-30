# Changelog

## [2.1.2](https://github.com/srobroek/agentic-packages/compare/matt-skills--v2.1.1...matt-skills--v2.1.2) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [2.1.1](https://github.com/srobroek/agentic-packages/compare/matt-skills--v2.1.0...matt-skills--v2.1.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/matt-skills--v2.0.0...matt-skills--v2.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/matt-skills--v1.1.0...matt-skills--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* pin all external #main refs to SHAs; internal subpath refs to semver ranges
* **bundles:** drop wshobson c4/code-documentation/documentation-generation; grill-me -> grilling

### Features

* **bundles:** drop wshobson c4/code-documentation/documentation-generation; grill-me -&gt; grilling ([942047e](https://github.com/srobroek/agentic-packages/commit/942047e6096485590d68a3fd18f30cb95b31e9e9))


### Chores

* pin all external #main refs to SHAs; internal subpath refs to semver ranges ([7b32fc1](https://github.com/srobroek/agentic-packages/commit/7b32fc13d3eb75710e7c40beb2d30672d0d9dc02))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/matt-skills-v1.0.0...matt-skills--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/matt-skills-v0.1.1...matt-skills-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))

## [0.1.1](https://github.com/srobroek/agentic-packages/compare/matt-skills-v0.1.0...matt-skills-v0.1.1) (2026-06-20)


### Bug Fixes

* **core:** remove dead mattpocock skill references ([5c02f5d](https://github.com/srobroek/agentic-packages/commit/5c02f5db3934e4160dd4f0035966d8784395af1a))
* **core:** remove dead mattpocock skill references ([f584488](https://github.com/srobroek/agentic-packages/commit/f5844883cc1671e1a562335610233c8d422f0fc9))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/matt-skills-v0.0.1...matt-skills-v0.1.0) (2026-06-02)


### Features

* **marketplace:** hand-authored local-path marketplace + apm pack outputs; drop dead packages [skip tests] ([ed11c25](https://github.com/srobroek/agentic-packages/commit/ed11c25cc54b9b31c41864f5d6ca24069c0588c8))
* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
