# Changelog

## [3.2.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v3.1.0...orchestrate--v3.2.0) (2026-07-22)


### Features

* dispatch approved pull requests from signed webhook events ([#601](https://github.com/srobroek/agentic-packages/issues/601)) ([b244cfe](https://github.com/srobroek/agentic-packages/commit/b244cfe0e43f4aa0010ca352e518d18059da3246))

## [3.1.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v3.0.0...orchestrate--v3.1.0) (2026-07-21)


### Features

* **agents:** preserve model routing in workflow packages ([df86afc](https://github.com/srobroek/agentic-packages/commit/df86afc45f5c6da979e939aba1ed7f5fe2fcbc6a))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v2.0.0...orchestrate--v3.0.0) (2026-07-21)


### ⚠ BREAKING CHANGES

* share MCP backends through 1MCP

### Features

* share MCP backends through 1MCP ([4896601](https://github.com/srobroek/agentic-packages/commit/4896601ca0326762493f340526a97a341b98e24a))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v1.1.0...orchestrate--v2.0.0) (2026-07-20)


### ⚠ BREAKING CHANGES

* **orchestrate:** replace graph.py/ledger.py state store with beads (bd)

### Features

* merge beads-only orchestrate refactor ([ef11395](https://github.com/srobroek/agentic-packages/commit/ef11395608ed7e5164cd3da5c44a901956d5b1a8))
* **orchestrate:** replace graph.py/ledger.py state store with beads (bd) ([3d24b36](https://github.com/srobroek/agentic-packages/commit/3d24b363668d7287e2a4e94868fab7b2489a716b))


### Bug Fixes

* **orchestrate,steering-speckit:** tier vocabulary in references and pointer/context split for lint compliance ([5ebbf02](https://github.com/srobroek/agentic-packages/commit/5ebbf02029869f53a3f409d795ad87ce9f960899))
* **orchestrate:** agent descriptions under cap with output contracts; regenerate marketplace with CI-pinned apm ([4ea3048](https://github.com/srobroek/agentic-packages/commit/4ea3048abfbdeb4c861e7642edef0decd5351440))
* **probes:** unknown is not clean, and count claims for the git user ([13660e9](https://github.com/srobroek/agentic-packages/commit/13660e9f66dcf181b031b24198a6c696c1b2f3c1))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v1.0.0...orchestrate--v1.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v0.3.0...orchestrate--v1.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* **steering:** Wave 4 steering rewrites — pragmatic, code-economy, dedup, language compression, orchestrate fixes

### Features

* **steering:** Wave 4 steering rewrites — pragmatic, code-economy, dedup, language compression, orchestrate fixes ([1412eaf](https://github.com/srobroek/agentic-packages/commit/1412eafea2ec018655d73d353337feb918dd27f0))


### Refactors

* **orchestrate:** surgical fixes from review pass ([c0fc174](https://github.com/srobroek/agentic-packages/commit/c0fc174b3e9d8fccd7842eaea2e5ea9cf25bcb58))

## [0.3.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v0.2.0...orchestrate--v0.3.0) (2026-07-05)


### Features

* orchestrate comms protocol v2 with verified injection, concurrency-safe run scripts, and message linting ([#484](https://github.com/srobroek/agentic-packages/issues/484)) ([8c9cce2](https://github.com/srobroek/agentic-packages/commit/8c9cce2fbecd0f31aa2b254a7bd4d03392ce2166))
* orchestrator-only-coordinates rule, terse agent reasoning/output, pragmatic terseness + comment guidance ([#483](https://github.com/srobroek/agentic-packages/issues/483)) ([446b624](https://github.com/srobroek/agentic-packages/commit/446b62498a0e96e5b6663a3977dbd931b64c8d41))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/orchestrate--v0.1.0...orchestrate--v0.2.0) (2026-07-05)


### Features

* **orchestrate:** multi-agent orchestration skill with DAG, ledger, and bundled agents ([#479](https://github.com/srobroek/agentic-packages/issues/479)) ([cb184d3](https://github.com/srobroek/agentic-packages/commit/cb184d3ee33c67e479b432e0a4f48f9972041242))

## 0.1.0

Initial release. Multi-agent orchestration skill: role-to-model routing,
persistent vs ephemeral subagents vs agent-teams, worktree isolation, a
deterministic stdlib task DAG (`graph.py`), a forensic JSONL run ledger
(`ledger.py`), agent discovery (`discover-agents.py`), and a merge/CI conflict
probe (`conflict-probe.sh`). Bundled agents: `workflow-coder`,
`integration-gatekeeper`, `ledger-scribe`.
