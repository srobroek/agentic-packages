# Changelog

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/agent-external-repo-worker--v2.2.2...agent-external-repo-worker--v3.0.0) (2026-07-27)


### ⚠ BREAKING CHANGES

* **agents:** `agent-coder` is now `agent-builder` and `agent-coder-high` is `agent-builder-high`. The agents `parallel-builder`, `worker`, `coder-high`, `domain-specialist-medium` and `domain-specialist-xhigh` no longer exist; use `builder` with an explicit mode, `builder-high`, or `domain-specialist{,-high}`. Spawn calls naming a removed agent must be updated.
* route every Codex agent to a benchmarked model tier ([#766](https://github.com/srobroek/agentic-packages/issues/766))

### Bug Fixes

* **agents:** pin every agent to a model, collapse duplicate tiers ([#771](https://github.com/srobroek/agentic-packages/issues/771)) ([fd8193f](https://github.com/srobroek/agentic-packages/commit/fd8193f6e1f8fb7a4bfcb889e24f4ccd5327a7f7))
* route every Codex agent to a benchmarked model tier ([#766](https://github.com/srobroek/agentic-packages/issues/766)) ([f8fb26a](https://github.com/srobroek/agentic-packages/commit/f8fb26aacaa45cbf7ab9ceaa42855089d34b6673))

## [2.2.2](https://github.com/srobroek/agentic-packages/compare/agent-external-repo-worker--v2.2.1...agent-external-repo-worker--v2.2.2) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [2.2.1](https://github.com/srobroek/agentic-packages/compare/agent-external-repo-worker--v2.2.0...agent-external-repo-worker--v2.2.1) (2026-07-23)


### Bug Fixes

* **agents:** harden isolation and delivery rules for delegated workers ([#657](https://github.com/srobroek/agentic-packages/issues/657)) ([956f6e1](https://github.com/srobroek/agentic-packages/commit/956f6e1615a484746023d8e63085d8f514b07bf7))

## [2.2.0](https://github.com/srobroek/agentic-packages/compare/agent-external-repo-worker--v2.1.0...agent-external-repo-worker--v2.2.0) (2026-07-21)


### Features

* **agents:** preserve model routing in workflow packages ([df86afc](https://github.com/srobroek/agentic-packages/commit/df86afc45f5c6da979e939aba1ed7f5fe2fcbc6a))

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/agent-external-repo-worker--v2.0.0...agent-external-repo-worker--v2.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/agent-external-repo-worker--v1.2.0...agent-external-repo-worker--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering

### Features

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering ([9cb202d](https://github.com/srobroek/agentic-packages/commit/9cb202d2b76a649dda0489baaeefd61a2e0829e1))


### Refactors

* **agentic:** replace sigil grammar with MUST/DEFAULT/ASK/NOT keywords throughout ([52a8958](https://github.com/srobroek/agentic-packages/commit/52a895874110733cc0f5f11197366659d3fe6074))
* **agents:** add output contracts + slim descriptions for coder, parallel-coder, pr-reviewer, adversarial-challenger, external-repo-worker, bloodhound, refactor-challenger ([193842f](https://github.com/srobroek/agentic-packages/commit/193842f10d79311bd8556334ea2702aabe98e9b8))

## [1.2.0](https://github.com/srobroek/agentic-packages/compare/agent-external-repo-worker--v1.1.1...agent-external-repo-worker--v1.2.0) (2026-07-05)


### Features

* continuous commit/push delivery cadence (steering-delivery package + agent/hook updates) ([#476](https://github.com/srobroek/agentic-packages/issues/476)) ([1f0534f](https://github.com/srobroek/agentic-packages/commit/1f0534f15b7b86952153feaacbbf3e2b9c8887c7))

## [1.1.1](https://github.com/srobroek/agentic-packages/compare/agent-external-repo-worker--v1.1.0...agent-external-repo-worker--v1.1.1) (2026-07-03)


### Bug Fixes

* **agents:** stop treating different-repo/direct-edit as isolation-free under concurrency ([#456](https://github.com/srobroek/agentic-packages/issues/456)) ([f4d0a21](https://github.com/srobroek/agentic-packages/commit/f4d0a21ae289f6554387ce0ad2cafb662b0d9c66))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/agent-external-repo-worker-v1.0.0...agent-external-repo-worker--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))


### Bug Fixes

* **agents:** drop abstract tools: so Claude grants a working toolset ([#402](https://github.com/srobroek/agentic-packages/issues/402)) ([564de79](https://github.com/srobroek/agentic-packages/commit/564de793da6858b7b697778da4560dda5084ef54))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/agent-external-repo-worker-v0.1.2...agent-external-repo-worker-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))

## [0.1.2](https://github.com/srobroek/agentic-packages/compare/agent-external-repo-worker-v0.1.1...agent-external-repo-worker-v0.1.2) (2026-06-12)


### Bug Fixes

* **agent-external-repo-worker:** bump Codex profile to gpt-5.5 ([#256](https://github.com/srobroek/agentic-packages/issues/256)) ([b5908b5](https://github.com/srobroek/agentic-packages/commit/b5908b5bad2833d564d842526a2b2151f3624cde))

## [0.1.1](https://github.com/srobroek/agentic-packages/compare/agent-external-repo-worker-v0.1.0...agent-external-repo-worker-v0.1.1) (2026-06-03)


### Bug Fixes

* canonical .apm/ package layout + audit-steering rename + GH templates ([4b2a5d6](https://github.com/srobroek/agentic-packages/commit/4b2a5d6418b2f7607e873db464212cd1f711ae67))
* canonical .apm/ package layout, rename audit-steering, add GH templates [skip tests] ([c7692f2](https://github.com/srobroek/agentic-packages/commit/c7692f2d68e36ecc28b65b1400b7057f6a651c16))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/agent-external-repo-worker-v0.0.1...agent-external-repo-worker-v0.1.0) (2026-06-02)


### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* **packages:** add apm.yml to all skill/agent packages; drop category/tags from apm.yml [skip tests] ([722502e](https://github.com/srobroek/agentic-packages/commit/722502e84d74c7fa89d433294355355add2cd523))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **packages:** move skills and agents into own top-level packages [skip tests] ([c9ca8d1](https://github.com/srobroek/agentic-packages/commit/c9ca8d13a8dd52c3c90a077966fb3118edf1a189))
