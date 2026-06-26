# Changelog

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
