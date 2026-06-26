# Changelog

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
