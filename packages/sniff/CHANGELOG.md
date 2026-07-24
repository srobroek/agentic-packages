# Changelog

## [3.2.3](https://github.com/srobroek/agentic-packages/compare/sniff--v3.2.2...sniff--v3.2.3) (2026-07-24)


### Bug Fixes

* **agents:** open replies with the verdict token via imperative scaffold ([#697](https://github.com/srobroek/agentic-packages/issues/697)) ([64ce7aa](https://github.com/srobroek/agentic-packages/commit/64ce7aae82e1d69a2b7f0b8fd076c44f6cf768a1))

## [3.2.2](https://github.com/srobroek/agentic-packages/compare/sniff--v3.2.1...sniff--v3.2.2) (2026-07-24)


### Bug Fixes

* **agents:** verdict line is the literal first line — no preamble, no markdown emphasis ([#688](https://github.com/srobroek/agentic-packages/issues/688)) ([0cef5d6](https://github.com/srobroek/agentic-packages/commit/0cef5d6698a0ee7b5f3337ef993a4bf9fb653e9a))

## [3.2.1](https://github.com/srobroek/agentic-packages/compare/sniff--v3.2.0...sniff--v3.2.1) (2026-07-23)


### Bug Fixes

* **agents:** converge Claude effort and Codex reasoning_effort pins ([#663](https://github.com/srobroek/agentic-packages/issues/663)) ([9f149f2](https://github.com/srobroek/agentic-packages/commit/9f149f2cda79e819ce25b37e5eba2ffdd52fd115))

## [3.2.0](https://github.com/srobroek/agentic-packages/compare/sniff--v3.1.0...sniff--v3.2.0) (2026-07-21)


### Features

* **agents:** preserve model routing in workflow packages ([df86afc](https://github.com/srobroek/agentic-packages/commit/df86afc45f5c6da979e939aba1ed7f5fe2fcbc6a))

## [3.1.0](https://github.com/srobroek/agentic-packages/compare/sniff--v3.0.0...sniff--v3.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/sniff--v2.2.1...sniff--v3.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering

### Features

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering ([9cb202d](https://github.com/srobroek/agentic-packages/commit/9cb202d2b76a649dda0489baaeefd61a2e0829e1))


### Refactors

* **agentic:** replace sigil grammar with MUST/DEFAULT/ASK/NOT keywords throughout ([52a8958](https://github.com/srobroek/agentic-packages/commit/52a895874110733cc0f5f11197366659d3fe6074))
* **agents:** add output contracts + slim descriptions for coder, parallel-coder, pr-reviewer, adversarial-challenger, external-repo-worker, bloodhound, refactor-challenger ([193842f](https://github.com/srobroek/agentic-packages/commit/193842f10d79311bd8556334ea2702aabe98e9b8))

## [2.2.1](https://github.com/srobroek/agentic-packages/compare/sniff--v2.2.0...sniff--v2.2.1) (2026-06-28)


### Bug Fixes

* **sniff:** give every tool a complete run recipe (command, config, exit codes, gotchas) [skip tests] ([#413](https://github.com/srobroek/agentic-packages/issues/413)) ([fca782e](https://github.com/srobroek/agentic-packages/commit/fca782e9b81a1e76f786385b4af97471299c0345))

## [2.2.0](https://github.com/srobroek/agentic-packages/compare/sniff--v2.1.0...sniff--v2.2.0) (2026-06-28)


### Features

* **sniff:** complete tool catalog + propose-full-set selection model [skip tests] ([#411](https://github.com/srobroek/agentic-packages/issues/411)) ([99c8ea6](https://github.com/srobroek/agentic-packages/commit/99c8ea63ba7b273e5bccf0e4b5d4533d7d7f449c))

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/sniff--v2.0.1...sniff--v2.1.0) (2026-06-28)


### Features

* **sniff:** config-aware scanning, no double-run, user-adjustable fan-out [skip tests] ([#409](https://github.com/srobroek/agentic-packages/issues/409)) ([849fa80](https://github.com/srobroek/agentic-packages/commit/849fa80b3328a7b459f3178fa6ca352d6506ec46))

## [2.0.1](https://github.com/srobroek/agentic-packages/compare/sniff--v2.0.0...sniff--v2.0.1) (2026-06-28)


### Bug Fixes

* **sniff:** ask target kind then specifics, with the full kind list incl. language/area filter [skip tests] ([#407](https://github.com/srobroek/agentic-packages/issues/407)) ([38688ef](https://github.com/srobroek/agentic-packages/commit/38688ef601072b477b7b0cd979eda640ec843195))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/sniff--v1.1.0...sniff--v2.0.0) (2026-06-28)


### ⚠ BREAKING CHANGES

* rebuild sniff as a refactoring auditor across 21 languages ([#405](https://github.com/srobroek/agentic-packages/issues/405))

### Features

* rebuild sniff as a refactoring auditor across 21 languages ([#405](https://github.com/srobroek/agentic-packages/issues/405)) ([61e03ab](https://github.com/srobroek/agentic-packages/commit/61e03abb39d495575bc84a765227814c5c3d7111))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/sniff-v1.0.0...sniff--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/sniff-v0.1.2...sniff-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))

## [0.1.2](https://github.com/srobroek/agentic-packages/compare/sniff-v0.1.1...sniff-v0.1.2) (2026-06-12)


### Bug Fixes

* **sniff:** concrete trigger description, runtime-neutral sweep ([#293](https://github.com/srobroek/agentic-packages/issues/293)) ([411b7d8](https://github.com/srobroek/agentic-packages/commit/411b7d801c8a1881c9206ef4b9c84fb210b0b81f))

## [0.1.1](https://github.com/srobroek/agentic-packages/compare/sniff-v0.1.0...sniff-v0.1.1) (2026-06-03)


### Bug Fixes

* canonical .apm/ package layout + audit-steering rename + GH templates ([4b2a5d6](https://github.com/srobroek/agentic-packages/commit/4b2a5d6418b2f7607e873db464212cd1f711ae67))
* canonical .apm/ package layout, rename audit-steering, add GH templates [skip tests] ([c7692f2](https://github.com/srobroek/agentic-packages/commit/c7692f2d68e36ecc28b65b1400b7057f6a651c16))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/sniff-v0.0.1...sniff-v0.1.0) (2026-06-02)


### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* **packages:** add apm.yml to all skill/agent packages; drop category/tags from apm.yml [skip tests] ([722502e](https://github.com/srobroek/agentic-packages/commit/722502e84d74c7fa89d433294355355add2cd523))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **packages:** move skills and agents into own top-level packages [skip tests] ([c9ca8d1](https://github.com/srobroek/agentic-packages/commit/c9ca8d13a8dd52c3c90a077966fb3118edf1a189))
