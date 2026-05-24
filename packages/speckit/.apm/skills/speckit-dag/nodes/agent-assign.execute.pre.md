# /speckit.agent-assign.execute — before you run this

## Came from
- /speckit.agent-assign.validate (preferred)
- /speckit.agent-assign.assign (only if user explicitly skips validation)

## Preconditions
- HARD-MISSING: specs/<feat>/tasks.md
- HARD-MISSING: specs/<feat>/agent-assignments.md
- SOFT: every agent referenced in agent-assignments.md exists in .claude/agents/ or ~/.claude/agents/

## Context absorbed from steering
- Replaces the deprecated `/speckit.implement` with per-task sub-agent execution. Each agent runs in its own context.
