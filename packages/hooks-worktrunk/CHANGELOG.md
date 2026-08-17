# Changelog

## [4.1.0](https://github.com/srobroek/agentic-packages/compare/hooks-worktrunk--v4.0.2...hooks-worktrunk--v4.1.0) (2026-08-17)


### Features

* **codex:** validate packages and standardize language tooling ([#856](https://github.com/srobroek/agentic-packages/issues/856)) ([42edbfb](https://github.com/srobroek/agentic-packages/commit/42edbfb3948c0103f3ce3ef5ba6819a08ae73566))

## [4.0.2](https://github.com/srobroek/agentic-packages/compare/hooks-worktrunk--v4.0.1...hooks-worktrunk--v4.0.2) (2026-08-17)


### Bug Fixes

* one undecodable byte no longer silences eleven more guards ([#852](https://github.com/srobroek/agentic-packages/issues/852)) ([3fb5835](https://github.com/srobroek/agentic-packages/commit/3fb58352d2f37ba67adc14ba3c03d204c1507a9e))

## [4.0.1](https://github.com/srobroek/agentic-packages/compare/hooks-worktrunk--v4.0.0...hooks-worktrunk--v4.0.1) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [4.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-worktrunk--v3.0.0...hooks-worktrunk--v4.0.0) (2026-07-30)


### ⚠ BREAKING CHANGES

* the hooks-worktree and mcp-1mcp packages are removed. Worktree lifecycle and cleanup are owned by hooks-worktrunk, which requires the wt binary; 1mcp has no replacement because nothing used it.
* the hooks-worktree and mcp-1mcp packages are removed. Worktree lifecycle and cleanup are owned by hooks-worktrunk, which requires the wt binary; 1mcp has no replacement because nothing used it.

### Features

* token-savings package with measured context-cost reduction ([#803](https://github.com/srobroek/agentic-packages/issues/803)) ([14b987e](https://github.com/srobroek/agentic-packages/commit/14b987edb9bcfb2bbcaf6c308af755fcea540f00))


### Bug Fixes

* close two guard bypasses found by fuzzing the Python hooks ([#806](https://github.com/srobroek/agentic-packages/issues/806)) ([7505cc7](https://github.com/srobroek/agentic-packages/commit/7505cc76fccad74c1ba0c5d2d017320b721475ff))


### Refactors

* consolidate the worktree and chezmoi hooks, drop four dead ones ([#804](https://github.com/srobroek/agentic-packages/issues/804)) ([cb49b0a](https://github.com/srobroek/agentic-packages/commit/cb49b0ab2119642c2902d030f956fd182c4181e2))

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
