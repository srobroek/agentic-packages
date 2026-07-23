# Changelog

## [3.2.1](https://github.com/srobroek/agentic-packages/compare/agent-adversarial-challenger--v3.2.0...agent-adversarial-challenger--v3.2.1) (2026-07-23)


### Bug Fixes

* **agents:** converge Claude effort and Codex reasoning_effort pins ([#663](https://github.com/srobroek/agentic-packages/issues/663)) ([9f149f2](https://github.com/srobroek/agentic-packages/commit/9f149f2cda79e819ce25b37e5eba2ffdd52fd115))

## [3.2.0](https://github.com/srobroek/agentic-packages/compare/agent-adversarial-challenger--v3.1.0...agent-adversarial-challenger--v3.2.0) (2026-07-21)


### Features

* **agents:** preserve model routing in workflow packages ([df86afc](https://github.com/srobroek/agentic-packages/commit/df86afc45f5c6da979e939aba1ed7f5fe2fcbc6a))

## [3.1.0](https://github.com/srobroek/agentic-packages/compare/agent-adversarial-challenger--v3.0.0...agent-adversarial-challenger--v3.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/agent-adversarial-challenger--v2.0.0...agent-adversarial-challenger--v3.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering

### Features

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering ([9cb202d](https://github.com/srobroek/agentic-packages/commit/9cb202d2b76a649dda0489baaeefd61a2e0829e1))


### Refactors

* **agentic:** replace sigil grammar with MUST/DEFAULT/ASK/NOT keywords throughout ([52a8958](https://github.com/srobroek/agentic-packages/commit/52a895874110733cc0f5f11197366659d3fe6074))
* **agents:** add output contracts + slim descriptions for coder, parallel-coder, pr-reviewer, adversarial-challenger, external-repo-worker, bloodhound, refactor-challenger ([193842f](https://github.com/srobroek/agentic-packages/commit/193842f10d79311bd8556334ea2702aabe98e9b8))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/agent-adversarial-challenger--v1.1.0...agent-adversarial-challenger--v2.0.0) (2026-07-02)


### ⚠ BREAKING CHANGES

* the `unstuck` package and the `debugging` bundle are removed. Anyone installing either must drop it; install agent-adversarial-challenger directly for the critic agent.

### Features

* retire the unstuck package and the debugging bundle ([#453](https://github.com/srobroek/agentic-packages/issues/453)) ([9c2c2eb](https://github.com/srobroek/agentic-packages/commit/9c2c2eb7a106158d1ccbb31b58e64c00ce4e872d))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/agent-adversarial-challenger-v1.0.0...agent-adversarial-challenger--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))


### Bug Fixes

* **agents:** drop abstract tools: so Claude grants a working toolset ([#402](https://github.com/srobroek/agentic-packages/issues/402)) ([564de79](https://github.com/srobroek/agentic-packages/commit/564de793da6858b7b697778da4560dda5084ef54))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/agent-adversarial-challenger-v0.2.0...agent-adversarial-challenger-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/agent-adversarial-challenger-v0.1.1...agent-adversarial-challenger-v0.2.0) (2026-06-09)


### Features

* **agent-adversarial-challenger:** generalize challenger beyond debugging ([4a0899c](https://github.com/srobroek/agentic-packages/commit/4a0899c48e8345a8f5917adf58f00ff4cf1adec0))
* **agent-adversarial-challenger:** generalize challenger beyond debugging [skip tests] ([d798ce3](https://github.com/srobroek/agentic-packages/commit/d798ce3491d3ac06a7b005c395bd1b71f90059a7))

## [0.1.1](https://github.com/srobroek/agentic-packages/compare/agent-adversarial-challenger-v0.1.0...agent-adversarial-challenger-v0.1.1) (2026-06-03)


### Bug Fixes

* canonical .apm/ package layout + audit-steering rename + GH templates ([4b2a5d6](https://github.com/srobroek/agentic-packages/commit/4b2a5d6418b2f7607e873db464212cd1f711ae67))
* canonical .apm/ package layout, rename audit-steering, add GH templates [skip tests] ([c7692f2](https://github.com/srobroek/agentic-packages/commit/c7692f2d68e36ecc28b65b1400b7057f6a651c16))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/agent-adversarial-challenger-v0.0.1...agent-adversarial-challenger-v0.1.0) (2026-06-02)


### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* **packages:** add apm.yml to all skill/agent packages; drop category/tags from apm.yml [skip tests] ([722502e](https://github.com/srobroek/agentic-packages/commit/722502e84d74c7fa89d433294355355add2cd523))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **packages:** move skills and agents into own top-level packages [skip tests] ([c9ca8d1](https://github.com/srobroek/agentic-packages/commit/c9ca8d13a8dd52c3c90a077966fb3118edf1a189))
