# Changelog

## [6.0.1](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v6.0.0...pr-shepherd--v6.0.1) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [6.0.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v5.0.0...pr-shepherd--v6.0.0) (2026-07-30)


### ⚠ BREAKING CHANGES

* merge-bead trailers are no longer required outside an orchestrate run, and are advisory rather than blocking inside one. A repository that relied on this hook to enforce merge-queue linkage on every PR must set PR_MERGE_QUEUE_ENFORCE, and must treat the advisory rather than a denial as the signal.
* **deps:** sync internal package pins (major-level dep releases)

### Features

* **deps:** sync internal package pins (major-level dep releases) ([7b63b60](https://github.com/srobroek/agentic-packages/commit/7b63b60828a8f675244f6cb99554723d07ca6a8f))


### Bug Fixes

* drop the PR bead trailers, and have the shepherd verify its own anchors ([#824](https://github.com/srobroek/agentic-packages/issues/824)) ([4ea4081](https://github.com/srobroek/agentic-packages/commit/4ea4081e6f7acb95d49cb977c69e1e119471f983))
* **pr-shepherd,orchestrate:** distinguish a rate-limited review bot from a working one ([#823](https://github.com/srobroek/agentic-packages/issues/823)) ([6d31687](https://github.com/srobroek/agentic-packages/commit/6d316871cef1b6b50837455e5ec95084185c1c29))

## [5.0.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v4.0.0...pr-shepherd--v5.0.0) (2026-07-30)


### ⚠ BREAKING CHANGES

* **pr-shepherd:** scripts/landing-contract.sh is replaced by scripts/landing-contract.py. Callers invoking the path directly must update it.
* the hooks-worktree and mcp-1mcp packages are removed. Worktree lifecycle and cleanup are owned by hooks-worktrunk, which requires the wt binary; 1mcp has no replacement because nothing used it.
* the hooks-worktree and mcp-1mcp packages are removed. Worktree lifecycle and cleanup are owned by hooks-worktrunk, which requires the wt binary; 1mcp has no replacement because nothing used it.

### Features

* **pr-shepherd:** port the landing contract to Python and prove merge-queue landings ([#807](https://github.com/srobroek/agentic-packages/issues/807)) ([841df3f](https://github.com/srobroek/agentic-packages/commit/841df3fe224004acb42e707bcca7624738def973))


### Refactors

* consolidate the worktree and chezmoi hooks, drop four dead ones ([#804](https://github.com/srobroek/agentic-packages/issues/804)) ([cb49b0a](https://github.com/srobroek/agentic-packages/commit/cb49b0ab2119642c2902d030f956fd182c4181e2))
* port the skill scripts to Python and fuzz every port ([#811](https://github.com/srobroek/agentic-packages/issues/811)) ([773ac2b](https://github.com/srobroek/agentic-packages/commit/773ac2bced832cb0144b7e21e6937e69b9e3b631))

## [4.0.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v3.0.0...pr-shepherd--v4.0.0) (2026-07-28)


### ⚠ BREAKING CHANGES

* **deps:** sync internal package pins (major-level dep releases)

### Features

* **deps:** sync internal package pins (major-level dep releases) ([1ea2d17](https://github.com/srobroek/agentic-packages/commit/1ea2d17165aab551582be9a3c1f9c3d7c28f6dc4))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v2.0.1...pr-shepherd--v3.0.0) (2026-07-28)


### ⚠ BREAKING CHANGES

* **hooks-bash-safety:** agentic-source-guard no longer runs; edits to agentic source files are no longer hook-gated.

### Bug Fixes

* **hooks-bash-safety:** block rm -rf that a leading cd redirects to a system path ([#788](https://github.com/srobroek/agentic-packages/issues/788)) ([34bfd74](https://github.com/srobroek/agentic-packages/commit/34bfd74cf22648d223e2c76f1d073ff7987787a8))

## [2.0.1](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v2.0.0...pr-shepherd--v2.0.1) (2026-07-27)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([4b7aecd](https://github.com/srobroek/agentic-packages/commit/4b7aecd27b8adb681c4ac25f1b243bf1bed4d904))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v1.1.0...pr-shepherd--v2.0.0) (2026-07-27)


### ⚠ BREAKING CHANGES

* **agents:** `agent-coder` is now `agent-builder` and `agent-coder-high` is `agent-builder-high`. The agents `parallel-builder`, `worker`, `coder-high`, `domain-specialist-medium` and `domain-specialist-xhigh` no longer exist; use `builder` with an explicit mode, `builder-high`, or `domain-specialist{,-high}`. Spawn calls naming a removed agent must be updated.
* route every Codex agent to a benchmarked model tier ([#766](https://github.com/srobroek/agentic-packages/issues/766))

### Bug Fixes

* **agents:** pin every agent to a model, collapse duplicate tiers ([#771](https://github.com/srobroek/agentic-packages/issues/771)) ([fd8193f](https://github.com/srobroek/agentic-packages/commit/fd8193f6e1f8fb7a4bfcb889e24f4ccd5327a7f7))
* give every APM instruction an explicit applyTo, add drift guard ([#769](https://github.com/srobroek/agentic-packages/issues/769)) ([d983034](https://github.com/srobroek/agentic-packages/commit/d98303486d87b5dfb348a4a04fa435afa5fce692))
* route every Codex agent to a benchmarked model tier ([#766](https://github.com/srobroek/agentic-packages/issues/766)) ([f8fb26a](https://github.com/srobroek/agentic-packages/commit/f8fb26aacaa45cbf7ab9ceaa42855089d34b6673))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v1.0.0...pr-shepherd--v1.1.0) (2026-07-26)


### Features

* one shepherd per repository via the sheepdog patrol lease ([#758](https://github.com/srobroek/agentic-packages/issues/758)) ([94f324b](https://github.com/srobroek/agentic-packages/commit/94f324b60058cbdb236bb431f33aaabaff3cd97d))


### Bug Fixes

* **pr-shepherd:** honour integration_owner on the drain path, not just the watcher ([#754](https://github.com/srobroek/agentic-packages/issues/754)) ([591ca58](https://github.com/srobroek/agentic-packages/commit/591ca580aa437aabc44c3d0c54054710fc64fdb0))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.15.2...pr-shepherd--v1.0.0) (2026-07-26)


### ⚠ BREAKING CHANGES

* **orchestrate:** enforce the parent-managed activation contract and cut contradictory steering ([#741](https://github.com/srobroek/agentic-packages/issues/741))

### Features

* **orchestrate:** enforce the parent-managed activation contract and cut contradictory steering ([#741](https://github.com/srobroek/agentic-packages/issues/741)) ([c72959f](https://github.com/srobroek/agentic-packages/commit/c72959f0f0f5300f6b049c04ec878a164d39d5d5))

## [0.15.2](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.15.1...pr-shepherd--v0.15.2) (2026-07-26)


### Documentation

* **orchestrate,pr-shepherd:** give the watcher contract and dead-claim rule one owner ([#737](https://github.com/srobroek/agentic-packages/issues/737)) ([5ce7a96](https://github.com/srobroek/agentic-packages/commit/5ce7a9652510476a019135bcdcadd1ea3ddbe49e))

## [0.15.1](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.15.0...pr-shepherd--v0.15.1) (2026-07-25)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([6c55c29](https://github.com/srobroek/agentic-packages/commit/6c55c291106d03bdb7f5a2912a6a1aba76025c18))

## [0.15.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.14.1...pr-shepherd--v0.15.0) (2026-07-25)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([5781282](https://github.com/srobroek/agentic-packages/commit/57812825a102bbfbc1738860e2f3210e97975889))


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))


### Refactors

* move guidance into the scripts and contracts that enforce it ([#726](https://github.com/srobroek/agentic-packages/issues/726)) ([40bcfdf](https://github.com/srobroek/agentic-packages/commit/40bcfdf27cd6bbf72db02ce143482eac91d4a4cc))

## [0.14.1](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.14.0...pr-shepherd--v0.14.1) (2026-07-24)


### Bug Fixes

* **agents:** open replies with the verdict token via imperative scaffold ([#697](https://github.com/srobroek/agentic-packages/issues/697)) ([64ce7aa](https://github.com/srobroek/agentic-packages/commit/64ce7aae82e1d69a2b7f0b8fd076c44f6cf768a1))

## [0.14.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.13.3...pr-shepherd--v0.14.0) (2026-07-24)


### Features

* **pr-shepherd:** add generalized watch-queue dashboard script ([#687](https://github.com/srobroek/agentic-packages/issues/687)) ([4322e71](https://github.com/srobroek/agentic-packages/commit/4322e71a25d22c036bf0e2a5abd04524dd82d968))


### Bug Fixes

* **agents:** verdict line is the literal first line — no preamble, no markdown emphasis ([#688](https://github.com/srobroek/agentic-packages/issues/688)) ([0cef5d6](https://github.com/srobroek/agentic-packages/commit/0cef5d6698a0ee7b5f3337ef993a4bf9fb653e9a))

## [0.13.3](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.13.2...pr-shepherd--v0.13.3) (2026-07-23)


### Bug Fixes

* **deps:** sync internal package pins to released versions ([#677](https://github.com/srobroek/agentic-packages/issues/677)) ([546411c](https://github.com/srobroek/agentic-packages/commit/546411c55b213309f210db1810ac35f48e6e41fe))

## [0.13.2](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.13.1...pr-shepherd--v0.13.2) (2026-07-23)


### Bug Fixes

* steering matches deployed models and sheds per-session token weight ([#664](https://github.com/srobroek/agentic-packages/issues/664)) ([05ac136](https://github.com/srobroek/agentic-packages/commit/05ac136fb5b81c8a3b2497078eb79d88a4aa9f2c))

## [0.13.1](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.13.0...pr-shepherd--v0.13.1) (2026-07-23)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([78b3c6b](https://github.com/srobroek/agentic-packages/commit/78b3c6b0d8b90b3d78e66913e25860bcc4628bf3))

## [0.13.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.12.0...pr-shepherd--v0.13.0) (2026-07-23)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([#646](https://github.com/srobroek/agentic-packages/issues/646)) ([29f3dd0](https://github.com/srobroek/agentic-packages/commit/29f3dd0e10f84f9c740db515743cc057d83bbb4f))

## [0.12.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.11.1...pr-shepherd--v0.12.0) (2026-07-22)


### Features

* make Codex and Claude APM integration target-aware ([#643](https://github.com/srobroek/agentic-packages/issues/643)) ([83fe64b](https://github.com/srobroek/agentic-packages/commit/83fe64b7bf119cb91aaea3f3d7932b2781a45eee))


### Bug Fixes

* **pr-shepherd:** normalize empty review decisions ([#644](https://github.com/srobroek/agentic-packages/issues/644)) ([6a7a11b](https://github.com/srobroek/agentic-packages/commit/6a7a11b8f9cd14a6c87843768478c1ac0efc35f9))

## [0.11.1](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.11.0...pr-shepherd--v0.11.1) (2026-07-22)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([ebdfd40](https://github.com/srobroek/agentic-packages/commit/ebdfd40464b78d18e0ea3ecfcefbc581f67d1f67))

## [0.11.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.10.0...pr-shepherd--v0.11.0) (2026-07-22)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([6d4aa7a](https://github.com/srobroek/agentic-packages/commit/6d4aa7a37618ef33f7dcc66d16b6fcb6c85535ae))

## [0.10.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.9.0...pr-shepherd--v0.10.0) (2026-07-22)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([c1720ad](https://github.com/srobroek/agentic-packages/commit/c1720ad12f33be022f89a744192cf6ed8b1380c5))


### Bug Fixes

* keep package artifacts stable after tests ([#629](https://github.com/srobroek/agentic-packages/issues/629)) ([f3fec83](https://github.com/srobroek/agentic-packages/commit/f3fec8320f69d1e719fa051473055a2e6e7e43fc))

## [0.9.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.8.1...pr-shepherd--v0.9.0) (2026-07-22)


### Features

* verify pull requests before and after merge ([#612](https://github.com/srobroek/agentic-packages/issues/612)) ([66aaa91](https://github.com/srobroek/agentic-packages/commit/66aaa91bccd7d8694fe65c7f0b645208f4855372))

## [0.8.1](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.8.0...pr-shepherd--v0.8.1) (2026-07-22)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([a7d6a10](https://github.com/srobroek/agentic-packages/commit/a7d6a10b5a89ab5ca128e8fe0bd873b48e4e6b54))

## [0.8.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.7.0...pr-shepherd--v0.8.0) (2026-07-22)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([f2c6de9](https://github.com/srobroek/agentic-packages/commit/f2c6de9745b359e719d2f57b51e359f0b7f86064))

## [0.7.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.6.0...pr-shepherd--v0.7.0) (2026-07-22)


### Features

* connect queue events to shepherd and orchestrator ([#608](https://github.com/srobroek/agentic-packages/issues/608)) ([58e25f8](https://github.com/srobroek/agentic-packages/commit/58e25f865f2c28cfb060f94a9bd1aa0ef6bf9dd5))

## [0.6.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.5.2...pr-shepherd--v0.6.0) (2026-07-21)


### Features

* **agents:** preserve model routing in workflow packages ([df86afc](https://github.com/srobroek/agentic-packages/commit/df86afc45f5c6da979e939aba1ed7f5fe2fcbc6a))

## [0.5.2](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.5.1...pr-shepherd--v0.5.2) (2026-07-21)


### Bug Fixes

* stop noisy hook warnings and broken pipes ([#575](https://github.com/srobroek/agentic-packages/issues/575)) ([f9f1acf](https://github.com/srobroek/agentic-packages/commit/f9f1acfabe0e16578f87a9d7a1e3b1b6bd7992b4))

## [0.5.1](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.5.0...pr-shepherd--v0.5.1) (2026-07-21)


### Bug Fixes

* **deps:** sync internal package pins (patch-level dep releases) ([d404fa5](https://github.com/srobroek/agentic-packages/commit/d404fa56d5d41c2b65af02525335cc91574b19d0))

## [0.5.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.4.0...pr-shepherd--v0.5.0) (2026-07-20)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([df10eb4](https://github.com/srobroek/agentic-packages/commit/df10eb45b8a8306bed96ef925d1d5ca7d5d6d2c6))

## [0.4.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.3.0...pr-shepherd--v0.4.0) (2026-07-20)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([40a8fbd](https://github.com/srobroek/agentic-packages/commit/40a8fbdfe26680765b58f0b9985d7364f26539fa))

## [0.3.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.2.0...pr-shepherd--v0.3.0) (2026-07-20)


### Features

* **deps:** sync internal package pins (minor-level dep releases) ([cea28c3](https://github.com/srobroek/agentic-packages/commit/cea28c3c82950dfecebfd8d43284e1eeaf1de960))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/pr-shepherd--v0.1.0...pr-shepherd--v0.2.0) (2026-07-20)


### Features

* merge pr-shepherd package ([f32a9dc](https://github.com/srobroek/agentic-packages/commit/f32a9dc7a6c1f4a4d60509720d349ebf1007fe93))
* **pr-shepherd:** add cross-session PR/merge shepherd package ([0b1d850](https://github.com/srobroek/agentic-packages/commit/0b1d8505338efa18f8b810e3c504bc9690172507))


### Bug Fixes

* **probes:** unknown is not clean, and count claims for the git user ([13660e9](https://github.com/srobroek/agentic-packages/commit/13660e9f66dcf181b031b24198a6c696c1b2f3c1))

## Changelog
