# Changelog

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/language-rust-v0.3.0...language-rust-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))

## [0.3.0](https://github.com/srobroek/agentic-packages/compare/language-rust-v0.2.0...language-rust-v0.3.0) (2026-06-24)


### Features

* **language-rust:** add architecture conventions steering ([6225ae7](https://github.com/srobroek/agentic-packages/commit/6225ae74a758a943e01f7f79409d68b78cf4bcf6))
* reusable Rust architecture steering (language-rust + language-steering-rust) ([6295a64](https://github.com/srobroek/agentic-packages/commit/6295a64afe379be3882a7eef2e83642d5c8339b9))
* reusable TypeScript/React architecture steering (+ steering dep-range fix) ([025390d](https://github.com/srobroek/agentic-packages/commit/025390d1ce49b60d5400c74a35a06269d4fd3d7a))


### Bug Fixes

* **language-rust:** track language-steering-rust#main ([4947fc3](https://github.com/srobroek/agentic-packages/commit/4947fc3876780f28942c3fbbbb4ffa0f4c01f692))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/language-rust-v0.1.2...language-rust-v0.2.0) (2026-06-20)


### Features

* adopt apm 0.21 semver ranges, sub-bundle core, add kiro target ([#341](https://github.com/srobroek/agentic-packages/issues/341)) ([d033e88](https://github.com/srobroek/agentic-packages/commit/d033e88fee643b036498c1edccc4ba50af742659))

## [0.1.2](https://github.com/srobroek/agentic-packages/compare/language-rust-v0.1.1...language-rust-v0.1.2) (2026-06-12)


### Bug Fixes

* bump bundle member pins to released versions, refresh README counts ([#307](https://github.com/srobroek/agentic-packages/issues/307)) ([a1c099b](https://github.com/srobroek/agentic-packages/commit/a1c099b9f03765459fdcb990e61b262aab967cbb))

## [0.1.1](https://github.com/srobroek/agentic-packages/compare/language-rust-v0.1.0...language-rust-v0.1.1) (2026-06-03)


### Bug Fixes

* exact-tag bundle pins, flatten core, decouple catchup/handover ([edc8535](https://github.com/srobroek/agentic-packages/commit/edc85355ba01fb779fe8f3e3afb6ee6303f557fe))
* exact-tag bundle pins, flatten core, decouple catchup/handover [skip tests] ([11d803e](https://github.com/srobroek/agentic-packages/commit/11d803ec2c62944083795a48b830eed213bbd3a0))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/language-rust-v0.0.1...language-rust-v0.1.0) (2026-06-02)


### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* **packages:** add apm.yml to all skill/agent packages; drop category/tags from apm.yml [skip tests] ([722502e](https://github.com/srobroek/agentic-packages/commit/722502e84d74c7fa89d433294355355add2cd523))
* publish standalone mcp packages ([3145100](https://github.com/srobroek/agentic-packages/commit/31451002a7ae874e59c7f11868dd039ba597730c))
* split optional mcp package installs ([c774562](https://github.com/srobroek/agentic-packages/commit/c774562b84c66117e2ce714208aed32a4e9df65b))


### Bug Fixes

* repair generated agents context links ([87a4b92](https://github.com/srobroek/agentic-packages/commit/87a4b92133966a8db34071e3ac8157d67b006174))
* use valid repo-locator dependency syntax for bundle members [skip tests] ([855d9d6](https://github.com/srobroek/agentic-packages/commit/855d9d67b2e6c93e9dd1b603fd7cf958e172682a))
* valid repo-locator dependency syntax for bundle members ([c4be60c](https://github.com/srobroek/agentic-packages/commit/c4be60cf8308c21be297b9fcf2381b3e6687ac61))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **bundles:** convert bundles to dependency-aggregator manifests [skip tests] ([615f549](https://github.com/srobroek/agentic-packages/commit/615f5493b15fb3e97231d0e1776bbef46cc86644))
* promote apm wrappers to packages ([bbe7484](https://github.com/srobroek/agentic-packages/commit/bbe748422b5f7dcc4ffbfe8354d21dc171c52add))
