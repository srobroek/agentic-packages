# Changelog

## [3.1.0](https://github.com/srobroek/agentic-packages/compare/hooks-attribution-guard--v3.0.2...hooks-attribution-guard--v3.1.0) (2026-08-17)


### Features

* **codex:** validate packages and standardize language tooling ([#856](https://github.com/srobroek/agentic-packages/issues/856)) ([42edbfb](https://github.com/srobroek/agentic-packages/commit/42edbfb3948c0103f3ce3ef5ba6819a08ae73566))

## [3.0.2](https://github.com/srobroek/agentic-packages/compare/hooks-attribution-guard--v3.0.1...hooks-attribution-guard--v3.0.2) (2026-08-17)


### Bug Fixes

* one undecodable byte no longer silences eleven more guards ([#852](https://github.com/srobroek/agentic-packages/issues/852)) ([3fb5835](https://github.com/srobroek/agentic-packages/commit/3fb58352d2f37ba67adc14ba3c03d204c1507a9e))

## [3.0.1](https://github.com/srobroek/agentic-packages/compare/hooks-attribution-guard--v3.0.0...hooks-attribution-guard--v3.0.1) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-attribution-guard--v2.1.1...hooks-attribution-guard--v3.0.0) (2026-07-28)


### ⚠ BREAKING CHANGES

* commands that previously passed silently are now judged. A destructive verb inside an inline shell string, or behind timeout, flock, or nice with an option value, is denied where it was allowed, and a download piped to any interpreter now warns.
* **steering-git-workflow:** the hook script is now attribution-guard.py and requires python3 on PATH.

### Bug Fixes

* **steering-git-workflow:** stop blocking pull requests when the policy check cannot verify them ([#794](https://github.com/srobroek/agentic-packages/issues/794)) ([023c0f0](https://github.com/srobroek/agentic-packages/commit/023c0f087717a57386d18d06f2575fca0435b7b1))
* stop the hook guards blocking correct work, and close the wrapper bypasses ([#796](https://github.com/srobroek/agentic-packages/issues/796)) ([217a455](https://github.com/srobroek/agentic-packages/commit/217a4559fe3d0be9fb2751ffbefd41dfe8903f0d))

## [2.1.1](https://github.com/srobroek/agentic-packages/compare/hooks-attribution-guard--v2.1.0...hooks-attribution-guard--v2.1.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/hooks-attribution-guard--v2.0.1...hooks-attribution-guard--v2.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [2.0.1](https://github.com/srobroek/agentic-packages/compare/hooks-attribution-guard--v2.0.0...hooks-attribution-guard--v2.0.1) (2026-07-02)


### Performance

* **hooks:** cut PreToolUse:Bash hot-path cost with pre-jq bail + single-parse ([#450](https://github.com/srobroek/agentic-packages/issues/450)) ([58c1ce1](https://github.com/srobroek/agentic-packages/commit/58c1ce168e99ef1ac63427903c9180bf1ae916fe))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-attribution-guard--v1.3.0...hooks-attribution-guard--v2.0.0) (2026-06-30)


### ⚠ BREAKING CHANGES

* mcp-package-version no longer ships the package-file-warn or pkg-version-warn hooks. Installers that relied on those hooks should install hooks-package-file-guard / hooks-pkg-version-warn (or the dependency-quality bundle) instead.

### Features

* add hooks-chezmoi-guard and hooks-attribution-guard guard-hook packages ([#369](https://github.com/srobroek/agentic-packages/issues/369)) ([92814f2](https://github.com/srobroek/agentic-packages/commit/92814f2cb43a8afb417f9c2e6518b822cb8adbab))
* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))
* split dependency tooling into independent packages + dependency-quality bundle ([#370](https://github.com/srobroek/agentic-packages/issues/370)) ([03d50a5](https://github.com/srobroek/agentic-packages/commit/03d50a5db3a1572fbe36a4ac1bc1e6877cd96ade))
* tighten autonomous-agent hook guards; add precommit-gate and close-keywords packages ([#391](https://github.com/srobroek/agentic-packages/issues/391)) ([34f155a](https://github.com/srobroek/agentic-packages/commit/34f155aab3ae1586b2ce16e2418a30a9d47b5137))


### Bug Fixes

* **hooks:** rework PreToolUse guards to never stall auto mode ([#432](https://github.com/srobroek/agentic-packages/issues/432)) ([e00ebb7](https://github.com/srobroek/agentic-packages/commit/e00ebb723fd8e00031fdf28c02ca6b846053d652))
* use installable package types so hooks + speckit resolve globally ([#387](https://github.com/srobroek/agentic-packages/issues/387)) ([ff2b7a2](https://github.com/srobroek/agentic-packages/commit/ff2b7a2200fc88bcf39abafe9f73ed6f5d31e942))

## [1.2.0](https://github.com/srobroek/agentic-packages/compare/hooks-attribution-guard-v1.1.0...hooks-attribution-guard--v1.2.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/hooks-attribution-guard-v1.0.1...hooks-attribution-guard-v1.1.0) (2026-06-26)


### Features

* tighten autonomous-agent hook guards; add precommit-gate and close-keywords packages ([#391](https://github.com/srobroek/agentic-packages/issues/391)) ([34f155a](https://github.com/srobroek/agentic-packages/commit/34f155aab3ae1586b2ce16e2418a30a9d47b5137))

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
