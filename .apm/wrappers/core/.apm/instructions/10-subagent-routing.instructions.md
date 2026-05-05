---
description: Model routing and verification policy for APM-managed subagents.
applyTo: "**/*"
---

# Subagent Routing

Use the main GPT-5.5 high/xhigh session for reasoning, planning, orchestration,
and verification.

Delegate implementation and creation work to project-installed agents when a
specialist agent matches the task. Prefer:

- `gpt-5.5` for high-risk judgment, planning, orchestration, review,
  verification, architecture, security, legal, data interpretation, and
  SpecKit task routing.
- `gpt-5.4` for frontend, UI, UX, browser-visible product work, and visual
  verification.
- `gpt-5.4-mini` for lightweight operational, lookup, synthesis, routing, and
  bounded non-code creation work.
- `gpt-5.3-codex` for complex or specialized implementation, migration,
  tests, and multi-file coding work.
- `gpt-5.3-codex-spark` for fast bounded code loops and mechanical
  implementation.

Every delegated result must be verified by the main session before handoff.
When planning, explicitly mark which steps are delegated and which can run in
parallel. See [agent routing details](../context/agent-routing.context.md).

When `apm.yml` contains `x-agentic.selected_agents`, treat that list as the
project's preferred active agent set. Use other installed agents only when the
selected set does not cover the task or the user explicitly asks for a different
specialist.
