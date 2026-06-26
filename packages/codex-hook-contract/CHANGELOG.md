# Changelog

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
