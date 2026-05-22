# /speckit.agent-assign.assign — before you run this

## Came from
- /speckit.checkpoint.commit (default — after the mid-cycle checkpoint)
- /speckit.tasks (acceptable if checkpoint was deferred)

## Preconditions
- HARD-MISSING: specs/<feat>/tasks.md

## Context absorbed from steering
- Scans `.claude/agents/` and `~/.claude/agents/` and matches tasks to specialised sub-agents. Review the proposed assignments before validate.
