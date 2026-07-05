# Changelog

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
