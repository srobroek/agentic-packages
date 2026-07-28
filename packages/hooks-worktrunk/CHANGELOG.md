# Changelog

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-worktrunk--v2.0.1...hooks-worktrunk--v3.0.0) (2026-07-28)


### ⚠ BREAKING CHANGES

* commands that previously passed silently are now judged. A destructive verb inside an inline shell string, or behind timeout, flock, or nice with an option value, is denied where it was allowed, and a download piped to any interpreter now warns.

### Bug Fixes

* stop the hook guards blocking correct work, and close the wrapper bypasses ([#796](https://github.com/srobroek/agentic-packages/issues/796)) ([217a455](https://github.com/srobroek/agentic-packages/commit/217a4559fe3d0be9fb2751ffbefd41dfe8903f0d))

## [2.0.1](https://github.com/srobroek/agentic-packages/compare/hooks-worktrunk--v2.0.0...hooks-worktrunk--v2.0.1) (2026-07-27)


### Bug Fixes

* give every APM instruction an explicit applyTo, add drift guard ([#769](https://github.com/srobroek/agentic-packages/issues/769)) ([d983034](https://github.com/srobroek/agentic-packages/commit/d98303486d87b5dfb348a4a04fa435afa5fce692))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-worktrunk--v1.0.0...hooks-worktrunk--v2.0.0) (2026-07-25)


### ⚠ BREAKING CHANGES

* deny unmanaged agent worktrees and route the native worktree lifecycle through Worktrunk ([#725](https://github.com/srobroek/agentic-packages/issues/725))

### Features

* deny unmanaged agent worktrees and route the native worktree lifecycle through Worktrunk ([#725](https://github.com/srobroek/agentic-packages/issues/725)) ([cc5e4d1](https://github.com/srobroek/agentic-packages/commit/cc5e4d145d50d5aa668cb6ce35d71443d3405966))


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## 1.0.0 (2026-07-25)


### Features

* enforce Worktrunk worktree lifecycle for agents ([46ec4cb](https://github.com/srobroek/agentic-packages/commit/46ec4cb5385c41020870b5492f1f83a7c8e59d14))
