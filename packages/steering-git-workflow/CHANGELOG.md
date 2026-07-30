# Changelog

## [4.0.1](https://github.com/srobroek/agentic-packages/compare/steering-git-workflow--v4.0.0...steering-git-workflow--v4.0.1) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [4.0.0](https://github.com/srobroek/agentic-packages/compare/steering-git-workflow--v3.0.0...steering-git-workflow--v4.0.0) (2026-07-30)


### ⚠ BREAKING CHANGES

* merge-bead trailers are no longer required outside an orchestrate run, and are advisory rather than blocking inside one. A repository that relied on this hook to enforce merge-queue linkage on every PR must set PR_MERGE_QUEUE_ENFORCE, and must treat the advisory rather than a denial as the signal.

### Bug Fixes

* drop the PR bead trailers, and have the shepherd verify its own anchors ([#824](https://github.com/srobroek/agentic-packages/issues/824)) ([4ea4081](https://github.com/srobroek/agentic-packages/commit/4ea4081e6f7acb95d49cb977c69e1e119471f983))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/steering-git-workflow--v2.3.6...steering-git-workflow--v3.0.0) (2026-07-28)


### ⚠ BREAKING CHANGES

* commands that previously passed silently are now judged. A destructive verb inside an inline shell string, or behind timeout, flock, or nice with an option value, is denied where it was allowed, and a download piped to any interpreter now warns.
* **steering-git-workflow:** the hook script is now attribution-guard.py and requires python3 on PATH.

### Bug Fixes

* **steering-git-workflow:** stop blocking pull requests when the policy check cannot verify them ([#794](https://github.com/srobroek/agentic-packages/issues/794)) ([023c0f0](https://github.com/srobroek/agentic-packages/commit/023c0f087717a57386d18d06f2575fca0435b7b1))
* stop the hook guards blocking correct work, and close the wrapper bypasses ([#796](https://github.com/srobroek/agentic-packages/issues/796)) ([217a455](https://github.com/srobroek/agentic-packages/commit/217a4559fe3d0be9fb2751ffbefd41dfe8903f0d))

## [2.3.6](https://github.com/srobroek/agentic-packages/compare/steering-git-workflow--v2.3.5...steering-git-workflow--v2.3.6) (2026-07-27)


### Bug Fixes

* give every APM instruction an explicit applyTo, add drift guard ([#769](https://github.com/srobroek/agentic-packages/issues/769)) ([d983034](https://github.com/srobroek/agentic-packages/commit/d98303486d87b5dfb348a4a04fa435afa5fce692))

## [2.3.5](https://github.com/srobroek/agentic-packages/compare/steering-git-workflow--v2.3.4...steering-git-workflow--v2.3.5) (2026-07-26)


### Bug Fixes

* **steering-git-workflow:** resolve the PR guard's beads workspace correctly ([#757](https://github.com/srobroek/agentic-packages/issues/757)) ([66d0609](https://github.com/srobroek/agentic-packages/commit/66d060993152638c77671d48d6f3fb9c3232c887))

## [2.3.4](https://github.com/srobroek/agentic-packages/compare/steering-git-workflow--v2.3.3...steering-git-workflow--v2.3.4) (2026-07-25)


### Refactors

* cut duplicated rules from steering, agents and skills ([#728](https://github.com/srobroek/agentic-packages/issues/728)) ([8f892aa](https://github.com/srobroek/agentic-packages/commit/8f892aa01b3b0ffbb5888cca0dc4178d57ee967d))

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
