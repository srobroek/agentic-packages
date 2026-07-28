# Subagent Fork Policy

LEGEND: Rules carry stable IDs (SF-n) cited by the enforcing hook.

subagent-fork-guard.py enforces SF-1..SF-2 on `PreToolUse:Agent`
(Codex `spawn_agent`; Claude Agent calls carry no `fork_turns` field, so the
guard is a no-op there).

- SF-1: `fork_turns="all"` -- and an *omitted* `fork_turns`, which the
  released Codex binary documents as equivalent to `"all"` (full-history
  fork) -- is denied. Forking the whole parent thread into a subagent burns
  tokens quadratically across a fan-out and leaks parent context into roles
  designed to receive a bounded brief.
- SF-2: numeric `fork_turns` above the maximum (default 3;
  `SUBAGENT_FORK_GUARD_MAX` overrides per-project) is denied. The legitimate
  "recent thread context explicitly required" case is the immediately
  preceding exchange; needing more is the signal to write a complete spawn
  brief instead.
- SF-3 (advisory, injected at SubagentStart and always-on in the main
  session): always execute with `fork_turns="none"` unless recent thread
  context is explicitly required; format the tool call as
  `spawn_agent(task_name="code-reviewer", fork_turns="none")`; put everything
  the subagent needs into the spawn prompt.

Why deny-not-ask: constitution III (hooks fail open, never stall autonomous
agents). A false deny costs one self-correcting retry with the corrected
format quoted in the reason; a false allow forks a large context tail.
