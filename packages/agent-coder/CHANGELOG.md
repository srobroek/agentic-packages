# Changelog

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/agent-coder--v2.0.0...agent-coder--v2.1.0) (2026-07-05)


### Features

* continuous commit/push delivery cadence (steering-delivery package + agent/hook updates) ([#476](https://github.com/srobroek/agentic-packages/issues/476)) ([1f0534f](https://github.com/srobroek/agentic-packages/commit/1f0534f15b7b86952153feaacbbf3e2b9c8887c7))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/agent-coder--v1.2.0...agent-coder--v2.0.0) (2026-07-03)


### ⚠ BREAKING CHANGES

* enforce subagent isolation with a 3-token model (readonly/extern/direct) and primary-checkout deny gate ([#458](https://github.com/srobroek/agentic-packages/issues/458))

### Features

* enforce subagent isolation with a 3-token model (readonly/extern/direct) and primary-checkout deny gate ([#458](https://github.com/srobroek/agentic-packages/issues/458)) ([3cfc4c0](https://github.com/srobroek/agentic-packages/commit/3cfc4c060c75536319ae5ed57716b5190a4ad223))


### Bug Fixes

* **agents:** stop treating different-repo/direct-edit as isolation-free under concurrency ([#456](https://github.com/srobroek/agentic-packages/issues/456)) ([f4d0a21](https://github.com/srobroek/agentic-packages/commit/f4d0a21ae289f6554387ce0ad2cafb662b0d9c66))

## [1.2.0](https://github.com/srobroek/agentic-packages/compare/agent-coder--v1.1.0...agent-coder--v1.2.0) (2026-07-02)


### Features

* parallel-coder agent + per-language LSP packages ([#449](https://github.com/srobroek/agentic-packages/issues/449)) ([112c80d](https://github.com/srobroek/agentic-packages/commit/112c80d900549c81b72c065ac0c5556f74263f3f))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/agent-coder-v1.0.0...agent-coder--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/agent-coder-v0.1.1...agent-coder-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))


### Refactors

* tidy catalog metadata, dedup steering, fix dead tool references ([#375](https://github.com/srobroek/agentic-packages/issues/375)) ([2ed492c](https://github.com/srobroek/agentic-packages/commit/2ed492c632cf40a8c6cf269216e85021333d4db5))

## [0.1.1](https://github.com/srobroek/agentic-packages/compare/agent-coder-v0.1.0...agent-coder-v0.1.1) (2026-06-03)


### Bug Fixes

* canonical .apm/ package layout + audit-steering rename + GH templates ([4b2a5d6](https://github.com/srobroek/agentic-packages/commit/4b2a5d6418b2f7607e873db464212cd1f711ae67))
* canonical .apm/ package layout, rename audit-steering, add GH templates [skip tests] ([c7692f2](https://github.com/srobroek/agentic-packages/commit/c7692f2d68e36ecc28b65b1400b7057f6a651c16))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/agent-coder-v0.0.1...agent-coder-v0.1.0) (2026-06-02)


### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* **packages:** add apm.yml to all skill/agent packages; drop category/tags from apm.yml [skip tests] ([722502e](https://github.com/srobroek/agentic-packages/commit/722502e84d74c7fa89d433294355355add2cd523))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **packages:** move skills and agents into own top-level packages [skip tests] ([c9ca8d1](https://github.com/srobroek/agentic-packages/commit/c9ca8d13a8dd52c3c90a077966fb3118edf1a189))
