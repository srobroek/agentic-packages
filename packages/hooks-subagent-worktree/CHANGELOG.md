# Changelog

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/hooks-subagent-worktree--v2.0.0...hooks-subagent-worktree--v2.1.0) (2026-07-08)


### Features

* agents clean up worktrees and build artifacts when they finish ([#498](https://github.com/srobroek/agentic-packages/issues/498)) ([eed91e5](https://github.com/srobroek/agentic-packages/commit/eed91e55e50c6e1cc6559011fc1f8baac2ee00d5))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-subagent-worktree--v1.0.0...hooks-subagent-worktree--v2.0.0) (2026-07-05)


### ⚠ BREAKING CHANGES

* **hooks-subagent-worktree:** the PreToolUse:Agent hook no longer denies subagent spawns or requires [iso:*] sentinels. It now posts a non-blocking advisory: if a subagent writes and runs in parallel, use isolation:"worktree"; if it runs isolated, commit before finishing so the worktree branch retains the work. Stays silent once isolation is declared. The 1.x deny-gate guessed wrong too often and blocked legitimate work; cmux native integration + Claude's native worktree lifecycle (baseRef=head) now cover what the gate approximated.

### Features

* **hooks-subagent-worktree:** convert deny-gate to non-blocking advisory ([#473](https://github.com/srobroek/agentic-packages/issues/473)) ([3bb8722](https://github.com/srobroek/agentic-packages/commit/3bb87228c332d6edd7e9e0c7011c679667c2bad6))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-subagent-worktree--v0.5.0...hooks-subagent-worktree--v1.0.0) (2026-07-03)


### ⚠ BREAKING CHANGES

* enforce subagent isolation with a 3-token model (readonly/extern/direct) and primary-checkout deny gate ([#458](https://github.com/srobroek/agentic-packages/issues/458))

### Features

* add hooks-subagent-worktree enforcement package ([#384](https://github.com/srobroek/agentic-packages/issues/384)) ([608d757](https://github.com/srobroek/agentic-packages/commit/608d7572168e06ae15788f7ed8f367f300ae0b74))
* enforce subagent isolation with a 3-token model (readonly/extern/direct) and primary-checkout deny gate ([#458](https://github.com/srobroek/agentic-packages/issues/458)) ([3cfc4c0](https://github.com/srobroek/agentic-packages/commit/3cfc4c060c75536319ae5ed57716b5190a4ad223))
* **hooks-subagent-worktree:** ship spawn-tagging instruction; fix type to hybrid ([#390](https://github.com/srobroek/agentic-packages/issues/390)) ([da05500](https://github.com/srobroek/agentic-packages/commit/da055000f7469ae7e96809c3c1181485bb7db9e9))
* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))


### Bug Fixes

* **agents:** stop treating different-repo/direct-edit as isolation-free under concurrency ([#456](https://github.com/srobroek/agentic-packages/issues/456)) ([f4d0a21](https://github.com/srobroek/agentic-packages/commit/f4d0a21ae289f6554387ce0ad2cafb662b0d9c66))
* use installable package types so hooks + speckit resolve globally ([#387](https://github.com/srobroek/agentic-packages/issues/387)) ([ff2b7a2](https://github.com/srobroek/agentic-packages/commit/ff2b7a2200fc88bcf39abafe9f73ed6f5d31e942))

## [0.4.0](https://github.com/srobroek/agentic-packages/compare/hooks-subagent-worktree-v0.3.0...hooks-subagent-worktree--v0.4.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [0.3.0](https://github.com/srobroek/agentic-packages/compare/hooks-subagent-worktree-v0.2.1...hooks-subagent-worktree-v0.3.0) (2026-06-26)


### Features

* **hooks-subagent-worktree:** ship spawn-tagging instruction; fix type to hybrid ([#390](https://github.com/srobroek/agentic-packages/issues/390)) ([da05500](https://github.com/srobroek/agentic-packages/commit/da055000f7469ae7e96809c3c1181485bb7db9e9))

## [0.2.1](https://github.com/srobroek/agentic-packages/compare/hooks-subagent-worktree-v0.2.0...hooks-subagent-worktree-v0.2.1) (2026-06-26)


### Bug Fixes

* use installable package types so hooks + speckit resolve globally ([#387](https://github.com/srobroek/agentic-packages/issues/387)) ([ff2b7a2](https://github.com/srobroek/agentic-packages/commit/ff2b7a2200fc88bcf39abafe9f73ed6f5d31e942))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/hooks-subagent-worktree-v0.1.0...hooks-subagent-worktree-v0.2.0) (2026-06-26)


### Features

* add hooks-subagent-worktree enforcement package ([#384](https://github.com/srobroek/agentic-packages/issues/384)) ([608d757](https://github.com/srobroek/agentic-packages/commit/608d7572168e06ae15788f7ed8f367f300ae0b74))
