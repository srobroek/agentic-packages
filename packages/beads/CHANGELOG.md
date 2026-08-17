# Changelog

## [2.1.1](https://github.com/srobroek/agentic-packages/compare/beads--v2.1.0...beads--v2.1.1) (2026-08-17)


### Bug Fixes

* **pr-shepherd:** close the four remaining fuzz defects, unblock bats CI, and clear the ruff backlog ([#863](https://github.com/srobroek/agentic-packages/issues/863)) ([80ef3db](https://github.com/srobroek/agentic-packages/commit/80ef3db32dc2d604e7d9d65a904d712acb15e85f))

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/beads--v2.0.1...beads--v2.1.0) (2026-08-17)


### Features

* **codex:** validate packages and standardize language tooling ([#856](https://github.com/srobroek/agentic-packages/issues/856)) ([42edbfb](https://github.com/srobroek/agentic-packages/commit/42edbfb3948c0103f3ce3ef5ba6819a08ae73566))

## [2.0.1](https://github.com/srobroek/agentic-packages/compare/beads--v2.0.0...beads--v2.0.1) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/beads--v1.0.0...beads--v2.0.0) (2026-07-30)


### ⚠ BREAKING CHANGES

* **beads:** the beads sync hooks are now Python and require python3 on PATH. beads-sync-hydrate.sh and beads-maintenance-check.sh are replaced by the single beads-sync-session.py; a machine-local override naming either old script by path must be repointed.
* the hooks-worktree and mcp-1mcp packages are removed. Worktree lifecycle and cleanup are owned by hooks-worktrunk, which requires the wt binary; 1mcp has no replacement because nothing used it.

### Features

* **beads:** opt-in sync hooks — Dolt first, JSONL fallback ([#779](https://github.com/srobroek/agentic-packages/issues/779)) ([c7047fc](https://github.com/srobroek/agentic-packages/commit/c7047fc46a6b6b474b48e743516745921f9d22f5))


### Refactors

* consolidate the worktree and chezmoi hooks, drop four dead ones ([#804](https://github.com/srobroek/agentic-packages/issues/804)) ([cb49b0a](https://github.com/srobroek/agentic-packages/commit/cb49b0ab2119642c2902d030f956fd182c4181e2))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/beads--v0.7.2...beads--v1.0.0) (2026-07-28)


### ⚠ BREAKING CHANGES

* the hook script is now subagent-model-guard.py and requires python3 on PATH.
* commands that previously passed silently are now judged. A destructive verb inside an inline shell string, or behind timeout, flock, or nice with an option value, is denied where it was allowed, and a download piped to any interpreter now warns.
* **steering-git-workflow:** the hook script is now attribution-guard.py and requires python3 on PATH.
* the secrets-scan and hooks-precommit-gate packages are removed. Secret scanning moves to the gitleaks pre-commit hook; install real git hooks for tool-independent enforcement.

### Bug Fixes

* **steering-git-workflow:** stop blocking pull requests when the policy check cannot verify them ([#794](https://github.com/srobroek/agentic-packages/issues/794)) ([023c0f0](https://github.com/srobroek/agentic-packages/commit/023c0f087717a57386d18d06f2575fca0435b7b1))
* stop the hook guards blocking correct work, and close the wrapper bypasses ([#796](https://github.com/srobroek/agentic-packages/issues/796)) ([217a455](https://github.com/srobroek/agentic-packages/commit/217a4559fe3d0be9fb2751ffbefd41dfe8903f0d))


### Refactors

* drop secrets-scan, hooks-precommit-gate, and the auto-approve hooks ([#792](https://github.com/srobroek/agentic-packages/issues/792)) ([195f194](https://github.com/srobroek/agentic-packages/commit/195f1946b7dd3212c672d827edcc7e2c292e39bc))
* port every remaining shell hook to Python ([#797](https://github.com/srobroek/agentic-packages/issues/797)) ([d01fd9a](https://github.com/srobroek/agentic-packages/commit/d01fd9a79bdc07b01d4477196c5277939fa935a3))

## [0.7.2](https://github.com/srobroek/agentic-packages/compare/beads--v0.7.1...beads--v0.7.2) (2026-07-27)


### Bug Fixes

* give every APM instruction an explicit applyTo, add drift guard ([#769](https://github.com/srobroek/agentic-packages/issues/769)) ([d983034](https://github.com/srobroek/agentic-packages/commit/d98303486d87b5dfb348a4a04fa435afa5fce692))

## [0.7.1](https://github.com/srobroek/agentic-packages/compare/beads--v0.7.0...beads--v0.7.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))


### Refactors

* move guidance into the scripts and contracts that enforce it ([#726](https://github.com/srobroek/agentic-packages/issues/726)) ([40bcfdf](https://github.com/srobroek/agentic-packages/commit/40bcfdf27cd6bbf72db02ce143482eac91d4a4cc))

## [0.7.0](https://github.com/srobroek/agentic-packages/compare/beads--v0.6.2...beads--v0.7.0) (2026-07-25)


### Features

* **orchestrate:** bead-as-brief v2 — claim-bound contracts, delegation-first fleet, cache policy ([#713](https://github.com/srobroek/agentic-packages/issues/713)) ([e8deb15](https://github.com/srobroek/agentic-packages/commit/e8deb151d222e843e9bc80fc6808c9acc141124f))

## [0.6.2](https://github.com/srobroek/agentic-packages/compare/beads--v0.6.1...beads--v0.6.2) (2026-07-23)


### Bug Fixes

* steering matches deployed models and sheds per-session token weight ([#664](https://github.com/srobroek/agentic-packages/issues/664)) ([05ac136](https://github.com/srobroek/agentic-packages/commit/05ac136fb5b81c8a3b2497078eb79d88a4aa9f2c))

## [0.6.1](https://github.com/srobroek/agentic-packages/compare/beads--v0.6.0...beads--v0.6.1) (2026-07-23)


### Bug Fixes

* verify landed work after squash merges ([#569](https://github.com/srobroek/agentic-packages/issues/569)) ([5ddf26a](https://github.com/srobroek/agentic-packages/commit/5ddf26a8a8afb52787eb516896b160485d958feb))

## [0.6.0](https://github.com/srobroek/agentic-packages/compare/beads--v0.5.1...beads--v0.6.0) (2026-07-22)


### Features

* make Codex and Claude APM integration target-aware ([#643](https://github.com/srobroek/agentic-packages/issues/643)) ([83fe64b](https://github.com/srobroek/agentic-packages/commit/83fe64b7bf119cb91aaea3f3d7932b2781a45eee))

## [0.5.1](https://github.com/srobroek/agentic-packages/compare/beads--v0.5.0...beads--v0.5.1) (2026-07-22)


### Bug Fixes

* keep package artifacts stable after tests ([#629](https://github.com/srobroek/agentic-packages/issues/629)) ([f3fec83](https://github.com/srobroek/agentic-packages/commit/f3fec8320f69d1e719fa051473055a2e6e7e43fc))

## [0.5.0](https://github.com/srobroek/agentic-packages/compare/beads--v0.4.2...beads--v0.5.0) (2026-07-22)


### Features

* keep agent replies and decisions in Beads ([#622](https://github.com/srobroek/agentic-packages/issues/622)) ([3e5082c](https://github.com/srobroek/agentic-packages/commit/3e5082c1fda4a36ebd67e78ef5ec234666f54a0d))

## [0.4.2](https://github.com/srobroek/agentic-packages/compare/beads--v0.4.1...beads--v0.4.2) (2026-07-22)


### Documentation

* **beads:** fold Codex-injected guidance into beads context ([#617](https://github.com/srobroek/agentic-packages/issues/617)) ([7dcc2b3](https://github.com/srobroek/agentic-packages/commit/7dcc2b39e2253e1a1936988160930713a8d0c1de))

## [0.4.1](https://github.com/srobroek/agentic-packages/compare/beads--v0.4.0...beads--v0.4.1) (2026-07-20)


### Bug Fixes

* **beads:** hand-correcting mirrored issue labels does not stick ([#566](https://github.com/srobroek/agentic-packages/issues/566)) ([7818094](https://github.com/srobroek/agentic-packages/commit/7818094e5cde5dfe25437cadcaa31e698befeee2))

## [0.4.0](https://github.com/srobroek/agentic-packages/compare/beads--v0.3.0...beads--v0.4.0) (2026-07-20)


### Features

* **beads:** github mirror conventions — credentials, re-labelling, guard interaction ([#563](https://github.com/srobroek/agentic-packages/issues/563)) ([994b15e](https://github.com/srobroek/agentic-packages/commit/994b15e43d766d09c386f3ca9d8a45449fe3f978))

## [0.3.0](https://github.com/srobroek/agentic-packages/compare/beads--v0.2.0...beads--v0.3.0) (2026-07-20)


### Features

* **beads:** subagent work-contract reminder and bead-id delegation rule ([88d8062](https://github.com/srobroek/agentic-packages/commit/88d8062a691a93fb0f946c1ab341356a7a847031))
* subagent beads work-contract reminder and bead-id delegation rule ([81d878b](https://github.com/srobroek/agentic-packages/commit/81d878b7f1602af288055437b9e67ee7632bdcfa))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/beads--v0.1.0...beads--v0.2.0) (2026-07-20)


### Features

* **beads:** add bd remember conventions alongside mempalace ([7327a29](https://github.com/srobroek/agentic-packages/commit/7327a29fc55f55bee4b1179f965e50b793ee4e18))
* **beads:** add beads (bd) conventions package to core ([aa5dde3](https://github.com/srobroek/agentic-packages/commit/aa5dde36215e95048d6d37af479cd0562119e716))
* **beads:** add findings-to-beads convention for read-only skills ([eead303](https://github.com/srobroek/agentic-packages/commit/eead30337f69063c56f4ab0445cbeaa224dc3621))
* **beads:** bead-as-handover rule for work continuing across sessions ([ada9c3b](https://github.com/srobroek/agentic-packages/commit/ada9c3bcb246aead57bdc61f70f21e601081fd34))
* **beads:** deny mutating gh issue commands in beads repos ([06c5873](https://github.com/srobroek/agentic-packages/commit/06c5873f2a59584b0430a36bc3530276be08064b))
* **beads:** git-anchor metadata includes worktree; workers stamp at claim ([97155f8](https://github.com/srobroek/agentic-packages/commit/97155f8152f199553717e507bbcf95921f6ed471))
* **beads:** session-scoped claiming identity and field taxonomy steering ([30edcdc](https://github.com/srobroek/agentic-packages/commit/30edcdcc9af442cbb8b73f65d869f5f1b42be713))


### Bug Fixes

* **beads:** complete field taxonomy — type field, full status set, bounce-back row ([00d00a9](https://github.com/srobroek/agentic-packages/commit/00d00a9b50dff59a5c621cac4a25b58c10bbb19a))
* **beads:** quote-strip and widen anchors in gh issue guard ([6ab1373](https://github.com/srobroek/agentic-packages/commit/6ab1373ccf5117e8449cc063c639bf15936c35b2))

## Changelog
