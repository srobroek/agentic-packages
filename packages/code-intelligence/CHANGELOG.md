# Changelog

## [9.1.0](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v9.0.2...code-intelligence--v9.1.0) (2026-08-17)


### Features

* **codex:** validate packages and standardize language tooling ([#856](https://github.com/srobroek/agentic-packages/issues/856)) ([42edbfb](https://github.com/srobroek/agentic-packages/commit/42edbfb3948c0103f3ce3ef5ba6819a08ae73566))

## [9.0.2](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v9.0.1...code-intelligence--v9.0.2) (2026-08-17)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([2e89d20](https://github.com/srobroek/agentic-packages/commit/2e89d2093e420a321d4c5b97016ea464ae4c61ba))

## [9.0.1](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v9.0.0...code-intelligence--v9.0.1) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [9.0.0](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v8.1.5...code-intelligence--v9.0.0) (2026-07-28)


### ⚠ BREAKING CHANGES

* the hook script is now subagent-model-guard.py and requires python3 on PATH.

### Refactors

* port every remaining shell hook to Python ([#797](https://github.com/srobroek/agentic-packages/issues/797)) ([d01fd9a](https://github.com/srobroek/agentic-packages/commit/d01fd9a79bdc07b01d4477196c5277939fa935a3))

## [8.1.5](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v8.1.4...code-intelligence--v8.1.5) (2026-07-25)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([6c55c29](https://github.com/srobroek/agentic-packages/commit/6c55c291106d03bdb7f5a2912a6a1aba76025c18))

## [8.1.4](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v8.1.3...code-intelligence--v8.1.4) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [8.1.3](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v8.1.2...code-intelligence--v8.1.3) (2026-07-24)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([9efa212](https://github.com/srobroek/agentic-packages/commit/9efa2125f49d5091193e6712fdc050e9cf57be79))

## [8.1.2](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v8.1.1...code-intelligence--v8.1.2) (2026-07-24)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([2cd577e](https://github.com/srobroek/agentic-packages/commit/2cd577e73098023b623149cfc9cb554af2234246))

## [8.1.1](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v8.1.0...code-intelligence--v8.1.1) (2026-07-22)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([d9c360b](https://github.com/srobroek/agentic-packages/commit/d9c360b3ee94e51cc59d997a7baa30e6abeb4d51))

## [8.1.0](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v8.0.0...code-intelligence--v8.1.0) (2026-07-21)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([649d3cc](https://github.com/srobroek/agentic-packages/commit/649d3ccf623c6cc25ab036cef1b17a614cd50a5e))

## [8.0.0](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v7.0.0...code-intelligence--v8.0.0) (2026-07-21)


### ⚠ BREAKING CHANGES

* **deps:** sync internal package pins (major-level dep releases)

### Features

* **deps:** sync internal package pins (major-level dep releases) ([424b28c](https://github.com/srobroek/agentic-packages/commit/424b28c351aa5f7ad6c3463152f09205addd413f))

## [7.0.0](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v6.2.0...code-intelligence--v7.0.0) (2026-07-21)


### ⚠ BREAKING CHANGES

* share MCP backends through 1MCP

### Features

* share MCP backends through 1MCP ([4896601](https://github.com/srobroek/agentic-packages/commit/4896601ca0326762493f340526a97a341b98e24a))

## [6.2.0](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v6.1.0...code-intelligence--v6.2.0) (2026-07-20)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([cec3d7c](https://github.com/srobroek/agentic-packages/commit/cec3d7c1026fb6cf532dea73ac02dcea62b01e1c))

## [6.1.0](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v6.0.0...code-intelligence--v6.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [6.0.0](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v5.0.0...code-intelligence--v6.0.0) (2026-07-09)


### ⚠ BREAKING CHANGES

* **code-intelligence:** consumers relying on code-intelligence to provide the codebase-memory-mcp server must add mcp-codebase-memory as a direct dependency.

### Features

* **code-intelligence:** drop mcp-codebase-memory from the bundle ([#511](https://github.com/srobroek/agentic-packages/issues/511)) ([be3cade](https://github.com/srobroek/agentic-packages/commit/be3cade83adb974930b6312853c0fe8673294129))

## [5.0.0](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v4.0.0...code-intelligence--v5.0.0) (2026-07-08)


### ⚠ BREAKING CHANGES

* **code-intelligence:** consumers of code-intelligence no longer get the SessionStart codebase indexing hook or the PostToolUse reindex-after-commit hook. Projects relying on those must enable codebase-memory-mcp's auto_index/auto_watch config (the recommended 0.9 setup) instead.

### Features

* **code-intelligence:** drop SessionStart index + PostToolUse reindex hooks ([#505](https://github.com/srobroek/agentic-packages/issues/505)) ([488773f](https://github.com/srobroek/agentic-packages/commit/488773f7e5f18ffba35fd968d3839100f4f14462))

## [4.0.0](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v3.0.0...code-intelligence--v4.0.0) (2026-07-08)


### ⚠ BREAKING CHANGES

* **steering-pragmatic:** steering-code-economy is removed; its content now ships in steering-pragmatic 4.0.0. steering-pragmatic is now type: hybrid and registers a SubagentStart hook.

### Features

* **steering-pragmatic:** absorb code-economy + inject working style into subagents ([#501](https://github.com/srobroek/agentic-packages/issues/501)) ([7f0e243](https://github.com/srobroek/agentic-packages/commit/7f0e2438feb9a7e464deb3ec620df73f4c93a9d5))


### Bug Fixes

* let release-please own version bumps for pragmatic and code-intelligence ([#502](https://github.com/srobroek/agentic-packages/issues/502)) ([01a2bb7](https://github.com/srobroek/agentic-packages/commit/01a2bb7d01126fe845429232e4d3ee40544288fc))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/code-intelligence--v2.0.0...code-intelligence--v3.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* code-economy rule overhaul — OVERRIDE, YAGNI section, hand-roll pricing, haiku routing guard ([#496](https://github.com/srobroek/agentic-packages/issues/496))
* **deps:** sync internal package pins (major-level dep releases)

### Features

* code-economy rule overhaul — OVERRIDE, YAGNI section, hand-roll pricing, haiku routing guard ([#496](https://github.com/srobroek/agentic-packages/issues/496)) ([954025f](https://github.com/srobroek/agentic-packages/commit/954025fd2514453cf3c5bc1fecd8678be5b75258))
* **deps:** sync internal package pins (major-level dep releases) ([0bdb7ce](https://github.com/srobroek/agentic-packages/commit/0bdb7ceae8bbd763f64baa26b9d7647863e1c3fc))

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
