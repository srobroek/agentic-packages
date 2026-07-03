# Changelog

## [1.1.3](https://github.com/srobroek/agentic-packages/compare/core--v1.1.2...core--v1.1.3) (2026-07-03)


### Bug Fixes

* **deps:** sync internal package pins to released versions ([#468](https://github.com/srobroek/agentic-packages/issues/468)) ([83b38c8](https://github.com/srobroek/agentic-packages/commit/83b38c8367e82b9df100780b31806524474f7864))

## [1.1.2](https://github.com/srobroek/agentic-packages/compare/core--v1.1.1...core--v1.1.2) (2026-07-03)


### Bug Fixes

* **deps:** sync internal package pins to released versions ([#466](https://github.com/srobroek/agentic-packages/issues/466)) ([d252bf8](https://github.com/srobroek/agentic-packages/commit/d252bf8604c34e6887ca95426d35026f18fca05f))

## [1.1.1](https://github.com/srobroek/agentic-packages/compare/core--v1.1.0...core--v1.1.1) (2026-06-29)


### Bug Fixes

* **build-native-plugins:** emit parseable {git,path} bundle deps ([#417](https://github.com/srobroek/agentic-packages/issues/417)) ([8bd39d4](https://github.com/srobroek/agentic-packages/commit/8bd39d47a8f03a7f162849099844ae332f858105))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/core-v1.0.0...core--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/core-v0.5.0...core-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))


### Bug Fixes

* **phase-1:** guard bypasses, bash-3.2/BSD portability, crashes, bundle pins + tests ([#360](https://github.com/srobroek/agentic-packages/issues/360)) ([b0c9106](https://github.com/srobroek/agentic-packages/commit/b0c91064313282a4265b9b0b8fb779f00afecd90))

## [0.5.0](https://github.com/srobroek/agentic-packages/compare/core-v0.4.1...core-v0.5.0) (2026-06-20)


### Features

* adopt apm 0.21 semver ranges, sub-bundle core, add kiro target ([#341](https://github.com/srobroek/agentic-packages/issues/341)) ([d033e88](https://github.com/srobroek/agentic-packages/commit/d033e88fee643b036498c1edccc4ba50af742659))

## [0.4.1](https://github.com/srobroek/agentic-packages/compare/core-v0.4.0...core-v0.4.1) (2026-06-20)


### Bug Fixes

* **core:** bundle latest catchup and resume-session, refresh marketplace versions ([#332](https://github.com/srobroek/agentic-packages/issues/332)) ([d94ce8c](https://github.com/srobroek/agentic-packages/commit/d94ce8ce076c4e87f9130667d40f215478c57d5f))

## [0.4.0](https://github.com/srobroek/agentic-packages/compare/core-v0.3.0...core-v0.4.0) (2026-06-20)


### Features

* **core:** bundle resume-session skill ([#327](https://github.com/srobroek/agentic-packages/issues/327)) ([e64ed16](https://github.com/srobroek/agentic-packages/commit/e64ed1668e1f89f161a7112e23eeb6a18fe680a5))

## [0.3.0](https://github.com/srobroek/agentic-packages/compare/core-v0.2.1...core-v0.3.0) (2026-06-20)


### Features

* **language-steering-rust:** add CI + Tauri steering, expand tooling defaults ([11b1e01](https://github.com/srobroek/agentic-packages/commit/11b1e012f99e2d5d49e41ac30e0afed005b97152))

## [0.2.1](https://github.com/srobroek/agentic-packages/compare/core-v0.2.0...core-v0.2.1) (2026-06-20)


### Bug Fixes

* **core:** remove dead mattpocock skill references ([5c02f5d](https://github.com/srobroek/agentic-packages/commit/5c02f5db3934e4160dd4f0035966d8784395af1a))
* **core:** remove dead mattpocock skill references ([f584488](https://github.com/srobroek/agentic-packages/commit/f5844883cc1671e1a562335610233c8d422f0fc9))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/core-v0.1.2...core-v0.2.0) (2026-06-19)


### Features

* **headroom:** add Headroom token-compression skill and wire into core ([#312](https://github.com/srobroek/agentic-packages/issues/312)) ([d216c88](https://github.com/srobroek/agentic-packages/commit/d216c88eb20dee33f6748ceeaaed9a49469eb0e0))

## [0.1.2](https://github.com/srobroek/agentic-packages/compare/core-v0.1.1...core-v0.1.2) (2026-06-12)


### Bug Fixes

* bump bundle member pins to released versions, refresh README counts ([#307](https://github.com/srobroek/agentic-packages/issues/307)) ([a1c099b](https://github.com/srobroek/agentic-packages/commit/a1c099b9f03765459fdcb990e61b262aab967cbb))

## [0.1.1](https://github.com/srobroek/agentic-packages/compare/core-v0.1.0...core-v0.1.1) (2026-06-03)


### Bug Fixes

* exact-tag bundle pins, flatten core, decouple catchup/handover ([edc8535](https://github.com/srobroek/agentic-packages/commit/edc85355ba01fb779fe8f3e3afb6ee6303f557fe))
* exact-tag bundle pins, flatten core, decouple catchup/handover [skip tests] ([11d803e](https://github.com/srobroek/agentic-packages/commit/11d803ec2c62944083795a48b830eed213bbd3a0))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/core-v0.0.1...core-v0.1.0) (2026-06-02)


### Features

* add page-composability rule to UI component steering ([f2ac2e1](https://github.com/srobroek/agentic-packages/commit/f2ac2e1231ab29076c04caa591fbed4a47b38acd))
* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* **packages:** add apm.yml to all skill/agent packages; drop category/tags from apm.yml [skip tests] ([722502e](https://github.com/srobroek/agentic-packages/commit/722502e84d74c7fa89d433294355355add2cd523))
* publish standalone mcp packages ([3145100](https://github.com/srobroek/agentic-packages/commit/31451002a7ae874e59c7f11868dd039ba597730c))
* split optional mcp package installs ([c774562](https://github.com/srobroek/agentic-packages/commit/c774562b84c66117e2ce714208aed32a4e9df65b))


### Bug Fixes

* bundle codex agent runtime patcher ([b73b361](https://github.com/srobroek/agentic-packages/commit/b73b3610bd169db9da3a4d4b9ae3f49042301c3a))
* compile claude steering in setup guidance ([32d6fe3](https://github.com/srobroek/agentic-packages/commit/32d6fe31943fae7c274a8cf5365d23d0ec24269a))
* remove pyyaml dependency from package pruner ([8abfefc](https://github.com/srobroek/agentic-packages/commit/8abfefc50f67af62d5b35a6bd367deb288ec54ed))
* repair generated agents context links ([87a4b92](https://github.com/srobroek/agentic-packages/commit/87a4b92133966a8db34071e3ac8157d67b006174))
* resolve direct local apm package links ([1e8f561](https://github.com/srobroek/agentic-packages/commit/1e8f5614123b3cbf9e316b31a1393e3351f45857))
* scope agents context link routing ([efa0f89](https://github.com/srobroek/agentic-packages/commit/efa0f897575a3a414a79fa2019ad849bdc170fe0))
* support local package context links ([fa92080](https://github.com/srobroek/agentic-packages/commit/fa920801986ae0b8d3a1b1ca690bcdb4e337ba7c))
* use valid repo-locator dependency syntax for bundle members [skip tests] ([855d9d6](https://github.com/srobroek/agentic-packages/commit/855d9d67b2e6c93e9dd1b603fd7cf958e172682a))
* valid repo-locator dependency syntax for bundle members ([c4be60c](https://github.com/srobroek/agentic-packages/commit/c4be60cf8308c21be297b9fcf2381b3e6687ac61))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **bundles:** convert bundles to dependency-aggregator manifests [skip tests] ([615f549](https://github.com/srobroek/agentic-packages/commit/615f5493b15fb3e97231d0e1776bbef46cc86644))
* promote apm wrappers to packages ([bbe7484](https://github.com/srobroek/agentic-packages/commit/bbe748422b5f7dcc4ffbfe8354d21dc171c52add))
