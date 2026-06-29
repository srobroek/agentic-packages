# Changelog

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/hooks-pkg-version-warn-v1.0.1...hooks-pkg-version-warn--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.1](https://github.com/srobroek/agentic-packages/compare/hooks-pkg-version-warn-v1.0.0...hooks-pkg-version-warn-v1.0.1) (2026-06-26)


### Bug Fixes

* use installable package types so hooks + speckit resolve globally ([#387](https://github.com/srobroek/agentic-packages/issues/387)) ([ff2b7a2](https://github.com/srobroek/agentic-packages/commit/ff2b7a2200fc88bcf39abafe9f73ed6f5d31e942))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-pkg-version-warn-v0.1.0...hooks-pkg-version-warn-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* mcp-package-version no longer ships the package-file-warn or pkg-version-warn hooks. Installers that relied on those hooks should install hooks-package-file-guard / hooks-pkg-version-warn (or the dependency-quality bundle) instead.

### Features

* split dependency tooling into independent packages + dependency-quality bundle ([#370](https://github.com/srobroek/agentic-packages/issues/370)) ([03d50a5](https://github.com/srobroek/agentic-packages/commit/03d50a5db3a1572fbe36a4ac1bc1e6877cd96ade))

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
