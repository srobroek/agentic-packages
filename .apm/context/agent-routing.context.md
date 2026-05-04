# Agent Routing

Agent definitions are authored once as `.apm/agents/*.agent.md`.

Each agent carries namespaced `x-agentic` frontmatter. The APM install step
creates runtime-native agent files; the `apm run patch-agents` finalizer then
normalizes runtime-specific metadata that APM cannot represent directly.

Codex patch fields:

- `model`
- `model_reasoning_effort`
- `sandbox_mode`

Claude patch fields:

- `model`
- `effort`
- `permissions`, when explicitly provided

Default routing:

- Simple coding and lightweight creation: `gpt-5.4-mini`, medium effort.
- Complex coding, review, and verification: `gpt-5.3-codex`, high effort.
- Main planning/orchestration remains the parent GPT-5.5 high/xhigh session.
