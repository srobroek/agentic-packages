# Changelog

## [2.2.0](https://github.com/srobroek/agentic-packages/compare/python-quality--v2.1.3...python-quality--v2.2.0) (2026-08-17)


### Features

* **codex:** validate packages and standardize language tooling ([#856](https://github.com/srobroek/agentic-packages/issues/856)) ([42edbfb](https://github.com/srobroek/agentic-packages/commit/42edbfb3948c0103f3ce3ef5ba6819a08ae73566))

## [2.1.3](https://github.com/srobroek/agentic-packages/compare/python-quality--v2.1.2...python-quality--v2.1.3) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [2.1.2](https://github.com/srobroek/agentic-packages/compare/python-quality--v2.1.1...python-quality--v2.1.2) (2026-07-25)


### Refactors

* cut duplicated rules from steering, agents and skills ([#728](https://github.com/srobroek/agentic-packages/issues/728)) ([8f892aa](https://github.com/srobroek/agentic-packages/commit/8f892aa01b3b0ffbb5888cca0dc4178d57ee967d))

## [2.1.1](https://github.com/srobroek/agentic-packages/compare/python-quality--v2.1.0...python-quality--v2.1.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))


### Refactors

* move guidance into the scripts and contracts that enforce it ([#726](https://github.com/srobroek/agentic-packages/issues/726)) ([40bcfdf](https://github.com/srobroek/agentic-packages/commit/40bcfdf27cd6bbf72db02ce143482eac91d4a4cc))

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/python-quality--v2.0.0...python-quality--v2.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/python-quality--v1.1.0...python-quality--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering

### Features

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering ([9cb202d](https://github.com/srobroek/agentic-packages/commit/9cb202d2b76a649dda0489baaeefd61a2e0829e1))


### Bug Fixes

* **skills:** de-hedge and trim descriptions across 17 skill files ([49b5ffa](https://github.com/srobroek/agentic-packages/commit/49b5ffa1555f7f0c8fad6aa4ea6a53dbfaa6873f))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/python-quality-v1.0.0...python-quality--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/python-quality-v0.1.2...python-quality-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))

## [0.1.2](https://github.com/srobroek/agentic-packages/compare/python-quality-v0.1.1...python-quality-v0.1.2) (2026-06-12)


### Bug Fixes

* **python-quality:** document tool order and fix.sh scope ([#289](https://github.com/srobroek/agentic-packages/issues/289)) ([50511d7](https://github.com/srobroek/agentic-packages/commit/50511d76808a04e24e927b1ef321451afae4829c))

## [0.1.1](https://github.com/srobroek/agentic-packages/compare/python-quality-v0.1.0...python-quality-v0.1.1) (2026-06-03)


### Bug Fixes

* canonical .apm/ package layout + audit-steering rename + GH templates ([4b2a5d6](https://github.com/srobroek/agentic-packages/commit/4b2a5d6418b2f7607e873db464212cd1f711ae67))
* canonical .apm/ package layout, rename audit-steering, add GH templates [skip tests] ([c7692f2](https://github.com/srobroek/agentic-packages/commit/c7692f2d68e36ecc28b65b1400b7057f6a651c16))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/python-quality-v0.0.1...python-quality-v0.1.0) (2026-06-02)


### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* **packages:** add apm.yml to all skill/agent packages; drop category/tags from apm.yml [skip tests] ([722502e](https://github.com/srobroek/agentic-packages/commit/722502e84d74c7fa89d433294355355add2cd523))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **packages:** move skills and agents into own top-level packages [skip tests] ([c9ca8d1](https://github.com/srobroek/agentic-packages/commit/c9ca8d13a8dd52c3c90a077966fb3118edf1a189))


### Documentation

* de-personalize, LOAD convention, README + inventory rewrite [skip tests] ([adf8e21](https://github.com/srobroek/agentic-packages/commit/adf8e210ff5721dd198f7c07f0022910af812df7))
