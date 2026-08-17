# Changelog

## [2.2.0](https://github.com/srobroek/agentic-packages/compare/agent-hook-contract--v2.1.2...agent-hook-contract--v2.2.0) (2026-08-17)


### Features

* **codex:** validate packages and standardize language tooling ([#856](https://github.com/srobroek/agentic-packages/issues/856)) ([42edbfb](https://github.com/srobroek/agentic-packages/commit/42edbfb3948c0103f3ce3ef5ba6819a08ae73566))

## [2.1.2](https://github.com/srobroek/agentic-packages/compare/agent-hook-contract--v2.1.1...agent-hook-contract--v2.1.2) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [2.1.1](https://github.com/srobroek/agentic-packages/compare/agent-hook-contract--v2.1.0...agent-hook-contract--v2.1.1) (2026-07-30)


### Bug Fixes

* quote frontmatter values holding a colon, so six primitives deploy at all ([#826](https://github.com/srobroek/agentic-packages/issues/826)) ([b3b6325](https://github.com/srobroek/agentic-packages/commit/b3b6325f0bf881160f6977c5257bc76d3c8ccae1))

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/agent-hook-contract--v2.0.0...agent-hook-contract--v2.1.0) (2026-07-30)


### Features

* token-savings package with measured context-cost reduction ([#803](https://github.com/srobroek/agentic-packages/issues/803)) ([14b987e](https://github.com/srobroek/agentic-packages/commit/14b987edb9bcfb2bbcaf6c308af755fcea540f00))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/agent-hook-contract--v1.0.0...agent-hook-contract--v2.0.0) (2026-07-28)


### ⚠ BREAKING CHANGES

* the hook script is now subagent-model-guard.py and requires python3 on PATH.
* the secrets-scan and hooks-precommit-gate packages are removed. Secret scanning moves to the gitleaks pre-commit hook; install real git hooks for tool-independent enforcement.

### Refactors

* drop secrets-scan, hooks-precommit-gate, and the auto-approve hooks ([#792](https://github.com/srobroek/agentic-packages/issues/792)) ([195f194](https://github.com/srobroek/agentic-packages/commit/195f1946b7dd3212c672d827edcc7e2c292e39bc))
* port every remaining shell hook to Python ([#797](https://github.com/srobroek/agentic-packages/issues/797)) ([d01fd9a](https://github.com/srobroek/agentic-packages/commit/d01fd9a79bdc07b01d4477196c5277939fa935a3))

## 1.0.0 (2026-07-28)


### ⚠ BREAKING CHANGES

* the codex-hook-contract package is renamed to agent-hook-contract. Update any dependency pin to the new package path.

### Features

* require Python for agent hooks and generalize the hook contract to Claude and Codex ([#790](https://github.com/srobroek/agentic-packages/issues/790)) ([45d3606](https://github.com/srobroek/agentic-packages/commit/45d36065aa0f56c9e34010388226aef8eb206fd8))


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [0.3.2](https://github.com/srobroek/agentic-packages/compare/codex-hook-contract--v0.3.1...codex-hook-contract--v0.3.2) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [0.3.1](https://github.com/srobroek/agentic-packages/compare/codex-hook-contract--v0.3.0...codex-hook-contract--v0.3.1) (2026-07-22)


### Bug Fixes

* prevent subagents from inheriting unintended models ([44f3d50](https://github.com/srobroek/agentic-packages/commit/44f3d501dfeb3ce2b645e53b5ddc77a63938fdb6))

## [0.3.0](https://github.com/srobroek/agentic-packages/compare/codex-hook-contract--v0.2.1...codex-hook-contract--v0.3.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [0.2.1](https://github.com/srobroek/agentic-packages/compare/codex-hook-contract--v0.2.0...codex-hook-contract--v0.2.1) (2026-07-05)


### Bug Fixes

* remove hardcoded home paths and macOS/Linux portability breaks ([#474](https://github.com/srobroek/agentic-packages/issues/474)) ([c7169ec](https://github.com/srobroek/agentic-packages/commit/c7169ec479439bbbe1f2cbcd5383b1b29452ada1))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/codex-hook-contract-v0.1.0...codex-hook-contract--v0.2.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/codex-hook-contract-v0.0.1...codex-hook-contract-v0.1.0) (2026-06-26)


### Features

* add secrets-scan, dep-audit CI, and codex-hook-contract packages ([#374](https://github.com/srobroek/agentic-packages/issues/374)) ([036efaa](https://github.com/srobroek/agentic-packages/commit/036efaa29b7133a73fad0b3aa652d8d952c7981d))

## 0.0.1

### Features

- **codex-hook-contract:** initial reference doc for the Codex CLI hook contract
  as exercised by this monorepo's guard hooks. Documents, with explicit
  VERIFIED / ASSUMED / UNKNOWN labels: the JSON hook event names (PascalCase in
  `hooks.json`, normalized to snake_case in `config.toml [hooks.state]`); the
  stdin payload shape, including the object-vs-string `.tool_input` ambiguity
  that caused the silent guard bypass fixed in `hooks-git-safety`; and how Codex
  honors a hook decision (the `hookSpecificOutput.permissionDecision` shape used
  by `PreToolUse` guards vs the `hookSpecificOutput.decision.behavior` shape used
  by the `PermissionRequest` hook). Each open claim ships an exact test to run.
  Documentation only -- no scripts, no tests. [skip tests]
