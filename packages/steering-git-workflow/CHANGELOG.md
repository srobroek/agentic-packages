# Changelog

## [2.3.3](https://github.com/srobroek/agentic-packages/compare/steering-git-workflow--v2.3.2...steering-git-workflow--v2.3.3) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [2.3.2](https://github.com/srobroek/agentic-packages/compare/steering-git-workflow--v2.3.1...steering-git-workflow--v2.3.2) (2026-07-23)


### Bug Fixes

* hook sanitizer detects dead project-level entries and PR guard fails open ([#665](https://github.com/srobroek/agentic-packages/issues/665)) ([0f1dbff](https://github.com/srobroek/agentic-packages/commit/0f1dbff9bf6d2021751f6f10f2903dcb45875092))

## [2.3.1](https://github.com/srobroek/agentic-packages/compare/steering-git-workflow--v2.3.0...steering-git-workflow--v2.3.1) (2026-07-23)


### Bug Fixes

* verify landed work after squash merges ([#569](https://github.com/srobroek/agentic-packages/issues/569)) ([5ddf26a](https://github.com/srobroek/agentic-packages/commit/5ddf26a8a8afb52787eb516896b160485d958feb))

## [2.3.0](https://github.com/srobroek/agentic-packages/compare/steering-git-workflow--v2.2.0...steering-git-workflow--v2.3.0) (2026-07-22)


### Features

* make Codex and Claude APM integration target-aware ([#643](https://github.com/srobroek/agentic-packages/issues/643)) ([83fe64b](https://github.com/srobroek/agentic-packages/commit/83fe64b7bf119cb91aaea3f3d7932b2781a45eee))


### Bug Fixes

* prevent duplicate and invalid release notes ([#645](https://github.com/srobroek/agentic-packages/issues/645)) ([01d3689](https://github.com/srobroek/agentic-packages/commit/01d3689d03245a46adb511b04cb3d12ce1c7b603))

## [2.2.0](https://github.com/srobroek/agentic-packages/compare/steering-git-workflow--v2.1.0...steering-git-workflow--v2.2.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/steering-git-workflow--v2.0.0...steering-git-workflow--v2.1.0) (2026-07-07)


### Features

* **hooks:** stable rule IDs for git-workflow, bash-safety, and git-safety guards ([#494](https://github.com/srobroek/agentic-packages/issues/494)) ([d46a50a](https://github.com/srobroek/agentic-packages/commit/d46a50ab266a706728455e127c906b87d73bba55))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/steering-git-workflow--v1.0.0...steering-git-workflow--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* the removed packages are no longer published; installs referencing them must update to core >=7 bundles.

### Features

* retire 13 nudge/duplicate packages in favor of static steering ([a2fc229](https://github.com/srobroek/agentic-packages/commit/a2fc229311e85435af1ba9ff1c172016f611436e))
