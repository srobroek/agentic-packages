# Changelog

## [16.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v15.1.0...orchestrate--v16.0.0) (2026-07-30)


### ⚠ BREAKING CHANGES

* **deps:** sync internal package pins (major-level dep releases)

### Features

* **deps:** sync internal package pins (major-level dep releases) ([7b63b60](https://github.com/srobroek/agentic-packages/commit/7b63b60828a8f675244f6cb99554723d07ca6a8f))


### Bug Fixes

* **pr-shepherd,orchestrate:** distinguish a rate-limited review bot from a working one ([#823](https://github.com/srobroek/agentic-packages/issues/823)) ([6d31687](https://github.com/srobroek/agentic-packages/commit/6d316871cef1b6b50837455e5ec95084185c1c29))
* specialists pick a narrow child agent instead of defaulting to general-purpose ([#828](https://github.com/srobroek/agentic-packages/issues/828)) ([65a04bf](https://github.com/srobroek/agentic-packages/commit/65a04bf78a4b4590aa134af582334ade5fb190ef))

## [15.1.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v15.0.0...orchestrate--v15.1.0) (2026-07-30)


### Features

* recover a stuck agent worktree instead of rebuilding it ([#810](https://github.com/srobroek/agentic-packages/issues/810)) ([2b3a06c](https://github.com/srobroek/agentic-packages/commit/2b3a06c87bfb956da078c370268a851a380d5f8b))

## [15.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v14.0.0...orchestrate--v15.0.0) (2026-07-28)


### ⚠ BREAKING CHANGES

* **deps:** sync internal package pins (major-level dep releases)

### Features

* **deps:** sync internal package pins (major-level dep releases) ([1ea2d17](https://github.com/srobroek/agentic-packages/commit/1ea2d17165aab551582be9a3c1f9c3d7c28f6dc4))

## [14.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v13.0.0...orchestrate--v14.0.0) (2026-07-28)


### ⚠ BREAKING CHANGES

* the codex-hook-contract package is renamed to agent-hook-contract. Update any dependency pin to the new package path.
* **hooks-bash-safety:** agentic-source-guard no longer runs; edits to agentic source files are no longer hook-gated.

### Features

* require Python for agent hooks and generalize the hook contract to Claude and Codex ([#790](https://github.com/srobroek/agentic-packages/issues/790)) ([45d3606](https://github.com/srobroek/agentic-packages/commit/45d36065aa0f56c9e34010388226aef8eb206fd8))


### Bug Fixes

* **hooks-bash-safety:** block rm -rf that a leading cd redirects to a system path ([#788](https://github.com/srobroek/agentic-packages/issues/788)) ([34bfd74](https://github.com/srobroek/agentic-packages/commit/34bfd74cf22648d223e2c76f1d073ff7987787a8))

## [13.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v12.0.0...orchestrate--v13.0.0) (2026-07-27)


### ⚠ BREAKING CHANGES

* **deps:** sync internal package pins (major-level dep releases)

### Features

* **deps:** sync internal package pins (major-level dep releases) ([f215865](https://github.com/srobroek/agentic-packages/commit/f21586533af761142538ca7082bd37cc5bd021ef))

## [12.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v11.0.2...orchestrate--v12.0.0) (2026-07-27)


### ⚠ BREAKING CHANGES

* **agents:** `agent-coder` is now `agent-builder` and `agent-coder-high` is `agent-builder-high`. The agents `parallel-builder`, `worker`, `coder-high`, `domain-specialist-medium` and `domain-specialist-xhigh` no longer exist; use `builder` with an explicit mode, `builder-high`, or `domain-specialist{,-high}`. Spawn calls naming a removed agent must be updated.
* route every Codex agent to a benchmarked model tier ([#766](https://github.com/srobroek/agentic-packages/issues/766))

### Bug Fixes

* **agents:** pin every agent to a model, collapse duplicate tiers ([#771](https://github.com/srobroek/agentic-packages/issues/771)) ([fd8193f](https://github.com/srobroek/agentic-packages/commit/fd8193f6e1f8fb7a4bfcb889e24f4ccd5327a7f7))
* **orchestrate:** read the expected bd version from mise.toml ([#773](https://github.com/srobroek/agentic-packages/issues/773)) ([26bbaac](https://github.com/srobroek/agentic-packages/commit/26bbaacfa82d03ca49acb6bb62fa476faff184f6))
* route every Codex agent to a benchmarked model tier ([#766](https://github.com/srobroek/agentic-packages/issues/766)) ([f8fb26a](https://github.com/srobroek/agentic-packages/commit/f8fb26aacaa45cbf7ab9ceaa42855089d34b6673))

## [11.0.2](https://github.com/srobroek/agentic-packages/compare/orchestrate--v11.0.1...orchestrate--v11.0.2) (2026-07-26)


### Bug Fixes

* **orchestrate:** stop the run-marker bind depending on a deployed exec bit ([#767](https://github.com/srobroek/agentic-packages/issues/767)) ([97b5ea7](https://github.com/srobroek/agentic-packages/commit/97b5ea7d190fc9181156b29c79a34952db23847a))

## [11.0.1](https://github.com/srobroek/agentic-packages/compare/orchestrate--v11.0.0...orchestrate--v11.0.1) (2026-07-26)


### Bug Fixes

* **orchestrate:** ship the run-activation scripts as executable ([#762](https://github.com/srobroek/agentic-packages/issues/762)) ([54f1d1f](https://github.com/srobroek/agentic-packages/commit/54f1d1fd21995be8e2a277ee07fa38379e21c11a))

## [11.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v10.0.2...orchestrate--v11.0.0) (2026-07-26)


### ⚠ BREAKING CHANGES

* **orchestrate:** conflict-probe.sh no longer accepts land, verify-landed or check-run. Callers needing a landing transaction use pr-shepherd directly as a separate tool. orchestrate no longer installs pr-shepherd as a dependency; install it alongside if you want the repository-global drain.

### Features

* one shepherd per repository via the sheepdog patrol lease ([#758](https://github.com/srobroek/agentic-packages/issues/758)) ([94f324b](https://github.com/srobroek/agentic-packages/commit/94f324b60058cbdb236bb431f33aaabaff3cd97d))
* **orchestrate:** make orchestrate standalone with no pr-shepherd dependency ([#756](https://github.com/srobroek/agentic-packages/issues/756)) ([49845e2](https://github.com/srobroek/agentic-packages/commit/49845e2c724ab29367b16b7e481055de4d1d3d1f))


### Bug Fixes

* **pr-shepherd:** honour integration_owner on the drain path, not just the watcher ([#754](https://github.com/srobroek/agentic-packages/issues/754)) ([591ca58](https://github.com/srobroek/agentic-packages/commit/591ca580aa437aabc44c3d0c54054710fc64fdb0))

## [10.0.2](https://github.com/srobroek/agentic-packages/compare/orchestrate--v10.0.1...orchestrate--v10.0.2) (2026-07-26)


### Bug Fixes

* **orchestrate:** triage swarm-validate warnings instead of treating all as defects ([#752](https://github.com/srobroek/agentic-packages/issues/752)) ([ae3fc04](https://github.com/srobroek/agentic-packages/commit/ae3fc04a13c178aa4de60225c91f0aa31b1d551f))

## [10.0.1](https://github.com/srobroek/agentic-packages/compare/orchestrate--v10.0.0...orchestrate--v10.0.1) (2026-07-26)


### Bug Fixes

* **orchestrate:** park external gates and gate decomposition on swarm validate ([#751](https://github.com/srobroek/agentic-packages/issues/751)) ([4489e41](https://github.com/srobroek/agentic-packages/commit/4489e41c63dac3428e52705efd9ee5e4d9818690))


### Documentation

* **orchestrate:** say that an artifact node needs a writable role ([#749](https://github.com/srobroek/agentic-packages/issues/749)) ([ddc6d40](https://github.com/srobroek/agentic-packages/commit/ddc6d4087850d4455c3612bd3a71b41c21f42c6e))

## [10.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v9.0.0...orchestrate--v10.0.0) (2026-07-26)


### ⚠ BREAKING CHANGES

* **orchestrate:** deny unrecognised agent types instead of skipping activation ([#747](https://github.com/srobroek/agentic-packages/issues/747))

### Bug Fixes

* **orchestrate:** deny unrecognised agent types instead of skipping activation ([#747](https://github.com/srobroek/agentic-packages/issues/747)) ([37ec780](https://github.com/srobroek/agentic-packages/commit/37ec780c3b46d426ddb7f37d10c7c531cb668372))

## [9.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v8.0.0...orchestrate--v9.0.0) (2026-07-26)


### ⚠ BREAKING CHANGES

* **deps:** sync internal package pins (major-level dep releases)

### Features

* **deps:** sync internal package pins (major-level dep releases) ([1a3cecf](https://github.com/srobroek/agentic-packages/commit/1a3cecf31c713e44dbc471e70401e6b3b05340a5))

## [8.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v7.0.1...orchestrate--v8.0.0) (2026-07-26)


### ⚠ BREAKING CHANGES

* **orchestrate:** enforce the parent-managed activation contract and cut contradictory steering ([#741](https://github.com/srobroek/agentic-packages/issues/741))

### Features

* **orchestrate:** enforce the parent-managed activation contract and cut contradictory steering ([#741](https://github.com/srobroek/agentic-packages/issues/741)) ([c72959f](https://github.com/srobroek/agentic-packages/commit/c72959f0f0f5300f6b049c04ec878a164d39d5d5))


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([d874171](https://github.com/srobroek/agentic-packages/commit/d87417111f585092d54020a502ae7a6f18a7a6a5))

## [7.0.1](https://github.com/srobroek/agentic-packages/compare/orchestrate--v7.0.0...orchestrate--v7.0.1) (2026-07-26)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([6a7467f](https://github.com/srobroek/agentic-packages/commit/6a7467f0ccb14a638f1e4301490e93854dbcfa9a))


### Documentation

* **orchestrate,pr-shepherd:** give the watcher contract and dead-claim rule one owner ([#737](https://github.com/srobroek/agentic-packages/issues/737)) ([5ce7a96](https://github.com/srobroek/agentic-packages/commit/5ce7a9652510476a019135bcdcadd1ea3ddbe49e))

## [7.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v6.0.1...orchestrate--v7.0.0) (2026-07-25)


### ⚠ BREAKING CHANGES

* **deps:** sync internal package pins (major-level dep releases)

### Features

* **deps:** sync internal package pins (major-level dep releases) ([1830127](https://github.com/srobroek/agentic-packages/commit/18301271a5088c8afc7ad4688974b1b1bc503241))

## [6.0.1](https://github.com/srobroek/agentic-packages/compare/orchestrate--v6.0.0...orchestrate--v6.0.1) (2026-07-25)


### Bug Fixes

* **orchestrate:** accept worktrunk-writer 2.x ([#732](https://github.com/srobroek/agentic-packages/issues/732)) ([af245d7](https://github.com/srobroek/agentic-packages/commit/af245d7beb14521c37c6d21bac751e12309d2c63))

## [6.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v5.0.0...orchestrate--v6.0.0) (2026-07-25)


### ⚠ BREAKING CHANGES

* remove the unused hooks-portability-ci package and three dead doc mirrors ([#724](https://github.com/srobroek/agentic-packages/issues/724))
* drop xhigh effort pins to high and remove a duplicate agent variant ([#723](https://github.com/srobroek/agentic-packages/issues/723))
* **deps:** sync internal package pins (major-level dep releases)

### Features

* **deps:** sync internal package pins (major-level dep releases) ([6eee221](https://github.com/srobroek/agentic-packages/commit/6eee221e133ea777bec62030374ea3f3e43b01fd))


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))
* close three guard bypasses and eight broken agent references ([#722](https://github.com/srobroek/agentic-packages/issues/722)) ([cbc6875](https://github.com/srobroek/agentic-packages/commit/cbc6875f53b3b048f4fe882bad69305a04e47bc3))
* drop xhigh effort pins to high and remove a duplicate agent variant ([#723](https://github.com/srobroek/agentic-packages/issues/723)) ([7ce15d2](https://github.com/srobroek/agentic-packages/commit/7ce15d2f601c232b1e8f2aff6e09706547d48849))


### Refactors

* move guidance into the scripts and contracts that enforce it ([#726](https://github.com/srobroek/agentic-packages/issues/726)) ([40bcfdf](https://github.com/srobroek/agentic-packages/commit/40bcfdf27cd6bbf72db02ce143482eac91d4a4cc))


### Chores

* remove the unused hooks-portability-ci package and three dead doc mirrors ([#724](https://github.com/srobroek/agentic-packages/issues/724)) ([6897316](https://github.com/srobroek/agentic-packages/commit/6897316695052c14b4055e3f8350d5ec1d7327cf))

## [5.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v4.2.2...orchestrate--v5.0.0) (2026-07-25)


### ⚠ BREAKING CHANGES

* **orchestrate:** subagent_type 'coder' -> 'builder', 'parallel-coder' -> 'parallel-builder'. Update any spawn calls referencing the old names.

### Features

* enforce Worktrunk worktree lifecycle for agents ([46ec4cb](https://github.com/srobroek/agentic-packages/commit/46ec4cb5385c41020870b5492f1f83a7c8e59d14))
* **orchestrate:** bead-as-brief v2 — claim-bound contracts, delegation-first fleet, cache policy ([#713](https://github.com/srobroek/agentic-packages/issues/713)) ([e8deb15](https://github.com/srobroek/agentic-packages/commit/e8deb151d222e843e9bc80fc6808c9acc141124f))


### Bug Fixes

* **orchestrate:** restore domain-specialist; rename coder-&gt;builder ([#715](https://github.com/srobroek/agentic-packages/issues/715)) ([223e0c9](https://github.com/srobroek/agentic-packages/commit/223e0c95cb8dee08d1f3cd00cd96cb598d78d24e))

## [4.2.2](https://github.com/srobroek/agentic-packages/compare/orchestrate--v4.2.1...orchestrate--v4.2.2) (2026-07-24)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([9efa212](https://github.com/srobroek/agentic-packages/commit/9efa2125f49d5091193e6712fdc050e9cf57be79))

## [4.2.1](https://github.com/srobroek/agentic-packages/compare/orchestrate--v4.2.0...orchestrate--v4.2.1) (2026-07-24)


### Bug Fixes

* **agents:** open replies with the verdict token via imperative scaffold ([#697](https://github.com/srobroek/agentic-packages/issues/697)) ([64ce7aa](https://github.com/srobroek/agentic-packages/commit/64ce7aae82e1d69a2b7f0b8fd076c44f6cf768a1))

## [4.2.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v4.1.3...orchestrate--v4.2.0) (2026-07-24)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([8005169](https://github.com/srobroek/agentic-packages/commit/800516906d6fe98604fd86f63833f03b06f5874e))

## [4.1.3](https://github.com/srobroek/agentic-packages/compare/orchestrate--v4.1.2...orchestrate--v4.1.3) (2026-07-24)


### Bug Fixes

* **agents:** verdict line is the literal first line — no preamble, no markdown emphasis ([#688](https://github.com/srobroek/agentic-packages/issues/688)) ([0cef5d6](https://github.com/srobroek/agentic-packages/commit/0cef5d6698a0ee7b5f3337ef993a4bf9fb653e9a))

## [4.1.2](https://github.com/srobroek/agentic-packages/compare/orchestrate--v4.1.1...orchestrate--v4.1.2) (2026-07-23)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([a67c683](https://github.com/srobroek/agentic-packages/commit/a67c68380f87633e1e8a6e44071e77d6ec385bc1))

## [4.1.1](https://github.com/srobroek/agentic-packages/compare/orchestrate--v4.1.0...orchestrate--v4.1.1) (2026-07-23)


### Bug Fixes

* **deps:** sync internal package pins to released versions ([#677](https://github.com/srobroek/agentic-packages/issues/677)) ([546411c](https://github.com/srobroek/agentic-packages/commit/546411c55b213309f210db1810ac35f48e6e41fe))

## [4.1.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v4.0.0...orchestrate--v4.1.0) (2026-07-23)


### Features

* agent linter catches empty descriptions, over-constraint, missing triggers, and bloat ([#672](https://github.com/srobroek/agentic-packages/issues/672)) ([47feb78](https://github.com/srobroek/agentic-packages/commit/47feb78421542944aa0f1ee7947e1b3ebab0f08d))


### Bug Fixes

* **agents:** converge Claude effort and Codex reasoning_effort pins ([#663](https://github.com/srobroek/agentic-packages/issues/663)) ([9f149f2](https://github.com/srobroek/agentic-packages/commit/9f149f2cda79e819ce25b37e5eba2ffdd52fd115))
* script dependencies self-declare and agent contracts match reality ([#667](https://github.com/srobroek/agentic-packages/issues/667)) ([6e0f967](https://github.com/srobroek/agentic-packages/commit/6e0f96709f0f88b76461a750e9b46aa5045cede6))

## [4.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v3.13.0...orchestrate--v4.0.0) (2026-07-23)


### ⚠ BREAKING CHANGES

* **deps:** sync internal package pins (major-level dep releases)

### Features

* **deps:** sync internal package pins (major-level dep releases) ([b7a1318](https://github.com/srobroek/agentic-packages/commit/b7a1318f6c28392ba74dd4720e784b28c6265075))

## [3.13.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v3.12.0...orchestrate--v3.13.0) (2026-07-23)


### Features

* standalone quality-guard agents for docs, lint, metrics, maintenance, and diff triage ([#656](https://github.com/srobroek/agentic-packages/issues/656)) ([1263c67](https://github.com/srobroek/agentic-packages/commit/1263c670ce5f7ab7de5b6cc5b55803e1dadaf8c0))


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([5297f20](https://github.com/srobroek/agentic-packages/commit/5297f20f05426e0875c33d8b1a7aaff89cf7e0fb))

## [3.12.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v3.11.0...orchestrate--v3.12.0) (2026-07-23)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([b80f8eb](https://github.com/srobroek/agentic-packages/commit/b80f8eb418fd873449dd26235b45ba7745b095c9))

## [3.11.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v3.10.0...orchestrate--v3.11.0) (2026-07-23)


### Features

* add documentation, lint, and metrics agents to orchestrate ([#650](https://github.com/srobroek/agentic-packages/issues/650)) ([10c1e30](https://github.com/srobroek/agentic-packages/commit/10c1e30ae271c1a5801301ae1948f7d2caea4ff8))
* **deps:** sync internal package pins (minor-level dep releases) ([#646](https://github.com/srobroek/agentic-packages/issues/646)) ([29f3dd0](https://github.com/srobroek/agentic-packages/commit/29f3dd0e10f84f9c740db515743cc057d83bbb4f))

## [3.10.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v3.9.1...orchestrate--v3.10.0) (2026-07-22)


### Features

* make Codex and Claude APM integration target-aware ([#643](https://github.com/srobroek/agentic-packages/issues/643)) ([83fe64b](https://github.com/srobroek/agentic-packages/commit/83fe64b7bf119cb91aaea3f3d7932b2781a45eee))

## [3.9.1](https://github.com/srobroek/agentic-packages/compare/orchestrate--v3.9.0...orchestrate--v3.9.1) (2026-07-22)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([d9c360b](https://github.com/srobroek/agentic-packages/commit/d9c360b3ee94e51cc59d997a7baa30e6abeb4d51))

## [3.9.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v3.8.0...orchestrate--v3.9.0) (2026-07-22)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([5600ce6](https://github.com/srobroek/agentic-packages/commit/5600ce62261d5c5313bc25b368b375974c477d18))


### Bug Fixes

* route agent code discovery through Serena ([bf9593c](https://github.com/srobroek/agentic-packages/commit/bf9593c14f5d486af11f2d364e8d5dd66d3b0306))

## [3.8.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v3.7.0...orchestrate--v3.8.0) (2026-07-22)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([6d4aa7a](https://github.com/srobroek/agentic-packages/commit/6d4aa7a37618ef33f7dcc66d16b6fcb6c85535ae))


### Bug Fixes

* make agent and watcher metadata safer ([4fd84c6](https://github.com/srobroek/agentic-packages/commit/4fd84c6fce0b64465fcb372eb38b7439e0ef79ac))

## [3.7.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v3.6.0...orchestrate--v3.7.0) (2026-07-22)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([c1720ad](https://github.com/srobroek/agentic-packages/commit/c1720ad12f33be022f89a744192cf6ed8b1380c5))
* discover packaged workers with validated metadata ([#625](https://github.com/srobroek/agentic-packages/issues/625)) ([0a170b8](https://github.com/srobroek/agentic-packages/commit/0a170b801d417cf912703228344d3eff25a8b36d))


### Bug Fixes

* keep package artifacts stable after tests ([#629](https://github.com/srobroek/agentic-packages/issues/629)) ([f3fec83](https://github.com/srobroek/agentic-packages/commit/f3fec8320f69d1e719fa051473055a2e6e7e43fc))

## [3.6.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v3.5.0...orchestrate--v3.6.0) (2026-07-22)


### Features

* preserve multi-agent decisions across restarts ([#616](https://github.com/srobroek/agentic-packages/issues/616)) ([69aaa25](https://github.com/srobroek/agentic-packages/commit/69aaa252e13c4fe1517a107d0aba748331bc9df3))


### Bug Fixes

* apply exact landing safety to orchestrated merges ([#623](https://github.com/srobroek/agentic-packages/issues/623)) ([4931e2f](https://github.com/srobroek/agentic-packages/commit/4931e2f40f12a13a3a10c78fe63ef2040bc41084))
* **deps:** sync internal package pins (patch-level dep releases) ([e7e4d7a](https://github.com/srobroek/agentic-packages/commit/e7e4d7a99bf6dc911138c1f085fd667873f70f9d))

## [3.5.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v3.4.0...orchestrate--v3.5.0) (2026-07-22)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([94e7d9a](https://github.com/srobroek/agentic-packages/commit/94e7d9a612133939a0c8ebcd975d0a4789855316))

## [3.4.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v3.3.0...orchestrate--v3.4.0) (2026-07-22)


### Features

* coordinate agents with Beads message threads ([#615](https://github.com/srobroek/agentic-packages/issues/615)) ([7f76270](https://github.com/srobroek/agentic-packages/commit/7f76270b70d4d520a96eb782af0bced88620b2f3))
* **deps:** sync internal package pins (minor-level dep releases) ([f2c6de9](https://github.com/srobroek/agentic-packages/commit/f2c6de9745b359e719d2f57b51e359f0b7f86064))
* let generic workers claim compatible ready tasks ([#614](https://github.com/srobroek/agentic-packages/issues/614)) ([3f5f47e](https://github.com/srobroek/agentic-packages/commit/3f5f47e60b4538b20f36f9672f71f56178a3e7d7))
* route code and non-code work to compatible agents ([#609](https://github.com/srobroek/agentic-packages/issues/609)) ([7b8eb51](https://github.com/srobroek/agentic-packages/commit/7b8eb51608119a413fcdd65c929398363eaa8d0c))
* route writable and research tasks through dedicated agents ([#613](https://github.com/srobroek/agentic-packages/issues/613)) ([7508b28](https://github.com/srobroek/agentic-packages/commit/7508b28e262b92940d90b7cb63acea856ae1edfb))

## [3.3.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v3.2.0...orchestrate--v3.3.0) (2026-07-22)


### Features

* connect queue events to shepherd and orchestrator ([#608](https://github.com/srobroek/agentic-packages/issues/608)) ([58e25f8](https://github.com/srobroek/agentic-packages/commit/58e25f865f2c28cfb060f94a9bd1aa0ef6bf9dd5))
* **deps:** sync internal package pins (minor-level dep releases) ([2b09640](https://github.com/srobroek/agentic-packages/commit/2b0964092bed55576ecac987011f87e0ae20aea5))

## [3.2.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v3.1.0...orchestrate--v3.2.0) (2026-07-22)


### Features

* dispatch approved pull requests from signed webhook events ([#601](https://github.com/srobroek/agentic-packages/issues/601)) ([b244cfe](https://github.com/srobroek/agentic-packages/commit/b244cfe0e43f4aa0010ca352e518d18059da3246))

## [3.1.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v3.0.0...orchestrate--v3.1.0) (2026-07-21)


### Features

* **agents:** preserve model routing in workflow packages ([df86afc](https://github.com/srobroek/agentic-packages/commit/df86afc45f5c6da979e939aba1ed7f5fe2fcbc6a))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v2.0.0...orchestrate--v3.0.0) (2026-07-21)


### ⚠ BREAKING CHANGES

* share MCP backends through 1MCP

### Features

* share MCP backends through 1MCP ([4896601](https://github.com/srobroek/agentic-packages/commit/4896601ca0326762493f340526a97a341b98e24a))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v1.1.0...orchestrate--v2.0.0) (2026-07-20)


### ⚠ BREAKING CHANGES

* **orchestrate:** replace graph.py/ledger.py state store with beads (bd)

### Features

* merge beads-only orchestrate refactor ([ef11395](https://github.com/srobroek/agentic-packages/commit/ef11395608ed7e5164cd3da5c44a901956d5b1a8))
* **orchestrate:** replace graph.py/ledger.py state store with beads (bd) ([3d24b36](https://github.com/srobroek/agentic-packages/commit/3d24b363668d7287e2a4e94868fab7b2489a716b))


### Bug Fixes

* **orchestrate,steering-speckit:** tier vocabulary in references and pointer/context split for lint compliance ([5ebbf02](https://github.com/srobroek/agentic-packages/commit/5ebbf02029869f53a3f409d795ad87ce9f960899))
* **orchestrate:** agent descriptions under cap with output contracts; regenerate marketplace with CI-pinned apm ([4ea3048](https://github.com/srobroek/agentic-packages/commit/4ea3048abfbdeb4c861e7642edef0decd5351440))
* **probes:** unknown is not clean, and count claims for the git user ([13660e9](https://github.com/srobroek/agentic-packages/commit/13660e9f66dcf181b031b24198a6c696c1b2f3c1))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v1.0.0...orchestrate--v1.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v0.3.0...orchestrate--v1.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* **steering:** Wave 4 steering rewrites — pragmatic, code-economy, dedup, language compression, orchestrate fixes

### Features

* **steering:** Wave 4 steering rewrites — pragmatic, code-economy, dedup, language compression, orchestrate fixes ([1412eaf](https://github.com/srobroek/agentic-packages/commit/1412eafea2ec018655d73d353337feb918dd27f0))


### Refactors

* **orchestrate:** surgical fixes from review pass ([c0fc174](https://github.com/srobroek/agentic-packages/commit/c0fc174b3e9d8fccd7842eaea2e5ea9cf25bcb58))

## [0.3.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v0.2.0...orchestrate--v0.3.0) (2026-07-05)


### Features

* orchestrate comms protocol v2 with verified injection, concurrency-safe run scripts, and message linting ([#484](https://github.com/srobroek/agentic-packages/issues/484)) ([8c9cce2](https://github.com/srobroek/agentic-packages/commit/8c9cce2fbecd0f31aa2b254a7bd4d03392ce2166))
* orchestrator-only-coordinates rule, terse agent reasoning/output, pragmatic terseness + comment guidance ([#483](https://github.com/srobroek/agentic-packages/issues/483)) ([446b624](https://github.com/srobroek/agentic-packages/commit/446b62498a0e96e5b6663a3977dbd931b64c8d41))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v0.1.0...orchestrate--v0.2.0) (2026-07-05)


### Features

* **orchestrate:** multi-agent orchestration skill with DAG, ledger, and bundled agents ([#479](https://github.com/srobroek/agentic-packages/issues/479)) ([cb184d3](https://github.com/srobroek/agentic-packages/commit/cb184d3ee33c67e479b432e0a4f48f9972041242))

## 0.1.0

Initial release. Multi-agent orchestration skill: role-to-model routing,
persistent vs ephemeral subagents vs agent-teams, worktree isolation, a
deterministic stdlib task DAG (`graph.py`), a forensic JSONL run ledger
(`ledger.py`), agent discovery (`discover-agents.py`), and a merge/CI conflict
probe (`conflict-probe.sh`). Bundled agents: `workflow-coder`,
`integration-gatekeeper`, `ledger-scribe`.
