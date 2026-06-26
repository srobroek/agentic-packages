# Changelog

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/secrets-scan-v1.0.0...secrets-scan-v1.1.0) (2026-06-26)


### Features

* tighten autonomous-agent hook guards; add precommit-gate and close-keywords packages ([#391](https://github.com/srobroek/agentic-packages/issues/391)) ([34f155a](https://github.com/srobroek/agentic-packages/commit/34f155aab3ae1586b2ce16e2418a30a9d47b5137))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/secrets-scan-v0.1.0...secrets-scan-v1.0.0) (2026-06-26)


### Features

* add secrets-scan, dep-audit CI, and codex-hook-contract packages ([#374](https://github.com/srobroek/agentic-packages/issues/374)) ([036efaa](https://github.com/srobroek/agentic-packages/commit/036efaa29b7133a73fad0b3aa652d8d952c7981d))


### Bug Fixes

* co-locate skill scripts so they resolve after install ([#376](https://github.com/srobroek/agentic-packages/issues/376)) ([1bb71cc](https://github.com/srobroek/agentic-packages/commit/1bb71ccac2ac14992506bddf11f0ae0ff5db5d0d))


### Chores

* release whats-new and secrets-scan at 1.0.0 ([#382](https://github.com/srobroek/agentic-packages/issues/382)) ([1a153fb](https://github.com/srobroek/agentic-packages/commit/1a153fbbbe8271cfb6856b5638452c95c4c49e34))

## 0.1.0

### Features

- **secrets-scan:** New hybrid package (skill + pre-commit hook) closing the gap
  where commit steering says to check for secrets but ships no tool. `scan.sh`
  auto-detects a scanner on PATH (gitleaks preferred, then trufflehog), scans the
  staged diff (`--staged`, default) or the working tree (`--working`), redacts
  matches, and exits with a stable contract: 0 clean, 1 finding, 2 no scanner.
- **secrets-scan:** PreToolUse hook (Claude + Codex) on `git commit` runs the
  scanner over the staged diff and blocks the commit (exit 2) with an actionable
  message and a documented bypass when a secret is found. When no scanner is
  installed it WARNs and allows the commit -- missing tooling never blocks work.
  Honors a `SECRETS_SCAN_SKIP=1` bypass (env var or inline command prefix). Uses
  the type-checked string-form `tool_input` idiom and the proven `git commit`
  anchor (also matches `git -C <path> commit`). Portable to bash 3.2 + BSD grep.
