# Changelog

## [1.0.1](https://github.com/srobroek/agentic-packages/compare/hooks-package-file-guard-v1.0.0...hooks-package-file-guard-v1.0.1) (2026-06-26)


### Bug Fixes

* use installable package types so hooks + speckit resolve globally ([#387](https://github.com/srobroek/agentic-packages/issues/387)) ([ff2b7a2](https://github.com/srobroek/agentic-packages/commit/ff2b7a2200fc88bcf39abafe9f73ed6f5d31e942))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-package-file-guard-v0.1.0...hooks-package-file-guard-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* mcp-package-version no longer ships the package-file-warn or pkg-version-warn hooks. Installers that relied on those hooks should install hooks-package-file-guard / hooks-pkg-version-warn (or the dependency-quality bundle) instead.

### Features

* split dependency tooling into independent packages + dependency-quality bundle ([#370](https://github.com/srobroek/agentic-packages/issues/370)) ([03d50a5](https://github.com/srobroek/agentic-packages/commit/03d50a5db3a1572fbe36a4ac1bc1e6877cd96ade))

## 0.1.0

### Features

* **hooks-package-file-guard:** initial release. Non-blocking PreToolUse hook
  (Edit/Write/MultiEdit) that warns when a dependency manifest is edited
  directly — `package.json`, `Cargo.toml`, `go.mod`, `pyproject.toml`,
  `Gemfile`, `composer.json` — steering toward the package manager's add command
  (`pnpm add`, `cargo add`, `go get`, `uv add`, `bundle add`, `composer
  require`). Advisory only (additionalContext); never blocks. Keys on the file
  path (`.tool_input.file_path` / `.notebook_path`) only — the Edit tool's
  replacement text is never treated as a path. Non-manifest edits and malformed
  stdin pass cleanly (exit 0). Cross-tool (Claude + Codex).
