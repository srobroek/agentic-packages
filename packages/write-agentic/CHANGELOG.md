# Changelog

## [5.0.0](https://github.com/srobroek/agentic-packages/compare/write-agentic--v4.0.1...write-agentic--v5.0.0) (2026-07-30)


### ⚠ BREAKING CHANGES

* **steering-pragmatic:** move conversational register to a Claude output style ([#814](https://github.com/srobroek/agentic-packages/issues/814))

### Refactors

* **steering-pragmatic:** move conversational register to a Claude output style ([#814](https://github.com/srobroek/agentic-packages/issues/814)) ([aea023b](https://github.com/srobroek/agentic-packages/commit/aea023bba47a18a87ee1d366e9c1d7e54470b9b4))

## [4.0.1](https://github.com/srobroek/agentic-packages/compare/write-agentic--v4.0.0...write-agentic--v4.0.1) (2026-07-25)


### Refactors

* cut duplicated rules from steering, agents and skills ([#728](https://github.com/srobroek/agentic-packages/issues/728)) ([8f892aa](https://github.com/srobroek/agentic-packages/commit/8f892aa01b3b0ffbb5888cca0dc4178d57ee967d))

## [4.0.0](https://github.com/srobroek/agentic-packages/compare/write-agentic--v3.4.0...write-agentic--v4.0.0) (2026-07-25)


### ⚠ BREAKING CHANGES

* **write-docs:** requires the vale binary on PATH (mise use -g vale, or brew install vale). Suppression syntax changes from <!-- write-docs:allow E2 --> to Vale's <!-- vale WriteDocs.SlopLexicon = NO --> off/on pairs, which are block-scoped rather than line-scoped.

### Features

* **write-docs:** check documentation prose with Vale instead of a bespoke linter ([#721](https://github.com/srobroek/agentic-packages/issues/721)) ([43fc7f7](https://github.com/srobroek/agentic-packages/commit/43fc7f766c6f4a9c6317a71f18ba33ff3fbf507c))


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [3.4.0](https://github.com/srobroek/agentic-packages/compare/write-agentic--v3.3.3...write-agentic--v3.4.0) (2026-07-25)


### Features

* **orchestrate:** bead-as-brief v2 — claim-bound contracts, delegation-first fleet, cache policy ([#713](https://github.com/srobroek/agentic-packages/issues/713)) ([e8deb15](https://github.com/srobroek/agentic-packages/commit/e8deb151d222e843e9bc80fc6808c9acc141124f))

## [3.3.3](https://github.com/srobroek/agentic-packages/compare/write-agentic--v3.3.2...write-agentic--v3.3.3) (2026-07-24)


### Bug Fixes

* **agents:** scan agents draft in working turns and compose the report in one pass ([#701](https://github.com/srobroek/agentic-packages/issues/701)) ([bf85043](https://github.com/srobroek/agentic-packages/commit/bf850438e20baea869e654a65a985f5257b58e97))

## [3.3.2](https://github.com/srobroek/agentic-packages/compare/write-agentic--v3.3.1...write-agentic--v3.3.2) (2026-07-24)


### Bug Fixes

* **agents:** open replies with the verdict token via imperative scaffold ([#697](https://github.com/srobroek/agentic-packages/issues/697)) ([64ce7aa](https://github.com/srobroek/agentic-packages/commit/64ce7aae82e1d69a2b7f0b8fd076c44f6cf768a1))

## [3.3.1](https://github.com/srobroek/agentic-packages/compare/write-agentic--v3.3.0...write-agentic--v3.3.1) (2026-07-24)


### Bug Fixes

* **agents:** verdict line is the literal first line — no preamble, no markdown emphasis ([#688](https://github.com/srobroek/agentic-packages/issues/688)) ([0cef5d6](https://github.com/srobroek/agentic-packages/commit/0cef5d6698a0ee7b5f3337ef993a4bf9fb653e9a))

## [3.3.0](https://github.com/srobroek/agentic-packages/compare/write-agentic--v3.2.0...write-agentic--v3.3.0) (2026-07-23)


### Features

* agent linter catches empty descriptions, over-constraint, missing triggers, and bloat ([#672](https://github.com/srobroek/agentic-packages/issues/672)) ([47feb78](https://github.com/srobroek/agentic-packages/commit/47feb78421542944aa0f1ee7947e1b3ebab0f08d))

## [3.2.0](https://github.com/srobroek/agentic-packages/compare/write-agentic--v3.1.0...write-agentic--v3.2.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [3.1.0](https://github.com/srobroek/agentic-packages/compare/write-agentic--v3.0.0...write-agentic--v3.1.0) (2026-07-07)


### Features

* **write-agentic:** add per-file x-lint override mechanism with E9 guard ([#497](https://github.com/srobroek/agentic-packages/issues/497)) ([f5c90b9](https://github.com/srobroek/agentic-packages/commit/f5c90b9e77ae6ba3ea19205e8de57344846ae521))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/write-agentic--v2.0.0...write-agentic--v3.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering
* **write-agentic:** package renamed write-a-skill -> write-agentic; referencing bundles updated.

### Features

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering ([9cb202d](https://github.com/srobroek/agentic-packages/commit/9cb202d2b76a649dda0489baaeefd61a2e0829e1))
* **write-agentic:** generalize write-a-skill to all agentic assets, add lint ([ff5df7a](https://github.com/srobroek/agentic-packages/commit/ff5df7a6614906c669eac40f8bc05c0ee55257cd))


### Refactors

* **agentic:** replace sigil grammar with MUST/DEFAULT/ASK/NOT keywords throughout ([52a8958](https://github.com/srobroek/agentic-packages/commit/52a895874110733cc0f5f11197366659d3fe6074))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/write-a-skill-v1.0.0...write-a-skill--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/write-a-skill-v0.1.2...write-a-skill-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))

## [0.1.2](https://github.com/srobroek/agentic-packages/compare/write-a-skill-v0.1.1...write-a-skill-v0.1.2) (2026-06-12)


### Bug Fixes

* **write-a-skill:** add expected layout example ([#303](https://github.com/srobroek/agentic-packages/issues/303)) ([f173b4b](https://github.com/srobroek/agentic-packages/commit/f173b4b2ca8c4fdaf90054914b3cf17bcfbbd721))

## [0.1.1](https://github.com/srobroek/agentic-packages/compare/write-a-skill-v0.1.0...write-a-skill-v0.1.1) (2026-06-03)


### Bug Fixes

* canonical .apm/ package layout + audit-steering rename + GH templates ([4b2a5d6](https://github.com/srobroek/agentic-packages/commit/4b2a5d6418b2f7607e873db464212cd1f711ae67))
* canonical .apm/ package layout, rename audit-steering, add GH templates [skip tests] ([c7692f2](https://github.com/srobroek/agentic-packages/commit/c7692f2d68e36ecc28b65b1400b7057f6a651c16))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/write-a-skill-v0.0.1...write-a-skill-v0.1.0) (2026-06-02)


### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* **packages:** add apm.yml to all skill/agent packages; drop category/tags from apm.yml [skip tests] ([722502e](https://github.com/srobroek/agentic-packages/commit/722502e84d74c7fa89d433294355355add2cd523))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **packages:** move skills and agents into own top-level packages [skip tests] ([c9ca8d1](https://github.com/srobroek/agentic-packages/commit/c9ca8d13a8dd52c3c90a077966fb3118edf1a189))


### Documentation

* de-personalize, LOAD convention, README + inventory rewrite [skip tests] ([adf8e21](https://github.com/srobroek/agentic-packages/commit/adf8e210ff5721dd198f7c07f0022910af812df7))
