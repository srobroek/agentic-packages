# Changelog

## [1.0.2](https://github.com/srobroek/agentic-packages/compare/hooks-close-keywords--v1.0.1...hooks-close-keywords--v1.0.2) (2026-08-17)


### Bug Fixes

* one undecodable byte no longer silences eleven more guards ([#852](https://github.com/srobroek/agentic-packages/issues/852)) ([3fb5835](https://github.com/srobroek/agentic-packages/commit/3fb58352d2f37ba67adc14ba3c03d204c1507a9e))

## [1.0.1](https://github.com/srobroek/agentic-packages/compare/hooks-close-keywords--v1.0.0...hooks-close-keywords--v1.0.1) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-close-keywords--v0.6.1...hooks-close-keywords--v1.0.0) (2026-07-28)


### ⚠ BREAKING CHANGES

* the PreToolUse hook is now pr-close-guard.py and the pre-commit entry is commit-msg-rewrite.py; both require python3 on PATH. A project that vendored normalize-closes.sh must re-vendor commit-msg-rewrite.py alongside close_keywords.py.

### Refactors

* port the close-keyword hooks to Python ([#795](https://github.com/srobroek/agentic-packages/issues/795)) ([472e125](https://github.com/srobroek/agentic-packages/commit/472e125a9e57efbc447a6b92a8d38a144916c8c9))

## [0.6.1](https://github.com/srobroek/agentic-packages/compare/hooks-close-keywords--v0.6.0...hooks-close-keywords--v0.6.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [0.6.0](https://github.com/srobroek/agentic-packages/compare/hooks-close-keywords--v0.5.1...hooks-close-keywords--v0.6.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [0.5.1](https://github.com/srobroek/agentic-packages/compare/hooks-close-keywords--v0.5.0...hooks-close-keywords--v0.5.1) (2026-07-02)


### Performance

* **hooks:** cut PreToolUse:Bash hot-path cost with pre-jq bail + single-parse ([#450](https://github.com/srobroek/agentic-packages/issues/450)) ([58c1ce1](https://github.com/srobroek/agentic-packages/commit/58c1ce168e99ef1ac63427903c9180bf1ae916fe))

## [0.5.0](https://github.com/srobroek/agentic-packages/compare/hooks-close-keywords--v0.4.0...hooks-close-keywords--v0.5.0) (2026-06-30)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))
* tighten autonomous-agent hook guards; add precommit-gate and close-keywords packages ([#391](https://github.com/srobroek/agentic-packages/issues/391)) ([34f155a](https://github.com/srobroek/agentic-packages/commit/34f155aab3ae1586b2ce16e2418a30a9d47b5137))


### Bug Fixes

* **hooks:** correct invalid package type hooks-&gt;instructions ([#397](https://github.com/srobroek/agentic-packages/issues/397)) ([ad12eaf](https://github.com/srobroek/agentic-packages/commit/ad12eaff7ba5691304f43388d5ca6ee0aac81946))
* **hooks:** rework PreToolUse guards to never stall auto mode ([#432](https://github.com/srobroek/agentic-packages/issues/432)) ([e00ebb7](https://github.com/srobroek/agentic-packages/commit/e00ebb723fd8e00031fdf28c02ca6b846053d652))

## [0.3.0](https://github.com/srobroek/agentic-packages/compare/hooks-close-keywords-v0.2.1...hooks-close-keywords--v0.3.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [0.2.1](https://github.com/srobroek/agentic-packages/compare/hooks-close-keywords-v0.2.0...hooks-close-keywords-v0.2.1) (2026-06-26)


### Bug Fixes

* **hooks:** correct invalid package type hooks-&gt;instructions ([#397](https://github.com/srobroek/agentic-packages/issues/397)) ([ad12eaf](https://github.com/srobroek/agentic-packages/commit/ad12eaff7ba5691304f43388d5ca6ee0aac81946))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/hooks-close-keywords-v0.1.0...hooks-close-keywords-v0.2.0) (2026-06-26)


### Features

* tighten autonomous-agent hook guards; add precommit-gate and close-keywords packages ([#391](https://github.com/srobroek/agentic-packages/issues/391)) ([34f155a](https://github.com/srobroek/agentic-packages/commit/34f155aab3ae1586b2ce16e2418a30a9d47b5137))

## Changelog
