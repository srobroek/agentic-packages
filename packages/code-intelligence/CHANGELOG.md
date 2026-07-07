# Changelog

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v1.1.3...code-intelligence--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* **agent-coder:** harden YAGNI rule against growth-bait; tighten parallel-coder output contract
* **steering:** code-economy to keyword convention; restore dropped ladder steps; exact-output coder contracts
* **hooks:** tier-gate the coder nudge; drop push test-gate and discovery steer
* the removed packages are no longer published; installs referencing them must update to core >=7 bundles.

### Features

* **code-intelligence:** inject code-economy, comment, and report rules into every subagent ([f7519b6](https://github.com/srobroek/agentic-packages/commit/f7519b69f288f1e821806d4e30a05bb70399563a))
* **hooks:** tier-gate the coder nudge; drop push test-gate and discovery steer ([786988a](https://github.com/srobroek/agentic-packages/commit/786988af6a80f3afe31e8763e1077e4a30e61920))
* retire 13 nudge/duplicate packages in favor of static steering ([a2fc229](https://github.com/srobroek/agentic-packages/commit/a2fc229311e85435af1ba9ff1c172016f611436e))


### Bug Fixes

* **agent-coder:** harden YAGNI rule against growth-bait; tighten parallel-coder output contract ([81fe444](https://github.com/srobroek/agentic-packages/commit/81fe444df97c4817f68afd772cf3d515ee1d3c5e))
* **agent-coder:** quote-free YAGNI phrasing — embedded quotes broke inject-script JSON ([bbce701](https://github.com/srobroek/agentic-packages/commit/bbce701d7296e46148861807056793ba06770b82))
* **steering:** code-economy to keyword convention; restore dropped ladder steps; exact-output coder contracts ([30bf4c8](https://github.com/srobroek/agentic-packages/commit/30bf4c8e8f84ad332b0be62767f0b0e427549487))

## [1.1.3](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v1.1.2...code-intelligence--v1.1.3) (2026-07-05)


### Bug Fixes

* remove hardcoded home paths and macOS/Linux portability breaks ([#474](https://github.com/srobroek/agentic-packages/issues/474)) ([c7169ec](https://github.com/srobroek/agentic-packages/commit/c7169ec479439bbbe1f2cbcd5383b1b29452ada1))

## [1.1.2](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v1.1.1...code-intelligence--v1.1.2) (2026-07-03)


### Bug Fixes

* **deps:** sync internal package pins to released versions ([#466](https://github.com/srobroek/agentic-packages/issues/466)) ([d252bf8](https://github.com/srobroek/agentic-packages/commit/d252bf8604c34e6887ca95426d35026f18fca05f))

## [1.1.1](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v1.1.0...code-intelligence--v1.1.1) (2026-06-29)


### Bug Fixes

* **build-native-plugins:** emit parseable {git,path} bundle deps ([#417](https://github.com/srobroek/agentic-packages/issues/417)) ([8bd39d4](https://github.com/srobroek/agentic-packages/commit/8bd39d47a8f03a7f162849099844ae332f858105))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/code-intelligence-v1.0.0...code-intelligence--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/code-intelligence-v0.2.0...code-intelligence-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))


### Bug Fixes

* **phase-1:** guard bypasses, bash-3.2/BSD portability, crashes, bundle pins + tests ([#360](https://github.com/srobroek/agentic-packages/issues/360)) ([b0c9106](https://github.com/srobroek/agentic-packages/commit/b0c91064313282a4265b9b0b8fb779f00afecd90))


### Refactors

* tidy catalog metadata, dedup steering, fix dead tool references ([#375](https://github.com/srobroek/agentic-packages/issues/375)) ([2ed492c](https://github.com/srobroek/agentic-packages/commit/2ed492c632cf40a8c6cf269216e85021333d4db5))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/code-intelligence-v0.1.3...code-intelligence-v0.2.0) (2026-06-20)


### Features

* adopt apm 0.21 semver ranges, sub-bundle core, add kiro target ([#341](https://github.com/srobroek/agentic-packages/issues/341)) ([d033e88](https://github.com/srobroek/agentic-packages/commit/d033e88fee643b036498c1edccc4ba50af742659))

## [0.1.3](https://github.com/srobroek/agentic-packages/compare/code-intelligence-v0.1.2...code-intelligence-v0.1.3) (2026-06-12)


### Bug Fixes

* bump bundle member pins to released versions, refresh README counts ([#307](https://github.com/srobroek/agentic-packages/issues/307)) ([a1c099b](https://github.com/srobroek/agentic-packages/commit/a1c099b9f03765459fdcb990e61b262aab967cbb))

## [0.1.2](https://github.com/srobroek/agentic-packages/compare/code-intelligence-v0.1.1...code-intelligence-v0.1.2) (2026-06-12)


### Bug Fixes

* **code-intelligence:** fire discovery-steer advisory once per session ([#260](https://github.com/srobroek/agentic-packages/issues/260)) ([19100b8](https://github.com/srobroek/agentic-packages/commit/19100b809b2a142c5ff690cacbcafe605a7b6e45))

## [0.1.1](https://github.com/srobroek/agentic-packages/compare/code-intelligence-v0.1.0...code-intelligence-v0.1.1) (2026-06-03)


### Bug Fixes

* exact-tag bundle pins, flatten core, decouple catchup/handover ([edc8535](https://github.com/srobroek/agentic-packages/commit/edc85355ba01fb779fe8f3e3afb6ee6303f557fe))
* exact-tag bundle pins, flatten core, decouple catchup/handover [skip tests] ([11d803e](https://github.com/srobroek/agentic-packages/commit/11d803ec2c62944083795a48b830eed213bbd3a0))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/code-intelligence-v0.0.1...code-intelligence-v0.1.0) (2026-06-02)


### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* **packages:** add apm.yml to all skill/agent packages; drop category/tags from apm.yml [skip tests] ([722502e](https://github.com/srobroek/agentic-packages/commit/722502e84d74c7fa89d433294355355add2cd523))
* publish standalone mcp packages ([3145100](https://github.com/srobroek/agentic-packages/commit/31451002a7ae874e59c7f11868dd039ba597730c))


### Bug Fixes

* compile claude steering in setup guidance ([32d6fe3](https://github.com/srobroek/agentic-packages/commit/32d6fe31943fae7c274a8cf5365d23d0ec24269a))
* use valid repo-locator dependency syntax for bundle members [skip tests] ([855d9d6](https://github.com/srobroek/agentic-packages/commit/855d9d67b2e6c93e9dd1b603fd7cf958e172682a))
* valid repo-locator dependency syntax for bundle members ([c4be60c](https://github.com/srobroek/agentic-packages/commit/c4be60cf8308c21be297b9fcf2381b3e6687ac61))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **bundles:** convert bundles to dependency-aggregator manifests [skip tests] ([615f549](https://github.com/srobroek/agentic-packages/commit/615f5493b15fb3e97231d0e1776bbef46cc86644))
* promote apm wrappers to packages ([bbe7484](https://github.com/srobroek/agentic-packages/commit/bbe748422b5f7dcc4ffbfe8354d21dc171c52add))
