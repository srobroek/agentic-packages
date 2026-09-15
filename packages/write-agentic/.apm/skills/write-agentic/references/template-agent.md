Content policy: apply the shared rules in the parent `SKILL.md`; do not duplicate them in generated assets.
# Agent Template

`.apm/agents/<name>.agent.md` is mirrored to `agents/<name>.md` by the generator.
The description loads into every session's registry. It pays rent always.

```markdown
---
name: <kebab-name>
description: <max 25 words: what it does, when the parent should spawn it, and one distinguishing boundary. Pipeline-internal agents (only spawned by name): max 10 words.>
x-agentic:
  model: <haiku|sonnet|opus - cheapest tier the task tolerates; see steering-subagent-routing>
  effort: <low|medium|high|xhigh>
  # permissions / memory / maxTurns / background only when needed
---

You are <role, one sentence>. <Scope boundary, one sentence.>

MODE  (only for multi-mode agents)
<mode-a> -> <behavior>   <mode-b> -> <behavior>   (parent passes mode in prompt)

## Task

1. <imperative step>
2. <...>

## Rules

MUST <hard constraint>
DEFAULT <default>
NOT <boundary: what this agent must NOT do -> who does it instead>

## Output

L1 VERDICT: <ENUM|ENUM|ENUM> - one line why
   <section> - only if non-empty; evidence as path:line
CAP <N>w clean - <M>w with findings
MUST Never reprint code, diffs, file contents, or the caller's claim.
```

## Rules for authoring

MUST Verdict enums use CAPS.
MUST Every section is conditional.
MUST State the cap in the contract.

MUST Phrase the first-line rule imperatively: `Begin your reply with \`VERDICT:\``.

For scan and analysis agents, separate working and final messages:

- reasoning lives in working turns between tool calls
- the final message is only the report
- compose the report in one pass
- check the first line before sending

"L1" is notation. Never print it.

MUST Subagents never load steering. Inline every rule the agent needs.
Code economy and comment density come from SubagentStart inject.
Put task-specific rules in the body.

NOT Generic "how to be an agent" prose. The harness covers it.
DEFAULT Worked scenarios: max 1, only when the failure mode is non-obvious.
