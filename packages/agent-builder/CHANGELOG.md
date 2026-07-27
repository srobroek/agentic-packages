# Changelog

## [7.0.2](https://github.com/srobroek/agentic-packages/compare/agent-coder--v7.0.1...agent-coder--v7.0.2) (2026-07-25)


### Refactors

* cut duplicated rules from steering, agents and skills ([#728](https://github.com/srobroek/agentic-packages/issues/728)) ([8f892aa](https://github.com/srobroek/agentic-packages/commit/8f892aa01b3b0ffbb5888cca0dc4178d57ee967d))

## [7.0.1](https://github.com/srobroek/agentic-packages/compare/agent-coder--v7.0.0...agent-coder--v7.0.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [7.0.0](https://github.com/srobroek/agentic-packages/compare/agent-coder--v6.1.3...agent-coder--v7.0.0) (2026-07-25)


### ⚠ BREAKING CHANGES

* **orchestrate:** subagent_type 'coder' -> 'builder', 'parallel-coder' -> 'parallel-builder'. Update any spawn calls referencing the old names.

### Bug Fixes

* **orchestrate:** restore domain-specialist; rename coder-&gt;builder ([#715](https://github.com/srobroek/agentic-packages/issues/715)) ([223e0c9](https://github.com/srobroek/agentic-packages/commit/223e0c95cb8dee08d1f3cd00cd96cb598d78d24e))

## [6.1.3](https://github.com/srobroek/agentic-packages/compare/agent-coder--v6.1.2...agent-coder--v6.1.3) (2026-07-23)


### Bug Fixes

* **agents:** converge Claude effort and Codex reasoning_effort pins ([#663](https://github.com/srobroek/agentic-packages/issues/663)) ([9f149f2](https://github.com/srobroek/agentic-packages/commit/9f149f2cda79e819ce25b37e5eba2ffdd52fd115))

## [6.1.2](https://github.com/srobroek/agentic-packages/compare/agent-coder--v6.1.1...agent-coder--v6.1.2) (2026-07-23)


### Bug Fixes

* **agents:** harden isolation and delivery rules for delegated workers ([#657](https://github.com/srobroek/agentic-packages/issues/657)) ([956f6e1](https://github.com/srobroek/agentic-packages/commit/956f6e1615a484746023d8e63085d8f514b07bf7))

## [6.1.1](https://github.com/srobroek/agentic-packages/compare/agent-coder--v6.1.0...agent-coder--v6.1.1) (2026-07-22)


### Bug Fixes

* route agent code discovery through Serena ([bf9593c](https://github.com/srobroek/agentic-packages/commit/bf9593c14f5d486af11f2d364e8d5dd66d3b0306))

## [6.1.0](https://github.com/srobroek/agentic-packages/compare/agent-coder--v6.0.0...agent-coder--v6.1.0) (2026-07-21)


### Features

* **agents:** preserve model routing in workflow packages ([df86afc](https://github.com/srobroek/agentic-packages/commit/df86afc45f5c6da979e939aba1ed7f5fe2fcbc6a))

## [6.0.0](https://github.com/srobroek/agentic-packages/compare/agent-coder--v5.0.0...agent-coder--v6.0.0) (2026-07-21)


### ⚠ BREAKING CHANGES

* **speckit:** remove noisy stop hooks ([#574](https://github.com/srobroek/agentic-packages/issues/574))

### Features

* **speckit:** remove noisy stop hooks ([#574](https://github.com/srobroek/agentic-packages/issues/574)) ([7637119](https://github.com/srobroek/agentic-packages/commit/76371191da9da679e92c99d3b8b6a6b3817065d7))

## [5.0.0](https://github.com/srobroek/agentic-packages/compare/agent-coder--v4.1.0...agent-coder--v5.0.0) (2026-07-21)


### ⚠ BREAKING CHANGES

* share MCP backends through 1MCP

### Features

* share MCP backends through 1MCP ([4896601](https://github.com/srobroek/agentic-packages/commit/4896601ca0326762493f340526a97a341b98e24a))

## [4.1.0](https://github.com/srobroek/agentic-packages/compare/agent-coder--v4.0.0...agent-coder--v4.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [4.0.0](https://github.com/srobroek/agentic-packages/compare/agent-coder--v3.0.0...agent-coder--v4.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* code-economy rule overhaul — OVERRIDE, YAGNI section, hand-roll pricing, haiku routing guard ([#496](https://github.com/srobroek/agentic-packages/issues/496))

### Features

* code-economy rule overhaul — OVERRIDE, YAGNI section, hand-roll pricing, haiku routing guard ([#496](https://github.com/srobroek/agentic-packages/issues/496)) ([954025f](https://github.com/srobroek/agentic-packages/commit/954025fd2514453cf3c5bc1fecd8678be5b75258))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/agent-coder--v2.1.0...agent-coder--v3.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* **agent-coder:** harden YAGNI rule against growth-bait; tighten parallel-coder output contract
* **steering:** code-economy to keyword convention; restore dropped ladder steps; exact-output coder contracts
* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering
* **hooks:** tier-gate the coder nudge; drop push test-gate and discovery steer

### Features

* **hooks:** tier-gate the coder nudge; drop push test-gate and discovery steer ([786988a](https://github.com/srobroek/agentic-packages/commit/786988af6a80f3afe31e8763e1077e4a30e61920))
* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering ([9cb202d](https://github.com/srobroek/agentic-packages/commit/9cb202d2b76a649dda0489baaeefd61a2e0829e1))


### Bug Fixes

* **agent-coder:** harden YAGNI rule against growth-bait; tighten parallel-coder output contract ([81fe444](https://github.com/srobroek/agentic-packages/commit/81fe444df97c4817f68afd772cf3d515ee1d3c5e))
* **agent-coder:** quote-free YAGNI phrasing — embedded quotes broke inject-script JSON ([bbce701](https://github.com/srobroek/agentic-packages/commit/bbce701d7296e46148861807056793ba06770b82))
* **steering:** code-economy to keyword convention; restore dropped ladder steps; exact-output coder contracts ([30bf4c8](https://github.com/srobroek/agentic-packages/commit/30bf4c8e8f84ad332b0be62767f0b0e427549487))


### Refactors

* **agentic:** replace sigil grammar with MUST/DEFAULT/ASK/NOT keywords throughout ([52a8958](https://github.com/srobroek/agentic-packages/commit/52a895874110733cc0f5f11197366659d3fe6074))
* **agents:** add output contracts + slim descriptions for coder, parallel-coder, pr-reviewer, adversarial-challenger, external-repo-worker, bloodhound, refactor-challenger ([193842f](https://github.com/srobroek/agentic-packages/commit/193842f10d79311bd8556334ea2702aabe98e9b8))

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
