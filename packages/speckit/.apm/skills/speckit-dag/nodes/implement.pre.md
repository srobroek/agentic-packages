# /speckit.implement — DEPRECATED

## Came from
- (legacy callers — this command is no longer the implementation path in this project)

## Preconditions
- HARD-DEPRECATED: /speckit.implement is deprecated in this project. Use /speckit.agent-assign.assign → /speckit.agent-assign.validate → /speckit.agent-assign.execute instead.

## Context absorbed from steering
- The agent-assign extension routes each task to a specialised sub-agent instead of running implementation in one generalist context. Benchmarks show meaningful quality gains; we've made it the project default.
