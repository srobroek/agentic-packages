# Changelog

## [2.3.1](https://github.com/srobroek/agentic-packages/compare/worktrunk-writer--v2.3.0...worktrunk-writer--v2.3.1) (2026-08-22)


### Bug Fixes

* merge bead no longer blocks its own implementer from taking a lease ([#877](https://github.com/srobroek/agentic-packages/issues/877)) ([59f130d](https://github.com/srobroek/agentic-packages/commit/59f130dc32b641192c631a8f492ceb54cb6be9d3))

## [2.3.0](https://github.com/srobroek/agentic-packages/compare/worktrunk-writer--v2.2.1...worktrunk-writer--v2.3.0) (2026-08-17)


### Features

* **codex:** validate packages and standardize language tooling ([#856](https://github.com/srobroek/agentic-packages/issues/856)) ([42edbfb](https://github.com/srobroek/agentic-packages/commit/42edbfb3948c0103f3ce3ef5ba6819a08ae73566))

## [2.2.1](https://github.com/srobroek/agentic-packages/compare/worktrunk-writer--v2.2.0...worktrunk-writer--v2.2.1) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [2.2.0](https://github.com/srobroek/agentic-packages/compare/worktrunk-writer--v2.1.1...worktrunk-writer--v2.2.0) (2026-07-30)


### Features

* **worktrunk-writer:** a SubagentStop trigger that records the exit ([#817](https://github.com/srobroek/agentic-packages/issues/817)) ([5616f53](https://github.com/srobroek/agentic-packages/commit/5616f534abfef3c1943d9b191a059d965439c5af))


### Bug Fixes

* **worktrunk-writer:** say which path was rejected and that a leading cd is missing ([#830](https://github.com/srobroek/agentic-packages/issues/830)) ([f7275c4](https://github.com/srobroek/agentic-packages/commit/f7275c403345e306585760488c8c96fb773bcc90))

## [2.1.1](https://github.com/srobroek/agentic-packages/compare/worktrunk-writer--v2.1.0...worktrunk-writer--v2.1.1) (2026-07-30)


### Bug Fixes

* **worktrunk-writer:** a tracking merge bead is not a competing lease ([#818](https://github.com/srobroek/agentic-packages/issues/818)) ([1761d0d](https://github.com/srobroek/agentic-packages/commit/1761d0d5f4b4c66d752cb7ed7cfeae4c1ab0b6d8))

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/worktrunk-writer--v2.0.1...worktrunk-writer--v2.1.0) (2026-07-30)


### Features

* recover a stuck agent worktree instead of rebuilding it ([#810](https://github.com/srobroek/agentic-packages/issues/810)) ([2b3a06c](https://github.com/srobroek/agentic-packages/commit/2b3a06c87bfb956da078c370268a851a380d5f8b))


### Bug Fixes

* **worktrunk-writer:** gate the SubagentStart handshake on protocol engagement ([#819](https://github.com/srobroek/agentic-packages/issues/819)) ([74e1959](https://github.com/srobroek/agentic-packages/commit/74e1959c718f849a195374a5b33b42896cb2e103))
* **worktrunk-writer:** resolve a WAIT checkout against its own repo ([#805](https://github.com/srobroek/agentic-packages/issues/805)) ([106254f](https://github.com/srobroek/agentic-packages/commit/106254fc7246441232a2a805e35e78a7e9b3e4c5))

## [2.0.1](https://github.com/srobroek/agentic-packages/compare/worktrunk-writer--v2.0.0...worktrunk-writer--v2.0.1) (2026-07-27)


### Bug Fixes

* give every APM instruction an explicit applyTo, add drift guard ([#769](https://github.com/srobroek/agentic-packages/issues/769)) ([d983034](https://github.com/srobroek/agentic-packages/commit/d98303486d87b5dfb348a4a04fa435afa5fce692))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/worktrunk-writer--v1.2.0...worktrunk-writer--v2.0.0) (2026-07-25)


### ⚠ BREAKING CHANGES

* **worktrunk-writer:** stop the hook blocking all delegation repo-wide ([#729](https://github.com/srobroek/agentic-packages/issues/729))

### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))
* **worktrunk-writer:** advise unleased delegation and stop overstating the gate ([#730](https://github.com/srobroek/agentic-packages/issues/730)) ([f122e2a](https://github.com/srobroek/agentic-packages/commit/f122e2a15699dfda808ccf9e0e3f8fe2d00b08d0))
* **worktrunk-writer:** stop the hook blocking all delegation repo-wide ([#729](https://github.com/srobroek/agentic-packages/issues/729)) ([e2292c6](https://github.com/srobroek/agentic-packages/commit/e2292c6c568f801fb96d70df3afffc923e6cc767))

## [1.2.0](https://github.com/srobroek/agentic-packages/compare/worktrunk-writer--v1.1.0...worktrunk-writer--v1.2.0) (2026-07-25)


### Features

* enforce Worktrunk worktree lifecycle for agents ([46ec4cb](https://github.com/srobroek/agentic-packages/commit/46ec4cb5385c41020870b5492f1f83a7c8e59d14))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/worktrunk-writer--v1.0.0...worktrunk-writer--v1.1.0) (2026-07-23)


### Features

* agent linter catches empty descriptions, over-constraint, missing triggers, and bloat ([#672](https://github.com/srobroek/agentic-packages/issues/672)) ([47feb78](https://github.com/srobroek/agentic-packages/commit/47feb78421542944aa0f1ee7947e1b3ebab0f08d))

## 1.0.0 (2026-07-22)


### Features

* make Codex and Claude APM integration target-aware ([#643](https://github.com/srobroek/agentic-packages/issues/643)) ([83fe64b](https://github.com/srobroek/agentic-packages/commit/83fe64b7bf119cb91aaea3f3d7932b2781a45eee))


### Bug Fixes

* prevent duplicate and invalid release notes ([#645](https://github.com/srobroek/agentic-packages/issues/645)) ([01d3689](https://github.com/srobroek/agentic-packages/commit/01d3689d03245a46adb511b04cb3d12ce1c7b603))
