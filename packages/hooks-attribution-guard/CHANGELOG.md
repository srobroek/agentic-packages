# Changelog

## [1.0.1](https://github.com/srobroek/agentic-packages/compare/hooks-attribution-guard-v1.0.0...hooks-attribution-guard-v1.0.1) (2026-06-26)


### Bug Fixes

* use installable package types so hooks + speckit resolve globally ([#387](https://github.com/srobroek/agentic-packages/issues/387)) ([ff2b7a2](https://github.com/srobroek/agentic-packages/commit/ff2b7a2200fc88bcf39abafe9f73ed6f5d31e942))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-attribution-guard-v0.1.0...hooks-attribution-guard-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* mcp-package-version no longer ships the package-file-warn or pkg-version-warn hooks. Installers that relied on those hooks should install hooks-package-file-guard / hooks-pkg-version-warn (or the dependency-quality bundle) instead.

### Features

* add hooks-chezmoi-guard and hooks-attribution-guard guard-hook packages ([#369](https://github.com/srobroek/agentic-packages/issues/369)) ([92814f2](https://github.com/srobroek/agentic-packages/commit/92814f2cb43a8afb417f9c2e6518b822cb8adbab))
* split dependency tooling into independent packages + dependency-quality bundle ([#370](https://github.com/srobroek/agentic-packages/issues/370)) ([03d50a5](https://github.com/srobroek/agentic-packages/commit/03d50a5db3a1572fbe36a4ac1bc1e6877cd96ade))

## 0.1.0

### Features

- **hooks-attribution-guard:** PreToolUse hook (Claude + Codex) that blocks
  `git commit` invocations carrying AI authorship attribution and exits 2 with
  an actionable message. Detects Co-Authored-By trailers naming
  Claude/Anthropic/`noreply@anthropic`, "Generated with/by Claude/AI" phrases,
  "AI-assisted"/"AI-generated" authorship qualifiers, and Claude Code trailer
  URLs. Patterns are scoped to attribution constructs so prose that merely
  mentions AI/Claude (e.g. "fix AI model loading bug") is allowed. Uses the
  type-checked string-form `tool_input` idiom and the proven `git commit`
  anchor (also matches `git -C <path> commit`). Portable to bash 3.2 + BSD grep.
