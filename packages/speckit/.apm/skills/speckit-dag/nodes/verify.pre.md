# /speckit.verify — before you run this

## Came from
- /speckit.verify-tasks (default)
- /speckit.agent-assign.execute (acceptable for short cycles)
- /speckit.bugfix.patch (post-bugfix verification)
- /speckit.tinyspec.implement (tinyspec cycle)

## Preconditions
- HARD-MISSING: specs/<feat>/plan.md

## Context absorbed from steering
- Validates implementation against the plan. If the diff doesn't address the plan, route back to agent-assign or refine.update.
