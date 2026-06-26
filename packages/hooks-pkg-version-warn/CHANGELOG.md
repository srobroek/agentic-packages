# Changelog

## 0.1.0

### Features

- **hooks-pkg-version-warn:** PreToolUse:Bash hook (Claude + Codex) that nudges
  toward installing the latest compatible version when a package install command
  is detected (`pnpm add`/`pnpm install`/`npm install`/`npm add`/`yarn add`,
  `uv add`/`uv pip install`/`pip install`, `go get`, `gem install`/`bundle add`,
  `composer require`). Advisory only via `additionalContext`, never blocks;
  `cargo add` is intentionally silent because it fetches latest by default. The
  script self-gates on the leading command token (verb + subcommand) so a
  substring such as `echo "pip install ..."` or `grep "npm install"` does not
  trip the advisory — its hook JSON carries no `if` filter (fixing the broken
  pipe-alternation `if` the original mcp-package-version variant relied on).
  Uses the type-checked string-form `tool_input` idiom and is portable to
  bash 3.2 + BSD utilities.
