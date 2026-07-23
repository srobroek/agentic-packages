---
name: example-agent
description: One- or two-sentence description of the subagent's job and when the
  main thread should delegate to it. This is what the router reads.
model: sonnet
effort: medium
permissionMode: acceptEdits
---

You are a focused subagent. State the role in the first paragraph: what this
agent owns, and the boundary it must not cross.

Describe the working method: which tools to prefer, which project conventions to
follow, and how to discover code (e.g. prefer semantic symbol tools, fall back
to grep and direct file inspection).

End with the required final-response contract so the main thread can consume the
result deterministically, for example:

Final response must include: changed files, verification commands and results,
risks or blockers, and any follow-up needed from the main thread.
