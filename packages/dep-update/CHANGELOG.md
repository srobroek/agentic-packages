# Changelog

## [4.1.0](https://github.com/srobroek/agentic-packages/compare/dep-update--v4.0.1...dep-update--v4.1.0) (2026-08-17)


### Features

* **codex:** validate packages and standardize language tooling ([#856](https://github.com/srobroek/agentic-packages/issues/856)) ([42edbfb](https://github.com/srobroek/agentic-packages/commit/42edbfb3948c0103f3ce3ef5ba6819a08ae73566))

## [4.0.1](https://github.com/srobroek/agentic-packages/compare/dep-update--v4.0.0...dep-update--v4.0.1) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [4.0.0](https://github.com/srobroek/agentic-packages/compare/dep-update--v3.0.0...dep-update--v4.0.0) (2026-07-30)


### ⚠ BREAKING CHANGES

* the hooks-worktree and mcp-1mcp packages are removed. Worktree lifecycle and cleanup are owned by hooks-worktrunk, which requires the wt binary; 1mcp has no replacement because nothing used it.
* the hooks-worktree and mcp-1mcp packages are removed. Worktree lifecycle and cleanup are owned by hooks-worktrunk, which requires the wt binary; 1mcp has no replacement because nothing used it.

### Refactors

* consolidate the worktree and chezmoi hooks, drop four dead ones ([#804](https://github.com/srobroek/agentic-packages/issues/804)) ([cb49b0a](https://github.com/srobroek/agentic-packages/commit/cb49b0ab2119642c2902d030f956fd182c4181e2))
* port the skill scripts to Python and fuzz every port ([#811](https://github.com/srobroek/agentic-packages/issues/811)) ([773ac2b](https://github.com/srobroek/agentic-packages/commit/773ac2bced832cb0144b7e21e6937e69b9e3b631))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/dep-update--v2.1.3...dep-update--v3.0.0) (2026-07-27)


### ⚠ BREAKING CHANGES

* **agents:** `agent-coder` is now `agent-builder` and `agent-coder-high` is `agent-builder-high`. The agents `parallel-builder`, `worker`, `coder-high`, `domain-specialist-medium` and `domain-specialist-xhigh` no longer exist; use `builder` with an explicit mode, `builder-high`, or `domain-specialist{,-high}`. Spawn calls naming a removed agent must be updated.

### Bug Fixes

* **agents:** pin every agent to a model, collapse duplicate tiers ([#771](https://github.com/srobroek/agentic-packages/issues/771)) ([fd8193f](https://github.com/srobroek/agentic-packages/commit/fd8193f6e1f8fb7a4bfcb889e24f4ccd5327a7f7))

## [2.1.3](https://github.com/srobroek/agentic-packages/compare/dep-update--v2.1.2...dep-update--v2.1.3) (2026-07-25)


### Refactors

* cut duplicated rules from steering, agents and skills ([#728](https://github.com/srobroek/agentic-packages/issues/728)) ([8f892aa](https://github.com/srobroek/agentic-packages/commit/8f892aa01b3b0ffbb5888cca0dc4178d57ee967d))

## [2.1.2](https://github.com/srobroek/agentic-packages/compare/dep-update--v2.1.1...dep-update--v2.1.2) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [2.1.1](https://github.com/srobroek/agentic-packages/compare/dep-update--v2.1.0...dep-update--v2.1.1) (2026-07-23)


### Bug Fixes

* script dependencies self-declare and agent contracts match reality ([#667](https://github.com/srobroek/agentic-packages/issues/667)) ([6e0f967](https://github.com/srobroek/agentic-packages/commit/6e0f96709f0f88b76461a750e9b46aa5045cede6))

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/dep-update--v2.0.0...dep-update--v2.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/dep-update--v1.0.0...dep-update--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering

### Features

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering ([9cb202d](https://github.com/srobroek/agentic-packages/commit/9cb202d2b76a649dda0489baaeefd61a2e0829e1))


### Bug Fixes

* **skills:** de-hedge and trim descriptions across 17 skill files ([49b5ffa](https://github.com/srobroek/agentic-packages/commit/49b5ffa1555f7f0c8fad6aa4ea6a53dbfaa6873f))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/dep-update--v0.1.0...dep-update--v1.0.0) (2026-06-29)


### ⚠ BREAKING CHANGES

* standalone, agent-driven project scaffolding with git-distributed add-on modules ([#418](https://github.com/srobroek/agentic-packages/issues/418))

### Features

* standalone, agent-driven project scaffolding with git-distributed add-on modules ([#418](https://github.com/srobroek/agentic-packages/issues/418)) ([318dc97](https://github.com/srobroek/agentic-packages/commit/318dc975d485dd04cf1903262b1227242204d482))

## 0.1.0

### Features

* Initial release: interactive dependency upgrade advisory skill. Detects
  ecosystems from lockfiles/manifests, queries PyPI and npm registries for
  current latest versions, classifies bumps as PATCH-SAFE / MINOR-CHECK /
  MAJOR-ADVISORY, surfaces CVEs via native scanners (pip-audit, npm/pnpm
  audit, osv-scanner), and applies patch and minor bumps one at a time behind
  a per-bump confirm. Major bumps are advisory-only and never applied. Reads
  `.project-setup/answers.toml` opportunistically; never writes it.
