# /speckit.agent-assign.validate — before you run this

## Came from
- /speckit.agent-assign.assign

## Preconditions
- HARD-MISSING: specs/<feat>/agent-assignments.md

## Context absorbed from steering
- Validates that referenced agents actually exist, that every task has an assignment, and that phase ordering is consistent. Failures route back to assign.
