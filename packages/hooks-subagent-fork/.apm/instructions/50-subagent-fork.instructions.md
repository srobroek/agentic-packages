---
description: Always-loaded fork_turns discipline for subagent spawns; the fork guard denies "all" and large values.
applyTo: "**/*"
---

Subagent spawns:

- Always execute with fork_turns="none" unless recent thread context is
  explicitly required.
- Format the tool call: spawn_agent(task_name="code-reviewer", fork_turns="none")

For the enforced limits, read
[subagent fork policy](../context/subagent-fork.subagent-fork-index.context.md).
