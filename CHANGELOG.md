# Changelog

## [17.1.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v17.0.0...srobroek-agentic--v17.1.0) (2026-07-24)


### Features

* agent conformance harness — behavioral contract tests for all shipped agents ([#682](https://github.com/srobroek/agentic-packages/issues/682)) ([1d44052](https://github.com/srobroek/agentic-packages/commit/1d440522d5650c8a4c9ca78f2bcc337a6bd843dd))
* **hooks-subagent-fork:** deny full-history and oversized fork_turns on Codex spawns ([#681](https://github.com/srobroek/agentic-packages/issues/681)) ([8330af5](https://github.com/srobroek/agentic-packages/commit/8330af57eb08291940f38a6be43af674af2d63d8))

## [17.0.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v16.12.0...srobroek-agentic--v17.0.0) (2026-07-23)


### ⚠ BREAKING CHANGES

* the eleven bundle packages are removed. Anyone installing them must drop the dependency; no replacement is needed as the bundles provided no content beyond wshobson plugin passthroughs.
* retire generic tier-wrapper agents in favor of semantic roles ([#668](https://github.com/srobroek/agentic-packages/issues/668))

### Features

* CI runs every test suite, caches dependencies, and gates workflow quality ([#666](https://github.com/srobroek/agentic-packages/issues/666)) ([a4461cc](https://github.com/srobroek/agentic-packages/commit/a4461cc314f2c3baa54e511be44d6589ba769996))
* drop bundled wshobson plugins and retire eleven empty bundles ([#671](https://github.com/srobroek/agentic-packages/issues/671)) ([6a3c4f9](https://github.com/srobroek/agentic-packages/commit/6a3c4f91a0ce805b0eb436cfd457d69670de4c42))
* retire generic tier-wrapper agents in favor of semantic roles ([#668](https://github.com/srobroek/agentic-packages/issues/668)) ([5ba8f01](https://github.com/srobroek/agentic-packages/commit/5ba8f019572661f184468fd99bf3fbfc9d5240e6))


### Bug Fixes

* hook sanitizer detects dead project-level entries and PR guard fails open ([#665](https://github.com/srobroek/agentic-packages/issues/665)) ([0f1dbff](https://github.com/srobroek/agentic-packages/commit/0f1dbff9bf6d2021751f6f10f2903dcb45875092))
* **inject-agent-models:** tolerate identical duplicate mappings across packages ([#669](https://github.com/srobroek/agentic-packages/issues/669)) ([c2eda86](https://github.com/srobroek/agentic-packages/commit/c2eda860c2caf85c5645b323779f5c669a8adaf2))
* script dependencies self-declare and agent contracts match reality ([#667](https://github.com/srobroek/agentic-packages/issues/667)) ([6e0f967](https://github.com/srobroek/agentic-packages/commit/6e0f96709f0f88b76461a750e9b46aa5045cede6))
* steering matches deployed models and sheds per-session token weight ([#664](https://github.com/srobroek/agentic-packages/issues/664)) ([05ac136](https://github.com/srobroek/agentic-packages/commit/05ac136fb5b81c8a3b2497078eb79d88a4aa9f2c))

## [16.12.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v16.11.0...srobroek-agentic--v16.12.0) (2026-07-23)


### Features

* standalone quality-guard agents for docs, lint, metrics, maintenance, and diff triage ([#656](https://github.com/srobroek/agentic-packages/issues/656)) ([1263c67](https://github.com/srobroek/agentic-packages/commit/1263c670ce5f7ab7de5b6cc5b55803e1dadaf8c0))

## [16.11.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v16.10.0...srobroek-agentic--v16.11.0) (2026-07-23)


### Features

* **mcp-serena:** pool backends by checkout ([#653](https://github.com/srobroek/agentic-packages/issues/653)) ([13f6c17](https://github.com/srobroek/agentic-packages/commit/13f6c1737d3a7985d16ec661dd6d141771c7745e))

## [16.10.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v16.9.0...srobroek-agentic--v16.10.0) (2026-07-23)


### Features

* add documentation, lint, and metrics agents to orchestrate ([#650](https://github.com/srobroek/agentic-packages/issues/650)) ([10c1e30](https://github.com/srobroek/agentic-packages/commit/10c1e30ae271c1a5801301ae1948f7d2caea4ff8))
* **user-journeys:** add Beads verification formulas ([#606](https://github.com/srobroek/agentic-packages/issues/606)) ([1ae5c5c](https://github.com/srobroek/agentic-packages/commit/1ae5c5c29fe185c62d2445bdea8bb6e04ef3006d))

## [16.9.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v16.8.0...srobroek-agentic--v16.9.0) (2026-07-22)


### Features

* make Codex and Claude APM integration target-aware ([#643](https://github.com/srobroek/agentic-packages/issues/643)) ([83fe64b](https://github.com/srobroek/agentic-packages/commit/83fe64b7bf119cb91aaea3f3d7932b2781a45eee))


### Bug Fixes

* prevent duplicate and invalid release notes ([#645](https://github.com/srobroek/agentic-packages/issues/645)) ([01d3689](https://github.com/srobroek/agentic-packages/commit/01d3689d03245a46adb511b04cb3d12ce1c7b603))

## [16.8.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v16.7.1...srobroek-agentic--v16.8.0) (2026-07-22)


### Features

* add direct fetcher MCP package ([816a044](https://github.com/srobroek/agentic-packages/commit/816a04439daba896d5ed5c0124c0c2bbe163f7c3))

## [16.7.1](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v16.7.0...srobroek-agentic--v16.7.1) (2026-07-22)


### Bug Fixes

* route agent code discovery through Serena ([bf9593c](https://github.com/srobroek/agentic-packages/commit/bf9593c14f5d486af11f2d364e8d5dd66d3b0306))

## [16.7.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v16.6.0...srobroek-agentic--v16.7.0) (2026-07-22)


### Features

* discover packaged workers with validated metadata ([#625](https://github.com/srobroek/agentic-packages/issues/625)) ([0a170b8](https://github.com/srobroek/agentic-packages/commit/0a170b801d417cf912703228344d3eff25a8b36d))


### Bug Fixes

* keep package artifacts stable after tests ([#629](https://github.com/srobroek/agentic-packages/issues/629)) ([f3fec83](https://github.com/srobroek/agentic-packages/commit/f3fec8320f69d1e719fa051473055a2e6e7e43fc))
* prevent subagents from inheriting unintended models ([44f3d50](https://github.com/srobroek/agentic-packages/commit/44f3d501dfeb3ce2b645e53b5ddc77a63938fdb6))

## [16.6.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v16.5.0...srobroek-agentic--v16.6.0) (2026-07-22)


### Features

* keep agent replies and decisions in Beads ([#622](https://github.com/srobroek/agentic-packages/issues/622)) ([3e5082c](https://github.com/srobroek/agentic-packages/commit/3e5082c1fda4a36ebd67e78ef5ec234666f54a0d))
* verify pull requests before and after merge ([#612](https://github.com/srobroek/agentic-packages/issues/612)) ([66aaa91](https://github.com/srobroek/agentic-packages/commit/66aaa91bccd7d8694fe65c7f0b645208f4855372))

## [16.5.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v16.4.0...srobroek-agentic--v16.5.0) (2026-07-22)


### Features

* connect queue events to shepherd and orchestrator ([#608](https://github.com/srobroek/agentic-packages/issues/608)) ([58e25f8](https://github.com/srobroek/agentic-packages/commit/58e25f865f2c28cfb060f94a9bd1aa0ef6bf9dd5))

## [16.4.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v16.3.0...srobroek-agentic--v16.4.0) (2026-07-22)


### Features

* dispatch approved pull requests from signed webhook events ([#601](https://github.com/srobroek/agentic-packages/issues/601)) ([b244cfe](https://github.com/srobroek/agentic-packages/commit/b244cfe0e43f4aa0010ca352e518d18059da3246))
* emit pull request lifecycle events from queue watchers ([#603](https://github.com/srobroek/agentic-packages/issues/603)) ([88768f8](https://github.com/srobroek/agentic-packages/commit/88768f8b9ccca64a27989a22c9ed77e720774ca5))

## [16.3.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v16.2.0...srobroek-agentic--v16.3.0) (2026-07-21)


### Features

* watch pull request queues with signed GitHub webhooks ([#598](https://github.com/srobroek/agentic-packages/issues/598)) ([0896546](https://github.com/srobroek/agentic-packages/commit/08965468317167fa7df6674b61fc906b47ad0ed5))

## [16.2.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v16.1.0...srobroek-agentic--v16.2.0) (2026-07-21)


### Features

* add native gh interval watcher skill ([3b17ed9](https://github.com/srobroek/agentic-packages/commit/3b17ed9f6c68e5359c8efca693b08ba6940b77be))

## [16.1.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v16.0.3...srobroek-agentic--v16.1.0) (2026-07-21)


### Features

* **agent-management:** compile global root contexts safely ([659b663](https://github.com/srobroek/agentic-packages/commit/659b663f6b5d3f0676348a2dba7e0872b07eb85a))


### Bug Fixes

* **hooks:** remove dead relative command paths ([#589](https://github.com/srobroek/agentic-packages/issues/589)) ([4ce1d9e](https://github.com/srobroek/agentic-packages/commit/4ce1d9e3685e6a5ddc92640311852f9883a669b2))

## [16.0.3](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v16.0.2...srobroek-agentic--v16.0.3) (2026-07-21)


### Bug Fixes

* sanitize stale hooks and harden 1MCP startup ([#586](https://github.com/srobroek/agentic-packages/issues/586)) ([b7c2e8f](https://github.com/srobroek/agentic-packages/commit/b7c2e8f7bfb5c7592c0b991c235e64a4d90882a4))

## [16.0.2](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v16.0.1...srobroek-agentic--v16.0.2) (2026-07-21)


### Bug Fixes

* make lifecycle trust checks reliable ([#585](https://github.com/srobroek/agentic-packages/issues/585)) ([6d7f4af](https://github.com/srobroek/agentic-packages/commit/6d7f4af411e0ce2286094c74891296be28b6f71c))

## [16.0.1](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v16.0.0...srobroek-agentic--v16.0.1) (2026-07-21)


### Bug Fixes

* **agent-management:** distribute agent model injector ([#582](https://github.com/srobroek/agentic-packages/issues/582)) ([cd63272](https://github.com/srobroek/agentic-packages/commit/cd6327260d47012962795206f0be3a1bcd4b3475))

## [16.0.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v15.0.0...srobroek-agentic--v16.0.0) (2026-07-21)


### ⚠ BREAKING CHANGES

* Replace patch-agentic-tools with the trusted install-agentic-tools, update-agentic-tools, or setup-agentic-tools wrappers. Review the lifecycle block and run apm lifecycle trust before using those commands.

### Features

* require trusted lifecycle hooks for agent model injection ([8fa1e37](https://github.com/srobroek/agentic-packages/commit/8fa1e374e9cd10dfbf7b0bcc4142d6997620e0fb))

## [15.0.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v14.0.0...srobroek-agentic--v15.0.0) (2026-07-21)


### ⚠ BREAKING CHANGES

* **speckit:** remove noisy stop hooks ([#574](https://github.com/srobroek/agentic-packages/issues/574))

### Features

* add managed Serena lifecycle hooks ([#576](https://github.com/srobroek/agentic-packages/issues/576)) ([e3d50ab](https://github.com/srobroek/agentic-packages/commit/e3d50ab3d80cabc945370b706ae91cb2eb823ef1))
* **speckit:** remove noisy stop hooks ([#574](https://github.com/srobroek/agentic-packages/issues/574)) ([7637119](https://github.com/srobroek/agentic-packages/commit/76371191da9da679e92c99d3b8b6a6b3817065d7))


### Bug Fixes

* stop noisy hook warnings and broken pipes ([#575](https://github.com/srobroek/agentic-packages/issues/575)) ([f9f1acf](https://github.com/srobroek/agentic-packages/commit/f9f1acfabe0e16578f87a9d7a1e3b1b6bd7992b4))

## [14.0.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v13.0.0...srobroek-agentic--v14.0.0) (2026-07-21)


### ⚠ BREAKING CHANGES

* share MCP backends through 1MCP

### Features

* share MCP backends through 1MCP ([4896601](https://github.com/srobroek/agentic-packages/commit/4896601ca0326762493f340526a97a341b98e24a))

## [13.0.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v12.5.1...srobroek-agentic--v13.0.0) (2026-07-20)


### ⚠ BREAKING CHANGES

* retire speckit-dag-hooks; formula resolves from user-level ~/.beads/formulas

### Features

* retire speckit-dag-hooks; formula resolves from user-level ~/.beads/formulas ([5607757](https://github.com/srobroek/agentic-packages/commit/5607757b1c6b8c777fc9ace5ebb5306e8b3264d8))

## [12.5.1](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v12.5.0...srobroek-agentic--v12.5.1) (2026-07-20)


### Bug Fixes

* **orchestrate:** agent descriptions under cap with output contracts; regenerate marketplace with CI-pinned apm ([4ea3048](https://github.com/srobroek/agentic-packages/commit/4ea3048abfbdeb4c861e7642edef0decd5351440))

## [12.5.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v12.4.0...srobroek-agentic--v12.5.0) (2026-07-20)


### Features

* **mcp-mempalace:** mine sessions automatically at session end and recall memory on demand ([#550](https://github.com/srobroek/agentic-packages/issues/550)) ([727720a](https://github.com/srobroek/agentic-packages/commit/727720ab0bd0b25210763cb838517e9a696a0b90))

## [12.4.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v12.3.0...srobroek-agentic--v12.4.0) (2026-07-20)


### Features

* **hooks-subagent-model:** deny model-less spawns of inherit-type subagents with routing guidance ([#542](https://github.com/srobroek/agentic-packages/issues/542)) ([26cd426](https://github.com/srobroek/agentic-packages/commit/26cd426e4dff3b0ae0e0d2ccfb8b4e43d11907c3))


### Bug Fixes

* pin the artifact generator so upstream releases stop breaking CI ([fabed94](https://github.com/srobroek/agentic-packages/commit/fabed94c9969c8e6def4d0f7dd83df0bc37b2fcb))


### Documentation

* **codex:** clarify subagent hook parity ([#541](https://github.com/srobroek/agentic-packages/issues/541)) ([22f61df](https://github.com/srobroek/agentic-packages/commit/22f61dfca9a2974ae8bf96e8d670bf99008a21a3))

## [12.3.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v12.2.0...srobroek-agentic--v12.3.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))


### Bug Fixes

* **codex:** deduplicate legacy hook wiring ([c8e74bc](https://github.com/srobroek/agentic-packages/commit/c8e74bccf3aef56512f683b4cc586a8525461200))


### Documentation

* **codex:** correct global APM target state ([e07c1ce](https://github.com/srobroek/agentic-packages/commit/e07c1ce3fffcd21b5be0cdc7b1c27b23cbdbe567))

## [12.2.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v12.1.1...srobroek-agentic--v12.2.0) (2026-07-14)


### Features

* **user-journeys:** service-agnostic user-journey lifecycle package ([#532](https://github.com/srobroek/agentic-packages/issues/532)) ([5799976](https://github.com/srobroek/agentic-packages/commit/57999765c239a322883d662545ab1b2739f19792))

## [12.1.1](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v12.1.0...srobroek-agentic--v12.1.1) (2026-07-13)


### Bug Fixes

* source-guard no longer blocks read-only inspection of managed assets ([#528](https://github.com/srobroek/agentic-packages/issues/528)) ([1fd60c8](https://github.com/srobroek/agentic-packages/commit/1fd60c871fb9fcd7d25264716b40a62c16e3d1b4))

## [12.1.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v12.0.0...srobroek-agentic--v12.1.0) (2026-07-12)


### Features

* **write-docs:** trigger on buried doc tasks + SubagentStart discipline hook ([#526](https://github.com/srobroek/agentic-packages/issues/526)) ([965587f](https://github.com/srobroek/agentic-packages/commit/965587f909a73e92c743a95f619a5d237c94c93a))

## [12.0.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v11.0.0...srobroek-agentic--v12.0.0) (2026-07-11)


### ⚠ BREAKING CHANGES

* docs-specs.project-docs.context.md is removed; installs relying on markdown-wide doc-style steering must add the write-docs package.

### Features

* write-docs skill for slop-free, release-focused documentation ([#522](https://github.com/srobroek/agentic-packages/issues/522)) ([3d874b8](https://github.com/srobroek/agentic-packages/commit/3d874b86d9379322ebaeb4ebea3b9e3f7f4bb30c))

## [11.0.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v10.1.0...srobroek-agentic--v11.0.0) (2026-07-09)


### ⚠ BREAKING CHANGES

* **code-intelligence:** consumers relying on code-intelligence to provide the codebase-memory-mcp server must add mcp-codebase-memory as a direct dependency.

### Features

* **code-intelligence:** drop mcp-codebase-memory from the bundle ([#511](https://github.com/srobroek/agentic-packages/issues/511)) ([be3cade](https://github.com/srobroek/agentic-packages/commit/be3cade83adb974930b6312853c0fe8673294129))

## [10.1.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v10.0.0...srobroek-agentic--v10.1.0) (2026-07-08)


### Features

* add MemPalace cross-session memory package (mcp-mempalace) ([#509](https://github.com/srobroek/agentic-packages/issues/509)) ([c021166](https://github.com/srobroek/agentic-packages/commit/c021166e2644ca742a9f1a0c7a77a613154b5133))

## [10.0.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v9.0.0...srobroek-agentic--v10.0.0) (2026-07-08)


### ⚠ BREAKING CHANGES

* **steering-pragmatic:** steering-code-economy is removed; its content now ships in steering-pragmatic 4.0.0. steering-pragmatic is now type: hybrid and registers a SubagentStart hook.

### Features

* **steering-pragmatic:** absorb code-economy + inject working style into subagents ([#501](https://github.com/srobroek/agentic-packages/issues/501)) ([7f0e243](https://github.com/srobroek/agentic-packages/commit/7f0e2438feb9a7e464deb3ec620df73f4c93a9d5))


### Bug Fixes

* let release-please own version bumps for pragmatic and code-intelligence ([#502](https://github.com/srobroek/agentic-packages/issues/502)) ([01a2bb7](https://github.com/srobroek/agentic-packages/commit/01a2bb7d01126fe845429232e4d3ee40544288fc))

## [9.0.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v8.0.0...srobroek-agentic--v9.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* workflow gates via speckit-gate; deprecate speckit-dag-hooks ([#493](https://github.com/srobroek/agentic-packages/issues/493))

### Features

* workflow gates via speckit-gate; deprecate speckit-dag-hooks ([#493](https://github.com/srobroek/agentic-packages/issues/493)) ([8e3414a](https://github.com/srobroek/agentic-packages/commit/8e3414a0f4768b1cc174e00cd6e7c00c57153131))

## [8.0.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v7.1.0...srobroek-agentic--v8.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* remove specs/ — project-setup spec archive moved with its extraction
* **speckit:** Wave 3 — cull advisory DAG nodes, merge agents 6→4, compress steering and setup
* **write-agentic:** package renamed write-a-skill -> write-agentic; referencing bundles updated.
* **bundles:** drop wshobson c4/code-documentation/documentation-generation; grill-me -> grilling
* **hooks:** tier-gate the coder nudge; drop push test-gate and discovery steer
* **hooks-subagent-worktree:** adopt advisory isolation guard
* the removed packages are no longer published; installs referencing them must update to core >=7 bundles.

### Features

* **bundles:** drop wshobson c4/code-documentation/documentation-generation; grill-me -&gt; grilling ([942047e](https://github.com/srobroek/agentic-packages/commit/942047e6096485590d68a3fd18f30cb95b31e9e9))
* **hooks-subagent-worktree:** adopt advisory isolation guard ([67581b1](https://github.com/srobroek/agentic-packages/commit/67581b17d5d9f32e1c5dbcd83cd5635923c5cd94))
* **hooks:** tier-gate the coder nudge; drop push test-gate and discovery steer ([786988a](https://github.com/srobroek/agentic-packages/commit/786988af6a80f3afe31e8763e1077e4a30e61920))
* retire 13 nudge/duplicate packages in favor of static steering ([a2fc229](https://github.com/srobroek/agentic-packages/commit/a2fc229311e85435af1ba9ff1c172016f611436e))
* **speckit:** Wave 3 — cull advisory DAG nodes, merge agents 6→4, compress steering and setup ([bb1a623](https://github.com/srobroek/agentic-packages/commit/bb1a62369b9d5b5f4ae23e6234a1f29f6ba8148f))
* **write-agentic:** generalize write-a-skill to all agentic assets, add lint ([ff5df7a](https://github.com/srobroek/agentic-packages/commit/ff5df7a6614906c669eac40f8bc05c0ee55257cd))


### Bug Fixes

* **agent-coder:** quote-free YAGNI phrasing — embedded quotes broke inject-script JSON ([bbce701](https://github.com/srobroek/agentic-packages/commit/bbce701d7296e46148861807056793ba06770b82))
* **hooks:** make chezmoi-sync advisory-only (no auto-commit/push) ([#487](https://github.com/srobroek/agentic-packages/issues/487)) ([5a9f2e5](https://github.com/srobroek/agentic-packages/commit/5a9f2e5ce01f7417a7bc0c9f61220f882cf89119))
* update merged-agent references in build_nodes.py and docs/speckit.md ([d6ae2ea](https://github.com/srobroek/agentic-packages/commit/d6ae2ea12ca008620003f338e0638532cc0e2096))


### Documentation

* **readme:** add post-release update and stale-content cleanup guide ([ca1154d](https://github.com/srobroek/agentic-packages/commit/ca1154dd69394074f72ed243f20f0dd8c253dfc3))


### Chores

* remove specs/ — project-setup spec archive moved with its extraction ([bc33ab0](https://github.com/srobroek/agentic-packages/commit/bc33ab00498dc2754dd96b4668a4530e43b780bb))

## [7.1.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v7.0.0...srobroek-agentic--v7.1.0) (2026-07-05)


### Features

* orchestrate comms protocol v2 with verified injection, concurrency-safe run scripts, and message linting ([#484](https://github.com/srobroek/agentic-packages/issues/484)) ([8c9cce2](https://github.com/srobroek/agentic-packages/commit/8c9cce2fbecd0f31aa2b254a7bd4d03392ce2166))

## [7.0.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v6.1.0...srobroek-agentic--v7.0.0) (2026-07-05)


### ⚠ BREAKING CHANGES

* **hooks-subagent-worktree:** the PreToolUse:Agent hook no longer denies subagent spawns or requires [iso:*] sentinels. It now posts a non-blocking advisory: if a subagent writes and runs in parallel, use isolation:"worktree"; if it runs isolated, commit before finishing so the worktree branch retains the work. Stays silent once isolation is declared. The 1.x deny-gate guessed wrong too often and blocked legitimate work; cmux native integration + Claude's native worktree lifecycle (baseRef=head) now cover what the gate approximated.

### Features

* bump reconcile parents to match highest dependency severity ([#471](https://github.com/srobroek/agentic-packages/issues/471)) ([b412b3f](https://github.com/srobroek/agentic-packages/commit/b412b3fcf120b1fc7efd32ac3881d35a32188dbf))
* continuous commit/push delivery cadence (steering-delivery package + agent/hook updates) ([#476](https://github.com/srobroek/agentic-packages/issues/476)) ([1f0534f](https://github.com/srobroek/agentic-packages/commit/1f0534f15b7b86952153feaacbbf3e2b9c8887c7))
* **hooks-subagent-worktree:** convert deny-gate to non-blocking advisory ([#473](https://github.com/srobroek/agentic-packages/issues/473)) ([3bb8722](https://github.com/srobroek/agentic-packages/commit/3bb87228c332d6edd7e9e0c7011c679667c2bad6))
* **orchestrate:** multi-agent orchestration skill with DAG, ledger, and bundled agents ([#479](https://github.com/srobroek/agentic-packages/issues/479)) ([cb184d3](https://github.com/srobroek/agentic-packages/commit/cb184d3ee33c67e479b432e0a4f48f9972041242))


### Bug Fixes

* remove hardcoded home paths and macOS/Linux portability breaks ([#474](https://github.com/srobroek/agentic-packages/issues/474)) ([c7169ec](https://github.com/srobroek/agentic-packages/commit/c7169ec479439bbbe1f2cbcd5383b1b29452ada1))

## [6.1.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v6.0.0...srobroek-agentic--v6.1.0) (2026-07-03)


### Features

* **cmux:** add cmux terminal skills bundle ([#462](https://github.com/srobroek/agentic-packages/issues/462)) ([a11c3d4](https://github.com/srobroek/agentic-packages/commit/a11c3d43ba920948d3d347fdffb0d8d87724172f))


### Bug Fixes

* drop external marketplace members so release pack works offline ([#465](https://github.com/srobroek/agentic-packages/issues/465)) ([9f658d4](https://github.com/srobroek/agentic-packages/commit/9f658d4b8ae210f31eb6de2984f40e2bcbf3e4f8))

## [6.0.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v5.0.0...srobroek-agentic--v6.0.0) (2026-07-03)


### ⚠ BREAKING CHANGES

* enforce subagent isolation with a 3-token model (readonly/extern/direct) and primary-checkout deny gate ([#458](https://github.com/srobroek/agentic-packages/issues/458))

### Features

* add steering-architecture package (compose over fork) ([#460](https://github.com/srobroek/agentic-packages/issues/460)) ([7b3a91f](https://github.com/srobroek/agentic-packages/commit/7b3a91fce332182ec0efa3111edb511216bd3a7e))
* enforce subagent isolation with a 3-token model (readonly/extern/direct) and primary-checkout deny gate ([#458](https://github.com/srobroek/agentic-packages/issues/458)) ([3cfc4c0](https://github.com/srobroek/agentic-packages/commit/3cfc4c060c75536319ae5ed57716b5190a4ad223))

## [5.0.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v4.4.0...srobroek-agentic--v5.0.0) (2026-07-02)


### ⚠ BREAKING CHANGES

* the `unstuck` package and the `debugging` bundle are removed. Anyone installing either must drop it; install agent-adversarial-challenger directly for the critic agent.

### Features

* retire the unstuck package and the debugging bundle ([#453](https://github.com/srobroek/agentic-packages/issues/453)) ([9c2c2eb](https://github.com/srobroek/agentic-packages/commit/9c2c2eb7a106158d1ccbb31b58e64c00ce4e872d))

## [4.4.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v4.3.0...srobroek-agentic--v4.4.0) (2026-07-02)


### Features

* block git push on stale or failing unit tests ([#451](https://github.com/srobroek/agentic-packages/issues/451)) ([34041b8](https://github.com/srobroek/agentic-packages/commit/34041b8468c6d307ae8a5b074f9dc4942bf7d848))
* parallel-coder agent + per-language LSP packages ([#449](https://github.com/srobroek/agentic-packages/issues/449)) ([112c80d](https://github.com/srobroek/agentic-packages/commit/112c80d900549c81b72c065ac0c5556f74263f3f))

## [4.3.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v4.2.0...srobroek-agentic--v4.3.0) (2026-07-01)


### Features

* **release-please:** add release-please skill package ([#447](https://github.com/srobroek/agentic-packages/issues/447)) ([27f6e7d](https://github.com/srobroek/agentic-packages/commit/27f6e7df230b8f2bfcaa01770f1c7f7973138173))

## [4.2.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v4.1.0...srobroek-agentic--v4.2.0) (2026-06-30)


### Features

* **goal-writer:** emit a self-sufficient /goal block, always save the doc ([#442](https://github.com/srobroek/agentic-packages/issues/442)) ([a6f6b44](https://github.com/srobroek/agentic-packages/commit/a6f6b44c609ae03677a2f0033c2b8677e7aeec70))

## [4.1.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v4.0.2...srobroek-agentic--v4.1.0) (2026-06-30)


### Features

* **goal-writer:** add goal-structuring skill ([#439](https://github.com/srobroek/agentic-packages/issues/439)) ([770bc15](https://github.com/srobroek/agentic-packages/commit/770bc15d9d219ae2d53907bbd5b6968cec2bd486))

## [4.0.2](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v4.0.1...srobroek-agentic--v4.0.2) (2026-06-30)


### Bug Fixes

* **hooks:** rework PreToolUse guards to never stall auto mode ([#432](https://github.com/srobroek/agentic-packages/issues/432)) ([e00ebb7](https://github.com/srobroek/agentic-packages/commit/e00ebb723fd8e00031fdf28c02ca6b846053d652))

## [4.0.1](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v4.0.0...srobroek-agentic--v4.0.1) (2026-06-29)


### Bug Fixes

* release-please workflow aborts when there is nothing to release ([#423](https://github.com/srobroek/agentic-packages/issues/423)) ([5c8209f](https://github.com/srobroek/agentic-packages/commit/5c8209fd62d18ef00fe6ed7d5155db41102be070))

## [4.0.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v3.0.0...srobroek-agentic--v4.0.0) (2026-06-29)


### ⚠ BREAKING CHANGES

* standalone, agent-driven project scaffolding with git-distributed add-on modules ([#418](https://github.com/srobroek/agentic-packages/issues/418))

### Features

* standalone, agent-driven project scaffolding with git-distributed add-on modules ([#418](https://github.com/srobroek/agentic-packages/issues/418)) ([318dc97](https://github.com/srobroek/agentic-packages/commit/318dc975d485dd04cf1903262b1227242204d482))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v2.0.0...srobroek-agentic--v3.0.0) (2026-06-29)


### ⚠ BREAKING CHANGES

* **speckit:** the /speckit.memory-md.* commands and the mcp-speckit-memory MCP server are no longer installed by speckit setup.

### Features

* **speckit:** drop memory-md extension and mcp-speckit-memory package ([#415](https://github.com/srobroek/agentic-packages/issues/415)) ([855bd7d](https://github.com/srobroek/agentic-packages/commit/855bd7d86bf8cadadbdc94179bc80c35eb06119d))


### Bug Fixes

* **build-native-plugins:** emit parseable {git,path} bundle deps ([#417](https://github.com/srobroek/agentic-packages/issues/417)) ([8bd39d4](https://github.com/srobroek/agentic-packages/commit/8bd39d47a8f03a7f162849099844ae332f858105))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic--v1.3.0...srobroek-agentic--v2.0.0) (2026-06-28)


### ⚠ BREAKING CHANGES

* rebuild sniff as a refactoring auditor across 21 languages ([#405](https://github.com/srobroek/agentic-packages/issues/405))

### Features

* rebuild sniff as a refactoring auditor across 21 languages ([#405](https://github.com/srobroek/agentic-packages/issues/405)) ([61e03ab](https://github.com/srobroek/agentic-packages/commit/61e03abb39d495575bc84a765227814c5c3d7111))

## [1.3.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v1.2.0...srobroek-agentic--v1.3.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.2.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v1.1.0...srobroek-agentic-v1.2.0) (2026-06-26)


### Features

* **hooks-quality:** defer before-commit gate to pre-commit when installed ([#392](https://github.com/srobroek/agentic-packages/issues/392)) ([525f6cc](https://github.com/srobroek/agentic-packages/commit/525f6cca7783c961b66eb47c00233d1d51a4eadc))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v1.0.1...srobroek-agentic-v1.1.0) (2026-06-26)


### Features

* tighten autonomous-agent hook guards; add precommit-gate and close-keywords packages ([#391](https://github.com/srobroek/agentic-packages/issues/391)) ([34f155a](https://github.com/srobroek/agentic-packages/commit/34f155aab3ae1586b2ce16e2418a30a9d47b5137))


### Bug Fixes

* stop the release workflow pushing artifacts to protected main ([#388](https://github.com/srobroek/agentic-packages/issues/388)) ([47ea423](https://github.com/srobroek/agentic-packages/commit/47ea423ad202506a7060523638c21ead0ae3b34b))

## [1.0.1](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v1.0.0...srobroek-agentic-v1.0.1) (2026-06-26)


### Bug Fixes

* install jinja2 in the release artifact-regen job ([#385](https://github.com/srobroek/agentic-packages/issues/385)) ([b89df31](https://github.com/srobroek/agentic-packages/commit/b89df316711e0f1f47dfcd1a7d13fd95b802476d))
* use installable package types so hooks + speckit resolve globally ([#387](https://github.com/srobroek/agentic-packages/issues/387)) ([ff2b7a2](https://github.com/srobroek/agentic-packages/commit/ff2b7a2200fc88bcf39abafe9f73ed6f5d31e942))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.17.0...srobroek-agentic-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* mcp-package-version no longer ships the package-file-warn or pkg-version-warn hooks. Installers that relied on those hooks should install hooks-package-file-guard / hooks-pkg-version-warn (or the dependency-quality bundle) instead.
* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* add hooks-chezmoi-guard and hooks-attribution-guard guard-hook packages ([#369](https://github.com/srobroek/agentic-packages/issues/369)) ([92814f2](https://github.com/srobroek/agentic-packages/commit/92814f2cb43a8afb417f9c2e6518b822cb8adbab))
* add hooks-subagent-worktree enforcement package ([#384](https://github.com/srobroek/agentic-packages/issues/384)) ([608d757](https://github.com/srobroek/agentic-packages/commit/608d7572168e06ae15788f7ed8f367f300ae0b74))
* add secrets-scan, dep-audit CI, and codex-hook-contract packages ([#374](https://github.com/srobroek/agentic-packages/issues/374)) ([036efaa](https://github.com/srobroek/agentic-packages/commit/036efaa29b7133a73fad0b3aa652d8d952c7981d))
* add whats-new upgrade-research skill ([#378](https://github.com/srobroek/agentic-packages/issues/378)) ([b330834](https://github.com/srobroek/agentic-packages/commit/b330834182d1dc42e511da1901fd04bc9f333797))
* direct/no-flattery steering + drop redundant global-apm.yml template ([#381](https://github.com/srobroek/agentic-packages/issues/381)) ([0a2a67a](https://github.com/srobroek/agentic-packages/commit/0a2a67ae8c960305d4a7f43d61d283a86801ad05))
* extend whats-new to services, platforms, and model families ([#379](https://github.com/srobroek/agentic-packages/issues/379)) ([a72e2d8](https://github.com/srobroek/agentic-packages/commit/a72e2d824d55fe8afb0dc31b8ce4789e35bfbaee))
* register the memory-md MCP server (mcp-speckit-memory) for SpecKit ([#371](https://github.com/srobroek/agentic-packages/issues/371)) ([adb8223](https://github.com/srobroek/agentic-packages/commit/adb8223c723bc8fc95a8152047b33b285847c1a4))
* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))
* split dependency tooling into independent packages + dependency-quality bundle ([#370](https://github.com/srobroek/agentic-packages/issues/370)) ([03d50a5](https://github.com/srobroek/agentic-packages/commit/03d50a5db3a1572fbe36a4ac1bc1e6877cd96ade))


### Bug Fixes

* **hooks:** repair silently-dead hook filters (if-alternation bug) ([#372](https://github.com/srobroek/agentic-packages/issues/372)) ([659d5fe](https://github.com/srobroek/agentic-packages/commit/659d5fe6bb24a27b1876f46c6a750379eb66ec87))
* **phase-1:** guard bypasses, bash-3.2/BSD portability, crashes, bundle pins + tests ([#360](https://github.com/srobroek/agentic-packages/issues/360)) ([b0c9106](https://github.com/srobroek/agentic-packages/commit/b0c91064313282a4265b9b0b8fb779f00afecd90))
* **speckit:** roadmap.write after iterate + regenerate stale bundles table ([#363](https://github.com/srobroek/agentic-packages/issues/363)) ([be1aa2c](https://github.com/srobroek/agentic-packages/commit/be1aa2c8ec14d36b7fb8dccbb3ad62396442193c))


### Refactors

* generate docs from one inventory + Jinja templates; fix stale README counts ([#373](https://github.com/srobroek/agentic-packages/issues/373)) ([33ccd45](https://github.com/srobroek/agentic-packages/commit/33ccd45826a87caf2e95c2a15f9d01e5ad4c69ed))
* **speckit-dag:** generate nodes.json from a stdlib dataclass builder ([#365](https://github.com/srobroek/agentic-packages/issues/365)) ([757755f](https://github.com/srobroek/agentic-packages/commit/757755f94968d1dfe2edd8f00493991c8f3b4065))
* **speckit-dag:** generate nodes.json from a stdlib dataclass builder ([#367](https://github.com/srobroek/agentic-packages/issues/367)) ([ae598a9](https://github.com/srobroek/agentic-packages/commit/ae598a949b3d09485bb352686073de524607e595))
* split core-global into independently installable packages ([#380](https://github.com/srobroek/agentic-packages/issues/380)) ([36f9470](https://github.com/srobroek/agentic-packages/commit/36f9470fc50a7ff5af2c7dd943a817a1d9808247))
* tidy catalog metadata, dedup steering, fix dead tool references ([#375](https://github.com/srobroek/agentic-packages/issues/375)) ([2ed492c](https://github.com/srobroek/agentic-packages/commit/2ed492c632cf40a8c6cf269216e85021333d4db5))


### Documentation

* add per-type package templates + dev-guide pointer ([#377](https://github.com/srobroek/agentic-packages/issues/377)) ([23ab3b5](https://github.com/srobroek/agentic-packages/commit/23ab3b5c4a8daa939bedc1ad6357701e15eae59b))

## [0.17.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.16.0...srobroek-agentic-v0.17.0) (2026-06-25)


### Features

* **speckit:** adopt memory-md 1.x across speckit, dag-hooks, and steering ([#355](https://github.com/srobroek/agentic-packages/issues/355)) ([450f1f3](https://github.com/srobroek/agentic-packages/commit/450f1f36ae8c9e42562e9270c414da34dd55dbfb))

## [0.16.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.15.0...srobroek-agentic-v0.16.0) (2026-06-24)


### Features

* **speckit:** checklist-after-tasks reorder, memory-md default, agent-assign + hook fixes ([56ceefc](https://github.com/srobroek/agentic-packages/commit/56ceefc09ae0c8e2e2f46977478f188daeb4fa7a))


### Bug Fixes

* **hooks-git-workflow:** make pre-commit test gate a soft warning [skip tests] ([9290b42](https://github.com/srobroek/agentic-packages/commit/9290b428e3fb6fe092c984494d57537f44c2206f))
* **hooks-git-workflow:** sync apm.yml description with soft-warn gate [skip tests] ([3f5758f](https://github.com/srobroek/agentic-packages/commit/3f5758f50df15056c5caf1f5830ed946432ce414))

## [0.15.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.14.0...srobroek-agentic-v0.15.0) (2026-06-24)


### Features

* reusable Rust architecture steering (language-rust + language-steering-rust) ([6295a64](https://github.com/srobroek/agentic-packages/commit/6295a64afe379be3882a7eef2e83642d5c8339b9))
* **speckit:** align with spec-kit 0.11.x — setup ownership, DAG node fix, converge ([8b2a51b](https://github.com/srobroek/agentic-packages/commit/8b2a51b3faa914ae86bbb6944ba62e408ca2e040))


### Documentation

* **speckit:** align orchestration doc with 0.11.x and converge [skip tests] ([d509410](https://github.com/srobroek/agentic-packages/commit/d5094108b5ab82befb7bcb6059f4b169b497b35e))

## [0.14.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.13.2...srobroek-agentic-v0.14.0) (2026-06-20)


### Features

* adopt apm 0.21 semver ranges, sub-bundle core, add kiro target ([#341](https://github.com/srobroek/agentic-packages/issues/341)) ([d033e88](https://github.com/srobroek/agentic-packages/commit/d033e88fee643b036498c1edccc4ba50af742659))

## [0.13.2](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.13.1...srobroek-agentic-v0.13.2) (2026-06-20)


### Bug Fixes

* **speckit-dag-hooks:** resolve feature from invoking agent's working dir ([2b9e423](https://github.com/srobroek/agentic-packages/commit/2b9e42396636545b04fd6a1a2e1d9d1badf06c63))
* **speckit-dag-hooks:** resolve feature from invoking agent's working dir ([742c5d3](https://github.com/srobroek/agentic-packages/commit/742c5d36fecbaefd42eabb98f85d61d1cfdff3e9))

## [0.13.1](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.13.0...srobroek-agentic-v0.13.1) (2026-06-20)


### Bug Fixes

* **core:** bundle latest catchup and resume-session, refresh marketplace versions ([#332](https://github.com/srobroek/agentic-packages/issues/332)) ([d94ce8c](https://github.com/srobroek/agentic-packages/commit/d94ce8ce076c4e87f9130667d40f215478c57d5f))

## [0.13.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.12.0...srobroek-agentic-v0.13.0) (2026-06-20)


### Features

* **core:** bundle resume-session skill ([#327](https://github.com/srobroek/agentic-packages/issues/327)) ([e64ed16](https://github.com/srobroek/agentic-packages/commit/e64ed1668e1f89f161a7112e23eeb6a18fe680a5))

## [0.12.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.11.0...srobroek-agentic-v0.12.0) (2026-06-20)


### Features

* **resume-session:** add agent session-resume skill ([#325](https://github.com/srobroek/agentic-packages/issues/325)) ([1f9aaf9](https://github.com/srobroek/agentic-packages/commit/1f9aaf953ad27941eadc8375256624d1d53c9f46))

## [0.11.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.10.1...srobroek-agentic-v0.11.0) (2026-06-20)


### Features

* **language-steering-rust:** add CI + Tauri steering, expand tooling defaults ([11b1e01](https://github.com/srobroek/agentic-packages/commit/11b1e012f99e2d5d49e41ac30e0afed005b97152))

## [0.10.1](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.10.0...srobroek-agentic-v0.10.1) (2026-06-20)


### Bug Fixes

* **core:** remove dead mattpocock skill references ([5c02f5d](https://github.com/srobroek/agentic-packages/commit/5c02f5db3934e4160dd4f0035966d8784395af1a))
* **core:** remove dead mattpocock skill references ([f584488](https://github.com/srobroek/agentic-packages/commit/f5844883cc1671e1a562335610233c8d422f0fc9))

## [0.10.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.9.0...srobroek-agentic-v0.10.0) (2026-06-20)


### Features

* **mcp-tauri:** add standalone Tauri MCP server package ([6f3b7b8](https://github.com/srobroek/agentic-packages/commit/6f3b7b883fccad1847dbb4d1df0dc7376394538b))
* **mcp-tauri:** add standalone Tauri MCP server package ([94f0b61](https://github.com/srobroek/agentic-packages/commit/94f0b6150611fe8f8a6d7b4efb8fd760b79afb1a))

## [0.9.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.8.0...srobroek-agentic-v0.9.0) (2026-06-19)


### Features

* **core-global:** add headroom skill to the global baseline ([#314](https://github.com/srobroek/agentic-packages/issues/314)) ([27c6202](https://github.com/srobroek/agentic-packages/commit/27c62027a826a7bb59f171ed72617985fb84ca16))

## [0.8.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.7.1...srobroek-agentic-v0.8.0) (2026-06-19)


### Features

* **headroom:** add Headroom token-compression skill and wire into core ([#312](https://github.com/srobroek/agentic-packages/issues/312)) ([d216c88](https://github.com/srobroek/agentic-packages/commit/d216c88eb20dee33f6748ceeaaed9a49469eb0e0))

## [0.7.1](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.7.0...srobroek-agentic-v0.7.1) (2026-06-12)


### Bug Fixes

* bump bundle member pins to released versions, refresh README counts ([#307](https://github.com/srobroek/agentic-packages/issues/307)) ([a1c099b](https://github.com/srobroek/agentic-packages/commit/a1c099b9f03765459fdcb990e61b262aab967cbb))

## [0.7.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.6.0...srobroek-agentic-v0.7.0) (2026-06-12)


### Features

* **unstuck:** outcome-gated stuck detection with escalation ladder ([#300](https://github.com/srobroek/agentic-packages/issues/300)) ([5e8e772](https://github.com/srobroek/agentic-packages/commit/5e8e7727348b01db0902ad2810509ed24c021571))


### Bug Fixes

* **audit-steering:** imperative trigger description ([#257](https://github.com/srobroek/agentic-packages/issues/257)) ([c80e9eb](https://github.com/srobroek/agentic-packages/commit/c80e9ebc35af4beab35054554d683aacf606f29b))
* **code-review:** concrete trigger description, runtime-neutral subagents ([#261](https://github.com/srobroek/agentic-packages/issues/261)) ([f6a131c](https://github.com/srobroek/agentic-packages/commit/f6a131c56b3afe199f304d2800b47fc6f853440b))
* **codebase-index:** document MCP dependency and concrete workflow ([#262](https://github.com/srobroek/agentic-packages/issues/262)) ([93099ab](https://github.com/srobroek/agentic-packages/commit/93099abeb94223e52a317529fc253205211202bb))
* **codebase-memory:** document MCP dependency and explore boundary ([#263](https://github.com/srobroek/agentic-packages/issues/263)) ([de50df6](https://github.com/srobroek/agentic-packages/commit/de50df60429b3969f806de6e91014a582692053e))
* **eli5:** tighten description, soften word budgets ([#268](https://github.com/srobroek/agentic-packages/issues/268)) ([e29a737](https://github.com/srobroek/agentic-packages/commit/e29a737a3dc6a39a7715f9f1f9fce8336e0ce7bb))
* **explore:** disambiguate vs codebase-memory ([#269](https://github.com/srobroek/agentic-packages/issues/269)) ([136bf20](https://github.com/srobroek/agentic-packages/commit/136bf204131caec9add520efd7c8eabb76b65903))
* **handover:** concrete trigger description, dedupe steps ([#271](https://github.com/srobroek/agentic-packages/issues/271)) ([e9c3d09](https://github.com/srobroek/agentic-packages/commit/e9c3d09be65b98fdc5b415af664f57027dcb3887))
* **optimize-steering:** comply with own description-length rules ([#286](https://github.com/srobroek/agentic-packages/issues/286)) ([bff10ed](https://github.com/srobroek/agentic-packages/commit/bff10ed47653c7d0e157cad5c09e77543960909a))
* **playwright:** imperative rules, dedupe guidance ([#287](https://github.com/srobroek/agentic-packages/issues/287)) ([19035a2](https://github.com/srobroek/agentic-packages/commit/19035a2fdde6270078687461c7e25d97802c63cf))
* **prompt-lookup:** trigger phrases and ARGUMENTS semantics ([#288](https://github.com/srobroek/agentic-packages/issues/288)) ([6e5d896](https://github.com/srobroek/agentic-packages/commit/6e5d896e3e0d4098f00469f522813290514c7364))
* **research:** tighten trigger description ([#291](https://github.com/srobroek/agentic-packages/issues/291)) ([fe00f77](https://github.com/srobroek/agentic-packages/commit/fe00f77a140c7dc447f4040c30077bf4852c4132))
* **sniff:** concrete trigger description, runtime-neutral sweep ([#293](https://github.com/srobroek/agentic-packages/issues/293)) ([411b7d8](https://github.com/srobroek/agentic-packages/commit/411b7d801c8a1881c9206ef4b9c84fb210b0b81f))
* validate hook JSON in CI, align speckit pipeline docs ([#304](https://github.com/srobroek/agentic-packages/issues/304)) ([d135baf](https://github.com/srobroek/agentic-packages/commit/d135baf1ea95c55b4fd84817182e3ca943786618))

## [0.6.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.5.0...srobroek-agentic-v0.6.0) (2026-06-10)


### Features

* **marketplace:** generate marketplace block from package manifests, sync description + version ([ce58db3](https://github.com/srobroek/agentic-packages/commit/ce58db369cc6b5239dcd89911acf18e5245ca263))

## [0.5.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.4.0...srobroek-agentic-v0.5.0) (2026-06-09)


### Features

* **agent-adversarial-challenger:** generalize challenger beyond debugging ([4a0899c](https://github.com/srobroek/agentic-packages/commit/4a0899c48e8345a8f5917adf58f00ff4cf1adec0))
* **agent-adversarial-challenger:** generalize challenger beyond debugging [skip tests] ([d798ce3](https://github.com/srobroek/agentic-packages/commit/d798ce3491d3ac06a7b005c395bd1b71f90059a7))

## [0.4.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.3.0...srobroek-agentic-v0.4.0) (2026-06-04)


### Features

* **core-global:** add recommended global baseline bundle [skip tests] ([#249](https://github.com/srobroek/agentic-packages/issues/249)) ([f966597](https://github.com/srobroek/agentic-packages/commit/f966597170541d4ea37207807a4f1a06c87e787d))

## [0.3.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.2.0...srobroek-agentic-v0.3.0) (2026-06-04)


### Features

* **chezmoi-editor:** add standalone dotfiles skill package [skip tests] ([#246](https://github.com/srobroek/agentic-packages/issues/246)) ([7ae2753](https://github.com/srobroek/agentic-packages/commit/7ae27531a106e7de0fd9cd0e6dd97f9666f57b3f))
* **hooks,steering:** add granular global guard hooks + pragmatic steering [skip tests] ([#248](https://github.com/srobroek/agentic-packages/issues/248)) ([11d60ed](https://github.com/srobroek/agentic-packages/commit/11d60ed5e9c4b342742e421995beebde7a157fa0))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.1.3...srobroek-agentic-v0.2.0) (2026-06-03)


### Features

* **readme:** add external-sources table grouping third-party deps by upstream repo [skip tests] ([52887df](https://github.com/srobroek/agentic-packages/commit/52887df478b9cf10993968236b75e8c8525a25fc))


### Bug Fixes

* **docs:** track docs/agents.md (negate the AGENTS.md gitignore match) [skip tests] ([78fd5f5](https://github.com/srobroek/agentic-packages/commit/78fd5f524199c4f31568e9647835e741787d8aa9))
* **readme:** mark external deps with ^ not * to avoid markdown italics ([17d4559](https://github.com/srobroek/agentic-packages/commit/17d4559f78fb52b86d5757bd4d41aa4434c68131))
* **readme:** mark external deps with ^ not * to avoid markdown italics [skip tests] ([107164b](https://github.com/srobroek/agentic-packages/commit/107164bb3f5aa8189680e5535e1f222bfef5c6e2))


### Documentation

* split inventory + SpecKit into docs/, slim the README ([9d26dd8](https://github.com/srobroek/agentic-packages/commit/9d26dd861094b56b0fd9c87c8d7b70fde5a4bf3b))
* split inventory + SpecKit into docs/, slim the README [skip tests] ([f348e76](https://github.com/srobroek/agentic-packages/commit/f348e766d290182d820882d21ad35d716f347acd))

## [0.1.3](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.1.2...srobroek-agentic-v0.1.3) (2026-06-03)


### Bug Fixes

* **readme:** parse package manifests as YAML for inventory tables ([2aba74d](https://github.com/srobroek/agentic-packages/commit/2aba74d66d4d0c643e8f97fcd46e6d97f28d57e0))
* **readme:** parse package manifests as YAML for inventory tables [skip tests] ([88ad974](https://github.com/srobroek/agentic-packages/commit/88ad97485f5b967078b9a2aefe3e4a61091e8a77))

## [0.1.2](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.1.1...srobroek-agentic-v0.1.2) (2026-06-03)


### Bug Fixes

* exact-tag bundle pins, flatten core, decouple catchup/handover ([edc8535](https://github.com/srobroek/agentic-packages/commit/edc85355ba01fb779fe8f3e3afb6ee6303f557fe))
* exact-tag bundle pins, flatten core, decouple catchup/handover [skip tests] ([11d803e](https://github.com/srobroek/agentic-packages/commit/11d803ec2c62944083795a48b830eed213bbd3a0))

## [0.1.1](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.1.0...srobroek-agentic-v0.1.1) (2026-06-03)


### Bug Fixes

* canonical .apm/ package layout + audit-steering rename + GH templates ([4b2a5d6](https://github.com/srobroek/agentic-packages/commit/4b2a5d6418b2f7607e873db464212cd1f711ae67))
* canonical .apm/ package layout, rename audit-steering, add GH templates [skip tests] ([c7692f2](https://github.com/srobroek/agentic-packages/commit/c7692f2d68e36ecc28b65b1400b7057f6a651c16))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/srobroek-agentic-v0.0.1...srobroek-agentic-v0.1.0) (2026-06-02)


### Features

* add agentic APM package marketplace ([a031e45](https://github.com/srobroek/agentic-packages/commit/a031e450ce3ce40cd9ba51a85e7a04bbaa74ebe3))
* add Claude model overrides for third-party agents + fix patch script [skip tests] ([b95eb43](https://github.com/srobroek/agentic-packages/commit/b95eb431c5358397a731287e5276e0e19e602300))
* add MCP server deps to core + create frontend bundle ([292182e](https://github.com/srobroek/agentic-packages/commit/292182e4b43a1212689a1b05c8aaab7ec7c14484))
* add page-composability rule to UI component steering ([f2ac2e1](https://github.com/srobroek/agentic-packages/commit/f2ac2e1231ab29076c04caa591fbed4a47b38acd))
* add progressive APM steering indexes ([f186fd9](https://github.com/srobroek/agentic-packages/commit/f186fd900b47c0028610f6757f2ff88a95ab7517))
* add soft coder-delegation reminder hook ([ed20a8f](https://github.com/srobroek/agentic-packages/commit/ed20a8f8efdf0b34f87eed27fa0ebbac1daede7c))
* incorporate msitarzewski/agency-agents as opt-in marketplace entries ([7d6ed5b](https://github.com/srobroek/agentic-packages/commit/7d6ed5b713854d0e4c8e291f23664170c89b78a1))
* **marketplace:** hand-authored local-path marketplace + apm pack outputs; drop dead packages [skip tests] ([ed11c25](https://github.com/srobroek/agentic-packages/commit/ed11c25cc54b9b31c41864f5d6ca24069c0588c8))
* merge frontend bundle variants ([00085d5](https://github.com/srobroek/agentic-packages/commit/00085d5ca0938fccb3ccee58dd447e5d55c13c3d))
* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* optimize MCP marketplace — replace github MCP with gh CLI, add LSP servers and bundle steering [skip tests] ([e7e98a1](https://github.com/srobroek/agentic-packages/commit/e7e98a12bbd035fc446425a5274bd6d6dc2b57e4))
* publish standalone mcp packages ([3145100](https://github.com/srobroek/agentic-packages/commit/31451002a7ae874e59c7f11868dd039ba597730c))
* **release:** per-package release-please config + apm-action release workflow [skip tests] ([8b95c82](https://github.com/srobroek/agentic-packages/commit/8b95c8294404255944057b1f938d8356d89c7670))
* split optional mcp package installs ([c774562](https://github.com/srobroek/agentic-packages/commit/c774562b84c66117e2ce714208aed32a4e9df65b))
* **steering:** add per-language optional steering packages [skip tests] ([d576229](https://github.com/srobroek/agentic-packages/commit/d576229613e0926c2253c8901eb27f05356964b7))


### Bug Fixes

* avoid pruning transitive apm dependencies ([23e75e6](https://github.com/srobroek/agentic-packages/commit/23e75e60b094bb848c669d0a1bedb5f629816505))
* bundle codex agent runtime patcher ([b73b361](https://github.com/srobroek/agentic-packages/commit/b73b3610bd169db9da3a4d4b9ae3f49042301c3a))
* compile claude steering in setup guidance ([32d6fe3](https://github.com/srobroek/agentic-packages/commit/32d6fe31943fae7c274a8cf5365d23d0ec24269a))
* dedupe language steering and strip constitution blocks ([de28232](https://github.com/srobroek/agentic-packages/commit/de28232e519e42da95d3103a76252a55f8e1c18f))
* drop mcp-hub guidance from SubagentStart context injection ([871e2d3](https://github.com/srobroek/agentic-packages/commit/871e2d30eefe5a32e7de5fb741172092fa8f77d2))
* drop tools list from coder agent source ([6821509](https://github.com/srobroek/agentic-packages/commit/682150956ed55c1d6b60378d9a8af1559a8f020e))
* drop tools list from speckit-implement-task agent source ([0eee1c5](https://github.com/srobroek/agentic-packages/commit/0eee1c5aa5397cf6c7698a6a2d16be3478b22e2d))
* **marketplace:** remove stale root marketplace.json so consumers read apm pack output [skip tests] ([2f2c7e0](https://github.com/srobroek/agentic-packages/commit/2f2c7e07251d446f38d1c543fd5342924879e102))
* persist stitch-skills plugins/stitch-design subdir in build sources ([98344e4](https://github.com/srobroek/agentic-packages/commit/98344e4da518486dc164da3837b98165ce0bc6a7))
* point stitch-skills marketplace entry at plugins/stitch-design ([d620b67](https://github.com/srobroek/agentic-packages/commit/d620b678d6051c3c7b1488510ab4b50682a659d2))
* prune stale apm packages during setup ([ab0529a](https://github.com/srobroek/agentic-packages/commit/ab0529a4560ef0666f66b03078368c56f8907712))
* **release-please:** consolidate into one release PR (separate-pull-requests false) [skip tests] ([867078f](https://github.com/srobroek/agentic-packages/commit/867078fdb4ec741b10d1f1191b6d16148bc39055))
* remove pyyaml dependency from package pruner ([8abfefc](https://github.com/srobroek/agentic-packages/commit/8abfefc50f67af62d5b35a6bd367deb288ec54ed))
* repair generated agents context links ([87a4b92](https://github.com/srobroek/agentic-packages/commit/87a4b92133966a8db34071e3ac8157d67b006174))
* resolve direct local apm package links ([1e8f561](https://github.com/srobroek/agentic-packages/commit/1e8f5614123b3cbf9e316b31a1393e3351f45857))
* scope agents context link routing ([efa0f89](https://github.com/srobroek/agentic-packages/commit/efa0f897575a3a414a79fa2019ad849bdc170fe0))
* skip test gate for agentic-only commits ([f7f9771](https://github.com/srobroek/agentic-packages/commit/f7f97710680549bce6d9fcd9a8696d4751e3131c))
* **speckit:** remove invalid Skill() if patterns from hooks — Skill is not a permission rule type ([a868530](https://github.com/srobroek/agentic-packages/commit/a86853092921f0b44e1eec34a1a953ea42e46d57))
* support local package context links ([fa92080](https://github.com/srobroek/agentic-packages/commit/fa920801986ae0b8d3a1b1ca690bcdb4e337ba7c))
* unify serena mcp package ([51f5d9d](https://github.com/srobroek/agentic-packages/commit/51f5d9d752c2a19b94b1148955b5091adad89333))
* use valid repo-locator dependency syntax for bundle members [skip tests] ([855d9d6](https://github.com/srobroek/agentic-packages/commit/855d9d67b2e6c93e9dd1b603fd7cf958e172682a))
* valid repo-locator dependency syntax for bundle members ([c4be60c](https://github.com/srobroek/agentic-packages/commit/c4be60cf8308c21be297b9fcf2381b3e6687ac61))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* **context:** flatten nested context layout to fix consumer link resolution [skip tests] ([498e7ce](https://github.com/srobroek/agentic-packages/commit/498e7cedd6f2b891f41694ba10e87474f41b241a))
* **packages:** move skills and agents into own top-level packages [skip tests] ([c9ca8d1](https://github.com/srobroek/agentic-packages/commit/c9ca8d13a8dd52c3c90a077966fb3118edf1a189))
* promote apm wrappers to packages ([bbe7484](https://github.com/srobroek/agentic-packages/commit/bbe748422b5f7dcc4ffbfe8354d21dc171c52add))
* **speckit:** remove root duplicates; extract workflow to steering-speckit [skip tests] ([7ff5284](https://github.com/srobroek/agentic-packages/commit/7ff52846cdc17386f83ceb5e6de187196bb0f3de))
* **steering:** drop maintainer-only meta context [skip tests] ([1c88308](https://github.com/srobroek/agentic-packages/commit/1c883087fb727a539b536814142552c7b11701c2))
* **steering:** split baseline into 3 opt-in packages; extract speckit hooks [skip tests] ([9a19504](https://github.com/srobroek/agentic-packages/commit/9a195043c208f8d03d462507a2720d66e7addc2c))


### Documentation

* de-personalize, LOAD convention, README + inventory rewrite [skip tests] ([adf8e21](https://github.com/srobroek/agentic-packages/commit/adf8e210ff5721dd198f7c07f0022910af812df7))
