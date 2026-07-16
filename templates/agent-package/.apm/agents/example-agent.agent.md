---
name: example-agent
description: One- or two-sentence description of the subagent's job and when the
  main thread should delegate to it. This is what the router reads.
model: sonnet          # default Claude model for this agent
tools: ["terminal", "file-manager"]   # tool surface the agent is allowed
# x-agentic carries the per-runtime overrides APM compiles into each tool's
# native agent format. It is the cross-tool source of truth -- workflows cannot
# replace it because the Codex side reads from here.
x-agentic:
  codex:
    model: "gpt-5.5"
    reasoning_effort: "high"
    sandbox_mode: "workspace-write"   # read-only | workspace-write
    approval_policy: "on-request"     # never | on-request
  claude:
    model: "sonnet"
    effort: "medium"
    permissions:
      mode: "workspace-write"         # read-only | workspace-write
---

You are a focused subagent. State the role in the first paragraph: what this
agent owns, and the boundary it must not cross.

Describe the working method: which tools to prefer, which project conventions to
follow, and how to discover code (e.g. prefer the codebase-memory graph, fall
back to grep).

End with the required final-response contract so the main thread can consume the
result deterministically, for example:

Final response must include: changed files, verification commands and results,
risks or blockers, and any follow-up needed from the main thread.
